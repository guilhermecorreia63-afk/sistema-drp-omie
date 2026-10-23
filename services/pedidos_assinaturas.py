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
