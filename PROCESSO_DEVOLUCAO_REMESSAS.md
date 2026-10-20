# Guia Oficial: Processo de Devolução de Remessa de Consignado (Omie ERP)

Este documento registra o procedimento homologado para devolução de remessas no Omie ERP com **seleção e ajuste específico de itens e quantidades**, garantindo que a entrada seja gerada corretamente sem erros contábeis ou de estoque.

---

## 📌 Contexto da Operação
Quando unidades/polos (ex: Parangaba, Cascavel, CEST Fortaleza) possuem remessas em consignado e parte dos itens precisa ser devolvida para a Matriz (ou para faturamento de pedidos específicos), a devolução padrão do Omie devolveria **todos** os itens da remessa.

Nosso processo realiza a **devolução seletiva**:
1. Executa a devolução oficial da remessa no Omie (o status da remessa passa a ser **"Devolvido"**).
2. O Omie gera automaticamente uma **Nota de Entrada**.
3. O sistema consulta a nota gerada e:
   - **Exclui (`cAcaoItem: "E"`)** os itens que NÃO devem ser devolvidos.
   - **Ajusta (`cAcaoItem: "A"`)** a quantidade dos itens devolvidos.
   - Aplica o **CFOP 1.917** (Devolução de consignado/remessa).
   - Garante a **movimentação de estoque (`cNaoMovEstoque: "N"`)**.
   - Define a categoria contábil como **`2.01.01` — Compras de Mercadorias para Revenda** (evitando categorias automáticas indevidas como "Despesa com Inscrição Reciclagem").

---

## ⚙️ Regras Fiscais e Contábeis Padronizadas

| Campo | Valor Padrão | Descrição |
|---|---|---|
| **CFOP** | `1.917` | Devolução de mercadoria remetida para venda fora do estabelecimento / consignação |
| **Categoria** | `2.01.01` | Compras de Mercadorias para Revenda |
| **Movimenta Estoque** | `cNaoMovEstoque: "N"` | Ativa a entrada física e disponível no estoque da Matriz |
| **Observação** | Texto explicativo | Ex: *"Entrada de remessa para faturamento de pedido que estava em consignado"* |

---

## ⚠️ Regra Crítica da API Omie (Gotcha / Importante)
No método `produtos/notaentrada/ -> AlterarNotaEnt`:
- **NUNCA** envie o campo `cNumeroNotaEnt` no bloco `cabec` ao alterar. Se enviar, a API do Omie retorna erro SOAP dizendo que o número não pode ser alterado.
- Envie apenas:
  ```json
  "cabec": {
      "nCodNotaEnt": <ID_DA_NOTA>,
      "nCodCli": <ID_DO_CLIENTE>
  }
  ```

---

## 💻 Como Executar via Código Python

O módulo já está implementado e disponível em [`services/devolucao_remessa.py`](file:///c:/Users/guilh/Documents/Projeto%20omie/services/devolucao_remessa.py).

### Exemplo de Uso:
```python
from services.devolucao_remessa import executar_devolucao_seletiva_remessa

# 1. Defina o ID da Remessa no Omie (nCodRem)
id_remessa = 2265363412  # Exemplo da remessa nº 1801

# 2. Defina os itens que deseja manter devolvidos e a quantidade exata
itens_a_devolver = {
    "PRD00770": 7  # 7 unidades de 'Dos Vícios às Virtudes'
}

# 3. Executar
resultado = executar_devolucao_seletiva_remessa(
    nCodRem=id_remessa,
    itens_manter=itens_a_devolver,
    observacao="Entrada de remessa para faturamento de pedido que estava em consignado"
)

print(resultado)
```

---

## 📜 Histórico de Devoluções Executadas com Sucesso

1. **Parangaba (Remessa 1800)**:
   - Gerou Nota de Entrada nº 363.
   - Itens mantidos:
     - `PRD00471` (Liturgia Diária Outubro - 2026): 4 un
     - `009605` (Bolsa Sacola Ecobag Ide a José): 1 un
     - `009605` (Bolsa Sacola Ecobag A Caminho de um para Felicidade): 1 un

2. **CEST Fortaleza**:
   - **Remessa 1801**: Gerou Nota de Entrada nº 364 (ID: 2265364021) — 7 un de `PRD00770` (Dos Vícios às Virtudes).
   - **Remessa 1756**: Gerou Nota de Entrada nº 365 (ID: 2265364033) — 34 un de `PRD00471` (Liturgia Outubro).
   - **Remessa 1685**: Gerou Nota de Entrada nº 366 (ID: 2265364098) — 6 un de `PRD00384` (Caderneta All or Nothing).
