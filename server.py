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
        else:
            super().do_GET()

    def do_POST(self):
        url_path = self.path.split('?')[0].rstrip('/')
        if url_path == '/api/cron_sync':
            self.handle_api_cron_sync()
        elif url_path == '/api/email':
            self.handle_api_email()
        elif url_path == '/api/sync':
            self.handle_api_sync()
        elif url_path in ['/api/producao', '/api/producao/salvar']:
            self.handle_api_producao_save()
        elif url_path == '/api/blacklist' or url_path == '/api/blacklist/salvar':
            self.handle_api_blacklist_save()
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
                if id_produto and str(id_produto).isdigit():
                    ncod_prod = int(id_produto)
                else:
                    res_prod = client.executar('geral/produtos/', 'ConsultarProduto', [{'codigo': sku}])
                    if res_prod and 'codigo_produto' in res_prod:
                        ncod_prod = res_prod['codigo_produto']

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
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'producao_status.json')
        producao_skus = []
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
        else:
            try:
                import database as db_mod
                st_map = db_mod.obter_status_producao()
                producao_skus = [k for k, v in st_map.items() if v]
            except Exception:
                producao_skus = []

        self._send_json({"success": True, "producao": producao_skus})

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

        num_pedido_target = str(body.get('numero_pedido', '')).strip()

        if os.path.exists(prods_json_path):
            try:
                with open(prods_json_path, 'r', encoding='utf-8') as f:
                    produtos = json.load(f)
                
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
                        # Atualiza o próprio SKU ou todos os SKUs que compartilham o mesmo numero_pedido
                        if (sku and p_sku == sku) or (num_pedido_target and p_ped == num_pedido_target):
                            p['data_previsao'] = data_previsao

                with open(prods_json_path, 'w', encoding='utf-8') as f:
                    json.dump(produtos, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[API SERVER] Erro ao atualizar produtos_turso.json: {e}")

        try:
            import database as db_mod
            if num_pedido_target and data_previsao is not None:
                # Salva no Turso DB para todos os SKUs do pedido
                for p in produtos:
                    p_sku = str(p.get('sku', '')).strip()
                    p_ped = str(p.get('numero_pedido', '')).strip()
                    if p_ped == num_pedido_target:
                        db_mod.salvar_status_producao(p_sku, True, data_previsao=data_previsao, numero_pedido=num_pedido_target)
            elif sku:
                db_mod.salvar_status_producao(sku, bool(em_producao), data_previsao=data_previsao, numero_pedido=num_pedido_target)
        except Exception as e:
            print(f"[API SERVER] Aviso Turso DB status producao: {e}")

        self._send_json({
            "success": True,
            "message": "Status de produção salvo com sucesso!",
            "producao": producao_lista
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
                    rid = str(c.get('nCodRem') or c.get('cNumeroRemessa') or r.get('remessa_id') or '')
                    if rid and r.get('status_transito'):
                        status_map[rid] = r.get('status_transito')
            except Exception:
                pass

        self._send_json({"success": True, "status_map": status_map})

    def handle_api_remessas_status_transito_save(self):
        body = self._read_body()
        remessa_id = str(body.get('remessa_id') or body.get('nCodRem') or body.get('cNumeroRemessa') or '').strip()
        novo_status = body.get('status_transito', 'PENDENTE')
        
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'status_remessas.json')
        status_map = {}
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    status_map = json.load(f)
            except Exception:
                status_map = {}
                
        if remessa_id:
            status_map[remessa_id] = novo_status
            if db:
                try:
                    db.atualizar_status_transito_db(remessa_id, novo_status)
                except Exception as ex:
                    print(f"[API SERVER] Erro ao atualizar status no banco: {ex}")
            
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(status_map, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[API SERVER] Erro ao salvar status_remessas.json: {e}")
            
        self._send_json({"success": True, "remessa_id": remessa_id, "status_transito": novo_status, "status_map": status_map})

    def handle_api_cron_sync(self):
        """
        Endpoint do Cron Job Automático (12h20 e 18h30 - Horário de Fortaleza / UTC-3).
        Sincroniza estoques e vendas, atualiza alertas e dispara o e-mail automático.
        """
        query = parse_qs(urlparse(self.path).query)
        force = query.get('force', ['false'])[0].lower() in ['true', '1', 'sim']

        lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'cron_lock.json')
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
            # A. Sincronização completa Omie / Turso
            import sync_service
            ok_sync, msg_sync, count_sync = sync_service.sincronizar_dados_seletivo("TUDO")
            print(f"[CRON API] Sync finalizado: ok={ok_sync}, msg={msg_sync}, prods={count_sync}", flush=True)

            # B. Disparo do e-mail de alerta automático
            import alertas_email
            if alertas_email:
                import importlib
                importlib.reload(alertas_email)
                ok_email, msg_email = alertas_email.enviar_email_alerta()
            else:
                ok_email, msg_email = False, "Módulo alertas_email não disponível."

            print(f"[CRON API] Disparo e-mail finalizado: ok={ok_email}, msg={msg_email}", flush=True)

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

    def handle_api_requisicao_compra(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        
        try:
            body = json.loads(post_data.decode('utf-8'))
        except Exception:
            body = {}

        itens = body.get('itens', [])
        cod_categ = body.get('codCateg', '2.04.06')
        dt_sugestao = body.get('dtSugestao', datetime.now().strftime("%d/%m/%Y"))
        obs = body.get('obsReqCompra', 'Requisição de Compra gerada pelo DRP Omie ERP')

        print(f"[API SERVER] Recebida solicitação de Requisição de Compra no Omie para {len(itens)} itens.")

        try:
            from omie_client import OmieClient
            client = OmieClient("MATRIZ")
            
            # Carrega mapeamento de produtos
            produtos_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')
            sku_map = {}
            if os.path.exists(produtos_json_path):
                with open(produtos_json_path, 'r', encoding='utf-8') as f:
                    prods = json.load(f)
                    for p in prods:
                        s = str(p.get('sku', '')).strip()
                        if s:
                            sku_map[s] = p.get('id_produto')

            itens_req = []
            nao_encontrados = []

            for item in itens:
                sku = str(item.get('sku') or item.get('codigo_produto') or item.get('codigo_item_integracao') or '').strip()
                qtd = float(item.get('quantidade') or item.get('qtde') or 1)
                preco = float(item.get('valor_unitario') or item.get('precoUnit') or 10.0)

                cod_prod = sku_map.get(sku)
                if not cod_prod:
                    # Tenta consultar no Omie se não achou no JSON local
                    resp_prod = client.executar("geral/produtos/", "ConsultarProduto", [{"codigo_produto_integracao": sku}])
                    if "codigo_produto" in resp_prod:
                        cod_prod = resp_prod["codigo_produto"]
                    else:
                        resp_prod = client.executar("geral/produtos/", "ConsultarProduto", [{"codigo": sku}])
                        if "codigo_produto" in resp_prod:
                            cod_prod = resp_prod["codigo_produto"]

                if cod_prod:
                    itens_req.append({
                        "codProd": int(cod_prod),
                        "qtde": qtd,
                        "precoUnit": preco
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
            kit = client.executar('geral/produtos/', 'ConsultarProduto', [{'codigo': sku}])
            if not kit or 'codigo_produto' not in kit:
                self._send_json({"success": False, "message": f"Kit SKU {sku} não encontrado no Omie ERP."})
                return

            ncod_kit = kit['codigo_produto']
            desc_kit = kit.get('descricao', '')
            valor_venda = float(kit.get('valor_unitario') or 0.0)
            comps_raw = kit.get('componentes_kit') or []

            estoques_matriz = {}
            json_turso = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'produtos_turso.json')
            if os.path.exists(json_turso):
                try:
                    with open(json_turso, 'r', encoding='utf-8') as f:
                        prods = json.load(f)
                        for p in prods:
                            sk = str(p.get('sku', '')).strip()
                            if sk:
                                estoques_matriz[sk] = int(p.get('matriz', 0))
                except Exception:
                    pass

            componentes = []
            for c in comps_raw:
                ncod_comp = c.get('codigo_produto_componente')
                cod_comp_id = c.get('codigo_componente')
                p_info = client.executar('geral/produtos/', 'ConsultarProduto', [{'codigo_produto': ncod_comp}])
                sku_comp = (p_info.get('codigo_produto_integracao') or p_info.get('codigo') or '').strip()
                desc_comp = p_info.get('descricao', '')
                
                est_matriz = estoques_matriz.get(sku_comp, 0)
                if est_matriz <= 0 and ncod_comp:
                    try:
                        est = client.executar('estoque/consulta/', 'ObterEstoqueProduto', [{'nCodProd': ncod_comp}])
                        if est and 'listaEstoque' in est and est['listaEstoque']:
                            est_matriz = int(est['listaEstoque'][0].get('saldo', 0))
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

import threading

def _iniciar_timer_sync_automatico_1h():
    def _loop_sync():
        import time
        while True:
            time.sleep(3600)  # Aguarda 1 hora entre sincronizações automáticas
            try:
                agora_txt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"[DRP BACKGROUND SYNC 1H] Sincronizando estoque dos produtos ativos em background ({agora_txt})...", flush=True)
                import sync_service
                ok, msg, count = sync_service.sincronizar_dados_seletivo("ESTOQUE_MATRIZ")
                print(f"[DRP BACKGROUND SYNC 1H] Atualização concluída com sucesso! ({count} produtos ativos).", flush=True)
            except Exception as e:
                print(f"[DRP BACKGROUND SYNC 1H] Erro ao sincronizar estoque em background: {e}", flush=True)

    t = threading.Thread(target=_loop_sync, daemon=True)
    t.start()
    print("[DRP SERVER] Agendador de sincronização automática de estoque a cada 1 hora iniciado em segundo plano.", flush=True)

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
    
    # _iniciar_timer_sync_automatico_1h()  # Desativado a pedido do usuário para evitar estouro de limite de requisições da API Omie
    print("[DRP SERVER] Sincronização automática de 1h desativada para preservar os limites de requisição da API Omie. Utilize o botão de sincronização manual quando necessário.", flush=True)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[DRP SERVER] Servidor encerrado pelo usuário.")
        httpd.server_close()

if __name__ == "__main__":
    main()
