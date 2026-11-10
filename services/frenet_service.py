# -*- coding: utf-8 -*-
"""
services/frenet_service.py
===========================
Integração com a API de Cotação de Frete da Frenet (Correios, J&T, Jadlog, Total Express, etc.).
Preparado para ler FRENET_TOKEN do .env quando configurado pelo usuário.
"""
import os
import requests
import logging

logger = logging.getLogger("frenet_service")

FRENET_URL = "https://api.frenet.com.br/shipping/quote"
CEP_ORIGEM_PADRAO = "60170-001" # Edições Shalom - Fortaleza / CE

def cotar_frete_frenet(cep_destino: str, valor_itens: float = 45.0, peso_kg: float = 0.3, cep_origem: str = None) -> dict:
    """
    Realiza cotação de frete na Frenet para o CEP de destino informado.
    """
    token = (os.getenv("Token_Frenet") or os.getenv("FRENET_TOKEN") or "").strip()
    if not token:
        return {
            "disponivel": False,
            "configurado": False,
            "message": "Frenet não configurada no .env (defina Token_Frenet ou FRENET_TOKEN). Insira o valor manualmente ou selecione Roberto Souza.",
            "cotacoes": []
        }

    cep_dest_clean = str(cep_destino or "").replace("-", "").replace(".", "").strip()
    cep_orig_clean = str(cep_origem or CEP_ORIGEM_PADRAO).replace("-", "").replace(".", "").strip()

    if len(cep_dest_clean) != 8:
        return {
            "disponivel": False,
            "configurado": True,
            "message": f"CEP de destino inválido: {cep_destino}",
            "cotacoes": []
        }

    payload = {
        "SellerCEP": cep_orig_clean,
        "RecipientCEP": cep_dest_clean,
        "ShipmentInvoiceValue": float(valor_itens or 45.0),
        "ShippingItemArray": [
            {
                "Height": 5,
                "Length": 21,
                "Width": 15,
                "Weight": max(0.1, float(peso_kg or 0.3)),
                "Quantity": 1
            }
        ]
    }

    headers = {
        "token": token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        resp = requests.post(FRENET_URL, json=payload, headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            servicos = data.get("ShippingSevicesArray", [])
            cotacoes = []
            for s in servicos:
                if not s.get("Error"):
                    cotacoes.append({
                        "servico": s.get("ServiceDescription"),
                        "transportadora": s.get("Carrier"),
                        "valor": float(s.get("ShippingPrice") or 0.0),
                        "prazo_dias": int(s.get("DeliveryTime") or 0)
                    })
            cotacoes.sort(key=lambda x: x["valor"])
            return {
                "disponivel": True,
                "configurado": True,
                "cotacoes": cotacoes,
                "message": f"{len(cotacoes)} cotações encontradas."
            }
        else:
            return {
                "disponivel": False,
                "configurado": True,
                "message": f"Erro Frenet HTTP {resp.status_code}: {resp.text[:150]}",
                "cotacoes": []
            }
    except Exception as e:
        logger.error(f"Erro ao consultar Frenet: {e}")
        return {
            "disponivel": False,
            "configurado": True,
            "message": f"Falha na conexão com Frenet: {str(e)}",
            "cotacoes": []
        }

def cotar_frete_paroquia_caixas(cep_destino: str, peso_total_kg: float, valor_total: float = 500.0, caixas_manual: int = None) -> dict:
    """
    Cotação inteligente para paróquias:
    - Permite definir manualmente a quantidade de caixas ou usar o padrão automático (limite 18 kg por caixa).
    - Para Correios (PAC/Sedex), J&T Express e Total Express: orça cada caixa e soma as cotações.
    - Para Braspress: cotação única do lote total fechado (não fraciona).
    """
    import math
    LIMITE_CAIXA_KG = 18.0
    peso_tot = max(0.1, float(peso_total_kg or 1.0))
    val_tot = max(10.0, float(valor_total or 100.0))

    if caixas_manual and int(caixas_manual) >= 1:
        num_caixas = int(caixas_manual)
    else:
        num_caixas = math.ceil(peso_tot / LIMITE_CAIXA_KG) if peso_tot > 0 else 1

    num_caixas = max(1, num_caixas)
    peso_por_caixa = round(peso_tot / num_caixas, 2)
    valor_por_caixa = round(val_tot / num_caixas, 2)

    # 1. Cotação fracionada por caixa (Correios, J&T, Total)
    res_caixa = cotar_frete_frenet(cep_destino, valor_itens=valor_por_caixa, peso_kg=peso_por_caixa)
    if not res_caixa.get("disponivel"):
        return res_caixa

    # 2. Cotação total (Braspress)
    res_total = cotar_frete_frenet(cep_destino, valor_itens=val_tot, peso_kg=peso_tot) if num_caixas > 1 else res_caixa

    cotacoes_finais = []
    
    # Processa as que cobram por caixa
    for c in res_caixa.get("cotacoes", []):
        transp = str(c.get("transportadora") or "").upper()
        serv = str(c.get("servico") or "").upper()
        
        # Pular Braspress na cotação fracionada
        if "BRASPRESS" in transp or "BRASPRESS" in serv:
            continue
            
        val_unit = float(c.get("valor") or 0.0)
        val_somado = round(val_unit * num_caixas, 2)
        desc_caixas = f" ({num_caixas}x caixas de {peso_por_caixa}kg)" if num_caixas > 1 else ""
        
        cotacoes_finais.append({
            "transportadora": c.get("transportadora"),
            "servico": f"{c.get('servico')}{desc_caixas}",
            "valor": val_somado,
            "valor_unit_caixa": val_unit,
            "prazo_dias": c.get("prazo_dias"),
            "caixas": num_caixas,
            "tipo_calculo": "POR_CAIXA"
        })

    # Processa Braspress (cotação única do lote total)
    for c in res_total.get("cotacoes", []):
        transp = str(c.get("transportadora") or "").upper()
        serv = str(c.get("servico") or "").upper()
        if "BRASPRESS" in transp or "BRASPRESS" in serv:
            cotacoes_finais.append({
                "transportadora": c.get("transportadora"),
                "servico": f"{c.get('servico')} (Cotação Única - Carga Total {peso_tot}kg)",
                "valor": float(c.get("valor") or 0.0),
                "valor_unit_caixa": float(c.get("valor") or 0.0),
                "prazo_dias": c.get("prazo_dias"),
                "caixas": 1,
                "tipo_calculo": "CARGA_UNICA"
            })

    cotacoes_finais.sort(key=lambda x: x["valor"])

    return {
        "disponivel": True,
        "configurado": True,
        "peso_total_kg": peso_tot,
        "num_caixas": num_caixas,
        "peso_por_caixa": peso_por_caixa,
        "cotacoes": cotacoes_finais,
        "message": f"{len(cotacoes_finais)} opções calculadas ({num_caixas} caixa(s))."
    }
