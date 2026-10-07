# -*- coding: utf-8 -*-
"""
controle_drp.py - Módulo Principal do DRP (Matriz / CD_SP)
==========================================================
Cálculo de estoque mínimo variável, status colorido,
gestão de blacklist, cálculo de frete por faixa de peso,
geração de PDF fiscal, suporte à Marca do produto e consulta ao Turso DB.

Idioma: Português do Brasil (PT-BR)
"""

from __future__ import annotations

import math
import os
from typing import List, Dict, Any, Tuple, Set
from datetime import datetime, timedelta
import pandas as pd

import database as db

# UFs das Regiões Sul e Sudeste
UFS_SUL_SUDESTE = {"SP", "RJ", "MG", "ES", "PR", "SC", "RS"}

# Tabela de Frete (Fortaleza)
FRETE_TABELA = [
    (0.01, 2.00, 11.50, "1 Cx Pequena"),
    (2.001, 6.00, 20.00, "1 Cx Pequena"),
    (6.001, 10.499, 25.00, "1 Cx Média"),
    (10.500, 16.499, 35.00, "1 Cx Grande"),
    (16.500, 31.000, 50.00, "2 Cx Grandes"),
    (31.500, 48.000, 60.00, "3 Cx Grandes"),
    (48.500, 64.000, 65.00, "4 Cx Grandes"),
    (64.500, 80.000, 73.00, "5 Cx Grandes"),
    (80.500, 96.000, 81.00, "6 Cx Grandes"),
    (96.500, 112.000, 89.00, "7 Cx Grandes"),
    (112.500, 128.000, 97.00, "8 Cx Grandes"),
    (128.500, 144.000, 105.00, "10 Cx Grandes"),
]

# Dados Fiscais de Remessa
CLIENTE_CODIGO_OMIE = 2216843393
CLIENTE_CNPJ = "07.044.456/0092-30"
CLIENTE_CNPJ_LIMPO = "07044456009230"
CLIENTE_NOME_FANTASIA = "COMUNIDADE CATOLICA SHALOM GUARULHOS MACEDO"
TRANSPORTADORA_NOME = "TRANSLATINO"
TRANSPORTADORA_CNPJ = "07.655.778/0001-88"
CFOP_REMESSA = "6152"
DESCRICAO_FISCAL_CFOP = "Remessa CD portal. CFOP 6.152. Transferencia de estoque entre CD."
NATUREZA_OPERACAO = "Remessa Transferência de Estoque - entre CD"
TIPO_FRETE = 0  # CIF
ESPECIE_VOLUMES = "VOLUMES"



class ControleDRP:
    """Classe para regras de negócio e cálculos do DRP."""

    def __init__(self):
        pass

    def calcular_frete(self, peso_bruto: float) -> Tuple[float, int, str]:
        """Calcula o valor do frete e a quantidade de volumes."""
        peso = max(0.01, float(peso_bruto))
        volumes = math.ceil(peso / 16.0)
        volumes = max(1, volumes)

        valor = 0.0
        desc_faixa = ""

        for min_p, max_p, val, desc in FRETE_TABELA:
            if min_p <= peso <= max_p:
                valor = val
                desc_faixa = desc
                break

        if valor == 0.0:
            if peso <= 144.0:
                valor = 105.00
                desc_faixa = "10 Cx Grandes"
            else:
                peso_excedente = peso - 144.0
                blocos_extras = math.ceil(peso_excedente / 16.0)
                valor = 105.00 + (blocos_extras * 8.00)
                desc_faixa = f"Extrapolação > 144kg ({volumes} Cx Grandes)"

        return round(valor, 2), volumes, desc_faixa

    def extrair_marca(self, r: pd.Series) -> str:
        """Retorna a marca real cadastrada no produto no Omie ERP (Informações Adicionais -> Marca)."""
        if 'marca' in r and pd.notna(r['marca']) and str(r['marca']).strip():
            return str(r['marca']).strip()
        
        nome = (str(r.get('nome', '')) or "").upper()
        fam = (str(r.get('familia', '')) or "").upper()

        if "SHALOM" in nome or "SHALOM" in fam:
            return "Edições Shalom"
        elif "AVE MARIA" in nome:
            return "Editora Ave Maria"
        elif "PEREGRINO" in nome:
            return "Edições Peregrino"
        elif "JERUSALEM" in nome:
            return "Paulus / Jerusalém"
        elif "CARLO ACUTIS" in nome:
            return "Shalom Artes"
        elif "CANCAO NOVA" in nome or "CANÇÃO NOVA" in nome:
            return "Canção Nova"
        elif "PAULINAS" in nome:
            return "Paulinas"
        elif "PAULUS" in nome:
            return "Paulus"
        elif fam in ["VESTUARIO", "CAMISAS", "VESTUÁRIO"]:
            return "Shalom Use"
        elif fam in ["ACESSORIOS", "ACESSÓRIOS", "TERÇO"]:
            return "Shalom Artes"
        else:
            return "GERAL"

    def carregar_dados_turso(self) -> List[Dict[str, Any]]:
        """
        Carrega produtos do Turso/SQLite mapeados e agrupados por SKU com a coluna Marca real do Omie ERP.
        """
        sql_produtos = "SELECT id_produto, sku, descricao as nome, familia, COALESCE(peso_bruto, 0.5) as peso_kg FROM produtos_cadastro"
        sql_sp = "SELECT id_produto, COALESCE(saldo_disponivel, 0) as cd_sp FROM estoque_sp"
        sql_matriz = "SELECT id_produto, COALESCE(saldo_disponivel, 0) as matriz FROM estoque_matriz"
        sql_vendas = "SELECT id_produto, uf_destino, quantidade, data_pedido FROM vendas_historico"

        try:
            df_prod = db.executar_query(sql_produtos)
            if df_prod is None or df_prod.empty:
                return self.obter_dados_base()

            id_para_sku = {}
            sku_info = {}

            for _, r in df_prod.iterrows():
                id_p = r['id_produto']
                raw_sku = str(r['sku']).strip() if pd.notna(r['sku']) and str(r['sku']).strip() else f"ID-{id_p}"
                id_para_sku[id_p] = raw_sku

                nome_prod = str(r['nome']) if pd.notna(r['nome']) else f"Produto {raw_sku}"
                fam_prod = str(r['familia']) if pd.notna(r['familia']) else "GERAL"
                marca_prod = self.extrair_marca(r)

                if raw_sku not in sku_info:
                    sku_info[raw_sku] = {
                        "sku": raw_sku,
                        "codigo": raw_sku,
                        "nome": nome_prod,
                        "familia": fam_prod,
                        "marca": marca_prod,
                        "peso_kg": float(r['peso_kg']) if pd.notna(r['peso_kg']) and float(r['peso_kg']) > 0 else 0.5,
                        "cd_sp": 0,
                        "matriz": 0,
                        "ativo": True,
                        "vendas_sul_sudeste_30d": 0.0,
                        "vendas_sul_sudeste_60d": 0.0,
                        "vendas_sul_sudeste_90d": 0.0,
                        "vendas_sul_sudeste_180d": 0.0,
                        "vendas_geral_30d": 0.0,
                        "vendas_geral_60d": 0.0,
                        "vendas_geral_90d": 0.0,
                        "vendas_geral_180d": 0.0,
                    }

            # Agrupar Estoque CD_SP por SKU
            df_sp = db.executar_query(sql_sp)
            if df_sp is not None and not df_sp.empty:
                for _, r in df_sp.iterrows():
                    sku = id_para_sku.get(r['id_produto'])
                    if sku and sku in sku_info:
                        sku_info[sku]['cd_sp'] += int(float(r['cd_sp']))

            # Agrupar Estoque Matriz por SKU
            df_mat = db.executar_query(sql_matriz)
            if df_mat is not None and not df_mat.empty:
                for _, r in df_mat.iterrows():
                    sku = id_para_sku.get(r['id_produto'])
                    if sku and sku in sku_info:
                        sku_info[sku]['matriz'] += int(float(r['matriz']))

            # Agrupar Vendas por SKU e Período
            df_vendas = db.executar_query(sql_vendas)
            if df_vendas is not None and not df_vendas.empty:
                df_vendas['data_pedido_dt'] = pd.to_datetime(df_vendas['data_pedido'], errors='coerce')
                df_vendas['uf_destino'] = df_vendas['uf_destino'].astype(str).str.upper().str.strip()
                df_vendas['quantidade'] = pd.to_numeric(df_vendas['quantidade'], errors='coerce').fillna(0)

                data_max = df_vendas['data_pedido_dt'].max()
                if pd.isna(data_max):
                    data_max = pd.Timestamp.now()

                df_vendas['sku'] = df_vendas['id_produto'].map(id_para_sku)
                df_vendas['eh_ss'] = df_vendas['uf_destino'].isin(UFS_SUL_SUDESTE)

                for d in [30, 60, 90, 180, 365]:
                    if d == 365:
                        cutoff = pd.Timestamp(f"{data_max.year}-01-01")
                    else:
                        cutoff = data_max - pd.Timedelta(days=d)
                    df_sub = df_vendas[df_vendas['data_pedido_dt'] >= cutoff]

                    grp_geral = df_sub.groupby('sku')['quantidade'].sum().to_dict()
                    grp_ss = df_sub[df_sub['eh_ss']].groupby('sku')['quantidade'].sum().to_dict()

                    for sku, total in grp_geral.items():
                        if sku in sku_info:
                            sku_info[sku][f"vendas_geral_{d}d"] = float(total)

                    for sku, total in grp_ss.items():
                        if sku in sku_info:
                            sku_info[sku][f"vendas_sul_sudeste_{d}d"] = float(total)

            return list(sku_info.values()) if sku_info else self.obter_dados_base()

        except Exception as exc:
            print(f"Aviso ao consultar Turso Cloud: {exc}")
            return self.obter_dados_base()

    def obter_dados_base(self) -> List[Dict[str, Any]]:
        """Retorna conjunto de dados inicial/fallback de produtos e vendas."""
        return [
            {
                "codigo": "PRD00060",
                "sku": "PRD00060",
                "nome": "TERCO TAU MADEIRA CARLO ACUTIS - AZUL",
                "familia": "TERÇO",
                "marca": "Shalom Artes",
                "cd_sp": 15,
                "matriz": 38,
                "peso_kg": 0.15,
                "vendas_sul_sudeste_30d": 10,
                "vendas_sul_sudeste_60d": 20,
                "vendas_sul_sudeste_90d": 30,
                "vendas_sul_sudeste_180d": 60,
                "vendas_geral_30d": 25,
                "vendas_geral_60d": 50,
                "vendas_geral_90d": 75,
                "vendas_geral_180d": 150,
                "ativo": True,
            },
        ]
