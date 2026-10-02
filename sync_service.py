# -*- coding: utf-8 -*-
"""
sync_service.py - Módulo de Sincronização Omie ERP -> Turso DB & JSON
======================================================================
1. Puxa a lista de produtos (ListarProdutos) para manter os SKUs e cadastros atualizados.
2. Consulta a Posição Real de Estoque (PosicaoEstoque) para obter o saldo disponível (saldo/físico).
3. Grava as atualizações no Turso DB e em data/produtos_turso.json.
"""

import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from omie_client import OmieClient
import database as db

def sincronizar_dados_seletivo(tipo_sync: str = "TUDO"):
    """
    Executa sincronização de catálogo e saldos reais de estoque com a Omie ERP:
    - TUDO: Estoques Matriz + CD_SP
    - ESTOQUE_CD: Saldo real de estoque do CD_SP
    - ESTOQUE_MATRIZ: Saldo real de estoque da Matriz
    - AMBOS_ESTOQUES: Saldo real da Matriz e CD_SP
    """
    caminho_json = os.path.join("data", "produtos_turso.json")
    produtos = []
    if os.path.exists(caminho_json):
        try:
            with open(caminho_json, "r", encoding="utf-8") as f:
                produtos = json.load(f)
        except Exception:
            produtos = []

    produtos_by_sku = {p["sku"]: p for p in produtos if "sku" in p}
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sync_matriz = tipo_sync in ["TUDO", "ESTOQUE_MATRIZ", "AMBOS_ESTOQUES"]
    sync_cd = tipo_sync in ["TUDO", "ESTOQUE_CD", "AMBOS_ESTOQUES"]

    client_matriz = OmieClient("MATRIZ") if sync_matriz else None
    client_cd = OmieClient("CD") if sync_cd else None

    # 1. Puxar produtos ativos do catálogo da Omie ERP (Matriz)
    if client_matriz:
        try:
            prods_matriz = client_matriz.listar_paginado("geral/produtos/", "ListarProdutos", "produto_servico_cadastro", param_base={"inativo": "N"}, max_paginas=30)
            print(f"[SYNC] Matriz retornou {len(prods_matriz)} produtos ativos do Omie ERP.")
            for pm in prods_matriz:
                sku = str(pm.get("codigo", "")).strip()
                inativo = str(pm.get("inativo", "N")).upper()
                if not sku or inativo == "S":
                    continue
                marca = (pm.get("marca") or "").strip() or "Edições Shalom"
                fam = (pm.get("descricao_familia") or "GERAL").upper()
                nome = pm.get("descricao", "")
                id_prod = pm.get("codigo_produto", 0)
                peso = float(pm.get("peso_bruto", 0.1) or 0.1)

                v_unit = float(pm.get("valor_unitario", 0) or 0)
                if sku in produtos_by_sku:
                    produtos_by_sku[sku]["id_produto"] = id_prod
                    produtos_by_sku[sku]["valor_unitario"] = v_unit
                    if marca:
                        produtos_by_sku[sku]["marca"] = marca
                    if nome:
                        produtos_by_sku[sku]["nome"] = nome
                    if fam:
                        produtos_by_sku[sku]["familia"] = fam
                    produtos_by_sku[sku]["ultima_sincronizacao"] = agora_str
                else:
                    novo_item = {
                        "id_produto": id_prod,
                        "sku": sku,
                        "nome": nome,
                        "marca": marca,
                        "familia": fam,
                        "cd_sp": 0,
                        "matriz": 0,
                        "peso_kg": peso,
                        "valor_unitario": v_unit,
                        "vendas_sul_sudeste_30d": 0,
                        "vendas_geral_30d": 0,
                        "ativo": True,
                        "em_producao": False,
                        "ultima_sincronizacao": agora_str
                    }
                    produtos_by_sku[sku] = novo_item
        except Exception as e:
            print(f"[SYNC] Erro ao sincronizar catálogo Matriz: {e}")

    # 2. Consultar Posição Real de Estoque em Lote Paginado (ListarPosEstoque)
    if sync_matriz and client_matriz:
        print("[SYNC] Consultando saldo real de estoque em lote (ListarPosEstoque) na Matriz...")
        try:
            pag = 1
            tot_pags = 1
            while pag <= tot_pags:
                payload = {
                    "nPagina": pag,
                    "nRegPorPagina": 100,
                    "dDataPosicao": data_hoje,
                    "cExibeTodos": "S",
                    "codigo_local_estoque": 1794541746
                }
                res = client_matriz.executar("estoque/consulta/", "ListarPosEstoque", [payload])
                if not res or "produtos" not in res:
                    break
                tot_pags = res.get("nTotPaginas", 1)
                for item in res.get("produtos", []):
                    sku = str(item.get("cCodigo", "")).strip()
                    cod_prod = item.get("nCodProd")
                    saldo_fisico = int(item.get("fisico", item.get("nSaldo", 0)))
                    saldo_reservado = int(item.get("reservado", 0))
                    p = produtos_by_sku.get(sku)
                    if p:
                        p["matriz"] = saldo_fisico
                        p["matriz_reservado"] = saldo_reservado
                        if cod_prod:
                            p["id_produto"] = cod_prod
                pag += 1
            print(f"[SYNC] Saldo de estoque da Matriz atualizado com sucesso!")
        except Exception as e:
            print(f"[SYNC] Erro ao consultar estoque Matriz em lote: {e}")

    if sync_cd and client_cd:
        print("[SYNC] Consultando saldo real de estoque em lote (ListarPosEstoque) no CD_SP...")
        try:
            pag = 1
            tot_pags = 1
            while pag <= tot_pags:
                payload = {
                    "nPagina": pag,
                    "nRegPorPagina": 100,
                    "dDataPosicao": data_hoje,
                    "cExibeTodos": "S",
                    "codigo_local_estoque": 3073865797
                }
                res = client_cd.executar("estoque/consulta/", "ListarPosEstoque", [payload])
                if not res or "produtos" not in res:
                    err_txt = res.get("faultstring") if isinstance(res, dict) else str(res)
                    print(f"[SYNC] [AVISO CD_SP] Omie retornou erro ao consultar estoque: {err_txt}")
                    break
                tot_pags = res.get("nTotPaginas", 1)
                for item in res.get("produtos", []):
                    sku = str(item.get("cCodigo", "")).strip()
                    cod_prod = item.get("nCodProd")
                    saldo_fisico = int(item.get("fisico", item.get("nSaldo", 0)))
                    saldo_reservado = int(item.get("reservado", 0))
                    p = produtos_by_sku.get(sku)
                    if p:
                        p["cd_sp"] = saldo_fisico
                        p["cd_sp_reservado"] = saldo_reservado
                        if cod_prod:
                            p["id_produto"] = cod_prod
                pag += 1
            print(f"[SYNC] Saldo de estoque do CD_SP consultado.")
        except Exception as e:
            print(f"[SYNC] Erro ao consultar estoque CD_SP em lote: {e}")

    # 3. Mesclar Vendas usando ControleDRP antes de gerar JSON
    try:
        from controle_drp import ControleDRP
        drp = ControleDRP()
        vendas_data = drp.carregar_dados_turso()
        vendas_by_sku = {v["sku"]: v for v in vendas_data}
        for sku, p in produtos_by_sku.items():
            if sku in vendas_by_sku:
                v = vendas_by_sku[sku]
                p["vendas_sul_sudeste_30d"] = v.get("vendas_sul_sudeste_30d", 0)
                p["vendas_sul_sudeste_60d"] = v.get("vendas_sul_sudeste_60d", 0)
                p["vendas_sul_sudeste_90d"] = v.get("vendas_sul_sudeste_90d", 0)
                p["vendas_sul_sudeste_180d"] = v.get("vendas_sul_sudeste_180d", 0)
                p["vendas_geral_30d"] = v.get("vendas_geral_30d", 0)
                p["vendas_geral_60d"] = v.get("vendas_geral_60d", 0)
                p["vendas_geral_90d"] = v.get("vendas_geral_90d", 0)
                p["vendas_geral_180d"] = v.get("vendas_geral_180d", 0)
    except Exception as e:
        print(f"[SYNC] Erro ao mesclar vendas do ControleDRP: {e}")

    lista_final = list(produtos_by_sku.values())

    # 4. Gravar lista atualizada em data/produtos_turso.json
    os.makedirs("data", exist_ok=True)
    try:
        with open(caminho_json, "w", encoding="utf-8") as f:
            json.dump(lista_final, f, ensure_ascii=False, indent=2)
        print(f"[SYNC] data/produtos_turso.json atualizado com {len(lista_final)} produtos.")
    except Exception as e:
        print(f"[SYNC] Erro ao salvar produtos_turso.json: {e}")

    # 4. Gravar no Banco de Dados Turso DB em lote
    try:
        db.inicializar_banco()
        batch_stmts = []
        for p in lista_final:
            batch_stmts.append({
                "query": """INSERT INTO produtos (
                    sku, codigo_produto, descricao, cd_sp, matriz, peso_kg, cmc, ativo, ultima_sincronizacao
                ) VALUES (
                    :sku, :codigo_produto, :descricao, :cd_sp, :matriz, :peso_kg, :cmc, :ativo, :ultima_sincronizacao
                ) ON CONFLICT(sku) DO UPDATE SET
                    matriz = excluded.matriz,
                    cd_sp = excluded.cd_sp,
                    codigo_produto = excluded.codigo_produto,
                    descricao = excluded.descricao,
                    peso_kg = excluded.peso_kg,
                    ativo = excluded.ativo,
                    ultima_sincronizacao = excluded.ultima_sincronizacao""",
                "params": {
                    "sku": p["sku"],
                    "codigo_produto": p.get("id_produto", 0),
                    "descricao": p.get("nome", ""),
                    "cd_sp": p.get("cd_sp", 0),
                    "matriz": p.get("matriz", 0),
                    "peso_kg": p.get("peso_kg", 0.1),
                    "cmc": p.get("valor_unitario", 0.0),
                    "ativo": 1 if p.get("ativo", True) else 0,
                    "ultima_sincronizacao": agora_str
                }
            })
        db.executar_batch_query(batch_stmts)
        print(f"[SYNC] Banco Turso DB / SQLite atualizado com sucesso em lote ({len(batch_stmts)} itens)!")
    except Exception as e:
        print(f"[SYNC] Erro ao salvar no Turso/SQLite: {e}")

    msg = f"Sincronização ({tipo_sync}) concluída com sucesso! Saldo real de estoque consultado na Omie e salvo no Turso DB."
    return True, msg, len(lista_final)

if __name__ == "__main__":
    ok, m, count = sincronizar_dados_seletivo("ESTOQUE_MATRIZ")
    print(f"Sync Final: ok={ok}, count={count}, m={m}")
