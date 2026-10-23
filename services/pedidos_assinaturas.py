# -*- coding: utf-8 -*-
"""
services/pedidos_assinaturas.py
================================
Gerenciamento de Pedidos de Venda de Assinaturas (Pão da Vida):
1. Lançamento de Pedidos no Omie ERP com Cenário Fiscal, Departamentos, Parcelas, Frete e Combos
2. Armazenamento seguro no Turso Cloud DB (tabelas assinaturas_pedidos_proximo_envio e assinantes_base)
3. Consulta de Metadados e Busca Rápida de Clientes
"""

import os
import sys
import time
import json
from datetime import datetime
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db
from omie_client import OmieClient
from services.frenet_service import cotar_frete_frenet

CENARIO_FISCAL_PADRAO = 1800980891 # Venda de Mercadoria - Livrarias/ Dif trans/PJ
CATEGORIA_RECEITA = "1.01.01" # Receita Comercial
CONTA_CORRENTE_MATRIZ = 1794541768
LOCAL_ESTOQUE_MATRIZ = 1794541740
VENDEDOR_PADRAO = 1818533448

DEPARTAMENTOS = [
    {"codigo": "1807684664", "descricao": "Comercial"},
    {"codigo": "1807684776", "descricao": "Loja Web / Ecommerce"}
]

COMBOS_ASSINATURA = [
    {"sku": "000223", "descricao": "Kit Assinatura Pão da Vida (Padrão)", "id_produto": 1863902383, "valor_unitario": 89.90},
    {"sku": "PRD00379", "descricao": "Assinatura Pão da Vida 1", "id_produto": 2027435776, "valor_unitario": 89.90},
    {"sku": "PRD00574", "descricao": "Assinatura Pão da Vida 2", "id_produto": 2148782047, "valor_unitario": 89.90}
]

PARCELAS_CADASTRO = [
    {"codigo": "000", "descricao": "À Vista"},
    {"codigo": "001", "descricao": "1 Parcela (Cartão / Boleto)"},
    {"codigo": "002", "descricao": "2 Parcelas"},
    {"codigo": "003", "descricao": "3 Parcelas"},
    {"codigo": "004", "descricao": "4 Parcelas"},
    {"codigo": "005", "descricao": "5 Parcelas"},
    {"codigo": "006", "descricao": "6 Parcelas"},
    {"codigo": "007", "descricao": "7 Parcelas"},
    {"codigo": "OIW", "descricao": "12 Parcelas (Anual)"},
    {"codigo": "A30", "descricao": "Para 30 dias"},
    {"codigo": "A15", "descricao": "Para 15 dias"},
    {"codigo": "A07", "descricao": "Para 7 dias"},
    {"codigo": "999", "descricao": "Informar número de parcelas"}
]

class PedidosAssinaturasService:
    def __init__(self):
        self.client = OmieClient("MATRIZ")

    def obter_metadados(self) -> Dict[str, Any]:
        """Retorna departamentos, cenário fiscal, condições de parcelamento e combos de assinatura."""
        return {
            "success": True,
            "cenario_fiscal": {
                "codigo": CENARIO_FISCAL_PADRAO,
                "descricao": "Venda de Mercadoria - Livrarias/ Dif trans/PJ"
            },
            "categoria": {
                "codigo": CATEGORIA_RECEITA,
                "descricao": "Receita Comercial"
            },
            "departamentos": DEPARTAMENTOS,
            "parcelas": PARCELAS_CADASTRO,
            "combos": COMBOS_ASSINATURA,
            "formas_envio": [
                {"codigo": "PAC", "descricao": "PAC - Correios Nacional"},
                {"codigo": "SEDEX", "descricao": "SEDEX - Correios Expresso"},
                {"codigo": "FRETE_GRATIS", "descricao": "Frete Grátis"},
                {"codigo": "JT", "descricao": "J&T Express"},
                {"codigo": "TOTAL", "descricao": "Total Express"},
                {"codigo": "ROBERTO_SOUZA", "descricao": "Roberto Souza (Entregador Próprio Fortaleza)"}
            ]
        }

    def buscar_clientes_omie(self, termo: str) -> List[Dict[str, Any]]:
        """Busca rápida de clientes no Omie por nome ou CPF/CNPJ."""
        termo = str(termo or "").strip()
        if not termo or len(termo) < 2:
            return []

        doc_clean = termo.replace(".", "").replace("-", "").replace("/", "")
        filtro = {}
        if doc_clean.isdigit() and len(doc_clean) in (11, 14):
            filtro["cnpj_cpf"] = termo
        else:
            filtro["nome_fantasia"] = termo

        try:
            res = self.client.executar("geral/clientes/", "ListarClientes", [{
                "pagina": 1,
                "registros_por_pagina": 15,
                "clientesFiltro": filtro
            }])
            clientes_raw = res.get("clientes_cadastro", [])
            resultado = []
            for c in clientes_raw:
                end_ent = c.get("enderecoEntrega") or {}
                rua = end_ent.get("end_entrega_endereco") or c.get("endereco") or ""
                num = end_ent.get("end_entrega_numero") or c.get("endereco_numero") or ""
                comp = end_ent.get("end_entrega_complemento") or c.get("complemento") or ""
                bairro = end_ent.get("end_entrega_bairro") or c.get("bairro") or ""
                cid_raw = end_ent.get("end_entrega_cidade") or c.get("cidade") or ""
                cid = cid_raw.split("(")[0].strip() if "(" in cid_raw else cid_raw.strip()
                uf = end_ent.get("end_entrega_estado") or c.get("estado") or ""
                cep = end_ent.get("end_entrega_cep") or c.get("cep") or ""

                resultado.append({
                    "codigo_cliente_omie": c.get("codigo_cliente_omie"),
                    "nome": c.get("nome_fantasia") or c.get("razao_social"),
                    "razao_social": c.get("razao_social"),
                    "cpf_cnpj": c.get("cnpj_cpf"),
                    "email": c.get("email"),
                    "telefone": f"({c.get('telefone1_ddd', '')}) {c.get('telefone1_numero', '')}".strip(),
                    "rua": rua,
                    "numero": num,
                    "complemento": comp,
                    "bairro": bairro,
                    "cidade": cid,
                    "uf": uf,
                    "cep": cep
                })
            return resultado
        except Exception as e:
            print(f"[ASSINATURAS] Erro ao buscar clientes Omie: {e}")
            return []

    def lancar_pedido_venda_omie(self, dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gera e transmite um novo Pedido de Venda no Omie ERP e armazena na tabela
        assinaturas_pedidos_proximo_envio no Turso DB.
        """
        cod_cli = int(dados.get("codigo_cliente_omie") or 0)
        cli_nome = str(dados.get("cliente_nome") or "").strip()
        cpf_cnpj = str(dados.get("cpf_cnpj") or "").strip()

        if cod_cli <= 0 and not cli_nome:
            return {"success": False, "message": "Cliente não informado."}

        # Endereço
        rua = str(dados.get("rua") or "").strip()
        num = str(dados.get("numero") or "").strip()
        comp = str(dados.get("complemento") or "").strip()
        bairro = str(dados.get("bairro") or "").strip()
        cid = str(dados.get("cidade") or "").strip()
        uf = str(dados.get("uf") or "").strip().upper()
        cep = str(dados.get("cep") or "").strip()

        # Fiscais & Contábeis
        cenario_id = int(dados.get("codigo_cenario_impostos") or CENARIO_FISCAL_PADRAO)
        categoria = str(dados.get("codigo_categoria") or CATEGORIA_RECEITA)
        depto_cod = str(dados.get("codigo_departamento") or "1807684664") # Comercial padrão
        depto_nome = "Comercial" if depto_cod == "1807684664" else "Loja Web / Ecommerce"
        cod_parc = str(dados.get("forma_pagamento_codigo") or dados.get("codigo_parcela") or "000")

        # Logística & Frete
        forma_envio = str(dados.get("forma_envio") or "PAC").upper()
        val_frete = float(dados.get("valor_frete") or 0.0)

        # Produto
        sku = str(dados.get("sku_produto") or "000223").strip()
        qtd = int(dados.get("quantidade") or dados.get("quantidade_assinaturas") or 1)
        val_unit = float(dados.get("valor_unitario") or 89.90)
        val_total = (qtd * val_unit) + val_frete

        # Buscar ID Omie do produto
        ncod_prod = 1863902383 # 000223 padrão
        for c in COMBOS_ASSINATURA:
            if c["sku"] == sku:
                ncod_prod = c["id_produto"]
                break

        # Montar payload do Omie
        cod_int_pv = f"PV_ASSIN_{int(time.time())}"[:20]
        modalidade_frete = "0" if val_frete > 0 else "9"

        payload_frete = {
            "modalidade": modalidade_frete,
            "valor_frete": val_frete,
            "especie_volumes": "VOLUME",
            "quantidade_volumes": 1,
            "peso_bruto": round(qtd * 0.35, 3),
            "peso_liquido": round(qtd * 0.30, 3)
        }
        if forma_envio == "ROBERTO_SOUZA":
            payload_frete["codigo_transportadora"] = 1854969807 # Roberto Souza

        payload_pv = {
            "cabecalho": {
                "codigo_cliente": cod_cli,
                "codigo_cenario_impostos": str(cenario_id),
                "data_previsao": datetime.now().strftime("%d/%m/%Y"),
                "etapa": "20", # 20 = Separar Estoque
                "codigo_parcela": cod_parc,
                "codigo_pedido_integracao": cod_int_pv,
                "origem_pedido": "API"
            },
            "departamentos": [
                {
                    "cCodDepto": depto_cod,
                    "nPerc": 100,
                    "nValor": val_total,
                    "nValorFixo": "N"
                }
            ],
            "frete": payload_frete,
            "informacoes_adicionais": {
                "codVend": VENDEDOR_PADRAO,
                "codigo_categoria": categoria,
                "codigo_conta_corrente": CONTA_CORRENTE_MATRIZ,
                "consumidor_final": "S",
                "dados_adicionais_nf": f"Assinatura Pão da Vida ({sku}) - Envio {forma_envio}. Entregar em: {rua}, {num} {comp} - {bairro}, {cid}/{uf} CEP {cep}"[:250]
            },
            "det": [
                {
                    "ide": {
                        "codigo_item_integracao": f"IT_{sku}_{int(time.time())}"[:20]
                    },
                    "produto": {
                        "codigo_produto": ncod_prod,
                        "quantidade": qtd,
                        "valor_unitario": val_unit,
                        "tipo_desconto": "V",
                        "valor_desconto": 0,
                        "codigo_local_estoque": LOCAL_ESTOQUE_MATRIZ
                    }
                }
            ]
        }

        try:
            res_omie = self.client.executar("produtos/pedido/", "IncluirPedido", [payload_pv])
            c_status = str(res_omie.get("codigo_status") or res_omie.get("cCodStatus") or "")
            num_ped = res_omie.get("numero_pedido") or res_omie.get("cNumeroPedido")
            cod_ped_omie = int(res_omie.get("codigo_pedido") or res_omie.get("nCodPed") or 0)

            if not num_ped and (c_status != "0" or res_omie.get("faultstring")):
                msg_err = res_omie.get("faultstring") or res_omie.get("descricao_status") or "Erro Omie"
                return {"success": False, "message": f"Erro Omie ERP ao gerar pedido: {msg_err}", "raw_omie": res_omie}

            # Inserir no Turso DB na tabela de novos pedidos de envio
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            periodo = dados.get("periodo_envio") or f"LOTE_{datetime.now().strftime('%m/%Y')}"
            obs = str(dados.get("observacao") or f"Lançado via DRP Omie ({depto_nome})").strip()

            sql_insert = """
                INSERT INTO assinaturas_pedidos_proximo_envio (
                    numero_pedido, codigo_pedido_omie, codigo_cliente_omie, cliente_nome, cpf_cnpj,
                    rua, numero, complemento, bairro, cidade, uf, cep,
                    quantidade_assinaturas, periodo_envio, observacao, criado_em,
                    departamento, codigo_departamento, codigo_cenario_impostos, forma_pagamento_codigo,
                    forma_envio, valor_frete, valor_total, sku_produto, origem_cadastro
                ) VALUES (
                    :num_ped, :cod_ped, :cod_cli, :nome, :cpf,
                    :rua, :num, :comp, :bairro, :cid, :uf, :cep,
                    :qtd, :periodo, :obs, :agora,
                    :depto, :cod_depto, :cenario, :forma_pag,
                    :envio, :v_frete, :v_tot, :sku, 'NOVO_LANCAMENTO_OMIE'
                )
            """
            db.executar_query(sql_insert, {
                "num_ped": str(num_ped),
                "cod_ped": cod_ped_omie,
                "cod_cli": cod_cli,
                "nome": cli_nome,
                "cpf": cpf_cnpj,
                "rua": rua,
                "num": num,
                "comp": comp,
                "bairro": bairro,
                "cid": cid,
                "uf": uf,
                "cep": cep,
                "qtd": qtd,
                "periodo": periodo,
                "obs": obs,
                "agora": agora,
                "depto": depto_nome,
                "cod_depto": depto_cod,
                "cenario": cenario_id,
                "forma_pag": cod_parc,
                "envio": forma_envio,
                "v_frete": val_frete,
                "v_tot": val_total,
                "sku": sku
            }, is_select=False)

            return {
                "success": True,
                "numero_pedido": str(num_ped),
                "codigo_pedido_omie": cod_ped_omie,
                "cliente_nome": cli_nome,
                "valor_total": val_total,
                "message": f"Pedido de Venda #{num_ped} gerado com sucesso no Omie ERP e cadastrado no banco de dados para o próximo envio!"
            }

        except Exception as e:
            print(f"[ASSINATURAS] Exceção ao lançar pedido Omie: {e}")
            return {"success": False, "message": f"Falha na comunicação com Omie ERP: {str(e)}"}

    def sincronizar_pedidos_faturados_omie(self, dias_retroativos: int = 0, dias_atras: int = None, numero_pedido_especifico: str = None, max_paginas: int = 3) -> Dict[str, Any]:
        """
        Consulta pedidos faturados / concluídos no Omie ERP que contenham os combos de assinatura:
        - 000223 (Kit Pão da Vida Padrão, ID 1863902383)
        - PRD00379 (Assinatura Pão da Vida 1, ID 2027435776)
        - PRD00574 (Assinatura Pão da Vida 2, ID 2148782047)
        Extrai os dados do assinante e endereço de entrega e persiste diretamente no Turso Cloud DB.
        Por padrão busca APENAS a partir de hoje (dias_retroativos = 0) para evitar duplicidade.
        Permite também buscar um pedido específico diretamente pelo número (ex: 18022).
        """
        from datetime import timedelta
        dias = dias_atras if dias_atras is not None else dias_retroativos
        data_inicio = (datetime.now() - timedelta(days=dias)).strftime("%d/%m/%Y")
        
        combos_map = {
            "000223": {"sku": "000223", "id": 1863902383, "nome": "Kit Assinatura Pão da Vida (Padrão)"},
            "PRD00379": {"sku": "PRD00379", "id": 2027435776, "nome": "Assinatura Pão da Vida 1"},
            "PRD00574": {"sku": "PRD00574", "id": 2148782047, "nome": "Assinatura Pão da Vida 2"},
            1863902383: {"sku": "000223", "id": 1863902383, "nome": "Kit Assinatura Pão da Vida (Padrão)"},
            2027435776: {"sku": "PRD00379", "id": 2027435776, "nome": "Assinatura Pão da Vida 1"},
            2148782047: {"sku": "PRD00574", "id": 2148782047, "nome": "Assinatura Pão da Vida 2"}
        }

        pedidos_importados = []
        total_analisados = 0
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            # Caso 1: Pedido específico informado (ex: 18022)
            if numero_pedido_especifico:
                num_alvo = str(numero_pedido_especifico).strip()
                res = self.client.executar("produtos/pedido/", "ConsultarPedido", [{"numero_pedido": num_alvo}])
                pv = res.get("pedido_venda_produto")
                if not pv:
                    return {"success": False, "message": f"Pedido #{num_alvo} não encontrado no Omie ERP."}
                lista_batches = [[pv]]
            else:
                lista_batches = []
                for pag in range(1, max_paginas + 1):
                    payload = {
                        "pagina": pag,
                        "registros_por_pagina": 50,
                        "apenas_importado_api": "N",
                        "filtrar_por_data_de": data_inicio
                    }
                    res = self.client.executar("produtos/pedido/", "ListarPedidos", [payload])
                    lista_ped = res.get("pedido_venda_produto", [])
                    if not lista_ped:
                        break
                    lista_batches.append(lista_ped)
                    tot_pags = int(res.get("total_de_paginas") or 1)
                    if pag >= tot_pags:
                        break

            for batch in lista_batches:
                total_analisados += len(batch)
                for p in batch:
                    cab = p.get("cabecalho", {})
                    num_ped = str(cab.get("numero_pedido") or "")
                    cod_ped = int(cab.get("codigo_pedido") or 0)
                    cod_cli = int(cab.get("codigo_cliente") or 0)
                    etapa = str(cab.get("etapa") or "")

                    # Verificar se contém combo de assinatura
                    itens = p.get("itens", []) or p.get("det", [])
                    qtd_assinaturas = 0
                    combo_identificado = "000223"
                    val_tot_itens = 0.0

                    for it in itens:
                        prod = it.get("produto") if isinstance(it.get("produto"), dict) else it
                        sku_item = str(prod.get("codigo_produto_integracao") or prod.get("codigo") or "").strip()
                        cid_item = prod.get("codigo_produto")
                        q_item = int(prod.get("quantidade") or 0)
                        v_unit = float(prod.get("valor_unitario") or 0.0)

                        if sku_item in combos_map:
                            qtd_assinaturas += q_item
                            combo_identificado = combos_map[sku_item]["sku"]
                            val_tot_itens += (q_item * v_unit)
                        elif cid_item in combos_map:
                            qtd_assinaturas += q_item
                            combo_identificado = combos_map[cid_item]["sku"]
                            val_tot_itens += (q_item * v_unit)

                    if qtd_assinaturas <= 0:
                        continue

                    # Extrair informações do cliente / endereço
                    info = p.get("informacoes_adicionais", {})
                    outros = info.get("outros_detalhes", {}) or {}
                    
                    cli_nome = str(outros.get("cNomeOd") or "").strip()
                    cpf_cnpj = str(outros.get("cCnpjCpfOd") or "").strip()
                    rua = str(outros.get("cEnderecoOd") or "").strip()
                    num = str(outros.get("cNumeroOd") or "").strip()
                    comp = str(outros.get("cComplementoOd") or "").strip()
                    bairro = str(outros.get("cBairroOd") or "").strip()
                    cid = str(outros.get("cCidadeOd") or "").strip()
                    uf = str(outros.get("cEstadoOd") or "").strip()
                    cep = str(outros.get("cCEPOd") or "").strip()

                    # Fallback para ConsultarCliente caso outros_detalhes esteja vazio
                    if not cli_nome and cod_cli > 0:
                        try:
                            cli_res = self.client.executar("geral/clientes/", "ConsultarCliente", [{"codigo_cliente_omie": cod_cli}])
                            cli_nome = cli_res.get("nome_fantasia") or cli_res.get("razao_social") or ""
                            cpf_cnpj = cli_res.get("cnpj_cpf") or ""
                            rua = cli_res.get("endereco") or ""
                            num = cli_res.get("endereco_numero") or ""
                            comp = cli_res.get("complemento") or ""
                            bairro = cli_res.get("bairro") or ""
                            cid = cli_res.get("cidade") or ""
                            uf = cli_res.get("estado") or ""
                            cep = cli_res.get("cep") or ""
                        except Exception:
                            pass

                    # Valor total do pedido
                    total_ped = p.get("total_pedido", {})
                    val_total = float(total_ped.get("valor_total_pedido") or cab.get("valor_total_pedido") or val_tot_itens)

                    if "PRD00379" in combo_identificado:
                        periodo_envio = "LOTE_04/2027 (Abril)"
                        exemplares_iniciais = 3 * qtd_assinaturas
                    elif "000223" in combo_identificado:
                        periodo_envio = "LOTE_01/2027 (Jan-Mar)"
                        exemplares_iniciais = 1 * qtd_assinaturas
                    else:
                        periodo_envio = "LOTE_01/2027 (Jan-Mar)"
                        exemplares_iniciais = 0

                    total_contratado = 12 * qtd_assinaturas
                    obs = f"Importado automaticamente do Omie (Pedido #{num_ped} - Etapa {etapa})"

                    # Upsert no Turso DB
                    check_df = db.executar_query("SELECT id FROM assinaturas_pedidos_proximo_envio WHERE codigo_pedido_omie = :cod_ped OR numero_pedido = :num_ped", {
                        "cod_ped": cod_ped,
                        "num_ped": num_ped
                    })

                    if check_df is not None and not check_df.empty:
                        existente_id = int(check_df.iloc[0]["id"])
                        sql_upd = """
                            UPDATE assinaturas_pedidos_proximo_envio SET
                                cliente_nome = :nome,
                                cpf_cnpj = :cpf,
                                rua = :rua,
                                numero = :num,
                                complemento = :comp,
                                bairro = :bairro,
                                cidade = :cid,
                                uf = :uf,
                                cep = :cep,
                                quantidade_assinaturas = :qtd,
                                sku_produto = :sku,
                                valor_total = :v_tot,
                                observacao = :obs,
                                periodo_envio = :periodo,
                                exemplares_entregues = :entregues,
                                total_exemplares_contratados = :tot_cont,
                                status_assinatura = 'ATIVO'
                            WHERE id = :id
                        """
                        db.executar_query(sql_upd, {
                            "nome": cli_nome, "cpf": cpf_cnpj, "rua": rua, "num": num,
                            "comp": comp, "bairro": bairro, "cid": cid, "uf": uf, "cep": cep,
                            "qtd": qtd_assinaturas, "sku": combo_identificado,
                            "v_tot": val_total, "obs": obs, "periodo": periodo_envio,
                            "entregues": exemplares_iniciais, "tot_cont": total_contratado,
                            "id": existente_id
                        }, is_select=False)
                    else:
                        sql_ins = """
                            INSERT INTO assinaturas_pedidos_proximo_envio (
                                numero_pedido, codigo_pedido_omie, codigo_cliente_omie, cliente_nome, cpf_cnpj,
                                rua, numero, complemento, bairro, cidade, uf, cep,
                                quantidade_assinaturas, periodo_envio, observacao, criado_em,
                                departamento, codigo_departamento, codigo_cenario_impostos, forma_pagamento_codigo,
                                forma_envio, valor_frete, valor_total, sku_produto, origem_cadastro,
                                exemplares_entregues, total_exemplares_contratados, status_assinatura
                            ) VALUES (
                                :num_ped, :cod_ped, :cod_cli, :nome, :cpf,
                                :rua, :num, :comp, :bairro, :cid, :uf, :cep,
                                :qtd, :periodo, :obs, :agora,
                                'Comercial', '1807684664', 1800980891, '000',
                                'CORREIOS', 0.0, :v_tot, :sku, 'IMPORTADO_FATURADO_OMIE',
                                :entregues, :tot_cont, 'ATIVO'
                            )
                        """
                        db.executar_query(sql_ins, {
                            "num_ped": num_ped, "cod_ped": cod_ped, "cod_cli": cod_cli,
                            "nome": cli_nome, "cpf": cpf_cnpj, "rua": rua, "num": num,
                            "comp": comp, "bairro": bairro, "cid": cid, "uf": uf, "cep": cep,
                            "qtd": qtd_assinaturas, "periodo": periodo_envio, "obs": obs,
                            "agora": agora, "v_tot": val_total, "sku": combo_identificado,
                            "entregues": exemplares_iniciais, "tot_cont": total_contratado
                        }, is_select=False)

                    pedidos_importados.append({
                        "numero_pedido": num_ped,
                        "codigo_pedido_omie": cod_ped,
                        "cliente_nome": cli_nome,
                        "sku_produto": combo_identificado,
                        "quantidade": qtd_assinaturas,
                        "valor_total": val_total
                    })



            return {
                "success": True,
                "importados_count": len(pedidos_importados),
                "total_analisados": total_analisados,
                "pedidos": pedidos_importados,
                "message": f"{len(pedidos_importados)} pedido(s) de assinatura identificados e sincronizados com sucesso no Turso DB!"
            }

        except Exception as e:
            print(f"[ASSINATURAS] Erro na sincronização de pedidos faturados Omie: {e}")
            return {"success": False, "message": f"Erro ao sincronizar pedidos Omie: {str(e)}"}

