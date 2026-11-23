## Context

O sistema usa uma lista de strings `meses = ["Jan/27", "Fev/27", ...]` como eixo de tempo único. Índices inteiros nessa lista são usados como variáveis de decisão no CP-SAT, como chaves de agrupamento de demanda e como labels de exibição. A janela válida de início `[inicio_min, inicio_max]` é calculada em `calcular_janela_inicio` usando `mes_termino_idx`, que hoje é derivado por `data_para_indice_mes(data_termino, meses)` — função que trunca a data para o início do mês e retorna seu índice. Isso faz com que o índice de término seja o mês do `data_termino`, não o último mês onde um curso ainda cabe integralmente.

Código relevante em `otimizador/utils.py`:
- `data_para_indice_mes` (linha ~47): converte "DD/MM/YYYY" → índice do mês truncando para o 1º do mês.
- `converter_projetos_para_modelo` (linha ~331): `config.mes_termino_idx = data_para_indice_mes(config.data_termino, meses)`.
- `calcular_janela_inicio` (linha ~121): aceita `mes_fim_projeto` e verifica `max(meses_ativos) <= mes_fim_projeto`.

## Goals / Non-Goals

**Goals:**
- Garantir que `inicio_max` seja o último mês M onde `date(ano_M, mes_M, 1) + N meses calendário ≤ parse(data_termino)`.
- Manter o restante do pipeline (Stage 1, Stage 2, reporting) inalterado.

**Non-Goals:**
- Mudar a unidade de duração de meses para dias.
- Alterar `calcular_janela_inicio`, `calcular_meses_ativos` ou qualquer lógica do Stage 1/2.
- Suportar entrada de duração em dias pelo usuário (escopo separado).

## Decisions

### Decisão 1: Nova função `_ultimo_mes_inicio_valido` em `utils.py`

**Escolha:** adicionar uma função privada `_ultimo_mes_inicio_valido(data_termino_str, duracao_meses, meses)` que percorre `meses` de trás para frente e retorna o índice do último mês M onde `date(ano_M, 1_de_M) + duracao_meses_calendário ≤ parse(data_termino_str)`.

**Aritmética de meses sem dependência externa:**
```python
from datetime import date

def _adicionar_meses(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)
```

**Alternativa descartada:** modificar `calcular_janela_inicio` para receber a data real. Isso ampliaria a assinatura de uma função chamada em vários lugares e misturaria responsabilidades (a função hoje trabalha exclusivamente com índices inteiros).

**Alternativa descartada:** usar `python-dateutil.relativedelta`. Acrescentaria dependência externa desnecessária.

### Decisão 2: Substituir a atribuição de `mes_termino_idx` em `converter_projetos_para_modelo`

**Escolha:** substituir:
```python
config.mes_termino_idx = data_para_indice_mes(config.data_termino, meses)
```
por:
```python
config.mes_termino_idx = _ultimo_mes_inicio_valido(
    config.data_termino, config.duracao_curso, meses
)
```

Isso propaga corretamente o `mes_termino_idx` para `calcular_janela_inicio` (que usa `mes_fim_projeto`) e para a criação de `Projeto` (campo `mes_fim_projeto`).

**Consequência:** `mes_termino_idx` passa a significar "último mês de início válido para um curso desta duração" em vez de "mês do `data_termino`". Isso é semanticamente mais correto para o uso que o sistema faz desse campo.

## Risks / Trade-offs

- [Risco] Projetos com `data_termino` no último dia do mês podem ter `mes_termino_idx` recuado em 1 se `01/M + duracao` for exatamente `01/M+1` que ainda é ≤ `ultimo_dia/M`. → Verificar com cenário: `data_termino = "31/01/2027"`, `duracao = 1` → `01/01 + 1 mês = 01/02 ≤ 31/01`? Não — 01/02 > 31/01 → Janeiro válido, Fevereiro inválido. Correto.
- [Risco] Configurações existentes que dependiam do comportamento atual (janela mais larga) terão resultados diferentes. → Comportamento novo é o correto; comportamento antigo era bug.

## Open Questions

_(nenhuma)_
