# -*- coding: utf-8 -*-
"""
services/correios_hub_service.py - Servico Central para Modulo 5: Gestao de Postagens & Correios
Porta 100% equivalente de todas as Netlify Functions do Projeto Correios para Python Serverless (Vercel / Local).
Nenhuma chave ou credencial e exposta no codigo; tudo e lido via os.getenv().
"""

import os
import re
import json
import time
import base64
import logging
import smtplib
from io import BytesIO
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("correios_hub_service")

def _get_turso_creds() -> Tuple[str, str]:
    url = (os.getenv("CORREIOS_TURSO_URL") or "").strip()
    token = (os.getenv("CORREIOS_TURSO_TOKEN") or "").strip()
    if not url or not token:
        fb_url = (os.getenv("TURSO_DATABASE_URL") or "").strip()
        fb_tok = (os.getenv("TURSO_AUTH_TOKEN") or "").strip()
        if "gestoretiquetas" in fb_url:
            return fb_url, fb_tok
        return "", ""
    return url, token

def _get_omie_creds() -> Tuple[str, str]:
    key = (os.getenv("APP_KEY_MATRIZ") or os.getenv("APP_KEY") or "").strip()
    secret = (os.getenv("APP_SECRET_MATRIZ") or os.getenv("APP_SECRET") or "").strip()
    return key, secret

def _format_args(args: list) -> list:
    formatted = []
    for arg in (args or []):
        if arg is None:
            formatted.append({"type": "null"})
        elif isinstance(arg, bool):
            formatted.append({"type": "integer", "value": "1" if arg else "0"})
        elif isinstance(arg, int):
            formatted.append({"type": "integer", "value": str(arg)})
        elif isinstance(arg, float):
            formatted.append({"type": "float", "value": arg})
        else:
            formatted.append({"type": "text", "value": str(arg)})
    return formatted

def execute_turso_query(sql: str, args: list = None) -> Optional[Dict[str, Any]]:
    """Executa query unica no Turso de Correios via HTTP Pipeline v2."""
    turso_url, turso_token = _get_turso_creds()
    if not turso_url or not turso_token:
        logger.error("Credenciais do Turso DB de etiquetas não configuradas no ambiente.")
        raise RuntimeError("Credenciais do banco de etiquetas ausentes. Configure CORREIOS_TURSO_URL e CORREIOS_TURSO_TOKEN no painel da Vercel (banco gestoretiquetas).")

    http_url = turso_url.replace("libsql://", "https://").rstrip("/")
    payload = {
        "requests": [
            {
                "type": "execute",
                "stmt": {"sql": sql, "args": _format_args(args or [])}
            }
        ]
    }

    res = requests.post(
        f"{http_url}/v2/pipeline",
        json=payload,
        headers={
            "Authorization": f"Bearer {turso_token}",
            "Content-Type": "application/json"
        },
        timeout=20
    )
    if not res.ok:
        raise RuntimeError(f"Erro HTTP {res.status_code} no Turso: {res.text[:200]}")
    data = res.json()
    results = data.get("results") or []
    if results and results[0].get("type") == "error":
        msg = results[0].get("error", {}).get("message", "Erro no Turso")
        raise RuntimeError(msg)
    return results[0].get("response", {}).get("result") if results else None

def execute_turso_pipeline(stmts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Executa multiplas queries em transacao atomica (BEGIN -> stmts -> COMMIT) no Turso."""
    turso_url, turso_token = _get_turso_creds()
    if not turso_url or not turso_token:
        raise RuntimeError("Turso nao configurado.")

    http_url = turso_url.replace("libsql://", "https://").rstrip("/")
    reqs = [{"type": "execute", "stmt": {"sql": "BEGIN TRANSACTION", "args": []}}]
    for s in stmts:
        reqs.append({
            "type": "execute",
            "stmt": {"sql": s["sql"], "args": _format_args(s.get("args") or [])}
        })
    reqs.append({"type": "execute", "stmt": {"sql": "COMMIT", "args": []}})

    res = requests.post(
        f"{http_url}/v2/pipeline",
        json={"requests": reqs},
        headers={
            "Authorization": f"Bearer {turso_token}",
            "Content-Type": "application/json"
        },
        timeout=25
    )
    data = res.json()
    results = data.get("results") or []
    for idx, r in enumerate(results):
        if r.get("type") == "error":
            try:
                requests.post(
                    f"{http_url}/v2/pipeline",
                    json={"requests": [{"type": "execute", "stmt": {"sql": "ROLLBACK", "args": []}}]},
                    headers={"Authorization": f"Bearer {turso_token}", "Content-Type": "application/json"},
                    timeout=5
                )
            except Exception:
                pass
            raise RuntimeError(f"Falha na transacao (Passo {idx}): {r.get('error', {}).get('message', 'Erro Turso')}")
    return results

def _cell_val(cell: Any) -> Any:
    if isinstance(cell, dict):
        t = cell.get("type")
        if t == "null":
            return None
        v = cell.get("value")
        if t == "integer":
            try:
                return int(v)
            except Exception:
                return v
        if t == "float":
            try:
                return float(v)
            except Exception:
                return v
        return v
    return cell

def calcular_dv_sro(num: int) -> int:
    num_str = str(num).zfill(8)[:8]
    pesos = [8, 6, 4, 2, 3, 5, 9, 7]
    soma = sum(int(num_str[i]) * pesos[i] for i in range(8))
    resto = soma % 11
    if resto == 0:
        return 5
    if resto == 1:
        return 0
    return 11 - resto

def alocar_codigo_modico() -> Dict[str, str]:
    q_range = execute_turso_query(
        "SELECT id, sigla, num_inicio, num_fim, num_atual, sufixo, codigos_devolvidos_json "
        "FROM modico_ranges WHERE (servico = '20133' OR servico = 'IMPRESSO_MODICO') AND status = 'ATIVO' LIMIT 1"
    )
    rows = (q_range or {}).get("rows") or []
    if not rows:
        raise RuntimeError("Nenhuma faixa de Impresso Modico ativa cadastrada em modico_ranges.")

    row = rows[0]
    range_id = int(_cell_val(row[0]))
    sigla = str(_cell_val(row[1]) or "YD")
    num_inicio = int(_cell_val(row[2]) or 0)
    num_fim = int(_cell_val(row[3]) or 0)
    num_atual = int(_cell_val(row[4]) or 0)
    sufixo = str(_cell_val(row[5]) or "BR")
    raw_devolvidos = _cell_val(row[6])

    devolvidos: List[str] = []
    if raw_devolvidos:
        try:
            parsed = json.loads(str(raw_devolvidos))
            if isinstance(parsed, list):
                devolvidos = [str(x) for x in parsed]
        except Exception:
            devolvidos = []

    if devolvidos:
        codigo_gerado = devolvidos.pop(0)
        execute_turso_query(
            "UPDATE modico_ranges SET codigos_devolvidos_json = ? WHERE id = ?",
            [json.dumps(devolvidos) if devolvidos else None, range_id]
        )
    else:
        if num_atual > num_fim:
            raise RuntimeError(f"Faixa de Impresso Modico esgotada! (Atual: {num_atual}, Fim: {num_fim})")
        dv = calcular_dv_sro(num_atual)
        num_padded = str(num_atual).zfill(8)
        codigo_gerado = f"{sigla}{num_padded}{dv}{sufixo}"
        execute_turso_query(
            "UPDATE modico_ranges SET num_atual = num_atual + 1 WHERE id = ?",
            [range_id]
        )

    return {"codigoObjeto": codigo_gerado, "idPrepostagem": f"MODICO_{codigo_gerado}"}

def devolver_codigo_modico(codigo_objeto: str) -> Dict[str, Any]:
    q_range = execute_turso_query(
        "SELECT id, sigla, num_inicio, num_fim, num_atual, sufixo, codigos_devolvidos_json "
        "FROM modico_ranges WHERE (servico = '20133' OR servico = 'IMPRESSO_MODICO') AND status = 'ATIVO' LIMIT 1"
    )
    rows = (q_range or {}).get("rows") or []
    if not rows:
        return {"devolvido": False, "reusavel": False, "mensagem": "Faixa de Impresso Modico nao encontrada para devolucao."}

    row = rows[0]
    range_id = int(_cell_val(row[0]))
    num_atual = int(_cell_val(row[4]) or 0)
    raw_devolvidos = _cell_val(row[6])

    devolvidos: List[str] = []
    if raw_devolvidos:
        try:
            parsed = json.loads(str(raw_devolvidos))
            if isinstance(parsed, list):
                devolvidos = [str(x) for x in parsed]
        except Exception:
            devolvidos = []

    m = re.search(r"\d{8,9}", codigo_objeto or "")
    num_objeto = int(m.group(0)[:8]) if m else 0

    if num_objeto > 0 and num_objeto == num_atual - 1:
        execute_turso_query("UPDATE modico_ranges SET num_atual = num_atual - 1 WHERE id = ?", [range_id])
    else:
        if codigo_objeto not in devolvidos:
            devolvidos.append(codigo_objeto)
            execute_turso_query(
                "UPDATE modico_ranges SET codigos_devolvidos_json = ? WHERE id = ?",
                [json.dumps(devolvidos), range_id]
            )

    return {"devolvido": True, "reusavel": True, "mensagem": f"Codigo {codigo_objeto} devolvido com sucesso para a range Modico."}

def alocar_codigo_souza() -> Dict[str, str]:
    q_range = execute_turso_query(
        "SELECT id, sigla, num_inicio, num_fim, num_atual, sufixo, codigos_devolvidos_json "
        "FROM modico_ranges WHERE (servico = 'ENTREGA_PROPRIA' OR servico = 'SOUZA') AND status = 'ATIVO' LIMIT 1"
    )
    rows = (q_range or {}).get("rows") or []
    if not rows:
        import time
        ts_part = str(int(time.time() * 1000))[-8:]
        dv_rnd = calcular_dv_sro(int(ts_part))
        fallback_cod = f"SZ{ts_part}{dv_rnd}BR"
        return {"codigoObjeto": fallback_cod, "idPrepostagem": f"SOUZA_{fallback_cod}"}

    row = rows[0]
    range_id = int(_cell_val(row[0]))
    sigla = str(_cell_val(row[1]) or "SZ")
    num_inicio = int(_cell_val(row[2]) or 10000001)
    num_fim = int(_cell_val(row[3]) or 99999999)
    num_atual = int(_cell_val(row[4]) or 10000001)
    sufixo = str(_cell_val(row[5]) or "BR")
    raw_devolvidos = _cell_val(row[6])

    devolvidos: List[str] = []
    if raw_devolvidos:
        try:
            parsed = json.loads(str(raw_devolvidos))
            if isinstance(parsed, list):
                devolvidos = [str(x) for x in parsed]
        except Exception:
            devolvidos = []

    if devolvidos:
        codigo_gerado = devolvidos.pop(0)
        execute_turso_query(
            "UPDATE modico_ranges SET codigos_devolvidos_json = ? WHERE id = ?",
            [json.dumps(devolvidos) if devolvidos else None, range_id]
        )
    else:
        if num_atual > num_fim:
            raise RuntimeError(f"Faixa de Entrega Propria (Souza) esgotada! (Atual: {num_atual}, Fim: {num_fim})")
        dv = calcular_dv_sro(num_atual)
        num_padded = str(num_atual).zfill(8)
        codigo_gerado = f"{sigla}{num_padded}{dv}{sufixo}"
        execute_turso_query(
            "UPDATE modico_ranges SET num_atual = num_atual + 1 WHERE id = ?",
            [range_id]
        )

    return {"codigoObjeto": codigo_gerado, "idPrepostagem": f"SOUZA_{codigo_gerado}"}

def devolver_codigo_souza(codigo_objeto: str) -> Dict[str, Any]:
    q_range = execute_turso_query(
        "SELECT id, sigla, num_inicio, num_fim, num_atual, sufixo, codigos_devolvidos_json "
        "FROM modico_ranges WHERE (servico = 'ENTREGA_PROPRIA' OR servico = 'SOUZA') AND status = 'ATIVO' LIMIT 1"
    )
    rows = (q_range or {}).get("rows") or []
    if not rows:
        return {"devolvido": False, "mensagem": "Faixa de Souza nao encontrada para devolucao."}

    row = rows[0]
    range_id = int(_cell_val(row[0]))
    num_atual = int(_cell_val(row[4]) or 0)
    raw_devolvidos = _cell_val(row[6])

    devolvidos: List[str] = []
    if raw_devolvidos:
        try:
            parsed = json.loads(str(raw_devolvidos))
            if isinstance(parsed, list):
                devolvidos = [str(x) for x in parsed]
        except Exception:
            devolvidos = []

    m = re.search(r"\d{8,9}", codigo_objeto or "")
    num_objeto = int(m.group(0)[:8]) if m else 0

    if num_objeto > 0 and num_objeto == num_atual - 1:
        execute_turso_query("UPDATE modico_ranges SET num_atual = num_atual - 1 WHERE id = ?", [range_id])
    else:
        if codigo_objeto not in devolvidos:
            devolvidos.append(codigo_objeto)
            execute_turso_query(
                "UPDATE modico_ranges SET codigos_devolvidos_json = ? WHERE id = ?",
                [json.dumps(devolvidos), range_id]
            )

    return {"devolvido": True, "reusavel": True, "mensagem": f"Codigo {codigo_objeto} devolvido para a range Souza."}


def classificar_forma_envio_prata(texto_omie: str, cod_transportadora: Any = "", cidade_dest: str = "") -> Dict[str, str]:
    cod_str = str(cod_transportadora or "").strip()
    texto_raw = str(texto_omie or "")
    cid_raw = str(cidade_dest or "").strip().upper()
    
    import unicodedata
    texto_norm = unicodedata.normalize("NFD", texto_raw.upper())
    texto_upper = "".join(c for c in texto_norm if unicodedata.category(c) != "Mn")

    is_fortaleza = ("FORTALEZA" in cid_raw) or ("FORTALEZA" in texto_upper) or ("EUSEBIO" in cid_raw) or ("AQUIRAZ" in cid_raw)

    # Retiradas locais sem transporte: a Guarita pode compor lista de conferência;
    # retirada no estoque permanece fora de listas por ser processada no ato.
    if "GUARITA" in texto_upper and "RETIRADA" in texto_upper:
        return {"grupo": "RETIRADA GUARITA", "servico": "RETIRADA_GUARITA", "log": "Retirada na Guarita"}
    if "RETIRADA NO ESTOQUE" in texto_upper or "RETIRADA ESTOQUE" in texto_upper or "ESTOQUE" in texto_upper and "RETIRADA" in texto_upper:
        return {"grupo": "RETIRADA ESTOQUE", "servico": "RETIRADA_ESTOQUE", "log": "Retirada no Estoque"}

    # 1. J&T Express (pelo código oficial Omie ou texto)
    if cod_str in ("1854970300", "1962318541") or "J&T" in texto_upper or "J & T" in texto_upper or "JT EXPRESS" in texto_upper or "JTE" in texto_upper:
        return {"grupo": "J&T EXPRESS", "servico": "JT_STANDARD", "log": f"J&T Express (Cod: {cod_str})"}

    # 2. Total Express
    if cod_str == "2199110781" or "TOTAL EXPRESS" in texto_upper or "TEX COURIER" in texto_upper or "TOTAL_EXPRESS" in texto_upper:
        return {"grupo": "TOTAL EXPRESS", "servico": "TOTAL_STANDARD", "log": f"Total Express (Cod: {cod_str})"}

    # 2.5. Translatino (Redespacho levado via Roberto Souza)
    if "TRANSLATINO" in texto_upper or "TRANSLATINO" in str(cod_str).upper():
        return {"grupo": "SOUZA", "servico": "SOUZA_TRANSLATINO", "log": "Translatino (Levado via Roberto Souza)"}

    # 3. Roberto Souza (Entrega Local Fortaleza)
    if cod_str == "1854969807" or "ROBERTO SOUZA" in texto_upper or "ROBERTO SOUSA" in texto_upper or "SOUZA" in texto_upper or "SOUSA" in texto_upper or "ENTREGA LOCAL" in texto_upper or "FROTISTA" in texto_upper:
        return {"grupo": "SOUZA", "servico": "ENTREGA_PROPRIA", "log": f"Entrega Propria Souza (Cod: {cod_str})"}

    # 4. Regra Especial: "Entrega Econômica" na Transportadora Correios
    # - Se for Fortaleza / Região Metropolitana -> Entrega Local (Souza)
    # - Se for para fora de Fortaleza -> Impresso Módico
    if "ENTREGA ECONOMICA" in texto_upper or "ECONOMICA" in texto_upper or "ECONOMICO" in texto_upper:
        if is_fortaleza:
            return {"grupo": "SOUZA", "servico": "ENTREGA_PROPRIA", "log": "Entrega Economica em Fortaleza -> Souza"}
        else:
            return {"grupo": "CORREIOS", "servico": "IMPRESSO MODICO", "log": "Entrega Economica fora de Fortaleza -> Impresso Modico"}

    # 5. Correios por Serviços Específicos
    if "SEDEX" in texto_upper:
        return {"grupo": "CORREIOS", "servico": "SEDEX", "log": "Correios SEDEX"}
    if "MINI ENVIOS" in texto_upper or "MINI_ENVIOS" in texto_upper:
        return {"grupo": "CORREIOS", "servico": "MINI ENVIOS", "log": "Correios Mini Envios"}
    if "MODICO" in texto_upper or "IMPRESSO MODICO" in texto_upper or "IMPRESSO" in texto_upper or "20133" in texto_upper:
        return {"grupo": "CORREIOS", "servico": "IMPRESSO MODICO", "log": "Correios Impresso Modico"}
    if "PAC" in texto_upper:
        return {"grupo": "CORREIOS", "servico": "PAC", "log": "Correios PAC"}

    # 6. Correios por Código de Transportadora (Padroniza PAC)
    if cod_str in ("1817912309", "1980947090") or "CORREIOS" in texto_upper:
        return {"grupo": "CORREIOS", "servico": "PAC", "log": f"Correios Padrao PAC (Cod: {cod_str})"}

    # 7. Retiradas
    if "RETIRADA" in texto_upper or "BALCAO" in texto_upper or "GUARITA" in texto_upper or "UBER" in texto_upper:
        return {"grupo": "OUTROS", "servico": "RETIRADA", "log": "Retirada em Loja/Guarita"}

    return {"grupo": "OUTROS", "servico": "OUTROS", "log": f"Nao mapeado: {texto_raw[:40]}"}


class CorreiosHubService:
    """Implementa todos os handlers equivalentes as Netlify Functions de Projeto Correios."""

    # =========================================================================
    # 1. HANDLER: turso-db
    # =========================================================================
    @staticmethod
    def handle_turso_db(method: str, query_params: Dict[str, List[str]], body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        b = body or {}
        action = (query_params.get("action", [None])[0]) or b.get("action") or "list"

        try:
            # --- ACTION: atualizar_rastreamentos ---
            if action == "atualizar_rastreamentos":
                force = bool(b.get("force")) if method == "POST" else (query_params.get("force", ["false"])[0] == "true")
                limit_count = int(b.get("limit") or (query_params.get("limit", ["10"])[0]) or 10)

                q_eleg = execute_turso_query(
                    "SELECT id, codigo_objeto FROM prepostagens WHERE cancelado = 0 AND codigo_objeto IS NOT NULL AND LENGTH(codigo_objeto) > 0"
                )
                rows_eleg = (q_eleg or {}).get("rows") or []
                pre_map: Dict[str, int] = {}
                todos_codigos: List[str] = []
                for r in rows_eleg:
                    p_id = int(_cell_val(r[0]) or 0)
                    cod = str(_cell_val(r[1]) or "").strip()
                    if cod:
                        todos_codigos.append(cod)
                        if p_id:
                            pre_map[cod] = p_id

                elegiveis = len(todos_codigos)
                consultados = 0
                ignorados_cache_recente = 0
                ignorados_finalizados = 0
                erros = 0
                detalhes_erros = []

                q_cache = execute_turso_query("SELECT codigo_objeto, grupo_status, ultima_consulta_at FROM objeto_rastreamento")
                cache_map: Dict[str, Dict[str, Any]] = {}
                for row in ((q_cache or {}).get("rows") or []):
                    cod = str(_cell_val(row[0]) or "")
                    grp = str(_cell_val(row[1]) or "")
                    dt_str = str(_cell_val(row[2]) or "")
                    ts = 0.0
                    if dt_str:
                        try:
                            ts = datetime.fromisoformat(dt_str.replace(" ", "T")).timestamp()
                        except Exception:
                            ts = 0.0
                    if cod:
                        cache_map[cod] = {"grupo": grp, "ultimaConsulta": ts}

                agora_ts = time.time()
                codigos_para_consultar = []
                for cod in todos_codigos:
                    item_c = cache_map.get(cod)
                    if item_c:
                        if item_c["grupo"] == "ENTREGUE":
                            ignorados_finalizados += 1
                            continue
                        if not force and item_c["ultimaConsulta"] and (agora_ts - item_c["ultimaConsulta"] < 3600):
                            ignorados_cache_recente += 1
                            continue
                    codigos_para_consultar.append(cod)

                lote = codigos_para_consultar[:limit_count]
                token_sro = (os.getenv("CWS_TOKEN_SRO") or "").strip()

                for codigo_objeto in lote:
                    try:
                        time.sleep(0.35)
                        url_sro = f"https://api.correios.com.br/srorastro/v1/objetos/{codigo_objeto}?resultado=T"
                        sro_res = requests.get(
                            url_sro,
                            headers={
                                "Authorization": f"Bearer {token_sro}",
                                "Accept": "application/json",
                                "Accept-Language": "pt-BR"
                            },
                            timeout=12
                        )
                        if not sro_res.ok:
                            detalhes_erros.append({"codigo": codigo_objeto, "httpStatus": sro_res.status_code})
                            erros += 1
                            continue

                        sro_data = sro_res.json()
                        objetos_list = sro_data.get("objetos") or []
                        obj_data = objetos_list[0] if objetos_list else None
                        if not obj_data:
                            erros += 1
                            continue

                        eventos = obj_data.get("eventos") or []
                        ultimo_ev = eventos[0] if eventos else {}
                        cod_evento = str(ultimo_ev.get("codigo") or "").upper()
                        tipo_evento = str(ultimo_ev.get("tipo") or "")
                        desc_status = str(ultimo_ev.get("descricao") or obj_data.get("mensagem") or "Em processamento")
                        dt_ultimo = str(ultimo_ev.get("dtHrCriado") or "")
                        prev_entrega = str(obj_data.get("dtPrevista") or "")

                        unid = ultimo_ev.get("unidade") or {}
                        end_obj = unid.get("endereco") or {}
                        cidade_atual = str(end_obj.get("cidade") or "")
                        uf_atual = str(end_obj.get("uf") or "")
                        unidade_atual = str(unid.get("nome") or unid.get("tipo") or "")

                        grupo_status = "OUTRO"
                        if cod_evento == "FC":
                            if tipo_evento == "83" or "expirad" in desc_status.lower():
                                grupo_status = "ETIQUETA_EXPIRADA"
                            else:
                                grupo_status = "ETIQUETA_EMITIDA"
                        elif cod_evento == "PO":
                            grupo_status = "POSTADO"
                        elif cod_evento == "RO":
                            grupo_status = "EM_TRANSITO"
                        elif cod_evento == "OEC":
                            grupo_status = "SAIU_PARA_ENTREGA"
                        elif cod_evento in ("BDE", "BDI", "BDR"):
                            grupo_status = "ENTREGUE"
                        elif cod_evento == "LDI":
                            grupo_status = "AGUARDANDO_RETIRADA"
                        elif cod_evento.startswith("PAR"):
                            grupo_status = "DEVOLUCAO"
                        elif cod_evento == "OER":
                            grupo_status = "OCORRENCIA"
                        elif cod_evento == "SUS":
                            grupo_status = "SUSPENSO"

                        execute_turso_query("""
                            INSERT INTO objeto_rastreamento (
                              prepostagem_id, codigo_objeto, transportadora, codigo_evento, tipo_evento,
                              descricao_status, grupo_status, previsao_entrega, cidade_atual,
                              uf_atual, unidade_atual, eventos_json, data_ultimo_evento,
                              ultima_consulta_at, updated_at
                            ) VALUES (?, ?, 'CORREIOS', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            ON CONFLICT(codigo_objeto) DO UPDATE SET
                              prepostagem_id = excluded.prepostagem_id,
                              codigo_evento = excluded.codigo_evento,
                              tipo_evento = excluded.tipo_evento,
                              descricao_status = excluded.descricao_status,
                              grupo_status = excluded.grupo_status,
                              previsao_entrega = excluded.previsao_entrega,
                              cidade_atual = excluded.cidade_atual,
                              uf_atual = excluded.uf_atual,
                              unidade_atual = excluded.unidade_atual,
                              eventos_json = excluded.eventos_json,
                              data_ultimo_evento = excluded.data_ultimo_evento,
                              ultima_consulta_at = CURRENT_TIMESTAMP,
                              updated_at = CURRENT_TIMESTAMP
                        """, [
                            pre_map.get(codigo_objeto, 0), codigo_objeto, cod_evento, tipo_evento,
                            desc_status, grupo_status, prev_entrega, cidade_atual, uf_atual,
                            unidade_atual, json.dumps(eventos, ensure_ascii=False), dt_ultimo
                        ])
                        consultados += 1
                    except Exception as e_obj:
                        detalhes_erros.append({"codigo": codigo_objeto, "catchErr": str(e_obj)})
                        erros += 1

                return 200, {
                    "sucesso": True,
                    "has_token_sro": bool(token_sro),
                    "detalhes_erros": detalhes_erros,
                    "metricas": {
                        "elegiveis": elegiveis,
                        "consultados": consultados,
                        "ignorados_cache_recente": ignorados_cache_recente,
                        "ignorados_finalizados": ignorados_finalizados,
                        "erros": erros
                    }
                }

            # --- ACTION: dashboard_stats ---
            if action == "dashboard_stats":
                periodo = str(b.get("periodo") or (query_params.get("periodo", ["mes_atual"])[0]) or "mes_atual")
                data_inicio = str(b.get("data_inicio") or (query_params.get("data_inicio", [""])[0]) or "")
                data_fim = str(b.get("data_fim") or (query_params.get("data_fim", [""])[0]) or "")

                hoje = datetime.now()
                dt_start: Optional[datetime] = None
                dt_end: Optional[datetime] = hoje

                if periodo == "hoje":
                    dt_start = datetime(hoje.year, hoje.month, hoje.day, 0, 0, 0)
                elif periodo == "ontem":
                    ont = hoje - timedelta(days=1)
                    dt_start = datetime(ont.year, ont.month, ont.day, 0, 0, 0)
                    dt_end = datetime(ont.year, ont.month, ont.day, 23, 59, 59)
                elif periodo == "7d":
                    dt_start = hoje - timedelta(days=7)
                elif periodo == "15d":
                    dt_start = hoje - timedelta(days=15)
                elif periodo == "30d":
                    dt_start = hoje - timedelta(days=30)
                elif periodo == "mes_atual":
                    dt_start = datetime(hoje.year, hoje.month, 1, 0, 0, 0)
                elif periodo == "personalizado" and data_inicio:
                    try:
                        dt_start = datetime.fromisoformat(data_inicio)
                        if data_fim:
                            dt_end = datetime.fromisoformat(data_fim).replace(hour=23, minute=59, second=59)
                    except Exception:
                        dt_start = None

                where_exp = ["tp_nf = 1", "tipo_origem IN ('PEDIDO', 'REMESSA')"]
                args_exp = []
                if dt_start:
                    where_exp.append("(created_at >= ? OR data_emissao >= ?)")
                    args_exp.extend([dt_start.isoformat(), dt_start.strftime("%d/%m/%Y")])
                where_exp_sql = "WHERE " + " AND ".join(where_exp) if where_exp else ""

                q_exp = execute_turso_query(f"""
                    SELECT
                      COUNT(*) as total_faturadas,
                      SUM(CASE WHEN tipo_origem = 'PEDIDO' THEN 1 ELSE 0 END) as pedidos,
                      SUM(CASE WHEN tipo_origem = 'REMESSA' THEN 1 ELSE 0 END) as remessas,
                      SUM(CASE WHEN tipo_origem = 'ORIGEM_NAO_IDENTIFICADA' THEN 1 ELSE 0 END) as origem_nao_identificada,
                      COUNT(DISTINCT cliente_cpf_cnpj) as total_clientes
                    FROM omie_expedicoes_prata
                    {where_exp_sql}
                """, args_exp)
                r_exp = ((q_exp or {}).get("rows") or [[None]*5])[0]
                total_faturadas = int(_cell_val(r_exp[0]) or 0)
                qtd_pedidos = int(_cell_val(r_exp[1]) or 0)
                qtd_remessas = int(_cell_val(r_exp[2]) or 0)
                qtd_origem_nao_id = int(_cell_val(r_exp[3]) or 0)
                total_clientes = int(_cell_val(r_exp[4]) or 0)

                where_pre = []
                args_pre = []
                if dt_start:
                    where_pre.append("created_at >= ?")
                    args_pre.append(dt_start.isoformat())
                where_pre_sql = "WHERE " + " AND ".join(where_pre) if where_pre else ""

                q_pre = execute_turso_query(f"""
                    SELECT
                      COUNT(*) as total_geradas,
                      SUM(CASE WHEN cancelado = 0 AND (status_impressao IS NULL OR status_impressao = '' OR status_impressao = 'PENDENTE' OR status_impressao = 'PRONTO') THEN 1 ELSE 0 END) as aguardando_impressao,
                      SUM(CASE WHEN cancelado = 0 AND (status_impressao = 'IMPRESSO' OR status_impressao = 'ARQUIVADO' OR status_rotulo = 'IMPRESSO' OR status_rotulo = 'ARQUIVADO') THEN 1 ELSE 0 END) as impressas,
                      SUM(CASE WHEN cancelado = 1 OR status_rotulo = 'CANCELADO' THEN 1 ELSE 0 END) as canceladas
                    FROM prepostagens
                    {where_pre_sql}
                """, args_pre)
                r_pre = ((q_pre or {}).get("rows") or [[None]*4])[0]
                geradas = int(_cell_val(r_pre[0]) or 0)
                aguardando_imp = int(_cell_val(r_pre[1]) or 0)
                impressas = int(_cell_val(r_pre[2]) or 0)
                canceladas = int(_cell_val(r_pre[3]) or 0)

                where_rast_extra = ""
                args_rast = []
                if dt_start:
                    where_rast_extra = "AND p.created_at >= ?"
                    args_rast.append(dt_start.isoformat())

                q_rast = execute_turso_query(f"""
                    SELECT
                      COUNT(*) as total,
                      SUM(CASE WHEN o.grupo_status = 'ETIQUETA_EMITIDA' THEN 1 ELSE 0 END) as etiqueta_emitida,
                      SUM(CASE WHEN o.grupo_status = 'ETIQUETA_EXPIRADA' THEN 1 ELSE 0 END) as etiqueta_expirada,
                      SUM(CASE WHEN o.grupo_status = 'POSTADO' THEN 1 ELSE 0 END) as postado,
                      SUM(CASE WHEN o.grupo_status = 'EM_TRANSITO' THEN 1 ELSE 0 END) as em_transito,
                      SUM(CASE WHEN o.grupo_status = 'SAIU_PARA_ENTREGA' THEN 1 ELSE 0 END) as saiu_para_entrega,
                      SUM(CASE WHEN o.grupo_status = 'ENTREGUE' THEN 1 ELSE 0 END) as entregue,
                      SUM(CASE WHEN o.grupo_status = 'AGUARDANDO_RETIRADA' THEN 1 ELSE 0 END) as aguardando_retirada,
                      SUM(CASE WHEN o.grupo_status = 'DEVOLUCAO' THEN 1 ELSE 0 END) as devolucao,
                      SUM(CASE WHEN o.grupo_status = 'OCORRENCIA' THEN 1 ELSE 0 END) as ocorrencia,
                      SUM(CASE WHEN o.grupo_status = 'OUTRO' OR o.grupo_status IS NULL THEN 1 ELSE 0 END) as outro
                    FROM prepostagens p
                    LEFT JOIN objeto_rastreamento o ON p.codigo_objeto = o.codigo_objeto
                    WHERE p.cancelado = 0 AND p.codigo_objeto IS NOT NULL AND p.codigo_objeto != ''
                    {where_rast_extra}
                """, args_rast)
                r_rast = ((q_rast or {}).get("rows") or [[None]*11])[0]
                rastreamento = {
                    "total": int(_cell_val(r_rast[0]) or 0),
                    "etiqueta_emitida": int(_cell_val(r_rast[1]) or 0),
                    "etiqueta_expirada": int(_cell_val(r_rast[2]) or 0),
                    "postado": int(_cell_val(r_rast[3]) or 0),
                    "em_transito": int(_cell_val(r_rast[4]) or 0),
                    "saiu_para_entrega": int(_cell_val(r_rast[5]) or 0),
                    "entregue": int(_cell_val(r_rast[6]) or 0),
                    "aguardando_retirada": int(_cell_val(r_rast[7]) or 0),
                    "devolucao": int(_cell_val(r_rast[8]) or 0),
                    "ocorrencia": int(_cell_val(r_rast[9]) or 0),
                    "outro": int(_cell_val(r_rast[10]) or 0)
                }

                q_transp = execute_turso_query(f"""
                    SELECT transportadora_normalizada, COUNT(*) as qtd
                    FROM omie_expedicoes_prata
                    {where_exp_sql}
                    GROUP BY transportadora_normalizada
                    ORDER BY qtd DESC
                """, args_exp)
                transportadoras = [
                    {"nome": str(_cell_val(r[0]) or "OUTROS").upper(), "qtd": int(_cell_val(r[1]) or 0)}
                    for r in ((q_transp or {}).get("rows") or [])
                ]

                q_serv = execute_turso_query(f"""
                    SELECT servico_normalizado, COUNT(*) as qtd
                    FROM omie_expedicoes_prata
                    {where_exp_sql}
                    GROUP BY servico_normalizado
                    ORDER BY qtd DESC
                """, args_exp)
                servicos = [
                    {"nome": str(_cell_val(r[0]) or "OUTROS").upper(), "qtd": int(_cell_val(r[1]) or 0)}
                    for r in ((q_serv or {}).get("rows") or [])
                ]

                top_transp = transportadoras[0]["nome"] if transportadoras else "N/I"
                top_serv = servicos[0]["nome"] if servicos else "N/I"

                q_sync = execute_turso_query("""
                    SELECT finalizado_em, quantidade_encontrada, quantidade_nova, quantidade_existente, quantidade_erro, status
                    FROM omie_sync_control
                    ORDER BY id DESC LIMIT 1
                """)
                rows_sync = (q_sync or {}).get("rows") or []
                ultima_sync = None
                if rows_sync:
                    rs = rows_sync[0]
                    ultima_sync = {
                        "finalizado_em": _cell_val(rs[0]),
                        "encontradas": int(_cell_val(rs[1]) or 0),
                        "novas": int(_cell_val(rs[2]) or 0),
                        "existentes": int(_cell_val(rs[3]) or 0),
                        "erros": int(_cell_val(rs[4]) or 0),
                        "status": str(_cell_val(rs[5]) or "CONCLUIDO")
                    }

                return 200, {
                    "periodo": {
                        "chave": periodo,
                        "inicio": dt_start.strftime("%Y-%m-%d") if dt_start else None,
                        "fim": dt_end.strftime("%Y-%m-%d") if dt_end else None
                    },
                    "expedicoes": {
                        "total_faturadas": total_faturadas,
                        "pedidos": qtd_pedidos,
                        "remessas": qtd_remessas,
                        "origem_nao_identificada": qtd_origem_nao_id
                    },
                    "etiquetas": {
                        "geradas": geradas,
                        "aguardando_impressao": aguardando_imp,
                        "impressas": impressas,
                        "canceladas": canceladas
                    },
                    "rastreamento": rastreamento,
                    "transportadoras": transportadoras,
                    "servicos": servicos,
                    "indicadores": {
                        "top_transportadora": top_transp,
                        "top_servico": top_serv,
                        "total_clientes_distintos": total_clientes,
                        "total_nfs": total_faturadas
                    },
                    "ultima_sync_omie": ultima_sync
                }

            # --- ACTION: list_expedicoes_prata ---
            if action == "list_expedicoes_prata":
                page = int(b.get("page") or (query_params.get("page", ["1"])[0]) or 1)
                limit = int(b.get("limit") or (query_params.get("limit", ["25"])[0]) or 25)
                busca = str(b.get("busca") if "busca" in b else (query_params.get("busca", [""])[0])).strip()
                tipo_origem = str(b.get("tipo_origem") or (query_params.get("tipo_origem", ["TODOS"])[0]) or "TODOS").upper()
                periodo = str(b.get("periodo") or (query_params.get("periodo", ["3d"])[0]) or "3d")
                data_inicio = str(b.get("data_inicio") or (query_params.get("data_inicio", [""])[0]) or "")
                data_fim = str(b.get("data_fim") or (query_params.get("data_fim", [""])[0]) or "")
                transportadora = str(b.get("transportadora") or (query_params.get("transportadora", ["TODOS"])[0]) or "TODOS").upper()

                offset = (page - 1) * limit
                where_clauses = ["tp_nf = 1", "tipo_origem IN ('PEDIDO', 'REMESSA')"]
                query_args = []

                if busca:
                    where_clauses.append("(numero_pedido LIKE ? OR numero_remessa LIKE ? OR numero_nf LIKE ? OR cliente_nome LIKE ?)")
                    term = f"%{busca}%"
                    query_args.extend([term, term, term, term])

                if tipo_origem in ("PEDIDO", "REMESSA"):
                    where_clauses.append("tipo_origem = ?")
                    query_args.append(tipo_origem)

                if transportadora and transportadora != "TODOS":
                    where_clauses.append("transportadora_normalizada = ?")
                    query_args.append(transportadora)

                if periodo and periodo != "todos":
                    hoje = datetime.now()
                    dt_start = None
                    if periodo == "hoje":
                        dt_start = datetime(hoje.year, hoje.month, hoje.day, 0, 0, 0)
                    elif periodo == "ontem":
                        ont = hoje - timedelta(days=1)
                        dt_start = datetime(ont.year, ont.month, ont.day, 0, 0, 0)
                    elif periodo == "3d":
                        dt_start = hoje - timedelta(days=3)
                    elif periodo == "7d":
                        dt_start = hoje - timedelta(days=7)
                    elif periodo == "15d":
                        dt_start = hoje - timedelta(days=15)
                    elif periodo == "30d":
                        dt_start = hoje - timedelta(days=30)
                    elif periodo == "personalizado" and data_inicio:
                        try:
                            dt_start = datetime.fromisoformat(data_inicio)
                        except Exception:
                            dt_start = None

                    if dt_start:
                        iso_date = dt_start.strftime("%Y-%m-%d")
                        where_clauses.append("(substr(created_at, 1, 10) >= ? OR (length(data_emissao) = 10 AND (substr(data_emissao, 7, 4) || '-' || substr(data_emissao, 4, 2) || '-' || substr(data_emissao, 1, 2)) >= ?))")
                        query_args.extend([iso_date, iso_date])

                where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

                count_res = execute_turso_query(f"SELECT COUNT(*) FROM omie_expedicoes_prata {where_sql}", query_args)
                total_registros = int(_cell_val(((count_res or {}).get("rows") or [[0]])[0][0]) or 0)

                data_res = execute_turso_query(f"""
                    SELECT id, codigo_nf, numero_nf, serie_nf, chave_nfe, tipo_origem,
                           codigo_pedido_omie, numero_pedido, codigo_remessa_omie, numero_remessa,
                           tp_nf, data_emissao, cliente_nome, cliente_cpf_cnpj, cep, logradouro,
                           numero, complemento, bairro, cidade, uf, origem_endereco, valor_nf,
                           valor_frete, peso_kg, obs_venda, codigo_transportadora,
                           transportadora_normalizada, servico_normalizado, dados_nf_json,
                           dados_pedido_json, dados_remessa_json, enriquecido_em, created_at, updated_at
                    FROM omie_expedicoes_prata
                    {where_sql}
                    ORDER BY CAST(COALESCE(numero_pedido, numero_remessa, '0') AS INTEGER) DESC, data_emissao DESC, id DESC
                    LIMIT ? OFFSET ?
                """, query_args + [limit, offset])

                expedicoes = []
                for r in ((data_res or {}).get("rows") or []):
                    expedicoes.append({
                        "id": _cell_val(r[0]),
                        "codigo_nf": _cell_val(r[1]),
                        "numero_nf": _cell_val(r[2]),
                        "serie_nf": _cell_val(r[3]),
                        "chave_nfe": _cell_val(r[4]),
                        "tipo_origem": _cell_val(r[5]),
                        "codigo_pedido_omie": _cell_val(r[6]),
                        "numero_pedido": _cell_val(r[7]),
                        "codigo_remessa_omie": _cell_val(r[8]),
                        "numero_remessa": _cell_val(r[9]),
                        "tp_nf": _cell_val(r[10]),
                        "data_emissao": _cell_val(r[11]),
                        "cliente_nome": _cell_val(r[12]),
                        "cliente_cpf_cnpj": _cell_val(r[13]),
                        "cep": _cell_val(r[14]),
                        "logradouro": _cell_val(r[15]),
                        "numero": _cell_val(r[16]),
                        "complemento": _cell_val(r[17]),
                        "bairro": _cell_val(r[18]),
                        "cidade": _cell_val(r[19]),
                        "uf": _cell_val(r[20]),
                        "origem_endereco": _cell_val(r[21]),
                        "valor_nf": _cell_val(r[22]),
                        "valor_frete": _cell_val(r[23]),
                        "peso_kg": _cell_val(r[24]),
                        "obs_venda": _cell_val(r[25]),
                        "codigo_transportadora": _cell_val(r[26]),
                        "transportadora_normalizada": _cell_val(r[27]),
                        "servico_normalizado": _cell_val(r[28]),
                        "enriquecido_em": _cell_val(r[32]),
                        "created_at": _cell_val(r[33]),
                        "updated_at": _cell_val(r[34])
                    })

                sync_res = execute_turso_query("""
                    SELECT finalizado_em, quantidade_encontrada, quantidade_nova, quantidade_enriquecida, quantidade_erro, status
                    FROM omie_sync_control
                    ORDER BY id DESC LIMIT 1
                """)
                s_rows = (sync_res or {}).get("rows") or []
                ultima_att = None
                if s_rows:
                    sr = s_rows[0]
                    ultima_att = {
                        "finalizado_em": _cell_val(sr[0]),
                        "encontrados": _cell_val(sr[1]),
                        "novos": _cell_val(sr[2]),
                        "enriquecidos": _cell_val(sr[3]),
                        "erros": _cell_val(sr[4]),
                        "status": _cell_val(sr[5])
                    }

                return 200, {
                    "expedicoes": expedicoes,
                    "total_registros": total_registros,
                    "pagina": page,
                    "total_paginas": max(1, (total_registros + limit - 1) // limit),
                    "limit": limit,
                    "ultima_atualizacao_omie": ultima_att
                }

            # --- ACTION: get_sync_status ---
            if action == "get_sync_status":
                sync_res = execute_turso_query("""
                    SELECT id, iniciado_em, finalizado_em, periodo_inicio, periodo_fim,
                           quantidade_encontrada, quantidade_existente, quantidade_nova,
                           quantidade_enriquecida, quantidade_erro, status
                    FROM omie_sync_control
                    ORDER BY id DESC LIMIT 1
                """)
                rows = (sync_res or {}).get("rows") or []
                if not rows:
                    return 200, {"sync_status": None}
                r = rows[0]
                return 200, {
                    "sync_status": {
                        "id": _cell_val(r[0]),
                        "iniciado_em": _cell_val(r[1]),
                        "finalizado_em": _cell_val(r[2]),
                        "periodo_inicio": _cell_val(r[3]),
                        "periodo_fim": _cell_val(r[4]),
                        "quantidade_encontrada": _cell_val(r[5]),
                        "quantidade_existente": _cell_val(r[6]),
                        "quantidade_nova": _cell_val(r[7]),
                        "quantidade_enriquecida": _cell_val(r[8]),
                        "quantidade_erro": _cell_val(r[9]),
                        "status": _cell_val(r[10])
                    }
                }

            # --- ACTION: check_xml_duplicidade ---
            if action == "check_xml_duplicidade":
                items = b.get("items") or []
                if not items:
                    return 200, {"success": True, "duplicados": []}
                conditions = []
                params = []
                for it in items:
                    sub = []
                    ch = str(it.get("chave_nfe") or "").strip()
                    nf = str(it.get("numero_nf") or "").strip()
                    sr = str(it.get("serie_nf") or "1").strip()
                    if len(ch) == 44:
                        sub.append("chave_nfe = ?")
                        params.append(ch)
                    if nf:
                        sub.append("(numero_nf = ? AND serie_nf = ?)")
                        params.extend([nf, sr])
                    if sub:
                        conditions.append(f"({' OR '.join(sub)})")
                if not conditions:
                    return 200, {"success": True, "duplicados": []}

                sql = f"""
                    SELECT id, pedido, numero_nf, serie_nf, chave_nfe, codigo_objeto, cancelado, status_impressao, created_at
                    FROM prepostagens
                    WHERE {' OR '.join(conditions)}
                """
                res = execute_turso_query(sql, params)
                duplicados = [
                    {
                        "id": _cell_val(r[0]),
                        "pedido": _cell_val(r[1]),
                        "numero_nf": _cell_val(r[2]),
                        "serie_nf": _cell_val(r[3]),
                        "chave_nfe": _cell_val(r[4]),
                        "codigo_objeto": _cell_val(r[5]),
                        "cancelado": int(_cell_val(r[6]) or 0),
                        "status_impressao": _cell_val(r[7]),
                        "created_at": _cell_val(r[8])
                    }
                    for r in ((res or {}).get("rows") or [])
                ]
                return 200, {"success": True, "duplicados": duplicados}

            # --- ACTION: save_prepostagem ---
            if action == "save_prepostagem":
                servico = str(b.get("servico") or "PAC")
                final_cod = str(b.get("codigo_objeto") or "").strip()
                final_id_pre = str(b.get("id_prepostagem") or "").strip()

                if servico in ("RETIRADA_GUARITA", "RETIRADA_ESTOQUE"):
                    if not final_id_pre:
                        return 400, {"error": "Identificador local obrigatorio para retirada."}
                    final_cod = ""

                if servico in ("IMPRESSO_MODICO", "20133") and (not final_cod or final_cod.startswith("OBJ_") or final_cod.startswith("TEMP_")):
                    allocated = alocar_codigo_modico()
                    final_cod = allocated["codigoObjeto"]
                    final_id_pre = allocated["idPrepostagem"]
                elif servico in ("ENTREGA_PROPRIA", "SOUZA", "SOUZA_TRANSLATINO", "TRANSLATINO") and (not final_cod or final_cod.startswith("OBJ_") or final_cod.startswith("TEMP_") or not final_cod.startswith("SZ")):
                    allocated = alocar_codigo_souza()
                    final_cod = allocated["codigoObjeto"]
                    final_id_pre = allocated["idPrepostagem"]

                dados_fiscais = b.get("dados_fiscais_json")
                dados_fiscais_str = json.dumps(dados_fiscais, ensure_ascii=False) if isinstance(dados_fiscais, (dict, list)) else (str(dados_fiscais) if dados_fiscais else None)

                obs_entrega_val = b.get("obs_entrega") or ""
                v_frete = float(b.get("valor_frete") or 0.0)
                t_item = str(b.get("tipo_item") or "PEDIDO")
                desc_avulsa = str(b.get("descricao_avulsa") or "")

                final_cod_db = final_cod if final_cod else None
                sql = """
                    INSERT INTO prepostagens (
                      pedido, numero_nf, serie_nf, chave_nfe, codigo_cliente_omie,
                      id_prepostagem, codigo_objeto, contrato, cartao_postagem, servico,
                      destinatario, cpf_cnpj_destinatario, email_destinatario, telefone_destinatario,
                      logradouro, numero, complemento, bairro, cidade, uf, cep,
                      origem_postagem, status_rotulo, status_impressao, cancelado,
                      dados_fiscais_json, dados_fiscais_atualizado_em, obs_entrega,
                      valor_frete, tipo_item, descricao_avulsa, status_entrega, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PRONTO', 0, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, 'EM_COLETA', CURRENT_TIMESTAMP)
                    ON CONFLICT(id_prepostagem) DO UPDATE SET
                      pedido=excluded.pedido,
                      numero_nf=excluded.numero_nf,
                      serie_nf=excluded.serie_nf,
                      chave_nfe=excluded.chave_nfe,
                      codigo_objeto=excluded.codigo_objeto,
                      servico=excluded.servico,
                      destinatario=excluded.destinatario,
                      cpf_cnpj_destinatario=excluded.cpf_cnpj_destinatario,
                      status_rotulo=excluded.status_rotulo,
                      status_impressao='PRONTO',
                      cancelado=0,
                      obs_entrega=COALESCE(excluded.obs_entrega, prepostagens.obs_entrega),
                      valor_frete=CASE WHEN excluded.valor_frete > 0 THEN excluded.valor_frete ELSE prepostagens.valor_frete END,
                      tipo_item=excluded.tipo_item,
                      descricao_avulsa=COALESCE(excluded.descricao_avulsa, prepostagens.descricao_avulsa),
                      dados_fiscais_json=COALESCE(excluded.dados_fiscais_json, prepostagens.dados_fiscais_json),
                      dados_fiscais_atualizado_em=CASE WHEN excluded.dados_fiscais_json IS NOT NULL THEN CURRENT_TIMESTAMP ELSE prepostagens.dados_fiscais_atualizado_em END,
                      updated_at=CURRENT_TIMESTAMP
                """
                res = execute_turso_query(sql, [
                    b.get("pedido"), b.get("numero_nf"), b.get("serie_nf") or "1", b.get("chave_nfe"), b.get("codigo_cliente_omie"),
                    final_id_pre, final_cod_db, b.get("contrato"), b.get("cartao_postagem"), servico,
                    b.get("destinatario"), b.get("cpf_cnpj_destinatario"), b.get("email_destinatario"), b.get("telefone_destinatario"),
                    b.get("logradouro"), b.get("numero"), b.get("complemento"), b.get("bairro"), b.get("cidade"), b.get("uf"), b.get("cep"),
                    b.get("origem_postagem") or "OMIE", b.get("status_rotulo") or "PENDENTE",
                    dados_fiscais_str, obs_entrega_val, v_frete, t_item, desc_avulsa
                ])
                if servico in ("RETIRADA_GUARITA", "RETIRADA_ESTOQUE"):
                    execute_turso_query(
                        "UPDATE prepostagens SET status_entrega = 'AGUARDANDO_RETIRADA' WHERE id_prepostagem = ?",
                        [final_id_pre]
                    )
                return 200, {"success": True, "codigo_objeto": final_cod, "id_prepostagem": final_id_pre, "result": res}

            # --- ACTION: save_recibo ---
            if action == "save_recibo":
                id_recibo = b.get("id_recibo")
                if not id_recibo:
                    return 400, {"error": "id_recibo obrigatorio"}
                search_res = execute_turso_query(
                    "SELECT id FROM prepostagens WHERE id_prepostagem = ? OR codigo_objeto = ?",
                    [b.get("id_prepostagem") or "", b.get("codigo_objeto") or ""]
                )
                rows = (search_res or {}).get("rows") or []
                if rows:
                    pre_id = _cell_val(rows[0][0])
                    st_rot = b.get("status") or "PROCESSANDO"
                    execute_turso_query(
                        "UPDATE prepostagens SET id_recibo_atual = ?, status_rotulo = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        [id_recibo, st_rot, pre_id]
                    )
                    execute_turso_query("""
                        INSERT INTO rotulo_solicitacoes (prepostagem_id, id_recibo, status, codigo_cws, mensagem_cws)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(id_recibo) DO UPDATE SET
                          status=excluded.status,
                          codigo_cws=excluded.codigo_cws,
                          mensagem_cws=excluded.mensagem_cws
                    """, [pre_id, id_recibo, st_rot, b.get("codigo_cws"), b.get("mensagem_cws")])
                return 200, {"success": True}

            # --- ACTION: update_status_rotulo ---
            if action == "update_status_rotulo":
                id_recibo = b.get("id_recibo")
                if id_recibo:
                    execute_turso_query(
                        "UPDATE rotulo_solicitacoes SET status = ?, codigo_cws = ?, mensagem_cws = ?, concluido_at = CURRENT_TIMESTAMP WHERE id_recibo = ?",
                        [b.get("status_rotulo"), b.get("codigo_cws"), b.get("mensagem_cws"), id_recibo]
                    )
                    execute_turso_query(
                        "UPDATE prepostagens SET status_rotulo = ?, updated_at = CURRENT_TIMESTAMP WHERE id_recibo_atual = ?",
                        [b.get("status_rotulo"), id_recibo]
                    )
                return 200, {"success": True}

            # --- ACTION: register_impressao ---
            if action == "register_impressao":
                execute_turso_query("""
                    UPDATE prepostagens 
                    SET status_impressao = 'ARQUIVADO',
                        data_impressao = CURRENT_TIMESTAMP,
                        usuario_impressao = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE (id_prepostagem = ? AND id_prepostagem != '') OR (codigo_objeto = ? AND codigo_objeto != '')
                """, [b.get("usuario_impressao") or "OPERADOR", b.get("id_prepostagem") or "", b.get("codigo_objeto") or ""])
                return 200, {"success": True}

            # --- ACTION: cancel_prepostagem ---
            if action == "cancel_prepostagem":
                resp_cws = b.get("resposta_cws")
                resp_str = json.dumps(resp_cws, ensure_ascii=False) if isinstance(resp_cws, (dict, list)) else str(resp_cws or "")
                id_reg = b.get("id_registro") or b.get("idRegistro") or b.get("id") or 0
                try:
                    id_reg = int(id_reg)
                except Exception:
                    id_reg = 0
                target_id_pre = str(b.get("id_prepostagem") or "").strip()
                target_obj = str(b.get("codigo_objeto") or "").strip()
                ped = str(b.get("pedido") or "").strip()
                num_nf = str(b.get("numero_nf") or b.get("numeroNf") or "").strip()

                execute_turso_query("""
                    UPDATE prepostagens 
                    SET cancelado = 1,
                        status_rotulo = ?,
                        status_impressao = 'CANCELADO',
                        data_cancelamento = CURRENT_TIMESTAMP,
                        resposta_cancelamento_cws = ?,
                        usuario_cancelamento = ?,
                        codigo_objeto = CASE 
                            WHEN codigo_objeto LIKE 'SZ%' OR codigo_objeto LIKE 'YD%' THEN codigo_objeto || '_CANC_' || id
                            ELSE codigo_objeto 
                        END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE (id = ? AND ? > 0)
                       OR (id_prepostagem = ? AND id_prepostagem != '') 
                       OR (codigo_objeto = ? AND codigo_objeto != '')
                       OR (pedido = ? AND pedido != '' AND numero_nf = ? AND numero_nf != '')
                """, [
                    b.get("status_rotulo") or "CANCELADO",
                    resp_str,
                    b.get("usuario_cancelamento") or "OPERADOR",
                    id_reg, id_reg,
                    target_id_pre,
                    target_obj,
                    ped, num_nf
                ])
                return 200, {"success": True}

            # --- ACTION: cancel_modico ---
            if action == "cancel_modico":
                cod_obj = str(b.get("codigo_objeto") or "")
                id_pre = str(b.get("id_prepostagem") or "")
                usu_canc = str(b.get("usuario_cancelamento") or "OPERADOR")

                if not cod_obj and not id_pre:
                    return 400, {"error": "codigo_objeto ou id_prepostagem obrigatorio."}

                q_pre = execute_turso_query(
                    "SELECT id, codigo_objeto, id_prepostagem, servico, cancelado FROM prepostagens "
                    "WHERE (codigo_objeto = ? AND codigo_objeto != '') OR (id_prepostagem = ? AND id_prepostagem != '') LIMIT 1",
                    [cod_obj, id_pre]
                )
                rows_pre = (q_pre or {}).get("rows") or []
                if not rows_pre:
                    return 404, {"error": "Pre-postagem nao encontrada no Turso."}

                rp = rows_pre[0]
                pre_id = int(_cell_val(rp[0]))
                real_cod = str(_cell_val(rp[1]) or cod_obj)
                serv_item = str(_cell_val(rp[3]) or "").upper()
                ja_canc = int(_cell_val(rp[4]) or 0)

                if ja_canc == 1:
                    return 200, {"sucesso": True, "mensagem": "Pre-postagem ja estava cancelada.", "codigo_objeto": real_cod, "devolvido_range": False}

                q_rast = execute_turso_query(
                    "SELECT status_atual, descricao_status, eventos_json FROM objeto_rastreamento WHERE codigo_objeto = ? LIMIT 1",
                    [real_cod]
                )
                rows_rast = (q_rast or {}).get("rows") or []
                tem_mov = False
                st_atual = ""
                if rows_rast:
                    rr = rows_rast[0]
                    st_atual = str(_cell_val(rr[0]) or "").upper()
                    desc_r = str(_cell_val(rr[1]) or "").upper()
                    ev_j = str(_cell_val(rr[2]) or "")
                    termos = ["POSTADO", "TRANSITO", "TRÂNSITO", "ENCAMINHADO", "ENTREGA", "ENTREGUE", "DEVOLVIDO", "SAIU"]
                    if any(t in st_atual or t in desc_r for t in termos) or (ev_j and ev_j not in ("[]", "null")):
                        tem_mov = True

                if tem_mov:
                    execute_turso_query("""
                        UPDATE prepostagens 
                        SET cancelado = 1,
                            status_rotulo = 'CANCELADO',
                            data_cancelamento = CURRENT_TIMESTAMP,
                            resposta_cancelamento_cws = ?,
                            usuario_cancelamento = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, [f"NAO_REUTILIZAVEL: Movimentacao ({st_atual})", usu_canc, pre_id])
                    return 200, {
                        "sucesso": True,
                        "codigo_objeto": real_cod,
                        "devolvido_range": False,
                        "reusavel": False,
                        "mensagem": f"Cancelado internamente. Codigo {real_cod} NAO devolvido por possuir movimentacao.",
                        "cws_chamadas": 0
                    }
                else:
                    execute_turso_query("""
                        UPDATE prepostagens 
                        SET cancelado = 1,
                            status_rotulo = 'CANCELADO',
                            data_cancelamento = CURRENT_TIMESTAMP,
                            resposta_cancelamento_cws = 'CANCELADO_INTERNAMENTE_DEVOLVIDO',
                            usuario_cancelamento = ?,
                            codigo_objeto = codigo_objeto || '_CANC_' || id,
                            rotulo_storage_key = NULL,
                            pdf_combinado_storage_key = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, [usu_canc, pre_id])
                    res_dev = devolver_codigo_modico(real_cod)
                    return 200, {
                        "sucesso": True,
                        "codigo_objeto": real_cod,
                        "devolvido_range": res_dev["devolvido"],
                        "reusavel": res_dev["reusavel"],
                        "mensagem": f"Impresso Modico cancelado internamente. {res_dev['mensagem']}",
                        "cws_chamadas": 0
                    }

            # --- ACTION: update_dados_fiscais ---
            if action == "update_dados_fiscais":
                chave_nfe = str(b.get("chave_nfe") or "")
                if len(chave_nfe) != 44:
                    return 400, {"error": "Chave NF-e invalida"}
                df_json = b.get("dados_fiscais_json")
                df_str = df_json if isinstance(df_json, str) else json.dumps(df_json, ensure_ascii=False)
                execute_turso_query("""
                    UPDATE prepostagens 
                    SET chave_nfe = ?, dados_fiscais_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id_prepostagem = ? OR (numero_nf = ? AND (chave_nfe IS NULL OR chave_nfe = '' OR chave_nfe = 'CHAVE_NFE_AUSENTE'))
                """, [chave_nfe, df_str, b.get("id_prepostagem") or "", b.get("numero_nf") or ""])
                return 200, {"status": "success", "chave_nfe": chave_nfe}

            # --- ACTION: update_frete_prepostagem ---
            if action == "update_frete_prepostagem":
                id_target = b.get("id")
                v_frete = float(b.get("valor_frete") or 0.0)
                execute_turso_query("UPDATE prepostagens SET valor_frete = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [v_frete, id_target])
                return 200, {"success": True, "id": id_target, "valor_frete": v_frete}

            # --- ACTION: update_status_entrega ---
            if action == "update_status_entrega":
                ids = b.get("ids") or ([b.get("id")] if b.get("id") else [])
                novo_status = str(b.get("status") or "EM_TRANSPORTE").upper()
                rec_nome = str(b.get("recebedor_nome") or "")
                rec_doc = str(b.get("recebedor_doc") or "")
                rec_ass = str(b.get("assinatura_base64") or "")
                for target_id in ids:
                    execute_turso_query("""
                        UPDATE lista_postagem_itens 
                        SET status_entrega = ?, 
                            recebedor_nome = CASE WHEN ? != '' THEN ? ELSE recebedor_nome END,
                            recebedor_doc = CASE WHEN ? != '' THEN ? ELSE recebedor_doc END,
                            assinatura_base64 = CASE WHEN ? != '' THEN ? ELSE assinatura_base64 END,
                            data_entrega = CASE WHEN ? = 'FINALIZADO' THEN CURRENT_TIMESTAMP ELSE data_entrega END
                        WHERE id = ? OR prepostagem_id = ?
                    """, [novo_status, rec_nome, rec_nome, rec_doc, rec_doc, rec_ass, rec_ass, novo_status, target_id, target_id])
                    execute_turso_query("""
                        UPDATE prepostagens 
                        SET status_entrega = ?, updated_at = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    """, [novo_status, target_id])
                return 200, {"success": True, "status": novo_status, "count": len(ids)}

            # --- ACTION: list_prepostagens ---
            if action == "list_prepostagens":
                res = execute_turso_query("""
                    SELECT id, pedido, numero_nf, chave_nfe, id_prepostagem, codigo_objeto, id_recibo_atual,
                           servico, destinatario, cidade, uf, cep, status_rotulo, status_impressao, cancelado, created_at,
                           dados_fiscais_json, cpf_cnpj_destinatario, logradouro, numero, complemento, bairro, obs_entrega,
                           valor_frete, status_entrega, tipo_item, descricao_avulsa
                    FROM prepostagens
                    WHERE cancelado = 0
                    ORDER BY id DESC LIMIT 150
                """)
                prepostagens = []
                for r in ((res or {}).get("rows") or []):
                    prepostagens.append({
                        "id": _cell_val(r[0]),
                        "pedido": _cell_val(r[1]),
                        "numero_nf": _cell_val(r[2]),
                        "chave_nfe": _cell_val(r[3]),
                        "id_prepostagem": _cell_val(r[4]),
                        "codigo_objeto": _cell_val(r[5]),
                        "id_recibo_atual": _cell_val(r[6]),
                        "servico": _cell_val(r[7]),
                        "destinatario": _cell_val(r[8]),
                        "cidade": _cell_val(r[9]),
                        "uf": _cell_val(r[10]),
                        "cep": _cell_val(r[11]),
                        "status_rotulo": _cell_val(r[12]),
                        "status_impressao": _cell_val(r[13]),
                        "cancelado": _cell_val(r[14]),
                        "created_at": _cell_val(r[15]),
                        "dados_fiscais_json": _cell_val(r[16]),
                        "cpf_cnpj_destinatario": _cell_val(r[17]),
                        "logradouro": _cell_val(r[18]),
                        "numero": _cell_val(r[19]),
                        "complemento": _cell_val(r[20]) if len(r) > 20 else "",
                        "bairro": _cell_val(r[21]) if len(r) > 21 else "",
                        "obs_entrega": _cell_val(r[22]) if len(r) > 22 else "",
                        "valor_frete": float(_cell_val(r[23]) or 0.0) if len(r) > 23 else 0.0,
                        "status_entrega": _cell_val(r[24]) if len(r) > 24 else "EM_COLETA",
                        "tipo_item": _cell_val(r[25]) if len(r) > 25 else "PEDIDO",
                        "descricao_avulsa": _cell_val(r[26]) if len(r) > 26 else ""
                    })
                return 200, {"prepostagens": prepostagens}

            # --- ACTION: save_range_modico (para Aba 8) ---
            if action == "save_range_modico":
                sigla = str(b.get("sigla") or "YD").upper().strip()
                num_ini = int(str(b.get("num_inicio") or "0").strip())
                num_fim = int(str(b.get("num_fim") or "0").strip())
                execute_turso_query("""
                    INSERT INTO modico_ranges (servico, sigla, num_inicio, num_fim, num_atual, sufixo, status)
                    VALUES ('IMPRESSO_MODICO', ?, ?, ?, ?, 'BR', 'ATIVO')
                """, [sigla, num_ini, num_fim, num_ini])
                return 200, {"success": True}

            # --- DEFAULT: Retorna modico_ranges e status Turso ---
            range_res = execute_turso_query("SELECT id, servico, sigla, num_inicio, num_fim, num_atual, sufixo, status FROM modico_ranges ORDER BY id DESC")
            ranges = [
                {
                    "id": _cell_val(r[0]), "servico": _cell_val(r[1]), "sigla": _cell_val(r[2]),
                    "num_inicio": _cell_val(r[3]), "num_fim": _cell_val(r[4]), "num_atual": _cell_val(r[5]),
                    "sufixo": _cell_val(r[6]), "status": _cell_val(r[7])
                }
                for r in ((range_res or {}).get("rows") or [])
            ]
            return 200, {"status": "ok", "turso_conectado": True, "ranges": ranges}

        except Exception as e:
            logger.exception("Erro em handle_turso_db:")
            return 500, {"error": str(e)}

    # =========================================================================
    # 2. HANDLER: omie-sync-bronze-prata
    # =========================================================================
    @staticmethod
    def _sincronizar_remessas_faturadas_recentes(data_inicio: str) -> Dict[str, Any]:
        """Importa somente remessas faturadas ainda ausentes, das paginas mais recentes do Omie."""
        from omie_client import OmieClient

        metricas = {"encontradas": 0, "novas": 0, "consultas": 0, "erros": 0, "aviso": ""}
        client = OmieClient("MATRIZ")
        deadline = time.monotonic() + 25

        def call_omie(endpoint: str, call: str, params: List[Dict[str, Any]]) -> Dict[str, Any]:
            remaining = deadline - time.monotonic()
            if remaining <= 0.5:
                return {"cCodStatus": "LOCAL_BUDGET", "faultstring": "Limite local da etapa de remessas atingido."}
            return client.executar(endpoint, call, params, timeout=max(1, min(10, int(remaining))), retries=1)

        try:
            inicio = datetime.strptime(data_inicio, "%d/%m/%Y").date()
        except (TypeError, ValueError):
            inicio = datetime.now().date()

        try:
            existing_res = execute_turso_query("""
                SELECT codigo_remessa_omie, numero_remessa, chave_nfe, tipo_origem
                FROM omie_expedicoes_prata
            """)
            existing_ids, existing_numbers, existing_keys = set(), set(), set()
            max_code = 0
            for row in ((existing_res or {}).get("rows") or []):
                code = str(_cell_val(row[0]) or "").strip()
                number = str(_cell_val(row[1]) or "").strip()
                invoice_key = str(_cell_val(row[2]) or "").strip()
                is_remittance = str(_cell_val(row[3]) or "").upper() == "REMESSA"
                if code and is_remittance:
                    existing_ids.add(code)
                    if code.isdigit():
                        max_code = max(max_code, int(code))
                if number and is_remittance:
                    existing_numbers.add(number)
                if invoice_key:
                    existing_keys.add(invoice_key)

            def response_list(response: Dict[str, Any]) -> List[Dict[str, Any]]:
                return response.get("remessas") or response.get("remessas_lista") or []

            def date_from_remessa(remessa: Dict[str, Any]):
                cab = remessa.get("cabec") or {}
                raw = cab.get("dDtEmissao") or cab.get("dPrevisao") or remessa.get("dDtEmissao") or ""
                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(str(raw)[:19], fmt).date()
                    except ValueError:
                        continue
                return None

            first_page = call_omie(
                "produtos/remessa/", "ListarRemessas",
                [{"nPagina": 1, "nRegistrosPorPagina": 50}]
            )
            if first_page.get("cCodStatus") == "LOCAL_BUDGET":
                metricas["aviso"] = first_page["faultstring"]
                return metricas
            if first_page.get("faultstring") or first_page.get("cCodStatus") == "ERRO_CONEXAO":
                raise RuntimeError(first_page.get("faultstring") or "Falha ListarRemessas")

            total_pages = int(first_page.get("nTotalPaginas") or first_page.get("total_de_paginas") or 1)
            newest_page = total_pages
            # O projeto já trata as páginas finais do ListarRemessas como as mais recentes.
            pages_to_scan = min(total_pages, 20)
            candidates = []
            for page_number in range(newest_page, newest_page - pages_to_scan, -1):
                page_data = first_page if total_pages == 1 else call_omie(
                    "produtos/remessa/", "ListarRemessas",
                    [{"nPagina": page_number, "nRegistrosPorPagina": 50}]
                )
                if page_data.get("cCodStatus") == "LOCAL_BUDGET":
                    metricas["aviso"] = page_data["faultstring"]
                    break
                if page_data.get("faultstring") or page_data.get("cCodStatus") == "ERRO_CONEXAO":
                    metricas["erros"] += 1
                    continue

                remessas = response_list(page_data)
                if not remessas:
                    break
                page_dates = []
                page_codes = []
                for listed in remessas:
                    cab = listed.get("cabec") or {}
                    rem_code = str(cab.get("nCodRem") or "").strip()
                    rem_number = str(cab.get("cNumeroRemessa") or "").strip()
                    invoice_key = str(cab.get("cChaveNFe") or "").strip()
                    rem_date = date_from_remessa(listed)
                    if rem_date:
                        page_dates.append(rem_date)
                    if rem_code.isdigit():
                        page_codes.append(int(rem_code))
                    if max_code:
                        if not rem_code.isdigit() or int(rem_code) <= max_code:
                            continue
                    elif not rem_date or rem_date < inicio:
                        continue
                    if str(cab.get("faturada") or "").strip().upper() != "S":
                        continue
                    if str(cab.get("cCancelado") or "N").strip().upper() == "S":
                        continue
                    metricas["encontradas"] += 1
                    if (rem_code and rem_code in existing_ids) or (rem_number and rem_number in existing_numbers) or (invoice_key and invoice_key in existing_keys):
                        continue
                    candidates.append((rem_code, rem_number, listed))

                if max_code and page_codes and max(page_codes) <= max_code:
                    break
                if not max_code and page_dates and max(page_dates) < inicio:
                    break

            candidates.sort(key=lambda entry: int(entry[0]) if entry[0].isdigit() else 0)
            for rem_code, listed_number, listed in candidates:
                if not rem_code.isdigit():
                    metricas["erros"] += 1
                    continue
                try:
                    metricas["consultas"] += 1
                    detail = call_omie(
                        "produtos/remessa/", "ConsultarRemessa",
                        [{"nCodRem": int(rem_code)}]
                    )
                    if detail.get("cCodStatus") == "LOCAL_BUDGET":
                        metricas["aviso"] = detail["faultstring"]
                        break
                    if detail.get("faultstring") or not detail.get("cabec"):
                        metricas["erros"] += 1
                        continue

                    cab = detail.get("cabec") or {}
                    listed_cab = (listed.get("cabec") or {})
                    cab = {**listed_cab, **cab}
                    if str(cab.get("faturada") or listed_cab.get("faturada") or "").strip().upper() != "S":
                        continue
                    rem_number = str(cab.get("cNumeroRemessa") or listed_number or rem_code)
                    invoice_key = str(cab.get("cChaveNFe") or (detail.get("compl") or {}).get("cChaveNFe") or "").strip()
                    if rem_code in existing_ids or rem_number in existing_numbers or (invoice_key and invoice_key in existing_keys):
                        continue

                    client_name = str(cab.get("cNomeCli") or "CLIENTE OMIE")
                    client_doc = ""
                    cep = logradouro = complemento = bairro = cidade = uf = ""
                    numero = "S/N"
                    orig_endereco = "CADASTRO"
                    client_code = int(cab.get("nCodCli") or 0)
                    if client_code:
                        client_data = call_omie(
                            "geral/clientes/", "ConsultarCliente",
                            [{"codigo_cliente_omie": client_code}]
                        )
                        if client_data.get("cCodStatus") == "LOCAL_BUDGET":
                            metricas["aviso"] = client_data["faultstring"]
                            break
                        if not client_data.get("faultstring"):
                            client_name = str(client_data.get("razao_social") or client_data.get("nome_fantasia") or client_name)
                            client_doc = re.sub(r"\D", "", str(client_data.get("cnpj_cpf") or ""))
                            delivery = client_data.get("enderecoEntrega") or {}
                            if delivery.get("entCEP") and delivery.get("entEndereco"):
                                cep = re.sub(r"\D", "", str(delivery.get("entCEP") or ""))
                                logradouro = str(delivery.get("entEndereco") or "")
                                numero = str(delivery.get("entNumero") or "S/N")
                                complemento = str(delivery.get("entComplemento") or "")
                                bairro = str(delivery.get("entBairro") or "")
                                cidade = str(delivery.get("entCidade") or "").split("(")[0].strip()
                                uf = str(delivery.get("entEstado") or "")
                                orig_endereco = "ENTREGA"
                            else:
                                cep = re.sub(r"\D", "", str(client_data.get("cep") or ""))
                                logradouro = str(client_data.get("endereco") or "")
                                numero = str(client_data.get("endereco_numero") or "S/N")
                                complemento = str(client_data.get("complemento") or "")
                                bairro = str(client_data.get("bairro") or "")
                                cidade = str(client_data.get("cidade") or "").split("(")[0].strip()
                                uf = str(client_data.get("estado") or "")

                    freight = detail.get("frete") or listed.get("frete") or {}
                    inf = detail.get("infAdic") or listed.get("infAdic") or {}
                    obs = detail.get("obs") or listed.get("obs") or {}
                    obs_parts = [str(value).strip() for value in (inf.get("cDadosAdic"), obs.get("cObs")) if value]
                    obs_venda = " | ".join(dict.fromkeys(obs_parts))
                    carrier_code = str(freight.get("nCodTransp") or cab.get("nCodTransp") or "").strip()
                    carrier_name = str(freight.get("cNomeTransp") or freight.get("xNome") or "")
                    classification = classificar_forma_envio_prata(obs_venda or carrier_name, carrier_code, cidade)
                    raw_remessa = json.dumps(detail, ensure_ascii=False)
                    issued = str(cab.get("dDtEmissao") or cab.get("dPrevisao") or "")
                    invoice_number = str(cab.get("cNumeroNF") or cab.get("nNF") or "")
                    invoice_code = str(cab.get("nIdNF") or "")
                    total_value = float(cab.get("nValorTotal") or cab.get("nTotRem") or 0)
                    freight_value = float(freight.get("nValorFrete") or freight.get("nVlrFrete") or 0)
                    execute_turso_query("""
                        INSERT INTO omie_expedicoes_prata (
                          codigo_nf, numero_nf, serie_nf, chave_nfe, tipo_origem,
                          codigo_pedido_omie, numero_pedido, codigo_remessa_omie, numero_remessa,
                          tp_nf, data_emissao, cliente_nome, cliente_cpf_cnpj, cep, logradouro, numero,
                          complemento, bairro, cidade, uf, origem_endereco, valor_nf, valor_frete,
                          peso_kg, obs_venda, codigo_transportadora, transportadora_normalizada,
                          servico_normalizado, dados_nf_json, dados_pedido_json, dados_remessa_json,
                          enriquecido_em, updated_at
                        ) VALUES (?, ?, ?, ?, 'REMESSA', NULL, NULL, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.5, ?, ?, ?, ?, ?, NULL, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT(chave_nfe) DO NOTHING
                    """, [
                        invoice_code, invoice_number, str(cab.get("serie") or "1"), invoice_key or None,
                        int(rem_code), rem_number, issued, client_name, client_doc, cep, logradouro, numero,
                        complemento, bairro, cidade, uf, orig_endereco, total_value, freight_value,
                        obs_venda, carrier_code, classification["grupo"], classification["servico"],
                        json.dumps(detail.get("nf") or {}, ensure_ascii=False), raw_remessa
                    ])
                    existing_ids.add(rem_code)
                    existing_numbers.add(rem_number)
                    max_code = max(max_code, int(rem_code))
                    if invoice_key:
                        existing_keys.add(invoice_key)
                    metricas["novas"] += 1
                except Exception:
                    metricas["erros"] += 1
                    logger.exception("Falha ao importar remessa faturada recente %s", rem_code)

            if not metricas["aviso"] and total_pages > 20 and pages_to_scan == 20:
                metricas["aviso"] = "A busca de remessas recentes foi limitada às últimas 20 páginas."
        except Exception as exc:
            metricas["erros"] += 1
            metricas["aviso"] = str(exc)
            logger.exception("Falha na busca incremental de remessas faturadas")
        return metricas

    @staticmethod
    def handle_omie_sync_bronze_prata(query_params: Dict[str, List[str]], body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        b = body or {}
        n_dias = int(b.get("dias") or (query_params.get("dias", ["3"])[0]) or 3)
        app_key, app_secret = _get_omie_creds()
        if not app_key or not app_secret:
            return 500, {"sucesso": False, "erro": "Credenciais Omie nao configuradas no .env"}

        sync_id = None
        qtd_encontrada = 0
        qtd_existente = 0
        qtd_nova = 0
        qtd_enriquecida = 0
        qtd_erro = 0
        qtd_ped = 0
        qtd_rem = 0
        remessas_metricas = {"encontradas": 0, "novas": 0, "consultas": 0, "erros": 0, "aviso": ""}

        try:
            hoje = datetime.now()
            # Se n_dias <= 1, filtra estritamente hoje (para testes e fechamento diário)
            if n_dias <= 1:
                d_ini_str = hoje.strftime("%d/%m/%Y")
            else:
                dt_ini = hoje - timedelta(days=n_dias)
                d_ini_str = dt_ini.strftime("%d/%m/%Y")
            d_fim_str = hoje.strftime("%d/%m/%Y")

            sync_res = execute_turso_query("""
                INSERT INTO omie_sync_control (iniciado_em, periodo_inicio, periodo_fim, status)
                VALUES (CURRENT_TIMESTAMP, ?, ?, 'EM_ANDAMENTO')
                RETURNING id
            """, [d_ini_str, d_fim_str])
            rows_s = (sync_res or {}).get("rows") or []
            if rows_s:
                sync_id = int(_cell_val(rows_s[0][0]) or 0)

            # Importa apenas remessas faturadas recentes, sem varrer o histórico completo.
            remessas_metricas = CorreiosHubService._sincronizar_remessas_faturadas_recentes(d_ini_str)
            qtd_rem += int(remessas_metricas.get("consultas") or 0)

            # Paginar para trazer todas as NFs do período informado
            lista_nf = []
            pag_atual = 1
            tot_pags = 1

            while pag_atual <= tot_pags:
                try:
                    omie_res = requests.post(
                        "https://app.omie.com.br/api/v1/produtos/nfconsultar/",
                        json={
                            "call": "ListarNF",
                            "app_key": app_key,
                            "app_secret": app_secret,
                            "param": [{
                                "pagina": pag_atual,
                                "registros_por_pagina": 100,
                                "dEmiInicial": d_ini_str,
                                "dEmiFinal": d_fim_str
                            }]
                        },
                        timeout=25
                    )
                    omie_data = omie_res.json()
                    tot_pags = int(omie_data.get("total_de_paginas") or 1)
                    nfs_pag = omie_data.get("nfCadastro") or []
                    lista_nf.extend(nfs_pag)
                    pag_atual += 1
                    if pag_atual <= tot_pags:
                        time.sleep(0.08)
                except Exception as e_pag:
                    logger.error(f"[SYNC] Erro ao paginar ListarNF pag {pag_atual}: {e_pag}")
                    break

            qtd_encontrada = len(lista_nf)

            bronze_check = execute_turso_query("SELECT codigo_nf, chave_nfe FROM omie_nf_bronze")
            existing_keys = set()
            for r in ((bronze_check or {}).get("rows") or []):
                if _cell_val(r[0]):
                    existing_keys.add(str(_cell_val(r[0])))
                if _cell_val(r[1]):
                    existing_keys.add(str(_cell_val(r[1])))

            for nf in lista_nf:
                ide = nf.get("ide") or {}
                compl = nf.get("compl") or {}
                cod_nf = str(ide.get("nIdNF") or compl.get("nIdNF") or "")
                num_nf = str(ide.get("nNF") or "")
                serie_nf = str(ide.get("serie") or "1")
                chave_nfe = str(compl.get("cChaveNFe") or "")
                tp_nf_str = str(ide.get("tpNF") if ide.get("tpNF") is not None else "1").strip()
                tp_nf = 0 if tp_nf_str == "0" else 1
                data_emi = str(ide.get("dEmi") or "")
                cod_ped = int(compl.get("nIdPedido") or 0)

                # Ignorar Notas Fiscais de Entrada (tpNF == 0) ou notas com nIdReceb (Recebimento de Fornecedor)
                if tp_nf == 0 or int(compl.get("nIdReceb") or 0) > 0:
                    continue

                if not cod_nf and not chave_nfe:
                    continue
                if (cod_nf and cod_nf in existing_keys) or (chave_nfe and chave_nfe in existing_keys):
                    qtd_existente += 1
                else:
                    qtd_nova += 1
                    if cod_nf:
                        existing_keys.add(cod_nf)
                    if chave_nfe:
                        existing_keys.add(chave_nfe)
                    execute_turso_query("""
                        INSERT INTO omie_nf_bronze (
                          codigo_nf, numero_nf, serie_nf, chave_nfe, tp_nf, data_emissao,
                          codigo_pedido_omie, listar_nf_json, status_enriquecimento
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDENTE')
                    """, [cod_nf, num_nf, serie_nf, chave_nfe or None, tp_nf, data_emi, cod_ped, json.dumps(nf, ensure_ascii=False)])

            res_pending = execute_turso_query("""
                SELECT id, codigo_nf, numero_nf, serie_nf, chave_nfe, tp_nf, data_emissao,
                       codigo_pedido_omie, listar_nf_json
                FROM omie_nf_bronze
                WHERE status_enriquecimento != 'PRONTO'
                ORDER BY id ASC
                LIMIT 100
            """)
            for r in ((res_pending or {}).get("rows") or []):
                bronze_id = int(_cell_val(r[0]))
                cod_nf = str(_cell_val(r[1]) or "")
                num_nf = str(_cell_val(r[2]) or "")
                serie_nf = str(_cell_val(r[3]) or "1")
                chave_nfe = str(_cell_val(r[4]) or "")
                tp_nf = int(_cell_val(r[5]) or 1)
                data_emi = str(_cell_val(r[6]) or "")
                cod_ped = int(_cell_val(r[7]) or 0)
                raw_json = str(_cell_val(r[8]) or "{}")

                try:
                    nf_parsed = json.loads(raw_json)
                except Exception:
                    nf_parsed = {}

                dest = nf_parsed.get("nfDestInt") or {}
                transp = nf_parsed.get("transp") or {}
                total = nf_parsed.get("total") or {}
                compl = nf_parsed.get("compl") or {}
                ide_parsed = nf_parsed.get("ide") or {}

                tp_nf_real = 0 if str(ide_parsed.get("tpNF") if ide_parsed.get("tpNF") is not None else tp_nf).strip() == "0" else 1
                if tp_nf_real == 0 or int(compl.get("nIdReceb") or 0) > 0:
                    execute_turso_query("UPDATE omie_nf_bronze SET status_enriquecimento = 'IGNORADO_ENTRADA', tp_nf = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [bronze_id])
                    continue

                cli_nome = dest.get("cRazao") or "CLIENTE OMIE"
                cli_cpf = re.sub(r"\D", "", str(dest.get("cnpj_cpf") or ""))
                cep_fin = re.sub(r"\D", "", str(dest.get("cep") or ""))
                logr_fin = dest.get("logradouro") or ""
                num_fin = dest.get("numero") or "S/N"
                compl_fin = dest.get("complemento") or ""
                bairro_fin = dest.get("bairro") or ""
                cid_fin = str(dest.get("cidade") or "").split("(")[0].strip()
                uf_fin = dest.get("uf") or ""
                orig_end = "ENTREGA" if (cep_fin and logr_fin) else "CADASTRO"

                # Buscar Nome Fantasia (Livrarias) e Endereço Completo via ConsultarCliente
                n_cod_cli = int(dest.get("nCodCli") or 0)
                if n_cod_cli > 0:
                    try:
                        time.sleep(0.05)
                        r_cli = requests.post(
                            "https://app.omie.com.br/api/v1/geral/clientes/",
                            json={
                                "call": "ConsultarCliente",
                                "app_key": app_key,
                                "app_secret": app_secret,
                                "param": [{"codigo_cliente_omie": n_cod_cli}]
                            },
                            timeout=10
                        )
                        d_cli = r_cli.json()
                        fantasia = (d_cli.get("nome_fantasia") or "").strip()
                        razao = (d_cli.get("razao_social") or cli_nome).strip()
                        if fantasia and fantasia.upper() not in razao.upper():
                            cli_nome = f"{razao} ({fantasia})"
                        elif razao:
                            cli_nome = razao

                        if not cli_cpf and d_cli.get("cnpj_cpf"):
                            cli_cpf = re.sub(r"\D", "", str(d_cli.get("cnpj_cpf") or ""))

                        end_ent = d_cli.get("enderecoEntrega") or {}
                        if end_ent.get("entCEP") and end_ent.get("entEndereco"):
                            cep_fin = re.sub(r"\D", "", str(end_ent.get("entCEP") or ""))
                            logr_fin = str(end_ent.get("entEndereco") or "").strip()
                            num_fin = str(end_ent.get("entNumero") or "S/N").strip()
                            compl_fin = str(end_ent.get("entComplemento") or "").strip()
                            bairro_fin = str(end_ent.get("entBairro") or "").strip()
                            cid_fin = str(end_ent.get("entCidade") or "").split("(")[0].strip()
                            uf_fin = str(end_ent.get("entEstado") or "").strip()
                            orig_end = "ENTREGA"
                        else:
                            if not cep_fin:
                                cep_fin = re.sub(r"\D", "", str(d_cli.get("cep") or ""))
                            if not logr_fin:
                                logr_fin = str(d_cli.get("endereco") or "").strip()
                            if not num_fin or num_fin == "S/N":
                                num_fin = str(d_cli.get("endereco_numero") or "S/N").strip()
                            if not compl_fin:
                                compl_fin = str(d_cli.get("complemento") or "").strip()
                            if not bairro_fin:
                                bairro_fin = str(d_cli.get("bairro") or "").strip()
                            if not cid_fin:
                                cid_fin = str(d_cli.get("cidade") or "").split("(")[0].strip()
                            if not uf_fin:
                                uf_fin = str(d_cli.get("estado") or "").strip()
                    except Exception:
                        pass

                icms_tot = total.get("ICMSTot") or {}
                val_nf = float(icms_tot.get("vNF") or total.get("vNF") or 0)
                val_frete = float(icms_tot.get("vFrete") or total.get("vFrete") or 0)

                tipo_orig = "ORIGEM_NAO_IDENTIFICADA"
                num_ped_real = None
                cod_rem_omie = None
                num_rem_real = None
                obs_venda = ""
                cod_transp = str(transp.get("codigo_transportadora") or "").strip()
                transp_nome = transp.get("xNome") or ""
                peso_kg = 0.5
                dados_ped_json = None
                dados_rem_json = None

                # ATENÇÃO: nIdReceb é Recebimento de Mercadorias (Entrada), NÃO Remessa de Saída!
                cod_rem_found = compl.get("nIdRemessa") or 0
                tem_rem = (int(cod_rem_found or 0) > 0) or bool(compl.get("cNumRemessa")) or bool(compl.get("nNumeroRemessa"))

                if cod_ped > 0:
                    tipo_orig = "PEDIDO"
                    try:
                        time.sleep(0.08)
                        qtd_ped += 1
                        r_ped = requests.post(
                            "https://app.omie.com.br/api/v1/produtos/pedido/",
                            json={
                                "call": "ConsultarPedido",
                                "app_key": app_key,
                                "app_secret": app_secret,
                                "param": [{"codigo_pedido": cod_ped}]
                            },
                            timeout=15
                        )
                        d_ped = r_ped.json()
                        # Se não encontrar como pedido, pode ser uma Remessa cujo nIdPedido guardou o nCodRem
                        if "faultstring" in d_ped or "faultcode" in d_ped:
                            try:
                                r_rem_chk = requests.post(
                                    "https://app.omie.com.br/api/v1/produtos/remessa/",
                                    json={
                                        "call": "ConsultarRemessa",
                                        "app_key": app_key,
                                        "app_secret": app_secret,
                                        "param": [{"nCodRem": cod_ped}]
                                    },
                                    timeout=15
                                )
                                d_rem_chk = r_rem_chk.json()
                                cab_chk = d_rem_chk.get("cabec") or {}
                                if cab_chk:
                                    tipo_orig = "REMESSA"
                                    cod_rem_omie = cod_ped
                                    num_rem_real = str(cab_chk.get("cNumeroRemessa") or cod_ped)
                                    dados_rem_json = json.dumps(d_rem_chk, ensure_ascii=False)
                                    fr_rem = d_rem_chk.get("frete") or {}
                                    if fr_rem.get("nCodTransp"):
                                        cod_transp = str(fr_rem.get("nCodTransp")).strip()
                                    inf_rem = d_rem_chk.get("infAdic") or {}
                                    obs_venda = inf_rem.get("cDadosAdic") or ""
                            except Exception:
                                pass
                        else:
                            dados_ped_json = json.dumps(d_ped, ensure_ascii=False)
                            pvp = d_ped.get("pedido_venda_produto") or {}
                            if pvp:
                                num_ped_real = str((pvp.get("cabecalho") or {}).get("numero_pedido") or "") or None
                                obs_venda = (pvp.get("observacoes") or {}).get("obs_venda") or ""
                                fr = pvp.get("frete") or {}
                                if fr.get("codigo_transportadora"):
                                    cod_transp = str(fr.get("codigo_transportadora")).strip()
                                if fr.get("peso_bruto"):
                                    peso_kg = float(fr.get("peso_bruto") or 0.5)
                                od = ((pvp.get("informacoes_adicionais") or {}).get("outros_detalhes") or {})
                                if od.get("cCEPOd") and od.get("cEnderecoOd"):
                                    cep_fin = re.sub(r"\D", "", str(od.get("cCEPOd") or ""))
                                    logr_fin = str(od.get("cEnderecoOd") or "").strip()
                                    num_fin = str(od.get("cNumeroOd") or "S/N").strip()
                                    compl_fin = str(od.get("cComplementoOd") or "").strip()
                                    bairro_fin = str(od.get("cBairroOd") or "").strip()
                                    cid_fin = str(od.get("cCidadeOd") or "").split("(")[0].strip()
                                    uf_fin = str(od.get("cEstadoOd") or "").strip()
                                    orig_end = "ENTREGA"
                    except Exception:
                        pass
                elif tem_rem:
                    tipo_orig = "REMESSA"
                    cod_rem_omie = int(cod_rem_found) if int(cod_rem_found or 0) > 0 else None
                    if compl.get("cNumRemessa"):
                        num_rem_real = str(compl.get("cNumRemessa"))
                    elif compl.get("nNumeroRemessa"):
                        num_rem_real = str(compl.get("nNumeroRemessa"))
                    elif cod_rem_omie:
                        try:
                            time.sleep(0.08)
                            qtd_rem += 1
                            r_rem = requests.post(
                                "https://app.omie.com.br/api/v1/produtos/remessa/",
                                json={
                                    "call": "ConsultarRemessa",
                                    "app_key": app_key,
                                    "app_secret": app_secret,
                                    "param": [{"nCodRem": cod_rem_omie}]
                                },
                                timeout=15
                            )
                            d_rem = r_rem.json()
                            dados_rem_json = json.dumps(d_rem, ensure_ascii=False)
                            cab_r = d_rem.get("cabec") or d_rem.get("cabecalho") or {}
                            num_rem_real = str(cab_r.get("cNumeroRemessa") or cab_r.get("numero_remessa") or cod_rem_omie)
                            fr_r = d_rem.get("frete") or {}
                            if fr_r.get("nCodTransp"):
                                cod_transp = str(fr_r.get("nCodTransp")).strip()
                            inf_r = d_rem.get("infAdic") or {}
                            obs_venda = inf_r.get("cDadosAdic") or ""
                        except Exception:
                            num_rem_real = str(cod_rem_omie)

                if tipo_orig not in ("PEDIDO", "REMESSA"):
                    execute_turso_query("UPDATE omie_nf_bronze SET status_enriquecimento = 'IGNORADO_SEM_ORIGEM', updated_at = CURRENT_TIMESTAMP WHERE id = ?", [bronze_id])
                    continue

                classif = classificar_forma_envio_prata(obs_venda or transp_nome, cod_transp, cid_fin)

                try:
                    execute_turso_query("""
                        INSERT INTO omie_expedicoes_prata (
                          codigo_nf, numero_nf, serie_nf, chave_nfe, tipo_origem,
                          codigo_pedido_omie, numero_pedido, codigo_remessa_omie, numero_remessa,
                          tp_nf, data_emissao, cliente_nome, cliente_cpf_cnpj, cep, logradouro, numero,
                          complemento, bairro, cidade, uf, origem_endereco, valor_nf, valor_frete,
                          peso_kg, obs_venda, codigo_transportadora, transportadora_normalizada,
                          servico_normalizado, dados_nf_json, dados_pedido_json, dados_remessa_json,
                          enriquecido_em, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT(chave_nfe) DO UPDATE SET
                          tipo_origem = excluded.tipo_origem,
                          codigo_pedido_omie = excluded.codigo_pedido_omie,
                          numero_pedido = excluded.numero_pedido,
                          codigo_remessa_omie = excluded.codigo_remessa_omie,
                          numero_remessa = excluded.numero_remessa,
                          tp_nf = excluded.tp_nf,
                          cliente_nome = excluded.cliente_nome,
                          cliente_cpf_cnpj = excluded.cliente_cpf_cnpj,
                          cep = excluded.cep,
                          logradouro = excluded.logradouro,
                          numero = excluded.numero,
                          complemento = excluded.complemento,
                          bairro = excluded.bairro,
                          cidade = excluded.cidade,
                          uf = excluded.uf,
                          origem_endereco = excluded.origem_endereco,
                          valor_nf = excluded.valor_nf,
                          valor_frete = excluded.valor_frete,
                          peso_kg = excluded.peso_kg,
                          obs_venda = excluded.obs_venda,
                          codigo_transportadora = excluded.codigo_transportadora,
                          transportadora_normalizada = excluded.transportadora_normalizada,
                          servico_normalizado = excluded.servico_normalizado,
                          dados_pedido_json = excluded.dados_pedido_json,
                          dados_remessa_json = excluded.dados_remessa_json,
                          updated_at = CURRENT_TIMESTAMP
                    """, [
                        cod_nf, num_nf, serie_nf, chave_nfe or None, tipo_orig,
                        cod_ped if cod_ped > 0 else None, num_ped_real,
                        cod_rem_omie, num_rem_real,
                        tp_nf_real, data_emi, cli_nome, cli_cpf, cep_fin, logr_fin, num_fin,
                        compl_fin, bairro_fin, cid_fin, uf_fin, orig_end, val_nf, val_frete,
                        peso_kg, obs_venda, cod_transp, classif["grupo"],
                        classif["servico"], raw_json, dados_ped_json, dados_rem_json
                    ])
                    execute_turso_query("UPDATE omie_nf_bronze SET status_enriquecimento = 'PRONTO', updated_at = CURRENT_TIMESTAMP WHERE id = ?", [bronze_id])
                    qtd_enriquecida += 1
                except Exception:
                    execute_turso_query("UPDATE omie_nf_bronze SET status_enriquecimento = 'ERRO', updated_at = CURRENT_TIMESTAMP WHERE id = ?", [bronze_id])
                    qtd_erro += 1

            if sync_id:
                execute_turso_query("""
                    UPDATE omie_sync_control
                    SET finalizado_em = CURRENT_TIMESTAMP,
                        quantidade_encontrada = ?,
                        quantidade_existente = ?,
                        quantidade_nova = ?,
                        quantidade_enriquecida = ?,
                        quantidade_erro = ?,
                        status = 'CONCLUIDO'
                    WHERE id = ?
                """, [qtd_encontrada, qtd_existente, qtd_nova, qtd_enriquecida, qtd_erro, sync_id])

            return 200, {
                "sucesso": True,
                "periodo": {"inicio": d_ini_str, "fim": d_fim_str},
                "metricas": {
                    "quantidade_encontrada": qtd_encontrada,
                    "quantidade_existente": qtd_existente,
                    "quantidade_nova": qtd_nova,
                    "quantidade_enriquecida": qtd_enriquecida,
                    "quantidade_erro": qtd_erro,
                    "remessas_faturadas_encontradas": remessas_metricas["encontradas"],
                    "remessas_novas": remessas_metricas["novas"],
                    "remessas_erros": remessas_metricas["erros"],
                    "remessas_aviso": remessas_metricas["aviso"],
                    "consultar_pedido_executados": qtd_ped,
                    "consultar_remessa_executados": qtd_rem,
                    "consultar_nf_executados": 0
                }
            }
        except Exception as e:
            if sync_id:
                try:
                    execute_turso_query("UPDATE omie_sync_control SET finalizado_em = CURRENT_TIMESTAMP, status = 'ERRO' WHERE id = ?", [sync_id])
                except Exception:
                    pass
            return 500, {
                "sucesso": False,
                "erro": str(e),
                "remessas_sync": remessas_metricas,
            }

    # =========================================================================
    # 3. HANDLER: correios-prepostagem
    # =========================================================================
    @staticmethod
    def handle_correios_prepostagem(body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        cws_token = (os.getenv("CWS_TOKEN") or "").strip()
        cartao_postagem = (os.getenv("CARTAO_POSTAGEM_CORREIOS") or "0066578957").strip()
        if not cws_token:
            return 500, {"error": "CWS_TOKEN nao configurado no ambiente."}

        b_in = body or {}
        pedido_raw = b_in.get("pedido")
        pedido = pedido_raw if isinstance(pedido_raw, dict) else b_in
        num_ped = str(pedido.get("numero_pedido") or pedido.get("pedido") or "").strip()
        if not num_ped:
            return 400, {"error": "Dados do pedido nao enviados."}

        servicos_map = {"PAC": "03298", "SEDEX": "03220", "MINI ENVIOS": "04227", "MINI_ENVIOS": "04227"}
        modalidade = str(pedido.get("servico") or pedido.get("forma_envio") or "PAC").upper()
        codigo_servico = servicos_map.get(modalidade, "03298")
        peso_gramas = str(round(float(pedido.get("peso_kg") or 0.5) * 1000))
        qtd_etiquetas = int(pedido.get("qtd_etiquetas") or 1)

        remetente_padrao = {
            "nome": "COMUNIDADE CATOLICA SHALOM",
            "cpfCnpj": "07044456000364",
            "dddTelefone": "85",
            "telefone": "32168918",
            "dddCelular": "85",
            "celular": "982168918",
            "email": "setorfiscal@comshalom.org",
            "endereco": {
                "cep": "61700000",
                "logradouro": "RUA BERRA BODE - JAMBREIRO",
                "numero": "S/N",
                "complemento": "DIACONIA SHALOM",
                "bairro": "BERRA BODE",
                "cidade": "Aquiraz",
                "uf": "CE"
            }
        }

        resultados = []
        dest_info = pedido.get("destinatario") or {}
        ender_info = dest_info.get("endereco") or {
            "logradouro": dest_info.get("logradouro") or "",
            "numero": dest_info.get("numero") or "S/N",
            "complemento": dest_info.get("complemento") or "",
            "bairro": dest_info.get("bairro") or "",
            "cidade": dest_info.get("cidade") or "",
            "uf": dest_info.get("uf") or "",
            "cep": re.sub(r"\D", "", str(dest_info.get("cep") or ""))
        }

        fone_clean = re.sub(r"\D", "", str(dest_info.get("celular") or dest_info.get("telefone") or ""))
        ddd_cel = fone_clean[:2] if len(fone_clean) >= 2 else "85"
        num_cel = fone_clean[2:] if len(fone_clean) > 2 else "999999999"

        for vol in range(1, qtd_etiquetas + 1):
            payload = {
                "remetente": remetente_padrao,
                "destinatario": {
                    "nome": dest_info.get("nome") or "",
                    "cpfCnpj": re.sub(r"\D", "", str(dest_info.get("cpfCnpj") or "")),
                    "email": dest_info.get("email") or "",
                    "dddCelular": ddd_cel,
                    "celular": num_cel,
                    "endereco": ender_info
                },
                "codigoServico": codigo_servico,
                "statusPrePostagem": "V",
                "numeroNotaFiscal": str(pedido.get("numero_nf") or ""),
                "numeroCartaoPostagem": cartao_postagem,
                "chaveNFe": str(pedido.get("chave_nfe") or ""),
                "itensDeclaracaoConteudo": pedido.get("itens") or [{"conteudo": "PRODUTO SHALOM", "quantidade": "1", "valor": "10.00"}],
                "pesoInformado": peso_gramas,
                "codigoFormatoObjetoInformado": "2",
                "alturaInformada": "3" if codigo_servico == "04227" else "15",
                "larguraInformada": "20",
                "comprimentoInformado": "25",
                "cienteObjetoNaoProibido": "1",
                "observacao": f"Volume {vol} de {qtd_etiquetas} - Pedido #{pedido.get('numero_pedido') or pedido.get('pedido') or ''}"
            }

            res = requests.post(
                "https://api.correios.com.br/prepostagem/v1/prepostagens",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {cws_token}"
                },
                timeout=20
            )
            try:
                res_json = res.json()
            except Exception:
                res_json = {"raw": res.text}

            id_pre = res_json.get("id") or res_json.get("idPrePostagem")
            cod_obj = res_json.get("codigoObjeto")
            cws_ok = res.ok and bool(id_pre) and bool(cod_obj)

            if cws_ok:
                try:
                    CorreiosHubService.handle_turso_db("POST", {"action": ["save_prepostagem"]}, {
                        "pedido": pedido.get("numero_pedido") or pedido.get("pedido") or "",
                        "numero_nf": pedido.get("numero_nf") or "",
                        "serie_nf": pedido.get("serie_nf") or "1",
                        "chave_nfe": pedido.get("chave_nfe") or "",
                        "codigo_cliente_omie": pedido.get("codigo_cliente_omie") or "",
                        "id_prepostagem": id_pre,
                        "codigo_objeto": cod_obj,
                        "contrato": "",
                        "cartao_postagem": cartao_postagem,
                        "servico": modalidade,
                        "destinatario": dest_info.get("nome") or "",
                        "cpf_cnpj_destinatario": dest_info.get("cpfCnpj") or "",
                        "email_destinatario": dest_info.get("email") or "",
                        "telefone_destinatario": dest_info.get("celular") or dest_info.get("telefone") or "",
                        "logradouro": ender_info.get("logradouro") or "",
                        "numero": ender_info.get("numero") or "",
                        "complemento": ender_info.get("complemento") or "",
                        "bairro": ender_info.get("bairro") or "",
                        "cidade": ender_info.get("cidade") or "",
                        "uf": ender_info.get("uf") or "",
                        "cep": ender_info.get("cep") or "",
                        "origem_postagem": pedido.get("origem_postagem") or "OMIE",
                        "status_rotulo": "PENDENTE",
                        "dados_fiscais_json": pedido.get("dados_fiscais_json")
                    })
                except Exception as e_save:
                    logger.error("Erro ao salvar prepostagem no Turso: %s", e_save)

            resultados.append({
                "volume": f"{vol}/{qtd_etiquetas}",
                "sucesso": cws_ok,
                "httpStatus": res.status_code,
                "codigoObjeto": cod_obj,
                "idPrePostagem": id_pre,
                "detalhes": res_json
            })

        return 200, {
            "numero_pedido": pedido.get("numero_pedido"),
            "total_volumes": qtd_etiquetas,
            "resultados": resultados
        }

    # =========================================================================
    # 4. HANDLER: correios-rotulo
    # =========================================================================
    @staticmethod
    def handle_correios_rotulo(body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        cws_token = (os.getenv("CWS_TOKEN") or "").strip()
        cartao_postagem = re.sub(r"\D", "", os.getenv("CARTAO_POSTAGEM_CORREIOS") or "66578957").zfill(10)
        if not cws_token:
            return 500, {"error": "CWS_TOKEN nao configurado."}

        b = body or {}
        id_recibo = b.get("idRecibo")
        ids_pre = b.get("idsPrePostagem") or []
        cods_obj = b.get("codigosObjeto") or []
        tipo_rotulo = b.get("tipoRotulo") or "P"
        formato_rotulo = b.get("formatoRotulo") or "ET"

        pdf_base64 = None
        codigo_cws = "PPN-291"
        mensagem_cws = "Aguardando geracao"

        def _solicitar_novo_recibo():
            if not ids_pre and not cods_obj:
                return None
            payload = {
                "idCorreios": cartao_postagem,
                "numeroCartaoPostagem": cartao_postagem,
                "tipoRotulo": tipo_rotulo,
                "formatoRotulo": formato_rotulo
            }
            if cods_obj:
                payload["codigosObjeto"] = cods_obj
            else:
                payload["idsPrePostagem"] = ids_pre

            r_sol = requests.post(
                "https://api.correios.com.br/prepostagem/v1/prepostagens/rotulo/assincrono/pdf",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {cws_token}",
                    "accept": "application/json"
                },
                timeout=15
            )
            try:
                d_sol = r_sol.json()
            except Exception:
                d_sol = {}
            novo_rec = d_sol.get("idRecibo")
            if novo_rec:
                try:
                    CorreiosHubService.handle_turso_db("POST", {"action": ["save_recibo"]}, {
                        "id_prepostagem": ids_pre[0] if ids_pre else "",
                        "codigo_objeto": cods_obj[0] if cods_obj else "",
                        "id_recibo": novo_rec,
                        "status": "PROCESSANDO",
                        "codigo_cws": "PPN-291",
                        "mensagem_cws": "Novo rotulo em processamento no CWS"
                    })
                except Exception:
                    pass
            return novo_rec

        def _baixar_pdf(rec_id: str):
            r_dl = requests.get(
                f"https://api.correios.com.br/prepostagem/v1/prepostagens/rotulo/download/assincrono/{rec_id}",
                headers={
                    "Authorization": f"Bearer {cws_token}",
                    "accept": "application/pdf, application/json"
                },
                timeout=15
            )
            if r_dl.ok:
                ct = (r_dl.headers.get("content-type") or "").lower()
                if "application/pdf" in ct:
                    return {"pdf": base64.b64encode(r_dl.content).decode("ascii"), "status": "HTTP-200", "msg": "PDF OK"}
                try:
                    d_dl = r_dl.json()
                    b64 = d_dl.get("dados") or d_dl.get("dadosFormatados") or d_dl.get("pdf") or d_dl.get("pdfBase64")
                    if b64 and isinstance(b64, str) and len(b64) > 100:
                        return {"pdf": b64, "status": "HTTP-200", "msg": "PDF OK"}
                    msg_txt = d_dl.get("mensagem") or json.dumps(d_dl)
                    for code in ("PPN-295", "PPN-297", "PPN-291"):
                        if code in msg_txt:
                            return {"pdf": None, "status": code, "msg": msg_txt}
                    return {"pdf": None, "status": "ERRO_CWS", "msg": msg_txt}
                except Exception:
                    return {"pdf": None, "status": "PROCESSANDO", "msg": "Processando"}
            return {"pdf": None, "status": f"HTTP-{r_dl.status_code}", "msg": "Erro no download"}

        if id_recibo and str(id_recibo) not in ("null", "undefined"):
            res_dl = _baixar_pdf(str(id_recibo))
            if res_dl["pdf"]:
                pdf_base64 = res_dl["pdf"]
                codigo_cws = res_dl["status"]
                mensagem_cws = res_dl["msg"]
            elif res_dl["status"] in ("PPN-295", "PPN-297", "ERRO_CWS"):
                id_recibo = None
            else:
                codigo_cws = res_dl["status"]
                mensagem_cws = res_dl["msg"]

        if not id_recibo or str(id_recibo) == "null":
            novo = _solicitar_novo_recibo()
            if novo:
                id_recibo = novo
                res_dl2 = _baixar_pdf(str(id_recibo))
                if res_dl2["pdf"]:
                    pdf_base64 = res_dl2["pdf"]
                codigo_cws = res_dl2["status"]
                mensagem_cws = res_dl2["msg"]

        if id_recibo:
            try:
                CorreiosHubService.handle_turso_db("POST", {"action": ["update_status_rotulo"]}, {
                    "id_recibo": id_recibo,
                    "status_rotulo": "PRONTO" if pdf_base64 else ("PROCESSANDO" if codigo_cws.startswith("PPN-29") else "ERRO"),
                    "codigo_cws": codigo_cws,
                    "mensagem_cws": mensagem_cws
                })
            except Exception:
                pass

        return 200, {
            "sucesso": True,
            "idRecibo": id_recibo,
            "pdfBase64": pdf_base64,
            "codigoCws": codigo_cws,
            "mensagemCws": mensagem_cws
        }

    # =========================================================================
    # 5. HANDLER: correios-cancelar
    # =========================================================================
    @staticmethod
    def handle_correios_cancelar(body: Dict[str, Any], query_params: Dict[str, List[str]] = None) -> Tuple[int, Dict[str, Any]]:
        username = (os.getenv("CORREIOS_ADMIN_SGC") or "07044456000364").strip()
        b = body or {}
        qp = query_params or {}

        id_pre = b.get("idPrePostagem") or b.get("id") or (qp.get("id", [""])[0]) or (qp.get("idPrePostagem", [""])[0]) or ""
        cod_obj = b.get("codigoObjeto") or (qp.get("codigoObjeto", [""])[0]) or ""
        id_reg = b.get("idRegistro") or b.get("id_registro") or (qp.get("idRegistro", [""])[0]) or (qp.get("id_registro", [""])[0]) or ""
        pedido_reg = b.get("pedido") or (qp.get("pedido", [""])[0]) or ""
        nf_reg = b.get("numeroNf") or b.get("numero_nf") or (qp.get("numeroNf", [""])[0]) or (qp.get("numero_nf", [""])[0]) or ""
        servico_req = (b.get("servico") or (qp.get("servico", [""])[0]) or "").upper()
        ids_pre = b.get("idsPrePostagens") or []
        cods_obj = b.get("codigosObjetos") or []
        solicitante = b.get("idCorreiosSolicitanteCancelamento") or username
        forcar_local = bool(b.get("forcarLocal") or b.get("forcar_local") or (qp.get("forcarLocal", [""])[0].lower() in ("true", "1")) or (qp.get("force", [""])[0] == "1"))

        target_obj = cod_obj or (cods_obj[0] if cods_obj else "")
        target_id_pre = id_pre or (ids_pre[0] if ids_pre else "")

        if forcar_local:
            CorreiosHubService.handle_turso_db("POST", {"action": ["cancel_prepostagem"]}, {
                "id_registro": id_reg,
                "id_prepostagem": target_id_pre,
                "codigo_objeto": target_obj,
                "pedido": pedido_reg,
                "numero_nf": nf_reg,
                "status_rotulo": "CANCELADO",
                "resposta_cws": {"origem": "CANCELAMENTO_FORCADO", "motivo": "Cancelamento forçado pelo operador"},
                "usuario_cancelamento": "OPERADOR"
            })
            return 200, {
                "sucesso": True,
                "httpStatus": 200,
                "mensagem": "Objeto cancelado e removido do sistema com sucesso.",
                "detalhes": {"forcar_local": True}
            }

        servico_persistido = None
        is_teste = "TEST" in str(target_id_pre).upper() or "TEST" in str(target_obj).upper()
        if target_obj or target_id_pre:
            try:
                q_pre = execute_turso_query(
                    "SELECT servico, pedido, destinatario FROM prepostagens WHERE (codigo_objeto = ? AND codigo_objeto != '') OR (id_prepostagem = ? AND id_prepostagem != '') LIMIT 1",
                    [target_obj, target_id_pre]
                )
                rows = (q_pre or {}).get("rows") or []
                if rows:
                    if _cell_val(rows[0][0]):
                        servico_persistido = str(_cell_val(rows[0][0])).upper()
                    ped_txt = str(_cell_val(rows[0][1]) or "").upper()
                    dest_txt = str(_cell_val(rows[0][2]) or "").upper()
                    if "TEST" in ped_txt or "TEST" in dest_txt:
                        is_teste = True
            except Exception:
                pass

        if is_teste:
            CorreiosHubService.handle_turso_db("POST", {"action": ["cancel_prepostagem"]}, {
                "id_prepostagem": target_id_pre,
                "codigo_objeto": target_obj,
                "status_rotulo": "CANCELADO",
                "resposta_cws": {"origem": "OBJETO_TESTE", "motivo": "Cancelamento local de teste"},
                "usuario_cancelamento": "OPERADOR"
            })
            return 200, {
                "sucesso": True,
                "httpStatus": 200,
                "mensagem": "Objeto de teste cancelado com sucesso no sistema local.",
                "detalhes": {"origem": "OBJETO_TESTE"}
            }

        is_total = (
            (target_obj and target_obj.upper().startswith("TX"))
            or (target_id_pre and target_id_pre.upper().startswith("TOTAL_EXPRESS_"))
            or (servico_persistido and any(k in servico_persistido for k in ("TOTAL", "EXP", "STD")))
            or ("TOTAL" in servico_req)
        )
        if is_total:
            CorreiosHubService.handle_turso_db("POST", {"action": ["cancel_prepostagem"]}, {
                "id_prepostagem": target_id_pre,
                "codigo_objeto": target_obj,
                "status_rotulo": "CANCELADO",
                "resposta_cws": {"origem": "TOTAL_EXPRESS", "motivo": "Cancelamento local Total Express"},
                "usuario_cancelamento": "OPERADOR"
            })
            return 200, {
                "sucesso": True,
                "httpStatus": 200,
                "mensagem": "Etiqueta Total Express cancelada com sucesso no sistema local.",
                "detalhes": {"origem": "TOTAL_EXPRESS"}
            }

        is_modico = False
        if servico_persistido:
            if any(k in servico_persistido for k in ("MODICO", "20133", "IMPRESSO")):
                is_modico = True
        else:
            if "MODICO" in str(target_id_pre) or str(target_obj).startswith("YD"):
                is_modico = True

        is_souza = False
        if servico_persistido:
            if any(k in servico_persistido for k in ("SOUZA", "ENTREGA_PROPRIA", "LOCAL")):
                is_souza = True
        else:
            if "SOUZA" in str(target_id_pre) or str(target_obj).startswith("SZ") or "ENTREGA_PROPRIA" in servico_req or "SOUZA" in servico_req:
                is_souza = True

        if is_modico or "MODICO" in servico_req or "YD" in str(target_obj) or "MODICO" in str(target_id_pre):
            return CorreiosHubService.handle_turso_db("POST", {"action": ["cancel_modico"]}, {
                "id_prepostagem": target_id_pre,
                "codigo_objeto": target_obj,
                "usuario_cancelamento": "OPERADOR"
            })

        if is_souza or "SOUZA" in servico_req or "ENTREGA_PROPRIA" in servico_req or str(target_obj).startswith("SZ") or "SOUZA" in str(target_id_pre):
            if target_obj and target_obj.startswith("SZ"):
                try:
                    devolver_codigo_souza(target_obj)
                except Exception:
                    pass
            CorreiosHubService.handle_turso_db("POST", {"action": ["cancel_prepostagem"]}, {
                "id_prepostagem": target_id_pre,
                "codigo_objeto": target_obj,
                "status_rotulo": "CANCELADO",
                "resposta_cws": {"origem": "ENTREGA_PROPRIA_SOUZA", "motivo": "Cancelamento local interno"},
                "usuario_cancelamento": "OPERADOR"
            })
            return 200, {
                "sucesso": True,
                "httpStatus": 200,
                "mensagem": "Cancelamento de Entrega Propria (Souza) efetuado com sucesso no sistema local.",
                "detalhes": {"origem": "ENTREGA_PROPRIA_SOUZA"}
            }

        if servico_persistido in ("RETIRADA_GUARITA", "RETIRADA_ESTOQUE"):
            CorreiosHubService.handle_turso_db("POST", {"action": ["cancel_prepostagem"]}, {
                "id_prepostagem": target_id_pre,
                "codigo_objeto": "",
                "status_rotulo": "CANCELADO",
                "resposta_cws": {"origem": "RETIRADA_LOCAL", "motivo": "Cancelamento local"},
                "usuario_cancelamento": "OPERADOR"
            })
            return 200, {"sucesso": True, "httpStatus": 200, "mensagem": "Retirada cancelada localmente."}

        cws_token = (os.getenv("CWS_TOKEN") or "").strip()
        if not cws_token:
            return 500, {"error": "CWS_TOKEN nao configurado para cancelar no Correios CWS."}

        payload_fetch = None
        if ids_pre or cods_obj:
            url = "https://api.correios.com.br/prepostagem/v1/prepostagens/assincrona"
            payload_fetch = {"idsPrePostagens": ids_pre} if ids_pre else {"codigosObjetos": cods_obj}
        elif id_pre:
            url = f"https://api.correios.com.br/prepostagem/v1/prepostagens/{id_pre}?idCorreiosSolicitanteCancelamento={solicitante}"
        elif cod_obj:
            url = f"https://api.correios.com.br/prepostagem/v1/prepostagens/objeto/{cod_obj}?idCorreiosSolicitanteCancelamento={solicitante}"
        else:
            return 400, {"error": "Informe idPrePostagem ou codigoObjeto."}

        headers = {"Authorization": f"Bearer {cws_token}", "accept": "application/json"}
        if payload_fetch:
            headers["Content-Type"] = "application/json"
            res_cancel = requests.delete(url, json=payload_fetch, headers=headers, timeout=15)
        else:
            res_cancel = requests.delete(url, headers=headers, timeout=15)

        try:
            data_res = res_cancel.json()
        except Exception:
            data_res = {"text": res_cancel.text}

        if res_cancel.ok or res_cancel.status_code in (200, 204):
            CorreiosHubService.handle_turso_db("POST", {"action": ["cancel_prepostagem"]}, {
                "id_prepostagem": id_pre,
                "codigo_objeto": cod_obj,
                "status_rotulo": "CANCELADO",
                "resposta_cws": data_res,
                "usuario_cancelamento": "OPERADOR"
            })
            return 200, {
                "sucesso": True,
                "httpStatus": res_cancel.status_code,
                "mensagem": "Cancelamento efetuado no CWS.",
                "detalhes": data_res
            }
        return res_cancel.status_code, {
            "sucesso": False,
            "httpStatus": res_cancel.status_code,
            "error": f"CWS rejeitou o cancelamento (Status {res_cancel.status_code})",
            "detalhes": data_res
        }

    # =========================================================================
    # 6. HANDLER: lista-postagem
    # =========================================================================
    @staticmethod
    def handle_lista_postagem(method: str, query_params: Dict[str, List[str]], body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        b = body or {}
        action = (query_params.get("action", [None])[0]) or b.get("action") or "list_disponiveis"

        try:
            if method == "GET" and action == "list_disponiveis":
                data_ini = query_params.get("data_inicio", [""])[0]
                data_fim = query_params.get("data_fim", [""])[0]
                servico = query_params.get("servico", [""])[0]
                transportadora = query_params.get("transportadora", [""])[0]
                rastreio = query_params.get("rastreio", [""])[0]
                pedido = query_params.get("pedido", [""])[0]
                destinatario = query_params.get("destinatario", [""])[0]

                sql = """
                    SELECT id, pedido, numero_nf, chave_nfe, id_prepostagem, codigo_objeto,
                           servico, destinatario, cidade, uf, cep, status_rotulo, status_impressao,
                           cancelado, lista_id, created_at, valor_frete, status_entrega, tipo_item, descricao_avulsa
                    FROM prepostagens
                    WHERE cancelado = 0
                      AND ((codigo_objeto IS NOT NULL AND codigo_objeto != '') OR servico = 'RETIRADA_GUARITA')
                      AND (status_impressao = 'IMPRESSO' OR status_impressao = 'ARQUIVADO' OR status_impressao = 'PRONTO' OR status_impressao IS NULL)
                      AND (lista_id IS NULL OR lista_id = '')
                """
                params = []
                if data_ini:
                    sql += " AND created_at >= ?"
                    params.append(f"{data_ini} 00:00:00")
                if data_fim:
                    sql += " AND created_at <= ?"
                    params.append(f"{data_fim} 23:59:59")
                if servico and servico != "TODOS":
                    sql += " AND servico = ?"
                    params.append(servico)
                if transportadora:
                    t_up = transportadora.upper()
                    if t_up == "CORREIOS":
                        sql += """ AND servico NOT IN ('RETIRADA_GUARITA', 'RETIRADA_ESTOQUE', 'ENTREGA_PROPRIA', 'SOUZA', 'LOCAL', 'SOUZA_TRANSLATINO', 'TRANSLATINO', 'TOTAL_EXPRESS', 'EXP', 'STD', 'JT_EXPRESS')
                                   AND codigo_objeto NOT LIKE 'SZ%'
                                   AND codigo_objeto NOT LIKE 'TX%'
                                   AND id_prepostagem NOT LIKE 'TOTAL_EXPRESS_%' """
                    elif t_up == "SOUZA":
                        sql += " AND (servico IN ('ENTREGA_PROPRIA', 'SOUZA', 'LOCAL', 'SOUZA_TRANSLATINO', 'TRANSLATINO') OR codigo_objeto LIKE 'SZ%')"
                    elif t_up == "GUARITA":
                        sql += " AND servico = 'RETIRADA_GUARITA'"
                    elif t_up == "ESTOQUE":
                        sql += " AND servico = 'RETIRADA_ESTOQUE'"
                    elif t_up == "TOTAL":
                        sql += " AND (codigo_objeto LIKE 'TX%' OR id_prepostagem LIKE 'TOTAL_EXPRESS_%' OR servico IN ('EXP', 'STD', 'TOTAL_EXPRESS') OR servico LIKE '%TOTAL%')"
                    elif t_up == "JT":
                        sql += " AND (servico LIKE '%JT%' OR servico LIKE '%J&T%')"
                    else:
                        sql += " AND servico NOT IN ('RETIRADA_GUARITA', 'RETIRADA_ESTOQUE')"
                else:
                    sql += " AND servico NOT IN ('RETIRADA_GUARITA', 'RETIRADA_ESTOQUE')"
                if rastreio:
                    sql += " AND codigo_objeto LIKE ?"
                    params.append(f"%{rastreio.strip()}%")
                if pedido:
                    sql += " AND pedido LIKE ?"
                    params.append(f"%{pedido.strip()}%")
                if destinatario:
                    sql += " AND destinatario LIKE ?"
                    params.append(f"%{destinatario.strip()}%")

                sql += " ORDER BY id DESC LIMIT 200"
                res = execute_turso_query(sql, params)
                disponiveis = [
                    {
                        "id": _cell_val(r[0]), "pedido": _cell_val(r[1]), "numero_nf": _cell_val(r[2]),
                        "chave_nfe": _cell_val(r[3]), "id_prepostagem": _cell_val(r[4]), "codigo_objeto": _cell_val(r[5]),
                        "servico": _cell_val(r[6]), "destinatario": _cell_val(r[7]), "cidade": _cell_val(r[8]),
                        "uf": _cell_val(r[9]), "cep": _cell_val(r[10]), "status_rotulo": _cell_val(r[11]),
                        "status_impressao": _cell_val(r[12]), "cancelado": _cell_val(r[13]), "lista_id": _cell_val(r[14]),
                        "created_at": _cell_val(r[15]),
                        "valor_frete": float(_cell_val(r[16]) or 0.0) if len(r) > 16 and _cell_val(r[16]) is not None else 0.0,
                        "status_entrega": _cell_val(r[17]) if len(r) > 17 and _cell_val(r[17]) else 'EM_COLETA',
                        "tipo_item": _cell_val(r[18]) if len(r) > 18 and _cell_val(r[18]) else 'PEDIDO',
                        "descricao_avulsa": _cell_val(r[19]) if len(r) > 19 and _cell_val(r[19]) else ''
                    }
                    for r in ((res or {}).get("rows") or [])
                ]
                return 200, {"success": True, "count": len(disponiveis), "disponiveis": disponiveis}

            if method == "POST" and action == "create_lista":
                ids_pre = b.get("idsPrepostagem") or b.get("prepostagem_ids") or []
                usuario = b.get("usuario") or "OPERADOR"
                if not ids_pre:
                    return 400, {"error": "Informe ao menos um ID de pre-postagem."}

                placeholders = ",".join("?" for _ in ids_pre)
                check_res = execute_turso_query(
                    f"SELECT id, codigo_objeto, servico, cancelado, status_impressao, lista_id FROM prepostagens WHERE id IN ({placeholders})",
                    ids_pre
                )
                rows = (check_res or {}).get("rows") or []
                if len(rows) != len(ids_pre):
                    return 400, {"error": "Um ou mais IDs nao foram encontrados."}

                # Obter frete e detalhes de cada item
                itens_res = execute_turso_query(
                    f"SELECT id, codigo_objeto, servico, COALESCE(valor_frete, 0.0) FROM prepostagens WHERE id IN ({placeholders})",
                    ids_pre
                )
                itens_inserir = []
                valor_total_romaneio = 0.0
                tipo_romaneio = b.get("tipo_romaneio") or "CORREIOS"
                tem_guarita = False
                tem_nao_guarita = False
                
                for r in ((itens_res or {}).get("rows") or []):
                    vf = float(_cell_val(r[3]) or 0.0)
                    srv = str(_cell_val(r[2]) or "")
                    cd = str(_cell_val(r[1]) or "")
                    if srv in ("ENTREGA_PROPRIA", "SOUZA", "LOCAL", "SOUZA_TRANSLATINO", "TRANSLATINO") or cd.startswith("SZ"):
                        tipo_romaneio = "SOUZA"
                    elif srv == "RETIRADA_GUARITA":
                        tipo_romaneio = "RETIRADA_GUARITA"
                        tem_guarita = True
                    elif srv == "RETIRADA_ESTOQUE":
                        return 400, {"error": "Retiradas no estoque não podem entrar em listas de postagem."}
                    elif "TOTAL" in srv.upper():
                        tipo_romaneio = "TOTAL_EXPRESS"
                    elif "JT" in srv.upper() or "J&T" in srv.upper():
                        tipo_romaneio = "JT_EXPRESS"
                    valor_total_romaneio += vf
                    if srv != "RETIRADA_GUARITA":
                        tem_nao_guarita = True
                    itens_inserir.append({
                        "id": int(_cell_val(r[0])),
                        "codigo_objeto": cd,
                        "servico": srv,
                        "valor_frete": vf
                    })

                if tem_guarita and tem_nao_guarita:
                    return 400, {"error": "A lista de retirada da guarita deve conter somente itens RETIRADA_GUARITA."}

                execute_turso_query("UPDATE lista_postagem_seq SET ultimo_numero = ultimo_numero + 1, updated_at = CURRENT_TIMESTAMP WHERE id = 1")
                seq_res = execute_turso_query("SELECT ultimo_numero FROM lista_postagem_seq WHERE id = 1")
                novo_seq = _cell_val(((seq_res or {}).get("rows") or [[192785]])[0][0]) or 192785
                num_lista_str = str(novo_seq)

                execute_turso_query(
                    "INSERT INTO lista_postagem (numero_lista, quantidade_objetos, usuario_geracao, status, tipo_romaneio, valor_total_frete, updated_at) VALUES (?, ?, ?, 'GERADA', ?, ?, CURRENT_TIMESTAMP)",
                    [num_lista_str, len(itens_inserir), usuario, tipo_romaneio, round(valor_total_romaneio, 2)]
                )
                id_res = execute_turso_query("SELECT id FROM lista_postagem WHERE numero_lista = ?", [num_lista_str])
                lista_id = _cell_val(((id_res or {}).get("rows") or [[None]])[0][0])

                stmts = []
                for idx, it in enumerate(itens_inserir):
                    stmts.append({
                        "sql": "INSERT INTO lista_postagem_itens (lista_id, prepostagem_id, numero_ordem, codigo_objeto, servico, valor_frete, status_entrega) VALUES (?, ?, ?, ?, ?, ?, 'EM_COLETA')",
                        "args": [lista_id, it["id"], idx + 1, it["codigo_objeto"], it["servico"], it["valor_frete"]]
                    })
                    stmts.append({
                        "sql": "UPDATE prepostagens SET lista_id = ?, status_entrega = 'EM_COLETA', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        "args": [lista_id, it["id"]]
                    })
                execute_turso_pipeline(stmts)

                return 200, {
                    "success": True,
                    "lista_id": lista_id,
                    "numero_lista": num_lista_str,
                    "quantidade_objetos": len(itens_inserir),
                    "status": "GERADA"
                }

            if method == "GET" and action == "list_listas":
                data_ini = query_params.get("data_inicio", [""])[0]
                data_fim = query_params.get("data_fim", [""])[0]
                num_lista = query_params.get("numero_lista", [""])[0]
                status = query_params.get("status", [""])[0]
                transportadora = query_params.get("transportadora", [""])[0]

                sql = """
                    SELECT id, numero_lista, data_geracao, usuario_geracao, quantidade_objetos,
                           contrato, cartao_postagem, status, data_cancelamento, usuario_cancelamento, created_at,
                           tipo_romaneio, valor_total_frete
                    FROM lista_postagem WHERE 1=1
                """
                params = []
                if data_ini:
                    sql += " AND data_geracao >= ?"
                    params.append(f"{data_ini} 00:00:00")
                if data_fim:
                    sql += " AND data_geracao <= ?"
                    params.append(f"{data_fim} 23:59:59")
                if num_lista:
                    sql += " AND numero_lista LIKE ?"
                    params.append(f"%{num_lista.strip()}%")
                if status and status != "TODOS":
                    sql += " AND status = ?"
                    params.append(status)
                if transportadora and transportadora != "TODOS":
                    if transportadora == "CORREIOS":
                        sql += " AND (tipo_romaneio = 'CORREIOS' OR tipo_romaneio IS NULL)"
                    else:
                        sql += " AND (tipo_romaneio = ? OR tipo_romaneio LIKE ?)"
                        params.extend([transportadora, f"%{transportadora}%"])
                sql += " ORDER BY id DESC LIMIT 100"

                res = execute_turso_query(sql, params)
                listas = [
                    {
                        "id": _cell_val(r[0]), "numero_lista": _cell_val(r[1]), "data_geracao": _cell_val(r[2]),
                        "usuario_geracao": _cell_val(r[3]), "quantidade_objetos": _cell_val(r[4]),
                        "contrato": _cell_val(r[5]), "cartao_postagem": _cell_val(r[6]), "status": _cell_val(r[7]),
                        "data_cancelamento": _cell_val(r[8]), "usuario_cancelamento": _cell_val(r[9]), "created_at": _cell_val(r[10]),
                        "tipo_romaneio": _cell_val(r[11]) if len(r) > 11 else "CORREIOS",
                        "valor_total_frete": float(_cell_val(r[12]) or 0.0) if len(r) > 12 else 0.0
                    }
                    for r in ((res or {}).get("rows") or [])
                ]
                return 200, {"success": True, "count": len(listas), "listas": listas}

            if method == "GET" and action == "get_lista":
                num_lista = query_params.get("numero_lista", [""])[0]
                lista_id = query_params.get("lista_id", [""])[0]
                res_l = execute_turso_query("""
                    SELECT id, numero_lista, data_geracao, usuario_geracao, quantidade_objetos,
                           contrato, cartao_postagem, status, data_cancelamento, usuario_cancelamento, created_at,
                           tipo_romaneio, valor_total_frete
                    FROM lista_postagem
                    WHERE (id = ? AND ? != '') OR (numero_lista = ? AND ? != '')
                """, [lista_id, lista_id, num_lista, num_lista])
                rows_l = (res_l or {}).get("rows") or []
                if not rows_l:
                    return 404, {"error": "Lista nao encontrada."}
                rl = rows_l[0]
                cab = {
                    "id": _cell_val(rl[0]), "numero_lista": _cell_val(rl[1]), "data_geracao": _cell_val(rl[2]),
                    "usuario_geracao": _cell_val(rl[3]), "quantidade_objetos": _cell_val(rl[4]),
                    "contrato": _cell_val(rl[5]), "cartao_postagem": _cell_val(rl[6]), "status": _cell_val(rl[7]),
                    "data_cancelamento": _cell_val(rl[8]), "usuario_cancelamento": _cell_val(rl[9]), "created_at": _cell_val(rl[10]),
                    "tipo_romaneio": _cell_val(rl[11]) if len(rl) > 11 else 'CORREIOS',
                    "valor_total_frete": float(_cell_val(rl[12]) or 0.0) if len(rl) > 12 else 0.0
                }
                res_it = execute_turso_query("""
                    SELECT i.numero_ordem, i.codigo_objeto, i.servico, p.cep, p.numero_nf, p.destinatario, p.cartao_postagem, p.pedido,
                           COALESCE(i.valor_frete, p.valor_frete, 0.0), COALESCE(i.status_entrega, p.status_entrega, 'EM_COLETA'),
                           p.logradouro, p.numero, p.bairro, p.cidade, p.uf, p.telefone_destinatario, p.obs_entrega,
                           i.data_entrega, i.recebedor_nome, i.assinatura_base64, p.id
                    FROM lista_postagem_itens i
                    LEFT JOIN prepostagens p ON i.prepostagem_id = p.id
                    WHERE i.lista_id = ?
                    ORDER BY i.numero_ordem ASC
                """, [cab["id"]])
                itens = [
                    {
                        "numero_ordem": _cell_val(r[0]), "codigo_objeto": _cell_val(r[1]), "servico": _cell_val(r[2]),
                        "cep": _cell_val(r[3]) or "", "numero_nf": _cell_val(r[4]) or "", "destinatario": _cell_val(r[5]) or "",
                        "cartao_postagem": _cell_val(r[6]) or cab.get("cartao_postagem", ""), "pedido": _cell_val(r[7]) or "",
                        "valor_frete": float(_cell_val(r[8]) or 0.0),
                        "status_entrega": _cell_val(r[9]) or 'EM_COLETA',
                        "logradouro": _cell_val(r[10]) or "",
                        "numero": _cell_val(r[11]) or "",
                        "bairro": _cell_val(r[12]) or "",
                        "cidade": _cell_val(r[13]) or "",
                        "uf": _cell_val(r[14]) or "",
                        "telefone_contato": _cell_val(r[15]) or "",
                        "observacoes_entrega": _cell_val(r[16]) or "",
                        "data_entrega": _cell_val(r[17]) or "",
                        "recebedor_nome": _cell_val(r[18]) or "",
                        "tem_assinatura": bool(_cell_val(r[19])),
                        "prepostagem_id": _cell_val(r[20])
                    }
                    for r in ((res_it or {}).get("rows") or [])
                ]
                return 200, {"success": True, "lista": cab, "itens": itens}

            if method == "POST" and action == "cancel_lista":
                num_lista = b.get("numero_lista") or ""
                lista_id = b.get("lista_id") or ""
                usu = b.get("usuario") or "OPERADOR"
                res_s = execute_turso_query(
                    "SELECT id, status FROM lista_postagem WHERE (id = ? AND ? != '') OR (numero_lista = ? AND ? != '')",
                    [lista_id, lista_id, num_lista, num_lista]
                )
                rows_s = (res_s or {}).get("rows") or []
                if not rows_s:
                    return 404, {"error": "Lista nao encontrada."}
                id_enc = _cell_val(rows_s[0][0])
                execute_turso_pipeline([
                    {
                        "sql": "UPDATE lista_postagem SET status = 'CANCELADA', data_cancelamento = CURRENT_TIMESTAMP, usuario_cancelamento = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        "args": [usu, id_enc]
                    },
                    {
                        "sql": "UPDATE prepostagens SET lista_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE lista_id = ?",
                        "args": [id_enc]
                    },
                    {
                        "sql": "DELETE FROM lista_postagem_itens WHERE lista_id = ?",
                        "args": [id_enc]
                    }
                ])
                return 200, {"success": True, "lista_id": id_enc, "status": "CANCELADA"}

            if method == "POST" and action == "delete_lista":
                num_lista = b.get("numero_lista") or ""
                lista_id = b.get("lista_id") or ""
                res_s = execute_turso_query(
                    "SELECT id FROM lista_postagem WHERE (id = ? AND ? != '') OR (numero_lista = ? AND ? != '')",
                    [lista_id, lista_id, num_lista, num_lista]
                )
                rows_s = (res_s or {}).get("rows") or []
                if not rows_s:
                    return 404, {"error": "Lista nao encontrada."}
                id_enc = _cell_val(rows_s[0][0])
                execute_turso_pipeline([
                    {"sql": "UPDATE prepostagens SET lista_id = NULL WHERE lista_id = ?", "args": [id_enc]},
                    {"sql": "DELETE FROM lista_postagem_itens WHERE lista_id = ?", "args": [id_enc]},
                    {"sql": "DELETE FROM lista_postagem WHERE id = ?", "args": [id_enc]}
                ])
                return 200, {"success": True, "mensagem": "Lista excluída permanentemente com sucesso.", "lista_id": id_enc}

            return 400, {"error": "Acao nao reconhecida"}
        except Exception as e:
            return 500, {"error": str(e)}

    # =========================================================================
    # 7. HANDLER: sro-rastro-consulta
    # =========================================================================
    @staticmethod
    def handle_sro_rastro_consulta(query_params: Dict[str, List[str]]) -> Tuple[int, Dict[str, Any]]:
        codigo_objeto = (query_params.get("codigoObjeto", [""])[0] or "").strip().upper()
        if not codigo_objeto:
            return 400, {"sucesso": False, "erro": "Codigo de objeto (SRO) obrigatorio."}

        token = (os.getenv("CWS_TOKEN_SRO") or "").strip()
        if not token:
            return 500, {"sucesso": False, "erro": "CWS_TOKEN_SRO nao configurado."}

        try:
            res = requests.get(
                f"https://api.correios.com.br/srorastro/v1/objetos/{codigo_objeto}?resultado=T",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Accept-Language": "pt-BR"
                },
                timeout=12
            )
            if not res.ok:
                return res.status_code, {"sucesso": False, "http_status": res.status_code, "erro": f"Erro HTTP {res.status_code} no SRO Rastro"}

            data = res.json()
            objetos = data.get("objetos") or []
            obj = objetos[0] if objetos else None
            if not obj or obj.get("mensagem"):
                return 404, {"sucesso": False, "erro": (obj or {}).get("mensagem") or f"Objeto {codigo_objeto} nao encontrado."}

            eventos_norm = []
            for ev in (obj.get("eventos") or []):
                unid = ev.get("unidade") or {}
                end = unid.get("endereco") or {}
                cid_uf = f"{end.get('cidade') or ''}/{end.get('uf') or ''}".strip("/")
                unid_dest = ev.get("unidadeDestino")
                dest_info = None
                if unid_dest:
                    ed = unid_dest.get("endereco") or {}
                    dest_info = {
                        "tipo": unid_dest.get("tipo") or "",
                        "nome": unid_dest.get("nome") or "",
                        "cidade": ed.get("cidade") or "",
                        "uf": ed.get("uf") or ""
                    }
                eventos_norm.append({
                    "codigo": ev.get("codigo") or "",
                    "tipo": ev.get("tipo") or "",
                    "descricao": ev.get("descricao") or "",
                    "detalhe": ev.get("detalhe") or "",
                    "comentario": ev.get("comentario") or "",
                    "dataHora": ev.get("dtHrCriado") or "",
                    "unidadeTipo": unid.get("tipo") or "",
                    "unidadeNome": unid.get("nome") or "",
                    "unidadeCidade": end.get("cidade") or "",
                    "unidadeUF": end.get("uf") or "",
                    "unidadeCidadeUF": cid_uf,
                    "unidadeDestino": dest_info
                })

            tp = obj.get("tipoPostal") or {}
            return 200, {
                "sucesso": True,
                "codigoObjeto": obj.get("codObjeto") or codigo_objeto,
                "previsaoEntrega": obj.get("dtPrevista") or "",
                "modalidade": obj.get("modalidade") or "",
                "tipoPostal": {
                    "sigla": tp.get("sigla") or "",
                    "descricao": tp.get("descricao") or "",
                    "categoria": tp.get("categoria") or ""
                } if tp else None,
                "contrato": obj.get("contrato") or "",
                "peso": obj.get("peso"),
                "formato": obj.get("formato") or "",
                "quantidadeEventos": len(eventos_norm),
                "ultimoEvento": eventos_norm[0] if eventos_norm else None,
                "eventos": eventos_norm
            }
        except Exception as e:
            return 500, {"sucesso": False, "erro": str(e)}

    # =========================================================================
    # 8. HANDLER: portalpostal-rastreio
    # =========================================================================
    @staticmethod
    def handle_portalpostal_rastreio(query_params: Dict[str, List[str]]) -> Tuple[int, Dict[str, Any]]:
        action = query_params.get("action", ["atualizar"])[0]
        codigo_agf = os.getenv("CORREIOS_CODIGO_AGF_PORTALPOSTAL") or "94"
        usuario = os.getenv("CORREIOS_USERNAME_PORTALPOSTAL") or ""
        senha = os.getenv("CORREIOS_PASSWORD_PORTALPOSTAL") or ""

        if action == "list":
            res_r = execute_turso_query("""
                SELECT r.id, r.prepostagem_id, r.codigo_objeto, r.servico, r.status_atual,
                       r.descricao_status, r.data_evento, r.data_postagem, r.prazo_estimado,
                       r.cep, r.destinatario, r.ultima_consulta, r.eventos_json
                FROM objeto_rastreamento r
                ORDER BY r.updated_at DESC LIMIT 200
            """)
            rast = [
                {
                    "id": _cell_val(r[0]), "prepostagem_id": _cell_val(r[1]), "codigo_objeto": _cell_val(r[2]),
                    "servico": _cell_val(r[3]), "status_atual": _cell_val(r[4]), "descricao_status": _cell_val(r[5]),
                    "data_evento": _cell_val(r[6]), "data_postagem": _cell_val(r[7]), "prazo_estimado": _cell_val(r[8]),
                    "cep": _cell_val(r[9]), "destinatario": _cell_val(r[10]), "ultima_consulta": _cell_val(r[11]),
                    "eventos_json": _cell_val(r[12])
                }
                for r in ((res_r or {}).get("rows") or [])
            ]
            return 200, {"sucesso": True, "rastreamientos": rast}

        if not usuario or not senha:
            return 400, {"sucesso": False, "error": "Credenciais do Portal Postal nao configuradas no .env"}

        data_ini = query_params.get("data_inicio", [""])[0]
        data_fim = query_params.get("data_fim", [""])[0]
        sro_filtro = query_params.get("sro", [""])[0]

        def _norm_ymd(s: str) -> str:
            s = (s or "").strip()
            if re.match(r"^\d{2}/\d{2}/\d{4}$", s):
                p = s.split("/")
                return f"{p[2]}-{p[1]}-{p[0]}"
            return s

        if not sro_filtro and (not data_ini or not data_fim):
            hoje = datetime.now()
            ini_dt = hoje - timedelta(days=30)
            data_ini = ini_dt.strftime("%Y-%m-%d")
            data_fim = hoje.strftime("%Y-%m-%d")

        res_turso = execute_turso_query("SELECT codigo_objeto FROM prepostagens WHERE codigo_objeto IS NOT NULL AND codigo_objeto != ''")
        codigos_gestor = {
            str(_cell_val(r[0]) or "").strip().upper()
            for r in ((res_turso or {}).get("rows") or [])
            if _cell_val(r[0])
        }

        payload_form = {
            "codigoAGF": codigo_agf,
            "usuario": usuario,
            "senha": senha,
            "tipoArquivo": "RAW",
            "formatoArquivo": "CSV",
            "separadorArquivo": ";",
            "cabecalhoArquivo": "S",
            "camposArquivo": "SRO|CODIGO_ECT|SERVICO|NF|CEP|DESTINATARIO|SITUACAO|DATA_SITUACAO|DATA_POSTAGEM|DATA_PRAZO",
            "tamanhoArquivo": "10"
        }
        if sro_filtro:
            payload_form["sro"] = sro_filtro.strip()
        else:
            payload_form["data_inicio"] = _norm_ymd(data_ini)
            payload_form["data_fim"] = _norm_ymd(data_fim)

        try:
            r_ws = requests.post(
                "http://www.portalpostal.com.br/Cliente/Servicos/ws_consulta_postagem.jsp",
                data=payload_form,
                timeout=20
            )
            txt = r_ws.text.strip()
            if txt.startswith("ERRO:"):
                sanitized = txt.replace(senha, "***").replace(usuario, "***")
                return 200, {"sucesso": False, "erro": sanitized}

            linhas = [l.strip() for l in txt.splitlines() if l.strip()]
            if len(linhas) <= 1:
                return 200, {"sucesso": True, "registros": [], "total": 0}

            cols = [c.strip().upper() for c in linhas[0].split(";")]
            registros = []
            for ln in linhas[1:]:
                vals = [v.strip() for v in ln.split(";")]
                item = {cols[idx]: (vals[idx] if idx < len(vals) else "") for idx in range(len(cols))}
                sro_cod = (item.get("SRO") or "").upper()
                if not sro_cod:
                    continue
                existe = sro_cod in codigos_gestor
                registros.append({
                    "sro": sro_cod,
                    "codigo_ect": item.get("CODIGO_ECT") or "",
                    "servico": item.get("SERVICO") or "",
                    "nf": item.get("NF") or "",
                    "cep": item.get("CEP") or "",
                    "destinatario": item.get("DESTINATARIO") or "",
                    "situacao": item.get("SITUACAO") or "",
                    "data_situacao": item.get("DATA_SITUACAO") or "",
                    "data_postagem": item.get("DATA_POSTAGEM") or "",
                    "data_prazo": item.get("DATA_PRAZO") or "",
                    "origem": "GESTOR" if existe else "PORTAL POSTAL"
                })

            return 200, {
                "sucesso": True,
                "total_portal_postal": len(registros),
                "total_gestor": sum(1 for r in registros if r["origem"] == "GESTOR"),
                "total_externos": sum(1 for r in registros if r["origem"] == "PORTAL POSTAL"),
                "registros": registros
            }
        except Exception as e:
            return 500, {"sucesso": False, "error": str(e)}

    # =========================================================================
    # 9. HANDLER: danfe-simplificada (ReportLab 100x160mm = 283x453pt)
    # =========================================================================
    @staticmethod
    def handle_danfe_simplificada(body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        dados = (body or {}).get("danfe") or {}
        if not dados:
            return 400, {"error": "Dados para geracao da DANFE Simplificada nao fornecidos."}

        chave_limpa = re.sub(r"\D", "", str(dados.get("chaveNfe") or ""))
        if len(chave_limpa) != 44:
            return 400, {"ok": False, "error": "CHAVE_NFE_AUSENTE", "message": f"Chave possui {len(chave_limpa)} digitos."}

        try:
            from reportlab.pdfgen import canvas as rl_canvas
            from reportlab.graphics.barcode import code128

            W, H = 283.0, 453.0
            buf = BytesIO()
            c = rl_canvas.Canvas(buf, pagesize=(W, H))

            def draw_text_top(txt: str, x: float, y_top: float, size: float, bold: bool = False):
                c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
                c.drawString(x, H - y_top - size, str(txt or ""))

            def draw_line_top(x1: float, y1: float, x2: float, y2: float, width: float = 1.0):
                c.setLineWidth(width)
                c.line(x1, H - y1, x2, H - y2)

            # 1. Titulo
            c.setLineWidth(1.0)
            c.rect(20, H - 16 - 24, 243, 24, stroke=1, fill=0)
            draw_text_top("DANFE Simplificado", 64, 21, 14, bold=True)

            # 2. Barcode Code128 da Chave (Centralizado)
            bc = code128.Code128(chave_limpa, barHeight=42, barWidth=0.68)
            x_bc = max(10.0, (W - bc.width) / 2.0)
            bc.drawOn(c, x_bc, H - 50 - 45)

            # 3. Chave & Protocolo
            draw_text_top("CHAVE DE ACESSO", 107.6, 102.8, 7, bold=True)
            draw_text_top(chave_limpa, 48.0, 112.0, 6.8, bold=False)

            draw_text_top("PROTOCOLO DE AUTORIZAÇÃO", 86.3, 123.8, 7, bold=True)
            prot_str = dados.get("nProt") or "223260101536353"
            dh_str = dados.get("dhRecbto") or dados.get("dhEmi") or datetime.now().strftime("%d/%m/%Y %H:%M")
            draw_text_top(f"{prot_str}  {dh_str}", 75.0, 133.0, 7, bold=False)
            draw_line_top(20, 148, 263, 148, 1)

            # 4. Emitente
            draw_text_top("DADOS DO EMITENTE:", 102.8, 149.3, 7, bold=True)
            emit = dados.get("emitente") or {}
            draw_text_top("Nome/Razão", 21, 160.8, 7)
            draw_text_top(str(emit.get("nome") or "ASSOCIACAO SHALOM")[:38], 89, 160.8, 7)
            draw_text_top("Endereço:", 21, 169.0, 7)
            end_emit = f"{emit.get('logradouro') or 'ESTRADA DO AQUIRAZ'}, {emit.get('numero') or '501'}, {emit.get('bairro') or 'LAGOA DO JUNCO'}"
            draw_text_top(end_emit[:42], 61, 169.0, 7)
            draw_text_top("Cidade:", 21, 188.8, 7)
            draw_text_top(str(emit.get("cidade") or "AQUIRAZ"), 61, 188.8, 7)
            draw_text_top("CEP:", 21, 197.8, 7)
            draw_text_top(str(emit.get("cep") or "61700-000"), 61, 197.8, 7)
            draw_text_top("UF:", 176.7, 197.8, 7)
            draw_text_top(str(emit.get("uf") or "CE"), 188, 197.8, 7)
            draw_text_top("CPF/CNPJ:", 21, 207.8, 7)
            draw_text_top(re.sub(r"\D", "", str(emit.get("cnpj") or "07044456000364")), 75, 207.8, 7)
            draw_text_top("IE:", 179.4, 207.8, 7)
            draw_text_top(str(emit.get("ie") or "068937741"), 188, 207.8, 7)
            draw_line_top(20, 221, 263, 221, 1)

            # 5. Dados Gerais NF-e
            draw_text_top("DADOS GERAIS DA NF-e:", 98.5, 222.3, 7, bold=True)
            draw_text_top("Tipo de operação (0 - entrada / 1 - saída): 1", 21, 233.8, 7, bold=True)
            draw_text_top("Número-Série:", 21, 243.8, 7)
            draw_text_top(f"{dados.get('nNF') or ''} - {dados.get('serie') or '1'}", 75, 243.8, 7)
            draw_text_top("Emissão:", 21, 253.8, 7)
            draw_text_top(str(dados.get("dhEmi") or dh_str), 75, 253.8, 7)
            draw_line_top(20, 269, 263, 269, 1)

            # 6. Destinatario
            draw_text_top("DADOS DO DESTINATÁRIO:", 94.2, 270.3, 7, bold=True)
            dest = dados.get("destinatario") or {}
            draw_text_top("Nome/Razão", 21, 281.8, 7)
            draw_text_top(str(dest.get("nome") or "Cliente")[:38], 89, 281.8, 7)
            draw_text_top("Endereço:", 21, 290.0, 7)
            end_dest = f"{dest.get('logradouro') or ''}, {dest.get('numero') or 'S/N'}"
            draw_text_top(end_dest[:42], 61, 290.0, 7)
            draw_text_top("Cidade:", 21, 309.8, 7)
            draw_text_top(str(dest.get("cidade") or ""), 61, 309.8, 7)
            draw_text_top("CEP:", 21, 318.8, 7)
            draw_text_top(str(dest.get("cep") or ""), 61, 318.8, 7)
            draw_text_top("UF:", 176.7, 318.8, 7)
            draw_text_top(str(dest.get("uf") or ""), 188, 318.8, 7)
            draw_text_top("CPF/CNPJ:", 21, 328.8, 7)
            draw_text_top(re.sub(r"\D", "", str(dest.get("cpfCnpj") or "")), 61, 328.8, 7)
            draw_line_top(20, 339.5, 263, 339.5, 1)

            # 7. Valor Total
            draw_text_top("Valor Total da Nota Fiscal", 20, 342.3, 7, bold=True)
            v_nf = float(dados.get("vNF") or 0.0)
            draw_text_top(f"{v_nf:.2f}".replace(".", ","), 132, 342.8, 7)
            draw_line_top(20, 354.5, 263, 354.5, 1)

            # 8. Rodape
            draw_text_top(f"Emissão em Contingência (0 - Não / 1 - Sim): {dados.get('contingencia') or '0'}", 21, 356.8, 7)
            draw_text_top("Protocolo", 21, 366.8, 7)
            draw_text_top(str(prot_str), 75, 366.0, 7)
            draw_line_top(20, 380.5, 263, 380.5, 1)

            c.showPage()
            c.save()
            pdf_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return 200, {"sucesso": True, "pdfBase64": pdf_b64}
        except Exception as e:
            logger.exception("Erro ao gerar DANFE Simplificada:")
            return 500, {"ok": False, "error": "ERRO_GERACAO_DANFE", "message": str(e)}

    # =========================================================================
    # 10. HANDLER: omie-pedidos & omie-pedido-detalhe
    # =========================================================================
    @staticmethod
    def handle_omie_pedidos(query_params: Dict[str, List[str]]) -> Tuple[int, Any]:
        action = query_params.get("action", [""])[0]
        num_nf_param = query_params.get("numero_nf", [""])[0]
        limite = int(query_params.get("limite", ["15"])[0] or 15)
        app_key, app_secret = _get_omie_creds()

        if action == "consultar_nfe" and num_nf_param:
            try:
                r_nf = requests.post(
                    "https://app.omie.com.br/api/v1/produtos/nfconsultar/",
                    json={
                        "call": "ListarNF",
                        "app_key": app_key,
                        "app_secret": app_secret,
                        "param": [{"pagina": 1, "registros_por_pagina": 10, "numero_nfe": num_nf_param}]
                    },
                    timeout=15
                )
                d_nf = r_nf.json()
                nfs = d_nf.get("nfCadastro") or []
                nf_enc = next((n for n in nfs if str((n.get("ide") or {}).get("nNF") or "").strip() == num_nf_param.strip()), nfs[0] if nfs else None)
                if not nf_enc:
                    return 404, {"error": "NF nao encontrada no Omie"}
                ide = nf_enc.get("ide") or {}
                compl = nf_enc.get("compl") or {}
                dest = nf_enc.get("nfDestInt") or {}
                total = nf_enc.get("total") or {}
                chave = re.sub(r"\D", "", str(compl.get("cChaveNFe") or ""))
                return 200, {
                    "status": "success",
                    "dadosFiscais": {
                        "chave_nfe": chave,
                        "numero_nf": str(ide.get("nNF") or num_nf_param),
                        "serie": str(ide.get("serie") or "1"),
                        "valor_total": float(total.get("vNF") or 0),
                        "protocolo_autorizacao": compl.get("nProt") or ide.get("nProt"),
                        "data_emissao": f"{ide.get('dEmi') or ''} {ide.get('hEmi') or ''}".strip(),
                        "destinatario": {
                            "nome": dest.get("cRazao") or "CLIENTE OMIE",
                            "cpfCnpj": re.sub(r"\D", "", str(dest.get("cnpj_cpf") or "")),
                            "logradouro": dest.get("logradouro") or "",
                            "numero": dest.get("numero") or "S/N",
                            "bairro": dest.get("bairro") or "",
                            "cidade": dest.get("cidade") or "",
                            "uf": dest.get("uf") or "",
                            "cep": re.sub(r"\D", "", str(dest.get("cep") or ""))
                        }
                    }
                }
            except Exception as e:
                return 500, {"error": str(e)}

        return 200, []

    # =========================================================================
    # 11. DISPATCHER UNIFICADO PARA QUALQUER FUNCAO NETLIFY / CORREIOS BRIDGE
    # =========================================================================
    @staticmethod
    def dispatch_function(func_name: str, method: str, query_params: Dict[str, List[str]], body: Dict[str, Any]) -> Tuple[int, Any]:
        fn = func_name.strip("/").lower()
        if fn == "auth-login":
            return 200, {"authenticated": True, "success": True}
        if fn == "turso-db":
            return CorreiosHubService.handle_turso_db(method, query_params, body)
        if fn == "omie-sync-bronze-prata":
            return CorreiosHubService.handle_omie_sync_bronze_prata(query_params, body)
        if fn == "correios-prepostagem":
            return CorreiosHubService.handle_correios_prepostagem(body)
        if fn == "correios-rotulo":
            return CorreiosHubService.handle_correios_rotulo(body)
        if fn == "correios-cancelar":
            return CorreiosHubService.handle_correios_cancelar(body, query_params)
        if fn == "lista-postagem":
            return CorreiosHubService.handle_lista_postagem(method, query_params, body)
        if fn == "sro-rastro-consulta":
            return CorreiosHubService.handle_sro_rastro_consulta(query_params)
        if fn == "portalpostal-rastreio":
            return CorreiosHubService.handle_portalpostal_rastreio(query_params)
        if fn == "danfe-simplificada":
            return CorreiosHubService.handle_danfe_simplificada(body)
        if fn == "total-express":
            try:
                import base64
                import sqlite3
                from pathlib import Path
                from services.total_express_service import TotalExpressService
                action = (query_params.get("action", [None])[0]) or body.get("action") or "registrar"
                db_path = TotalExpressService.get_db_path()
                if action == "registrar":
                    pedido = body.get("pedido") or body
                    key = str(pedido.get("chave_nfe") or "").strip()
                    number = str(pedido.get("numero_pedido") or pedido.get("numero_remessa") or pedido.get("pedido") or "").strip()
                    if db_path.exists():
                        with sqlite3.connect(db_path) as conn:
                            if key and len(key) == 44:
                                existing = conn.execute("SELECT pedido, awb, status FROM total_express_encomendas WHERE documento_fiscal LIKE ? LIMIT 1", (f"%{key}%",)).fetchone()
                            else:
                                existing = conn.execute("SELECT pedido, awb, status FROM total_express_encomendas WHERE pedido = ? LIMIT 1", (number,)).fetchone()
                        if existing and (existing[1] or existing[2] in ("REGISTRADO", "PARCIAL", "ENVIANDO")):
                            return 409, {"sucesso": False, "duplicado": True, "erro": f"Encomenda já registrada ou em processamento (pedido {existing[0]}, AWB {existing[1] or 'pendente'})."}
                    response = TotalExpressService.registrar_encomenda(pedido)
                    status = int(response.get("httpStatus") or (200 if response.get("sucesso") else 400))
                    if response.get("sucesso"):
                        return (206 if response.get("parcial") else 200), response
                    return status, response
                if action == "listar":
                    return 200, {"sucesso": True, "encomendas": TotalExpressService.listar_encomendas()}
                if action == "cancelar":
                    awb = str(body.get("awb") or query_params.get("awb", [""])[0] or "").strip()
                    pedido = str(body.get("pedido") or query_params.get("pedido", [""])[0] or "").strip()
                    motivo = str(body.get("motivo") or "Cancelamento operacional").strip()
                    if db_path.exists():
                        with sqlite3.connect(db_path) as conn:
                            if awb:
                                conn.execute("UPDATE total_express_encomendas SET status = 'CANCELADO', erro = ? WHERE awb = ?", (f"Cancelado: {motivo}", awb))
                            elif pedido:
                                conn.execute("UPDATE total_express_encomendas SET status = 'CANCELADO', erro = ? WHERE pedido = ?", (f"Cancelado: {motivo}", pedido))
                            conn.commit()
                    return 200, {"sucesso": True, "mensagem": f"Etiqueta Total Express {awb or pedido} cancelada localmente com sucesso."}
                if action == "etiqueta":
                    awb = str(body.get("awb") or query_params.get("awb", [""])[0] or "").strip()
                    entry = next((item for item in TotalExpressService.listar_encomendas() if item.get("awb") == awb), None)
                    payload = {}
                    if entry:
                        payload = json.loads(entry.get("payload_json") or "{}")
                    else:
                        # Tenta buscar no Turso DB se não achou no cache local da instância
                        turso_res = execute_turso_query("""
                            SELECT pedido, numero_nf, chave_nfe, destinatario, logradouro, numero, complemento, bairro, cidade, uf, cep, valor_frete, dados_fiscais_json
                            FROM prepostagens
                            WHERE codigo_objeto = ? OR id_prepostagem = ? LIMIT 1
                        """, [awb, f"TOTAL_EXPRESS_{awb}"])
                        if turso_res and turso_res.get("rows"):
                            r = turso_res["rows"][0]
                            dados_fiscais = json.loads(_cell_val(r[12]) or "{}") if len(r) > 12 and _cell_val(r[12]) else {}
                            payload = {
                                "encomendas": [{
                                    "pedido": _cell_val(r[0]),
                                    "destinatario": {
                                        "nome": _cell_val(r[3]),
                                        "endereco": {
                                            "logradouro": _cell_val(r[4]),
                                            "numero": _cell_val(r[5]),
                                            "complemento": _cell_val(r[6]),
                                            "bairro": _cell_val(r[7]),
                                            "cidade": _cell_val(r[8]),
                                            "estado": _cell_val(r[9]),
                                            "cep": _cell_val(r[10])
                                        }
                                    },
                                    "docFiscal": {
                                        "nfe": [{
                                            "nfeNumero": _cell_val(r[1]),
                                            "nfeChave": _cell_val(r[2]),
                                            "nfeValTotal": dados_fiscais.get("vNF") or 0.0
                                        }]
                                    }
                                }]
                            }
                            entry = {
                                "awb": awb,
                                "rota": "05-TZL-SP-LOC-[I88]",
                                "codigo_barras": awb,
                                "tipo_servico": "EXP",
                                "pedido": _cell_val(r[0])
                            }

                    req_pedido = body.get("pedido") or body.get("item") or {}
                    if not entry and not req_pedido:
                        return 404, {"sucesso": False, "erro": "AWB não encontrada localmente."}

                    shipment = (payload.get("encomendas") or [{}])[0]
                    dest_obj = shipment.get("destinatario") or req_pedido.get("destinatario") or {}
                    address = dest_obj.get("endereco") or req_pedido.get("endereco") or {}
                    doc_fiscal = (shipment.get("docFiscal", {}).get("nfe") or [{}])[0]

                    # Enriquecimento via omie_expedicoes_prata se faltar logradouro ou bairro
                    ped_val = str((entry or {}).get("pedido") or req_pedido.get("numero_pedido") or req_pedido.get("pedido") or "").strip()
                    nf_val = str(doc_fiscal.get("nfeNumero") or req_pedido.get("numero_nf") or "").strip()
                    ch_val = str(doc_fiscal.get("nfeChave") or req_pedido.get("chave_nfe") or "").strip()
                    if (not address.get("logradouro") or not address.get("bairro")) and (ped_val or nf_val or ch_val):
                        try:
                            prata_fb = execute_turso_query("""
                                SELECT logradouro, numero, complemento, bairro, cidade, uf, cep, cliente_nome
                                FROM omie_expedicoes_prata
                                WHERE (numero_pedido = ? AND numero_pedido != '')
                                   OR (numero_nf = ? AND numero_nf != '')
                                   OR (chave_nfe = ? AND chave_nfe != '')
                                LIMIT 1
                            """, [ped_val, nf_val, ch_val])
                            if prata_fb and prata_fb.get("rows"):
                                prow = prata_fb["rows"][0]
                                if not address.get("logradouro"):
                                    address["logradouro"] = _cell_val(prow[0]) or ""
                                if not address.get("numero"):
                                    address["numero"] = _cell_val(prow[1]) or ""
                                if not address.get("complemento"):
                                    address["complemento"] = _cell_val(prow[2]) or ""
                                if not address.get("bairro"):
                                    address["bairro"] = _cell_val(prow[3]) or ""
                                if not address.get("cidade"):
                                    address["cidade"] = _cell_val(prow[4]) or ""
                                if not address.get("estado"):
                                    address["estado"] = _cell_val(prow[5]) or ""
                                if not address.get("cep"):
                                    address["cep"] = _cell_val(prow[6]) or ""
                                if not dest_obj.get("nome"):
                                    dest_obj["nome"] = _cell_val(prow[7]) or ""
                        except Exception as e_pr:
                            logger.warning(f"Fallback omie_expedicoes_prata falhou: {e_pr}")

                    dados_etiqueta = {
                        "awb": awb,
                        "rota": (entry or {}).get("rota") or req_pedido.get("rota") or "05-TZL-SP-LOC-[I88]",
                        "codigoBarras": (entry or {}).get("codigo_barras") or req_pedido.get("codigoBarras") or awb,
                        "tipoServico": (entry or {}).get("tipo_servico") or req_pedido.get("tipoServico") or "STD",
                        "pedido": (entry or {}).get("pedido") or req_pedido.get("numero_pedido") or req_pedido.get("pedido") or "",
                        "destinatario": {
                            "nome": dest_obj.get("nome") or req_pedido.get("cliente_nome") or "",
                            "cpfCnpj": dest_obj.get("cpfCnpj") or req_pedido.get("cliente_cpf_cnpj") or "",
                            "endereco": address
                        },
                        "numero_nf": doc_fiscal.get("nfeNumero") or req_pedido.get("numero_nf") or "",
                        "serie_nf": doc_fiscal.get("nfeSerie") or req_pedido.get("serie_nf") or "1",
                        "chave_nfe": doc_fiscal.get("nfeChave") or req_pedido.get("chave_nfe") or "",
                        "valor_nf": doc_fiscal.get("nfeValTotal") or req_pedido.get("valor_nf") or 0.0,
                        "data_emissao": doc_fiscal.get("nfeData") or req_pedido.get("data_emissao") or "",
                        "peso_kg": shipment.get("peso") or req_pedido.get("peso_kg") or 0.830,
                        "volumes": shipment.get("volumes") or req_pedido.get("volumes") or 1
                    }
                    pdf_bytes = TotalExpressService.gerar_etiqueta(dados_etiqueta)
                    return 200, {"sucesso": True, "pdfBase64": base64.b64encode(pdf_bytes).decode("ascii"), "mimeType": "application/pdf"}
                return 400, {"sucesso": False, "erro": f"Ação '{action}' inválida para total-express."}
            except Exception as exc:
                logger.exception("Erro na integração Total Express")
                return 500, {"sucesso": False, "erro": str(exc)}
        if fn == "jt-express":
            try:
                from services.jt_express_service import JTExpressService
                action = (query_params.get("action", [None])[0]) or body.get("action") or "addOrder"
                if action == "addOrder":
                    ped = body.get("pedido") or body
                    res_jt = JTExpressService.criar_pedido(ped)
                    status_c = 200 if res_jt.get("sucesso") else 400
                    return status_c, res_jt
                elif action == "getOrders":
                    serial_numbers = body.get("serialNumber")
                    if serial_numbers is None:
                        serial_numbers = query_params.get("serialNumber", [])
                    result = JTExpressService.consultar_pedidos(serial_numbers, command=body.get("command", 1))
                    return int(result.get("httpStatus") or 502), result
                elif action == "quote":
                    result = JTExpressService.cotar_frete(
                        body.get("originZipCode", ""), body.get("destinationZipCode", ""),
                        body.get("weight"), body.get("insuredAmount"),
                        goods_type_code=body.get("goodsTypeCode", "bm000006"),
                        product_type_code=body.get("productTypeCode", "EZ"),
                    )
                    return int(result.get("httpStatus") or 502), result
                elif action in ("printOrder", "etiqueta"):
                    bill_code = str(body.get("billCode") or query_params.get("billCode", [""])[0])
                    size = body.get("printSize", 0)
                    result = JTExpressService.obter_etiqueta(bill_code, print_size=size)
                    return int(result.get("httpStatus") or 502), result
                elif action == "trace":
                    bill_code = str(body.get("billCode") or query_params.get("billCode", [""])[0])
                    res_tr = JTExpressService.rastrear_objeto(bill_code)
                    return int(res_tr.get("httpStatus") or (200 if res_tr.get("sucesso") else 502)), res_tr
                elif action == "cancelOrder":
                    bill_code = str(body.get("billCode") or query_params.get("billCode", [""])[0])
                    tx_id = str(body.get("txlogisticId") or query_params.get("txlogisticId", [""])[0])
                    motivo = str(body.get("reason") or "Cancelamento operacional")
                    res_cn = JTExpressService.cancelar_pedido(bill_code, tx_id, motivo)
                    return 200, res_cn
                return 400, {"sucesso": False, "erro": f"Acao '{action}' invalida para jt-express"}
            except Exception as e_jt:
                return 500, {"sucesso": False, "erro": str(e_jt)}
        if fn == "frenet":
            try:
                from services.frenet_service import cotar_frete_frenet
                cep = str(query_params.get("cep", [""])[0] or body.get("cep") or "").strip()
                v_itens = float(query_params.get("valor", [query_params.get("v_itens", [45.0])[0]])[0] or body.get("valor") or 45.0)
                peso = float(query_params.get("peso", [0.3])[0] or body.get("peso") or 0.3)
                res_fr = cotar_frete_frenet(cep, valor_itens=v_itens, peso_kg=peso)
                return 200, res_fr
            except Exception as e_fr:
                return 500, {"disponivel": False, "error": str(e_fr), "cotacoes": []}
        if fn in ("omie-pedidos", "omie-pedido-detalhe"):
            return CorreiosHubService.handle_omie_pedidos(query_params)
        return 404, {"error": f"Funcao '{func_name}' nao encontrada no CorreiosHubService."}
