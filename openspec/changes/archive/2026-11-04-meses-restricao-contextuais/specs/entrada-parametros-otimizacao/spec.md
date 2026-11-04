## MODIFIED Requirements

### Requirement: Coleta de meses de restrição via menu interativo
O sistema SHALL coletar `meses_recesso` e `meses_ferias_escolares` explicitamente do usuário durante a configuração de nova simulação, em vez de usar valores default do dataclass.

A coleta SHALL ocorrer somente após o período do projeto estar determinado, utilizando a nova função `_obter_meses_restricao(meses)` passando a lista `meses_periodo` derivada das datas dos projetos.

Quando `meses` for `None` (retrocompatibilidade), ambas as listas resultam em `[]` e o sistema emite aviso informando que meses de restrição não foram configurados.

#### Scenario: Nova configuração — meses coletados com contexto
- **WHEN** o usuário inicia uma nova configuração e informa os projetos
- **THEN** o sistema deriva `meses_periodo` e chama `obter_parametros_usuario(meses=meses_periodo)`, garantindo que os meses de restrição sejam selecionados dentre os meses reais do projeto

#### Scenario: Configuração carregada de JSON
- **WHEN** o usuário carrega uma configuração existente de arquivo JSON
- **THEN** o sistema usa os valores de `meses_recesso` e `meses_ferias_escolares` já persistidos no JSON sem re-prompt ao usuário

#### Scenario: Chamada sem período (retrocompatibilidade)
- **WHEN** `obter_parametros_usuario()` é chamada sem argumento `meses`
- **THEN** `meses_recesso` e `meses_ferias_escolares` são `[]` e um aviso é exibido

### Requirement: Ordem de coleta — projetos antes de parâmetros
O sistema SHALL coletar a configuração dos projetos (incluindo `data_inicio` e `data_termino`) ANTES de coletar os parâmetros globais de otimização no fluxo de nova configuração.

#### Scenario: Projetos coletados primeiro no fluxo de nova configuração
- **WHEN** o usuário opta por nova configuração em `menu_gerenciar_configuracoes`
- **THEN** `obter_projetos_usuario()` é chamada antes de `obter_parametros_usuario()`

#### Scenario: Parâmetros de solver coletados com período disponível
- **WHEN** `obter_parametros_usuario(meses=meses_periodo)` é chamada
- **THEN** todos os campos de solver (capacidade, spread, timeout, pesos) são coletados normalmente, seguidos da seção de restrições de calendário contextualizada ao período real
