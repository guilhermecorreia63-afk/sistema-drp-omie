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

    # 3. Consultar Requisições de Compra ativas no Omie ERP (PesquisarReq)
    prods_em_compra_map = {} # sku_str ou id_prod -> {"qtd": int, "data_previsao": str, "numero_pedido": str}

    if client_matriz:
        print("[SYNC] Consultando Requisições de Compra ativas no Omie (PesquisarReq)...")
        try:
            res_reqs = client_matriz.executar("produtos/requisicaocompra/", "PesquisarReq", [{"pagina": 1, "registros_por_pagina": 100}])
            reqs = res_reqs.get("requisicaoCadastro", [])
            for r in reqs:
                cab_req = r.get("cabecalhoReq", {})
                dt_prev_req = cab_req.get("dtSugestao", "")
                cod_req = r.get("cCodIntReq") or r.get("nCodReq") or ""
                for it in r.get("ItensReqCompra", []):
                    cod_p = it.get("codProd")
                    qtd_p = int(it.get("qtde", 0) or 0)
                    if cod_p:
                        cod_p_int = int(cod_p)
                        if cod_p_int not in prods_em_compra_map:
                            prods_em_compra_map[cod_p_int] = {"qtd": qtd_p, "data_previsao": dt_prev_req, "numero_pedido": str(cod_req)}
            print(f"[SYNC] Encontrados {len(prods_em_compra_map)} produtos em Requisições de Compra ativas no Omie.")
        except Exception as e_req:
            print(f"[SYNC] Aviso ao consultar Requisições de Compra no Omie: {e_req}")

    # Atualiza 'em_producao' e reconhece Entrada de Estoque (aumento de saldo)
    prods_turso_db = {}
    if db:
        try:
            prods_turso_db = db.obter_detalhes_producao()
        except Exception:
            try:
                raw_st = db.obter_status_producao()
                prods_turso_db = {k: {"em_producao": v, "data_previsao": "", "quantidade_producao": 0, "numero_pedido": ""} for k, v in raw_st.items()}
            except Exception:
                prods_turso_db = {}

    for sku, p in produtos_by_sku.items():
        id_prod = int(p.get("id_produto", 0) or 0)
        matriz_anterior = int(p.get("matriz_anterior", p.get("matriz", 0)))
        matriz_atual = int(p.get("matriz", 0))

        # 1. Se o saldo em estoque AUMENTOU em relação à leitura anterior, houve Entrada de Estoque!
        # Nesse caso, remove a tag 'em_producao' e limpa 'data_previsao'
        if matriz_atual > matriz_anterior and matriz_anterior >= 0:
            p["em_producao"] = False
            p["qtd_producao"] = 0
            p["data_previsao"] = ""
            p["numero_pedido"] = ""
            if db:
                try:
                    db.salvar_status_producao(sku, False, data_previsao="", quantidade_producao=0, numero_pedido="")
                except Exception:
                    pass
            print(f"[SYNC ENTRADA] Saldo do SKU {sku} aumentou de {matriz_anterior} para {matriz_atual}. Tag 'em_producao' removida automaticamente!")

        # 2. Se o usuário definiu o status manualmente no Turso DB, RESPEITA a escolha do usuário!
        elif sku in prods_turso_db:
            db_info = prods_turso_db[sku]
            if isinstance(db_info, dict):
                p["em_producao"] = bool(db_info.get("em_producao", False))
                p["data_previsao"] = db_info.get("data_previsao", "") if p["em_producao"] else ""
                p["numero_pedido"] = db_info.get("numero_pedido", "") if p["em_producao"] else ""
            else:
                p["em_producao"] = bool(db_info)

        # 3. Caso não haja definição manual salva, verifica se o item está em requisição de compra ativa
        elif sku in prods_em_compra_map or id_prod in prods_em_compra_map:
            match_info = prods_em_compra_map.get(sku) or prods_em_compra_map.get(id_prod)
            p["em_producao"] = True
            p["qtd_producao"] = match_info.get("qtd", 0)
            if match_info.get("data_previsao"):
                p["data_previsao"] = match_info["data_previsao"]
            if match_info.get("numero_pedido"):
                p["numero_pedido"] = match_info["numero_pedido"]
            if db:
                try:
                    db.salvar_status_producao(sku, True, data_previsao=p.get("data_previsao", ""), quantidade_producao=p.get("qtd_producao", 0), numero_pedido=p.get("numero_pedido", ""))
                except Exception:
                    pass

    # 4. Mesclar Vendas usando ControleDRP antes de gerar JSON
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
