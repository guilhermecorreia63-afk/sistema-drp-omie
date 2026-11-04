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
│   ├── jt_express_service.py  # Serviço de despacho e cotação J&T Express
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
