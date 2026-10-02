# -*- coding: utf-8 -*-
"""
services/remessas.py - Serviço de Remessas de Mercadorias (Omie ERP)
====================================================================
Cobre:
- Incluir remessa para bonificação
- Incluir remessa para doação
- Reenvios de devoluções

Idioma: Português do Brasil (PT-BR)
"""

from typing import List, Dict, Any, Optional
from omie_client import create_omie_client
from database import get_database


class RemessasService:
    """Serviço para operações de remessas de mercadorias."""

    def __init__(self, empresa: str = "matriz"):
        self.client = create_omie_client(empresa)
        self.db = get_database()

    def incluir_remessa(
        self,
        tipo_remessa: str,
        itens: List[Dict[str, Any]],
        observacao: str = "",
        cliente_receptor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Inclui uma remessa de mercadorias.

        Tipos:
        - "bonificacao": Remessa para bonificação
        - "doacao": Remessa para doação
        - "devolucao": Reenvio de devolução

        Args:
            tipo_remessa: Tipo da remessa (bonificacao, doacao, devolucao)
            itens: Lista de itens com SKU e quantidade
            observacao: Texto livre para observação
            cliente_receptor: CPF/CNPJ do cliente receptivo (para doação)

        Returns:
            Dicionário com resultado da operação.
        """
        payload = {
            "tipo_remessa": tipo_remessa,
            "itens": itens,
            "observacao": observacao,
        }
        if cliente_receptor:
            payload["cliente_receptor"] = cliente_receptor

        try:
            resultado = self.client.call_api("produtos/remessa", payload=payload)
            return resultado
        except Exception as error:
            return {"sucesso": False, "erro": str(error)}

    def reconectar_devolucao(self, devolucao_id: int, nota_entrada_id: Optional[int] = None) -> bool:
        """Renova/Reenvia uma devolução já processada."""
        return self.db.inserir_reenvio(devolucao_id, "reenvio", nota_entrada_id)

    def listar_remessas(self, limite: int = 100) -> List[Dict[str, Any]]:
        """Lista remessas do banco de dados."""
        return self.db.get_reenvios(limite)

    def registrar_remessa(self, devolucao_id: int, tipo_remessa: str, nota_entrada_id: int) -> bool:
        """Registra uma remessa no banco local."""
        return self.db.inserir_reenvio(devolucao_id, tipo_remessa, nota_entrada_id)