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

// Configurar Listeners de Eventos
function setupEventListeners() {
    // Tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            const tabId = tab.dataset.tab;
            tab.classList.add('active');
            document.getElementById(tabId).classList.add('active');
            
            // Atualizar títulos
            if (tabId === 'tab-cd-sp') {
                document.getElementById('page-heading').innerText = '🚚 Reposição de Estoque CD_SP';
                document.getElementById('page-subheading').innerHTML = 'Vendas <strong>Sul e Sudeste</strong> | Estoque Alvo: (Demanda × (Dias + LeadTime)) + 20% Seg.';
            } else if (tabId === 'tab-matriz') {
                document.getElementById('page-heading').innerText = '🏭 Estoque & Ordem de Produção Matriz';
                document.getElementById('page-subheading').innerHTML = 'Vendas <strong>Brasil Inteiro (Geral)</strong> | Estoque Alvo: (Demanda × (Dias + LeadTime)) + 20% Seg.';
            } else if (tabId === 'tab-remessas') {
                document.getElementById('page-heading').innerText = '📦 Gestão de Remessas & Trânsito CD_SP';
                document.getElementById('page-subheading').innerHTML = 'Acompanhamento de Remessas de Transferência (Matriz → CD_SP) no <strong>Omie ERP</strong>';
                carregarRemessasOmie();
            } else if (tabId === 'tab-analise-matriz') {
                document.getElementById('page-heading').innerText = '📊 Aba 4 — Análise de Produtos da Matriz (Matriz BCG)';
                document.getElementById('page-subheading').innerHTML = 'Classificação em <strong>Estrela, Vaca Leiteira, Interrogação e Abacaxi</strong> com base em volume e crescimento';
                renderizarAbaAnaliseMatriz();
            } else if (tabId === 'tab-depositos-matriz') {
                document.getElementById('page-heading').innerText = '🏬 Aba 5 — Depósitos da Matriz (Sub-locais)';
                document.getElementById('page-subheading').innerHTML = 'Gestão de sub-locais (Fracionado, Depósito 1, Depósito 2) e saldo <strong>A localizar</strong>';
                carregarEDesenharDepositosMatriz();
            } else if (tabId === 'tab-combos-kit') {
                document.getElementById('page-heading').innerText = '📦 Aba 6 — Gestão de Combos & Kits Omie';
                document.getElementById('page-subheading').innerHTML = 'Monitoramento de componentes e automação de redefinição de valor de venda do <strong>Kit Assinatura Pão da Vida (SKU 000223)</strong>';
                carregarDetalhesCombo();
            }
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
    addListener('btn-requisicao-compra-matriz-footer', 'click', () => abrirModalRequisicaoCompra());

    // Modais
    addListener('btn-leadtime-modal', 'click', abrirModalLeadTime);
    addListener('btn-close-leadtime', 'click', fecharModalLeadTime);
    addListener('btn-save-leadtime', 'click', salvarLeadTimes);

    addListener('btn-blacklist-modal', 'click', abrirModalBlacklist);
    addListener('btn-close-blacklist', 'click', fecharModalBlacklist);
    addListener('btn-cancel-blacklist', 'click', fecharModalBlacklist);
    addListener('btn-export-blacklist-txt', 'click', exportarBlacklistTXT);

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

        const resp = await fetch('data/produtos_turso.json?_t=' + Date.now());
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

        // Regra 1: Produtos SEM movimentação no período NÃO entram na reposição (somente entram se tiverem estoque > 0 ou forem destaque)
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
    const elCD = document.getElementById('count-selected-blacklist');
    if (elCD) elCD.innerText = state.skusChecadosCD.size;
    const elMat = document.getElementById('count-selected-blacklist-matriz');
    if (elMat) elMat.innerText = state.skusChecadosMatriz.size;
    
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
                    body: JSON.stringify({ remessa_id: remessaId, status_transito: novoSt })
                });
                const resData = await resp.json();
                if (resData.success) {
                    statusMap[remessaId] = novoSt;
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
                    fetch('/api/remessas/salvar_status_transito', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ remessa_id: String(c.cNumeroRemessa || c.nCodRem), status_transito: remessaObj.status_transito || 'PENDENTE', itens: itens })
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
            if (confirm(`Tem certeza que deseja remover TODOS os produtos do Pedido #${numPedido} da Produção?`)) {
                for (const p of itensPedido) {
                    state.producao.delete(p.sku);
                    p.em_producao = false;
                    delete p.numero_pedido;
                    delete p.fornecedor;
                    delete p.data_previsao;
                    try {
                        await fetch('/api/producao/salvar', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ sku: p.sku, em_producao: false, quantidade_producao: 0, data_previsao: '', numero_pedido: '', fornecedor: '' })
                        });
                    } catch (errServ) {}
                }
                modal.classList.remove('active');
                render();
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
    } else {
        produtosCompra = state.produtos.filter(p => {
            if (p.ativo === false || state.blacklist.has(p.sku)) return false;
            const fam = (p.familia || 'GERAL').toUpperCase();
            if (state.familiasExcluidas.has(fam)) return false;

            const vendas = p[`vendas_geral_${state.periodoDias}d`] || 0;
            const lt = getLeadTimeFamilia(p.familia, 'matriz');
            const estAlvo = calcularEstoqueAlvo(vendas, state.periodoDias, state.abastecimentoDias, lt);
            const nec = Math.max(0, Math.ceil(estAlvo - p.matriz));

            if (state.skusChecadosMatriz.has(p.sku)) return true;
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

