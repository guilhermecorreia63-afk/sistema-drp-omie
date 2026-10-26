"""
Serviço Oficial de Consulta ao SRO Rastro dos Correios.
Consome a API v1 dos Correios utilizando a credencial segura CWS_TOKEN_SRO / TOKEN_SRO.
"""
import os
import sys
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List

raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from dotenv import load_dotenv
load_dotenv(os.path.join(raiz, ".env"))

def consultar_sro_objeto(codigo_objeto: str) -> Dict[str, Any]:
    """
    Consulta o rastreamento de um objeto na API Oficial SRO Rastro dos Correios.
    Retorna a linha do tempo completa e normalizada de eventos.
    """
    cod = str(codigo_objeto or "").strip().upper()
    if not cod:
        return {"sucesso": False, "mensagem": "Código de objeto não informado."}

    token = os.getenv("CWS_TOKEN_SRO") or os.getenv("TOKEN_SRO")
    if not token:
        return {
            "sucesso": False,
            "mensagem": "Token do SRO Rastro (CWS_TOKEN_SRO) não configurado no arquivo .env."
        }

    url = f"https://api.correios.com.br/srorastro/v1/objetos/{cod}?resultado=T"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Accept-Language": "pt-BR"
        }
    )

    # 1. Consulta prévia ao Portal Postal WebService
    dados_portal_postal = None
    try:
        from services import portal_postal_service
        resp_pp = portal_postal_service.consultar_por_sro(cod)
        if resp_pp.get("sucesso"):
            dados_portal_postal = resp_pp
    except Exception as e_pp:
        pass

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            objetos = data.get("objetos", [])
            if not objetos:
                if dados_portal_postal:
                    return {
                        "sucesso": True,
                        "codigo": cod,
                        "origem": "PORTAL_POSTAL",
                        "status_geral": dados_portal_postal.get("situacao") or "Objeto em Trânsito",
                        "descricao_status": f"Status Portal Postal: {dados_portal_postal.get('situacao')} (NF {dados_portal_postal.get('nf')})",
                        "destinatario": dados_portal_postal.get("destinatario"),
                        "data_postagem": dados_portal_postal.get("data_postagem"),
                        "eventos": [{
                            "codigo": "PP-01",
                            "tipo": "PORTAL_POSTAL",
                            "descricao": dados_portal_postal.get("situacao"),
                            "detalhe": f"Postado em {dados_portal_postal.get('data_postagem')} | Prazo estimado: {dados_portal_postal.get('data_prazo')}",
                            "data_hora": dados_portal_postal.get("data_situacao") or dados_portal_postal.get("data_postagem"),
                            "unidade_nome": "Agência dos Correios / Portal Postal",
                            "cidade_uf": ""
                        }]
                    }
                return {
                    "sucesso": False,
                    "codigo": cod,
                    "mensagem": f"Objeto {cod} não localizado no SRO Rastro."
                }

            obj = objetos[0]
            msg_obj = obj.get("mensagem")
            raw_eventos = obj.get("eventos", [])

            if not raw_eventos:
                # Se não tem eventos no SRO, mas o Portal Postal tem a postagem
                if dados_portal_postal:
                    return {
                        "sucesso": True,
                        "codigo": cod,
                        "origem": "PORTAL_POSTAL",
                        "status_geral": dados_portal_postal.get("situacao") or "Objeto em Trânsito",
                        "descricao_status": f"{dados_portal_postal.get('situacao')} (NF {dados_portal_postal.get('nf')})",
                        "destinatario": dados_portal_postal.get("destinatario"),
                        "data_postagem": dados_portal_postal.get("data_postagem"),
                        "eventos": [{
                            "codigo": "PP-01",
                            "tipo": "PORTAL_POSTAL",
                            "descricao": dados_portal_postal.get("situacao"),
                            "detalhe": f"Postado em {dados_portal_postal.get('data_postagem')} | Prazo estimado: {dados_portal_postal.get('data_prazo')}",
                            "data_hora": dados_portal_postal.get("data_situacao") or dados_portal_postal.get("data_postagem"),
                            "unidade_nome": "Agência dos Correios / Portal Postal",
                            "cidade_uf": ""
                        }]
                    }
                return {
                    "sucesso": True,
                    "codigo": cod,
                    "status_geral": "Etiqueta Gerada / Em Processamento",
                    "descricao_status": msg_obj or "Objeto cadastrado no sistema dos Correios. Aguardando primeira bipagem na agência.",
                    "eventos": []
                }

            eventos_norm = []
            for ev in raw_eventos:
                unidade = ev.get("unidade", {})
                end_unidade = unidade.get("endereco", {})
                cidade_uf_origem = ""
                if end_unidade:
                    cidade_uf_origem = f"{end_unidade.get('cidade', '')}/{end_unidade.get('uf', '')}".strip("/")

                dest_info = None
                unidade_dest = ev.get("unidadeDestino")
                if unidade_dest:
                    end_dest = unidade_dest.get("endereco", {})
                    dest_info = {
                        "tipo": unidade_dest.get("tipo", ""),
                        "nome": unidade_dest.get("nome", ""),
                        "cidade_uf": f"{end_dest.get('cidade', '')}/{end_dest.get('uf', '')}".strip("/")
                    }

                eventos_norm.append({
                    "codigo": ev.get("codigo", ""),
                    "tipo": ev.get("tipo", ""),
                    "descricao": ev.get("descricao", ""),
                    "detalhe": ev.get("detalhe", ""),
                    "data_hora": ev.get("dtCriacao", ""),
                    "unidade_nome": unidade.get("nome") or unidade.get("tipo", ""),
                    "cidade_uf": cidade_uf_origem,
                    "destino": dest_info
                })

            ultimo = eventos_norm[0] if eventos_norm else {}
            status_geral = ultimo.get("descricao", "Em Trânsito")

            return {
                "sucesso": True,
                "codigo": cod,
                "status_geral": status_geral,
                "data_ultimo_evento": ultimo.get("data_hora", ""),
                "local_ultimo_evento": ultimo.get("cidade_uf", ""),
                "eventos": eventos_norm
            }

    except urllib.error.HTTPError as e:
        err_msg = f"HTTP {e.code}"
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            err_msg = err_body.get("msgs", [err_msg])[0] if isinstance(err_body.get("msgs"), list) else err_body.get("mensagem", err_msg)
        except Exception:
            pass
        return {"sucesso": False, "codigo": cod, "mensagem": f"Erro na consulta aos Correios: {err_msg}"}
    except Exception as e:
        return {"sucesso": False, "codigo": cod, "mensagem": f"Falha de conexão com os Correios: {str(e)}"}
