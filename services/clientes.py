# -*- coding: utf-8 -*-
"""
services/clientes.py - Serviço de Clientes e Fornecedores (Omie ERP)
======================================================================
Cobre:
- Incluir cliente
- Consultar por CPF/CNPJ
- Listar clientes e fornecedores

Idioma: Português do Brasil (PT-BR)
"""

from typing import List, Dict, Any, Optional
from omie_client import OmieClient, create_omie_client
from database import get_database


class ClientesService:
    """Serviço para operações com clientes e fornecedores."""

    def __init__(self, empresa: str = "matriz"):
        self.client = create_omie_client(empresa)
        self.db = get_database()

    def consultar_por_cpf_cnpj(self, cpf_cnpj: str) -> Dict[str, Any]:
        """Consulta cliente ou fornecedor por CPF ou CNPJ."""
        return self.client.consultar_cliente_cpf_cnpj(cpf_cnpj)

    def listar_clientes(self, limite: int = 100) -> List[Dict[str, Any]]:
        """Lista todos os clientes salvos no banco."""
        return self.db.get_clientes(limite)

    def incluir_cliente(self, cpf_cnpj: str, nome: str, tipo: str = "Cliente") -> bool:
        """Inclui um cliente no banco de dados."""
        return self.db.inserir_cliente(cpf_cnpj, nome, tipo)
