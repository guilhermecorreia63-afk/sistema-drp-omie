"""
Cliente HTTP Central para comunicação com o Omie ERP v1.
Implementa tratamento de erros, rate limiting e paginação automática.
"""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

class OmieClient:
    URL_BASE = "https://app.omie.com.br/api/v1"

    def __init__(self, unidade="MATRIZ"):
        self.unidade = unidade.upper()
        if self.unidade == "CD":
            self.app_key = os.getenv("APP_KEY_CD")
            self.app_secret = os.getenv("APP_SECRET_CD")
        else:
            self.app_key = os.getenv("APP_KEY_MATRIZ")
            self.app_secret = os.getenv("APP_SECRET_MATRIZ")

        if not self.app_key or not self.app_secret:
            # Fallback para chaves genéricas se definidas
            self.app_key = self.app_key or os.getenv("OMIE_APP_KEY") or os.getenv("APP_KEY")
            self.app_secret = self.app_secret or os.getenv("OMIE_APP_SECRET") or os.getenv("APP_SECRET")

    def executar(self, endpoint_relativo: str, call: str, param: list = None, timeout: int = 30, retries: int = 3):
        """Executa chamadas POST na API da Omie com gestão de erros e rate limit."""
        if not self.app_key or not self.app_secret:
            return {"cCodStatus": "-101", "faultstring": f"Credenciais ausentes para a unidade {self.unidade}"}

        url = f"{self.URL_BASE.rstrip('/')}/{endpoint_relativo.strip('/')}/"
        payload = {
            "call": call,
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "param": param or [{}]
        }
        headers = {"Content-Type": "application/json"}

        for tentativa in range(1, retries + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=timeout)

                # HTTP 429 - Limite de 240 req/min estourado
                if resp.status_code == 429:
                    time.sleep(2.0 * tentativa)
                    continue

                if resp.status_code == 200:
                    return resp.json()

                try:
                    return resp.json()
                except Exception:
                    return {"cCodStatus": str(resp.status_code), "faultstring": resp.text}

            except requests.exceptions.RequestException as e:
                if tentativa == retries:
                    return {"cCodStatus": "ERRO_CONEXAO", "faultstring": str(e)}
                time.sleep(1.0 * tentativa)

        return {"cCodStatus": "ERRO_DESCONHECIDO", "faultstring": "Falha na comunicação"}

    def listar_paginado(self, endpoint_relativo: str, call: str, chave_lista: str, param_base: dict = None, max_paginas: int = 50):
        """Percorre as páginas da API trazendo os registros consolidados."""
        pagina = 1
        total_paginas = 1
        todos_itens = []
        p_dict = dict(param_base or {})

        while pagina <= total_paginas and pagina <= max_paginas:
            p_dict["pagina"] = pagina
            p_dict["registros_por_pagina"] = 100
            p_dict["apenas_importado_api"] = p_dict.get("apenas_importado_api", "N")

            res = self.executar(endpoint_relativo, call, [p_dict])

            if "faultstring" in res and res.get("cCodStatus") != "0":
                break

            total_paginas = res.get("total_de_paginas", 1)
            itens = res.get(chave_lista, [])
            if not itens:
                break

            todos_itens.extend(itens)
            pagina += 1
            time.sleep(0.05)  # Intervalo de segurança preventiva contra 429

        return todos_itens