# -*- coding: utf-8 -*-
"""
inteligencia_matriz.py - Motor de Inteligência de Produção e Compras (Matriz)
=============================================================================
- Curva ABC por Família (Classe A, B, C relativa dentro da família)
- Análise de Grade para Rupturas Isoladas (Vestuário: PP..3G, Ícones: A3..A7)
- Ritmo e Tendência de Vendas (Acelerando, Estável, Desacelerando)
- Análise de Lote Mínimo & Anos/Meses de Cobertura
- Ação Recomendada de Reposição/Produção
"""

import json
import os
import re
from typing import Dict, List, Any

# Tamanhos de Grade Conhecidos
TAMANHOS_VESTUARIO = ["PP", "P", "M", "G", "GG", "XG", "2G", "3G"]
TAMANHOS_ICONES = ["A3", "A4", "A5", "A6", "A7"]

def extrair_base_e_tamanho(nome_prod: str) -> tuple[str, str]:
    """
    Extrai o nome base do modelo e o tamanho do produto (Vestuário ou Ícones).
    Ex: "CAMISA DEUS E FIEL M" -> ("CAMISA DEUS E FIEL", "M")
    Ex: "ICONE NOSSA SENHORA A4" -> ("ICONE NOSSA SENHORA", "A4")
    """
    nome_up = (nome_prod or "").upper().strip()
    
    # Check Vestuário
    for tam in sorted(TAMANHOS_VESTUARIO, key=len, reverse=True):
        pattern = r'(?:\s+|-|_)' + re.escape(tam) + r'(?:\s+|$)'
        if re.search(pattern, nome_up):
            base = re.sub(pattern, ' ', nome_up).strip()
            return base, tam

    # Check Ícones
    for tam in sorted(TAMANHOS_ICONES, key=len, reverse=True):
        pattern = r'(?:\s+|-|_)' + re.escape(tam) + r'(?:\s+|$)'
        if re.search(pattern, nome_up):
            base = re.sub(pattern, ' ', nome_up).strip()
            return base, tam

    return nome_up, ""

def calcular_inteligencia_matriz(produtos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Executa o cálculo completo de inteligência para os produtos da Matriz.
    """
    if not produtos:
        return {"produtos": [], "kpis": {}, "familias": []}

    # 1. Agrupar produtos por Família para Curva ABC Relativa
    familias_map: Dict[str, List[Dict[str, Any]]] = {}
    for p in produtos:
        fam = (p.get("familia") or "OUTROS").strip().upper()
        if fam not in familias_map:
            familias_map[fam] = []
        familias_map[fam].append(p)

    produtos_analisados = []
    tot_rupturas_isoladas = 0
    tot_classe_a_alta = 0
    tot_risco_encalhe = 0

    # 2. Processar cada família separadamente (Curva ABC por Família)
    for fam_nome, prods_fam in familias_map.items():
        # Ordenar produtos da família pelo volume de vendas (ou faturamento) últimos 30d/60d
        prods_sorted = sorted(
            prods_fam,
            key=lambda x: (x.get("vendas_geral_30d", 0) * x.get("valor_unitario", 1.0)),
            reverse=True
        )

        tot_vendas_fam = sum(p.get("vendas_geral_30d", 0) for p in prods_sorted)
        tot_val_fam = sum(p.get("vendas_geral_30d", 0) * p.get("valor_unitario", 1.0) for p in prods_sorted)

        acum_val = 0.0
        n_prods = len(prods_sorted)

        for idx, p in enumerate(prods_sorted):
            val_p = p.get("vendas_geral_30d", 0) * p.get("valor_unitario", 1.0)
            acum_val += val_p
            pct_acum = (acum_val / tot_val_fam) if tot_val_fam > 0 else (idx + 1) / n_prods

            # Definir Classe ABC por Família
            if pct_acum <= 0.80 or (n_prods <= 3 and idx == 0):
                classe_abc = "A"
            elif pct_acum <= 0.95 or (n_prods <= 5 and idx <= 1):
                classe_abc = "B"
            else:
                classe_abc = "C"

            p_copia = dict(p)
            p_copia["classe_abc_familia"] = classe_abc

            # 3. Tendência de Vendas (30d vs Média 90d/180d)
            v30 = p.get("vendas_geral_30d", 0)
            v90 = p.get("vendas_geral_90d", 0)
            v_media_mensal_90 = v90 / 3.0 if v90 > 0 else 0.0

            if v30 > (v_media_mensal_90 * 1.25) and v30 >= 5:
                tendencia = "Acelerando 🔥"
                if classe_abc == "A":
                    tot_classe_a_alta += 1
            elif v30 < (v_media_mensal_90 * 0.70) and v_media_mensal_90 > 2:
                tendencia = "Desacelerando 📉"
            else:
                tendencia = "Estável ➡️"

            p_copia["tendencia_vendas"] = tendencia

            # 4. Lote Mínimo & Anos/Meses de Cobertura
            fam_up = fam_nome.upper()
            if "VESTUARIO" in fam_up or "CAMISA" in fam_up or "BLUSA" in fam_up:
                lote_minimo = 100
            elif "ICONE" in fam_up or "QUADRO" in fam_up:
                lote_minimo = 50
            else:
                lote_minimo = 500

            v30_diaria = max(0.033, v30 / 30.0)
            est_matriz = p.get("matriz", 0)
            meses_cobertura_atual = round((est_matriz / (v30_diaria * 30.0)), 1) if v30 > 0 else (99.0 if est_matriz > 0 else 0.0)
            meses_cobertura_lote = round((lote_minimo / (v30_diaria * 30.0)), 1) if v30 > 0 else 99.0

            p_copia["lote_minimo"] = lote_minimo
            p_copia["meses_cobertura_atual"] = meses_cobertura_atual
            p_copia["meses_cobertura_lote"] = meses_cobertura_lote

            risco_encalhe = False
            if meses_cobertura_lote > 24 and tendencia == "Desacelerando 📉":
                risco_encalhe = True
                tot_risco_encalhe += 1

            p_copia["risco_encalhe"] = risco_encalhe

            produtos_analisados.append(p_copia)

    # 5. Agrupamento de Grades (Vestuário e Ícones) para Ruptura Isolada
    modelos_grade: Dict[str, List[Dict[str, Any]]] = {}
    for p in produtos_analisados:
        base, tam = extrair_base_e_tamanho(p.get("nome", ""))
        p["modelo_base"] = base
        p["tamanho_grade"] = tam
        if tam:
            if base not in modelos_grade:
                modelos_grade[base] = []
            modelos_grade[base].append(p)

    for base, itens in modelos_grade.items():
        if len(itens) < 2:
            continue
        
        tam_com_estoque = [i for i in itens if i.get("matriz", 0) > 5]
        tam_zerados = [i for i in itens if i.get("matriz", 0) <= 2]

        if len(tam_zerados) > 0 and len(tam_com_estoque) > 0:
            # Temos Ruptura Isolada!
            tamanhos_zerados_str = ", ".join(i.get("tamanho_grade") for i in tam_zerados)
            for i in itens:
                i["status_grade"] = f"⚠️ Ruptura Isolada ({tamanhos_zerados_str})"
                if i in tam_zerados:
                    i["acao_recomendada"] = f"🟢 Produzir Apenas Tam. {i.get('tamanho_grade')}"
                    tot_rupturas_isoladas += 1
                else:
                    i["acao_recomendada"] = "🟡 Grade com Saldo (Aguardar Consumo)"
        elif len(tam_zerados) == len(itens):
            for i in itens:
                i["status_grade"] = "🔴 Ruptura Total da Grade"
                i["acao_recomendada"] = "🟢 Avaliar Reposição da Coleção Inteira"
        else:
            for i in itens:
                i["status_grade"] = "✅ Grade Equilibrada"
                if i.get("meses_cobertura_atual", 0) < 1.0 and i.get("classe_abc_familia") in ["A", "B"]:
                    i["acao_recomendada"] = "🟢 Reposição Recomendada"
                else:
                    i["acao_recomendada"] = "⚪ Saldo Adequado"

    # Preencher ação recomendada para itens sem grade definida
    for p in produtos_analisados:
        if "acao_recomendada" not in p:
            st_matriz = p.get("matriz", 0)
            v30 = p.get("vendas_geral_30d", 0)
            abc = p.get("classe_abc_familia", "C")
            risco = p.get("risco_encalhe", False)

            if st_matriz <= 5 and v30 >= 10 and abc in ["A", "B"]:
                p["acao_recomendada"] = "🟢 Prioridade de Produção/Compra (Classe A/B)"
                p["status_grade"] = "🚨 Ruptura / Estoque Baixo"
            elif risco:
                p["acao_recomendada"] = "🔴 Não Repor em Lote Padrão (Cauda Longa / Risco Encalhe)"
                p["status_grade"] = "⚠️ Desacelerando"
            elif st_matriz > 50 and v30 < 5:
                p["acao_recomendada"] = "🟡 Excesso / Baixa Rotação (Sem Ação)"
                p["status_grade"] = "📦 Saldo Suficiente"
            else:
                p["acao_recomendada"] = "⚪ Saldo Normal"
                p["status_grade"] = "✅ Normal"

    kpis = {
        "tot_produtos": len(produtos_analisados),
        "tot_rupturas_isoladas": tot_rupturas_isoladas,
        "tot_classe_a_alta": tot_classe_a_alta,
        "tot_risco_encalhe": tot_risco_encalhe,
        "familias": sorted(list(familias_map.keys()))
    }

    return {
        "produtos": produtos_analisados,
        "kpis": kpis,
        "familias": sorted(list(familias_map.keys()))
    }
