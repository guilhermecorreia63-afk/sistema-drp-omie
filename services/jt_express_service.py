# -*- coding: utf-8 -*-
"""
services/jt_express_service.py - Integração Oficial com API J&T Express Brasil
Suporta Homologação e Produção, autenticação por assinatura Digest (MD5 + Base64),
criação de pedido (order/addOrder), consulta (order/getOrders), cancelamento (order/cancelOrder)
e rastreamento (logistics/trace).
"""

import os
import json
import time
import base64
import hashlib
import requests
import re
from typing import Dict, Any, List, Optional, Tuple

class JTExpressService:
    # URL Oficial confirmada pela J&T Express Brasil (Slides 4, 5 e 7)
    URL_PRODUCAO = "https://openapi.jtjms-br.com/webopenplatformapi/api"
    URL_HOMOLOGACAO = "https://demoopenapi.jtjms-br.com/webopenplatformapi/api"

    @classmethod
    def get_credentials(cls) -> Dict[str, str]:
        customer_code = os.getenv("JT_CUSTOMER_CODE") or os.getenv("COSTUMER_CODE") or ""
        password = os.getenv("JT_PASSWORD") or os.getenv("SENHA") or ""
        app_token = os.getenv("JT_APP_TOKEN") or os.getenv("APP_TOKEN_JT") or ""
        app_secret = os.getenv("JT_APP_SECRET") or os.getenv("APP_SECRET_JT") or ""
        env = (os.getenv("JT_ENV") or "homologacao").strip().lower()

        base_url = cls.URL_PRODUCAO if env == "producao" else cls.URL_HOMOLOGACAO

        return {
            "customer_code": customer_code.strip(),
            "password": password.strip(),
            "app_token": app_token.strip(),
            "app_secret": app_secret.strip(),
            "base_url": base_url,
            "env": env
        }

    @staticmethod
    def gerar_md5(texto: str) -> str:
        """Gera hash MD5 hexadecimal em maiúsculas conforme documentação J&T."""
        m = hashlib.md5()
        m.update(texto.encode("utf-8"))
        return m.hexdigest().upper()

    @classmethod
    def gerar_digest_biz_content(cls, customer_code: str, password_raw: str, private_key: str) -> str:
        """
        Gera a assinatura de conteúdo (bizContent digest):
        1. pwd_md5 = MD5(password_raw + 'jadada236t2') em maiúsculas
        2. digest_inner = MD5(customer_code + pwd_md5 + private_key)
        3. digest = Base64(digest_inner)
        """
        # Conforme manual J&T / Slide 3:
        # pwd is equal to MD5 (plain text password (H5CD3zE6) + jadada236t2) -> uppercase
        pwd_salt = password_raw + "jadada236t2"
        pwd_md5 = cls.gerar_md5(pwd_salt)

        # Regra do business parameter digest:
        # Base64(Md5(customerCode + pwd_md5 + privateKey))
        concat_str = customer_code + pwd_md5 + private_key
        hash_bytes = hashlib.md5(concat_str.encode("utf-8")).digest()
        return base64.b64encode(hash_bytes).decode("ascii")

    @classmethod
    def gerar_header_digest(cls, biz_content_str: str, private_key: str) -> str:
        """
        Gera a assinatura dinâmica do Header exigida em cada requisição:
        Base64(MD5(bizContent + privateKey))
        """
        raw_concat = biz_content_str + private_key
        hash_bytes = hashlib.md5(raw_concat.encode("utf-8")).digest()
        return base64.b64encode(hash_bytes).decode("ascii")

    @classmethod
    def post_jt(cls, endpoint: str, biz_content_dict: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """
        Executa requisição POST para a API J&T Express com cabeçalhos e digest dinâmicos.
        """
        creds = cls.get_credentials()
        customer_code = creds["customer_code"]
        private_key = creds["app_secret"] # privateKey / app_secret
        api_account = creds["app_token"] or customer_code

        # Se o bizContent não possuir o customerCode e digest interno, injetar automaticamente
        if "customerCode" not in biz_content_dict:
            biz_content_dict["customerCode"] = customer_code
        if "digest" not in biz_content_dict:
            biz_content_dict["digest"] = cls.gerar_digest_biz_content(customer_code, creds["password"], private_key)

        biz_json_str = json.dumps(biz_content_dict, ensure_ascii=False)

        # Assinatura dinâmica do Header para esta requisição
        header_digest = cls.gerar_header_digest(biz_json_str, private_key)
        timestamp_ms = str(int(time.time() * 1000))

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "apiAccount": api_account,
            "digest": header_digest,
            "timestamp": timestamp_ms
        }

        url = f"{creds['base_url']}/{endpoint.lstrip('/')}"

        try:
            # A API da J&T espera o form x-www-form-urlencoded com a chave bizContent
            resp = requests.post(
                url,
                data={"bizContent": biz_json_str},
                headers=headers,
                timeout=25
            )
            data = resp.json()
            return resp.status_code, data
        except Exception as e:
            return 500, {"code": "0", "msg": f"Erro de conexão com API J&T: {str(e)}"}

    # =========================================================================
    # 1. CRIAÇÃO DE PEDIDO (addOrder)
    # Documentação: order/addOrder
    # =========================================================================
    @classmethod
    def criar_pedido(cls, pedido_drp: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cria um novo pedido na J&T Express a partir de dados da NF-e / Pedido DRP.
        Retorna código de rastreamento (billCode / txlogisticId) e sortingCode.
        """
        creds = cls.get_credentials()
        dest = pedido_drp.get("destinatario") or {}
        end = dest.get("endereco") or {}
        
        # Remetente padrão: Diaconia Geral Edições Shalom
        remetente = {
            "name": "COMUNIDADE CATOLICA SHALOM",
            "mobile": "85982168918",
            "phone": "8532168918",
            "postCode": "61700-000",
            "countryCode": "BRA",
            "prov": "CE",
            "city": "Aquiraz",
            "area": "Berra Bode",
            "address": "RUA BERRA BODE - JAMBREIRO, S/N - DIACONIA SHALOM"
        }

        cep_limpo = re.sub(r"\D", "", str(end.get("cep") or dest.get("cep") or ""))
        cep_fmt = f"{cep_limpo[:5]}-{cep_limpo[5:]}" if len(cep_limpo) == 8 else cep_limpo

        destinatario = {
            "name": (dest.get("nome") or "CLIENTE").strip()[:60],
            "mobile": re.sub(r"\D", "", str(dest.get("celular") or dest.get("telefone") or "85999999999"))[:15],
            "phone": re.sub(r"\D", "", str(dest.get("telefone") or "8532168918"))[:15],
            "postCode": cep_fmt,
            "countryCode": "BRA",
            "prov": (end.get("uf") or dest.get("uf") or "CE").strip().upper()[:2],
            "city": (end.get("cidade") or dest.get("cidade") or "").strip()[:40],
            "area": (end.get("bairro") or dest.get("bairro") or "Centro").strip()[:40],
            "address": f"{end.get('logradouro') or 'Rua'}, {end.get('numero') or 'S/N'} {end.get('complemento') or ''}".strip()[:100]
        }

        num_origem = str(pedido_drp.get("numero_pedido") or pedido_drp.get("numero_remessa") or pedido_drp.get("numero_nf") or "AVULSO")
        txlogistic_id = f"PED_{num_origem}_{int(time.time())}"

        peso_kg = float(pedido_drp.get("peso_kg") or 0.5)
        valor_nf = float(pedido_drp.get("valor_nf") or 10.0)

        biz_content = {
            "customerCode": creds["customer_code"],
            "txlogisticId": txlogistic_id,
            "expressType": "EZ", # Standard Express J&T
            "orderType": "2",    # 2 = NF-e
            "serviceType": "02",
            "deliveryType": "03",
            "sender": remetente,
            "receiver": destinatario,
            "weight": f"{peso_kg:.2f}",
            "itemsValue": f"{valor_nf:.2f}",
            "insuredAmount": f"{valor_nf:.2f}",
            "items": [
                {
                    "itemName": "LIVROS / ARTIGOS RELIGIOSOS",
                    "number": 1,
                    "itemValue": f"{valor_nf:.2f}"
                }
            ]
        }

        # Se houver NF-e vinculada
        chave_nfe = str(pedido_drp.get("chave_nfe") or "").strip()
        num_nf = str(pedido_drp.get("numero_nf") or "").strip()
        if chave_nfe and len(chave_nfe) == 44:
            biz_content["invoice"] = {
                "invoiceType": "1", # 1 = NF-e eletrônica
                "invoiceNumber": num_nf,
                "invoiceAccessKey": chave_nfe
            }

        status_code, resp_data = cls.post_jt("order/addOrder", biz_content)
        
        # Resposta de Sucesso J&T: code == "1"
        if str(resp_data.get("code")) == "1":
            order_data = resp_data.get("data") or {}
            order_list = order_data.get("orderList") or []
            item_resp = order_list[0] if order_list else {}
            bill_code = item_resp.get("billCode") or order_data.get("billCode") or ""
            sorting_code = order_data.get("sortingCode") or ""

            return {
                "sucesso": True,
                "billCode": bill_code,
                "txlogisticId": txlogistic_id,
                "sortingCode": sorting_code,
                "raw": resp_data
            }
        else:
            return {
                "sucesso": False,
                "erro": resp_data.get("msg") or resp_data.get("message") or "Erro desconhecido ao emitir J&T",
                "raw": resp_data
            }

    # =========================================================================
    # 2. RASTREAMENTO (logistics/trace)
    # =========================================================================
    @classmethod
    def rastrear_objeto(cls, bill_code: str) -> Dict[str, Any]:
        """Consulta eventos de rastreamento do objeto J&T."""
        creds = cls.get_credentials()
        biz_content = {
            "customerCode": creds["customer_code"],
            "command": "0", # 0 = billCodes
            "billCodes": bill_code
        }
        status_code, resp_data = cls.post_jt("logistics/trace", biz_content)
        if str(resp_data.get("code")) == "1":
            lista = resp_data.get("data") or []
            item = lista[0] if lista else {}
            return {"sucesso": True, "eventos": item.get("details") or [], "raw": resp_data}
        return {"sucesso": False, "erro": resp_data.get("msg") or "Rastreio não localizado"}

    # =========================================================================
    # 3. CANCELAMENTO DE PEDIDO (order/cancelOrder)
    # =========================================================================
    @classmethod
    def cancelar_pedido(cls, bill_code: str, txlogistic_id: str = "", motivo: str = "Cancelamento operacional") -> Dict[str, Any]:
        """Cancela pedido emitido na J&T que ainda não possua movimentações."""
        creds = cls.get_credentials()
        biz_content = {
            "customerCode": creds["customer_code"],
            "orderType": "2",
            "billCode": bill_code,
            "txlogisticId": txlogistic_id,
            "reason": motivo
        }
        status_code, resp_data = cls.post_jt("order/cancelOrder", biz_content)
        if str(resp_data.get("code")) == "1":
            return {"sucesso": True, "mensagem": "Cancelado com sucesso na J&T", "raw": resp_data}
        return {"sucesso": False, "erro": resp_data.get("msg") or "Falha ao cancelar na J&T"}
