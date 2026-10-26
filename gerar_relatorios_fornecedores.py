import os
import sys
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# Paleta de Cores Premium Executiva
PRIMARY = colors.HexColor("#0F172A")    # Slate 900
SECONDARY = colors.HexColor("#1E3A8A")  # Blue 900
ACCENT = colors.HexColor("#0284C7")     # Sky 600
NEUTRAL_DARK = colors.HexColor("#1E293B")
NEUTRAL_LIGHT = colors.HexColor("#F8FAFC")
BORDER_COLOR = colors.HexColor("#CBD5E1")
GOLD_ACCENT = colors.HexColor("#D97706")
GREEN_STATUS = colors.HexColor("#059669")

class NumberedCanvas(canvas.Canvas):
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
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Cabeçalho
        self.drawString(36, 560, "EDIÇÕES SHALOM — PLANEJAMENTO DE SUPRIMENTOS & ESTOQUE PRONTA ENTREGA")
        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.5)
        self.line(36, 552, 806, 552)

        # Rodapé
        self.line(36, 32, 806, 32)
        self.drawString(36, 20, "Documento de Estudo Estratégico para Alinhamento com Fornecedores | Confidencial")
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(806, 20, page_text)
        self.restoreState()

def criar_estilos():
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=PRIMARY,
        spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
        spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=SECONDARY,
        spaceBefore=10,
        spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=NEUTRAL_DARK
    ))
    styles.add(ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=NEUTRAL_DARK
    ))
    styles.add(ParagraphStyle(
        'TableHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.white,
        alignment=1 # Center
    ))
    styles.add(ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=NEUTRAL_DARK
    ))
    return styles

# ==============================================================================
# 1. GERAR RELATÓRIO 1: ÍCONES E CRUZES
# ==============================================================================
def gerar_pdf_icones_cruzes(caminho_pdf):
    doc = SimpleDocTemplate(
        caminho_pdf,
        pagesize=landscape(A4),
        leftMargin=36,
        rightMargin=36,
        topMargin=45,
        bottomMargin=45
    )
    styles = criar_estilos()
    story = []

    # Título
    story.append(Paragraph("ESTUDO E PADRONIZAÇÃO DE COMPRAS: ÍCONES E CRUZES", styles['DocTitle']))
    story.append(Paragraph("Análise de vendas (30, 60 e 90 dias), curva de demanda por grade (A3 a A7) e proposta de pronta entrega para fornecedores.", styles['DocSub']))
    story.append(Spacer(1, 4))

    # Box Explicativo de Grade
    card_data = [[
        Paragraph(
            "<b>DIRETRIZ ESTRATÉGICA DA GRADE DE ÍCONES:</b><br/>"
            "• <b>Tamanhos Grandes (A3 e A4):</b> Demanda pontual e institucional (~3% a 7% do volume). Pedir lotes enxutos (1 a 2 un).<br/>"
            "• <b>Tamanhos Carro-Chefe (A5, A6 e A7):</b> Alta rotatividade pessoal, oratório e cabeceira (~90% do volume total).<br/>"
            "• <b>Meta Fornecedor:</b> Manter estoque a pronta entrega garantindo reposição apenas dos tamanhos em ruptura sem obrigação de comprar a grade inteira.",
            styles['CalloutText']
        )
    ]]
    t_card = Table(card_data, colWidths=[770])
    t_card.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#93C5FD")),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_card)
    story.append(Spacer(1, 8))

    story.append(Paragraph("1. ÍCONES — GRADE DE MODELOS SELECIONADOS (A3 A A7)", styles['SectionHeader']))

    headers_icones = [
        Paragraph("Modelo / Devoção", styles['TableHead']),
        Paragraph("A3 (Peça Central)<br/>(Foco: 1 a 2 un)", styles['TableHead']),
        Paragraph("A4 (Capela)<br/>(Foco: 2 a 3 un)", styles['TableHead']),
        Paragraph("A5 (Oratório)<br/>(Foco: 8 a 12 un)", styles['TableHead']),
        Paragraph("A6 (Cabeceira)<br/>(Foco: 15 a 20 un)", styles['TableHead']),
        Paragraph("A7 (Bolsa/Portátil)<br/>(Foco: 12 a 15 un)", styles['TableHead']),
        Paragraph("Estoque Alvo Sugerido<br/>(Pronta Entrega)", styles['TableHead'])
    ]

    tabela_icones_dados = [headers_icones]

    modelos_lista = [
        ("Sagrada Família 1 (Cód 42 - Tradicional)", "-", "000638 (A4)", "000639 (A5)", "000641 (A6)", "000642 (A7)", "35 un (Grade A4-A7)"),
        ("Sagrada Família 2 (Cód 44 - Arte Bizantina)", "PRD00475 (A3)", "000650 (A4)", "000647 (A5)", "000648 (A6)", "000649 (A7)", "40 un (Grade A3-A7)"),
        ("Sagrada Família 3 (Cód 41 - Releitura)", "-", "-", "PRD00118 (A5)", "010320 (A6)", "010321 (A7)", "30 un (Grade A5-A7)"),
        ("Santa Teresinha (Cód 124 - Tradicional)", "000037 (A3)", "000038 (A4)", "000039 (A5)", "000040 (A6)", "000041 (A7)", "38 un (Grade A3-A7)"),
        ("Santa Teresinha Egito (Cód 126)", "-", "-", "000678 (A5)", "000679 (A6)", "000680 (A7)", "30 un (Grade A5-A7)"),
        ("Santa Teresa de Ávila (Cód 119)", "-", "007655 (A4)", "007654 (A5)", "000054 (A6)", "005243 (A7)", "35 un (Grade A4-A7)"),
        ("São Francisco de Assis (Cód 118 / 120)", "-", "000624 (A4)", "000625 (A5)", "000626 (A6)", "000562 (A7)", "35 un (Grade A4-A7)"),
        ("Carlo Acutis (Cód 131 - Versão Oficial)", "-", "-", "009556 (A5)", "009557 (A6)", "006591 (A7)", "30 un (Grade A5-A7)"),
        ("Jesus Cristo Esposo que Vem 40 Anos (Cód 09)", "-", "008143 (A4)", "008146 (A5)", "008148 (A6)", "008149 (A7)", "35 un (Grade A4-A7)"),
        ("N.S. Toda Pequena (Cód 53 - Tradicional)", "007510 (A3)", "007508 (A4)", "007509 (A5)", "008492 (A6)", "007524 (A7)", "40 un (Grade A3-A7)"),
        ("N.S. Toda Pequena (Cód 54 - Releitura)", "009636 (A3)", "009637 (A4)", "009285 (A5)", "009284 (A6)", "009283 (A7)", "40 un (Grade A3-A7)"),
        ("São José Peregrino (Cód 98 - Tradicional)", "-", "000273 (A4)", "000274 (A5)", "000275 (A6)", "000276 (A7)", "35 un (Grade A4-A7)"),
        ("São José Peregrino Azul (Cód 99)", "000272 (A3)", "-", "007156 (A5)", "007157 (A6)", "007158 (A7)", "35 un (Grade A3-A7)")
    ]

    for m in modelos_lista:
        tabela_icones_dados.append([
            Paragraph(f"<b>{m[0]}</b>", styles['TableCellBold']),
            Paragraph(m[1], styles['TableCell']),
            Paragraph(m[2], styles['TableCell']),
            Paragraph(m[3], styles['TableCell']),
            Paragraph(m[4], styles['TableCell']),
            Paragraph(m[5], styles['TableCell']),
            Paragraph(f"<font color='#059669'><b>{m[6]}</b></font>", styles['TableCellBold'])
        ])

    col_widths_icones = [170, 95, 95, 100, 100, 100, 110]
    t_icones = Table(tabela_icones_dados, colWidths=col_widths_icones, repeatRows=1)
    t_icones.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, NEUTRAL_LIGHT]),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_icones)
    story.append(Spacer(1, 10))

    # Seção 2: Cruzes
    story.append(Paragraph("2. CRUZES — MODELOS PADRONIZADOS", styles['SectionHeader']))
    headers_cruzes = [
        Paragraph("Tipo de Cruz / Descrição", styles['TableHead']),
        Paragraph("SKU / Código", styles['TableHead']),
        Paragraph("Tamanho / Grade", styles['TableHead']),
        Paragraph("Comportamento de Saída", styles['TableHead']),
        Paragraph("Estoque Padrão Pronta Entrega", styles['TableHead'])
    ]
    dados_cruzes = [headers_cruzes]
    itens_cruzes = [
        ("ÍCONE CRUZ DUAS FACES A5 (CÓD 38)", "002504", "Tamanho Único (A5)", "Alta saída contínua (estudo / oratório)", "20 a 25 un"),
        ("CRUZ DE SÃO DAMIÃO / BIZANTINA A3", "000682", "A3 (42x30 cm)", "Baixa saída (igrejas / capelas)", "2 a 3 un"),
        ("CRUZ DE SÃO DAMIÃO / BIZANTINA A4 (CÓD 36)", "000683", "A4 (30x21 cm)", "Média saída", "5 un"),
        ("CRUZ DE SÃO DAMIÃO / BIZANTINA A5 (CÓD 36)", "000684", "A5 (21x15 cm)", "Alta saída", "15 a 20 un"),
        ("CRUZ DE SÃO DAMIÃO / BIZANTINA A6 (CÓD 36)", "000685", "A6 (15x10 cm)", "Altíssima saída", "20 a 25 un"),
        ("CRUZ DE SÃO DAMIÃO / BIZANTINA A7 (CÓD 36)", "000762", "A7 (10x7 cm)", "Alta saída (portátil)", "15 a 20 un"),
        ("CRUZ BIZANTINA ARTE FIORENTINA 29x23", "005659", "Tamanho Médio (29x23 cm)", "Saída para presentes especiais", "5 a 10 un"),
        ("CRUZ BIZANTINA ARTE FIORENTINA 45x35", "005658", "Tamanho Grande (45x35 cm)", "Saída para altar", "3 a 5 un"),
    ]
    for c in itens_cruzes:
        dados_cruzes.append([
            Paragraph(f"<b>{c[0]}</b>", styles['TableCellBold']),
            Paragraph(c[1], styles['TableCell']),
            Paragraph(c[2], styles['TableCell']),
            Paragraph(c[3], styles['TableCell']),
            Paragraph(f"<font color='#059669'><b>{c[4]}</b></font>", styles['TableCellBold'])
        ])

    t_cruzes = Table(dados_cruzes, colWidths=[240, 90, 140, 170, 130])
    t_cruzes.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), SECONDARY),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, NEUTRAL_LIGHT]),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_cruzes)

    doc.build(story, canvasmaker=NumberedCanvas)
    return caminho_pdf

# ==============================================================================
# 2. GERAR RELATÓRIO 2: VELAS E TOALHAS
# ==============================================================================
def gerar_pdf_velas_toalhas(caminho_pdf):
    doc = SimpleDocTemplate(
        caminho_pdf,
        pagesize=landscape(A4),
        leftMargin=36,
        rightMargin=36,
        topMargin=45,
        bottomMargin=45
    )
    styles = criar_estilos()
    story = []

    # Título
    story.append(Paragraph("ESTUDO E PADRONIZAÇÃO DE COMPRAS: VELAS E TOALHAS LITÚRGICAS", styles['DocTitle']))
    story.append(Paragraph("Mapeamento ampliado de Velas 5 cm e 3 cm, Toalhas Oficiais e parâmetros de pronta entrega no fornecedor.", styles['DocSub']))
    story.append(Spacer(1, 4))

    # Seção 1: Velas 5cm
    story.append(Paragraph("1. VELAS 5 CM — MAPEAMENTO AMPLIADO DE MODELOS", styles['SectionHeader']))
    headers_velas5 = [
        Paragraph("SKU", styles['TableHead']),
        Paragraph("Descrição da Vela 5 cm", styles['TableHead']),
        Paragraph("Histórico Recente (30d / 60d / 90d)", styles['TableHead']),
        Paragraph("Média Mensal Estimada", styles['TableHead']),
        Paragraph("Estoque Pronta Entrega Sugerido", styles['TableHead'])
    ]
    dados_v5 = [headers_velas5]
    velas_5cm_lista = [
        ("001249", "VELA MANUSCRITA SÃO JOSÉ PROV. MARROM 5 CM", "1 / 2 / 3 un", "~1,0 un/mês", "10 a 15 un"),
        ("PRD00052", "VELA MANUSCRITA CARLO ACUTIS 5 CM", "1 / 2 / 3 un", "~1,0 un/mês", "10 a 15 un"),
        ("PRD00070", "VELA MANUSCRITA SANTA TERESA D'ÁVILA SÓ DEUS BASTA 5 CM", "0 / 1 / 2 un", "~0,7 un/mês", "10 un"),
        ("001700", "VELA LITÚRGICA 5 CM (TRADICIONAL)", "0 / 1 / 2 un", "~0,7 un/mês", "10 a 15 un"),
        ("PRD00580", "VELA SANTA TERESINHA MINHA VOCAÇÃO É O AMOR 5 CM", "1 / 2 / 3 un", "~1,0 un/mês", "10 a 15 un"),
        ("003900", "VELA MANUSCRITA NOSSA SENHORA APARECIDA 5 CM", "1 / 1 / 2 un", "~0,7 un/mês", "10 un"),
        ("001254", "VELA MANUSCRITA RAINHA DA PAZ 5 CM", "1 / 1 / 2 un", "~0,7 un/mês", "10 un"),
        ("PRD00642", "VELA MANUSCRITA NOSSA SENHORA DE FÁTIMA 5 CM", "0 / 1 / 2 un", "~0,7 un/mês", "10 un"),
        ("004276", "VELA MANUSCRITA SAGRADO CORAÇÃO DE JESUS 5 CM", "0 / 1 / 2 un", "~0,7 un/mês", "10 un"),
        ("PRD00381", "VELA MANUSCRITA IMACULADO CORAÇÃO DE MARIA 5 CM", "0 / 1 / 2 un", "~0,7 un/mês", "10 un"),
        ("008858", "VELA MANUSCRITA VINDE AMAR O AMOR 5 CM", "0 / 1 / 1 un", "~0,5 un/mês", "10 un"),
        ("001248", "VELA MANUSCRITA SÃO JOSÉ PROV. AMARELA 5 CM", "0 / 1 / 1 un", "~0,5 un/mês", "10 un"),
        ("003007", "VELA MANUSCRITA PRESÉPIO 5 CM (SAZONAL NATAL)", "0 / 0 / 1 un", "Sazonal Natal", "15 a 20 un (Q4)"),
        ("PRD00775", "KIT SÃO MIGUEL — VELA 5 CM", "1 / 2 / 3 un", "~1,0 un/mês", "10 un")
    ]
    for v in velas_5cm_lista:
        dados_v5.append([
            Paragraph(v[0], styles['TableCellBold']),
            Paragraph(f"<b>{v[1]}</b>", styles['TableCell']),
            Paragraph(v[2], styles['TableCell']),
            Paragraph(v[3], styles['TableCell']),
            Paragraph(f"<font color='#059669'><b>{v[4]}</b></font>", styles['TableCellBold'])
        ])

    t_v5 = Table(dados_v5, colWidths=[80, 310, 130, 110, 140])
    t_v5.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, NEUTRAL_LIGHT]),
        ('PADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_v5)
    story.append(Spacer(1, 8))

    # Seção 2: Velas 3cm
    story.append(Paragraph("2. VELAS 3 CM — PRINCIPAIS MODELOS DE LINHA", styles['SectionHeader']))
    headers_velas3 = [
        Paragraph("SKU", styles['TableHead']),
        Paragraph("Descrição da Vela 3 cm", styles['TableHead']),
        Paragraph("Histórico Recente (30d / 60d / 90d)", styles['TableHead']),
        Paragraph("Média Mensal Estimada", styles['TableHead']),
        Paragraph("Estoque Pronta Entrega Sugerido", styles['TableHead'])
    ]
    dados_v3 = [headers_velas3]
    velas_3cm_lista = [
        ("008021", "VELA MANUSCRITA VIVER DE AMOR 3 CM", "2 / 4 / 6 un", "~2,0 un/mês", "15 a 20 un"),
        ("007564", "VELA PARA TE AMAR SÓ TENHO HOJE 3 CM", "2 / 4 / 5 un", "~1,7 un/mês", "15 un"),
        ("009931", "VELA MANUSCRITA SÓ O INFINITO PREENCHE 3 CM", "2 / 3 / 5 un", "~1,7 un/mês", "15 un"),
        ("007552", "VELA LITÚRGICA VINDE ESPÍRITO SANTO 3 CM", "1 / 2 / 4 un", "~1,3 un/mês", "10 a 15 un"),
        ("008729", "VELA SÃO JOSÉ PROVIDÊNCIA AMARELA 3 CM", "1 / 2 / 3 un", "~1,0 un/mês", "10 a 15 un"),
        ("007551", "VELA JESUS, MARIA E JOSÉ 3 CM", "1 / 2 / 3 un", "~1,0 un/mês", "10 a 15 un"),
        ("001719", "VELA MANUSCRITA RAINHA DA PAZ 3 CM", "0 / 1 / 2 un", "~0,7 un/mês", "10 un"),
        ("001707", "VELA LITÚRGICA 3 CM (TRADICIONAL)", "0 / 1 / 2 un", "~0,7 un/mês", "10 un"),
        ("PRD00258", "VELA CARLO ACUTIS 3 CM", "1 / 2 / 3 un", "~1,0 un/mês", "10 un"),
        ("PRD00631", "VELA ESPOSA DO ESPÍRITO 3 CM", "0 / 1 / 2 un", "~0,7 un/mês", "10 un"),
        ("PRD00857", "VELA MIGUEL ARCANJO 3 CM", "1 / 1 / 2 un", "~0,7 un/mês", "10 un"),
        ("009932", "VELA A MEDIDA DO AMOR É AMAR SEM MEDIDAS 3 CM", "0 / 1 / 2 un", "~0,7 un/mês", "10 un")
    ]
    for v in velas_3cm_lista:
        dados_v3.append([
            Paragraph(v[0], styles['TableCellBold']),
            Paragraph(f"<b>{v[1]}</b>", styles['TableCell']),
            Paragraph(v[2], styles['TableCell']),
            Paragraph(v[3], styles['TableCell']),
            Paragraph(f"<font color='#059669'><b>{v[4]}</b></font>", styles['TableCellBold'])
        ])

    t_v3 = Table(dados_v3, colWidths=[80, 310, 130, 110, 140])
    t_v3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), SECONDARY),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, NEUTRAL_LIGHT]),
        ('PADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_v3)
    story.append(Spacer(1, 8))

    # Seção 3: Toalhas Litúrgicas Especiais
    story.append(Paragraph("3. TOALHAS LITÚRGICAS OFICIAIS SHALOM", styles['SectionHeader']))
    headers_toalhas = [
        Paragraph("SKU", styles['TableHead']),
        Paragraph("Descrição da Toalha", styles['TableHead']),
        Paragraph("Finalidade Litúrgica / Uso", styles['TableHead']),
        Paragraph("Demanda Mensal Estimada", styles['TableHead']),
        Paragraph("Estoque Pronta Entrega Sugerido", styles['TableHead'])
    ]
    dados_toalhas = [headers_toalhas]
    toalhas_lista = [
        ("003653", "TOALHA LITÚRGICA SHALOM — P BRANCA LETRAS DOURADAS", "Toalha oficial de celebrações, eventos e capelas Shalom (Bordado em letras douradas)", "~4 a 6 un/mês", "20 a 25 un"),
        ("009539", "TOALHA LITÚRGICA MARIA BRANCA", "Toalha mariana litúrgica para oratórios e altares dedicados a Nossa Senhora", "~3 a 5 un/mês", "15 a 20 un")
    ]
    for t in toalhas_lista:
        dados_toalhas.append([
            Paragraph(f"<b>{t[0]}</b>", styles['TableCellBold']),
            Paragraph(f"<b>{t[1]}</b>", styles['TableCellBold']),
            Paragraph(t[2], styles['TableCell']),
            Paragraph(t[3], styles['TableCell']),
            Paragraph(f"<font color='#059669'><b>{t[4]}</b></font>", styles['TableCellBold'])
        ])

    t_t = Table(dados_toalhas, colWidths=[80, 270, 210, 100, 110])
    t_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#065F46")), # Emerald 800
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, NEUTRAL_LIGHT]),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_t)

    doc.build(story, canvasmaker=NumberedCanvas)
    return caminho_pdf

if __name__ == '__main__':
    pdf1 = os.path.abspath('Relatorio_Fornecedor_Icones_e_Cruzes.pdf')
    pdf2 = os.path.abspath('Relatorio_Fornecedor_Velas_e_Toalhas.pdf')
    
    print(f"Gerando PDF 1: {pdf1}...")
    gerar_pdf_icones_cruzes(pdf1)
    
    print(f"Gerando PDF 2: {pdf2}...")
    gerar_pdf_velas_toalhas(pdf2)
    
    print("\nAmbos os relatórios executivos em PDF foram gerados com sucesso!")
