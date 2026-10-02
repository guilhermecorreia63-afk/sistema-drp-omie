# -*- coding: utf-8 -*-
"""
app.py - Painel DRP - Controle de Reposição CD_SP / Matriz (Turso DB Integrado)
=============================================================================
Aplicação Streamlit para controle de reposição DRP, consulta em tempo real ao
banco de dados Turso (3.412+ produtos), cálculo de estoque mínimo variável,
status colorido, gestão de produção e emissão de remessas fiscais de transferência.

Idioma: Português do Brasil (PT-BR)
"""

import streamlit as st
import pandas as pd
import math
import os
from datetime import datetime

from controle_drp import (
    ControleDRP,
    CLIENTE_CNPJ,
    TRANSPORTADORA_NOME,
    TRANSPORTADORA_CNPJ,
    CFOP_REMESSA,
    TIPO_FRETE,
    ESPECIE_VOLUMES,
    DESCRICAO_FISCAL_CFOP
)
import database as db

# Configuração da Página
st.set_page_config(
    page_title="DRP Omie ERP - Matriz & CD_SP",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilização CSS Customizada (Visual Premium)
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #e0e0e0;
    }
    .metric-card {
        background-color: #1e222b;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #00d4b1;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        margin-bottom: 10px;
    }
    .badge-status {
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        color: white;
        display: inline-block;
        font-size: 0.85rem;
    }
    .badge-ruptura { background-color: #c62828; }
    .badge-alerta { background-color: #f57f17; color: black; }
    .badge-estavel { background-color: #2e7d32; }
    .badge-excesso { background-color: #0288d1; }
    .badge-producao { background-color: #9c27b0; }
    
    .stButton>button {
        border-radius: 8px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar Banco de Dados
db.inicializar_banco()

# Inicializar Controle DRP
drp = ControleDRP()

# Função Cacheada para carregar produtos do Turso
@st.cache_data(ttl=120, show_spinner="Carregando produtos do banco de dados Turso...")
def carregar_produtos_banco():
    return drp.carregar_dados_turso()

# Header Principal
st.title("📦 DRP - Controle de Reposição CD_SP & Matriz")
st.caption("Conectado ao Banco de Dados Turso Cloud (3.412+ produtos) | Omie ERP")

# Carregar dados persistidos no banco
blacklist_db = db.obter_blacklist()
producao_db = db.obter_status_producao()
sazonal_db = db.obter_sazonalidade()

# Toggle de visibilidade da sidebar
if "sidebar_visible" not in st.session_state:
    st.session_state.sidebar_visible = False

# Botão principal para mostrar/ocultar filtros
if st.button("📋 Mostrar / Ocultar Painel de Filtros", use_container_width=True):
    st.session_state.sidebar_visible = not st.session_state.sidebar_visible
    st.rerun()

# Sidebar de Filtros (condicional ao session_state)
if st.session_state.sidebar_visible:
    with st.sidebar:
        st.header("⚙️ Parâmetros do DRP")
        
        dias_historico = st.selectbox(
            "📅 Período do Histórico de Vendas",
            options=[30, 60, 90, 180],
            index=0,
            help="Seleciona o intervalo de faturamento para cálculo da média móvel diária."
        )
        
        dias_abastecimento = st.slider(
            "⏱️ Tempo de Abastecimento (Dias)",
            min_value=7,
            max_value=120,
            value=30,
            step=5,
            help="Cobertura de estoque desejada em dias."
        )
        
        st.markdown("---")
        st.subheader("🔍 Busca & Filtros")
        busca_termo = st.text_input("Buscar SKU ou Nome", placeholder="Ex: 009861 ou Chave")

        # Carregar produtos do Turso
        dados_base = carregar_produtos_banco()
        todas_familias = sorted(list(set(d["familia"] for d in dados_base if d.get("familia"))))
        
        familias_excluidas = st.multiselect(
            "Excluir Famílias",
            options=todas_familias,
            default=[f for f in todas_familias if "USO" in f.upper() or "EMBALAGEM" in f.upper()],
            help="Produtos destas famílias não serão exibidos na análise DRP."
        )
        
        # Gerenciador de Blacklist na Sidebar
        with st.expander("🖤 Gerenciar Blacklist (Itens Ocultos)"):
            # Busca dentro da blacklist para filtrar produtos
            busca_blacklist = st.text_input("🔍 Buscar SKU ou Nome para Blacklist", placeholder="Ex: 009861 ou Chave")
            # Filtrar produtos baseado na busca
            if busca_blacklist:
                termo = busca_blacklist.strip().lower()
                dados_filtrados = [d for d in dados_base if termo in d['sku'].lower() or termo in d['nome'].lower()]
            else:
                dados_filtrados = dados_base
            # Limitar a 500 para performance, mas após filtro
            todos_skus = [f"{d['sku']} - {d['nome'][:30]}" for d in dados_filtrados[:500]]
            skus_blacklist_selecionados = st.multiselect(
                "Adicionar à Blacklist:",
                options=todos_skus,
                default=[f"{d['sku']} - {d['nome'][:30]}" for d in dados_filtrados if d['sku'] in blacklist_db]
            )
            
            skus_para_salvar = set(s.split(" - ")[0] for s in skus_blacklist_selecionados)
            if skus_para_salvar != blacklist_db:
                db.salvar_blacklist(skus_para_salvar)
                blacklist_db = skus_para_salvar
                st.cache_data.clear()
                st.success("Blacklist atualizada!")

        st.markdown("---")
        if st.button("🔄 Recarregar Dados do Turso", use_container_width=True):
            st.cache_data.clear()
            st.toast("Dados do Turso recarregados!", icon="✅")
            st.rerun()
else:
    # Se sidebar oculta, ainda definir variáveis padrão para não quebrar o resto
    dias_historico = 30
    dias_abastecimento = 30
    busca_termo = ""
    familias_excluidas = []
    dados_base = carregar_produtos_banco()

# Processamento e Preparação dos Dados DRP
produtos_processados = []

termo_busca = busca_termo.strip().lower()

for prod in dados_base:
    sku = prod["sku"]
    nome = prod["nome"]
    
    # 1. Filtro de Ativos
    if not prod.get("ativo", True):
        continue
        
    # 2. Filtro de Blacklist
    if sku in blacklist_db:
        continue
        
    # 3. Filtro de Famílias
    if prod.get("familia") in familias_excluidas:
        continue

    # 4. Filtro de Busca por texto
    if termo_busca:
        if termo_busca not in sku.lower() and termo_busca not in nome.lower():
            continue

    em_prod = producao_db.get(sku, False)
    eh_saz = sazonal_db.get(sku, "SAZONAL" in nome.upper())
    
    # --- Vendas Aba 1: Sul / Sudeste ---
    key_vendas_ss = f"vendas_sul_sudeste_{dias_historico}d"
    vendas_ss = prod.get(key_vendas_ss, 0)
    est_min_cd = drp.calcular_estoque_minimo(vendas_ss, dias_historico, dias_abastecimento)
    dias_duracao_cd = drp.calcular_dias_duracao(prod["cd_sp"], vendas_ss, dias_historico)
    status_cd, cor_cd = drp.definir_status(prod["cd_sp"], est_min_cd, em_producao=em_prod)
    necessidade_cd = max(0, int(math.ceil(est_min_cd - prod["cd_sp"])))

    # --- Vendas Aba 2: Geral Brasil ---
    key_vendas_geral = f"vendas_geral_{dias_historico}d"
    vendas_geral = prod.get(key_vendas_geral, 0)
    est_min_matriz = drp.calcular_estoque_minimo(vendas_geral, dias_historico, dias_abastecimento)
    dias_duracao_matriz = drp.calcular_dias_duracao(prod["matriz"], vendas_geral, dias_historico)
    status_matriz, cor_matriz = drp.definir_status(prod["matriz"], est_min_matriz, em_producao=em_prod)
    
    produtos_processados.append({
        "sku": sku,
        "codigo": prod["codigo"],
        "nome": nome,
        "familia": prod["familia"],
        "cd_sp": prod["cd_sp"],
        "matriz": prod["matriz"],
        "peso_kg": prod["peso_kg"],
        "vendas_ss": vendas_ss,
        "vendas_geral": vendas_geral,
        "est_min_cd": est_min_cd,
        "necessidade_cd": necessidade_cd,
        "dias_duracao_cd": dias_duracao_cd,
        "status_cd": status_cd,
        "cor_cd": cor_cd,
        "est_min_matriz": est_min_matriz,
        "dias_duracao_matriz": dias_duracao_matriz,
        "status_matriz": status_matriz,
        "cor_matriz": cor_matriz,
        "em_producao": em_prod,
        "eh_sazonal": eh_saz,
    })

# Criação das Duas Abas
tab1, tab2 = st.tabs([
    "🚚 Aba 1: Reposição CD_SP (Matriz → CD_SP)",
    "🏭 Aba 2: Estoque & Produção da Matriz"
])

# ==============================================================================
# ABA 1: REPOSIÇÃO CD_SP
# ==============================================================================
with tab1:
    st.subheader("🚚 Reposição de Estoque CD_SP (Dados do Turso DB)")
    st.markdown(f"**Vendas:** Faturamento **Sul/Sudeste** nos últimos **{dias_historico} dias** | Meta Abastecimento: **{dias_abastecimento} dias** | Total carregado: **{len(produtos_processados)}** produtos.")

    # Resumo em Métricas
    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    rupturas_cd = sum(1 for p in produtos_processados if p["status_cd"] == "Ruptura")
    alertas_cd = sum(1 for p in produtos_processados if p["status_cd"] == "Alerta")
    estaveis_cd = sum(1 for p in produtos_processados if p["status_cd"] == "Estável")
    excessos_cd = sum(1 for p in produtos_processados if p["status_cd"] == "Excesso")
    producao_count = sum(1 for p in produtos_processados if p["em_producao"])

    col_m1.metric("🔴 Ruptura", rupturas_cd)
    col_m2.metric("🟡 Alerta", alertas_cd)
    col_m3.metric("🟢 Estável", estaveis_cd)
    col_m4.metric("🔵 Excesso", excessos_cd)
    col_m5.metric("🟣 Em Produção", producao_count)

    st.markdown("---")
    
    # Paginação para renderização ultra rápida
    limite_exibicao = st.slider("Exibir primeiros N produtos:", 10, 500, 50, key="limite_cd_sp")
    
    st.write(f"### Produtos para Transferência Matriz → CD_SP (Exibindo 1 até {min(limite_exibicao, len(produtos_processados))})")

    # Lista Interativa de Seleção
    itens_para_remessa = []

    for idx, item in enumerate(produtos_processados[:limite_exibicao]):
        sku = item["sku"]
        matriz_tem_estoque = item["matriz"] >= item["necessidade_cd"] and item["necessidade_cd"] > 0
        
        checked_default = matriz_tem_estoque and item["status_cd"] in ["Ruptura", "Alerta"]

        badge_class = {
            "Ruptura": "badge-ruptura",
            "Alerta": "badge-alerta",
            "Estável": "badge-estavel",
            "Excesso": "badge-excesso",
            "Em Produção": "badge-producao"
        }.get(item["status_cd"], "badge-estavel")

        col_chk, col_info, col_est, col_status, col_qtd = st.columns([0.4, 3, 2, 1.5, 1.5])
        
        with col_chk:
            selecionado = st.checkbox("Selecionar", value=checked_default, key=f"chk_remessa_{sku}", label_visibility="collapsed")
            
        with col_info:
            st.markdown(f"**{item['sku']}** - {item['nome']}")
            st.caption(f"Família: `{item['familia']}` | Vendas Sul/Sudeste ({dias_historico}d): `{item['vendas_ss']}` un")
            
        with col_est:
            st.write(f"CD_SP: **{item['cd_sp']}** | Matriz: **{item['matriz']}**")
            st.caption(f"Mínimo CD: `{item['est_min_cd']:.1f}` un | Duração: `{item['dias_duracao_cd']}` dias")
            
        with col_status:
            st.markdown(f"<span class='badge-status {badge_class}'>{item['status_cd']}</span>", unsafe_allow_html=True)
            if not matriz_tem_estoque and item["necessidade_cd"] > 0:
                st.caption("⚠️ *Matriz sem estoque suficiente*")
                
        with col_qtd:
            qtd_abastecer = st.number_input(
                "Qtd Enviar",
                min_value=0,
                max_value=max(0, int(item["matriz"])),
                value=int(item["necessidade_cd"]) if matriz_tem_estoque else 0,
                key=f"input_qtd_{sku}"
            )
            
        st.markdown("<hr style='margin: 8px 0; border-color: #262730;'/>", unsafe_allow_html=True)

        if selecionado and qtd_abastecer > 0:
            itens_para_remessa.append({
                "sku": sku,
                "nome": item["nome"],
                "qtd_abastecer": qtd_abastecer,
                "peso_kg": item["peso_kg"]
            })

    # Seção de Emissão de Remessa Fiscal
    st.markdown("---")
    st.subheader("📄 Emissão de Remessa & Cálculo de Frete")

    if itens_para_remessa:
        peso_total = sum(i["peso_kg"] * i["qtd_abastecer"] for i in itens_para_remessa)
        valor_frete, volumes, desc_faixa = drp.calcular_frete(peso_total)

        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        col_r1.metric("📦 Total de Itens", len(itens_para_remessa))
        col_r2.metric("⚖️ Peso Bruto Total", f"{peso_total:.2f} kg")
        col_r3.metric("📦 Qtd Caixas (até 16kg)", f"{volumes} VOLUMES")
        col_r4.metric("💰 Frete Estimado", f"R$ {valor_frete:.2f}")

        st.info(f"**Dados Fiscais:** CFOP `{CFOP_REMESSA}` | Cliente CNPJ `{CLIENTE_CNPJ}` | Transportadora `{TRANSPORTADORA_NOME}` (CNPJ `{TRANSPORTADORA_CNPJ}`) | Frete CIF (Tipo 0) | Faixa: `{desc_faixa}`")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("📝 Gerar Prévia do Texto Fiscal", use_container_width=True):
                texto_rem = drp.gerar_texto_remessa(itens_para_remessa)
                st.code(texto_rem, language="text")

        with c2:
            if st.button("📄 Gerar e Baixar PDF da Remessa", use_container_width=True):
                caminho_pdf = drp.gerar_pdf_remessa(itens_para_remessa, "remessa_cd_sp.pdf")
                if os.path.exists("remessa_cd_sp.pdf"):
                    with open("remessa_cd_sp.pdf", "rb") as f:
                        st.download_button(
                            label="⬇️ Download PDF Remessa",
                            data=f,
                            file_name=f"remessa_cd_sp_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    st.success("PDF da remessa gerado com sucesso!")
    else:
        st.warning("Nenhum produto selecionado com quantidade a enviar para gerar a remessa.")


# ==============================================================================
# ABA 2: ESTOQUE & PRODUÇÃO DA MATRIZ
# ==============================================================================
with tab2:
    st.subheader("🏭 Controle de Estoque & Ordem de Produção da Matriz")
    st.markdown(f"**Vendas:** Faturamento **Brasil Inteiro** nos últimos **{dias_historico} dias** | Meta Abastecimento: **{dias_abastecimento} dias** | Total carregado: **{len(produtos_processados)}** produtos.")

    # Resumo Matriz
    col_pm1, col_pm2, col_pm3, col_pm4, col_pm5 = st.columns(5)
    rupturas_mat = sum(1 for p in produtos_processados if p["status_matriz"] == "Ruptura")
    alertas_mat = sum(1 for p in produtos_processados if p["status_matriz"] == "Alerta")
    estaveis_mat = sum(1 for p in produtos_processados if p["status_matriz"] == "Estável")
    excessos_mat = sum(1 for p in produtos_processados if p["status_matriz"] == "Excesso")

    col_pm1.metric("🔴 Ruptura Matriz", rupturas_mat)
    col_pm2.metric("🟡 Alerta Matriz", alertas_mat)
    col_pm3.metric("🟢 Estável Matriz", estaveis_mat)
    col_pm4.metric("🔵 Excesso Matriz", excessos_mat)
    col_pm5.metric("🟣 Em Produção", producao_count)

    st.markdown("---")
    
    limite_exibicao_mat = st.slider("Exibir primeiros N produtos (Matriz):", 10, 500, 50, key="limite_matriz")
    st.write(f"### Painel de Produção e Sazonalidade (Exibindo 1 até {min(limite_exibicao_mat, len(produtos_processados))})")

    for item in produtos_processados[:limite_exibicao_mat]:
        sku = item["sku"]
        badge_class_mat = {
            "Ruptura": "badge-ruptura",
            "Alerta": "badge-alerta",
            "Estável": "badge-estavel",
            "Excesso": "badge-excesso",
            "Em Produção": "badge-producao"
        }.get(item["status_matriz"], "badge-estavel")

        c_info, c_est, c_status, c_prod, c_saz = st.columns([3, 2, 1.5, 1.5, 1.5])
        
        with c_info:
            st.markdown(f"**{item['sku']}** - {item['nome']}")
            st.caption(f"Família: `{item['familia']}` | Vendas Brasil ({dias_historico}d): `{item['vendas_geral']}` un")

        with c_est:
            st.write(f"Estoque Matriz: **{item['matriz']}** un")
            st.caption(f"Estoque Mínimo: `{item['est_min_matriz']:.1f}` un | Duração: `{item['dias_duracao_matriz']}` dias")

        with c_status:
            st.markdown(f"<span class='badge-status {badge_class_mat}'>{item['status_matriz']}</span>", unsafe_allow_html=True)

        with c_prod:
            em_prod_toggle = st.checkbox(
                "Em Produção 🟣",
                value=item["em_producao"],
                key=f"tgl_prod_{sku}"
            )
            if em_prod_toggle != item["em_producao"]:
                db.salvar_status_producao(sku, em_prod_toggle)
                st.cache_data.clear()
                st.rerun()

        with c_saz:
            sazonal_toggle = st.checkbox(
                "Sazonal ❄️",
                value=item["eh_sazonal"],
                key=f"tgl_saz_{sku}"
            )
            if sazonal_toggle != item["eh_sazonal"]:
                db.salvar_sazonalidade(sku, sazonal_toggle)
                st.cache_data.clear()
                st.rerun()

        st.markdown("<hr style='margin: 8px 0; border-color: #262730;'/>", unsafe_allow_html=True)
