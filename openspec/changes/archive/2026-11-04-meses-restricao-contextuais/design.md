## Context

O sistema usa duas fases de coleta de dados: `obter_parametros_usuario()` para parâmetros globais (capacidade, spread, timeout, pesos) e `obter_projetos_usuario()` para configuração dos projetos (nome, datas, turmas). Atualmente, a ordem em `main.py` é: parâmetros → projetos.

Os campos `meses_recesso` e `meses_ferias_escolares` fazem parte de `ParametrosOtimizacao`, mas nunca são pedidos ao usuário: o dataclass define defaults hardcoded (`['Dez/26']`, `['Jul/26', 'Dez/26']`), e `obter_parametros_usuario()` não os passa na construção do objeto. O resultado é que qualquer config criada pelo menu interativo nasce sem restrições de calendário válidas.

A lista `meses` usada pelo solver é derivada das datas dos projetos em `main.py` ETAPA 2, e os índices de férias/recesso são calculados com `if m in meses` — meses fora do período são silenciosamente descartados.

## Goals / Non-Goals

**Goals:**
- Coletar `meses_recesso` e `meses_ferias_escolares` explicitamente do usuário no fluxo de nova configuração.
- Exibir apenas os meses pertencentes ao período real do projeto para seleção.
- Validar entradas em tempo real (número fora do intervalo → re-prompt).
- Manter retrocompatibilidade: configs JSON carregadas e fluxo de carregamento inalterados.
- Manter compatibilidade de assinatura: `obter_parametros_usuario()` sem argumento ainda funciona (retorna listas vazias com aviso).

**Non-Goals:**
- Alterar `data_models.py` (representação interna `List[str]` mantida).
- Alterar `config_manager.py`, `stage_1.py`, `stage_2.py` ou qualquer módulo de relatório.
- Suporte a anos implícitos ou meses agnósticos de ano (ex.: "todo Dezembro").
- Interface gráfica ou seleção por checkboxes — CLI puro.

## Decisions

### Decisão 1: Inverter a ordem de coleta em main.py

**Escolha:** projetos primeiro, depois parâmetros (com `meses_periodo` disponível).

**Alternativa considerada:** manter a ordem atual e adicionar uma etapa extra após a coleta dos projetos para perguntar os meses.

**Razão:** Inverter é mais limpo — evita uma segunda chamada a um módulo já encerrado, mantém o fluxo linear, e a coleta de projetos não depende de nenhum parâmetro global para funcionar. A única dependência de ordem é `obter_parametros_financeiros(projetos)`, que já recebe os projetos como argumento — mantém-se após a coleta de parâmetros.

### Decisão 2: Nova função privada `_obter_meses_restricao(meses)`

**Escolha:** função privada em `user_input.py`, separada de `obter_parametros_usuario`.

**Alternativa considerada:** embutir a lógica de exibição/coleta diretamente em `obter_parametros_usuario`.

**Razão:** Separação de responsabilidades e testabilidade. A função de coleta de restrições tem lógica própria (exibição em grade, validação de range, loop de confirmação) que cresce com manutenção. Manter isolada também facilita reutilização futura.

### Decisão 3: Parâmetro `meses` opcional em `obter_parametros_usuario`

**Escolha:** `meses: Optional[List[str]] = None` com comportamento de fallback (listas vazias + aviso).

**Alternativa considerada:** tornar o parâmetro obrigatório.

**Razão:** Retrocompatibilidade com quaisquer chamadas externas (testes, scripts) que não passem o período. O aviso visível no terminal evita a situação silenciosa atual.

### Decisão 4: Derivar `meses_periodo` em main.py antes de chamar `obter_parametros_usuario`

**Escolha:** reutilizar `gerar_lista_meses` já importada em `main.py` para derivar o período imediatamente após `obter_projetos_usuario()`.

**Razão:** `gerar_lista_meses` já existe, já é usada na ETAPA 2, e produz exatamente o formato `"Mês/AA"` esperado. Não há duplicação de lógica — apenas antecipa a chamada do que já ocorre mais adiante.

## Risks / Trade-offs

- **[Risco] Usuário acostumado com a ordem antiga fica desorientado** → Mitigação: os cabeçalhos de cada seção (`CONFIGURAÇÃO DE PROJETOS`, `CONFIGURAÇÃO DE PARÂMETROS GLOBAIS`) são mantidos e claramente impressos no terminal.
- **[Risco] Projeto com múltiplas datas inconsistentes gera período errado** → Mitigação: `gerar_lista_meses` recebe `min(data_inicio)` e `max(data_termino)` — mesmo comportamento já usado na ETAPA 2.
- **[Trade-off] Meses de restrição são específicos por ano** → O sistema não suporta restrições genéricas (ex.: "todo Dezembro"). Para projetos que se estendem por múltiplos anos, o usuário deve selecionar cada instância. Isso é um comportamento conhecido e documentado no aviso de "meses fora do período" adicionado anteriormente.

## Open Questions

- Nenhuma questão em aberto. O escopo está totalmente definido e alinhado com o código existente.
