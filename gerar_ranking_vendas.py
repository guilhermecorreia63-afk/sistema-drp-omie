"""
Módulo de Geração de Ranking de Vendas Omie ERP
------------------------------------------------
Gera relatórios (Console, JSON e PDF) dos produtos mais vendidos por família.

Exemplos de uso:
  # Vendas nos últimos 90 dias estritos:
  python gerar_ranking_vendas.py --familia "ESPIRITUALIDADE - EDIÇÕES, ORDO AMORIS, INFANTIL, ESTUDO BÍBLICO" --dias 90 --top 30

  # Todo o histórico de vendas registrado no Omie ERP (sem filtro de data):
  python gerar_ranking_vendas.py --familia "ESPIRITUALIDADE - EDIÇÕES, ORDO AMORIS, INFANTIL, ESTUDO BÍBLICO" --dias 0 --top 30

  # Vendas de um ano específico (ex: 2025 ou 2026):
  python gerar_ranking_vendas.py --familia "ESPIRITUALIDADE - EDIÇÕES, ORDO AMORIS, INFANTIL, ESTUDO BÍBLICO" --ano 2025 --top 30
"""

import sys
import os
import argparse
import json
import unicodedata
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.abspath('.'))
from omie_client import OmieClient

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm


def normalize_text(text: str) -> str:
    """Normaliza texto removendo acentos, cedilhas e caracteres especiais para comparação insensível."""
    if not text:
        return ""
    s = str(text).replace('Ç', 'C').replace('ç', 'c')
    return ''.join(c for c in unicodedata.normalize('NFD', s.upper()) if unicodedata.category(c) != 'Mn')


def buscar_skus_familias(lista_familias: list):
    """Filtra SKUs pertencentes a uma ou mais famílias no Turso / produtos.json com tolerância a acentos."""
    skus = {}
    json_path = 'data/produtos_turso.json'
    
    norm_alvos = [normalize_text(f) for f in lista_familias if f.strip()]
    
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            produtos = json.load(f)
        for p in produtos:
            fam_norm = normalize_text(p.get('familia') or p.get('descricao_familia') or '')
            
            for norm_alvo in norm_alvos:
                matched = False
                if norm_alvo in fam_norm or fam_norm in norm_alvo:
                    matched = True
                elif 'ESPIRITUALIDADE' in norm_alvo and 'ESPIRITUALIDADE' in fam_norm and 'EDICOES' in fam_norm:
                    matched = True
                elif 'ORDO' in norm_alvo and 'AMORIS' in norm_alvo and 'ORDO' in fam_norm:
                    matched = True
                elif 'INFANTIL' in norm_alvo and 'INFANTIL' in fam_norm:
                    matched = True
                elif 'ESTUDO' in norm_alvo and 'BIBLICO' in norm_alvo and 'ESTUDO' in fam_norm:
                    matched = True
                
                if matched:
                    skus[p['sku']] = p.get('descricao') or p['sku']
                    break
    return skus


def calcular_ranking_vendas(str_familias: str = "ESPIRITUALIDADE - EDIÇÕES", dias: int = 90, top_n: int = 30, ano: int = None):
    lista_familias = [f.strip() for f in str_familias.split(',') if f.strip()]
    
    label_periodo = f"Últimos {dias} dias" if dias > 0 else ("Histórico Completo" if not ano else f"Ano de {ano}")
    
    print(f"=== GERANDO RANKING TOP {top_n} DE VENDAS ===")
    print(f"Famílias Selecionadas: {', '.join(lista_familias)} | Período: {label_periodo}")
    sys.stdout.flush()
    
    skus_familia = buscar_skus_familias(lista_familias)
    print(f"Total de SKUs mapeados no grupo de famílias: {len(skus_familia)}")
    sys.stdout.flush()

    dt_limite = datetime.now() - timedelta(days=dias) if (dias > 0 and not ano) else None
    
    payload_base = {
        'pagina': 1,
        'registros_por_pagina': 100,
        'apenas_importado_api': 'N'
    }
    
    if dias > 0 and not ano:
        payload_base['filtrar_por_data_de'] = dt_limite.strftime('%d/%m/%Y')
        payload_base['filtrar_por_data_ate'] = datetime.now().strftime('%d/%m/%Y')
    elif ano:
        payload_base['filtrar_por_data_de'] = f"01/01/{ano}"
        payload_base['filtrar_por_data_ate'] = f"31/12/{ano}"
    
    vendas_por_sku = defaultdict(int)
    vendas_valor_total = defaultdict(float)

    for unidade in ['MATRIZ', 'CD_SP']:
        client = OmieClient(unidade)
        pag = 1
        tot_pags = 1
        print(f"\n---> Consultando Pedidos na unidade {unidade}...")
        sys.stdout.flush()
        while pag <= tot_pags:
            req_param = dict(payload_base)
            req_param['pagina'] = pag
            
            res = client.executar('produtos/pedido/', 'ListarPedidos', [req_param])
            if not res or 'pedido_venda_produto' not in res:
                break
            tot_pags = res.get('total_de_paginas', 1)
            
            for ped in res.get('pedido_venda_produto', []):
                cab = ped.get('cabecalho', {})
                info = ped.get('infoCadastro', {})
                
                if cab.get('etapa') == '60' or cab.get('encerrado') == 'C' or info.get('cancelado') == 'S':
                    continue
                
                for item in ped.get('det', []):
                    prod = item.get('produto', {})
                    sku = str(prod.get('codigo', '')).strip()
                    qtd = int(prod.get('quantidade', 0))
                    val_total = float(prod.get('valor_total', 0.0))
                    if not skus_familia or sku in skus_familia:
                        vendas_por_sku[sku] += qtd
                        vendas_valor_total[sku] += val_total
            pag += 1

    # Buscar títulos atualizados no Omie para os itens do ranking
    client_matriz = OmieClient('MATRIZ')
    ranking = []
    for sku, qtd in sorted(vendas_por_sku.items(), key=lambda x: x[1], reverse=True)[:top_n]:
        titulo = skus_familia.get(sku, sku)
        if titulo == sku or len(titulo) < 3:
            res_p = client_matriz.executar('geral/produtos/', 'ConsultarProduto', [{'codigo': sku}])
            if res_p and 'descricao' in res_p:
                titulo = res_p['descricao']

        ranking.append({
            'sku': sku,
            'titulo': titulo,
            'qtd_vendida': qtd,
            'valor_total': round(vendas_valor_total[sku], 2)
        })

    print(f"\nRanking processado com sucesso! Total de {len(ranking)} produtos encontrados.")
    sys.stdout.flush()

    if len(lista_familias) == 1:
        nome_limpo = "".join([c if c.isalnum() else "_" for c in lista_familias[0]])
        pdf_filename = f"Ranking_Top{top_n}_{nome_limpo}.pdf"
    else:
        pdf_filename = f"Ranking_Top{top_n}_MultiplasFamilias.pdf"

    gerar_pdf(ranking, pdf_filename, lista_familias, dias, top_n, label_periodo)
    
    return ranking, pdf_filename


def gerar_pdf(ranking: list, pdf_filename: str, lista_familias: list, dias: int, top_n: int, label_periodo: str):
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22,
        textColor=colors.HexColor('#1e293b'), alignment=1, spaceAfter=4
    )

    familias_str = ", ".join(lista_familias)
    subtitle_style = ParagraphStyle(
        'DocSubtitle', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=13,
        textColor=colors.HexColor('#475569'), alignment=1, spaceAfter=15
    )

    meta_style = ParagraphStyle('MetaText', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor('#334155'))
    meta_val_style = ParagraphStyle('MetaValText', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, textColor=colors.HexColor('#0f172a'))

    cell_rank_style = ParagraphStyle('CellRank', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11, alignment=1, textColor=colors.HexColor('#1e293b'))
    cell_sku_style = ParagraphStyle('CellSku', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=1, textColor=colors.HexColor('#0f766e'))
    cell_title_style = ParagraphStyle('CellTitle', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor('#1e293b'))
    cell_num_style = ParagraphStyle('CellNum', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=2, textColor=colors.HexColor('#0f172a'))
    th_style = ParagraphStyle('THText', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.white, alignment=1)

    elements = []

    elements.append(Paragraph("EDIÇÕES SHALOM — RELATÓRIO DE VENDAS", title_style))
    elements.append(Paragraph(f"Ranking dos {top_n} Produtos Mais Vendidos<br/>(Famílias: <b>{familias_str}</b>)", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0f766e'), spaceAfter=12))

    total_pecas = sum(r['qtd_vendida'] for r in ranking)
    total_faturamento = sum(r['valor_total'] for r in ranking)
    data_emissao = datetime.now().strftime('%d/%m/%Y às %H:%M')

    summary_data = [
        [
            Paragraph("<b>Período Auditado:</b>", meta_style), Paragraph(label_periodo, meta_val_style),
            Paragraph("<b>Total Peças Vendidas:</b>", meta_style), Paragraph(f"<b>{total_pecas:,} UN</b>", meta_val_style)
        ],
        [
            Paragraph("<b>Unidades Consolidadas:</b>", meta_style), Paragraph("Matriz + CD SP", meta_val_style),
            Paragraph("<b>Faturamento Acumulado:</b>", meta_style), Paragraph(f"<b>R$ {total_faturamento:,.2f}</b>", meta_val_style)
        ],
        [
            Paragraph("<b>Data de Emissão:</b>", meta_style), Paragraph(data_emissao, meta_val_style),
            Paragraph("<b>Famílias Selecionadas:</b>", meta_style), Paragraph(familias_str[:45] + ('...' if len(familias_str) > 45 else ''), meta_val_style)
        ]
    ]

    t_summary = Table(summary_data, colWidths=[3.5*cm, 5.0*cm, 4.2*cm, 5.3*cm])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f1f5f9')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
    ]))

    elements.append(t_summary)
    elements.append(Spacer(1, 15))

    headers = [
        Paragraph("<b>#</b>", th_style),
        Paragraph("<b>Código SKU</b>", th_style),
        Paragraph("<b>Descrição do Produto</b>", th_style),
        Paragraph("<b>Qtd Vendida</b>", th_style),
        Paragraph("<b>Total (R$)</b>", th_style)
    ]

    table_data = [headers]

    for idx, r in enumerate(ranking, 1):
        row = [
            Paragraph(f"{idx:02d}", cell_rank_style),
            Paragraph(r['sku'], cell_sku_style),
            Paragraph(r['titulo'], cell_title_style),
            Paragraph(f"{r['qtd_vendida']} UN", cell_num_style),
            Paragraph(f"R$ {r['valor_total']:,.2f}", cell_num_style)
        ]
        table_data.append(row)

    t_ranking = Table(table_data, colWidths=[1.0*cm, 2.5*cm, 9.5*cm, 2.5*cm, 2.5*cm])
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f766e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ]

    for i in range(1, len(table_data)):
        if i % 2 == 0:
            t_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f8fafc')))

    t_ranking.setStyle(TableStyle(t_style))
    elements.append(t_ranking)

    elements.append(Spacer(1, 15))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e1'), spaceAfter=8))
    footer_text = Paragraph("<font color='#64748b'>Relatório gerado automaticamente pelo Sistema de Gestão DRP / Omie ERP — Edições Shalom.</font>", ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=1))
    elements.append(footer_text)

    doc.build(elements)
    print(f"PDF salvo com sucesso em: {os.path.abspath(pdf_filename)}")
    sys.stdout.flush()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Gerador de Ranking de Vendas por Família no Omie ERP")
    parser.add_argument('--familia', type=str, default="ESPIRITUALIDADE - EDIÇÕES", help="Nome ou lista de famílias separadas por vírgula")
    parser.add_argument('--dias', type=int, default=90, help="Período de dias retroativos (0 para histórico completo)")
    parser.add_argument('--ano', type=int, default=None, help="Filtrar por ano específico (ex: 2025 ou 2026)")
    parser.add_argument('--top', type=int, default=30, help="Quantidade de itens no ranking")

    args = parser.parse_args()
    calcular_ranking_vendas(str_familias=args.familia, dias=args.dias, top_n=args.top, ano=args.ano)
