import os
import io
import urllib.request
import logging
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import requests
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
import csv

import tempfile

load_dotenv()
logger = logging.getLogger("assinaturas_service")

GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/1lqDiqjD5fmQ9r2f3KS-MK2ebn4YxMRTDBwybsvm7wDw/export?format=xlsx"

# Cache seguro no diretório temporário do sistema (/tmp no Vercel/Linux)
TEMP_DIR = tempfile.gettempdir()
CACHE_SHEET_LIVE = os.path.join(TEMP_DIR, "planilha_ao_vivo.xlsx")
LOCAL_SHEET_REPO = os.path.join(os.path.dirname(__file__), "..", "planilha_ao_vivo.xlsx")
LOCAL_SHEET_FALLBACK = os.path.join(os.path.dirname(__file__), "..", "1° Assinatura PDV (respostas) (1).xlsx")

# Cache em memória RAM da instância serverless
_CACHED_BYTES_EXCEL = None
_CACHED_DOWNLOAD_TIME = None

# Produtos Omie
PRODUTOS_LITURGIA = {
    "jan27": {
        "codigo": "PRD00561",
        "id_matriz": 2147282282,
        "descricao": "LITURGIA DIARIA JANEIRO - 2027",
        "peso_kg": 0.100,
        "mes_nome": "Janeiro 2027"
    },
    "fev27": {
        "codigo": "PRD00562",
        "id_matriz": 2147282526,
        "descricao": "LITURGIA DIARIA FEVEREIRO - 2027",
        "peso_kg": 0.100,
        "mes_nome": "Fevereiro 2027"
    },
    "mar27": {
        "codigo": "PRD00563",
        "id_matriz": 2147282582,
        "descricao": "LITURGIA DIARIA MARÇO - 2027",
        "peso_kg": 0.100,
        "mes_nome": "Março 2027"
    }
}

# Dados Fiscais e Logística
CLIENTE_EDICOES_SHALOM_ID = 1854959029
TRANSPORTADORA_ROBERTO_ID = 1854969807
CATEGORIA_RECEITA_COMERCIAL = "1.01.01"
VALOR_UNITARIO_ROBERTO_FINAL = 4.50

# Estados com envio exclusivo via PAC (não usar Impresso Módico devido ao tempo de trânsito)
ESTADOS_PAC_OBRIGATORIO = {"AM", "AC", "RR", "AP", "PA", "RO", "TO"}

# Tabela de Frete Fortaleza (Roberto)
FRETE_TABELA_ROBERTO = [
    (0.01, 2.00, 11.50, "1 Cx Pequena"),
    (2.001, 6.00, 20.00, "1 Cx Pequena"),
    (6.001, 10.499, 25.00, "1 Cx Média"),
    (10.500, 16.499, 35.00, "1 Cx Grande"),
    (16.500, 31.000, 50.00, "2 Cx Grandes"),
    (31.500, 48.000, 60.00, "3 Cx Grandes"),
    (48.500, 64.000, 65.00, "4 Cx Grandes"),
    (64.500, 80.000, 73.00, "5 Cx Grandes"),
    (80.500, 96.000, 81.00, "6 Cx Grandes"),
    (96.500, 112.000, 89.00, "7 Cx Grandes"),
    (112.500, 128.000, 97.00, "8 Cx Grandes"),
    (128.500, 144.000, 105.00, "10 Cx Grandes"),
]

def calcular_frete_tabela(peso_kg):
    for min_p, max_p, val, desc in FRETE_TABELA_ROBERTO:
        if min_p <= peso_kg <= max_p:
            return {"valor": val, "descricao": desc}
    if peso_kg > 144.000:
        return {"valor": None, "descricao": "Sob Negociação Especial (> 144 kg)"}
    return {"valor": 11.50, "descricao": "1 Cx Pequena"}

def limpar_cep(cep_raw):
    if not cep_raw:
        return ""
    digits = "".join(c for c in str(cep_raw) if c.isdigit())
    return digits.zfill(8) if digits else ""

def formatar_cep(cep_clean):
    if len(cep_clean) == 8:
        return f"{cep_clean[:5]}-{cep_clean[5:]}"
    return cep_clean

def is_fortaleza_metro(cep_clean):
    if not cep_clean or len(cep_clean) < 8:
        return False
    c5 = int(cep_clean[:5])
    # 60000-000 a 60899-999 (Fortaleza Capital)
    # 61900-000 a 61939-999 (Maracanaú / Região Metropolitana)
    return (60000 <= c5 <= 60899) or (61900 <= c5 <= 61939)

def sincronizar_planilha(forcar=True):
    """
    Baixa a planilha mais recente do Google Sheets com proteção total a Read-only filesystem.
    Salva no diretório temporário do sistema (/tmp no Linux/Vercel) e mantém cópia em memória RAM.
    """
    global _CACHED_BYTES_EXCEL, _CACHED_DOWNLOAD_TIME
    
    agora = datetime.now()
    if not forcar and _CACHED_BYTES_EXCEL and _CACHED_DOWNLOAD_TIME:
        if (agora - _CACHED_DOWNLOAD_TIME).total_seconds() < 600:
            return {"sucesso": True, "mensagem": "Usando planilha em cache da memória."}

    logger.info("Baixando planilha ao vivo do Google Sheets...")
    req = urllib.request.Request(
        GOOGLE_SHEETS_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            if len(data) < 5000:
                raise ValueError(f"Download retornou arquivo inválido ou vazio ({len(data)} bytes).")
            
            _CACHED_BYTES_EXCEL = data
            _CACHED_DOWNLOAD_TIME = agora
            
            # Tenta persistir no diretório /tmp (permitido no Vercel/Linux)
            try:
                with open(CACHE_SHEET_LIVE, "wb") as f:
                    f.write(data)
                logger.info(f"Planilha salva em cache temporário: {CACHE_SHEET_LIVE} ({len(data)} bytes)")
            except Exception as fe:
                logger.warning(f"Não foi possível salvar em disco ({fe}), mantida com sucesso em memória RAM.")
                
            return {"sucesso": True, "mensagem": "Planilha sincronizada diretamente do Google Sheets com sucesso!"}
    except Exception as e:
        logger.warning(f"Erro ao baixar planilha do Google Sheets: {e}. Verificando caches...")
        if _CACHED_BYTES_EXCEL:
            return {"sucesso": True, "aviso": f"Usando última versão baixada em memória ({e})"}
        if os.path.exists(CACHE_SHEET_LIVE):
            return {"sucesso": True, "aviso": f"Usando cópia em cache temporário ({e})"}
        if os.path.exists(LOCAL_SHEET_REPO):
            return {"sucesso": True, "aviso": f"Usando cópia estática do repositório ({e})"}
        if os.path.exists(LOCAL_SHEET_FALLBACK):
            return {"sucesso": True, "aviso": f"Usando cópia de backup do repositório ({e})"}
        raise RuntimeError(f"Não foi possível obter a planilha: {e}")

def carregar_workbook_assinaturas(forcar_download=False):
    """
    Retorna o workbook do OpenpyXL priorizando cache em memória RAM,
    seguido por /tmp, arquivo estático e backup.
    """
    global _CACHED_BYTES_EXCEL
    
    if forcar_download or (_CACHED_BYTES_EXCEL is None and not os.path.exists(CACHE_SHEET_LIVE)):
        try:
            sincronizar_planilha(forcar=forcar_download)
        except Exception as e:
            logger.warning(f"Falha na sincronização inicial: {e}")

    if _CACHED_BYTES_EXCEL:
        return openpyxl.load_workbook(io.BytesIO(_CACHED_BYTES_EXCEL), data_only=True)

    if os.path.exists(CACHE_SHEET_LIVE):
        return openpyxl.load_workbook(CACHE_SHEET_LIVE, data_only=True)

    if os.path.exists(LOCAL_SHEET_REPO):
        return openpyxl.load_workbook(LOCAL_SHEET_REPO, data_only=True)

    if os.path.exists(LOCAL_SHEET_FALLBACK):
        return openpyxl.load_workbook(LOCAL_SHEET_FALLBACK, data_only=True)

    # Tentativa final forçada de download
    sincronizar_planilha(forcar=True)
    if _CACHED_BYTES_EXCEL:
        return openpyxl.load_workbook(io.BytesIO(_CACHED_BYTES_EXCEL), data_only=True)

    raise RuntimeError("Nenhuma fonte de planilha de assinaturas disponível.")

def obter_caminho_planilha():
    """Mantido para compatibilidade."""
    if os.path.exists(CACHE_SHEET_LIVE):
        return CACHE_SHEET_LIVE
    if os.path.exists(LOCAL_SHEET_REPO):
        return LOCAL_SHEET_REPO
    if os.path.exists(LOCAL_SHEET_FALLBACK):
        return LOCAL_SHEET_FALLBACK
    return CACHE_SHEET_LIVE

def mesclar_pedidos_turso_nas_assinaturas(clientes_processados):
    """
    Mescla pedidos faturados de assinaturas gravados no Turso DB
    (tabela assinaturas_pedidos_proximo_envio) ao Lote Trimestral atual.
    Garante que clientes como Marielli Araújo (#18022) recebam os 3 exemplares
    de Jan, Fev e Mar/2027, e gera os metadados de ciclos restantes para a caixinha de controle.
    """
    try:
        import database as db
        df_turso = db.executar_query("SELECT * FROM assinaturas_pedidos_proximo_envio ORDER BY id ASC")
        if df_turso is None or df_turso.empty:
            return clientes_processados

        import re
        cpfs_existentes = {re.sub(r'\D', '', str(c.get("cpf_cnpj") or "")) for c in clientes_processados if c.get("cpf_cnpj")}
        nomes_existentes = {str(c.get("cliente") or "").strip().upper() for c in clientes_processados}

        for _, r in df_turso.iterrows():
            num_ped = str(r.get("numero_pedido") or "").strip()
            cli_nome = str(r.get("cliente_nome") or "").strip()
            cpf_raw = str(r.get("cpf_cnpj") or "").strip()
            cpf_clean = re.sub(r'\D', '', cpf_raw)
            qtd_ass = int(r.get("quantidade_assinaturas") or 1)
            cidade = str(r.get("cidade") or "").strip()
            uf = str(r.get("uf") or "").strip().upper()
            cep_clean = limpar_cep(r.get("cep"))
            rua = str(r.get("rua") or "").strip()
            num = str(r.get("numero") or "").strip()
            comp = str(r.get("complemento") or "").strip()
            bairro = str(r.get("bairro") or "").strip()

            # Evitar duplicar se o assinante já estiver na lista da planilha por CPF ou Nome idêntico
            if cpf_clean and cpf_clean in cpfs_existentes:
                continue
            if cli_nome.upper() in nomes_existentes:
                continue

            # Regra de Elegibilidade do Lote Atual (Jan a Mar/2027):
            # - Combo PRD00379: faturou e enviou Jan/Fev/Mar/2027 diretamente no pedido Omie faturado.
            #   Logo, o cliente JÁ RECEBEU Jan, Fev e Mar! NÃO entra no Lote 1 para evitar envio em duplicidade!
            #   Seu próximo envio é o Lote 2 (Abril/2027) com 9 exemplares restantes.
            # - Combo 000223: faturou Dez/2026 no pedido inicial.
            #   DEVE ENTRAR NO LOTE ATUAL para receber os 3 exemplares de Jan, Fev e Mar/2027.
            #   Como Dezembro já foi enviado na venda, qtd_dez26_extra = 0 (sem badge de enviar dez/26 junto).
            sku_p = str(r.get("sku_produto") or "").strip().upper()
            if "PRD00379" in sku_p:
                continue

            total_exemplares_cliente = qtd_ass * 3
            peso_kg = round(total_exemplares_cliente * 0.100, 3)

            # Ciclos flexíveis respeitando envio trimestral e semestral consolidado (6 meses)
            ciclos_info = {
                "total_contratado": 12 * qtd_ass,
                "ja_recebidos": 1 * qtd_ass,
                "neste_lote": 3 * qtd_ass,
                "restantes_futuros": 8 * qtd_ass,
                "origem": f"Pedido Omie #{num_ped} (Combo {sku_p or '000223'})",
                "etapas": [
                    {"ciclo": "Dezembro/2026", "status": "ENVIADO", "badge": "success", "obs": f"Enviado no Pedido Omie #{num_ped}", "qtd": qtd_ass * 1},
                    {"ciclo": "Jan, Fev, Mar/2027 (Lote 1)", "status": "NESTE_LOTE", "badge": "primary", "obs": "INCLUSO NESTE LOTE ATUAL (1 Jan + 1 Fev + 1 Mar)", "qtd": qtd_ass * 3},
                    {"ciclo": "Abr, Mai, Jun/2027 (Lote 2)", "status": "PENDENTE", "badge": "secondary", "obs": "Aguardando 2º Lote Trimestral", "qtd": qtd_ass * 3},
                    {"ciclo": "Jul a Nov/2027 (Lote 3 - 5 meses)", "status": "PENDENTE", "badge": "secondary", "obs": "Envio Semestral Consolidado (fechamento)", "qtd": qtd_ass * 5}
                ]
            }

            item = {
                "linha_planilha": f"OMIE_{num_ped or r.get('id')}",
                "codigo_cliente": r.get("codigo_cliente_omie") or f"OM_{num_ped}",
                "cliente": cli_nome,
                "cpf_cnpj": cpf_raw,
                "rua": rua,
                "numero": num,
                "complemento": comp,
                "bairro": bairro,
                "cidade": cidade,
                "uf": uf,
                "cep": formatar_cep(cep_clean),
                "cep_limpo": cep_clean,
                "quantidade_assinaturas": qtd_ass,
                "jan27": True,
                "fev27": True,
                "mar27": True,
                "qtd_jan27": qtd_ass,
                "qtd_fev27": qtd_ass,
                "qtd_mar27": qtd_ass,
                "total_exemplares": total_exemplares_cliente,
                "total_exemplares_envio": total_exemplares_cliente,
                "qtd_dez26_extra": 0,
                "observacao_especial": f"Origem: Pedido Omie #{num_ped} (Faturado)",
                "peso_kg": peso_kg,
                "is_renovacao": False,
                "data_registro_base": str(r.get("criado_em") or "")[:10],
                "origem_pedido_omie": num_ped,
                "ciclos_info": ciclos_info
            }
            clientes_processados.append(item)
            nomes_existentes.add(cli_nome.upper())

    except Exception as e:
        logger.warning(f"Erro ao mesclar pedidos Turso nas assinaturas: {e}")

    return clientes_processados

def processar_assinaturas_pdv(forcar_download=False):
    """
    Lê a planilha e calcula elegibilidade para Jan/27, Fev/27, Mar/27
    e divide nos 5 grupos operacionais.
    """
    wb = carregar_workbook_assinaturas(forcar_download=forcar_download)
    
    # Selecionar aba 'Envios PDV'
    ws = None
    for name in wb.sheetnames:
        if "Envios" in name or "PDV" in name:
            ws = wb[name]
            break
    if not ws:
        ws = wb.active

    headers = [c for c in next(ws.iter_rows(max_row=1, values_only=True))]
    col_dez26 = 40 # Dezembro/2026

    clientes_processados = []
    seen_dedup_unicos = set()

    for idx, r in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        reg = r[0]
        cod = r[1]
        qtd = r[2]
        ren_dt = r[3]
        ren_qtd = r[4]
        cli = r[41]
        cpf = str(r[42] or "").strip()
        rua = str(r[43] or "").strip()
        num_raw = r[44]
        if isinstance(num_raw, float) and num_raw.is_integer():
            numero = str(int(num_raw))
        else:
            numero = str(num_raw or "").strip()
            if numero.endswith(".0"):
                numero = numero[:-2]
        compl = str(r[45] or "").strip() if r[45] else ""
        if compl.endswith(".0"):
            compl = compl[:-2]
        bairro = str(r[46] or "").strip()
        cidade = str(r[47] or "").strip()
        uf = str(r[48] or "").strip().upper()
        cep_clean = limpar_cep(r[49])

        if not cli or str(cli).startswith("#") or str(cod).startswith("#"):
            continue

        cli_up = str(cli or "").upper()
        cod_str = str(cod or "")

        # =====================================================================
        # EXCLUSÃO DE PARÓQUIAS E ASSINANTES VENCIDOS (SEM RENOVAÇÃO CONFIRMADA)
        # =====================================================================
        # 1. Jaqueline Alves da Cruz (vencida em jun/26, sem renovação)
        if "JAQUELINE ALVES DA CRUZ" in cli_up or cod_str == "12586":
            continue

        # 2. Paróquia de Nossa Senhora da Glória (vencida)
        if "PAROQUIA DE NOSSA SENHORA DA GLORIA" in cli_up or cod_str == "73":
            continue

        # 3. Paróquia Nossa Senhora do Perpétuo Socorro - Alto Alegre (sem pedido de renovação)
        if "ALTO ALEGRE" in cli_up or cod_str == "568":
            continue

        # 4. Comunidade Católica Shalom Goiânia (sem pedido de renovação)
        if ("SHALOM" in cli_up and ("GOIÂNIA" in cli_up or "GOIANIA" in cli_up)) or cod_str == "16802":
            continue

        # 5. Mitra Diocesana de Lages - P N Sra do Perpétuo Socorro (terminou em nov/26)
        if ("LAGES" in cli_up and "PERP" in cli_up) or cod_str == "20678":
            continue

        # 6. Mitra Diocesana de Guarulhos - Paróquia N Sra Aparecida (terminou em jul/26)
        if ("GUARULHOS" in cli_up and "APARECIDA" in cli_up) or cod_str == "65":
            continue

        # 7. Diocese de Marabá - Paróquia de S. Maria (contrato antigo Cód 184 que terminou em nov/26)
        if cod_str == "184":
            continue

        # =====================================================================
        # DEDUPLICAÇÃO DE ASSINANTES (CONFIRMADO: POSSUEM APENAS 1 ASSINATURA REAL)
        # =====================================================================
        # Excluir o registro duplicado na planilha e manter apenas 1 envio ativo para:
        # 1. Associação Mãe da Divina Misericórdia (Cód 20392, linhas 2 e 20)
        # 2. Thaís Queiroz (Cód 10305, linhas 105 e 699)
        # 3. Sidirlene Santos (Cód 11180, linhas 701 e 1080)
        if cod_str in {"20392", "10305", "11180"} or any(n in cli_up for n in ["DIVINA MISERICORDIA", "DIVINA MISERICÓRDIA", "THAIS QUEIROZ", "THAÍS QUEIROZ", "SIDIRLENE SANTOS"]):
            chave_dedup = cod_str if cod_str else cli_up
            if chave_dedup in seen_dedup_unicos:
                continue
            seen_dedup_unicos.add(chave_dedup)

        # =====================================================================
        # ENRIQUECIMENTO DE CNPJs OFICIAIS DO OMIE ERP PARA PARÓQUIAS VÁLIDAS
        # =====================================================================
        if "PIO DE PIETRELCINA" in cli_up or "MARITUBA" in str(r[47] or "").upper():
            cpf = "04.814.851/0102-72"
        elif "ALFREDO VASCONCELOS" in cli_up or cod_str == "15619":
            cpf = "00.638.765/0001-51"
        elif ("CUIAB" in cli_up or "CUIABA" in str(r[47] or "").upper()) and "ROSARIO" in cli_up:
            cpf = "03.005.139/0015-11"
        elif ("MARABA" in cli_up or "MARABÁ" in cli_up) and ("SANTA MARIA" in cli_up or cod_str == "17339"):
            cpf = "04.882.130/0015-51"

        qtd_val = 1
        if ren_qtd and isinstance(ren_qtd, (int, float)) and ren_qtd > 0:
            qtd_val = int(ren_qtd)
        elif qtd and isinstance(qtd, (int, float)) and qtd > 0:
            qtd_val = int(qtd)

        # =====================================================================
        # REGRA DO CICLO DE 12 EXEMPLARES (ASSINATURA ANUAL BASEADA EM CAIXINHAS)
        # =====================================================================
        # Contagem real de caixinhas marcadas no ciclo de 2026 (colunas 29 a 40)
        # Colunas: 29=Jan/26, 30=Fev/26, 31=Mar/26, ..., 40=Dez/26
        caixinhas_marcadas_2026 = 0
        meses_marcados_nomes = []
        nomes_meses_2026 = ['Jan/26', 'Fev/26', 'Mar/26', 'Abr/26', 'Mai/26', 'Jun/26', 'Jul/26', 'Ago/26', 'Set/26', 'Out/26', 'Nov/26', 'Dez/26']
        for idx_m, c_idx in enumerate(range(29, 41)):
            v = r[c_idx]
            if v is True or v == 1 or str(v).strip().upper() in ['TRUE', 'VERDADEIRO', '1']:
                caixinhas_marcadas_2026 += 1
                meses_marcados_nomes.append(nomes_meses_2026[idx_m])

        dt_base = None
        is_renovacao = False
        elegivel = False
        jan = False
        fev = False
        mar = False
        ja_recebidos_antes = 0
        
        # Prioridade 1: Renovação registrada em 2026 ou 2027
        if ren_dt and isinstance(ren_dt, datetime) and ren_dt.year >= 2026:
            dt_base = ren_dt
            is_renovacao = True
            qtd_val = int(ren_qtd) if ren_qtd and isinstance(ren_qtd, (int, float)) and ren_qtd > 0 else (int(qtd) if qtd and isinstance(qtd, (int, float)) else 1)
        # Prioridade 2: Primeiro registro em 2026 ou 2027
        elif reg and isinstance(reg, datetime) and reg.year >= 2026:
            dt_base = reg
            qtd_val = int(qtd) if qtd and isinstance(qtd, (int, float)) else 1
        elif isinstance(reg, str) and len(reg) >= 10 and reg.startswith("2026"):
            try:
                dt_base = datetime.strptime(reg[:10], "%Y-%m-%d")
                qtd_val = int(qtd) if qtd and isinstance(qtd, (int, float)) else 1
            except Exception:
                pass

        # Prioridade 3: Grandes volumes / Paróquias contínuas institucionais (>= 20 unidades)
        if not dt_base and qtd and isinstance(qtd, (int, float)) and qtd >= 20:
            rec_dez26 = (r[col_dez26] is True or r[col_dez26] == 1 or str(r[col_dez26]).strip().upper() in ['TRUE', 'VERDADEIRO', '1'])
            if rec_dez26:
                jan, fev, mar = True, True, True
                elegivel = True
                qtd_val = int(qtd)
                ja_recebidos_antes = caixinhas_marcadas_2026

        # CÁLCULO PRINCIPAL: BASEADO NA CONTAGEM REAL DE CAIXINHAS RECEBIDAS
        if not elegivel:
            if caixinhas_marcadas_2026 > 0:
                ja_recebidos_antes = caixinhas_marcadas_2026
                saldo_restante = max(0, 12 - ja_recebidos_antes)
                
                # Se já recebeu 12 caixinhas completas (como Mario Brito Cód 424 ou Heloísa Barbosa Cód 555),
                # o ciclo anual de 12 meses já está 100% CONCLUÍDO e não deve receber no Lote 1
                if saldo_restante == 0 and not is_renovacao:
                    continue
                
                # Se ainda tem saldo restante de exemplares a receber do ciclo
                if saldo_restante > 0:
                    jan = (saldo_restante >= 1)
                    fev = (saldo_restante >= 2)
                    mar = (saldo_restante >= 3)
                    elegivel = (jan or fev or mar)
            elif dt_base:
                ano_start = dt_base.year
                m_start = dt_base.month
                ex_jan = (2027 - ano_start) * 12 + (1 - m_start) + 1
                ex_fev = (2027 - ano_start) * 12 + (2 - m_start) + 1
                ex_mar = (2027 - ano_start) * 12 + (3 - m_start) + 1
                jan = (1 <= ex_jan <= 12)
                fev = (1 <= ex_fev <= 12)
                mar = (1 <= ex_mar <= 12)
                elegivel = (jan or fev or mar)
                pos_jan = ex_jan
                ja_recebidos_antes = max(0, (pos_jan - 1)) if pos_jan > 1 else 0

        if not elegivel:
            continue

        # Acréscimo manual solicitado pelo usuário para cliente 15619 (Alfredo Vasconcelos)
        if str(cod) == "15619" or "ALFREDO VASCONCELOS" in str(cli).upper():
            qtd_val += 50 # 101 original + 50 = 151 assinaturas

        # Observação especial solicitada pelo usuário para Silvana Maria dos Santos Silva (Linha 523 / Cód 18427)
        obs_especial = ""
        qtd_dez26_extra = 0
        cli_upper = str(cli).upper()
        if str(cod) == "18427" or "SILVANA MARIA DO SANTOS SILVA" in cli_upper or "SILVANA MARIA DOS SANTOS SILVA" in cli_upper:
            obs_especial = "Enviar 1 und de Dezembro/2026 junto com Jan, Fev e Mar"
            qtd_dez26_extra = 1

        meses_cont = (1 if jan else 0) + (1 if fev else 0) + (1 if mar else 0)
        total_exemplares_cliente = qtd_val * meses_cont
        peso_total_cliente_kg = round((total_exemplares_cliente + qtd_dez26_extra) * 0.100, 3)

        total_apos_lote = ja_recebidos_antes + meses_cont
        restantes_apos_lote = max(0, 12 - total_apos_lote)
        status_apos_lote = "CONCLUIDO" if total_apos_lote >= 12 else "ATIVO"

        etapas_cliente = []
        if ja_recebidos_antes > 0:
            meses_desc = f" ({meses_marcados_nomes[0]} a {meses_marcados_nomes[-1]})" if len(meses_marcados_nomes) >= 2 else (f" ({meses_marcados_nomes[0]})" if meses_marcados_nomes else "")
            etapas_cliente.append({
                "ciclo": "Exemplares Anteriores (2026)",
                "status": "ENVIADO",
                "badge": "success",
                "obs": f"{ja_recebidos_antes} exemplar(es) já recebidos{meses_desc}",
                "qtd": ja_recebidos_antes * qtd_val
            })

        meses_inclusos = []
        if jan: meses_inclusos.append("Jan")
        if fev: meses_inclusos.append("Fev")
        if mar: meses_inclusos.append("Mar")
        str_inclusos = ", ".join(meses_inclusos)

        etapas_cliente.append({
            "ciclo": "Lote 1 (Jan, Fev e Mar/2027)",
            "status": "NESTE_LOTE",
            "badge": "primary",
            "obs": f"{meses_cont} exemplar(es) incluídos neste lote ({str_inclusos})",
            "qtd": total_exemplares_cliente
        })
        if restantes_apos_lote > 0:
            etapas_cliente.append({
                "ciclo": "Próximos Lotes (Abril em diante)",
                "status": "PENDENTE",
                "badge": "secondary",
                "obs": f"{restantes_apos_lote} exemplar(es) restantes para conclusão",
                "qtd": restantes_apos_lote * qtd_val
            })
        else:
            etapas_cliente.append({
                "ciclo": "Conclusão do Contrato Anual",
                "status": "CONCLUIDO",
                "badge": "success",
                "obs": "12 exemplares completados com sucesso neste lote!",
                "qtd": 0
            })

        ciclos_info = {
            "total_contratado": 12 * qtd_val,
            "ja_recebidos": ja_recebidos_antes * qtd_val,
            "neste_lote": total_exemplares_cliente,
            "restantes_futuros": restantes_apos_lote * qtd_val,
            "origem": "Planilha Envios PDV (Controle de Caixinhas)",
            "etapas": etapas_cliente
        }

        item = {
            "linha_planilha": idx,
            "codigo_cliente": cod,
            "cliente": cli,
            "cpf_cnpj": cpf,
            "rua": rua,
            "numero": numero,
            "complemento": compl,
            "bairro": bairro,
            "cidade": cidade,
            "uf": uf,
            "cep": formatar_cep(cep_clean),
            "cep_limpo": cep_clean,
            "quantidade_assinaturas": qtd_val,
            "jan27": jan,
            "fev27": fev,
            "mar27": mar,
            "qtd_jan27": qtd_val if jan else 0,
            "qtd_fev27": qtd_val if fev else 0,
            "qtd_mar27": qtd_val if mar else 0,
            "total_exemplares": total_exemplares_cliente,
            "total_exemplares_envio": total_exemplares_cliente + qtd_dez26_extra,
            "qtd_dez26_extra": qtd_dez26_extra,
            "observacao_especial": obs_especial,
            "peso_kg": peso_total_cliente_kg,
            "is_renovacao": is_renovacao,
            "data_registro_base": dt_base.strftime("%d/%m/%Y") if dt_base else "-",
            "status_assinatura": status_apos_lote,
            "ja_recebidos_antes": ja_recebidos_antes,
            "restantes_apos_lote": restantes_apos_lote,
            "ciclos_info": {
                "total_contratado": 12 * qtd_val,
                "ja_recebidos": ja_recebidos_antes * qtd_val,
                "neste_lote": total_exemplares_cliente,
                "restantes_futuros": restantes_apos_lote * qtd_val,
                "status_apos_lote": status_apos_lote,
                "meses_cont": meses_cont,
                "origem": "Base de Assinantes (Planilha/Turso)",
                "etapas": etapas_cliente
            }
        }
        clientes_processados.append(item)

    # Mesclar pedidos de venda novos faturados no Omie registrados no Turso DB
    clientes_processados = mesclar_pedidos_turso_nas_assinaturas(clientes_processados)

    # Classificar os 5 grupos
    g1_paroquias_ce = []
    g2_paroquias_fora = []
    g3_finais_fortaleza = []
    g4_finais_pac_norte = []
    g5_finais_modico_brasil = []

    for c in clientes_processados:
        qtd = c["quantidade_assinaturas"]
        cep = c["cep_limpo"]
        uf = c["uf"]
        cidade = c["cidade"].upper()

        eh_fortaleza = is_fortaleza_metro(cep) or (uf == "CE" and "FORTALEZA" in cidade)

        if qtd >= 20:
            if eh_fortaleza:
                # Calcular frete do Roberto para paróquias Fortaleza
                frete_info = calcular_frete_tabela(c["peso_kg"])
                c["frete_previsto"] = frete_info["valor"]
                c["frete_obs"] = frete_info["descricao"]
                c["transportadora"] = "Roberto Souza de Oliveira"
                c["cfop"] = "5949"
                g1_paroquias_ce.append(c)
            else:
                c["transportadora"] = "PAC Correios ou Braspress (Cotação por Peso)"
                c["cfop"] = "6949"
                g2_paroquias_fora.append(c)
        else:
            if eh_fortaleza:
                # Roberto Souza cobra R$ 4,50 fixo por entrega/cliente final, independente do peso ou quantidade
                c["custo_entrega"] = 4.50
                c["entregador"] = "Roberto Souza de Oliveira (R$ 4,50 fixo/entrega)"
                g3_finais_fortaleza.append(c)
            elif uf in ESTADOS_PAC_OBRIGATORIO:
                c["tipo_envio"] = "PAC Correios (Exceção Estados Distantes)"
                g4_finais_pac_norte.append(c)
            else:
                c["tipo_envio"] = "Impresso Módico Correios"
                g5_finais_modico_brasil.append(c)

    # Totais consolidados
    tot_jan = sum(c["qtd_jan27"] for c in clientes_processados)
    tot_fev = sum(c["qtd_fev27"] for c in clientes_processados)
    tot_mar = sum(c["qtd_mar27"] for c in clientes_processados)
    tot_geral_pecas = tot_jan + tot_fev + tot_mar
    tot_geral_peso = round(tot_geral_pecas * 0.100, 2)

    def resumir_grupo(lista, nome_id, titulo, descricao, tipo_logistica, custo_total_frete=None):
        q_jan = sum(x["qtd_jan27"] for x in lista)
        q_fev = sum(x["qtd_fev27"] for x in lista)
        q_mar = sum(x["qtd_mar27"] for x in lista)
        tot_pecas = q_jan + q_fev + q_mar
        tot_peso = round(tot_pecas * 0.100, 2)
        tot_assinaturas = sum(x["quantidade_assinaturas"] for x in lista)
        res = {
            "id": nome_id,
            "titulo": titulo,
            "descricao": descricao,
            "tipo_logistica": tipo_logistica,
            "total_clientes": len(lista),
            "total_assinaturas": tot_assinaturas,
            "jan27": q_jan,
            "fev27": q_fev,
            "mar27": q_mar,
            "total_pecas": tot_pecas,
            "total_peso_kg": tot_peso,
            "clientes": lista
        }
        if custo_total_frete is not None:
            res["custo_total_frete"] = custo_total_frete
        return res

    grupos = {
        "paroquias_ce": resumir_grupo(
            g1_paroquias_ce, "paroquias_ce",
            "Paróquias e Grandes Assinantes Fortaleza & CE (≥ 20 un)",
            "Grandes volumes com entrega em Fortaleza/CE. CFOP 5949, Categoria Receita Comercial 1.01.01, Transportadora Roberto Souza.",
            "Transportadora Roberto Souza de Oliveira"
        ),
        "paroquias_fora": resumir_grupo(
            g2_paroquias_fora, "paroquias_fora",
            "Paróquias e Grandes Assinantes Outros Estados (≥ 20 un)",
            "Grandes volumes fora do CE. Cotação por peso total via PAC ou Braspress. CFOP 6949.",
            "Cotação PAC / Braspress"
        ),
        "finais_fortaleza": resumir_grupo(
            g3_finais_fortaleza, "finais_fortaleza",
            "Clientes Finais Fortaleza (1 a 19 un)",
            "Entregas locais em Fortaleza com Roberto Souza (R$ 4,50 fixo por cliente/entrega). Remessa de Baixa no Omie.",
            "Entregador Roberto Souza (R$ 4,50 fixo/entrega)",
            custo_total_frete=round(len(g3_finais_fortaleza) * 4.50, 2)
        ),
        "finais_modico_brasil": resumir_grupo(
            g5_finais_modico_brasil, "finais_modico_brasil",
            "Clientes Finais Brasil - Impresso Módico (1 a 19 un)",
            "Envio econômico via Correios (Impresso Módico). Exportação de etiquetas para Correios e baixa no Omie.",
            "Correios Impresso Módico"
        ),
        "finais_pac_norte": resumir_grupo(
            g4_finais_pac_norte, "finais_pac_norte",
            "Clientes Finais Estados Demorados - PAC Obrigatório (1 a 19 un)",
            "Região Norte (AM, AC, RR, AP, PA, RO, TO). Obrigatoriamente enviados por PAC devido ao prazo dos Correios.",
            "Correios PAC Obrigatório"
        )
    }

    return {
        "sucesso": True,
        "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "produtos": PRODUTOS_LITURGIA,
        "consolidado_geral": {
            "total_clientes_elegiveis": len(clientes_processados),
            "jan27": tot_jan,
            "fev27": tot_fev,
            "mar27": tot_mar,
            "total_pecas": tot_geral_pecas,
            "total_peso_kg": tot_geral_peso
        },
        "grupos": grupos
    }

def gerar_excel_etiquetas(grupo_id="todos"):
    """
    Gera uma planilha Excel pronta para download com as etiquetas, rotas de envio
    e auditoria de ciclos (já recebidos, neste lote e restantes).
    Suporta grupo específico ou 'todos' / 'geral' para consolidado de todos os grupos.
    """
    dados = processar_assinaturas_pdv(forcar_download=False)
    
    if grupo_id in ("todos", "geral", "consolidado", "") or not grupo_id:
        clientes_lista = []
        for g_chave, g_dados in dados["grupos"].items():
            for c in g_dados["clientes"]:
                c_copy = dict(c)
                c_copy["grupo_nome"] = g_dados["titulo"]
                clientes_lista.append(c_copy)
        titulo_aba = "Auditoria Completa (Todos)"
    else:
        grupo = dados["grupos"].get(grupo_id)
        if not grupo:
            raise ValueError(f"Grupo {grupo_id} não encontrado.")
        clientes_lista = []
        for c in grupo["clientes"]:
            c_copy = dict(c)
            c_copy["grupo_nome"] = grupo["titulo"]
            clientes_lista.append(c_copy)
        titulo_aba = f"Etiquetas - {grupo_id[:20]}"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = titulo_aba[:31]

    # Estilos
    header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")

    headers = [
        "Linha", "Cód. Cliente", "Destinatário / Cliente", "CPF / CNPJ", "Grupo / Modalidade",
        "Logradouro", "Número", "Complemento", "Bairro", "Cidade", "UF", "CEP",
        "Assinaturas", "Jan/27", "Fev/27", "Mar/27", "Exemplares Lote Atual",
        "Já Recebidos (2026)", "Restantes Futuros", "Status Contrato", "Peso (kg)", "Obs / Envio"
    ]
    ws.append(headers)

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for c in clientes_lista:
        obs_extra = c.get("entregador") or c.get("transportadora") or c.get("tipo_envio") or c.get("observacao_especial") or ""
        row = [
            c.get("linha_planilha"),
            c.get("codigo_cliente"),
            c.get("cliente"),
            c.get("cpf_cnpj"),
            c.get("grupo_nome"),
            c.get("rua"),
            c.get("numero"),
            c.get("complemento"),
            c.get("bairro"),
            c.get("cidade"),
            c.get("uf"),
            c.get("cep"),
            c.get("quantidade_assinaturas"),
            c.get("qtd_jan27"),
            c.get("qtd_fev27"),
            c.get("qtd_mar27"),
            c.get("total_exemplares_envio") or c.get("total_exemplares"),
            c.get("ja_recebidos_antes", 0),
            c.get("restantes_apos_lote", 0),
            c.get("status_assinatura", "ATIVO"),
            c.get("peso_kg"),
            obs_extra
        ]
        ws.append(row)

    # Ajuste de largura de colunas
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 50)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()

def gerar_remessa_baixa_omie(grupo_id, conta="MATRIZ"):
    """
    Cria a Remessa de Baixa de Estoque no Omie para o grupo selecionado
    (Clientes Finais Fortaleza, Clientes Finais Correios Módico ou PAC Norte).
    """
    dados = processar_assinaturas_pdv(forcar_download=False)
    grupo = dados["grupos"].get(grupo_id)
    if not grupo:
        raise ValueError(f"Grupo {grupo_id} inválido.")

    q_jan = grupo["jan27"]
    q_fev = grupo["fev27"]
    q_mar = grupo["mar27"]

    if q_jan + q_fev + q_mar == 0:
        raise ValueError("Não há itens para gerar remessa neste grupo.")

    obs_map = {
        "finais_fortaleza": "Baixa de Liturgias enviadas a clientes finais Fortaleza",
        "finais_modico_brasil": "Baixa de Liturgias enviadas a clientes finais Brasil - Impresso Módico",
        "finais_pac_norte": "Baixa de Liturgias enviadas a clientes finais Brasil - PAC Norte",
    }
    observacao = obs_map.get(grupo_id, f"Baixa de Liturgias enviadas a {grupo['titulo']}")

    # Montar itens da remessa
    itens = []
    num_item = 1
    if q_jan > 0:
        itens.append({
            "num_item": num_item,
            "codigo_produto": PRODUTOS_LITURGIA["jan27"]["id_matriz"],
            "quantidade": q_jan,
            "valor_unitario": 0.01,
            "cfop": "5949"
        })
        num_item += 1

    if q_fev > 0:
        itens.append({
            "num_item": num_item,
            "codigo_produto": PRODUTOS_LITURGIA["fev27"]["id_matriz"],
            "quantidade": q_fev,
            "valor_unitario": 0.01,
            "cfop": "5949"
        })
        num_item += 1

    if q_mar > 0:
        itens.append({
            "num_item": num_item,
            "codigo_produto": PRODUTOS_LITURGIA["mar27"]["id_matriz"],
            "quantidade": q_mar,
            "valor_unitario": 0.01,
            "cfop": "5949"
        })
        num_item += 1

    payload_remessa = {
        "cabecalho": {
            "codigo_cliente": CLIENTE_EDICOES_SHALOM_ID,
            "codigo_cenario_impostos": 0, # Cenário Baixa / Simples
            "data_emissao": datetime.now().strftime("%d/%m/%Y"),
            "observacoes": observacao
        },
        "itens": itens
    }

    # Chaves da Matriz
    key = os.getenv("APP_KEY_MATRIZ", "").strip(" \"'")
    sec = os.getenv("APP_SECRET_MATRIZ", "").strip(" \"'")

    logger.info(f"Disparando IncluirRemessa para {grupo_id} no Omie: {payload_remessa}")
    url = "https://app.omie.com.br/api/v1/produtos/remessa/"
    res = requests.post(url, json={
        "call": "IncluirRemessa",
        "app_key": key,
        "app_secret": sec,
        "param": [payload_remessa]
    }).json()

    if res.get("faultstring"):
        logger.error(f"Erro Omie ao incluir remessa: {res.get('faultstring')}")
        return {
            "sucesso": False,
            "erro": res.get("faultstring"),
            "detalhes": res
        }

    return {
        "sucesso": True,
        "numero_remessa": res.get("numero_remessa"),
        "codigo_remessa": res.get("codigo_remessa"),
        "grupo": grupo_id,
        "total_pecas": q_jan + q_fev + q_mar,
        "observacao": observacao
    }

# Mapeamento de Clientes Paróquias Conhecidas no Omie
CLIENTES_PAROQUIAS_OMIE = {
    "PAROQUIA DE NOSSA SENHORA DA GLORIA": 1863704996,
    "73": 1863704996,
    "PAROQUIA DE NOSSA SENHORA DO PERPETUO SOCORRO - Alto alegre": 2027483054,
    "PAROQUIA DE NOSSA SENHORA DO PERPETUO SOCORRO - ALTO ALEGRE": 2027483054,
    "568": 2027483054,
    "PAROQUIA NOSSA SENHORA DO ROSARIO EM ALFREDO VASCONCELOS - MG": 2216020406,
    "ALFREDO VASCONCELOS": 2216020406,
    "15619": 2216020406,
    "PAROQUIA NOSSA SENHORA DO ROSARIO - Mitra Arquidiocesana de Cuiaba": 1854967420,
    "CUIABA": 1854967420,
    "16384": 1854967420,
    "Comunidade Católica Shalom Goiânia": 1903882289,
    "Comunidade Católica Shalom Comunidade Católica Shalom Goiânia": 1903882289,
    "16802": 1903882289
}

def buscar_ou_identificar_id_cliente_omie(cliente_item):
    """Retorna o codigo_cliente_omie para a paróquia ou busca por CNPJ/Nome."""
    cod = str(cliente_item.get("codigo_cliente") or "").strip()
    if cod in CLIENTES_PAROQUIAS_OMIE:
        return CLIENTES_PAROQUIAS_OMIE[cod]

    nome = cliente_item.get("cliente", "").strip()
    for k, v in CLIENTES_PAROQUIAS_OMIE.items():
        if k.lower() in nome.lower() or nome.lower() in k.lower():
            return v
    
    cpf_cnpj = cliente_item.get("cpf_cnpj", "").strip()
    key = os.getenv("APP_KEY_MATRIZ", "").strip(" \"'")
    sec = os.getenv("APP_SECRET_MATRIZ", "").strip(" \"'")
    url = "https://app.omie.com.br/api/v1/geral/clientes/"

    if cpf_cnpj and len(cpf_cnpj) >= 11:
        try:
            r = requests.post(url, json={
                "call": "ConsultarCliente",
                "app_key": key,
                "app_secret": sec,
                "param": [{"cnpj_cpf": cpf_cnpj}]
            }).json()
            if r.get("codigo_cliente_omie"):
                return r.get("codigo_cliente_omie")
        except Exception as e:
            logger.warning(f"Erro ao buscar cliente por CPF/CNPJ: {e}")

    # Fallback busca por fantasia
    try:
        palavra = nome.split()[0] if nome else ""
        if len(palavra) >= 4:
            r2 = requests.post(url, json={
                "call": "ListarClientesResumido",
                "app_key": key,
                "app_secret": sec,
                "param": [{
                    "pagina": 1,
                    "registros_por_pagina": 10,
                    "apenas_importado_api": "N",
                    "clientesFiltro": {"nome_fantasia": palavra}
                }]
            }).json()
            for c in r2.get("clientes_cadastro_resumido", []):
                if c.get("codigo_cliente"):
                    return c.get("codigo_cliente")
    except Exception as e:
        logger.warning(f"Erro ao buscar cliente por fantasia: {e}")

    return None

def gerar_remessa_paroquia_omie(cliente_dados, valor_frete=None, transportadora_id=None):
    """
    Cria a Remessa padrão no Omie para uma paróquia específica.
    Cenário padrão, CFOP 5949 (dentro do CE) ou 6949 (fora do CE),
    Categoria Receita Comercial (1.01.01), Transportadora Roberto Souza.
    """
    cod_cliente_omie = buscar_ou_identificar_id_cliente_omie(cliente_dados)
    if not cod_cliente_omie:
        raise ValueError(f"Não foi possível localizar o código do cliente Omie para: {cliente_dados.get('cliente')}")

    is_ce = (cliente_dados.get("uf") == "CE") or is_fortaleza_metro(cliente_dados.get("cep_limpo", ""))
    cfop = "5949" if is_ce else "6949"

    q_jan = int(cliente_dados.get("qtd_jan27", 0))
    q_fev = int(cliente_dados.get("qtd_fev27", 0))
    q_mar = int(cliente_dados.get("qtd_mar27", 0))

    if q_jan + q_fev + q_mar == 0:
        raise ValueError("Quantidade de itens da remessa zerada.")

    itens = []
    num_item = 1
    if q_jan > 0:
        itens.append({
            "num_item": num_item,
            "codigo_produto": PRODUTOS_LITURGIA["jan27"]["id_matriz"],
            "quantidade": q_jan,
            "valor_unitario": 0.01,
            "cfop": cfop
        })
        num_item += 1

    if q_fev > 0:
        itens.append({
            "num_item": num_item,
            "codigo_produto": PRODUTOS_LITURGIA["fev27"]["id_matriz"],
            "quantidade": q_fev,
            "valor_unitario": 0.01,
            "cfop": cfop
        })
        num_item += 1

    if q_mar > 0:
        itens.append({
            "num_item": num_item,
            "codigo_produto": PRODUTOS_LITURGIA["mar27"]["id_matriz"],
            "quantidade": q_mar,
            "valor_unitario": 0.01,
            "cfop": cfop
        })
        num_item += 1

    transp = transportadora_id or (TRANSPORTADORA_ROBERTO_ID if is_ce else None)
    
    cabecalho = {
        "codigo_cliente": cod_cliente_omie,
        "codigo_cenario_impostos": 0,
        "categoria": CATEGORIA_RECEITA_COMERCIAL,
        "data_emissao": datetime.now().strftime("%d/%m/%Y"),
        "observacoes": f"Remessa Liturgia Diária Pão da Vida (Jan/Fev/Mar 2027) - Paróquia {cliente_dados.get('cliente')}"
    }

    if transp:
        cabecalho["codigo_transportadora"] = transp

    if valor_frete is not None and float(valor_frete) > 0:
        cabecalho["valor_frete"] = float(valor_frete)

    payload_remessa = {
        "cabecalho": cabecalho,
        "itens": itens
    }

    key = os.getenv("APP_KEY_MATRIZ", "").strip(" \"'")
    sec = os.getenv("APP_SECRET_MATRIZ", "").strip(" \"'")

    logger.info(f"Disparando IncluirRemessa de Paróquia no Omie: {payload_remessa}")
    url = "https://app.omie.com.br/api/v1/produtos/remessa/"
    res = requests.post(url, json={
        "call": "IncluirRemessa",
        "app_key": key,
        "app_secret": sec,
        "param": [payload_remessa]
    }).json()

    if res.get("faultstring"):
        logger.error(f"Erro Omie ao incluir remessa de paróquia: {res.get('faultstring')}")
        return {
            "sucesso": False,
            "erro": res.get("faultstring"),
            "detalhes": res
        }

    return {
        "sucesso": True,
        "numero_remessa": res.get("numero_remessa"),
        "codigo_remessa": res.get("codigo_remessa"),
        "cliente": cliente_dados.get("cliente"),
        "codigo_cliente_omie": cod_cliente_omie,
        "total_pecas": q_jan + q_fev + q_mar,
        "cfop": cfop,
        "valor_frete": valor_frete
    }

# =============================================================================
# EXPORTAÇÃO PADRÃO OFICIAL DOS CORREIOS (SIGEP / PRE-POSTAGEM)
# =============================================================================
CORREIOS_COLUNAS = [
    "NOME",
    "EMPRESA",
    "CPF",
    "CEP",
    "ENDEREÇO",
    "NUMERO",
    "COMPLEMENTO",
    "BAIRRO",
    "CIDADE",
    "UF",
    "AOS_CUIDADOS",
    "NOTA_FISCAL",
    "SERVICO",
    "SERV_ADICIONAIS",
    "VALOR_DECLARADO",
    "OBSERVAÇÕES",
    "CONTEUDO",
    "DDD",
    "TELEFONE",
    "EMAIL",
    "IDENTIFICADOR_CLIENTE (chave do cliente)",
    "PESO",
    "ALTURA",
    "LARGURA",
    "COMPRIMENTO",
    "ENTREGA_VIZINHO",
    "RFID",
    "CHAVE_NOTA_FISCAL"
]

def obter_texto_periodo_etiqueta(c):
    """
    Formata o texto de período para a etiqueta e coluna NOTA_FISCAL dos Correios
    Ex: '1 Jan. à Mar', '1 Jan', '2 Jan. à Mar', '151 Jan. à Mar'
    """
    jan = bool(c.get("jan27"))
    fev = bool(c.get("fev27"))
    mar = bool(c.get("mar27"))
    qtd = c.get("quantidade_assinaturas", 1)
    extra_dez = c.get("qtd_dez26_extra", 0)

    if jan and fev and mar:
        base = f"{qtd} Jan. à Mar"
    elif jan and fev and not mar:
        base = f"{qtd} Jan. e Fev"
    elif jan and not fev and not mar:
        base = f"{qtd} Jan"
    elif not jan and fev and mar:
        base = f"{qtd} Fev. e Mar"
    elif not jan and fev and not mar:
        base = f"{qtd} Fev"
    elif not jan and not fev and mar:
        base = f"{qtd} Mar"
    elif jan and not fev and mar:
        base = f"{qtd} Jan. e Mar"
    else:
        base = f"{qtd} Exemplares"

    if extra_dez > 0:
        return f"{base} (+ 1 Dez/26)"
    return base

def obter_clientes_do_filtro(dados, grupo_id):
    """Retorna lista de clientes conforme o filtro selecionado."""
    if grupo_id == "todos_correios":
        # Junta Impresso Módico + PAC Norte
        g_mod = dados["grupos"].get("finais_modico_brasil", {}).get("clientes", [])
        g_pac = dados["grupos"].get("finais_pac_norte", {}).get("clientes", [])
        return g_mod + g_pac
    elif grupo_id == "todos":
        lista = []
        for g in dados["grupos"].values():
            lista.extend(g.get("clientes", []))
        return lista
    else:
        grupo = dados["grupos"].get(grupo_id)
        if not grupo:
            raise ValueError(f"Grupo {grupo_id} não encontrado.")
        return grupo.get("clientes", [])

def gerar_arquivo_correios(grupo_id, formato="xlsx"):
    """
    Gera o arquivo padronizado dos Correios com 28 colunas exatas
    nos formatos .XLSX ou .CSV (UTF-8 com BOM).
    """
    dados = processar_assinaturas_pdv(forcar_download=False)
    clientes = obter_clientes_do_filtro(dados, grupo_id)

    linhas_dados = []
    for c in clientes:
        obs_c = c.get("observacao_especial", "")
        conteudo_c = "LITURGIAS (+ 1 DEZ/26)" if c.get("qtd_dez26_extra") else "LITURGIAS"
        linha = [
            c.get("cliente", ""),                                # NOME
            "",                                                   # EMPRESA
            c.get("cpf_cnpj", ""),                               # CPF
            c.get("cep", ""),                                    # CEP
            c.get("rua", ""),                                    # ENDEREÇO
            c.get("numero", ""),                                 # NUMERO
            c.get("complemento", "") or "",                      # COMPLEMENTO
            c.get("bairro", ""),                                 # BAIRRO
            c.get("cidade", ""),                                 # CIDADE
            c.get("uf", ""),                                     # UF
            "",                                                   # AOS_CUIDADOS
            obter_texto_periodo_etiqueta(c),                     # NOTA_FISCAL (Ex: 1 Jan. à Mar)
            "",                                                   # SERVICO
            "",                                                   # SERV_ADICIONAIS
            "",                                                   # VALOR_DECLARADO
            obs_c,                                                # OBSERVAÇÕES
            conteudo_c,                                           # CONTEUDO
            "",                                                   # DDD
            "",                                                   # TELEFONE
            "",                                                   # EMAIL
            str(c.get("codigo_cliente") or c.get("linha_planilha") or ""), # IDENTIFICADOR_CLIENTE
            "",                                                   # PESO
            "",                                                   # ALTURA
            "",                                                   # LARGURA
            "",                                                   # COMPRIMENTO
            "",                                                   # ENTREGA_VIZINHO
            "",                                                   # RFID
            ""                                                    # CHAVE_NOTA_FISCAL
        ]
        linhas_dados.append(linha)

    if formato.lower() == "csv":
        import csv
        output = io.StringIO()
        # Escreve com delimitador vírgula e quote nos campos necessários
        writer = csv.writer(output, delimiter=",", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(CORREIOS_COLUNAS)
        for row in linhas_dados:
            writer.writerow(row)
        # Retorna bytes codificados em UTF-8 com BOM para Excel e Correios
        return output.getvalue().encode("utf-8-sig")

    else:
        # Formato XLSX
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Correios"

        # Cabeçalho estilizado
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Arial", size=9, bold=True, color="FFFFFF")
        border_thin = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0")
        )

        ws.append(CORREIOS_COLUNAS)
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        ws.row_dimensions[1].height = 28

        for row_data in linhas_dados:
            ws.append(row_data)

        # Ajuste de largura das colunas
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 11), 40)

        out_bin = io.BytesIO()
        wb.save(out_bin)
        out_bin.seek(0)
        return out_bin.getvalue()


# =============================================================================
# RELATÓRIO OPERACIONAL EM PDF DE CONFERÊNCIA E ETIQUETAS (REPORTLAB)
# =============================================================================
class NumberedCanvas(canvas.Canvas):
    """Canvas com numeração de páginas 'Página X de Y' e rodapé institucional."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Linha fina de separação
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(20, 25, 822, 25)

        # Texto do rodapé
        self.drawString(20, 15, "Edições Shalom — Sistema DRP Omie | Relatório de Envio de Assinaturas Liturgia Diária 2027")
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(822, 15, page_str)
        self.restoreState()

def gerar_pdf_espelho_remessa_individual(cliente):
    """
    Gera um Espelho de Remessa / Ordem de Separação Individual (A4 Retrato)
    específico para uma Paróquia ou Assinante individual, parecendo a DANFE/espelho de remessa
    do Omie para conferência física antes da emissão.
    """
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4, # 595.27 x 841.89 pt
        leftMargin=25,
        rightMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()

    st_title = ParagraphStyle('RTitle', fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=colors.HexColor("#0F172A"))
    st_sub = ParagraphStyle('RSub', fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor("#475569"))
    st_sec = ParagraphStyle('RSec', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor("#1E3A8A"))
    st_th = ParagraphStyle('RTH', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white, alignment=1)
    st_td = ParagraphStyle('RTD', fontName='Helvetica', fontSize=8, leading=10.5, textColor=colors.HexColor("#1E293B"))
    st_td_center = ParagraphStyle('RTDC', fontName='Helvetica', fontSize=8, leading=10.5, alignment=1, textColor=colors.HexColor("#1E293B"))
    st_td_bold_center = ParagraphStyle('RTDBC', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=1, textColor=colors.HexColor("#047857"))

    story = []

    # Cabeçalho Oficial
    cli_cod = cliente.get("codigo_cliente") or cliente.get("linha_planilha") or "-"
    num_remessa_prev = f"REM-SEP-{cli_cod}-2027"
    
    header_data = [
        [
            Paragraph("<b>EDIÇÕES SHALOM</b><br/><font size=7.5 color='#475569'>Comunidade Católica Shalom | CNPJ: 07.044.456/0001-00<br/>Rua Maria Tomásia, 72 - Aldeota, Fortaleza - CE | CEP: 60150-170</font>", st_sub),
            Paragraph(f"<b>ESPELHO DE REMESSA & SEPARAÇÃO</b><br/><font size=9 color='#B45309'><b>{num_remessa_prev}</b></font><br/><font size=7.5 color='#64748B'>Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}</font>", st_title)
        ]
    ]
    t_header = Table(header_data, colWidths=[315, 230])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 8))

    # Natureza da Operação e Dados Fiscais Previstos
    is_ce = (cliente.get("uf") == "CE") or is_fortaleza_metro(cliente.get("cep_limpo", ""))
    cfop_prev = cliente.get("cfop") or ("5949" if is_ce else "6949")
    fisc_data = [
        [
            Paragraph("<b>NATUREZA DA OPERAÇÃO:</b> REMESSA PARA DISTRIBUIÇÃO / ASSINATURA PÃO DA VIDA", st_sub),
            Paragraph(f"<b>CFOP PREVISTO:</b> {cfop_prev}", st_sub),
            Paragraph("<b>CATEGORIA OMIE:</b> 1.01.01", st_sub),
        ]
    ]
    t_fisc = Table(fisc_data, colWidths=[270, 135, 140])
    t_fisc.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_fisc)
    story.append(Spacer(1, 8))

    # Bloco Destinatário
    compl_txt = f" ({cliente.get('complemento')})" if cliente.get('complemento') else ""
    end_dest = f"{cliente.get('rua', '')}, {cliente.get('numero', '')}{compl_txt} - {cliente.get('bairro', '')}"
    dest_data = [
        [Paragraph("<b>DADOS DO DESTINATÁRIO / ASSINANTE</b>", st_sec), Paragraph("", st_sec)],
        [
            Paragraph(f"<b>Razão Social / Nome:</b> {cliente.get('cliente', '')}", st_td),
            Paragraph(f"<b>CPF / CNPJ:</b> {cliente.get('cpf_cnpj') or 'Não informado'}", st_td)
        ],
        [
            Paragraph(f"<b>Endereço de Entrega:</b> {end_dest}", st_td),
            Paragraph(f"<b>Cód. Cliente:</b> {cliente.get('codigo_cliente') or '-'} (Linha: {cliente.get('linha_planilha')})", st_td)
        ],
        [
            Paragraph(f"<b>Município / UF:</b> {cliente.get('cidade', '')} / <b>{cliente.get('uf', '')}</b>", st_td),
            Paragraph(f"<b>CEP:</b> {cliente.get('cep', '')}", st_td)
        ]
    ]
    t_dest = Table(dest_data, colWidths=[365, 180])
    t_dest.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EFF6FF")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#93C5FD")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#DBEAFE")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_dest)
    story.append(Spacer(1, 8))

    # Bloco Transportador & Frete
    transp_nome = cliente.get("transportadora") or cliente.get("entregador") or ("Roberto Souza de Oliveira" if is_ce else "PAC / Correios / Braspress")
    frete_val_txt = f"R$ {cliente.get('frete_previsto', 0):,.2f}" if cliente.get('frete_previsto') else (f"R$ {cliente.get('custo_entrega', 0):,.2f}" if cliente.get('custo_entrega') else "A calcular na cotação")
    transp_data = [
        [Paragraph("<b>DADOS DA LOGÍSTICA & TRANSPORTE</b>", st_sec), Paragraph("", st_sec)],
        [
            Paragraph(f"<b>Transportadora / Entregador:</b> {transp_nome}", st_td),
            Paragraph(f"<b>Frete Previsto:</b> <b>{frete_val_txt}</b>", st_td)
        ],
        [
            Paragraph(f"<b>Modalidade de Frete:</b> Conta do Emitente (CIF / Contratual Shalom)", st_td),
            Paragraph(f"<b>Condição de Envio:</b> {cliente.get('frete_obs') or 'Entrega Direta no Endereço'}", st_td)
        ]
    ]
    t_transp = Table(transp_data, colWidths=[365, 180])
    t_transp.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_transp)
    story.append(Spacer(1, 10))

    # Tabela Grade de Itens da Remessa / Almoxarifado
    q_jan = int(cliente.get("qtd_jan27", 0))
    q_fev = int(cliente.get("qtd_fev27", 0))
    q_mar = int(cliente.get("qtd_mar27", 0))
    tot_pecas = q_jan + q_fev + q_mar
    tot_peso = round(tot_pecas * 0.100, 3)

    items_header = [
        Paragraph("Item", st_th),
        Paragraph("Cód. Omie", st_th),
        Paragraph("Descrição do Produto", st_th),
        Paragraph("Mês Ref.", st_th),
        Paragraph("Qtd Separar", st_th),
        Paragraph("Peso Unit.", st_th),
        Paragraph("Peso Total", st_th),
        Paragraph("Visto [ ✓ ]", st_th)
    ]
    items_rows = [items_header]

    idx_item = 1
    if q_jan > 0:
        items_rows.append([
            Paragraph(str(idx_item), st_td_center),
            Paragraph("PRD00561", st_td_center),
            Paragraph("LITURGIA DIARIA JANEIRO - 2027", st_td),
            Paragraph("Jan/2027", st_td_center),
            Paragraph(f"<b>{q_jan} un</b>", st_td_bold_center),
            Paragraph("0,100 kg", st_td_center),
            Paragraph(f"{round(q_jan * 0.100, 2):,.2f} kg", st_td_center),
            Paragraph("[    ]", st_td_center)
        ])
        idx_item += 1

    if q_fev > 0:
        items_rows.append([
            Paragraph(str(idx_item), st_td_center),
            Paragraph("PRD00562", st_td_center),
            Paragraph("LITURGIA DIARIA FEVEREIRO - 2027", st_td),
            Paragraph("Fev/2027", st_td_center),
            Paragraph(f"<b>{q_fev} un</b>", st_td_bold_center),
            Paragraph("0,100 kg", st_td_center),
            Paragraph(f"{round(q_fev * 0.100, 2):,.2f} kg", st_td_center),
            Paragraph("[    ]", st_td_center)
        ])
        idx_item += 1

    if q_mar > 0:
        items_rows.append([
            Paragraph(str(idx_item), st_td_center),
            Paragraph("PRD00563", st_td_center),
            Paragraph("LITURGIA DIARIA MARÇO - 2027", st_td),
            Paragraph("Mar/2027", st_td_center),
            Paragraph(f"<b>{q_mar} un</b>", st_td_bold_center),
            Paragraph("0,100 kg", st_td_center),
            Paragraph(f"{round(q_mar * 0.100, 2):,.2f} kg", st_td_center),
            Paragraph("[    ]", st_td_center)
        ])
        idx_item += 1

    # Exemplar extra de Dez/26 se houver
    if cliente.get("qtd_dez26_extra"):
        items_rows.append([
            Paragraph(str(idx_item), st_td_center),
            Paragraph("EXTRA", st_td_center),
            Paragraph("LITURGIA DIARIA DEZEMBRO - 2026 (Item Complementar)", st_td),
            Paragraph("Dez/2026", st_td_center),
            Paragraph("<b>1 un</b>", st_td_bold_center),
            Paragraph("0,100 kg", st_td_center),
            Paragraph("0,10 kg", st_td_center),
            Paragraph("[    ]", st_td_center)
        ])
        tot_pecas += 1
        tot_peso = round(tot_peso + 0.100, 3)

    # Linha Total
    items_rows.append([
        Paragraph("<b>TOTAL</b>", st_td_center),
        Paragraph("", st_td_center),
        Paragraph("<b>TOTAL GERAL DE VOLUMES E EXEMPLARES A SEPARAR</b>", st_td),
        Paragraph("", st_td_center),
        Paragraph(f"<b>{tot_pecas} un</b>", st_td_bold_center),
        Paragraph("", st_td_center),
        Paragraph(f"<b>{tot_peso:,.2f} kg</b>", st_td_bold_center),
        Paragraph("[ ✓ ]", st_td_center)
    ])

    t_items = Table(items_rows, colWidths=[28, 62, 195, 52, 60, 48, 52, 48])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#F1F5F9")),
    ]))
    story.append(t_items)
    story.append(Spacer(1, 10))

    # Observações e Instruções de Separação
    obs_extra_txt = f"<br/><font color='#B45309'><b>⚠️ ALERTA: {cliente['observacao_especial']}</b></font>" if cliente.get("observacao_especial") else ""
    obs_data = [
        [Paragraph(f"<b>INSTRUÇÕES & OBSERVAÇÕES DE SEPARAÇÃO:</b><br/>"
                   f"1. Material consignado para distribuição de assinantes. Sem valor de venda comercial avulsa.<br/>"
                   f"2. Conferir integridade física dos exemplares antes de acondicionar na caixa/envelope de transporte.<br/>"
                   f"3. Após a separação e conferência física, confirmar a transmissão da Remessa no sistema DRP/Omie.{obs_extra_txt}", st_sub)]
    ]
    t_obs = Table(obs_data, colWidths=[545])
    t_obs.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEF3C7") if cliente.get("observacao_especial") else colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#F59E0B") if cliente.get("observacao_especial") else colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_obs)
    story.append(Spacer(1, 15))

    # Termo de Assinaturas e Validação de Separação
    term_data = [
        [
            Paragraph("<b>SEPARAÇÃO FÍSICA NO ESTOQUE</b><br/><br/>Assinatura: ___________________________<br/>Nome do Separador: ___________________<br/>Data: _____/_____/2027", st_sub),
            Paragraph("<b>CONFERÊNCIA DE EMBALAGEM</b><br/><br/>Assinatura: ___________________________<br/>Nome do Conferente: ___________________<br/>Data: _____/_____/2027", st_sub),
            Paragraph("<b>EXPEDIÇÃO / COLETA</b><br/><br/>Assinatura: ___________________________<br/>Motorista/Coleta: _____________________<br/>Data: _____/_____/2027", st_sub),
        ]
    ]
    t_term = Table(term_data, colWidths=[181, 182, 182])
    t_term.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FFFFFF")),
    ]))
    story.append(t_term)

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


def gerar_pdf_relatorio_grupo(grupo_id="todos", linha=None):
    """
    Gera Romaneio de Separação e Conferência de Remessa.
    - Se linha for informada: Gera o Espelho de Remessa Individual da Paróquia/Cliente (A4 Retrato).
    - Se linha for None: Gera o Romaneio Geral de Separação do Grupo (A4 Paisagem).
    """
    dados = processar_assinaturas_pdv(forcar_download=False)

    # Caso 1: Espelho de Remessa Individual
    if linha is not None:
        linha_str = str(linha).strip()
        todos_clientes = []
        for g in dados["grupos"].values():
            todos_clientes.extend(g.get("clientes", []))
            
        cliente_alvo = None
        for c in todos_clientes:
            if str(c.get("linha_planilha")) == linha_str or str(c.get("codigo_cliente")) == linha_str:
                cliente_alvo = c
                break
                
        if cliente_alvo:
            return gerar_pdf_espelho_remessa_individual(cliente_alvo)

    # Caso 2: Romaneio de Separação do Grupo / Geral (A4 Paisagem)
    if grupo_id == "todos":
        titulo_grupo = "Romaneio Geral de Separação (Todos os Grupos)"
        desc_grupo = "Consolidação geral de separação de estoque de todos os assinantes elegíveis para o 1º Tri/2027."
        clientes = []
        for g in dados["grupos"].values():
            clientes.extend(g.get("clientes", []))
    elif grupo_id == "todos_correios":
        titulo_grupo = "Romaneio de Separação - Correios Brasil (Impresso Módico + PAC Norte)"
        desc_grupo = "Separação para todos os envios via Correios em território nacional."
        g_mod = dados["grupos"].get("finais_modico_brasil", {}).get("clientes", [])
        g_pac = dados["grupos"].get("finais_pac_norte", {}).get("clientes", [])
        clientes = g_mod + g_pac
    else:
        grupo = dados["grupos"].get(grupo_id)
        if not grupo:
            raise ValueError(f"Grupo {grupo_id} não encontrado.")
        titulo_grupo = f"Romaneio de Separação — {grupo.get('titulo', grupo_id)}"
        desc_grupo = grupo.get("descricao", "")
        clientes = grupo.get("clientes", [])

    # Totais da seleção
    tot_clientes = len(clientes)
    tot_assinaturas = sum(c.get("quantidade_assinaturas", 0) for c in clientes)
    tot_jan = sum(c.get("qtd_jan27", 0) for c in clientes)
    tot_fev = sum(c.get("qtd_fev27", 0) for c in clientes)
    tot_mar = sum(c.get("qtd_mar27", 0) for c in clientes)
    tot_pecas = tot_jan + tot_fev + tot_mar
    tot_peso = round(tot_pecas * 0.100, 2)

    # Custo de frete se for Fortaleza
    frete_texto = ""
    if grupo_id == "finais_fortaleza":
        custo_frete = round(tot_clientes * 4.50, 2)
        frete_texto = f" | Frete Roberto: R$ {custo_frete:,.2f} ({tot_clientes} entregas x R$ 4,50)"

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4), # 841.89 x 595.27 pt
        leftMargin=20,
        rightMargin=20,
        topMargin=20,
        bottomMargin=35
    )

    styles = getSampleStyleSheet()

    # Estilos customizados
    style_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=17,
        textColor=colors.HexColor("#0F172A")
    )
    style_subtitle = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#475569")
    )
    style_card_val = ParagraphStyle(
        'CardVal',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=12.5,
        alignment=1,
        textColor=colors.HexColor("#0F172A")
    )
    style_card_lbl = ParagraphStyle(
        'CardLbl',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=8.5,
        alignment=1,
        textColor=colors.HexColor("#64748B")
    )
    style_th = ParagraphStyle(
        'TH',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white,
        alignment=1
    )
    style_td = ParagraphStyle(
        'TD',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#1E293B")
    )
    style_td_center = ParagraphStyle(
        'TDCenter',
        parent=style_td,
        alignment=1
    )
    style_td_bold_center = ParagraphStyle(
        'TDBoldCenter',
        parent=style_td,
        fontName='Helvetica-Bold',
        alignment=1,
        textColor=colors.HexColor("#047857")
    )

    story = []

    # 1. Cabeçalho Superior tipo Remessa
    header_data = [
        [
            Paragraph(f"<b>EDIÇÕES SHALOM — ORDEM DE SEPARAÇÃO & ROMANEIO DE REMESSA</b><br/><font size=9.5 color='#1E40AF'><b>{titulo_grupo}</b></font>", style_title),
            Paragraph(f"<b>Emissão:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}<br/><font color='#64748B'>{desc_grupo}</font>", style_subtitle)
        ]
    ]
    t_header = Table(header_data, colWidths=[470, 332])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 5))

    # 2. Grade de Separação de Estoque no Almoxarifado (Cards/Tabela)
    kpi_data = [
        [
            Paragraph(f"<b>{tot_clientes}</b>", style_card_val),
            Paragraph(f"<b>{tot_assinaturas}</b>", style_card_val),
            Paragraph(f"<b>{tot_jan} un</b>", style_card_val),
            Paragraph(f"<b>{tot_fev} un</b>", style_card_val),
            Paragraph(f"<b>{tot_mar} un</b>", style_card_val),
            Paragraph(f"<font color='#047857'><b>{tot_pecas} un</b></font>", style_card_val),
            Paragraph(f"<b>{tot_peso:,.1f} kg</b>", style_card_val),
            Paragraph(f"<b>{frete_texto or 'Padrão Grupo'}</b>", style_card_val),
        ],
        [
            Paragraph("Total Volumes/Entregas", style_card_lbl),
            Paragraph("Assinaturas Ativas", style_card_lbl),
            Paragraph("PRD00561 (Jan/27)", style_card_lbl),
            Paragraph("PRD00562 (Fev/27)", style_card_lbl),
            Paragraph("PRD00563 (Mar/27)", style_card_lbl),
            Paragraph("Total Peças a Retirar", style_card_lbl),
            Paragraph("Peso Bruto Total", style_card_lbl),
            Paragraph("Logística / Frete", style_card_lbl),
        ]
    ]
    t_kpis = Table(kpi_data, colWidths=[80, 80, 100, 100, 100, 105, 90, 147])
    t_kpis.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_kpis)
    story.append(Spacer(1, 8))

    # 3. Romaneio Detalhado por Assinante/Pacote (com caixa de visto de separação)
    # Largura total disponível: 802 pt
    col_widths = [24, 24, 34, 140, 204, 90, 52, 30, 30, 30, 34, 110]
    table_rows = [
        [
            Paragraph("Sep.", style_th),
            Paragraph("Linha", style_th),
            Paragraph("Cód.", style_th),
            Paragraph("Destinatário / Cliente", style_th),
            Paragraph("Endereço / Bairro", style_th),
            Paragraph("Cidade / UF", style_th),
            Paragraph("CEP", style_th),
            Paragraph("Jan", style_th),
            Paragraph("Fev", style_th),
            Paragraph("Mar", style_th),
            Paragraph("Total", style_th),
            Paragraph("Embalagem / Rota", style_th)
        ]
    ]

    for c in clientes:
        txt_etiqueta = obter_texto_periodo_etiqueta(c)
        compl = f" ({c.get('complemento')})" if c.get('complemento') else ""
        end_completo = f"{c.get('rua', '')}, {c.get('numero', '')}{compl} - {c.get('bairro', '')}"
        
        jan_str = f"✓ {c.get('qtd_jan27')}" if c.get("jan27") else "-"
        fev_str = f"✓ {c.get('qtd_fev27')}" if c.get("fev27") else "-"
        mar_str = f"✓ {c.get('qtd_mar27')}" if c.get("mar27") else "-"

        nome_cell = f"<b>{c.get('cliente', '')}</b>"
        if c.get("cpf_cnpj"):
            nome_cell += f"<br/><font size=6 color='#64748B'>{c['cpf_cnpj']}</font>"
        if c.get("observacao_especial"):
            nome_cell += f"<br/><font size=6 color='#B45309'><b>⚠️ {c['observacao_especial']}</b></font>"

        tot_cell = str(c.get('total_exemplares', 0))
        if c.get("qtd_dez26_extra"):
            tot_cell = f"<b>{c.get('total_exemplares_envio', c.get('total_exemplares', 0))}</b><br/><font size=5.5 color='#B45309'><b>(+1 Dez)</b></font>"
        else:
            tot_cell = f"<b>{tot_cell}</b>"

        table_rows.append([
            Paragraph("[  ]", style_td_center),
            Paragraph(str(c.get("linha_planilha", "")), style_td_center),
            Paragraph(str(c.get("codigo_cliente", "-") or "-"), style_td_center),
            Paragraph(nome_cell, style_td),
            Paragraph(end_completo, style_td),
            Paragraph(f"{c.get('cidade', '')} / <b>{c.get('uf', '')}</b>", style_td),
            Paragraph(c.get("cep", ""), style_td_center),
            Paragraph(jan_str, style_td_center),
            Paragraph(fev_str, style_td_center),
            Paragraph(mar_str, style_td_center),
            Paragraph(tot_cell, style_td_bold_center),
            Paragraph(f"<font color='#1E40AF'><b>{txt_etiqueta}</b></font><br/><font size=6 color='#64748B'>{c.get('entregador') or c.get('transportadora') or c.get('tipo_envio') or 'LITURGIAS'}</font>", style_td),
        ])

    t_main = Table(table_rows, colWidths=col_widths, repeatRows=1)
    
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
    ]

    for r in range(1, len(table_rows)):
        if r % 2 == 0:
            t_style.append(('BACKGROUND', (0, r), (-1, r), colors.HexColor("#F8FAFC")))

    t_main.setStyle(TableStyle(t_style))
    story.append(t_main)
    story.append(Spacer(1, 10))

    # 4. Termo de Separação e Liberação Física no Rodapé
    term_data = [
        [
            Paragraph("<b>SEPARAÇÃO FÍSICA NO ALMOXARIFADO</b><br/><br/>Assinatura: _________________________________<br/>Nome do Separador: _________________________<br/>Data: _____/_____/2027", style_subtitle),
            Paragraph("<b>CONFERÊNCIA DE VOLUMES / EXPEDIÇÃO</b><br/><br/>Assinatura: _________________________________<br/>Nome do Conferente: _________________________<br/>Data: _____/_____/2027", style_subtitle),
            Paragraph("<b>RECEBIMENTO TRANSPORTE / COLETA</b><br/><br/>Assinatura: _________________________________<br/>Motorista / RG: ______________________________<br/>Data: _____/_____/2027", style_subtitle),
        ]
    ]
    t_term = Table(term_data, colWidths=[267, 267, 268])
    t_term.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FFFFFF")),
    ]))
    
    # Mantém o quadro de assinaturas junto
    story.append(KeepTogether(t_term))

    doc.build(story, canvasmaker=NumberedCanvas)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()
