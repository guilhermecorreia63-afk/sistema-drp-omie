"""
Serviço de Sincronização Inteligente de Rastreios de Assinaturas.
Regras Estritas:
1. Descarta 100% de dados de testes do Projeto Correios (ignora TESTE, ROUTING, DESTINATARIO, etc.).
2. Só importa e cruza rastreios com assinantes reais de assinaturas_pedidos_proximo_envio e assinantes_base.
3. Identifica a natureza de cada envio:
   - 1º Envio (Jan a Março/2027) - Pedido Omie #... (para combos como PRD00379)
   - 1º Envio (Dezembro/2026) - Pedido Omie #... (para combos como 000223)
   - Lotes Trimestrais / Semestrais (Lote 1, Lote 2, Lote 3, etc.)
4. Prepara a estrutura multi-envios para que clientes como Marielli Araújo Paiva tenham seu histórico completo.
"""
import os
import sys
import json
import re
import urllib.request
from datetime import datetime

raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from dotenv import load_dotenv
load_dotenv(os.path.join(raiz, ".env"))

import database as db

def obter_config_correios_turso():
    url = (
        os.getenv("CORREIOS_TURSO_URL") or
        os.getenv("TURSO_CORREIOS_URL") or
        os.getenv("TURSO_URL_CORREIOS") or
        os.getenv("GESTOR_TURSO_URL") or
        os.getenv("CORREIOS_DATABASE_URL") or
        os.getenv("TURSO_DATABASE_URL_CORREIOS")
    )
    token = (
        os.getenv("CORREIOS_TURSO_TOKEN") or
        os.getenv("TURSO_CORREIOS_TOKEN") or
        os.getenv("TURSO_AUTH_TOKEN_CORREIOS") or
        os.getenv("GESTOR_TURSO_TOKEN") or
        os.getenv("CORREIOS_AUTH_TOKEN") or
        os.getenv("TURSO_TOKEN_CORREIOS")
    )
    if url and url.startswith("libsql://"):
        url = "https://" + url[9:]
    return url, token

def limpar_digitos(doc):
    if not doc:
        return ""
    return re.sub(r"\D", "", str(doc))

def normalizar_nome(nome):
    if not nome:
        return ""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(nome)).encode("ASCII", "ignore").decode("ASCII")
    return s.strip().upper()

def eh_registro_teste(nome, pedido):
    texto = f"{nome} {pedido}".upper()
    termos_teste = ["TESTE", "ROUTING", "DESTINATARIO", "REUSO", "MODICO", "PED-PAC-", "PED-SEDEX-", "PED-MINI-"]
    for t in termos_teste:
        if t in texto:
            return True
    return False

def consultar_gestor_turso(sql):
    """Executa query no banco do Projeto Correios via pipeline HTTP da Turso."""
    url, token = obter_config_correios_turso()
    if not url or not token:
        raise Exception("Configurações dos Correios Turso (CORREIOS_TURSO_URL / CORREIOS_TURSO_TOKEN) não encontradas nas variáveis de ambiente.")

    pipeline_url = f"{url.rstrip('/')}/v2/pipeline"
    body = {
        "requests": [
            {
                "type": "execute",
                "stmt": {"sql": sql}
            }
        ]
    }
    req = urllib.request.Request(
        pipeline_url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        res = data.get("results", [])[0]
        if res.get("type") == "error":
            raise Exception(res.get("error", {}).get("message", "Erro no Turso Gestor"))
        result = res.get("response", {}).get("result", {})
        cols = [c["name"] for c in result.get("cols", [])]
        rows = []
        for r in result.get("rows", []):
            vals = [item.get("value") for item in r]
            rows.append(dict(zip(cols, vals)))
        return rows

def sincronizar_rastreios_correios():
    """
    Sincroniza os rastreios dos pedidos de assinaturas e lotes de envio.
    1. Registra e atualiza pedidos faturados do Omie (inclusive Fortaleza com entregador próprio).
    2. Consulta o banco do Projeto Correios (se configurado) e enriquece os rastreios dos assinantes reais.
    """
    # 1. Carregar assinantes do Turso local (pedidos novos e base ativa)
    df_ass_ped = db.executar_query("SELECT id, numero_pedido, cliente_nome, cpf_cnpj, cidade, uf, sku_produto FROM assinaturas_pedidos_proximo_envio")
    df_ass_base = db.executar_query("SELECT id, codigo_cliente_omie, cliente_nome, cpf_cnpj, cidade, uf FROM assinantes_base")
    df_rastreios_existentes = db.executar_query("SELECT id, codigo_rastreio, numero_pedido, tipo_envio, status_rastreio FROM assinaturas_rastreios")

    existentes_codigos = set()
    existentes_pedidos = set()
    mapa_rastreios_por_ped = {}

    if df_rastreios_existentes is not None and not df_rastreios_existentes.empty:
        for _, r in df_rastreios_existentes.iterrows():
            c = str(r.get("codigo_rastreio") or "").strip().upper()
            p = str(r.get("numero_pedido") or "").strip()
            if c: existentes_codigos.add(c)
            if p:
                existentes_pedidos.add(p)
                mapa_rastreios_por_ped[p] = dict(r)

    mapa_pedidos = {}
    mapa_cpfs = {}
    mapa_nomes = {}

    if df_ass_ped is not None and not df_ass_ped.empty:
        for _, row in df_ass_ped.iterrows():
            ped = str(row.get("numero_pedido") or "").strip()
            cpf = limpar_digitos(row.get("cpf_cnpj"))
            nome = normalizar_nome(row.get("cliente_nome"))
            item = dict(row)
            item["origem_tipo"] = "PEDIDO_OMIE"
            if ped: mapa_pedidos[ped] = item
            if cpf: mapa_cpfs[cpf] = item
            if nome: mapa_nomes[nome] = item

    if df_ass_base is not None and not df_ass_base.empty:
        for _, row in df_ass_base.iterrows():
            cpf = limpar_digitos(row.get("cpf_cnpj"))
            nome = normalizar_nome(row.get("cliente_nome"))
            item = dict(row)
            item["origem_tipo"] = "BASE_ATIVA"
            if cpf and cpf not in mapa_cpfs: mapa_cpfs[cpf] = item
            if nome and nome not in mapa_nomes: mapa_nomes[nome] = item

    novos_inseridos = 0
    atualizados = 0
    ignorados_testes = 0
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 2. Assegurar que os Pedidos Faturados no Omie apareçam no Painel de Rastreio (inclusive Fortaleza e pedidos novos)
    if df_ass_ped is not None and not df_ass_ped.empty:
        for _, row in df_ass_ped.iterrows():
            ped = str(row.get("numero_pedido") or "").strip()
            nome = str(row.get("cliente_nome") or "").strip()
            cpf = str(row.get("cpf_cnpj") or "").strip()
            cidade_raw = str(row.get("cidade") or "").strip().upper()
            uf_raw = str(row.get("uf") or "").strip().upper()
            cid = f"{row.get('cidade') or ''} / {row.get('uf') or ''}"
            sku = str(row.get("sku_produto") or "")

            eh_fortaleza = ("FORTALEZA" in cidade_raw) or (uf_raw == "CE" and any(m in cidade_raw for m in ["FORTALEZA", "MARACANAU", "MARACANAÚ", "CAUCAIA", "EUSEBIO", "EUSÉBIO"]))

            if "PRD00379" in sku:
                tipo_envio = f"1º Envio (Jan a Março/2027) - Pedido Omie #{ped}"
            elif "000223" in sku:
                tipo_envio = f"1º Envio (Dezembro/2026) - Pedido Omie #{ped}"
            else:
                tipo_envio = f"1º Envio (Inicial) - Pedido Omie #{ped}"

            if eh_fortaleza:
                tipo_envio += " (Entrega Própria Fortaleza)"

            if ped not in mapa_rastreios_por_ped:
                if eh_fortaleza:
                    cod_placeholder = f"ENTREGA_PROPRIA_{ped}"
                    status_inicial = "Enviado"
                else:
                    cod_placeholder = f"AGUARDANDO_POSTAGEM_{ped}"
                    status_inicial = "Aguardando Despacho"

                sql_ins_ped = """
                    INSERT INTO assinaturas_rastreios (
                        codigo_rastreio, cliente_nome, numero_pedido, cpf_cnpj, cidade_uf,
                        lote_referencia, tipo_envio, data_postagem, status_rastreio, criado_em
                    ) VALUES (
                        :cod, :nome, :ped, :cpf, :cid,
                        :lote, :tipo, :dt, :st, :agora
                    )
                """
                db.executar_query(sql_ins_ped, {
                    "cod": cod_placeholder, "nome": nome, "ped": ped, "cpf": cpf,
                    "cid": cid, "lote": tipo_envio, "tipo": tipo_envio,
                    "dt": datetime.now().strftime("%d/%m/%Y"), "st": status_inicial, "agora": agora_str
                }, is_select=False)
                novos_inseridos += 1
                mapa_rastreios_por_ped[ped] = {"codigo_rastreio": cod_placeholder, "status_rastreio": status_inicial}
            else:
                # Se já existia e é Fortaleza com placeholder antigo, atualiza para Entrega Própria e Enviado
                r_exist = mapa_rastreios_por_ped[ped]
                cod_exist = str(r_exist.get("codigo_rastreio") or "")
                st_exist = str(r_exist.get("status_rastreio") or "")
                if eh_fortaleza and (cod_exist.startswith("AGUARDANDO_") or not cod_exist.startswith("ENTREGA_PROPRIA_")):
                    novo_st = "Entregue" if "ENTREG" in st_exist.upper() else "Enviado"
                    db.executar_query(
                        "UPDATE assinaturas_rastreios SET codigo_rastreio = :cod, tipo_envio = :tipo, status_rastreio = :st WHERE id = :id",
                        {"cod": f"ENTREGA_PROPRIA_{ped}", "tipo": tipo_envio, "st": novo_st, "id": int(r_exist["id"])},
                        is_select=False
                    )
                    atualizados += 1

    # 3. Consultar pré-postagens do Projeto Correios (se configurado)
    url_correios, token_correios = obter_config_correios_turso()
    if not url_correios or not token_correios:
        msg = f"Sincronização concluída! {novos_inseridos} novo(s) envio(s) (inclusive Fortaleza/Entrega Própria) atualizados com sucesso no painel."
        return {
            "sucesso": True,
            "mensagem": msg,
            "novos_inseridos": novos_inseridos,
            "atualizados": atualizados,
            "aviso": "Conexão Correios Turso pendente de variáveis no Vercel (pedidos de Fortaleza e locais sincronizados com sucesso)."
        }

    try:
        sql = """
            SELECT codigo_objeto, pedido, destinatario, cpf_cnpj_destinatario,
                   cidade, uf, status_rotulo, cancelado, created_at
            FROM prepostagens
            WHERE codigo_objeto IS NOT NULL AND TRIM(codigo_objeto) != ''
            ORDER BY created_at DESC
        """
        postagens = consultar_gestor_turso(sql)
    except Exception as e:
        msg = f"Pedidos locais atualizados ({novos_inseridos} novos). Aviso Correios: {e}"
        return {"sucesso": True, "mensagem": msg, "novos_inseridos": novos_inseridos, "atualizados": atualizados}

    # 4. Processar postagens com validação estrita (ignorar 100% dos testes)
    for p in postagens:
        num_ped = str(p.get("pedido") or "").strip()
        dest_nome = str(p.get("destinatario") or "").strip()
        cpf_dest = limpar_digitos(p.get("cpf_cnpj_destinatario"))
        cod_objeto = str(p.get("codigo_objeto") or "").strip().upper()

        if eh_registro_teste(dest_nome, num_ped):
            ignorados_testes += 1
            continue

        assinante_match = None
        if num_ped and num_ped in mapa_pedidos:
            assinante_match = mapa_pedidos[num_ped]
        elif cpf_dest and cpf_dest in mapa_cpfs:
            assinante_match = mapa_cpfs[cpf_dest]
        elif dest_nome:
            nome_norm = normalizar_nome(dest_nome)
            for k_nome, item in mapa_nomes.items():
                if nome_norm == k_nome or (len(nome_norm) > 10 and (nome_norm in k_nome or k_nome in nome_norm)):
                    assinante_match = item
                    break

        if not assinante_match:
            continue

        cidade = str(p.get("cidade") or assinante_match.get("cidade") or "").strip()
        uf = str(p.get("uf") or assinante_match.get("uf") or "").strip()
        cidade_uf = f"{cidade} / {uf}" if cidade or uf else ""
        cliente_final = assinante_match.get("cliente_nome") or dest_nome
        cancelado = int(p.get("cancelado") or 0)
        status_post = "Cancelada" if cancelado == 1 else (str(p.get("status_rotulo") or "Postado").strip())
        criado = str(p.get("created_at") or agora_str)[:10]

        sku = str(assinante_match.get("sku_produto") or "")
        ped_ref = str(assinante_match.get("numero_pedido") or num_ped)

        if assinante_match.get("origem_tipo") == "PEDIDO_OMIE":
            if "PRD00379" in sku:
                tipo_envio = f"1º Envio (Jan a Março/2027) - Pedido Omie #{ped_ref}"
            elif "000223" in sku:
                tipo_envio = f"1º Envio (Dezembro/2026) - Pedido Omie #{ped_ref}"
            else:
                tipo_envio = f"1º Envio (Inicial) - Pedido Omie #{ped_ref}"
        else:
            tipo_envio = "Lote 1 (Jan, Fev e Março/2027)"

        cpf_final = assinante_match.get("cpf_cnpj") or p.get("cpf_cnpj_destinatario") or ""

        if cod_objeto in existentes_codigos:
            sql_upd = """
                UPDATE assinaturas_rastreios SET
                    status_rastreio = :st,
                    tipo_envio = :tipo,
                    cpf_cnpj = :cpf,
                    cidade_uf = :cid,
                    numero_pedido = :ped
                WHERE codigo_rastreio = :cod
            """
            db.executar_query(sql_upd, {
                "st": status_post, "tipo": tipo_envio, "cpf": cpf_final,
                "cid": cidade_uf, "ped": ped_ref, "cod": cod_objeto
            }, is_select=False)
            atualizados += 1
        else:
            sql_ins = """
                INSERT INTO assinaturas_rastreios (
                    codigo_rastreio, cliente_nome, numero_pedido, cpf_cnpj, cidade_uf,
                    lote_referencia, tipo_envio, data_postagem, status_rastreio, criado_em
                ) VALUES (
                    :cod, :nome, :ped, :cpf, :cid,
                    :lote, :tipo, :dt, :st, :agora
                )
            """
            db.executar_query(sql_ins, {
                "cod": cod_objeto, "nome": cliente_final, "ped": ped_ref,
                "cpf": cpf_final, "cid": cidade_uf, "lote": tipo_envio,
                "tipo": tipo_envio, "dt": criado, "st": status_post, "agora": agora_str
            }, is_select=False)
            existentes_codigos.add(cod_objeto)
            novos_inseridos += 1

    msg = f"Sincronização de assinaturas concluída! {novos_inseridos} registros atualizados com sucesso (dados de testes do Projeto Correios foram 100% filtrados e descartados)."
    return {
        "sucesso": True,
        "mensagem": msg,
        "novos_inseridos": novos_inseridos,
        "atualizados": atualizados,
        "ignorados_testes": ignorados_testes
    }

if __name__ == "__main__":
    resultado = sincronizar_rastreios_correios()
    print(resultado["mensagem"])
