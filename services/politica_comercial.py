# -*- coding: utf-8 -*-
"""
services/politica_comercial.py
Regras oficiais da Política de Descontos por Família (Edições Shalom / Portal de Pedidos).
Validação: 18/10/2026.
"""

import unicodedata
from typing import Dict, List, Any

def normalizar_texto(txt: str) -> str:
    if not txt:
        return ""
    txt = unicodedata.normalize('NFKD', str(txt)).encode('ASCII', 'ignore').decode('ASCII')
    return txt.upper().strip()

def obter_desconto_item(sku: str, descricao: str, familia: str, condicao: str = 'A_VISTA_AUTO', simular_50: bool = False) -> float:
    """
    Calcula a alíquota percentual de desconto para um produto de acordo com a
    Política Comercial Oficial por Família.

    condicao: 'A_VISTA_AUTO' (sobe para 50% se elegível), 'A_VISTA_NORMAL' (40%), 'A_PRAZO' (35%/30%/etc.)
    """
    s = normalizar_texto(sku)
    d = normalizar_texto(descricao)
    f = normalizar_texto(familia)

    # 1. CASOS QUE NÃO SEGUEM A FAMÍLIA (EXCEÇÕES RÍGIDAS)
    # - SKU 008693 (Tu me atraíste 2023): 35% à vista e 30% a prazo. Não sobe para 50%.
    if s == '008693' or s == '8693':
        return 35.0 if 'VISTA' in condicao else 30.0

    # - SKUs PRD00228 e PRD00609: 0%
    if s in ['PRD00228', 'PRD00609']:
        return 0.0

    # - Título com ASSEMBLEIA GERAL e 2024: 0%
    if 'ASSEMBLEIA GERAL' in d and '2024' in d:
        return 0.0

    # - Título com MANUAL, RECICLAGEM e 2026: 0%
    if 'MANUAL' in d and 'RECICLAGEM' in d and '2026' in d:
        return 0.0

    # - Remessa CD: 0%
    if 'REMESSA CD' in d or 'TRANSFERENCIA' in d:
        return 0.0

    # Se a família não estiver preenchida, inferir por palavras-chave na descrição
    if not f or f == 'NONE':
        if 'CAMISA' in d or 'BABY LOOK' in d:
            f = 'CAMISAS'
        elif 'TERCO' in d or 'ROSARIO' in d:
            f = 'TERCO'
        elif 'CADERNETA' in d or 'BLOCO' in d or 'CANETA' in d:
            f = 'PAPELARIA'
        elif 'BIBLIA' in d:
            f = 'BIBLIAS'
        else:
            f = 'EDICOES'

    # 2. GRUPO EM DESTAQUE (Elegível a 50% por Volume)
    # Contém EDICOES, ESTUDO BIBLICO, INFANTIL, ORDO AMORIS, PHILIPPOS, ESPIRITUALIDADE - EDICOES
    grupo_50_elegivel = False
    if any(x in f for x in ['EDICAO', 'EDICO', 'EDICOES']):
        grupo_50_elegivel = True
    elif f in ['ESTUDO BIBLICO', 'INFANTIL', 'ORDO AMORIS', 'PHILIPPOS', 'ESPIRITUALIDADE - EDICOES']:
        grupo_50_elegivel = True

    if grupo_50_elegivel:
        if 'PRAZO' in condicao:
            return 35.0
        elif condicao == 'A_VISTA_NORMAL':
            return 40.0
        else: # 'A_VISTA_AUTO' ou com volume
            return 50.0 if simular_50 else 40.0

    # 3. LINHA 2: AGENDAS
    if f == 'AGENDAS':
        return 30.0 if 'PRAZO' in condicao else 35.0

    # 4. LINHA 3: LITURGIA
    if f == 'LITURGIA':
        return 35.0

    # 5. LINHA 4: Contém BIBLIA, Contém DOCUMENTOS, ESCUTA, ESPIRITUALIDADE - TERCEIROS, TE SEGUIREI, SAZONAIS
    if 'BIBLIA' in f or 'DOCUMENTOS' in f or f in ['ESCUTA', 'ESPIRITUALIDADE - TERCEIROS', 'TE SEGUIREI', 'SAZONAIS']:
        return 30.0

    # 6. LINHA 5: PAPELARIA
    if f == 'PAPELARIA':
        return 20.0 if 'PRAZO' in condicao else 25.0

    # 7. LINHA 6: PANO, ROSARIO, TERCO, IMAGEM, ICONE, ACESSORIOS, BONE, CAMISAS
    if f in ['PANO', 'ROSARIO', 'TERCO', 'IMAGEM', 'ICONE', 'ACESSORIOS', 'BONE', 'CAMISAS']:
        return 20.0

    # 8. LINHA 7: VELA, TOALHAS
    if f in ['VELA', 'TOALHAS']:
        return 10.0 if 'PRAZO' in condicao else 15.0

    # 9. LINHA 8: MANUAL
    if f == 'MANUAL':
        return 0.0 if 'PRAZO' in condicao else 10.0

    # 10. LINHA 9: LANCHONETE, MATERIAL DE ESCRITORIO, CAIXAS, Contém EMBALAGEM, Contém USO E CONSUMO, GERAL ou Qualquer outra
    return 0.0

def calcular_politica_carrinho(itens: List[Dict[str, Any]], condicao: str = 'A_VISTA_AUTO') -> Dict[str, Any]:
    """
    Avalia a cesta de itens, simulando se o líquido atinge o corte de volume de R$ 5.000,00
    para destravar os 50% no grupo elegível.
    Retorna a lista atualizada com percentuais e totais consolidados.
    """
    # Passo 1: Simulação prévia com 50% nas famílias elegíveis para checar corte de R$ 5.000
    atinge_volume_5000 = False

    if condicao == 'A_VISTA_AUTO':
        sim_liq = 0.0
        for it in itens:
            qtd = float(it.get('qtd_vendida') or it.get('acerto_a_cobrar') or 0.0)
            if qtd <= 0:
                continue
            pr = float(it.get('preco_unitario') or it.get('preco') or 0.0)
            sku = str(it.get('sku') or '')
            desc = str(it.get('descricao') or it.get('desc') or '')
            fam = str(it.get('familia') or '')
            desc_pct = obter_desconto_item(sku, desc, fam, condicao='A_VISTA_AUTO', simular_50=True)
            sim_liq += (qtd * pr * (1 - desc_pct / 100.0))

        if sim_liq > 5000.0:
            atinge_volume_5000 = True

    # Passo 2: Aplicação definitiva
    tot_bruto = 0.0
    tot_desc = 0.0
    tot_liquido = 0.0
    itens_processados = []

    for it in itens:
        it_copia = dict(it)
        qtd = float(it.get('qtd_vendida') or it.get('acerto_a_cobrar') or 0.0)
        pr = float(it.get('preco_unitario') or it.get('preco') or 0.0)
        sku = str(it.get('sku') or '')
        desc = str(it.get('descricao') or it.get('desc') or '')
        fam = str(it.get('familia') or '')

        desc_pct = obter_desconto_item(
            sku, desc, fam,
            condicao=condicao,
            simular_50=atinge_volume_5000 if condicao == 'A_VISTA_AUTO' else False
        )

        sub_bruto = qtd * pr
        sub_desc = sub_bruto * (desc_pct / 100.0)
        sub_liq = sub_bruto - sub_desc

        it_copia['desconto_pct'] = desc_pct
        it_copia['valor_total_bruto'] = sub_bruto
        it_copia['valor_total_liquido'] = sub_liq

        tot_bruto += sub_bruto
        tot_desc += sub_desc
        tot_liquido += sub_liq
        itens_processados.append(it_copia)

    return {
        "condicao": condicao,
        "corte_volume_atingido": atinge_volume_5000,
        "total_bruto": round(tot_bruto, 2),
        "total_desconto": round(tot_desc, 2),
        "total_liquido": round(tot_liquido, 2),
        "itens": itens_processados
    }
