# -*- coding: utf-8 -*-
"""
Camada de banco de dados híbrida: Turso Cloud HTTP v2 e SQLite Local.
Inclui tabelas para o Módulo DRP (Blacklist, Produção Matriz, Sazonalidade, Cache de Produtos/Vendas).
"""
import os
import sqlite3
import requests
import math
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
DB_LOCAL = Path("data") / "database_local.db"

def _format_turso_arg(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return {"type": "null"}
    elif isinstance(v, bool):
        return {"type": "integer", "value": "1" if v else "0"}
    elif isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    elif isinstance(v, float):
        return {"type": "float", "value": float(v)}
    return {"type": "text", "value": str(v)}

def _parse_turso_value(val_obj):
    if not isinstance(val_obj, dict):
        return val_obj
    t = val_obj.get("type")
    v = val_obj.get("value")
    if t == "null":
        return None
    elif t == "integer":
        return int(v) if v is not None else None
    elif t == "float":
        return float(v) if v is not None else None
    return v

def executar_query(query: str, params: dict | tuple = None, is_select: bool = True):
    tem_turso = bool(TURSO_URL and TURSO_TOKEN and "turso.io" in TURSO_URL)

    if tem_turso:
        try:
            stmt = {"sql": query}
            if params:
                if isinstance(params, dict):
                    stmt["named_args"] = [
                        {"name": (k if k.startswith(":") else f":{k}"), "value": _format_turso_arg(v)}
                        for k, v in params.items()
                    ]
                elif isinstance(params, (list, tuple)):
                    stmt["args"] = [_format_turso_arg(v) for v in params]

            url_base = TURSO_URL.replace("libsql://", "https://").replace("sqlite+libsql://", "https://").strip("/")
            headers = {"Authorization": f"Bearer {TURSO_TOKEN}", "Content-Type": "application/json"}
            resp = requests.post(f"{url_base}/v2/pipeline", headers=headers, json={"requests": [{"type": "execute", "stmt": stmt}]}, timeout=15)
            res_json = resp.json()

            results = res_json.get("results", [])
            if results and results[0].get("type") != "error":
                res_exec = results[0].get("response", {}).get("result", {})
                cols = [c.get("name") for c in res_exec.get("cols", [])]
                raw_rows = res_exec.get("rows", [])
                parsed_rows = [[_parse_turso_value(cell) for cell in r] for r in raw_rows]
                return pd.DataFrame(parsed_rows, columns=cols) if is_select else res_exec
        except Exception:
            pass  # Fallback para SQLite local

    # Modo SQLite Local
    DB_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_LOCAL)
    try:
        if is_select:
            return pd.read_sql_query(query, conn, params=params)
        else:
            cur = conn.cursor()
            cur.execute(query, params or ())
            conn.commit()
            return None
    finally:
        conn.close()

def executar_batch_query(stmts_list: list):
    """Executa múltiplos comandos SQL em lote (batch) de alta velocidade no Turso Cloud ou SQLite."""
    if not stmts_list:
        return True

    tem_turso = bool(TURSO_URL and TURSO_TOKEN and "turso.io" in TURSO_URL)
    if tem_turso:
        try:
            url_base = TURSO_URL.replace("libsql://", "https://").replace("sqlite+libsql://", "https://").strip("/")
            headers = {"Authorization": f"Bearer {TURSO_TOKEN}", "Content-Type": "application/json"}

            # Envia pacotes de até 100 statements em cada chamada HTTP no pipeline v2
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
                            {"name": (k[1:] if k.startswith(":") else k), "value": _format_turso_arg(v)}
                            for k, v in params.items()
                        ]
                    requests_payload.append({"type": "execute", "stmt": stmt})

                resp = requests.post(f"{url_base}/v2/pipeline", headers=headers, json={"requests": requests_payload}, timeout=30)
            return True
        except Exception as e:
            print(f"[TURSO BATCH] Fallback SQLite por exceção: {e}")

    # Fallback para SQLite Local
    DB_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_LOCAL)
    try:
        cur = conn.cursor()
        for item in stmts_list:
            cur.execute(item["query"], item.get("params") or {})
        conn.commit()
        return True
    finally:
        conn.close()

def inicializar_banco():
    tabelas = [
        """CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE,
            cpf_cnpj TEXT,
            ultima_nf TEXT,
            data_registro TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS produtos (
            sku TEXT PRIMARY KEY,
            codigo_produto INTEGER,
            descricao TEXT,
            marca TEXT,
            familia TEXT,
            cd_sp INTEGER DEFAULT 0,
            matriz INTEGER DEFAULT 0,
            peso_kg REAL DEFAULT 0.1,
            ativo INTEGER DEFAULT 1,
            cmc REAL,
            id_local INTEGER,
            cfop TEXT,
            ultima_atualizacao TEXT,
            ultima_sincronizacao TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS drp_blacklist (
            sku TEXT PRIMARY KEY,
            nome TEXT,
            data_adicao TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS drp_producao (
            sku TEXT PRIMARY KEY,
            em_producao INTEGER DEFAULT 0,
            quantidade_producao INTEGER DEFAULT 0,
            data_previsao TEXT,
            data_atualizacao TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS drp_sazonal (
            sku TEXT PRIMARY KEY,
            eh_sazonal INTEGER DEFAULT 0,
            fator_ajuste REAL DEFAULT 1.0,
            observacao TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS drp_remessas (
            remessa_id TEXT PRIMARY KEY,
            codigo_remessa INTEGER,
            numero_remessa TEXT,
            data_previsao TEXT,
            faturada TEXT,
            cancelada TEXT,
            valor_total REAL,
            status_transito TEXT DEFAULT 'PENDENTE',
            itens_json TEXT,
            dados_raw_json TEXT,
            ultima_atualizacao TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS drp_depositos_matriz (
            sku TEXT PRIMARY KEY,
            fracionado INTEGER DEFAULT 0,
            deposito_1 INTEGER DEFAULT 0,
            deposito_2 INTEGER DEFAULT 0,
            ultima_atualizacao TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS drp_historico_transferencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT,
            nome_produto TEXT,
            origem TEXT,
            destino TEXT,
            quantidade INTEGER,
            data_hora TEXT,
            observacao TEXT
        )"""
    ]
    for sql in tabelas:
        executar_query(sql, is_select=False)

    # Migração defensiva para colunas adicionais no Turso/SQLite
    colunas_extras = [
        ("cd_sp", "INTEGER DEFAULT 0"),
        ("matriz", "INTEGER DEFAULT 0"),
        ("peso_kg", "REAL DEFAULT 0.1"),
        ("marca", "TEXT"),
        ("familia", "TEXT"),
        ("ativo", "INTEGER DEFAULT 1"),
        ("ultima_sincronizacao", "TEXT")
    ]
    for col_nome, col_tipo in colunas_extras:
        try:
            executar_query(f"ALTER TABLE produtos ADD COLUMN {col_nome} {col_tipo}", is_select=False)
        except Exception:
            pass

    # Limpa registros fantasma / nulos antigos
    try:
        executar_query("DELETE FROM drp_remessas WHERE remessa_id IS NULL OR remessa_id IN ('', '0', 'undefined', 'None', 'nan') OR codigo_remessa IS NULL OR codigo_remessa = 0", is_select=False)
    except Exception:
        pass

def _safe_val(v, default=None):
    import math
    if v is None:
        return default
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return default
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    return v

def _clean_obj_nan(obj):
    import math
    if obj is None:
        return None
    if isinstance(obj, (dict, list, tuple)):
        if isinstance(obj, dict):
            return {k: _clean_obj_nan(v) for k, v in obj.items()}
        return [_clean_obj_nan(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass
    return obj

def obter_remessas_db() -> list[dict]:
    try:
        df = executar_query("SELECT * FROM drp_remessas WHERE remessa_id NOT IN ('', '0', 'undefined', 'None', 'nan') AND codigo_remessa > 0 ORDER BY CAST(codigo_remessa AS INTEGER) DESC")
        if df is not None and not df.empty:
            remessas = []
            for _, row in df.iterrows():
                import json
                raw_json = row.get('dados_raw_json')
                r_obj = {}
                if raw_json and isinstance(raw_json, str):
                    try:
                        r_obj = json.loads(raw_json)
                    except Exception:
                        r_obj = {}

                # Limpa qualquer NaN recursivamente
                r_obj = _clean_obj_nan(r_obj) or {}

                cod_rem_val = _safe_val(row.get('codigo_remessa'), 0)
                num_rem_val = str(_safe_val(row.get('numero_remessa'), cod_rem_val or ''))
                d_prev_val = str(_safe_val(row.get('data_previsao'), ''))
                fat_val = str(_safe_val(row.get('faturada'), 'N'))
                canc_val = str(_safe_val(row.get('cancelada'), 'N'))
                v_tot_val = float(_safe_val(row.get('valor_total'), 0.0) or 0.0)

                if not cod_rem_val or str(num_rem_val).lower() in ('', '0', 'undefined', 'none', 'nan'):
                    continue

                # Garante que a chave 'cabec' exista e esteja populada sem valores NaN
                if 'cabec' not in r_obj or not isinstance(r_obj['cabec'], dict):
                    r_obj['cabec'] = {}
                
                c = r_obj['cabec']
                c['nCodRem'] = _safe_val(c.get('nCodRem'), cod_rem_val) or cod_rem_val
                c['cNumeroRemessa'] = str(_safe_val(c.get('cNumeroRemessa'), num_rem_val) or num_rem_val)
                c['dPrevisao'] = str(_safe_val(c.get('dPrevisao'), d_prev_val) or d_prev_val)
                c['faturada'] = str(_safe_val(c.get('faturada'), fat_val) or fat_val)
                c['cCancelado'] = str(_safe_val(c.get('cCancelado'), canc_val) or canc_val)
                c['nTotRem'] = _safe_val(c.get('nTotRem') or c.get('nValorTotal'), v_tot_val) or v_tot_val

                # Injeta ou sobrepõe o status_transito do banco
                r_obj['status_transito'] = _safe_val(row.get('status_transito'), 'PENDENTE') or 'PENDENTE'
                
                # Se houver itens_json salvo e r_obj não tiver itens
                if row.get('itens_json') and not r_obj.get('itens') and not r_obj.get('produtos'):
                    try:
                        r_obj['itens'] = _clean_obj_nan(json.loads(row['itens_json']))
                    except Exception:
                        pass
                        
                remessas.append(r_obj)
            return remessas
    except Exception as e:
        print(f"[DB] Tabela drp_remessas ausente ou erro ao consultar: {e}. Tentando inicializar...")
        try:
            inicializar_banco()
            df = executar_query("SELECT * FROM drp_remessas WHERE remessa_id NOT IN ('', '0', 'undefined', 'None', 'nan') AND codigo_remessa > 0 ORDER BY CAST(codigo_remessa AS INTEGER) DESC")
            if df is not None and not df.empty:
                remessas = []
                for _, row in df.iterrows():
                    import json
                    raw_json = row.get('dados_raw_json')
                    r_obj = json.loads(raw_json) if (raw_json and isinstance(raw_json, str)) else {}
                    r_obj = _clean_obj_nan(r_obj) or {}
                    cod_rem_val = _safe_val(row.get('codigo_remessa'), 0)
                    num_rem_val = str(_safe_val(row.get('numero_remessa'), cod_rem_val or ''))
                    if not cod_rem_val or str(num_rem_val).lower() in ('', '0', 'undefined', 'none', 'nan'):
                        continue
                    d_prev_val = str(_safe_val(row.get('data_previsao'), ''))
                    fat_val = str(_safe_val(row.get('faturada'), 'N'))
                    canc_val = str(_safe_val(row.get('cancelada'), 'N'))
                    v_tot_val = float(_safe_val(row.get('valor_total'), 0.0) or 0.0)
                    if 'cabec' not in r_obj or not isinstance(r_obj['cabec'], dict):
                        r_obj['cabec'] = {}
                    c = r_obj['cabec']
                    c['nCodRem'] = _safe_val(c.get('nCodRem'), cod_rem_val) or cod_rem_val
                    c['cNumeroRemessa'] = str(_safe_val(c.get('cNumeroRemessa'), num_rem_val) or num_rem_val)
                    c['dPrevisao'] = str(_safe_val(c.get('dPrevisao'), d_prev_val) or d_prev_val)
                    c['faturada'] = str(_safe_val(c.get('faturada'), fat_val) or fat_val)
                    c['cCancelado'] = str(_safe_val(c.get('cCancelado'), canc_val) or canc_val)
                    c['nTotRem'] = _safe_val(c.get('nTotRem') or c.get('nValorTotal'), v_tot_val) or v_tot_val
                    r_obj['status_transito'] = _safe_val(row.get('status_transito'), 'PENDENTE') or 'PENDENTE'
                    if row.get('itens_json') and not r_obj.get('itens') and not r_obj.get('produtos'):
                        try: r_obj['itens'] = _clean_obj_nan(json.loads(row['itens_json']))
                        except Exception: pass
                    remessas.append(r_obj)
                return remessas
        except Exception as ex2:
            print(f"[DB] Erro no retry de obter remessas: {ex2}")
    return []

def salvar_remessas_db(remessas_lista: list[dict]):
    import json
    for r in remessas_lista:
        r_clean = _clean_obj_nan(r) or {}
        c = r_clean.get('cabec') or {}
        remessa_id = str(c.get('nCodRem') or c.get('cNumeroRemessa') or r_clean.get('codigo_remessa') or '').strip()
        if not remessa_id or remessa_id.lower() in ('0', 'none', 'undefined', 'nan'):
            continue
        cod_rem = int(c.get('nCodRem') or r_clean.get('codigo_remessa') or 0)
        if cod_rem == 0:
            continue
        num_rem = str(c.get('cNumeroRemessa') or cod_rem)
        d_prev = str(c.get('dPrevisao') or '')
        faturada = str(c.get('faturada') or 'N')
        cancelada = str(c.get('cCancelado') or 'N')
        v_total = float(c.get('nValorTotal') or c.get('nTotRem') or 0.0)
        st_transito = r_clean.get('status_transito') or 'PENDENTE'
        
        itens = r_clean.get('itens') or r_clean.get('det') or r_clean.get('produtos') or []
        itens_str = json.dumps(_clean_obj_nan(itens), ensure_ascii=False)
        raw_str = json.dumps(r_clean, ensure_ascii=False)

        try:
            executar_query(
                """INSERT INTO drp_remessas (
                    remessa_id, codigo_remessa, numero_remessa, data_previsao, faturada, cancelada, valor_total, status_transito, itens_json, dados_raw_json, ultima_atualizacao
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(remessa_id) DO UPDATE SET
                    codigo_remessa=excluded.codigo_remessa,
                    numero_remessa=excluded.numero_remessa,
                    data_previsao=excluded.data_previsao,
                    faturada=excluded.faturada,
                    cancelada=excluded.cancelada,
                    valor_total=excluded.valor_total,
                    itens_json=CASE WHEN length(excluded.itens_json) > 5 THEN excluded.itens_json ELSE drp_remessas.itens_json END,
                    dados_raw_json=excluded.dados_raw_json,
                    ultima_atualizacao=datetime('now')""",
                (remessa_id, cod_rem, num_rem, d_prev, faturada, cancelada, v_total, st_transito, itens_str, raw_str),
                is_select=False
            )
        except Exception as e:
            # Fallback sem sintaxe ON CONFLICT
            try:
                executar_query(
                    "INSERT OR REPLACE INTO drp_remessas (remessa_id, codigo_remessa, numero_remessa, data_previsao, faturada, cancelada, valor_total, status_transito, itens_json, dados_raw_json, ultima_atualizacao) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                    (remessa_id, cod_rem, num_rem, d_prev, faturada, cancelada, v_total, st_transito, itens_str, raw_str),
                    is_select=False
                )
            except Exception as ex:
                print(f"[DB] Erro ao salvar remessa {remessa_id}: {ex}")

def atualizar_status_transito_db(remessa_id: str, status_transito: str):
    try:
        executar_query(
            "UPDATE drp_remessas SET status_transito = ?, ultima_atualizacao = datetime('now') WHERE remessa_id = ?",
            (status_transito, str(remessa_id)),
            is_select=False
        )
        # Se não existia ainda na tabela, insere registro minimo
        executar_query(
            "INSERT OR IGNORE INTO drp_remessas (remessa_id, status_transito, ultima_atualizacao) VALUES (?, ?, datetime('now'))",
            (str(remessa_id), status_transito),
            is_select=False
        )
    except Exception as e:
        print(f"[DB] Erro ao atualizar status de transito {remessa_id}: {e}")

def obter_blacklist() -> set[str]:
    try:
        df = executar_query("SELECT sku FROM drp_blacklist")
        if df is not None and not df.empty:
            return set(df['sku'].dropna().astype(str).tolist())
    except Exception:
        pass
    return set()

def salvar_blacklist(skus: set[str]):
    try:
        executar_query("DELETE FROM drp_blacklist", is_select=False)
        for sku in skus:
            executar_query("INSERT OR REPLACE INTO drp_blacklist (sku, data_adicao) VALUES (?, datetime('now'))", (sku,), is_select=False)
    except Exception:
        pass

def obter_status_producao() -> dict[str, bool]:
    try:
        df = executar_query("SELECT sku, em_producao FROM drp_producao")
        if df is not None and not df.empty:
            return {row['sku']: bool(row['em_producao']) for _, row in df.iterrows()}
    except Exception:
        pass
    return {}

def obter_detalhes_producao() -> dict[str, dict]:
    try:
        try:
            executar_query("ALTER TABLE drp_producao ADD COLUMN data_previsao TEXT", is_select=False)
        except Exception:
            pass
        df = executar_query("SELECT sku, em_producao, quantidade_producao, data_previsao FROM drp_producao")
        if df is not None and not df.empty:
            res = {}
            for _, row in df.iterrows():
                res[row['sku']] = {
                    'em_producao': bool(row.get('em_producao', 0)),
                    'quantidade_producao': int(row.get('quantidade_producao', 0) or 0),
                    'data_previsao': str(row.get('data_previsao', '') or '')
                }
            return res
    except Exception:
        pass
    return {}

def salvar_status_producao(sku: str, em_producao: bool, data_previsao: str = None, quantidade_producao: int = 0):
    try:
        try:
            executar_query("ALTER TABLE drp_producao ADD COLUMN data_previsao TEXT", is_select=False)
        except Exception:
            pass
        
        val_dt = data_previsao if data_previsao is not None else ''
        executar_query(
            "INSERT INTO drp_producao (sku, em_producao, data_previsao, quantidade_producao, data_atualizacao) VALUES (?, ?, ?, ?, datetime('now')) ON CONFLICT(sku) DO UPDATE SET em_producao=excluded.em_producao, data_previsao=excluded.data_previsao, quantidade_producao=excluded.quantidade_producao, data_atualizacao=datetime('now')",
            (sku, 1 if em_producao else 0, val_dt, quantidade_producao),
            is_select=False
        )
    except Exception as e:
        print(f"[DB] Erro ao salvar status producao {sku}: {e}")

def obter_sazonalidade() -> dict[str, bool]:
    try:
        df = executar_query("SELECT sku, eh_sazonal FROM drp_sazonal")
        if df is not None and not df.empty:
            return {row['sku']: bool(row['eh_sazonal']) for _, row in df.iterrows()}
    except Exception:
        pass
    return {}

def obter_depositos_matriz_db() -> dict[str, dict]:
    try:
        df = executar_query("SELECT sku, fracionado, deposito_1, deposito_2 FROM drp_depositos_matriz")
        if df is not None and not df.empty:
            res = {}
            for _, r in df.iterrows():
                res[str(r['sku'])] = {
                    'fracionado': int(r.get('fracionado') or 0),
                    'deposito_1': int(r.get('deposito_1') or 0),
                    'deposito_2': int(r.get('deposito_2') or 0)
                }
            return res
    except Exception as e:
        print(f"[DB] Erro ao obter depositos matriz: {e}")
    return {}

def salvar_deposito_matriz_db(sku: str, fracionado: int = 0, deposito_1: int = 0, deposito_2: int = 0):
    try:
        executar_query(
            """INSERT OR REPLACE INTO drp_depositos_matriz (sku, fracionado, deposito_1, deposito_2, ultima_atualizacao)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (str(sku), int(fracionado), int(deposito_1), int(deposito_2)),
            is_select=False
        )
    except Exception as e:
        print(f"[DB] Erro ao salvar deposito matriz {sku}: {e}")

def registrar_transferencia_deposito_db(sku: str, nome_produto: str, origem: str, destino: str, quantidade: int, observacao: str = ""):
    try:
        executar_query(
            """INSERT INTO drp_historico_transferencias (sku, nome_produto, origem, destino, quantidade, data_hora, observacao)
               VALUES (?, ?, ?, ?, ?, datetime('now'), ?)""",
            (str(sku), str(nome_produto), str(origem), str(destino), int(quantidade), str(observacao)),
            is_select=False
        )
    except Exception as e:
        print(f"[DB] Erro ao registrar transferencia: {e}")

def obter_historico_transferencias_db(limit: int = 100) -> list[dict]:
    try:
        df = executar_query("SELECT id, sku, nome_produto, origem, destino, quantidade, data_hora, observacao FROM drp_historico_transferencias ORDER BY id DESC LIMIT ?", (int(limit),))
        if df is not None and not df.empty:
            return df.to_dict(orient="records")
    except Exception as e:
        print(f"[DB] Erro ao obter historico transferencias: {e}")
    return []

if __name__ == "__main__":
    inicializar_banco()
    print("✅ Banco DRP inicializado com sucesso!")