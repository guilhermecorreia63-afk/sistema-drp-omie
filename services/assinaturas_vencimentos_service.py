import sys, os
sys.path.insert(0, os.path.abspath('.'))
import json
import re
from typing import Dict, Any, List
import database as db
from services.assinaturas_service import processar_assinaturas_pdv, carregar_workbook_assinaturas
from services.pedidos_assinaturas import PedidosAssinaturasService

def normalizar_telefone(tel_str: str) -> str:
    """Extrai dígitos do telefone e retorna no formato internacional 55DDDNUMERO para WhatsApp."""
    if not tel_str:
        return ""
    digits = re.sub(r'\D', '', str(tel_str))
    # Caso contenha DDD duplicado ex: 2121986905150 (13 digitos)
    if len(digits) == 13 and digits[:2] == digits[2:4]:
        digits = digits[2:] # vira 21986905150
    # Caso contenha DDI 55
    if len(digits) in [10, 11]:
        return "55" + digits
    elif len(digits) in [12, 13] and digits.startswith("55"):
        return digits
    return digits

def obter_contatos_assinantes_cache() -> Dict[str, Dict[str, str]]:
    """Carrega mapa de contatos {cpf_cnpj_limpo: {telefone, email}} do cache."""
    try:
        df = db.executar_query("SELECT cpf_cnpj, telefone, email FROM assinantes_contatos_cache")
        if df is not None and not df.empty:
            cache = {}
            for _, r in df.iterrows():
                cpf_limpo = re.sub(r'\D', '', str(r['cpf_cnpj'] or ""))
                if cpf_limpo:
                    cache[cpf_limpo] = {
                        "telefone": str(r['telefone'] or "").strip(),
                        "email": str(r['email'] or "").strip()
                    }
            return cache
    except Exception as e:
        print(f"Erro ao ler assinantes_contatos_cache: {e}")
    return {}

def salvar_contato_assinante(cpf_cnpj: str, telefone: str = "", email: str = "", nome: str = "", cod_omie: int = 0):
    """Salva ou atualiza telefone/email de um assinante no cache Turso."""
    try:
        cpf_limpo = re.sub(r'\D', '', str(cpf_cnpj))
        db.executar_query(
            """INSERT INTO assinantes_contatos_cache (cpf_cnpj, codigo_cliente_omie, nome, telefone, email, atualizado_em)
               VALUES (:cpf, :cod, :nome, :tel, :email, CURRENT_TIMESTAMP)
               ON CONFLICT(cpf_cnpj) DO UPDATE SET
               telefone = excluded.telefone,
               email = excluded.email,
               atualizado_em = CURRENT_TIMESTAMP""",
            {"cpf": cpf_limpo, "cod": cod_omie, "nome": nome, "tel": telefone, "email": email}
        )
        return True
    except Exception as e:
        print(f"Erro ao salvar contato cache: {e}")
        return False

def buscar_contato_omie_por_cpf(cpf_cnpj: str) -> Dict[str, str]:
    """Consulta o Omie ERP para obter telefone e e-mail via ListarClientes com filtro por CPF/CNPJ."""
    if not cpf_cnpj:
        return {"telefone": "", "email": ""}
    
    cpf_limpo = re.sub(r'\D', '', str(cpf_cnpj))
    try:
        s = PedidosAssinaturasService()
        formatos = [cpf_cnpj]
        if len(cpf_limpo) == 11:
            formatos.append(f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}")
        elif len(cpf_limpo) == 14:
            formatos.append(f"{cpf_limpo[:2]}.{cpf_limpo[2:5]}.{cpf_limpo[5:8]}/{cpf_limpo[8:12]}-{cpf_limpo[12:]}")
        formatos.append(cpf_limpo)

        for fmt in set(formatos):
            res = s.client.executar("geral/clientes/", "ListarClientes", [{
                "pagina": 1,
                "registros_por_pagina": 1,
                "clientesFiltro": {"cnpj_cpf": fmt}
            }])
            cad = res.get("clientes_cadastro", [])
            if cad:
                c = cad[0]
                ddd = str(c.get("telefone1_ddd") or "").strip()
                num = str(c.get("telefone1_numero") or "").strip()
                
                # Trata formatação limpa do telefone
                if num.startswith("(") and ")" in num:
                    tel_final = num
                elif ddd:
                    tel_final = f"({ddd}) {num}".strip()
                else:
                    tel_final = num

                email_final = str(c.get("email") or "").strip()
                nome = c.get("razao_social") or c.get("nome_fantasia") or ""
                cod_omie = int(c.get("codigo_cliente_omie") or 0)

                salvar_contato_assinante(cpf_limpo, tel_final, email_final, nome, cod_omie)
                return {"telefone": tel_final, "email": email_final}
    except Exception as e:
        print(f"Erro ao buscar contato Omie para {cpf_cnpj}: {e}")

    return {"telefone": "", "email": ""}

def carregar_lista_vencimentos_pdv(filtro_status: str = "todos") -> Dict[str, Any]:
    """
    Retorna assinantes classificados por:
    - CONCLUI_LOTE: Conclui o ciclo de 12 meses neste lote de envio (0 meses restantes após lote, ex: 12/12)
    - VENCENDO: 1 a 3 meses restantes após este lote (vence nos próximos envios de 2027)
    - ATIVO: 4 ou mais meses restantes após este lote (contratos em andamento / recentes)
    """
    contatos_cache = obter_contatos_assinantes_cache()

    # 1. Obter assinantes do lote atual (444 assinantes ativos de Jan, Fev, Mar 2027)
    dados_pdv = processar_assinaturas_pdv(forcar_download=False)
    todos_lote = []
    for grp_key in dados_pdv.get("grupos", {}):
        todos_lote.extend(dados_pdv["grupos"][grp_key].get("clientes", []))

    resultado = []
    seen_cpfs = set()

    for c in todos_lote:
        cpf = str(c.get("cpf_cnpj") or "").strip()
        cpf_limpo = re.sub(r'\D', '', cpf)
        if not cpf_limpo or cpf_limpo in seen_cpfs:
            continue
        seen_cpfs.add(cpf_limpo)

        qtd_ass = int(c.get("quantidade_assinaturas", 1) or 1)
        if qtd_ass <= 0:
            qtd_ass = 1

        # Obter dados de ciclos
        ci = c.get("ciclos_info") or {}
        
        # ja_recebidos e restantes em número de meses/ciclos
        if c.get("ja_recebidos_antes") is not None:
            meses_ja_recebidos = int(c.get("ja_recebidos_antes", 0))
        elif ci.get("ja_recebidos") is not None:
            meses_ja_recebidos = int(ci.get("ja_recebidos")) // qtd_ass
        else:
            meses_ja_recebidos = 0

        if c.get("restantes_apos_lote") is not None:
            meses_restantes = int(c.get("restantes_apos_lote", 0))
        elif ci.get("restantes_futuros") is not None:
            meses_restantes = int(ci.get("restantes_futuros")) // qtd_ass
        else:
            meses_restantes = 0

        # Meses entregues neste lote atual (Lote 1: Jan, Fev, Mar)
        meses_neste_lote = (1 if c.get("jan27") else 0) + (1 if c.get("fev27") else 0) + (1 if c.get("mar27") else 0) + (1 if c.get("qtd_dez26_extra", 0) > 0 else 0)
        ciclo_atual_mes = min(12, meses_ja_recebidos + meses_neste_lote)

        # Contato do cache ou do próprio objeto
        contato = contatos_cache.get(cpf_limpo, {})
        tel = contato.get("telefone") or c.get("telefone") or ""
        email = contato.get("email") or c.get("email") or ""

        # Classificação correta das 3 categorias de assinantes ativos no envio:
        # 1. CONCLUI_LOTE (0 restantes após o envio atual) -> ex: Paróquia São Pio de Pietrelcina (recebe 12/12)
        # 2. VENCENDO (1 a 3 restantes após o envio atual) -> precisará renovar no próximo trimestre
        # 3. ATIVO (4 ou mais restantes após o envio atual) -> Rosangela e outros com ciclo longo restante
        if meses_restantes == 0:
            st = "CONCLUI_LOTE"
            label = "🏁 Conclui no Lote Atual (12/12)"
            badge_class = "danger"
            status_desc = "Contrato encerra com este envio (12 de 12 exemplares entregues). Entrar em contato para renovação imediata!"
        elif meses_restantes in [1, 2, 3]:
            st = "VENCENDO"
            label = f"⚠️ Vencendo em Breve ({meses_restantes} restante{'s' if meses_restantes > 1 else ''})"
            badge_class = "warning"
            status_desc = f"Faltam {meses_restantes} exemplar(es) após este lote para completar os 12 meses."
        else:
            st = "ATIVO"
            label = f"✅ Em Andamento ({meses_restantes} restantes)"
            badge_class = "success"
            status_desc = f"Assinatura em andamento com {meses_restantes} exemplares futuros restantes."

        # Mensagem WhatsApp personalizada
        primeiro_nome = (c.get("cliente") or "").split()[0].title()
        if st == "CONCLUI_LOTE":
            msg_wpp = (
                f"Olá {primeiro_nome}! Graça e paz! Aqui é das Edições Shalom. "
                f"Sua assinatura da Liturgia Diária Pão da Vida está concluindo o ciclo de 12 meses agora no Lote de Jan/Fev/Mar 2027. "
                f"Podemos preparar a renovação da sua assinatura para garantir os próximos meses sem interrupção?"
            )
        elif st == "VENCENDO":
            msg_wpp = (
                f"Olá {primeiro_nome}! Graça e paz! Aqui é das Edições Shalom. "
                f"Sua assinatura da Liturgia Diária Pão da Vida está chegando aos últimos meses ({meses_restantes} exemplar(es) restante(s)). "
                f"Gostaria de antecipar a renovação para continuar recebendo com tranquilidade?"
            )
        else:
            msg_wpp = (
                f"Olá {primeiro_nome}! Graça e paz! Aqui é das Edições Shalom. "
                f"Passando para avisar que o seu envio de Jan, Fev e Mar/2027 da Liturgia Diária Pão da Vida foi preparado com sucesso!"
            )

        tel_wpp = normalizar_telefone(tel)

        item = {
            "id": c.get("codigo_cliente") or c.get("linha_planilha"),
            "cliente": c.get("cliente"),
            "cpf_cnpj": cpf,
            "cpf_limpo": cpf_limpo,
            "telefone": tel,
            "telefone_wpp": tel_wpp,
            "link_whatsapp": f"https://wa.me/{tel_wpp}?text={re.sub(r' ', '%20', msg_wpp)}" if (tel_wpp and len(tel_wpp) >= 10) else None,
            "email": email,
            "cidade": c.get("cidade"),
            "uf": c.get("uf"),
            "quantidade_assinaturas": qtd_ass,
            "ja_recebidos": meses_ja_recebidos,
            "neste_lote": meses_neste_lote,
            "ciclo_atual_mes": ciclo_atual_mes,
            "restantes": meses_restantes,
            "status_vencimento": st,
            "status_label": label,
            "status_desc": status_desc,
            "badge_class": badge_class,
            "tipo_envio": c.get("tipo_envio", "Correios"),
            "origem": c.get("origem_pedido_omie") and f"Pedido Omie #{c.get('origem_pedido_omie')}" or "Planilha Envios PDV"
        }

        if filtro_status == "todos" or filtro_status.upper() == st:
            resultado.append(item)

    # Ordena: CONCLUI_LOTE primeiro (mais urgente para contato), depois VENCENDO, depois ATIVO
    ordem_status = {"CONCLUI_LOTE": 1, "VENCENDO": 2, "ATIVO": 3}
    resultado.sort(key=lambda x: (ordem_status.get(x["status_vencimento"], 9), x["restantes"], x["cliente"]))

    totais = {
        "total": len(resultado) if filtro_status == "todos" else len(todos_lote),
        "conclui_lote": sum(1 for r in resultado if r["status_vencimento"] == "CONCLUI_LOTE") if filtro_status != "todos" else sum(1 for r in todos_lote if r.get("restantes_apos_lote") == 0),
        "vencendo": sum(1 for r in resultado if r["status_vencimento"] == "VENCENDO") if filtro_status != "todos" else sum(1 for r in todos_lote if r.get("restantes_apos_lote") in [1, 2, 3]),
        "ativos": sum(1 for r in resultado if r["status_vencimento"] == "ATIVO") if filtro_status != "todos" else sum(1 for r in todos_lote if (r.get("restantes_apos_lote") or 0) > 3)
    }

    return {"success": True, "totais": totais, "assinantes": resultado}
