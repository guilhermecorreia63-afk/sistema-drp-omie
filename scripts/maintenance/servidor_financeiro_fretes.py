"""Isolated local preview; no DRP scheduler and no automatic external synchronization."""

import argparse
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from services.frete_financeiro_http import handle


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "static" / "frete_financeiro"), **kwargs)

    def do_GET(self):
        if not handle(self, "GET"):
            super().do_GET()

    def do_POST(self):
        if not handle(self, "POST"):
            self.send_error(404)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--porta", type=int, default=8898)
    args = parser.parse_args()
    print(f"Financeiro de Fretes: http://127.0.0.1:{args.porta} (somente leitura de fontes externas)", flush=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.porta), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
