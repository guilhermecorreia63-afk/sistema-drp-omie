"""Shared localhost-only HTTP adapter for the freight dashboard."""

import json
import posixpath
from datetime import date
from urllib.parse import parse_qs, urlparse, unquote

from services.frete_financeiro_service import Store, dashboard, json_safe, start_sync


def private_cache_path(path):
    decoded = posixpath.normpath(unquote(urlparse(path).path).replace('\\', '/')).lower()
    return decoded == '/data/frete_financeiro' or decoded.startswith('/data/frete_financeiro/')


def handle(handler, method):
    path = urlparse(handler.path).path.rstrip("/")
    if not path.startswith("/api/frete_financeiro/"):
        return False

    def send(status, data):
        raw = json.dumps(json_safe(data), ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Cache-Control", "no-store, private")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Content-Length", str(len(raw)))
        handler.end_headers()
        handler.wfile.write(raw)
        return True

    origin = handler.headers.get("Origin")
    host = handler.headers.get("Host", "")
    if handler.client_address[0] not in ("127.0.0.1", "::1"):
        return send(403, {"erro": "Painel financeiro restrito ao localhost nesta etapa."})
    if origin and (urlparse(origin).hostname not in ("localhost", "127.0.0.1", "::1") or urlparse(origin).netloc != host):
        return send(403, {"erro": "Origem não autorizada para dados financeiros locais."})
    params = parse_qs(urlparse(handler.path).query)
    try:
        if method == "GET" and path == "/api/frete_financeiro/painel":
            today = date.today()
            start = params.get("inicio", [today.replace(day=1).isoformat()])[0]
            end = params.get("fim", [today.isoformat()])[0]
            return send(200, dashboard(start, end, params.get("departamento", [""])[0], params.get("transportadora", [""])[0]))
        if method == "GET" and path.startswith("/api/frete_financeiro/job/"):
            store = Store()
            job = store.get("jobs", path.rsplit("/", 1)[-1])
            if not job:
                return send(404, {"erro": "Atualização não encontrada."})
            import time
            lock = store.get("settings", "job_lock", {})
            if job["status"] == "running" and lock.get("until", 0) < time.time():
                job = {**job, "status": "failed", "aviso": "Processo anterior interrompido. Os dados foram preservados; uma nova atualização pode retomar."}
            return send(200, job)
        if method == "POST" and path == "/api/frete_financeiro/sincronizar":
            length = int(handler.headers.get("Content-Length") or "0")
            if length <= 0 or length > 4096:
                return send(400, {"erro": "Corpo da solicitação deve conter somente período de consulta."})
            body = json.loads(handler.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                return send(400, {"erro": "Solicitação deve ser objeto JSON."})
            return send(202, start_sync(body.get("inicio", ""), body.get("fim", "")))
        return send(404, {"erro": "Operação financeira não encontrada."})
    except (ValueError, TypeError, UnicodeError):
        return send(400, {"erro": "Período ou solicitação inválidos; use datas ISO e até 31 dias."})
    except Exception as exc:
        return send(500, {"erro": f"Erro local do painel ({type(exc).__name__}); nenhum segredo foi exposto."})
