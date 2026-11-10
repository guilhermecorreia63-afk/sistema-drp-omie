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
import binascii
import hashlib
import requests
import re
from decimal import Decimal, InvalidOperation
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
        # pwd = MD5(password_raw + protocol salt), uppercase hexadecimal.
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
        biz_content_dict = dict(biz_content_dict)
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
            try:
                data = resp.json()
            except ValueError:
                return resp.status_code, {"code": "0", "msg": "J&T retornou uma resposta não JSON.", "formatoInvalido": True}
            return resp.status_code, data
        except requests.RequestException as e:
            return 502, {"code": "0", "msg": f"Falha de comunicação com API J&T ({type(e).__name__})."}

    @classmethod
    def consultar_pedidos(cls, serial_numbers: List[str], command: int = 1) -> Dict[str, Any]:
        """Consulta getOrders; command=1 da captura e command=2 por billCode no PDF de apresentação, p.8."""
        if not isinstance(serial_numbers, list) or not serial_numbers:
            return {"sucesso": False, "httpStatus": 400, "erro": "Informe uma lista de identificadores de pedido J&T."}
        if type(command) is not int or command not in (1, 2) or any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value.strip()) for value in serial_numbers):
            return {"sucesso": False, "httpStatus": 400, "erro": "Esta consulta suporta command=1 da captura e command=2 demonstrado no PDF para billCode."}
        creds = cls.get_credentials()
        if any(not creds.get(key) for key in ("customer_code", "password", "app_secret")):
            return {"sucesso": False, "httpStatus": 503, "erro": "Configuração J&T incompleta para consultar pedidos."}
        status, response = cls.post_jt("order/getOrders", {
            "serialNumber": [value.strip() for value in serial_numbers],
            "command": command,
            "customerCode": creds["customer_code"],
        })
        if not isinstance(response, dict):
            return {"sucesso": False, "httpStatus": 502, "erro": "Resposta de consulta J&T fora do formato esperado."}
        if 200 <= status < 300 and str(response.get("code")) == "1":
            data = response.get("data")
            return {"sucesso": True, "httpStatus": status, "dados": data, "codigoApi": "1", "dadosDisponiveis": bool(data),
                "mensagem": "Consulta aceita pela J&T." if data else "Consulta aceita pela J&T, mas nenhum pedido foi retornado para os identificadores informados."}
        message = str(response.get("msg") or response.get("message") or "Consulta de pedido J&T não concluída.")
        for key in ("customer_code", "password", "app_token", "app_secret"):
            if creds.get(key):
                message = message.replace(creds[key], "[REDACTED]")
        effective_status = status if not 200 <= status < 300 else (502 if response.get("formatoInvalido") else 422)
        return {"sucesso": False, "httpStatus": effective_status, "statusHttpJt": status, "codigoApi": str(response.get("code") or ""), "erro": message}

    @classmethod
    def cotar_frete(cls, cep_origem: str, cep_destino: str, peso_kg: Any, valor_declarado: Any,
                   goods_type_code: str = "bm000006", product_type_code: str = "EZ") -> Dict[str, Any]:
        """Cotação documentada em 'Efetuando uma cotação...', pp.4-8 e apresentação p.4."""
        origin = re.sub(r"\D", "", str(cep_origem or ""))
        destination = re.sub(r"\D", "", str(cep_destino or ""))
        if len(origin) != 8 or len(destination) != 8:
            return {"sucesso": False, "httpStatus": 400, "erro": "Informe CEP de origem e destino com 8 dígitos."}
        try:
            weight = Decimal(str(peso_kg))
            amount = Decimal(str(valor_declarado))
            if not weight.is_finite() or not amount.is_finite() or weight <= 0 or amount < 0:
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            return {"sucesso": False, "httpStatus": 400, "erro": "Peso deve ser positivo e valor declarado não negativo, ambos finitos."}
        if not isinstance(goods_type_code, str) or not goods_type_code.strip() or product_type_code != "EZ":
            return {"sucesso": False, "httpStatus": 400, "erro": "Informe goodsTypeCode; a tabela documentada para este teste é EZ."}
        creds = cls.get_credentials()
        if any(not creds.get(key) for key in ("customer_code", "password", "app_secret")):
            return {"sucesso": False, "httpStatus": 503, "erro": "Configuração J&T incompleta para cotação."}
        status, response = cls.post_jt("spmComCost/getComCostAndTime", {
            "customerCode": creds["customer_code"], "originZipCode": origin, "destinationZipCode": destination,
            "goodsTypeCode": goods_type_code.strip(), "productTypeCode": product_type_code,
            "insuredAmount": format(amount, ".2f"), "weight": format(weight, "f"),
        })
        if not isinstance(response, dict):
            return {"sucesso": False, "httpStatus": 502, "erro": "Resposta de cotação J&T fora do formato esperado."}
        if 200 <= status < 300 and str(response.get("code")) == "1" and isinstance(response.get("data"), dict):
            data = response["data"]
            warnings = []
            try:
                returned_cost = Decimal(str(data.get("cost")))
                usable = returned_cost.is_finite() and returned_cost > 0
            except (InvalidOperation, ValueError, TypeError):
                usable = False
            if not usable:
                warnings.append("Custo retornado zero/ausente/inválido; não interpretar como frete grátis sem confirmação comercial da J&T.")
            if data.get("aging") in (None, 0, "0", ""):
                warnings.append("Prazo ausente ou zero; confirmar disponibilidade/prazo no ambiente de homologação.")
            return {"sucesso": True, "httpStatus": status, "codigoApi": "1", "dados": data,
                "cost": data.get("cost"), "aging": data.get("aging"),
                "riskPremiumFee": data.get("riskPremiumFee"), "riskPremiumWaybillFee": data.get("riskPremiumWaybillFee"),
                "origem": "COTACAO_DIRETA_JT", "frete_pago": False,
                "cotacao_valor_positivo": usable, "advertencias": warnings}
        message = str(response.get("msg") or response.get("message") or "Cotação J&T não concluída.")
        for key in ("customer_code", "password", "app_token", "app_secret"):
            if creds.get(key):
                message = message.replace(creds[key], "[REDACTED]")
        return {"sucesso": False, "httpStatus": status if not 200 <= status < 300 else 422,
            "statusHttpJt": status, "codigoApi": str(response.get("code") or ""), "erro": message}

    # =========================================================================
    # 1. CRIAÇÃO DE PEDIDO (addOrder)
    # Documentação: order/addOrder
    # =========================================================================
    @classmethod
    def criar_pedido(cls, pedido_drp: Dict[str, Any], *, txlogistic_id: Optional[str] = None) -> Dict[str, Any]:
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
        txlogistic_id = txlogistic_id or f"PED_{num_origem}_{int(time.time())}"

        peso_kg = float(pedido_drp.get("peso_kg") or 0.5)
        valor_nf = float(pedido_drp.get("valor_nf") or 10.0)

        biz_content = {
            "customerCode": creds["customer_code"],
            "txlogisticId": txlogistic_id,
            "expressType": "EZ", # Standard Express J&T
            "orderType": "2",    # Cobrança mensal, conforme exemplo completo enviado pela J&T.
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
        if isinstance(resp_data, dict) and 200 <= status_code < 300 and str(resp_data.get("code")) == "1":
            order_data = resp_data.get("data") or {}
            order_list = order_data.get("orderList") or []
            item_resp = order_list[0] if order_list else {}
            bill_code = item_resp.get("billCode") or order_data.get("billCode") or ""
            sorting_code = order_data.get("sortingCode") or ""

            return {
                "sucesso": True,
                "httpStatus": status_code,
                "billCode": bill_code,
                "txlogisticId": txlogistic_id,
                "sortingCode": sorting_code,
                "raw": resp_data
            }
        else:
            if not isinstance(resp_data, dict):
                return {"sucesso": False, "httpStatus": 502, "txlogisticId": txlogistic_id, "erro": "Resposta de criação J&T fora do formato esperado."}
            message = str(resp_data.get("msg") or resp_data.get("message") or "Erro desconhecido ao emitir J&T")
            for key in ("customer_code", "password", "app_token", "app_secret"):
                if creds.get(key):
                    message = message.replace(creds[key], "[REDACTED]")
            return {
                "sucesso": False,
                "httpStatus": status_code if not 200 <= status_code < 300 else 422,
                "statusHttpJt": status_code, "codigoApi": str(resp_data.get("code") or ""),
                "txlogisticId": txlogistic_id,
                "erro": message,
                "raw": resp_data
            }

    @classmethod
    def criar_pedido_estruturado(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Contrato completo fornecido pelo suporte: translate e campos fiscais no nível raiz.

        Não converte silenciosamente o modelo DRP antigo nem reutiliza digests recebidos.
        """
        if not isinstance(payload, dict):
            return {"sucesso": False, "httpStatus": 400, "erro": "Payload J&T deve ser objeto JSON."}
        errors = []
        required = ("txlogisticId", "expressType", "orderType", "serviceType", "deliveryType", "goodsType", "weight",
            "invoiceNumber", "invoiceSerialNumber", "invoiceMoney", "taxCode", "invoiceAccessKey", "invoiceIssueDate")
        errors.extend(f"Campo obrigatório neste modelo: {key}." for key in required if payload.get(key) in (None, ""))
        allowed = set(required) | {"sender", "receiver", "translate", "totalQuantity", "items"}
        extra = set(payload) - allowed - {"customerCode", "digest"}
        if extra:
            errors.append("Campos fora do exemplo completo: " + ", ".join(sorted(extra)))
        party_fields = ("name", "postCode", "mailBox", "taxNumber", "mobile", "phone", "prov", "city", "street", "streetNumber", "address", "areaCode", "ieNumber", "area")
        for name in ("sender", "receiver", "translate"):
            party = payload.get(name)
            if not isinstance(party, dict):
                errors.append(f"Bloco {name} obrigatório.")
                continue
            errors.extend(f"{name}.{key} não informado." for key in party_fields if party.get(key) in (None, ""))
            if name != "receiver" and not party.get("company"):
                errors.append(f"{name}.company não informado.")
            if not re.fullmatch(r"\d{8}", str(party.get("postCode") or "")):
                errors.append(f"{name}.postCode deve conter 8 dígitos.")
        volumes = payload.get("totalQuantity")
        if type(volumes) is not int or volumes <= 0:
            errors.append("totalQuantity deve ser inteiro positivo.")
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            errors.append("items deve conter ao menos um item.")
        else:
            for index, item in enumerate(items):
                if not isinstance(item, dict) or any(item.get(key) in (None, "") for key in ("itemType", "itemName", "number", "desc", "itemNcm")):
                    errors.append(f"items[{index}] incompleto no modelo recebido.")
        try:
            weight, amount = Decimal(str(payload.get("weight"))), Decimal(str(payload.get("invoiceMoney")))
            if not weight.is_finite() or weight <= 0 or not amount.is_finite() or amount < 0:
                raise ValueError()
        except (ValueError, InvalidOperation, TypeError):
            errors.append("weight/invoiceMoney devem ser números finitos e válidos.")
        if not re.fullmatch(r"\d{44}", str(payload.get("invoiceAccessKey") or "")):
            errors.append("invoiceAccessKey deve conter 44 dígitos do documento fornecido, sem fabricar chave.")
        if errors:
            return {"sucesso": False, "httpStatus": 400, "erro": "; ".join(errors), "erros_validacao": errors}
        creds = cls.get_credentials()
        if any(not creds.get(key) for key in ("customer_code", "password", "app_token", "app_secret")):
            return {"sucesso": False, "httpStatus": 503, "erro": "Configuração J&T incompleta para criação estruturada."}
        content = {key: value for key, value in payload.items() if key in allowed}
        content["customerCode"] = creds["customer_code"]
        status, response = cls.post_jt("order/addOrder", content)
        if not isinstance(response, dict):
            return {"sucesso": False, "httpStatus": 502, "erro": "Resposta de criação J&T fora do formato esperado.", "txlogisticId": content["txlogisticId"]}
        success = 200 <= status < 300 and str(response.get("code")) == "1"
        result = {"sucesso": success, "httpStatus": status if success or not 200 <= status < 300 else 422,
            "statusHttpJt": status, "codigoApi": str(response.get("code") or ""), "txlogisticId": content["txlogisticId"],
            "campos_enviados_sem_autenticacao": sorted(key for key in content if key != "customerCode")}
        if success:
            data = response.get("data") or {}
            orders = (data.get("orderList") or []) if isinstance(data, dict) else []
            first = orders[0] if orders and isinstance(orders[0], dict) else {}
            result.update({"billCode": first.get("billCode") or (data.get("billCode") if isinstance(data, dict) else None),
                "sortingCode": data.get("sortingCode") if isinstance(data, dict) else None, "dados": data})
        else:
            message = str(response.get("msg") or response.get("message") or "Criação estruturada J&T não concluída.")
            for key in ("customer_code", "password", "app_token", "app_secret"):
                if creds.get(key):
                    message = message.replace(creds[key], "[REDACTED]")
            result["erro"] = message
        return result

    # =========================================================================
    # 2. RASTREAMENTO (logistics/trace)
    # =========================================================================
    @classmethod
    def rastrear_objeto(cls, bill_code: str) -> Dict[str, Any]:
        """Consulta eventos de rastreamento do objeto J&T."""
        bill_code = str(bill_code or "").strip()
        if not bill_code or not re.fullmatch(r"[A-Za-z0-9-]+", bill_code):
            return {"sucesso": False, "httpStatus": 400, "erro": "Informe um código de rastreio J&T válido."}
        creds = cls.get_credentials()
        missing = [key for key in ("customer_code", "password", "app_secret") if not creds.get(key)]
        if missing:
            return {"sucesso": False, "httpStatus": 503, "erro": "Configuração J&T incompleta para consulta de rastreio."}
        biz_content = {
            "customerCode": creds["customer_code"],
            "command": "0", # 0 = billCodes
            "billCodes": bill_code
        }
        status_code, resp_data = cls.post_jt("logistics/trace", biz_content)
        if not isinstance(resp_data, dict):
            return {"sucesso": False, "httpStatus": 502, "erro": "Resposta de rastreio J&T fora do formato esperado."}
        if 200 <= status_code < 300 and str(resp_data.get("code")) == "1":
            lista = resp_data.get("data")
            if not isinstance(lista, list) or any(not isinstance(item, dict) for item in lista):
                return {"sucesso": False, "httpStatus": 502, "erro": "Lista de rastreio J&T fora do formato esperado."}
            if not lista:
                return {"sucesso": False, "httpStatus": 404, "erro": "Nenhum objeto de rastreio retornado pela J&T."}
            item = lista[0]
            details = item.get("details")
            if details is not None and (not isinstance(details, list) or any(not isinstance(event, dict) for event in details)):
                return {"sucesso": False, "httpStatus": 502, "erro": "Eventos de rastreio J&T fora do formato esperado."}
            return {"sucesso": True, "httpStatus": status_code, "eventos": details or [], "raw": resp_data}
        message = str(resp_data.get("msg") or resp_data.get("message") or "Rastreio não localizado")
        for key in ("customer_code", "password", "app_token", "app_secret"):
            if creds.get(key):
                message = message.replace(creds[key], "[REDACTED]")
        return {"sucesso": False, "httpStatus": status_code if not 200 <= status_code < 300 else 422,
            "statusHttpJt": status_code, "codigoApi": str(resp_data.get("code") or ""), "erro": message}

    @classmethod
    def obter_etiqueta(cls, bill_code: str, print_size: int = 0,
                      print_endpoint: str = "order/printOrder") -> Dict[str, Any]:
        """Resgata o PDF oficial; somente caminhos explicitamente presentes nos manuais recebidos."""
        bill_code = str(bill_code or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9-]+", bill_code):
            return {"sucesso": False, "httpStatus": 400, "erro": "Informe um billCode J&T válido para obter etiqueta."}
        if type(print_size) is not int or print_size not in (0, 1, 2):
            return {"sucesso": False, "httpStatus": 400, "erro": "printSize deve ser 0, 1 ou 2, conforme documentação."}
        if print_endpoint not in ("order/printOrder", "order/r/printOrder"):
            return {"sucesso": False, "httpStatus": 400, "erro": "Caminho de etiqueta fora dos dois modelos documentados."}
        creds = cls.get_credentials()
        if any(not creds.get(key) for key in ("customer_code", "password", "app_token", "app_secret")):
            return {"sucesso": False, "httpStatus": 503, "erro": "Configuração J&T incompleta para etiqueta."}
        status, response = cls.post_jt(print_endpoint, {"customerCode": creds["customer_code"], "billCode": bill_code, "printSize": print_size})
        if not isinstance(response, dict):
            return {"sucesso": False, "httpStatus": 502, "erro": "Resposta de etiqueta J&T fora do formato esperado."}
        if not 200 <= status < 300 or str(response.get("code")) != "1":
            message = str(response.get("msg") or response.get("message") or "Etiqueta J&T não obtida.")
            for key in ("customer_code", "password", "app_token", "app_secret"):
                if creds.get(key):
                    message = message.replace(creds[key], "[REDACTED]")
            return {"sucesso": False, "httpStatus": status if not 200 <= status < 300 else 422,
                "statusHttpJt": status, "codigoApi": str(response.get("code") or ""), "erro": message}
        data = response.get("data")
        if not isinstance(data, dict) or str(data.get("billCode") or "").strip() != bill_code:
            return {"sucesso": False, "httpStatus": 502, "erro": "Etiqueta retornada sem o billCode solicitado; não disponibilizada para impressão."}
        encoded = data.get("base64EncodeContent")
        if not isinstance(encoded, str) or not encoded.strip() or len(encoded) > 30000000:
            return {"sucesso": False, "httpStatus": 502, "erro": "Conteúdo Base64 da etiqueta ausente ou acima do limite local."}
        encoded = "".join(encoded.split())
        try:
            pdf = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            return {"sucesso": False, "httpStatus": 502, "erro": "Conteúdo Base64 inválido na etiqueta J&T."}
        if not pdf.startswith(b"%PDF-"):
            return {"sucesso": False, "httpStatus": 502, "erro": "O arquivo retornado pela J&T não é um PDF reconhecível."}
        return {"sucesso": True, "httpStatus": status, "codigoApi": "1", "billCode": bill_code,
            "printSize": print_size, "pdfBase64": encoded, "mimeType": "application/pdf", "tamanhoBytes": len(pdf),
            "origem": "PDF_OFICIAL_JT", "endpointUtilizado": print_endpoint}

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
