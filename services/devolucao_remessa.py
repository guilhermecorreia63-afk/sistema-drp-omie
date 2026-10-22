# -*- coding: utf-8 -*-
"""
services/devolucao_remessa.py
==============================
Módulo oficial de devolução de remessas com ajuste seletivo de itens e quantidades no Omie ERP.

Fluxo do Processo:
1. Executa 'DevolverRemessa' no Omie (produtos/remessa/) passando o 'nCodRem'.
   O Omie altera o status da remessa para 'Devolvido' e cria automaticamente uma Nota de Entrada correspondente.
2. Aguarda o assentamento da nota gerada (3 a 4 segundos).
3. Consulta a Nota de Entrada criada via 'ConsultarNotaEnt' (produtos/notaentrada/) para obter os itens e o cliente.
4. Prepara as alterações:
   - Itens não desejados recebem cAcaoItem='E' (exclusão).
   - Itens mantidos recebem cAcaoItem='A', com a quantidade ajustada (nQtde), CFOP '1.917' (devolução)
     e movimentação de estoque ativada (infAdicItem.cNaoMovEstoque='N').
5. Aplica a categoria oficial de 'Compras de Mercadorias para Revenda' (cCodCateg='2.01.01') e observação explicativa.
6. Atualiza a Nota de Entrada via 'AlterarNotaEnt' (produtos/notaentrada/).
   NOTA CRÍTICA: Nunca enviar 'cNumeroNotaEnt' no cabeçalho durante a alteração, apenas 'nCodNotaEnt' e 'nCodCli'.
"""

import time
import json
import logging
from typing import Dict, List, Any, Optional

try:
    from omie_client import OmieClient
except ImportError:
    from services.omie_client import OmieClient

logger = logging.getLogger("DevolucaoRemessa")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CATEGORIA_COMPRAS_REVENDA = "2.01.01" # Compras de Mercadorias para Revenda
CFOP_DEVOLUCAO = "1.917"              # Entrada de devolução de mercadoria remetida para venda fora do estabelecimento / consignação


def executar_devolucao_seletiva_remessa(
    nCodRem: int,
    itens_manter: Dict[str, int],
    observacao: str = "Entrada de remessa para faturamento de pedido que estava em consignado",
    cod_categoria: str = CATEGORIA_COMPRAS_REVENDA,
    client: Optional[OmieClient] = None
) -> Dict[str, Any]:
    """
    Executa a devolução oficial de uma remessa no Omie, filtrando apenas os itens e quantidades desejadas.

    :param nCodRem: ID numérico da remessa no Omie (ex: 2265363412 ou obtido pelo número)
    :param itens_manter: Dicionário mapeando SKU/Código do produto para a quantidade a devolver.
                         Ex: {"PRD00770": 7} ou {"000566": 10}
    :param observacao: Texto para gravar no campo de observação da Nota de Entrada.
    :param cod_categoria: Código da categoria contábil/financeira (padrão: 2.01.01 - Compras de Mercadorias para Revenda)
    :param client: Instância do OmieClient (MATRIZ). Se None, instancia automaticamente.
    :return: Dicionário com resultado da operação {'sucesso': bool, 'nIdDevolucao': int, 'nota': dict, ...}
    """
    if client is None:
        client = OmieClient("MATRIZ")

    logger.info(f"[DEVOLUCAO] Iniciando devolução da Remessa nCodRem={nCodRem}...")
    
    # 1. Devolver a remessa via API
    res_dev = client.executar("produtos/remessa/", "DevolverRemessa", [{"nCodRem": int(nCodRem)}])
    if not res_dev or res_dev.get("cStatus") not in ["0", 0]:
        erro_msg = res_dev.get("cDescStatus") or res_dev.get("faultstring") or str(res_dev)
        raise RuntimeError(f"Erro ao devolver remessa {nCodRem} no Omie: {erro_msg}")

    nIdDevolucao = res_dev.get("nIdDevolucao")
    logger.info(f"[DEVOLUCAO] Remessa devolvida com sucesso! Nota de Entrada ID: {nIdDevolucao}")

    # 2. Aguarda assentamento do registro no Omie
    time.sleep(3.5)

    # 3. Consultar a Nota de Entrada gerada
    nota_entrada = client.executar("produtos/notaentrada/", "ConsultarNotaEnt", [{"nCodNotaEnt": int(nIdDevolucao)}])
    if not nota_entrada or "cabec" not in nota_entrada:
        raise RuntimeError(f"Erro ao consultar a Nota de Entrada {nIdDevolucao}: {nota_entrada}")

    cabec = nota_entrada.get("cabec", {})
    nCodCli = cabec.get("nCodCli")
    num_nota = cabec.get("cNumeroNotaEnt", "")
    itens_nota = nota_entrada.get("produtos", [])

    logger.info(f"[DEVOLUCAO] Nota {num_nota} gerada para cliente {nCodCli} com {len(itens_nota)} itens.")

    # 3.1 Mapear itens_manter para nCodProd garantindo compatibilidade com SKU e ID numérico
    map_cod_prod_qtd = {}
    for chave, qtd in itens_manter.items():
        if str(chave).isdigit():
            map_cod_prod_qtd[int(chave)] = qtd
        else:
            res_p = client.executar("geral/produtos/", "ConsultarProduto", [{"codigo_produto_integracao": str(chave).strip()}])
            if res_p and "codigo_produto" in res_p:
                map_cod_prod_qtd[int(res_p["codigo_produto"])] = qtd
            else:
                logger.warning(f"[DEVOLUCAO] Não foi possível localizar nCodProd para chave '{chave}'")

    # 4. Montar a lista de alterações/exclusões de produtos
    produtos_alteracao = []
    itens_encontrados = set()

    for item in itens_nota:
        cod_it = item.get("nCodIt")
        cod_prod = item.get("nCodProd")
        desc_item = item.get("cDescItem", "") or f"Produto {cod_prod}"

        # Verifica se o item deve ser mantido
        qtd_alvo = map_cod_prod_qtd.get(int(cod_prod)) if cod_prod else None

        if qtd_alvo is not None and qtd_alvo > 0:
            # Manter item e ajustar quantidade e CFOP
            logger.info(f" -> MANTER item nCodProd={cod_prod} ({desc_item}): ajustando para {qtd_alvo} un, CFOP {CFOP_DEVOLUCAO}")
            produtos_alteracao.append({
                "nCodIt": cod_it,
                "cAcaoItem": "A",
                "nQtde": int(qtd_alvo),
                "cCFOP": CFOP_DEVOLUCAO,
                "infAdicItem": {
                    "cNaoMovEstoque": "N"  # Movimentar estoque ativado
                }
            })
            itens_encontrados.add(cod_prod)
        else:
            # Excluir item da nota de entrada
            logger.info(f" -> EXCLUIR item nCodProd={cod_prod} ({desc_item}) da Nota de Entrada")
            produtos_alteracao.append({
                "nCodIt": cod_it,
                "cAcaoItem": "E"
            })

    # 5. Montar payload de AlterarNotaEnt
    # ATENÇÃO: NUNCA passar 'cNumeroNotaEnt' no cabecalho de alteração!
    payload_alterar = {
        "cabec": {
            "nCodNotaEnt": int(nIdDevolucao),
            "nCodCli": int(nCodCli)
        },
        "infAdic": {
            "cCodCateg": str(cod_categoria)  # Força "2.01.01" (Compras de Mercadorias para Revenda)
        },
        "obs": {
            "cObs": observacao
        },
        "produtos": produtos_alteracao
    }

    # Pausa de segurança contra rate limit
    time.sleep(3.0)

    # 6. Executar AlterarNotaEnt
    res_alt = client.executar("produtos/notaentrada/", "AlterarNotaEnt", [payload_alterar])
    logger.info(f"[DEVOLUCAO] Resposta da alteração da Nota {num_nota}: {res_alt}")

    return {
        "sucesso": True,
        "nIdDevolucao": nIdDevolucao,
        "cNumeroNotaEnt": num_nota,
        "nCodCli": nCodCli,
        "categoria": cod_categoria,
        "itens_devolvidos": list(itens_encontrados),
        "resposta_alteracao": res_alt
    }
