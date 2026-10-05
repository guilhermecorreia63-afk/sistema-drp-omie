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
        super().do_GET()

    def do_POST(self):
        super().do_POST()
