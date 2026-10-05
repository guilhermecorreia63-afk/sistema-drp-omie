# -*- coding: utf-8 -*-
"""
api/index.py - Vercel Serverless Function Handler para todas as APIs (/api/*)
"""
import sys
import os

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from server import DRPRequestHandler

class handler(DRPRequestHandler):
    def do_GET(self):
        url_path = self.path.split('?')[0].rstrip('/')
        if url_path == '/api/cron_sync':
            self.handle_api_cron_sync()
        elif url_path == '/api/blacklist':
            self.handle_api_blacklist_get()
        elif url_path in ['/api/remessas/status_transito', '/api/remessas/status']:
            self.handle_api_remessas_status_transito_get()
        elif url_path == '/api/remessas/listar':
            self.handle_api_remessas_listar()
        elif url_path == '/api/depara':
            self.handle_api_depara_get()
        elif url_path == '/api/depositos':
            self.handle_api_depositos_get()
        elif url_path == '/api/depositos/historico':
            self.handle_api_depositos_historico()
        elif url_path in ['/api/depositos/enderecos', '/api/producao']:
            if url_path == '/api/producao':
                self.handle_api_producao_get()
            else:
                self.handle_api_depositos_enderecos_get()
        elif url_path == '/api/combo/detalhes':
            self.handle_api_combo_detalhes()
        else:
            self._send_json({"success": False, "message": f"Endpoint GET não encontrado: {self.path}"}, status=404)
