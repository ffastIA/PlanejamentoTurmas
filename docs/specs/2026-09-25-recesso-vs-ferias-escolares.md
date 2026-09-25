# Análise do texto e plano: distinguir recesso institucional de férias escolares

> **Status: implementado e verificado em 2026-09-25.** Arquivado aqui como
> registro histórico da decisão de design. Uma diferença em relação ao texto
> original do plano: na Seção 9, os módulos de relatório
> (`plotting.py`, `spreadsheets.py`, `pdf_generator.py`) acabaram recebendo
> os **dois** calendários (`meses_recesso_idx`, `meses_ferias_escolares_idx`)
> em vez de só a união, porque as funções `calcular_fluxo_caixa_detalhado`,
> `calcular_evolucao_instrutores` e `calcular_lower_bounds` (em `utils.py`)
> precisam resolver o calendário efetivo por turma/projeto para produzir
> números corretos para projetos isentos — usar só a união teria subcontado
> a atividade desses projetos nos relatórios. O restante do plano foi
> implementado como descrito abaixo.

## Contexto

O texto colado é o relatório de um colega analisando por que ainda existe um
pico de 54 turmas (Out/27–Nov/27) na config atual do IdearTec, mesmo após
reduzir `ondas` para 1. Ele testou variar `peso_monotonia` (0 a 10000) e o
pico não muda — ou seja, não é um problema de peso/suavização, é geometria de
calendário: os meses de férias (ex. Jul/27 e Dez/27) são "buracos"
obrigatórios em que **nenhuma turma pode estar ativa**, e as 195 turmas do
IdearTec (585 turma-mês) precisam ser inteiramente encaixadas nos meses
restantes. Isso força o solver a concentrar turmas logo antes/depois de cada
buraco para fechar a conta. Remover as férias do cálculo (teste) achata a
curva quase perfeitamente (pico 42).

A ideia original do usuário era permitir que projetos que não dependem do
calendário escolar (oficinas, cursos em espaços tecnológicos) tivessem turmas
ativas durante os meses de férias, "preenchendo" os buracos do calendário
compartilhado e aliviando a pressão sobre projetos que de fato dependem da
escola (como o IdearTec) — atacando a causa raiz identificada no relatório
sem precisar alongar prazos.

**Correção importante feita pelo usuário**: nem todo mês de "férias" é igual.
Existem dois tipos, que podem ou não coincidir no calendário:

1. **Recesso institucional** (férias dos instrutores): os instrutores
   literalmente não estão disponíveis. Nenhuma turma pode ocorrer, de
   nenhum tipo — isso vale para qualquer projeto, isento ou não.
2. **Férias escolares**: as escolas fecham, mas os instrutores continuam
   disponíveis. Cursos executados em escola não podem ocorrer, mas oficinas
   e cursos em espaços tecnológicos podem, porque não dependem da escola
   estar aberta nem do instrutor estar de férias.

Exemplo dado pelo usuário: Dezembro = recesso de instrutores **e** férias
escolares (bloqueio total, nenhuma turma). Janeiro = só férias escolares
(instrutores disponíveis → oficinas/espaços tecnológicos podem rodar
normalmente, só cursos em escola ficam bloqueados).

Isso significa que a "tag no projeto" (permite ou não rodar em mês de
férias) não pode simplesmente ligar/desligar um único `meses_ferias` global
— é preciso **dois calendários de bloqueio separados**, com regras
diferentes de quem eles afetam:

| Tipo de mês              | Afeta projeto comum | Afeta projeto isento (oficina/espaço tec.) |
|---------------------------|:---:|:---:|
| Recesso institucional      | bloqueia | bloqueia (instrutor indisponível, tag não importa) |
| Férias escolares (só)      | bloqueia | **não bloqueia** |

Investigação confirmou que hoje existe **um único** parâmetro global
`ParametrosOtimizacao.meses_ferias` (`otimizador/data_models.py:98-100`), que
mistura os dois conceitos, e nenhum conceito de tipo/modalidade de curso
existe em código ou nos JSONs de config (`configuracoes_otimizacao/*.json`).
Esse único parâmetro é consumido por `calcular_meses_ativos()`
(`otimizador/utils.py:65-86`), que é o ponto de estrangulamento por onde
passam Stage 1, Stage 2 e os módulos de diagnóstico/validação — logo, o
plano precisa separar esse parâmetro em dois, e propagar ambos (mais a nova
tag por projeto) por todos os mesmos pontos.

## Implementação

### 1. `otimizador/data_models.py`

- `ParametrosOtimizacao` (linha 93-125): substituir o campo único
  `meses_ferias: List[str]` (linha 98-100) por dois campos:
  ```python
  meses_recesso: List[str] = field(
      default_factory=lambda: ['Dez/26']
  )
  meses_ferias_escolares: List[str] = field(
      default_factory=lambda: ['Jul/26', 'Dez/26']
  )
  ```
  (valores-exemplo — mantêm o default anterior coberto pela união dos dois).
  Nenhuma validação de range é necessária além da já ausente para o campo
  antigo.
- `ConfiguracaoProjeto` (linha 36-49): adicionar
  `permite_ferias_escolares: bool = False` logo após `turmas_min_por_mes`
  (linha 46), antes dos campos derivados `mes_inicio_idx`/`mes_termino_idx`.
  Nome explícito (em vez de `permite_ferias` genérico) para deixar claro que
  a flag só afeta férias escolares — recesso institucional bloqueia mesmo
  projetos com a tag, então não faz sentido a flag mencionar "férias" sem
  qualificar. Default `False` preserva o comportamento atual para todo
  projeto existente.
- `Projeto` namedtuple (linha 10-21): adicionar campo
  `permite_ferias_escolares` (bool) ao final.
- `Turma` namedtuple (linha 27-29): adicionar campo
  `permite_ferias_escolares` (bool) — necessário para o Stage 2 saber, por
  turma individual, se ela pode estar ativa em mês de férias escolares.

### 2. `otimizador/utils.py`

- Adicionar uma função pequena de composição, reutilizada em todos os
  pontos que hoje calculam meses ativos/janelas:
  ```python
  def calcular_meses_bloqueados(
      permite_ferias_escolares: bool,
      meses_recesso_idx: list,
      meses_ferias_escolares_idx: list
  ) -> list:
      """
      Recesso institucional bloqueia sempre (instrutor indisponível).
      Férias escolares só bloqueiam quem depende de escola.
      """
      if permite_ferias_escolares:
          return meses_recesso_idx
      return sorted(set(meses_recesso_idx) | set(meses_ferias_escolares_idx))
  ```
  `calcular_meses_ativos()` (linha 65-86) **não muda de assinatura** —
  continua recebendo um único `meses_ferias_idx` "efetivo" já resolvido pelo
  chamador via `calcular_meses_bloqueados()`.
- `converter_projetos_para_modelo()` (linha 263-407+): a assinatura passa a
  receber `meses_recesso_idx` e `meses_ferias_escolares_idx` (em vez do
  único `meses_ferias`). No início do loop `for config in projetos_config`
  (linha 284), calcular:
  ```python
  bloqueados = calcular_meses_bloqueados(
      config.permite_ferias_escolares, meses_recesso_idx, meses_ferias_escolares_idx
  )
  ```
  e usar `bloqueados` (em vez do parâmetro global) nas três chamadas que
  hoje usam a lista global para essa config: `calcular_janela_inicio`
  (linha 299-306), `_calcular_inicio_max_onda` (linha 357-364) e
  `_avancar_inicio_min_pos_onda` (linha 399-404).
  Propagar `config.permite_ferias_escolares` como novo argumento posicional
  nas duas construções de `Projeto(...)` (linha 319-330 e 385-396).
- As funções de relatório do próprio `utils.py` —
  `calcular_fluxo_caixa_detalhado`, `calcular_evolucao_instrutores` e
  `calcular_lower_bounds` — também foram atualizadas para receber os dois
  calendários e resolver o bloqueio efetivo por turma/projeto via
  `calcular_meses_bloqueados()`, em vez de um `meses_ferias_idx` único.

### 3. `otimizador/core/stage_1.py`

- Ler os dois parâmetros em vez de um (linha 36-38):
  ```python
  meses_recesso_idx = [meses.index(m) for m in parametros.meses_recesso if m in meses]
  meses_ferias_escolares_idx = [meses.index(m) for m in parametros.meses_ferias_escolares if m in meses]
  ```
- Para cada `proj`, calcular uma vez `bloqueados_proj =
  calcular_meses_bloqueados(proj.permite_ferias_escolares,
  meses_recesso_idx, meses_ferias_escolares_idx)` e usar `bloqueados_proj`
  (em vez do `meses_ferias_idx` global) em todos os pontos que hoje chamam
  `calcular_meses_ativos(...)` para essa onda/projeto:
  - Linha 52-54 (diagnóstico estrutural, `ultimo_mes_onda`)
  - Linha 114-116 (sequencialidade entre ondas, `ma_ant`)
  - Linha 130-131 (agregação de demanda mensal, `ma`)
  - Linha 154-156 e 163-164 (restrição de mínimo por mês)
  - Filtros `if m in meses_ferias_idx: continue` nas linhas 59 e 160 também
    devem usar `bloqueados_proj`, não o global.
- Suavização (mantendo a decisão já validada anteriormente: meses de férias
  escolares em que há turma isenta ativa devem ser suavizados normalmente,
  não só limitados por pico máximo) — como `demanda_mensal_vars` só ganha
  entrada em um mês bloqueado quando algum projeto isento tem turma ativa
  ali (nunca em mês de recesso, que bloqueia todo mundo), os filtros de
  "meses monitorados" continuam podendo depender só de
  `m in demanda_mensal_vars`, sem checar `meses_ferias_idx` global:
  - Linha 179-182 (`meses_monitorados`): manter/or simplificar para só
    `m in demanda_mensal_vars` (sem excluir por lista global).
  - Linha 227-229 (penalização de "queda"): remover o `continue` baseado no
    global — a checagem de `m not in demanda_mensal_vars` já cobre
    corretamente meses de recesso e meses de férias escolares sem atividade.
  - Linha 250 (`cruza_ferias`) permanece como está.
- Incluir `'permite_ferias_escolares': proj.permite_ferias_escolares` em
  cada item de `cronograma` (linha 316-337), para o Stage 2 reconstruir a
  flag por turma.
- Retorno da função (linha 406-412): trocar a chave `'meses_ferias'` por
  `'meses_recesso'` e `'meses_ferias_escolares'` (ou manter ambas as listas
  de índice separadas), já que consumidores a jusante (relatórios) também
  vão precisar dos dois calendários.

### 4. `otimizador/core/stage_2.py`

- Assinatura de `otimizar_atribuicao_e_carga()` (linha 25-31) passa a
  receber `meses_recesso_idx` e `meses_ferias_escolares_idx` em vez de
  `meses_ferias_idx`.
- Construção de `Turma(...)` (linha 52-58): incluir
  `permite_ferias_escolares=item['permite_ferias_escolares']`.
- `_dimensionar_pool()` (linha 127-146) e o cálculo de `meses_ativos_turma`
  em `_resolver_subproblema()` (linha 171-176): ambos hoje chamam
  `calcular_meses_ativos(turma.mes_inicio, turma.duracao, meses_ferias_idx,
  num_meses)` usando a lista global. Trocar por, por turma:
  ```python
  bloqueados_turma = calcular_meses_bloqueados(
      turma.permite_ferias_escolares, meses_recesso_idx, meses_ferias_escolares_idx
  )
  ```
  Sem isso, o Stage 2 recalcularia os meses ativos de uma turma isenta
  pulando férias escolares mesmo quando ela deveria estar ativa ali —
  dessincronizando do cronograma real gerado pelo Stage 1 (bug de
  consistência, não só de suavização).
- `meses_letivos` (linha 169), usado no laço de capacidade mensal (R2,
  linha 231-237), hoje exclui todo mês da lista global. Precisa refletir
  quais meses realmente têm turma ativa (já calculado via `turmas_no_mes`,
  linha 177-180) — trocar a base do laço de capacidade para os meses
  presentes em `turmas_no_mes`, não para "todo mês fora da lista global".
- `meses_com_turma` (linha 182): mesma correção — parte de
  `range(num_meses)` (ou de `turmas_no_mes.keys()`), não de `meses_letivos`
  restrito globalmente.
- R3 "Sem atribuições em meses de férias" (linha 252-258) passa a ter duas
  camadas — recesso bloqueia sempre, férias escolares só bloqueiam quem não
  tem a tag:
  ```python
  for m in meses_recesso_idx:
      for t in turmas_no_mes.get(m, []):
          for i in range(num_inst):
              model.Add(x[i, t] == 0)
  for m in meses_ferias_escolares_idx:
      for t in turmas_no_mes.get(m, []):
          if turmas[t].permite_ferias_escolares:
              continue
          for i in range(num_inst):
              model.Add(x[i, t] == 0)
  ```
  (Continua "redundante mas explícito", pois `turmas_no_mes` já reflete os
  meses corretos por construção — serve de rede de segurança.)

### 5. `otimizador/validacao_viabilidade.py` (linha 39-48) e `otimizador/diagnostico_restricoes.py` (linha ~40-42)

O cálculo de `meses_ferias_no_periodo` (usado para derivar
`duracao_meses_letivos`) hoje soma todo mês da lista global. Trocado para
somar `meses_recesso` sempre e `meses_ferias_escolares` só quando o projeto
não tem `permite_ferias_escolares=True` (evitando dupla contagem de um mês
que é simultaneamente recesso e férias escolares). Sem esse ajuste, a
validação prévia de viabilidade geraria avisos/erros falsos para projetos
isentos com curso longo sobrepondo férias escolares.

### 6. `otimizador/debug_diagnostico.py`

Recebia `meses_ferias_idx` e repassava para `calcular_meses_ativos`.
Atualizado para os dois novos parâmetros, resolvendo o bloqueio por
item/turma via `calcular_meses_bloqueados()`, seguindo o mesmo padrão do
Stage 1/2.

### 7. `otimizador/io/user_input.py` — CLI interativa

Em `_configurar_projeto_interativo()`, adicionado um prompt logo após o de
"Mínimo de turmas ativas/mês":
```python
permite_ferias_escolares_str = input(
    f"Permite execução durante férias ESCOLARES (oficina / espaço tecnológico)? (S/N) "
    f"[{'S' if (is_editing and projeto_existente.permite_ferias_escolares) else 'N'}]: "
).strip().upper()
permite_ferias_escolares = permite_ferias_escolares_str == 'S' if permite_ferias_escolares_str else (
    projeto_existente.permite_ferias_escolares if is_editing else False
)
```
e passado `permite_ferias_escolares=permite_ferias_escolares` na construção
de `ConfiguracaoProjeto(...)`. `exibir_resumo_parametros`/
`exibir_resumo_projetos` também passaram a exibir os dois calendários e a
tag por projeto.

`obter_parametros_usuario()` continua **não** perguntando
`meses_recesso`/`meses_ferias_escolares` interativamente (só vêm do default
do dataclass ou de config carregada) — mesma lacuna que já existia para o
campo único antigo, fora de escopo.

### 8. `otimizador/io/config_manager.py` — migração de configs antigas

`carregar_configuracao()` ganhou uma migração explícita antes de instanciar
`ParametrosOtimizacao`:
```python
params_data = dict(data.get("parametros", {}))
if 'meses_ferias' in params_data:
    legado = params_data.pop('meses_ferias')
    params_data.setdefault('meses_recesso', legado)
    params_data.setdefault('meses_ferias_escolares', [])
params = ParametrosOtimizacao(**params_data)
```
Isso preserva o comportamento anterior por padrão: todo mês que já era
"férias" vira recesso institucional (bloqueio universal), e o usuário
reclassifica manualmente os meses que forem só férias escolares depois.
Verificado com uma config real salva antes da mudança: carregou sem erro,
`meses_recesso` recebeu a lista antiga, `meses_ferias_escolares` ficou
vazia, e nenhum projeto tem `permite_ferias_escolares=True` por default —
comportamento idêntico ao anterior.

### 9. `main.py` e módulos de relatório

`main.py` passou a calcular `meses_recesso_idx` e `meses_ferias_escolares_idx`
separadamente e propagar ambos para `converter_projetos_para_modelo`,
`stage_2.otimizar_atribuicao_e_carga`, e todas as chamadas de relatório.
Diferente do texto original do plano (que previa passar só a união para
os relatórios), `plotting.py`, `spreadsheets.py` e `pdf_generator.py`
acabaram recebendo os **dois** calendários em cada função que produz
gráficos/planilhas que dependem de meses ativos por turma
(`gerar_grafico_turmas_projeto_mes`, `gerar_grafico_demanda_prog_rob`,
`plotar_conclusoes_por_mes`, `gerar_grafico_evolucao_instrutores`,
`gerar_grafico_fluxo_caixa`, `gerar_planilha_detalhada`,
`diagnosticar_fluxo_dados`), resolvendo o bloqueio por turma/projeto via
`calcular_meses_bloqueados()` — necessário para que oficinas isentas não
apareçam com atividade zerada nos relatórios durante férias escolares.

### Fora de escopo (não mexido)

- Diferenciação visual entre recesso e férias escolares nos relatórios
  (gráficos/planilhas/PDF) — ambos aparecem como "mês com alguma restrição",
  sem cor/hachura distinta.
- Prompts de CLI para editar `meses_recesso`/`meses_ferias_escolares`
  interativamente (hoje só editável via JSON — mesma lacuna pré-existente).

## Verificação (executada em 2026-09-25)

1. **Smoke test sintético** (script descartável, não versionado): projeto
   "EscolaX" (não isento) + projeto "OficinaY" (`permite_ferias_escolares=True`),
   calendário com Fev/27 = recesso + férias escolares, Mar/27 = só férias
   escolares. Resultado: OficinaY foi escalada com turma ativa em Mar/27;
   EscolaX nunca ativa em Fev/27 nem Mar/27; nenhum dos dois projetos ativo
   em Fev/27 (recesso); Stage 2 atribuiu instrutor à turma de OficinaY em
   Mar/27 e nunca atribuiu nada em Fev/27.
2. **Smoke test de migração**: carregada a config real mais recente
   (`config_20260924_165300.json`, que tinha o campo antigo `meses_ferias`
   com 4 meses). Migração converteu para `meses_recesso` = os 4 meses
   antigos, `meses_ferias_escolares` = lista vazia, todos os projetos com
   `permite_ferias_escolares=False`. `validar_viabilidade_configuracao` e
   `diagnosticar_restricoes` rodaram sem erro sobre essa config migrada.
3. Todos os arquivos editados passaram em `python -m py_compile` sem erros
   de sintaxe.
