(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const state = { data: null, tab: 'conciliados', job: null, search: '' };
  const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  const integer = new Intl.NumberFormat('pt-BR');
  const today = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const isoDate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
  const labels = {
    FRETE_GRATIS: 'Ecommerce: frete grátis', COMERCIAL_SEM_COBRANCA: 'Comercial: sem cobrança de frete',
    REPASSADO_DEFICITARIO: 'Cliente pagou menos que o custo', REPASSADO_COM_SOBRA: 'Cobrança acima do custo', EQUILIBRADO: 'Cobrança igual ao custo',
    COBRANCA_ALOCADA_OUTRO_PERIODO: 'Cobrança contada na primeira postagem de outro período',
    FRETE_COBRADO_PENDENTE: 'Conferir cobrança na NF/pedido', CUSTO_TOTAL_PENDENTE: 'Aguardando custo oficial Total Express',
    CUSTO_PORTAL_PENDENTE: 'Custo Portal Postal não confirmado', REFERENCIA_SEM_VINCULO_OMIE: 'Referência não vinculada ao Omie',
    NF_AMBIGUA: 'Mais de uma NF corresponde à referência', DEPARTAMENTO_PENDENTE: 'Departamento ausente ou misto',
    NAO_E_VENDA_COMUM: 'Fora de venda comum: revisar', OPERACAO_VENDA_PENDENTE: 'Operação de venda não identificada',
    NF_CANCELADA_CONFERIR: 'NF cancelada: conferir cobrança', DEVOLUCAO_CONFERIR_FINANCEIRO: 'Devolução: revisar financeiro',
    DATA_POSTAGEM_A_CONFERIR: 'Data de postagem pendente', CANCELAMENTO_CONFERIR_COBRANCA: 'Postagem cancelada: conferir custo',
    LITURGIA_REFERENCIA_001_REGRA_USUARIO: 'Liturgia: referência -001 (regra informada)',
    LITURGIA_REFERENCIA_MESES: 'Liturgia: referência aos meses', LITURGIA_CONTEUDO_SEM_NF_NUMERICA: 'Liturgia no conteúdo sem NF numérica'
  };
  $('date-start').value = isoDate(monthStart);
  $('date-end').value = isoDate(today);
  $('date-start').max = isoDate(today);
  $('date-end').max = isoDate(today);

  function showNotice(message, error = false) {
    const el = $('notice');
    el.textContent = message || '';
    el.hidden = !message;
    el.classList.toggle('error', error);
  }
  function apiError(payload, fallback) {
    return payload && (payload.erro || payload.error || payload.mensagem) || fallback;
  }
  async function jsonResponse(response) {
    if (!String(response.headers.get('Content-Type') || '').includes('application/json')) {
      throw new Error('O backend principal precisa carregar as novas rotas. O painel isolado está em http://127.0.0.1:8898/.');
    }
    return response.json();
  }
  function asMoney(value, dash = true) {
    if (value === null || value === undefined || value === '') return dash ? '—' : money.format(0);
    const n = Number(value);
    return Number.isFinite(n) ? money.format(n) : '—';
  }
  function asNumber(value) {
    if (value === null || value === undefined || value === '') return '—';
    const n = Number(value);
    return Number.isFinite(n) ? integer.format(n) : '—';
  }
  function asDate(value) {
    if (!value) return '—';
    const d = new Date(`${String(value).slice(0, 10)}T00:00:00`);
    return Number.isNaN(d.getTime()) ? String(value) : new Intl.DateTimeFormat('pt-BR').format(d);
  }
  function queryParams() {
    const params = new URLSearchParams({ inicio: $('date-start').value, fim: $('date-end').value });
    if ($('department').value) params.set('departamento', $('department').value);
    if ($('carrier').value) params.set('transportadora', $('carrier').value);
    return params;
  }
  async function loadData() {
    showNotice('Carregando dados conciliados…');
    try {
      const response = await fetch(`/api/frete_financeiro/painel?${queryParams()}`, { headers: { Accept: 'application/json' } });
      const data = await jsonResponse(response);
      if (!response.ok) throw new Error(apiError(data, `Falha ao carregar dados (${response.status}).`));
      state.data = data;
      render();
      showNotice('');
    } catch (error) {
      showNotice(error.message || 'Não foi possível carregar os dados.', true);
    }
  }
  function filteredRows() {
    if (!state.data) return [];
    const key = state.search.trim().toLocaleLowerCase('pt-BR');
    const source = Array.isArray(state.data[state.tab]) ? state.data[state.tab] : [];
    if (!key) return source;
    return source.filter((row) => [row.nf, row.pedido, row.cliente, row.objeto, row.referencia]
      .some((value) => String(value ?? '').toLocaleLowerCase('pt-BR').includes(key)));
  }
  function cell(row, value, className = '') {
    const td = document.createElement('td');
    if (className) td.className = className;
    td.textContent = value === null || value === undefined || value === '' ? '—' : String(value);
    return td;
  }
  function buildTable() {
    const configs = {
      conciliados: { title: 'Conciliados', cols: [['NF / série','nf'],['Pedido','pedido'],['Cliente','cliente'],['Data','data'],['Transportadora','transportadora'],['Objetos','objetos'],['Departamento','departamento'],['Custo registrado','custo','money'],['Cobrança','cobranca','money'],['Origem cobrança','fonte_cobranca'],['Saldo','saldo','money'],['Situação / alerta','situacao']] },
      pendentes: { title: 'Pendentes / sem NF', cols: [['Objeto','objeto'],['Referência','referencia'],['Data','data'],['Transportadora','transportadora'],['Cliente','cliente'],['Custo conhecido','custo','money'],['Departamento','departamento'],['Status','status']] },
      excluidos: { title: 'Excluídos (Liturgias)', cols: [['Objeto','objeto'],['Referência','referencia'],['Data','data'],['Transportadora','transportadora'],['Cliente','cliente'],['Custo','custo','money'],['Motivo','motivo']] }
    };
    const config = configs[state.tab];
    $('table-title').textContent = config.title;
    $('table-summary').textContent = `${integer.format(filteredRows().length)} registros exibidos`;
    const head = $('table-head'); head.replaceChildren();
    const tr = document.createElement('tr');
    config.cols.forEach(([label]) => { const th = document.createElement('th'); th.textContent = label; tr.append(th); });
    head.append(tr);
    const body = $('table-body'); body.replaceChildren();
    filteredRows().forEach((row) => {
      const line = document.createElement('tr');
       config.cols.forEach(([, key, type]) => {
         let value = row[key];
         if (state.tab === 'pendentes') {
           if (key === 'objeto' && !value) value = (row.objetos || []).join(', ');
           if (key === 'referencia' && !value) value = row.nf;
           if (key === 'status' && !value) value = row.situacao;
           if (key === 'custo' && value == null) value = row.custo_conhecido_parcial;
         }
        let cls = '';
        if (type === 'money') { value = asMoney(value); cls = 'number'; }
         else if (key === 'data') value = asDate(value);
        else if (key === 'nf' && value) value = `${value}${row.serie ? ` / ${row.serie}` : ''}`;
        else if (key === 'objetos' && Array.isArray(value)) value = value.join(', ');
         else if (key === 'situacao') value = [labels[row.situacao] || row.situacao, row.alerta].filter(Boolean).join(' · ') || '—';
         else if (key === 'status' || key === 'motivo') value = labels[value] || value;
        line.append(cell(row, value, cls));
      });
      body.append(line);
    });
    $('empty-state').hidden = filteredRows().length !== 0;
  }
  function renderIndicators() {
    const data = state.data;
    const ind = data?.indicadores || {};
    const notes = Number(ind.notas_conciliadas || 0);
    $('metric-notes').textContent = asNumber(ind.notas_conciliadas);
    $('metric-objects').textContent = asNumber(ind.objetos);
    $('metric-cost').textContent = notes === 0 ? '—' : asMoney(ind.custo);
    $('metric-charge').textContent = notes === 0 ? '—' : asMoney(ind.cobranca);
    $('metric-balance').textContent = notes === 0 ? '—' : asMoney(ind.saldo);
    $('free-shipping').textContent = notes === 0 ? '—' : asMoney(ind.frete_gratis_ecommerce);
    $('no-charge').textContent = notes === 0 ? '—' : asMoney(ind.comercial_sem_cobranca);
    $('deficit').textContent = notes === 0 ? '—' : asMoney(ind.deficit_repasses);
    $('recovery').textContent = ind.recuperacao_percentual == null ? '—' : `${new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 2}).format(Number(ind.recuperacao_percentual))}%`;
    $('pending-cost').textContent = asMoney(data?.custo_conhecido_pendentes);
    for (const tab of ['conciliados', 'pendentes', 'excluidos']) $( `count-${tab}`).textContent = integer.format(Array.isArray(data?.[tab]) ? data[tab].length : 0);
    const sync = data?.ultima_atualizacao;
    $('updated-at').textContent = `Última atualização: ${sync?.finalizado_em ? asDate(sync.finalizado_em) : 'não informada'}`;
    $('refresh-status').textContent = sync?.status ? `Fonte: ${sync.status}${sync.aviso ? ` · ${sync.aviso}` : ''}` : '';
    const warning = $('source-warning');
    const rules = Array.isArray(data?.regras) ? data.regras : [];
    const totalExpress = (data?.conciliados || []).some((r) => String(r.transportadora || '').toUpperCase().includes('TOTAL EXPRESS')) || $('carrier').value === 'TOTAL EXPRESS';
    const messages = [...rules];
    if (totalExpress) messages.unshift('Total Express: não há fonte de custo faturado; cotações não são consideradas custo pago.');
    warning.textContent = messages.join(' ');
    warning.hidden = messages.length === 0;
  }
  function renderComparison() {
    const departments = state.data?.por_departamento || {};
    const entries = Object.entries(departments).filter(([name]) => !$('department').value || $('department').value === name);
    const container = $('department-bars'); container.replaceChildren();
    const usable = entries.filter(([, v]) => Number(v?.notas_conciliadas || 0) > 0);
    $('comparison').hidden = usable.length === 0;
    if (!usable.length) return;
    const max = Math.max(1, ...usable.flatMap(([, v]) => [Number(v.cobranca || 0), Number(v.custo || 0)]));
    usable.forEach(([name, values]) => {
      const row = document.createElement('div'); row.className = 'dept-row';
      const label = document.createElement('div'); label.className = 'dept-label'; label.textContent = name;
      const group = document.createElement('div'); group.className = 'bar-pair';
      for (const [key, cls] of [['cobranca','charge'], ['custo','cost']]) {
        const track = document.createElement('div'); track.className = 'bar-track';
        const bar = document.createElement('div'); bar.className = `bar ${cls}`;
        bar.style.width = `${Math.max(0, Number(values[key] || 0) / max * 100)}%`;
        bar.setAttribute('aria-label', `${key === 'custo' ? 'Custo registrado' : 'Cobrança'}: ${asMoney(values[key])}`);
        track.append(bar); group.append(track);
      }
      const vals = document.createElement('div'); vals.className = 'bar-values';
      vals.textContent = `Cobrança ${asMoney(values.cobranca)} · Custo ${asMoney(values.custo)}`;
      group.append(vals); row.append(label, group); container.append(row);
    });
  }
  function render() { renderIndicators(); renderComparison(); buildTable(); }
  function validateDates() {
    const start = new Date(`${$('date-start').value}T00:00:00`);
    const end = new Date(`${$('date-end').value}T00:00:00`);
    const now = new Date(`${isoDate(today)}T00:00:00`);
    if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || start > end || end > now || (end - start) / 86400000 > 30) {
      showNotice('Informe datas válidas, sem futuro e com intervalo máximo de 31 dias.', true);
      return false;
    }
    return true;
  }
  function exportCsv() {
    const columns = {
      conciliados: [['NF','nf'],['Série','serie'],['Pedido','pedido'],['Cliente','cliente'],['Data','data'],['Transportadora','transportadora'],['Objetos','objetos'],['Departamento','departamento'],['Custo','custo'],['Cobrança','cobranca'],['Origem cobrança','fonte_cobranca'],['Origem custo','fonte_custo'],['Saldo','saldo'],['Situação','situacao'],['Alerta','alerta']],
      pendentes: [['Objeto','objeto'],['Referência','referencia'],['Data','data'],['Transportadora','transportadora'],['Cliente','cliente'],['Custo','custo'],['Departamento','departamento'],['Status','status']],
      excluidos: [['Objeto','objeto'],['Referência','referencia'],['Data','data'],['Transportadora','transportadora'],['Cliente','cliente'],['Custo','custo'],['Motivo','motivo']]
    }[state.tab];
    const quote = (value) => {
      let text = value == null ? '' : Array.isArray(value) ? value.join(', ') : String(value);
      if (/^[\s\u0000-\u001f]*[=+@\-]/.test(text) && !/^-?\d+(?:[.,]\d+)?$/.test(text)) text = `'${text}`;
      return `"${text.replace(/"/g, '""')}"`;
    };
    const lines = [columns.map(([name]) => quote(name)).join(';')];
    filteredRows().forEach((row) => lines.push(columns.map(([, key]) => {
      let value = row[key];
      if (state.tab === 'pendentes') {
        if (key === 'objeto' && !value) value = (row.objetos || []).join(', ');
        if (key === 'referencia' && !value) value = row.nf;
        if (key === 'status' && !value) value = row.situacao;
        if (key === 'custo' && value == null) value = row.custo_conhecido_parcial;
      }
      return quote(key === 'data' ? asDate(value) : value);
    }).join(';')));
    const blob = new Blob([`\uFEFF${lines.join('\r\n')}`], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `frete-financeiro-${state.tab}-${$('date-start').value}-${$('date-end').value}.csv`; link.click(); URL.revokeObjectURL(link.href);
  }
  async function synchronize() {
    if (state.job || !validateDates()) return;
    const button = $('sync-button'); button.disabled = true;
    showNotice('Solicitando atualização das fontes…');
    try {
      const response = await fetch('/api/frete_financeiro/sincronizar', { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ inicio: $('date-start').value, fim: $('date-end').value }) });
      const job = await jsonResponse(response);
      if (response.status !== 202 || !job.id) throw new Error(apiError(job, `Não foi possível iniciar a leitura (${response.status}).`));
      state.job = job.id;
      await pollJob();
    } catch (error) {
      state.job = null; showNotice(error.message || 'Falha ao atualizar as fontes.', true);
    } finally { button.disabled = false; }
  }
  async function pollJob() {
    while (state.job) {
      let response, job;
      try {
        response = await fetch(`/api/frete_financeiro/job/${encodeURIComponent(state.job)}`, { headers: { Accept: 'application/json' } });
        job = await jsonResponse(response);
        if (!response.ok) throw new Error(apiError(job, `Falha ao consultar atualização (${response.status}).`));
      } catch (error) { state.job = null; showNotice(error.message || 'Falha ao consultar atualização.', true); return; }
      const calls = job.chamadas_externas == null ? '' : ` · ${job.chamadas_externas}/25 chamadas`;
      $('refresh-status').textContent = `${job.etapa || job.status}${calls}`;
      if (job.status === 'running') {
        showNotice(`Atualização em andamento: ${job.etapa || 'processando'}${calls}`);
        await new Promise((resolve) => setTimeout(resolve, 1500));
        continue;
      }
      const status = job.status;
      state.job = null;
      await loadData();
      if (status === 'partial') showNotice(`${job.aviso || 'Atualização parcial. Os dados preservados foram carregados.'} Você pode clicar em “Atualizar fontes (leitura)” para continuar.`);
      else if (status === 'failed') showNotice(job.aviso || 'A atualização falhou; os dados disponíveis foram preservados.', true);
      else if (job.aviso) showNotice(job.aviso);
      else showNotice(status === 'complete' ? 'Atualização concluída.' : 'Atualização finalizada.');
    }
  }
  $('apply-filters').addEventListener('click', () => { if (validateDates()) loadData(); });
  $('sync-button').addEventListener('click', synchronize);
  $('search').addEventListener('input', (event) => { state.search = event.target.value; if (state.data) buildTable(); });
  $('export-csv').addEventListener('click', exportCsv);
  document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((item) => item.classList.toggle('active', item === tab));
    state.tab = tab.dataset.tab; buildTable();
  }));
  loadData();
})();
