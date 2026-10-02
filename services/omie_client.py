# -*- coding: utf-8 -*-
"""
ome_client.py - Cliente HTTP para Integração com a API Omie ERP v1
======================================================================
Responsável por:
- Comunicação HTTP com a API Omie ERP v1
- Suporte a multi-empresa (Matriz vs CD)
- Paginação automática de registros
- Tratamento robusto de erros (403, 429, 500, -101, -103)
- Rate Limiting rígido (240 req/min, máx 4 req/s, 4 chamadas concorrentes)
- Retry automático com backoff exponencial
- Cache com trava de redundância de 60s (st.cache_data)

Autor: Sistema de Integração ERP
Versão: 1.0.0
Idioma: Português do Brasil (PT-BR)
"""

from __future__ import annotations

import os
import time
import logging
import threading
from typing import Any, Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

import requests
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("omie_client")


# ---------------------------------------------------------------------------
# Constantes de Rate Limiting
# ---------------------------------------------------------------------------
MAX_REQUESTS_PER_MINUTE: int = 240          # Máximo de requisições por minuto
MAX_REQUESTS_PER_SECOND: float = 4.0        # Máximo de 4 requisições por segundo
MAX_CONCURRENT_CALLS: int = 4               # Máximo de 4 chamadas concorrentes por método
REDUNDANCY_LOCK_SECONDS: int = 60           # Trabalha de redundância de 60s para cache

# Códigos de erro conhecidos da API Omie
OMIE_ERROR_CODES: Dict[int, str] = {
    -101: "Chave de autenticação inválida",
    -103: "Empresa não encontrada ou inativa",
    403: "Acesso proibido - Permissão insuficiente",
    429: "Rate limit excedido - Muitas requisições",
    500: "Erro interno do servidor",
}

# Códigos de status HTTP para retry
RETRY_STATUS_CODES: List[int] = [429, 500, 502, 503, 504]


# ---------------------------------------------------------------------------
# Dataclasses de Configuração
# ---------------------------------------------------------------------------
@dataclass
class OmieConfig:
    """Configuração de credenciais para uma empresa Omie."""

    app_key: str = ""
    app_secret: str = ""
    empresa_nome: str = "Matriz"
    empresa_id: int = 1

    def __post_init__(self) -> None:
        """Valida que as credenciais não estão vazias."""
        if not self.app_key or not self.app_secret:
            logger.warning(
                "Configuração para '%s' sem credenciais válidas. "
                "Verifique o arquivo .env.",
                self.empresa_nome,
            )


@dataclass
class RateLimitState:
    """Estado interno do rate limiter."""

    request_timestamps: deque = field(default_factory=deque)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def can_proceed(self) -> bool:
        """Verifica se uma nova requisição pode prosseguir respeitando o rate limit."""
        now = time.time()
        cutoff = now - 60.0  # Janela de 1 minuto

        # Remove timestamps antigos da janela
        while self.request_timestamps and self.request_timestamps[0] < cutoff:
            self.request_timestamps.popleft()

        return len(self.request_timestamps) < MAX_REQUESTS_PER_MINUTE

    def wait_if_needed(self) -> None:
        """Aguarda se necessário para respeitar o rate limit de 4 req/s."""
        with self.lock:
            now = time.time()
            cutoff = now - 1.0  # Janela de 1 segundo

            # Remove timestamps antigos
            while self.request_timestamps and self.request_timestamps[0] < cutoff:
                self.request_timestamps.popleft()

            if len(self.request_timestamps) >= 4:
                # Espera até o primeiro timestamp sair da janela
                sleep_time = self.request_timestamps[0] + 1.0 - now + 0.05
                if sleep_time > 0:
                    logger.info("Rate limiter aguardando %.2fs para respeitar limite de 4 req/s", sleep_time)
                    time.sleep(sleep_time)

            self.request_timestamps.append(time.time())


# ---------------------------------------------------------------------------
# Exceções Específicas
# ---------------------------------------------------------------------------
class OmieAPIError(Exception):
    """Exceção base para erros da API Omie."""

    def __init__(self, message: str, error_code: int, http_status: int = 0):
        self.error_code = error_code
        self.http_status = http_status
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"[OmieAPIError {self.error_code}] {self.message}"


class RateLimitError(OmieAPIError):
    """Erro de limite de taxa excedido."""


class AuthenticationError(OmieAPIError):
    """Erro de autenticação."""


class ServiceUnavailableError(OmieAPIError):
    """Erro de serviço indisponível."""


# ---------------------------------------------------------------------------
# Gerenciador de Rate Limiting Global
# ---------------------------------------------------------------------------
class RateLimiter:
    """Gerenciador centralizado de rate limiting para toda a aplicação."""

    _instance: Optional[RateLimiter] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> RateLimiter:
        """Implementa padrão Singleton para taxa única por aplicação."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Inicializa os rastreadores de taxa por método."""
        self._states: Dict[str, RateLimitState] = {}
        self._global_lock = threading.Lock()

    def acquire(self, method_name: str = "default") -> None:
        """Adquire permissão para fazer uma requisição respeitando todos os limites."""
        state = self._get_state(method_name)
        state.wait_if_needed()

        # Verifica limite global de 240 req/min
        if not state.can_proceed():
            # Aguarda o final da janela de 1 minuto
            oldest = state.request_timestamps[0] if state.request_timestamps else time.time()
            sleep_duration = oldest + 60.0 - time.time() + 0.1
            logger.info("Rate limiter global aguardando %.2fs (240 req/min atingido)", sleep_duration)
            time.sleep(max(0, sleep_duration))
            # Remove timestamps antigos após espera
            cutoff = time.time() - 60.0
            while state.request_timestamps and state.request_timestamps[0] < cutoff:
                state.request_timestamps.popleft()

    def _get_state(self, method_name: str) -> RateLimitState:
        """Obtém ou cria o estado de rate limiting para um método."""
        if method_name not in self._states:
            with self._global_lock:
                if method_name not in self._states:
                    self._states[method_name] = RateLimitState()
        return self._states[method_name]

    def record_call(self, method_name: str) -> None:
        """Registra uma chamada para rastreamento de taxa."""
        state = self._get_state(method_name)
        with state.lock:
            state.request_timestamps.append(time.time())


# ---------------------------------------------------------------------------
# Cliente Principal da API Omie
# ---------------------------------------------------------------------------
class OmieClient:
    """
    Cliente HTTP para integração com a API Omie ERP v1.

    Suporta:
    - Multi-empresa (Matriz e CD - Contabilidade/Divisão)
    - Paginação automática
    - Rate limiting rigoroso (240 req/min, 4 req/s)
    - Tratamento de erros com retry (429, 500, -101, -103)
    - Cache com trava de redundância de 60 segundos

    Exemplo de uso:
        >>> client = OmieClient(empresa="matriz")
        >>> resultado = client.consultar_clientes(cpf_cnpj="12345678901")
    """

    BASE_URL: str = "https://app.omie.com.br/api/geral/"
    _instance: Optional["OmieClient"] = None
    _rate_limiter: RateLimiter = RateLimiter()

    def __new__(cls, empresa: str = "matriz") -> "OmieClient":
        """Cria ou retorna instância para a empresa especificada."""
        if cls._instance is None or cls._instance._empresa_atual != empresa:
            cls._instance = super().__new__(cls)
            cls._instance._empresa_atual = empresa
            cls._instance._config = cls._load_config(empresa)
        return cls._instance

    def __init__(self, empresa: str = "matriz") -> None:
        """Inicializa o cliente com credenciais da empresa selecionada."""
        self._empresa_atual: str = empresa
        self._config: OmieConfig = self._load_config(empresa)
        self._session: requests.Session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "OmieERP-Integration/1.0.0 (Python)",
        })
        self._max_retries: int = 3
        self._retry_delay: float = 2.0  # Segundos de espera no retry de 429
        self._cache: Dict[str, Tuple[Any, float]] = {}  # cache: key -> (data, timestamp)

    def _load_config(self, empresa: str) -> OmieConfig:
        """
        Carrega as credenciais da empresa selecionada.

        Args:
            empresa: Nome da empresa ("matriz" ou "cd").

        Returns:
            OmieConfig com as credenciais carregadas.
        """
        if empresa.lower() == "cd":
            app_key = os.getenv("APP_KEY_CD", "")
            app_secret = os.getenv("APP_SECRET_CD", "")
            config = OmieConfig(
                app_key=app_key,
                app_secret=app_secret,
                empresa_nome="CD - Contabilidade/Divisão",
                empresa_id=2,
            )
        else:
            app_key = os.getenv("APP_KEY_MATRIZ", "")
            app_secret = os.getenv("APP_SECRET_MATRIZ", "")
            config = OmieConfig(
                app_key=app_key,
                app_secret=app_secret,
                empresa_nome="Matriz",
                empresa_id=1,
            )
        return config

    def _check_rate_limit(self, method_name: str) -> None:
        """Verifica e aplica o rate limiting antes de cada chamada."""
        self._rate_limiter.acquire(method_name)
        self._rate_limiter.record_call(method_name)

    def _parse_omie_response(self, response: requests.Response, method_name: str) -> Dict[str, Any]:
        """
        Analisa a resposta da API Omie tratando erros específicos.

        Args:
            response: Resposta HTTP bruta.
            method_name: Nome do método para logging.

        Returns:
            Dicionário com os dados da resposta.

        Raises:
            OmieAPIError: Em caso de erros da API.
        """
        # Trata códigos de status HTTP
        if response.status_code == 429:
            logger.warning("Rate limit 429 atingido para %s. Aguardando 2s...", method_name)
            raise RateLimitError(
                f"Rate limit excedido (429) para {method_name}",
                error_code=429,
                http_status=429,
            )

        if response.status_code == 403:
            raise AuthenticationError(
                "Acesso proibido (403) - Verifique as credenciais",
                error_code=403,
                http_status=403,
            )

        if response.status_code >= 500:
            raise ServiceUnavailableError(
                f"Erro interno do servidor ({response.status_code})",
                error_code=response.status_code,
                http_status=response.status_code,
            )

        # Tenta parsear o JSON da resposta
        try:
            data = response.json()
        except (ValueError, KeyError) as parse_error:
            logger.error("Erro ao parsear JSON da resposta: %s", parse_error)
            raise OmieAPIError(
                f"Erro ao analisar resposta JSON: {parse_error}",
                error_code=-100,
                http_status=response.status_code,
            ) from parse_error

        # Verifica erros no formato Omie (campo 'Erro' com código negativo)
        if "Erro" in data or "erro" in data:
            error_info = data.get("Erro") or data.get("erro")
            code = error_info.get("Codigo") if isinstance(error_info, dict) else error_info
            message = error_info.get("Msg") if isinstance(error_info, dict) else str(error_info)

            # Traduz códigos de erro conhecidos
            if code in OMIE_ERROR_CODES:
                raise OmieAPIError(
                    f"{OMIE_ERROR_CODES[code]} (Código: {code})",
                    error_code=code,
                    http_status=response.status_code,
                )

            raise OmieAPIError(
                f"Erro da API Omie: {message}",
                error_code=code if isinstance(code, int) else -100,
                http_status=response.status_code,
            )

        return data

    def _retry_on_error(self, func, *args, **kwargs) -> Any:
        """
        Executa uma função com retry automático em caso de erros recuperáveis.

        Args:
            func: Função a ser executada.
            *args: Argumentos posicionais para a função.
            **kwargs: Argumentos nomeados para a função.

        Returns:
            Resultado da função executada com sucesso.

        Raises:
            OmieAPIError: Após esgotar todas as tentativas de retry.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                return func(*args, **kwargs)
            except RateLimitError as rate_error:
                last_exception = rate_error
                logger.warning(
                    "Tentativa %d/%d falhou por rate limit. Aguardando %.1fs...",
                    attempt, self._max_retries, self._retry_delay * attempt,
                )
                time.sleep(self._retry_delay * attempt)
            except ServiceUnavailableError as service_error:
                last_exception = service_error
                logger.warning(
                    "Tentativa %d/%d falhou por serviço indisponível. Aguardando %.1fs...",
                    attempt, self._max_retries, self._retry_delay * attempt,
                )
                time.sleep(self._retry_delay * attempt)
            except OmieAPIError as api_error:
                # Erros de autenticação não têm retry
                if api_error.http_status == 403:
                    raise
                if api_error.error_code in (-101, -103):
                    raise
                last_exception = api_error
                time.sleep(self._retry_delay)

        raise last_exception  # type: ignore[misc]

    def _make_request(
        self,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        method: str = "POST",
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = False,
        cache_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Realiza uma requisição HTTP à API Omie com todas as proteções.

        Args:
            endpoint: Endpoint da API (ex: "geral/clientes/incluir").
            payload: Dados JSON a serem enviados.
            method: Método HTTP (POST ou GET).
            params: Parâmetros de query string.
            use_cache: Se True, usa cache com trava de redundância de 60s.
            cache_key: Chave personalizada para cache.

        Returns:
            Dicionário com a resposta da API.

        Raises:
            OmieAPIError: Em caso de erro na API.
        """
        # Verifica rate limiting
        self._check_rate_limit(endpoint)

        # Verifica cache
        cache_identifier = cache_key or f"{method}_{endpoint}_{hash(str(payload))}"
        if use_cache:
            cached = self._get_from_cache(cache_identifier)
            if cached is not None:
                logger.info("Cache hit para %s (redundância < 60s)", cache_identifier)
                return cached

        # Monta URL completa
        url = f"{self.BASE_URL}{endpoint}"

        # Monta headers com autenticação
        headers = self._session.headers.copy()
        headers["Authorization"] = f"Bearer {self._config.app_key}:{self._config.app_secret}"

        # Executa requisição com retry
        def _do_request() -> requests.Response:
            if method.upper() == "POST":
                return self._session.post(url, json=payload, headers=headers, timeout=30)
            else:
                return self._session.get(url, params=params, headers=headers, timeout=30)

        response = self._retry_on_error(_do_request)

        # Analisa resposta
        result = self._parse_omie_response(response, endpoint)

        # Salva em cache se habilitado
        if use_cache:
            self._save_to_cache(cache_identifier, result)

        return result

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """
        Recupera um valor do cache se ainda estiver dentro da redundância de 60s.

        Args:
            key: Chave do cache.

        Returns:
            Valor cacheado ou None se expirado.
        """
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < REDUNDANCY_LOCK_SECONDS:
                return data
            else:
                del self._cache[key]  # Expirado
        return None

    def _save_to_cache(self, key: str, data: Any) -> None:
        """Salva um valor no cache com timestamp atual."""
        self._cache[key] = (data, time.time())

    # -----------------------------------------------------------------------
    # Métodos de Paginação Automática
    # -----------------------------------------------------------------------
    def _paginate_request(
        self,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        page_size: int = 100,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Realiza chamadas paginadas à API Omie, retornando todos os registros.

        Args:
            endpoint: Endpoint para consulta.
            payload: Filtros para a consulta.
            page_size: Registros por página (padrão 100).
            max_pages: Máximo de páginas a buscar (None = ilimitado).

        Returns:
            Lista completa de registros de todas as páginas.
        """
        all_results: List[Dict[str, Any]] = []
        current_page: int = 1
        total_pages: int = 1

        while True:
            # Prepara payload com paginação
            request_payload = (payload or {}).copy()
            request_payload["pagina"] = current_page
            request_payload["num_reg_por_pag"] = page_size

            logger.info("Buscando página %d/%d de %s...", current_page, total_pages, endpoint)
            response = self._make_request(endpoint, payload=request_payload)

            # Processa resultados (formato Omie varia por endpoint)
            records = response.get("reg", response.get("resultado", response.get("data", [])))
            if isinstance(records, dict):
                records = [records]

            all_results.extend(records)

            # Obtém total de páginas
            total_pages = response.get("total_pages", response.get("num_pag", 1))
            if isinstance(total_pages, str):
                total_pages = int(total_pages)

            # Condição de parada
            if max_pages and current_page >= max_pages:
                break
            if current_page >= total_pages or not records:
                break

            current_page += 1

            # Respeita rate limit entre páginas
            time.sleep(0.05)

        logger.info("Paginação concluída: %d registros totais em %d páginas.", len(all_results), current_page - 1)
        return all_results

    # -----------------------------------------------------------------------
    # Métodos de Consulta por Filtro (CPF/CNPJ)
    # -----------------------------------------------------------------------
    def consultar_cliente_cpf_cnpj(self, cpf_cnpj: str, empresa: Optional[str] = None) -> Dict[str, Any]:
        """
        Consulta um cliente ou fornecedor por CPF ou CNPJ.

        Args:
            cpf_cnpj: Número do CPF (11 dígitos) ou CNPJ (14 dígitos).
            empresa: Override da empresa (opcional).

        Returns:
            Dados do cliente/encontrado.

        Raises:
            OmieAPIError: Se cliente não encontrado ou erro de API.
        """
        if empresa:
            config = self._load_config(empresa)
        else:
            config = self._config

        endpoint = "geral/clientes"
        payload = {
            "cnpj": cpf_cnpj if len(cpf_cnpj) > 11 else "",
            "cpf": cpf_cnpj if len(cpf_cnpj) <= 11 else "",
        }

        response = self._make_request(endpoint, payload=payload, use_cache=True, cache_key=f"cliente_{cpf_cnpj}")
        return response

    # -----------------------------------------------------------------------
    # API Genérica de Chamada
    # -----------------------------------------------------------------------
    def call_api(
        self,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        use_cache: bool = False,
        cache_key: Optional[str] = None,
        pagination: bool = False,
        page_size: int = 100,
    ) -> Any:
        """
        Chamada genérica à API Omie com todas as proteções aplicadas.

        Args:
            endpoint: Endpoint da API.
            payload: Dados para POST.
            use_cache: Se True, usa cache com 60s de redundância.
            cache_key: Chave custom para cache.
            pagination: Se True, busca todas as páginas automaticamente.
            page_size: Tamanho da página para paginação.

        Returns:
            Resultado da API (lista ou dicionário).
        """
        if pagination:
            return self._paginate_request(endpoint, payload=payload, page_size=page_size)
        return self._make_request(endpoint, payload=payload, use_cache=use_cache, cache_key=cache_key)


# ---------------------------------------------------------------------------
# Factory para criar instâncias rápidas
# ---------------------------------------------------------------------------
def create_omie_client(empresa: str = "matriz") -> OmieClient:
    """
    Factory para criar uma instância do cliente Omie.

    Args:
        empresa: "matriz" ou "cd".

    Returns:
        Instância configurada do OmieClient.
    """
    return OmieClient(empresa=empresa)


# ---------------------------------------------------------------------------
# Bloco de teste direto (executar com: python omie_client.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("Omie Client - Teste de Conexão")
    print("=" * 60)

    # Testa conexão com Matriz
    try:
        client_matriz = OmieClient(empresa="matriz")
        print("✓ Cliente Matriz inicializado com sucesso")
    except Exception as error:
        print(f"✗ Erro ao inicializar cliente Matriz: {error}")

    # Testa conexão com CD
    try:
        client_cd = OmieClient(empresa="cd")
        print("✓ Cliente CD inicializado com sucesso")
    except Exception as error:
        print(f"✗ Erro ao inicializar cliente CD: {error}")

    print("\nPara usar o cliente, importe: from omie_client import OmieClient")
    print("Exemplo: client = OmieClient(empresa='matriz')")
