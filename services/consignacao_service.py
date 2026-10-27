# -*- coding: utf-8 -*-
"""
services/consignacao_service.py
Lógica de negócio e integração Omie/Turso para o Módulo de Consignação (Ida e Volta).
- Busca de clientes e remessas em aberto
- Unificação de remessas com consolidação de itens
- Persistência de acertos no Turso DB
- Geração de Devoluções de Remessa (CFOP 1.917) e Pedidos de Venda no Omie
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database as db
from omie_client import OmieClient

# ID do cenário fiscal oficial no Omie para Venda Mercadoria (Consignação sem contrato / 1818515488)
CENARIO_VENDA_CONSIGNACAO = 1818515488 
# ID da categoria comercial padrão Matriz
CATEGORIA_COMERCIAL_PADRAO = "1.01.01"
# Categoria padrão para o Retorno de Remessa (Nota de Entrada): Compras de Mercadorias para Revenda
CATEGORIA_RETORNO_REMESSA_PADRAO = "2.01.01"
# Conta Corrente: Omie.CASH
CONTA_CORRENTE_MATRIZ = 1794541768
LOCAL_ESTOQUE_MATRIZ = 1794541746

def _df_to_records(df_or_list) -> List[Dict[str, Any]]:
    if df_or_list is None:
        return []
    if hasattr(df_or_list, 'to_dict'):
        return df_or_list.to_dict('records')
    if isinstance(df_or_list, list):
        res = []
        for x in df_or_list:
            if isinstance(x, dict):
                res.append(x)
            elif hasattr(x, '_asdict'):
                res.append(x._asdict())
            else:
                try:
                    res.append(dict(x))
                except Exception:
                    pass
        return res
    return []

class ConsignacaoService:

    def __init__(self):
        self.client = OmieClient("MATRIZ")
        self._produtos_cache = None

    def _carregar_produtos_cache(self) -> Dict[str, Any]:
        if self._produtos_cache is not None:
            return self._produtos_cache
        
        caminho_json = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'produtos_turso.json')
        id_map = {}
        sku_map = {}
        ean_map = {}
        prods = []
        if os.path.exists(caminho_json):
            try:
                with open(caminho_json, 'r', encoding='utf-8') as f:
                    prods = json.load(f)
                    for p in prods:
                        if p.get('id_produto'):
                            id_map[int(p['id_produto'])] = p
                        if p.get('codigo_produto'):
                            id_map[int(p['codigo_produto'])] = p
                        sku_val = str(p.get('sku') or p.get('codigo') or '').strip().upper()
                        if sku_val:
                            sku_map[sku_val] = p
                        ean_val = str(p.get('ean') or p.get('codigo_barras') or '').strip()
                        if ean_val:
                            ean_map[ean_val] = p
            except Exception as e:
                print(f"[CONSIGNACAO] Erro ao carregar cache de produtos: {e}")
        
        self._produtos_cache = {"by_id": id_map, "by_sku": sku_map, "by_ean": ean_map, "lista": prods}
        return self._produtos_cache

    def buscar_produto(self, termo: str) -> List[Dict[str, Any]]:
        """
        Busca produtos por Código (SKU), Código Omie (ID numérico),
        EAN / Código de Barras, ou Nome / Descrição.
        """
        termo = str(termo or "").strip()
        if not termo:
            return []

        termo_upper = termo.upper()
        termo_sem_zero = termo_upper.lstrip("0")
        cache = self._carregar_produtos_cache()

        resultados = []
        ids_vistos = set()

        # 1. Match direto em EAN / Código de barras
        if termo in cache.get("by_ean", {}):
            p = cache["by_ean"][termo]
            pid = int(p.get("id_produto") or p.get("codigo_produto") or 0)
            ids_vistos.add(pid)
            resultados.append({
                "sku": str(p.get("sku") or p.get("codigo") or "").strip(),
                "id_produto": pid,
                "codigo_produto": pid,
                "nome": p.get("nome") or p.get("descricao") or "",
                "descricao": p.get("nome") or p.get("descricao") or "",
                "ean": termo,
                "codigo_barras": termo,
                "valor_unitario": float(p.get("valor_unitario") or 0.0),
                "familia": p.get("familia") or ""
            })

        # 2. Match direto em SKU / Código
        if termo_upper in cache.get("by_sku", {}):
            p = cache["by_sku"][termo_upper]
            pid = int(p.get("id_produto") or p.get("codigo_produto") or 0)
            if pid not in ids_vistos:
                ids_vistos.add(pid)
                resultados.append({
                    "sku": str(p.get("sku") or p.get("codigo") or "").strip(),
                    "id_produto": pid,
                    "codigo_produto": pid,
                    "nome": p.get("nome") or p.get("descricao") or "",
                    "descricao": p.get("nome") or p.get("descricao") or "",
                    "ean": str(p.get("ean") or p.get("codigo_barras") or ""),
                    "codigo_barras": str(p.get("ean") or p.get("codigo_barras") or ""),
                    "valor_unitario": float(p.get("valor_unitario") or 0.0),
                    "familia": p.get("familia") or ""
                })

        # 3. Match em toda a lista (SKU com/sem zeros, ID numérico, EAN, Nome)
        for p in cache.get("lista", []):
            sku = str(p.get("sku") or p.get("codigo") or "").strip().upper()
            pid_str = str(p.get("id_produto") or p.get("codigo_produto") or "").strip()
            pid = int(pid_str) if pid_str.isdigit() else 0
            if pid in ids_vistos:
                continue

            ean = str(p.get("ean") or p.get("codigo_barras") or "").strip()
            nome = str(p.get("nome") or p.get("descricao") or "").strip().upper()

            match = False
            if termo_upper in (sku, pid_str, ean):
                match = True
            elif termo_sem_zero and (sku.lstrip("0") == termo_sem_zero or pid_str == termo_sem_zero or (ean and ean.lstrip("0") == termo_sem_zero)):
                match = True
            elif termo_upper in sku or (ean and termo_upper in ean) or termo_upper in nome:
                match = True

            if match:
                ids_vistos.add(pid)
                resultados.append({
                    "sku": sku,
                    "id_produto": pid,
                    "codigo_produto": pid,
                    "nome": p.get("nome") or p.get("descricao") or "",
                    "descricao": p.get("nome") or p.get("descricao") or "",
                    "ean": ean,
                    "codigo_barras": ean,
                    "valor_unitario": float(p.get("valor_unitario") or 0.0),
                    "familia": p.get("familia") or ""
                })
                if len(resultados) >= 15:
                    break

        # 4. Fallback Omie API caso não encontre
        if not resultados and len(termo) >= 3:
            try:
                res_cod = self.client.executar("geral/produtos/", "ConsultarProduto", [{"codigo": termo}])
                if res_cod and "codigo_produto" in res_cod:
                    pid = int(res_cod.get("codigo_produto") or 0)
                    resultados.append({
                        "sku": str(res_cod.get("codigo") or termo).strip(),
                        "id_produto": pid,
                        "codigo_produto": pid,
                        "nome": res_cod.get("descricao") or "",
                        "descricao": res_cod.get("descricao") or "",
                        "ean": str(res_cod.get("ean") or "").strip(),
                        "codigo_barras": str(res_cod.get("ean") or "").strip(),
                        "valor_unitario": float(res_cod.get("valor_unitario") or 0.0),
                        "familia": str(res_cod.get("descricao_familia") or "")
                    })
            except Exception:
                pass

        return resultados

    def buscar_clientes(self, termo: str) -> List[Dict[str, Any]]:
        """Busca clientes por Nome Fantasia, Razão Social, CNPJ ou Número de Remessa no Omie/Turso."""
        termo = termo.strip()
        if not termo:
            return []

        resultado = []
        vistos = set()

        # 0. Se o termo for numérico, pode ser número de remessa (ex: 1788 ou 1760)
        if termo.isdigit() and len(termo) <= 6:
            try:
                num_rem_busca = int(termo)
                # Tentar achar a remessa nas últimas páginas ou cache
                res_rem = self.client.executar('produtos/remessa/', 'ListarRemessas', [{'nPagina': 1, 'nRegistrosPorPagina': 50}])
                tot_pags = res_rem.get('nTotalPaginas', 1)
                for p in range(tot_pags, max(1, tot_pags - 6), -1):
                    p_res = self.client.executar('produtos/remessa/', 'ListarRemessas', [{'nPagina': p, 'nRegistrosPorPagina': 50}])
                    for r in p_res.get('remessas', []):
                        cab = r.get('cabec', {})
                        if str(cab.get('cNumeroRemessa')) == str(num_rem_busca):
                            n_cli = cab.get('nCodCli')
                            if n_cli and n_cli not in vistos:
                                # Consultar cliente
                                c_info = self.client.executar('geral/clientes/', 'ConsultarCliente', [{'codigo_cliente_omie': n_cli}])
                                if c_info and 'codigo_cliente_omie' in c_info:
                                    vistos.add(n_cli)
                                    resultado.append({
                                        "codigo_cliente": c_info.get('codigo_cliente_omie'),
                                        "nome_fantasia": c_info.get('nome_fantasia') or c_info.get('razao_social'),
                                        "razao_social": c_info.get('razao_social'),
                                        "cnpj_cpf": c_info.get('cnpj_cpf'),
                                        "cidade": c_info.get('cidade'),
                                        "estado": c_info.get('estado'),
                                        "remessa_encontrada": str(num_rem_busca)
                                    })
                            break
                    if resultado:
                        break
            except Exception as e_rem:
                print(f"[CONSIGNACAO] Erro ao buscar por número de remessa: {e_rem}")

        # 1. Tentar busca direta no Omie via ListarClientesResumido (rápido e flexível)
        try:
            res = self.client.executar('geral/clientes/', 'ListarClientesResumido', [{
                'pagina': 1,
                'registros_por_pagina': 30,
                'clientesFiltro': {'nome_fantasia': termo}
            }])
            clientes_omie = res.get('clientes_cadastro_resumido', [])
            
            # Se não encontrou por fantasia, tenta por razao social
            if not clientes_omie:
                res2 = self.client.executar('geral/clientes/', 'ListarClientesResumido', [{
                    'pagina': 1,
                    'registros_por_pagina': 30,
                    'clientesFiltro': {'razao_social': termo}
                }])
                clientes_omie = res2.get('clientes_cadastro_resumido', [])

            # Se ainda não achou e termo parece CNPJ/CPF
            if not clientes_omie and any(c.isdigit() for c in termo):
                res3 = self.client.executar('geral/clientes/', 'ListarClientesResumido', [{
                    'pagina': 1,
                    'registros_por_pagina': 30,
                    'clientesFiltro': {'cnpj_cpf': termo}
                }])
                clientes_omie = res3.get('clientes_cadastro_resumido', [])

            for c in clientes_omie:
                cod = c.get('codigo_cliente') or c.get('codigo_cliente_omie')
                if cod and cod not in vistos:
                    vistos.add(cod)
                    resultado.append({
                        "codigo_cliente": cod,
                        "nome_fantasia": c.get('nome_fantasia') or c.get('razao_social'),
                        "razao_social": c.get('razao_social'),
                        "cnpj_cpf": c.get('cnpj_cpf'),
                        "cidade": c.get('cidade'),
                        "estado": c.get('estado')
                    })
            if resultado:
                return resultado
        except Exception as e:
            print(f"[CONSIGNACAO] Erro na busca de clientes Omie: {e}")

        # 2. Fallback busca SQLite / Turso
        try:
            sql = """
                SELECT id, nome, cpf_cnpj, ultima_nf FROM clientes 
                WHERE nome LIKE :q OR cpf_cnpj LIKE :q LIMIT 20
            """
            df_cli = db.executar_query(sql, {"q": f"%{termo}%"})
            rows = _df_to_records(df_cli)
            for r in rows:
                cod = r.get('id')
                if cod and cod not in vistos:
                    vistos.add(cod)
                    resultado.append({
                        "codigo_cliente": cod,
                        "nome_fantasia": r.get('nome'),
                        "razao_social": r.get('nome'),
                        "cnpj_cpf": r.get('cpf_cnpj')
                    })
            return resultado
        except Exception:
            return resultado

    def listar_remessas_cliente(self, codigo_cliente: int) -> List[Dict[str, Any]]:
        """Lista remessas emitidas para o cliente buscando páginas recentes."""
        try:
            # Pegar total de páginas
            init_res = self.client.executar('produtos/remessa/', 'ListarRemessas', [{'nPagina': 1, 'nRegistrosPorPagina': 50}])
            tot_pags = init_res.get('nTotalPaginas', 1)

            remessas_encontradas = []
            # Varre as últimas páginas onde estão as remessas recentes
            pag_inicio = max(1, tot_pags - 6)
            for p in range(tot_pags, pag_inicio - 1, -1):
                res = self.client.executar('produtos/remessa/', 'ListarRemessas', [{'nPagina': p, 'nRegistrosPorPagina': 50}])
                for r in res.get('remessas', []):
                    c = r.get('cabec', {})
                    if int(c.get('nCodCli') or 0) == int(codigo_cliente):
                        # Só remessas não canceladas
                        if c.get('cCancelado') != 'S':
                            remessas_encontradas.append({
                                "nCodRem": c.get('nCodRem'),
                                "numero_remessa": str(c.get('cNumeroRemessa') or ''),
                                "numero_nf": c.get('cNumeroNF') or '',
                                "data_previsao": c.get('dPrevisao') or '',
                                "valor_total": float(c.get('nValorTotal') or 0.0),
                                "etapa": c.get('cEtapa') or 'Concluído',
                                "cenario_impostos": c.get('codigo_cenario_impostos'),
                                "faturada": c.get('faturada') or 'N'
                            })
            
            # Ordenar por número decrescente
            remessas_encontradas.sort(key=lambda x: int(x['numero_remessa']) if str(x['numero_remessa']).isdigit() else 0, reverse=True)
            return remessas_encontradas
        except Exception as e:
            print(f"[CONSIGNACAO] Erro ao listar remessas do cliente {codigo_cliente}: {e}")
            return []

    def obter_detalhes_remessa(self, nCodRem: int) -> Dict[str, Any]:
        """Obtém os dados completos de uma remessa com sua lista de produtos."""
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scratch')
        cache_file = os.path.join(cache_dir, f"remessa_{nCodRem}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        det = self.client.executar('produtos/remessa/', 'ConsultarRemessa', [{'nCodRem': nCodRem}])
        if det and 'cabec' in det:
            try:
                os.makedirs(cache_dir, exist_ok=True)
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(det, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        return det

    def unificar_remessas(self, remessas_ids: List[int], desconto_padrao_pct: float = 30.0) -> Dict[str, Any]:
        """
        Recebe lista de nCodRem, consulta cada uma e consolida os itens somando
        quantidades enviadas para SKUs repetidos.
        """
        cache = self._carregar_produtos_cache()
        itens_agrupados = {}
        remessas_info = []

        for nCodRem in remessas_ids:
            rem = self.obter_detalhes_remessa(nCodRem)
            if not rem or 'cabec' not in rem:
                continue

            cab = rem.get('cabec', {})
            num_rem = str(cab.get('cNumeroRemessa') or '')
            remessas_info.append({
                "nCodRem": nCodRem,
                "numero_remessa": num_rem,
                "data": cab.get('dPrevisao'),
                "valor_total": float(cab.get('nValorTotal') or 0.0),
                "faturada": cab.get('faturada') or 'N'
            })

            for p in rem.get('produtos', []):
                ncod = int(p.get('nCodProd') or 0)
                sku = str(p.get('cCodItInt') or p.get('cCodigo') or '').strip()
                desc = p.get('cDescricao') or ''
                qtd = int(p.get('nQtde') or 0)
                val_unit = float(p.get('nValUnit') or 0.0)
                fam = ""
                if ncod in cache['by_id']:
                    prod_info = cache['by_id'][ncod]
                    sku = str(prod_info.get('codigo') or prod_info.get('sku') or sku).strip()
                    desc = prod_info.get('nome') or prod_info.get('descricao') or desc
                    fam = prod_info.get('familia') or ""
                    if val_unit <= 0:
                        val_unit = float(prod_info.get('valor_unitario') or 0.0)
                elif sku in cache.get('by_sku', {}):
                    prod_info = cache['by_sku'][sku]
                    fam = prod_info.get('familia') or ""
                    if not desc:
                        desc = prod_info.get('nome') or prod_info.get('descricao') or desc
                    if val_unit <= 0:
                        val_unit = float(prod_info.get('valor_unitario') or 0.0)

                # Desconto sugerido pela Política Comercial Oficial de Famílias
                try:
                    from services.politica_comercial import obter_desconto_item
                    desc_calc = obter_desconto_item(sku, desc, fam, condicao='A_VISTA_AUTO', simular_50=False)
                except Exception:
                    desc_calc = desconto_padrao_pct

                chave = sku if sku else f"PROD_{ncod}"

                if chave not in itens_agrupados:
                    itens_agrupados[chave] = {
                        "sku": sku,
                        "codigo_produto": ncod,
                        "descricao": desc,
                        "familia": fam,
                        "qtd_enviada": 0,
                        "qtd_retorno": 0,
                        "qtd_vendida": 0,
                        "preco_unitario": val_unit,
                        "desconto_pct": desc_calc,
                        "remessas_origem": {}
                    }

                itens_agrupados[chave]["qtd_enviada"] += qtd
                itens_agrupados[chave]["remessas_origem"][num_rem] = itens_agrupados[chave]["remessas_origem"].get(num_rem, 0) + qtd

        # Converte para lista ordenada por descrição
        lista_final = list(itens_agrupados.values())
        lista_final.sort(key=lambda x: str(x.get("descricao") or x.get("sku") or "").upper())

        return {
            "remessas": remessas_info,
            "total_skus": len(lista_final),
            "total_pecas_enviadas": sum(x["qtd_enviada"] for x in lista_final),
            "itens": lista_final
        }

    def salvar_acerto(self, dados_acerto: Dict[str, Any]) -> Dict[str, Any]:
        """Salva ou atualiza um acerto de consignação no Turso DB."""
        codigo_acerto = dados_acerto.get("codigo_acerto")
        if not codigo_acerto:
            codigo_acerto = f"AC-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        cli_obj = dados_acerto.get("cliente") or {}
        cod_cli = dados_acerto.get("codigo_cliente_omie") or cli_obj.get("codigo_cliente")
        cli_nome = dados_acerto.get("cliente_nome") or cli_obj.get("nome_fantasia") or cli_obj.get("razao_social")
        cli_doc = dados_acerto.get("cliente_cnpj_cpf") or cli_obj.get("cnpj_cpf")
        rems = dados_acerto.get("remessas_unificadas") or dados_acerto.get("remessas_selecionadas") or []
        rems_json = json.dumps(rems, ensure_ascii=False)
        status = dados_acerto.get("status", "EM_CONFERENCIA")
        desc_pct = float(dados_acerto.get("desconto_padrao_pct", 30.0))
        
        tot_env = int(dados_acerto.get("total_enviado", 0))
        tot_ret = int(dados_acerto.get("total_retorno", 0))
        tot_vend = int(dados_acerto.get("total_vendido", 0))

        val_bruto = float(dados_acerto.get("valor_total_bruto", 0.0))
        val_desc = float(dados_acerto.get("valor_total_desconto", 0.0))
        val_liq = float(dados_acerto.get("valor_total_liquido", 0.0))

        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Upsert acerto
        sql_check = "SELECT id FROM consignacao_acertos WHERE codigo_acerto = :cod"
        df_check = db.executar_query(sql_check, {"cod": codigo_acerto})
        existente = _df_to_records(df_check)

        if existente:
            acerto_id = existente[0]["id"]
            sql_up = """
                UPDATE consignacao_acertos SET
                    codigo_cliente_omie = :cli, cliente_nome = :nome, cliente_cnpj_cpf = :doc,
                    remessas_unificadas = :rems, status = :st, desconto_padrao_pct = :desc,
                    total_enviado = :env, total_retorno = :ret, total_vendido = :vend,
                    valor_total_bruto = :v_bruto, valor_total_desconto = :v_desc, valor_total_liquido = :v_liq,
                    atualizado_em = :agora
                WHERE id = :id
            """
            db.executar_query(sql_up, {
                "id": acerto_id, "cli": cod_cli, "nome": cli_nome, "doc": cli_doc,
                "rems": rems_json, "st": status, "desc": desc_pct, "env": tot_env,
                "ret": tot_ret, "vend": tot_vend, "v_bruto": val_bruto,
                "v_desc": val_desc, "v_liq": val_liq, "agora": agora
            }, is_select=False)
        else:
            sql_ins = """
                INSERT INTO consignacao_acertos (
                    codigo_acerto, codigo_cliente_omie, cliente_nome, cliente_cnpj_cpf,
                    remessas_unificadas, status, desconto_padrao_pct, total_enviado,
                    total_retorno, total_vendido, valor_total_bruto, valor_total_desconto,
                    valor_total_liquido, criado_em, atualizado_em
                ) VALUES (
                    :cod, :cli, :nome, :doc, :rems, :st, :desc, :env, :ret, :vend,
                    :v_bruto, :v_desc, :v_liq, :agora, :agora
                )
            """
            db.executar_query(sql_ins, {
                "cod": codigo_acerto, "cli": cod_cli, "nome": cli_nome, "doc": cli_doc,
                "rems": rems_json, "st": status, "desc": desc_pct, "env": tot_env,
                "ret": tot_ret, "vend": tot_vend, "v_bruto": val_bruto,
                "v_desc": val_desc, "v_liq": val_liq, "agora": agora
            }, is_select=False)
            df_id = db.executar_query(sql_check, {"cod": codigo_acerto})
            recs_id = _df_to_records(df_id)
            acerto_id = recs_id[0]["id"] if recs_id else 0

        # Gravar itens
        itens = dados_acerto.get("itens", [])
        if itens and acerto_id:
            db.executar_query("DELETE FROM consignacao_acerto_itens WHERE acerto_id = :id", {"id": acerto_id}, is_select=False)
            cache = self._carregar_produtos_cache()
            for it in itens:
                sku = str(it.get("sku") or "").strip()
                ncod = int(it.get("codigo_produto_omie") or it.get("codigo_produto") or it.get("id_produto") or 0)
                if ncod <= 0 and sku:
                    ncod = int(cache.get("by_sku", {}).get(sku, {}).get("id_produto") or 0)

                sql_item = """
                    INSERT INTO consignacao_acerto_itens (
                        acerto_id, sku, codigo_produto_omie, descricao, qtd_enviada,
                        qtd_retorno, qtd_vendida, preco_unitario, desconto_pct,
                        valor_total_liquido, remessas_origem
                    ) VALUES (
                        :ac_id, :sku, :ncod, :desc, :env, :ret, :vend, :preco, :desc_pct,
                        :v_liq, :orig
                    )
                """
                db.executar_query(sql_item, {
                    "ac_id": acerto_id,
                    "sku": sku,
                    "ncod": ncod,
                    "desc": it.get("descricao", ""),
                    "env": int(it.get("qtd_enviada", 0)),
                    "ret": int(it.get("qtd_retorno", 0)),
                    "vend": int(it.get("qtd_vendida", 0)),
                    "preco": float(it.get("preco_unitario", 0.0)),
                    "desc_pct": float(it.get("desconto_pct", 30.0)),
                    "v_liq": float(it.get("valor_total_liquido", 0.0)),
                    "orig": json.dumps(it.get("remessas_origem", {}), ensure_ascii=False)
                }, is_select=False)

        return {"success": True, "acerto_id": acerto_id, "codigo_acerto": codigo_acerto, "status": status}

    def listar_acertos(self) -> List[Dict[str, Any]]:
        """Lista histórico de acertos salvos no Turso DB com cálculo de prazos de 30 dias."""
        try:
            sql = "SELECT * FROM consignacao_acertos ORDER BY id DESC LIMIT 50"
            df = db.executar_query(sql)
            rows = _df_to_records(df)
            res = []
            hoje = datetime.now().date()
            for r_dict in rows:
                if r_dict.get("remessas_unificadas") and isinstance(r_dict["remessas_unificadas"], str):
                    try:
                        r_dict["remessas_unificadas"] = json.loads(r_dict["remessas_unificadas"])
                    except Exception:
                        pass

                # Cálculo de prazos
                raw_dt_ini = r_dict.get("data_inicio_prazo")
                raw_criado = r_dict.get("criado_em")
                dt_ini_str = ""
                if raw_dt_ini and str(raw_dt_ini).strip() not in ("None", "nan"):
                    dt_ini_str = str(raw_dt_ini).strip()[:10]
                elif raw_criado and str(raw_criado).strip() not in ("None", "nan"):
                    dt_ini_str = str(raw_criado).strip()[:10]

                dias_prazo = 30
                try:
                    dias_prazo = int(float(r_dict.get("dias_prazo") or 30))
                except Exception:
                    dias_prazo = 30

                dias_decorridos = 0
                dias_restantes = dias_prazo
                dt_venc_str = ""
                dt_ini_fmt = ""

                if dt_ini_str and len(dt_ini_str) == 10:
                    try:
                        dt_ini = datetime.strptime(dt_ini_str, "%Y-%m-%d").date()
                        dias_decorridos = (hoje - dt_ini).days
                        dias_restantes = dias_prazo - dias_decorridos
                        dt_venc = dt_ini + timedelta(days=dias_prazo)
                        dt_venc_str = dt_venc.strftime("%d/%m/%Y")
                        dt_ini_fmt = dt_ini.strftime("%d/%m/%Y")
                    except Exception:
                        pass

                r_dict["dias_prazo"] = dias_prazo
                r_dict["dias_decorridos"] = max(0, dias_decorridos)
                r_dict["dias_restantes"] = dias_restantes
                r_dict["data_vencimento"] = dt_venc_str
                r_dict["data_inicio_formatada"] = dt_ini_fmt

                st = r_dict.get("status", "EM_CONFERENCIA")
                if st == "FINALIZADO_OMIE":
                    r_dict["prazo_status"] = "CONCLUIDO"
                    r_dict["prazo_label"] = "Concluído Omie"
                    r_dict["prazo_cor"] = "#10b981"
                elif dias_restantes <= 0:
                    r_dict["prazo_status"] = "VENCIDO"
                    r_dict["prazo_label"] = f"Vencido há {abs(dias_restantes)} dias! Fazer contagem" if dias_restantes < 0 else "Prazo Venceu Hoje! Fazer contagem"
                    r_dict["prazo_cor"] = "#ef4444"
                elif dias_restantes <= 5:
                    r_dict["prazo_status"] = "ALERTA_5D"
                    r_dict["prazo_label"] = f"Atenção: Faltam {dias_restantes} dias ({dt_venc_str})"
                    r_dict["prazo_cor"] = "#f59e0b"
                else:
                    r_dict["prazo_status"] = "EM_ANDAMENTO"
                    r_dict["prazo_label"] = f"Faltam {dias_restantes} dias ({dt_venc_str})"
                    r_dict["prazo_cor"] = "#38bdf8"

                # Aliases de compatibilidade para o frontend
                r_dict["faturamento_liquido"] = float(r_dict.get("valor_total_liquido") or 0.0)
                r_dict["total_devolvido"] = int(r_dict.get("total_retorno") or 0)
                r_dict["cliente_omie_id"] = r_dict.get("codigo_cliente_omie")
                
                rems_list = r_dict.get("remessas_unificadas") or []
                if isinstance(rems_list, str):
                    try:
                        rems_list = json.loads(rems_list)
                    except Exception:
                        rems_list = []
                r_dict["remessas_ids"] = [
                    str(r.get("numero_remessa") or r.get("nCodRem") or "")
                    for r in rems_list
                    if str(r.get("numero_remessa") or r.get("nCodRem") or "").strip()
                ]

                res.append(r_dict)
            return res
        except Exception as e:
            print(f"[CONSIGNACAO] Erro ao listar acertos: {e}")
            return []

    def buscar_codigo_remessa(self, termo: str) -> Optional[int]:
        """
        Localiza o nCodRem no Omie a partir do número da remessa (cNumeroRemessa)
        ou código interno (nCodRem).
        """
        termo_str = str(termo or "").strip()
        if not termo_str:
            return None

        # 1. Se parecer com um nCodRem do Omie (>= 8 dígitos numéricos)
        if termo_str.isdigit() and len(termo_str) >= 8:
            try:
                res = self.client.executar('produtos/remessa/', 'ConsultarRemessa', [{'nCodRem': int(termo_str)}])
                if res and 'cabec' in res and 'faultstring' not in res:
                    return int(res['cabec']['nCodRem'])
            except Exception:
                pass

        # 2. Busca por cNumeroRemessa (ex: 1863, 1868)
        try:
            init_res = self.client.executar('produtos/remessa/', 'ListarRemessas', [{'nPagina': 1, 'nRegistrosPorPagina': 50}])
            tot_pags = int(init_res.get('nTotalPaginas') or 1)

            # Varre as páginas de trás para frente (remessas recentes estão nas últimas páginas)
            for p in range(tot_pags, 0, -1):
                res = self.client.executar('produtos/remessa/', 'ListarRemessas', [{'nPagina': p, 'nRegistrosPorPagina': 50}])
                for r in res.get('remessas', []):
                    cab = r.get('cabec', {})
                    num_cad = str(cab.get('cNumeroRemessa', '')).strip()
                    cod_cad = str(cab.get('nCodRem', '')).strip()
                    if num_cad == termo_str or cod_cad == termo_str:
                        return int(cab['nCodRem'])
        except Exception as e:
            print(f"[CONSIGNACAO] Erro ao buscar código da remessa {termo_str}: {e}")

        return None

    def vincular_remessa_aberta(self, dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Vincula uma remessa existente no Omie para iniciar a contagem regressiva de 30 dias.
        """
        nCodRem = int(dados.get("nCodRem") or 0)
        num_rem_input = str(dados.get("numero_remessa") or "").strip()
        dt_inicio = str(dados.get("data_inicio_prazo") or dados.get("data_inicio") or datetime.now().strftime("%Y-%m-%d")).strip()[:10]
        if "/" in dt_inicio:
            partes = dt_inicio.split("/")
            if len(partes) == 3:
                dt_inicio = f"{partes[2]}-{partes[1]}-{partes[0]}"
        dias_prazo = int(dados.get("dias_prazo") or 30)

        if not nCodRem and num_rem_input:
            nCodRem = self.buscar_codigo_remessa(num_rem_input) or 0

        if not nCodRem:
            return {"success": False, "message": f"Remessa #{num_rem_input or nCodRem} não encontrada no Omie."}

        unif = self.unificar_remessas([nCodRem], desconto_padrao_pct=30.0)
        itens = unif.get("itens", [])
        if not itens:
            return {"success": False, "message": f"Remessa {num_rem_input or nCodRem} não encontrada ou vazia no Omie."}

        num_rem = "0"
        for it in itens:
            orig = it.get("remessas_origem", {})
            if orig:
                num_rem = list(orig.keys())[0]
                break

        res_rem = self.client.executar("produtos/remessa/", "ConsultarRemessa", [{"nCodRem": nCodRem}])
        cab = res_rem.get("cabec", {})
        cod_cli = cab.get("nCodCli", 0)
        num_rem = cab.get("cNumeroRemessa", num_rem)

        cli_nome = f"Cliente Remessa #{num_rem}"
        cli_doc = ""
        if cod_cli:
            try:
                res_c = self.client.executar("geral/clientes/", "ConsultarCliente", [{"codigo_cliente_omie": cod_cli}])
                cli_nome = res_c.get("nome_fantasia") or res_c.get("razao_social") or cli_nome
                cli_doc = res_c.get("cnpj_cpf") or ""
            except Exception:
                pass

        val_bruto = sum(float(it.get("qtd_enviada", 0)) * float(it.get("preco_unitario", 0)) for it in itens)
        val_desc = val_bruto * 0.30
        val_liq = val_bruto - val_desc
        tot_env = sum(int(it.get("qtd_enviada", 0)) for it in itens)

        cod_acerto = f"AC-REM{num_rem}"
        payload_acerto = {
            "codigo_acerto": cod_acerto,
            "codigo_cliente_omie": cod_cli,
            "cliente_nome": cli_nome,
            "cliente_cnpj_cpf": cli_doc,
            "cliente": {
                "codigo_cliente": cod_cli,
                "nome_fantasia": cli_nome,
                "razao_social": cli_nome,
                "cnpj_cpf": cli_doc
            },
            "remessas_unificadas": [{
                "nCodRem": nCodRem,
                "numero_remessa": str(num_rem),
                "data_previsao": cab.get("dPrevisao", ""),
                "valor_total": val_bruto,
                "faturada": "N"
            }],
            "total_enviado": tot_env,
            "valor_total_bruto": val_bruto,
            "valor_total_desconto": val_desc,
            "valor_total_liquido": val_liq,
            "itens": itens,
            "desconto_padrao_pct": 30.0,
            "condicao_comercial": "A_VISTA_AUTO",
            "status": "EM_ANDAMENTO"
        }

        res_salvar = self.salvar_acerto(payload_acerto)
        if res_salvar.get("success"):
            db.executar_query("""
                UPDATE consignacao_acertos
                SET data_inicio_prazo = :dt, dias_prazo = :dp, alerta_5d_enviado = 0, alerta_30d_enviado = 0
                WHERE codigo_acerto = :ca
            """, {"dt": dt_inicio, "dp": dias_prazo, "ca": cod_acerto}, is_select=False)
            return {"success": True, "codigo_acerto": cod_acerto, "message": f"Remessa #{num_rem} vinculada com sucesso! Prazo de {dias_prazo} dias iniciado em {dt_inicio}."}

        return res_salvar

    def atualizar_inicio_prazo(self, acerto_id: int, nova_data_inicio: str, dias_prazo: int = 30) -> Dict[str, Any]:
        """Atualiza a data de início e prazo da contagem."""
        try:
            db.executar_query("""
                UPDATE consignacao_acertos
                SET data_inicio_prazo = :dt, dias_prazo = :dp, alerta_5d_enviado = 0, alerta_30d_enviado = 0
                WHERE id = :id
            """, {"dt": nova_data_inicio[:10], "dp": dias_prazo, "id": int(acerto_id)}, is_select=False)
            return {"success": True, "message": "Prazo de consignação atualizado com sucesso!"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def verificar_alertas_prazos_consignacao(self) -> Dict[str, Any]:
        """
        Verifica remessas em aberto e dispara e-mail de alerta:
        - 5 dias antes de vencer o prazo de 30 dias.
        - Quando completar 30 dias (vencido o prazo para contagem física).
        Destinatários: faturamentoedicoes@comshalom.org e comprasedicoes@comshalom.org
        Remetente: logisticaedicoes@gmail.com
        """
        destinatarios = ["faturamentoedicoes@comshalom.org", "comprasedicoes@comshalom.org"]
        acertos = self.listar_acertos()
        alertas_disparados = []

        import alertas_email

        for ac in acertos:
            st = ac.get("status")
            if st == "FINALIZADO_OMIE":
                continue

            dias_rest = ac.get("dias_restantes", 30)
            alerta_5d = int(ac.get("alerta_5d_enviado") or 0)
            alerta_30d = int(ac.get("alerta_30d_enviado") or 0)
            cli = ac.get("cliente_nome", "Cliente")
            rems = [f"#{r.get('numero_remessa') or r}" for r in (ac.get("remessas_unificadas") or [])]
            rems_txt = ", ".join(rems) if rems else ac.get("codigo_acerto")
            dt_venc = ac.get("data_vencimento", "")
            ac_id = ac.get("id")

            # Alerta de 5 dias
            if dias_rest <= 5 and dias_rest > 0 and alerta_5d == 0:
                assunto = f"⏳ [Consignação] Faltam {dias_rest} dias para acerto: {cli} (Remessa {rems_txt})"
                corpo = f"""
                <div style="font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; padding: 25px; border-radius: 8px;">
                    <h2 style="color: #f59e0b; margin-top: 0;">⏳ Alerta de Consignação - Vencimento Próximo</h2>
                    <p style="font-size: 1.05rem;">Atenção Logística e Faturamento,</p>
                    <p>O consignado abaixo está a <strong>{dias_rest} dias de completar o ciclo de 30 dias</strong>:</p>
                    <ul style="background: rgba(255,255,255,0.05); padding: 15px 25px; border-radius: 6px; line-height: 1.8;">
                        <li><strong>Cliente:</strong> {cli}</li>
                        <li><strong>Remessa(s):</strong> {rems_txt}</li>
                        <li><strong>Peças Enviadas:</strong> {ac.get('total_enviado')} un</li>
                        <li><strong>Data Limite da Contagem:</strong> {dt_venc}</li>
                    </ul>
                    <p style="color: #cbd5e1;">Favor entrar em contato com a vendedora/responsável para agendar o recolhimento ou contagem física do estoque.</p>
                </div>
                """
                ok, msg = alertas_email.enviar_email_alerta(destinatarios=destinatarios, assunto_custom=assunto, html_custom=corpo)
                if ok:
                    db.executar_query("UPDATE consignacao_acertos SET alerta_5d_enviado = 1 WHERE id = :id", {"id": ac_id}, is_select=False)
                    alertas_disparados.append(f"Alerta 5 dias enviado para {cli} ({rems_txt})")

            # Alerta de 30 dias (Vencido)
            elif dias_rest <= 0 and alerta_30d == 0:
                dias_venc = abs(dias_rest)
                assunto = f"🚨 [Consignação URGENTE] Prazo de 30 Dias Vencido: {cli} (Remessa {rems_txt})"
                corpo = f"""
                <div style="font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; padding: 25px; border-radius: 8px;">
                    <h2 style="color: #ef4444; margin-top: 0;">🚨 Alerta de Consignação Vencida - Fazer Contagem!</h2>
                    <p style="font-size: 1.05rem;">Atenção Logística e Faturamento,</p>
                    <p>O prazo de 30 dias do consignado <strong>completou o ciclo e venceu</strong>{' hoje' if dias_venc == 0 else f' há {dias_venc} dias'}:</p>
                    <ul style="background: rgba(255,255,255,0.05); padding: 15px 25px; border-radius: 6px; line-height: 1.8;">
                        <li><strong>Cliente:</strong> {cli}</li>
                        <li><strong>Remessa(s):</strong> {rems_txt}</li>
                        <li><strong>Peças em Consignação:</strong> {ac.get('total_enviado')} un</li>
                        <li><strong>Data Limite Original:</strong> {dt_venc}</li>
                    </ul>
                    <p style="color: #fca5a5; font-weight: bold;">É necessário realizar a contagem física das peças devolvidas e faturar os itens vendidos no Omie ERP imediatamente.</p>
                </div>
                """
                ok, msg = alertas_email.enviar_email_alerta(destinatarios=destinatarios, assunto_custom=assunto, html_custom=corpo)
                if ok:
                    db.executar_query("UPDATE consignacao_acertos SET alerta_30d_enviado = 1 WHERE id = :id", {"id": ac_id}, is_select=False)
                    alertas_disparados.append(f"Alerta 30 dias enviado para {cli} ({rems_txt})")

        return {"success": True, "alertas_enviados": alertas_disparados}

    def obter_acerto(self, acerto_id_ou_cod: Any) -> Dict[str, Any]:
        """Obtém um acerto completo e seus itens do Turso DB."""
        val_id = int(acerto_id_ou_cod) if str(acerto_id_ou_cod).isdigit() else 0
        cod_str = str(acerto_id_ou_cod).strip()
        sql = "SELECT * FROM consignacao_acertos WHERE id = :id_val OR codigo_acerto = :cod_val"
        df = db.executar_query(sql, {"id_val": val_id, "cod_val": cod_str})
        rows = _df_to_records(df)
        if not rows:
            return {}
        
        acerto = rows[0]
        rec_id = acerto.get("id")
        if acerto.get("remessas_unificadas") and isinstance(acerto["remessas_unificadas"], str):
            try:
                acerto["remessas_unificadas"] = json.loads(acerto["remessas_unificadas"])
            except Exception:
                pass

        sql_itens = "SELECT * FROM consignacao_acerto_itens WHERE acerto_id = :id ORDER BY descricao ASC"
        df_itens = db.executar_query(sql_itens, {"id": rec_id})
        rows_itens = _df_to_records(df_itens)
        cache = self._carregar_produtos_cache()
        itens = []
        for it_dict in rows_itens:
            if it_dict.get("remessas_origem") and isinstance(it_dict["remessas_origem"], str):
                try:
                    it_dict["remessas_origem"] = json.loads(it_dict["remessas_origem"])
                except Exception:
                    pass

            sku = str(it_dict.get("sku") or "").strip()
            ncod = int(it_dict.get("codigo_produto_omie") or 0)
            fam = it_dict.get("familia") or ""
            if not fam:
                if ncod in cache["by_id"]:
                    fam = cache["by_id"][ncod].get("familia") or ""
                elif sku in cache.get("by_sku", {}):
                    fam = cache["by_sku"][sku].get("familia") or ""
            it_dict["familia"] = fam
            itens.append(it_dict)

        acerto["itens"] = itens
        return acerto

    def integrar_omie(self, acerto: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa as operações no Omie para liquidar o acerto:
        1. Gera Devolução de Remessa (CFOP 1.917) para reincorporar peças devolvidas ao estoque
        2. Gera Pedido de Venda no Omie (Cenário Consignação Sem Contrato) para as peças vendidas
        """
        acerto_id = acerto.get("id")
        cod_cli = int(acerto.get("codigo_cliente_omie") or 0)
        itens = acerto.get("itens", [])

        itens_vendidos = [x for x in itens if int(x.get("qtd_vendida", 0)) > 0]
        itens_devolvidos = [x for x in itens if int(x.get("qtd_retorno", 0)) > 0]

        resultado = {
            "success": True,
            "pedido_venda": None,
            "devolucoes": [],
            "erros": []
        }

        # 1. Gerar Pedido de Venda no Omie para os itens vendidos (ou vincular pedido já lançado manualmente)
        pedido_manual = str(acerto.get("numero_pedido_manual") or "").strip()
        
        # Se o usuário já lançou o pedido manualmente no Omie (ex: Pedido 17845)
        if pedido_manual:
            resultado["pedido_venda"] = {
                "numero_pedido": pedido_manual,
                "codigo_pedido": 0,
                "codigo_status": "0",
                "descricao_status": f"Pedido de Venda #{pedido_manual} vinculado manualmente com sucesso!"
            }
        elif itens_vendidos and cod_cli:
            try:
                cache = self._carregar_produtos_cache()
                det_produtos = []
                for idx, it in enumerate(itens_vendidos, 1):
                    sku = str(it.get("sku") or "").strip()
                    ncod = int(it.get("codigo_produto_omie") or it.get("codigo_produto") or it.get("id_produto") or 0)
                    if ncod <= 0 and sku:
                        ncod = int(cache.get("by_sku", {}).get(sku, {}).get("id_produto") or 0)
                    qtd = int(it.get("qtd_vendida"))
                    preco_tab = float(it.get("preco_unitario") or 0.0)
                    desc_pct = float(it.get("desconto_pct") or 30.0)
                    
                    det_produtos.append({
                        "ide": {
                            "codigo_item_integracao": f"IT_{idx}_{sku}"[:20]
                        },
                        "produto": {
                            "codigo_produto": ncod,
                            "quantidade": qtd,
                            "valor_unitario": preco_tab,
                            "percentual_desconto": desc_pct,
                            "tipo_desconto": "P"
                        },
                        "inf_adic": {
                            "codigo_categoria_item": CATEGORIA_COMERCIAL_PADRAO,
                            "codigo_cenario_impostos_item": str(CENARIO_VENDA_CONSIGNACAO),
                            "codigo_local_estoque": LOCAL_ESTOQUE_MATRIZ
                        }
                    })

                cli_email = ""
                try:
                    cli_det = self.client.executar("geral/clientes/", "ConsultarCliente", [{"codigo_cliente_omie": cod_cli}])
                    cli_email = str(cli_det.get("email") or "").strip()
                except Exception:
                    pass

                cod_vend = int(acerto.get("codigo_vendedora") or 1818533448)

                cod_int_pv = f"PV_CONSIG_{int(time.time())}"[:20]
                payload_pv = {
                    "cabecalho": {
                        "codigo_cliente": cod_cli,
                        "codigo_cenario_impostos": str(CENARIO_VENDA_CONSIGNACAO),
                        "data_previsao": datetime.now().strftime("%d/%m/%Y"),
                        "etapa": "20", # Etapa Separar Estoque
                        "codigo_parcela": "000",
                        "codigo_pedido_integracao": cod_int_pv,
                        "origem_pedido": "API"
                    },
                    "informacoes_adicionais": {
                        "codVend": cod_vend,
                        "codigo_categoria": CATEGORIA_COMERCIAL_PADRAO,
                        "codigo_conta_corrente": CONTA_CORRENTE_MATRIZ,
                        "consumidor_final": "S",
                        "enviar_email": "S",
                        "utilizar_emails": cli_email,
                        "dados_adicionais_nf": f"Venda de mercadoria remetida em consignação sem contrato - Acerto {acerto.get('codigo_acerto')}"
                    },
                    "det": det_produtos
                }

                res_pv = self.client.executar("produtos/pedido/", "IncluirPedido", [payload_pv])
                # Omie retorna { "numero_pedido": "...", "codigo_pedido": ..., "codigo_status": "0", "descricao_status": "..." }
                c_status = str(res_pv.get("codigo_status") or res_pv.get("cCodStatus") or "")
                num_ped = res_pv.get("numero_pedido") or res_pv.get("cNumeroPedido")

                if (c_status == "0" or num_ped) and not res_pv.get("faultstring"):
                    resultado["pedido_venda"] = {
                        "numero_pedido": num_ped,
                        "codigo_pedido": res_pv.get("codigo_pedido") or res_pv.get("nCodPed"),
                        "codigo_status": c_status,
                        "descricao_status": res_pv.get("descricao_status") or "Pedido de Venda cadastrado com sucesso!"
                    }
                else:
                    msg_erro = res_pv.get("faultstring") or res_pv.get("descricao_status") or res_pv.get("cDesStatus") or "Erro ao gerar pedido no Omie"
                    resultado["erros"].append(f"Erro Pedido de Venda: {msg_erro}")
            except Exception as e:
                resultado["erros"].append(f"Exceção Pedido de Venda: {str(e)}")

        # 2. Registrar Devolução de Remessa no Omie
        # Descobrir UF do cliente para definir CFOP (1.917 no CE ou 2.917 fora do CE)
        uf_cli = "CE"
        try:
            cli_det = self.client.executar("geral/clientes/", "ConsultarCliente", [{"codigo_cliente_omie": cod_cli}])
            uf_cli = str(cli_det.get("estado") or "CE").upper().strip()
        except Exception:
            pass
        cfop_retorno = "1.917" if uf_cli == "CE" else "2.917"

        remessas_unificadas = acerto.get("remessas_unificadas", [])
        for rem_info in remessas_unificadas:
            nCodRem = rem_info.get("nCodRem") if isinstance(rem_info, dict) else None
            num_rem = rem_info.get("numero_remessa") if isinstance(rem_info, dict) else str(rem_info)
            is_faturada = None
            if isinstance(rem_info, dict) and "faturada" in rem_info:
                is_faturada = (rem_info.get("faturada") == "S")

            if nCodRem:
                # Se não sabemos se está faturada pelo cache, consultar o cabeçalho no Omie
                if is_faturada is None:
                    try:
                        r_det = self.obter_detalhes_remessa(nCodRem)
                        is_faturada = (r_det.get("cabec", {}).get("faturada") == "S")
                    except Exception:
                        is_faturada = True # fallback
                
                # Se a remessa NÃO foi faturada no Omie (manual em aberto), NÃO gera devolução fiscal
                if not is_faturada:
                    resultado["devolucoes"].append({
                        "numero_remessa": num_rem,
                        "nCodRem": nCodRem,
                        "faturada": "N",
                        "tipo": "MANUAL_NAO_FATURADA",
                        "mensagem": f"Remessa #{num_rem} não foi faturada no Omie. Favor excluir a remessa manualmente no Omie após validar com o vendedor para estornar o estoque."
                    })
                    continue

                # Se a remessa FOI faturada no Omie, gera a Devolução de Remessa oficial (CFOP 1.917)
                try:
                    payload_dev = {"nCodRem": int(nCodRem)}
                    res_dev = self.client.executar("produtos/remessa/", "DevolverRemessa", [payload_dev])
                    
                    # 2.1 Ajustar a Nota de Entrada gerada automaticamente: Categoria 2.01.01, CFOP correto e Movimentar Estoque (cNaoMovEstoque: 'N')
                    nIdDev = res_dev.get("nIdDevolucao")
                    if nIdDev:
                        try:
                            nota_det = self.client.executar("produtos/notaentrada/", "ConsultarNotaEnt", [{"nCodNotaEnt": int(nIdDev)}])
                            if nota_det and "cabec" in nota_det:
                                prods_alt = []
                                for p in nota_det.get("produtos", []):
                                    prods_alt.append({
                                        "nCodIt": p.get("nCodIt"),
                                        "nCodProd": p.get("nCodProd"),
                                        "cCFOP": cfop_retorno,
                                        "nQtde": p.get("nQtde"),
                                        "nValUnit": p.get("nValUnit"),
                                        "codigo_local_estoque": LOCAL_ESTOQUE_MATRIZ,
                                        "infAdicItem": {
                                            "cNaoMovEstoque": "N"
                                        },
                                        "cAcaoItem": "A"
                                    })
                                payload_alt_nota = {
                                    "cabec": {
                                        "nCodNotaEnt": int(nIdDev),
                                        "nCodCli": nota_det["cabec"].get("nCodCli") or cod_cli
                                    },
                                    "infAdic": {
                                        "cCodCateg": CATEGORIA_RETORNO_REMESSA_PADRAO
                                    },
                                    "produtos": prods_alt
                                }
                                self.client.executar("produtos/notaentrada/", "AlterarNotaEnt", [payload_alt_nota])
                        except Exception as e_ne:
                            print(f"[CONSIGNACAO] Aviso ao ajustar Nota de Entrada {nIdDev}: {e_ne}")

                    resultado["devolucoes"].append({
                        "numero_remessa": num_rem,
                        "nCodRem": nCodRem,
                        "resultado": res_dev
                    })
                except Exception as ex_dev:
                    resultado["devolucoes"].append({
                        "numero_remessa": num_rem,
                        "nCodRem": nCodRem,
                        "erro": str(ex_dev)
                    })

        # 3. Atualizar status no Turso DB
        # Se foi concluído ou se já tinha devolução feita e vinculou o pedido
        tem_devolucao_ok = any(
            d.get("resultado", {}).get("cCodStatus") == "0" or 
            "sucesso" in str(d.get("resultado", "")).lower() or
            d.get("tipo") == "MANUAL_NAO_FATURADA"
            for d in resultado["devolucoes"]
        )
        tem_pv_ok = bool(resultado["pedido_venda"])

        if tem_pv_ok and (tem_devolucao_ok or not resultado["devolucoes"]):
            novo_status = "FINALIZADO_OMIE"
            resultado["success"] = True
        elif not resultado["erros"]:
            novo_status = "FINALIZADO_OMIE"
            resultado["success"] = True
        else:
            novo_status = "ERRO_INTEGRACAO"
            resultado["success"] = False

        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dados_pv_str = json.dumps(resultado["pedido_venda"], ensure_ascii=False) if resultado["pedido_venda"] else ""
        dados_dev_str = json.dumps(resultado["devolucoes"], ensure_ascii=False)

        sql_up = """
            UPDATE consignacao_acertos SET
                status = :st,
                dados_pedido_venda_omie = :pv,
                dados_devolucao_omie = :dev,
                atualizado_em = :agora
            WHERE id = :id
        """
        db.executar_query(sql_up, {
            "st": novo_status,
            "pv": dados_pv_str,
            "dev": dados_dev_str,
            "agora": agora,
            "id": acerto_id
        }, is_select=False)

        resultado["novo_status"] = novo_status
        return resultado

    CLIENTE_EVENTOS_ID = 2266589781

    def listar_remessas_eventos(self) -> List[Dict[str, Any]]:
        """Lista as remessas em aberto do cliente EVENTOS (ID 2266589781)."""
        return self.listar_remessas_cliente(self.CLIENTE_EVENTOS_ID)

    def salvar_remessa_evento(self, dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cria ou atualiza uma remessa em aberto para o cliente EVENTOS.
        Suporta inserção por leitor de código de barras / mobile.
        """
        nCodRem = int(dados.get('nCodRem') or 0)
        nome_evento = str(dados.get('nome_evento') or 'Evento / Stand Comercial').strip()
        itens = dados.get('itens', [])
        if not itens:
            return {"success": False, "message": "Nenhum produto adicionado na remessa de evento."}

        cache = self._carregar_produtos_cache()

        produtos_payload = []
        tot_pecas = 0
        tot_valor = 0.0

        for idx, it in enumerate(itens, 1):
            sku = str(it.get('sku') or '').strip().upper()
            ncod = int(it.get('codigo_produto') or it.get('nCodProd') or 0)
            qtd = int(it.get('quantidade') or it.get('nQtde') or 1)
            val_unit = float(it.get('preco_unitario') or it.get('nValUnit') or 0.0)

            if ncod == 0 and sku:
                p_info = cache.get('by_sku', {}).get(sku)
                if p_info:
                    ncod = int(p_info.get('id_produto') or p_info.get('codigo_produto') or 0)
                    if val_unit <= 0:
                        val_unit = float(p_info.get('valor_unitario') or 0.0)

            if val_unit <= 0 and ncod in cache.get('by_id', {}):
                val_unit = float(cache['by_id'][ncod].get('valor_unitario') or 0.0)

            tot_pecas += qtd
            tot_valor += (qtd * val_unit)

            produtos_payload.append({
                "cCFOP": "5.917",
                "cCodItInt": f"EV_{idx}_{sku}"[:20],
                "nCodIt": 0,
                "nCodProd": ncod,
                "nQtde": qtd,
                "nValUnit": val_unit
            })

        if nCodRem > 0:
            # Alterar remessa existente
            try:
                rem_existente = self.client.executar("produtos/remessa/", "ConsultarRemessa", [{"nCodRem": nCodRem}])
                if not rem_existente or "cabec" not in rem_existente:
                    return {"success": False, "message": f"Remessa #{nCodRem} não encontrada no Omie."}

                cabec = rem_existente.get("cabec", {})
                frete = rem_existente.get("frete", {})
                infAdic = rem_existente.get("infAdic", {})

                cabec["codigo_cenario_impostos"] = CENARIO_FISCAL_5917
                cabec["nCodCli"] = self.CLIENTE_EVENTOS_ID

                payload_alterar = {
                    "cabec": cabec,
                    "frete": frete,
                    "infAdic": infAdic,
                    "obs": {"cObs": f"Remessa Evento: {nome_evento}"},
                    "produtos": produtos_payload
                }

                def strip_bad_keys(d):
                    if isinstance(d, dict):
                        for k in list(d.keys()):
                            if k.lower() in ('ncodcen', 'ccodcen'):
                                d.pop(k, None)
                            else:
                                strip_bad_keys(d[k])
                    elif isinstance(d, list):
                        for item in d:
                            strip_bad_keys(item)

                strip_bad_keys(payload_alterar)
                res_omie = self.client.executar("produtos/remessa/", "AlterarRemessa", [payload_alterar])
                cCodStatus = str(res_omie.get("cCodStatus") or "")
                faultstring = res_omie.get("faultstring") or res_omie.get("cDesStatus") or ""

                if faultstring and ("ERROR" in faultstring.upper() or (cCodStatus and cCodStatus != "0")):
                    return {"success": False, "message": f"Erro Omie: {faultstring}", "raw_omie": res_omie}

                return {
                    "success": True,
                    "nCodRem": nCodRem,
                    "numero_remessa": str(cabec.get("cNumeroRemessa") or nCodRem),
                    "total_pecas": tot_pecas,
                    "valor_total": tot_valor,
                    "message": f"Remessa #{cabec.get('cNumeroRemessa') or nCodRem} atualizada com sucesso no Omie ERP!"
                }
            except Exception as e:
                return {"success": False, "message": f"Exceção ao alterar remessa: {str(e)}"}
        else:
            # Criar nova remessa para EVENTOS
            cod_int_rem = f"EVT_{int(time.time())}"[:20]
            payload_nova = {
                "cabec": {
                    "cCodIntRem": cod_int_rem,
                    "dPrevisao": datetime.now().strftime("%d/%m/%Y"),
                    "nCodCli": self.CLIENTE_EVENTOS_ID,
                    "nCodRem": 0,
                    "nCodVend": "1818533592", # Lyvia Rodrigues ou vendedor padrão
                    "codigo_cenario_impostos": CENARIO_FISCAL_5917
                },
                "frete": {
                    "cEspVol": "VOLUMES",
                    "cMarVol": "",
                    "cNumVol": "1",
                    "cPlaca": "",
                    "cTpFrete": "9",
                    "cUF": "",
                    "nCodTransp": 0,
                    "nPesoBruto": round(tot_pecas * 0.3, 2),
                    "nPesoLiq": round(tot_pecas * 0.28, 2),
                    "nQtdVol": 1,
                    "nValFrete": 0,
                    "nValOutras": 0,
                    "nValSeguro": 0
                },
                "infAdic": {
                    "cCodCateg": CATEGORIA_RECEITA,
                    "cConsFinal": "S",
                    "cContato": "EVENTOS SHALOM",
                    "cDadosAdic": f"Remessa de mercadorias para evento em consignacao - {nome_evento}",
                    "cNumCtr": "",
                    "cPedido": "",
                    "nCodProj": 0
                },
                "obs": {
                    "cObs": f"Evento: {nome_evento} (Remessa em Aberto)"
                },
                "produtos": produtos_payload
            }

            try:
                res = self.client.executar("produtos/remessa/", "IncluirRemessa", [payload_nova])
                c_status = str(res.get("cCodStatus") or "")
                num_rem = res.get("cNumeroRemessa") or str(res.get("nCodRem") or "")
                faultstring = res.get("faultstring") or res.get("cDesStatus") or ""

                if (c_status == "0" or num_rem) and not res.get("faultstring"):
                    return {
                        "success": True,
                        "nCodRem": res.get("nCodRem"),
                        "numero_remessa": num_rem,
                        "total_pecas": tot_pecas,
                        "valor_total": tot_valor,
                        "message": f"Nova Remessa #{num_rem} criada com sucesso para EVENTOS no Omie ERP!"
                    }
                else:
                    return {"success": False, "message": f"Erro Omie: {faultstring}", "raw_omie": res}
            except Exception as e:
                return {"success": False, "message": f"Exceção ao incluir remessa no Omie: {str(e)}"}


