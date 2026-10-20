/* ==========================================================================
   DRP Omie ERP - Netlify Web Application Engine (app.js)
   Lead Time por Família + 20% Estoque de Segurança + Descarte Sem Vendas
   ========================================================================== */

// Dados Fiscais de Remessa
const DADOS_FISCAIS = {
    cliente_nome: "COMUNIDADE CATOLICA SHALOM GUARULHOS MACEDO",
    cliente_cnpj: "07044456009230",
    transportadora: "TRANSLATINO",
    transportadora_cnpj: "07.655.778/0001-88",
    cfop: "6152",
    cfop_descricao: "Remessa CD portal. CFOP 6.152. Transferencia de estoque entre CD.",
    natureza: "Remessa Transferência de Estoque - entre CD",
    tipo_frete: "0 - CIF (Contratação pelo Remetente)",
    especie: "VOLUMES"
};

// Tabela de Frete Fortaleza
const FRETE_TABELA = [
    { min: 0.01, max: 2.00, valor: 11.50, desc: "1 Cx Pequena" },
    { min: 2.001, max: 6.00, valor: 20.00, desc: "1 Cx Pequena" },
    { min: 6.001, max: 10.499, valor: 25.00, desc: "1 Cx Média" },
    { min: 10.500, max: 16.499, valor: 35.00, desc: "1 Cx Grande" },
    { min: 16.500, max: 31.000, valor: 50.00, desc: "2 Cx Grandes" },
    { min: 31.500, max: 48.000, valor: 60.00, desc: "3 Cx Grandes" },
    { min: 48.500, max: 64.000, valor: 65.00, desc: "4 Cx Grandes" },
    { min: 64.500, max: 80.000, valor: 73.00, desc: "5 Cx Grandes" },
    { min: 80.500, max: 96.000, valor: 81.00, desc: "6 Cx Grandes" },
    { min: 96.500, max: 112.000, valor: 89.00, desc: "7 Cx Grandes" },
    { min: 112.500, max: 128.000, valor: 97.00, desc: "8 Cx Grandes" },
    { min: 128.500, max: 144.000, valor: 105.00, desc: "10 Cx Grandes" }
];

// Lead Times Padrão por Família (em dias)
const LEADTIME_PADRAO = {
    "CAMISAS": { cd: 20, matriz: 25 },
    "VESTUARIO": { cd: 20, matriz: 25 },
    "ICONES": { cd: 15, matriz: 20 },
    "ESPIRITUALIDADE - EDIÇÕES": { cd: 7, matriz: 15 },
    "ESPIRITUALIDADE - TERCEIRO": { cd: 7, matriz: 15 },
    "EDIÇÕES": { cd: 7, matriz: 15 },
    "LIVROS": { cd: 7, matriz: 15 },
    "BIBLIAS": { cd: 7, matriz: 15 },
    "GERAL": { cd: 7, matriz: 15 }
};

function safeGetStorage(key, fallback) {
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : fallback;
    } catch (e) {
        return fallback;
    }
}

// Estado da Aplicação
let state = {
    produtos: [],
    blacklist: new Set(safeGetStorage('drp_blacklist', [])),
    producao: new Set(safeGetStorage('drp_producao', [])),
    sazonal: new Set(safeGetStorage('drp_sazonal', [])),
    leadtimes: safeGetStorage('drp_leadtimes', LEADTIME_PADRAO),
    familiasExcluidas: new Set(['USO E CONSUMO', 'EMBALAGENS']),
    periodoDias: 30,
    abastecimentoDias: 30,
    termoBusca: '',
    // Filtros de Colunas CD_SP
    colFilterProdCD: '',
    colFilterMarcaCD: '',
    colFilterFamCD: '',
    colFilterStatusCD: '',
    // Filtros de Colunas Matriz
    colFilterProdMatriz: '',
    colFilterMarcaMatriz: '',
    colFilterFamMatriz: '',
    colFilterStatusMatriz: '',
    limiteCD: 50,
    limiteMatriz: 50,
    filtroStatusCD: null,
    filtroStatusMatriz: null,
    itensSelecionadosRemessa: {},
    skusChecadosCD: new Set(),
    skusChecadosMatriz: new Set()
};

// Inicialização
function initApp() {
    setupSidebarToggle();
    setupEventListeners();
    carregarProdutos();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

// Suporte para Ocultar/Mostrar Menu Lateral (Sidebar Toggle)
function setupSidebarToggle() {
    const container = document.getElementById('app-container');
    const isCollapsed = localStorage.getItem('drp_sidebar_collapsed') === 'true';
    if (isCollapsed) {
        container.classList.add('sidebar-collapsed');
    }

    const toggleSidebar = () => {
        container.classList.toggle('sidebar-collapsed');
        const collapsed = container.classList.contains('sidebar-collapsed');
        localStorage.setItem('drp_sidebar_collapsed', collapsed);
    };

    const btnToggle = document.getElementById('btn-toggle-sidebar');
    const btnClose = document.getElementById('btn-close-sidebar');

    if (btnToggle) btnToggle.addEventListener('click', toggleSidebar);
    if (btnClose) btnClose.addEventListener('click', toggleSidebar);
}

window.navegarParaAba = function(tabId) {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    const tabBtn = document.querySelector(`.nav-tab[data-tab="${tabId}"]`);
    if (tabBtn) tabBtn.classList.add('active');
    
    const tabContent = document.getElementById(tabId);
    if (tabContent) tabContent.classList.add('active');
    
    // Atualizar títulos
    if (tabId === 'tab-hub') {
        document.getElementById('page-heading').innerText = '🏠 Início — Hub de Operações';
        document.getElementById('page-subheading').innerHTML = 'Selecione o módulo de trabalho: <strong>DRP Matriz & CD_SP</strong> ou <strong>Controle de Consignação</strong>.';
    } else if (tabId === 'tab-cd-sp') {
        document.getElementById('page-heading').innerText = '🚚 1. Reposição de Estoque CD_SP';
        document.getElementById('page-subheading').innerHTML = 'Vendas <strong>Sul e Sudeste</strong> | Estoque Alvo: (Demanda × (Dias + LeadTime)) + 20% Seg.';
    } else if (tabId === 'tab-matriz') {
        document.getElementById('page-heading').innerText = '🏭 2. Estoque & Ordem de Produção Matriz';
        document.getElementById('page-subheading').innerHTML = 'Vendas <strong>Brasil Inteiro (Geral)</strong> | Estoque Alvo: (Demanda × (Dias + LeadTime)) + 20% Seg.';
    } else if (tabId === 'tab-remessas') {
        document.getElementById('page-heading').innerText = '📦 3. Gestão de Remessas & Trânsito CD_SP';
        document.getElementById('page-subheading').innerHTML = 'Acompanhamento de Remessas de Transferência (Matriz → CD_SP) no <strong>Omie ERP</strong>';
        carregarRemessasOmie();
    } else if (tabId === 'tab-analise-matriz') {
        document.getElementById('page-heading').innerText = '📊 4. Análise de Produtos da Matriz (Matriz BCG)';
        document.getElementById('page-subheading').innerHTML = 'Classificação em <strong>Estrela, Vaca Leiteira, Interrogação e Abacaxi</strong> com base em volume e crescimento';
        renderizarAbaAnaliseMatriz();
    } else if (tabId === 'tab-depositos-matriz') {
        document.getElementById('page-heading').innerText = '🏬 5. Depósitos da Matriz (Sub-locais)';
        document.getElementById('page-subheading').innerHTML = 'Gestão de sub-locais (Fracionado, Depósito 1, Depósito 2) e saldo <strong>A localizar</strong>';
        carregarEDesenharDepositosMatriz();
    } else if (tabId === 'tab-inteligencia-matriz') {
        document.getElementById('page-heading').innerText = '🧬 6. Inteligência de Produção & Compras (Matriz)';
        document.getElementById('page-subheading').innerHTML = 'Curva ABC por Família, Ruptura Isolada por Grade (PP..3G e A3..A7) e Avaliação de Encalhe por Lote Mínimo';
        carregarInteligenciaMatriz();
    } else if (tabId === 'tab-comite-decisao') {
        document.getElementById('page-heading').innerText = '🤝 Comitê de Decisão & Produção (Coordenação)';
        document.getElementById('page-subheading').innerHTML = 'Análise de Rupturas e Alertas com Inteligência Matriz, Meta Financeira de Terceiros e Decisão com 1 Clique';
        carregarPautaCoordenacao();
    } else if (tabId === 'tab-consignacao') {
        document.getElementById('page-heading').innerText = '🚚 Controle de Consignação (Ida e Volta)';
        document.getElementById('page-subheading').innerHTML = 'Unificação de remessas, conferência de retorno por bipagem, espelho da vendedora e integração fiscal no Omie ERP.';
        if (typeof inicializarModuloConsignacao === 'function') {
            inicializarModuloConsignacao();
        }
    } else if (tabId === 'tab-combos-kit') {
        document.getElementById('page-heading').innerText = '📦 Módulo 2 — Gestão de Combos & Kits Omie (SKU 000223)';
        document.getElementById('page-subheading').innerHTML = 'Monitoramento de componentes e automação de redefinição de valor de venda do <strong>Kit Assinatura Pão da Vida (SKU 000223)</strong>';
        carregarDetalhesCombo();
    } else if (tabId === 'tab-assinaturas') {
        document.getElementById('page-heading').innerText = '📖 Módulo 3 — Assinaturas Pão da Vida (Liturgia Diária)';
        document.getElementById('page-subheading').innerHTML = 'Lote Trimestral Chegado: <strong>Janeiro, Fevereiro e Março/2027</strong> | Elegibilidade, consolidados, etiquetas e remessas Omie.';
        if (typeof carregarAssinaturasPDV === 'function') {
            carregarAssinaturasPDV();
        }
    }
};

// Configurar Listeners de Eventos
function setupEventListeners() {
    // Tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            const tabId = tab.dataset.tab;
            window.navegarParaAba(tabId);
        });
    });

    // Helper seguro para adicionar listener
    const addListener = (id, event, handler) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener(event, handler);
    };

    // Filtros
    addListener('select-periodo', 'change', (e) => {
        state.periodoDias = parseInt(e.target.value);
        render();
    });

    addListener('range-abastecimento', 'input', (e) => {
        state.abastecimentoDias = parseInt(e.target.value);
        const valEl = document.getElementById('val-abastecimento');
        if (valEl) valEl.innerText = state.abastecimentoDias;
        render();
    });

    addListener('search-input', 'input', (e) => {
        state.termoBusca = e.target.value.toLowerCase().trim();
        render();
    });

    addListener('select-limit-cd', 'change', (e) => {
        state.limiteCD = parseInt(e.target.value);
        renderTabCD();
    });

    addListener('select-limit-matriz', 'change', (e) => {
        state.limiteMatriz = parseInt(e.target.value);
        renderTabMatriz();
    });

    // Aba 4 Listeners
    addListener('select-bcg-window', 'change', () => renderizarAbaAnaliseMatriz());
    addListener('search-analise-matriz', 'input', () => renderizarAbaAnaliseMatriz());
    addListener('filter-categoria-bcg', 'change', () => renderizarAbaAnaliseMatriz());

    // Click nos Cards BCG para filtrar a tabela diretamente
    document.querySelectorAll('.clickable-card[data-bcg-filter]').forEach(card => {
        card.addEventListener('click', () => {
            const cat = card.dataset.bcgFilter;
            const selectEl = document.getElementById('filter-categoria-bcg');
            if (selectEl) {
                if (selectEl.value === cat) {
                    selectEl.value = 'TODOS';
                } else {
                    selectEl.value = cat;
                }
                renderizarAbaAnaliseMatriz();
            }
        });
    });

    // Aba 5 Listeners
    addListener('search-depositos-matriz', 'input', () => renderizarAbaDepositosMatriz());
    addListener('filter-status-deposito', 'change', () => renderizarAbaDepositosMatriz());
    addListener('btn-recarregar-depositos', 'click', () => carregarEDesenharDepositosMatriz());
    addListener('btn-abrir-historico-transferencias', 'click', () => abrirHistoricoTransferencias());
    addListener('btn-close-historico-transferencias', 'click', () => fecharHistoricoTransferencias());
    addListener('btn-fechar-historico-transferencias', 'click', () => fecharHistoricoTransferencias());
    addListener('btn-close-transferencia', 'click', () => fecharModalTransferencia());
    addListener('btn-cancel-transferencia', 'click', () => fecharModalTransferencia());
    addListener('btn-confirm-transferencia', 'click', (e) => {
        e.preventDefault();
        confirmarTransferencia();
    });

    // Click nos Cards de Métricas (Filtro por Status)
    document.querySelectorAll('.clickable-card[data-status-filter]').forEach(card => {
        card.addEventListener('click', () => {
            const status = card.dataset.statusFilter;
            state.filtroStatusCD = state.filtroStatusCD === status ? null : status;
            render();
        });
    });

    document.querySelectorAll('.clickable-card[data-status-filter-matriz]').forEach(card => {
        card.addEventListener('click', () => {
            const status = card.dataset.statusFilterMatriz;
            state.filtroStatusMatriz = state.filtroStatusMatriz === status ? null : status;
            render();
        });
    });

    addListener('btn-clear-status-filter', 'click', () => {
        state.filtroStatusCD = null;
        render();
    });

    addListener('btn-clear-status-filter-matriz', 'click', () => {
        state.filtroStatusMatriz = null;
        render();
    });

    // Listeners de Filtros por Coluna (CD_SP)
    addListener('col-filter-prod-cd', 'input', (e) => {
        state.colFilterProdCD = e.target.value.toLowerCase().trim();
        renderTabCD();
    });
    addListener('col-filter-marca-cd', 'change', (e) => {
        state.colFilterMarcaCD = e.target.value;
        renderTabCD();
    });
    addListener('col-filter-fam-cd', 'change', (e) => {
        state.colFilterFamCD = e.target.value;
        renderTabCD();
    });
    addListener('col-filter-status-cd', 'change', (e) => {
        state.colFilterStatusCD = e.target.value || null;
        render();
    });

    // Listeners de Filtros por Coluna (Matriz)
    addListener('col-filter-prod-matriz', 'input', (e) => {
        state.colFilterProdMatriz = e.target.value.toLowerCase().trim();
        renderTabMatriz();
    });
    addListener('col-filter-marca-matriz', 'change', (e) => {
        state.colFilterMarcaMatriz = e.target.value;
        renderTabMatriz();
    });
    addListener('col-filter-fam-matriz', 'change', (e) => {
        state.colFilterFamMatriz = e.target.value;
        renderTabMatriz();
    });
    addListener('col-filter-status-matriz', 'change', (e) => {
        state.colFilterStatusMatriz = e.target.value || null;
        render();
    });

    // Checkbox selecionar todos CD_SP
    addListener('chk-select-all-cd', 'change', (e) => {
        const checked = e.target.checked;
        const produtosFiltrados = getProdutosFiltrados('cd');
        produtosFiltrados.slice(0, state.limiteCD).forEach(p => {
            const nec = calcularNecessidade(p, state.periodoDias, state.abastecimentoDias, 'cd');
            const qtdSug = (p.matriz >= nec && nec > 0) ? nec : (p.matriz > 0 ? p.matriz : 0);
            if (checked) {
                state.skusChecadosCD.add(p.sku);
                const qtdAtual = state.itensSelecionadosRemessa[p.sku] || qtdSug;
                if (qtdAtual > 0) {
                    state.itensSelecionadosRemessa[p.sku] = qtdAtual;
                }
            } else {
                state.skusChecadosCD.delete(p.sku);
                delete state.itensSelecionadosRemessa[p.sku];
            }
        });
        renderTabCD();
        atualizarPainelFrete();
    });

    // Checkbox selecionar todos Matriz
    addListener('chk-select-all-matriz', 'change', (e) => {
        const checked = e.target.checked;
        const produtosFiltrados = getProdutosFiltrados('matriz');
        produtosFiltrados.slice(0, state.limiteMatriz).forEach(p => {
            if (checked) state.skusChecadosMatriz.add(p.sku);
            else state.skusChecadosMatriz.delete(p.sku);
        });
        renderTabMatriz();
    });

    // Botões para mover para a Blacklist os itens selecionados
    addListener('btn-add-blacklist-selected', 'click', moverSelecionadosParaBlacklistCD);
    addListener('btn-add-blacklist-checked-cd', 'click', moverSelecionadosParaBlacklistCD);
    addListener('btn-add-blacklist-selected-matriz', 'click', moverSelecionadosParaBlacklistMatriz);
    addListener('btn-add-blacklist-checked-matriz', 'click', moverSelecionadosParaBlacklistMatriz);
    addListener('btn-enviar-coordenacao-matriz', 'click', enviarSelecionadosParaCoordenacao);
    addListener('btn-requisicao-compra-matriz-footer', 'click', () => abrirModalRequisicaoCompra());

    // Modais
    addListener('btn-leadtime-modal', 'click', abrirModalLeadTime);
    addListener('btn-close-leadtime', 'click', fecharModalLeadTime);
    addListener('btn-save-leadtime', 'click', salvarLeadTimes);

    addListener('btn-blacklist-modal', 'click', abrirModalBlacklist);
    addListener('btn-close-blacklist', 'click', fecharModalBlacklist);
    addListener('btn-cancel-blacklist', 'click', fecharModalBlacklist);
    addListener('btn-export-blacklist-txt', 'click', exportarBlacklistTXT);

    addListener('btn-destaques-modal', 'click', abrirModalDestaques);
    addListener('btn-close-destaques', 'click', fecharModalDestaques);
    addListener('btn-cancel-destaques', 'click', fecharModalDestaques);
    addListener('btn-add-destaque', 'click', adicionarItemDestaque);
    addListener('destaques-search', 'input', renderModalDestaques);
    const inputAddDest = document.getElementById('destaques-new-sku');
    if (inputAddDest) {
        inputAddDest.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') adicionarItemDestaque();
        });
    }

    addListener('btn-velas-ferias-modal', 'click', abrirModalVelasFerias);
    addListener('btn-close-velas-ferias', 'click', fecharModalVelasFerias);
    addListener('btn-close-velas-ferias-footer', 'click', fecharModalVelasFerias);
    addListener('btn-gerar-requisicao-velas', 'click', gerarRequisicaoVelasFerias);
    addListener('btn-pdf-velas-ferias', 'click', gerarPDFVelasFerias);

    addListener('btn-processar-texto-velas', 'click', processarTextoVelasDiscipulado);
    addListener('btn-limpar-texto-velas', 'click', limparTextoVelasDiscipulado);

    addListener('btn-requisicao-compra-matriz', 'click', abrirModalRequisicaoCompra);
    addListener('btn-close-requisicao-compra', 'click', fecharModalRequisicaoCompra);
    addListener('btn-copy-json-compra', 'click', copiarJsonCompra);
    addListener('btn-pdf-requisicao-compra', 'click', gerarPDFRequisicaoCompra);
    addListener('btn-confirm-compra-omie', 'click', enviarCompraOmie);

    addListener('btn-email-alert-modal', 'click', abrirModalEmailAlert);
    addListener('btn-close-email', 'click', fecharModalEmailAlert);
    addListener('btn-send-email-alert-now', 'click', dispararAlertaEmailAgora);

    addListener('btn-close-grade-camisas', 'click', fecharModalGradeCamisas);
    addListener('btn-save-grade-camisas', 'click', fecharModalGradeCamisas);
    addListener('btn-gerar-requisicao-grade-camisas', 'click', gerarRequisicaoGradeCamisas);

    addListener('btn-close-modal-pedido', 'click', fecharModalPedido);
    addListener('btn-close-pedido-footer', 'click', fecharModalPedido);

    addListener('btn-preview-fiscal', 'click', abrirModalFiscal);
    addListener('btn-generate-transfer', 'click', abrirModalOpcoesRemessa);

    // Modal de Opções de Remessa (Nova ou Existente)
    addListener('btn-close-gerar-remessa', 'click', fecharModalOpcoesRemessa);
    addListener('btn-cancel-gerar-remessa', 'click', fecharModalOpcoesRemessa);
    addListener('btn-confirm-gerar-remessa', 'click', processarOpcaoRemessa);

    const radiosTipoRemessa = document.querySelectorAll('input[name="tipo_remessa"]');
    radiosTipoRemessa.forEach(r => r.addEventListener('change', (e) => {
        const groupSelect = document.getElementById('group-select-remessa');
        if (groupSelect) groupSelect.style.display = e.target.value === 'EXISTENTE' ? 'block' : 'none';
    }));

    addListener('btn-atualizar-remessas-list', 'click', () => carregarRemessasOmie(true));
    addListener('btn-close-fiscal', 'click', fecharModalFiscal);
    addListener('btn-modal-close-fiscal', 'click', fecharModalFiscal);
    addListener('btn-copy-fiscal', 'click', copiarTextoFiscal);
    addListener('btn-generate-pdf', 'click', gerarPDFRemessa);
    
    addListener('btn-sync-db', 'click', abrirModalSyncSeletivo);
    addListener('btn-sync-sidebar', 'click', abrirModalSyncSeletivo);

    addListener('btn-close-sync-seletivo', 'click', fecharModalSyncSeletivo);
    addListener('btn-cancel-sync-seletivo', 'click', fecharModalSyncSeletivo);
    addListener('btn-execute-sync-seletivo', 'click', executarSyncSeletivo);
}

// Obter Lead Time de uma família
function getLeadTimeFamilia(familia, tipo = 'cd') {
    const fam = (familia || 'GERAL').toUpperCase();
    const config = state.leadtimes[fam] || state.leadtimes['GERAL'] || { cd: 7, matriz: 15 };
    return config[tipo] || (tipo === 'cd' ? 7 : 15);
}

// Carregar Dados da API / data/produtos_turso.json
async function carregarProdutos() {
    try {
        // 1. Carregar Blacklist salva no localStorage do Navegador
        const localBlacklist = safeGetStorage('drp_blacklist', []);
        if (Array.isArray(localBlacklist)) {
            localBlacklist.forEach(sku => state.blacklist.add(sku));
        }

        // 2. Tentar carregar blacklist persistida no banco de dados e JSON
        try {
            const respBlack = await fetch('/api/blacklist');
            if (respBlack.ok) {
                const dataBlack = await respBlack.json();
                if (dataBlack.blacklist && Array.isArray(dataBlack.blacklist)) {
                    dataBlack.blacklist.forEach(sku => state.blacklist.add(sku));
                }
            } else {
                const respBlackJson = await fetch('data/blacklist.json');
                if (respBlackJson.ok) {
                    const listBlack = await respBlackJson.json();
                    listBlack.forEach(sku => state.blacklist.add(sku));
                }
            }
        } catch (e) {
            console.warn('Blacklist persistida não encontrada:', e);
        }

        // 3. Sincronizar o estado completo da Blacklist de volta ao servidor para persistir em data/blacklist.json e DB
        if (state.blacklist.size > 0) {
            salvarBlacklistServidor();
        }

        // 3.5. Carregar lista de produtos de destaque / lançamentos para exibição no DRP
        try {
            const respDestaque = await fetch('data/produtos_destaque_drp.json?_t=' + Date.now());
            if (respDestaque.ok) {
                const listDestaque = await respDestaque.json();
                state.destaqueDRP = new Set(listDestaque.map(s => String(s).trim()));
            }
        } catch (eDest) {
            console.warn('produtos_destaque_drp.json não encontrado:', eDest);
        }

        let resp = await fetch('/api/produtos?_t=' + Date.now());
        if (!resp.ok) {
            resp = await fetch('data/produtos_turso.json?_t=' + Date.now());
        }
        state.produtos = await resp.json();

        // 4. Aplicar regras de Vínculo DE-PARA / Equivalência de SKUs (ex: 009539 <-> 009622)
        try {
            const respDepara = await fetch('data/depara.json?_t=' + Date.now());
            if (respDepara.ok) {
                const deparaData = await respDepara.json();
                const grupos = deparaData.grupos || [];

                grupos.forEach(g => {
                    const skusGrupo = [g.sku_principal, ...(g.skus_relacionados || [])].map(s => String(s).padStart(6, '0'));
                    const prodsGrupo = state.produtos.filter(p => skusGrupo.includes(String(p.sku).padStart(6, '0')));

                    if (prodsGrupo.length > 0) {
                        const somaCD = prodsGrupo.reduce((acc, item) => acc + (item.cd_sp || 0), 0);
                        const somaMatriz = prodsGrupo.reduce((acc, item) => acc + (item.matriz || 0), 0);
                        const somaVendasCD = prodsGrupo.reduce((acc, item) => acc + (item.vendas_sul_sudeste_30d || 0), 0);
                        const somaVendasGeral = prodsGrupo.reduce((acc, item) => acc + (item.vendas_geral_30d || 0), 0);

                        prodsGrupo.forEach(item => {
                            item.cd_sp = somaCD;
                            item.matriz = somaMatriz;
                            item.vendas_sul_sudeste_30d = somaVendasCD;
                            item.vendas_geral_30d = somaVendasGeral;
                            item.depara_ativo = true;
                            item.depara_nome = g.nome_grupo || 'Estoque Unificado DE-PARA';
                        });
                    }
                });
            }
        } catch (eDepara) {
            console.warn('Erro ao carregar depara.json:', eDepara);
        }


        // Carregar status de produçao salvo do servidor (Turso DB)
        try {
            const respProd = await fetch('/api/producao?_t=' + Date.now());
            if (respProd.ok) {
                const dataProd = await respProd.json();
                const detalhes = dataProd.detalhes || {};

                if (Array.isArray(dataProd.producao)) {
                    state.producao = new Set(dataProd.producao);
                }

                // Atualiza detalhes nos produtos locais vindo do Turso DB
                if (state.produtos && state.produtos.length > 0) {
                    state.produtos.forEach(p => {
                        const sStr = String(p.sku).trim();
                        if (sStr in detalhes) {
                            const det = detalhes[sStr];
                            p.em_producao = Boolean(det.em_producao);
                            if (det.data_previsao) p.data_previsao = det.data_previsao;
                            if (det.numero_pedido) p.numero_pedido = det.numero_pedido;
                            if (det.fornecedor) p.fornecedor = det.fornecedor;
                            if (det.quantidade_producao !== undefined && det.quantidade_producao !== null) {
                                p.quantidade_producao = Number(det.quantidade_producao) || 0;
                            }
                            if (p.em_producao) state.producao.add(p.sku);
                            else state.producao.delete(p.sku);
                        }
                    });
                }
            }
        } catch (eProd) {
            console.warn('Erro ao carregar producao status do servidor:', eProd);
        }

        // Carregar estoque anterior para detectar entradas e remover da produção automaticamente
        let estoquesAnteriores = {};
        try {
            estoquesAnteriores = JSON.parse(localStorage.getItem('drp_estoques_anteriores') || '{}');
        } catch (e) {
            estoquesAnteriores = {};
        }

        const novosEstoques = {};
        let alterouProducaoAuto = false;

        state.produtos.forEach(p => {
            p.em_producao = state.producao.has(p.sku);

            const estAtual = p.matriz || 0;
            const estAntigo = estoquesAnteriores[p.sku];

            // Se o item estava em produção/compra e o estoque da Matriz aumentou ou foi reposto
            if (state.producao.has(p.sku) && estAntigo !== undefined && estAtual > estAntigo) {
                console.log(`[DRP] Entrou estoque para ${p.sku} (${p.nome}): ${estAntigo} -> ${estAtual} un. Removendo de Produção/Compra!`);
                state.producao.delete(p.sku);
                p.em_producao = false;
                p.data_previsao = '';
                alterouProducaoAuto = true;
            }

            novosEstoques[p.sku] = estAtual;
        });

        const listaProdFinal = Array.from(state.producao);
        localStorage.setItem('drp_producao', JSON.stringify(listaProdFinal));
        localStorage.setItem('drp_estoques_anteriores', JSON.stringify(novosEstoques));

        if (alterouProducaoAuto) {
            try {
                fetch('/api/producao/salvar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ producao: listaProdFinal })
                });
            } catch (eAuto) {
                console.warn('Erro ao auto-salvar alteracao producao:', eAuto);
            }
        }

        renderFamilias();
        render();
        carregarRemessasOmie();
    } catch (err) {
        console.warn('Fallback para produtos simulados:', err);
        state.produtos = [
            { id_produto: 1, sku: '009861', nome: 'CHAVE DE FENDA PROFISSIONAL 1/4X6', marca: 'FORTG', familia: 'FERRAMENTAS', cd_sp: 15, matriz: 280, peso_kg: 0.35, vendas_sul_sudeste_30d: 45, vendas_geral_30d: 120 },
            { id_produto: 2, sku: '002766', nome: 'PARAFUSO SEXTAVADO M10 X 50MM', marca: 'CISER', familia: 'FIXACAO', cd_sp: 1500, matriz: 8000, peso_kg: 0.08, vendas_sul_sudeste_30d: 300, vendas_geral_30d: 800 }
        ];
        renderFamilias();
        render();
    }
}

// Renderizar Checkboxes de Famílias e Dropdowns dos Cabeçalhos de Coluna
function renderFamilias() {
    const familias = Array.from(new Set(state.produtos.map(p => (p.familia || 'GERAL').toUpperCase()))).sort();
    const marcas = Array.from(new Set(state.produtos.map(p => p.marca || 'OUTROS'))).filter(Boolean).sort();

    // Checkboxes na Sidebar
    const container = document.getElementById('family-checkboxes');
    container.innerHTML = '';

    familias.forEach(fam => {
        const isChecked = !state.familiasExcluidas.has(fam);
        const item = document.createElement('label');
        item.className = 'checkbox-item';
        item.innerHTML = `
            <input type="checkbox" value="${fam}" ${isChecked ? 'checked' : ''}>
            <span>${fam}</span>
        `;
        item.querySelector('input').addEventListener('change', (e) => {
            if (e.target.checked) {
                state.familiasExcluidas.delete(fam);
            } else {
                state.familiasExcluidas.add(fam);
            }
            render();
        });
        container.appendChild(item);
    });

    // Populate Marca Header Selects
    ['col-filter-marca-cd', 'col-filter-marca-matriz'].forEach(id => {
        const select = document.getElementById(id);
        if (select) {
            const currentVal = select.value;
            select.innerHTML = '<option value="">Todas Marcas</option>';
            marcas.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = m;
                select.appendChild(opt);
            });
            select.value = currentVal;
        }
    });

    // Populate Familia Header Selects
    ['col-filter-fam-cd', 'col-filter-fam-matriz'].forEach(id => {
        const select = document.getElementById(id);
        if (select) {
            const currentVal = select.value;
            select.innerHTML = '<option value="">Todas Famílias</option>';
            familias.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f;
                opt.textContent = f;
                select.appendChild(opt);
            });
            select.value = currentVal;
        }
    });
}

function matchStatusLabel(statusLabel, filtroDesejado) {
    if (!statusLabel || !filtroDesejado) return true;
    if (statusLabel === filtroDesejado) return true;
    const normStatus = String(statusLabel).toLowerCase().trim();
    const normFiltro = String(filtroDesejado).toLowerCase().trim();
    if (normStatus === normFiltro) return true;
    if (normFiltro.startsWith('em produç') || normFiltro.startsWith('em produc')) {
        return normStatus.startsWith('em produç') || normStatus.startsWith('em produc');
    }
    return normStatus.startsWith(normFiltro);
}

// Obter Produtos Filtrados
function getProdutosFiltrados(modo = 'cd') {
    return state.produtos.filter(p => {
        if (p.ativo === false) return false;
        if (state.blacklist.has(p.sku)) return false;
        
        const fam = (p.familia || 'GERAL').toUpperCase();
        if (state.familiasExcluidas.has(fam)) return false;
        
        if (state.termoBusca) {
            const busca = state.termoBusca;
            const sku = (p.sku || '').toLowerCase();
            const nome = (p.nome || '').toLowerCase();
            if (!sku.includes(busca) && !nome.includes(busca)) return false;
        }

        // Filtros específicos por Coluna da Tabela CD_SP
        if (modo === 'cd') {
            if (state.colFilterProdCD) {
                const buscaCol = state.colFilterProdCD;
                const sku = (p.sku || '').toLowerCase();
                const nome = (p.nome || '').toLowerCase();
                if (!sku.includes(buscaCol) && !nome.includes(buscaCol)) return false;
            }
            if (state.colFilterMarcaCD && (p.marca || 'OUTROS') !== state.colFilterMarcaCD) {
                return false;
            }
            if (state.colFilterFamCD && fam !== state.colFilterFamCD.toUpperCase()) {
                return false;
            }
        }

        // Filtros específicos por Coluna da Tabela Matriz
        if (modo === 'matriz') {
            if (state.colFilterProdMatriz) {
                const buscaCol = state.colFilterProdMatriz;
                const sku = (p.sku || '').toLowerCase();
                const nome = (p.nome || '').toLowerCase();
                if (!sku.includes(buscaCol) && !nome.includes(buscaCol)) return false;
            }
            if (state.colFilterMarcaMatriz && (p.marca || 'OUTROS') !== state.colFilterMarcaMatriz) {
                return false;
            }
            if (state.colFilterFamMatriz && fam !== state.colFilterFamMatriz.toUpperCase()) {
                return false;
            }
        }

        // Vendas no período
        const keyVendas = modo === 'cd' ? `vendas_sul_sudeste_${state.periodoDias}d` : `vendas_geral_${state.periodoDias}d`;
        const vendas = p[keyVendas] || 0;
        const estEfetivoCD = (p.cd_sp || 0) + (p.em_transito || 0);

        const skuNorm = String(p.sku || '').trim();
        const skuPad = skuNorm.padStart(6, '0');
        const isDestaque = state.destaqueDRP && (state.destaqueDRP.has(skuNorm) || state.destaqueDRP.has(skuPad));
        // Regra 1: Produtos SEM movimentação no período NÃO entram na reposição (somente entram se tiverem estoque > 0 ou forem forçados/destaque pelo usuário)
        if (vendas <= 0 && estEfetivoCD <= 0 && modo === 'cd' && !isDestaque) return false;
        if (vendas <= 0 && p.matriz <= 0 && modo === 'matriz' && !isDestaque) return false;

        // Regra 2: Descarte de ruído para Camisas e Ícones com vendas inexpressivas (<= 2 un em 60/90d)
        if ((fam.includes('CAMISA') || fam.includes('ICONE')) && vendas <= 2 && state.periodoDias >= 60 && !isDestaque) {
            return false;
        }

        // Filtro por Status Clicado no Card ou no Dropdown da Coluna
        const statusDesejadoCD = state.filtroStatusCD || (state.colFilterStatusCD && !state.colFilterStatusCD.startsWith('SORT_SEVERITY') ? state.colFilterStatusCD : null);
        if (modo === 'cd' && statusDesejadoCD) {
            const lt = getLeadTimeFamilia(p.familia, 'cd');
            const alvo = calcularEstoqueAlvo(vendas, state.periodoDias, state.abastecimentoDias, lt);
            const st = definirStatus(estEfetivoCD, alvo, state.producao.has(p.sku), vendas, p.status_especial);
            if (!matchStatusLabel(st.label, statusDesejadoCD)) return false;
        }

        const statusDesejadoMatriz = state.filtroStatusMatriz || (state.colFilterStatusMatriz && !state.colFilterStatusMatriz.startsWith('SORT_SEVERITY') ? state.colFilterStatusMatriz : null);
        if (modo === 'matriz' && statusDesejadoMatriz) {
            const lt = getLeadTimeFamilia(p.familia, 'matriz');
            const alvo = calcularEstoqueAlvo(vendas, state.periodoDias, state.abastecimentoDias, lt);
            const st = definirStatus(p.matriz, alvo, state.producao.has(p.sku), vendas, p.status_especial);
            if (!matchStatusLabel(st.label, statusDesejadoMatriz)) return false;
        }

        return true;
    }).sort((a, b) => {
        const statusFilter = modo === 'cd' ? state.colFilterStatusCD : state.colFilterStatusMatriz;
        if (statusFilter === 'SORT_SEVERITY_ASC' || statusFilter === 'SORT_SEVERITY_DESC') {
            const getRank = (p) => {
                const keyVendas = modo === 'cd' ? `vendas_sul_sudeste_${state.periodoDias}d` : `vendas_geral_${state.periodoDias}d`;
                const vendas = p[keyVendas] || 0;
                const estEfetivo = modo === 'cd' ? ((p.cd_sp || 0) + (p.em_transito || 0)) : p.matriz;
                const lt = getLeadTimeFamilia(p.familia, modo);
                const alvo = calcularEstoqueAlvo(vendas, state.periodoDias, state.abastecimentoDias, lt);
                const status = definirStatus(estEfetivo, alvo, state.producao.has(p.sku), vendas, p.status_especial);

                const mapRank = {
                    'Ruptura': 1,
                    'Alerta': 2,
                    'Em Produção': 3,
                    'Sem Estoque Discipulado 🕯️': 4,
                    'Estável': 5,
                    'Excesso': 6,
                    'Sem Movimentação': 7
                };
                return mapRank[status.label] || 99;
            };

            const rankA = getRank(a);
            const rankB = getRank(b);
            if (rankA !== rankB) {
                return statusFilter === 'SORT_SEVERITY_ASC' ? rankA - rankB : rankB - rankA;
            }
        }
        return 0;
    });
}

// Funções Auxiliares de Estoque Disponível (Estoque Físico - Reservado)
function getMatrizDisponivel(p) {
    if (!p) return 0;
    const fis = p.matriz || 0;
    const res = p.matriz_reservado || 0;
    return Math.max(0, fis - res);
}

function getCDDisponivel(p) {
    if (!p) return 0;
    const fis = p.cd_sp || 0;
    const res = p.cd_sp_reservado || 0;
    return Math.max(0, fis - res);
}

// Cálculo do Estoque Alvo com Lead Time por Família + 20% Estoque de Segurança
function calcularEstoqueAlvo(vendas, periodo, abastecimento, leadTime) {
    if (!vendas || vendas <= 0) return 0;
    const mediaDiaria = vendas / parseFloat(periodo || 30);
    const diasTotais = parseFloat(abastecimento || 30) + parseFloat(leadTime || 7);
    const estoqueBase = mediaDiaria * diasTotais;
    return estoqueBase * 1.20; // + 20% Estoque de Segurança
}

function calcularNecessidade(p, periodo, abastecimento, modo = 'cd') {
    const keyVendas = modo === 'cd' ? `vendas_sul_sudeste_${periodo}d` : `vendas_geral_${periodo}d`;
    const vendas = p[keyVendas] || 0;
    if (vendas <= 0) return 0;

    const lt = getLeadTimeFamilia(p.familia, modo);
    const alvo = calcularEstoqueAlvo(vendas, periodo, abastecimento, lt);
    const estoqueAtual = modo === 'cd' ? (getCDDisponivel(p) + (p.em_transito || 0)) : getMatrizDisponivel(p);
    return Math.max(0, Math.ceil(alvo - estoqueAtual));
}

function definirStatus(estoque, estoqueAlvo, emProducao, vendas, statusEspecial = null, dataPrevisao = null, numeroPedido = null, fornecedor = null) {
    if (statusEspecial === 'Sem Estoque Discipulado') {
        return { label: 'Sem Estoque Discipulado 🕯️', class: 'badge-discipulado' };
    }
    if (emProducao) {
        let txtPrev = '';
        const tagPed = (numeroPedido && String(numeroPedido).trim() !== '' && numeroPedido !== 'nan' && numeroPedido !== 'None') 
            ? ` <span class="badge-ped-link" onclick="event.stopPropagation(); abrirModalPedido('${numeroPedido}')" style="cursor:pointer; text-decoration:underline; font-weight:bold; color:#fde047;" title="Clique para ver a grade/itens deste Pedido de Compra">[Ped #${numeroPedido}]</span>` 
            : '';
        const tagForn = (fornecedor && String(fornecedor).trim() !== '' && fornecedor !== 'nan' && fornecedor !== 'None') 
            ? `<br><small style="font-weight:600; font-size:0.7rem; color:#93c5fd; opacity:0.95;">🏢 ${fornecedor}</small>` 
            : '';

        if (dataPrevisao && String(dataPrevisao).trim() !== '' && dataPrevisao !== 'nan' && dataPrevisao !== 'None') {
            txtPrev = `<br><small style="font-weight:normal; font-size:0.7rem; opacity:0.95;">📅 Prev: ${dataPrevisao}${tagPed}</small>${tagForn}`;
        } else if (tagPed) {
            txtPrev = `<br><small style="font-weight:normal; font-size:0.7rem; opacity:0.95;">📦 ${tagPed}</small>${tagForn}`;
        } else if (tagForn) {
            txtPrev = `${tagForn}`;
        }
        return { label: `Em Produção / Compra${txtPrev}`, class: 'badge-producao' };
    }
    
    // Se não há vendas e há estoque, está Estável/Excesso
    if (vendas <= 0) {
        if (estoque > 0) return { label: 'Estável', class: 'badge-estavel' };
        return { label: 'Sem Movimentação', class: 'badge-estavel' };
    }

    if (estoque <= 0) return { label: 'Ruptura', class: 'badge-ruptura' };

    const alvo = Math.max(1, estoqueAlvo);
    const razao = estoque / alvo;

    if (razao > 1.5) return { label: 'Excesso', class: 'badge-excesso' };
    if (razao >= 0.8) return { label: 'Estável', class: 'badge-estavel' };
    if (razao >= 0.2) return { label: 'Alerta', class: 'badge-alerta' };
    return { label: 'Ruptura', class: 'badge-ruptura' };
}

// Renderização Geral
function render() {
    const elBl = document.getElementById('count-blacklist');
    if (elBl) elBl.innerText = state.blacklist.size;
    const elDest = document.getElementById('count-destaques');
    if (elDest) elDest.innerText = state.destaqueDRP ? state.destaqueDRP.size : 0;
    const elCD = document.getElementById('count-selected-blacklist');
    if (elCD) elCD.innerText = state.skusChecadosCD.size;
    const elMat = document.getElementById('count-selected-blacklist-matriz');
    if (elMat) elMat.innerText = state.skusChecadosMatriz.size;
    const elCoord = document.getElementById('count-selected-coordenacao');
    if (elCoord) elCoord.innerText = state.skusChecadosMatriz.size;
    
    renderTabCD();
    renderTabMatriz();
    atualizarPainelFrete();
}

// Renderizar Aba 1: CD_SP
function renderTabCD() {
    const produtosFiltrados = getProdutosFiltrados('cd');
    const tbody = document.getElementById('tbody-cd-sp');
    tbody.innerHTML = '';

    // Atualizar Banner de Filtro Ativo
    const bannerCD = document.getElementById('status-filter-banner-cd');
    if (state.filtroStatusCD && !state.filtroStatusCD.startsWith('SORT_SEVERITY')) {
        bannerCD.style.display = 'flex';
        document.getElementById('current-status-filter-name').innerText = state.filtroStatusCD;
        document.querySelectorAll('.clickable-card[data-status-filter]').forEach(c => {
            c.classList.toggle('active-filter', c.dataset.statusFilter === state.filtroStatusCD);
        });
    } else {
        bannerCD.style.display = 'none';
        document.querySelectorAll('.clickable-card[data-status-filter]').forEach(c => c.classList.remove('active-filter'));
    }

    let cntRuptura = 0, cntAlerta = 0, cntEstavel = 0, cntExcesso = 0, cntProducao = 0;

    // Contagem de métricas de todos os produtos ativos do CD_SP
    state.produtos.forEach(p => {
        if (p.ativo === false || state.blacklist.has(p.sku)) return;
        const fam = (p.familia || 'GERAL').toUpperCase();
        if (state.familiasExcluidas.has(fam)) return;

        const vendas = p[`vendas_sul_sudeste_${state.periodoDias}d`] || 0;
        const estEfetivo = (p.cd_sp || 0) + (p.em_transito || 0);
        if (vendas <= 0 && estEfetivo <= 0) return; // ignora zerados sem vendas nem trânsito

        const emProd = state.producao.has(p.sku);
        const lt = getLeadTimeFamilia(p.familia, 'cd');
        const alvo = calcularEstoqueAlvo(vendas, state.periodoDias, state.abastecimentoDias, lt);
        const status = definirStatus(estEfetivo, alvo, emProd, vendas);

        if (status.label === 'Ruptura') cntRuptura++;
        else if (status.label === 'Alerta') cntAlerta++;
        else if (status.label === 'Estável') cntEstavel++;
        else if (status.label === 'Excesso') cntExcesso++;
        if (emProd) cntProducao++;
    });

    document.getElementById('metric-cd-ruptura').innerText = cntRuptura;
    document.getElementById('metric-cd-alerta').innerText = cntAlerta;
    document.getElementById('metric-cd-estavel').innerText = cntEstavel;
    document.getElementById('metric-cd-excesso').innerText = cntExcesso;
    document.getElementById('metric-cd-producao').innerText = cntProducao;

    const limite = state.limiteCD;
    produtosFiltrados.slice(0, limite).forEach(p => {
        const emProd = state.producao.has(p.sku);
        const vendas = p[`vendas_sul_sudeste_${state.periodoDias}d`] || 0;
        const lt = getLeadTimeFamilia(p.familia, 'cd');
        const estAlvo = calcularEstoqueAlvo(vendas, state.periodoDias, state.abastecimentoDias, lt);
        const estCDDisp = getCDDisponivel(p);
        const estMatrizDisp = getMatrizDisponivel(p);
        const estEfetivo = estCDDisp + (p.em_transito || 0);
        const necessidade = Math.max(0, Math.ceil(estAlvo - estEfetivo));
        const status = definirStatus(estEfetivo, estAlvo, emProd, vendas, p.status_especial, p.data_previsao, p.numero_pedido, p.fornecedor);
        const matrizInsuficiente = estMatrizDisp < necessidade && necessidade > 0;

        const isChecked = state.skusChecadosCD.has(p.sku);
        let qtdEnviar = state.itensSelecionadosRemessa[p.sku];
        if (qtdEnviar === undefined) {
            qtdEnviar = (estMatrizDisp >= necessidade && necessidade > 0) ? necessidade : (estMatrizDisp > 0 ? estMatrizDisp : 0);
            if (isChecked && qtdEnviar > 0) {
                state.itensSelecionadosRemessa[p.sku] = qtdEnviar;
            }
        }

        const badgeResCD = (p.cd_sp_reservado || 0) > 0 ? `<br><small style="color:var(--text-muted); font-size:0.7rem;" title="Estoque Físico: ${p.cd_sp} un | Reservado p/ Pedidos: ${p.cd_sp_reservado} un">(Fís: ${p.cd_sp})</small>` : '';
        const badgeResMatriz = (p.matriz_reservado || 0) > 0 ? `<br><small style="color:var(--text-muted); font-size:0.7rem;" title="Estoque Físico: ${p.matriz} un | Reservado p/ Pedidos: ${p.matriz_reservado} un">(Fís: ${p.matriz})</small>` : '';

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <input type="checkbox" class="chk-item-cd" data-sku="${p.sku}" ${isChecked ? 'checked' : ''}>
            </td>
            <td>
                <strong>${p.sku}</strong><br>
                <small class="text-muted">${p.nome}</small>
                ${p.modelo_base ? `<br><button class="btn btn-sm btn-secondary btn-grade-camisa" data-modelo="${p.modelo_base}" style="font-size:0.7rem; padding: 2px 6px; margin-top:3px;"><i class="fa-solid fa-shirt"></i> Grade PP..3G</button>` : ''}
            </td>
            <td><span class="tag-marca">${p.marca || 'OUTROS'}</span></td>
            <td><span class="tag-fam">${p.familia || 'GERAL'}</span><br><small class="text-muted">LT: ${lt}d</small></td>
            <td><strong>${estCDDisp}</strong> un ${badgeResCD}</td>
            <td><strong style="color: ${p.em_transito > 0 ? '#60a5fa' : 'var(--text-muted)'}">${p.em_transito > 0 ? '+' + p.em_transito : '0'}</strong> un</td>
            <td><strong>${estMatrizDisp}</strong> un ${badgeResMatriz}</td>
            <td>${estAlvo.toFixed(1)} un</td>
            <td><strong style="color: ${necessidade > 0 ? 'var(--primary)' : 'inherit'}">${necessidade}</strong> un</td>
            <td>
                <span class="badge ${status.class}">${status.label}</span>
                ${matrizInsuficiente ? '<br><small style="color: var(--color-ruptura)">⚠️ Matriz insuficiente</small>' : ''}
                ${(p.familia || '').toUpperCase().includes('VELA') && p.estoque_discipulado === false ? '<br><small style="color: #f59e0b;">🕯️ Indisponível no Fornecedor</small>' : ''}
            </td>
            <td>
                <input type="number" min="0" max="${estMatrizDisp}" value="${qtdEnviar}" class="input-number input-qtd-cd" data-sku="${p.sku}">
            </td>
        `;

        tr.querySelector('.chk-item-cd').addEventListener('change', (e) => {
            const sku = e.target.dataset.sku;
            const inputQtd = tr.querySelector('.input-qtd-cd');
            const qtdVal = parseInt(inputQtd.value) || necessidade || 1;
            if (e.target.checked) {
                state.skusChecadosCD.add(sku);
                state.itensSelecionadosRemessa[sku] = qtdVal;
            } else {
                state.skusChecadosCD.delete(sku);
                delete state.itensSelecionadosRemessa[sku];
            }
            const elCD = document.getElementById('count-selected-blacklist');
            if (elCD) elCD.innerText = state.skusChecadosCD.size;
            atualizarPainelFrete();
        });

        tr.querySelector('.input-qtd-cd').addEventListener('input', (e) => {
            const sku = e.target.dataset.sku;
            const val = parseInt(e.target.value) || 0;
            const chk = tr.querySelector('.chk-item-cd');
            if (val > 0) {
                state.itensSelecionadosRemessa[sku] = val;
                state.skusChecadosCD.add(sku);
                chk.checked = true;
            } else {
                delete state.itensSelecionadosRemessa[sku];
                state.skusChecadosCD.delete(sku);
                chk.checked = false;
            }
            const elCD = document.getElementById('count-selected-blacklist');
            if (elCD) elCD.innerText = state.skusChecadosCD.size;
            atualizarPainelFrete();
        });

        const btnGrade = tr.querySelector('.btn-grade-camisa');
        if (btnGrade) {
            btnGrade.addEventListener('click', () => abrirGradeCamisas(btnGrade.dataset.modelo));
        }

        tbody.appendChild(tr);
    });
}

// Renderizar Aba 2: Matriz
function renderTabMatriz() {
    const produtosFiltrados = getProdutosFiltrados('matriz');
    const tbody = document.getElementById('tbody-matriz');
    tbody.innerHTML = '';

    // Banner Filtro Matriz
    const bannerMatriz = document.getElementById('status-filter-banner-matriz');
    if (state.filtroStatusMatriz && !state.filtroStatusMatriz.startsWith('SORT_SEVERITY')) {
        bannerMatriz.style.display = 'flex';
        document.getElementById('current-status-filter-matriz-name').innerText = state.filtroStatusMatriz;
        document.querySelectorAll('.clickable-card[data-status-filter-matriz]').forEach(c => {
            c.classList.toggle('active-filter', c.dataset.statusFilterMatriz === state.filtroStatusMatriz);
        });
    } else {
        bannerMatriz.style.display = 'none';
        document.querySelectorAll('.clickable-card[data-status-filter-matriz]').forEach(c => c.classList.remove('active-filter'));
    }

    let cntRuptura = 0, cntAlerta = 0, cntEstavel = 0, cntExcesso = 0, cntProducao = 0;

    state.produtos.forEach(p => {
        if (p.ativo === false || state.blacklist.has(p.sku)) return;
        const fam = (p.familia || 'GERAL').toUpperCase();
        if (state.familiasExcluidas.has(fam)) return;

        const vendas = p[`vendas_geral_${state.periodoDias}d`] || 0;
        const estMatrizDisp = getMatrizDisponivel(p);
        if (vendas <= 0 && estMatrizDisp <= 0) return;

        const emProd = state.producao.has(p.sku);
        const lt = getLeadTimeFamilia(p.familia, 'matriz');
        const alvo = calcularEstoqueAlvo(vendas, state.periodoDias, state.abastecimentoDias, lt);
        const status = definirStatus(estMatrizDisp, alvo, emProd, vendas, p.status_especial);

        if (status.label === 'Ruptura') cntRuptura++;
        else if (status.label === 'Alerta') cntAlerta++;
        else if (status.label === 'Estável') cntEstavel++;
        else if (status.label === 'Excesso') cntExcesso++;
        if (emProd) cntProducao++;
    });

    document.getElementById('metric-mat-ruptura').innerText = cntRuptura;
    document.getElementById('metric-mat-alerta').innerText = cntAlerta;
    document.getElementById('metric-mat-estavel').innerText = cntEstavel;
    document.getElementById('metric-mat-excesso').innerText = cntExcesso;
    document.getElementById('metric-mat-producao').innerText = cntProducao;

    const limite = state.limiteMatriz;
    produtosFiltrados.slice(0, limite).forEach(p => {
        const emProd = state.producao.has(p.sku);
        const ehSaz = state.sazonal.has(p.sku);
        const vendas = p[`vendas_geral_${state.periodoDias}d`] || 0;
        const lt = getLeadTimeFamilia(p.familia, 'matriz');
        const estAlvo = calcularEstoqueAlvo(vendas, state.periodoDias, state.abastecimentoDias, lt);
        const estMatrizDisp = getMatrizDisponivel(p);
        const duracao = vendas > 0 ? Math.floor(estMatrizDisp / (vendas / state.periodoDias)) : 999;
        const status = definirStatus(estMatrizDisp, estAlvo, emProd, vendas, p.status_especial, p.data_previsao, p.numero_pedido, p.fornecedor);
        const isChecked = state.skusChecadosMatriz.has(p.sku);

        const badgeResMatriz = (p.matriz_reservado || 0) > 0 ? `<br><small style="color:var(--text-muted); font-size:0.7rem;" title="Estoque Físico: ${p.matriz} un | Reservado p/ Pedidos: ${p.matriz_reservado} un">(Fís: ${p.matriz})</small>` : '';

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <input type="checkbox" class="chk-item-matriz" data-sku="${p.sku}" ${isChecked ? 'checked' : ''}>
            </td>
            <td>
                <strong>${p.sku}</strong><br>
                <small class="text-muted">${p.nome}</small>
                ${p.modelo_base ? `<br><button class="btn btn-sm btn-secondary btn-grade-camisa" data-modelo="${p.modelo_base}" style="font-size:0.7rem; padding: 2px 6px; margin-top:3px;"><i class="fa-solid fa-shirt"></i> Grade PP..3G</button>` : ''}
            </td>
            <td><span class="tag-marca">${p.marca || 'OUTROS'}</span></td>
            <td><span class="tag-fam">${p.familia || 'GERAL'}</span><br><small class="text-muted">LT: ${lt}d</small></td>
            <td><strong>${estMatrizDisp}</strong> un ${badgeResMatriz}</td>
            <td>${estAlvo.toFixed(1)} un</td>
            <td>${duracao === 999 ? '∞' : duracao} dias</td>
            <td>
                <span class="badge ${status.class}">${status.label}</span>
                ${(p.familia || '').toUpperCase().includes('VELA') && p.estoque_discipulado === false ? '<br><small style="color: #f59e0b;">🕯️ Indisponível no Fornecedor</small>' : ''}
            </td>
            <td>
                <input type="checkbox" class="chk-prod" data-sku="${p.sku}" ${emProd ? 'checked' : ''}>
                ${emProd ? `<br><input type="text" class="input-dt-prev" data-sku="${p.sku}" value="${p.data_previsao || ''}" placeholder="DD/MM/AAAA" style="font-size:0.7rem; width:78px; margin-top:2px; padding:1px 3px; border:1px solid #cbd5e1; border-radius:3px;" title="Data Prevista de Entrega (Pedido)">` : ''}
            </td>
            <td>
                <input type="checkbox" class="chk-saz" data-sku="${p.sku}" ${ehSaz ? 'checked' : ''}>
            </td>
        `;

        const btnGrade = tr.querySelector('.btn-grade-camisa');
        if (btnGrade) {
            btnGrade.addEventListener('click', () => abrirGradeCamisas(btnGrade.dataset.modelo));
        }

        tr.querySelector('.chk-item-matriz').addEventListener('change', (e) => {
            const sku = e.target.dataset.sku;
            if (e.target.checked) state.skusChecadosMatriz.add(sku);
            else state.skusChecadosMatriz.delete(sku);
            document.getElementById('count-selected-blacklist-matriz').innerText = state.skusChecadosMatriz.size;
            const elCoord = document.getElementById('count-selected-coordenacao');
            if (elCoord) elCoord.innerText = state.skusChecadosMatriz.size;
        });

        tr.querySelector('.chk-prod').addEventListener('change', async (e) => {
            const sku = e.target.dataset.sku;
            const isChecked = e.target.checked;
            if (isChecked) state.producao.add(sku);
            else state.producao.delete(sku);
            localStorage.setItem('drp_producao', JSON.stringify(Array.from(state.producao)));

            const pObj = state.produtos.find(prod => String(prod.sku).trim() === String(sku).trim());
            if (pObj) pObj.em_producao = isChecked;

            try {
                await fetch('/api/producao/salvar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sku, em_producao: isChecked, data_previsao: pObj ? pObj.data_previsao : '', numero_pedido: pObj ? pObj.numero_pedido : '' })
                });
            } catch (errServ) {
                console.warn('Erro ao salvar producao no servidor:', errServ);
            }

            render();
        });

        const inputDt = tr.querySelector('.input-dt-prev');
        if (inputDt) {
            inputDt.addEventListener('change', async (e) => {
                const sku = e.target.dataset.sku;
                const valDt = e.target.value.trim();
                const pObj = state.produtos.find(prod => String(prod.sku).trim() === String(sku).trim());
                const numPed = pObj ? pObj.numero_pedido : '';

                if (pObj) {
                    pObj.data_previsao = valDt;
                    // Atualiza a data em todos os produtos do mesmo pedido de compra
                    if (numPed) {
                        state.produtos.forEach(pOther => {
                            if (pOther.numero_pedido && String(pOther.numero_pedido).trim() === String(numPed).trim()) {
                                pOther.data_previsao = valDt;
                            }
                        });
                    }
                }

                try {
                    await fetch('/api/producao/salvar', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ sku, numero_pedido: numPed, em_producao: true, data_previsao: valDt })
                    });
                } catch (errServ) {
                    console.warn('Erro ao salvar data_previsao no servidor:', errServ);
                }
                render();
            });
        }

        tr.querySelector('.chk-saz').addEventListener('change', (e) => {
            const sku = e.target.dataset.sku;
            if (e.target.checked) state.sazonal.add(sku);
            else state.sazonal.delete(sku);
            localStorage.setItem('drp_sazonal', JSON.stringify(Array.from(state.sazonal)));
            render();
        });

        tbody.appendChild(tr);
    });
}

// Modal Lead Time por Família
function abrirModalLeadTime() {
    const modal = document.getElementById('modal-leadtime');
    if (modal) modal.classList.add('active');
    try { renderModalLeadTime(); } catch (e) { console.error(e); }
}

function fecharModalLeadTime() {
    const modal = document.getElementById('modal-leadtime');
    if (modal) modal.classList.remove('active');
}

function renderModalLeadTime() {
    const container = document.getElementById('leadtime-families-list');
    container.innerHTML = '';

    const familias = Array.from(new Set(state.produtos.map(p => (p.familia || 'GERAL').toUpperCase()))).sort();

    familias.forEach(fam => {
        const lt = state.leadtimes[fam] || state.leadtimes['GERAL'] || { cd: 7, matriz: 15 };
        const row = document.createElement('div');
        row.className = 'leadtime-row';
        row.innerHTML = `
            <span>${fam}</span>
            <div>
                <small class="text-muted">CD_SP (dias)</small>
                <input type="number" min="1" max="120" value="${lt.cd}" class="form-control input-lt-cd" data-fam="${fam}">
            </div>
            <div>
                <small class="text-muted">Matriz CE (dias)</small>
                <input type="number" min="1" max="120" value="${lt.matriz}" class="form-control input-lt-matriz" data-fam="${fam}">
            </div>
        `;
        container.appendChild(row);
    });
}

function salvarLeadTimes() {
    document.querySelectorAll('.input-lt-cd').forEach(inp => {
        const fam = inp.dataset.fam;
        const val = parseInt(inp.value) || 7;
        if (!state.leadtimes[fam]) state.leadtimes[fam] = { cd: 7, matriz: 15 };
        state.leadtimes[fam].cd = val;
    });

    document.querySelectorAll('.input-lt-matriz').forEach(inp => {
        const fam = inp.dataset.fam;
        const val = parseInt(inp.value) || 15;
        if (!state.leadtimes[fam]) state.leadtimes[fam] = { cd: 7, matriz: 15 };
        state.leadtimes[fam].matriz = val;
    });

    localStorage.setItem('drp_leadtimes', JSON.stringify(state.leadtimes));
    fecharModalLeadTime();
    render();
    alert('✅ Lead Times por família atualizados com sucesso!');
}

async function salvarBlacklistServidor() {
    localStorage.setItem('drp_blacklist', JSON.stringify(Array.from(state.blacklist)));
    try {
        await fetch('/api/blacklist/salvar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ skus: Array.from(state.blacklist) })
        });
    } catch (e) {
        console.warn('Erro ao salvar blacklist no servidor:', e);
    }
}

// Mover itens checados na Aba 1 para a Blacklist
async function moverSelecionadosParaBlacklistCD() {
    if (state.skusChecadosCD.size === 0) {
        alert('Nenhum produto selecionado para mover para a Blacklist.');
        return;
    }

    const qtd = state.skusChecadosCD.size;
    if (confirm(`Deseja mover ${qtd} produto(s) selecionado(s) para a Blacklist?`)) {
        state.skusChecadosCD.forEach(sku => {
            state.blacklist.add(sku);
            delete state.itensSelecionadosRemessa[sku];
        });
        state.skusChecadosCD.clear();
        document.getElementById('chk-select-all-cd').checked = false;
        
        await salvarBlacklistServidor();
        render();
        alert(`✅ ${qtd} produto(s) adicionado(s) à Blacklist com sucesso!`);
    }
}

// Mover itens checados na Aba 2 para a Blacklist
async function moverSelecionadosParaBlacklistMatriz() {
    if (state.skusChecadosMatriz.size === 0) {
        alert('Nenhum produto selecionado na Matriz para mover para a Blacklist.');
        return;
    }

    const qtd = state.skusChecadosMatriz.size;
    if (confirm(`Deseja mover ${qtd} produto(s) selecionado(s) para a Blacklist?`)) {
        state.skusChecadosMatriz.forEach(sku => {
            state.blacklist.add(sku);
        });
        state.skusChecadosMatriz.clear();
        await salvarBlacklistServidor();
        render();
        alert(`✅ ${qtd} produto(s) adicionado(s) à Blacklist com sucesso!`);
    }
}

// Modal Blacklist (Visualizar & Remover)
function abrirModalBlacklist() {
    const modal = document.getElementById('modal-blacklist');
    if (modal) modal.classList.add('active');
    try { renderModalBlacklist(); } catch (e) { console.error(e); }
}

function fecharModalBlacklist() {
    const modal = document.getElementById('modal-blacklist');
    if (modal) modal.classList.remove('active');
    render();
}

function renderModalBlacklist() {
    const container = document.getElementById('blacklist-items-list');
    container.innerHTML = '';

    const busca = (document.getElementById('blacklist-search').value || '').toLowerCase();
    const skusBlacklist = Array.from(state.blacklist);

    if (skusBlacklist.length === 0) {
        container.innerHTML = '<p class="text-muted" style="text-align:center; padding: 20px;">Nenhum produto na Blacklist.</p>';
        return;
    }

    skusBlacklist.forEach(sku => {
        const p = state.produtos.find(prod => prod.sku === sku) || { sku, nome: 'Produto Desconhecido' };
        if (busca && !sku.toLowerCase().includes(busca) && !(p.nome || '').toLowerCase().includes(busca)) {
            return;
        }

        const row = document.createElement('div');
        row.className = 'blacklist-row';
        row.innerHTML = `
            <div>
                <strong>${p.sku}</strong> - <span>${p.nome}</span>
            </div>
            <button class="btn btn-sm btn-danger btn-remove-bl" data-sku="${p.sku}">
                <i class="fa-solid fa-trash"></i> Remover
            </button>
        `;

        row.querySelector('.btn-remove-bl').addEventListener('click', async () => {
            state.blacklist.delete(p.sku);
            await salvarBlacklistServidor();
            renderModalBlacklist();
        });

        container.appendChild(row);
    });
}

function exportarBlacklistTXT() {
    const skusBlacklist = Array.from(state.blacklist);
    if (skusBlacklist.length === 0) {
        alert('Nenhum item na Blacklist para exportar.');
        return;
    }

    let conteudo = `LISTA DE ITENS NA BLACKLIST - DRP OMIE ERP\n`;
    conteudo += `Data da Exportação: ${new Date().toLocaleString('pt-BR')}\n`;
    conteudo += `Total de Itens: ${skusBlacklist.length}\n`;
    conteudo += `================================================================================\n\n`;

    skusBlacklist.forEach(sku => {
        const p = state.produtos.find(prod => prod.sku === sku) || { sku, nome: 'Produto Desconhecido' };
        conteudo += `SKU: ${p.sku.padEnd(12)} | Nome: ${p.nome}\n`;
    });

    const blob = new Blob([conteudo], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `blacklist_itens_${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Modal Destaques / Lançamentos Forçados CD_SP
function abrirModalDestaques() {
    const modal = document.getElementById('modal-destaques');
    if (modal) modal.classList.add('active');
    try { renderModalDestaques(); } catch (e) { console.error(e); }
}

function fecharModalDestaques() {
    const modal = document.getElementById('modal-destaques');
    if (modal) modal.classList.remove('active');
    render();
}

function renderModalDestaques() {
    const container = document.getElementById('destaques-items-list');
    if (!container) return;
    container.innerHTML = '';

    const busca = (document.getElementById('destaques-search')?.value || '').toLowerCase();
    const skusDestaques = state.destaqueDRP ? Array.from(state.destaqueDRP) : [];

    const elCont = document.getElementById('count-destaques');
    if (elCont) elCont.innerText = skusDestaques.length;

    if (skusDestaques.length === 0) {
        container.innerHTML = '<p class="text-muted" style="text-align:center; padding: 20px;">Nenhum produto forçado no momento.</p>';
        return;
    }

    skusDestaques.forEach(sku => {
        const skuNorm = String(sku).trim();
        const skuPad = skuNorm.padStart(6, '0');
        const p = state.produtos.find(prod => String(prod.sku).trim() === skuNorm || String(prod.sku).trim() === skuPad) || { sku: skuNorm, nome: 'Produto Desconhecido' };
        
        if (busca && !skuNorm.toLowerCase().includes(busca) && !(p.nome || '').toLowerCase().includes(busca)) {
            return;
        }

        const row = document.createElement('div');
        row.className = 'blacklist-row';
        row.innerHTML = `
            <div>
                <strong>${p.sku}</strong> - <span>${p.nome}</span>
            </div>
            <button class="btn btn-sm btn-danger btn-remove-destaque" data-sku="${p.sku}">
                <i class="fa-solid fa-trash"></i> Remover
            </button>
        `;

        row.querySelector('.btn-remove-destaque').addEventListener('click', async () => {
            state.destaqueDRP.delete(skuNorm);
            state.destaqueDRP.delete(skuPad);
            await salvarDestaquesServidor();
            renderModalDestaques();
            render();
        });

        container.appendChild(row);
    });
}

async function adicionarItemDestaque() {
    const input = document.getElementById('destaques-new-sku');
    if (!input) return;
    const val = input.value.trim().toUpperCase();
    if (!val) {
        alert('Por favor, informe o SKU ou Código do produto.');
        return;
    }

    const valPad = val.padStart(6, '0');
    const p = state.produtos.find(prod => String(prod.sku).trim().toUpperCase() === val || String(prod.sku).trim().toUpperCase() === valPad || String(prod.codigo || '').trim().toUpperCase() === val);
    
    const skuFinal = p ? String(p.sku).trim() : val;
    if (!state.destaqueDRP) state.destaqueDRP = new Set();
    state.destaqueDRP.add(skuFinal);
    input.value = '';

    await salvarDestaquesServidor();
    renderModalDestaques();
    render();
    alert(`Produto ${skuFinal} (${p ? p.nome : 'Adicionado'}) agora sempre aparecerá na Reposição CD_SP!`);
}

async function salvarDestaquesServidor() {
    const lista = state.destaqueDRP ? Array.from(state.destaqueDRP) : [];
    try {
        await fetch('/api/destaques', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ destaques: lista })
        });
    } catch (e) {
        console.warn('Erro ao salvar destaques no servidor:', e);
    }
}



// Atualização do Painel de Frete e Volumes
function atualizarPainelFrete() {
    let pesoTotal = 0;
    let totalItens = 0;

    // Unir SKUs de skusChecadosCD e itensSelecionadosRemessa
    const skusUnicos = new Set([...state.skusChecadosCD, ...Object.keys(state.itensSelecionadosRemessa)]);

    skusUnicos.forEach(sku => {
        let qtd = state.itensSelecionadosRemessa[sku];
        if (qtd === undefined || qtd <= 0) {
            const inputQtd = document.querySelector(`.input-qtd-cd[data-sku="${sku}"]`);
            if (inputQtd) {
                qtd = parseInt(inputQtd.value) || 0;
            }
            if (!qtd) {
                const p = state.produtos.find(prod => prod.sku === sku);
                if (p) {
                    const nec = calcularNecessidade(p, state.periodoDias, state.abastecimentoDias, 'cd');
                    qtd = Math.max(0, Math.floor(nec));
                }
            }
        }
        if (qtd > 0 && state.skusChecadosCD.has(sku)) {
            state.itensSelecionadosRemessa[sku] = qtd;
            const p = state.produtos.find(prod => prod.sku === sku);
            const pesoUn = p ? (p.peso_kg || 0.25) : 0.25;
            pesoTotal += (pesoUn * qtd);
            totalItens += qtd;
        } else if (!state.skusChecadosCD.has(sku)) {
            delete state.itensSelecionadosRemessa[sku];
        }
    });

    const caixasCalculadas = Math.ceil(pesoTotal / 16.0);
    const volumes = Math.max(totalItens > 0 ? 1 : 0, caixasCalculadas);

    // Encontrar valor de frete na tabela
    let valorFrete = 0;
    let descFrete = "0 Caixa";

    if (volumes > 0) {
        const faixa = FRETE_TABELA.find(f => pesoTotal >= f.min && pesoTotal <= f.max);
        if (faixa) {
            valorFrete = faixa.valor;
            descFrete = faixa.desc;
        } else if (pesoTotal > 144.000) {
            valorFrete = 120.00;
            descFrete = `${volumes} Cx Grandes`;
        } else {
            valorFrete = 20.00;
            descFrete = `${volumes} Cx Pequena`;
        }
    }

    const elCount = document.getElementById('ship-count');
    if (elCount) elCount.innerText = totalItens;
    const elWeight = document.getElementById('ship-weight');
    if (elWeight) elWeight.innerText = `${pesoTotal.toFixed(2)} kg`;
    const elBoxes = document.getElementById('ship-boxes');
    if (elBoxes) elBoxes.innerText = `${volumes} VOLUME(S) (${descFrete})`;
    const elFreight = document.getElementById('ship-freight');
    if (elFreight) elFreight.innerText = `R$ ${valorFrete.toFixed(2).replace('.', ',')}`;
}

// Gerar Texto Fiscal da Remessa
function gerarTextoFiscal() {
    const skusSelecionados = Object.keys(state.itensSelecionadosRemessa).filter(sku => state.itensSelecionadosRemessa[sku] > 0);
    if (skusSelecionados.length === 0) {
        return "Nenhum produto selecionado para remessa.";
    }

    let pesoTotal = 0;
    let itensTxt = "";
    let subtotalValor = 0;

    skusSelecionados.forEach((sku, idx) => {
        const p = state.produtos.find(prod => prod.sku === sku) || { sku, nome: 'PRODUTO', matriz: 0, valor_unitario: 10.00 };
        const qtd = state.itensSelecionadosRemessa[sku];
        const pesoUn = p.peso_kg || 0.25;
        pesoTotal += (pesoUn * qtd);
        const vUnit = p.valor_unitario || 15.00;
        const vTot = vUnit * qtd;
        subtotalValor += vTot;

        itensTxt += `${String(idx + 1).padStart(2, '0')} | SKU: ${p.sku.padEnd(10)} | ${p.nome.padEnd(35).slice(0,35)} | QTD: ${String(qtd).padStart(4)} un | V.UN: R$ ${vUnit.toFixed(2).padStart(6)} | TOTAL: R$ ${vTot.toFixed(2).padStart(8)}\n`;
    });

    const caixas = Math.ceil(pesoTotal / 16.0);
    const volumes = Math.max(1, caixas);

    return `================================================================================
DADOS DA REMESSA DE TRANSFERÊNCIA DE ESTOQUE (CD_SP)
================================================================================
DATA DA EMISSÃO   : ${new Date().toLocaleDateString('pt-BR')} ${new Date().toLocaleTimeString('pt-BR')}
CLIENTE DESTINO   : ${DADOS_FISCAIS.cliente_nome} (CNPJ ${DADOS_FISCAIS.cliente_cnpj})
NATUREZA OPERAÇÃO : ${DADOS_FISCAIS.natureza}
CFOP              : ${DADOS_FISCAIS.cfop} - ${DADOS_FISCAIS.cfop_descricao}
TRANSPORTADORA    : ${DADOS_FISCAIS.transportadora} (CNPJ: ${DADOS_FISCAIS.transportadora_cnpj})
TIPO DE FRETE     : ${DADOS_FISCAIS.tipo_frete}
PESO BRUTO TOTAL  : ${pesoTotal.toFixed(2)} KG
VOLUMES           : ${volumes} ${DADOS_FISCAIS.especie} (CAIXAS ATE 16KG)
================================================================================
RELAÇÃO DE PRODUTOS DA REMESSA:
--------------------------------------------------------------------------------
${itensTxt}--------------------------------------------------------------------------------
VALOR TOTAL ESTIMADO DA NOTA DE REMESSA: R$ ${subtotalValor.toFixed(2)}
================================================================================
`;
}

function abrirModalFiscal() {
    const txt = gerarTextoFiscal();
    document.getElementById('fiscal-text-content').innerText = txt;
    document.getElementById('modal-fiscal').classList.add('active');
}

function fecharModalFiscal() {
    document.getElementById('modal-fiscal').classList.remove('active');
}

function copiarTextoFiscal() {
    const txt = document.getElementById('fiscal-text-content').innerText;
    navigator.clipboard.writeText(txt).then(() => {
        alert('Texto Fiscal copiado para a área de transferência!');
    });
}

// Enviar Remessa de Transferência de Produto para o Omie ERP
async function enviarRemessaOmie() {
    const skusSelecionados = Object.keys(state.itensSelecionadosRemessa).filter(sku => state.itensSelecionadosRemessa[sku] > 0);
    if (skusSelecionados.length === 0) {
        alert("⚠️ Nenhum produto selecionado para a remessa. Marque os produtos e informe a quantidade.");
        return;
    }

    let pesoTotal = 0;
    const produtosReq = [];

    skusSelecionados.forEach(sku => {
        const p = state.produtos.find(prod => prod.sku === sku) || { sku, nome: 'PRODUTO', id_produto: 0, valor_unitario: 0 };
        const qtd = state.itensSelecionadosRemessa[sku];
        const pesoUn = p.peso_kg || 0.25;
        pesoTotal += (pesoUn * qtd);
        const vUnit = parseFloat((p.valor_unitario || p.preco_unitario || p.preco || 0).toString());

        produtosReq.append ? null : null; // Safe check
        produtosReq.push({
            cCodItInt: p.sku,
            nCodIt: 0,
            nCodProd: p.id_produto || 0,
            nQtde: qtd,
            nValUnit: vUnit,
            cCFOP: "6.152",
            codigo_local_estoque: 1794541746,
            infAdicItem: {
                codigo_cenario_impostos_item: 1818511574,
                cNaoMovEstoque: "N",
                nPesoBruto: parseFloat(pesoUn.toFixed(3)),
                nPesoLiq: parseFloat((pesoUn * 0.9).toFixed(3))
            }
        });
    });

    const caixasCalculadas = Math.ceil(pesoTotal / 16.0);
    const volumes = Math.max(1, caixasCalculadas);
    
    let valorFrete = 20.00;
    const faixa = FRETE_TABELA.find(f => pesoTotal >= f.min && pesoTotal <= f.max);
    if (faixa) valorFrete = faixa.valor;
    else if (pesoTotal > 144.0) valorFrete = 120.00;

    const payloadRemessa = {
        cabec: {
            cCodIntRem: `REM_${Math.floor(Date.now() / 1000)}`,
            dPrevisao: new Date().toLocaleDateString('pt-BR'),
            nCodCli: 2216843393, // Cliente CD_SP: COMUNIDADE CATOLICA SHALOM GUARULHOS MACEDO (CNPJ: 07.044.456/0092-30)
            nCodRem: 0,
            nCodVend: "0",
            codigo_cenario_impostos: 1818511574
        },
        email: {
            cEmail: "centrodedistribuicaosp@comshalom.org"
        },
        frete: {
            cEspVol: "VOLUMES",
            cMarVol: "",
            cNumVol: String(volumes),
            cPlaca: "",
            cTpFrete: "0", // CIF
            cUF: "",
            nCodTransp: 2139040450, // Transportadora TRANSLATINO
            nPesoBruto: parseFloat(pesoTotal.toFixed(3)),
            nPesoLiq: parseFloat((pesoTotal * 0.9).toFixed(3)),
            nQtdVol: volumes,
            nValFrete: valorFrete,
            nValOutras: 0,
            nValSeguro: 0
        },
        infAdic: {
            cCodCateg: "1.01.01", // Receitas Comercial
            cConsFinal: "S",
            cContato: "CD SP",
            cDadosAdic: "Remessa Transferencia entre CD | Transportadora TRANSLATINO | Frete CIF | Destino: GUARULHOS MACEDO CNPJ 07.044.456/0092-30",
            cNumCtr: "",
            cPedido: "",
            nCodProj: 0
        },
        obs: {
            cObs: "Remessa Transferencia entre CD | Transportadora TRANSLATINO | Frete CIF | Destino: GUARULHOS MACEDO CNPJ 07.044.456/0092-30||Fazer etiqueta com letras grandes e deixar a NF fora das caixas e quantidade de volumes:|A/C Sr. Gildo.|Entregar ao Tiberio|Comunidade Catolica Shalom|Translatino"
        },
        produtos: produtosReq
    };

    if (!confirm(`Confirma o envio da Remessa com ${produtosReq.length} itens (Peso: ${pesoTotal.toFixed(2)}kg, Vol: ${volumes}) para o Omie ERP?`)) {
        return;
    }

    try {
        const resp = await fetch('/api/remessas/incluir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payloadRemessa)
        });
        const data = await resp.json();
        if (data.success || data.cCodStatus === "0" || data.nCodRem) {
            alert(`✅ Remessa de Produto para Guarulhos Macedo (CNPJ 07.044.456/0092-30) lançada com sucesso no Omie!\nCódigo Omie: ${data.data?.nCodRem || data.nCodRem || data.cCodIntRem || ''}`);
            state.itensSelecionadosRemessa = {};
            state.skusChecadosCD.clear();
            render();
            carregarRemessasOmie();
        } else {
            alert(`❌ Erro ao enviar Remessa: ${data.message || data.cDesStatus || JSON.stringify(data)}`);
        }
    } catch (e) {
        alert(`❌ Erro na comunicação com o servidor: ${e.message}`);
    }
}

// ==========================================
// FUNÇÕES DO MODAL DE OPÇÕES DE REMESSA
// ==========================================
function abrirModalOpcoesRemessa() {
    let skus = Object.keys(state.itensSelecionadosRemessa).filter(sku => state.itensSelecionadosRemessa[sku] > 0);
    
    // Se marcou checkboxes mas o valor ficou 0, preenche com 1 ou a quantidade necessária/disponível
    if (skus.length === 0 && state.skusChecadosCD.size > 0) {
        state.skusChecadosCD.forEach(sku => {
            const p = state.produtos.find(prod => prod.sku === sku);
            if (p) {
                const nec = calcularNecessidade(p, state.periodoDias, state.abastecimentoDias, 'cd');
                const qtd = (p.matriz >= nec && nec > 0) ? nec : (p.matriz > 0 ? p.matriz : 1);
                state.itensSelecionadosRemessa[sku] = qtd;
            }
        });
        skus = Object.keys(state.itensSelecionadosRemessa).filter(sku => state.itensSelecionadosRemessa[sku] > 0);
    }

    if (skus.length === 0) {
        alert('⚠️ Marque ao menos um produto com quantidade a enviar maior que zero (Qtd a Enviar) para gerar a remessa.');
        return;
    }

    const modal = document.getElementById('modal-gerar-remessa');
    if (modal) {
        modal.classList.add('active');
        carregarRemessasPendentesSelect();
    } else {
        // Fallback direto se o modal não for encontrado no DOM
        enviarRemessaOmie();
    }
}

function fecharModalOpcoesRemessa() {
    const modal = document.getElementById('modal-gerar-remessa');
    if (modal) modal.classList.remove('active');
}

async function carregarRemessasPendentesSelect(forceSync = false) {
    const select = document.getElementById('select-remessa-existente');
    if (!select) return;
    select.innerHTML = '<option value="">Carregando remessas em aberto...</option>';
    try {
        const resp = await fetch('/api/remessas/listar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force_sync: forceSync })
        });
        const data = await resp.json();
        const remessas = data.remessas || data.remessas_lista || (data.data && data.data.remessas_lista) || [];
        
        // Filtra APENAS as remessas em aberto (Não Faturadas e Não Canceladas)
        let pendentes = remessas.filter(r => {
            const c = r.cabec || r.cabecalho || {};
            const fat = (c.faturada || r.faturada || 'N').toString().toUpperCase();
            const canc = (c.cCancelado || r.cancelada || 'N').toString().toUpperCase();
            return fat !== 'S' && canc !== 'S';
        });

        // Se não achou remessa em aberto no banco local e ainda não tentamos sincronizar a Omie, força sync
        if (pendentes.length === 0 && !forceSync) {
            return carregarRemessasPendentesSelect(true);
        }

        if (pendentes.length === 0) {
            select.innerHTML = '<option value="">Nenhuma remessa em aberto encontrada.</option>';
        } else {
            select.innerHTML = '<option value="">-- Selecione uma Remessa em Aberto --</option>';
            pendentes.forEach(r => {
                const c = r.cabec || r.cabecalho || {};
                const codRem = c.nCodRem || r.codigo_remessa || r.remessa_id;
                const numRem = c.cNumeroRemessa || r.numero_remessa || codRem || 'S/N';
                const dPrev = c.dPrevisao || r.data_previsao || '-';
                select.innerHTML += `<option value="${codRem}">Remessa #${numRem} - Previsão: ${dPrev}</option>`;
            });
        }
    } catch(e) {
        select.innerHTML = '<option value="">Erro ao carregar remessas em aberto.</option>';
    }
}

async function processarOpcaoRemessa() {
    const tipo = document.querySelector('input[name="tipo_remessa"]:checked').value;
    
    if (tipo === 'NOVA') {
        fecharModalOpcoesRemessa();
        enviarRemessaOmie(); // Fluxo original de IncluirRemessa
    } else {
        const nCodRem = document.getElementById('select-remessa-existente').value;
        if (!nCodRem) {
            alert('Por favor, selecione uma remessa existente na lista.');
            return;
        }
        fecharModalOpcoesRemessa();
        adicionarItensRemessaExistente(parseInt(nCodRem));
    }
}

async function adicionarItensRemessaExistente(nCodRem) {
    const skus = Object.keys(state.itensSelecionadosRemessa);
    let pesoNovosItens = 0;
    const produtosAdicionais = [];

    skus.forEach(sku => {
        const qtd = state.itensSelecionadosRemessa[sku];
        const p = state.produtos.find(prod => prod.sku === sku);
        if (!p) return;

        const vUnit = parseFloat((p.valor_unitario || p.preco_unitario || p.preco || p.valor_unitario_venda || 15.00).toString()) || 15.00;
        const pesoProd = parseFloat((p.peso_kg || p.peso || 0.2).toString().replace(',', '.'));
        pesoNovosItens += (pesoProd * qtd);

        produtosAdicionais.push({
            cCodItInt: p.sku,
            nCodProd: p.id_produto || 0,
            nQtde: qtd,
            nValUnit: vUnit,
            cCFOP: "6.152",
            codigo_local_estoque: 1794541746,
            ICMS: { cModBC: "", cOrigem: "0", cSitTrib: "41", nAliq: 0, nBC: 0, nRedBC: 0, nValor: 0 },
            PIS: { cSitTribPIS: "07", cTpCalcPIS: "", nAliqPIS: 0, nBCPIS: 0, nQtdUTPIS: 0, nValPISUT: 0, nValPIS: 0 },
            COFINS: { cSitTribCOFINS: "07", cTpCalcCOFINS: "", nAliqCOFINS: 0, nBCCOFINS: 0, nQtdUTCOFINS: 0, nVaCOFINSSUT: 0, nValCOFINS: 0 },
            infAdicItem: {
                codigo_cenario_impostos_item: 1818511574,
                cNaoMovEstoque: "N",
                nPesoBruto: parseFloat(pesoProd.toFixed(3)),
                nPesoLiq: parseFloat((pesoProd * 0.9).toFixed(3))
            }
        });
    });

    if (!confirm(`Confirma a adição de ${produtosAdicionais.length} produtos (Peso Novo: ${pesoNovosItens.toFixed(2)}kg) à Remessa #${nCodRem}?`)) return;

    // Mostra loading
    const btn = document.getElementById('btn-generate-transfer');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Atualizando...';
    btn.disabled = true;

    try {
        const resp = await fetch('/api/remessas/alterar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nCodRem, novosProdutos: produtosAdicionais })
        });
        const data = await resp.json();
        
        if (data.success) {
            alert(`✅ Remessa #${nCodRem} atualizada com sucesso no Omie!`);
            state.itensSelecionadosRemessa = {};
            state.skusChecadosCD.clear();
            render();
            carregarRemessasOmie(true); // Forçar Sincronização
        } else {
            alert(`❌ Erro ao atualizar Remessa: ${data.message || data.cDesStatus || JSON.stringify(data)}`);
        }
    } catch(e) {
        alert(`❌ Erro de conexão ao tentar atualizar a remessa.`);
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// ==========================================
// Carregar e Exibir Remessas no Tab 3
async function carregarRemessasOmie(forceSync = false) {
    const tbody = document.getElementById('tbody-remessas');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 20px;"><i class="fa-solid fa-spinner fa-spin"></i> Carregando remessas de transferencia (Guarulhos Macedo)...</td></tr>`;

    try {
        const resp = await fetch('/api/remessas/listar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force_sync: forceSync })
        });
        const data = await resp.json();
        
        if (data.status === 'error') {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #f87171; padding: 20px;">Erro Omie: ${data.message}</td></tr>`;
            return;
        }

        let status_transito_map = {};
        try {
            const respSt = await fetch('/api/remessas/status_transito');
            if (respSt.ok) {
                const dataSt = await respSt.json();
                status_transito_map = dataSt.status_map || {};
            }
        } catch (e) {
            console.warn('Não foi possível carregar status_transito:', e);
        }

        const remessas = data.remessas || data.remessas_lista || (data.data && (data.data.remessas || data.data.remessas_lista)) || [];
        if (remessas.length > 0) {
            renderTabelaRemessas(remessas, status_transito_map);
            atualizarEmTransitoProdutos(remessas, status_transito_map);
        } else {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #f87171; padding: 20px;">Nenhuma remessa encontrada ou erro no Omie: ${data.message || ''}</td></tr>`;
        }

    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #f87171; padding: 20px;">Erro ao carregar remessas: ${e.message}</td></tr>`;
    }
}

// Calcular soma em trânsito por SKU baseado nas remessas com status "EM_TRANSPORTE" ou "COLETADO"
async function atualizarEmTransitoProdutos(remessas, statusMap) {
    const somaTransitoPorSku = {};

    for (const r of remessas) {
        const c = r.cabec || {};
        const codRem = c.nCodRem || r.codigo_remessa || r.remessa_id;
        const numRem = c.cNumeroRemessa || r.numero_remessa || codRem;
        const remessaId = String(numRem || codRem || '');
        const stTransito = (statusMap[remessaId] || statusMap[String(codRem)] || r.status_transito || 'PENDENTE').toUpperCase();

        // Se o status alterado pelo usuário for EM_TRANSPORTE ou COLETADO, somamos os itens
        if (stTransito === 'EM_TRANSPORTE' || stTransito === 'COLETADO') {
            let itens = r.produtos || r.det || r.itens || [];

            // Se os itens não estiverem pré-carregados na remessa, busca da API Omie
            if (itens.length === 0 && codRem) {
                try {
                    const resp = await fetch('/api/remessas/status', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ nCodRem: codRem, cCodIntRem: "" })
                    });
                    const resData = await resp.json();
                    if (resData.success && resData.data) {
                        const rDetalhe = resData.data;
                        itens = rDetalhe.produtos || rDetalhe.det || rDetalhe.itens || rDetalhe.itensRemessa || rDetalhe.listaProdutos || [];
                        if (itens.length === 0 && rDetalhe.data) {
                            itens = rDetalhe.data.produtos || rDetalhe.data.det || rDetalhe.data.itens || [];
                        }
                        if (itens.length > 0) {
                            r.produtos = itens;
                            r.itens = itens;
                        }
                    }
                } catch (e) {
                    console.warn('Erro ao carregar itens em trânsito para remessa', codRem, e);
                }
            }

            itens.forEach(item => {
                const prod = item.produto || item;
                const sku = String(item.cCodItInt || prod.cCodItInt || prod.cCodigo || prod.codigo_produto || prod.cSKU || '').trim();
                const qtd = parseFloat(item.nQtde || item.nQtd || item.quantidade || prod.nQtde || prod.nQtd || 0);

                if (sku && qtd > 0) {
                    somaTransitoPorSku[sku] = (somaTransitoPorSku[sku] || 0) + qtd;
                    const skuPad = String(sku).padStart(6, '0');
                    if (skuPad !== sku) {
                        somaTransitoPorSku[skuPad] = (somaTransitoPorSku[skuPad] || 0) + qtd;
                    }
                }
            });
        }
    }

    // Atualizar no estado global de produtos
    let houveAlteracao = false;
    state.produtos.forEach(p => {
        const skuPad = String(p.sku).padStart(6, '0');
        const qtdTransitoCalculada = somaTransitoPorSku[p.sku] || somaTransitoPorSku[skuPad] || 0;
        if (p.em_transito !== qtdTransitoCalculada) {
            p.em_transito = qtdTransitoCalculada;
            houveAlteracao = true;
        }
    });

    renderTabCD();
}

function renderTabelaRemessas(remessas, statusMap = {}) {
    const tbody = document.getElementById('tbody-remessas');
    tbody.innerHTML = '';

    // Filtrar e garantir apenas remessas válidas de Guarulhos Macedo
    const remessasGuarulhos = remessas.filter(r => {
        const c = r.cabec || r.cabecalho || r;
        const codRem = (c.nCodRem || r.codigo_remessa || r.remessa_id || '').toString();
        const numRem = (c.cNumeroRemessa || r.numero_remessa || '').toString();

        if (!codRem || codRem === '0' || codRem.toLowerCase() === 'undefined' || numRem.toLowerCase() === 'undefined') {
            return false;
        }

        const obs = (r.obs ? (r.obs.cObs || '') : (r.observacao || '')).toUpperCase();
        const dadosAdic = (r.infAdic ? (r.infAdic.cDadosAdic || '') : '').toUpperCase();
        const nCli = (c.nCodCli || r.nCodCli || '').toString();
        
        return nCli === '2216843393' || obs.includes('GUARULHOS') || obs.includes('MACEDO') || obs.includes('0092-30') || obs.includes('009230') || dadosAdic.includes('GUARULHOS') || dadosAdic.includes('MACEDO') || dadosAdic.includes('0092-30') || true;
    });

    // Ordenar do MAIS ATUAL para o MAIS ANTIGO
    remessasGuarulhos.sort((a, b) => {
        const cA = a.cabec || a.cabecalho || a;
        const cB = b.cabec || b.cabecalho || b;
        const idA = parseInt(cA.nCodRem || a.codigo_remessa || cA.cNumeroRemessa || a.numero_remessa || 0);
        const idB = parseInt(cB.nCodRem || b.codigo_remessa || cB.cNumeroRemessa || b.numero_remessa || 0);
        return idB - idA;
    });

    if (remessasGuarulhos.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 20px;">Nenhuma remessa de transferência para Guarulhos Macedo (CNPJ 07.044.456/0092-30) encontrada.</td></tr>`;
        return;
    }

    remessasGuarulhos.slice(0, 50).forEach(r => {
        const c = r.cabec || r.cabecalho || r;
        const codRem = c.nCodRem || r.codigo_remessa || r.remessa_id;
        const numRem = c.cNumeroRemessa || r.numero_remessa || codRem;
        const remessaId = String(numRem || codRem || '');
        const obsFormatada = 'COMUNIDADE CATOLICA SHALOM GUARULHOS MACEDO';
        
        const isFaturada = (c.faturada || r.faturada || 'N').toString().toUpperCase() === 'S';
        const isCancelada = (c.cCancelado || r.cancelada || 'N').toString().toUpperCase() === 'S';
        
        let statusBadge = '<span class="badge badge-alerta">Em Aberto / Criada</span>';
        if (isCancelada) statusBadge = '<span class="badge badge-ruptura">Cancelada</span>';
        else if (isFaturada) statusBadge = '<span class="badge badge-estavel">Faturada (NF-e Emitida)</span>';

        const stSalvo = statusMap[remessaId] || statusMap[String(codRem)] || r.status_transito || 'PENDENTE';

        const vTotal = parseFloat(c.nValorTotal || c.nTotRem || r.valor_total || 0.0);

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${numRem}</strong><br><small style="color:var(--text-muted);">ID: ${codRem}</small></td>
            <td><strong>${obsFormatada}</strong></td>
            <td>${c.dPrevisao || r.data_previsao || '-'}</td>
            <td>${statusBadge}</td>
            <td><strong>R$ ${vTotal.toFixed(2)}</strong></td>
            <td>
                <select class="select-status-transito" data-remessa-id="${remessaId}" style="padding: 6px 10px; border-radius: 6px; background: #1e293b; color: #fff; border: 1px solid #334155; cursor: pointer; font-weight: 500;">
                    <option value="PENDENTE" ${stSalvo === 'PENDENTE' ? 'selected' : ''}>⚪ Pendente</option>
                    <option value="COLETADO" ${stSalvo === 'COLETADO' ? 'selected' : ''}>🟡 Coletado</option>
                    <option value="EM_TRANSPORTE" ${stSalvo === 'EM_TRANSPORTE' ? 'selected' : ''}>🚚 Em Transporte</option>
                    <option value="ENTREGUE" ${stSalvo === 'ENTREGUE' ? 'selected' : ''}>✅ Entregue</option>
                </select>
            </td>
            <td>
                <button class="btn btn-sm btn-secondary btn-consultar-remessa" data-cod="${codRem}">
                    <i class="fa-solid fa-eye"></i> Detalhes
                </button>
            </td>
        `;

        const selectSt = tr.querySelector('.select-status-transito');
        selectSt.addEventListener('change', async (e) => {
            const novoSt = e.target.value;
            try {
                const resp = await fetch('/api/remessas/salvar_status_transito', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ remessa_id: remessaId, nCodRem: codRem, cNumeroRemessa: numRem, status_transito: novoSt })
                });
                const resData = await resp.json();
                if (resData.success) {
                    statusMap[remessaId] = novoSt;
                    statusMap[String(codRem)] = novoSt;
                    statusMap[String(numRem)] = novoSt;
                    r.status_transito = novoSt;
                    await atualizarEmTransitoProdutos(remessasGuarulhos, statusMap);
                } else {
                    alert('Erro ao salvar status de trânsito.');
                }
            } catch (err) {
                alert('Erro na comunicação com o servidor ao salvar status.');
            }
        });

        tr.querySelector('.btn-consultar-remessa').addEventListener('click', () => consultarRemessaDetalhes(r));
        tbody.appendChild(tr);
    });
}

async function consultarRemessaDetalhes(remessaObj) {
    const modal = document.getElementById('modal-detalhes-remessa');
    if (!modal) return;

    const c = remessaObj.cabec || {};
    const nCodRem = c.nCodRem || remessaObj.codigo_remessa;

    document.getElementById('detalhes-remessa-num').innerText = `#${c.cNumeroRemessa || c.nCodRem || nCodRem}`;
    
    const headerInfo = document.getElementById('detalhes-remessa-header-info');
    headerInfo.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; font-size: 0.9rem;">
            <div><strong>Cliente / Destino:</strong> ${DADOS_FISCAIS.cliente_nome}</div>
            <div><strong>Previsão de Entrega:</strong> ${c.dPrevisao || '-'}</div>
            <div><strong>Valor Total da Nota:</strong> R$ ${(c.nValorTotal || c.nTotRem || 0).toFixed(2)}</div>
            <div><strong>Carregando itens do Omie ERP...</strong></div>
        </div>
    `;

    const tbody = document.getElementById('tbody-detalhes-remessa-itens');
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 20px; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Consultando produtos na Omie...</td></tr>`;

    modal.classList.add('active');

    const btnClose = document.getElementById('btn-close-detalhes-remessa');
    const btnCancel = document.getElementById('btn-cancel-detalhes-remessa');
    const fechar = () => modal.classList.remove('active');
    if (btnClose) btnClose.onclick = fechar;
    if (btnCancel) btnCancel.onclick = fechar;

    let itens = remessaObj.produtos || remessaObj.det || remessaObj.itens || [];

    // Se a remessa da listagem não contiver a propriedade de itens, fazemos chamada à API /api/remessas/status para buscar os detalhes
    if (itens.length === 0 && nCodRem) {
        try {
            const resp = await fetch('/api/remessas/status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nCodRem: nCodRem, cCodIntRem: "" })
            });
            const resData = await resp.json();
            if (resData.success && resData.data) {
                const rDetalhe = resData.data;
                itens = rDetalhe.produtos || rDetalhe.det || rDetalhe.itens || rDetalhe.itensRemessa || rDetalhe.listaProdutos || (rDetalhe.cabec && rDetalhe.cabec.itens) || [];
                if (itens.length === 0 && rDetalhe.data) {
                    itens = rDetalhe.data.produtos || rDetalhe.data.det || rDetalhe.data.itens || [];
                }
                if (itens.length > 0) {
                    remessaObj.itens = itens;
                    remessaObj.produtos = itens;
                    // Notifica servidor para salvar itens no banco de dados
                    const payloadSave = { remessa_id: String(c.cNumeroRemessa || c.nCodRem), nCodRem: c.nCodRem, cNumeroRemessa: c.cNumeroRemessa, itens: itens };
                    if (remessaObj.status_transito) {
                        payloadSave.status_transito = remessaObj.status_transito;
                    }
                    fetch('/api/remessas/salvar_status_transito', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payloadSave)
                    }).catch(() => {});
                }
            }
        } catch (err) {
            console.warn('Erro ao consultar detalhes via API Omie:', err);
        }
    }

    headerInfo.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; font-size: 0.9rem;">
            <div><strong>Cliente / Destino:</strong> ${DADOS_FISCAIS.cliente_nome}</div>
            <div><strong>Previsão de Entrega:</strong> ${c.dPrevisao || '-'}</div>
            <div><strong>Valor Total da Nota:</strong> R$ ${(c.nValorTotal || c.nTotRem || 0).toFixed(2)}</div>
            <div><strong>Total de Itens:</strong> ${itens.length} produto(s)</div>
        </div>
    `;

    tbody.innerHTML = '';

    if (itens.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 20px; color: #f87171;">Nenhum item encontrado ou falha ao retornar produtos desta remessa.</td></tr>`;
    } else {
        itens.forEach(item => {
            const prod = item.produto || item;
            const nCodProd = item.nCodProd || prod.nCodProd || 0;
            let rawSku = item.cCodItInt || prod.cCodItInt || prod.cCodigo || prod.codigo_produto || prod.cSKU || '';
            if (rawSku === 'undefined' || rawSku === 'null') rawSku = '';

            const skuPad = rawSku ? String(rawSku).padStart(6, '0') : '';
            const pMatched = (state.produtos || []).find(p => 
                (rawSku && (p.sku === rawSku || p.codigo === rawSku || String(p.sku).padStart(6, '0') === skuPad)) ||
                (nCodProd && (p.id_produto == nCodProd || p.nCodProd == nCodProd || p.codigo_produto == nCodProd))
            );

            const sku = (pMatched ? (pMatched.sku || pMatched.codigo) : (rawSku || '-'));
            let desc = item.cDescricao || prod.cDescricao || prod.descricao || prod.nome;

            // Busca na lista global de produtos se a descrição não estiver no item
            if (!desc || desc === 'Produto Sem Nome') {
                if (pMatched) {
                    desc = pMatched.nome || pMatched.descricao;
                }
            }
            if (!desc) desc = 'Produto Sem Nome';

            const qtd = parseFloat(item.nQtde || item.nQtd || item.quantidade || prod.nQtde || prod.nQtd || 0);
            const vUnit = parseFloat(item.nValUnit || item.nPrecoUnit || item.valor_unitario || prod.nValUnit || 0);
            const vTotal = parseFloat(item.nValTotal || (qtd * vUnit) || 0);

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${sku}</strong></td>
                <td>${desc}</td>
                <td><strong style="color: var(--primary);">${qtd} un</strong></td>
                <td>R$ ${vUnit.toFixed(2)}</td>
                <td><strong>R$ ${vTotal.toFixed(2)}</strong></td>
            `;
            tbody.appendChild(tr);
        });
    }
}

// Gerar PDF da Remessa com jsPDF
function gerarPDFRemessa() {
    if (Object.keys(state.itensSelecionadosRemessa).length === 0) {
        alert('Selecione ao menos um produto para gerar a remessa em PDF.');
        return;
    }

    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    const texto = gerarTextoFiscal();

    doc.setFont("courier", "normal");
    doc.setFontSize(9);

    const linhas = texto.split('\n');
    let y = 15;

    linhas.forEach(linha => {
        if (y > 280) {
            doc.addPage();
            y = 15;
        }
        doc.text(linha, 10, y);
        y += 4.5;
    });

    doc.save(`remessa_cd_sp_${new Date().toISOString().slice(0,10)}.pdf`);
}

// ----------------------------------------------------------------------
// MODAL 1: GRADE DE TAMANHOS DE CAMISAS (PP a 3G/XGG)
// ----------------------------------------------------------------------
let modeloGradeAtual = null;

function abrirGradeCamisas(modeloBase) {
    if (!modeloBase) return;
    modeloGradeAtual = modeloBase;
    document.getElementById('grade-modelo-nome').innerText = `Modelo: ${modeloBase}`;
    const tbody = document.getElementById('tbody-grade-camisas');
    tbody.innerHTML = '';

    // Filtrar todas as variações deste modelo
    const variacoes = state.produtos.filter(p => p.modelo_base === modeloBase);
    
    // Ordenar tamanhos tradicionalmente
    const ordemTamanhos = ['PP', 'P', 'M', 'G', 'GG', 'XG', 'XGG', '3G', '4G', 'OUTRO'];
    variacoes.sort((a, b) => {
        const ia = ordemTamanhos.indexOf((a.tamanho || '').toUpperCase());
        const ib = ordemTamanhos.indexOf((b.tamanho || '').toUpperCase());
        return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });

    variacoes.forEach(p => {
        const emProd = state.producao.has(p.sku);
        const vendas = p[`vendas_geral_${state.periodoDias}d`] || 0;
        const lt = getLeadTimeFamilia(p.familia, 'matriz');
        const estAlvo = calcularEstoqueAlvo(vendas, state.periodoDias, state.abastecimentoDias, lt);
        const estMatrizDisp = getMatrizDisponivel(p);
        const status = definirStatus(estMatrizDisp, estAlvo, emProd, vendas, p.status_especial);

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${p.sku}</strong></td>
            <td><span class="tag-fam" style="font-size:0.85rem; font-weight:bold;">${p.tamanho || 'UN'}</span></td>
            <td><strong>${estMatrizDisp}</strong> un ${p.matriz_reservado > 0 ? `<small style="font-size:0.7rem; color:var(--text-muted);">(Fís: ${p.matriz})</small>` : ''}</td>
            <td>${estAlvo.toFixed(1)} un</td>
            <td><span class="badge ${status.class}">${status.label}</span></td>
            <td>
                <input type="checkbox" class="chk-prod-grade" data-sku="${p.sku}" ${emProd ? 'checked' : ''}>
            </td>
        `;

        tr.querySelector('.chk-prod-grade').addEventListener('change', async (e) => {
            const sku = e.target.dataset.sku;
            const isChecked = e.target.checked;
            if (isChecked) state.producao.add(sku);
            else state.producao.delete(sku);
            localStorage.setItem('drp_producao', JSON.stringify(Array.from(state.producao)));

            const pObj = state.produtos.find(prod => String(prod.sku).trim() === String(sku).trim());
            if (pObj) pObj.em_producao = isChecked;

            try {
                await fetch('/api/producao/salvar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sku, em_producao: isChecked })
                });
            } catch (errServ) {
                console.warn('Erro ao salvar producao grade no servidor:', errServ);
            }

            render();
        });

        tbody.appendChild(tr);
    });

    document.getElementById('modal-grade-camisas').classList.add('active');
}

function fecharModalGradeCamisas() {
    document.getElementById('modal-grade-camisas').classList.remove('active');
    render();
}

function fecharModalPedido() {
    const modal = document.getElementById('modal-detalhes-pedido');
    if (modal) modal.classList.remove('active');
}

window.abrirModalPedido = function(numPedido) {
    const modal = document.getElementById('modal-detalhes-pedido');
    if (!modal) return;

    numPedido = String(numPedido).trim();
    document.getElementById('ped-modal-numero').innerText = `#${numPedido}`;

    const itensPedido = state.produtos.filter(p => String(p.numero_pedido || '').trim() === numPedido);

    let fornecedor = '-';
    let previsao = '-';

    itensPedido.forEach(p => {
        if (p.fornecedor && p.fornecedor !== 'nan' && p.fornecedor !== 'None') fornecedor = p.fornecedor;
        if (p.data_previsao && p.data_previsao !== 'nan' && p.data_previsao !== 'None') previsao = p.data_previsao;
    });

    document.getElementById('ped-modal-fornecedor').innerText = fornecedor;
    document.getElementById('ped-modal-previsao').innerText = previsao;
    document.getElementById('ped-modal-total-itens').innerText = itensPedido.length;

    const tbody = document.getElementById('tbody-detalhes-pedido');
    tbody.innerHTML = '';

    if (itensPedido.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--text-muted); padding: 20px;">Nenhum produto encontrado no DRP para o Pedido #${numPedido}.</td></tr>`;
    } else {
        itensPedido.forEach(p => {
            const emProd = state.producao.has(p.sku);
            const vendas = p[`vendas_geral_${state.periodoDias}d`] || 0;
            const lt = getLeadTimeFamilia(p.familia, 'matriz');
            const estAlvo = calcularEstoqueAlvo(vendas, state.periodoDias, state.abastecimentoDias, lt);
            const estMatrizDisp = getMatrizDisponivel(p);
            const estCDDisp = getCDDisponivel(p);
            const status = definirStatus(estMatrizDisp, estAlvo, emProd, vendas, p.status_especial);

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${p.sku}</strong></td>
                <td><small>${p.nome}</small></td>
                <td><strong>${p.quantidade_producao || 0}</strong> un</td>
                <td><strong>${estMatrizDisp}</strong> un</td>
                <td><strong>${estCDDisp}</strong> un</td>
                <td><span class="badge ${status.class}">${status.label}</span></td>
                <td>
                    <button class="btn btn-sm btn-danger btn-remover-item-ped" data-sku="${p.sku}" title="Remover item da produção"><i class="fa-solid fa-trash"></i></button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        tbody.querySelectorAll('.btn-remover-item-ped').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const sku = e.currentTarget.dataset.sku;
                if (confirm(`Remover SKU ${sku} do Pedido #${numPedido}?`)) {
                    state.producao.delete(sku);
                    const prod = state.produtos.find(p => p.sku === sku);
                    if (prod) {
                        prod.em_producao = false;
                        delete prod.numero_pedido;
                        delete prod.fornecedor;
                        delete prod.data_previsao;
                    }
                    try {
                        await fetch('/api/producao/salvar', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ sku, em_producao: false, quantidade_producao: 0, data_previsao: '', numero_pedido: '', fornecedor: '' })
                        });
                    } catch (errServ) {
                        console.warn('Erro ao remover item da producao:', errServ);
                    }
                    abrirModalPedido(numPedido);
                    render();
                }
            });
        });
    }

    const btnRemoverPedido = document.getElementById('btn-remover-pedido-completo');
    if (btnRemoverPedido) {
        btnRemoverPedido.onclick = async () => {
            if (confirm(`Tem certeza que deseja remover TODOS os produtos do Pedido #${numPedido} da Produção? Ele não voltará mais a ser exibido.`)) {
                btnRemoverPedido.disabled = true;
                btnRemoverPedido.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Removendo...';
                try {
                    const resp = await fetch('/api/pedido_compra/remover', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ numero_pedido: String(numPedido) })
                    });
                    const resJson = await resp.json();
                    if (resJson.success) {
                        for (const p of itensPedido) {
                            state.producao.delete(p.sku);
                            p.em_producao = false;
                            p.numero_pedido = '';
                            p.fornecedor = '';
                            p.data_previsao = '';
                            p.qtd_producao = 0;
                            p.quantidade_producao = 0;
                        }
                        if (typeof mostrarNotificacao === 'function') {
                            mostrarNotificacao(`Pedido #${numPedido} removido da produção com sucesso!`, 'success');
                        }
                    } else {
                        alert(resJson.error || 'Erro ao remover pedido.');
                    }
                } catch (errServ) {
                    console.error('Erro ao remover pedido:', errServ);
                    alert('Falha na comunicação com o servidor.');
                } finally {
                    btnRemoverPedido.disabled = false;
                    btnRemoverPedido.innerHTML = '<i class="fa-solid fa-trash"></i> Remover Pedido Inteiro da Produção';
                    modal.classList.remove('active');
                    render();
                }
            }
        };
    }

    modal.classList.add('active');
};

function gerarRequisicaoGradeCamisas() {
    if (!modeloGradeAtual) return;
    const variacoes = state.produtos.filter(p => p.modelo_base === modeloGradeAtual);
    if (variacoes.length === 0) return;

    // Marcar todos os SKUs da grade na Matriz
    variacoes.forEach(p => {
        state.skusChecadosMatriz.add(p.sku);
    });
    
    fecharModalGradeCamisas();
    abrirModalRequisicaoCompra();
}

// ----------------------------------------------------------------------
// MODAL 2: PROJEÇÃO DE VELAS FÉRIAS DISCIPULADO (15/09 a 05/10 - 20 DIAS)
// ----------------------------------------------------------------------
let velasFeriasSelecionadas = {};
let estoqueDiscipuladoTexto = {};

function abrirModalVelasFerias() {
    const modal = document.getElementById('modal-velas-ferias');
    if (modal) modal.classList.add('active');

    try {
        const txtSalvo = localStorage.getItem('drp_velas_discipulado_texto');
        const txtArea = document.getElementById('txt-velas-discipulado');
        if (txtArea && txtSalvo) {
            txtArea.value = txtSalvo;
        }

        const selSalva = localStorage.getItem('drp_velas_discipulado_selecao');
        velasFeriasSelecionadas = selSalva ? JSON.parse(selSalva) : {};
        const estSalvo = localStorage.getItem('drp_estoque_discipulado_texto');
        estoqueDiscipuladoTexto = estSalvo ? JSON.parse(estSalvo) : {};

        renderizarTabelaVelasFerias();
    } catch (e) {
        console.error('[DRP] Erro ao renderizar tabela de velas férias:', e);
    }
}

function renderizarTabelaVelasFerias() {
    const tbody = document.getElementById('tbody-velas-ferias');
    if (!tbody) return;
    tbody.innerHTML = '';

    const velas = state.produtos.filter(p => {
        const nome = (p.nome || '').toUpperCase();
        const fam = (p.familia || '').toUpperCase();
        const ehVela = fam.includes('VELA') || nome.includes('VELA');
        const ehCombo = nome.includes('COMBO') || nome.includes('KIT') || fam.includes('COMBO') || fam.includes('KIT');
        return ehVela && !ehCombo && p.ativo !== false;
    });

    velas.forEach(p => {
        const vendas30d = p.vendas_geral_30d || 0;
        const vendasDiarias = vendas30d / 30.0;
        const demanda20d = Math.ceil(vendasDiarias * 20); // 20 dias de férias (15/09 a 05/10)
        const estDiscTxt = estoqueDiscipuladoTexto[p.sku] !== undefined ? estoqueDiscipuladoTexto[p.sku] : null;
        
        // Necessidade considerando o estoque informado pelo Discipulado
        const estDiscipuladoReal = estDiscTxt !== null ? estDiscTxt : 0;
        const necessidadeFerias = Math.max(0, demanda20d - p.matriz - estDiscipuladoReal);
        // Catálogo Discipulado: verde 'Sim' apenas se o produto estiver ativamente no catálogo do Discipulado (estoque_discipulado === true)
        const noDiscipulado = p.estoque_discipulado === true;

        const isChecked = velasFeriasSelecionadas[p.sku] !== undefined && velasFeriasSelecionadas[p.sku] > 0;
        const qtdVal = velasFeriasSelecionadas[p.sku] || necessidadeFerias || 1;

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <input type="checkbox" class="chk-vela-ferias" data-sku="${p.sku}" ${isChecked ? 'checked' : ''}>
            </td>
            <td><strong>${p.sku}</strong></td>
            <td>${p.nome}</td>
            <td>${noDiscipulado ? '<span class="badge badge-estavel">✅ Sim</span>' : '<span class="badge badge-discipulado">🕯️ Não</span>'}</td>
            <td>
                <strong style="color: ${estDiscTxt !== null ? '#60a5fa' : 'var(--text-muted)'}">
                    ${estDiscTxt !== null ? estDiscTxt + ' un' : '-'}
                </strong>
            </td>
            <td><strong>${p.matriz}</strong> un</td>
            <td>${vendasDiarias.toFixed(2)}/dia</td>
            <td><strong>${demanda20d}</strong> un</td>
            <td>
                <input type="number" min="0" value="${qtdVal}" class="input-number input-qtd-vela-ferias" data-sku="${p.sku}" style="width: 80px;">
            </td>
        `;

        tr.querySelector('.chk-vela-ferias').addEventListener('change', (e) => {
            const sku = e.target.dataset.sku;
            const inp = tr.querySelector('.input-qtd-vela-ferias');
            if (e.target.checked) {
                const val = parseInt(inp.value) || 1;
                velasFeriasSelecionadas[sku] = val;
            } else {
                delete velasFeriasSelecionadas[sku];
            }
            salvarSelecaoVelasLocalStorage();
        });

        tr.querySelector('.input-qtd-vela-ferias').addEventListener('input', (e) => {
            const sku = e.target.dataset.sku;
            const val = parseInt(e.target.value) || 0;
            if (val > 0) {
                velasFeriasSelecionadas[sku] = val;
                tr.querySelector('.chk-vela-ferias').checked = true;
            } else {
                delete velasFeriasSelecionadas[sku];
                tr.querySelector('.chk-vela-ferias').checked = false;
            }
            salvarSelecaoVelasLocalStorage();
        });

        tbody.appendChild(tr);
    });

    const chkAll = document.getElementById('chk-select-all-velas');
    if (chkAll) {
        chkAll.checked = false;
        chkAll.onchange = (e) => {
            const checked = e.target.checked;
            document.querySelectorAll('.chk-vela-ferias').forEach(chk => {
                chk.checked = checked;
                const sku = chk.dataset.sku;
                const tr = chk.closest('tr');
                const inp = tr.querySelector('.input-qtd-vela-ferias');
                if (checked) {
                    const val = parseInt(inp.value) || 1;
                    velasFeriasSelecionadas[sku] = val;
                } else {
                    delete velasFeriasSelecionadas[sku];
                }
            });
            salvarSelecaoVelasLocalStorage();
        };
    }
}

function salvarSelecaoVelasLocalStorage() {
    localStorage.setItem('drp_velas_discipulado_selecao', JSON.stringify(velasFeriasSelecionadas));
}

function processarTextoVelasDiscipulado() {
    const txtArea = document.getElementById('txt-velas-discipulado');
    if (!txtArea) return;
    const txt = txtArea.value.trim();
    if (!txt) {
        alert('Por favor, cole ou digite o texto com a lista de velas do Discipulado.');
        return;
    }

    localStorage.setItem('drp_velas_discipulado_texto', txt);

    // Filtrar velas genuínas do catálogo (excluir combos/kits)
    const velasCatalogo = state.produtos.filter(p => {
        const nome = (p.nome || '').toUpperCase();
        const fam = (p.familia || '').toUpperCase();
        const ehVela = fam.includes('VELA') || nome.includes('VELA');
        const ehCombo = nome.includes('COMBO') || nome.includes('KIT') || fam.includes('COMBO') || fam.includes('KIT');
        return ehVela && !ehCombo && p.ativo !== false;
    });

    const linhas = txt.split('\n');
    let reconhecidos = 0;
    let itensDetalhes = [];
    let naoEncontrados = [];

    linhas.forEach(linha => {
        const l = linha.trim();
        if (!l) return;

        let qtd = 1;
        const matchQtdInicio = l.match(/^(\d+)[\s*xX_-]*/);
        let textoBusca = l;

        if (matchQtdInicio) {
            qtd = parseInt(matchQtdInicio[1], 10);
            textoBusca = l.substring(matchQtdInicio[0].length).trim();
        } else {
            const matchQtdFim = l.match(/[\s*xX_-]+(\d+)\s*(un|und|pcs|peças)?$/i);
            if (matchQtdFim) {
                qtd = parseInt(matchQtdFim[1], 10);
                textoBusca = l.substring(0, matchQtdFim.index).trim();
            }
        }

        const termos = textoBusca.toUpperCase()
            .replace(/[^\w\s]/gi, '')
            .split(/\s+/)
            .filter(t => t.length > 2 && !['VELA', 'VELAS', 'COM', 'DE', 'DA', 'DO', 'UN', 'UND', 'PCS'].includes(t));

        let melhorMatch = null;
        let melhorScore = 0;

        velasCatalogo.forEach(p => {
            const nomeP = (p.nome || '').toUpperCase().replace(/[^\w\s]/gi, '');
            const skuP = (p.sku || '').toUpperCase();

            let score = 0;
            if (skuP === textoBusca.toUpperCase()) {
                score += 100;
            }

            termos.forEach(t => {
                if (nomeP.includes(t)) score += 10;
            });

            if (score > melhorScore) {
                melhorScore = score;
                melhorMatch = p;
            }
        });

        if (melhorMatch && melhorScore >= 10) {
            estoqueDiscipuladoTexto[melhorMatch.sku] = qtd;
            
            // Recalcular necessidade com base no estoque do Discipulado
            const vendas30d = melhorMatch.vendas_geral_30d || 0;
            const demanda20d = Math.ceil((vendas30d / 30.0) * 20);
            const necRecalculada = Math.max(0, demanda20d - melhorMatch.matriz - qtd);
            
            velasFeriasSelecionadas[melhorMatch.sku] = necRecalculada > 0 ? necRecalculada : 1;
            reconhecidos++;
            itensDetalhes.push(`<li><strong>${melhorMatch.sku}</strong> - ${melhorMatch.nome} (Estoque Discipulado: <strong>${qtd} un</strong> | Necessidade: <strong>${velasFeriasSelecionadas[melhorMatch.sku]} un</strong>)</li>`);
        } else {
            naoEncontrados.push(l);
        }
    });

    localStorage.setItem('drp_estoque_discipulado_texto', JSON.stringify(estoqueDiscipuladoTexto));
    salvarSelecaoVelasLocalStorage();
    renderizarTabelaVelasFerias();

    // Auto-recolher a caixa de texto para dar 100% de espaço para a tabela de velas
    const details = document.getElementById('details-importar-velas');
    if (details) {
        details.open = false;
    }

    const resDiv = document.getElementById('div-resultado-reconhecimento');
    if (resDiv) {
        let html = `<div style="padding: 8px 12px; border-radius: 6px; background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: #34d399; font-size: 0.85rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">`;
        html += `<div><strong>🎉 ${reconhecidos} vela(s) reconhecida(s) e marcada(s) na tabela abaixo!</strong>`;
        if (naoEncontrados.length > 0) {
            html += `<span style="color: #f87171; margin-left: 8px;">(⚠️ ${naoEncontrados.length} não associada(s): ${naoEncontrados.join(', ')})</span>`;
        }
        html += `</div>`;
        html += `<button class="btn btn-secondary btn-sm" onclick="document.getElementById('details-importar-velas').open = true" style="padding: 2px 8px; font-size: 0.78rem; background: rgba(255,255,255,0.1); color: #fff;">✏️ Ver / Editar Texto</button>`;
        html += `</div>`;
        resDiv.innerHTML = html;
    }
}

function limparTextoVelasDiscipulado() {
    const txtArea = document.getElementById('txt-velas-discipulado');
    if (txtArea) txtArea.value = '';
    localStorage.removeItem('drp_velas_discipulado_texto');
    localStorage.removeItem('drp_velas_discipulado_selecao');
    velasFeriasSelecionadas = {};
    const resDiv = document.getElementById('div-resultado-reconhecimento');
    if (resDiv) resDiv.innerHTML = '';
    renderizarTabelaVelasFerias();
}

function fecharModalVelasFerias() {
    document.getElementById('modal-velas-ferias').classList.remove('active');
}

function gerarRequisicaoVelasFerias() {
    const skusVelas = Object.keys(velasFeriasSelecionadas).filter(s => velasFeriasSelecionadas[s] > 0);
    if (skusVelas.length === 0) {
        alert('Selecione ao menos uma vela ou cole a lista de texto para gerar a requisição.');
        return;
    }

    // Filtrar EXCLUSIVAMENTE os produtos de velas selecionados (sem misturar com itens da Matriz)
    const produtosVelasExclusivas = state.produtos.filter(p => skusVelas.includes(p.sku));

    fecharModalVelasFerias();
    abrirModalRequisicaoCompra(produtosVelasExclusivas);
}

// ----------------------------------------------------------------------
// MODAL 3: REQUIÇÃO / PEDIDO DE COMPRA OMIE ERP (ABA 2 MATRIZ)
// ----------------------------------------------------------------------
function abrirModalRequisicaoCompra(itensExclusivos = null) {
    const tbody = document.getElementById('tbody-requisicao-compra');
    tbody.innerHTML = '';

    let produtosCompra = [];
    if (itensExclusivos && itensExclusivos.length > 0) {
        produtosCompra = itensExclusivos;
    } else if (state.skusChecadosMatriz && state.skusChecadosMatriz.size > 0) {
        // Se o usuário selecionou checkboxes específicas na Aba 2, filtrar SOMENTE os produtos selecionados!
        produtosCompra = state.produtos.filter(p => state.skusChecadosMatriz.has(p.sku));
    } else {
        // Se nenhum checkbox estiver marcado, sugere os produtos em Ruptura / Alerta
        produtosCompra = state.produtos.filter(p => {
            if (p.ativo === false || state.blacklist.has(p.sku)) return false;
            const fam = (p.familia || 'GERAL').toUpperCase();
            if (state.familiasExcluidas.has(fam)) return false;

            const vendas = p[`vendas_geral_${state.periodoDias}d`] || 0;
            const lt = getLeadTimeFamilia(p.familia, 'matriz');
            const estAlvo = calcularEstoqueAlvo(vendas, state.periodoDias, state.abastecimentoDias, lt);
            const nec = Math.max(0, Math.ceil(estAlvo - p.matriz));

            return nec > 0 && (p.matriz <= 0 || p.matriz / (estAlvo || 1) < 0.8);
        }).slice(0, 50);
    }

    if (produtosCompra.length === 0) {
        alert('Nenhum produto selecionado para requisição de compra.');
        return;
    }

    const payloadOmie = {
        codCateg: "2.04.06",
        codIntReqCompra: `REQ_${Date.now()}`,
        codProj: 0,
        dtSugestao: new Date(Date.now() + 15 * 86400000).toLocaleDateString('pt-BR'),
        obsReqCompra: `Requisição de Compra gerada pelo DRP Omie (${produtosCompra.length} itens)`,
        ItensReqCompra: produtosCompra.map(p => {
            let nec = velasFeriasSelecionadas[p.sku] || 0;
            if (nec <= 0) {
                const vendas = p[`vendas_geral_${state.periodoDias}d`] || 0;
                const lt = getLeadTimeFamilia(p.familia, 'matriz');
                const estAlvo = calcularEstoqueAlvo(vendas, state.periodoDias, state.abastecimentoDias, lt);
                nec = Math.max(1, Math.ceil(estAlvo - p.matriz));
            }
            return {
                codProd: p.id_produto || p.sku,
                codIntProd: p.sku,
                qtde: nec,
                precoUnit: p.valor_unitario || 10.00
            };
        })
    };

    document.getElementById('json-requisicao-compra').innerText = JSON.stringify(payloadOmie, null, 2);

    produtosCompra.forEach(p => {
        let nec = velasFeriasSelecionadas[p.sku] || 0;
        const vendas = p[`vendas_geral_${state.periodoDias}d`] || 0;
        const lt = getLeadTimeFamilia(p.familia, 'matriz');
        const estAlvo = calcularEstoqueAlvo(vendas, state.periodoDias, state.abastecimentoDias, lt);
        const estMatrizDisp = getMatrizDisponivel(p);
        if (nec <= 0) {
            nec = Math.max(1, Math.ceil(estAlvo - estMatrizDisp));
        }

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${p.sku}</strong></td>
            <td>${p.nome}</td>
            <td>${estMatrizDisp} un ${p.matriz_reservado > 0 ? `<small style="font-size:0.75rem; color:var(--text-muted);">(Fís: ${p.matriz})</small>` : ''}</td>
            <td>${estAlvo.toFixed(1)} un</td>
            <td><input type="number" min="1" value="${nec}" class="input-number input-qtd-compra" data-sku="${p.sku}"></td>
        `;
        tbody.appendChild(tr);
    });

    document.getElementById('modal-requisicao-compra').classList.add('active');
}

function fecharModalRequisicaoCompra() {
    document.getElementById('modal-requisicao-compra').classList.remove('active');
}

function copiarJsonCompra() {
    const jsonTxt = document.getElementById('json-requisicao-compra').innerText;
    navigator.clipboard.writeText(jsonTxt).then(() => {
        alert('Payload JSON de Requisição de Compra Omie copiado para a área de transferência!');
    });
}

async function enviarCompraOmie() {
    const btn = document.getElementById('btn-confirm-compra-omie');
    const originalText = btn ? btn.innerText : 'Enviar Pedido para Omie ERP';
    if (btn) {
        btn.disabled = true;
        btn.innerText = '⏳ Enviando para Omie ERP...';
    }

    try {
        const inputs = document.querySelectorAll('.input-qtd-compra');
        const itens = [];
        inputs.forEach(inp => {
            const sku = inp.getAttribute('data-sku');
            const qtd = parseFloat(inp.value) || 1;
            if (sku && qtd > 0) {
                itens.push({
                    sku: sku,
                    quantidade: qtd,
                    valor_unitario: 10.00
                });
            }
        });

        if (itens.length === 0) {
            alert('Nenhum item selecionado ou com quantidade válida.');
            return;
        }

        const res = await fetch('/api/requisicao-compra', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                codCateg: '2.04.06',
                dtSugestao: new Date(Date.now() + 15 * 86400000).toLocaleDateString('pt-BR'),
                obsReqCompra: `Requisição DRP Omie ERP (${itens.length} itens)`,
                itens: itens
            })
        });

        const data = await res.json();
        if (data.success) {
            // Adicionar automaticamente os SKUs enviados à lista de Produção
            itens.forEach(item => {
                if (item.sku) state.producao.add(item.sku);
            });
            localStorage.setItem('drp_producao', JSON.stringify(Array.from(state.producao)));

            alert(`🎉 ${data.message}\n\nCódigo da Requisição no Omie: ${data.codReqCompra}\nTotal de Itens: ${data.itens_enviados}\n\n📦 ${itens.length} produto(s) entrara(m) automaticamente no status 'Em Produção / Compra 🟣'!`);
            
            // Limpar seleções
            state.skusChecadosMatriz.clear();
            velasFeriasSelecionadas = {};
            localStorage.removeItem('drp_velas_discipulado_selecao');

            fecharModalRequisicaoCompra();
            render();
        } else {
            alert(`❌ Erro ao enviar requisição ao Omie ERP:\n${data.message}`);
        }
    } catch (err) {
        alert(`❌ Erro na comunicação com o servidor: ${err.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = originalText;
        }
    }
}

// Gerar PDF de Velas Selecionadas
function gerarPDFVelasFerias() {
    const skusVelas = Object.keys(velasFeriasSelecionadas).filter(s => velasFeriasSelecionadas[s] > 0);
    if (skusVelas.length === 0) {
        alert('Selecione ao menos uma vela para gerar o PDF.');
        return;
    }

    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    const dataStr = new Date().toLocaleDateString('pt-BR');

    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.text("PROJEÇÃO DE VELAS - FÉRIAS DISCIPULADO (15/SET A 05/OUT)", 14, 18);

    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.text(`Data do Relatório: ${dataStr} | Total de Itens: ${skusVelas.length}`, 14, 25);
    doc.text("--------------------------------------------------------------------------------------------------", 14, 30);

    let y = 38;
    doc.setFont("helvetica", "bold");
    doc.text("SKU", 14, y);
    doc.text("Descrição da Vela", 45, y);
    doc.text("Qtd Solicitada", 160, y);

    y += 4;
    doc.text("--------------------------------------------------------------------------------------------------", 14, y);
    y += 6;

    doc.setFont("helvetica", "normal");
    skusVelas.forEach(sku => {
        const p = state.produtos.find(prod => prod.sku === sku) || { sku, nome: 'VELA' };
        const qtd = velasFeriasSelecionadas[sku];

        if (y > 275) {
            doc.addPage();
            y = 20;
        }

        doc.text(p.sku, 14, y);
        doc.text((p.nome || '').slice(0, 50), 45, y);
        doc.text(`${qtd} un`, 160, y);
        y += 6;
    });

    doc.save(`projecao_velas_discipulado_${new Date().toISOString().slice(0,10)}.pdf`);
}

// Gerar PDF da Requisição de Compra / Pedido Omie
function gerarPDFRequisicaoCompra() {
    const inputs = document.querySelectorAll('.input-qtd-compra');
    const itens = [];
    inputs.forEach(inp => {
        const sku = inp.getAttribute('data-sku');
        const qtd = parseFloat(inp.value) || 0;
        if (sku && qtd > 0) {
            const p = state.produtos.find(prod => prod.sku === sku) || { sku, nome: 'PRODUTO' };
            itens.push({ sku: p.sku, nome: p.nome, qtd });
        }
    });

    if (itens.length === 0) {
        alert('Nenhum item selecionado na requisição para gerar PDF.');
        return;
    }

    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    const dataStr = new Date().toLocaleDateString('pt-BR');

    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.text("REQUISIÇÃO / PEDIDO DE COMPRA - OMIE ERP", 14, 18);

    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.text(`Data Sugestão: ${dataStr} | Total de Itens: ${itens.length}`, 14, 25);
    doc.text("--------------------------------------------------------------------------------------------------", 14, 30);

    let y = 38;
    doc.setFont("helvetica", "bold");
    doc.text("SKU", 14, y);
    doc.text("Produto", 45, y);
    doc.text("Qtd Solicitada", 160, y);

    y += 4;
    doc.text("--------------------------------------------------------------------------------------------------", 14, y);
    y += 6;

    doc.setFont("helvetica", "normal");
    itens.forEach(item => {
        if (y > 275) {
            doc.addPage();
            y = 20;
        }
        doc.text(item.sku, 14, y);
        doc.text((item.nome || '').slice(0, 50), 45, y);
        doc.text(`${item.qtd} un`, 160, y);
        y += 6;
    });

    doc.save(`requisicao_compra_omie_${new Date().toISOString().slice(0,10)}.pdf`);
}
function abrirModalEmailAlert() {
    document.getElementById('modal-email-alert').classList.add('active');
}

function fecharModalEmailAlert() {
    document.getElementById('modal-email-alert').classList.remove('active');
}

async function dispararAlertaEmailAgora() {
    const destinatarios = document.getElementById('input-email-destinatarios').value;
    const btnSend = document.getElementById('btn-send-email-alert-now');
    
    if (btnSend) {
        btnSend.disabled = true;
        btnSend.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enviando e-mail...';
    }

    try {
        const resp = await fetch('/api/email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ destinatarios })
        });

        const data = await resp.json();

        if (resp.ok && data.success) {
            alert(`📧 ${data.message}\n\nDestinatários: ${destinatarios}\nRelatório salvo localmente em data/ultimo_alerta_email.html`);
            fecharModalEmailAlert();
        } else {
            alert(`⚠️ Atenção ao Enviar E-mail:\n\n${data.message || 'Credenciais SMTP ausentes no .env'}\n\nO relatório HTML foi gerado em data/ultimo_alerta_email.html.`);
            fecharModalEmailAlert();
        }
    } catch (err) {
        console.error('Erro ao chamar API de e-mail:', err);
        alert(`❌ Erro ao conectar ao servidor backend:\n${err.message}\n\nCertifique-se de executar 'python server.py 8889'.`);
    } finally {
        if (btnSend) {
            btnSend.disabled = false;
            btnSend.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Disparar Alerta Agora';
        }
    }
}

// ----------------------------------------------------------------------
// MODAL 5: SINCRONIZAÇÃO SELETIVA & RECARREGAR DADOS OMIE ERP
// ----------------------------------------------------------------------
function abrirModalSyncSeletivo() {
    const modal = document.getElementById('modal-sync-seletivo');
    if (modal) modal.classList.add('active');
}

function fecharModalSyncSeletivo() {
    const modal = document.getElementById('modal-sync-seletivo');
    if (modal) modal.classList.remove('active');
    const msg = document.getElementById('sync-status-msg');
    if (msg) msg.style.display = 'none';
}

async function executarSyncSeletivo() {
    const tipo = document.getElementById('select-tipo-sync').value;
    const msg = document.getElementById('sync-status-msg');
    const btnSyncExec = document.getElementById('btn-execute-sync-seletivo') || document.getElementById('btn-exec-sync-seletivo');

    if (msg) {
        msg.style.display = 'block';
        msg.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Conectando à API Omie ERP (0%)...';
    }
    if (btnSyncExec) btnSyncExec.disabled = true;

    const descricoes = {
        'TUDO': 'Sincronizar Tudo (Estoques + Vendas Matriz e CD_SP)',
        'ESTOQUE_CD': 'Puxar apenas Estoque Novo do CD_SP',
        'ESTOQUE_MATRIZ': 'Puxar apenas Estoque Novo da Matriz',
        'AMBOS_ESTOQUES': 'Puxar Ambos os Estoques (Matriz + CD_SP)',
        'VENDAS_CD': 'Puxar apenas Vendas de SP (Sul/Sudeste)',
        'VENDAS_MATRIZ': 'Puxar apenas Vendas Gerais (Nacional)',
        'AMBAS_VENDAS': 'Puxar Ambas as Vendas (Matriz + CD_SP)'
    };

    let progress = 10;
    const timer = setInterval(() => {
        if (progress < 90) {
            progress += 20;
            if (msg) msg.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Atualizando estoque Omie & Turso DB (${progress}%)...`;
        }
    }, 400);

    try {
        const resp = await fetch('/api/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tipo })
        });

        clearInterval(timer);
        const resData = await resp.json();

        if (msg) msg.innerHTML = '<i class="fa-solid fa-circle-check" style="color:#34d399;"></i> Sincronização concluída com sucesso (100%)!';

        if (resp.ok && resData.success) {
            await carregarProdutos();
            setTimeout(() => {
                if (msg) msg.style.display = 'none';
                fecharModalSyncSeletivo();
                alert(`✅ Sincronização concluída com sucesso (100%)!\n\nOpção executada: ${descricoes[tipo] || tipo}\n${resData.count || 0} produtos sincronizados e atualizados no banco de dados Turso.`);
            }, 600);
        } else {
            throw new Error(resData.message || 'Erro ao sincronizar dados');
        }
    } catch (err) {
        clearInterval(timer);
        console.error('Erro no sync seletivo:', err);
        alert(`❌ Falha na sincronização:\n${err.message}\n\nCertifique-se de executar 'python server.py 8889'.`);
    } finally {
        if (btnSyncExec) btnSyncExec.disabled = false;
    }
}

/* ==========================================================================
   ABA 4: ANÁLISE DE PRODUTOS DA MATRIZ (MATRIZ BCG)
   ========================================================================== */

function renderizarAbaAnaliseMatriz() {
    const tbody = document.getElementById('tbody-analise-matriz');
    if (!tbody) return;

    const searchTerm = (document.getElementById('search-analise-matriz')?.value || '').toLowerCase().trim();
    const filterCat = document.getElementById('filter-categoria-bcg')?.value || 'TODOS';
    const bcgWindow = document.getElementById('select-bcg-window')?.value || '30_30';

    if (!state.produtos || state.produtos.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 25px;">Nenhum produto carregado.</td></tr>`;
        return;
    }

    // 1. Filtrar produtos ativos e não-blacklist
    const prodsAtivos = state.produtos.filter(p => p.ativo !== false && !state.blacklist.has(p.sku));

    // 2. Calcular Vendas Recentes e Anteriores por Produto
    const analisados = prodsAtivos.map(p => {
        let rec = 0;
        let ant = 0;

        if (bcgWindow === '30_30') {
            rec = p.vendas_geral_30d || 0;
            ant = Math.max(0, (p.vendas_geral_60d || 0) - (p.vendas_geral_30d || 0));
        } else {
            rec = p.vendas_geral_60d || 0;
            ant = Math.max(0, (p.vendas_geral_180d || 0) - (p.vendas_geral_60d || 0));
        }

        const totalVendasHist = (p.vendas_geral_180d || 0) + (p.vendas_geral_90d || 0) + (p.vendas_geral_30d || 0);

        let varPct = 0;
        if (ant > 0) {
            varPct = ((rec - ant) / ant) * 100;
        } else if (rec > 0) {
            varPct = 100.0;
        }

        return {
            produto: p,
            rec,
            ant,
            varPct,
            totalVendasHist
        };
    });

    // 3. Determinar Mediana de Vendas para Threshold de Volume Alto/Baixo
    const vendasComVendas = analisados.map(a => a.rec).filter(v => v > 0).sort((a, b) => a - b);
    let volumeThreshold = 5;
    if (vendasComVendas.length > 0) {
        const mid = Math.floor(vendasComVendas.length / 2);
        volumeThreshold = vendasComVendas.length % 2 !== 0 ? vendasComVendas[mid] : (vendasComVendas[mid - 1] + vendasComVendas[mid]) / 2;
        volumeThreshold = Math.max(2, volumeThreshold);
    }

    // 4. Classificar cada produto na Matriz BCG
    let countEstrela = 0;
    let countVaca = 0;
    let countInterrogacao = 0;
    let countAbacaxi = 0;
    let countInsuficiente = 0;

    analisados.forEach(item => {
        const { rec, ant, varPct, totalVendasHist } = item;

        // Se o produto não possui histórico de vendas suficiente em nenhum período
        if (rec === 0 && ant === 0 && totalVendasHist === 0) {
            item.categoria = 'DADOS_INSUFICIENTES';
            item.categoriaLabel = '⚠️ Dados insuficientes';
            item.badgeClass = 'badge-bcg-insuficiente';
            countInsuficiente++;
            return;
        }

        const volAlto = rec >= volumeThreshold;
        const crescAlto = varPct >= 0;

        if (volAlto && crescAlto) {
            item.categoria = 'ESTRELA';
            item.categoriaLabel = '⭐ Estrela';
            item.badgeClass = 'badge-bcg-estrela';
            countEstrela++;
        } else if (volAlto && !crescAlto) {
            item.categoria = 'VACA_LEITEIRA';
            item.categoriaLabel = '🐮 Vaca leiteira';
            item.badgeClass = 'badge-bcg-vaca';
            countVaca++;
        } else if (!volAlto && crescAlto) {
            item.categoria = 'INTERROGACAO';
            item.categoriaLabel = '❓ Interrogação';
            item.badgeClass = 'badge-bcg-interrogacao';
            countInterrogacao++;
        } else {
            item.categoria = 'ABACAXI';
            item.categoriaLabel = '🍍 Abacaxi';
            item.badgeClass = 'badge-bcg-abacaxi';
            countAbacaxi++;
        }
    });

    // 5. Atualizar Cards KPI
    const elEst = document.getElementById('kpi-count-estrela');
    const elVac = document.getElementById('kpi-count-vaca');
    const elInt = document.getElementById('kpi-count-interrogacao');
    const elAba = document.getElementById('kpi-count-abacaxi');
    const elIns = document.getElementById('kpi-count-insuficiente');

    if (elEst) elEst.innerText = countEstrela;
    if (elVac) elVac.innerText = countVaca;
    if (elInt) elInt.innerText = countInterrogacao;
    if (elAba) elAba.innerText = countAbacaxi;
    if (elIns) elIns.innerText = countInsuficiente;

    // Highlight no Card selecionado
    document.querySelectorAll('.clickable-card[data-bcg-filter]').forEach(card => {
        if (card.dataset.bcgFilter === filterCat) {
            card.classList.add('active-filter');
        } else {
            card.classList.remove('active-filter');
        }
    });

    // 6. Aplicar Filtros de Busca e Categoria
    let exibidos = analisados.filter(item => {
        const p = item.produto;
        const matchSearch = !searchTerm || p.sku.toLowerCase().includes(searchTerm) || (p.nome || '').toLowerCase().includes(searchTerm);
        const matchCat = filterCat === 'TODOS' || item.categoria === filterCat;
        return matchSearch && matchCat;
    });

    if (exibidos.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 25px;">Nenhum produto encontrado com os filtros selecionados.</td></tr>`;
        return;
    }

    // 7. Renderizar Linhas da Tabela
    tbody.innerHTML = exibidos.map(item => {
        const p = item.produto;
        const varFmt = item.categoria === 'DADOS_INSUFICIENTES' ? '-' : (item.varPct > 0 ? `+${item.varPct.toFixed(1)}%` : `${item.varPct.toFixed(1)}%`);
        const varColor = item.varPct > 0 ? '#34d399' : (item.varPct < 0 ? '#f87171' : 'var(--text-muted)');

        return `
            <tr>
                <td><strong>${p.sku}</strong></td>
                <td>
                    <div style="font-weight:600; color:var(--text-main);">${p.nome || 'Produto sem nome'}</div>
                </td>
                <td>
                    <span style="font-size:0.8rem; color:var(--text-muted);">${p.familia || '-'} / ${p.marca || '-'}</span>
                </td>
                <td style="text-align:center; font-weight:600;">${item.rec} un</td>
                <td style="text-align:center; font-weight:600; color:var(--text-muted);">${item.ant} un</td>
                <td style="text-align:center; font-weight:600; color:${varColor};">${varFmt}</td>
                <td style="text-align:center; font-weight:700; color:var(--primary);">${p.matriz || 0} un</td>
                <td style="text-align:center;">
                    <span class="badge-bcg ${item.badgeClass}">${item.categoriaLabel}</span>
                </td>
            </tr>
        `;
    }).join('');
}


/* ==========================================================================
   ABA 5: DEPÓSITOS DA MATRIZ & SUB-LOCAIS
   ========================================================================== */

// Carregar Dados de Sub-locais e Endereços do Servidor
async function carregarEDesenharDepositosMatriz() {
    try {
        const [respDep, respEnd] = await Promise.all([
            fetch('/api/depositos'),
            fetch('/api/depositos/enderecos')
        ]);
        if (respDep.ok) {
            const dataDep = await respDep.json();
            if (dataDep.depositos) state.depositos = dataDep.depositos;
        }
        if (respEnd.ok) {
            const dataEnd = await respEnd.json();
            if (dataEnd.enderecos) state.enderecos = dataEnd.enderecos;
        }
    } catch (e) {
        console.warn('Erro ao carregar dados de depósitos/endereços:', e);
    }
    renderizarAbaDepositosMatriz();
}

function alterarOrdenacaoDepositosSelect(val) {
    if (!val) return;
    const parts = val.split('_');
    state.sortDepositoField = parts[0];
    state.sortDepositoDir = parts[1] || 'desc';
    renderizarAbaDepositosMatriz();
}

function ordenarPorColunaDeposito(field) {
    if (state.sortDepositoField === field) {
        state.sortDepositoDir = state.sortDepositoDir === 'asc' ? 'desc' : 'asc';
    } else {
        state.sortDepositoField = field;
        state.sortDepositoDir = (field === 'sku' || field === 'nome') ? 'asc' : 'desc';
    }
    
    // Atualizar valor do select
    const sel = document.getElementById('sort-deposito-matriz');
    if (sel) {
        const targetVal = `${field}_${state.sortDepositoDir}`;
        const hasOption = Array.from(sel.options).some(opt => opt.value === targetVal);
        if (hasOption) sel.value = targetVal;
    }
    renderizarAbaDepositosMatriz();
}

function renderizarAbaDepositosMatriz() {
    const tbody = document.getElementById('tbody-depositos-matriz');
    if (!tbody) return;

    state.depositos = state.depositos || {};

    const searchTerm = (document.getElementById('search-depositos-matriz')?.value || '').toLowerCase().trim();
    const filterStatus = document.getElementById('filter-status-deposito')?.value || 'TODOS';

    if (!state.produtos || state.produtos.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 25px;">Nenhum produto carregado.</td></tr>`;
        return;
    }

    const prodsAtivos = state.produtos.filter(p => p.ativo !== false && !state.blacklist.has(p.sku));

    // Totais Consolidados p/ KPI Cards
    let sumTotalMatriz = 0;
    let sumFracionado = 0;
    let sumDep1 = 0;
    let sumDep2 = 0;
    let sumALocalizar = 0;

    let alertasPicking = [];
    let divergencias = [];

    const listaProcessada = prodsAtivos.map(p => {
        const skuStr = String(p.sku).trim();
        const totalMatriz = p.matriz || 0;
        const sub = state.depositos[skuStr] || { fracionado: 0, deposito_1: 0, deposito_2: 0 };
        
        const deposito1 = sub.deposito_1 || 0;
        const deposito2 = sub.deposito_2 || 0;
        
        // FÓRMULA CENTRAL ATUALIZADA:
        // Fracionado é o saldo remanescente do Estoque Físico Total da Matriz após separar o estoque nos Depósitos 1 e 2
        // Fracionado = Total Matriz - (Depósito 1 + Depósito 2)
        const fracionadoCalculado = totalMatriz - (deposito1 + deposito2);
        const fracionado = Math.max(0, fracionadoCalculado);
        
        // Divergência ocorre quando o total contado nos Depósitos 1 e 2 excede o Estoque Físico da Matriz
        const temDivergencia = fracionadoCalculado < 0;
        const aLocalizar = temDivergencia ? fracionadoCalculado : 0;

        sumTotalMatriz += totalMatriz;
        sumFracionado += fracionado;
        sumDep1 += deposito1;
        sumDep2 += deposito2;
        sumALocalizar += Math.abs(aLocalizar);

        // Alerta de Reabastecimento: Fracionado <= 5 com unidades guardadas no Dep 1 ou Dep 2
        const fracionadoZerado = fracionado <= 5 && totalMatriz > 0;
        const temEstoqueContadoEmOutro = deposito2 > 0 || deposito1 > 0;

        if (temDivergencia) {
            divergencias.push({ p, aLocalizar, fracionado, deposito1, deposito2, totalMatriz });
        }

        if (fracionadoZerado && temEstoqueContadoEmOutro) {
            const fonte = deposito2 > 0 ? `Depósito 2 (${deposito2} un)` : `Depósito 1 (${deposito1} un)`;
            alertasPicking.push({ p, fracionado, fonte, deposito1, deposito2, totalMatriz });
        }

        return {
            p,
            totalMatriz,
            fracionado,
            fracionadoCalculado,
            deposito1,
            deposito2,
            aLocalizar,
            temDivergencia,
            fracionadoZerado,
            temEstoqueContadoEmOutro
        };
    });

    // Guardar para o relatório de impressão/email
    window._ultimosAlertasPicking = alertasPicking;

    // Atualizar KPI Cards
    const elTotM = document.getElementById('kpi-dep-total-matriz');
    const elFrac = document.getElementById('kpi-dep-fracionado');
    const elDep1 = document.getElementById('kpi-dep-deposito1');
    const elDep2 = document.getElementById('kpi-dep-deposito2');
    const elALoc = document.getElementById('kpi-dep-alocalizar');

    if (elTotM) elTotM.innerText = sumTotalMatriz.toLocaleString('pt-BR');
    if (elFrac) elFrac.innerText = sumFracionado.toLocaleString('pt-BR');
    if (elDep1) elDep1.innerText = sumDep1.toLocaleString('pt-BR');
    if (elDep2) elDep2.innerText = sumDep2.toLocaleString('pt-BR');
    if (elALoc) elALoc.innerText = sumALocalizar.toLocaleString('pt-BR');

    // Renderizar Painel de Alertas
    const containerAlertas = document.getElementById('container-alertas-depositos');
    if (containerAlertas) {
        let htmlAlertas = '';
        if (divergencias.length > 0) {
            htmlAlertas += `
                <div class="alert-divergencia-box" style="margin-bottom:10px;">
                    <div>
                        <i class="fa-solid fa-triangle-exclamation fa-lg"></i>
                        <b>Atenção: ${divergencias.length} produto(s) com Divergência (Estoque nos Depósitos > Total Físico Matriz)!</b>
                        <span style="font-size:0.8rem; margin-left: 8px;">A soma contada nos Depósitos 1 e 2 excede o estoque no sistema. Verificar ajuste de estoque.</span>
                    </div>
                </div>
            `;
        }
        if (alertasPicking.length > 0) {
            htmlAlertas += `
                <div class="alert-picking-box" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                    <div>
                        <i class="fa-solid fa-box-archive fa-lg"></i>
                        <b>Assistência de Reabastecimento: ${alertasPicking.length} produto(s) necessitam busca para o Fracionado!</b>
                        <span style="font-size:0.8rem; margin-left: 8px;">O saldo no Fracionado é crítico (≤ 5 un). Buscar caixas no Depósito 1 ou 2.</span>
                    </div>
                    <div style="display:flex; gap:8px;">
                        <button class="btn btn-sm btn-success" style="padding:5px 12px; font-weight:600;" onclick="imprimirListaReabastecimento()">
                            <i class="fa-solid fa-print"></i> Imprimir Lista (PDF)
                        </button>
                        <button class="btn btn-sm btn-primary" style="padding:5px 12px; font-weight:600;" onclick="enviarEmailReabastecimento()">
                            <i class="fa-solid fa-envelope"></i> Enviar p/ E-mail
                        </button>
                    </div>
                </div>
            `;
        }
        containerAlertas.innerHTML = htmlAlertas;
    }

    // Filtrar Produtos para Tabela
    let exibidos = listaProcessada.filter(item => {
        const p = item.p;
        const matchSearch = !searchTerm || p.sku.toLowerCase().includes(searchTerm) || (p.nome || '').toLowerCase().includes(searchTerm);
        
        let matchStatus = true;
        if (filterStatus === 'DIVERGENCIA') matchStatus = item.temDivergencia;
        else if (filterStatus === 'ALERTA_PICKING') matchStatus = item.fracionadoZerado && item.temEstoqueContadoEmOutro;
        else if (filterStatus === 'LOCALIZADO') matchStatus = item.aLocalizar === 0 && item.fracionado > 0;
        else if (filterStatus === 'PENDENTE') matchStatus = item.aLocalizar < 0;

        return matchSearch && matchStatus;
    });

    // Ordenação Padronizada (Padrão: Depósito 2 Maior -> Menor)
    state.sortDepositoField = state.sortDepositoField || 'deposito2';
    state.sortDepositoDir = state.sortDepositoDir || 'desc';

    exibidos.sort((a, b) => {
        let valA, valB;
        if (state.sortDepositoField === 'sku') {
            valA = String(a.p.sku || '').toLowerCase();
            valB = String(b.p.sku || '').toLowerCase();
            return state.sortDepositoDir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
        } else if (state.sortDepositoField === 'nome') {
            valA = String(a.p.nome || '').toLowerCase();
            valB = String(b.p.nome || '').toLowerCase();
            return state.sortDepositoDir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
        } else {
            valA = Number(a[state.sortDepositoField] || 0);
            valB = Number(b[state.sortDepositoField] || 0);
            return state.sortDepositoDir === 'asc' ? valA - valB : valB - valA;
        }
    });

    // Atualizar Ícones de Ordenação nas colunas da Tabela
    ['sku', 'nome', 'totalMatriz', 'fracionado', 'deposito1', 'deposito2', 'aLocalizar'].forEach(f => {
        const iconEl = document.getElementById(`sort-icon-${f}`);
        if (iconEl) {
            if (state.sortDepositoField === f) {
                iconEl.innerText = state.sortDepositoDir === 'asc' ? ' ⬆️' : ' ⬇️';
            } else {
                iconEl.innerText = '';
            }
        }
    });

    if (exibidos.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 25px;">Nenhum produto encontrado com os filtros selecionados.</td></tr>`;
        return;
    }

    tbody.innerHTML = exibidos.map(item => {
        const p = item.p;
        const skuStr = String(p.sku).trim();
        const { totalMatriz, fracionado, deposito1, deposito2, aLocalizar, temDivergencia, fracionadoZerado, temEstoqueContadoEmOutro } = item;

        // Endereços de Armazenamento do Omie
        const endObj = (state.enderecos || {})[skuStr] || {};
        const endFrac = endObj.fracionado || '';
        const endDep1 = endObj.deposito_1 || '';

        const badgeEndFrac = endFrac ? `<div style="font-size:0.75rem; color:#38bdf8; font-weight:600; margin-top:2px;" title="Endereço de Picking (Omie)"><i class="fa-solid fa-location-dot"></i> ${endFrac}</div>` : `<div style="font-size:0.7rem; color:var(--text-muted); margin-top:2px; opacity:0.6;">📍 S/ End.</div>`;
        const badgeEndDep1 = endDep1 ? `<div style="font-size:0.75rem; color:#f59e0b; font-weight:600; margin-top:2px;" title="Endereço no Depósito 1 (Omie)"><i class="fa-solid fa-warehouse"></i> ${endDep1}</div>` : `<div style="font-size:0.7rem; color:var(--text-muted); margin-top:2px; opacity:0.6;">🏭 S/ End.</div>`;

        // Status & Alertas de Busca
        let statusBadge = '';
        if (temDivergencia) {
            statusBadge = `<span class="badge-loc badge-loc-divergencia" title="Depósitos excedem o Total Físico da Matriz">⚠️ Divergência (${aLocalizar} un)</span>`;
        } else if (fracionadoZerado && temEstoqueContadoEmOutro) {
            const fonte = deposito2 > 0 ? `Dep. 2 (${deposito2} un)` : `Dep. 1 (${deposito1} un)`;
            const txtStatus = fracionado === 0 ? 'Zerado' : `${fracionado} un`;
            statusBadge = `<span class="badge-loc badge-loc-alerta" title="Fracionado com ${txtStatus}. Buscar estoque no ${fonte}">📦 Buscar no ${fonte}</span>`;
        } else if (aLocalizar === 0) {
            statusBadge = `<span class="badge-loc badge-loc-ok">✅ 100% Localizado</span>`;
        } else {
            statusBadge = `<span class="badge-loc badge-loc-pendente">🔍 Sobra/Ajuste: ${aLocalizar} un</span>`;
        }

        const colorALocalizar = aLocalizar < 0 ? '#f87171' : (aLocalizar === 0 ? '#34d399' : '#c084fc');
        const colorFracionado = fracionado === 0 ? '#f87171' : (fracionado <= 5 ? '#f59e0b' : '#38bdf8');

        return `
            <tr data-sku="${p.sku}">
                <td><strong>${p.sku}</strong></td>
                <td>
                    <div style="font-weight:600; color:var(--text-main);">${p.nome || 'Produto sem nome'}</div>
                    <div style="font-size:0.75rem; color:var(--text-muted);">${p.familia || '-'}</div>
                </td>
                <td style="text-align:center; font-weight:700; color:var(--primary);">${totalMatriz} un</td>
                <td style="text-align:center;">
                    <span style="font-size:1.05rem; font-weight:700; color:${colorFracionado};">${fracionado} un</span>
                    ${badgeEndFrac}
                </td>
                <td style="text-align:center;">
                    <input type="number" class="deposito-input dep-1" value="${deposito1}" min="0" onchange="atualizarContagemInline('${p.sku}')">
                    ${badgeEndDep1}
                </td>
                <td style="text-align:center;">
                    <input type="number" class="deposito-input dep-2" value="${deposito2}" min="0" onchange="atualizarContagemInline('${p.sku}')">
                </td>
                <td style="text-align:center; font-weight:700; color:${colorALocalizar};">
                    ${aLocalizar} un
                </td>
                <td style="text-align:center;">
                    ${statusBadge}
                </td>
                <td style="text-align:center;">
                    <div style="display:flex; gap:6px; justify-content:center; flex-wrap:wrap;">
                        <button class="btn btn-sm btn-secondary" style="padding:4px 8px; background:rgba(245, 158, 11, 0.15); border:1px solid rgba(245, 158, 11, 0.4); color:#f59e0b;" onclick="abrirModalEndereco('${p.sku}', '${(p.nome || '').replace(/'/g, "\\'")}', '${p.id_produto || p.nCodProd || ''}')" title="Editar Endereço de Armazenamento no Omie ERP">
                            <i class="fa-solid fa-location-dot"></i> Endereço
                        </button>
                        <button class="btn btn-sm btn-secondary" onclick="abrirModalTransferencia('${p.sku}', '${(p.nome || '').replace(/'/g, "\\'")}')" title="Transferir entre locais">
                            <i class="fa-solid fa-arrow-right-arrow-left"></i> Transferir
                        </button>
                        <button class="btn btn-sm btn-primary" onclick="salvarContagemRow('${p.sku}')" title="Salvar contagem">
                            <i class="fa-solid fa-floppy-disk"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// Atualiza cálculo 'Fracionado' e 'A Localizar' em tempo real ao digitar nos inputs de Depósito 1 / 2
function atualizarContagemInline(sku) {
    const row = document.querySelector(`tr[data-sku="${sku}"]`);
    if (!row) return;

    const p = state.produtos.find(prod => String(prod.sku).trim() === String(sku).trim());
    if (!p) return;

    const totalMatriz = p.matriz || 0;
    const dep1 = parseInt(row.querySelector('.dep-1')?.value || 0);
    const dep2 = parseInt(row.querySelector('.dep-2')?.value || 0);
    const frac = Math.max(0, totalMatriz - (dep1 + dep2));

    state.depositos[String(sku).trim()] = { fracionado: frac, deposito_1: dep1, deposito_2: dep2 };
    renderizarAbaDepositosMatriz();
}

async function salvarContagemRow(sku) {
    const row = document.querySelector(`tr[data-sku="${sku}"]`);
    if (!row) return;

    const p = state.produtos.find(prod => String(prod.sku).trim() === String(sku).trim());
    const totalMatriz = p ? (p.matriz || 0) : 0;

    const dep1 = parseInt(row.querySelector('.dep-1')?.value || 0);
    const dep2 = parseInt(row.querySelector('.dep-2')?.value || 0);
    const frac = Math.max(0, totalMatriz - (dep1 + dep2));

    try {
        const resp = await fetch('/api/depositos/salvar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sku: String(sku).trim(), fracionado: frac, deposito_1: dep1, deposito_2: dep2 })
        });
        const res = await resp.json();
        if (resp.ok && res.success) {
            state.depositos[String(sku).trim()] = { fracionado: frac, deposito_1: dep1, deposito_2: dep2 };
            renderizarAbaDepositosMatriz();
            alert(`✅ Contagem do produto ${sku} salva com sucesso!`);
        } else {
            alert(`❌ Erro ao salvar contagem: ${res.message || 'Falha na requisição'}`);
        }
    } catch (e) {
        console.error('Erro ao salvar contagem:', e);
        alert(`❌ Erro de conexão ao salvar contagem.`);
    }
}

// Abrir Modal de Transferência
function abrirModalTransferencia(sku, nomeProduto) {
    document.getElementById('transf-sku').value = sku;
    document.getElementById('transf-produto-nome').value = `${sku} - ${nomeProduto}`;
    document.getElementById('transf-quantidade').value = 1;
    document.getElementById('transf-obs').value = '';

    const modal = document.getElementById('modal-transferencia-deposito');
    if (modal) modal.classList.add('active');
}

function fecharModalTransferencia() {
    const modal = document.getElementById('modal-transferencia-deposito');
    if (modal) modal.classList.remove('active');
}

// Executar Transferência
async function confirmarTransferencia() {
    const sku = document.getElementById('transf-sku').value;
    const nomeProd = document.getElementById('transf-produto-nome').value;
    const origem = document.getElementById('transf-origem').value;
    const destino = document.getElementById('transf-destino').value;
    const qtd = parseInt(document.getElementById('transf-quantidade').value || 0);
    const obs = document.getElementById('transf-obs').value;

    if (!sku || qtd <= 0) {
        alert('Selecione uma quantidade válida maior que zero.');
        return;
    }

    if (origem === destino) {
        alert('A origem e o destino não podem ser o mesmo local.');
        return;
    }

    const skuStr = String(sku).trim();
    const sub = state.depositos[skuStr] || { fracionado: 0, deposito_1: 0, deposito_2: 0 };
    
    // Validar se origem tem saldo suficiente quando a origem for um sub-local contado
    if (origem === 'DEP_2' && sub.deposito_2 < qtd) {
        if (!confirm(`⚠️ O Depósito 2 tem apenas ${sub.deposito_2} un contadas. Deseja realizar a transferência assim mesmo?`)) return;
    } else if (origem === 'DEP_1' && sub.deposito_1 < qtd) {
        if (!confirm(`⚠️ O Depósito 1 tem apenas ${sub.deposito_1} un contadas. Deseja realizar a transferência assim mesmo?`)) return;
    } else if (origem === 'FRACIONADO' && sub.fracionado < qtd) {
        if (!confirm(`⚠️ O Fracionado tem apenas ${sub.fracionado} un contadas. Deseja realizar a transferência assim mesmo?`)) return;
    }

    // Aplicar a transferência no estado local
    if (origem === 'DEP_2') sub.deposito_2 = Math.max(0, sub.deposito_2 - qtd);
    else if (origem === 'DEP_1') sub.deposito_1 = Math.max(0, sub.deposito_1 - qtd);
    else if (origem === 'FRACIONADO') sub.fracionado = Math.max(0, sub.fracionado - qtd);

    if (destino === 'FRACIONADO') sub.fracionado = (sub.fracionado || 0) + qtd;
    else if (destino === 'DEP_1') sub.deposito_1 = (sub.deposito_1 || 0) + qtd;
    else if (destino === 'DEP_2') sub.deposito_2 = (sub.deposito_2 || 0) + qtd;

    state.depositos[skuStr] = sub;

    try {
        await fetch('/api/depositos/transferir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sku: skuStr,
                nome_produto: nomeProd,
                origem,
                destino,
                quantidade: qtd,
                observacao: obs
            })
        });

        await fetch('/api/depositos/salvar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sku: skuStr, fracionado: sub.fracionado, deposito_1: sub.deposito_1, deposito_2: sub.deposito_2 })
        });

        fecharModalTransferencia();
        renderizarAbaDepositosMatriz();
        alert(`✅ Transferência de ${qtd} un registrada com sucesso!`);
    } catch (e) {
        console.error('Erro ao executar transferência:', e);
        alert('Erro ao registrar transferência no servidor.');
    }
}

// Imprimir / Baixar Lista de Reabastecimento em Formato Limpo p/ Impressão ou PDF
function imprimirListaReabastecimento() {
    const alertas = window._ultimosAlertasPicking || [];
    if (alertas.length === 0) {
        alert("Nenhum produto necessita de reabastecimento no momento.");
        return;
    }

    const dataHora = new Date().toLocaleString('pt-BR');
    let rowsHtml = alertas.map((item, idx) => `
        <tr>
            <td style="padding:10px; border:1px solid #cbd5e1; text-align:center;">${idx + 1}</td>
            <td style="padding:10px; border:1px solid #cbd5e1; font-weight:bold; color:#0f172a;">${item.p.sku}</td>
            <td style="padding:10px; border:1px solid #cbd5e1;">${item.p.nome || ''}</td>
            <td style="padding:10px; border:1px solid #cbd5e1; text-align:center; font-weight:bold;">${item.totalMatriz} un</td>
            <td style="padding:10px; border:1px solid #cbd5e1; text-align:center; color:#dc2626; font-weight:bold;">${item.fracionado} un</td>
            <td style="padding:10px; border:1px solid #cbd5e1; text-align:center; font-weight:bold; color:#0284c7;">${item.fonte}</td>
            <td style="padding:10px; border:1px solid #cbd5e1; text-align:center; color:#475569;">[ &nbsp; &nbsp; ] ________ un</td>
        </tr>
    `).join('');

    const printWin = window.open('', '_blank', 'width=950,height=750');
    printWin.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>Lista de Reabastecimento do Fracionado (Picking)</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; color: #1e293b; background: #fff; }
                .header { border-bottom: 2px solid #0284c7; padding-bottom: 12px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: flex-end; }
                h2 { margin: 0; color: #0f172a; font-size: 1.5rem; }
                p { margin: 4px 0 0 0; color: #64748b; font-size: 0.9rem; }
                table { width: 100%; border-collapse: collapse; margin-top: 10px; }
                th { background: #f8fafc; color: #334155; padding: 12px 10px; border: 1px solid #cbd5e1; text-align: left; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; }
                td { font-size: 0.9rem; }
                .footer { margin-top: 50px; display: flex; justify-content: space-between; font-size: 0.9rem; color: #475569; }
                .signature { border-top: 1px solid #94a3b8; width: 280px; text-align: center; padding-top: 6px; }
            </style>
        </head>
        <body>
            <div class="header">
                <div>
                    <h2>📦 LISTA DE REABASTECIMENTO DO FRACIONADO (PICKING)</h2>
                    <p>Controle DRP Matriz | Data: ${dataHora}</p>
                </div>
                <div style="text-align:right;">
                    <strong style="font-size:1.1rem; color:#0284c7;">${alertas.length} produto(s)</strong>
                </div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th style="text-align:center; width: 40px;">#</th>
                        <th style="width: 100px;">SKU</th>
                        <th>Produto</th>
                        <th style="text-align:center; width: 100px;">Estoque Total</th>
                        <th style="text-align:center; width: 120px;">Fracionado Atual</th>
                        <th style="text-align:center; width: 160px;">Retirar De (Origem)</th>
                        <th style="text-align:center; width: 150px;">Visto / Qtd Retirada</th>
                    </tr>
                </thead>
                <tbody>
                    ${rowsHtml}
                </tbody>
            </table>
            <div class="footer">
                <div class="signature">Operador / Conferente de Estoque</div>
                <div class="signature">Supervisão de Logística</div>
            </div>
            <script>
                window.onload = function() { window.print(); }
            </script>
        </body>
        </html>
    `);
    printWin.document.close();
}

async function enviarEmailReabastecimento() {
    const alertas = window._ultimosAlertasPicking || [];
    if (alertas.length === 0) {
        alert("Nenhum produto necessita de reabastecimento no momento.");
        return;
    }

    if (!confirm(`Deseja enviar a lista de reabastecimento de ${alertas.length} produto(s) por e-mail para o setor de Estoque/Galpão?`)) return;

    try {
        const payload = {
            assunto: `[ALERTA DRP] Reabastecimento do Fracionado - ${alertas.length} produto(s)`,
            alertas: alertas.map(a => ({
                sku: a.p.sku,
                nome: a.p.nome,
                total: a.totalMatriz,
                fracionado: a.fracionado,
                fonte: a.fonte
            }))
        };
        const resp = await fetch('/api/depositos/email_reabastecimento', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const res = await resp.json();
        if (resp.ok && res.success) {
            alert("✉️ Lista de reabastecimento enviada com sucesso por e-mail para a equipe do galpão!");
        } else {
            alert(`✅ Lista registrada! ${res.message || ''}`);
        }
    } catch (e) {
        console.error("Erro ao enviar e-mail de reabastecimento:", e);
        alert("✅ Alerta de reabastecimento registrado com sucesso!");
    }
}

// Abrir e renderizar Histórico de Transferências
async function abrirHistoricoTransferencias() {
    const modal = document.getElementById('modal-historico-transferencias');
    const tbody = document.getElementById('tbody-historico-transferencias');
    if (modal) modal.classList.add('active');

    if (tbody) tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;"><i class="fa-solid fa-spinner fa-spin"></i> Carregando histórico...</td></tr>`;

    try {
        const resp = await fetch('/api/depositos/historico');
        if (resp.ok) {
            const data = await resp.json();
            const historico = data.historico || [];
            
            if (historico.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:20px;">Nenhuma transferência registrada até o momento.</td></tr>`;
                return;
            }

            const mapLoc = { 'A_LOCALIZAR': 'A Localizar', 'DEP_2': 'Depósito 2', 'DEP_1': 'Depósito 1', 'FRACIONADO': 'Fracionado' };

            tbody.innerHTML = historico.map(h => `
                <tr>
                    <td style="font-size:0.8rem; color:var(--text-muted);">${h.data_hora || '-'}</td>
                    <td><strong>${h.sku || '-'}</strong></td>
                    <td style="font-size:0.85rem;">${h.nome_produto || '-'}</td>
                    <td><span class="badge-loc badge-loc-pendente">${mapLoc[h.origem] || h.origem}</span></td>
                    <td><span class="badge-loc badge-loc-ok">${mapLoc[h.destino] || h.destino}</span></td>
                    <td style="font-weight:700; color:var(--primary); text-align:center;">${h.quantidade} un</td>
                    <td style="font-size:0.8rem; color:var(--text-muted);">${h.observacao || '-'}</td>
                </tr>
            `).join('');
        }
    } catch (e) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--color-ruptura);">Erro ao carregar histórico.</td></tr>`;
    }
}

function fecharHistoricoTransferencias() {
    const modal = document.getElementById('modal-historico-transferencias');
    if (modal) modal.classList.remove('active');
}

async function sincronizarEstoqueOmieDepositos() {
    const btn = document.getElementById('btn-sync-estoque-omie');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Sincronizando (Ativos)...`;
    }
    try {
        const resp = await fetch('/api/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tipo: 'ESTOQUE_MATRIZ' })
        });
        const data = await resp.json();
        if (resp.ok && data.success) {
            alert(`✅ Estoque da Matriz (Produtos Ativos) sincronizado com sucesso da Omie ERP!`);
            await carregarProdutos();
            await carregarDepositosMatriz();
            renderizarAbaDepositosMatriz();
        } else {
            alert(`❌ Erro ao sincronizar estoque: ${data.message || 'Falha na resposta'}`);
        }
    } catch (e) {
        console.error('Erro na sincronização de estoque:', e);
        alert('❌ Erro de conexão ao sincronizar estoque com a Omie.');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-rotate"></i> Sincronizar Estoque Omie (Ativos)`;
        }
    }
}

async function recarregarDepositosCompletos() {
    const btn = document.getElementById('btn-recarregar-depositos');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Recarregando...`;
    }
    try {
        await carregarProdutos();
        await carregarDepositosMatriz();
        renderizarAbaDepositosMatriz();
    } catch (e) {
        console.error('Erro ao recarregar depósitos:', e);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i> Recarregar Depósitos`;
        }
    }
}

// Modal e Funções de Gestão de Endereçamento (Omie ERP & DRP)
function abrirModalEndereco(sku, nomeProduto, idProduto) {
    state.enderecos = state.enderecos || {};
    const skuStr = String(sku).trim();
    const endObj = state.enderecos[skuStr] || {};

    document.getElementById('end-sku').value = skuStr;
    document.getElementById('end-id-produto').value = idProduto || '';
    document.getElementById('end-produto-nome').value = `${skuStr} - ${nomeProduto}`;
    document.getElementById('end-fracionado').value = endObj.fracionado || '';
    document.getElementById('end-deposito1').value = endObj.deposito_1 || '';

    const stEl = document.getElementById('end-status-omie');
    if (stEl) { stEl.style.display = 'none'; stEl.innerHTML = ''; }

    const modal = document.getElementById('modal-editar-endereco');
    if (modal) modal.classList.add('active');
}

function fecharModalEndereco() {
    const modal = document.getElementById('modal-editar-endereco');
    if (modal) modal.classList.remove('active');
}

async function confirmarSalvarEndereco() {
    const sku = document.getElementById('end-sku').value;
    const idProduto = document.getElementById('end-id-produto').value;
    const fracionado = document.getElementById('end-fracionado').value.trim().toUpperCase();
    const deposito1 = document.getElementById('end-deposito1').value.trim().toUpperCase();

    const btn = document.getElementById('btn-salvar-endereco-omie');
    const stEl = document.getElementById('end-status-omie');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Salvando no Omie...`;
    }
    if (stEl) {
        stEl.style.display = 'block';
        stEl.style.color = '#38bdf8';
        stEl.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Enviando atualização da característica "Endereço" para o Omie ERP...`;
    }

    try {
        const resp = await fetch('/api/depositos/enderecos/salvar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sku,
                id_produto: idProduto,
                fracionado,
                deposito_1: deposito1
            })
        });

        const res = await resp.json();
        if (resp.ok && res.success) {
            state.enderecos = state.enderecos || {};
            state.enderecos[sku] = res.endereco || { fracionado, deposito_1: deposito1 };
            renderizarAbaDepositosMatriz();
            fecharModalEndereco();
            const msgFinal = res.omie_msg ? `${res.message}\nℹ️ ${res.omie_msg}` : res.message;
            alert(`✅ ${msgFinal}`);
        } else {
            alert(`❌ Erro ao salvar endereço: ${res.message || 'Falha no servidor'}`);
        }
    } catch (e) {
        console.error('Erro ao salvar endereço:', e);
        alert('❌ Erro de conexão ao salvar endereço.');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Salvar no Omie ERP & DRP`;
        }
    }
}

// Tirar produtos selecionados (ou todos) do status Em Produção / Compra
async function tirarSelecionadosProducao() {
    const totalSelecionados = state.skusChecadosMatriz ? state.skusChecadosMatriz.size : 0;
    
    if (totalSelecionados > 0) {
        if (!confirm(`Deseja tirar os ${totalSelecionados} produto(s) selecionados do status Em Produção / Compra?`)) return;
        
        state.skusChecadosMatriz.forEach(sku => {
            state.producao.delete(sku);
            const p = state.produtos.find(prod => String(prod.sku).trim() === String(sku).trim());
            if (p) p.em_producao = false;
        });
        state.skusChecadosMatriz.clear();
        const elCount = document.getElementById('count-selected-blacklist-matriz');
        if (elCount) elCount.innerText = '0';
    } else {
        if (!confirm('Nenhum produto marcado com a caixa de seleção na tabela.\n\nDeseja desmarcar TODOS os produtos atualmente no status Em Produção / Compra?')) return;
        
        state.producao.clear();
        if (state.produtos) {
            state.produtos.forEach(p => p.em_producao = false);
        }
    }

    const novaProducao = Array.from(state.producao);
    localStorage.setItem('drp_producao', JSON.stringify(novaProducao));

    try {
        await fetch('/api/producao/salvar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ producao: novaProducao })
        });
    } catch (e) {
        console.error('Erro ao salvar desmarcar producao:', e);
    }

    render();
}

// ==========================================
// AUTOMAÇÃO & GESTÃO DO COMBO (SKU 000223)
// ==========================================

async function carregarDetalhesCombo() {
    const tbody = document.getElementById('tbody-componentes-combo');
    const precoEl = document.getElementById('combo-preco-atual');
    const banner = document.getElementById('combo-alert-banner');
    if (!tbody) return;

    try {
        const resp = await fetch('/api/combo/detalhes?sku=000223');
        const data = await resp.json();

        if (!resp.ok || !data.success) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:#f87171;">⚠️ ${data.message || 'Erro ao carregar combo.'}</td></tr>`;
            return;
        }

        const combo = data.combo || {};
        const comps = data.componentes || [];

        if (precoEl) {
            precoEl.textContent = `R$ ${parseFloat(combo.valor_venda || 89.90).toFixed(2).replace('.', ',')}`;
        }

        let alertasCriticos = [];
        let htmlRows = '';

        if (comps.length === 0) {
            htmlRows = `<tr><td colspan="5" style="text-align:center; color: var(--text-muted); padding: 15px;">Nenhum componente ativo vinculado a este combo no Omie ERP.</td></tr>`;
        } else {
            comps.forEach(c => {
                let badgeStatus = '';

                if (c.nivel_alerta === 'REMOVER') {
                    badgeStatus = `<span class="badge" style="background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4);"><i class="fa-solid fa-circle-exclamation"></i> <= 5 un (Remover Recomendado)</span>`;
                    alertasCriticos.push(`🚨 <b>${c.descricao} (${c.sku})</b> possui apenas <b>${c.estoque_matriz} un em estoque</b>! Clique no botão ao lado para retirar do combo e redefinir o valor para R$ 89,90.`);
                } else if (c.nivel_alerta === 'CRITICO') {
                    badgeStatus = `<span class="badge" style="background: rgba(249, 115, 22, 0.2); color: #fb923c; border: 1px solid rgba(249, 115, 22, 0.4);"><i class="fa-solid fa-triangle-exclamation"></i> <= 20 un (Nível Crítico)</span>`;
                    alertasCriticos.push(`⚡ <b>${c.descricao} (${c.sku})</b> está em nível crítico de estoque (<b>${c.estoque_matriz} un</b>).`);
                } else if (c.nivel_alerta === 'ATENCAO') {
                    badgeStatus = `<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4);"><i class="fa-solid fa-circle-info"></i> <= 50 un (Atenção)</span>`;
                    alertasCriticos.push(`🟡 <b>${c.descricao} (${c.sku})</b> atingiu o alerta de atenção (<b>${c.estoque_matriz} un</b>).`);
                } else {
                    badgeStatus = `<span class="badge" style="background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.4);"><i class="fa-solid fa-circle-check"></i> > 50 un (Estável)</span>`;
                }

                const btnDangerStyle = (c.nivel_alerta === 'REMOVER' || c.nivel_alerta === 'CRITICO') 
                    ? `background: #ef4444; color: #fff; font-weight: 700; box-shadow: 0 0 10px rgba(239,68,68,0.5);`
                    : `background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4);`;

                const nomeEscaped = (c.descricao || '').replace(/'/g, "\\'");

                htmlRows += `
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <td style="padding: 10px 14px; font-weight: 600; color: #f8fafc;">${c.sku}</td>
                        <td style="padding: 10px 14px; color: #cbd5e1;">${c.descricao}</td>
                        <td style="padding: 10px 14px; text-align: center; font-weight: 700; color: ${c.estoque_matriz <= 5 ? '#f87171' : (c.estoque_matriz <= 20 ? '#fb923c' : '#f8fafc')}; font-size: 0.95rem;">
                            ${c.estoque_matriz} un
                        </td>
                        <td style="padding: 10px 14px; text-align: center;">${badgeStatus}</td>
                        <td style="padding: 10px 14px; text-align: right;">
                            <button class="btn btn-sm" style="${btnDangerStyle} padding: 6px 12px; font-size: 0.8rem;" onclick="removerComponenteCombo('000223', ${c.codigo_componente}, ${c.codigo_produto_componente}, '${nomeEscaped}')" title="Retirar componente do Kit no Omie ERP e redefinir preço de venda para R$ 89,90">
                                <i class="fa-solid fa-trash-can"></i> Retirar do Combo & Fixar R$ 89,90
                            </button>
                        </td>
                    </tr>
                `;
            });
        }

        tbody.innerHTML = htmlRows;

        if (banner) {
            if (alertasCriticos.length > 0) {
                banner.style.display = 'block';
                banner.style.cssText = 'background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); color: #fca5a5; padding: 12px 16px; border-radius: 8px; font-size: 0.85rem; line-height: 1.6; margin-bottom: 14px;';
                banner.innerHTML = alertasCriticos.join('<br>');
            } else {
                banner.style.display = 'none';
            }
        }

    } catch (e) {
        console.error('Erro ao carregar detalhes do combo:', e);
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:#f87171; padding: 15px;">Erro de conexão com a API.</td></tr>`;
    }
}

async function removerComponenteCombo(skuCombo, codComp, codProdComp, nomeComp) {
    const confirmar = confirm(`⚠️ Confirma a remoção do componente "${nomeComp}" do Combo SKU ${skuCombo}?\n\nIsso executará 2 ações automáticas no Omie ERP:\n1. Excluir o componente do Kit via AlterarComponentesKit.\n2. Redefinir o valor de venda do combo para R$ 89,90 via AlterarProduto.`);
    if (!confirmar) return;

    try {
        const resp = await fetch('/api/combo/remover_componente', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sku_combo: skuCombo,
                codigo_componente: codComp,
                codigo_produto_componente: codProdComp,
                novo_valor_venda: 89.90
            })
        });
        const res = await resp.json();
        if (resp.ok && res.success) {
            alert(`✅ ${res.message}`);
            carregarDetalhesCombo();
        } else {
            alert(`❌ Erro ao alterar combo: ${res.message || 'Falha no servidor'}`);
        }
    } catch (e) {
        console.error('Erro ao remover componente:', e);
        alert('❌ Erro de comunicação ao tentar remover componente do combo.');
    }
}

async function redefinirPrecoCombo() {
    const confirmar = confirm('Deseja fixar o valor de venda do Combo SKU 000223 para R$ 89,90 no Omie ERP?');
    if (!confirmar) return;

    try {
        const resp = await fetch('/api/combo/alterar_preco', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sku_combo: '000223',
                valor_venda: 89.90
            })
        });
        const res = await resp.json();
        if (resp.ok && res.success) {
            alert(`✅ ${res.message}`);
            carregarDetalhesCombo();
        } else {
            alert(`❌ Erro ao alterar preço: ${res.message || 'Falha'}`);
        }
    } catch (e) {
        console.error('Erro ao alterar preço:', e);
    }
}

// ==========================================
// ABA 7: INTELIGÊNCIA DE PRODUÇÃO MATRIZ
// ==========================================
let stateInteligenciaMatriz = {
    produtos: [],
    kpis: {},
    familias: []
};

async function carregarInteligenciaMatriz(forceReload = false) {
    const tbody = document.getElementById('tbody-inteligencia-matriz');
    if (!tbody) return;

    if (stateInteligenciaMatriz.produtos.length > 0 && !forceReload) {
        renderTabelaInteligenciaMatriz(stateInteligenciaMatriz.produtos);
        return;
    }

    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 25px;"><i class="fa-solid fa-spinner fa-spin"></i> Processando inteligência de produção da Matriz...</td></tr>`;

    try {
        const resp = await fetch('/api/inteligencia_matriz');
        const res = await resp.json();
        if (resp.ok && res.success && res.data) {
            stateInteligenciaMatriz.produtos = res.data.produtos || [];
            stateInteligenciaMatriz.kpis = res.data.kpis || {};
            stateInteligenciaMatriz.familias = res.data.familias || [];

            // Atualizar KPIs de Topo
            const k = stateInteligenciaMatriz.kpis;
            document.getElementById('kpi-intel-rupturas-grade').innerText = k.tot_rupturas_isoladas || 0;
            document.getElementById('kpi-intel-classe-a').innerText = k.tot_classe_a_alta || 0;
            document.getElementById('kpi-intel-risco-encalhe').innerText = k.tot_risco_encalhe || 0;
            document.getElementById('kpi-intel-total-prods').innerText = k.tot_produtos || 0;

            // Popular Seletor de Famílias
            const selFam = document.getElementById('filter-familia-inteligencia');
            if (selFam) {
                const valAtual = selFam.value;
                selFam.innerHTML = `<option value="TODAS">Todas as Famílias (${stateInteligenciaMatriz.familias.length})</option>`;
                stateInteligenciaMatriz.familias.forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f;
                    opt.innerText = f;
                    selFam.appendChild(opt);
                });
                selFam.value = valAtual || 'TODAS';
            }

            renderTabelaInteligenciaMatriz(stateInteligenciaMatriz.produtos);
        } else {
            tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: #f87171; padding: 25px;">Erro ao carregar inteligência: ${res.message || 'Falha'}</td></tr>`;
        }
    } catch (e) {
        console.error('Erro ao carregar inteligência matriz:', e);
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: #f87171; padding: 25px;">Erro de conexão ao carregar inteligência de produção.</td></tr>`;
    }
}

function filtrarTabelaInteligenciaMatriz() {
    const busca = (document.getElementById('search-inteligencia-matriz')?.value || '').toLowerCase().trim();
    const famFiltro = document.getElementById('filter-familia-inteligencia')?.value || 'TODAS';
    const abcFiltro = document.getElementById('filter-abc-inteligencia')?.value || 'TODOS';
    const acaoFiltro = document.getElementById('filter-acao-inteligencia')?.value || 'TODOS';

    const prodsFiltrados = stateInteligenciaMatriz.produtos.filter(p => {
        const txt = `${p.sku} ${p.nome} ${p.modelo_base || ''}`.toLowerCase();
        if (busca && !txt.includes(busca)) return false;
        if (famFiltro !== 'TODAS' && (p.familia || '').toUpperCase() !== famFiltro.toUpperCase()) return false;
        if (abcFiltro !== 'TODOS' && p.classe_abc_familia !== abcFiltro) return false;
        
        if (acaoFiltro === 'RUPTURA_GRADE' && !(p.status_grade || '').includes('Ruptura Isolada')) return false;
        if (acaoFiltro === 'PRODUZIR' && !(p.acao_recomendada || '').includes('Produzir') && !(p.acao_recomendada || '').includes('Reposição') && !(p.acao_recomendada || '').includes('Prioridade')) return false;
        if (acaoFiltro === 'ENCALHE' && !p.risco_encalhe) return false;

        return true;
    });

    renderTabelaInteligenciaMatriz(prodsFiltrados);
}

function renderTabelaInteligenciaMatriz(lista) {
    const tbody = document.getElementById('tbody-inteligencia-matriz');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!lista || lista.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 25px;">Nenhum produto encontrado com os filtros aplicados.</td></tr>`;
        return;
    }

    lista.slice(0, 150).forEach(p => {
        const tr = document.createElement('tr');
        
        // Badge Classe ABC
        let abcBadge = '<span class="badge" style="background: rgba(100, 116, 139, 0.2); color: #94a3b8; border: 1px solid rgba(100, 116, 139, 0.4);">Classe C</span>';
        if (p.classe_abc_familia === 'A') {
            abcBadge = '<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); font-weight: 700;">⭐ Classe A</span>';
        } else if (p.classe_abc_familia === 'B') {
            abcBadge = '<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4);">🟡 Classe B</span>';
        }

        // Badge Status Grade
        let stGradeBadge = `<span style="font-size: 0.85rem; color: #94a3b8;">${p.status_grade || 'Normal'}</span>`;
        if ((p.status_grade || '').includes('Ruptura Isolada')) {
            stGradeBadge = `<span class="badge badge-alerta" style="font-weight:700;">${p.status_grade}</span>`;
        } else if ((p.status_grade || '').includes('Ruptura Total')) {
            stGradeBadge = `<span class="badge badge-ruptura" style="font-weight:700;">${p.status_grade}</span>`;
        }

        // Badge Cobertura Lote
        let cobText = `${p.meses_cobertura_lote || 0} meses`;
        if (p.lote_minimo === 0) cobText = 'Sem Lote Mínimo';
        else if (p.meses_cobertura_lote >= 99) cobText = 'Sem vendas recentes';
        let cobColor = '#94a3b8';
        if (p.risco_encalhe) cobColor = '#f87171';
        else if (p.lote_minimo > 0 && p.meses_cobertura_lote < 6) cobColor = '#34d399';

        // Badge Ação Recomendada
        let acaoBadge = `<span style="font-size: 0.85rem; color: #cbd5e1;">${p.acao_recomendada || '-'}</span>`;
        if ((p.acao_recomendada || '').includes('Produzir') || (p.acao_recomendada || '').includes('Prioridade')) {
            acaoBadge = `<span class="badge badge-estavel" style="font-size: 0.82rem; padding: 6px 12px; font-weight: 700;">${p.acao_recomendada}</span>`;
        } else if ((p.acao_recomendada || '').includes('Não Repor') || (p.acao_recomendada || '').includes('Cauda Longa')) {
            acaoBadge = `<span class="badge badge-ruptura" style="font-size: 0.82rem; padding: 6px 12px;">${p.acao_recomendada}</span>`;
        } else if ((p.acao_recomendada || '').includes('Aguardar')) {
            acaoBadge = `<span class="badge badge-alerta" style="font-size: 0.82rem; padding: 6px 12px;">${p.acao_recomendada}</span>`;
        }

        tr.innerHTML = `
            <td>
                <strong>${p.sku}</strong>
                ${p.tamanho_grade ? `<br><span class="badge" style="background:rgba(59,130,246,0.2); color:#60a5fa; font-size:0.75rem;">Tam: ${p.tamanho_grade}</span>` : ''}
            </td>
            <td>
                <strong>${p.nome || p.descricao}</strong>
                ${p.modelo_base && p.modelo_base !== p.nome ? `<br><small style="color:var(--text-muted);">Modelo: ${p.modelo_base}</small>` : ''}
            </td>
            <td><span class="badge" style="background:rgba(255,255,255,0.05); color:#e2e8f0;">${p.familia || 'OUTROS'}</span></td>
            <td style="text-align:center;"><strong>${p.matriz || 0} un</strong></td>
            <td style="text-align:center;">${abcBadge}</td>
            <td style="text-align:center;">${stGradeBadge}</td>
            <td style="text-align:center;"><strong style="font-size:0.85rem;">${p.tendencia_vendas || 'Estável ➡️'}</strong></td>
            <td style="text-align:center; color: ${cobColor}; font-weight:600;">${cobText}<br><small style="color:var(--text-muted);">(Lote Mín: ${p.lote_minimo || 'N/A'})</small></td>
            <td style="text-align:center;">${acaoBadge}</td>
        `;

        tr.style.cursor = 'pointer';
        tr.title = 'Clique para ver o diagnóstico completo e ajustar o lote mínimo';
        const prodSku = p.sku;
        tr.onclick = (e) => {
            e.stopPropagation();
            abrirModalDetalhesInteligencia(prodSku);
        };
        tr.addEventListener('click', (e) => {
            e.stopPropagation();
            abrirModalDetalhesInteligencia(prodSku);
        });

        tbody.appendChild(tr);
    });
}

function abrirModalDetalhesInteligencia(sku) {
    if (!sku || !stateInteligenciaMatriz.produtos) return;
    const targetSku = String(sku).trim().toUpperCase();
    const p = stateInteligenciaMatriz.produtos.find(x => {
        const s = String(x.sku || '').trim().toUpperCase();
        return s === targetSku ||
               s.padStart(6, '0') === targetSku.padStart(6, '0') ||
               s.replace(/\D/g, '') === targetSku.replace(/\D/g, '');
    });
    if (!p) {
        console.warn("[INTELIGENCIA] Produto não encontrado no estado local:", sku);
        return;
    }

    const modal = document.getElementById('modal-detalhes-inteligencia');
    const body = document.getElementById('body-detalhes-inteligencia');
    if (!modal || !body) return;

    const d = p.detalhes_calculo || {};

    let statusColor = '#3b82f6';
    let statusBg = 'rgba(59, 130, 246, 0.15)';
    if (p.tendencia_vendas === 'Acelerando 🔥') {
        statusColor = '#34d399';
        statusBg = 'rgba(16, 185, 129, 0.15)';
    } else if (p.tendencia_vendas === 'Desacelerando 📉') {
        statusColor = '#f87171';
        statusBg = 'rgba(239, 68, 68, 0.15)';
    }

    let html = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 15px; margin-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 15px;">
            <div>
                <h4 style="margin:0; font-size:1.15rem; color:#34d399;">${p.sku} — ${p.nome || p.descricao}</h4>
                <p style="margin:4px 0 0 0; font-size:0.85rem; color:var(--text-muted);">
                    Família: <strong>${p.familia || 'OUTROS'}</strong> | Marca: <strong>${p.marca || 'SHALOM'}</strong>
                </p>
            </div>
            <div style="text-align: right;">
                <span class="badge" style="font-size: 0.9rem; padding: 6px 12px; background: rgba(59,130,246,0.2); color: #60a5fa; border: 1px solid rgba(59,130,246,0.4);">
                    Classe ${p.classe_abc_familia} (Família)
                </span>
            </div>
        </div>

        <!-- Banner de Diagnóstico Explicativo -->
        <div style="padding: 12px 16px; border-radius: 8px; background: ${statusBg}; border: 1px solid ${statusColor}; color: ${statusColor}; margin-bottom: 16px; font-size: 0.92rem; font-weight: 500;">
            <i class="fa-solid fa-circle-info" style="margin-right: 8px;"></i>
            <strong>Diagnóstico do Sistema:</strong> ${d.explicacao_status || p.tendencia_vendas || 'Normal'}
        </div>

        <!-- Container do Gráfico de Vendas -->
        <div class="card mb-3" style="background: rgba(15, 23, 42, 0.7); padding: 16px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); margin-bottom: 16px;">
            <h5 style="margin:0 0 12px 0; color:#38bdf8; display:flex; align-items:center; gap:8px; font-size: 0.95rem;">
                <i class="fa-solid fa-chart-column"></i> Evolução Mensal de Saídas & Remessas p/ CD_SP (Últimos 3 Meses Reais)
            </h5>
            <div style="position: relative; height: 220px; width: 100%;">
                <canvas id="chart-tendencia-inteligencia"></canvas>
            </div>
        </div>

        <!-- Bloco 1: Curva ABC por Família -->
        <div class="card mb-3" style="background: rgba(15, 23, 42, 0.6); padding: 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); margin-bottom: 12px;">
            <h5 style="margin:0 0 10px 0; color:#fbbf24; display:flex; align-items:center; gap:8px; font-size: 0.92rem;">
                <i class="fa-solid fa-chart-pie"></i> 1. Posicionamento na Família "${d.familia || ''}"
            </h5>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; font-size: 0.88rem;">
                <div>• Ranking na Família: <strong>${d.rank_familia}º de ${d.total_produtos_familia} produtos</strong></div>
                <div>• Faturamento 30d: <strong>R$ ${(d.faturamento_prod_30d || 0).toFixed(2)}</strong></div>
                <div>• Share da Família: <strong>${d.share_familia_pct || 0}%</strong></div>
                <div>• Corte Acumulado ABC: <strong>${d.pct_acumulado_familia || 0}%</strong></div>
            </div>
        </div>

        <!-- Bloco 2: Histórico e Velocidade de Vendas -->
        <div class="card mb-3" style="background: rgba(15, 23, 42, 0.6); padding: 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); margin-bottom: 12px;">
            <h5 style="margin:0 0 10px 0; color:#60a5fa; display:flex; align-items:center; gap:8px; font-size: 0.92rem;">
                <i class="fa-solid fa-chart-line"></i> 2. Detalhamento de Vendas & Saídas Matriz (Alinhado com o Comitê)
            </h5>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; font-size: 0.88rem;">
                <div>• Vendas 30d (Geral): <strong>${d.vendas_diretas_30d || 0} un</strong></div>
                <div>• Média Mensal (90d): <strong>${d.media_mensal_90d || 0} un/mês</strong></div>
                <div>• Vendas Ano (365d): <strong>${d.vendas_365d || 0} un</strong></div>
                <div>• Remessas CD_SP (30d): <strong>+${d.remessas_cd_sp_30d || 0} un</strong></div>
                <div>• Saídas Totais Matriz (30d): <strong>${d.demanda_total_matriz_30d || 0} un/mês</strong> <small style="color:var(--text-muted);">(Vendas + Remessas)</small></div>
                <div>• Variação Velocidade: <strong>${d.variacao_tendencia_pct > 0 ? '+' : ''}${d.variacao_tendencia_pct || 0}%</strong></div>
                <div>• Status de Tendência: <strong>${p.tendencia_vendas || 'Estável'}</strong></div>
            </div>
        </div>

        <!-- Bloco 3: Ajuste Manual de Lote Mínimo -->
        <div class="card mb-3" style="background: rgba(30, 41, 59, 0.7); padding: 14px; border-radius: 8px; border: 1px solid rgba(245, 158, 11, 0.3);">
            <h5 style="margin:0 0 10px 0; color:#f59e0b; display:flex; align-items:center; gap:8px; font-size: 0.92rem;">
                <i class="fa-solid fa-sliders"></i> 3. Ajustar Lote Mínimo de Produção / Compra
            </h5>
            <p style="margin:0 0 10px 0; font-size:0.82rem; color:var(--text-muted);">
                Regra atual: <strong>${d.origem_lote || 'Padrão'}</strong> | Estoque Disponível Matriz: <strong>${d.estoque_matriz || 0} un</strong> (${d.meses_cobertura_atual || 0} meses de estoque).
            </p>
            <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                <label style="font-size: 0.88rem; font-weight: 600; color: #f8fafc;">Lote Mínimo Personalizado:</label>
                <input type="number" id="input-lote-manual-${p.sku}" class="form-control" style="width: 120px;" value="${d.lote_minimo || 0}" min="0" step="10">
                <button class="btn btn-primary btn-sm" onclick="salvarLoteManualJs('${p.sku}')">
                    <i class="fa-solid fa-floppy-disk"></i> Salvar Lote Mínimo
                </button>
            </div>
        </div>

        <!-- Bloco 4: Envio para o Comitê de Decisão -->
        <div class="card mb-3" style="background: rgba(192, 132, 252, 0.08); padding: 14px; border-radius: 8px; border: 1px solid rgba(192, 132, 252, 0.3);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div>
                    <h5 style="margin:0; color:#c084fc; display:flex; align-items:center; gap:8px; font-size: 0.92rem;">
                        <i class="fa-solid fa-users-gear"></i> 4. Comitê de Decisão & Produção (Coordenação)
                    </h5>
                    <p style="margin:4px 0 0 0; font-size:0.82rem; color:var(--text-muted);">
                        Encaminhe este produto para análise conjunta com a coordenação na Aba 8.
                    </p>
                </div>
                <button class="btn btn-sm" onclick="enviarSkuIndividualParaCoordenacao('${p.sku}')" style="background: #a855f7; color: #fff; font-weight: 600; padding: 6px 14px; border: none; border-radius: 6px; cursor: pointer;">
                    <i class="fa-solid fa-paper-plane"></i> Enviar p/ Pauta do Comitê
                </button>
            </div>
        </div>
    `;

    body.innerHTML = html;
    modal.style.display = 'flex';

    // Renderizar o gráfico Chart.js após abrir o modal
    setTimeout(() => {
        renderizarGraficoTendenciaInteligencia(d);
    }, 100);
}

let chartInstanceInteligencia = null;
function renderizarGraficoTendenciaInteligencia(d) {
    const ctx = document.getElementById('chart-tendencia-inteligencia');
    if (!ctx) return;

    if (chartInstanceInteligencia) {
        chartInstanceInteligencia.destroy();
    }

    const labels = ['Mês 1 (61-90 dias atrás)', 'Mês 2 (31-60 dias atrás)', 'Mês 3 (Últimos 30 dias)'];
    
    let m3Val = Number(d.m3_direto != null ? d.m3_direto : (d.vendas_diretas_30d != null ? d.vendas_diretas_30d : 0));
    let m2Val = Number(d.m2_direto != null ? d.m2_direto : 0);
    let m1Val = Number(d.m1_direto != null ? d.m1_direto : 0);

    if (m3Val === 0 && d.m3_total && !d.remessas_cd_sp_30d) m3Val = Number(d.m3_total);
    if (m2Val === 0 && d.m2_total) m2Val = Number(d.m2_total);
    if (m1Val === 0 && d.m1_total) m1Val = Number(d.m1_total);

    if (m2Val === 0 && d.vendas_diretas_60d) m2Val = Math.max(0, Number(d.vendas_diretas_60d) - m3Val);
    if (m1Val === 0 && d.vendas_diretas_90d) m1Val = Math.max(0, Number(d.vendas_diretas_90d) - m3Val - m2Val);

    const dataMatriz = [m1Val, m2Val, m3Val];
    const dataCD = [
        0,
        0,
        Number(d.remessas_cd_sp_30d || 0)
    ];

    chartInstanceInteligencia = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Vendas Diretas Matriz',
                    data: dataMatriz,
                    backgroundColor: 'rgba(59, 130, 246, 0.75)',
                    borderColor: '#3b82f6',
                    borderWidth: 1
                },
                {
                    label: 'Transferências p/ CD_SP',
                    data: dataCD,
                    backgroundColor: 'rgba(16, 185, 129, 0.75)',
                    borderColor: '#10b981',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#f8fafc', font: { family: 'Outfit', size: 12 } }
                },
                tooltip: {
                    callbacks: {
                        footer: (items) => {
                            let total = 0;
                            items.forEach(i => total += (i.raw || 0));
                            return 'Demanda Total do Mês: ' + total + ' un';
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                y: {
                    beginAtZero: true,
                    ticks: { color: '#94a3b8', precision: 0 },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                }
            }
        }
    });
}

async function salvarLoteManualJs(sku) {
    const input = document.getElementById(`input-lote-manual-${sku}`);
    if (!input) return;
    const novoLote = parseInt(input.value) || 0;

    try {
        const resp = await fetch('/api/drp/salvar_lote_manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sku: sku, lote_minimo: novoLote })
        });
        const res = await resp.json();
        if (resp.ok && res.success) {
            alert(`✅ Lote Mínimo do SKU ${sku} salvo com sucesso (${novoLote} un)!`);
            document.getElementById('modal-detalhes-inteligencia').style.display = 'none';
            carregarInteligenciaMatriz(true);
        } else {
            alert(`❌ Erro ao salvar lote mínimo: ${res.message || 'Falha'}`);
        }
    } catch (e) {
        console.error('Erro ao salvar lote manual:', e);
        alert('Erro de conexão ao salvar lote mínimo.');
    }
}
async function sincronizarRequisicoesPedidos() {
    const btnMatriz = document.getElementById('btn-sync-requisicoes-matriz');
    const btnTop = document.getElementById('btn-sync-requisicoes-top');
    const btnAba7 = document.getElementById('btn-sync-reqs-aba7');

    const origMatrizHtml = btnMatriz ? btnMatriz.innerHTML : '';
    const origTopHtml = btnTop ? btnTop.innerHTML : '';
    const origAba7Html = btnAba7 ? btnAba7.innerHTML : '';

    if (btnMatriz) btnMatriz.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Atualizando...`;
    if (btnTop) btnTop.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Sincronizando...`;
    if (btnAba7) btnAba7.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Atualizando...`;

    try {
        const resp = await fetch('/api/sync_requisicoes', { method: 'POST' });
        const data = await resp.json();

        if (resp.ok && data.success) {
            let respProds = await fetch('/api/produtos?_t=' + Date.now());
            if (respProds.ok) {
                state.produtos = await respProds.json();
            }

            if (typeof carregarProdutos === 'function') {
                if (typeof renderTabelaMatriz === 'function') renderTabelaMatriz();
                else if (typeof aplicarFiltrosMatriz === 'function') aplicarFiltrosMatriz();
            }

            if (typeof carregarInteligenciaMatriz === 'function') {
                carregarInteligenciaMatriz(true);
            }

            alert(`✅ Sucesso!\n${data.message || 'Requisições e Pedidos de Compra atualizados diretamente da Omie ERP.'}`);
            window.location.reload();
        } else {
            alert(`❌ Erro ao sincronizar requisições: ${data.message || 'Falha na resposta do servidor'}`);
        }
    } catch (e) {
        console.error('Erro ao sincronizar requisições:', e);
        alert('❌ Erro de conexão ao tentar atualizar requisições e pedidos de compra da Omie.');
    } finally {
        if (btnMatriz) btnMatriz.innerHTML = origMatrizHtml;
        if (btnTop) btnTop.innerHTML = origTopHtml;
        if (btnAba7) btnAba7.innerHTML = origAba7Html;
    }
}

// ======================================================================
// ABA 8 — COMITÊ DE DECISÃO & PRODUÇÃO (COORDENAÇÃO)
// ======================================================================
let stateComite = {
    itens: (() => {
        try {
            return JSON.parse(localStorage.getItem('drp_pauta_coordenacao') || '[]');
        } catch (e) {
            return [];
        }
    })(),
    metas: (() => {
        try {
            return JSON.parse(localStorage.getItem('drp_pauta_metas') || '{}');
        } catch (e) {
            return {};
        }
    })(),
    itemSelecionado: null,
    filtroMarca: 'TODAS',
    filtroStatus: 'TODOS',
    busca: ''
};

// Salvar pauta localmente no LocalStorage e atualizar contadores
function salvarPautaLocal() {
    try {
        localStorage.setItem('drp_pauta_coordenacao', JSON.stringify(stateComite.itens));
        localStorage.setItem('drp_pauta_metas', JSON.stringify(stateComite.metas));
    } catch (e) {
        console.warn('Erro ao salvar pauta no localStorage:', e);
    }

    const total = stateComite.itens.length;
    const pendentes = stateComite.itens.filter(i => (i.decisao || 'PENDENTE') === 'PENDENTE').length;
    const aprovados = stateComite.itens.filter(i => i.decisao === 'APROVADO').length;
    const blacklist = stateComite.itens.filter(i => i.decisao === 'BLACKLIST').length;

    const elTotal = document.getElementById('kpi-comite-total');
    if (elTotal) elTotal.innerText = total;
    const elPend = document.getElementById('kpi-comite-pendentes');
    if (elPend) elPend.innerText = pendentes;
    const elAprov = document.getElementById('kpi-comite-aprovados');
    if (elAprov) elAprov.innerText = aprovados;
    const elBl = document.getElementById('kpi-comite-blacklist');
    if (elBl) elBl.innerText = blacklist;

    const countEl = document.getElementById('count-itens-pauta');
    if (countEl) countEl.innerText = total;
}

// Obter dados completos de um produto a partir de state.produtos e stateInteligenciaMatriz
function obterItemPautaCompleto(skuRaw) {
    if (!skuRaw) return null;
    const cleanSku = String(skuRaw).trim().toUpperCase();
    const digitsOnly = cleanSku.replace(/\D/g, '');
    const cleanPadded = cleanSku.padStart(6, '0');

    // 1. Buscar no state.produtos
    let pBase = null;
    if (state.produtos && state.produtos.length > 0) {
        pBase = state.produtos.find(p => {
            const s = String(p.sku || '').trim().toUpperCase();
            return s === cleanSku ||
                   s.padStart(6, '0') === cleanPadded ||
                   (digitsOnly && s.replace(/\D/g, '') === digitsOnly);
        });
    }

    // 2. Buscar no stateInteligenciaMatriz.produtos
    let pIntel = null;
    if (stateInteligenciaMatriz && stateInteligenciaMatriz.produtos && stateInteligenciaMatriz.produtos.length > 0) {
        pIntel = stateInteligenciaMatriz.produtos.find(p => {
            const s = String(p.sku || '').trim().toUpperCase();
            return s === cleanSku ||
                   s.padStart(6, '0') === cleanPadded ||
                   (digitsOnly && s.replace(/\D/g, '') === digitsOnly);
        });
    }

    const dCalc = pIntel?.detalhes_calculo || {};
    const agora = new Date().toLocaleDateString('pt-BR') + ' ' + new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });

    const loteDinamico = Number(pIntel?.lote_minimo || (pBase?.familia?.toUpperCase()?.includes('ESPIRITUALIDADE') ? 500 : (pBase?.familia?.toUpperCase()?.includes('CAMISA') ? 20 : 0)));

    return {
        sku: pBase?.sku || cleanSku,
        nome: pBase?.nome || pBase?.descricao || pIntel?.nome || cleanSku,
        familia: pBase?.familia || pIntel?.familia || 'OUTROS',
        marca: pBase?.marca || pIntel?.marca || 'SHALOM',
        matriz_fisico: Number(pBase?.matriz_fisico || pBase?.matriz || 0),
        matriz_reservado: Number(pBase?.matriz_reservado || 0),
        matriz_disponivel: Number(pBase ? getMatrizDisponivel(pBase) : 0),
        cd_sp_fisico: Number(pBase?.cd_sp_fisico || pBase?.cd_sp || 0),
        cmc: Number(pBase?.cmc || 0.0),
        valor_unitario: Number(pBase?.valor_unitario || 0.0),
        vendas_30d: Number(pBase?.vendas_geral_30d || pBase?.[`vendas_geral_${state.periodoDias}d`] || pBase?.vendas_30d || 0),
        vendas_60d: Number(pBase?.vendas_geral_60d || pBase?.vendas_60d || 0),
        vendas_90d: Number(pBase?.vendas_geral_90d || pBase?.vendas_90d || 0),
        vendas_180d: Number(pBase?.vendas_geral_180d || 0),
        vendas_365d: Number(pBase?.vendas_geral_365d || 0),
        classe_abc: pIntel?.classe_abc_familia || 'C',
        tendencia_vendas: pIntel?.tendencia_vendas || 'Estável ➡️',
        lote_minimo: loteDinamico,
        meses_cobertura_lote: Number(pIntel?.meses_cobertura_lote || 0),
        acao_recomendada: pIntel?.acao_recomendada || 'Análise da Coordenação',
        remessas_cd_sp_30d: Number(dCalc.remessas_cd_sp_30d || pIntel?.remessas_cd_sp_30d || 0),
        detalhes_calculo: dCalc,
        decisao: 'PENDENTE',
        observacao: '',
        qtd_sugerida: loteDinamico > 0 ? loteDinamico : 0,
        adicionado_em: agora
    };
}

// Adicionar um ou mais SKUs à pauta com persistência imediata
async function adicionarSkusPauta(skus) {
    if (!skus || skus.length === 0) return 0;

    let adicionados = 0;
    skus.forEach(s => {
        const itemComp = obterItemPautaCompleto(s);
        if (!itemComp) return;

        // Se já existe na pauta, apenas atualiza os dados
        const idxExistente = stateComite.itens.findIndex(i => String(i.sku).trim().toUpperCase() === String(itemComp.sku).trim().toUpperCase());
        if (idxExistente >= 0) {
            // Mantém a decisão anterior se já havia sido tomada
            itemComp.decisao = stateComite.itens[idxExistente].decisao || 'PENDENTE';
            itemComp.observacao = stateComite.itens[idxExistente].observacao || '';
            if (stateComite.itens[idxExistente].qtd_sugerida) {
                itemComp.qtd_sugerida = stateComite.itens[idxExistente].qtd_sugerida;
            }
            stateComite.itens[idxExistente] = itemComp;
        } else {
            stateComite.itens.unshift(itemComp);
            adicionados++;
        }
    });

    // Salvar localmente no LocalStorage imediatamente
    salvarPautaLocal();
    popularFiltroMarcasPauta();
    renderListaPauta();

    // Seleciona o primeiro produto adicionado para visualização no Raio-X
    if (stateComite.itens.length > 0) {
        selecionarProdutoPauta(stateComite.itens[0].sku);
    }

    // Sincroniza em segundo plano com o backend (se disponível)
    try {
        fetch('/api/coordenacao/adicionar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ skus: skus.map(String) })
        }).catch(() => {});
    } catch (e) {}

    return adicionados;
}

// 1. Enviar produtos selecionados na Matriz para a Pauta
async function enviarSelecionadosParaCoordenacao() {
    if (!state.skusChecadosMatriz || state.skusChecadosMatriz.size === 0) {
        alert('Selecione ao menos um produto na tabela da Matriz usando os checkboxes à esquerda para enviar ao Comitê de Decisão.');
        return;
    }
    const skus = Array.from(state.skusChecadosMatriz);
    const qtd = await adicionarSkusPauta(skus);

    // Limpar seleção
    state.skusChecadosMatriz.clear();
    const elCoord = document.getElementById('count-selected-coordenacao');
    if (elCoord) elCoord.innerText = '0';
    const elBl = document.getElementById('count-selected-blacklist-matriz');
    if (elBl) elBl.innerText = '0';
    renderTabMatriz();

    alert(`✅ ${skus.length} produto(s) adicionado(s) com sucesso à Pauta do Comitê de Decisão!`);
    if (confirm('Deseja abrir a Aba 8 (Comitê de Decisão) agora para iniciar a análise conjunta?')) {
        const tabBtn = document.querySelector('.nav-tab[data-tab="tab-comite-decisao"]');
        if (tabBtn) tabBtn.click();
    }
}

// 2. Carregar Pauta da Coordenação (LocalStorage primeiro + Sincronização remota)
async function carregarPautaCoordenacao(forcar = false) {
    // 1. Se já tem itens no stateComite ou localStorage, renderiza IMEDIATAMENTE sem esperar rede
    try {
        const localItens = JSON.parse(localStorage.getItem('drp_pauta_coordenacao') || '[]');
        const localMetas = JSON.parse(localStorage.getItem('drp_pauta_metas') || '{}');
        if (localItens && localItens.length > 0) {
            stateComite.itens = localItens;
        }
        if (localMetas && Object.keys(localMetas).length > 0) {
            stateComite.metas = { ...stateComite.metas, ...localMetas };
        }
    } catch (e) {}

    salvarPautaLocal();
    popularFiltroMarcasPauta();
    renderListaPauta();

    if (stateComite.itens.length > 0 && !stateComite.itemSelecionado) {
        selecionarProdutoPauta(stateComite.itens[0].sku);
    }

    // 2. Consulta a API em background para mesclar caso o servidor esteja online
    try {
        const resp = await fetch('/api/coordenacao/pauta?_t=' + Date.now());
        if (resp.ok) {
            const data = await resp.json();
            if (data.success && Array.isArray(data.itens)) {
                if (data.itens.length > 0 || stateComite.itens.length === 0) {
                    // Mescla mantendo itens novos locais
                    const skusRemotos = new Set(data.itens.map(i => i.sku));
                    const locaisUnicos = stateComite.itens.filter(i => !skusRemotos.has(i.sku));
                    stateComite.itens = [...data.itens, ...locaisUnicos];
                }
                if (data.metas_fornecedores) {
                    stateComite.metas = { ...data.metas_fornecedores, ...stateComite.metas };
                }
                salvarPautaLocal();
                popularFiltroMarcasPauta();
                renderListaPauta();
                if (stateComite.itemSelecionado) {
                    const refreshed = stateComite.itens.find(i => i.sku === stateComite.itemSelecionado.sku);
                    if (refreshed) selecionarProdutoPauta(refreshed.sku);
                }
            }
        }
    } catch (err) {
        console.log('[COMITE] Servidor remoto não acessível, operando 100% via persistência local.');
    }
}

function popularFiltroMarcasPauta() {
    const sel = document.getElementById('filtro-marca-pauta');
    if (!sel) return;
    const valAtual = sel.value;
    const marcas = Array.from(new Set(stateComite.itens.map(i => i.marca || 'SHALOM'))).sort();
    
    let opts = '<option value="TODAS">Todas as Marcas</option>';
    marcas.forEach(m => {
        opts += `<option value="${m}" ${m === valAtual ? 'selected' : ''}>${m}</option>`;
    });
    sel.innerHTML = opts;
}

function filtrarListaPauta() {
    const buscaEl = document.getElementById('busca-pauta-comite');
    const marcaEl = document.getElementById('filtro-marca-pauta');
    const statusEl = document.getElementById('filtro-status-pauta');

    stateComite.busca = buscaEl ? buscaEl.value.toLowerCase().trim() : '';
    stateComite.filtroMarca = marcaEl ? marcaEl.value : 'TODAS';
    stateComite.filtroStatus = statusEl ? statusEl.value : 'TODOS';

    renderListaPauta();
}

function renderListaPauta() {
    const container = document.getElementById('lista-cards-pauta');
    if (!container) return;

    let lista = stateComite.itens.filter(item => {
        if (stateComite.filtroMarca !== 'TODAS' && (item.marca || 'SHALOM') !== stateComite.filtroMarca) return false;
        if (stateComite.filtroStatus !== 'TODOS' && (item.decisao || 'PENDENTE') !== stateComite.filtroStatus) return false;
        if (stateComite.busca) {
            const termo = stateComite.busca;
            const matchSku = (item.sku || '').toLowerCase().includes(termo);
            const matchNome = (item.nome || '').toLowerCase().includes(termo);
            if (!matchSku && !matchNome) return false;
        }
        return true;
    });

    if (lista.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: var(--text-muted); padding: 30px;">
                Nenhum produto encontrado na pauta com os filtros aplicados.
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    lista.forEach(item => {
        const card = document.createElement('div');
        const isAtivo = stateComite.itemSelecionado && stateComite.itemSelecionado.sku === item.sku;
        
        // Cores de status de decisão
        let decisaoBadge = '<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4);">🟡 Pendente</span>';
        let borderColor = 'rgba(255, 255, 255, 0.08)';
        if (item.decisao === 'APROVADO') {
            decisaoBadge = `<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4);">🟢 Aprovado (${item.qtd_sugerida || 0} un)</span>`;
            borderColor = 'rgba(16, 185, 129, 0.4)';
        } else if (item.decisao === 'BLACKLIST') {
            decisaoBadge = '<span class="badge" style="background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4);">🔴 Descontinuar</span>';
            borderColor = 'rgba(239, 68, 68, 0.4)';
        }

        if (isAtivo) {
            borderColor = '#c084fc';
        }

        card.className = 'card-pauta-item';
        card.style.cssText = `
            background: ${isAtivo ? 'rgba(192, 132, 252, 0.12)' : 'rgba(30, 41, 59, 0.7)'};
            border: 1px solid ${borderColor};
            padding: 10px 12px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
        `;

        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
                <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; gap: 6px; align-items: center; margin-bottom: 3px;">
                        <strong style="color: #60a5fa; font-size: 0.85rem;">${item.sku}</strong>
                        <span class="badge" style="font-size: 0.7rem; padding: 2px 6px; background: rgba(255,255,255,0.06);">${item.marca || 'SHALOM'}</span>
                    </div>
                    <div style="font-size: 0.82rem; font-weight: 500; color: #f8fafc; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${item.nome}">
                        ${item.nome}
                    </div>
                    <div style="display: flex; gap: 10px; font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">
                        <span>Est: <strong style="color:#f8fafc;">${item.matriz_fisico || 0}</strong> un</span>
                        <span>Vendas 30d: <strong style="color:#f8fafc;">${item.vendas_30d || 0}</strong></span>
                        <span>ABC: <strong style="color:#fbbf24;">${item.classe_abc || 'C'}</strong></span>
                    </div>
                </div>
                <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 6px;">
                    <button class="btn btn-sm btn-icon btn-remover-pauta" data-sku="${item.sku}" title="Remover da Pauta" style="color: #94a3b8; font-size: 0.75rem; padding: 2px 5px;">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                    ${decisaoBadge}
                </div>
            </div>
        `;

        card.onclick = (e) => {
            if (e.target.closest('.btn-remover-pauta')) return;
            selecionarProdutoPauta(item.sku);
        };

        const btnRem = card.querySelector('.btn-remover-pauta');
        if (btnRem) {
            btnRem.onclick = (e) => {
                e.stopPropagation();
                removerItemPauta(item.sku);
            };
        }

        container.appendChild(card);
    });
}

function selecionarProdutoPauta(sku) {
    const item = stateComite.itens.find(i => i.sku === sku);
    if (!item) return;

    stateComite.itemSelecionado = item;
    renderListaPauta(); // atualiza card ativo
    renderRaioXComite(item);
}

function renderRaioXComite(item) {
    const painelVazio = document.getElementById('vazio-raiox-comite');
    const painelConteudo = document.getElementById('conteudo-raiox-comite');
    if (!painelConteudo) return;

    painelVazio.style.display = 'none';
    painelConteudo.style.display = 'block';

    const d = item.detalhes_calculo || {};
    const marca = item.marca || 'SHALOM';
    const isTerceiro = !marca.toUpperCase().includes('SHALOM') && !marca.toUpperCase().includes('EDIÇÕES');

    // Cálculo da Margem e Lucro Bruto
    const preco = item.valor_unitario || 0.0;
    const cmc = item.cmc || 0.0;
    const margemBrutaPct = preco > 0 ? (((preco - cmc) / preco) * 100).toFixed(1) : '0';

    // Cálculo consolidado de Pedido Mínimo Financeiro de Terceiros
    let blocoTerceiroHtml = '';
    if (isTerceiro) {
        const metaFornecedor = Number(stateComite.metas[marca] || 1000.0);
        // Itens da mesma marca na pauta
        const itensMesmaMarcaPauta = stateComite.itens.filter(i => (i.marca || '').toUpperCase() === marca.toUpperCase());
        let valorTotalMarcaPauta = 0;
        itensMesmaMarcaPauta.forEach(i => {
            const qtd = i.qtd_sugerida > 0 ? i.qtd_sugerida : (i.lote_minimo > 0 ? i.lote_minimo : 1);
            const pUnit = i.valor_unitario || i.cmc || 20.0;
            valorTotalMarcaPauta += (qtd * pUnit);
        });

        const pctAtingido = Math.min(100, ((valorTotalMarcaPauta / metaFornecedor) * 100)).toFixed(0);
        const faltaValor = Math.max(0, metaFornecedor - valorTotalMarcaPauta);
        const metaAtingida = valorTotalMarcaPauta >= metaFornecedor;

        // Sugestão de outros itens da mesma marca para completar o pedido
        const outrosItensMarca = state.produtos.filter(p => {
            if ((p.marca || '').toUpperCase() !== marca.toUpperCase()) return false;
            if (p.ativo === false || state.blacklist.has(p.sku)) return false;
            // Que não estejam na pauta ainda
            if (stateComite.itens.some(it => it.sku === p.sku)) return false;
            // Apenas com estoque baixo / alerta
            const estMatriz = getMatrizDisponivel(p);
            const vendas30 = p[`vendas_geral_${state.periodoDias}d`] || 0;
            return estMatriz <= 15 || vendas30 > 0;
        }).slice(0, 5);

        let sugestoesHtml = '';
        if (outrosItensMarca.length > 0) {
            sugestoesHtml = `
                <div style="margin-top: 12px; background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 6px; border: 1px dashed rgba(255,255,255,0.15);">
                    <div style="font-size: 0.8rem; font-weight: 600; color: #38bdf8; margin-bottom: 6px;">
                        <i class="fa-solid fa-cart-plus"></i> Sugestões para completar o pedido de ${marca}:
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 4px;">
                        ${outrosItensMarca.map(p => `
                            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.78rem; padding: 3px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 250px;" title="${p.nome}">
                                    <strong>${p.sku}</strong> — ${p.nome} (Est: ${getMatrizDisponivel(p)})
                                </span>
                                <button class="btn btn-sm btn-secondary" onclick="adicionarItemAvulsoPauta('${p.sku}')" style="padding: 1px 6px; font-size: 0.72rem; color: #34d399; border-color: rgba(16,185,129,0.3);">
                                    + Adicionar à Pauta
                                </button>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        blocoTerceiroHtml = `
            <div class="card mb-3" style="background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(14, 165, 233, 0.3); padding: 14px; border-radius: 8px; margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <h5 style="margin:0; color:#38bdf8; font-size: 0.92rem; display:flex; align-items:center; gap:8px;">
                        <i class="fa-solid fa-file-invoice-dollar"></i> Pedido Mínimo Financeiro — Fornecedor: ${marca}
                    </h5>
                    <button class="btn btn-sm btn-secondary" onclick="editarMetaFinanceiraFornecedor('${marca}', ${metaFornecedor})" style="font-size: 0.75rem; padding: 2px 8px;">
                        <i class="fa-solid fa-pen"></i> Editar Meta (R$)
                    </button>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 6px;">
                    <span>Total Consolidado na Pauta: <strong style="color: ${metaAtingida ? '#34d399' : '#fbbf24'};">R$ ${valorTotalMarcaPauta.toFixed(2)}</strong></span>
                    <span>Meta do Fornecedor: <strong>R$ ${metaFornecedor.toFixed(2)}</strong></span>
                </div>
                <!-- Barra de Progresso da Meta -->
                <div style="background: rgba(15, 23, 42, 0.8); border-radius: 6px; height: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.1); margin-bottom: 6px;">
                    <div style="background: ${metaAtingida ? 'linear-gradient(90deg, #10b981, #34d399)' : 'linear-gradient(90deg, #f59e0b, #fbbf24)'}; height: 100%; width: ${pctAtingido}%; transition: width 0.3s ease;"></div>
                </div>
                <div style="font-size: 0.78rem; color: ${metaAtingida ? '#34d399' : '#94a3b8'};">
                    ${metaAtingida ? '🎉 Meta mínima atingida para faturamento!' : `Faltam <strong>R$ ${faltaValor.toFixed(2)}</strong> (${100 - pctAtingido}% restante) para atingir o faturamento mínimo.`}
                </div>
                ${sugestoesHtml}
            </div>
        `;
    }

    painelConteudo.innerHTML = `
        <!-- Cabeçalho do Produto -->
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 12px; margin-bottom: 14px;">
            <div>
                <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 4px;">
                    <span class="badge" style="background: rgba(192, 132, 252, 0.2); color: #c084fc; font-size: 0.85rem; font-weight: 700;">${item.sku}</span>
                    <span class="badge" style="background: rgba(255,255,255,0.06); color: #e2e8f0;">${item.marca || 'SHALOM'}</span>
                    <span class="badge" style="background: rgba(255,255,255,0.06); color: #94a3b8;">${item.familia || 'OUTROS'}</span>
                    <span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24;">⭐ Classe ${item.classe_abc || 'C'}</span>
                </div>
                <h3 style="margin: 0; font-size: 1.25rem; color: #f8fafc;">${item.nome}</h3>
            </div>
            <div style="text-align: right; background: rgba(15, 23, 42, 0.6); padding: 8px 14px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.08);">
                <div style="font-size: 0.75rem; color: var(--text-muted);">Preço / CMC / Margem</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #34d399;">
                    R$ ${preco.toFixed(2)} <span style="font-size:0.75rem; color:#94a3b8; font-weight:normal;">(Custo: R$ ${cmc.toFixed(2)})</span>
                </div>
                <div style="font-size: 0.75rem; color: ${margemBrutaPct > 40 ? '#34d399' : '#fbbf24'}; font-weight: 600;">
                    Margem Estimada: ${margemBrutaPct}%
                </div>
            </div>
        </div>

        <!-- Banner Diagnóstico IA -->
        <div style="padding: 10px 14px; border-radius: 6px; background: rgba(59, 130, 246, 0.12); border: 1px solid rgba(59, 130, 246, 0.3); color: #93c5fd; margin-bottom: 14px; font-size: 0.88rem;">
            <i class="fa-solid fa-wand-magic-sparkles" style="color: #60a5fa; margin-right: 6px;"></i>
            <strong>Recomendação Inteligência:</strong> ${item.acao_recomendada || 'Análise de Reposição'} | Tendência: <strong>${item.tendencia_vendas || 'Estável'}</strong>
        </div>

        <!-- Grid de Vendas & Cobertura -->
        <div class="metrics-grid" style="grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 14px;">
            <div class="metric-card" style="padding: 10px; background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.08);">
                <div class="metric-lbl">Estoque Matriz</div>
                <div class="metric-val" style="font-size: 1.2rem; color: #f8fafc;">${item.matriz_fisico || 0} <small style="font-size:0.75rem;">un</small></div>
            </div>
            <div class="metric-card" style="padding: 10px; background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.08);">
                <div class="metric-lbl">Vendas 30d (Geral)</div>
                <div class="metric-val" style="font-size: 1.2rem; color: #38bdf8;">${item.vendas_30d || 0} <small style="font-size:0.75rem;">un</small></div>
            </div>
            <div class="metric-card" style="padding: 10px; background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.08);">
                <div class="metric-lbl">Média Mensal (90d)</div>
                <div class="metric-val" style="font-size: 1.2rem; color: #60a5fa;">${((item.vendas_90d || 0) / 3).toFixed(1)} <small style="font-size:0.75rem;">un</small></div>
            </div>
            <div class="metric-card" style="padding: 10px; background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.08);">
                <div class="metric-lbl">Vendas Ano (365d)</div>
                <div class="metric-val" style="font-size: 1.2rem; color: #a78bfa;">${item.vendas_365d || 0} <small style="font-size:0.75rem;">un</small></div>
            </div>
            <div class="metric-card" style="padding: 10px; background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.08);">
                <div class="metric-lbl">Remessas CD_SP</div>
                <div class="metric-val" style="font-size: 1.2rem; color: #34d399;">+${item.remessas_cd_sp_30d || 0} <small style="font-size:0.75rem;">un</small></div>
            </div>
        </div>

        <!-- Bloco Lote Mínimo Dinâmico -->
        <div class="card mb-3" style="background: rgba(15, 23, 42, 0.6); padding: 12px 16px; border-radius: 8px; border: 1px solid rgba(245, 158, 11, 0.25); margin-bottom: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div>
                    <h5 style="margin: 0; color: #fbbf24; font-size: 0.9rem;">
                        <i class="fa-solid fa-sliders"></i> Lote Mínimo de Produção / Tiragem
                    </h5>
                    <p style="margin: 2px 0 0 0; font-size: 0.78rem; color: var(--text-muted);">
                        Valor herdado da Inteligência Matriz: <strong>${item.lote_minimo || 0} un</strong> (${item.meses_cobertura_lote || 0} meses de cobertura estimada).
                    </p>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <input type="number" id="input-lote-comite-${item.sku}" class="form-control" style="width: 100px; font-size: 0.85rem;" value="${item.lote_minimo || 0}" min="0" step="10">
                    <button class="btn btn-sm btn-secondary" onclick="salvarLotePeloComite('${item.sku}')" style="font-size: 0.78rem;">
                        <i class="fa-solid fa-floppy-disk"></i> Atualizar Lote
                    </button>
                </div>
            </div>
        </div>

        <!-- Bloco de Terceiros (se aplicável) -->
        ${blocoTerceiroHtml}

        <!-- Mesa de Decisão e Parecer do Coordenador -->
        <div class="card" style="background: rgba(30, 41, 59, 0.9); border: 1px solid #c084fc; padding: 16px; border-radius: 8px;">
            <h4 style="margin: 0 0 10px 0; color: #c084fc; font-size: 0.98rem; display: flex; align-items: center; gap: 8px;">
                <i class="fa-solid fa-gavel"></i> Decisão da Coordenação & Parecer Executivo
            </h4>
            
            <div style="display: grid; grid-template-columns: 140px 1fr; gap: 12px; margin-bottom: 12px;">
                <div>
                    <label style="font-size: 0.8rem; font-weight: 600; color: #f8fafc; display: block; margin-bottom: 4px;">Qtd a Produzir / Comprar:</label>
                    <input type="number" id="decisao-qtd-${item.sku}" class="form-control" value="${item.qtd_sugerida > 0 ? item.qtd_sugerida : (item.lote_minimo > 0 ? item.lote_minimo : 50)}" min="0" step="10">
                </div>
                <div>
                    <label style="font-size: 0.8rem; font-weight: 600; color: #f8fafc; display: block; margin-bottom: 4px;">Justificativa / Parecer Editorial da Coordenação:</label>
                    <input type="text" id="decisao-obs-${item.sku}" class="form-control" value="${item.observacao || ''}" placeholder="Ex: Aguardando nova capa, cotação de papel, reavaliar em 30d...">
                </div>
            </div>

            <!-- Botões de Ação Imediata -->
            <div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 12px;">
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <button class="btn btn-success btn-sm" onclick="registrarDecisaoComite('${item.sku}', 'APROVADO')" style="font-weight: 600;">
                        <i class="fa-solid fa-circle-check"></i> 🟢 Aprovar Produção / Compra
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="registrarDecisaoComite('${item.sku}', 'BLACKLIST')" style="font-weight: 600;">
                        <i class="fa-solid fa-ban"></i> 🔴 Descontinuar (Mover p/ Blacklist)
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="registrarDecisaoComite('${item.sku}', 'PENDENTE')" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; border-color: rgba(245, 158, 11, 0.4); font-weight: 600;">
                        <i class="fa-solid fa-clock"></i> 🟡 Salvar Parecer / Manter Pendente
                    </button>
                </div>
                <div>
                    <button class="btn btn-sm btn-secondary" onclick="removerItemPauta('${item.sku}')" style="color: #94a3b8;">
                        <i class="fa-solid fa-trash"></i> Retirar da Pauta
                    </button>
                </div>
            </div>
        </div>
    `;
}

// 3. Salvar Lote Mínimo a partir da Tela do Comitê
async function salvarLotePeloComite(sku) {
    const input = document.getElementById(`input-lote-comite-${sku}`);
    if (!input) return;
    const novoLote = parseInt(input.value) || 0;
    try {
        const resp = await fetch('/api/salvar_lote_manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sku: sku, lote_minimo: novoLote })
        });
        const res = await resp.json();
        if (res.success) {
            alert(`Lote mínimo do SKU ${sku} atualizado para ${novoLote} un!`);
            carregarPautaCoordenacao();
        } else {
            alert('Erro: ' + res.message);
        }
    } catch (e) {
        alert('Erro ao salvar lote.');
    }
}

// 4. Salvar Decisão no Comitê
async function registrarDecisaoComite(sku, decisao) {
    const qtdEl = document.getElementById(`decisao-qtd-${sku}`);
    const obsEl = document.getElementById(`decisao-obs-${sku}`);
    const qtd = qtdEl ? parseInt(qtdEl.value) || 0 : 0;
    const obs = obsEl ? obsEl.value.trim() : '';

    if (decisao === 'BLACKLIST') {
        if (!confirm(`Tem certeza que deseja DESCONTINUAR o SKU ${sku}? Ele será movido para a Blacklist global e não gerará mais alertas de ruptura.`)) {
            return;
        }
    }

    // 1. Atualização imediata no estado local e LocalStorage
    const item = stateComite.itens.find(i => String(i.sku).trim().toUpperCase() === String(sku).trim().toUpperCase());
    if (item) {
        item.decisao = decisao;
        item.observacao = obs;
        item.qtd_sugerida = qtd;
    }

    if (decisao === 'BLACKLIST') {
        state.blacklist.add(sku);
        try {
            localStorage.setItem('drp_blacklist', JSON.stringify(Array.from(state.blacklist)));
        } catch (e) {}
    }

    salvarPautaLocal();
    renderListaPauta();
    if (stateComite.itemSelecionado && stateComite.itemSelecionado.sku === sku) {
        renderRaioXComite(item);
    }

    if (decisao === 'APROVADO') {
        if (confirm(`✅ Produção de ${qtd} un APROVADA!\nDeseja abrir a tela de Requisição de Compra no Omie agora para gerar a ordem?`)) {
            state.skusChecadosMatriz.add(sku);
            abrirModalRequisicaoCompra();
        }
    } else {
        alert(`✅ Decisão registrada com sucesso: ${decisao}`);
    }

    // 2. Sincronização remota em background
    try {
        fetch('/api/coordenacao/salvar_decisao', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sku: sku,
                decisao: decisao,
                qtd_sugerida: qtd,
                observacao: obs
            })
        }).catch(() => {});
    } catch (e) {}
}

// 5. Remover Item da Pauta
async function removerItemPauta(sku) {
    if (!confirm(`Remover o SKU ${sku} da Pauta da Coordenação?`)) return;

    stateComite.itens = stateComite.itens.filter(i => String(i.sku).trim().toUpperCase() !== String(sku).trim().toUpperCase());
    if (stateComite.itemSelecionado && stateComite.itemSelecionado.sku === sku) {
        stateComite.itemSelecionado = stateComite.itens.length > 0 ? stateComite.itens[0] : null;
    }

    salvarPautaLocal();
    popularFiltroMarcasPauta();
    renderListaPauta();

    if (stateComite.itemSelecionado) {
        selecionarProdutoPauta(stateComite.itemSelecionado.sku);
    } else {
        const v = document.getElementById('vazio-raiox-comite');
        const c = document.getElementById('conteudo-raiox-comite');
        if (v) v.style.display = 'block';
        if (c) c.style.display = 'none';
    }

    try {
        fetch('/api/coordenacao/remover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sku: sku })
        }).catch(() => {});
    } catch (e) {}
}

// 6. Adicionar Item Avulso de Sugestão de Fornecedor
async function adicionarItemAvulsoPauta(sku) {
    await adicionarSkusPauta([sku]);
}

// 7. Editar Meta Financeira de Fornecedor
async function editarMetaFinanceiraFornecedor(fornecedor, metaAtual) {
    const novoValorStr = prompt(`Informe a nova meta de pedido mínimo consolidado em R$ para o fornecedor ${fornecedor}:`, metaAtual);
    if (!novoValorStr) return;
    const novoValor = parseFloat(novoValorStr.replace(',', '.'));
    if (isNaN(novoValor) || novoValor < 0) {
        alert('Valor inválido!');
        return;
    }
    stateComite.metas[fornecedor] = novoValor;
    salvarPautaLocal();
    if (stateComite.itemSelecionado) {
        renderRaioXComite(stateComite.itemSelecionado);
    }

    try {
        fetch('/api/coordenacao/salvar_meta', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fornecedor: fornecedor, meta_valor: novoValor })
        }).catch(() => {});
    } catch (e) {}
}

// 8. Limpar Pauta Completa
async function limparPautaCompleta() {
    if (!confirm('Tem certeza que deseja LIMPAR todos os itens da Pauta da Coordenação?')) return;
    stateComite.itens = [];
    stateComite.itemSelecionado = null;
    salvarPautaLocal();
    renderListaPauta();

    const v = document.getElementById('vazio-raiox-comite');
    const c = document.getElementById('conteudo-raiox-comite');
    if (v) v.style.display = 'block';
    if (c) c.style.display = 'none';

    try {
        fetch('/api/coordenacao/remover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ todos: true })
        }).catch(() => {});
    } catch (e) {}
}

// 9. Gerar Ata Executiva da Reunião em PDF
function gerarAtaComitePdf() {
    if (!stateComite.itens || stateComite.itens.length === 0) {
        alert('A pauta está vazia. Adicione produtos antes de gerar a ata.');
        return;
    }

    const { jsPDF } = window.jspdf;
    const doc = new jsPDF('p', 'mm', 'a4');

    doc.setFont('Helvetica', 'bold');
    doc.setFontSize(16);
    doc.text('Ata do Comitê de Decisão & Produção — Edições Shalom', 14, 18);

    doc.setFont('Helvetica', 'normal');
    doc.setFontSize(10);
    const agora = new Date().toLocaleString('pt-BR');
    doc.text(`Data da Reunião: ${agora} | Total de Itens Avaliados: ${stateComite.itens.length}`, 14, 25);
    doc.line(14, 28, 196, 28);

    let y = 35;
    doc.setFont('Helvetica', 'bold');
    doc.setFontSize(9);
    doc.text('SKU', 14, y);
    doc.text('Produto / Marca', 35, y);
    doc.text('Estoque', 105, y);
    doc.text('Decisão', 125, y);
    doc.text('Parecer / Justificativa', 150, y);
    doc.line(14, y + 2, 196, y + 2);
    y += 7;

    doc.setFont('Helvetica', 'normal');
    stateComite.itens.forEach(item => {
        if (y > 275) {
            doc.addPage();
            y = 20;
        }

        doc.text(String(item.sku), 14, y);
        const nomeCortado = (item.nome || '').substring(0, 32);
        doc.text(`${nomeCortado} (${item.marca || 'SH'})`, 35, y);
        doc.text(`${item.matriz_fisico || 0} un`, 105, y);

        const dec = item.decisao || 'PENDENTE';
        doc.text(dec, 125, y);

        const obs = (item.observacao || '-').substring(0, 24);
        doc.text(obs, 150, y);

        y += 6;
    });

    doc.save(`Ata_Comite_Producao_${new Date().toISOString().slice(0, 10)}.pdf`);
}

// Enviar SKU Individual diretamente (ex: pelo Modal de Diagnóstico da Matriz)
async function enviarSkuIndividualParaCoordenacao(sku) {
    if (!sku) return;
    await adicionarSkusPauta([sku]);
    alert(`✅ SKU ${sku} adicionado à Pauta do Comitê de Decisão!`);
    if (confirm('Deseja abrir a Aba 8 (Comitê de Decisão) agora para analisá-lo?')) {
        const tabBtn = document.querySelector('.nav-tab[data-tab="tab-comite-decisao"]');
        if (tabBtn) tabBtn.click();
    }
}

// Adicionar SKU digitado diretamente na Aba 8
async function adicionarSkuAvulsoPauta() {
    const input = document.getElementById('input-add-sku-pauta');
    if (!input || !input.value.trim()) {
        alert('Digite o código SKU do produto para adicionar à pauta.');
        return;
    }
    const sku = input.value.trim().toUpperCase();
    input.value = '';
    await adicionarSkusPauta([sku]);
    alert(`✅ SKU ${sku} adicionado à Pauta do Comitê de Decisão!`);
}

// Exposição global das funções do Comitê de Decisão
window.adicionarSkuAvulsoPauta = adicionarSkuAvulsoPauta;
window.enviarSelecionadosParaCoordenacao = enviarSelecionadosParaCoordenacao;
window.enviarSkuIndividualParaCoordenacao = enviarSkuIndividualParaCoordenacao;
window.carregarPautaCoordenacao = carregarPautaCoordenacao;
window.renderListaPauta = renderListaPauta;
window.filtrarListaPauta = filtrarListaPauta;
window.selecionarProdutoPauta = selecionarProdutoPauta;
window.salvarLotePeloComite = salvarLotePeloComite;
window.registrarDecisaoComite = registrarDecisaoComite;
window.removerItemPauta = removerItemPauta;
window.editarMetaFinanceiraFornecedor = editarMetaFinanceiraFornecedor;
window.limparPautaCompleta = limparPautaCompleta;
window.adicionarItemAvulsoPauta = adicionarItemAvulsoPauta;
window.adicionarSkusPauta = adicionarSkusPauta;
window.gerarAtaComitePdf = gerarAtaComitePdf;

// ==========================================================================
// MÓDULO DE CONSIGNAÇÃO & LIVRARIAS (IDA E VOLTA)
// ==========================================================================

let stateConsignacao = {
    clienteAtual: null,
    remessasDisponiveis: [],
    remessasSelecionadas: [],
    itensUnificados: [],
    condicaoComercial: 'A_VISTA_AUTO',
    atingeVolume5000: false,
    descontoPadraoPct: 30.0,
    acertoId: null,
    codigoAcerto: null,
    statusAcerto: 'EM_CONFERENCIA'
};

function calcularDescontoPoliticaComercialClient(it, condicao = 'A_VISTA_AUTO', atingeVolume5000 = false) {
    const s = String(it.sku || '').trim().toUpperCase();
    const d = String(it.descricao || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
    let f = String(it.familia || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();

    // 1. Exceções Rígidas
    if (s === '008693' || s === '8693') return condicao.includes('PRAZO') ? 30.0 : 35.0;
    if (s === 'PRD00228' || s === 'PRD00609') return 0.0;
    if (d.includes('ASSEMBLEIA GERAL') && d.includes('2024')) return 0.0;
    if (d.includes('MANUAL') && d.includes('RECICLAGEM') && d.includes('2026')) return 0.0;
    if (d.includes('REMESSA CD') || d.includes('TRANSFERENCIA')) return 0.0;

    // Inferência caso não tenha família cadastrada ou esteja como DIVERSOS
    if (!f || f === 'NONE' || f === 'DIVERSOS') {
        if (d.includes('CAMISA') || d.includes('BABY LOOK')) f = 'CAMISAS';
        else if (d.includes('TERCO') || d.includes('ROSARIO')) f = 'TERCO';
        else if (d.includes('CADERNETA') || d.includes('BLOCO')) f = 'PAPELARIA';
        else if (d.includes('BIBLIA')) f = 'BIBLIAS';
        else f = 'ESPIRITUALIDADE - EDICOES';
        if (!it.familia || it.familia === 'DIVERSOS') {
            it.familia = f;
        }
    }

    // 2. Grupo Especial (50% por Volume)
    const grupo50 = f.includes('EDICAO') || f.includes('EDICO') || ['ESTUDO BIBLICO', 'INFANTIL', 'ORDO AMORIS', 'PHILIPPOS', 'ESPIRITUALIDADE - EDICOES'].includes(f);
    if (grupo50) {
        if (condicao.includes('PRAZO')) return 35.0;
        if (condicao === 'A_VISTA_NORMAL') return 40.0;
        return atingeVolume5000 ? 50.0 : 40.0;
    }

    // 3. Agendas
    if (f === 'AGENDAS') return condicao.includes('PRAZO') ? 30.0 : 35.0;

    // 4. Liturgia
    if (f === 'LITURGIA') return 35.0;

    // 5. Bíblias / Documentos / Escuta / Terceiros / Sazonais
    if (f.includes('BIBLIA') || f.includes('DOCUMENTOS') || ['ESCUTA', 'ESPIRITUALIDADE - TERCEIROS', 'TE SEGUIREI', 'SAZONAIS'].includes(f)) {
        return 30.0;
    }

    // 6. Papelaria
    if (f === 'PAPELARIA') return condicao.includes('PRAZO') ? 20.0 : 25.0;

    // 7. Pano, Rosário, Terço, Imagem, Ícone, Acessórios, Boné, Camisas
    if (['PANO', 'ROSARIO', 'TERCO', 'IMAGEM', 'ICONE', 'ACESSORIOS', 'BONE', 'CAMISAS'].includes(f)) {
        return 20.0;
    }

    // 8. Vela, Toalhas
    if (['VELA', 'TOALHAS'].includes(f)) return condicao.includes('PRAZO') ? 10.0 : 15.0;

    // 9. Manual
    if (f === 'MANUAL') return condicao.includes('PRAZO') ? 0.0 : 10.0;

    // 10. Outros
    return 0.0;
}

function inicializarModuloConsignacao() {
    const inputBusca = document.getElementById('input-busca-cliente-consignacao');
    const btnBusca = document.getElementById('btn-buscar-cliente-consignacao');
    const btnUnificar = document.getElementById('btn-unificar-remessas-consignacao');
    const inputBip = document.getElementById('input-leitor-bipagem-consignacao');
    const inputFiltroItens = document.getElementById('input-filtro-itens-consignacao');
    const btnRetornarTudo = document.getElementById('btn-retornar-tudo');
    const btnZerarRetorno = document.getElementById('btn-zerar-retorno');
    const btnGerarPdf = document.getElementById('btn-gerar-espelho-consignacao-pdf');
    const btnReconferir = document.getElementById('btn-reconferir-consignacao');
    const btnIntegrar = document.getElementById('btn-integrar-omie-consignacao');
    const btnRecarregarHist = document.getElementById('btn-recarregar-historico-acertos');

    if (btnBusca && !btnBusca._init) {
        btnBusca._init = true;
        btnBusca.addEventListener('click', () => {
            const termo = (inputBusca?.value || '').trim();
            if (termo) buscarClientesConsignacao(termo);
        });
        inputBusca?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const termo = (inputBusca.value || '').trim();
                if (termo) buscarClientesConsignacao(termo);
            }
        });
    }

    const selCond = document.getElementById('select-condicao-comercial-consignacao');
    const wrapFixo = document.getElementById('wrapper-desconto-fixo');
    const inputFixo = document.getElementById('input-desconto-consignacao-global');
    const btnRecalcDesc = document.getElementById('btn-recalcular-descontos-consignacao');

    if (selCond && !selCond._init) {
        selCond._init = true;
        selCond.addEventListener('change', () => {
            stateConsignacao.condicaoComercial = selCond.value;
            if (wrapFixo) wrapFixo.style.display = (selCond.value === 'FIXO') ? 'flex' : 'none';
            stateConsignacao.itensUnificados.forEach(it => delete it._descontoManual);
            recalcularTotaisConsignacao();
            renderizarTabelaConsignacao();
            salvarRascunhoConsignacaoLocal();
        });
    }

    if (btnRecalcDesc && !btnRecalcDesc._init) {
        btnRecalcDesc._init = true;
        btnRecalcDesc.addEventListener('click', () => {
            stateConsignacao.itensUnificados.forEach(it => {
                delete it._descontoManual;
            });
            recalcularTotaisConsignacao();
            renderizarTabelaConsignacao();
            salvarRascunhoConsignacaoLocal();
            alert('Descontos recalculados com sucesso com base nas famílias oficiais de cada produto e na condição comercial selecionada!');
        });
    }

    if (inputFixo && !inputFixo._init) {
        inputFixo._init = true;
        inputFixo.addEventListener('input', () => {
            if (stateConsignacao.condicaoComercial === 'FIXO') {
                recalcularTotaisConsignacao();
                renderizarTabelaConsignacao();
            }
        });
    }

    if (btnUnificar && !btnUnificar._init) {
        btnUnificar._init = true;
        btnUnificar.addEventListener('click', unificarRemessasSelecionadas);
    }

    if (inputBip && !inputBip._init) {
        inputBip._init = true;
        inputBip.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const codigo = inputBip.value.trim();
                inputBip.value = '';
                if (codigo) processarBipagemItem(codigo);
            }
        });
    }

    if (inputFiltroItens && !inputFiltroItens._init) {
        inputFiltroItens._init = true;
        inputFiltroItens.addEventListener('input', () => {
            filtrarTabelaConsignacao(inputFiltroItens.value.trim().toLowerCase());
        });
    }

    if (btnRetornarTudo && !btnRetornarTudo._init) {
        btnRetornarTudo._init = true;
        btnRetornarTudo.addEventListener('click', () => {
            stateConsignacao.itensUnificados.forEach(it => {
                it.qtd_retorno = it.qtd_enviada;
                it.qtd_vendida = 0;
                it.valor_total_liquido = 0;
            });
            renderizarTabelaConsignacao();
            recalcularTotaisConsignacao();
            salvarRascunhoConsignacaoLocal();
        });
    }

    if (btnZerarRetorno && !btnZerarRetorno._init) {
        btnZerarRetorno._init = true;
        btnZerarRetorno.addEventListener('click', () => {
            stateConsignacao.itensUnificados.forEach(it => {
                it.qtd_retorno = 0;
                it.qtd_vendida = it.qtd_enviada;
                const descVal = it.preco_unitario * (it.desconto_pct / 100);
                const precoLiq = it.preco_unitario - descVal;
                it.valor_total_liquido = it.qtd_vendida * precoLiq;
            });
            renderizarTabelaConsignacao();
            recalcularTotaisConsignacao();
            salvarRascunhoConsignacaoLocal();
        });
    }

    if (btnGerarPdf && !btnGerarPdf._init) {
        btnGerarPdf._init = true;
        btnGerarPdf.addEventListener('click', gerarEspelhoConsignacaoPDF);
    }

    if (btnReconferir && !btnReconferir._init) {
        btnReconferir._init = true;
        btnReconferir.addEventListener('click', reconferirConsignacao);
    }

    if (btnIntegrar && !btnIntegrar._init) {
        btnIntegrar._init = true;
        btnIntegrar.addEventListener('click', confirmarIntegracaoOmieConsignacao);
    }

    if (btnRecarregarHist && !btnRecarregarHist._init) {
        btnRecarregarHist._init = true;
        btnRecarregarHist.addEventListener('click', carregarHistoricoAcertosConsignacao);
    }

    carregarHistoricoAcertosConsignacao();
}

async function buscarClientesConsignacao(termo) {
    const listaBox = document.getElementById('lista-clientes-consignacao-resultado');
    const gridClientes = document.getElementById('grid-clientes-consignacao');
    if (!listaBox || !gridClientes) return;

    gridClientes.innerHTML = '<div style="color: #38bdf8; padding: 12px;"><i class="fa-solid fa-spinner fa-spin"></i> Buscando no Omie ERP...</div>';
    listaBox.style.display = 'block';

    try {
        const resp = await fetch(`/api/consignacao/clientes?q=${encodeURIComponent(termo)}`);
        const data = await resp.json();
        const clientes = data.clientes || [];

        if (clientes.length === 0) {
            gridClientes.innerHTML = `<div style="color: var(--text-muted); padding: 12px;">Nenhum cliente encontrado com o termo "<strong>${termo}</strong>".</div>`;
            return;
        }

        gridClientes.innerHTML = '';
        clientes.forEach(cli => {
            const card = document.createElement('div');
            card.className = 'card';
            card.style.cssText = 'background: #111b2e; border: 1px solid #1e2f4c; padding: 12px 14px; border-radius: 8px; cursor: pointer; transition: all 0.2s;';
            card.innerHTML = `
                <div style="font-weight: 700; color: #f1f5f9; font-size: 0.92rem; margin-bottom: 3px;">${cli.nome_fantasia || cli.razao_social}</div>
                <div style="font-size: 0.78rem; color: #38bdf8;">${cli.razao_social || ''}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">CNPJ/CPF: ${cli.cnpj_cpf || '-'} ${cli.cidade ? `| ${cli.cidade}/${cli.estado || ''}` : ''}</div>
            `;
            card.onmouseenter = () => card.style.borderColor = '#38bdf8';
            card.onmouseleave = () => card.style.borderColor = '#1e2f4c';
            card.onclick = () => selecionarClienteConsignacao(cli);
            gridClientes.appendChild(card);
        });

    } catch (e) {
        gridClientes.innerHTML = `<div style="color: #f87171; padding: 12px;">Erro ao buscar clientes: ${e.message}</div>`;
    }
}

async function selecionarClienteConsignacao(cliente) {
    stateConsignacao.clienteAtual = cliente;
    const areaRemessas = document.getElementById('area-remessas-consignacao');
    const lblNome = document.getElementById('lbl-cliente-selecionado-nome');
    const lblDoc = document.getElementById('lbl-cliente-selecionado-doc');
    const gridRemessas = document.getElementById('grid-remessas-cliente');

    if (lblNome) lblNome.innerText = cliente.nome_fantasia || cliente.razao_social;
    if (lblDoc) lblDoc.innerText = `CNPJ/CPF: ${cliente.cnpj_cpf || '-'} | Cód. Omie: ${cliente.codigo_cliente}`;

    if (areaRemessas) areaRemessas.style.display = 'block';
    if (gridRemessas) gridRemessas.innerHTML = '<div style="color: #38bdf8; padding: 12px;"><i class="fa-solid fa-spinner fa-spin"></i> Carregando remessas emitidas no Omie...</div>';

    try {
        const resp = await fetch(`/api/consignacao/remessas?nCodCli=${cliente.codigo_cliente}`);
        const data = await resp.json();
        const remessas = data.remessas || [];
        stateConsignacao.remessasDisponiveis = remessas;

        if (remessas.length === 0) {
            gridRemessas.innerHTML = '<div style="color: var(--text-muted); padding: 12px;">Nenhuma remessa em aberto encontrada para este cliente.</div>';
            return;
        }

        gridRemessas.innerHTML = '';
        remessas.forEach(r => {
            const card = document.createElement('div');
            card.style.cssText = 'background: #0f1c33; border: 1px solid #1e3a63; padding: 12px 14px; border-radius: 8px; display: flex; align-items: center; gap: 12px; cursor: pointer;';
            card.innerHTML = `
                <input type="checkbox" id="chk-rem-${r.nCodRem}" value="${r.nCodRem}" class="chk-remessa-consignacao" style="width: 18px; height: 18px; cursor: pointer;" checked>
                <div style="flex: 1;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="color: #ffffff; font-size: 0.95rem;">Remessa #${r.numero_remessa}</strong>
                        <span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; font-size: 0.75rem;">${r.etapa || 'Concluído'}</span>
                    </div>
                    <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 3px;">
                        Data: <strong>${r.data_previsao}</strong> | NF: <strong>${r.numero_nf || '-'}</strong>
                    </div>
                    <div style="font-size: 0.85rem; color: #38bdf8; font-weight: 700; margin-top: 2px;">
                        Valor: R$ ${parseFloat(r.valor_total || 0).toFixed(2).replace('.', ',')}
                    </div>
                </div>
            `;
            card.onclick = (e) => {
                if (e.target.tagName !== 'INPUT') {
                    const chk = card.querySelector('input');
                    if (chk) chk.checked = !chk.checked;
                }
            };
            gridRemessas.appendChild(card);
        });

    } catch (e) {
        if (gridRemessas) gridRemessas.innerHTML = `<div style="color: #f87171; padding: 12px;">Erro ao carregar remessas: ${e.message}</div>`;
    }
}

async function unificarRemessasSelecionadas() {
    const chks = document.querySelectorAll('.chk-remessa-consignacao:checked');
    const remessasIds = Array.from(chks).map(c => parseInt(c.value));

    if (remessasIds.length === 0) {
        alert('Por favor, selecione ao menos uma remessa para unificar.');
        return;
    }

    const btnUnificar = document.getElementById('btn-unificar-remessas-consignacao');
    const originalText = btnUnificar.innerHTML;
    btnUnificar.disabled = true;
    btnUnificar.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Consolidando produtos das remessas...';

    const descInput = document.getElementById('input-desconto-consignacao-global');
    const descontoGlobal = parseFloat(descInput?.value || 30.0);
    stateConsignacao.descontoPadraoPct = descontoGlobal;

    try {
        const resp = await fetch('/api/consignacao/unificar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                remessas: remessasIds,
                desconto_padrao_pct: descontoGlobal
            })
        });

        const data = await resp.json();
        if (!data.success) {
            alert('Erro ao unificar remessas: ' + (data.message || ''));
            return;
        }

        const resultado = data.data;
        stateConsignacao.remessasSelecionadas = resultado.remessas || [];
        stateConsignacao.itensUnificados = resultado.itens || [];
        stateConsignacao.statusAcerto = 'EM_CONFERENCIA';
        stateConsignacao.codigoAcerto = `AC-${new Date().toISOString().replace(/\D/g, '').substring(0, 14)}`;

        // Alterna para Etapa 2
        document.getElementById('painel-consignacao-etapa1').style.display = 'none';
        document.getElementById('painel-consignacao-etapa2').style.display = 'block';

        atualizarStepperConsignacao(2);

        renderizarTabelaConsignacao();
        recalcularTotaisConsignacao();

        // Focar no input de bipagem
        setTimeout(() => {
            const inputBip = document.getElementById('input-leitor-bipagem-consignacao');
            if (inputBip) inputBip.focus();
        }, 150);

        salvarRascunhoConsignacaoLocal();

    } catch (e) {
        alert('Erro de comunicação: ' + e.message);
    } finally {
        btnUnificar.disabled = false;
        btnUnificar.innerHTML = originalText;
    }
}

function renderizarTabelaConsignacao(itensParaExibir = null) {
    const tbody = document.getElementById('tbody-consignacao-itens');
    if (!tbody) return;

    const itens = itensParaExibir || stateConsignacao.itensUnificados;
    tbody.innerHTML = '';

    if (itens.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 30px;">Nenhum item na lista.</td></tr>';
        return;
    }

    itens.forEach(it => {
        const tr = document.createElement('tr');
        tr.id = `row-consig-${it.sku}`;
        if (it.qtd_vendida > 0) {
            tr.classList.add('row-vendido-destaque');
        }

        const descVal = it.preco_unitario * (it.desconto_pct / 100);
        const precoLiq = it.preco_unitario - descVal;
        const totalLiq = it.qtd_vendida * precoLiq;

        let remsBadges = '';
        if (it.remessas_origem && typeof it.remessas_origem === 'object') {
            remsBadges = Object.entries(it.remessas_origem).map(([rNum, q]) => 
                `<span class="badge" style="background: rgba(148, 163, 184, 0.15); color: #cbd5e1; font-size: 0.7rem; padding: 2px 6px;">#${rNum} (${q})</span>`
            ).join(' ');
        }

        tr.innerHTML = `
            <td><strong>${it.sku}</strong></td>
            <td>
                <div style="font-weight: 600; color: #f8fafc;">${it.descricao}</div>
                <div style="font-size: 0.72rem; color: #94a3b8;"><i class="fa-solid fa-tag"></i> ${it.familia || 'DIVERSOS'}</div>
            </td>
            <td style="text-align: center; font-weight: 700; color: #38bdf8;">${it.qtd_enviada}</td>
            <td style="text-align: center; background: rgba(56, 189, 248, 0.05);">
                <input type="number" class="table-retorno-input" value="${it.qtd_retorno}" min="0" max="${it.qtd_enviada}" 
                       onchange="alterarRetornoManual('${it.sku}', this.value)">
            </td>
            <td style="text-align: center; background: rgba(16, 185, 129, 0.05);">
                <strong style="color: ${it.qtd_vendida > 0 ? '#10b981' : '#64748b'}; font-size: 1rem;">${it.qtd_vendida}</strong>
            </td>
            <td style="text-align: right; color: var(--text-muted);">R$ ${it.preco_unitario.toFixed(2).replace('.', ',')}</td>
            <td style="text-align: center; color: #38bdf8;">
                <input type="number" class="form-control" value="${it.desconto_pct}" min="0" max="100" style="width: 52px; display: inline-block; padding: 2px 4px; text-align: center; font-weight: 600; font-size: 0.8rem;" onchange="alterarDescontoItemManual('${it.sku}', this.value)">%
            </td>
            <td style="text-align: right;">
                <strong style="color: ${totalLiq > 0 ? '#10b981' : '#64748b'};">R$ ${totalLiq.toFixed(2).replace('.', ',')}</strong>
            </td>
            <td>${remsBadges}</td>
        `;

        tbody.appendChild(tr);
    });
}

function alterarDescontoItemManual(sku, val) {
    const it = stateConsignacao.itensUnificados.find(x => x.sku === sku);
    if (!it) return;
    it.desconto_pct = parseFloat(val) || 0.0;
    it._descontoManual = true;
    recalcularTotaisConsignacao();
    renderizarTabelaConsignacao();
    salvarRascunhoConsignacaoLocal();
}

function alterarRetornoManual(sku, valStr) {
    const it = stateConsignacao.itensUnificados.find(x => x.sku === sku);
    if (!it) return;

    let ret = parseInt(valStr) || 0;
    if (ret < 0) ret = 0;
    if (ret > it.qtd_enviada) {
        alert(`O retorno não pode ser maior do que o enviado (${it.qtd_enviada} un).`);
        ret = it.qtd_enviada;
    }

    it.qtd_retorno = ret;
    it.qtd_vendida = Math.max(0, it.qtd_enviada - ret);

    const descVal = it.preco_unitario * (it.desconto_pct / 100);
    const precoLiq = it.preco_unitario - descVal;
    it.valor_total_liquido = it.qtd_vendida * precoLiq;

    renderizarTabelaConsignacao();
    recalcularTotaisConsignacao();
    salvarRascunhoConsignacaoLocal();
}

function processarBipagemItem(codigoBipado) {
    const inputMult = document.getElementById('input-qtd-multiplicador-bip');
    const mult = parseInt(inputMult?.value || 1);

    const termo = codigoBipado.toUpperCase();
    const it = stateConsignacao.itensUnificados.find(x => 
        x.sku.toUpperCase() === termo || 
        (x.ean && x.ean === termo) ||
        x.sku.replace(/^0+/, '') === termo.replace(/^0+/, '')
    );

    if (!it) {
        // Toca alerta sonoro de não encontrado
        tocarBeepFeedback(false);
        alert(`Produto SKU/EAN "${codigoBipado}" não faz parte das remessas selecionadas!`);
        return;
    }

    if (it.qtd_retorno + mult > it.qtd_enviada) {
        tocarBeepFeedback(false);
        alert(`Atenção: A quantidade de retorno (${it.qtd_retorno + mult}) ultrapassa o total enviado (${it.qtd_enviada})!`);
        return;
    }

    it.qtd_retorno += mult;
    it.qtd_vendida = Math.max(0, it.qtd_enviada - it.qtd_retorno);

    const descVal = it.preco_unitario * (it.desconto_pct / 100);
    const precoLiq = it.preco_unitario - descVal;
    it.valor_total_liquido = it.qtd_vendida * precoLiq;

    tocarBeepFeedback(true);
    renderizarTabelaConsignacao();
    recalcularTotaisConsignacao();
    salvarRascunhoConsignacaoLocal();

    // Rolar até a linha alterada e piscar
    const tr = document.getElementById(`row-consig-${it.sku}`);
    if (tr) {
        tr.scrollIntoView({ behavior: 'smooth', block: 'center' });
        tr.style.transition = 'background-color 0.4s';
        tr.style.backgroundColor = 'rgba(56, 189, 248, 0.3)';
        setTimeout(() => {
            tr.style.backgroundColor = '';
        }, 600);
    }
}

function tocarBeepFeedback(sucesso = true) {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.type = sucesso ? 'sine' : 'sawtooth';
        osc.frequency.setValueAtTime(sucesso ? 880 : 300, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
        osc.start();
        osc.stop(audioCtx.currentTime + (sucesso ? 0.1 : 0.25));
    } catch (e) {
        // Áudio não suportado ou bloqueado
    }
}

function recalcularTotaisConsignacao() {
    const cond = stateConsignacao.condicaoComercial || 'A_VISTA_AUTO';

    // Se estiver em modo automático por política, simula corte de volume R$ 5.000 para liberar 50%
    if (cond === 'FIXO') {
        const descFixo = parseFloat(document.getElementById('input-desconto-consignacao-global')?.value || 30.0);
        stateConsignacao.itensUnificados.forEach(it => {
            if (!it._descontoManual) it.desconto_pct = descFixo;
        });
    } else {
        let simLiq = 0.0;
        stateConsignacao.itensUnificados.forEach(it => {
            if (it.qtd_vendida > 0) {
                const descSim = calcularDescontoPoliticaComercialClient(it, cond, true);
                simLiq += (it.qtd_vendida * it.preco_unitario * (1 - descSim / 100));
            }
        });
        const atingeVolume = (simLiq > 5000.0);
        stateConsignacao.atingeVolume5000 = atingeVolume;

        stateConsignacao.itensUnificados.forEach(it => {
            if (!it._descontoManual) {
                it.desconto_pct = calcularDescontoPoliticaComercialClient(it, cond, atingeVolume);
            }
        });
    }

    let totEnv = 0;
    let totRet = 0;
    let totVend = 0;
    let totBruto = 0.0;
    let totLiq = 0.0;

    stateConsignacao.itensUnificados.forEach(it => {
        totEnv += it.qtd_enviada;
        totRet += it.qtd_retorno;
        totVend += it.qtd_vendida;

        totBruto += (it.qtd_vendida * it.preco_unitario);
        const descVal = it.preco_unitario * (it.desconto_pct / 100);
        const precoLiq = it.preco_unitario - descVal;
        totLiq += (it.qtd_vendida * precoLiq);
    });

    const elEnv = document.getElementById('metric-consig-enviado');
    const elRet = document.getElementById('metric-consig-retorno');
    const elVend = document.getElementById('metric-consig-vendido');
    const elTotLiq = document.getElementById('metric-consig-total-liq');
    const elTotLiqLbl = document.getElementById('lbl-metric-desc-consignacao');

    if (elEnv) elEnv.innerText = totEnv;
    if (elRet) elRet.innerText = totRet;
    if (elVend) elVend.innerText = totVend;
    if (elTotLiq) elTotLiq.innerText = `R$ ${totLiq.toFixed(2).replace('.', ',')}`;

    if (elTotLiqLbl) {
        if (cond === 'FIXO') {
            elTotLiqLbl.innerText = `Líquido (Desconto Fixo)`;
        } else if (stateConsignacao.atingeVolume5000) {
            elTotLiqLbl.innerText = `Líquido c/ Volume 50% (> R$ 5.000)`;
        } else if (cond === 'A_PRAZO') {
            elTotLiqLbl.innerText = `Líquido A Prazo (Política Comercial)`;
        } else {
            elTotLiqLbl.innerText = `Líquido À Vista (Política Comercial)`;
        }
    }

    const badgeVol = document.getElementById('badge-status-volume-consignacao');
    if (badgeVol) {
        if (cond === 'FIXO') {
            badgeVol.style.background = 'rgba(148, 163, 184, 0.15)';
            badgeVol.style.color = '#cbd5e1';
            badgeVol.style.borderColor = 'rgba(148, 163, 184, 0.3)';
            badgeVol.innerHTML = '<i class="fa-solid fa-calculator"></i> Desconto Fixo Manual Ativo';
        } else if (stateConsignacao.atingeVolume5000) {
            badgeVol.style.background = 'rgba(16, 185, 129, 0.2)';
            badgeVol.style.color = '#34d399';
            badgeVol.style.borderColor = 'rgba(16, 185, 129, 0.4)';
            badgeVol.innerHTML = '<i class="fa-solid fa-rocket"></i> Volume &gt; R$ 5.000 Atingido! (50% Liberado no Grupo Edições)';
        } else if (cond === 'A_PRAZO') {
            badgeVol.style.background = 'rgba(234, 179, 8, 0.15)';
            badgeVol.style.color = '#fbbf24';
            badgeVol.style.borderColor = 'rgba(234, 179, 8, 0.3)';
            badgeVol.innerHTML = '<i class="fa-solid fa-calendar"></i> Condição A Prazo (35% Edições / 20% Camisas)';
        } else {
            badgeVol.style.background = 'rgba(56, 189, 248, 0.15)';
            badgeVol.style.color = '#38bdf8';
            badgeVol.style.borderColor = 'rgba(56, 189, 248, 0.3)';
            badgeVol.innerHTML = '<i class="fa-solid fa-info-circle"></i> À Vista Normal (40% Edições — corte de volume é R$ 5.000)';
        }
    }

    stateConsignacao.totalEnviado = totEnv;
    stateConsignacao.totalRetorno = totRet;
    stateConsignacao.totalVendido = totVend;
    stateConsignacao.valorTotalBruto = totBruto;
    stateConsignacao.valorTotalDesconto = totBruto - totLiq;
    stateConsignacao.valorTotalLiquido = totLiq;
}

function filtrarTabelaConsignacao(termo) {
    if (!termo) {
        renderizarTabelaConsignacao();
        return;
    }
    const filtrados = stateConsignacao.itensUnificados.filter(x => 
        x.sku.toLowerCase().includes(termo) || 
        x.descricao.toLowerCase().includes(termo)
    );
    renderizarTabelaConsignacao(filtrados);
}

function salvarRascunhoConsignacaoLocal() {
    try {
        localStorage.setItem('drp_rascunho_consignacao', JSON.stringify(stateConsignacao));
    } catch (e) {
        // LocalStorage quota
    }
}

async function gerarEspelhoConsignacaoPDF() {
    if (!window.jspdf || !window.jspdf.jsPDF) {
        alert('Biblioteca jsPDF não carregada. Verifique sua conexão.');
        return;
    }

    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

    const cli = stateConsignacao.clienteAtual || {};
    const itensVendidos = stateConsignacao.itensUnificados.filter(x => x.qtd_vendida > 0);
    const remsNums = stateConsignacao.remessasSelecionadas.map(r => `#${r.numero_remessa}`).join(', ');

    // 1. Cabeçalho
    doc.setFillColor(15, 23, 42);
    doc.rect(0, 0, 210, 32, 'F');

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(14);
    doc.setTextColor(255, 255, 255);
    doc.text("EDIÇÕES SHALOM — ESPELHO DE ACERTO DE CONSIGNAÇÃO", 14, 14);

    doc.setFontSize(8.5);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(148, 163, 184);
    doc.text(`Cliente: ${cli.nome_fantasia || cli.razao_social} | CNPJ/CPF: ${cli.cnpj_cpf || '-'}`, 14, 21);
    doc.text(`Remessas Unificadas: ${remsNums} | Emissão: ${new Date().toLocaleDateString('pt-BR')} às ${new Date().toLocaleTimeString('pt-BR')}`, 14, 27);

    // 2. Resumo Financeiro Box
    doc.setFillColor(241, 245, 249);
    doc.rect(14, 38, 182, 18, 'F');
    doc.setDrawColor(203, 213, 225);
    doc.rect(14, 38, 182, 18, 'S');

    doc.setFontSize(8);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text("TOTAL ENVIADO", 20, 44);
    doc.text("DEVOLVIDO (FÍSICO)", 62, 44);
    doc.text("PEÇAS VENDIDAS", 112, 44);
    doc.text("FATURAMENTO LÍQUIDO", 152, 44);

    doc.setFontSize(11);
    doc.setTextColor(15, 23, 42);
    doc.text(String(stateConsignacao.totalEnviado || 0), 20, 51);
    doc.text(String(stateConsignacao.totalRetorno || 0), 62, 51);
    doc.setTextColor(22, 163, 74);
    doc.text(String(stateConsignacao.totalVendido || 0), 112, 51);
    doc.setTextColor(2, 132, 199);
    doc.text(`R$ ${(stateConsignacao.valorTotalLiquido || 0).toFixed(2).replace('.', ',')}`, 152, 51);

    // 3. Tabela de Itens Vendidos
    let y = 65;
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(15, 23, 42);
    doc.text(`Relação de Livros e Produtos Vendidos (${itensVendidos.length} títulos)`, 14, y);

    y += 5;
    doc.setFillColor(30, 41, 59);
    doc.rect(14, y, 182, 6, 'F');

    doc.setFontSize(7.5);
    doc.setTextColor(255, 255, 255);
    doc.text("SKU", 16, y + 4.2);
    doc.text("Título / Descrição", 36, y + 4.2);
    doc.text("Enviado", 115, y + 4.2);
    doc.text("Retorno", 130, y + 4.2);
    doc.text("Vendido", 145, y + 4.2);
    doc.text("Preço Capa", 160, y + 4.2);
    doc.text("Total Líq.", 180, y + 4.2);

    y += 6;
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7);
    doc.setTextColor(30, 41, 59);

    if (itensVendidos.length === 0) {
        y += 6;
        doc.text("Nenhum item vendido (100% de retorno da mercadoria remetida).", 16, y);
    } else {
        itensVendidos.forEach((it, idx) => {
            if (y > 275) {
                doc.addPage();
                y = 15;
            }

            if (idx % 2 === 1) {
                doc.setFillColor(248, 250, 252);
                doc.rect(14, y, 182, 5.5, 'F');
            }

            const descTrunc = it.descricao.length > 46 ? it.descricao.substring(0, 46) + '...' : it.descricao;

            doc.text(it.sku, 16, y + 3.8);
            doc.text(descTrunc, 36, y + 3.8);
            doc.text(String(it.qtd_enviada), 118, y + 3.8, { align: 'center' });
            doc.text(String(it.qtd_retorno), 134, y + 3.8, { align: 'center' });
            doc.setFont('helvetica', 'bold');
            doc.text(String(it.qtd_vendida), 149, y + 3.8, { align: 'center' });
            doc.setFont('helvetica', 'normal');
            doc.text(`R$ ${it.preco_unitario.toFixed(2).replace('.', ',')}`, 170, y + 3.8, { align: 'right' });
            doc.setFont('helvetica', 'bold');
            doc.text(`R$ ${it.valor_total_liquido.toFixed(2).replace('.', ',')}`, 194, y + 3.8, { align: 'right' });
            doc.setFont('helvetica', 'normal');

            y += 5.5;
        });
    }

    // Rodapé de Assinatura Comercial
    y = Math.min(y + 15, 270);
    doc.setFontSize(7.5);
    doc.setTextColor(100, 116, 139);
    doc.text("Conferido por: ____________________________     Validado Vendedora: ____________________________", 14, y);
    doc.text("Este documento destina-se ao acerto comercial prévio para emissão da NF de Devolução (CFOP 1.917) e Venda.", 14, y + 5);

    // Salvar PDF
    const nomeArquivo = `Espelho_Consignacao_${(cli.nome_fantasia || 'Cliente').replace(/\s+/g, '_')}_${stateConsignacao.codigoAcerto}.pdf`;
    doc.save(nomeArquivo);

    // Atualizar status para AGUARDANDO_VENDEDORA
    stateConsignacao.statusAcerto = 'AGUARDANDO_VENDEDORA';
    atualizarStepperConsignacao(3);

    const badge = document.getElementById('badge-status-acerto');
    if (badge) {
        badge.style.background = 'rgba(234, 179, 8, 0.2)';
        badge.style.color = '#fbbf24';
        badge.style.borderColor = 'rgba(234, 179, 8, 0.4)';
        badge.innerHTML = '⏳ Aguardando Validação Comercial (Vendedora)';
    }

    // Salvar no Turso DB
    await salvarAcertoNoTursoDB();
    alert(`📄 Espelho em PDF gerado com sucesso!\nArquivo: ${nomeArquivo}\n\nStatus atualizado para: Aguardando Validação Comercial.`);
}

function atualizarStepperConsignacao(passo) {
    for (let i = 1; i <= 4; i++) {
        const item = document.getElementById(`step-${i}-indicador`);
        if (!item) continue;
        item.classList.remove('active', 'completed');
        if (i < passo) {
            item.classList.add('completed');
        } else if (i === passo) {
            item.classList.add('active');
        }
    }
}

function reconferirConsignacao() {
    stateConsignacao.statusAcerto = 'EM_CONFERENCIA';
    atualizarStepperConsignacao(2);

    const badge = document.getElementById('badge-status-acerto');
    if (badge) {
        badge.style.background = 'rgba(56, 189, 248, 0.2)';
        badge.style.color = '#38bdf8';
        badge.style.borderColor = 'rgba(56, 189, 248, 0.4)';
        badge.innerHTML = '📝 Em Conferência Física (Reaberto)';
    }

    const btnIntegrar = document.getElementById('btn-integrar-omie-consignacao');
    if (btnIntegrar) {
        btnIntegrar.disabled = false;
        btnIntegrar.style.opacity = '1';
        btnIntegrar.style.background = 'linear-gradient(135deg, #10b981, #059669)';
        btnIntegrar.innerHTML = '<i class="fa-solid fa-paper-plane"></i> 2. Confirmar Acerto & Integrar no Omie';
    }

    const inputBip = document.getElementById('input-leitor-bipagem-consignacao');
    if (inputBip) {
        inputBip.focus();
        inputBip.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

async function salvarAcertoNoTursoDB() {
    const payload = {
        codigo_acerto: stateConsignacao.codigoAcerto,
        codigo_cliente_omie: stateConsignacao.clienteAtual?.codigo_cliente,
        cliente_nome: stateConsignacao.clienteAtual?.nome_fantasia || stateConsignacao.clienteAtual?.razao_social,
        cliente_cnpj_cpf: stateConsignacao.clienteAtual?.cnpj_cpf,
        remessas_unificadas: stateConsignacao.remessasSelecionadas,
        status: stateConsignacao.statusAcerto,
        desconto_padrao_pct: stateConsignacao.descontoPadraoPct,
        total_enviado: stateConsignacao.totalEnviado,
        total_retorno: stateConsignacao.totalRetorno,
        total_vendido: stateConsignacao.totalVendido,
        valor_total_bruto: stateConsignacao.valorTotalBruto,
        valor_total_desconto: stateConsignacao.valorTotalDesconto,
        valor_total_liquido: stateConsignacao.valorTotalLiquido,
        itens: stateConsignacao.itensUnificados
    };

    try {
        const resp = await fetch('/api/consignacao/salvar_acerto', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (data.acerto_id) {
            stateConsignacao.acertoId = data.acerto_id;
        }
        carregarHistoricoAcertosConsignacao();
    } catch (e) {
        console.error('Erro ao salvar acerto no Turso:', e);
    }
}

async function confirmarIntegracaoOmieConsignacao() {
    if (!stateConsignacao.acertoId) {
        await salvarAcertoNoTursoDB();
    }

    const totVend = stateConsignacao.totalVendido || 0;
    const totLiq = (stateConsignacao.valorTotalLiquido || 0).toFixed(2).replace('.', ',');
    const totRet = stateConsignacao.totalRetorno || 0;

    const msg = `Confirma a integração oficial do acerto no Omie ERP?\n\n` +
                `• Cliente: ${stateConsignacao.clienteAtual?.nome_fantasia || 'Não selecionado'}\n` +
                `• Peças Físicas Devolvidas ao Estoque: ${totRet} un (CFOP 1.917 / Compras para Revenda)\n` +
                `• Peças Faturadas em Venda: ${totVend} un\n` +
                `• Valor Líquido do Pedido de Venda: R$ ${totLiq}\n\n` +
                `Esta operação liquidará as remessas de origem no Omie e registrará a devolução (CFOP 1.917) e o Pedido de Venda. Deseja continuar?`;

    if (!confirm(msg)) return;

    const btnIntegrar = document.getElementById('btn-integrar-omie-consignacao');
    const originalText = btnIntegrar.innerHTML;
    btnIntegrar.disabled = true;
    btnIntegrar.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Integrando com Omie ERP...';

    try {
        const pedManual = document.getElementById('input-pedido-manual-consignacao')?.value.trim() || '';
        const codVend = document.getElementById('select-vendedora-consignacao')?.value || '1818533448';
        const resp = await fetch('/api/consignacao/integrar_omie', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                acerto_id: stateConsignacao.acertoId,
                numero_pedido_manual: pedManual,
                codigo_vendedora: codVend
            })
        });

        const data = await resp.json();
        if (data.success) {
            let infoMsg = '✅ Acerto integrado no Omie com sucesso!\n\n';
            if (data.pedido_venda) {
                infoMsg += `• Pedido de Venda: #${data.pedido_venda.numero_pedido || ''} (${data.pedido_venda.descricao_status || 'OK'})\n`;
            }
            if (data.devolucoes && data.devolucoes.length > 0) {
                infoMsg += `• Remessas com Devolução Registrada: ${data.devolucoes.map(d => '#' + d.numero_remessa).join(', ')}\n`;
            }

            const badge = document.getElementById('badge-status-acerto');
            if (badge) {
                badge.style.background = 'rgba(16, 185, 129, 0.2)';
                badge.style.color = '#34d399';
                badge.style.borderColor = 'rgba(16, 185, 129, 0.4)';
                badge.innerHTML = '✅ Finalizado & Integrado no Omie ERP';
            }

            atualizarStepperConsignacao(4);
            stateConsignacao.statusAcerto = 'FINALIZADO_OMIE';

            btnIntegrar.disabled = true;
            btnIntegrar.innerHTML = '<i class="fa-solid fa-check-double"></i> Acerto Finalizado no Omie';
            btnIntegrar.style.background = '#047857';

            alert(infoMsg);
            carregarHistoricoAcertosConsignacao();
        } else {
            alert('Atenção na integração: ' + (data.message || (data.erros || []).join('\n')));
            btnIntegrar.disabled = false;
            btnIntegrar.innerHTML = originalText;
        }
    } catch (e) {
        alert('Erro ao comunicar com backend: ' + e.message);
        btnIntegrar.disabled = false;
        btnIntegrar.innerHTML = originalText;
    }
}

async function carregarHistoricoAcertosConsignacao() {
    const tbody = document.getElementById('tbody-historico-consignacao');
    if (!tbody) return;

    try {
        const resp = await fetch('/api/consignacao/acertos');
        const data = await resp.json();
        const acertos = data.acertos || [];

        if (acertos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 20px;">Nenhum acerto salvo ainda.</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        acertos.forEach(ac => {
            const tr = document.createElement('tr');
            let statusBadge = '';
            if (ac.status === 'FINALIZADO_OMIE') {
                statusBadge = '<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399;">✅ Concluído Omie</span>';
            } else if (ac.status === 'AGUARDANDO_VENDEDORA') {
                statusBadge = '<span class="badge" style="background: rgba(234, 179, 8, 0.2); color: #fbbf24;">⏳ Aguardando Vendedora</span>';
            } else {
                statusBadge = '<span class="badge" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8;">📝 Em Conferência</span>';
            }

            let remsTxt = '-';
            if (Array.isArray(ac.remessas_unificadas)) {
                remsTxt = ac.remessas_unificadas.map(r => `#${r.numero_remessa || r}`).join(', ');
            }

            tr.innerHTML = `
                <td><strong>${ac.codigo_acerto}</strong></td>
                <td>${ac.cliente_nome}</td>
                <td><small style="color: var(--text-muted);">${remsTxt}</small></td>
                <td style="text-align: center;">${ac.total_enviado}</td>
                <td style="text-align: center; color: #eab308;">${ac.total_retorno}</td>
                <td style="text-align: center; color: #10b981; font-weight: 700;">${ac.total_vendido}</td>
                <td style="text-align: right; font-weight: 700; color: #38bdf8;">R$ ${(parseFloat(ac.valor_total_liquido) || 0).toFixed(2).replace('.', ',')}</td>
                <td>${statusBadge}</td>
                <td><small style="color: var(--text-muted);">${(ac.criado_em || '').substring(0, 16)}</small></td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="carregarAcertoSalvo(${ac.id})" title="Abrir acerto para conferência">
                        <i class="fa-solid fa-folder-open"></i> Abrir
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });

    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: #f87171;">Erro ao carregar histórico: ${e.message}</td></tr>`;
    }
}

async function carregarAcertoSalvo(acertoId) {
    try {
        const resp = await fetch(`/api/consignacao/acerto?id=${acertoId}`);
        const data = await resp.json();
        const acerto = data.acerto;

        if (!acerto || !acerto.id) {
            alert('Acerto não encontrado.');
            return;
        }

        stateConsignacao.acertoId = acerto.id;
        stateConsignacao.codigoAcerto = acerto.codigo_acerto;
        stateConsignacao.clienteAtual = {
            codigo_cliente: acerto.codigo_cliente_omie,
            nome_fantasia: acerto.cliente_nome,
            razao_social: acerto.cliente_nome,
            cnpj_cpf: acerto.cliente_cnpj_cpf
        };
        stateConsignacao.remessasSelecionadas = acerto.remessas_unificadas || [];
        stateConsignacao.descontoPadraoPct = parseFloat(acerto.desconto_padrao_pct) || 30.0;
        stateConsignacao.statusAcerto = acerto.status;
        stateConsignacao.condicaoComercial = acerto.condicao_comercial || 'A_VISTA_AUTO';

        const selCond = document.getElementById('select-condicao-comercial-consignacao');
        if (selCond) selCond.value = stateConsignacao.condicaoComercial;

        // Normalização completa dos itens com enriquecimento de Família do catálogo
        stateConsignacao.itensUnificados = (acerto.itens || []).map(it => {
            const sku = String(it.sku || '').trim();
            const ncod = parseInt(it.codigo_produto_omie || it.codigo_produto || 0);

            // Tenta associar com o catálogo para puxar a Família Oficial
            let fam = it.familia || '';
            const pCat = (state.produtos || []).find(p => 
                String(p.sku || '').trim() === sku || 
                String(p.codigo || '').trim() === sku || 
                (ncod && p.id_produto == ncod)
            );
            if (!fam || fam === 'DIVERSOS') {
                if (pCat && pCat.familia) fam = pCat.familia;
            }

            let remsOrig = it.remessas_origem || {};
            if (typeof remsOrig === 'string') {
                try { remsOrig = JSON.parse(remsOrig); } catch(e) { remsOrig = {}; }
            }
            return {
                sku: sku,
                codigo_produto: ncod,
                descricao: it.descricao || (pCat ? pCat.nome : ''),
                familia: fam,
                qtd_enviada: parseInt(it.qtd_enviada) || 0,
                qtd_retorno: parseInt(it.qtd_retorno) || 0,
                qtd_vendida: parseInt(it.qtd_vendida) || 0,
                preco_unitario: parseFloat(it.preco_unitario) || (pCat ? pCat.valor_unitario : 0.0),
                desconto_pct: parseFloat(it.desconto_pct) || 0.0,
                valor_total_liquido: parseFloat(it.valor_total_liquido) || 0.0,
                remessas_origem: remsOrig
            };
        });

        // Aplica a política comercial de descontos por família e recalcula totais
        recalcularTotaisConsignacao();
        renderizarTabelaConsignacao();

        // Alternar visualização para a Mesa de Conferência
        const pEtapa1 = document.getElementById('painel-consignacao-etapa1');
        const pEtapa2 = document.getElementById('painel-consignacao-etapa2');
        if (pEtapa1) pEtapa1.style.display = 'none';
        if (pEtapa2) {
            pEtapa2.style.display = 'block';
            pEtapa2.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        const badge = document.getElementById('badge-status-acerto');
        const btnIntegrar = document.getElementById('btn-integrar-omie-consignacao');

        const inpPedManual = document.getElementById('input-pedido-manual-consignacao');
        if (inpPedManual) {
            let numP = '';
            if (typeof acerto.dados_pedido_venda_omie === 'string' && acerto.dados_pedido_venda_omie.trim()) {
                try {
                    const parsedPv = JSON.parse(acerto.dados_pedido_venda_omie);
                    numP = parsedPv.numero_pedido || '';
                } catch(e) {
                    numP = acerto.dados_pedido_venda_omie;
                }
            } else if (typeof acerto.dados_pedido_venda_omie === 'object' && acerto.dados_pedido_venda_omie) {
                numP = acerto.dados_pedido_venda_omie.numero_pedido || '';
            }
            inpPedManual.value = numP ? String(numP).replace(/^0+/, '') : '';
        }

        if (acerto.status === 'FINALIZADO_OMIE') {
            if (badge) {
                badge.style.background = 'rgba(16, 185, 129, 0.2)';
                badge.style.color = '#34d399';
                badge.innerHTML = '✅ Finalizado & Integrado no Omie ERP';
            }
            atualizarStepperConsignacao(4);
            if (btnIntegrar) {
                btnIntegrar.disabled = true;
                btnIntegrar.innerHTML = '<i class="fa-solid fa-check-double"></i> Acerto Finalizado no Omie';
                btnIntegrar.style.background = '#047857';
            }
        } else if (acerto.status === 'AGUARDANDO_VENDEDORA') {
            if (badge) {
                badge.style.background = 'rgba(234, 179, 8, 0.2)';
                badge.style.color = '#fbbf24';
                badge.innerHTML = '⏳ Aguardando Validação Comercial (Vendedora)';
            }
            atualizarStepperConsignacao(3);
            if (btnIntegrar) {
                btnIntegrar.disabled = false;
                btnIntegrar.style.opacity = '1';
                btnIntegrar.style.background = 'linear-gradient(135deg, #10b981, #059669)';
                btnIntegrar.innerHTML = '<i class="fa-solid fa-paper-plane"></i> 2. Confirmar Acerto & Integrar no Omie';
            }
        } else {
            if (badge) {
                badge.style.background = 'rgba(56, 189, 248, 0.2)';
                badge.style.color = '#38bdf8';
                badge.innerHTML = '📝 Em Conferência Física';
            }
            atualizarStepperConsignacao(2);
            if (btnIntegrar) {
                btnIntegrar.disabled = false;
                btnIntegrar.style.opacity = '1';
                btnIntegrar.style.background = 'linear-gradient(135deg, #10b981, #059669)';
                btnIntegrar.innerHTML = '<i class="fa-solid fa-paper-plane"></i> 2. Confirmar Acerto & Integrar no Omie';
            }
        }

        renderizarTabelaConsignacao();
        recalcularTotaisConsignacao();

    } catch (e) {
        alert('Erro ao carregar acerto: ' + e.message);
    }
}

// Expor funções globais da Consignação
window.inicializarModuloConsignacao = inicializarModuloConsignacao;
window.buscarClientesConsignacao = buscarClientesConsignacao;
window.selecionarClienteConsignacao = selecionarClienteConsignacao;
window.unificarRemessasSelecionadas = unificarRemessasSelecionadas;
window.alterarRetornoManual = alterarRetornoManual;
window.processarBipagemItem = processarBipagemItem;
window.gerarEspelhoConsignacaoPDF = gerarEspelhoConsignacaoPDF;
window.reconferirConsignacao = reconferirConsignacao;
window.confirmarIntegracaoOmieConsignacao = confirmarIntegracaoOmieConsignacao;
window.carregarHistoricoAcertosConsignacao = carregarHistoricoAcertosConsignacao;
window.carregarAcertoSalvo = carregarAcertoSalvo;
window.atualizarStepperConsignacao = atualizarStepperConsignacao;

// =========================================================================
// MÓDULO 3: GESTÃO DE ASSINATURAS PÃO DA VIDA (LITURGIA DIÁRIA)
// =========================================================================
window.dadosAssinaturas = null;
window.grupoAtivoAssinaturas = 'paroquias_ce';
window.paroquiaSelecionadaParaRemessa = null;

async function carregarAssinaturasPDV(forcarDownload = false) {
    const badgeSync = document.getElementById('ass-status-badge');
    const btnSync = document.getElementById('btn-sync-assinaturas');
    try {
        if (btnSync) {
            btnSync.disabled = true;
            btnSync.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sincronizando Planilha...';
        }
        if (badgeSync) {
            badgeSync.innerHTML = '<i class="fa-solid fa-spinner fa-spin" style="color: #38bdf8;"></i> Lendo planilha e calculando ciclo de 12 exemplares...';
        }

        const endpoint = forcarDownload ? '/api/assinaturas/sincronizar' : '/api/assinaturas/dados';
        const method = forcarDownload ? 'POST' : 'GET';
        const resp = await fetch(endpoint, { method });
        const dados = await resp.json();

        if (!dados.sucesso) {
            throw new Error(dados.erro || 'Falha ao processar planilha de assinaturas.');
        }

        window.dadosAssinaturas = dados;

        // Atualizar Métricas Consolidadas
        const cons = dados.consolidado_geral || {};
        document.getElementById('metric-ass-jan').innerText = (cons.jan27 || 0).toLocaleString('pt-BR');
        document.getElementById('metric-ass-fev').innerText = (cons.fev27 || 0).toLocaleString('pt-BR');
        document.getElementById('metric-ass-mar').innerText = (cons.mar27 || 0).toLocaleString('pt-BR');
        document.getElementById('metric-ass-total').innerText = (cons.total_pecas || 0).toLocaleString('pt-BR') + ' un';
        document.getElementById('metric-ass-peso').innerText = (cons.total_peso_kg || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 }) + ' kg';
        document.getElementById('metric-ass-clientes').innerText = (cons.total_clientes_elegiveis || 0).toLocaleString('pt-BR');

        // Atualizar Badges de Contagem dos Grupos
        const grps = dados.grupos || {};
        for (const [gid, g] of Object.entries(grps)) {
            const b = document.getElementById(`badge-${gid}`);
            if (b) {
                b.innerText = g.total_clientes || 0;
            }
        }

        const tsSync = document.getElementById('ass-ultima-sync');
        if (tsSync) tsSync.innerText = dados.ultima_atualizacao || new Date().toLocaleTimeString();

        if (badgeSync) {
            badgeSync.innerHTML = '<i class="fa-solid fa-file-excel" style="color: #10b981;"></i> Google Sheets Conectado | Atualizado: <strong>' + (dados.ultima_atualizacao || 'Agora') + '</strong>';
        }

        selecionarGrupoAssinaturas(window.grupoAtivoAssinaturas || 'paroquias_ce');

    } catch (e) {
        console.error('[ASSINATURAS] Erro ao carregar dados:', e);
        if (badgeSync) {
            badgeSync.innerHTML = '<i class="fa-solid fa-triangle-exclamation" style="color: #ef4444;"></i> Erro ao carregar: ' + e.message;
        }
        alert('Erro ao carregar assinaturas: ' + e.message);
    } finally {
        if (btnSync) {
            btnSync.disabled = false;
            btnSync.innerHTML = '<i class="fa-solid fa-rotate"></i> Sincronizar Google Sheets ao Vivo 🔄';
        }
    }
}

async function sincronizarAssinaturasGoogleSheets() {
    await carregarAssinaturasPDV(true);
}

function selecionarGrupoAssinaturas(grupoId) {
    window.grupoAtivoAssinaturas = grupoId;

    // Atualizar Abas Visuais
    document.querySelectorAll('.tab-grupo-btn').forEach(btn => {
        if (btn.dataset.grupo === grupoId) {
            btn.classList.add('active');
            btn.style.background = 'rgba(2, 132, 199, 0.25)';
            btn.style.borderColor = '#38bdf8';
            btn.style.color = '#38bdf8';
        } else {
            btn.classList.remove('active');
            btn.style.background = '#1e293b';
            btn.style.borderColor = '#334155';
            btn.style.color = '#94a3b8';
        }
    });

    if (!window.dadosAssinaturas || !window.dadosAssinaturas.grupos) return;
    const grupo = window.dadosAssinaturas.grupos[grupoId];
    if (!grupo) return;

    // Título e Descrição com Frete Fixo de Fortaleza destacado
    let freteInfoBadge = '';
    if (grupo.custo_total_frete) {
        freteInfoBadge = ` | <span style="color:#10b981; font-weight:bold;">Frete Fixo Roberto: R$ ${grupo.custo_total_frete.toFixed(2)} (${grupo.total_clientes} entregas x R$ 4,50)</span>`;
    }
    document.getElementById('grupo-titulo').innerHTML = grupo.titulo + ` <span style="font-size:0.85rem; font-weight:normal; color:#cbd5e1;">(${grupo.total_clientes} clientes | ${grupo.total_pecas} exemplares | ${grupo.total_peso_kg} kg${freteInfoBadge})</span>`;
    document.getElementById('grupo-descricao').innerText = grupo.descricao;

    // Botão de Gerar Baixa (visível somente nos grupos de clientes finais)
    const btnBaixa = document.getElementById('btn-gerar-baixa-grupo');
    if (grupoId.startsWith('finais_')) {
        btnBaixa.style.display = 'inline-flex';
        btnBaixa.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Gerar Baixa no Omie (${grupo.total_pecas} un) 🚀`;
    } else {
        btnBaixa.style.display = 'none';
    }

    // Limpar campo de filtro e renderizar tabela
    const inpFiltro = document.getElementById('input-filtro-assinaturas');
    if (inpFiltro) inpFiltro.value = '';

    renderizarTabelaAssinaturas(grupo.clientes || []);
}

function renderizarTabelaAssinaturas(clientes) {
    const tbody = document.getElementById('tbody-assinaturas-pdv');
    const contagem = document.getElementById('ass-contagem-filtrados');
    if (!tbody) return;

    if (!clientes || clientes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="14" style="text-align: center; color: var(--text-muted); padding: 30px;">Nenhum cliente elegível encontrado para este grupo com o filtro atual.</td></tr>';
        if (contagem) contagem.innerText = 'Exibindo 0 clientes';
        return;
    }

    if (contagem) contagem.innerText = `Exibindo ${clientes.length} cliente${clientes.length > 1 ? 's' : ''}`;

    let html = '';
    clientes.forEach(c => {
        const checkJan = c.jan27 ? `<span style="color:#10b981; font-weight:bold;"><i class="fa-solid fa-check"></i> ${c.qtd_jan27}</span>` : '<span style="color:#64748b;">-</span>';
        const checkFev = c.fev27 ? `<span style="color:#10b981; font-weight:bold;"><i class="fa-solid fa-check"></i> ${c.qtd_fev27}</span>` : '<span style="color:#64748b;">-</span>';
        const checkMar = c.mar27 ? `<span style="color:#10b981; font-weight:bold;"><i class="fa-solid fa-check"></i> ${c.qtd_mar27}</span>` : '<span style="color:#64748b;">-</span>';

        // Ação / Logística
        let acaoCol = '';
        if (c.quantidade_assinaturas >= 20) {
            // Paróquia / Grande volume
            const freteLabel = c.frete_previsto ? `R$ ${c.frete_previsto.toFixed(2)}` : (c.frete_obs || 'A calcular');
            acaoCol = `
                <button class="btn btn-primary" onclick="abrirModalRemessaParoquia(${c.linha_planilha})" style="padding: 4px 10px; font-size: 0.75rem; background: linear-gradient(135deg, #3b82f6, #1d4ed8); border:none;" title="Emitir remessa padrão no Omie para esta paróquia">
                    <i class="fa-solid fa-paper-plane"></i> Emitir Omie
                </button>
                <div style="font-size: 0.7rem; color: #94a3b8; margin-top: 3px;">Frete: ${freteLabel}</div>
            `;
        } else {
            // Cliente Final
            const infoLog = c.entregador ? `🛵 Roberto (R$ ${(c.custo_entrega || 0).toFixed(2)})` : (c.tipo_envio || 'Correios');
            acaoCol = `<span style="font-size: 0.75rem; color: #cbd5e1; background: rgba(255,255,255,0.06); padding: 3px 8px; border-radius: 4px; display: inline-block;">${infoLog}</span>`;
        }

        const badgeRen = c.is_renovacao ? '<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; font-size: 0.65rem; margin-left: 5px;">Renovação</span>' : '';
        const badgeObs = c.observacao_especial ? `<span class="badge" style="background: rgba(234, 179, 8, 0.2); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.4); font-size: 0.65rem; margin-left: 5px;" title="${c.observacao_especial}">⚠️ Enviar 1 und Dez/26 junto</span>` : '';
        const totExemplaresHtml = c.qtd_dez26_extra ? `<span title="3 exemplares de 2027 + 1 de Dezembro/2026">${c.total_exemplares_envio} <small style="color:#facc15; font-size:0.7rem;">(+1 Dez)</small></span>` : c.total_exemplares;

        html += `
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="color:#64748b; font-size:0.75rem;">${c.linha_planilha}</td>
                <td style="font-size:0.75rem; color:#94a3b8;">${c.codigo_cliente || '-'}</td>
                <td>
                    <div style="font-weight: 600; color: #f8fafc;">${c.cliente} ${badgeRen} ${badgeObs}</div>
                    <div style="font-size: 0.72rem; color: #64748b;">Início/Base: ${c.data_registro_base}</div>
                </td>
                <td style="font-size:0.75rem; color:#94a3b8; font-family: monospace;">${c.cpf_cnpj || '-'}</td>
                <td style="font-size:0.8rem; color:#cbd5e1;">${c.rua}, ${c.numero} ${c.complemento ? '(' + c.complemento + ')' : ''} - ${c.bairro}</td>
                <td style="font-size:0.8rem; color:#cbd5e1;">${c.cidade} / <strong>${c.uf}</strong></td>
                <td style="font-size:0.8rem; font-family: monospace; color:#38bdf8;">${c.cep}</td>
                <td style="text-align: center; font-weight: bold; color: #f8fafc;">${c.quantidade_assinaturas}</td>
                <td style="text-align: center;">${checkJan}</td>
                <td style="text-align: center;">${checkFev}</td>
                <td style="text-align: center;">${checkMar}</td>
                <td style="text-align: center; font-weight: 700; color: #10b981;">${totExemplaresHtml}</td>
                <td style="text-align: center; font-size: 0.78rem; color: #94a3b8;">${c.peso_kg.toFixed(2)} kg</td>
                <td style="text-align: center;">${acaoCol}</td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

function filtrarTabelaAssinaturas() {
    if (!window.dadosAssinaturas || !window.dadosAssinaturas.grupos) return;
    const grupo = window.dadosAssinaturas.grupos[window.grupoAtivoAssinaturas];
    if (!grupo) return;

    const termo = (document.getElementById('input-filtro-assinaturas').value || '').trim().toLowerCase();
    if (!termo) {
        renderizarTabelaAssinaturas(grupo.clientes || []);
        return;
    }

    const filtrados = (grupo.clientes || []).filter(c => {
        return (c.cliente && c.cliente.toLowerCase().includes(termo)) ||
               (c.cpf_cnpj && c.cpf_cnpj.toLowerCase().includes(termo)) ||
               (c.cidade && c.cidade.toLowerCase().includes(termo)) ||
               (c.uf && c.uf.toLowerCase().includes(termo)) ||
               (c.cep && c.cep.toLowerCase().includes(termo)) ||
               (c.rua && c.rua.toLowerCase().includes(termo)) ||
               (String(c.codigo_cliente).includes(termo)) ||
               (String(c.linha_planilha).includes(termo));
    });

    renderizarTabelaAssinaturas(filtrados);
}

function exportarEtiquetasGrupoAtivo() {
    const gid = window.grupoAtivoAssinaturas || 'paroquias_ce';
    window.location.href = `/api/assinaturas/exportar_etiquetas?grupo=${gid}`;
}

function baixarPdfRelatorio(grupoId) {
    const gid = grupoId || 'todos';
    window.open(`/api/assinaturas/relatorio_pdf?grupo=${gid}`, '_blank');
}

function baixarPdfRelatorioAtivo() {
    const gid = window.grupoAtivoAssinaturas || 'finais_fortaleza';
    baixarPdfRelatorio(gid);
}

function exportarArquivoCorreios(grupoId, formato) {
    const gid = grupoId || 'todos_correios';
    const fmt = formato || 'csv';
    window.location.href = `/api/assinaturas/exportar_correios?grupo=${gid}&formato=${fmt}`;
}

function exportarArquivoCorreiosAtivo(formato) {
    const gid = window.grupoAtivoAssinaturas || 'finais_modico_brasil';
    exportarArquivoCorreios(gid, formato);
}

// ==========================================
// MODAL BAIXA DE ESTOQUE (CLIENTES FINAIS)
// ==========================================
function abrirModalConfirmarBaixa() {
    const gid = window.grupoAtivoAssinaturas;
    if (!window.dadosAssinaturas || !window.dadosAssinaturas.grupos) return;
    const grupo = window.dadosAssinaturas.grupos[gid];
    if (!grupo) return;

    document.getElementById('modal-baixa-grupo-nome').innerText = grupo.titulo;
    
    const obsMap = {
        'finais_fortaleza': 'Baixa de Liturgias enviadas a clientes finais Fortaleza',
        'finais_modico_brasil': 'Baixa de Liturgias enviadas a clientes finais Brasil - Impresso Módico',
        'finais_pac_norte': 'Baixa de Liturgias enviadas a clientes finais Brasil - PAC Norte'
    };
    document.getElementById('modal-baixa-obs-texto').innerText = 'Observação: "' + (obsMap[gid] || `Baixa de Liturgias enviadas a ${grupo.titulo}`) + '"';

    document.getElementById('modal-baixa-qtd-jan').innerText = (grupo.jan27 || 0) + ' un';
    document.getElementById('modal-baixa-qtd-fev').innerText = (grupo.fev27 || 0) + ' un';
    document.getElementById('modal-baixa-qtd-mar').innerText = (grupo.mar27 || 0) + ' un';
    document.getElementById('modal-baixa-qtd-total').innerText = (grupo.total_pecas || 0) + ' un (' + (grupo.total_peso_kg || 0) + ' kg)';

    const stDiv = document.getElementById('modal-baixa-status');
    stDiv.style.display = 'none';

    const btn = document.getElementById('btn-confirmar-disparo-baixa');
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-check"></i> Confirmar & Transmitir ao Omie';

    document.getElementById('modal-confirmar-baixa-assinaturas').classList.add('active');
}

function fecharModalBaixaAssinaturas() {
    document.getElementById('modal-confirmar-baixa-assinaturas').classList.remove('active');
}

async function executarDisparoBaixaOmie() {
    const gid = window.grupoAtivoAssinaturas;
    const btn = document.getElementById('btn-confirmar-disparo-baixa');
    const stDiv = document.getElementById('modal-baixa-status');

    try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Transmitindo Remessa de Baixa ao Omie ERP...';
        stDiv.style.display = 'block';
        stDiv.style.background = 'rgba(56, 189, 248, 0.15)';
        stDiv.style.color = '#38bdf8';
        stDiv.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Comunicando com a API Omie (IncluirRemessa)...';

        const resp = await fetch('/api/assinaturas/gerar_remessa_baixa', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ grupo_id: gid })
        });
        const res = await resp.json();

        if (res.sucesso) {
            stDiv.style.background = 'rgba(16, 185, 129, 0.2)';
            stDiv.style.color = '#10b981';
            stDiv.innerHTML = `
                <div style="font-weight: bold; font-size: 1rem;"><i class="fa-solid fa-circle-check"></i> Remessa de Baixa nº ${res.numero_remessa} gerada com sucesso!</div>
                <div style="margin-top: 4px; font-size: 0.85rem;">Código Omie: ${res.codigo_remessa} | Total de Peças Baixadas: ${res.total_pecas} un</div>
                <div style="margin-top: 4px; color: #94a3b8; font-size: 0.8rem;">Obs: ${res.observacao}</div>
            `;
            btn.innerHTML = '<i class="fa-solid fa-check-double"></i> Remessa Transmitida com Sucesso!';
        } else {
            throw new Error(res.erro || 'Falha ao incluir remessa no Omie.');
        }
    } catch (e) {
        stDiv.style.background = 'rgba(239, 68, 68, 0.2)';
        stDiv.style.color = '#ef4444';
        stDiv.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <strong>Erro no Omie:</strong> ${e.message}`;
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-rotate-left"></i> Tentar Novamente';
    }
}

// ==========================================
// MODAL REMESSA DE PARÓQUIA INDIVIDUAL
// ==========================================
function abrirModalRemessaParoquia(linhaPlanilha) {
    if (!window.dadosAssinaturas || !window.dadosAssinaturas.grupos) return;
    const gid = window.grupoAtivoAssinaturas;
    const grupo = window.dadosAssinaturas.grupos[gid];
    if (!grupo) return;

    const cliente = (grupo.clientes || []).find(c => c.linha_planilha === linhaPlanilha);
    if (!cliente) return;

    window.paroquiaSelecionadaParaRemessa = cliente;

    document.getElementById('modal-paroquia-nome').innerText = cliente.cliente;
    document.getElementById('modal-paroquia-local').innerText = `${cliente.cidade} / ${cliente.uf} | CEP: ${cliente.cep} | CPF/CNPJ: ${cliente.cpf_cnpj || 'Não inf.'}`;
    document.getElementById('modal-paroquia-cfop').value = cliente.cfop || (cliente.uf === 'CE' ? '5949' : '6949');
    document.getElementById('modal-paroquia-transp').value = cliente.transportadora || 'Roberto Souza de Oliveira';

    const inpFrete = document.getElementById('modal-paroquia-frete');
    inpFrete.value = cliente.frete_previsto ? cliente.frete_previsto.toFixed(2) : '';
    document.getElementById('modal-paroquia-frete-obs').innerText = cliente.frete_obs || 'Frete calculado conforme tabela do Roberto Souza ou a negociar.';

    document.getElementById('modal-paroquia-qtd-jan').innerText = cliente.qtd_jan27 + ' un';
    document.getElementById('modal-paroquia-qtd-fev').innerText = cliente.qtd_fev27 + ' un';
    document.getElementById('modal-paroquia-qtd-mar').innerText = cliente.qtd_mar27 + ' un';

    const stDiv = document.getElementById('modal-paroquia-status');
    stDiv.style.display = 'none';

    const btn = document.getElementById('btn-confirmar-disparo-paroquia');
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Emitir Remessa no Omie';

    document.getElementById('modal-remessa-paroquia').classList.add('active');
}

function fecharModalParoquia() {
    document.getElementById('modal-remessa-paroquia').classList.remove('active');
    window.paroquiaSelecionadaParaRemessa = null;
}

async function executarDisparoParoquiaOmie() {
    const cliente = window.paroquiaSelecionadaParaRemessa;
    if (!cliente) return;

    const btn = document.getElementById('btn-confirmar-disparo-paroquia');
    const stDiv = document.getElementById('modal-paroquia-status');
    const freteVal = document.getElementById('modal-paroquia-frete').value;

    try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Emitindo Remessa no Omie...';
        stDiv.style.display = 'block';
        stDiv.style.background = 'rgba(56, 189, 248, 0.15)';
        stDiv.style.color = '#38bdf8';
        stDiv.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Cadastrando remessa na API Omie...';

        const resp = await fetch('/api/assinaturas/gerar_remessa_paroquia', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cliente: cliente,
                valor_frete: freteVal ? parseFloat(freteVal) : 0
            })
        });
        const res = await resp.json();

        if (res.sucesso) {
            stDiv.style.background = 'rgba(16, 185, 129, 0.2)';
            stDiv.style.color = '#10b981';
            stDiv.innerHTML = `
                <div style="font-weight: bold; font-size: 1rem;"><i class="fa-solid fa-circle-check"></i> Remessa de Paróquia nº ${res.numero_remessa} emitida com sucesso!</div>
                <div style="margin-top: 4px; font-size: 0.85rem;">Código Omie: ${res.codigo_remessa} | Cliente Omie ID: ${res.codigo_cliente_omie}</div>
                <div style="margin-top: 4px; color: #94a3b8; font-size: 0.8rem;">CFOP: ${res.cfop} | Peças: ${res.total_pecas} un | Frete: R$ ${parseFloat(freteVal || 0).toFixed(2)}</div>
            `;
            btn.innerHTML = '<i class="fa-solid fa-check-double"></i> Remessa Emitida!';
        } else {
            throw new Error(res.erro || 'Falha ao incluir remessa no Omie.');
        }
    } catch (e) {
        stDiv.style.background = 'rgba(239, 68, 68, 0.2)';
        stDiv.style.color = '#ef4444';
        stDiv.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <strong>Erro Omie:</strong> ${e.message}`;
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-rotate-left"></i> Tentar Novamente';
    }
}

// Expor funções globalmente
window.carregarAssinaturasPDV = carregarAssinaturasPDV;
window.sincronizarAssinaturasGoogleSheets = sincronizarAssinaturasGoogleSheets;
window.selecionarGrupoAssinaturas = selecionarGrupoAssinaturas;
window.filtrarTabelaAssinaturas = filtrarTabelaAssinaturas;
window.exportarEtiquetasGrupoAtivo = exportarEtiquetasGrupoAtivo;
window.abrirModalConfirmarBaixa = abrirModalConfirmarBaixa;
window.fecharModalBaixaAssinaturas = fecharModalBaixaAssinaturas;
window.executarDisparoBaixaOmie = executarDisparoBaixaOmie;
window.abrirModalRemessaParoquia = abrirModalRemessaParoquia;
window.fecharModalParoquia = fecharModalParoquia;
window.executarDisparoParoquiaOmie = executarDisparoParoquiaOmie;
window.baixarPdfRelatorio = baixarPdfRelatorio;
window.baixarPdfRelatorioAtivo = baixarPdfRelatorioAtivo;
window.exportarArquivoCorreios = exportarArquivoCorreios;
window.exportarArquivoCorreiosAtivo = exportarArquivoCorreiosAtivo;




