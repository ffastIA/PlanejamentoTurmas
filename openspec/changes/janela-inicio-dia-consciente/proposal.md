## Why

A janela de início válida de uma turma é calculada usando o índice do mês de término do projeto (`mes_termino_idx`), que é derivado truncando a data real para o primeiro dia do mês. Isso faz com que o sistema permita starts em meses onde o curso não consegue terminar antes da data real de encerramento — resultando em restrição `turmas_min_por_mes` aplicada sobre meses que, na prática, não comportam um curso completo.

Exemplo concreto: projeto com período 11/01/2027–10/02/2027, duração 1 mês, min 2 turmas/mês e total 2 turmas. O sistema gera `meses = ["Jan/27", "Fev/27"]` e permite início em Fevereiro, embora um curso começando em 01/02 termine em 01/03 — depois do encerramento real. A restrição de mínimo é aplicada sobre 2 meses, exigindo 4 turmas quando só há 2.

## What Changes

- Nova função `_ultimo_mes_inicio_valido(data_termino_str, duracao_meses, meses)` em `otimizador/utils.py`: retorna o índice do último mês M tal que um curso iniciado em 01/M e com duração `duracao_meses` termina em data ≤ `data_termino_str`.
- `converter_projetos_para_modelo` passa a usar essa nova função para derivar `mes_termino_idx` e `inicio_max_global`, em vez de `data_para_indice_mes` (que trunca para o início do mês sem considerar a duração do curso).

## Capabilities

### New Capabilities

- `janela-inicio-validacao`: Validação dia-consciente da janela de início de turmas, garantindo que apenas meses onde um curso pode ser concluído dentro da data real de encerramento do projeto sejam considerados válidos.

### Modified Capabilities

_(nenhuma — nenhuma spec existente é alterada)_

## Impact

- `otimizador/utils.py`: função nova `_ultimo_mes_inicio_valido`, alteração em `converter_projetos_para_modelo` (~2 linhas).
- Nenhuma alteração em `stage_1.py`, `stage_2.py`, `data_models.py`, `config_manager.py` ou nos módulos de reporting.
- Projetos cujo `data_termino` cai antes do fim do mês terão `inicio_max` menor do que antes — comportamento correto.
- Projetos cujo `data_termino` cai no último dia do mês ou é o último dia (ex.: 31/01/2027) terão comportamento idêntico ao atual.
