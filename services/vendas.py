# -*- coding: utf-8 -*-
"""
services/vendas.py - Serviço de Vendas e Pedidos (Omie ERP)
===========================================================
Cobre:
- Listar pedidos por período
- Acompanhar etapas de pedidos (20, 80, 50, 60)
- Gerenciar etapas de pedidos

Idioma: Português do Brasil (PT-BR)
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from omie_client import create_omie_client
from database import get_database


class VendasService:
    """Serviço para operações de vendas e pedidos."""

    def __init__(self, empresa: str = "matriz"):
        self.client = create_omie_client(empresa)
        self.db = get_database()

    def listar_pedidos_por_periodo(self, data_inicio: str, data_fim: str) -> List[Dict[str, Any]]:
        """Lista pedidos entre duas datas."""
        # Tenta obter via API Omie
        try:
            resultado = self.client.call_api(
                "geral/pedidos",
                payload={"data_inicial": data_inicio, "data_final": data_fim},
                pagination=True,
                page_size=100,
            )
            return resultado
        except Exception:
            # Fallback para banco de dados local
            return self.db.get_pedidos_por_periodo(data_inicio, data_fim)

    def acompanhar_etapas(self, etapa: int, limite: int = 100) -> List[Dict[str, Any]]:
        """Acompanha pedidos de acordo com a etapa especificada."""
        return self.db.get_pedidos_por_etapa(etapa, limite)

    def listar_etapas_pedidos(self, pedido_id: int) -> List[Dict[str, Any]]:
        """Lista todas as etapas de um pedido específico."""
        # Usar cliente Omie para consultar etapas
        try:
            return self.client.call_api(
                "pedido/etapas",
                payload={"pedido_id": pedido_id},
                pagination=False,
            )
        except Exception:
            # Fallback para dados armazenados
            return self.db.execute(
                "SELECT * FROM pedido_etapas WHERE pedido_id = ? ORDER BY etapa",
                (pedido_id,),
            )

    def registrar_pedido_na_etapa(self, pedido_id: int, etapa: int, data: str) -> bool:
        """Registra a ocorrência de um pedido em determinada etapa."""
        data_registro = {
            "pedido_id": pedido_id,
            "etapa": etapa,
            "data": data,
        }
        return self.db.insert("pedido_etapas", data_registro)