import os
import json
import re
import urllib.request
from datetime import datetime
from dotenv import load_dotenv
import database as db

load_dotenv()

# Configurações do Banco Turso do Projeto Correios (Gestor de Etiquetas)
GESTOR_TURSO_URL = os.getenv("CORREIOS_TURSO_URL")
GESTOR_TURSO_TOKEN = os.getenv("CORREIOS_TURSO_TOKEN")

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

def consultar_gestor_turso(sql):
    """Executa query no banco do Projeto Correios via pipeline HTTP da Turso."""
    url = f"{GESTOR_TURSO_URL}/v2/pipeline"
    body = {
        "requests": [
            {
                "type": "execute",
                "stmt": {"sql": sql}
            }
        ]
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {GESTOR_TURSO_TOKEN}",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
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
    Busca todas as pré-postagens cadastradas no Gestor de Etiquetas dos Correios
    e sincroniza com o banco de dados do DRP de Assinaturas (assinaturas_rastreios),
    vinculando por Pedido Omie, CPF ou similaridade de Nome.
    """
    if not GESTOR_TURSO_URL or not GESTOR_TURSO_TOKEN:
        return {"sucesso": False, "mensagem": "Configurações dos Correios (CORREIOS_TURSO_URL / CORREIOS_TURSO_TOKEN) não configuradas no arquivo .env."}

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
        return {"sucesso": False, "mensagem": f"Erro ao acessar banco do Projeto Correios: {e}"}

    if not postagens:
        return {"sucesso": True, "mensagem": "Nenhuma pré-postagem com código de rastreio encontrada no Projeto Correios.", "total": 0}

    # Carregar assinantes do Turso local para cruzamento inteligente
    df_ass_ped = db.executar_query("SELECT id, numero_pedido, cliente_nome, cpf_cnpj, cidade, uf FROM assinaturas_pedidos_proximo_envio")
    df_ass_base = db.executar_query("SELECT id, codigo_cliente_omie, cliente_nome, cpf_cnpj, cidade, uf FROM assinantes_base")
    df_rastreios_existentes = db.executar_query("SELECT id, codigo_rastreio FROM assinaturas_rastreios")

    existentes_codigos = set()
    if df_rastreios_existentes is not None and not df_rastreios_existentes.empty:
        existentes_codigos = {str(r).strip().upper() for r in df_rastreios_existentes["codigo_rastreio"].dropna()}

    mapa_pedidos = {}
    mapa_cpfs = {}
    mapa_nomes = {}

    if df_ass_ped is not None and not df_ass_ped.empty:
        for _, row in df_ass_ped.iterrows():
            ped = str(row.get("numero_pedido") or "").strip()
            cpf = limpar_digitos(row.get("cpf_cnpj"))
            nome = normalizar_nome(row.get("cliente_nome"))
            if ped: mapa_pedidos[ped] = row
            if cpf: mapa_cpfs[cpf] = row
            if nome: mapa_nomes[nome] = row

    if df_ass_base is not None and not df_ass_base.empty:
        for _, row in df_ass_base.iterrows():
            cpf = limpar_digitos(row.get("cpf_cnpj"))
            nome = normalizar_nome(row.get("cliente_nome"))
            if cpf and cpf not in mapa_cpfs: mapa_cpfs[cpf] = row
            if nome and nome not in mapa_nomes: mapa_nomes[nome] = row

    novos_inseridos = 0
    atualizados = 0
    vinculados_pedido = 0
    vinculados_cpf = 0
    vinculados_nome = 0

    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for p in postagens:
        cod_objeto = str(p.get("codigo_objeto") or "").strip().upper()
        if not cod_objeto or len(cod_objeto) < 9:
            continue

        num_ped = str(p.get("pedido") or "").strip()
        dest_nome = str(p.get("destinatario") or "").strip()
        cidade = str(p.get("cidade") or "").strip()
        uf = str(p.get("uf") or "").strip()
        cidade_uf = f"{cidade} / {uf}" if cidade or uf else ""
        cpf_dest = limpar_digitos(p.get("cpf_cnpj_destinatario"))
        cancelado = int(p.get("cancelado") or 0)
        status_post = "Cancelada" if cancelado == 1 else (str(p.get("status_rotulo") or "Postado").strip())
        criado = str(p.get("created_at") or agora_str)[:10]

        # Cruzamento Inteligente em 3 Etapas:
        cruzou = False
        cliente_final = dest_nome

        # 1. Por Pedido Omie
        if num_ped and num_ped in mapa_pedidos:
            reg = mapa_pedidos[num_ped]
            cliente_final = reg.get("cliente_nome") or cliente_final
            if not cidade_uf:
                cidade_uf = f"{reg.get('cidade') or ''} / {reg.get('uf') or ''}"
            vinculados_pedido += 1
            cruzou = True

        # 2. Por CPF/CNPJ
        elif cpf_dest and cpf_dest in mapa_cpfs:
            reg = mapa_cpfs[cpf_dest]
            cliente_final = reg.get("cliente_nome") or cliente_final
            if not cidade_uf:
                cidade_uf = f"{reg.get('cidade') or ''} / {reg.get('uf') or ''}"
            vinculados_cpf += 1
            cruzou = True

        # 3. Por Similaridade de Nome
        elif dest_nome:
            nome_norm = normalizar_nome(dest_nome)
            for k_nome, reg in mapa_nomes.items():
                if nome_norm == k_nome or (len(nome_norm) > 10 and (nome_norm in k_nome or k_nome in nome_norm)):
                    cliente_final = reg.get("cliente_nome") or cliente_final
                    if not cidade_uf:
                        cidade_uf = f"{reg.get('cidade') or ''} / {reg.get('uf') or ''}"
                    vinculados_nome += 1
                    cruzou = True
                    break

        # Se já existe no banco assinaturas_rastreios, atualiza status
        if cod_objeto in existentes_codigos:
            sql_upd = """
                UPDATE assinaturas_rastreios SET
                    status_rastreio = :st,
                    cidade_uf = CASE WHEN cidade_uf IS NULL OR cidade_uf = '' THEN :cid ELSE cidade_uf END,
                    numero_pedido = CASE WHEN numero_pedido IS NULL OR numero_pedido = '' THEN :ped ELSE numero_pedido END
                WHERE codigo_rastreio = :cod
            """
            db.executar_query(sql_upd, {
                "st": status_post, "cid": cidade_uf, "ped": num_ped, "cod": cod_objeto
            }, is_select=False)
            atualizados += 1
        else:
            sql_ins = """
                INSERT INTO assinaturas_rastreios (
                    codigo_rastreio, cliente_nome, numero_pedido, cidade_uf,
                    lote_referencia, data_postagem, status_rastreio, criado_em
                ) VALUES (
                    :cod, :nome, :ped, :cid, 'Lote 1 (Jan-Mar/2027)', :dt, :st, :agora
                )
            """
            db.executar_query(sql_ins, {
                "cod": cod_objeto, "nome": cliente_final, "ped": num_ped,
                "cid": cidade_uf, "dt": criado, "st": status_post, "agora": agora_str
            }, is_select=False)
            existentes_codigos.add(cod_objeto)
            novos_inseridos += 1

    detalhe_cruzamento = f"({vinculados_pedido} vinculados por Pedido, {vinculados_cpf} por CPF e {vinculados_nome} por Nome)"
    return {
        "sucesso": True,
        "mensagem": f"Sincronização concluída! {novos_inseridos} novos rastreios importados e {atualizados} atualizados {detalhe_cruzamento}.",
        "novos_inseridos": novos_inseridos,
        "atualizados": atualizados,
        "total_processados": len(postagens),
        "vinculados_pedido": vinculados_pedido,
        "vinculados_cpf": vinculados_cpf,
        "vinculados_nome": vinculados_nome
    }
