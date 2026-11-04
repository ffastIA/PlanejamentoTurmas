## Why

Os campos `meses_recesso` e `meses_ferias_escolares` nunca são coletados via menu interativo — `obter_parametros_usuario()` cria `ParametrosOtimizacao` sem passá-los, então o objeto sempre nasce com os defaults hardcoded no dataclass (`['Dez/26']`, `['Jul/26', 'Dez/26']`). Como o projeto roda em 2027, esses meses ficam fora do período e são silenciosamente descartados, fazendo o solver operar sem nenhuma restrição de calendário.

## What Changes

- A ordem de coleta em `main.py` é invertida: projetos são coletados **antes** dos parâmetros globais, para que o período do projeto seja conhecido no momento em que os meses de restrição são pedidos ao usuário.
- Uma nova função `_obter_meses_restricao(meses)` em `user_input.py` exibe os meses do período numerados e coleta a seleção do usuário para recesso e férias escolares.
- `obter_parametros_usuario()` recebe um parâmetro opcional `meses: List[str]`; quando fornecido, chama `_obter_meses_restricao` e passa os resultados para `ParametrosOtimizacao`. Quando `None`, usa listas vazias e emite aviso.
- O `main.py` deriva `meses_periodo` das datas dos projetos antes de chamar `obter_parametros_usuario`.

## Capabilities

### New Capabilities

- `coleta-meses-restricao`: Coleta interativa dos meses de recesso e férias escolares, contextualizada ao período real do projeto, com exibição numerada e validação de entrada.

### Modified Capabilities

- `entrada-parametros-otimizacao`: O contrato de entrada dos parâmetros globais de otimização muda: `meses_recesso` e `meses_ferias_escolares` passam a ser coletados via input (não mais implícitos por default), e a função aceita o período como contexto.

## Impact

- `otimizador/io/user_input.py`: assinatura de `obter_parametros_usuario` alterada; nova função `_obter_meses_restricao` adicionada.
- `main.py`: ordem de coleta invertida; derivação de `meses_periodo` inserida antes da chamada de parâmetros.
- Sem impacto em `data_models.py`, `config_manager.py`, `stage_1.py`, `stage_2.py` ou qualquer módulo de relatório.
- Fluxo de **carregamento** de config JSON existente inalterado — meses já persistidos são usados diretamente.
