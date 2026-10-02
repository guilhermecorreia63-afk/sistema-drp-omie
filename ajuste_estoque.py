"""
Módulo Padronizado de Ajuste de Estoque Omie (Matriz)
---------------------------------------------------
Este módulo automatiza o processo de ajuste de estoque (Entradas por sobra e Saídas via Remessa por falta)
com base em contagens físicas auditadas versus o saldo atual no Omie ERP.

Regras de Negócio Padronizadas:
1. Fornecedor / Cliente Padrão: EDICOES SHALOM (CNPJ 07.044.456/0003-64 | ID Omie: 1854959029)
2. Local de Estoque: Matriz Padrão (ID 1794541746)

3. ENTRADA (Físico > Sistema | IncluirNotaEnt):
   - Categoria / Receita: Compra para Revenda (2.01.03)
   - CFOP: 1.949
   - ICMS: 41 (Isenta / Não tributada)
   - PIS: 74 (Operação Sem Incidência)
   - COFINS: 74 (Operação Sem Incidência)
   - Preço / Custo: Preço de Custo (CMC) do produto no Omie. Se for Ícone, aplica 20% de desconto sobre valor de venda.

4. SAÍDA VIA REMESSA (Físico < Sistema | IncluirRemessa):
   - Cenário Fiscal: Baixa de Estoque (ID: 1818512707)
   - Categoria / Receita: Venda Comercial (1.01.02)
   - CFOP: 5.927 (Baixa de Estoque)
   - ICMS: 41 (Isenta / Não tributada)
   - PIS: 07 (Operação Isenta)
   - COFINS: 07 (Operação Isenta)
   - Preço / Custo: Preço de Custo (CMC) / valor unitário de tabela.
"""

import os
import sys
import json
import time
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath('.'))
from omie_client import OmieClient

# Constantes globais do Omie
ID_CLIENTE_EDICOES_SHALOM = 1854959029 # CNPJ: 07.044.456/0003-64
LOCAL_ESTOQUE_MATRIZ_PADRAO = 1794541746
CODIGO_CENARIO_BAIXA_ESTOQUE = 1818512707 # Cenário Fiscal "Baixa de Estoque"

CATEGORIA_COMPRA_REVENDA = "2.01.03"
CATEGORIA_VENDA_COMERCIAL = "1.01.02"

URL_NOTA_ENTRADA = "https://app.omie.com.br/api/v1/produtos/notaentrada/"

class AjusteEstoqueManager:
    def __init__(self, unidade="MATRIZ"):
        self.client = OmieClient(unidade)
        self.app_key = self.client.app_key
        self.app_secret = self.client.app_secret

    def obter_dados_produto(self, identificador: str):
        """Busca dados de um produto pelo SKU (codigo_produto_integracao) ou codigo."""
        # 1. Tentar por codigo_produto_integracao (SKU)
        res = self.client.executar("geral/produtos/", "ConsultarProduto", [{
            "codigo_produto_integracao": str(identificador).strip()
        }])
        
        if not res or "codigo_produto" not in res:
            # 2. Tentar por codigo interno
            res = self.client.executar("geral/produtos/", "ConsultarProduto", [{
                "codigo": str(identificador).strip()
            }])

        if not res or "codigo_produto" not in res:
            # 3. Tentar por nCodProd direto se numérico
            if str(identificador).strip().isdigit():
                res = self.client.executar("geral/produtos/", "ConsultarProduto", [{
                    "codigo_produto": int(identificador)
                }])

        if res and "codigo_produto" in res:
            ncod = res["codigo_produto"]
            sku = res.get("codigo_produto_integracao") or res.get("codigo")
            descr = res.get("descricao", "")
            
            # Buscar estoque atual
            res_est = self.client.executar("estoque/consulta/", "ObterEstoqueProduto", [{
                "nCodProd": ncod
            }])
            estoque_matriz = 0
            if res_est and "listaEstoque" in res_est:
                for loc in res_est["listaEstoque"]:
                    if loc.get("codigo_local_estoque") == LOCAL_ESTOQUE_MATRIZ_PADRAO or loc.get("local") == "PADRAO":
                        estoque_matriz = int(loc.get("saldo", 0))
                        break
                else:
                    if res_est["listaEstoque"]:
                        estoque_matriz = int(res_est["listaEstoque"][0].get("saldo", 0))

            # Preço unitário / Custo
            val_venda = float(res.get("valor_unitario") or 0.0)
            val_custo = float(res.get("preco_custo") or res.get("custo_medio") or val_venda)

            # Regra de desconto de 20% para ÍCONES
            is_icone = "ICONE" in descr.upper() or "ÍCONE" in descr.upper()
            val_custo_calculado = round(val_venda * 0.80, 2) if (is_icone and val_venda > 0) else (val_custo if val_custo > 0 else val_venda)

            return {
                "nCodProd": ncod,
                "sku": sku,
                "descricao": descr,
                "qtd_sistema": estoque_matriz,
                "valor_venda": val_venda,
                "valor_custo": val_custo_calculado,
                "is_icone": is_icone
            }

        return None

    def analisar_contagem(self, contagem_fisica: dict):
        """
        Recebe um dicionário {SKU_ou_CODIGO: QTD_FISICA} ou lista de dicts.
        Compara físico x sistema e gera o relatório de Entradas e Saídas.
        """
        if isinstance(contagem_fisica, list):
            # Converter lista para dict
            cont_dict = {}
            for item in contagem_fisica:
                k = item.get("sku") or item.get("codigo") or item.get("nCodProd")
                v = item.get("qtd_fisica") or item.get("qtd") or 0
                cont_dict[k] = v
            contagem_fisica = cont_dict

        print(f"=== INICIANDO ANÁLISE DE ESTOQUE ({len(contagem_fisica)} PRODUTOS) ===")

        relatorio = []
        entradas = []
        saidas = []

        for key, qtd_fisica in contagem_fisica.items():
            info = self.obter_dados_produto(key)
            if not info:
                print(f"⚠️ Produto '{key}' não encontrado no Omie!")
                continue

            qtd_sis = info["qtd_sistema"]
            diferenca = qtd_fisica - qtd_sis

            item_res = {
                "nCodProd": info["nCodProd"],
                "sku": info["sku"],
                "descricao": info["descricao"],
                "qtd_fisica": qtd_fisica,
                "qtd_sistema": qtd_sis,
                "diferenca": diferenca,
                "valor_custo_unit": info["valor_custo"],
                "valor_venda": info["valor_venda"],
            }

            if diferenca > 0:
                item_res["acao"] = "ENTRADA"
                item_res["qtd_ajuste"] = diferenca
                item_res["custo_total_ajuste"] = round(diferenca * info["valor_custo"], 2)
                entradas.append(item_res)
            elif diferenca < 0:
                item_res["acao"] = "SAÍDA (REMESSA)"
                item_res["qtd_ajuste"] = abs(diferenca)
                item_res["custo_total_ajuste"] = round(abs(diferenca) * info["valor_custo"], 2)
                saidas.append(item_res)
            else:
                item_res["acao"] = "CORRETO"
                item_res["qtd_ajuste"] = 0
                item_res["custo_total_ajuste"] = 0.0

            relatorio.append(item_res)

        return {
            "relatorio": relatorio,
            "entradas": entradas,
            "saidas": saidas,
            "totais": {
                "itens_analisados": len(relatorio),
                "total_entradas_pecas": sum(e["qtd_ajuste"] for e in entradas),
                "custo_total_entradas": sum(e["custo_total_ajuste"] for e in entradas),
                "total_saidas_pecas": sum(s["qtd_ajuste"] for s in saidas),
                "custo_total_saidas": sum(s["custo_total_ajuste"] for s in saidas)
            }
        }

    def lancar_nota_entrada(self, entradas: list, valor_unit_custom: float = None):
        """Lança Nota de Entrada no Omie para as sobras de estoque (IncluirNotaEnt)."""
        if not entradas:
            print("Nenhuma entrada pendente para lançar.")
            return None

        import requests
        itens_payload = []

        for idx, item in enumerate(entradas, 1):
            val_unit = valor_unit_custom if valor_unit_custom is not None else item["valor_custo_unit"]
            itens_payload.append({
                "cCodItInt": f"ENT_{idx:03d}",
                "nCodProd": int(item["nCodProd"]),
                "codigo_local_estoque": LOCAL_ESTOQUE_MATRIZ_PADRAO,
                "nQtde": int(item["qtd_ajuste"]),
                "nValUnit": float(val_unit),
                "cCFOP": "1.949",
                "ICMS": {
                    "cOrigem": "0",
                    "cSitTrib": "41"
                },
                "PIS": {
                    "cSitTribPIS": "74"
                },
                "COFINS": {
                    "cSitTribCOFINS": "74"
                }
            })

        cod_integracao = f"ENT_AJU_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        payload = {
            "call": "IncluirNotaEnt",
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "param": [{
                "cabec": {
                    "cCodIntNotaEnt": cod_integracao[:20],
                    "dPrevisao": datetime.now().strftime("%d/%m/%Y"),
                    "nCodCli": ID_CLIENTE_EDICOES_SHALOM,
                },
                "infAdic": {
                    "cCodCateg": CATEGORIA_COMPRA_REVENDA
                },
                "produtos": itens_payload,
            }],
        }

        print(f"\n[ENVIANDO] Nota de Entrada ({len(itens_payload)} itens, {sum(i['nQtde'] for i in itens_payload)} pcs)...")
        resp = requests.post(URL_NOTA_ENTRADA, json=payload, headers={"Content-Type": "application/json"}, timeout=120)
        res_json = resp.json()
        print("RESPOSTA ENTRADA OMIE:", json.dumps(res_json, indent=2, ensure_ascii=False))
        return res_json

    def lancar_remessa_saida(self, saidas: list, valor_unit_custom: float = None):
        """Lança Remessa de Saída no Omie para as faltas de estoque (IncluirRemessa)."""
        if not saidas:
            print("Nenhuma saída pendente para lançar.")
            return None

        produtos_req = []
        peso_total = 0.0

        for idx, item in enumerate(saidas, 1):
            val_unit = valor_unit_custom if valor_unit_custom is not None else item["valor_custo_unit"]
            qtd = int(item["qtd_ajuste"])
            peso_total += (0.2 * qtd)

            prod_entry = {
                "cCFOP": "5.927",
                "cCodItInt": f"SAI_{idx:03d}",
                "nCodIt": 0,
                "nCodProd": int(item["nCodProd"]),
                "nQtde": qtd,
                "nValUnit": float(val_unit),
                "ICMS": {
                    "cModBC": "",
                    "cOrigem": "0",
                    "cSitTrib": "41",
                    "nAliq": 0,
                    "nBC": 0,
                    "nRedBC": 0,
                    "nValor": 0
                },
                "PIS": {
                    "cSitTribPIS": "07",
                    "cTpCalcPIS": "",
                    "nAliqPIS": 0,
                    "nBCPIS": 0,
                    "nQtdUTPIS": 0,
                    "nValPISUT": 0,
                    "nValPIS": 0
                },
                "COFINS": {
                    "cSitTribCOFINS": "07",
                    "cTpCalcCOFINS": "",
                    "nAliqCOFINS": 0,
                    "nBCCOFINS": 0,
                    "nQtdUTCOFINS": 0,
                    "nVaCOFINSSUT": 0,
                    "nValCOFINS": 0
                },
                "infAdicItem": {
                    "codigo_cenario_impostos_item": CODIGO_CENARIO_BAIXA_ESTOQUE,
                    "cNaoMovEstoque": "N"
                }
            }
            produtos_req.append(prod_entry)

        timestamp_str = str(int(time.time()))

        payload = {
            "cabec": {
                "cCodIntRem": f"REM_AJU_{timestamp_str}",
                "dPrevisao": time.strftime("%d/%m/%Y"),
                "nCodCli": ID_CLIENTE_EDICOES_SHALOM,
                "nCodRem": 0,
                "nCodVend": "",
                "codigo_cenario_impostos": CODIGO_CENARIO_BAIXA_ESTOQUE
            },
            "email": {
                "cEmail": "centrodedistribuicao@comshalom.org"
            },
            "frete": {
                "cEspVol": "VOLUMES",
                "cMarVol": "",
                "cNumVol": "1",
                "cPlaca": "",
                "cTpFrete": "9",
                "cUF": "",
                "nCodTransp": 0,
                "nPesoBruto": float(round(peso_total, 3)),
                "nPesoLiq": float(round(peso_total * 0.9, 3)),
                "nQtdVol": 1,
                "nValFrete": 0,
                "nValOutras": 0,
                "nValSeguro": 0
            },
            "infAdic": {
                "cCodCateg": CATEGORIA_VENDA_COMERCIAL,
                "cConsFinal": "S",
                "cContato": "MATRIZ",
                "cDadosAdic": "Baixa de Estoque - Ajuste de Estoque Auditado (CFOP 5.927)",
                "cNumCtr": "",
                "cPedido": "",
                "nCodProj": 0
            },
            "obs": {
                "cObs": "Baixa de Estoque - Ajuste Fisico Matriz"
            },
            "produtos": produtos_req
        }

        print(f"\n[ENVIANDO] Remessa de Saida ({len(produtos_req)} itens, {sum(i['nQtde'] for i in produtos_req)} pcs)...")
        res = self.client.executar("produtos/remessa/", "IncluirRemessa", [payload])
        print("RESPOSTA SAIDA OMIE:", json.dumps(res, indent=2, ensure_ascii=False))
        return res

    def executar_ajuste_completo(self, contagem_fisica: dict, valor_unit_custom: float = None):
        """Executa a análise, Entrada e Saída de forma automatizada."""
        analise = self.analisar_contagem(contagem_fisica)

        print("\n--- RESUMO DA ANÁLISE DE AJUSTE ---")
        print(f"Itens Analisados: {analise['totais']['itens_analisados']}")
        print(f"Entradas (Sobras): {len(analise['entradas'])} SKUs ({analise['totais']['total_entradas_pecas']} pçs)")
        print(f"Saídas (Faltas): {len(analise['saidas'])} SKUs ({analise['totais']['total_saidas_pecas']} pçs)")

        res_entrada = None
        if analise["entradas"]:
            res_entrada = self.lancar_nota_entrada(analise["entradas"], valor_unit_custom=valor_unit_custom)

        res_saida = None
        if analise["saidas"]:
            res_saida = self.lancar_remessa_saida(analise["saidas"], valor_unit_custom=valor_unit_custom)

        return {
            "analise": analise,
            "resultado_entrada": res_entrada,
            "resultado_saida": res_saida
        }

if __name__ == "__main__":
    print("Módulo de Ajuste de Estoque Omie pronto para uso.")
