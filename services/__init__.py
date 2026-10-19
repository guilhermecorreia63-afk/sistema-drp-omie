# -*- coding: utf-8 -*-
"""
services/__init__.py - Módulo de Serviços do Omie ERP
"""

try:
    from services.consignacao_service import ConsignacaoService
except ImportError:
    ConsignacaoService = None

try:
    from services.clientes import ClientesService
    from services.produtos import ProdutosService
    from services.vendas import VendasService
    from services.estoque import EstoqueService
    from services.remessas import RemessasService
except Exception:
    ClientesService = None
    ProdutosService = None
    VendasService = None
    EstoqueService = None
    RemessasService = None

__all__ = [
    "ConsignacaoService",
    "ClientesService",
    "ProdutosService",
    "VendasService",
    "EstoqueService",
    "RemessasService",
]