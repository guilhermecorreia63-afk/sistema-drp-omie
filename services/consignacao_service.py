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
from datetime import datetime
from typing import Dict, List, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database as db
from omie_client import OmieClient

# ID do cenário fiscal oficial no Omie para Venda Mercadoria (Consignação sem contrato / 1800980891)
CENARIO_VENDA_CONSIGNACAO = 1800980891 
# ID da categoria comercial padrão Matriz
CATEGORIA_COMERCIAL_PADRAO = "1.01.01"
# Categoria padrão para o Retorno de Remessa (Nota de Entrada): Compras de Mercadorias para Revenda
CATEGORIA_RETORNO_REMESSA_PADRAO = "2.01.01"
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
        if os.path.exists(caminho_json):
            try:
                with open(caminho_json, 'r', encoding='utf-8') as f:
                    prods = json.load(f)
                    for p in prods:
                        if p.get('id_produto'):
                            id_map[int(p['id_produto'])] = p
                        if p.get('codigo'):
                            sku_map[str(p['codigo']).strip()] = p
            except Exception as e:
                print(f"[CONSIGNACAO] Erro ao carregar cache de produtos: {e}")
        
        self._produtos_cache = {"by_id": id_map, "by_sku": sku_map}
        return self._produtos_cache

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
                                "cenario_impostos": c.get('codigo_cenario_impostos')
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
                "valor_total": float(cab.get('nValorTotal') or 0.0)
            })

            for p in rem.get('produtos', []):
                ncod = int(p.get('nCodProd') or 0)
                sku = str(p.get('cCodItInt') or p.get('cCodigo') or '').strip()
                desc = p.get('cDescricao') or ''
                qtd = int(p.get('nQtde') or 0)
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

        cod_cli = dados_acerto.get("codigo_cliente_omie")
        cli_nome = dados_acerto.get("cliente_nome")
        cli_doc = dados_acerto.get("cliente_cnpj_cpf")
        rems_json = json.dumps(dados_acerto.get("remessas_unificadas", []), ensure_ascii=False)
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
            for it in itens:
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
                    "sku": it.get("sku", ""),
                    "ncod": int(it.get("codigo_produto", 0)),
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
        """Lista histórico de acertos salvos no Turso DB."""
        try:
            sql = "SELECT * FROM consignacao_acertos ORDER BY id DESC LIMIT 50"
            df = db.executar_query(sql)
            rows = _df_to_records(df)
            res = []
            for r_dict in rows:
                if r_dict.get("remessas_unificadas") and isinstance(r_dict["remessas_unificadas"], str):
                    try:
                        r_dict["remessas_unificadas"] = json.loads(r_dict["remessas_unificadas"])
                    except Exception:
                        pass
                res.append(r_dict)
            return res
        except Exception as e:
            print(f"[CONSIGNACAO] Erro ao listar acertos: {e}")
            return []

    def obter_acerto(self, acerto_id: int) -> Dict[str, Any]:
        """Obtém um acerto completo e seus itens do Turso DB."""
        sql = "SELECT * FROM consignacao_acertos WHERE id = :id"
        df = db.executar_query(sql, {"id": acerto_id})
        rows = _df_to_records(df)
        if not rows:
            return {}
        
        acerto = rows[0]
        if acerto.get("remessas_unificadas") and isinstance(acerto["remessas_unificadas"], str):
            try:
                acerto["remessas_unificadas"] = json.loads(acerto["remessas_unificadas"])
            except Exception:
                pass

        sql_itens = "SELECT * FROM consignacao_acerto_itens WHERE acerto_id = :id ORDER BY descricao ASC"
        df_itens = db.executar_query(sql_itens, {"id": acerto_id})
        rows_itens = _df_to_records(df_itens)
        itens = []
        for it_dict in rows_itens:
            if it_dict.get("remessas_origem") and isinstance(it_dict["remessas_origem"], str):
                try:
                    it_dict["remessas_origem"] = json.loads(it_dict["remessas_origem"])
                except Exception:
                    pass
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
                det_produtos = []
                for idx, it in enumerate(itens_vendidos, 1):
                    ncod = int(it.get("codigo_produto_omie") or it.get("codigo_produto") or 0)
                    qtd = int(it.get("qtd_vendida"))
                    preco_tab = float(it.get("preco_unitario") or 0.0)
                    desc_pct = float(it.get("desconto_pct") or 30.0)
                    sku = str(it.get("sku") or "")
                    
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

                cod_int_pv = f"PV_CONSIG_{int(time.time())}"[:20]
                payload_pv = {
                    "cabecalho": {
                        "codigo_cliente": cod_cli,
                        "codigo_cenario_impostos": str(CENARIO_VENDA_CONSIGNACAO),
                        "data_previsao": datetime.now().strftime("%d/%m/%Y"),
                        "etapa": "10", # Etapa inicial Proposta / Pedido
                        "codigo_parcela": "000",
                        "codigo_integracao": cod_int_pv,
                        "origem_pedido": "API"
                    },
                    "informacoes_adicionais": {
                        "codigo_categoria": CATEGORIA_COMERCIAL_PADRAO,
                        "codigo_conta_corrente": CONTA_CORRENTE_MATRIZ,
                        "consumidor_final": "S",
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
        remessas_unificadas = acerto.get("remessas_unificadas", [])
        for rem_info in remessas_unificadas:
            nCodRem = rem_info.get("nCodRem") if isinstance(rem_info, dict) else None
            num_rem = rem_info.get("numero_remessa") if isinstance(rem_info, dict) else str(rem_info)
            if nCodRem:
                try:
                    # Garantir que a Categoria do Retorno de Remessa seja padronizada como Compras de Mercadorias para Revenda (2.01.01)
                    try:
                        rem_det = self.obter_detalhes_remessa(int(nCodRem))
                        if rem_det and "cabec" in rem_det:
                            inf_adic = rem_det.get("infAdic") or {}
                            if inf_adic.get("cCodCateg") != CATEGORIA_RETORNO_REMESSA_PADRAO:
                                inf_adic["cCodCateg"] = CATEGORIA_RETORNO_REMESSA_PADRAO
                                rem_det["infAdic"] = inf_adic
                                self.client.executar("produtos/remessa/", "AlterarRemessa", [rem_det])
                    except Exception as e_cat:
                        print(f"[CONSIGNACAO] Aviso ao definir categoria 2.01.01 na remessa {nCodRem}: {e_cat}")

                    payload_dev = {"nCodRem": int(nCodRem)}
                    res_dev = self.client.executar("produtos/remessa/", "DevolverRemessa", [payload_dev])
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
        tem_devolucao_ok = any(d.get("resultado", {}).get("cCodStatus") == "0" or "sucesso" in str(d.get("resultado", "")).lower() for d in resultado["devolucoes"])
        tem_pv_ok = bool(resultado["pedido_venda"])

        if tem_pv_ok and (tem_devolucao_ok or not resultado["devolucoes"]):
            novo_status = "FINALIZADO_OMIE"
        elif not resultado["erros"]:
            novo_status = "FINALIZADO_OMIE"
        else:
            novo_status = "ERRO_INTEGRACAO"

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

