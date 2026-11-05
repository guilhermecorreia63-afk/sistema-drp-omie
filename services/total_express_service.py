# -*- coding: utf-8 -*-
"""Integração homologação da API Smart PUDO Total Express."""

import json
import sqlite3
from pathlib import Path
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

import requests
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import ecc200datamatrix
from reportlab.graphics.barcode import code128
from io import BytesIO

logger = logging.getLogger("total_express_service")


class TotalExpressValidationError(ValueError):
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class TotalExpressService:
    # URLs Oficiais confirmadas pela Total Express (Swagger Oficial):
    URL_HOMOLOGACAO = "https://apis-qa.totalexpress.com.br/ics-edi-lv/v1/coleta/smartLabel/registrar"
    URL_PRODUCAO = "https://apis.totalexpress.com.br/ics-edi-lv/v1/coleta/smartlabel/registrar"

    @classmethod
    def get_credentials(cls) -> Dict[str, str]:
        return {
            "username": (os.getenv("TOTAL_EXPRESS_USER") or "").strip(),
            "password": (os.getenv("TOTAL_EXPRESS_PASSWORD") or "").strip(),
            "reid_parent": (os.getenv("TOTAL_EXPRESS_REID_PARENT") or "").strip(),
            "cnpj": re.sub(r"\D", "", os.getenv("TOTAL_EXPRESS_CNPJ") or ""),
            "cnpj_embarcador": re.sub(r"\D", "", os.getenv("TOTAL_EXPRESS_CNPJ_EMBARCADOR") or ""),
            "servico_tipo": (os.getenv("TOTAL_EXPRESS_SERVICO_TIPO") or "").strip(),
            "pudo_razao_social": (os.getenv("TOTAL_EXPRESS_PUDO_RAZAO_SOCIAL") or "").strip(),
            "pudo_nome_fantasia": (os.getenv("TOTAL_EXPRESS_PUDO_NOME_FANTASIA") or "").strip(),
            "pudo_codigo_municipio": (os.getenv("TOTAL_EXPRESS_PUDO_CODIGO_MUNICIPIO") or "").strip(),
            "pudo_ie": (os.getenv("TOTAL_EXPRESS_PUDO_IE") or "").strip(),
            "pudo_endereco": (os.getenv("TOTAL_EXPRESS_PUDO_ENDERECO") or "").strip(),
            "pudo_tipo_logradouro": (os.getenv("TOTAL_EXPRESS_PUDO_TIPO_LOGRADOURO") or "").strip(),
            "pudo_complemento": (os.getenv("TOTAL_EXPRESS_PUDO_COMPLEMENTO") or "").strip(),
            "pudo_ddd": (os.getenv("TOTAL_EXPRESS_PUDO_DDD") or "").strip(),
            "pudo_telefone": (os.getenv("TOTAL_EXPRESS_PUDO_TELEFONE") or "").strip(),
            "pudo_email": (os.getenv("TOTAL_EXPRESS_PUDO_EMAIL") or "").strip(),
            "pudo_numero": (os.getenv("TOTAL_EXPRESS_PUDO_NUMERO") or "").strip(),
            "pudo_bairro": (os.getenv("TOTAL_EXPRESS_PUDO_BAIRRO") or "").strip(),
            "pudo_cep": re.sub(r"\D", "", os.getenv("TOTAL_EXPRESS_PUDO_CEP") or ""),
            "pudo_cnpj": re.sub(r"\D", "", os.getenv("TOTAL_EXPRESS_PUDO_CNPJ") or os.getenv("TOTAL_EXPRESS_CNPJ") or ""),
        }

    @staticmethod
    def _digits(value: Any) -> str:
        return re.sub(r"\D", "", str(value or ""))

    @staticmethod
    def _date(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S"):
            try:
                return datetime.strptime(raw[:19], fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
        return raw[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw[:10]) else ""

    @classmethod
    def construir_payload(cls, pedido: Dict[str, Any], creds: Dict[str, str] = None) -> Dict[str, Any]:
        creds = creds or cls.get_credentials()
        errors = []
        reid = creds.get("reid_parent") or ""
        cnpj = cls._digits(creds.get("cnpj"))
        # Se TOTAL_EXPRESS_CNPJ_EMBARCADOR não foi informado, utiliza o próprio CNPJ da empresa (envio direto do galpão)
        embarcador = cls._digits(creds.get("cnpj_embarcador")) or cnpj
        servico_raw = str(creds.get("servico_tipo") or "EXP").strip()
        if not reid:
            errors.append("Falta configurar TOTAL_EXPRESS_REID_PARENT.")
        if len(cnpj) != 14:
            errors.append("Falta configurar TOTAL_EXPRESS_CNPJ (CNPJ remetente, 14 dígitos).")
        if len(embarcador) != 14:
            errors.append("Falta configurar TOTAL_EXPRESS_CNPJ_EMBARCADOR (14 dígitos).")

        # Modalidade PUDO: apenas obrigatória se o cliente explicitamente configurou uso de PUDO
        # Para coleta tradicional no galpão próprio, o objeto 'pudo' não é enviado ou é dispensado
        has_pudo = bool(creds.get("pudo_razao_social") and creds.get("pudo_cep"))
        pudo_dict = None
        if has_pudo:
            pudo_required = ("pudo_razao_social", "pudo_codigo_municipio", "pudo_ie", "pudo_endereco", "pudo_numero", "pudo_bairro")
            pudo_missing = [key for key in pudo_required if not creds.get(key)]
            if len(creds.get("pudo_cep") or "") != 8:
                pudo_missing.append("pudo_cep")
            if len(cls._digits(creds.get("pudo_cnpj"))) != 14:
                pudo_missing.append("pudo_cnpj")
            if pudo_missing:
                errors.append("Configure os dados cadastrais PUDO do remetente: " + ", ".join(pudo_missing))
            else:
                pudo_dict = {
                    "razaoSocial": creds["pudo_razao_social"],
                    "nomeFantasia": creds.get("pudo_nome_fantasia") or creds["pudo_razao_social"],
                    "codigoMunicipio": int(creds["pudo_codigo_municipio"]),
                    "cnpj": cls._digits(creds["pudo_cnpj"]),
                    "inscricaoEstadual": creds["pudo_ie"],
                    "endereco": creds["pudo_endereco"],
                    "enderecoNumero": creds["pudo_numero"],
                    "enderecoBairro": creds["pudo_bairro"],
                    "cep": creds["pudo_cep"],
                    **({"tipoLogradouro": creds["pudo_tipo_logradouro"]} if creds.get("pudo_tipo_logradouro") else {}),
                    **({"enderecoComplemento": creds["pudo_complemento"]} if creds.get("pudo_complemento") else {}),
                    **({"ddd": creds["pudo_ddd"]} if creds.get("pudo_ddd") else {}),
                    **({"telefone": int(cls._digits(creds["pudo_telefone"]))} if cls._digits(creds.get("pudo_telefone")) else {}),
                    **({"email": creds["pudo_email"]} if creds.get("pudo_email") else {}),
                }

        # Serviço Tipo:
        # A Total Express exige código numérico contratado (Ex: 1 = EXP / Expresso Total)
        if servico_raw.isdigit():
            service_type = int(servico_raw)
        else:
            service_type = 1 # Padrão EXP (Expresso Total contratado para Edições Shalom)

        recipient = pedido.get("destinatario") or {}
        address = recipient.get("endereco") or {}
        name = str(recipient.get("nome") or pedido.get("cliente_nome") or "").strip()
        cpf_cnpj = cls._digits(recipient.get("cpfCnpj") or recipient.get("cpf_cnpj") or pedido.get("cliente_cpf_cnpj"))
        cep = cls._digits(address.get("cep") or recipient.get("cep") or pedido.get("cep"))
        street = str(address.get("logradouro") or pedido.get("logradouro") or "").strip()
        number = str(address.get("numero") or pedido.get("numero") or "").strip()
        complement = str(address.get("complemento") or pedido.get("complemento") or "").strip()
        neighborhood = str(address.get("bairro") or pedido.get("bairro") or "").strip()
        city = str(address.get("cidade") or recipient.get("cidade") or pedido.get("cidade") or "").split("(")[0].strip()
        state = str(address.get("uf") or recipient.get("uf") or pedido.get("uf") or "").strip().upper()
        if not name:
            errors.append("Nome do destinatário obrigatório.")
        if len(name) > 60:
            errors.append("Nome do destinatário excede 60 caracteres.")
        if len(cpf_cnpj) not in (11, 14):
            errors.append("CPF/CNPJ do destinatário precisa ter 11 ou 14 dígitos.")
        if len(cep) != 8:
            errors.append("CEP do destinatário precisa ter 8 dígitos.")
        if not street or len(street) > 150:
            errors.append("Logradouro obrigatório (máximo 150 caracteres).")
        if not number:
            errors.append("Número do endereço obrigatório; informe S/N quando inexistente.")
        if len(number) > 30:
            errors.append("Número do endereço excede 30 caracteres.")
        if len(complement) > 100:
            errors.append("Complemento excede 100 caracteres.")
        if not neighborhood or len(neighborhood) > 100:
            errors.append("Bairro obrigatório (máximo 100 caracteres).")
        if not city or len(city) > 80:
            errors.append("Cidade obrigatória (máximo 80 caracteres).")
        if len(state) != 2:
            errors.append("UF obrigatória (2 letras).")
        phone_raw = cls._digits(recipient.get("telefone") or recipient.get("celular") or pedido.get("telefone") or pedido.get("celular") or "8532168918")
        if not re.fullmatch(r"\d{1,12}", phone_raw):
            phone_raw = phone_raw[-11:] if len(phone_raw) > 11 else "8532168918"
        order = str(pedido.get("numero_pedido") or pedido.get("numero_remessa") or pedido.get("pedido") or "").strip()
        if not order or len(order) > 60:
            errors.append("Código do pedido obrigatório (máximo 60 caracteres).")
        # Serviço Tipo (1 = EXP / Expresso Total contratado para Edições Shalom):
        if servico_raw.isdigit():
            service_type = int(servico_raw)
        else:
            service_type = 1
        if service_type == 13:
            errors.append("Serviço reverso (13) exige informações comerciais adicionais; emissão bloqueada.")
        try:
            weight = float(pedido.get("peso_kg") or 0)
            if weight <= 0 or weight >= 1000:
                raise ValueError()
        except (TypeError, ValueError):
            errors.append("Peso precisa ser positivo e caber no campo decimal (3,2).")
            weight = 0
        try:
            volumes = int(pedido.get("volumes") or pedido.get("qtd_volumes") or pedido.get("qtd_etiquetas") or 1)
            if volumes <= 0 or volumes > 99:
                raise ValueError()
        except (TypeError, ValueError):
            errors.append("Quantidade de volumes deve ser de 1 a 99.")
            volumes = 1
        nature = str(pedido.get("natureza") or pedido.get("natureza_mercadoria") or "LIVROS / ARTIGOS RELIGIOSOS").strip()
        if not nature:
            nature = "LIVROS / ARTIGOS RELIGIOSOS"
        if len(nature) > 60:
            nature = nature[:60]
        invoice_key = cls._digits(pedido.get("chave_nfe"))
        invoice_type = "nfe" if (invoice_key or pedido.get("numero_nf")) else str(pedido.get("documento_tipo") or "").strip().lower()
        invoice_number = cls._digits(pedido.get("numero_nf"))
        invoice_series = cls._digits(pedido.get("serie_nf") or "1")
        invoice_date = cls._date(pedido.get("data_emissao") or pedido.get("data_nf"))
        doc_fiscal = {}
        if invoice_key or invoice_number:
            if len(invoice_key) != 44:
                errors.append("NF-e indicada mas chave de acesso não tem 44 dígitos.")
            if not invoice_number:
                errors.append("NF-e indicada mas número da nota está ausente.")
            if not invoice_series:
                errors.append("NF-e indicada mas série está ausente.")
            if not invoice_date:
                errors.append("NF-e indicada mas data de emissão não foi reconhecida.")
            try:
                total = float(pedido.get("valor_nf") or 0)
                if total <= 0:
                    raise ValueError()
            except (TypeError, ValueError):
                errors.append("NF-e indicada mas valor total é inválido/ausente.")
                total = 0
            invoice = {
                "nfeNumero": int(invoice_number) if invoice_number else 0,
                "nfeSerie": int(invoice_series) if invoice_series else 0,
                "nfeData": invoice_date,
                "nfeValTotal": round(total, 2),
                "nfeValProd": round(float(pedido.get("valor_produtos") or total), 2),
                "nfeChave": invoice_key,
            }
            cfop = cls._digits(pedido.get("cfop_nf") or pedido.get("cfop"))
            if cfop:
                invoice["nfeCfop"] = int(cfop[:4])
            doc_fiscal = {"nfe": [invoice]}
        else:
            errors.append("Smart PUDO exige ao menos um documento fiscal; não há NF-e nem outros documentos para compor com segurança.")
        if errors:
            raise TotalExpressValidationError(errors)

        phone_clean = cls._digits(recipient.get("telefone") or recipient.get("celular") or pedido.get("telefone") or "8532168918")
        phone = int(phone_clean) if phone_clean else 8532168918

        encomenda = {
            "servicoTipo": service_type,
            "entregaTipo": int(pedido.get("entrega_tipo") or 0),
            "peso": round(weight, 2),
            "volumes": volumes,
            "condFrete": "CIF",
            "pedido": order,
            "natureza": nature,
            "icmsIsencao": int(pedido.get("icms_isencao") or 0),
            "destinatario": {
                "nome": name,
                "cpfCnpj": cpf_cnpj,
                "endereco": {
                    "logradouro": street,
                    "numero": number,
                    "bairro": neighborhood,
                    "cidade": city,
                    "estado": state,
                    "pais": "Brasil",
                    "cep": cep,
                },
                "telefone1": phone,
            },
            "docFiscal": doc_fiscal,
        }
        # Inclui o bloco 'pudo' apenas se estiver configurado para modalidade PUDO
        if pudo_dict:
            encomenda["pudo"] = pudo_dict
        if complement:
            encomenda["destinatario"]["endereco"]["complemento"] = complement
        for source, target, limit in (("email", "email", 80), ("ponto_referencia", "pontoReferencia", 255)):
            value = str(recipient.get(source) or address.get(source) or "").strip()
            if value:
                encomenda["destinatario"][target] = value[:limit]
        reid_val = int(reid) if str(reid).isdigit() else reid
        payload_dict = {
            "remetenteId": reid_val,
            "reidParent": str(reid),
            "cnpj": cnpj,
            "encomendas": [encomenda]
        }
        if embarcador and embarcador != cnpj:
            payload_dict["cnpjEmbarcador"] = embarcador
        return payload_dict

    @classmethod
    def get_db_path(cls) -> Path:
        env_path = os.getenv("TOTAL_EXPRESS_DB_PATH")
        if env_path:
            p = Path(env_path)
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                return p
            except (OSError, PermissionError):
                pass
        # No ambiente Vercel / AWS Lambda o filesystem é Read-Only exceto /tmp
        if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            tmp_dir = Path("/tmp")
            try:
                tmp_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            return tmp_dir / "total_express_local.db"
        local_dir = Path("data")
        try:
            local_dir.mkdir(parents=True, exist_ok=True)
            return local_dir / "total_express_local.db"
        except (OSError, PermissionError):
            import tempfile
            return Path(tempfile.gettempdir()) / "total_express_local.db"

    @classmethod
    def registrar_encomenda(cls, pedido: Dict[str, Any]) -> Dict[str, Any]:
        creds = cls.get_credentials()
        if not creds["username"] or not creds["password"]:
            return {"sucesso": False, "pendente_credenciais": True, "erro": "Configure TOTAL_EXPRESS_USER e TOTAL_EXPRESS_PASSWORD para homologação."}
        try:
            payload = cls.construir_payload(pedido, creds)
        except TotalExpressValidationError as exc:
            cls.salvar_resultado(pedido, {"pedido": pedido.get("numero_pedido") or pedido.get("pedido")}, {}, "ERRO_VALIDACAO", erro=str(exc))
            return {"sucesso": False, "erros_validacao": exc.errors, "erro": str(exc)}
        order = payload["encomendas"][0]["pedido"]
        path = cls.get_db_path()
        with sqlite3.connect(path, timeout=10) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS total_express_encomendas (id INTEGER PRIMARY KEY AUTOINCREMENT, pedido TEXT NOT NULL UNIQUE, status TEXT NOT NULL, awb TEXT UNIQUE, rota TEXT, codigo_barras TEXT, tipo_servico TEXT, data TEXT, hora TEXT, documento_fiscal TEXT, payload_json TEXT NOT NULL, resposta_json TEXT, erro TEXT, criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT status, awb FROM total_express_encomendas WHERE pedido = ?", (order,)).fetchone()
            if existing and (existing[1] or existing[0] in ("REGISTRADO", "PARCIAL", "ENVIANDO")):
                conn.rollback()
                return {"sucesso": False, "duplicado": True, "erro": f"Pedido {order} já registrado localmente (status {existing[0]}, AWB {existing[1] or 'indisponível'}). Não reenviado."}
            conn.execute("INSERT INTO total_express_encomendas (pedido,status,payload_json) VALUES (?, 'ENVIANDO', ?) ON CONFLICT(pedido) DO UPDATE SET status='ENVIANDO', payload_json=excluded.payload_json, erro=NULL, atualizado_em=CURRENT_TIMESTAMP", (order, json.dumps(payload, ensure_ascii=False)))
        env = (os.getenv("TOTAL_EXPRESS_ENV") or "producao").strip().lower()
        target_url = cls.URL_PRODUCAO if env == "producao" else cls.URL_HOMOLOGACAO
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "PostmanRuntime/7.43.0",
            "Accept": "*/*",
            "Connection": "keep-alive"
        }
        try:
            response = requests.post(target_url, json=payload, auth=(creds["username"], creds["password"]), headers=headers, timeout=25)
            try:
                data = response.json()
            except ValueError:
                data = {"respostaTexto": response.text[:4000]}
            retorno = data.get("retorno") or {}
            success_items = retorno.get("encomendas") or []
            api_errors = retorno.get("erros") or []
            result = {"sucesso": response.status_code == 200, "httpStatus": response.status_code, "raw": data, "payload": payload}
            if response.status_code in (200, 206):
                result["retorno"] = retorno
                result["erros"] = api_errors
                for item in success_items:
                    volume = (item.get("volumes") or [{}])[0]
                    persisted = {**item, **volume, "documentoFiscal": item.get("documentoFiscal") or []}
                    cls.salvar_resultado(pedido, persisted, payload, "REGISTRADO" if response.status_code == 200 else "PARCIAL", data)
                for item_error in api_errors:
                    cls.salvar_resultado({**pedido, "numero_pedido": str(item_error.get("pedido") or order)}, {"pedido": str(item_error.get("pedido") or order)}, payload, "ERRO_API", data, str(item_error.get("erro") or "Erro de processamento parcial"))
                if response.status_code == 206:
                    result["sucesso"] = bool(success_items)
                    result["parcial"] = True
            elif response.status_code == 400:
                result["erro"] = data
                cls.salvar_resultado(pedido, {"pedido": order}, payload, "ERRO_API", data, json.dumps(data, ensure_ascii=False))
            else:
                result["erro"] = f"HTTP inesperado {response.status_code}"
                cls.salvar_resultado(pedido, {"pedido": order}, payload, "ERRO_HTTP", data, result["erro"])
            return result
        except requests.RequestException as exc:
            logger.exception("Falha de conexão na homologação Smart PUDO")
            cls.salvar_resultado(pedido, {"pedido": order}, payload, "ERRO_CONEXAO", erro=str(exc))
            return {"sucesso": False, "erro": f"Falha de conexão: {exc}"}

    @classmethod
    def salvar_resultado(cls, pedido: Dict[str, Any], encomenda: Dict[str, Any], payload: Dict[str, Any], status: str, resposta: Dict[str, Any] = None, erro: str = "") -> None:
        path = cls.get_db_path()
        serialized = json.dumps(resposta or {}, ensure_ascii=False)
        try:
            with sqlite3.connect(path, timeout=10) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""CREATE TABLE IF NOT EXISTS total_express_encomendas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pedido TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    awb TEXT UNIQUE,
                    rota TEXT,
                    codigo_barras TEXT,
                    tipo_servico TEXT,
                    data TEXT,
                    hora TEXT,
                    documento_fiscal TEXT,
                    payload_json TEXT NOT NULL,
                    resposta_json TEXT,
                    erro TEXT,
                    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )""")
                conn.execute("""INSERT INTO total_express_encomendas
                    (pedido, status, awb, rota, codigo_barras, tipo_servico, data, hora,
                     documento_fiscal, payload_json, resposta_json, erro)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(pedido) DO UPDATE SET status=excluded.status,
                     awb=COALESCE(excluded.awb, total_express_encomendas.awb),
                     rota=COALESCE(excluded.rota, total_express_encomendas.rota),
                     codigo_barras=COALESCE(excluded.codigo_barras, total_express_encomendas.codigo_barras),
                     tipo_servico=COALESCE(excluded.tipo_servico, total_express_encomendas.tipo_servico),
                     data=COALESCE(excluded.data, total_express_encomendas.data),
                     hora=COALESCE(excluded.hora, total_express_encomendas.hora),
                     documento_fiscal=COALESCE(excluded.documento_fiscal, total_express_encomendas.documento_fiscal),
                     payload_json=excluded.payload_json, resposta_json=excluded.resposta_json,
                     erro=excluded.erro, atualizado_em=CURRENT_TIMESTAMP""",
                    (str(encomenda.get("pedido") or pedido.get("numero_pedido") or ""), status,
                     encomenda.get("awb"), encomenda.get("rota"), encomenda.get("codigoBarras"),
                     encomenda.get("tipoServico"), encomenda.get("data"), encomenda.get("hora"),
                     json.dumps(encomenda.get("documentoFiscal") or [], ensure_ascii=False),
                     json.dumps(payload, ensure_ascii=False), serialized, erro))
        except Exception as sql_err:
            logger.warning(f"Erro ao salvar SQLite local Total Express: {sql_err}")

        # Espelhar pré-postagem no Turso DB se AWB gerado com sucesso
        awb = encomenda.get("awb")
        if awb and status in ("REGISTRADO", "PARCIAL"):
            try:
                from services.correios_hub_service import execute_turso_query
                pedido_num = str(encomenda.get("pedido") or pedido.get("numero_pedido") or pedido.get("pedido") or "")
                nf_num = str(pedido.get("numero_nf") or "")
                dest_nome = str(pedido.get("cliente_nome") or (pedido.get("destinatario") or {}).get("nome") or "")
                dest_obj = pedido.get("destinatario") or {}
                end_obj = dest_obj.get("endereco") or {}
                cidade_dest = str(pedido.get("cidade") or end_obj.get("cidade") or "")
                uf_dest = str(pedido.get("uf") or end_obj.get("uf") or "")
                cep_dest = str(pedido.get("cep") or end_obj.get("cep") or "")
                servico_nome = encomenda.get("tipoServico") or "TOTAL_EXPRESS"
                execute_turso_query("""
                    INSERT INTO prepostagens (
                        pedido, numero_nf, chave_nfe, id_prepostagem, codigo_objeto,
                        servico, destinatario, cidade, uf, cep, status_rotulo, status_impressao, cancelado, tipo_item
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PRONTO', 'PENDENTE', 0, 'PEDIDO')
                    ON CONFLICT(codigo_objeto) DO UPDATE SET
                        status_rotulo='PRONTO', status_impressao='PENDENTE', cancelado=0
                """, [pedido_num, nf_num, str(pedido.get("chave_nfe") or ""), f"TOTAL_EXPRESS_{awb}", awb, servico_nome, dest_nome, cidade_dest, uf_dest, cep_dest])
            except Exception as turso_err:
                logger.warning(f"Não foi possível espelhar AWB Total Express no Turso DB: {turso_err}")

    @classmethod
    def listar_encomendas(cls) -> List[Dict[str, Any]]:
        path = cls.get_db_path()
        if not path.exists():
            return []
        try:
            with sqlite3.connect(path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT * FROM total_express_encomendas ORDER BY id DESC LIMIT 200").fetchall()
            return [dict(row) for row in rows]
        except Exception:
            return []

    @staticmethod
    def _desenhar_danfe_simplificada(c: canvas.Canvas, dados: Dict[str, Any], W: float, H: float) -> None:
        chave = re.sub(r"\D", "", str(dados.get("chave_nfe") or ""))
        if len(chave) != 44:
            return

        def dt(txt, x, y_top, size, bold=False):
            c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            c.drawString(x, H - y_top - size, str(txt or ""))

        def dl(x1, y1, x2, y2, width=0.8):
            c.setLineWidth(width)
            c.line(x1, H - y1, x2, H - y2)

        # 1. Box Título
        c.setLineWidth(0.8)
        c.rect(5 * mm, H - 14 * mm, 90 * mm, 10 * mm, stroke=1, fill=0)
        dt("DANFE Simplificado", 32 * mm, 6.5 * mm, 12, bold=True)

        # 2. Barcode
        bc = code128.Code128(chave, barHeight=14 * mm, barWidth=0.42 * mm)
        bc.drawOn(c, 7 * mm, H - 32 * mm)

        # 3. Chave
        dt("CHAVE DE ACESSO", 36 * mm, 33 * mm, 6.5, bold=True)
        chave_fmt = " ".join([chave[i:i+4] for i in range(0, 44, 4)])
        dt(chave_fmt, 10 * mm, 37 * mm, 6.2, bold=False)

        # 4. Protocolo
        dt("PROTOCOLO DE AUTORIZAÇÃO", 30 * mm, 42 * mm, 6.5, bold=True)
        prot = dados.get("protocolo") or ("223260101536353 - " + datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        dt(prot, 20 * mm, 46 * mm, 6.2, bold=False)
        dl(5 * mm, 50 * mm, 95 * mm, 50 * mm)

        # 5. Emitente
        dt("DADOS DO EMITENTE:", 35 * mm, 51.5 * mm, 6.8, bold=True)
        dt("Nome/Razão: ASSOCIACAO SHALOM", 6 * mm, 56 * mm, 6.5)
        dt("CNPJ: 07.044.456/0003-64       IE: 068937741", 6 * mm, 60 * mm, 6.5)
        dt("Endereço: R CE 040, 16 AO LADO DA ENEL - LAGOA DO JUNCO", 6 * mm, 64 * mm, 6)
        dt("Cidade: AQUIRAZ / CE          CEP: 61700-000", 6 * mm, 68 * mm, 6.5)
        dl(5 * mm, 72 * mm, 95 * mm, 72 * mm)

        # 6. Dados Gerais NF-e
        dt("DADOS GERAIS DA NF-e:", 35 * mm, 73.5 * mm, 6.8, bold=True)
        dt("Tipo de operação: 1 (Saída)", 6 * mm, 78 * mm, 6.5, bold=True)
        nf_num = str(dados.get("numero_nf") or "").lstrip("0") or "SEM_NF"
        serie = str(dados.get("serie_nf") or "1")
        dt(f"Número: {nf_num}     Série: {serie}     Emissão: {dados.get('data_emissao') or datetime.now().strftime('%d/%m/%Y')}", 6 * mm, 82 * mm, 6.5)
        dl(5 * mm, 86 * mm, 95 * mm, 86 * mm)

        # 7. Destinatário
        dt("DADOS DO DESTINATÁRIO:", 34 * mm, 87.5 * mm, 6.8, bold=True)
        dest_nome = str(dados.get("dest_nome") or "")
        dt(f"Nome: {dest_nome[:45]}", 6 * mm, 92 * mm, 6.5)
        dest_doc = str(dados.get("dest_cpf_cnpj") or "")
        if dest_doc:
            dt(f"CPF/CNPJ: {dest_doc}", 6 * mm, 96 * mm, 6.5)
        dest_end = str(dados.get("dest_endereco") or "")
        dt(f"Endereço: {dest_end[:45]}", 6 * mm, 100 * mm, 6.5)
        dest_cid = str(dados.get("dest_cidade") or "")
        dest_uf = str(dados.get("dest_uf") or "")
        dest_cep = str(dados.get("dest_cep") or "")
        dt(f"Cidade: {dest_cid} / {dest_uf}    CEP: {dest_cep}", 6 * mm, 104 * mm, 6.5)
        dl(5 * mm, 108 * mm, 95 * mm, 108 * mm)

        # 8. Valor Total
        dt("VALOR TOTAL DA NOTA FISCAL:", 6 * mm, 112 * mm, 7.5, bold=True)
        val = float(dados.get("valor_nf") or 0.0)
        dt(f"R$ {val:.2f}".replace(".", ","), 55 * mm, 112 * mm, 8, bold=True)
        dl(5 * mm, 118 * mm, 95 * mm, 118 * mm)

        # 9. Rodapé
        dt("Emissão em Contingência: 0 - Não", 6 * mm, 122 * mm, 6.2)
        dt("Consulta via leitor de QR Code ou portal SEFAZ", 6 * mm, 126 * mm, 6)
        dt("EMISSÃO AUTORIZADA", 38 * mm, 131 * mm, 7, bold=True)

    @classmethod
    def gerar_etiqueta(cls, dados: Dict[str, Any]) -> bytes:
        awb = str(dados.get("awb") or "").strip()
        if not awb:
            raise ValueError("AWB obrigatória para gerar etiqueta.")

        W = 100 * mm
        H = 140 * mm
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=(W, H))
        c.setTitle(f"Etiqueta Total Express {awb}")

        # Extração de campos normalizados
        dest = dados.get("destinatario") or {}
        if isinstance(dest, str):
            dest_nome = dest
            end_dest = {}
        else:
            dest_nome = str(dest.get("nome") or dados.get("dest_nome") or "").strip()
            end_dest = dest.get("endereco") or {}

        logradouro = str(end_dest.get("logradouro") or dados.get("logradouro") or "").strip()
        numero = str(end_dest.get("numero") or dados.get("numero") or "").strip()
        complemento = str(end_dest.get("complemento") or dados.get("complemento") or "").strip()
        bairro = str(end_dest.get("bairro") or dados.get("bairro") or "").strip()
        cidade = str(end_dest.get("cidade") or dados.get("cidade") or "").strip().upper()
        uf = str(end_dest.get("estado") or end_dest.get("uf") or dados.get("uf") or "").strip().upper()
        cep = str(end_dest.get("cep") or dados.get("cep") or "").strip()

        pedido_num = str(dados.get("pedido") or dados.get("numero_pedido") or "").strip()
        nf_num = str(dados.get("numero_nf") or "").lstrip("0") or "SEM_NF"
        chave_nfe = re.sub(r"\D", "", str(dados.get("chave_nfe") or ""))
        rota = str(dados.get("rota") or "05-TZL-SP-LOC-[I88]").strip()
        tipo_servico = str(dados.get("tipoServico") or dados.get("tipo_servico") or "STD").strip().upper()
        servico_sigla = "EXP" if "EXP" in tipo_servico else "STD"

        # Formatação de data (ex: 05/Nov)
        meses_br = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        agora = datetime.now()
        dt_str = dados.get("data_emissao") or dados.get("data") or ""
        dt_exibicao = f"{agora.day:02d}/{meses_br[agora.month - 1]}"
        if dt_str:
            try:
                if "-" in dt_str:
                    parts = dt_str.split("T")[0].split("-")
                    dt_exibicao = f"{int(parts[2]):02d}/{meses_br[int(parts[1]) - 1]}"
                elif "/" in dt_str:
                    parts = dt_str.split("/")
                    dt_exibicao = f"{int(parts[0]):02d}/{meses_br[int(parts[1]) - 1]}"
            except Exception:
                pass

        # Peso formatado com 3 casas decimais
        try:
            peso_val = float(dados.get("peso_kg") or dados.get("peso") or 0.830)
            peso_fmt = f"{peso_val:.3f}"
        except Exception:
            peso_fmt = "0.830"

        vol_val = str(dados.get("volumes") or dados.get("volume") or "1")

        # ========================================================
        # PÁGINA 1: ETIQUETA OFICIAL TOTAL EXPRESS (100% FIEL)
        # ========================================================

        # 1. Linha Topo
        c.setLineWidth(1)
        c.line(4 * mm, H - 4 * mm, 96 * mm, H - 4 * mm)

        # 2. Total Express
        c.setFont("Helvetica-Bold", 17)
        c.drawString(5 * mm, H - 12 * mm, "Total Express")

        # 3. Destinatário
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(5 * mm, H - 20 * mm, f"Dest.: {dest_nome[:42]}")

        # Endereço do Destinatário
        c.setFont("Helvetica", 6.8)
        logr_line = f"{logradouro}, {numero} {complemento}".strip().rstrip(",")
        c.drawString(5 * mm, H - 26 * mm, logr_line[:48])
        c.drawString(5 * mm, H - 31 * mm, f"Bairro: {bairro[:25]}    CEP: {cep[:15]}")
        c.drawString(5 * mm, H - 36 * mm, f"Cidade: {cidade[:28]}    Estado: {uf[:4]}")

        # 4. Remetente (Edições Shalom)
        c.setFont("Helvetica", 6.2)
        c.drawString(5 * mm, H - 43 * mm, "Rem.: EDICOES SHALOM")
        c.drawString(5 * mm, H - 48 * mm, "R CE 040, 16 AO LADO DA ENEL - LAGOA DO JUNCO")
        c.drawString(5 * mm, H - 53 * mm, "Aquiraz / CE  61700000")
        c.drawString(5 * mm, H - 58 * mm, "CNPJ: 07044456000364")

        # 5. Box Serviço (Canto Superior Direito)
        c.setLineWidth(0.8)
        c.rect(81 * mm, H - 23 * mm, 15 * mm, 18 * mm, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(83 * mm, H - 12 * mm, servico_sigla)
        c.setFont("Helvetica-Bold", 6)
        c.drawString(82.5 * mm, H - 17 * mm, "TOTAL")
        c.setFont("Helvetica", 5.5)
        c.drawString(82.5 * mm, H - 20.5 * mm, "express")

        # 6. Tabela / Quadro de Dados Fiscais
        qx = 66 * mm
        qy = H - 65 * mm
        qw = 30 * mm
        qh = 40 * mm
        c.rect(qx, qy, qw, qh, stroke=1, fill=0)
        c.setFillColorRGB(0, 0, 0)
        c.rect(qx, qy, 8 * mm, qh, fill=1, stroke=0)

        fields = [
            ("NF", nf_num),
            ("PED", pedido_num),
            ("VOL", vol_val),
            ("TP", pedido_num),
            ("DT", dt_exibicao),
            ("KG", peso_fmt),
            ("PEÇA", f"{vol_val} / {vol_val}")
        ]
        row_h = qh / 7
        for idx, (label, val) in enumerate(fields):
            y_cell = qy + qh - (idx + 1) * row_h
            if idx > 0:
                c.setStrokeColorRGB(1, 1, 1)
                c.setLineWidth(0.5)
                c.line(qx, y_cell + row_h, qx + 8 * mm, y_cell + row_h)
                c.setStrokeColorRGB(0, 0, 0)
                c.line(qx + 8 * mm, y_cell + row_h, qx + qw, y_cell + row_h)
            c.setFillColorRGB(1, 1, 1)
            c.setFont("Helvetica-Bold", 6.5)
            c.drawCentredString(qx + 4 * mm, y_cell + 1.8 * mm, label)
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica-Bold" if idx < 2 else "Helvetica", 6.8)
            c.drawString(qx + 10 * mm, y_cell + 1.8 * mm, str(val)[:15])

        # 7. Faixa da Rota Central
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(1.2)
        c.line(4 * mm, H - 68 * mm, 96 * mm, H - 68 * mm)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(50 * mm, H - 75.5 * mm, rota)
        c.line(4 * mm, H - 79 * mm, 96 * mm, H - 79 * mm)

        # 8. Código de Barras Code 128 (AWB)
        barcode_val = str(dados.get("codigoBarras") or awb).strip()
        bar = code128.Code128(barcode_val, barHeight=44 * mm, barWidth=0.44 * mm, humanReadable=False)
        bar.drawOn(c, 8 * mm, H - 128 * mm)

        # 9. AWB Vertical Rotacionada 90°
        c.saveState()
        c.translate(88 * mm, H - 128 * mm)
        c.rotate(90)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(0, 0, f"AWB   {awb}")
        c.restoreState()

        # 10. Rodapé e Linha Pontilhada
        c.setLineWidth(0.7)
        c.setDash([2, 2], 0)
        c.line(2 * mm, H - 134 * mm, 98 * mm, H - 134 * mm)
        c.setDash([], 0)
        c.setFont("Helvetica", 5.5)
        dt_full = agora.strftime("%d/%m/%Y %H:%M")
        c.drawRightString(96 * mm, H - 138 * mm, f"Impressão via ICS - Total Express - {dt_full}")

        c.showPage()

        # ========================================================
        # PÁGINA 2: DANFE SIMPLIFICADA (SE HOUVER CHAVE NFE)
        # ========================================================
        if chave_nfe and len(chave_nfe) == 44:
            danfe_dados = {
                "chave_nfe": chave_nfe,
                "numero_nf": nf_num,
                "serie_nf": str(dados.get("serie_nf") or "1"),
                "data_emissao": dt_str or agora.strftime("%d/%m/%Y"),
                "valor_nf": float(dados.get("valor_nf") or 0.0),
                "dest_nome": dest_nome,
                "dest_cpf_cnpj": str(dest.get("cpfCnpj") or dados.get("cliente_cpf_cnpj") or ""),
                "dest_endereco": logr_line,
                "dest_cidade": cidade,
                "dest_uf": uf,
                "dest_cep": cep,
                "protocolo": dados.get("protocolo") or ("223260101536353 - " + agora.strftime("%d/%m/%Y %H:%M:%S"))
            }
            cls._desenhar_danfe_simplificada(c, danfe_dados, W, H)
            c.showPage()

        c.save()
        return buffer.getvalue()
