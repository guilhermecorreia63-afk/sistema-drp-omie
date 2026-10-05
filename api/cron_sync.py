# -*- coding: utf-8 -*-
"""
api/cron_sync.py - Endpoint Vercel Serverless para Cron Jobs (12h20 e 18h30 Fortaleza)
"""
import sys
import os

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from server import DRPRequestHandler

class handler(DRPRequestHandler):
    def do_GET(self):
        self.handle_api_cron_sync()

    def do_POST(self):
        self.handle_api_cron_sync()
