# -*- coding: utf-8 -*-
"""
services/estoque.py - Serviço de Estoque e Almoxarifados (Omie ERP)
===============================================================
Cobre:
- Consulta de saldo de estoque (PosicaoEstoque)
- Consulta de CMC (Código de Material por Centro?)
- Ajuste de estoque
- Movimento de estoque
- Locais / Almoxarifados

Idioma: Português do Brasil (PT-BR)
"""

from typing import List, Dict, Any, Optional
from omie_client import create_omie_client
from database import get_database


class EstoqueService:
    """Serviço para operações de estoque e almoxarifados."""

    def __init__(self, empresa: str = "matriz"):
        self.client = create_omie_client(empresa)
        self.db = get_database()

    def consultar_saldo_estoque(self, codigo_sku: str, almoxarifado: Optional[str] = None) -> Dict[str, Any]:
        """Consulta saldo de estoque (PosicaoEstoque) para um SKU."""
        try:
            payload = {"sku": codigo_sku}
            if almoxarifado:
                payload["almoxarifado"] = almoxarifado
            return self.client.call_api("estoque/consulta", payload=payload)
        except Exception:
            return {}

    def consultar_cmc(self, codigo_sku: str) -> Dict[str, Any]:
        """Consulta CMC (Código de Material) do produto."""
        try:
            return self.client.call_api(
                "estoque/consulta",
                payload={"sku": codigo_sku, "tipo": "cmc"},
            )
        except Exception:
            return {}

    def ajustar_estoque(self, codigo_sku: str, quantidade: int, tipo: str = "entrada") -> bool:
        """Realiza ajuste de estoque (entrada ou saída)."""
        payload = {
            "sku": codigo_sku,
            "quantidade": quantidade,
            "tipo": tipo,
        }
        try:
            self.client.call_api("estoque/ajuste", payload=payload)
            return True
        except Exception:
            return False

    def registrar_movimento(self, codigo_sku: str, quantidade: int, tipo_movimento: str, origem: str = "") -> bool:
        """Registra movimento de estoque."""
        data = {
            "codigo_sku": codigo_sku,
            "quantidade": quantidade,
            "tipo_movimento": tipo_movimento,
            "origem": origem,
            "data_movimento": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return self.db.insert("estoque_movimento", data)

    def listar_locais_almoxarifados(self, limite: int = 100) -> List[Dict[str, Any]]:
        """Lista locais/almoxarifados."""
        return self.db.execute(f"SELECT * FROM estoque_locais LIMIT {limite}")