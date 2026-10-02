# -*- coding: utf-8 -*-
"""
services/__init__.py - Módulo de Serviços do Omie ERP
===================================================
Pacote de serviços com módulos para cada área de integração.

Módulos disponíveis:
- clientes.py: Clientes e Fornecedores
- produtos.py: Catálogo e características
- vendas.py: Pedidos e etapas de venda
- estoque.py: Estoque e almoxarifados
- remessas.py: Remessas de mercadorias

Idioma: Português do Brasil (PT-BR)
"""

# Importações para facilitar uso
from services.clientes import ClientesService
from services.produtos import ProdutosService
from services.vendas import VendasService
from services.estoque import EstoqueService
from services.remessas import RemessasService

__all__ = [
    "ClientesService",
    "ProdutosService",
    "VendasService",
    "EstoqueService",
    "RemessasService",
]