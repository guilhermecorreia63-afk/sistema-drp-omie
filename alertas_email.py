# -*- coding: utf-8 -*-
"""
alertas_email.py - Módulo de Alertas por E-mail & Agendador DRP (CD_SP / Matriz)
==============================================================================
Dispara relatórios sintéticos de rupturas e alertas via e-mail agrupados por Família,
destacando os itens que já se encontram EM PRODUÇÃO / COMPRA e ignorando itens da
Blacklist, Liturgias, Combos e PDFs digitais.
"""

import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DESTINATARIOS_DEFAULT = ["faturamentoedicoes@comshalom.org", "comprasedicoes@comshalom.org"]

def carregar_status_producao():
    set_producao = set()
    p_json = os.path.join("data", "producao_status.json")
    if os.path.exists(p_json):
        try:
            with open(p_json, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, list):
                    set_producao.update(d)
                elif isinstance(d, dict):
                    set_producao.update({k for k, v in d.items() if v})
        except Exception as e:
            print(f"[ALERTAS EMAIL] Erro ao ler producao_status.json: {e}")
    try:
        import database as db_mod
        st = db_mod.obter_status_producao()
        if st and isinstance(st, dict):
            set_producao.update({k for k, v in st.items() if v})
    except Exception:
        pass
    return set_producao

def carregar_blacklist():
    set_bl = set()
    bl_json = os.path.join("data", "blacklist.json")
    if os.path.exists(bl_json):
        try:
            with open(bl_json, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, list):
                    set_bl.update(d)
        except Exception as e:
            print(f"[ALERTAS EMAIL] Erro ao ler blacklist.json: {e}")
    try:
        import database as db_mod
        st = db_mod.obter_blacklist()
        if st and isinstance(st, (set, list)):
            set_bl.update(st)
    except Exception:
        pass
    return set_bl

def gerar_relatorio_sintetico():
    caminho_json = os.path.join("data", "produtos_turso.json")
    if not os.path.exists(caminho_json):
        return "Arquivo de produtos não encontrado.", [], [], [], [], []

    with open(caminho_json, "r", encoding="utf-8") as f:
        produtos = json.load(f)

    set_producao = carregar_status_producao()
    set_bl = carregar_blacklist()

    rupturas_cd = []
    alertas_cd = []
    rupturas_matriz = []
    alertas_matriz = []
    velas_ferias = []

    # Estruturas agrupadas por Família: { "NOME_FAMILIA": [ {produto...}, ... ] }
    grupos_matriz = {}
    grupos_cd = {}

    total_em_producao_ruptura = 0

    for p in produtos:
        if not p.get("ativo"):
            continue

        sku_str = str(p.get("sku") or p.get("codigo") or "").strip()
        fam = str(p.get("familia") or "GERAL").strip().upper()
        nome_orig = str(p.get("nome") or "Produto sem nome").strip()
        nome_up = nome_orig.upper()

        # REGRAS DE FILTRAGEM (EXCLUSÃO)
        # 1. Blacklist
        if sku_str in set_bl:
            continue

        # 2. Família / Nome LITURGIA (não incluir por enquanto conforme solicitado)
        if "LITURGIA" in fam or "LITURGIA" in nome_up or nome_up.startswith("LITURGIA"):
            continue

        # 3. COMBOS (não incluir no relatório)
        if "COMBO" in fam or "COMBO" in nome_up:
            continue

        # 4. Produtos Digitais / PDFs
        if "PDF LIVRO" in nome_up or nome_up.startswith("PDF "):
            continue

        # Determina se está Em Produção / Compra
        em_prod = (sku_str in set_producao) or (p.get("em_producao") is True)
        p["em_producao_flag"] = em_prod

        # 1. CD_SP
        vendas_ss = p.get("vendas_sul_sudeste_30d", 0) or 0
        est_efetivo_cd = (p.get("cd_sp", 0) or 0) + (p.get("em_transito", 0) or 0)
        if vendas_ss > 0:
            alvo_cd = (vendas_ss / 30.0) * (30 + 7) * 1.20
            if est_efetivo_cd <= 0:
                p_cd = dict(p)
                p_cd["tipo_alerta"] = "RUPTURA"
                rupturas_cd.append(p_cd)
                grupos_cd.setdefault(fam, []).append(p_cd)
            elif est_efetivo_cd / (alvo_cd or 1) < 0.8:
                p_cd = dict(p)
                p_cd["tipo_alerta"] = "ALERTA"
                alertas_cd.append(p_cd)
                grupos_cd.setdefault(fam, []).append(p_cd)

        # 2. Matriz
        vendas_geral = p.get("vendas_geral_30d", 0) or 0
        est_matriz = p.get("matriz", 0) or 0
        if vendas_geral > 0:
            alvo_mat = (vendas_geral / 30.0) * (30 + 15) * 1.20
            if est_matriz <= 0 and p.get("status_especial") != "Sem Estoque Discipulado":
                p_mat = dict(p)
                p_mat["tipo_alerta"] = "RUPTURA"
                rupturas_matriz.append(p_mat)
                grupos_matriz.setdefault(fam, []).append(p_mat)
                if em_prod:
                    total_em_producao_ruptura += 1
            elif est_matriz / (alvo_mat or 1) < 0.8:
                p_mat = dict(p)
                p_mat["tipo_alerta"] = "ALERTA"
                alertas_matriz.append(p_mat)
                grupos_matriz.setdefault(fam, []).append(p_mat)
                if em_prod:
                    total_em_producao_ruptura += 1

        # 3. Projeção Velas Férias
        if "VELA" in fam or "VELA" in nome_up:
            demanda20d = int((vendas_geral / 30.0) * 20)
            nec = max(0, demanda20d - est_matriz)
            if nec > 0:
                velas_ferias.append({
                    "sku": sku_str,
                    "nome": nome_orig,
                    "estoque_matriz": est_matriz,
                    "demanda_20d": demanda20d,
                    "necessario": nec,
                    "em_producao": em_prod,
                    "discipulado": p.get("estoque_discipulado", True)
                })

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Construção do HTML sintético e detalhado por Família
    html_sections = []

    # 1. Matriz por Família
    for familia in sorted(grupos_matriz.keys()):
        itens = grupos_matriz[familia]
        linhas_html = []
        for item in itens:
            tipo = item["tipo_alerta"]
            cor_tipo = "#ef4444" if tipo == "RUPTURA" else "#f59e0b"
            em_p = item.get("em_producao_flag")

            badge_prod = '<span style="background-color:#8b5cf6; color:#ffffff; padding:2px 8px; border-radius:10px; font-weight:bold; font-size:11px; margin-left:6px;">🛠️ EM PRODUÇÃO / COMPRA</span>' if em_p else '<span style="color:#9ca3af; font-size:11px; margin-left:6px;">- (Pendente)</span>'

            linhas_html.append(f"""
            <tr style="border-bottom:1px solid #334155;">
                <td style="padding:8px; font-weight:bold; color:#f8fafc;">{item['sku']}</td>
                <td style="padding:8px; color:#e2e8f0;">{item['nome']}{badge_prod}</td>
                <td style="padding:8px; text-align:center; color:#f8fafc;">{item.get('matriz', 0)} un</td>
                <td style="padding:8px; text-align:center; color:#94a3b8;">{int(item.get('vendas_geral_30d', 0))} un</td>
                <td style="padding:8px; text-align:center;"><span style="color:{cor_tipo}; font-weight:bold; font-size:11px; text-transform:uppercase;">{tipo}</span></td>
            </tr>
            """)

        html_sections.append(f"""
        <div style="margin-bottom:20px; background-color:#1e293b; border-radius:8px; padding:12px; border:1px solid #334155;">
            <h4 style="margin:0 0 10px 0; color:#38bdf8; font-size:14px; text-transform:uppercase; border-bottom:1px dashed #475569; padding-bottom:6px;">
                📁 Família: {familia} ({len(itens)} itens)
            </h4>
            <table style="width:100%; border-collapse:collapse; font-size:12px;">
                <thead>
                    <tr style="background-color:#0f172a; color:#94a3b8; text-align:left;">
                        <th style="padding:6px; width:15%;">SKU</th>
                        <th style="padding:6px; width:45%;">Produto</th>
                        <th style="padding:6px; text-align:center; width:15%;">Estoque Matriz</th>
                        <th style="padding:6px; text-align:center; width:10%;">Vendas 30d</th>
                        <th style="padding:6px; text-align:center; width:15%;">Status DRP</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(linhas_html)}
                </tbody>
            </table>
        </div>
        """)

    # 2. CD_SP por Família
    html_sections_cd = []
    for familia in sorted(grupos_cd.keys()):
        itens = grupos_cd[familia]
        linhas_html = []
        for item in itens:
            tipo = item["tipo_alerta"]
            cor_tipo = "#ef4444" if tipo == "RUPTURA" else "#f59e0b"
            em_p = item.get("em_producao_flag")
            badge_prod = '<span style="background-color:#8b5cf6; color:#ffffff; padding:2px 8px; border-radius:10px; font-weight:bold; font-size:11px; margin-left:6px;">🛠️ EM PRODUÇÃO / COMPRA</span>' if em_p else ''

            linhas_html.append(f"""
            <tr style="border-bottom:1px solid #334155;">
                <td style="padding:8px; font-weight:bold; color:#f8fafc;">{item['sku']}</td>
                <td style="padding:8px; color:#e2e8f0;">{item['nome']}{badge_prod}</td>
                <td style="padding:8px; text-align:center; color:#f8fafc;">{item.get('cd_sp', 0)} un</td>
                <td style="padding:8px; text-align:center; color:#94a3b8;">{int(item.get('vendas_sul_sudeste_30d', 0))} un</td>
                <td style="padding:8px; text-align:center;"><span style="color:{cor_tipo}; font-weight:bold; font-size:11px;">{tipo}</span></td>
            </tr>
            """)

        html_sections_cd.append(f"""
        <div style="margin-bottom:20px; background-color:#1e293b; border-radius:8px; padding:12px; border:1px solid #334155;">
            <h4 style="margin:0 0 10px 0; color:#fbbf24; font-size:14px; text-transform:uppercase; border-bottom:1px dashed #475569; padding-bottom:6px;">
                📁 Família: {familia} ({len(itens)} itens)
            </h4>
            <table style="width:100%; border-collapse:collapse; font-size:12px;">
                <thead>
                    <tr style="background-color:#0f172a; color:#94a3b8; text-align:left;">
                        <th style="padding:6px; width:15%;">SKU</th>
                        <th style="padding:6px; width:45%;">Produto</th>
                        <th style="padding:6px; text-align:center; width:15%;">Estoque CD</th>
                        <th style="padding:6px; text-align:center; width:10%;">Vendas SS 30d</th>
                        <th style="padding:6px; text-align:center; width:15%;">Status DRP</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(linhas_html)}
                </tbody>
            </table>
        </div>
        """)

    # Tabela Velas Férias
    linhas_velas = []
    for v in velas_ferias:
        badge_p = '<span style="background-color:#8b5cf6; color:#ffffff; padding:2px 6px; border-radius:8px; font-weight:bold; font-size:10px;">🛠️ EM PRODUÇÃO / COMPRA</span>' if v['em_producao'] else ''
        linhas_velas.append(f"""
        <tr style="border-bottom:1px solid #334155;">
            <td style="padding:6px; font-weight:bold; color:#f8fafc;">{v['sku']}</td>
            <td style="padding:6px; color:#e2e8f0;">{v['nome']} {badge_p}</td>
            <td style="padding:6px; text-align:center; color:#f8fafc;">{v['estoque_matriz']} un</td>
            <td style="padding:6px; text-align:center; color:#94a3b8;">{v['demanda_20d']} un</td>
            <td style="padding:6px; text-align:center; font-weight:bold; color:#34d399;">+{v['necessario']} un</td>
        </tr>
        """)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px;">
        <div style="max-width: 900px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; padding: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #334155;">
            
            <div style="border-bottom: 2px solid #3b82f6; padding-bottom: 15px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
                <h2 style="margin: 0; color: #60a5fa; font-size: 20px;">📦 Relatório Sintético DRP - Divisão por Famílias</h2>
                <span style="font-size: 12px; color: #94a3b8;">Processado em: {agora}</span>
            </div>

            <!-- Dashboard Sintético -->
            <div style="display: flex; gap: 12px; margin-bottom: 25px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 160px; background-color: #0f172a; padding: 12px; border-radius: 8px; border-left: 4px solid #ef4444;">
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">Rupturas Matriz</div>
                    <div style="font-size: 22px; font-weight: bold; color: #f87171;">{len(rupturas_matriz)} itens</div>
                </div>
                <div style="flex: 1; min-width: 160px; background-color: #0f172a; padding: 12px; border-radius: 8px; border-left: 4px solid #f59e0b;">
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">Alertas Matriz</div>
                    <div style="font-size: 22px; font-weight: bold; color: #fbbf24;">{len(alertas_matriz)} itens</div>
                </div>
                <div style="flex: 1; min-width: 160px; background-color: #0f172a; padding: 12px; border-radius: 8px; border-left: 4px solid #8b5cf6;">
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">Já Em Produção/Compra</div>
                    <div style="font-size: 22px; font-weight: bold; color: #a78bfa;">{total_em_producao_ruptura} itens</div>
                </div>
                <div style="flex: 1; min-width: 160px; background-color: #0f172a; padding: 12px; border-radius: 8px; border-left: 4px solid #3b82f6;">
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">Rupturas CD_SP</div>
                    <div style="font-size: 22px; font-weight: bold; color: #60a5fa;">{len(rupturas_cd)} itens</div>
                </div>
            </div>

            <!-- Seção 1: Matriz CE por Família -->
            <h3 style="color: #60a5fa; border-left: 4px solid #3b82f6; padding-left: 10px; margin-top: 25px;">
                🏭 Matriz CE (Demanda Nacional) - Agrupado por Família
            </h3>
            {''.join(html_sections) if html_sections else '<p style="color:#94a3b8;">Nenhum produto em ruptura ou alerta na Matriz.</p>'}

            <!-- Seção 2: CD_SP por Família -->
            <h3 style="color: #fbbf24; border-left: 4px solid #f59e0b; padding-left: 10px; margin-top: 35px;">
                🚚 CD_SP (Região Sul/Sudeste) - Agrupado por Família
            </h3>
            {''.join(html_sections_cd) if html_sections_cd else '<p style="color:#94a3b8;">Nenhum produto em ruptura ou alerta no CD_SP.</p>'}

            <!-- Seção 3: Velas Férias -->
            <h3 style="color: #34d399; border-left: 4px solid #10b981; padding-left: 10px; margin-top: 35px;">
                🕯️ Projeção Velas - Férias Discipulado ({len(velas_ferias)} itens)
            </h3>
            {f'''
            <table style="width:100%; border-collapse:collapse; font-size:12px; background-color:#1e293b; border-radius:8px; overflow:hidden;">
                <thead>
                    <tr style="background-color:#0f172a; color:#94a3b8; text-align:left;">
                        <th style="padding:8px;">SKU</th>
                        <th style="padding:8px;">Produto</th>
                        <th style="padding:8px; text-align:center;">Estoque Matriz</th>
                        <th style="padding:8px; text-align:center;">Demanda 20d</th>
                        <th style="padding:8px; text-align:center;">Necessidade</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(linhas_velas)}
                </tbody>
            </table>
            ''' if velas_ferias else '<p style="color:#94a3b8;">Nenhuma vela necessita de lote extra no período de férias.</p>'}

            <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #334155; text-align: center; color: #64748b; font-size: 11px;">
                Sistema de Gestão DRP Edições Shalom & Omie ERP - Gerado automaticamente em {agora}.
            </div>
        </div>
    </body>
    </html>
    """

    return html, rupturas_cd, alertas_cd, rupturas_matriz, alertas_matriz, velas_ferias

def gerar_pdf_relatorio(rupturas_cd, alertas_cd, rupturas_matriz, alertas_matriz, velas_ferias, caminho_pdf):
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Relatorio Sintetico de Alertas DRP - Omie ERP (Por Familia)", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, f"Data do Processamento: {datetime.now().strftime('%d/%m/%Y %H:%M')}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # Agrupar Matriz por Família
        grupos_mat = {}
        for p in rupturas_matriz + alertas_matriz:
            fam = str(p.get("familia") or "GERAL").upper()
            grupos_mat.setdefault(fam, []).append(p)

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"1. Matriz CE - Rupturas ({len(rupturas_matriz)}) / Alertas ({len(alertas_matriz)})", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)

        for fam in sorted(grupos_mat.keys()):
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, f" [Familia: {fam}]", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            for p in grupos_mat[fam][:20]:
                nome = str(p.get("nome", ""))[:40]
                tag_prod = " [EM PRODUCAO/COMPRA]" if p.get("em_producao_flag") else ""
                tipo = p.get("tipo_alerta", "ALERTA")
                pdf.cell(0, 5, f"   -{tipo} SKU: {p.get('sku')} | {nome} | Est: {p.get('matriz', 0)}{tag_prod}", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(3)

        # Agrupar CD_SP por Família
        grupos_cd = {}
        for p in rupturas_cd + alertas_cd:
            fam = str(p.get("familia") or "GERAL").upper()
            grupos_cd.setdefault(fam, []).append(p)

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"2. CD_SP - Rupturas ({len(rupturas_cd)}) / Alertas ({len(alertas_cd)})", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)

        for fam in sorted(grupos_cd.keys()):
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, f" [Familia: {fam}]", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            for p in grupos_cd[fam][:20]:
                nome = str(p.get("nome", ""))[:40]
                tag_prod = " [EM PRODUCAO/COMPRA]" if p.get("em_producao_flag") else ""
                tipo = p.get("tipo_alerta", "ALERTA")
                pdf.cell(0, 5, f"   -{tipo} SKU: {p.get('sku')} | {nome} | Est: {p.get('cd_sp', 0)}{tag_prod}", new_x="LMARGIN", new_y="NEXT")

        os.makedirs(os.path.dirname(caminho_pdf), exist_ok=True)
        pdf.output(caminho_pdf)
        print(f"[PDF] Relatório PDF gerado com sucesso em: {caminho_pdf}")
        return True
    except Exception as e:
        print(f"[PDF] Erro ao gerar PDF de alerta: {e}")
        return False

def enviar_email_alerta(destinatarios=None, assunto_custom=None, html_custom=None):
    from dotenv import dotenv_values
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(dotenv_path=env_path, override=True)
    vals = dotenv_values(env_path) if os.path.exists(env_path) else {}

    # Trata caso onde `enviar_email_alerta(assunto, corpo_html)` foi chamado positionalmente
    if isinstance(destinatarios, str) and html_custom is None and ("<html" in destinatarios or "<h3>" in destinatarios or "<b>" in destinatarios):
        html_custom = destinatarios
        destinatarios = DESTINATARIOS_DEFAULT
    elif isinstance(destinatarios, str) and not ("@" in destinatarios):
        assunto_custom = destinatarios
        destinatarios = DESTINATARIOS_DEFAULT

    if destinatarios is None or not destinatarios:
        destinatarios = DESTINATARIOS_DEFAULT
    elif isinstance(destinatarios, str):
        destinatarios = [d.strip() for d in destinatarios.split(",") if d.strip()]

    if html_custom:
        html = html_custom
        rupturas_cd, alertas_cd, rupturas_matriz, alertas_matriz, velas_ferias = [], [], [], [], []
        r_cd, r_mat = 0, 0
    else:
        html, rupturas_cd, alertas_cd, rupturas_matriz, alertas_matriz, velas_ferias = gerar_relatorio_sintetico()
        r_cd = len(rupturas_cd)
        r_mat = len(rupturas_matriz)

    caminho_log = os.path.join("data", "ultimo_alerta_email.html")
    try:
        with open(caminho_log, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        print(f"Erro ao salvar HTML de alerta: {e}")

    smtp_server = (vals.get("SMTP_SERVER") or os.getenv("SMTP_SERVER") or "smtp.gmail.com").strip().strip('"\'')
    smtp_port_raw = (vals.get("SMTP_PORT") or os.getenv("SMTP_PORT") or "587").strip().strip('"\'')
    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        smtp_port = 587

    smtp_user = (vals.get("SMTP_USER") or os.getenv("SMTP_USER") or "").strip().strip('"\'')
    smtp_password = (vals.get("SMTP_PASSWORD") or os.getenv("SMTP_PASSWORD") or "").strip().strip('"\'')

    if not smtp_user or not smtp_password:
        print("[Alerta E-mail] Credenciais SMTP não configuradas no .env (SMTP_USER/SMTP_PASSWORD). Relatório gerado localmente em data/ultimo_alerta_email.html")
        return False, "Credenciais SMTP ausentes no .env (SMTP_USER / SMTP_PASSWORD)."

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = assunto_custom or f"🚨 Relatório DRP Omie - Rupturas Por Família (Matriz: {r_mat} | CD_SP: {r_cd})"
        msg["From"] = smtp_user
        msg["To"] = ", ".join(destinatarios)

        part_html = MIMEText(html, "html", "utf-8")
        msg.attach(part_html)

        if not html_custom:
            caminho_pdf = os.path.join("data", "relatorio_alertas_drp.pdf")
            if gerar_pdf_relatorio(rupturas_cd, alertas_cd, rupturas_matriz, alertas_matriz, velas_ferias, caminho_pdf):
                try:
                    with open(caminho_pdf, "rb") as f:
                        part_pdf = MIMEApplication(f.read(), _subtype="pdf")
                        part_pdf.add_header("Content-Disposition", "attachment", filename="Relatorio_Alertas_DRP_Por_Familia.pdf")
                        msg.attach(part_pdf)
                except Exception as e:
                    print(f"[PDF] Aviso ao anexar PDF no e-mail: {e}")

        server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, destinatarios, msg.as_string())
        server.quit()

        print(f"[OK] E-mail enviado com sucesso (com anexo PDF) para: {', '.join(destinatarios)}")
        return True, "E-mail de alerta enviado com sucesso (com anexo PDF)!"
    except Exception as err:
        print(f"[ERRO] Erro ao enviar e-mail via SMTP: {err}")
        return False, str(err)

if __name__ == "__main__":
    print("[ALERTAS DRP] Executando Gerador de Alertas DRP Por Família...")
    enviar_email_alerta()
