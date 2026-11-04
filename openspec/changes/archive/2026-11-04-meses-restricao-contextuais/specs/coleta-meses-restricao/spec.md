## ADDED Requirements

### Requirement: Exibição de meses disponíveis do período
O sistema SHALL exibir a lista completa de meses do período do projeto, numerados sequencialmente, antes de solicitar a seleção dos meses de restrição.

#### Scenario: Lista exibida com período real
- **WHEN** o usuário inicia a configuração de nova simulação com um projeto de Jan/27 a Mai/28
- **THEN** o sistema exibe 17 meses numerados de 1 (Jan/27) a 17 (Mai/28), com título indicando período e quantidade

### Requirement: Seleção de meses de recesso por número
O sistema SHALL aceitar a seleção de meses de recesso institucional via lista de números separados por vírgula, onde cada número corresponde à posição do mês na lista exibida.

#### Scenario: Seleção válida de um mês
- **WHEN** o usuário informa `12` para um período com Dez/27 na posição 12
- **THEN** o sistema inclui `"Dez/27"` em `meses_recesso` de `ParametrosOtimizacao`

#### Scenario: Seleção de múltiplos meses
- **WHEN** o usuário informa `7, 12`
- **THEN** o sistema inclui `"Jul/27"` e `"Dez/27"` em `meses_recesso`

#### Scenario: Entrada vazia — nenhum recesso
- **WHEN** o usuário pressiona Enter sem digitar nada
- **THEN** `meses_recesso` resulta em lista vazia `[]`

#### Scenario: Número fora do intervalo
- **WHEN** o usuário informa um número menor que 1 ou maior que o total de meses
- **THEN** o sistema exibe aviso e repete o prompt de recesso sem perder estado

### Requirement: Seleção de meses de férias escolares por número
O sistema SHALL aceitar a seleção de meses de férias escolares com as mesmas regras de entrada dos meses de recesso, em prompt separado exibido após o de recesso.

#### Scenario: Seleção com sobreposição ao recesso
- **WHEN** o usuário seleciona um mês tanto como recesso quanto como férias escolares
- **THEN** o sistema aceita a seleção e inclui o mês em ambas as listas, exibindo aviso informativo no preview

#### Scenario: Entrada vazia — nenhuma féria escolar
- **WHEN** o usuário pressiona Enter no prompt de férias escolares
- **THEN** `meses_ferias_escolares` resulta em lista vazia `[]`

### Requirement: Preview e confirmação antes de finalizar
O sistema SHALL exibir um resumo das seleções (recesso e férias escolares) e solicitar confirmação do usuário antes de prosseguir.

#### Scenario: Usuário confirma seleção
- **WHEN** o sistema exibe o preview e o usuário confirma com `S` ou Enter
- **THEN** as listas são aceitas e a coleta de parâmetros prossegue

#### Scenario: Usuário rejeita e corrige
- **WHEN** o usuário responde `N` na confirmação
- **THEN** o sistema reinicia o prompt de recesso, mantendo os demais campos já preenchidos intactos

### Requirement: Strings de saída no formato canônico "Mês/AA"
O sistema SHALL produzir strings de meses no formato `"Mês/AA"` (ex.: `"Dez/27"`, `"Jul/27"`), extraídas diretamente da lista `meses` recebida como parâmetro, sem transformação ou conversão.

#### Scenario: Formato preservado da lista de entrada
- **WHEN** a lista `meses` contém `"Dez/27"` na posição 12 e o usuário seleciona `12`
- **THEN** a string `"Dez/27"` é incluída na lista de saída sem modificação
