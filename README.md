# Integracao Omie ERP v1 - Estrutura Completa
> **ATENCAO:** Nenhuma chave real esta exposta neste repositorio. Consulte instrument.md para diretrizes de seguranca.

## Estrutura
- `.env.example` - Modelo de variaveis de ambiente
- `requirements.txt` - Dependencias (inclui netlify-cli para testes locais)
- `omie_client.py` - Cliente HTTP Omie (multi-empresa, rate limit, retry)
- `database.py` - Turso LibSQL HTTP Pipeline v2 + SQLite fallback
- `services/` - Clientes, Produtos, Vendas, Estoque, Remessas
- `app.py` - Painel Streamlit com tab DRP (Reposicao CD_SP / Matriz)
- `controle_drp.py` - Calculo de estoque minimo, frete, remessa e PDF
- `instrument.md` - Documento central de arquitetura e seguranca

## Executar
streamlit run app.py

