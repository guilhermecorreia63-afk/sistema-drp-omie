# -*- coding: utf-8 -*-
"""
inteligencia_matriz.py - Motor de Inteligência de Produção e Compras (Matriz v2)
=================================================================================
- Filtragem automática da Blacklist
- Lote Mínimo específico por regra de Família:
    - ESPIRITUALIDADE - EDIÇÕES: 500 un
    - CAMISAS / VESTUÁRIO: 20 un (por grade)
    - Demais famílias (Ícones, Bíblias, Acessórios, Philippos, Escuta, etc.): 0 un (Sem lote limite)
    - Suporte a ajuste manual customizado de Lote Mínimo por produto
- Incorporação de Remessas/Transferências enviadas ao CD_SP na demanda da Matriz
- Detalhamento completo do cálculo para Modal de Diagnóstico
- Ruptura isolada de grade (PP..3G e A3..A7)
"""

import json
import os
import re
from typing import Dict, List, Any

import database as db

# Tamanhos de Grade Conhecidos
TAMANHOS_VESTUARIO = ["PP", "P", "M", "G", "GG", "XG", "2G", "3G"]
TAMANHOS_ICONES = ["A3", "A4", "A5", "A6", "A7"]

# Caminho para arquivo de sobreposição manual de lote mínimo
CAMINHO_LOTES_MANUAIS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'lotes_minimos_custom.json')

def carregar_lotes_manuais() -> Dict[str, int]:
    if os.path.exists(CAMINHO_LOTES_MANUAIS):
        try:
            with open(CAMINHO_LOTES_MANUAIS, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def salvar_lote_manual(sku: str, lote: int) -> bool:
    lotes = carregar_lotes_manuais()
    lotes[sku.strip()] = max(0, int(lote))
    try:
        os.makedirs(os.path.dirname(CAMINHO_LOTES_MANUAIS), exist_ok=True)
        with open(CAMINHO_LOTES_MANUAIS, 'w', encoding='utf-8') as f:
            json.dump(lotes, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[INTELIGENCIA] Erro ao salvar lote manual: {e}")
        return False

def extrair_base_e_tamanho(nome_prod: str) -> tuple[str, str]:
    nome_up = (nome_prod or "").upper().strip()
    
    for tam in sorted(TAMANHOS_VESTUARIO, key=len, reverse=True):
        pattern = r'(?:\s+|-|_)' + re.escape(tam) + r'(?:\s+|$)'
        if re.search(pattern, nome_up):
            base = re.sub(pattern, ' ', nome_up).strip()
            return base, tam

    for tam in sorted(TAMANHOS_ICONES, key=len, reverse=True):
        pattern = r'(?:\s+|-|_)' + re.escape(tam) + r'(?:\s+|$)'
        if re.search(pattern, nome_up):
            base = re.sub(pattern, ' ', nome_up).strip()
            return base, tam

    return nome_up, ""

def obter_remessas_por_sku() -> Dict[str, float]:
    """
    Calcula a soma de remessas/transferências enviadas pela Matriz para o CD_SP
    nos últimos 30 dias a partir da tabela drp_remessas.
    """
    remessas_map = {}
    try:
        df = db.executar_query("SELECT itens_json, status_transito, ultima_atualizacao FROM drp_remessas")
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                st = (row.get('status_transito') or '').upper()
                # Considera remessas ativas (Pendente, Coletado, Em Transporte, Entregue)
                if st in ['EM_TRANSPORTE', 'COLETADO', 'ENTREGUE', 'PENDENTE']:
                    itens_str = row.get('itens_json')
                    if itens_str and isinstance(itens_str, str) and len(itens_str) > 5:
                        try:
                            itens = json.loads(itens_str)
                            for it in itens:
                                prod = it.get('produto') or it
                                sku = str(it.get('cCodItInt') or prod.get('cCodItInt') or prod.get('cCodigo') or prod.get('codigo_produto') or prod.get('cSKU') or '').strip()
                                qtd = float(it.get('nQtde') or it.get('nQtd') or it.get('quantidade') or prod.get('nQtde') or prod.get('nQtd') or 0)
                                if sku and qtd > 0:
                                    remessas_map[sku] = remessas_map.get(sku, 0.0) + qtd
                                    sku_pad = sku.padStart(6, '0') if hasattr(sku, 'padStart') else str(sku).zfill(6)
                                    remessas_map[sku_pad] = remessas_map.get(sku_pad, 0.0) + qtd
                        except Exception:
                            pass
    except Exception as e:
        print(f"[INTELIGENCIA] Erro ao carregar remessas por SKU: {e}")
    return remessas_map

def calcular_inteligencia_matriz(produtos: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not produtos:
        return {"produtos": [], "kpis": {}, "familias": []}

    # 1. Carregar e Normalizar Blacklist
    blacklist_raw = set()
    try:
        blacklist_raw = db.obter_blacklist()
    except Exception:
        pass

    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'blacklist.json')
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    blacklist_raw.update(data)
        except Exception:
            pass

    blacklist_norm = set()
    for item in blacklist_raw:
        s = str(item).strip().upper()
        if s:
            blacklist_norm.add(s)
            blacklist_norm.add(s.zfill(6))
            digits = re.sub(r'[^0-9]', '', s)
            if digits:
                blacklist_norm.add(digits)
                blacklist_norm.add(digits.zfill(6))
                blacklist_norm.add(f"PRD{digits.zfill(5)}")
                blacklist_norm.add(f"PRD{digits.zfill(6)}")

    # 2. Carregar Lotes Manuais Customizados
    lotes_manuais = carregar_lotes_manuais()

    # 3. Carregar Remessas CD_SP
    remessas_cd_sp = obter_remessas_por_sku()

    # 4. Filtrar produtos fora da Blacklist e fora de COMBOS / KITS (100% de exclusão)
    produtos_validos = []
    for p in produtos:
        sku = str(p.get("sku", "")).strip().upper()
        nome = (p.get("nome") or p.get("descricao") or "").strip().upper()
        fam = (p.get("familia") or "").strip().upper()

        # Filtrar COMBOS, KITS e PRESENTE DA FAMÍLIA (não entram na reposição/análise)
        is_combo = (
            "COMBO" in fam or "COMBOS" in fam or
            "COMBO" in nome or "COMBOS" in nome or
            "KIT" in fam or "KITS" in fam or
            "CONJUNTO" in fam or "CONJUNTO" in nome or
            "PRESENTE DA FAM" in nome
        )
        if is_combo:
            continue

        sku_pad = sku.zfill(6)
        digits = re.sub(r'[^0-9]', '', sku)
        digits_pad = digits.zfill(6) if digits else ""

        is_blacklisted = (
            sku in blacklist_norm or
            sku_pad in blacklist_norm or
            (digits and digits in blacklist_norm) or
            (digits_pad and digits_pad in blacklist_norm) or
            (digits_pad and f"PRD{digits_pad}" in blacklist_norm)
        )
        if is_blacklisted:
            continue
        produtos_validos.append(p)

    # 5. Agrupar produtos por Família para Curva ABC Relativa
    familias_map: Dict[str, List[Dict[str, Any]]] = {}
    for p in produtos_validos:
        fam = (p.get("familia") or "OUTROS").strip().upper()
        if fam not in familias_map:
            familias_map[fam] = []
        familias_map[fam].append(p)

    produtos_analisados = []
    tot_rupturas_isoladas = 0
    tot_classe_a_alta = 0
    tot_risco_encalhe = 0

    # 6. Processar cada família
    for fam_nome, prods_fam in familias_map.items():
        # Calcular demanda total da Matriz = Vendas Diretas Matriz Geral + Remessas para CD_SP
        for p in prods_fam:
            sku = str(p.get("sku", "")).strip()
            sku_pad = sku.zfill(6)
            rem_qtd = remessas_cd_sp.get(sku, 0.0) or remessas_cd_sp.get(sku_pad, 0.0)
            
            v30_direto = float(p.get("vendas_geral_30d") if p.get("vendas_geral_30d") is not None else (p.get("vendas_sul_sudeste_30d") or p.get("vendas_30d") or 0.0))
            v60_direto = float(p.get("vendas_geral_60d") if p.get("vendas_geral_60d") is not None else (p.get("vendas_sul_sudeste_60d") or p.get("vendas_60d") or 0.0))
            v90_direto = float(p.get("vendas_geral_90d") if p.get("vendas_geral_90d") is not None else (p.get("vendas_sul_sudeste_90d") or p.get("vendas_90d") or 0.0))

            # Separação exata mês a mês (30d recentes, 31-60d, 61-90d)
            m3_direto = v30_direto
            m2_direto = max(0.0, v60_direto - v30_direto)
            m1_direto = max(0.0, v90_direto - v60_direto)

            m3_total = m3_direto + rem_qtd
            m2_total = m2_direto
            m1_total = m1_direto

            p["_demanda_30d"] = m3_total
            p["remessas_cd_sp_30d"] = rem_qtd
            p["_m3_total"] = m3_total
            p["_m2_total"] = m2_total
            p["_m1_total"] = m1_total
            p["_m3_direto"] = m3_direto
            p["_m2_direto"] = m2_direto
            p["_m1_direto"] = m1_direto

        # Ordenar produtos da família pela demanda/faturamento total da Matriz
        prods_sorted = sorted(
            prods_fam,
            key=lambda x: (x["_demanda_30d"] * float(x.get("valor_unitario", 1.0))),
            reverse=True
        )

        tot_val_fam = sum(p["_demanda_30d"] * float(p.get("valor_unitario", 1.0)) for p in prods_sorted)
        tot_qtd_fam = sum(p["_demanda_30d"] for p in prods_sorted)
        n_prods = len(prods_sorted)

        acum_val = 0.0
        for idx, p in enumerate(prods_sorted):
            sku = str(p.get("sku", "")).strip()
            val_p = p["_demanda_30d"] * float(p.get("valor_unitario", 1.0))
            acum_val += val_p
            pct_acum = (acum_val / tot_val_fam) if tot_val_fam > 0 else (idx + 1) / n_prods

            # Definir Classe ABC da Família
            if pct_acum <= 0.80 or (n_prods <= 3 and idx == 0):
                classe_abc = "A"
            elif pct_acum <= 0.95 or (n_prods <= 5 and idx <= 1):
                classe_abc = "B"
            else:
                classe_abc = "C"

            p_copia = dict(p)
            p_copia["classe_abc_familia"] = classe_abc

            # Regras Específicas de Lote Mínimo (Por Família ou pelo Nome do Produto)
            fam_up = fam_nome.upper()
            nome_up = (p.get("nome") or p.get("descricao") or "").upper()
            is_camisa = (
                "CAMISA" in fam_up or "VESTUARIO" in fam_up or "BLUSA" in fam_up or "BABYLOOK" in fam_up or
                "CAMISA" in nome_up or "BLUSA" in nome_up or "BABYLOOK" in nome_up or "CAMISETA" in nome_up
            )

            if sku in lotes_manuais:
                lote_minimo = lotes_manuais[sku]
                origem_lote = "Manual"
            elif is_camisa:
                lote_minimo = 20
                origem_lote = "Padrão Camisas (20 un)"
            elif "ESPIRITUALIDADE" in fam_up and ("EDIÇ" in fam_up or "EDIC" in fam_up):
                lote_minimo = 500
                origem_lote = "Padrão Edições (500 un)"
            else:
                lote_minimo = 0
                origem_lote = "Sem Lote Mínimo"

            # Tendência de Vendas Mês a Mês (Mês 3 Atual vs Média dos Meses M1 e M2)
            m3 = p["_m3_total"]
            m2 = p["_m2_total"]
            m1 = p["_m1_total"]
            media_m1_m2 = (m1 + m2) / 2.0

            variacao_pct = 0.0
            if media_m1_m2 > 0:
                variacao_pct = round(((m3 - media_m1_m2) / media_m1_m2) * 100, 1)

            if m3 > (media_m1_m2 * 1.20) and m3 >= 5:
                tendencia = "Acelerando 🔥"
                if classe_abc == "A":
                    tot_classe_a_alta += 1
            elif m3 < (media_m1_m2 * 0.70) and media_m1_m2 > 2:
                tendencia = "Desacelerando 📉"
            else:
                tendencia = "Estável ➡️"

            p_copia["tendencia_vendas"] = tendencia

            # Cobertura c/ Lote Mínimo baseada no Estoque DISPONÍVEL (Saldo Livre)
            v30_diaria = max(0.033, m3 / 30.0)
            est_matriz_bruto = float(p.get("matriz", 0) or 0)
            est_matriz_res = float(p.get("matriz_reservado", 0) or 0)
            est_matriz_disp = p.get("matriz_disponivel")
            if est_matriz_disp is None:
                est_matriz_disp = max(0.0, est_matriz_bruto - est_matriz_res)
            
            est_matriz = int(est_matriz_disp) # Saldo livre/disponível
            p_copia["matriz"] = est_matriz # Usar saldo disponível no card e tabela
            
            meses_cobertura_atual = round((est_matriz / (v30_diaria * 30.0)), 1) if m3 > 0 else (99.0 if est_matriz > 0 else 0.0)
            
            if lote_minimo > 0:
                meses_cobertura_lote = round((lote_minimo / (v30_diaria * 30.0)), 1) if m3 > 0 else 99.0
            else:
                meses_cobertura_lote = 0.0

            p_copia["lote_minimo"] = lote_minimo
            p_copia["origem_lote"] = origem_lote
            p_copia["meses_cobertura_atual"] = meses_cobertura_atual
            p_copia["meses_cobertura_lote"] = meses_cobertura_lote

            risco_encalhe = False
            if lote_minimo > 0 and meses_cobertura_lote > 24 and tendencia == "Desacelerando 📉":
                risco_encalhe = True
                tot_risco_encalhe += 1

            p_copia["risco_encalhe"] = risco_encalhe

            # Explicação textual amigável do status de tendência
            if tendencia == "Acelerando 🔥":
                explicacao_status = f"Acelerando 🔥: A demanda do mês recente ({round(m3)} un) superou a média dos 2 meses anteriores ({round(media_m1_m2, 1)} un/mês) em +{variacao_pct}%. O produto está em alta rotação."
            elif tendencia == "Desacelerando 📉":
                explicacao_status = f"Desacelerando 📉: A demanda do mês recente ({round(m3)} un) caiu {variacao_pct}% em relação à média recente ({round(media_m1_m2, 1)} un/mês). Alerta para evitar lote excessivo."
            else:
                explicacao_status = f"Estável ➡️: A demanda recente ({round(m3)} un) está alinhada à média dos meses anteriores ({round(media_m1_m2, 1)} un/mês) com variação de {variacao_pct}%."

            # Detalhamento completo do cálculo para o Modal de Diagnóstico
            p_copia["detalhes_calculo"] = {
                "sku": sku,
                "nome": p.get("nome", ""),
                "familia": fam_nome,
                "classe_abc": classe_abc,
                "rank_familia": idx + 1,
                "total_produtos_familia": n_prods,
                "faturamento_prod_30d": round(val_p, 2),
                "faturamento_familia_30d": round(tot_val_fam, 2),
                "share_familia_pct": round((val_p / tot_val_fam * 100) if tot_val_fam > 0 else 0.0, 2),
                "pct_acumulado_familia": round(pct_acum * 100, 1),
                "vendas_diretas_30d": float(m3_direto),
                "remessas_cd_sp_30d": float(p.get("remessas_cd_sp_30d", 0)),
                "demanda_total_matriz_30d": round(m3, 1),
                "m3_total": round(m3, 1),
                "m2_total": round(m2, 1),
                "m1_total": round(m1, 1),
                "m3_direto": round(m3_direto, 1),
                "m2_direto": round(m2_direto, 1),
                "m1_direto": round(m1_direto, 1),
                "media_mensal_90d": round(media_m1_m2, 1),
                "variacao_tendencia_pct": variacao_pct,
                "tendencia": tendencia,
                "explicacao_status": explicacao_status,
                "estoque_matriz": est_matriz,
                "lote_minimo": lote_minimo,
                "origem_lote": origem_lote,
                "meses_cobertura_atual": meses_cobertura_atual,
                "meses_cobertura_lote": meses_cobertura_lote
            }

            produtos_analisados.append(p_copia)

    # 7. Agrupamento de Grades (Vestuário e Ícones) para Ruptura Isolada
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
            v30 = p.get("_demanda_30d", 0)
            abc = p.get("classe_abc_familia", "C")
            risco = p.get("risco_encalhe", False)

            if st_matriz <= 5 and v30 >= 10 and abc in ["A", "B"]:
                p["acao_recomendada"] = "🟢 Prioridade de Produção/Compra (Classe A/B)"
                p["status_grade"] = "🚨 Ruptura / Estoque Baixo"
            elif risco:
                p["acao_recomendada"] = "🔴 Não Repor em Lote Padrão (Risco Encalhe)"
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
