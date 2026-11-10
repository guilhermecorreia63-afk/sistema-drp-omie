# Projeto Omie: Expedição, Faturamento e Logística

Aplicação web local para operações integradas ao Omie ERP e ao banco Turso, incluindo expedição, geração/impressão de etiquetas, listas de postagem, romaneios locais e controle operacional de DRP.

---

## 🚀 Executar Localmente

Na raiz do projeto, inicie o backend e servidor estático:

```powershell
python server.py 8889
```

Acesse no navegador: `http://localhost:8889`.  
*Ambiente 100% local. Não é necessário nem autorizado fazer deploy para testar alterações locais.*

---

## 📂 Arquitetura & Estrutura de Diretórios

A estrutura do projeto foi padronizada e organizada para evitar acúmulo de arquivos soltos na raiz e separar claramente código em produção, serviços, dados, scripts e relatórios:

```text
Projeto omie/
├── api/                       # Handlers e pontos de entrada serverless (Vercel / Netlify)
│   ├── cron_sync.py           # Rotina cron de sincronização periódica
│   └── index.py               # Gateway central de requisições /api/*
│
├── services/                  # Módulos de domínio, regras de negócio e integrações
│   ├── omie_client.py         # Cliente de API e chamadas RPC do Omie ERP
│   ├── correios_hub_service.py# Hub logístico: expedições, pré-postagens, listas/PLP, SRO
│   ├── frenet_service.py      # Integração de cotação de fretes via Frenet API
│   ├── jt_express_service.py  # Criação/cancelamento/rastreio J&T; cotação vem da Frenet
│   ├── total_express_service.py # Serviço e banco local da Total Express
│   ├── portal_postal_service.py # Integração com AGF / Portal Postal
│   ├── assinaturas_*.py       # Regras e gestão de ciclos de assinantes
│   ├── consignacao_service.py # Gestão de notas e estoque consignado
│   └── estoque.py, vendas.py  # Módulos de consulta e sincronização Omie
│
├── data/                      # Dados persistentes de runtime e bancos de dados ativos
│   ├── database_local.db      # Banco SQLite local do DRP e cache operacional
│   ├── total_express_local.db # Banco local homologado de etiquetas Total Express
│   ├── produtos_turso.json    # Catálogo canônico sincronizado com Turso DB / Omie
│   └── *.json                 # Mapeamentos (depara, blacklist, lotes mínimos)
│
├── reports/                   # Relatórios executivos, planilhas geradas e exports
│   ├── *.xlsx / *.csv         # Balanços consignados, auditorias e listas de assinantes
│   └── *.pdf                  # Relatórios TOC, rankings de vendas e conferências
│
├── scripts/                   # Scripts auxiliares, automações e ferramentas CLI
│   └── maintenance/           # Scripts de manutenção, ranking e ajuste de estoque
│
├── scratch/                   # Scripts temporários de análise pontual e investigações
│
├── archive/                   # Arquivos históricos, patches aplicados e backups
│   ├── patches/               # Scripts patch_*.py que já foram executados e aplicados
│   ├── samples/               # Amostras estáticas de payloads JSON de APIs
│   ├── empty_dbs/             # Caches de SQLite vazios antigos retirados da raiz
│   └── legacy_docs/           # Documentações e READMEs antigos arquivados
│
├── index.html                 # Interface SPA central (10 módulos operacionais)
├── styles.css                 # Folha de estilos central e design responsivo
├── app.js                     # Controlador da interface principal e navegação do Hub
├── correios_module.js         # Controlador do Módulo 5 (Expedição, PLP, Rótulos, Motorista)
├── server.py                  # Servidor HTTP local (Bridge de APIs, Netlify Functions e DRP)
├── database.py                # Conexão com Turso DB (libSQL HTTP pipeline) e fallback local
├── sync_service.py            # Sincronizador de catálogo de produtos e estoques
├── controle_drp.py            # Regras de cálculo de DRP e parâmetros de reposição
├── inteligencia_matriz.py     # Análise de giro, curvas ABC e demandas da Matriz
└── alertas_email.py           # Disparador de notificações de ruptura de estoque
```

---

## 📌 Guia de Organização: Onde colocar novos arquivos

Para manter o projeto limpo, seguro e sustentável, siga rigorosamente as diretrizes abaixo:

1. **Novos Serviços e Integrações Externas**:
   - Devem sempre ser criados dentro de `services/` (ex: `services/minha_transportadora.py`).
   - Evite criar arquivos de serviço soltos na raiz.

2. **Novos Scripts de Manutenção e Tarefas Pontuais**:
   - Scripts recorrentes ou operacionais: coloque em `scripts/maintenance/`.
   - Scripts pontuais de depuração rápida: coloque em `scratch/`.
   - **Nunca** deixe scripts com prefixo `patch_*.py` na raiz após aplicar uma correção. Mova-os para `archive/patches/` ou descarte-os.

3. **Planilhas, PDFs e Exportações**:
   - Devem ser gerados e salvos dentro de `reports/` (ou `exportacoes_correios_pdv/` se for específico de expedição balcão).
   - Não salve arquivos `.xlsx`, `.csv` ou `.pdf` de conferência soltos na raiz.

4. **Bancos de Dados e Caches**:
   - Ficam centralizados dentro de `data/`.
   - Não crie novos bancos `.db` diretamente na raiz.

5. **Dados de Catálogo (`produtos_turso.json`)**:
   - O arquivo oficial em produção e runtime é **`data/produtos_turso.json`**.
   - A raiz não deve conter cópias duplicadas desse JSON para evitar inconsistência de estoque.

---

## 🔒 Segurança e Credenciais

- **Nunca versionar ou expor valores de credenciais**: O arquivo `.env` deve permanecer exclusivamente no ambiente local e nunca ser compartilhado.
- Em documentações ou prompts, cite apenas os nomes das variáveis (ex: `OMIE_APP_KEY`, `TURSO_DATABASE_URL`).
- Não realize operações de `git push`, `git commit` ou deploy em produção sem solicitação expressa do usuário.

---

## 🤝 Trabalho Colaborativo entre Agentes (Codex / Kilo e Antigravity)

1. Ambos os assistentes operam diretamente nesta mesma árvore de diretórios.
2. Antes de iniciar qualquer alteração, confira a existência e o conteúdo real dos arquivos no disco.
3. Respeite as pastas `services/`, `data/`, `reports/` e `scripts/maintenance/` para que o repositório permaneça organizado e profissional.

## Estado verificado da J&T (09/11/2026)

- O serviço implementa `order/addOrder`, `order/cancelOrder` e `logistics/trace`. Em 10/11/2026 foi adicionada a consulta `order/getOrders`, com `serialNumber[]` e `command=1`, conforme a captura fornecida pelo usuário.
- A rota local de consulta é `/.netlify/functions/jt-express?action=trace`, com `billCode`. Usar sempre a ação explícita: a ação padrão da rota é criação de pedido.
- O ambiente configurado foi verificado como homologação. Presença de variáveis não comprova autenticação aceita pela API. Não imprimir valores de configuração nem assinaturas de requisições reais.
- A consulta SELECT encontrou zero pré-postagens ativas J&T na tabela `prepostagens`; faltou um código real para testar o rastreamento externo.
- A seleção J&T na emissão da interface ainda não estava ligada ao serviço específico. Foi adicionada proteção para não despachar esse pedido indevidamente pela rota Correios. Não habilitar a emissão antes de concluir persistência, etiqueta, duplicidade e validações específicas.
- O serviço não implementa consulta de frete faturado. Os valores J&T do levantamento das Liturgias são cotações Frenet, não comprovantes de pagamento.
- Auditoria read-only: `python scripts/maintenance/auditar_jt_consultas.py`. A opção `--cotar-amostra-frenet` consulta uma cotação atual. `--bill-code` permite consultar um rastreio existente, sem criar pedido.
- Testes offline: `python -m unittest discover -s scripts/maintenance -p test_jt_consultas.py -v`.
- Diagnóstico local em `reports/jt_diagnostico/consultas_somente_leitura.json`; não publicar relatórios com informações operacionais sem revisão.
- Teste real de 10/11/2026: `order/getOrders` no ambiente de homologação respondeu HTTP 200, código `1`, mas `data: []` para o identificador de exemplo. Consulta aceita não significa pedido localizado nem emissão/rastreio homologados.
- Rota de consulta de pedido: `/.netlify/functions/jt-express?action=getOrders`. O script `scripts/maintenance/testar_jt_homologacao.py --serial-number IDENTIFICADOR` recusa produção, não cria/cancela pedidos e só tenta rastrear códigos de envio retornados pela consulta ou fornecidos explicitamente. Com `--reusar-consulta`, usa apenas o relatório local anterior.
- Relatório desta tentativa: `reports/jt_diagnostico/RELATORIO_HOMOLOGACAO.md` e `homologacao_pedido_rastreio.json`, com dados sensíveis removidos.
- Rastreio isolado de homologação: `python scripts/maintenance/testar_jt_homologacao.py --bill-code CODIGO`, sem precisar consultar pedido. A opção pode ser repetida até três vezes. Os três códigos da captura `/mock/logistics/trace` foram consultados em 10/11/2026 e retornaram `billcodes not exist`; resultado salvo em `reports/jt_diagnostico/homologacao_rastreios.json`, sem inventar eventos do mock.
- PDFs analisados em 10/11/2026 confirmam cotação direta `spmComCost/getComCostAndTime`. O método `cotar_frete()` e a ação local `jt-express?action=quote` preservam preço base, risco e total sem dupla contagem. No demo a consulta retornou custo/prazo zero; isso não foi considerado frete grátis ou preço comercial validado.
- Houve uma tentativa explicitamente autorizada de criar pedido no demo: código `145003050`, `Illegal parameters`, sem código de envio. Produção não foi chamada. `scripts/maintenance/executar_ciclo_jt_demo.py` mantém checkpoint para não repetir criação após recusa/timeout; `--somente-relatorio` não chama APIs. Não apagar o checkpoint para forçar outra criação sem revisar o retorno e a documentação completa.
- Resultado e rascunho de e-mail em `reports/jt_diagnostico/ciclo_criacao_cotacao_demo.json` e `EMAIL_SUPORTE_JT.md`; não enviados automaticamente.
- Atualização após receber o JSON completo do suporte: `criar_pedido_estruturado()` inclui `translate`, dados completos das partes e campos fiscais no nível raiz. Uma nova tentativa demo gerou `billCode=U88030069389077`; consulta e rastreio retornaram HTTP 200/código `1`, com `details=[]` (sem eventos). A autenticação dessas chamadas foi conferida sem registrar valores e aceita pelo demo; isso não homologa produção, etiqueta ou faturamento.
- `scripts/maintenance/testar_jt_estrutura_completa.py --somente-relatorio` mostra o resultado salvo sem rede. O checkpoint da tentativa completa é separado do teste incompleto anterior. Não repetir criação nem apagar checkpoints; emissão completa na interface ainda está bloqueada até finalizar o fluxo específico. Relatório: `reports/jt_diagnostico/estrutura_completa_autenticacao.json`; o rascunho de e-mail agora pede simulação de eventos e confirmação da cotação, pois a estrutura completa já foi aceita.
- Smart Label validada digitalmente em 10/11/2026: `order/printOrder`, `printSize=0`, HTTP 200/código `1`, PDF oficial de uma página 76 × 130 mm para o envio demo já criado. Visualização em `http://localhost:8889/reports/jt_diagnostico/etiqueta_demo.html`; arquivo e metadados em `reports/jt_diagnostico/`. Nenhuma impressão física foi executada pelo agente. Não usar esse PDF de homologação em mercadoria real.
- `scripts/maintenance/obter_etiqueta_jt_demo.py` busca a etiqueta ou usa cache, sem criar/cancelar pedidos e com produção bloqueada. A rota `jt-express?action=printOrder` e o getter da interface agora usam o PDF oficial para itens J&T existentes; não substituem por rótulo Correios se houver erro. A fila operacional não foi alimentada com o teste; emissão completa continua pendente. Webhooks serão estudados em etapa posterior.
