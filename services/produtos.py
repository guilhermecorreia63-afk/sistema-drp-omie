# -*- coding: utf-8 -*-
"""
services/produtos.py - Serviço de Catálogo de Produtos e Características
=========================================================================
Idioma: Português do Brasil (PT-BR)
"""
from typing import List, Dict, Any, Optional
from omie_client import create_omie_client
from database import get_database
class ProdutosService:
    def __init__(self, empresa: str = "matriz"):
        self.client = create_omie_client(empresa)
        self.db = get_database()
    def listar_produtos(self, limite: int = 100) -> List[Dict[str, Any]]:
        return self.db.get_produtos(limite)
    def buscar_por_sku(self, codigo_sku: str) -> Optional[Dict[str, Any]]:
        resultados = self.db.execute("SELECT * FROM produtos WHERE codigo_sku = ? LIMIT 1", (codigo_sku,))
        return resultados[0] if resultados else None
    def incluir_produto(self, codigo_sku: str, descricao: str, familia_id: int = 0) -> bool:
        return self.db.inserir_produto(codigo_sku, descricao, familia_id)
    def listar_familias(self, limite: int = 100) -> List[Dict[str, Any]]:
        return self.db.execute(f"SELECT * FROM familias LIMIT {limite}")

