"""Manual bounded source update/cache summary. No operational writes."""

import argparse
import json
import sys
import threading
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.frete_financeiro_service import Store, dashboard, json_safe, start_sync


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inicio", default=date.today().replace(day=1).isoformat())
    parser.add_argument("--fim", default=date.today().isoformat())
    parser.add_argument("--atualizar", action="store_true", help="Read Portal Postal/Omie with per-run API budget; default is cache only.")
    args = parser.parse_args()
    store = Store()
    if args.atualizar:
        result = start_sync(args.inicio, args.fim, store)
        print(json.dumps(result), flush=True)
        worker = next((t for t in threading.enumerate() if t.name == "FreteFinanceiro-" + result["id"]), None)
        if worker:
            worker.join()
        job = store.get("jobs", result["id"])
        print(json.dumps(job, ensure_ascii=True), flush=True)
    data = dashboard(args.inicio, args.fim, store=store)
    summary = {"periodo": data["periodo"], "indicadores": data["indicadores"],
        "notas_ou_referencias_pendentes": len(data["pendentes"]), "postagens_excluidas": len(data["excluidos"]),
        "pendencias_por_motivo": dict(Counter(row.get("situacao") or row.get("status") for row in data["pendentes"])),
        "por_departamento": data["por_departamento"], "custo_conhecido_pendentes": data["custo_conhecido_pendentes"]}
    print(json.dumps(json_safe(summary), ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
