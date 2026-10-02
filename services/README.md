# Integracao Omie ERP v1 - Estrutura Completa

> **ATENCAO:** Este projeto inclui credenciais sensiveis. NUNCA exponha chaves em chats de IA e NUNCA suba arquivos sensiveis no GitHub.

## Documentacao Central

Consulte o arquivo `instrument.md` para diretrizes completas de arquitetura, seguranca, idioma (PT-BR) e uso do Netlify para testes locais antes do deploy.

## Estrutura

- `.env.example` — Modelo de variaveis (sem credenciais reais)
- `requirements.txt` — Dependencias (inclui `netlify-cli` para testes locais)
- `omie_client.py` — Cliente HTTP com rate limit (240 req/min), retry e multi-empresa
- `database.py` — Turso HTTP Pipeline v2 + SQLite fallback
- `services/` — Modulos de clientes, produtos, vendas, estoque e remessas
- `app.py` — Painel Streamlit com tabs, filtros, cards e leitor XML

## Executar Localmente

```bash
# Com Streamlit (recomendado para testes)
streamlit run app.py

# Com Netlify CLI (para testar antes do deploy)
npm install -g netlify-cli
netlify dev
```

## Seguranca

- `.gitignore` protege `.env`, `secrets.toml`, `*.db`
- Nenhuma chave real esta presente nos arquivos deste repositorio
- Todo codigo, docstrings e comentarios estao rigorosamente em PT-BR

## Antigravity / Leitura

Este projeto foi construído obedecendo as diretrizes do Antigravity: todo codigo, documentacao e resposta devem estar em Portugues do Brasil (PT-BR) para leitura correta.

