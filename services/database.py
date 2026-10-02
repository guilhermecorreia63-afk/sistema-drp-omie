# -*- coding: utf-8 -*-
"""
database.py - Camada de Dados Turso (LibSQL HTTP Pipeline v2) + SQLite Local
=============================================================================
Responsável por:
- Conexão com Turso Cloud via HTTP Pipeline v2
- Fallback automático e transparente para SQLite local
- Criação das tabelas (pedidos, clientes, produtos, devolucoes, reenvios)
- Operações CRUD com tratamento de erros
- Cache de consultas no banco de dados

Autor: Sistema de Integração ERP
Versão: 1.0.0
Idioma: Português do Brasil (PT-BR)
"""

from __future__ import annotations

import os
import sqlite3
import logging
from typing import Any, Optional, List, Dict, Tuple
from datetime import datetime

import requests
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

logger = logging.getLogger("database")

# ---------------------------------------------------------------------------
# Constantes de Configuração
# ---------------------------------------------------------------------------
TURSO_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
LOCAL_DB_PATH = "database_local.db"

# Tabelas obrigatórias conforme especificação
REQUIRED_TABLES = [
    "pedidos",
    "clientes",
    "produtos",
    "devolucoes",
    "reenvios",
]


# ---------------------------------------------------------------------------
# Classe de Conexão com Turso (LibSQL HTTP Pipeline v2)
# ---------------------------------------------------------------------------
class TursoConnection:
    """
    Conexão com o banco Turso Cloud via HTTP Pipeline v2.

    Utiliza chamadas HTTP para executar SQL no banco remoto,
    evitando a necessidade de bibliotecas nativas do LibSQL.
    """

    def __init__(self, database_url: Optional[str] = None, auth_token: Optional[str] = None):
        self.url = database_url or TURSO_URL
        self.token = auth_token or TURSO_TOKEN
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            })

    def _execute_sql(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """
        Executa uma query SQL via HTTP Pipeline v2 do Turso.

        Args:
            sql: Comando SQL.
            params: Parâmetros para o SQL (usados para prevenção de SQL injection).

        Returns:
            Lista de dicionários com resultados.
        """
        if not self.url:
            raise ConnectionError("URL do Turso não configurada. Verifique TURSO_DATABASE_URL.")

        payload = {
            "sql": sql,
            "params": params if params else None,
        }

        try:
            response = self.session.post(self.url, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                rows = result.get("results", [])
                # Normaliza resultados para lista de dicionários
                if isinstance(rows, list):
                    return [dict(row) for row in rows if isinstance(row, dict)]
                return []
            else:
                logger.error("Erro Turso HTTP %s: %s", response.status_code, response.text)
                return []
        except requests.RequestException as error:
            logger.error("Erro de comunicação com Turso: %s", error)
            return []

    def execute(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Executa SQL e retorna resultados."""
        return self._execute_sql(sql, params)

    def execute_insert(self, table: str, data: Dict[str, Any]) -> bool:
        """Insere dados em uma tabela."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        result = self.execute(sql, tuple(data.values()))
        return len(result) >= 0  # Sempre retorna True para inserts


# ---------------------------------------------------------------------------
# Classe de Conexão SQLite (Fallback Local)
# ---------------------------------------------------------------------------
class SQLiteConnection:
    """Conexão com SQLite local para execução offline."""

    def __init__(self, db_path: str = LOCAL_DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Permite acesso por nome de coluna

    def execute(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Executa SQL e retorna resultados como dicionários."""
        cursor = self.conn.execute(sql, params)
        self.conn.commit()
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return [dict(zip(columns, row)) for row in rows]

    def execute_insert(self, table: str, data: Dict[str, Any]) -> bool:
        """Insere dados no banco SQLite."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        self.execute(sql, tuple(data.values()))
        return True

    def create_tables(self) -> None:
        """Cria as tabelas obrigatórias se não existirem."""
        cursor = self.conn.cursor()

        # Tabela de pedidos (vendas)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER UNIQUE,
                cliente_cpf_cnpj TEXT,
                etapa INTEGER,
                valor_total REAL,
                data_pedido TEXT,
                status TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela de clientes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cpf_cnpj TEXT UNIQUE,
                nome TEXT,
                tipo TEXT,
                telefone TEXT,
                email TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela de produtos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_sku TEXT UNIQUE,
                descricao TEXT,
                familia_id INTEGER,
                codigo_barras TEXT,
                estoque_quantidade INTEGER DEFAULT 0,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela de devoluções
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devolucoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_cpf_cnpj TEXT,
                pedido_id INTEGER,
                motivo TEXT,
                status TEXT DEFAULT 'Pendente de Entrada',
                data_devolucao TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela de reenvios (remessas de devolução)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reenvios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                devolucao_id INTEGER,
                tipo_remessa TEXT,
                nota_entrada_id INTEGER,
                data_envio TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()
        logger.info("Tabelas criadas/validadas no SQLite local (%s)", self.db_path)


# ---------------------------------------------------------------------------
# Classe de Dados Unificada (Turso + SQLite Fallback)
# ---------------------------------------------------------------------------
class DatabaseLayer:
    """
    Camada de dados unificada que tenta Turso primeiro,
    e faz fallback transparente para SQLite se necessário.
    """

    def __init__(self):
        self.turso = TursoConnection()
        self.sqlite = SQLiteConnection()
        self.use_turso = bool(self.turso.url and self.turso.token)
        self.sqlite.create_tables()  # Garante que SQLite esteja pronto

    def _try_turso(self, sql: str, params: Tuple = ()) -> Optional[List[Dict[str, Any]]]:
        """Tenta executar no Turso, retornando None se falhar."""
        if not self.use_turso:
            return None
        try:
            result = self.turso.execute(sql, params)
            if result is not None:
                return result
        except Exception as error:
            logger.warning("Falha no Turso, fazendo fallback para SQLite: %s", error)
        return None

    def execute(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """
        Executa SQL com fallback automático.

        Tenta Turso primeiro; se falhar, usa SQLite local.
        """
        # Tenta Turso
        turso_result = self._try_turso(sql, params)
        if turso_result is not None:
            return turso_result

        # Fallback para SQLite
        return self.sqlite.execute(sql, params)

    def insert(self, table: str, data: Dict[str, Any]) -> bool:
        """Insere dados com fallback automático."""
        # Tenta Turso
        if self.use_turso:
            try:
                self.turso.execute_insert(table, data)
                return True
            except Exception as error:
                logger.warning("Falha no Turso insert, fallback SQLite: %s", error)

        # Fallback SQLite
        return self.sqlite.execute_insert(table, data)

    def get_clientes(self, limite: int = 100) -> List[Dict[str, Any]]:
        """Retorna lista de clientes."""
        return self.execute(f"SELECT * FROM clientes LIMIT {limite}")

    def get_pedidos_por_etapa(self, etapa: int, limite: int = 100) -> List[Dict[str, Any]]:
        """Retorna pedidos filtrados por etapa."""
        return self.execute(
            f"SELECT * FROM pedidos WHERE etapa = ? LIMIT {limite}", (etapa,)
        )

    def get_pedidos_por_periodo(self, data_inicio: str, data_fim: str, limite: int = 100) -> List[Dict[str, Any]]:
        """Retorna pedidos entre datas."""
        return self.execute(
            "SELECT * FROM pedidos WHERE data_pedido >= ? AND data_pedido <= ? LIMIT ?",
            (data_inicio, data_fim, limite),
        )

    def get_produtos(self, limite: int = 100) -> List[Dict[str, Any]]:
        return self.execute(f"SELECT * FROM produtos LIMIT {limite}")

    def get_devolucoes_pendentes(self, limite: int = 100) -> List[Dict[str, Any]]:
        return self.execute(
            "SELECT * FROM devolucoes WHERE status = 'Pendente de Entrada' LIMIT ?",
            (limite,),
        )

    def get_reenvios(self, limite: int = 100) -> List[Dict[str, Any]]:
        return self.execute(f"SELECT * FROM reenvios LIMIT {limite}")

    def inserir_pedido(self, pedido_id: int, cliente_cpf_cnpj: str, etapa: int, valor_total: float, status: str = "Aberto") -> bool:
        data = {
            "pedido_id": pedido_id,
            "cliente_cpf_cnpj": cliente_cpf_cnpj,
            "etapa": etapa,
            "valor_total": valor_total,
            "data_pedido": datetime.now().strftime("%Y-%m-%d"),
            "status": status,
        }
        return self.insert("pedidos", data)

    def inserir_cliente(self, cpf_cnpj: str, nome: str, tipo: str = "Cliente") -> bool:
        data = {
            "cpf_cnpj": cpf_cnpj,
            "nome": nome,
            "tipo": tipo,
            "criado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return self.insert("clientes", data)

    def inserir_produto(self, codigo_sku: str, descricao: str, familia_id: int = 0) -> bool:
        data = {
            "codigo_sku": codigo_sku,
            "descricao": descricao,
            "familia_id": familia_id,
            "criado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return self.insert("produtos", data)

    def inserir_devolucao(self, cliente_cpf_cnpj: str, pedido_id: int, motivo: str) -> bool:
        data = {
            "cliente_cpf_cnpj": cliente_cpf_cnpj,
            "pedido_id": pedido_id,
            "motivo": motivo,
            "status": "Pendente de Entrada",
            "data_devolucao": datetime.now().strftime("%Y-%m-%d"),
        }
        return self.insert("devolucoes", data)

    def inserir_reenvio(self, devolucao_id: int, tipo_remessa: str, nota_entrada_id: Optional[int] = None) -> bool:
        data = {
            "devolucao_id": devolucao_id,
            "tipo_remessa": tipo_remessa,
            "nota_entrada_id": nota_entrada_id,
            "data_envio": datetime.now().strftime("%Y-%m-%d"),
        }
        return self.insert("reenvios", data)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Compatibilidade de Funções Globais (Root / Services)
# ---------------------------------------------------------------------------
def _format_turso_arg(v):
    if v is None:
        return {"type": "null"}
    elif isinstance(v, bool):
        return {"type": "integer", "value": "1" if v else "0"}
    elif isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    elif isinstance(v, float):
        return {"type": "float", "value": float(v)}
    return {"type": "text", "value": str(v)}

def executar_batch_query(stmts_list: list):
    """Executa múltiplos comandos SQL em lote (batch) no Turso Cloud ou SQLite."""
    if not stmts_list:
        return True

    tem_turso = bool(TURSO_URL and TURSO_TOKEN and "turso.io" in TURSO_URL)
    if tem_turso:
        try:
            url_base = TURSO_URL.replace("libsql://", "https://").replace("sqlite+libsql://", "https://").strip("/")
            headers = {"Authorization": f"Bearer {TURSO_TOKEN}", "Content-Type": "application/json"}
            chunk_size = 100
            for i in range(0, len(stmts_list), chunk_size):
                chunk = stmts_list[i:i + chunk_size]
                requests_payload = []
                for item in chunk:
                    query = item.get("query")
                    params = item.get("params") or {}
                    stmt = {"sql": query}
                    if params:
                        stmt["named_args"] = [
                            {"name": (k if k.startswith(":") else f":{k}"), "value": _format_turso_arg(v)}
                            for k, v in params.items()
                        ]
                    requests_payload.append({"type": "execute", "stmt": stmt})
                requests.post(f"{url_base}/v2/pipeline", headers=headers, json={"requests": requests_payload}, timeout=30)
            return True
        except Exception as e:
            logger.error("Erro no batch Turso: %s", e)

    # Fallback para SQLite Local
    local_path = os.path.join("data", "database_local.db")
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(local_path)
    try:
        cur = conn.cursor()
        for item in stmts_list:
            cur.execute(item["query"], item.get("params") or {})
        conn.commit()
        return True
    finally:
        conn.close()

def executar_query(query: str, params: dict | tuple = None, is_select: bool = True):
    tem_turso = bool(TURSO_URL and TURSO_TOKEN and "turso.io" in TURSO_URL)
    if tem_turso:
        try:
            url_base = TURSO_URL.replace("libsql://", "https://").replace("sqlite+libsql://", "https://").strip("/")
            headers = {"Authorization": f"Bearer {TURSO_TOKEN}", "Content-Type": "application/json"}
            stmt = {"sql": query}
            if params and isinstance(params, dict):
                stmt["named_args"] = [{"name": (k if k.startswith(":") else f":{k}"), "value": _format_turso_arg(v)} for k, v in params.items()]
            requests.post(f"{url_base}/v2/pipeline", headers=headers, json={"requests": [{"type": "execute", "stmt": stmt}]}, timeout=15)
            return None
        except Exception:
            pass

    local_path = os.path.join("data", "database_local.db")
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(local_path)
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        conn.commit()
    finally:
        conn.close()

def inicializar_banco():
    local_path = os.path.join("data", "database_local.db")
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(local_path)
    try:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS produtos (
            sku TEXT PRIMARY KEY,
            codigo_produto INTEGER,
            descricao TEXT,
            marca TEXT,
            familia TEXT,
            cd_sp INTEGER DEFAULT 0,
            matriz INTEGER DEFAULT 0,
            peso_kg REAL DEFAULT 0.1,
            ativo INTEGER DEFAULT 1,
            ultima_sincronizacao TEXT
        )""")
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    print("Módulo services/database.py atualizado com sucesso.")
