import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("portal_postal_service")

PORTAL_POSTAL_WS_URL = "http://www.portalpostal.com.br/Cliente/Servicos/ws_consulta_postagem.jsp"

def get_credentials():
    codigo_agf = os.getenv("CORREIOS_CODIGO_AGF_PORTALPOSTAL", "94")
    usuario = os.getenv("CORREIOS_USERNAME_PORTALPOSTAL")
    senha = os.getenv("CORREIOS_PASSWORD_PORTALPOSTAL")
    return codigo_agf, usuario, senha

def consultar_por_sro(sro):
    """
    Consulta o código de rastreio SRO diretamente no WebService do Portal Postal.
    Retorna os dados oficiais de postagem e entrega do objeto.
    """
    codigo_agf, usuario, senha = get_credentials()
    if not usuario or not senha:
        logger.warning("Credenciais do Portal Postal não configuradas.")
        return {"sucesso": False, "erro": "Credenciais do Portal Postal ausentes no .env."}

    sro_clean = str(sro or "").strip().upper()
    if not sro_clean:
        return {"sucesso": False, "erro": "Código SRO não informado."}

    campos = "SRO|CODIGO_ECT|SERVICO|NF|CEP|DESTINATARIO|SITUACAO|DATA_SITUACAO|DATA_POSTAGEM|DATA_PRAZO"
    params = {
        "codigoAGF": codigo_agf,
        "usuario": usuario,
        "senha": senha,
        "tipoArquivo": "RAW",
        "formatoArquivo": "CSV",
        "separadorArquivo": ";",
        "cabecalhoArquivo": "S",
        "camposArquivo": campos,
        "tamanhoArquivo": "10",
        "sro": sro_clean
    }

    try:
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=ISO-8859-1"}
        res = requests.post(PORTAL_POSTAL_WS_URL, data=params, headers=headers, timeout=20)
        
        if res.status_code != 200:
            return {"sucesso": False, "erro": f"Portal Postal retornou HTTP {res.status_code}"}

        text = res.text.strip()
        if text.startswith("ERRO:"):
            # Sanitiza a resposta para nunca expor senhas/usuários
            erro_msg = text.replace(senha, "***").replace(usuario, "***")
            return {"sucesso": False, "erro": erro_msg}

        linhas = [l.strip() for l in text.splitlines() if l.strip()]
        if len(linhas) <= 1:
            return {"sucesso": False, "erro": f"Objeto {sro_clean} não encontrado no Portal Postal."}

        cols = [c.strip().upper() for c in linhas[0].split(";")]
        vals = [v.strip() for v in linhas[1].split(";")]
        registro = dict(zip(cols, vals))

        return {
            "sucesso": True,
            "origem": "PORTAL_POSTAL",
            "sro": registro.get("SRO"),
            "servico": registro.get("SERVICO"),
            "nf": registro.get("NF"),
            "cep": registro.get("CEP"),
            "destinatario": registro.get("DESTINATARIO"),
            "situacao": registro.get("SITUACAO"),
            "data_situacao": registro.get("DATA_SITUACAO"),
            "data_postagem": registro.get("DATA_POSTAGEM"),
            "data_prazo": registro.get("DATA_PRAZO"),
            "dados_brutos": registro
        }
    except Exception as e:
        logger.error(f"Erro ao consultar SRO {sro_clean} no Portal Postal: {e}")
        return {"sucesso": False, "erro": str(e)}

def consultar_por_periodo(data_inicio, data_fim):
    """
    Consulta todas as postagens do Portal Postal dentro de um intervalo de datas.
    data_inicio e data_fim devem estar no formato YYYY-MM-DD ou DD/MM/YYYY.
    """
    codigo_agf, usuario, senha = get_credentials()
    if not usuario or not senha:
        return {"sucesso": False, "erro": "Credenciais do Portal Postal ausentes."}

    # Normalizar para YYYY-MM-DD
    def norm_dt(d_str):
        if not d_str: return ""
        s = str(d_str).strip()
        if "/" in s:
            p = s.split("/")
            if len(p) == 3: return f"{p[2]}-{p[1]}-{p[0]}"
        return s

    d_ini = norm_dt(data_inicio)
    d_fim = norm_dt(data_fim)

    campos = "SRO|CODIGO_ECT|SERVICO|NF|CEP|DESTINATARIO|SITUACAO|DATA_SITUACAO|DATA_POSTAGEM|DATA_PRAZO"
    params = {
        "codigoAGF": codigo_agf,
        "usuario": usuario,
        "senha": senha,
        "tipoArquivo": "RAW",
        "formatoArquivo": "CSV",
        "separadorArquivo": ";",
        "cabecalhoArquivo": "S",
        "camposArquivo": campos,
        "tamanhoArquivo": "10",
        "data_inicio": d_ini,
        "data_fim": d_fim
    }

    try:
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=ISO-8859-1"}
        res = requests.post(PORTAL_POSTAL_WS_URL, data=params, headers=headers, timeout=30)
        
        text = res.text.strip()
        if text.startswith("ERRO:"):
            return {"sucesso": False, "erro": text.replace(senha, "***").replace(usuario, "***")}

        linhas = [l.strip() for l in text.splitlines() if l.strip()]
        if len(linhas) <= 1:
            return {"sucesso": True, "registros": [], "total": 0}

        cols = [c.strip().upper() for c in linhas[0].split(";")]
        registros = []
        for l in linhas[1:]:
            vals = [v.strip() for v in l.split(";")]
            reg = dict(zip(cols, vals))
            registros.append({
                "sro": reg.get("SRO"),
                "codigo_ect": reg.get("CODIGO_ECT"),
                "servico": reg.get("SERVICO"),
                "nf": reg.get("NF"),
                "cep": reg.get("CEP"),
                "destinatario": reg.get("DESTINATARIO"),
                "situacao": reg.get("SITUACAO"),
                "data_situacao": reg.get("DATA_SITUACAO"),
                "data_postagem": reg.get("DATA_POSTAGEM"),
                "data_prazo": reg.get("DATA_PRAZO")
            })

        return {"sucesso": True, "registros": registros, "total": len(registros)}
    except Exception as e:
        logger.error(f"Erro ao consultar período no Portal Postal: {e}")
        return {"sucesso": False, "erro": str(e)}

def buscar_objeto_por_destinatario_ou_nf(destinatario=None, nf=None, data_inicio="2026-09-01", data_fim="2026-10-31"):
    """
    Busca nas postagens recentes do Portal Postal por nome de destinatário ou número de Nota Fiscal.
    Útil quando o código de rastreio inicial era uma etiqueta preliminar ou cancelada.
    """
    resp = consultar_por_periodo(data_inicio, data_fim)
    if not resp.get("sucesso"):
        return None

    dest_norm = str(destinatario or "").strip().upper()
    nf_clean = str(nf or "").replace("-1", "").strip()

    for r in resp.get("registros", []):
        r_dest = str(r.get("destinatario") or "").strip().upper()
        r_nf = str(r.get("nf") or "").replace("-1", "").strip()

        if nf_clean and nf_clean == r_nf:
            return r

        if dest_norm and len(dest_norm) >= 6:
            # Match exato ou de substring relevante
            if dest_norm in r_dest or r_dest in dest_norm:
                return r

    return None
