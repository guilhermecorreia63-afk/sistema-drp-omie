"""Read-only financial freight reconciliation. Operational DBs are never updated.

Local SQLite keeps source snapshots/checkpoints, not payment confirmations.
"""

import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import threading
import time
import unicodedata
import uuid
from collections import defaultdict
from contextlib import contextmanager, closing
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "frete_financeiro" / "financeiro.sqlite3"
LOCK = threading.Lock()
ACTIVE_JOB = None
DEFAULT_DEPTS = {"1807684664": "Comercial", "1807684776": "Loja Web / Ecommerce"}


class ReadLimit(RuntimeError):
    pass


class SourceFailure(ReadLimit):
    pass


def normalize(value):
    return "".join(c for c in unicodedata.normalize("NFKD", str(value or "").upper()) if not unicodedata.combining(c))


def money(value):
    if value is None or str(value).strip() == "":
        return None
    raw = str(value).replace("R$", "").strip().replace(" ", "")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        amount = Decimal(raw)
        return amount.quantize(Decimal("0.01")) if amount.is_finite() else None
    except InvalidOperation:
        return None


def iso_date(value):
    text = str(value or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def validate_period(start, end):
    begin, stop = date.fromisoformat(start), date.fromisoformat(end)
    if stop < begin or (stop - begin).days > 30 or stop > date.today():
        raise ValueError("Selecione até 31 dias, sem data futura.")
    return begin, stop


def exclude_reason(shipment):
    ref = normalize(shipment.get("NF") or "").strip()
    content = normalize(shipment.get("CONTEUDO") or "")
    dest = normalize(shipment.get("DESTINATARIO") or "").strip()

    # Exclusão explícita de envios de Liturgias faturados como pedido/cliente novo
    if "ANSELMO FERREIRA DE CASTRO" in dest:
        return "LITURGIA_ENVIO_ASSINATURAS_NOVO_CLIENTE_ANSELMO"
    if "GUILHERME COSTA ALMEIDA" in dest:
        return "LITURGIA_ENVIO_ASSINATURAS_NOVO_CLIENTE_GUILHERME"

    if re.search(r"-\s*001\b", ref):
        return "LITURGIA_REFERENCIA_001_REGRA_USUARIO"
    if re.search(r"\b(JAN(?:EIRO)?|FEV(?:EREIRO)?|MARCO|MAR|ABR(?:IL)?|MAIO|MAI|JUN(?:HO)?|JUL(?:HO)?|AGOSTO|AGO|SET(?:EMBRO)?|OUT(?:UBRO)?|NOV(?:EMBRO)?|DEZ(?:EMBRO)?)\b", ref):
        return "LITURGIA_REFERENCIA_MESES"
    if not invoice_reference(ref) and ("LITURGIA" in content or "PAO DA VIDA" in content):
        return "LITURGIA_CONTEUDO_SEM_NF_NUMERICA"
    return None


def invoice_reference(value):
    match = re.fullmatch(r"\s*0*(\d{1,10})(?:-(\d{1,3}))?\s*", str(value or ""))
    return (str(int(match.group(1))), str(int(match.group(2))) if match.group(2) else None) if match else None


def nf_key(nf):
    comp, ide = nf.get("compl") or {}, nf.get("ide") or {}
    return str(comp.get("cChaveNFe") or f"NF:{ide.get('serie')}:{ide.get('nNF')}:{comp.get('nIdNF')}")


def unwrap_order(value):
    nested = value.get("pedido_venda_produto")
    return nested if isinstance(nested, dict) else nested[0] if isinstance(nested, list) and len(nested) == 1 else value


def dept_of(nf, order, departments):
    entries = (nf.get("pedido") or {}).get("Departamentos") or order.get("departamentos") or []
    entries = [entry for entry in entries if "nPercentualDistribuicao" not in entry or money(entry["nPercentualDistribuicao"]) != 0]
    descriptions = [departments.get(str(entry.get("cCodigoDepartamento") or entry.get("codigo_departamento") or ""), "") for entry in entries]
    groups = set()
    for name in descriptions:
        text = normalize(name).replace("-", "").replace(" ", "")
        groups.add("Ecommerce" if "ECOMMERCE" in text or "LOJAWEB" in text else "Comercial" if "COMERCIAL" in text else "Não identificado")
    group = next(iter(groups)) if len(groups) == 1 else "Misto/revisar" if groups else "Não identificado"
    return group, " / ".join(name for name in descriptions if name)


def freight_charged(nf, order):
    totals = (nf.get("total") or {}).get("ICMSTot") or {}
    fiscal = money(totals.get("vFrete"))
    if fiscal is not None and fiscal > 0:
        return fiscal, "NF", None
    freight = order.get("frete") or {}
    ordered = money(freight.get("valor_frete"))
    if ordered is not None and ordered >= 0:
        return ordered, "PEDIDO" if fiscal is None else "NF+PEDIDO" if ordered == fiscal else "PEDIDO_NF_DIVERGENTE", "NF sem frete positivo; cobrança tomada do pedido." if ordered > 0 and fiscal == 0 else None
    if fiscal == 0 and order.get("cabecalho") and "valor_frete" not in freight:
        return Decimal(0), "NF_ZERO_PEDIDO_CONSULTADO_SEM_FRETE", "NF explicitamente zerada e pedido consultado sem campo valor_frete; aplicado critério de ausência de cobrança informado pelo operador."
    if fiscal is not None and not (nf.get("compl") or {}).get("nIdPedido"):
        return fiscal, "NF_SEM_PEDIDO_VINCULADO", None
    return None, "AGUARDANDO_CONFERENCIA_PEDIDO", None


class Store:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS shipments (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS invoices (id TEXT PRIMARY KEY, payload TEXT NOT NULL, origin TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cache (id TEXT PRIMARY KEY, payload TEXT NOT NULL, fetched REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def put(self, table, key, payload, origin=""):
        if table not in ("shipments", "invoices", "orders", "jobs", "settings"):
            raise ValueError("Tabela inválida.")
        if table == "invoices":
            payload = {**payload, "_financeiro_origem": origin,
                "_financeiro_verificado_epoch": time.time() if origin == "OMIE_API_LEITURA" else payload.get("_financeiro_verificado_epoch", 0)}
        encoded = json.dumps(payload, ensure_ascii=False)
        with self.connect() as conn:
            if table == "invoices":
                conn.execute("INSERT OR REPLACE INTO invoices VALUES (?, ?, ?)", (key, encoded, origin))
            else:
                conn.execute(f"INSERT OR REPLACE INTO {table} VALUES (?, ?)", (key, encoded))

    def get(self, table, key, default=None):
        if table not in ("shipments", "invoices", "orders", "jobs", "settings"):
            raise ValueError("Tabela inválida.")
        with self.connect() as conn:
            row = conn.execute(f"SELECT payload FROM {table} WHERE id=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def all(self, table):
        if table not in ("shipments", "invoices", "orders", "jobs"):
            raise ValueError("Tabela inválida.")
        with self.connect() as conn:
            rows = conn.execute(f"SELECT payload FROM {table}").fetchall()
        return [json.loads(row[0]) for row in rows]

    def cached(self, key, ttl):
        with self.connect() as conn:
            row = conn.execute("SELECT payload,fetched FROM cache WHERE id=?", (key,)).fetchone()
        return json.loads(row[0]) if row and time.time() - row[1] < ttl else None

    def save_cache(self, key, payload):
        with self.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (key, json.dumps(payload, ensure_ascii=False), time.time()))


class Reader:
    def __init__(self, store, budget=25):
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        from omie_client import OmieClient
        from services.portal_postal_service import get_credentials
        self.client = OmieClient("MATRIZ")
        self.agf, self.user, self.password = get_credentials()
        self.store, self.budget, self.calls, self.last, self.empty = store, budget, 0, 0, 0

    def safe_error(self, text):
        for secret in (self.client.app_key, self.client.app_secret, self.agf, self.user, self.password):
            if secret:
                text = text.replace(str(secret), "[REDACTED]")
        return text[:300]

    def fetch(self, source, parameters, ttl, execute):
        key = hashlib.sha256(json.dumps([source, parameters], sort_keys=True).encode()).hexdigest()
        cached = self.store.cached(key, ttl)
        if cached is not None:
            return cached
        blocked = self.store.get("settings", "omie_block", {})
        if source.startswith("omie") and blocked.get("until", 0) > time.time():
            raise ReadLimit("Omie em cooldown local; consultas não repetidas.")
        if self.calls >= self.budget:
            raise ReadLimit("Orçamento de chamadas atingido. Use Continuar atualização para concluir as pendências com cache.")
        time.sleep(max(0, 0.7 - (time.monotonic() - self.last)))
        self.calls += 1
        self.last = time.monotonic()
        result = execute()
        self.store.save_cache(key, result)
        return result

    def omie(self, method, parameters):
        endpoints = {"ListarNF": "produtos/nfconsultar", "ConsultarNF": "produtos/nfconsultar",
            "ConsultarPedido": "produtos/pedido", "ListarDepartamentos": "geral/departamentos"}
        if method not in endpoints:
            raise ValueError("Somente métodos de leitura autorizados.")
        if not self.client.app_key or not self.client.app_secret:
            raise ReadLimit("Configuração Omie ausente; nenhum valor foi exposto.")

        def execute():
            try:
                response = requests.post(f"https://app.omie.com.br/api/v1/{endpoints[method]}/", json={
                    "call": method, "app_key": self.client.app_key, "app_secret": self.client.app_secret, "param": [parameters]},
                    timeout=(8, 35), allow_redirects=False)
                data = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise SourceFailure(f"{method}: {type(exc).__name__}. Processo interrompido sem retentativas agressivas.") from None
            fault = str(data.get("faultstring") or "") if isinstance(data, dict) else "Resposta inesperada"
            if "NAO EXISTEM REGISTROS PARA A PAGINA" in normalize(fault):
                self.empty += 1
                if self.empty >= 2:
                    raise ReadLimit("Duas buscas sem registros: interrompido para não acumular erros no Omie. Referências ficam pendentes.")
                return {"nfCadastro": [], "total_de_paginas": 0}
            if response.status_code != 200 or fault:
                if response.status_code in (425, 429) or "CONSUMO" in normalize(fault):
                    match = re.search(r"(?:aguarde|em)\s+(\d+)\s+segundos", fault, re.I)
                    self.store.put("settings", "omie_block", {"until": time.time() + (int(match[1]) if match else 1800) + 1})
                raise SourceFailure(f"{method} HTTP {response.status_code}: {self.safe_error(fault)}")
            self.empty = 0
            return data
        return self.fetch("omie:" + method, parameters, 86400, execute)

    def postal(self, start, end):
        if not all((self.agf, self.user, self.password)):
            raise ReadLimit("Configuração Portal Postal incompleta.")
        parameters = {"tipoArquivo": "RAW", "formatoArquivo": "CSV", "separadorArquivo": ";", "cabecalhoArquivo": "S", "tamanhoArquivo": "10",
            "camposArquivo": "SRO|SERVICO|NF|CEP|DESTINATARIO|PESO|VALOR|DATA_POSTAGEM|CONTEUDO|SITUACAO",
            "data_inicio": start, "data_fim": end}

        def execute():
            try:
                response = requests.post("https://www.portalpostal.com.br/Cliente/Servicos/ws_consulta_postagem.jsp",
                    data={**parameters, "codigoAGF": self.agf, "usuario": self.user, "senha": self.password}, timeout=(8, 45), allow_redirects=False)
            except requests.RequestException as exc:
                raise ReadLimit(f"Portal Postal: {type(exc).__name__}.") from None
            text = response.content.decode("iso-8859-1", errors="replace").strip()
            if response.status_code != 200 or text.upper().startswith("ERRO:"):
                raise ReadLimit(f"Portal Postal HTTP {response.status_code}: {self.safe_error(text)}")
            if not text:
                return []
            reader = csv.DictReader(io.StringIO(text), delimiter=";")
            if not {"SRO", "NF", "VALOR"}.issubset({str(field).strip().upper() for field in reader.fieldnames or []}):
                raise ReadLimit("Cabeçalho Portal Postal sem os campos financeiros esperados.")
            rows = []
            for row in reader:
                if None in row:
                    raise ReadLimit("Linha CSV inconsistente; não transformar custo ausente em zero.")
                rows.append({str(key).strip().upper(): str(value or "").strip() for key, value in row.items()})
            return rows
        return self.fetch("portal:financeiro", parameters, 900, execute)


def import_total(store):
    path = Path(os.getenv("TOTAL_EXPRESS_DB_PATH") or ROOT / "data" / "total_express_local.db")
    if not path.is_file():
        return 0
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM total_express_encomendas WHERE awb IS NOT NULL AND awb != ''").fetchall()
    except sqlite3.Error:
        return 0
    count = 0
    for raw in rows:
        row = dict(raw)
        try:
            payload = json.loads(row.get("payload_json") or "{}")
            shipment = (payload.get("encomendas") or [{}])[0]
            invoice = ((shipment.get("docFiscal") or {}).get("nfe") or [{}])[0]
            fiscal_number = str(invoice.get("nfeNumero") or "")
            reference = fiscal_number or str(row.get("pedido") or "")
            store.put("shipments", "TOTAL:" + str(row["awb"]), {
                "SRO": str(row["awb"]), "NF": reference, "NF_CONFIRMADA_PAYLOAD": bool(fiscal_number),
                "CHAVE_NFE": invoice.get("nfeChave"), "DESTINATARIO": (shipment.get("destinatario") or {}).get("nome"),
                "DATA_POSTAGEM": iso_date(row.get("data")) or iso_date(row.get("criado_em")), "VALOR": None,
                "SITUACAO": row.get("status"), "CONTEUDO": "", "CARRIER": "TOTAL EXPRESS",
                "ORIGEM_CUSTO": "CUSTO_FATURADO_TOTAL_NAO_DISPONIVEL",
            })
            count += 1
        except (ValueError, TypeError, KeyError, IndexError):
            continue
    return count


def reconcile(shipments, invoices, orders, departments, start, end):
    """Credit a NF once, on its earliest KNOWN posting; never equate unknown with zero."""
    by_number, by_key = defaultdict(list), {}
    for nf in invoices:
        key = nf_key(nf)
        by_key[key] = nf
    for key, nf in by_key.items():
        raw_number = str((nf.get("ide") or {}).get("nNF") or "")
        if raw_number.isdigit():
            by_number[str(int(raw_number))].append((key, nf))
    groups, excluded, pending = defaultdict(list), [], []
    deduped = {(p.get("CARRIER", "CORREIOS"), p.get("SRO")): p for p in shipments if p.get("SRO")}
    for shipment in deduped.values():
        posted = iso_date(shipment.get("DATA_POSTAGEM"))
        in_period = bool(posted and start <= posted <= end)
        base = {"objeto": shipment["SRO"], "referencia": shipment.get("NF"), "data": posted,
            "transportadora": shipment.get("CARRIER", "CORREIOS"), "cliente": shipment.get("DESTINATARIO"),
            "custo": money(shipment.get("VALOR")), "departamento": "Não identificado", "situacao_origem": shipment.get("SITUACAO")}
        reason = exclude_reason(shipment)
        if reason:
            if in_period:
                excluded.append({**base, "motivo": reason})
            continue
        if not posted:
            pending.append({**base, "status": "DATA_POSTAGEM_A_CONFERIR"})
            continue
        if "CANCEL" in normalize(shipment.get("SITUACAO")):
            if in_period:
                pending.append({**base, "status": "CANCELAMENTO_CONFERIR_COBRANCA"})
            continue
        exact = shipment.get("CHAVE_NFE")
        candidates = [(exact, by_key[exact])] if exact in by_key else []
        reference = invoice_reference(shipment.get("NF"))
        if not candidates and reference and (shipment.get("CARRIER") != "TOTAL EXPRESS" or shipment.get("NF_CONFIRMADA_PAYLOAD")):
            candidates = by_number.get(reference[0], [])
            if reference[1] is not None:
                candidates = [(key, nf) for key, nf in candidates if str((nf.get("ide") or {}).get("serie") or "").lstrip("0") == reference[1].lstrip("0")]
        if len(candidates) != 1:
            if in_period:
                pending.append({**base, "status": "NF_AMBIGUA" if candidates else "REFERENCIA_SEM_VINCULO_OMIE", "cobranca": None, "saldo": None})
            continue
        key, nf = candidates[0]
        groups[key].append((base, nf))
    reconciled = []
    for key, group in groups.items():
        selected = [entry for entry in group if start <= entry[0]["data"] <= end]
        if not selected:
            continue
        nf = group[0][1]
        ide, original_order = nf.get("ide") or {}, nf.get("pedido") or {}
        order_id = str((nf.get("compl") or {}).get("nIdPedido") or "")
        order = unwrap_order(orders.get(order_id) or {})
        dept, description = dept_of(nf, order, departments)
        charged, charged_source, warning = freight_charged(nf, order)
        first = min(group, key=lambda entry: (entry[0]["data"], entry[0]["objeto"]))[0]
        allocated_charge = charged if start <= first["data"] <= end else Decimal(0) if charged is not None else None
        costs = [entry[0]["custo"] for entry in selected]
        total_cost = sum(costs, Decimal(0)) if all(value is not None and value > 0 for value in costs) else None
        carrier = " / ".join(sorted({entry[0]["transportadora"] for entry in selected}))
        row = {"chave_nfe": key, "nf": str(ide.get("nNF") or ""), "serie": str(ide.get("serie") or ""),
            "pedido": str(original_order.get("cNumPedido") or ""), "cliente": (nf.get("nfDestInt") or {}).get("cRazao") or selected[0][0]["cliente"],
            "data": min(entry[0]["data"] for entry in selected), "transportadora": carrier,
            "objetos": [entry[0]["objeto"] for entry in selected], "departamento": dept, "descricao_departamento": description,
            "destinatarios_postagens": sorted({str(entry[0].get("cliente") or "") for entry in selected}),
            "custo": total_cost, "cobranca_documento": charged, "cobranca": allocated_charge,
            "fonte_cobranca": charged_source, "fonte_custo": "PORTAL_POSTAL" if carrier == "CORREIOS" else "AGUARDANDO_FONTE_TOTAL",
            "fonte_nf": nf.get("_financeiro_origem") or "NF_FORNECIDA",
            "primeira_postagem_conhecida": first["data"], "alerta": warning,
            "situacao": "PENDENTE", "saldo": None, "custo_conhecido_parcial": sum((value for value in costs if value is not None and value >= 0), Decimal(0))}
        if ide.get("dCan") or ide.get("dInut") or ide.get("cDeneg") == "S" or original_order.get("cCancelado") == "S":
            row["situacao"] = "NF_CANCELADA_CONFERIR"
        elif not original_order.get("opPedido"):
            row["situacao"] = "OPERACAO_VENDA_PENDENTE"
        elif str(original_order.get("opPedido") or "") not in ("11", "12") or str(ide.get("finNFe") or "1") != "1":
            row["situacao"] = "NAO_E_VENDA_COMUM"
        elif original_order.get("cDevolvido") == "S" or original_order.get("cDevParcial") == "S":
            row["situacao"] = "DEVOLUCAO_CONFERIR_FINANCEIRO"
        elif dept not in ("Comercial", "Ecommerce"):
            row["situacao"] = "DEPARTAMENTO_PENDENTE"
        elif total_cost is None:
            row["situacao"] = "CUSTO_TOTAL_PENDENTE" if "TOTAL" in carrier else "CUSTO_PORTAL_PENDENTE"
        elif charged is None:
            row["situacao"] = "FRETE_COBRADO_PENDENTE"
        else:
            row["saldo"] = allocated_charge - total_cost
            row["situacao"] = "FRETE_GRATIS" if charged == 0 and dept == "Ecommerce" else "COMERCIAL_SEM_COBRANCA" if charged == 0 else "COBRANCA_ALOCADA_OUTRO_PERIODO" if allocated_charge == 0 else "REPASSADO_DEFICITARIO" if row["saldo"] < 0 else "REPASSADO_COM_SOBRA" if row["saldo"] > 0 else "EQUILIBRADO"
        (reconciled if row["saldo"] is not None else pending).append(row)
    return reconciled, pending, excluded


def dashboard(start, end, department="", carrier="", store=None):
    validate_period(start, end)
    store = store or Store()
    department_map = store.get("settings", "departments", DEFAULT_DEPTS)
    reconciled, pending, excluded = reconcile(store.all("shipments"), store.all("invoices"),
        {str(row["id"]): row["payload"] for row in store.all("orders")}, department_map, start, end)

    def selected(row):
        return (not department or row.get("departamento") == department) and (not carrier or carrier in row.get("transportadora", ""))

    reconciled = [row for row in reconciled if selected(row)]
    pending = [row for row in pending if selected(row)]
    excluded = [row for row in excluded if selected(row)]
    def summary(rows):
        cost = sum((row["custo"] for row in rows), Decimal(0))
        charged = sum((row["cobranca"] for row in rows), Decimal(0))
        return {"notas_conciliadas": len(rows), "objetos": sum(len(row["objetos"]) for row in rows),
            "custo": cost, "cobranca": charged, "saldo": charged - cost,
            "frete_gratis_ecommerce": sum((row["custo"] for row in rows if row["situacao"] == "FRETE_GRATIS"), Decimal(0)),
            "comercial_sem_cobranca": sum((row["custo"] for row in rows if row["situacao"] == "COMERCIAL_SEM_COBRANCA"), Decimal(0)),
            "deficit_repasses": sum((-row["saldo"] for row in rows if row["cobranca_documento"] > 0 and row["saldo"] < 0), Decimal(0)),
            "recuperacao_percentual": charged / cost * 100 if cost else None}
    result = {"periodo": {"inicio": start, "fim": end}, "indicadores": summary(reconciled), "conciliados": reconciled,
        "pendentes": pending, "excluidos": excluded, "por_departamento": {dept: summary([row for row in reconciled if row["departamento"] == dept]) for dept in ("Comercial", "Ecommerce")},
        "custo_conhecido_pendentes": sum((row.get("custo_conhecido_parcial", row.get("custo")) or 0 for row in pending), Decimal(0)),
        "ultima_atualizacao": store.get("settings", "last_sync"),
        "fonte_total_express": store.get("settings", "total_source", {"custo_faturado_disponivel": False}),
        "regras": ["Valor cobrado em NF/pedido não comprova recebimento bancário; valor Portal Postal não comprova fatura quitada.",
            "Resultado gerencial apenas do frete, não lucro líquido do pedido.",
            "Cobrança alocada uma vez na primeira postagem CONHECIDA da NF. Histórico importado depois pode alterar essa alocação.",
            "Sem vínculo ou sem custo permanece pendente, nunca frete grátis automático.",
            "Total Express não entra no saldo enquanto não houver fonte confiável de custo; Frenet não é frete pago.",
            "Excluídas referências textuais de meses e -001 por regra do operador; exclusões ficam auditáveis."]}
    return result


def _run_job(job_id, start, end, store):
    global ACTIVE_JOB
    job = {"id": job_id, "status": "running", "etapa": "Iniciando", "chamadas_externas": 0, "iniciado_em": datetime.now().astimezone().isoformat()}
    reader = None

    def progress(label):
        job.update(etapa=label, chamadas_externas=reader.calls if reader else 0)
        store.put("jobs", job_id, job)
        lock = store.get("settings", "job_lock", {})
        if lock.get("id") == job_id:
            store.put("settings", "job_lock", {"id": job_id, "until": time.time() + 900})

    try:
        reader = Reader(store)
        begin, stop = validate_period(start, end)
        current = begin
        while current <= stop:
            until = min(stop, current + timedelta(days=6))
            progress(f"Portal Postal: {current} a {until}")
            for row in reader.postal(current.isoformat(), until.isoformat()):
                if row.get("SRO"):
                    row["CARRIER"] = "CORREIOS"
                    store.put("shipments", "CORREIOS:" + row["SRO"], row)
            current = until + timedelta(days=1)
        progress("Lendo registros Total Express locais, sem chamar a API")
        total_count = import_total(store)
        store.put("settings", "total_source", {"registros_locais_lidos": total_count,
            "custo_faturado_disponivel": False, "consultou_api_total": False,
            "observacao": "Somente registros de encomenda locais; não é fatura nem confirmação de postagem."})
        needed = {ref[0] for post in store.all("shipments") if not exclude_reason(post) and (ref := invoice_reference(post.get("NF"))) and (posted := iso_date(post.get("DATA_POSTAGEM"))) and start <= posted <= end}
        progress("Aproveitando cache fiscal existente")
        for path in (ROOT / "data" / "levantamento_liturgias").glob("omie_nf_v1_*.json"):
            try:
                for nf in json.loads(path.read_text(encoding="utf-8")).get("nfCadastro") or []:
                    num = str((nf.get("ide") or {}).get("nNF") or "").lstrip("0") or "0"
                    if num in needed and nf.get("pedido"):
                        if not store.get("invoices", nf_key(nf)):
                            store.put("invoices", nf_key(nf), {**nf, "_financeiro_verificado_epoch": path.stat().st_mtime}, "CACHE_FISCAL_EXISTENTE_NAO_RECONSULTADO")
            except (ValueError, OSError):
                continue
        progress("Conferindo departamentos Omie")
        depts = dict(DEFAULT_DEPTS)
        page = 1
        while page <= 10:
            response = reader.omie("ListarDepartamentos", {"pagina": page, "registros_por_pagina": 100})
            depts.update({str(row["codigo"]): row["descricao"] for row in response.get("departamentos") or []})
            if page >= int(response.get("total_de_paginas") or 1):
                break
            page += 1
        store.put("settings", "departments", depts)
        known = {str((nf.get("ide") or {}).get("nNF") or "").lstrip("0") or "0" for nf in store.all("invoices")
            if time.time() - nf.get("_financeiro_verificado_epoch", 0) < 86400}
        remaining = sorted((int(number) for number in needed - known if int(number) > 0), key=lambda value: (len(str(value)), -value))
        ranges = []
        for value in remaining:
            if ranges and value <= ranges[-1][1] and ranges[-1][1] - value <= 100:
                ranges[-1][0] = min(ranges[-1][0], value)
            else:
                ranges.append([value, value])
        for lower, upper in ranges:
            page = 1
            while page <= 10:
                progress(f"Buscando NFs {lower}–{upper}, página {page}")
                data = reader.omie("ListarNF", {"pagina": page, "registros_por_pagina": 100,
                    "nNFInicial": lower, "nNFFinal": upper, "tpNF": "1", "tpAmb": "1", "cDetalhesPedido": "S", "cApenasResumo": "N"})
                for nf in data.get("nfCadastro") or []:
                    store.put("invoices", nf_key(nf), nf, "OMIE_API_LEITURA")
                total = int(data.get("total_de_paginas") or 0)
                if page >= total:
                    break
                if total > 10:
                    raise ReadLimit("Busca fiscal excedeu limite de páginas, preservando dados já coletados.")
                page += 1
        for nf in store.all("invoices"):
            number = str((nf.get("ide") or {}).get("nNF") or "").lstrip("0") or "0"
            order_id = str((nf.get("compl") or {}).get("nIdPedido") or "")
            charged = money(((nf.get("total") or {}).get("ICMSTot") or {}).get("vFrete"))
            cached_order = store.get("orders", order_id) if order_id else None
            if number not in needed or not order_id or (charged is not None and charged > 0):
                continue
            if cached_order and ((not cached_order["payload"].get("_financeiro_erro") and time.time() - cached_order.get("consultado_em", 0) < 86400)
                    or (cached_order["payload"].get("_financeiro_erro") and time.time() - cached_order.get("tentado_em", 0) < 3600)):
                continue
            progress(f"Conferindo frete do pedido da NF {number}")
            try:
                order = reader.omie("ConsultarPedido", {"codigo_pedido": int(order_id)})
            except SourceFailure as exc:
                store.put("orders", order_id, {"id": order_id, "payload": {"_financeiro_erro": str(exc)}, "tentado_em": time.time()})
                raise
            store.put("orders", order_id, {"id": order_id, "payload": order, "consultado_em": time.time()})
        job["status"] = "complete"
        progress("Conciliação concluída; referências não encontradas permanecem pendentes")
    except ReadLimit as exc:
        job["status"] = "partial"
        job["aviso"] = str(exc)
        progress("Resultados parciais preservados; conferir aviso/continuar depois")
    except Exception as exc:
        job["status"] = "failed"
        job["aviso"] = f"Falha local ({type(exc).__name__}); dados coletados foram preservados."
        progress("Falha de atualização")
    finally:
        job["finalizado_em"] = datetime.now().astimezone().isoformat()
        job["chamadas_externas"] = reader.calls if reader else 0
        store.put("jobs", job_id, job)
        store.put("settings", "last_sync", job)
        if store.get("settings", "job_lock", {}).get("id") == job_id:
            store.put("settings", "job_lock", {})
        with LOCK:
            if ACTIVE_JOB == job_id:
                ACTIVE_JOB = None


def start_sync(start, end, store=None):
    global ACTIVE_JOB
    validate_period(start, end)
    store = store or Store()
    with LOCK:
        if ACTIVE_JOB:
            return {"id": ACTIVE_JOB, "status": "running", "reutilizou_job_ativo": True}
        with store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute("SELECT payload FROM settings WHERE id='job_lock'").fetchone()
            lock = json.loads(previous[0]) if previous else {}
            if lock.get("until", 0) > time.time():
                old = conn.execute("SELECT payload FROM jobs WHERE id=?", (lock["id"],)).fetchone()
                if old and json.loads(old[0]).get("status") == "running":
                    return {"id": lock["id"], "status": "running", "reutilizou_job_ativo": True}
            job_id = uuid.uuid4().hex
            conn.execute("INSERT OR REPLACE INTO settings VALUES ('job_lock',?)", (json.dumps({"id": job_id, "until": time.time() + 900}),))
        ACTIVE_JOB = job_id
        store.put("jobs", job_id, {"id": job_id, "status": "running", "etapa": "Na fila", "chamadas_externas": 0})
    threading.Thread(target=_run_job, args=(job_id, start, end, store), name="FreteFinanceiro-" + job_id, daemon=True).start()
    return {"id": job_id, "status": "running"}


def json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value
