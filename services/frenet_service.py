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
    token = os.getenv("FRENET_TOKEN", "").strip()
    if not token:
        return {
            "disponivel": False,
            "configurado": False,
            "message": "Frenet não configurada no .env (defina FRENET_TOKEN). Insira o valor manualmente ou selecione Roberto Souza.",
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
