"""Offline financial reconciliation; no credentials or external APIs."""

import hashlib
import io
import json
import sys
import tempfile
import time
import unittest
from datetime import date, timedelta
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import services.frete_financeiro_service as f

START, END = "2026-11-01", "2026-11-12"


def nf(charged="15", dept="1807684664", key="NFKEY", series="1", order_id=123):
    return {"ide": {"nNF": "000123", "serie": series, "tpNF": "1", "finNFe": "1"},
        "compl": {"cChaveNFe": key, "nIdPedido": order_id}, "nfDestInt": {"cRazao": "CLIENTE FIXTURE"},
        "total": {"ICMSTot": {"vFrete": charged}},
        "pedido": {"opPedido": "11", "cNumPedido": "42", "Departamentos": [{"cCodigoDepartamento": dept, "nPercentualDistribuicao": 100}]}}


def post(code="AA123456789BR", cost="10", ref="123-1", when="2026-11-03", carrier="CORREIOS"):
    return {"SRO": code, "VALOR": cost, "NF": ref, "DATA_POSTAGEM": when, "CARRIER": carrier, "DESTINATARIO": "CLIENTE FIXTURE"}


def reconcile(posts, invoices=None, orders=None):
    return f.reconcile(posts, invoices if invoices is not None else [nf()], orders or {}, f.DEFAULT_DEPTS, START, END)


class FinancialFreightTests(unittest.TestCase):
    def test_charge_once_and_sum_all_objects_of_same_nf(self):
        rows, pending, excluded = reconcile([post(), post("BB123456789BR", "20")])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["custo"], D(30))
        self.assertEqual(rows[0]["cobranca"], D(15))
        self.assertEqual(rows[0]["saldo"], D(-15))
        self.assertEqual(rows[0]["situacao"], "REPASSADO_DEFICITARIO")

    def test_duplicate_sro_is_not_a_second_cost(self):
        rows, _, _ = reconcile([post(), post()])
        self.assertEqual(rows[0]["custo"], D(10))
        self.assertEqual(len(rows[0]["objetos"]), 1)

    def test_ecommerce_zero_confirmed_order_is_free_shipping_cost(self):
        rows, _, _ = reconcile([post()], [nf("0", "1807684776")], {"123": {"pedido_venda_produto": {"frete": {"valor_frete": 0}}}})
        self.assertEqual(rows[0]["situacao"], "FRETE_GRATIS")
        self.assertEqual(rows[0]["saldo"], D(-10))

    def test_zero_nf_with_unchecked_order_stays_pending(self):
        rows, pending, _ = reconcile([post()], [nf("0", "1807684776")])
        self.assertEqual(rows, [])
        self.assertEqual(pending[0]["situacao"], "FRETE_COBRADO_PENDENTE")
        self.assertIsNone(pending[0]["cobranca"])

    def test_user_zero_rule_requires_successful_order_and_zero_nf(self):
        rows, _, _ = reconcile([post()], [nf("0", "1807684776")], {"123": {"pedido_venda_produto": {"cabecalho": {"codigo_pedido": 123}, "frete": {"modalidade": "0"}}}})
        self.assertEqual(rows[0]["situacao"], "FRETE_GRATIS")
        self.assertEqual(rows[0]["fonte_cobranca"], "NF_ZERO_PEDIDO_CONSULTADO_SEM_FRETE")

    def test_failed_order_cannot_be_used_for_zero_rule(self):
        rows, pending, _ = reconcile([post()], [nf("0", "1807684776")], {"123": {"_financeiro_erro": "Timeout"}})
        self.assertFalse(rows)
        self.assertEqual(pending[0]["situacao"], "FRETE_COBRADO_PENDENTE")

    def test_nf_zero_but_positive_order_uses_order_without_duplicate_receipt(self):
        rows, _, _ = reconcile([post()], [nf("0", "1807684776")], {"123": {"pedido_venda_produto": {"frete": {"valor_frete": "12.00"}}}})
        self.assertEqual(rows[0]["cobranca"], D(12))
        self.assertEqual(rows[0]["saldo"], D(2))
        self.assertEqual(rows[0]["fonte_cobranca"], "PEDIDO_NF_DIVERGENTE")

    def test_missing_freight_fields_are_not_a_confirmed_zero(self):
        rows, pending, _ = reconcile([post()], [nf(None, "1807684776")])
        self.assertFalse(rows)
        self.assertIsNone(pending[0]["saldo"])

    def test_month_references_and_001_are_auditable_exclusions(self):
        rows, pending, excluded = reconcile([post(ref="1.Jul à dez"), post("BB123456789BR", ref="19819842-001")])
        self.assertEqual(rows, [])
        self.assertEqual(pending, [])
        self.assertEqual(len(excluded), 2)

    def test_customer_name_never_matches_without_invoice_reference(self):
        rows, pending, _ = reconcile([post(ref="CLIENTE FIXTURE")])
        self.assertEqual(rows, [])
        self.assertEqual(pending[0]["status"], "REFERENCIA_SEM_VINCULO_OMIE")

    def test_multiple_series_need_disambiguation(self):
        invoices = [nf(key="KEY1", series="1"), nf(key="KEY2", series="2")]
        rows, pending, _ = reconcile([post(ref="123")], invoices)
        self.assertEqual(rows, [])
        self.assertEqual(pending[0]["status"], "NF_AMBIGUA")
        rows, _, _ = reconcile([post(ref="123-2")], invoices)
        self.assertEqual(rows[0]["chave_nfe"], "KEY2")

    def test_revenue_is_not_credited_twice_in_later_posting_period(self):
        rows, _, _ = reconcile([post(when="2026-10-31"), post("BB123456789BR", when="2026-11-03")])
        self.assertEqual(rows[0]["cobranca_documento"], D(15))
        self.assertEqual(rows[0]["cobranca"], D(0))
        self.assertEqual(rows[0]["saldo"], D(-10))
        self.assertEqual(rows[0]["situacao"], "COBRANCA_ALOCADA_OUTRO_PERIODO")

    def test_total_without_actual_cost_never_enters_balance(self):
        rows, pending, _ = reconcile([post(carrier="TOTAL EXPRESS", cost=None) | {"NF_CONFIRMADA_PAYLOAD": True}])
        self.assertEqual(rows, [])
        self.assertEqual(pending[0]["situacao"], "CUSTO_TOTAL_PENDENTE")
        self.assertIsNone(pending[0]["saldo"])

    def test_zero_postal_cost_is_not_assumed_free_service(self):
        rows, pending, _ = reconcile([post(cost="0")])
        self.assertFalse(rows)
        self.assertEqual(pending[0]["situacao"], "CUSTO_PORTAL_PENDENTE")

    def test_mixed_departments_require_review(self):
        invoice = nf()
        invoice["pedido"]["Departamentos"].append({"cCodigoDepartamento": "1807684776", "nPercentualDistribuicao": 50})
        rows, pending, _ = reconcile([post()], [invoice])
        self.assertEqual(rows, [])
        self.assertEqual(pending[0]["situacao"], "DEPARTAMENTO_PENDENTE")

    def test_zero_percent_department_does_not_make_sale_mixed(self):
        invoice = nf()
        invoice["pedido"]["Departamentos"].append({"cCodigoDepartamento": "1807684776", "nPercentualDistribuicao": 0})
        rows, _, _ = reconcile([post()], [invoice])
        self.assertEqual(rows[0]["departamento"], "Comercial")

    def test_cancelled_nf_never_becomes_recovered_freight(self):
        invoice = nf()
        invoice["ide"]["dCan"] = "2026-11-02"
        rows, pending, _ = reconcile([post()], [invoice])
        self.assertEqual(rows, [])
        self.assertEqual(pending[0]["situacao"], "NF_CANCELADA_CONFERIR")

    def test_missing_value_is_different_from_explicit_zero(self):
        self.assertIsNone(f.money(None))
        self.assertIsNone(f.money(""))
        self.assertEqual(f.money("0"), D(0))
        self.assertEqual(f.money("R$ 1.234,56"), D("1234.56"))


class FinancialStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=r"C:\Users\guilh\AppData\Local\Temp\kilo")
        self.store = f.Store(Path(self.temp.name) / "fixture.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_aggregates_decimal_money_and_ecommerce_subsidy(self):
        self.store.put("shipments", "A", post())
        self.store.put("invoices", "NFKEY", nf("0", "1807684776"), "FIXTURE")
        self.store.put("orders", "123", {"id": "123", "payload": {"pedido_venda_produto": {"frete": {"valor_frete": 0}}}})
        result = f.dashboard(START, END, store=self.store)
        self.assertEqual(result["indicadores"]["frete_gratis_ecommerce"], D(10))
        self.assertEqual(result["indicadores"]["saldo"], D(-10))
        self.assertEqual(f.json_safe(result)["indicadores"]["custo"], "10.00")

    def test_budget_exhaustion_does_not_execute_request(self):
        reader = object.__new__(f.Reader)
        reader.store, reader.calls, reader.budget = self.store, 0, 0
        fetch = Mock()
        with self.assertRaises(f.ReadLimit):
            reader.fetch("omie:ConsultarNF", {"nNF": "123"}, 100, fetch)
        fetch.assert_not_called()

    def test_cached_response_is_available_without_spending_budget(self):
        reader = object.__new__(f.Reader)
        reader.store, reader.calls, reader.budget = self.store, 0, 0
        params = {"nNF": "123"}
        key = hashlib.sha256(json.dumps(["omie:ConsultarNF", params], sort_keys=True).encode()).hexdigest()
        self.store.save_cache(key, {"fixture": True})
        fetch = Mock()
        self.assertEqual(reader.fetch("omie:ConsultarNF", params, 100, fetch), {"fixture": True})
        fetch.assert_not_called()

    def test_cross_process_active_job_is_reused(self):
        self.store.put("settings", "job_lock", {"id": "EXISTING", "until": time.time() + 500})
        self.store.put("jobs", "EXISTING", {"id": "EXISTING", "status": "running"})
        with patch.object(f, "ACTIVE_JOB", None), patch.object(f.threading, "Thread") as thread:
            result = f.start_sync(date.today().isoformat(), date.today().isoformat(), self.store)
        self.assertEqual(result["id"], "EXISTING")
        thread.assert_not_called()

    def test_department_filter_does_not_mix_unmatched_costs(self):
        self.store.put("shipments", "A", post())
        self.store.put("invoices", "NFKEY", nf(), "FIXTURE")
        result = f.dashboard(START, END, department="Ecommerce", store=self.store)
        self.assertEqual(result["indicadores"]["notas_conciliadas"], 0)


class FinancialHttpTests(unittest.TestCase):
    def handler(self, origin=None, client="127.0.0.1"):
        handler = Mock()
        handler.path = "/api/frete_financeiro/painel?inicio=2026-11-01&fim=2026-11-12"
        handler.headers = {"Host": "127.0.0.1:8898"}
        if origin:
            handler.headers["Origin"] = origin
        handler.client_address = (client, 12345)
        handler.wfile = io.BytesIO()
        return handler

    def test_remote_clients_are_refused_before_database(self):
        from services.frete_financeiro_http import handle
        handler = self.handler(client="192.168.1.10")
        with patch("services.frete_financeiro_http.dashboard") as dashboard:
            handle(handler, "GET")
        handler.send_response.assert_called_once_with(403)
        dashboard.assert_not_called()

    def test_other_websites_cannot_read_local_financial_data(self):
        from services.frete_financeiro_http import handle
        handler = self.handler(origin="https://example.org")
        with patch("services.frete_financeiro_http.dashboard") as dashboard:
            handle(handler, "GET")
        handler.send_response.assert_called_once_with(403)
        dashboard.assert_not_called()

    def test_private_cache_block_matches_encoded_and_head_paths(self):
        from services.frete_financeiro_http import private_cache_path
        for path in ("/data/frete_financeiro/financeiro.sqlite3", "/data/frete_financeiro", "/%64ata/frete_financeiro/financeiro.sqlite3?x=1", "/DATA/FRETE_FINANCEIRO/financeiro.sqlite3"):
            self.assertTrue(private_cache_path(path))
        self.assertFalse(private_cache_path("/static/frete_financeiro/index.html"))


if __name__ == "__main__":
    unittest.main()
