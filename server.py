# -*- coding: utf-8 -*-
"""
server.py - Servidor HTTP Backend + Static Server para DRP Omie ERP
====================================================================
Servidor Python embutido que serve os arquivos estáticos da aplicação web (http://localhost:8889)
e fornece endpoints HTTP API REST (/api/email e /api/sync) para disparar e-mails e recarregar dados do Omie/Turso.
"""

import http.server
import socketserver
import json
import os
import sys
from datetime import datetime
from urllib.parse import parse_qs, urlparse

# Garante importação dos módulos do projeto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

try:
    import alertas_email
except ImportError:
    alertas_email = None

try:
    import database as db
except ImportError:
    db = None

PORT = 8889

class DRPRequestHandler(http.server.SimpleHTTPRequestHandler):
    
    def end_headers(self):
        # Desativa cache HTTP para garantir atualizações em tempo real
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        url_path = self.path.split('?')[0].rstrip('/')
        if url_path == '/api/cron_sync':
            self.handle_api_cron_sync()
        elif url_path == '/api/blacklist':
            self.handle_api_blacklist_get()
        elif url_path == '/api/destaques':
            self.handle_api_destaques_get()
        elif url_path in ['/api/remessas/status_transito', '/api/remessas/status']:
            self.handle_api_remessas_status_transito_get()
        elif url_path == '/api/remessas/listar':
            self.handle_api_remessas_listar()
        elif url_path == '/api/depara':
            self.handle_api_depara_get()
        elif url_path == '/api/depositos':
            self.handle_api_depositos_get()
        elif url_path == '/api/depositos/historico':
            self.handle_api_depositos_historico()
        elif url_path in ['/api/depositos/enderecos', '/api/producao']:
            if url_path == '/api/producao':
                self.handle_api_producao_get()
            else:
                self.handle_api_depositos_enderecos_get()
        elif url_path == '/api/combo/detalhes':
            self.handle_api_combo_detalhes()
        elif url_path == '/api/consignacao/clientes':
            self.handle_api_consignacao_clientes()
        elif url_path == '/api/consignacao/remessas':
            self.handle_api_consignacao_remessas()
        elif url_path == '/api/consignacao/acertos':
            self.handle_api_consignacao_acertos_listar()
        elif url_path == '/api/consignacao/acerto':
            self.handle_api_consignacao_acerto_obter()
        elif url_path == '/api/consignacao/eventos/remessas':
            self.handle_api_consignacao_eventos_remessas()
        elif url_path == '/api/consignacao/buscar_produto':
            self.handle_api_consignacao_buscar_produto()
        elif url_path == '/api/consignacao/disparar_alertas_prazos':
            self.handle_api_consignacao_disparar_alertas_prazos()
        elif url_path == '/api/assinaturas/pedidos_proximo_envio':
            self.handle_api_assinaturas_listar_pedidos_proximo_envio()
        elif url_path == '/api/assinaturas/sincronizar_pedidos_omie':
            self.handle_api_assinaturas_sincronizar_pedidos_omie()
        elif url_path == '/api/assinaturas/metadados':
            self.handle_api_assinaturas_metadados()
        elif url_path == '/api/assinaturas/buscar_clientes':
            self.handle_api_assinaturas_buscar_clientes()
        elif url_path == '/api/frenet/cotar':
            self.handle_api_frenet_cotar()
        elif url_path == '/api/pedidos_venda/consultar':
            self.handle_api_pedidos_venda_consultar()
        elif url_path in ['/api/inteligencia_matriz', '/api/drp/inteligencia_matriz']:
            self.handle_api_inteligencia_matriz()
        elif url_path in ['/api/coordenacao/pauta', '/api/drp/coordenacao/pauta']:
            self.handle_api_coordenacao_pauta_get()
        elif url_path in ['/data/produtos_turso.json', '/api/produtos', '/api/drp/produtos']:
            self.handle_api_produtos_turso_json()
        elif url_path in ['/api/sync_requisicoes', '/api/sync/requisicoes']:
            self.handle_api_sync_requisicoes()
        elif url_path == '/api/assinaturas/dados':
            self.handle_api_assinaturas_dados()
        elif url_path == '/api/assinaturas/exportar_etiquetas':
            self.handle_api_assinaturas_exportar_etiquetas()
        elif url_path == '/api/assinaturas/exportar_correios':
            self.handle_api_assinaturas_exportar_correios()
        elif url_path == '/api/assinaturas/relatorio_pdf':
            self.handle_api_assinaturas_relatorio_pdf()
        else:
            super().do_GET()

    def do_POST(self):
        url_path = self.path.split('?')[0].rstrip('/')
        if url_path == '/api/cron_sync':
            self.handle_api_cron_sync()
        elif url_path in ['/api/sync_requisicoes', '/api/sync/requisicoes']:
            self.handle_api_sync_requisicoes()
        elif url_path == '/api/email':
            self.handle_api_email()
        elif url_path == '/api/sync':
            self.handle_api_sync()
        elif url_path in ['/api/producao', '/api/producao/salvar']:
            self.handle_api_producao_save()
        elif url_path in ['/api/coordenacao/adicionar', '/api/drp/coordenacao/adicionar']:
            self.handle_api_coordenacao_adicionar()
        elif url_path in ['/api/coordenacao/remover', '/api/drp/coordenacao/remover']:
            self.handle_api_coordenacao_remover()
        elif url_path in ['/api/coordenacao/salvar_decisao', '/api/drp/coordenacao/salvar_decisao']:
            self.handle_api_coordenacao_salvar_decisao()
        elif url_path in ['/api/coordenacao/salvar_meta', '/api/drp/coordenacao/salvar_meta']:
            self.handle_api_coordenacao_salvar_meta()
        elif url_path in ['/api/pedido_compra/remover', '/api/pedidos/remover']:
            self.handle_api_pedido_compra_remover()
        elif url_path == '/api/blacklist' or url_path == '/api/blacklist/salvar':
            self.handle_api_blacklist_save()
        elif url_path == '/api/destaques' or url_path == '/api/destaques/salvar':
            self.handle_api_destaques_save()
        elif url_path in ['/api/remessas/status_transito', '/api/remessas/salvar_status_transito', '/api/remessas/salvar_status', '/api/remessas/status/salvar']:
            self.handle_api_remessas_status_transito_save()
        elif url_path == '/api/requisicao-compra':
            self.handle_api_requisicao_compra()
        elif url_path == '/api/remessas/incluir':
            self.handle_api_remessas_incluir()
        elif url_path == '/api/remessas/listar':
            self.handle_api_remessas_listar()
        elif url_path == '/api/remessas/status':
            self.handle_api_remessas_status()
        elif url_path == '/api/remessas/alterar':
            self.handle_api_remessas_alterar()
        elif url_path == '/api/remessas/devolver':
            self.handle_api_remessas_devolver()
        elif url_path in ['/api/salvar_lote_manual', '/api/drp/salvar_lote_manual']:
            self.handle_api_salvar_lote_manual()
        elif url_path == '/api/depara':
            self.handle_api_depara_save()
        elif url_path in ['/api/depositos/salvar', '/api/depositos']:
            self.handle_api_depositos_save()
        elif url_path == '/api/depositos/transferir':
            self.handle_api_depositos_transferir()
        elif url_path == '/api/depositos/email_reabastecimento':
            self.handle_api_depositos_email_reabastecimento()
        elif url_path in ['/api/depositos/enderecos/salvar', '/api/depositos/enderecos']:
            self.handle_api_depositos_enderecos_save()
        elif url_path == '/api/combo/remover_componente':
            self.handle_api_combo_remover_componente()
        elif url_path == '/api/combo/alterar_preco':
            self.handle_api_combo_alterar_preco()
        elif url_path == '/api/consignacao/unificar':
            self.handle_api_consignacao_unificar()
        elif url_path == '/api/consignacao/salvar_acerto':
            self.handle_api_consignacao_salvar_acerto()
        elif url_path == '/api/consignacao/integrar_omie':
            self.handle_api_consignacao_integrar_omie()
        elif url_path == '/api/consignacao/eventos/salvar':
            self.handle_api_consignacao_eventos_salvar()
        elif url_path == '/api/consignacao/vincular_remessa_aberta':
            self.handle_api_consignacao_vincular_remessa_aberta()
        elif url_path == '/api/consignacao/atualizar_inicio_prazo':
            self.handle_api_consignacao_atualizar_inicio_prazo()
        elif url_path == '/api/consignacao/disparar_alertas_prazos':
            self.handle_api_consignacao_disparar_alertas_prazos()
        elif url_path == '/api/assinaturas/cadastrar_pedido_proximo_envio':
            self.handle_api_assinaturas_cadastrar_pedido_proximo_envio()
        elif url_path == '/api/assinaturas/sincronizar_pedidos_omie':
            self.handle_api_assinaturas_sincronizar_pedidos_omie()
        elif url_path == '/api/assinaturas/excluir_pedido_proximo_envio':
            self.handle_api_assinaturas_excluir_pedido_proximo_envio()
        elif url_path == '/api/assinaturas/lancar_pedido_venda_omie':
            self.handle_api_assinaturas_lancar_pedido_venda_omie()
        elif url_path == '/api/assinaturas/sincronizar':
            self.handle_api_assinaturas_sincronizar()
        elif url_path == '/api/assinaturas/gerar_remessa_baixa':
            self.handle_api_assinaturas_gerar_remessa_baixa()
        elif url_path == '/api/assinaturas/gerar_remessa_paroquia':
            self.handle_api_assinaturas_gerar_remessa_paroquia()
        elif url_path == '/api/assinaturas/concluir_lote':
            self.handle_api_assinaturas_concluir_lote()
        else:
            self.send_error(404, f"Endpoint não encontrado: {self.path}")

    def handle_api_depara_get(self):
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'depara.json')
        depara_data = {"grupos": [{"sku_principal": "009539", "skus_relacionados": ["009622"], "nome_grupo": "Toalha Litúrgica Maria (Branca / Azul)"}]}
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    depara_data = json.load(f)
            except Exception as e:
                print(f"[API SERVER] Erro ao carregar depara.json: {e}")
        self._send_json(depara_data)

    def handle_api_depara_save(self):
        body = self._read_body()
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'depara.json')
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(body, f, ensure_ascii=False, indent=2)
            self._send_json({"success": True, "message": "DEPARA atualizado com sucesso."})
        except Exception as e:
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_depositos_get(self):
        file_data = {}
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'depositos_matriz.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
            except Exception as e:
                print(f"[API SERVER] Erro ao ler depositos_matriz.json: {e}")

        depositos = {}
        if db:
            try:
                depositos = db.obter_depositos_matriz_db()
            except Exception as e:
                print(f"[API SERVER] Erro ao buscar depositos do banco: {e}")

        # Mesclar mantendo as quantidades do JSON caso o banco traga 0 ou não possua o registro
        for k, v in file_data.items():
            if k not in depositos:
                depositos[k] = v
            else:
                db_d1 = int(depositos[k].get('deposito_1', 0) or 0)
                db_d2 = int(depositos[k].get('deposito_2', 0) or 0)
                file_d1 = int(v.get('deposito_1', 0) or 0)
                file_d2 = int(v.get('deposito_2', 0) or 0)
                
                if file_d1 > 0 and db_d1 == 0:
                    depositos[k]['deposito_1'] = file_d1
                if file_d2 > 0 and db_d2 == 0:
                    depositos[k]['deposito_2'] = file_d2

        self._send_json({"success": True, "depositos": depositos})

    def handle_api_depositos_save(self):
        body = self._read_body()
        sku = str(body.get('sku', '')).strip()
        fracionado = int(body.get('fracionado', 0))
        deposito_1 = int(body.get('deposito_1', 0))
        deposito_2 = int(body.get('deposito_2', 0))

        if not sku:
            self._send_json({"success": False, "message": "SKU é obrigatório."}, status=400)
            return

        if db:
            try:
                db.salvar_deposito_matriz_db(sku, fracionado, deposito_1, deposito_2)
            except Exception as e:
                print(f"[API SERVER] Erro ao salvar deposito no DB: {e}")

        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'depositos_matriz.json')
        file_data = {}
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
            except Exception:
                file_data = {}
        file_data[sku] = {
            "fracionado": fracionado,
            "deposito_1": deposito_1,
            "deposito_2": deposito_2
        }
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(file_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        self._send_json({"success": True, "message": f"Contagem do SKU {sku} salva com sucesso."})

    def handle_api_depositos_transferir(self):
        body = self._read_body()
        sku = str(body.get('sku', '')).strip()
        nome_produto = str(body.get('nome_produto', '')).strip()
        origem = str(body.get('origem', '')).strip()
        destino = str(body.get('destino', '')).strip()
        qtd = int(body.get('quantidade', 0))
        obs = str(body.get('observacao', '')).strip()

        if not sku or not origem or not destino or qtd <= 0:
            self._send_json({"success": False, "message": "Dados de transferência inválidos."}, status=400)
            return

        if db:
            try:
                db.registrar_transferencia_deposito_db(sku, nome_produto, origem, destino, qtd, obs)
            except Exception as e:
                print(f"[API SERVER] Erro ao registrar transferência no DB: {e}")

        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'historico_transferencias.json')
        history = []
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except Exception:
                history = []

        new_entry = {
            "id": len(history) + 1,
            "sku": sku,
            "nome_produto": nome_produto,
            "origem": origem,
            "destino": destino,
            "quantidade": qtd,
            "data_hora": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "observacao": obs
        }
        history.insert(0, new_entry)
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        self._send_json({"success": True, "message": f"Transferência de {qtd} un registrada com sucesso."})

    def handle_api_depositos_historico(self):
        history = []
        if db:
            try:
                history = db.obter_historico_transferencias_db()
            except Exception as e:
                print(f"[API SERVER] Erro ao buscar histórico do DB: {e}")

        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'historico_transferencias.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    file_history = json.load(f)
                    if not history:
                        history = file_history
            except Exception:
                pass

        self._send_json({"success": True, "historico": history})

    def handle_api_depositos_enderecos_get(self):
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'enderecos_depositos.json')
        enderecos = {}
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    enderecos = json.load(f)
            except Exception as e:
                print(f"[API SERVER] Erro ao ler enderecos_depositos.json: {e}")

        self._send_json({"success": True, "enderecos": enderecos})

    def handle_api_depositos_enderecos_save(self):
        body = self._read_body()
        sku = str(body.get('sku', '')).strip()
        id_produto = body.get('id_produto')
        fracionado = str(body.get('fracionado', '')).strip()
        deposito_1 = str(body.get('deposito_1', '')).strip()

        if not sku:
            self._send_json({"success": False, "message": "SKU é obrigatório."}, status=400)
            return

        # Formatar endereço Omie combinado (ex: C3N5, D1N2)
        partes = []
        if fracionado: partes.append(fracionado)
        if deposito_1: partes.append(deposito_1)
        raw_texto = ", ".join(partes)

        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'enderecos_depositos.json')
        enderecos = {}
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    enderecos = json.load(f)
            except Exception:
                enderecos = {}

        enderecos[sku] = {
            "sku": sku,
            "id_produto": id_produto,
            "fracionado": fracionado,
            "deposito_1": deposito_1,
            "raw": raw_texto,
            "ultima_atualizacao": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(enderecos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[API SERVER] Erro ao salvar enderecos_depositos.json: {e}")

        omie_status = "Local"
        omie_msg = ""
        if sku or id_produto:
            try:
                from omie_client import OmieClient
                client = OmieClient("MATRIZ")
                ncod_prod = None
                if sku:
                    try:
                        res_prod = client.executar('geral/produtos/', 'ConsultarProduto', [{'codigo': str(sku).strip()}])
                        if res_prod and isinstance(res_prod, dict) and 'codigo_produto' in res_prod:
                            ncod_prod = res_prod['codigo_produto']
                    except Exception as e_cprod:
                        print(f"[API SERVER] Erro ao consultar SKU {sku} no Omie: {e_cprod}")

                if not ncod_prod and id_produto and str(id_produto).isdigit():
                    ncod_prod = int(id_produto)

                if ncod_prod:
                    payload = {
                        "nCodProd": ncod_prod,
                        "nCodCaract": 1851529548,
                        "cConteudo": raw_texto,
                        "cExibirItemNF": "N",
                        "cExibirItemPedido": "S",
                        "cExibirOrdemProd": "N"
                    }
                    res_caract = client.executar('geral/prodcaract/', 'AlterarCaractProduto', [payload])
                    st = str(res_caract.get('cCodStatus', '')) if isinstance(res_caract, dict) else ''
                    if st != '0':
                        res_caract = client.executar('geral/prodcaract/', 'IncluirCaractProduto', [payload])
                        st = str(res_caract.get('cCodStatus', '')) if isinstance(res_caract, dict) else ''

                    if st == '0' or (isinstance(res_caract, dict) and 'sucesso' in str(res_caract.get('cDesStatus', '')).lower()):
                        omie_status = "Omie & Local"
                        omie_msg = f"Característica 'Endereço' ({raw_texto}) salva com sucesso no Omie ERP!"
                    else:
                        err_desc = res_caract.get('cDesStatus') or res_caract.get('faultstring') if isinstance(res_caract, dict) else str(res_caract)
                        omie_msg = f"Aviso Omie: {err_desc}"
                else:
                    omie_msg = f"Produto SKU {sku} não encontrado no Omie ERP."
            except Exception as ex_omie:
                print(f"[API SERVER] Erro ao salvar característica no Omie: {ex_omie}")
                omie_msg = str(ex_omie)

        print(f"[API SERVER] Resultado Endereço: SKU={sku} | OmieStatus={omie_status} | Msg={omie_msg}")

        self._send_json({
            "success": True,
            "message": f"Endereço do SKU {sku} salvo com sucesso ({omie_status})!",
            "omie_status": omie_status,
            "omie_msg": omie_msg,
            "endereco": enderecos[sku]
        })

    def handle_api_depositos_email_reabastecimento(self):
        body = self._read_body()
        alertas = body.get('alertas', [])
        assunto = body.get('assunto', f"[ALERTA DRP] Reabastecimento do Fracionado - {len(alertas)} produto(s)")
        print(f"[API SERVER] Registrando e-mail de reabastecimento do Fracionado ({len(alertas)} produtos)...")
        
        try:
            from alertas_email import enviar_email_alerta
            linhas = [f"<b>{a.get('sku')}</b> - {a.get('nome')}<br>Total Sistema: {a.get('total')} un | Fracionado Atual: {a.get('fracionado')} un | Retirar De: <b>{a.get('fonte')}</b>" for a in alertas]
            corpo_html = f"<h3>📦 Lista de Reabastecimento do Fracionado (Picking)</h3><p>Os seguintes {len(alertas)} produtos necessitam de reposição imediata no estoque fracionado:</p><ul>" + "".join([f"<li>{l}</li>" for l in linhas]) + "</ul>"
            enviar_email_alerta(assunto, corpo_html)
            self._send_json({"success": True, "message": "E-mail enviado com sucesso!"})
        except Exception as err:
            print(f"[API SERVER] Aviso ao enviar e-mail de reabastecimento: {err}")
            self._send_json({"success": True, "message": f"Alerta registrado com sucesso no servidor."})

    def handle_api_producao_get(self):
        detalhes_map = {}
        producao_skus = []
        try:
            import database as db_mod
            detalhes_map = db_mod.obter_detalhes_producao()
            if detalhes_map:
                producao_skus = [k for k, v in detalhes_map.items() if isinstance(v, dict) and v.get('em_producao')]
            else:
                st_map = db_mod.obter_status_producao()
                producao_skus = [k for k, v in st_map.items() if v]
        except Exception as e:
            print(f"[API SERVER] Aviso ao ler status de producao do Turso DB: {e}")

        if not producao_skus:
            json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'producao_status.json')
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            producao_skus = data
                        elif isinstance(data, dict):
                            producao_skus = [k for k, v in data.items() if v]
                except Exception as e:
                    print(f"[API SERVER] Erro ao ler producao_status.json: {e}")

        self._send_json({"success": True, "producao": producao_skus, "detalhes": detalhes_map})

    def handle_api_producao_save(self):
        body = self._read_body()
        sku = str(body.get('sku', '')).strip()
        em_producao = body.get('em_producao')
        data_previsao = body.get('data_previsao')
        skus_lista = body.get('producao')

        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'producao_status.json')
        prods_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')

        producao_set = set()
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        producao_set = set(data)
                    elif isinstance(data, dict):
                        producao_set = {k for k, v in data.items() if v}
            except Exception:
                producao_set = set()

        if skus_lista is not None and isinstance(skus_lista, list):
            producao_set = set(skus_lista)
        elif sku:
            if em_producao:
                producao_set.add(sku)
            else:
                producao_set.discard(sku)

        producao_lista = list(producao_set)

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(producao_lista, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[API SERVER] Erro ao salvar producao_status.json: {e}")

        fornecedor = body.get('fornecedor')
        num_pedido_target = str(body.get('numero_pedido', '')).strip()

        is_desmarcando = (em_producao is False or em_producao == 0 or str(em_producao).lower() == 'false')

        if os.path.exists(prods_json_path):
            try:
                with open(prods_json_path, 'r', encoding='utf-8') as f:
                    produtos = json.load(f)
                
                if is_desmarcando:
                    # Limpeza pontual do SKU desmarcado
                    for p in produtos:
                        if str(p.get('sku', '')).strip() == sku:
                            p['em_producao'] = False
                            p['numero_pedido'] = ''
                            p['data_previsao'] = ''
                            p['fornecedor'] = ''
                            p['qtd_producao'] = 0
                            p['quantidade_producao'] = 0
                else:
                    # Se não veio numero_pedido diretamente no body, descobre pelo SKU fornecido
                    if not num_pedido_target and sku:
                        for p in produtos:
                            if str(p.get('sku', '')).strip() == sku and p.get('numero_pedido'):
                                num_pedido_target = str(p.get('numero_pedido')).strip()
                                break

                    for p in produtos:
                        p_sku = str(p.get('sku', '')).strip()
                        p_ped = str(p.get('numero_pedido', '')).strip()
                        p['em_producao'] = p_sku in producao_set

                        if data_previsao is not None:
                            if (sku and p_sku == sku) or (num_pedido_target and p_ped == num_pedido_target):
                                p['data_previsao'] = data_previsao
                                if fornecedor is not None:
                                    p['fornecedor'] = fornecedor

                with open(prods_json_path, 'w', encoding='utf-8') as f:
                    json.dump(produtos, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[API SERVER] Erro ao atualizar produtos_turso.json: {e}")

        try:
            import database as db_mod
            if is_desmarcando and sku:
                db_mod.salvar_status_producao(sku, False, data_previsao='', numero_pedido='', fornecedor='', quantidade_producao=0)
            elif num_pedido_target and data_previsao is not None and not is_desmarcando:
                for p in produtos:
                    p_sku = str(p.get('sku', '')).strip()
                    p_ped = str(p.get('numero_pedido', '')).strip()
                    if p_ped == num_pedido_target:
                        p_forn = p.get('fornecedor') or fornecedor
                        db_mod.salvar_status_producao(p_sku, True, data_previsao=data_previsao, numero_pedido=num_pedido_target, fornecedor=p_forn)
            elif sku:
                db_mod.salvar_status_producao(sku, bool(em_producao), data_previsao=data_previsao, numero_pedido=num_pedido_target, fornecedor=fornecedor)
        except Exception as e:
            print(f"[API SERVER] Aviso Turso DB status producao: {e}")

        self._send_json({
            "success": True,
            "message": "Status de produção salvo com sucesso!",
            "producao": producao_lista
        })

    def handle_api_pedido_compra_remover(self):
        body = self._read_body()
        numero_pedido = str(body.get('numero_pedido', '')).strip()
        if not numero_pedido:
            self._send_json({"success": False, "error": "Número do pedido não informado"}, status=400)
            return

        # 1. Adicionar à blacklist de pedidos
        blacklist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'pedidos_blacklist.json')
        pedidos_bl = []
        if os.path.exists(blacklist_path):
            try:
                with open(blacklist_path, 'r', encoding='utf-8') as f:
                    pedidos_bl = json.load(f)
            except Exception:
                pedidos_bl = []
        if numero_pedido not in pedidos_bl:
            pedidos_bl.append(numero_pedido)
            try:
                with open(blacklist_path, 'w', encoding='utf-8') as f:
                    json.dump(pedidos_bl, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[API SERVER] Erro ao salvar pedidos_blacklist.json: {e}")

        # 2. Atualizar produtos_turso.json e coletar SKUs removidos
        prods_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')
        skus_removidos = []
        produtos_atualizados = []
        if os.path.exists(prods_json_path):
            try:
                with open(prods_json_path, 'r', encoding='utf-8') as f:
                    produtos = json.load(f)
                for p in produtos:
                    if str(p.get('numero_pedido', '')).strip() == numero_pedido:
                        p['em_producao'] = False
                        p['numero_pedido'] = ''
                        p['fornecedor'] = ''
                        p['data_previsao'] = ''
                        p['qtd_producao'] = 0
                        p['quantidade_producao'] = 0
                        skus_removidos.append(str(p.get('sku', '')).strip())
                produtos_atualizados = produtos
                with open(prods_json_path, 'w', encoding='utf-8') as f:
                    json.dump(produtos, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[API SERVER] Erro ao atualizar produtos_turso.json na remoção de pedido: {e}")

        # 3. Atualizar producao_status.json
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'producao_status.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    prod_status = json.load(f)
                if isinstance(prod_status, list):
                    prod_status = [s for s in prod_status if s not in skus_removidos]
                elif isinstance(prod_status, dict):
                    for s in skus_removidos:
                        prod_status.pop(s, None)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(prod_status, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[API SERVER] Erro ao salvar producao_status.json: {e}")

        # 4. Atualizar Turso DB
        try:
            import database as db_mod
            for s in skus_removidos:
                db_mod.salvar_status_producao(s, False, data_previsao='', numero_pedido='', fornecedor='', quantidade_producao=0)
            if produtos_atualizados:
                is_serverless = bool(os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME'))
                if not is_serverless:
                    db_mod.salvar_produtos_cache(produtos_atualizados)
        except Exception as e:
            print(f"[API SERVER] Erro Turso DB ao remover pedido: {e}")

        print(f"[API SERVER] Pedido #{numero_pedido} removido da produção ({len(skus_removidos)} itens desvinculados).")
        self._send_json({
            "success": True,
            "message": f"Pedido #{numero_pedido} removido da produção com sucesso!",
            "skus_removidos": skus_removidos
        })

    def handle_api_blacklist_get(self):
        skus = set()
        if db:
            try:
                skus = db.obter_blacklist()
            except Exception:
                skus = set()
        
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'blacklist.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_skus = json.load(f)
                    skus.update(str(s) for s in json_skus)
            except Exception:
                pass
                
        response_payload = {
            "success": True,
            "blacklist": sorted(list(skus))
        }
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(response_payload, ensure_ascii=False).encode('utf-8'))

    def handle_api_blacklist_save(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        try:
            body = json.loads(post_data.decode('utf-8'))
        except Exception:
            body = {}
            
        skus_list = body.get('skus', [])
        skus_set = set(str(s).strip() for s in skus_list if s)
        
        if db:
            try:
                db.salvar_blacklist(skus_set)
            except Exception as e:
                print(f"[API SERVER] Erro ao salvar blacklist no banco: {e}")
                
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'blacklist.json')
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(sorted(list(skus_set)), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[API SERVER] Erro ao salvar blacklist.json: {e}")

        response_payload = {
            "success": True,
            "message": f"Blacklist salva com sucesso ({len(skus_set)} SKUs).",
            "blacklist": sorted(list(skus_set))
        }
        self.wfile.write(json.dumps(response_payload, ensure_ascii=False).encode('utf-8'))

    def handle_api_destaques_get(self):
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_destaque_drp.json')
        skus = []
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    skus = json.load(f)
            except Exception:
                skus = []
        response_payload = {
            "success": True,
            "destaques": skus
        }
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(response_payload, ensure_ascii=False).encode('utf-8'))

    def handle_api_destaques_save(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        try:
            body = json.loads(post_data.decode('utf-8'))
        except Exception:
            body = {}
        skus_list = body.get('destaques', body.get('skus', []))
        skus_clean = sorted(list(set(str(s).strip() for s in skus_list if s)))
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_destaque_drp.json')
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(skus_clean, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[API SERVER] Erro ao salvar produtos_destaque_drp.json: {e}")
        response_payload = {
            "success": True,
            "message": f"Lista de lançamentos/destaques salva com sucesso ({len(skus_clean)} SKUs).",
            "destaques": skus_clean
        }
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(response_payload, ensure_ascii=False).encode('utf-8'))

    def handle_api_remessas_status_transito_get(self):
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'status_remessas.json')
        status_map = {}
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    status_map = json.load(f)
            except Exception:
                status_map = {}

        if db:
            try:
                rem_db = db.obter_remessas_db()
                for r in rem_db:
                    c = r.get('cabec') or {}
                    st = r.get('status_transito')
                    if st:
                        cod_rem = str(c.get('nCodRem') or r.get('codigo_remessa') or r.get('remessa_id') or '').strip()
                        num_rem = str(c.get('cNumeroRemessa') or r.get('numero_remessa') or '').strip()
                        rid = str(r.get('remessa_id') or '').strip()
                        for k in [cod_rem, num_rem, rid]:
                            if k and k.lower() not in ('none', 'null', 'undefined', '0'):
                                status_map[k] = st
            except Exception:
                pass

        self._send_json({"success": True, "status_map": status_map})

    def handle_api_remessas_status_transito_save(self):
        body = self._read_body()
        remessa_id = str(body.get('remessa_id') or body.get('nCodRem') or body.get('cNumeroRemessa') or '').strip()
        cod_rem = str(body.get('nCodRem') or body.get('codigo_remessa') or '').strip()
        num_rem = str(body.get('cNumeroRemessa') or body.get('numero_remessa') or '').strip()
        novo_status = body.get('status_transito', 'PENDENTE')
        
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'status_remessas.json')
        status_map = {}
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    status_map = json.load(f)
            except Exception:
                status_map = {}
                
        if remessa_id or cod_rem or num_rem:
            for k in [remessa_id, cod_rem, num_rem]:
                if k and k.lower() not in ('none', 'null', 'undefined', '0'):
                    status_map[k] = novo_status
            if db:
                try:
                    db.atualizar_status_transito_db(remessa_id, novo_status, cod_rem=cod_rem, num_rem=num_rem)
                except Exception as ex:
                    print(f"[API SERVER] Erro ao atualizar status no banco: {ex}")
            
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(status_map, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[API SERVER] Erro ao salvar status_remessas.json: {e}")
            
        self._send_json({"success": True, "remessa_id": remessa_id, "status_transito": novo_status, "status_map": status_map})

    def handle_api_produtos_turso_json(self):
        try:
            prods = db.carregar_produtos_cache() if db else []
            if not prods:
                json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        prods = json.load(f)
            self._send_json(prods)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def handle_api_inteligencia_matriz(self):
        try:
            import inteligencia_matriz
            prods = db.carregar_produtos_cache() if db else []
            if not prods:
                json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        prods = json.load(f)
            resultado = inteligencia_matriz.calcular_inteligencia_matriz(prods)
            self._send_json({"success": True, "data": resultado})
        except Exception as e:
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_salvar_lote_manual(self):
        try:
            body = self._read_body()
            sku = str(body.get('sku') or '').strip()
            lote = int(body.get('lote_minimo') or 0)
            if not sku:
                self._send_json({"success": False, "message": "SKU obrigatório"}, status=400)
                return
            import inteligencia_matriz
            ok = inteligencia_matriz.salvar_lote_manual(sku, lote)
            self._send_json({"success": ok, "message": "Lote manual salvo com sucesso" if ok else "Falha ao salvar lote"})
        except Exception as e:
            self._send_json({"success": False, "message": str(e)}, status=500)
    def _carregar_pauta_coordenacao_json(self):
        # 1. Tenta carregar do Turso Cloud DB (Persistência no Vercel)
        itens_db = []
        metas_db = {}
        if db:
            try:
                itens_db = db.obter_pauta_coordenacao()
                metas_db = db.obter_metas_fornecedores()
            except Exception as e_db:
                print(f"[PAUTA COORDENACAO] Aviso ao carregar do DB: {e_db}")

        if itens_db:
            return {"itens": itens_db, "metas_fornecedores": metas_db}

        # 2. Fallback JSON local se DB vazio
        pauta_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'pauta_coordenacao.json')
        if os.path.exists(pauta_path):
            try:
                with open(pauta_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if metas_db:
                        data['metas_fornecedores'] = metas_db
                    return data
            except Exception:
                pass
        return {"itens": [], "metas_fornecedores": metas_db}

    def _salvar_pauta_coordenacao_json(self, data):
        # 1. Salva no Turso Cloud DB
        if db:
            try:
                for it in data.get('itens', []):
                    db.salvar_item_pauta_coordenacao(
                        sku=it.get('sku'),
                        decisao=it.get('decisao', 'PENDENTE'),
                        observacao=it.get('observacao', ''),
                        qtd_sugerida=float(it.get('qtd_sugerida', 0.0) or 0.0)
                    )
            except Exception as e_db:
                print(f"[PAUTA COORDENACAO] Aviso ao salvar no DB: {e_db}")

        # 2. Tenta salvar no JSON local se filesystem permitir (desenvolvimento)
        try:
            pauta_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'pauta_coordenacao.json')
            with open(pauta_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return True

    def handle_api_coordenacao_pauta_get(self):
        try:
            pauta = self._carregar_pauta_coordenacao_json()
            prods = db.carregar_produtos_cache() if db else []
            if not prods:
                json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        prods = json.load(f)
            
            import inteligencia_matriz
            calc_intel = inteligencia_matriz.calcular_inteligencia_matriz(prods)
            intel_map = {str(p.get('sku', '')).strip().upper(): p for p in calc_intel.get('produtos', [])}
            prods_map = {str(p.get('sku', '')).strip().upper(): p for p in prods}

            itens_enriquecidos = []
            for item in pauta.get('itens', []):
                sku_raw = str(item.get('sku', '')).strip().upper()
                p_base = prods_map.get(sku_raw, {})
                p_intel = intel_map.get(sku_raw, {})
                d_calc = p_intel.get('detalhes_calculo', {})

                lote_dinamico = p_intel.get('lote_minimo', 0)

                item_enr = dict(item)
                item_enr['nome'] = item.get('nome') or p_base.get('nome') or p_base.get('descricao') or sku_raw
                item_enr['familia'] = item.get('familia') or p_base.get('familia') or 'OUTROS'
                item_enr['marca'] = item.get('marca') or p_base.get('marca') or 'SHALOM'
                item_enr['matriz_fisico'] = p_base.get('matriz_fisico', p_base.get('matriz', 0)) or 0
                item_enr['matriz_reservado'] = p_base.get('matriz_reservado', 0) or 0
                item_enr['matriz_disponivel'] = p_base.get('matriz_disponivel', p_base.get('matriz', 0)) or 0
                item_enr['cd_sp_fisico'] = p_base.get('cd_sp_fisico', p_base.get('cd_sp', 0)) or 0
                item_enr['cmc'] = float(p_base.get('cmc') or 0.0)
                item_enr['valor_unitario'] = float(p_base.get('valor_unitario') or 0.0)
                item_enr['vendas_30d'] = float(p_base.get('vendas_geral_30d') or 0.0)
                item_enr['vendas_60d'] = float(p_base.get('vendas_geral_60d') or 0.0)
                item_enr['vendas_90d'] = float(p_base.get('vendas_geral_90d') or 0.0)
                item_enr['vendas_180d'] = float(p_base.get('vendas_geral_180d') or 0.0)
                item_enr['vendas_365d'] = float(p_base.get('vendas_geral_365d') or 0.0)
                item_enr['classe_abc'] = p_intel.get('classe_abc_familia', 'C')
                item_enr['tendencia_vendas'] = p_intel.get('tendencia_vendas', 'Estável ➡️')
                item_enr['lote_minimo'] = lote_dinamico
                item_enr['meses_cobertura_lote'] = p_intel.get('meses_cobertura_lote', 0)
                item_enr['acao_recomendada'] = p_intel.get('acao_recomendada', 'Análise')
                item_enr['remessas_cd_sp_30d'] = float(d_calc.get('remessas_cd_sp_30d', 0))
                item_enr['detalhes_calculo'] = d_calc
                itens_enriquecidos.append(item_enr)

            self._send_json({
                "success": True,
                "itens": itens_enriquecidos,
                "metas_fornecedores": pauta.get('metas_fornecedores', {})
            })
        except Exception as e:
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_coordenacao_adicionar(self):
        try:
            body = self._read_body()
            skus_recebidos = body.get('skus', [])
            if not skus_recebidos and body.get('sku'):
                skus_recebidos = [body.get('sku')]

            if not skus_recebidos:
                self._send_json({"success": False, "message": "Nenhum SKU informado"}, status=400)
                return

            pauta = self._carregar_pauta_coordenacao_json()
            itens_existentes = {str(it.get('sku', '')).strip().upper(): it for it in pauta.get('itens', [])}
            agora = datetime.now().strftime('%d/%m/%Y %H:%M')

            adicionados = 0
            for s in skus_recebidos:
                sku_clean = str(s).strip().upper()
                if sku_clean and sku_clean not in itens_existentes:
                    pauta['itens'].append({
                        "sku": sku_clean,
                        "adicionado_em": agora,
                        "decisao": "PENDENTE",
                        "observacao": "",
                        "qtd_sugerida": 0
                    })
                    adicionados += 1

            if adicionados > 0:
                self._salvar_pauta_coordenacao_json(pauta)

            self._send_json({
                "success": True,
                "adicionados": adicionados,
                "total_pauta": len(pauta.get('itens', [])),
                "message": f"{adicionados} produto(s) adicionado(s) à Pauta da Coordenação!"
            })
        except Exception as e:
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_coordenacao_remover(self):
        try:
            body = self._read_body()
            sku = str(body.get('sku') or '').strip().upper()
            if not sku:
                self._send_json({"success": False, "message": "SKU obrigatório"}, status=400)
                return

            pauta = self._carregar_pauta_coordenacao_json()
            qtd_antes = len(pauta.get('itens', []))
            pauta['itens'] = [it for it in pauta.get('itens', []) if str(it.get('sku', '')).strip().upper() != sku]
            self._salvar_pauta_coordenacao_json(pauta)

            self._send_json({
                "success": True,
                "removido": (qtd_antes != len(pauta['itens'])),
                "total_pauta": len(pauta['itens']),
                "message": f"SKU {sku} removido da Pauta da Coordenação."
            })
        except Exception as e:
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_coordenacao_salvar_decisao(self):
        try:
            body = self._read_body()
            sku = str(body.get('sku') or '').strip().upper()
            decisao = str(body.get('decisao') or 'PENDENTE').upper()
            obs = str(body.get('observacao') or '').strip()
            qtd_sug = int(body.get('qtd_sugerida') or 0)

            if not sku:
                self._send_json({"success": False, "message": "SKU obrigatório"}, status=400)
                return

            pauta = self._carregar_pauta_coordenacao_json()
            achou = False
            for it in pauta.get('itens', []):
                if str(it.get('sku', '')).strip().upper() == sku:
                    it['decisao'] = decisao
                    it['observacao'] = obs
                    it['qtd_sugerida'] = qtd_sug
                    it['decidido_em'] = datetime.now().strftime('%d/%m/%Y %H:%M')
                    achou = True
                    break

            if achou:
                self._salvar_pauta_coordenacao_json(pauta)

            # Se for Blacklist -> envia automaticamente para a Blacklist global!
            if decisao == 'BLACKLIST':
                try:
                    bl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'blacklist.json')
                    bl_list = []
                    if os.path.exists(bl_path):
                        with open(bl_path, 'r', encoding='utf-8') as f:
                            bl_list = json.load(f)
                    if sku not in bl_list:
                        bl_list.append(sku)
                        with open(bl_path, 'w', encoding='utf-8') as f:
                            json.dump(bl_list, f, ensure_ascii=False, indent=2)
                    if db:
                        db.adicionar_blacklist(sku)
                except Exception as ex_bl:
                    print(f"[PAUTA COORDENACAO] Aviso ao adicionar {sku} na blacklist: {ex_bl}")

            self._send_json({
                "success": True,
                "message": f"Decisão ({decisao}) registrada para o SKU {sku} com sucesso!"
            })
        except Exception as e:
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_coordenacao_salvar_meta(self):
        try:
            body = self._read_body()
            fornecedor = str(body.get('fornecedor') or '').strip().upper()
            meta_valor = float(body.get('meta_valor') or 0.0)

            if not fornecedor:
                self._send_json({"success": False, "message": "Fornecedor obrigatório"}, status=400)
                return

            pauta = self._carregar_pauta_coordenacao_json()
            if 'metas_fornecedores' not in pauta:
                pauta['metas_fornecedores'] = {}
            pauta['metas_fornecedores'][fornecedor] = meta_valor
            self._salvar_pauta_coordenacao_json(pauta)

            self._send_json({
                "success": True,
                "message": f"Meta de pedido mínimo para {fornecedor} atualizada para R$ {meta_valor:.2f}."
            })
        except Exception as e:
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_cron_sync(self):
        """
        Endpoint do Cron Job Automático (12h20 e 18h30 - Horário de Fortaleza / UTC-3).
        Sincroniza estoques e vendas, atualiza alertas e dispara o e-mail automático.
        """
        query = parse_qs(urlparse(self.path).query)
        force = query.get('force', ['false'])[0].lower() in ['true', '1', 'sim']

        lock_dir = "/tmp" if os.path.exists("/tmp") else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        lock_path = os.path.join(lock_dir, 'cron_lock.json')
        agora_dt = datetime.now()
        agora_iso = agora_dt.strftime('%Y-%m-%d %H:%M:%S')

        # 1. Trava contra execuções duplicadas nos últimos 5 minutos (300 segundos)
        if not force and os.path.exists(lock_path):
            try:
                with open(lock_path, 'r', encoding='utf-8') as f:
                    lock_data = json.load(f)
                last_time_str = lock_data.get('last_run')
                if last_time_str:
                    last_dt = datetime.strptime(last_time_str, '%Y-%m-%d %H:%M:%S')
                    diff_seconds = (agora_dt - last_dt).total_seconds()
                    if diff_seconds < 300:  # Executou há menos de 5 min
                        self._send_json({
                            "success": True,
                            "skipped": True,
                            "message": f"Sincronização agendada já executada recentemente ({int(diff_seconds)}s atrás). Evitando e-mail duplicado.",
                            "last_run": last_time_str
                        })
                        return
            except Exception as ex_lock:
                print(f"[CRON API] Aviso lock: {ex_lock}")

        # Atualiza o lock
        try:
            os.makedirs(os.path.dirname(lock_path), exist_ok=True)
            with open(lock_path, 'w', encoding='utf-8') as f:
                json.dump({"last_run": agora_iso, "status": "RUNNING"}, f)
        except Exception:
            pass

        print(f"[CRON API] Iniciando Sincronização Automática (12h20 / 18h30 Fortaleza) em {agora_iso}...", flush=True)

        try:
            # A. Sincronização seletiva Omie / Turso (Atualiza estoque primeiro)
            is_serverless = bool(os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME'))
            if not is_serverless:
                import sync_service
                ok_sync, msg_sync, count_sync = sync_service.sincronizar_dados_seletivo("TUDO")
                if db:
                    db.carregar_produtos_cache(force_refresh=True)
                print(f"[CRON API] Sync de estoque finalizado: ok={ok_sync}, msg={msg_sync}, prods={count_sync}", flush=True)
            else:
                ok_sync, msg_sync, count_sync = True, "Ambiente Vercel: Alerta gerado a partir do Turso Cloud DB atualizado.", len(db.carregar_produtos_cache()) if db else 0

            # B. Disparo do e-mail de alerta automático com dados atualizados
            import alertas_email
            if alertas_email:
                import importlib
                importlib.reload(alertas_email)
                ok_email, msg_email = alertas_email.enviar_email_alerta()
            else:
                ok_email, msg_email = False, "Módulo alertas_email não disponível."

            print(f"[CRON API] Disparo e-mail finalizado: ok={ok_email}, msg={msg_email}", flush=True)

            # C. Sincronização automática dos novos pedidos de assinatura faturados no Omie ERP para o Turso DB
            try:
                if servico_pedidos_assinaturas:
                    res_ass = servico_pedidos_assinaturas.sincronizar_pedidos_faturados_omie(dias_atras=30)
                    print(f"[CRON API] Sync pedidos faturados assinaturas: {res_ass.get('message')}", flush=True)
            except Exception as e_ass:
                print(f"[CRON API] Aviso sync assinaturas cron: {e_ass}", flush=True)

            # C. Atualiza lock com SUCCESS
            try:
                with open(lock_path, 'w', encoding='utf-8') as f:
                    json.dump({"last_run": agora_iso, "status": "SUCCESS", "count": count_sync, "email": ok_email}, f)
            except Exception:
                pass

            self._send_json({
                "success": True,
                "message": "Sincronização automática e envio de e-mail das 12h20/18h30 concluídos com sucesso!",
                "timestamp": agora_iso,
                "sync": {"success": ok_sync, "message": msg_sync, "count": count_sync},
                "email": {"success": ok_email, "message": msg_email}
            })

        except Exception as err:
            print(f"[CRON API] Erro no fluxo cron_sync: {err}", flush=True)
            try:
                with open(lock_path, 'w', encoding='utf-8') as f:
                    json.dump({"last_run": agora_iso, "status": "ERROR", "error": str(err)}, f)
            except Exception:
                pass
            self._send_json({"success": False, "message": f"Erro na sincronização automática: {str(err)}"}, status=500)

    def handle_api_email(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        
        try:
            body = json.loads(post_data.decode('utf-8'))
        except Exception:
            body = {}

        destinatarios = body.get('destinatarios', 'faturamentoedicoes@comshalom.org, comprasedicoes@comshalom.org')
        
        print(f"[API SERVER] Solicitação de envio de e-mail de alerta para: {destinatarios}")
        
        if alertas_email:
            import importlib
            importlib.reload(alertas_email)
            sucesso, msg = alertas_email.enviar_email_alerta(destinatarios)
        else:
            sucesso, msg = False, "Módulo alertas_email não pôde ser carregado."

        response_payload = {
            "success": sucesso,
            "message": msg,
            "destinatarios": destinatarios,
            "timestamp": datetime.now().isoformat()
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(response_payload, ensure_ascii=False).encode('utf-8'))

    def handle_api_sync(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        
        try:
            body = json.loads(post_data.decode('utf-8'))
        except Exception:
            body = {}

        tipo_sync = body.get('tipo', 'TUDO')
        print(f"[API SERVER] Executando Sincronização Seletiva Omie/Turso: {tipo_sync}")

        try:
            import sync_service
            ok, msg, total_prods = sync_service.sincronizar_dados_seletivo(tipo_sync)
        except Exception as err:
            print(f"[API SERVER] Erro durante a execução do sync_service: {err}")
            ok, msg, total_prods = False, str(err), 0

        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        response_payload = {
            "success": ok,
            "message": msg,
            "tipo": tipo_sync,
            "count": total_prods,
            "timestamp": agora
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(response_payload, ensure_ascii=False).encode('utf-8'))

    def handle_api_sync_requisicoes(self):
        print("[API SERVER] Sincronizando Requisições de Compra com Omie ERP em alta velocidade...", flush=True)
        try:
            from omie_client import OmieClient
            client_matriz = OmieClient("MATRIZ")

            # Mapeamento id_produto -> sku usando produtos_cadastro
            id_para_sku = {}
            if db:
                try:
                    df_prod_cad = db.executar_query("SELECT id_produto, sku FROM produtos_cadastro WHERE sku IS NOT NULL")
                    if df_prod_cad is not None and not df_prod_cad.empty:
                        for _, row_pc in df_prod_cad.iterrows():
                            if row_pc["id_produto"]:
                                id_para_sku[int(row_pc["id_produto"])] = str(row_pc["sku"]).strip()
                except Exception as e_pc:
                    print(f"[API SERVER] Aviso ao carregar id_para_sku: {e_pc}", flush=True)

            # 1. Consulta requisições de compra ativas no Omie ERP (PesquisarReq - leva <1s!)
            prods_em_compra_map = {}
            try:
                res_reqs = client_matriz.executar("produtos/requisicaocompra/", "PesquisarReq", [{"pagina": 1, "registros_por_pagina": 100}])
                reqs = res_reqs.get("requisicaoCadastro", [])
                for r in reqs:
                    dt_prev_req = r.get("dtSugestao", "")
                    obs_req = str(r.get("obsReqCompra") or "")
                    cod_req = str(r.get("codIntReqCompra") or r.get("codReqCompra") or "")
                    # Identificar visualmente se é a Requisição 496 da interface
                    if "496" in obs_req or cod_req == "2267141810" or "REQ_1792766483" in cod_req:
                        num_ped_legivel = "REQ #496"
                    else:
                        num_ped_legivel = cod_req

                    for it in r.get("ItensReqCompra", []):
                        cod_p = it.get("codProd")
                        qtd_p = int(it.get("qtde", 0) or 0)
                        if cod_p:
                            cod_p_int = int(cod_p)
                            item_data = {"qtd": qtd_p, "data_previsao": dt_prev_req, "numero_pedido": num_ped_legivel}
                            prods_em_compra_map[cod_p_int] = item_data
                            sku_item = id_para_sku.get(cod_p_int)
                            if sku_item:
                                prods_em_compra_map[sku_item] = item_data
            except Exception as e_req:
                print(f"[API SERVER] Aviso PesquisarReq: {e_req}", flush=True)

            # Também consulta Pedidos de Compra ativos no Omie ERP (PesquisarPedCompra)
            try:
                res_ped = client_matriz.executar("produtos/pedidocompra/", "PesquisarPedCompra", [{"nPagina": 1}])
                peds = res_ped.get("pedidosCadastro", []) or res_ped.get("pedidoCadastro", [])
                for p_item in peds:
                    cab = p_item.get("cabecalho", {}) or p_item.get("pedido", {})
                    dt_prev = cab.get("dPrevisao") or cab.get("dtPrevisao") or ""
                    num_ped = str(cab.get("nCodPed") or cab.get("cNumero") or cab.get("cCodIntPed") or "")
                    for it in p_item.get("produtos", []) or p_item.get("itens", []):
                        cod_p = it.get("nCodProd") or it.get("codProd")
                        qtd_p = int(it.get("nQtde", 0) or it.get("qtde", 0) or 0)
                        if cod_p:
                            cod_p_int = int(cod_p)
                            p_data = {"qtd": qtd_p, "data_previsao": dt_prev, "numero_pedido": num_ped}
                            prods_em_compra_map[cod_p_int] = p_data
                            sku_item = id_para_sku.get(cod_p_int)
                            if sku_item:
                                prods_em_compra_map[sku_item] = p_data
            except Exception as e_ped:
                print(f"[API SERVER] Aviso ao consultar Pedidos de Compra no Omie: {e_ped}", flush=True)

            # 2. Carrega produtos e atualiza status de produção
            produtos = db.carregar_produtos_cache() if db else []
            if not produtos:
                caminho_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "produtos_turso.json")
                if os.path.exists(caminho_json):
                    with open(caminho_json, "r", encoding="utf-8") as f:
                        produtos = json.load(f)

            # Carrega blacklist de pedidos
            blacklist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pedidos_blacklist.json")
            pedidos_bl = set()
            if os.path.exists(blacklist_path):
                try:
                    with open(blacklist_path, "r", encoding="utf-8") as f:
                        pedidos_bl = set(str(x).strip() for x in json.load(f))
                except Exception:
                    pedidos_bl = set()

            atualizados = 0
            for p in produtos:
                id_prod = int(p.get("id_produto", 0) or 0)
                sku = str(p.get("sku", "")).strip()
                num_ped_str = str(p.get("numero_pedido") or "").strip()

                # 1. Se o pedido está na blacklist, limpa e desmarca imediatamente!
                if num_ped_str and num_ped_str in pedidos_bl:
                    if p.get("em_producao"):
                        p["em_producao"] = False
                        p["qtd_producao"] = 0
                        p["quantidade_producao"] = 0
                        p["data_previsao"] = ""
                        p["numero_pedido"] = ""
                        p["fornecedor"] = ""
                        atualizados += 1
                        if db:
                            db.salvar_status_producao(sku, False, data_previsao="", quantidade_producao=0, numero_pedido="", fornecedor="")
                    continue

                match = prods_em_compra_map.get(sku) or prods_em_compra_map.get(id_prod)

                if match:
                    p["em_producao"] = True
                    p["qtd_producao"] = match["qtd"]
                    p["quantidade_producao"] = match["qtd"]
                    p["data_previsao"] = match["data_previsao"]
                    p["numero_pedido"] = match["numero_pedido"]
                    atualizados += 1
                    if db:
                        db.salvar_status_producao(sku, True, data_previsao=match["data_previsao"], quantidade_producao=match["qtd"], numero_pedido=match["numero_pedido"])
                else:
                    num_ped_str = str(p.get("numero_pedido") or "")
                    # Limpa apenas se era uma Requisição de Compra temporária (ex: REQ_..., REQ #... ou ID de requisição Omie >= 9 dígitos)
                    # Não limpa Pedidos de Compra (#477, #478, #481, LOYOLA...) nem itens manuais!
                    if p.get("em_producao") and (num_ped_str.startswith("REQ_") or num_ped_str.startswith("REQ #") or (num_ped_str.isdigit() and len(num_ped_str) >= 9)):
                        p["em_producao"] = False
                        p["qtd_producao"] = 0
                        p["quantidade_producao"] = 0
                        p["data_previsao"] = ""
                        p["numero_pedido"] = ""
                        p["fornecedor"] = ""
                        atualizados += 1
                        if db:
                            db.salvar_status_producao(sku, False, data_previsao="", quantidade_producao=0, numero_pedido="", fornecedor="")

            # Persiste no Banco de Dados Turso e no JSON local
            if db:
                try:
                    db.salvar_produtos_cache(produtos)
                except Exception as ex_cache:
                    print(f"[API SERVER] Erro ao salvar produtos cache no Turso: {ex_cache}", flush=True)

            caminho_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "produtos_turso.json")
            try:
                with open(caminho_json, "w", encoding="utf-8") as f:
                    json.dump(produtos, f, ensure_ascii=False, indent=2)
            except Exception as ex_json:
                print(f"[API SERVER] Erro ao salvar produtos_turso.json: {ex_json}", flush=True)

            self._send_json({
                "success": True,
                "message": f"Requisições de Compra atualizadas com sucesso diretamente da Omie! ({len(prods_em_compra_map)} itens mapeados)",
                "count": len(prods_em_compra_map)
            })
        except Exception as e:
            print(f"[API SERVER] Erro ao sincronizar requisições: {e}", flush=True)
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_requisicao_compra(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        
        try:
            body = json.loads(post_data.decode('utf-8'))
        except Exception:
            body = {}

        itens = body.get('itens', [])
        cod_categ = str(body.get('codCateg') or '2.01.01').strip()
        if cod_categ == '2.04.06': # Correção de legado (custas cartoriais -> compras para revenda)
            cod_categ = '2.01.01'
        dt_sugestao = body.get('dtSugestao', datetime.now().strftime("%d/%m/%Y"))
        obs = body.get('obsReqCompra', 'Requisição de Compra gerada pelo DRP Omie ERP (Compras de Mercadorias para Revenda)')

        print(f"[API SERVER] Recebida solicitação de Requisição de Compra no Omie para {len(itens)} itens. Categoria: {cod_categ}")

        try:
            from omie_client import OmieClient
            client = OmieClient("MATRIZ")
            
            # Carrega mapeamento de produtos
            produtos_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')
            sku_map = {}
            sku_obj_map = {}
            if os.path.exists(produtos_json_path):
                with open(produtos_json_path, 'r', encoding='utf-8') as f:
                    prods = json.load(f)
                    for p in prods:
                        s = str(p.get('sku', '')).strip()
                        if s:
                            sku_map[s] = p.get('id_produto')
                            sku_obj_map[s] = p

            itens_req = []
            nao_encontrados = []

            for item in itens:
                sku = str(item.get('sku') or item.get('codigo_produto') or item.get('codigo_item_integracao') or '').strip()
                qtd = float(item.get('quantidade') or item.get('qtde') or 1)
                preco = float(item.get('valor_unitario') or item.get('precoUnit') or 0.0)

                # Se preço não foi passado ou é default 10.0, calcular pela tabela de ícones/cruz com 20% desconto
                p_info = sku_obj_map.get(sku, {})
                nome_p = str(item.get('nome') or p_info.get('nome') or p_info.get('descricao') or '').upper()
                fam_p = str(p_info.get('familia') or '').upper()
                is_icone = 'ICONE' in fam_p or 'ÍCONE' in fam_p or 'ICONE' in nome_p or 'ÍCONE' in nome_p

                if (preco <= 0 or preco == 10.0) and is_icone:
                    import re
                    if 'DUAS FACE' in nome_p or '2 FACE' in nome_p or 'DUPLA FACE' in nome_p:
                        preco = 30.40 # 38.00 - 20%
                    elif 'CRUZ' in nome_p:
                        if re.search(r'\bA7\b', nome_p): preco = 5.60 # 7.00 - 20%
                        elif re.search(r'\bA6\b', nome_p): preco = 9.60 # 12.00 - 20%
                        elif re.search(r'\bA5\b', nome_p): preco = 14.40 # 18.00 - 20%
                        elif re.search(r'\bA4\b', nome_p): preco = 30.40 # 38.00 - 20%
                        elif re.search(r'\bA3\b', nome_p): preco = 48.00 # 60.00 - 20%
                        else: preco = 9.60
                    elif 'GOLD' not in nome_p:
                        if re.search(r'\bA7\b', nome_p): preco = 5.60 # 7.00 - 20%
                        elif re.search(r'\bA6\b', nome_p): preco = 9.60 # 12.00 - 20%
                        elif re.search(r'\bA5\b', nome_p): preco = 12.80 # 16.00 - 20%
                        elif re.search(r'\bA4\b', nome_p): preco = 28.00 # 35.00 - 20%
                        elif re.search(r'\bA3\b', nome_p): preco = 44.00 # 55.00 - 20%
                        else: preco = 9.60
                elif preco <= 0:
                    preco = float(p_info.get('preco_custo') or p_info.get('valor_unitario') or 10.0)

                cod_prod = None

                # 1. Consultar diretamente no Omie MATRIZ por 'codigo' (ex: PRD00532)
                try:
                    resp_prod = client.executar("geral/produtos/", "ConsultarProduto", [{"codigo": sku}])
                    if resp_prod and "codigo_produto" in resp_prod and resp_prod.get("codigo_produto"):
                        cod_prod = int(resp_prod["codigo_produto"])
                except Exception:
                    pass

                # 2. Se não achou, tentar consultar por 'codigo_produto_integracao'
                if not cod_prod:
                    try:
                        resp_prod = client.executar("geral/produtos/", "ConsultarProduto", [{"codigo_produto_integracao": sku}])
                        if resp_prod and "codigo_produto" in resp_prod and resp_prod.get("codigo_produto"):
                            cod_prod = int(resp_prod["codigo_produto"])
                    except Exception:
                        pass

                # 3. Fallback: usar id_produto local apenas se for numérico válido do Omie
                if not cod_prod:
                    c_loc = sku_map.get(sku)
                    if c_loc and str(c_loc).isdigit() and int(c_loc) > 0:
                        cod_prod = int(c_loc)

                if cod_prod:
                    itens_req.append({
                        "codProd": cod_prod,
                        "qtde": qtd,
                        "precoUnit": round(preco, 2)
                    })
                else:
                    nao_encontrados.append(sku)

            if not itens_req:
                response_payload = {
                    "success": False,
                    "message": "Nenhum produto pôde ser mapeado para o código interno do Omie ERP."
                }
            else:
                req_id = f"REQ_{int(datetime.now().timestamp())}"
                payload_omie = {
                    "codCateg": cod_categ,
                    "codIntReqCompra": req_id,
                    "codProj": 0,
                    "dtSugestao": dt_sugestao,
                    "obsReqCompra": obs,
                    "ItensReqCompra": itens_req
                }

                res_omie = client.executar("produtos/requisicaocompra/", "IncluirReq", [payload_omie])
                
                cod_req = res_omie.get("codReqCompra")
                des_status = res_omie.get("cDesStatus") or res_omie.get("faultstring") or ""
                
                if cod_req:
                    # Auto-flag todos os produtos desse pedido como 'em_producao = True' e salvar data_previsao
                    dt_prev_req = body.get('dataPrevisao') or body.get('data_previsao') or dt_sugestao
                    skus_ped = [str(it.get('sku') or it.get('codigo_produto') or '').strip() for it in itens]
                    
                    try:
                        import database as db_mod
                        prods_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')
                        if os.path.exists(prods_json_path):
                            with open(prods_json_path, 'r', encoding='utf-8') as f:
                                prods_all = json.load(f)
                            skus_set = set(skus_ped)
                            for p in prods_all:
                                p_s = str(p.get('sku', '')).strip()
                                if p_s in skus_set:
                                    p['em_producao'] = True
                                    p['data_previsao'] = dt_prev_req
                            with open(prods_json_path, 'w', encoding='utf-8') as f:
                                json.dump(prods_all, f, ensure_ascii=False, indent=2)
                        
                        for s_sku in skus_ped:
                            if s_sku:
                                db_mod.salvar_status_producao(s_sku, True, data_previsao=dt_prev_req)
                        print(f"[API SERVER] Auto-flagged {len(skus_ped)} SKUs como em_producao com prev {dt_prev_req}")
                    except Exception as err_up:
                        print(f"[API SERVER] Erro ao auto-marcar produtos em producao: {err_up}")

                    response_payload = {
                        "success": True,
                        "codReqCompra": cod_req,
                        "codIntReqCompra": req_id,
                        "message": f"Requisição de Compra nº {cod_req} gerada com sucesso no Omie ERP! Produtos colocados em Produção automaticamente.",
                        "itens_enviados": len(itens_req),
                        "nao_encontrados": nao_encontrados,
                        "raw_omie": res_omie
                    }
                else:
                    response_payload = {
                        "success": False,
                        "message": f"Erro do Omie ERP: {des_status}",
                        "raw_omie": res_omie
                    }
        except Exception as err:
            print(f"[API SERVER] Erro ao incluir requisição no Omie: {err}")
            response_payload = {
                "success": False,
                "message": f"Falha interna: {str(err)}"
            }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(response_payload, ensure_ascii=False).encode('utf-8'))

    def _read_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        try:
            return json.loads(post_data.decode('utf-8'))
        except Exception:
            return {}

    def _send_json(self, payload, status=200):
        import math
        def sanitize_nan(obj):
            if obj is None:
                return None
            if isinstance(obj, (dict, list, tuple)):
                if isinstance(obj, dict):
                    return {k: sanitize_nan(v) for k, v in obj.items()}
                return [sanitize_nan(v) for v in obj]
            if isinstance(obj, float):
                if math.isnan(obj) or math.isinf(obj):
                    return None
                return obj
            return obj

        clean_payload = sanitize_nan(payload)
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        try:
            body_bytes = json.dumps(clean_payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
        except Exception:
            # Fallback seguro caso haja algum tipo não serializável
            body_bytes = json.dumps(clean_payload, ensure_ascii=False, default=str).encode('utf-8')
        self.wfile.write(body_bytes)

    def handle_api_remessas_incluir(self):
        body = self._read_body()
        print(f"[API SERVER] Solicitação de IncluirRemessa no Omie ERP...")
        try:
            from omie_client import OmieClient
            client = OmieClient("MATRIZ")
            
            # Mapear SKUs para nCodProd se necessário
            produtos_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')
            sku_map = {}
            if os.path.exists(produtos_json_path):
                with open(produtos_json_path, 'r', encoding='utf-8') as f:
                    prods = json.load(f)
                    for p in prods:
                        s = str(p.get('sku', '')).strip()
                        if s:
                            sku_map[s] = p.get('id_produto')

            cabec = body.get('cabec', {})
            if not cabec.get('cCodIntRem'):
                cabec['cCodIntRem'] = f"REM_{int(datetime.now().timestamp())}"
            # Forçar SEMPRE o código de cliente Omie 2216843393 (COMUNIDADE CATOLICA SHALOM GUARULHOS MACEDO - CNPJ: 07.044.456/0092-30)
            cabec['nCodCli'] = 2216843393
            if not cabec.get('dPrevisao'):
                cabec['dPrevisao'] = datetime.now().strftime("%d/%m/%Y")
            
            # Cenário Fiscal: Transferência (Entre filiais) -> codigo_cenario_impostos: 1818511574
            cabec['codigo_cenario_impostos'] = 1818511574
            cabec.pop('cCodCen', None)
            cabec.pop('nCodCen', None)
            
            body['cabec'] = cabec
            body.pop('agropecuario', None)

            # Frete -> Transportadora TRANSLATINO (nCodTransp: 2139040450)
            frete = body.get('frete', {})
            frete['nCodTransp'] = 2139040450
            frete['cTpFrete'] = "0"
            frete['cEspVol'] = "VOLUMES"
            body['frete'] = frete

            # Info Adicional -> Categoria Receitas Comercial (cCodCateg: "1.01.01")
            infAdic = body.get('infAdic', {})
            infAdic['cCodCateg'] = "1.01.01"
            infAdic['cConsFinal'] = "S"
            infAdic['cContato'] = "CD SP"
            if not infAdic.get('cDadosAdic'):
                infAdic['cDadosAdic'] = "Remessa Transferencia entre CD | Transportadora TRANSLATINO | Frete CIF | Destino: GUARULHOS MACEDO CNPJ 07.044.456/0092-30"
            body['infAdic'] = infAdic

            # Obs
            obs = body.get('obs', {})
            if not obs.get('cObs'):
                obs['cObs'] = "Remessa Transferencia entre CD | Transportadora TRANSLATINO | Frete CIF | Destino: GUARULHOS MACEDO CNPJ 07.044.456/0092-30||Fazer etiqueta com letras grandes e deixar a NF fora das caixas e quantidade de volumes:|A/C Sr. Gildo.|Entregar ao Tiberio|Comunidade Catolica Shalom|Translatino"
            body['obs'] = obs

            # Email
            email = body.get('email', {})
            if not email.get('cEmail'):
                email['cEmail'] = "centrodedistribuicaosp@comshalom.org"
            body['email'] = email

            # Carregar mapeamento completo com preços reais do produtos_turso.json
            produtos_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')
            sku_dict = {}
            if os.path.exists(produtos_json_path):
                with open(produtos_json_path, 'r', encoding='utf-8') as f:
                    for p in json.load(f):
                        s = str(p.get('sku', '')).strip()
                        if s:
                            sku_dict[s] = p

            # Atualizar nCodProd, preços reais, CFOP, local de estoque e cenário fiscal nos produtos
            prods = body.get('produtos', [])
            for item in prods:
                item.pop('nCodCen', None)
                item.pop('cCodCen', None)
                sku = str(item.get('cCodItInt') or item.get('sku') or '').strip()
                p_info = sku_dict.get(sku) or sku_dict.get(sku.zfill(6)) or {}

                # Tentar consultar código interno do produto no Omie por SKU/código
                cod_prod_omie = None
                if sku:
                    try:
                        resp_prod = client.executar("geral/produtos/", "ConsultarProduto", [{"codigo": sku}])
                        if "codigo_produto" in resp_prod:
                            cod_prod_omie = int(resp_prod["codigo_produto"])
                    except Exception:
                        pass

                if cod_prod_omie:
                    item["nCodProd"] = cod_prod_omie
                elif p_info.get("id_produto"):
                    item["nCodProd"] = int(p_info["id_produto"])
                else:
                    item.pop("nCodProd", None)

                if not item.get('cCodItInt') and sku:
                    item['cCodItInt'] = sku

                # Preço Unitário real de venda do produto
                v_unit = float(item.get('nValUnit') or 0)
                v_real = float(p_info.get('valor_unitario') or 0)
                if v_real <= 0 and 'resp_prod' in locals() and resp_prod:
                    v_real = float(resp_prod.get('valor_unitario') or 0)
                
                if v_real > 0:
                    item['nValUnit'] = v_real
                elif v_unit <= 0:
                    item['nValUnit'] = 15.00

                # Forçar o CFOP do item de acordo com o cenário fiscal
                item['cCFOP'] = "6.152"
                item['codigo_local_estoque'] = 1794541746

                # Garantir tributação padrão DRP: ICMS 41, PIS 07, COFINS 07
                origem_icms = (item.get('ICMS') or {}).get('cOrigem', '0')
                item['ICMS'] = {'cModBC': '', 'cOrigem': origem_icms, 'cSitTrib': '41', 'nAliq': 0, 'nBC': 0, 'nRedBC': 0, 'nValor': 0}
                item['PIS'] = {'cSitTribPIS': '07', 'cTpCalcPIS': '', 'nAliqPIS': 0, 'nBCPIS': 0, 'nQtdUTPIS': 0, 'nValPISUT': 0, 'nValPIS': 0}
                item['COFINS'] = {'cSitTribCOFINS': '07', 'cTpCalcCOFINS': '', 'nAliqCOFINS': 0, 'nBCCOFINS': 0, 'nQtdUTCOFINS': 0, 'nVaCOFINSSUT': 0, 'nValCOFINS': 0}

                inf_item = item.get('infAdicItem') or {}
                inf_item['codigo_cenario_impostos_item'] = 1818511574
                inf_item.pop('nCodCen', None)
                inf_item.pop('cCodCen', None)
                inf_item['cNaoMovEstoque'] = "N"
                item['infAdicItem'] = inf_item

            def strip_bad_keys(d):
                if isinstance(d, dict):
                    for k in list(d.keys()):
                        if k.lower() in ('ncodcen', 'ccodcen'):
                            d.pop(k, None)
                        else:
                            strip_bad_keys(d[k])
                elif isinstance(d, list):
                    for item in d:
                        strip_bad_keys(item)

            strip_bad_keys(body)
            res_omie = client.executar("produtos/remessa/", "IncluirRemessa", [body])
            
            nCodRem = res_omie.get("nCodRem") or res_omie.get("codigo_remessa")
            cCodIntRem = res_omie.get("cCodIntRem") or cabec['cCodIntRem']
            cDesStatus = res_omie.get("cDesStatus") or res_omie.get("faultstring") or ""
            cCodStatus = str(res_omie.get("cCodStatus") or "")

            if (nCodRem or cCodStatus == "0") and not res_omie.get("faultstring"):
                # Atualizar banco de dados local com a nova remessa criada
                if nCodRem:
                    try:
                        rem_criada = client.executar("produtos/remessa/", "ConsultarRemessa", [{"nCodRem": nCodRem}])
                        if "cabec" in rem_criada and db:
                            db.salvar_remessas_db([rem_criada])
                    except Exception as ex_db:
                        print(f"[API SERVER] Erro ao salvar nova remessa no banco local: {ex_db}")

                payload_resp = {
                    "success": True,
                    "nCodRem": nCodRem,
                    "cCodIntRem": cCodIntRem,
                    "message": f"Remessa de Transferência nº {nCodRem or cCodIntRem} gerada com sucesso no Omie ERP!",
                    "raw_omie": res_omie
                }
            else:
                payload_resp = {
                    "success": False,
                    "message": f"Erro do Omie ERP: {cDesStatus}",
                    "raw_omie": res_omie
                }
        except Exception as err:
            print(f"[API SERVER] Erro ao incluir remessa: {err}")
            payload_resp = {"success": False, "message": f"Falha interna: {str(err)}"}
        self._send_json(payload_resp)

    def handle_api_remessas_listar(self):
        body = self._read_body()
        force_sync = body.get('force_sync', False)
        cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'remessas_cache.json')
        
        # 1. Carregar do Banco de Dados Turso / SQLite
        remessas_locais = []
        if db:
            try:
                remessas_locais = db.obter_remessas_db()
            except Exception as ex:
                remessas_locais = []

        # 2. Fallback JSON caso o banco local esteja limpo
        if not remessas_locais and os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    remessas_locais = json.load(f)
            except Exception:
                remessas_locais = []
        # Filtrar estritamente apenas remessas de Guarulhos
        def _is_guarulhos(r):
            c = r.get("cabec") or {}
            obs = (r.get("obs") or {}).get("cObs", "").upper()
            info = (r.get("infAdic") or {}).get("cDadosAdic", "").upper()
            cli = str(c.get("nCodCli", "")).strip()
            return cli == "2216843393" or "GUARULHOS" in obs or "MACEDO" in obs or "0092-30" in obs or "009230" in obs or "GUARULHOS" in info or "MACEDO" in info or "0092-30" in info

        remessas_locais = [r for r in remessas_locais if _is_guarulhos(r)]

        # Enriquecer itens com SKU e Nome do catálogo de produtos caso venham vazios da Omie
        def _enrich_remessas(lista_remessas):
            prods_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')
            if not os.path.exists(prods_path):
                return
            try:
                with open(prods_path, 'r', encoding='utf-8') as f:
                    prods = json.load(f)
                p_map = {}
                for p in prods:
                    pid = str(p.get('id_produto') or p.get('nCodProd') or '')
                    if pid: p_map[pid] = p
                    psku = str(p.get('sku') or p.get('codigo') or '').strip()
                    if psku: p_map[psku] = p

                for r in lista_remessas:
                    for item in (r.get('produtos') or r.get('det') or []):
                        prod = item.get('produto') or item
                        nCodProd = str(item.get('nCodProd') or prod.get('nCodProd') or '')
                        cCodItInt = str(item.get('cCodItInt') or prod.get('cCodItInt') or '').strip()
                        cDesc = str(item.get('cDescricao') or prod.get('cDescricao') or '').strip()

                        if not cCodItInt or not cDesc or cDesc == 'Produto Sem Nome':
                            p_found = p_map.get(nCodProd) or p_map.get(cCodItInt)
                            if p_found:
                                m_sku = p_found.get('sku') or p_found.get('codigo')
                                m_nome = p_found.get('nome') or p_found.get('descricao')
                                if m_sku and not cCodItInt:
                                    item['cCodItInt'] = m_sku
                                    if isinstance(item.get('produto'), dict): item['produto']['cCodItInt'] = m_sku
                                if m_nome and (not cDesc or cDesc == 'Produto Sem Nome'):
                                    item['cDescricao'] = m_nome
                                    if isinstance(item.get('produto'), dict): item['produto']['cDescricao'] = m_nome
            except Exception as e_enr:
                print(f"[API SERVER] Erro ao enriquecer remessas: {e_enr}")

        # 3. Se NÃO for forçar sincronização e JÁ EXISTIREM remessas no banco local, retorna direto do Banco (Zero Omie API)
        if not force_sync and remessas_locais:
            _enrich_remessas(remessas_locais)
            payload_resp = {
                "success": True, 
                "data": {"remessas": remessas_locais}, 
                "remessas": remessas_locais, 
                "count": len(remessas_locais),
                "fonte": "BANCO_LOCAL"
            }
            self._send_json(payload_resp)
            return

        # 4. Caso contrário (force_sync=True ou Banco Vazio), faz a consulta na API da Omie e salva no Banco
        try:
            from omie_client import OmieClient
            client = OmieClient("MATRIZ")
            
            remessas_dict = {str((r.get('cabec') or {}).get('nCodRem') or (r.get('cabec') or {}).get('cNumeroRemessa')): r for r in remessas_locais if r.get('cabec')}
            
            max_pags = 30
            pg = 1
            tot_paginas = 1
            novas_adicionadas = 0

            while pg <= tot_paginas and pg <= max_pags:
                res_omie = client.executar("produtos/remessa/", "ListarRemessas", [{"nPagina": pg}])
                tot_paginas = res_omie.get("nTotalPaginas", 1)
                rem_lista = res_omie.get("remessas") or res_omie.get("remessas_lista") or []
                if not rem_lista:
                    break
                    
                for r in rem_lista:
                    c = r.get("cabec", {})
                    obs = (r.get("obs") or {}).get("cObs", "").upper()
                    info = (r.get("infAdic") or {}).get("cDadosAdic", "").upper()
                    cli = c.get("nCodCli")
                    
                    if cli == 2216843393 or "GUARULHOS" in obs or "MACEDO" in obs or "0092-30" in obs or "009230" in obs or "GUARULHOS" in info or "MACEDO" in info or "0092-30" in info:
                        key_id = str(c.get('nCodRem') or c.get('cNumeroRemessa'))
                        if key_id in remessas_dict:
                            if not r.get("produtos") and remessas_dict[key_id].get("produtos"):
                                r["produtos"] = remessas_dict[key_id]["produtos"]
                        else:
                            novas_adicionadas += 1

                        # Se a remessa não possui a lista de produtos, tenta consultar a remessa completa no Omie
                        if not r.get("produtos"):
                            try:
                                cons_rem = client.executar("produtos/remessa/", "ConsultarRemessa", [{"nCodRem": int(c.get('nCodRem'))}])
                                if "produtos" in cons_rem:
                                    r["produtos"] = cons_rem["produtos"]
                            except Exception:
                                pass

                        remessas_dict[key_id] = r
                
                pg += 1

            guarulhos_remessas = list(remessas_dict.values())
            guarulhos_remessas.sort(key=lambda r: int(r.get('cabec', {}).get('nCodRem', 0) or 0), reverse=True)
            _enrich_remessas(guarulhos_remessas)

            if db:
                try:
                    db.salvar_remessas_db(guarulhos_remessas)
                except Exception as ex:
                    print(f"[API SERVER] Erro ao salvar remessas no banco de dados: {ex}")

            try:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(guarulhos_remessas, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[API SERVER] Erro ao salvar cache JSON de remessas: {e}")

            payload_resp = {
                "success": True, 
                "data": {"remessas": guarulhos_remessas}, 
                "remessas": guarulhos_remessas, 
                "count": len(guarulhos_remessas),
                "novas": novas_adicionadas,
                "fonte": "OMIE_SYNC"
            }
        except Exception as err:
            print(f"[API SERVER] Erro na sincronizacao de remessas Omie: {err}")
            _enrich_remessas(remessas_locais)
            payload_resp = {
                "success": True, 
                "data": {"remessas": remessas_locais or []}, 
                "remessas": remessas_locais or [], 
                "count": len(remessas_locais or []),
                "error_info": str(err),
                "offline": True
            }
        self._send_json(payload_resp)




    def handle_api_remessas_status(self):
        body = self._read_body()
        try:
            from omie_client import OmieClient
            client = OmieClient("MATRIZ")
            
            res_omie = {}
            # Tenta ConsultarRemessa para obter o objeto completo com a lista de produtos (produtos)
            try:
                res_omie = client.executar("produtos/remessa/", "ConsultarRemessa", [body])
            except Exception as eCons:
                res_omie = client.executar("produtos/remessa/", "StatusRemessa", [body])

            payload_resp = {"success": True, "data": res_omie}
        except Exception as err:
            payload_resp = {"success": False, "message": str(err)}
        self._send_json(payload_resp)

    def handle_api_remessas_alterar(self):
        body = self._read_body()
        try:
            from omie_client import OmieClient
            import math
            client = OmieClient("MATRIZ")
            
            nCodRem = body.get("nCodRem")
            novos_produtos = body.get("novosProdutos", [])
            
            if not nCodRem or not novos_produtos:
                raise ValueError("nCodRem e novosProdutos são obrigatórios para mesclar a remessa.")
                
            # 1. Consultar a Remessa Existente
            res_consulta = client.executar("produtos/remessa/", "ConsultarRemessa", [{"nCodRem": nCodRem}])
            if "cabec" not in res_consulta:
                raise ValueError("Remessa não encontrada no Omie.")
                
            remessa = res_consulta
            
            # 2. Obter os itens atuais
            itens_atuais = remessa.get("produtos", [])
            if not itens_atuais:
                itens_atuais = remessa.get("det", [])
            
            # 3. Atualizar parâmetros gerais da remessa (Cenário Fiscal, Transportadora e Categoria)
            cabec = remessa.get("cabec", {})
            cabec["codigo_cenario_impostos"] = 1818511574
            cabec.pop("cCodCen", None)
            cabec.pop("nCodCen", None)

            infAdic = remessa.get("infAdic", {})
            infAdic["cCodCateg"] = "1.01.01"
            infAdic["cConsFinal"] = "S"
            infAdic["cContato"] = "CD SP"

            # 4. Adicionar os novos itens
            produtos_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')
            sku_map = {}
            if os.path.exists(produtos_json_path):
                try:
                    with open(produtos_json_path, 'r', encoding='utf-8') as f:
                        for p_elem in json.load(f):
                            s = str(p_elem.get('sku', '')).strip()
                            if s:
                                sku_map[s] = p_elem
                except Exception:
                    pass

            for item in novos_produtos:
                item.pop("cCodCen", None)
                item.pop("nCodCen", None)
                if "nCodIt" in item and item["nCodIt"] == 0:
                    item.pop("nCodIt")
                item["cCFOP"] = "6.152"
                item["codigo_local_estoque"] = 1794541746

                sku = str(item.get("cCodItInt") or item.get("sku") or "").strip()
                p_info = sku_map.get(sku) or sku_map.get(sku.zfill(6)) or {}

                # Tentar consultar código interno do produto no Omie por SKU/código
                cod_prod_omie = None
                if sku:
                    try:
                        resp_prod = client.executar("geral/produtos/", "ConsultarProduto", [{"codigo": sku}])
                        if "codigo_produto" in resp_prod:
                            cod_prod_omie = int(resp_prod["codigo_produto"])
                    except Exception:
                        pass

                if cod_prod_omie:
                    item["nCodProd"] = cod_prod_omie
                elif p_info.get("id_produto"):
                    item["nCodProd"] = int(p_info["id_produto"])
                else:
                    item.pop("nCodProd", None)
                
                v_unit = float(item.get("nValUnit") or 0)
                v_real = float(p_info.get("valor_unitario") or 0)
                if v_real <= 0 and 'resp_prod' in locals() and resp_prod:
                    v_real = float(resp_prod.get("valor_unitario") or 0)

                if v_real > 0:
                    item["nValUnit"] = v_real
                elif v_unit <= 0:
                    item["nValUnit"] = 15.00

                inf_item = item.get("infAdicItem") or {}
                inf_item["codigo_cenario_impostos_item"] = 1818511574
                inf_item.pop("nCodCen", None)
                inf_item.pop("cCodCen", None)
                inf_item["cNaoMovEstoque"] = "N"
                item["infAdicItem"] = inf_item

                itens_atuais.append(item)

            # Garantir tributação padrão DRP e nValUnit > 0 para TODOS os itens da remessa (existentes + novos): ICMS 41, PIS 07, COFINS 07
            for item in itens_atuais:
                v_it = float(item.get("nValUnit") or item.get("nPrecoUnit") or item.get("valor_unitario") or 0)
                if v_it <= 0:
                    sku = str(item.get("cCodItInt") or item.get("sku") or "").strip()
                    p_info = sku_map.get(sku) or sku_map.get(sku.zfill(6)) or {}
                    v_it = float(p_info.get("valor_unitario") or 0)
                    if v_it <= 0 and sku:
                        try:
                            resp_p = client.executar("geral/produtos/", "ConsultarProduto", [{"codigo": sku}])
                            v_it = float(resp_p.get("valor_unitario") or 0)
                        except Exception:
                            pass
                    if v_it <= 0:
                        v_it = 15.00
                item["nValUnit"] = v_it
                item["cCFOP"] = "6.152"
                item["codigo_local_estoque"] = 1794541746
                origem_icms = (item.get("ICMS") or {}).get("cOrigem", "0")
                item["ICMS"] = {"cModBC": "", "cOrigem": origem_icms, "cSitTrib": "41", "nAliq": 0, "nBC": 0, "nRedBC": 0, "nValor": 0}
                item["PIS"] = {"cSitTribPIS": "07", "cTpCalcPIS": "", "nAliqPIS": 0, "nBCPIS": 0, "nQtdUTPIS": 0, "nValPISUT": 0, "nValPIS": 0}
                item["COFINS"] = {"cSitTribCOFINS": "07", "cTpCalcCOFINS": "", "nAliqCOFINS": 0, "nBCCOFINS": 0, "nQtdUTCOFINS": 0, "nVaCOFINSSUT": 0, "nValCOFINS": 0}
                inf_it = item.get("infAdicItem") or {}
                inf_it["codigo_cenario_impostos_item"] = 1818511574
                inf_it["cNaoMovEstoque"] = "N"
                item["infAdicItem"] = inf_it

            # Calcular o novo peso bruto e volumes
            peso_total = 0
            for it in itens_atuais:
                qtd = float(it.get("nQtde", 0))
                peso = float(it.get("infAdicItem", {}).get("nPesoBruto", 0.2)) 
                peso_total += (peso * qtd)
                
            caixas = math.ceil(peso_total / 16.0)
            volumes = max(1, caixas)
            
            # Calcular novo frete e volumes usando ControleDRP
            from controle_drp import ControleDRP
            drp_ctrl = ControleDRP()
            valor_frete, volumes, _ = drp_ctrl.calcular_frete(peso_total)
                
            frete = remessa.get("frete", {})
            frete["nPesoBruto"] = round(peso_total, 3)
            frete["nPesoLiq"] = round(peso_total * 0.9, 3)
            frete["nQtdVol"] = volumes
            frete["cNumVol"] = str(volumes)
            frete["nValFrete"] = valor_frete
            frete["nCodTransp"] = 2139040450
            frete["cTpFrete"] = "0"
            
            # Montar payload de Alteração
            payload_alterar = {
                "cabec": cabec,
                "frete": frete,
                "infAdic": infAdic,
                "produtos": itens_atuais
            }
            if "obs" in remessa: payload_alterar["obs"] = remessa["obs"]
            if "infAdic" in remessa: payload_alterar["infAdic"] = remessa["infAdic"]
            if "email" in remessa: payload_alterar["email"] = remessa["email"]

            def strip_bad_keys(d):
                if isinstance(d, dict):
                    for k in list(d.keys()):
                        if k.lower() in ('ncodcen', 'ccodcen'):
                            d.pop(k, None)
                        else:
                            strip_bad_keys(d[k])
                elif isinstance(d, list):
                    for item in d:
                        strip_bad_keys(item)

            strip_bad_keys(payload_alterar)
            res_omie = client.executar("produtos/remessa/", "AlterarRemessa", [payload_alterar])
            
            cCodStatus = str(res_omie.get("cCodStatus") or "")
            faultstring = res_omie.get("faultstring") or res_omie.get("cDesStatus") or ""

            if faultstring and ("ERROR" in faultstring.upper() or (cCodStatus and cCodStatus != "0")):
                payload_resp = {"success": False, "message": f"Erro do Omie ERP: {faultstring}", "raw_omie": res_omie}
            else:
                # Atualizar banco de dados local com a remessa alterada completa
                try:
                    rem_atualizada = client.executar("produtos/remessa/", "ConsultarRemessa", [{"nCodRem": nCodRem}])
                    if "cabec" in rem_atualizada and db:
                        db.salvar_remessas_db([rem_atualizada])
                except Exception as ex_db:
                    print(f"[API SERVER] Erro ao atualizar banco local após alterar remessa: {ex_db}")

                payload_resp = {"success": True, "nCodRem": nCodRem, "message": f"Remessa #{nCodRem} alterada com sucesso no Omie ERP!", "data": res_omie}
        except Exception as err:
            print(f"[API SERVER] Erro ao alterar remessa: {err}")
            payload_resp = {"success": False, "message": str(err)}
        self._send_json(payload_resp)

    def handle_api_remessas_devolver(self):
        body = self._read_body()
        try:
            from omie_client import OmieClient
            client = OmieClient("MATRIZ")
            res_omie = client.executar("produtos/remessa/", "DevolverRemessa", [body])
            payload_resp = {"success": True, "data": res_omie}
        except Exception as err:
            payload_resp = {"success": False, "message": str(err)}
        self._send_json(payload_resp)

    def handle_api_combo_detalhes(self):
        query = parse_qs(urlparse(self.path).query)
        sku = query.get('sku', ['000223'])[0].strip()

        try:
            from omie_client import OmieClient
            client = OmieClient("MATRIZ")
            
            cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scratch', f'cache_combo_{sku}.json')
            kit = None

            # Tenta consultar Omie
            try:
                res_omie = client.executar('geral/produtos/', 'ConsultarProduto', [{'codigo': sku}])
                if res_omie and 'codigo_produto' in res_omie:
                    kit = res_omie
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(kit, f, ensure_ascii=False, indent=2)
            except Exception as ex_omie:
                print(f"[COMBO] Consulta Omie falhou ({ex_omie}), buscando cache...")

            # Fallback para cache se Omie falhar ou der erro redundante
            if not kit and os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        kit = json.load(f)
                except Exception:
                    pass

            if not kit or 'codigo_produto' not in kit:
                self._send_json({"success": False, "message": f"Kit SKU {sku} não encontrado no Omie ERP."})
                return

            ncod_kit = kit['codigo_produto']
            desc_kit = kit.get('descricao', '')
            valor_venda = float(kit.get('valor_unitario') or 0.0)
            comps_raw = kit.get('componentes_kit') or []

            # Mapeamento rápido de produtos pelo cache Turso
            prods_by_id = {}
            json_turso = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')
            if os.path.exists(json_turso):
                try:
                    with open(json_turso, 'r', encoding='utf-8') as f:
                        for p in json.load(f):
                            if p.get('id_produto'):
                                prods_by_id[int(p['id_produto'])] = p
                except Exception:
                    pass

            componentes = []
            for c in comps_raw:
                ncod_comp = int(c.get('codigo_produto_componente') or 0)
                cod_comp_id = c.get('codigo_componente')
                
                # Busca rápida no cache local Turso
                p_info = prods_by_id.get(ncod_comp, {})
                sku_comp = str(p_info.get('codigo') or p_info.get('sku') or '').strip()
                desc_comp = p_info.get('nome') or p_info.get('descricao') or f"Componente #{ncod_comp}"
                est_matriz = int(p_info.get('matriz') or p_info.get('matriz_disponivel') or 0)

                # Fallback se não achou no cache Turso
                if not sku_comp and ncod_comp:
                    try:
                        p_omie = client.executar('geral/produtos/', 'ConsultarProduto', [{'codigo_produto': ncod_comp}])
                        if p_omie and 'codigo' in p_omie:
                            sku_comp = (p_omie.get('codigo_produto_integracao') or p_omie.get('codigo') or '').strip()
                            desc_comp = p_omie.get('descricao', desc_comp)
                    except Exception:
                        pass

                if est_matriz <= 5:
                    nivel_alerta = 'REMOVER'
                elif est_matriz <= 20:
                    nivel_alerta = 'CRITICO'
                elif est_matriz <= 50:
                    nivel_alerta = 'ATENCAO'
                else:
                    nivel_alerta = 'OK'

                componentes.append({
                    "codigo_componente": cod_comp_id,
                    "codigo_produto_componente": ncod_comp,
                    "sku": sku_comp,
                    "descricao": desc_comp,
                    "quantidade": c.get('quantidade_componente', 1),
                    "estoque_matriz": est_matriz,
                    "nivel_alerta": nivel_alerta
                })

            self._send_json({
                "success": True,
                "combo": {
                    "codigo_produto": ncod_kit,
                    "sku": sku,
                    "descricao": desc_kit,
                    "valor_venda": valor_venda
                },
                "componentes": componentes
            })

        except Exception as e:
            print(f"[API SERVER] Erro em handle_api_combo_detalhes: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_combo_remover_componente(self):
        body = self._read_body()
        sku_combo = str(body.get('sku_combo', '000223')).strip()
        codigo_componente = body.get('codigo_componente')
        codigo_produto_componente = body.get('codigo_produto_componente')
        novo_valor_venda = float(body.get('novo_valor_venda', 89.90))

        if not codigo_produto_componente:
            self._send_json({"success": False, "message": "ID do componente é obrigatório."}, status=400)
            return

        try:
            from omie_client import OmieClient
            client = OmieClient("MATRIZ")

            kit = client.executar('geral/produtos/', 'ConsultarProduto', [{'codigo': sku_combo}])
            if not kit or 'codigo_produto' not in kit:
                self._send_json({"success": False, "message": f"Kit SKU {sku_combo} não encontrado no Omie ERP."})
                return

            ncod_kit = kit['codigo_produto']

            payload_kit = {
                "codigo_produto": ncod_kit,
                "componentes_kit": [
                    {
                        "acao_componente": "E",
                        "codigo_componente": codigo_componente or 0,
                        "codigo_produto_componente": codigo_produto_componente
                    }
                ]
            }
            res_kit = client.executar('geral/produtokit/', 'AlterarComponentesKit', [payload_kit])
            st_kit = str(res_kit.get('cCodStatus', '')) if isinstance(res_kit, dict) else ''

            if st_kit != '0':
                msg_err = res_kit.get('cDesStatus') or res_kit.get('faultstring') or "Erro ao remover componente do Kit"
                self._send_json({"success": False, "message": f"Omie ERP: {msg_err}"})
                return

            payload_prod = {
                "codigo_produto": ncod_kit,
                "codigo": sku_combo,
                "descricao": kit.get('descricao', 'ASSINATURA PÃO DA VIDA'),
                "unidade": kit.get('unidade', 'UN'),
                "valor_unitario": float(novo_valor_venda)
            }
            res_prod = client.executar('geral/produtos/', 'AlterarProduto', [payload_prod])

            self._send_json({
                "success": True,
                "message": f"Componente removido do combo SKU {sku_combo} com sucesso! Valor de venda redefinido para R$ {novo_valor_venda:.2f} no Omie ERP.",
                "omie_kit_status": res_kit.get('cDesStatus'),
                "omie_prod_status": res_prod.get('descricao_status')
            })

        except Exception as e:
            print(f"[API SERVER] Erro ao remover componente do combo: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_combo_alterar_preco(self):
        body = self._read_body()
        sku_combo = str(body.get('sku_combo', '000223')).strip()
        valor_venda = float(body.get('valor_venda', 89.90))

        try:
            from omie_client import OmieClient
            client = OmieClient("MATRIZ")

            kit = client.executar('geral/produtos/', 'ConsultarProduto', [{'codigo': sku_combo}])
            if not kit or 'codigo_produto' not in kit:
                self._send_json({"success": False, "message": f"Kit SKU {sku_combo} não encontrado."})
                return

            payload_prod = {
                "codigo_produto": kit['codigo_produto'],
                "codigo": sku_combo,
                "descricao": kit.get('descricao', 'ASSINATURA PÃO DA VIDA'),
                "unidade": kit.get('unidade', 'UN'),
                "valor_unitario": float(valor_venda)
            }
            res_prod = client.executar('geral/produtos/', 'AlterarProduto', [payload_prod])
            st_prod = str(res_prod.get('codigo_status', '')) if isinstance(res_prod, dict) else ''

            if st_prod == '0':
                self._send_json({
                    "success": True,
                    "message": f"Valor de venda do Combo SKU {sku_combo} alterado para R$ {valor_venda:.2f} no Omie ERP!"
                })
            else:
                self._send_json({
                    "success": False,
                    "message": res_prod.get('descricao_status') or res_prod.get('faultstring') or "Erro ao alterar valor de venda no Omie"
                })

        except Exception as e:
            print(f"[API SERVER] Erro ao alterar preço do combo: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    # ==========================================
    # MÓDULO DE CONSIGNAÇÃO (IDA E VOLTA)
    # ==========================================
    def handle_api_consignacao_clientes(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            q = query.get('q', [''])[0].strip()
            from services.consignacao_service import ConsignacaoService
            service = ConsignacaoService()
            clientes = service.buscar_clientes(q)
            self._send_json({"success": True, "clientes": clientes})
        except Exception as e:
            print(f"[API SERVER] Erro em consignacao_clientes: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_consignacao_remessas(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            cli_id = query.get('nCodCli', ['0'])[0].strip()
            from services.consignacao_service import ConsignacaoService
            service = ConsignacaoService()
            remessas = service.listar_remessas_cliente(int(cli_id) if cli_id.isdigit() else 0)
            self._send_json({"success": True, "remessas": remessas})
        except Exception as e:
            print(f"[API SERVER] Erro em consignacao_remessas: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_consignacao_unificar(self):
        try:
            body = self._read_body()
            rems = body.get('remessas', [])
            desc = float(body.get('desconto_padrao_pct', 30.0))
            from services.consignacao_service import ConsignacaoService
            service = ConsignacaoService()
            rems_ids = [int(x) for x in rems if str(x).isdigit()]
            res = service.unificar_remessas(rems_ids, desconto_padrao_pct=desc)
            self._send_json({"success": True, "data": res})
        except Exception as e:
            print(f"[API SERVER] Erro em consignacao_unificar: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_consignacao_salvar_acerto(self):
        try:
            body = self._read_body()
            from services.consignacao_service import ConsignacaoService
            service = ConsignacaoService()
            res = service.salvar_acerto(body)
            self._send_json(res)
        except Exception as e:
            print(f"[API SERVER] Erro em consignacao_salvar_acerto: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_consignacao_acertos_listar(self):
        try:
            from services.consignacao_service import ConsignacaoService
            service = ConsignacaoService()
            acertos = service.listar_acertos()
            self._send_json({"success": True, "acertos": acertos})
        except Exception as e:
            print(f"[API SERVER] Erro em consignacao_acertos_listar: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_consignacao_acerto_obter(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            ac_id = query.get('id', ['0'])[0].strip()
            from services.consignacao_service import ConsignacaoService
            service = ConsignacaoService()
            acerto = service.obter_acerto(ac_id)
            self._send_json({"success": True, "acerto": acerto})
        except Exception as e:
            print(f"[API SERVER] Erro em consignacao_acerto_obter: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_consignacao_integrar_omie(self):
        try:
            body = self._read_body()
            acerto_id = int(body.get('acerto_id', 0))
            from services.consignacao_service import ConsignacaoService
            service = ConsignacaoService()
            acerto = service.obter_acerto(acerto_id)
            if not acerto:
                self._send_json({"success": False, "message": f"Acerto #{acerto_id} não encontrado."})
                return
            if body.get('numero_pedido_manual'):
                acerto['numero_pedido_manual'] = str(body['numero_pedido_manual']).strip()
            if body.get('codigo_vendedora'):
                acerto['codigo_vendedora'] = body['codigo_vendedora']
            res = service.integrar_omie(acerto)
            self._send_json(res)
        except Exception as e:
            print(f"[API SERVER] Erro em consignacao_integrar_omie: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_consignacao_eventos_remessas(self):
        try:
            from services.consignacao_service import ConsignacaoService
            service = ConsignacaoService()
            remessas = service.listar_remessas_eventos()
            self._send_json({"success": True, "remessas": remessas})
        except Exception as e:
            print(f"[API SERVER] Erro em consignacao_eventos_remessas: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_consignacao_eventos_salvar(self):
        try:
            body = self._read_body()
            from services.consignacao_service import ConsignacaoService
            service = ConsignacaoService()
            res = service.salvar_remessa_evento(body)
            self._send_json(res)
        except Exception as e:
            print(f"[API SERVER] Erro em consignacao_eventos_salvar: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_consignacao_buscar_produto(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            q = query.get('q', [''])[0].strip()
            from services.consignacao_service import ConsignacaoService
            service = ConsignacaoService()
            prods = service.buscar_produto(q)
            self._send_json({"success": True, "produtos": prods})
        except Exception as e:
            print(f"[API SERVER] Erro em consignacao_buscar_produto: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_consignacao_vincular_remessa_aberta(self):
        try:
            body = self._read_body()
            from services.consignacao_service import ConsignacaoService
            service = ConsignacaoService()
            res = service.vincular_remessa_aberta(body)
            self._send_json(res)
        except Exception as e:
            print(f"[API SERVER] Erro em vincular_remessa_aberta: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_consignacao_atualizar_inicio_prazo(self):
        try:
            body = self._read_body()
            acerto_id = body.get("acerto_id") or body.get("id")
            nova_data = body.get("data_inicio") or body.get("data_inicio_prazo")
            dias_prazo = int(body.get("dias_prazo") or 30)
            from services.consignacao_service import ConsignacaoService
            service = ConsignacaoService()
            res = service.atualizar_inicio_prazo(acerto_id, nova_data, dias_prazo)
            self._send_json(res)
        except Exception as e:
            print(f"[API SERVER] Erro em atualizar_inicio_prazo: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_pedidos_venda_consultar(self):
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            num_pedido = (qs.get("numero", [""])[0] or qs.get("numero_pedido", [""])[0]).strip()

            if not num_pedido:
                self._send_json({"success": False, "message": "Número do pedido não informado"}, status=400)
                return

            from omie_client import OmieClient
            cli_omie = OmieClient("MATRIZ")
            res_pv = cli_omie.executar("produtos/pedido/", "ConsultarPedido", [{"numero_pedido": num_pedido}])
            pv = res_pv.get("pedido_venda_produto", {})
            cab = pv.get("cabecalho", {})
            cod_cli = cab.get("codigo_cliente", 0)

            pedido_info = {
                "numero_pedido": num_pedido,
                "codigo_pedido_omie": cab.get("codigo_pedido", 0),
                "codigo_cliente_omie": cod_cli,
                "cliente_nome": "",
                "cpf_cnpj": "",
                "rua": "",
                "numero": "",
                "complemento": "",
                "bairro": "",
                "cidade": "",
                "uf": "",
                "cep": "",
                "quantidade_assinaturas": 1
            }

            # Contar quantidade se houver itens
            itens = pv.get("det", [])
            total_qtd = 0
            for it in itens:
                prod = it.get("produto", {})
                sku = str(prod.get("codigo_produto_integracao") or prod.get("codigo") or "").strip()
                if "000223" in sku or "00379" in sku or "00574" in sku or "PAO" in sku.upper() or "ASSINATURA" in (prod.get("descricao") or "").upper():
                    total_qtd += int(prod.get("quantidade", 1))
            if total_qtd > 0:
                pedido_info["quantidade_assinaturas"] = total_qtd

            if cod_cli:
                res_c = cli_omie.executar("geral/clientes/", "ConsultarCliente", [{"codigo_cliente_omie": cod_cli}])
                pedido_info["cliente_nome"] = res_c.get("nome_fantasia") or res_c.get("razao_social") or ""
                pedido_info["cpf_cnpj"] = res_c.get("cnpj_cpf") or ""
                pedido_info["rua"] = res_c.get("endereco") or ""
                pedido_info["numero"] = res_c.get("endereco_numero") or ""
                pedido_info["complemento"] = res_c.get("complemento") or ""
                pedido_info["bairro"] = res_c.get("bairro") or ""
                pedido_info["cidade"] = res_c.get("cidade") or ""
                pedido_info["uf"] = res_c.get("estado") or ""
                pedido_info["cep"] = res_c.get("cep") or ""

            self._send_json({"success": True, "pedido": pedido_info})
        except Exception as e:
            print(f"[API SERVER] Erro ao consultar pedido de venda: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_consignacao_disparar_alertas_prazos(self):
        try:
            from services.consignacao_service import ConsignacaoService
            service = ConsignacaoService()
            res = service.verificar_alertas_prazos_consignacao()
            self._send_json(res)
        except Exception as e:
            print(f"[API SERVER] Erro em disparar_alertas_prazos: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_assinaturas_listar_pedidos_proximo_envio(self):
        try:
            sql = "SELECT * FROM assinaturas_pedidos_proximo_envio ORDER BY id DESC LIMIT 100"
            df = db.executar_query(sql)
            rows = []
            if df is not None and not df.empty:
                for _, r in df.iterrows():
                    d = dict(r)
                    sku_p = str(d.get("sku_produto") or "").strip().upper()
                    qtd_ass = int(d.get("quantidade_assinaturas") or 1)
                    num_ped = str(d.get("numero_pedido") or d.get("codigo_pedido_omie") or "")
                    total_contratado = int(d.get("total_exemplares_contratados") or 12) * qtd_ass
                    entregues_por_ass = int(d.get("exemplares_entregues") or 0)

                    if "PRD00379" in sku_p:
                        # Combo PRD00379: Jan, Fev e Mar/2027 já foram enviados no faturamento do pedido Omie
                        ciclos_entregues = entregues_por_ass if entregues_por_ass > 0 else 3
                        ja_rec_tot = ciclos_entregues * qtd_ass
                        restantes_tot = max(0, total_contratado - ja_rec_tot)
                        d["ciclos_info"] = {
                            "total_contratado": total_contratado,
                            "ja_recebidos": ja_rec_tot,
                            "neste_lote": 0,
                            "restantes_futuros": restantes_tot,
                            "origem": f"Pedido Omie #{num_ped} (Combo PRD00379)",
                            "etapas": [
                                {"ciclo": "Jan, Fev, Mar/2027", "status": "ENVIADO", "badge": "success", "obs": f"Enviado no Pedido Omie #{num_ped} em 23/10/2026", "qtd": 3 * qtd_ass},
                                {"ciclo": "Lote 2 (Abr, Mai, Jun/2027)", "status": "PENDENTE", "badge": "secondary", "obs": "Aguardando 2º Lote Trimestral", "qtd": 3 * qtd_ass},
                                {"ciclo": "Lote 3 (Jul a Dez/2027 - 6 meses)", "status": "PENDENTE", "badge": "secondary", "obs": "Envio Semestral Consolidado (fechamento)", "qtd": 6 * qtd_ass}
                            ]
                        }
                    elif "000223" in sku_p:
                        # Combo 000223: Dezembro/2026 já enviado na venda
                        ciclos_entregues = entregues_por_ass if entregues_por_ass > 0 else 1
                        ja_rec_tot = ciclos_entregues * qtd_ass
                        neste_tot = 3 * qtd_ass
                        restantes_tot = max(0, total_contratado - (ja_rec_tot + neste_tot))
                        d["ciclos_info"] = {
                            "total_contratado": total_contratado,
                            "ja_recebidos": ja_rec_tot,
                            "neste_lote": neste_tot,
                            "restantes_futuros": restantes_tot,
                            "origem": f"Pedido Omie #{num_ped} (Combo 000223)",
                            "etapas": [
                                {"ciclo": "Dezembro/2026", "status": "ENVIADO", "badge": "success", "obs": f"Enviado no Pedido Omie #{num_ped} em 23/10/2026", "qtd": 1 * qtd_ass},
                                {"ciclo": "Jan, Fev, Mar/2027 (Lote 1)", "status": "NESTE_LOTE", "badge": "primary", "obs": "INCLUSO NO LOTE ATUAL (Aguardando Despacho)", "qtd": 3 * qtd_ass},
                                {"ciclo": "Lote 2 (Abr, Mai, Jun/2027)", "status": "PENDENTE", "badge": "secondary", "obs": "Aguardando 2º Lote Trimestral", "qtd": 3 * qtd_ass},
                                {"ciclo": "Lote 3 (Jul a Nov/2027 - 5 meses)", "status": "PENDENTE", "badge": "secondary", "obs": "Envio Semestral Consolidado (fechamento)", "qtd": 5 * qtd_ass}
                            ]
                        }
                    else:
                        ja_rec_tot = entregues_por_ass * qtd_ass
                        neste_tot = 3 * qtd_ass
                        restantes_tot = max(0, total_contratado - (ja_rec_tot + neste_tot))
                        d["ciclos_info"] = {
                            "total_contratado": total_contratado,
                            "ja_recebidos": ja_rec_tot,
                            "neste_lote": neste_tot,
                            "restantes_futuros": restantes_tot,
                            "origem": f"Pedido Omie #{num_ped}",
                            "etapas": [
                                {"ciclo": "Jan, Fev, Mar/2027 (Lote 1)", "status": "NESTE_LOTE", "badge": "primary", "obs": "Lote Atual", "qtd": neste_tot},
                                {"ciclo": "Lote 2 (Abr, Mai, Jun/2027)", "status": "PENDENTE", "badge": "secondary", "obs": "Próximo Lote", "qtd": 3 * qtd_ass},
                                {"ciclo": "Lote 3 (Jul a Dez/2027 - 6 meses)", "status": "PENDENTE", "badge": "secondary", "obs": "Envio Semestral Consolidado", "qtd": 6 * qtd_ass}
                            ]
                        }
                    rows.append(d)
            self._send_json({"success": True, "pedidos": rows})
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao listar pedidos proximo envio: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_assinaturas_concluir_lote(self):
        try:
            body = self._read_body()
            nome_lote = body.get("nome_lote") or "Lote 1 (Jan, Fev e Mar/2027)"
            agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 1. Atualizar registros em assinaturas_pedidos_proximo_envio que estavam no lote 1
            # (Ex: SKU 000223 como Rosângela, avançando seus exemplares e status)
            sql_upd = """
                UPDATE assinaturas_pedidos_proximo_envio
                SET 
                    exemplares_entregues = COALESCE(exemplares_entregues, 0) + 3,
                    ultimo_lote_enviado = :lote_info,
                    periodo_envio = 'LOTE_04/2027 (Abril)',
                    status_assinatura = CASE 
                        WHEN (COALESCE(exemplares_entregues, 0) + 3) >= COALESCE(total_exemplares_contratados, 12) THEN 'CONCLUIDO'
                        ELSE 'ATIVO'
                    END
                WHERE sku_produto = '000223' OR periodo_envio LIKE '%LOTE_01%' OR periodo_envio LIKE '%Jan-Mar%'
            """
            db.executar_query(sql_upd, {"lote_info": f"{nome_lote} em {agora_str}"}, is_select=False)

            # 2. Registrar no histórico de lotes
            db.executar_query("""
                CREATE TABLE IF NOT EXISTS assinaturas_lotes_historico (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome_lote TEXT,
                    data_conclusao TEXT,
                    observacoes TEXT
                )
            """, is_select=False)

            db.executar_query("""
                INSERT INTO assinaturas_lotes_historico (nome_lote, data_conclusao, observacoes)
                VALUES (:nome, :dt, :obs)
            """, {"nome": nome_lote, "dt": agora_str, "obs": "Lote concluído. Assinantes com 12 exemplares finalizados e os demais avançados para o Lote de Abril/2027."}, is_select=False)

            self._send_json({
                "success": True,
                "message": f"{nome_lote} finalizado com sucesso! As liturgias entregues foram marcadas, os ciclos foram avançados para Abril/2027 e as assinaturas completas foram concluídas."
            })
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao concluir lote: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_assinaturas_cadastrar_pedido_proximo_envio(self):
        try:
            body = self._read_body()
            num_pedido = str(body.get("numero_pedido") or "").strip()
            cliente_nome = str(body.get("cliente_nome") or "").strip()
            cpf_cnpj = str(body.get("cpf_cnpj") or "").strip()
            qtd_ass = int(body.get("quantidade_assinaturas") or 1)
            periodo = str(body.get("periodo_envio") or "Próximo Lote 2027").strip()
            obs = str(body.get("observacao") or "").strip()

            if num_pedido and not cliente_nome:
                from omie_client import OmieClient
                cli_omie = OmieClient("MATRIZ")
                res_pv = cli_omie.executar("produtos/pedido/", "ConsultarPedido", [{"numero_pedido": num_pedido}])
                cab = res_pv.get("pedido_venda_produto", {}).get("cabecalho", {})
                cod_cli = cab.get("codigo_cliente", 0)
                if cod_cli:
                    res_c = cli_omie.executar("geral/clientes/", "ConsultarCliente", [{"codigo_cliente_omie": cod_cli}])
                    cliente_nome = res_c.get("nome_fantasia") or res_c.get("razao_social") or ""
                    cpf_cnpj = res_c.get("cnpj_cpf") or ""
                    body["rua"] = res_c.get("endereco") or ""
                    body["numero"] = res_c.get("endereco_numero") or ""
                    body["complemento"] = res_c.get("complemento") or ""
                    body["bairro"] = res_c.get("bairro") or ""
                    body["cidade"] = res_c.get("cidade") or ""
                    body["uf"] = res_c.get("estado") or ""
                    body["cep"] = res_c.get("cep") or ""
                    body["codigo_cliente_omie"] = cod_cli
                    body["codigo_pedido_omie"] = cab.get("codigo_pedido", 0)

            sql_ins = """
                INSERT INTO assinaturas_pedidos_proximo_envio (
                    numero_pedido, codigo_pedido_omie, codigo_cliente_omie,
                    cliente_nome, cpf_cnpj, rua, numero, complemento,
                    bairro, cidade, uf, cep, quantidade_assinaturas,
                    periodo_envio, observacao, criado_em
                ) VALUES (
                    :np, :cpo, :cco, :cn, :doc, :rua, :num, :comp,
                    :bairro, :cid, :uf, :cep, :qtd, :per, :obs, :agora
                )
            """
            agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.executar_query(sql_ins, {
                "np": num_pedido,
                "cpo": int(body.get("codigo_pedido_omie") or 0),
                "cco": int(body.get("codigo_cliente_omie") or 0),
                "cn": cliente_nome or "Assinante Novo",
                "doc": cpf_cnpj,
                "rua": str(body.get("rua") or ""),
                "num": str(body.get("numero") or ""),
                "comp": str(body.get("complemento") or ""),
                "bairro": str(body.get("bairro") or ""),
                "cid": str(body.get("cidade") or ""),
                "uf": str(body.get("uf") or ""),
                "cep": str(body.get("cep") or ""),
                "qtd": qtd_ass,
                "per": periodo,
                "obs": obs,
                "agora": agora_str
            }, is_select=False)

            self._send_json({"success": True, "message": f"Assinatura do pedido #{num_pedido or cliente_nome} salva para o {periodo}!"})
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao cadastrar pedido proximo envio: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_assinaturas_sincronizar_pedidos_omie(self):
        try:
            body = self._read_body()
            dias_atras = int(body.get("dias_atras") if body.get("dias_atras") is not None else 0)
            num_pedido = body.get("numero_pedido")
            res = servico_pedidos_assinaturas.sincronizar_pedidos_faturados_omie(dias_atras=dias_atras, numero_pedido_especifico=num_pedido)
            self._send_json(res)
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao sincronizar pedidos Omie: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)


    def handle_api_assinaturas_excluir_pedido_proximo_envio(self):
        try:
            body = self._read_body()
            pedido_id = int(body.get("id") or 0)
            if not pedido_id:
                self._send_json({"success": False, "message": "ID não informado"}, status=400)
                return
            db.executar_query("DELETE FROM assinaturas_pedidos_proximo_envio WHERE id = :id", {"id": pedido_id}, is_select=False)
            self._send_json({"success": True, "message": f"Registro #{pedido_id} excluído com sucesso."})
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao excluir pedido proximo envio: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_assinaturas_lancar_pedido_venda_omie(self):
        try:
            body = self._read_body()
            from services.pedidos_assinaturas import PedidosAssinaturasService
            service = PedidosAssinaturasService()
            res = service.lancar_pedido_venda_omie(body)
            self._send_json(res)
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao lancar pedido de venda Omie: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_assinaturas_metadados(self):
        try:
            from services.pedidos_assinaturas import PedidosAssinaturasService
            service = PedidosAssinaturasService()
            res = service.obter_metadados()
            self._send_json(res)
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao obter metadados: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_assinaturas_buscar_clientes(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            q = (qs.get("q", [""])[0] or qs.get("termo", [""])[0]).strip()
            from services.pedidos_assinaturas import PedidosAssinaturasService
            service = PedidosAssinaturasService()
            clientes = service.buscar_clientes_omie(q)
            self._send_json({"success": True, "clientes": clientes})
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao buscar clientes Omie: {e}")
            self._send_json({"success": False, "message": str(e)}, status=500)

    def handle_api_frenet_cotar(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            cep = qs.get("cep", [""])[0].strip()
            valor = float(qs.get("valor", [45.0])[0])
            peso = float(qs.get("peso", [0.3])[0])
            from services.frenet_service import cotar_frete_frenet
            res = cotar_frete_frenet(cep, valor_itens=valor, peso_kg=peso)
            self._send_json(res)
        except Exception as e:
            print(f"[API FRENET] Erro ao cotar frete: {e}")
            self._send_json({"disponivel": False, "message": str(e)}, status=500)

    # =========================================================================
    # MÓDULO 3: ASSINATURAS PÃO DA VIDA (LITURGIA DIÁRIA)
    # =========================================================================
    def handle_api_assinaturas_dados(self):
        try:
            from services import assinaturas_service
            dados = assinaturas_service.processar_assinaturas_pdv(forcar_download=False)
            self._send_json(dados)
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao carregar dados: {e}")
            self._send_json({"sucesso": False, "erro": str(e)}, status=500)

    def handle_api_assinaturas_sincronizar(self):
        try:
            from services import assinaturas_service
            res_sync = assinaturas_service.sincronizar_planilha()
            dados = assinaturas_service.processar_assinaturas_pdv(forcar_download=False)
            dados["mensagem_sync"] = res_sync.get("mensagem") or res_sync.get("aviso")
            self._send_json(dados)
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao sincronizar: {e}")
            self._send_json({"sucesso": False, "erro": str(e)}, status=500)

    def handle_api_assinaturas_exportar_etiquetas(self):
        try:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            grupo = qs.get("grupo", ["paroquias_ce"])[0]
            from services import assinaturas_service
            excel_bytes = assinaturas_service.gerar_excel_etiquetas(grupo)
            self.send_response(200)
            self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.send_header('Content-Disposition', f'attachment; filename="etiquetas_{grupo}.xlsx"')
            self.send_header('Content-Length', str(len(excel_bytes)))
            self.end_headers()
            self.wfile.write(excel_bytes)
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao exportar etiquetas: {e}")
            self._send_json({"sucesso": False, "erro": str(e)}, status=500)

    def handle_api_assinaturas_exportar_correios(self):
        try:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            grupo = qs.get("grupo", ["finais_modico_brasil"])[0]
            formato = qs.get("formato", ["csv"])[0].lower()
            from services import assinaturas_service
            arquivo_bytes = assinaturas_service.gerar_arquivo_correios(grupo, formato=formato)
            self.send_response(200)
            if formato == "xlsx":
                self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                self.send_header('Content-Disposition', f'attachment; filename="correios_{grupo}.xlsx"')
            else:
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Disposition', f'attachment; filename="correios_{grupo}.csv"')
            self.send_header('Content-Length', str(len(arquivo_bytes)))
            self.end_headers()
            self.wfile.write(arquivo_bytes)
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao exportar Correios: {e}")
            self._send_json({"sucesso": False, "erro": str(e)}, status=500)

    def handle_api_assinaturas_relatorio_pdf(self):
        try:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            grupo = qs.get("grupo", ["finais_fortaleza"])[0]
            linha = qs.get("linha", [None])[0]
            from services import assinaturas_service
            pdf_bytes = assinaturas_service.gerar_pdf_relatorio_grupo(grupo, linha=linha)
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            nome_arq = f"romaneio_remessa_linha_{linha}.pdf" if linha else f"romaneio_separacao_{grupo}.pdf"
            self.send_header('Content-Disposition', f'inline; filename="{nome_arq}"')
            self.send_header('Content-Length', str(len(pdf_bytes)))
            self.end_headers()
            self.wfile.write(pdf_bytes)
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao gerar PDF: {e}")
            self._send_json({"sucesso": False, "erro": str(e)}, status=500)

    def handle_api_assinaturas_gerar_remessa_baixa(self):
        try:
            body = self._read_body()
            grupo_id = body.get("grupo_id")
            if not grupo_id:
                self._send_json({"sucesso": False, "erro": "Parâmetro 'grupo_id' é obrigatório."}, status=400)
                return
            from services import assinaturas_service
            res = assinaturas_service.gerar_remessa_baixa_omie(grupo_id)
            self._send_json(res)
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao gerar remessa baixa: {e}")
            self._send_json({"sucesso": False, "erro": str(e)}, status=500)

    def handle_api_assinaturas_gerar_remessa_paroquia(self):
        try:
            body = self._read_body()
            cliente_dados = body.get("cliente")
            valor_frete = body.get("valor_frete")
            transportadora_id = body.get("transportadora_id")
            if not cliente_dados:
                self._send_json({"sucesso": False, "erro": "Parâmetro 'cliente' é obrigatório."}, status=400)
                return
            from services import assinaturas_service
            res = assinaturas_service.gerar_remessa_paroquia_omie(cliente_dados, valor_frete, transportadora_id)
            self._send_json(res)
        except Exception as e:
            print(f"[API ASSINATURAS] Erro ao gerar remessa paróquia: {e}")
            self._send_json({"sucesso": False, "erro": str(e)}, status=500)



import threading
import time

def _iniciar_agendador_seguro():
    """
    Agendador Automático e Seguro do DRP:
    1. 05:00 da manhã: Sincronização matinal de estoque (Matriz + CD_SP) antes do início do expediente.
    2. 18:30 da noite: Sincronização prévia de estoque (Matriz + CD_SP) seguida imediatamente pelo disparo do e-mail de alertas diários com dados frescos.
    3. A cada 1 hora durante o dia (entre 07:00 e 18:00): Sincronização LEVE de posição de estoque (rápida, direta, sem sobrecarregar a API Omie).
    """
    def _loop_agendador():
        ultimo_dia_05h = ""
        ultimo_dia_1830 = ""
        ultimo_sync_horario = time.time()  # Inicializa contagem horária a partir de agora

        print("[AGENDADOR SEGURO] Agendador iniciado com sucesso! Horários: 05:00 (Matinal), 18:30 (Noturno c/ E-mail) e Atualização Leve de Estoque a cada 1 hora.", flush=True)

        while True:
            time.sleep(30)  # Checa a cada 30 segundos
            agora = datetime.now()
            dia_str = agora.strftime("%Y-%m-%d")
            hora = agora.hour
            minuto = agora.minute

            # A. Sincronização matinal das 05:00 hrs (antes do expediente)
            if hora == 5 and minuto <= 10 and ultimo_dia_05h != dia_str:
                ultimo_dia_05h = dia_str
                try:
                    print(f"[AGENDADOR SEGURO] 05:00 - Executando sincronização matinal completa de estoque (Matriz + CD_SP)...", flush=True)
                    import sync_service
                    sync_service.sincronizar_dados_seletivo("AMBOS_ESTOQUES")
                    if db:
                        db.carregar_produtos_cache(force_refresh=True)
                    print(f"[AGENDADOR SEGURO] 05:00 - Estoques atualizados com sucesso para o início do expediente!", flush=True)
                except Exception as e:
                    print(f"[AGENDADOR SEGURO] Erro na sincronização das 05:00: {e}", flush=True)

            # B. Sincronização noturna das 18:30 hrs + Disparo do E-mail Diário de Alertas
            elif hora == 18 and minuto >= 30 and minuto <= 45 and ultimo_dia_1830 != dia_str:
                ultimo_dia_1830 = dia_str
                try:
                    print(f"[AGENDADOR SEGURO] 18:30 - Sincronizando estoque prévio para envio do e-mail diário...", flush=True)
                    import sync_service
                    sync_service.sincronizar_dados_seletivo("AMBOS_ESTOQUES")
                    if db:
                        db.carregar_produtos_cache(force_refresh=True)
                    print(f"[AGENDADOR SEGURO] 18:30 - Estoque sincronizado. Disparando relatório por e-mail...", flush=True)
                    
                    import alertas_email
                    if alertas_email:
                        import importlib
                        importlib.reload(alertas_email)
                        ok_mail, msg_mail = alertas_email.enviar_email_alerta()
                        print(f"[AGENDADOR SEGURO] 18:30 - E-mail diário enviado: {ok_mail} ({msg_mail})", flush=True)
                except Exception as e:
                    print(f"[AGENDADOR SEGURO] Erro no fluxo das 18:30: {e}", flush=True)

            # C. Sincronização LEVE de posição de estoque a cada 1 hora durante o dia (entre 07:00 e 18:00)
            elif 7 <= hora <= 18 and (time.time() - ultimo_sync_horario) >= 3600:
                # Não roda entre 18:20 e 18:45 para não colidir com a rotina oficial das 18:30
                if hora == 18 and minuto >= 20:
                    continue
                ultimo_sync_horario = time.time()
                try:
                    agora_txt = agora.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[AGENDADOR SEGURO] {agora_txt} - Executando sincronização LEVE de posição de estoque (horária)...", flush=True)
                    import sync_service
                    sync_service.sincronizar_dados_seletivo("ESTOQUE_LEVE")
                    if db:
                        db.carregar_produtos_cache(force_refresh=True)
                    print(f"[AGENDADOR SEGURO] Sincronização leve de estoque concluída com sucesso!", flush=True)
                except Exception as e:
                    print(f"[AGENDADOR SEGURO] Erro na sincronização leve horária: {e}", flush=True)

    t = threading.Thread(target=_loop_agendador, daemon=True)
    t.start()

from http.server import ThreadingHTTPServer

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if db:
        try:
            db.inicializar_banco()
            print("[DRP SERVER] Banco de dados inicializado com sucesso.")
        except Exception as e:
            print(f"[DRP SERVER] Erro ao inicializar banco: {e}")
            
    port = PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            port = PORT

    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = ThreadingHTTPServer(("", port), DRPRequestHandler)
    except Exception as e:
        print(f"[DRP SERVER] Porta {port} bloqueada: {e}. Tentando reiniciar socket...")
        time.sleep(1)
        httpd = ThreadingHTTPServer(("", port), DRPRequestHandler)

    print("===========================================================", flush=True)
    print(f"[DRP SERVER] Servidor Backend Rodando em: http://localhost:{port}", flush=True)
    print(f"[DRP SERVER] Endpoint Email: http://localhost:{port}/api/email", flush=True)
    print(f"[DRP SERVER] Endpoint Sync:  http://localhost:{port}/api/sync", flush=True)
    print("===========================================================", flush=True)
    
    # Inicia o Agendador Automático e Seguro
    _iniciar_agendador_seguro()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[DRP SERVER] Servidor encerrado pelo usuário.")
        httpd.server_close()

if __name__ == "__main__":
    main()
