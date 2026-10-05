# -*- coding: utf-8 -*-
"""
api/index.py - Vercel Serverless Function Entry Point for DRP Omie ERP Backend
"""
import sys
import os

# Adiciona o diretório raiz do projeto ao sys.path para importar server, database, sync_service, etc.
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from server import DRPRequestHandler

# Exporta o handler HTTP que o Vercel Python Runtime utiliza automaticamente
handler = DRPRequestHandler
