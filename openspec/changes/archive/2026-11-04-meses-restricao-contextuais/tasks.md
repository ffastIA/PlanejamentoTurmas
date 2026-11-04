## 1. user_input.py — nova função de coleta

- [x] 1.1 Adicionar `Tuple` ao import de `typing` em `user_input.py`
- [x] 1.2 Criar função `_obter_meses_restricao(meses: List[str]) -> Tuple[List[str], List[str]]` que exibe os meses do período em grade numerada (5 colunas) com título indicando período e quantidade
- [x] 1.3 Implementar prompt de recesso: aceitar números separados por vírgula, validar range (1 a len(meses)), re-prompt em caso de entrada inválida, Enter vazio retorna `[]`
- [x] 1.4 Implementar prompt de férias escolares com mesma lógica do 1.3
- [x] 1.5 Exibir preview das seleções (recesso + férias) e solicitar confirmação S/N; se N, reiniciar a partir do prompt de recesso
- [x] 1.6 Garantir que strings retornadas são extraídas diretamente de `meses` pelo índice selecionado (sem conversão de formato)

## 2. user_input.py — modificar obter_parametros_usuario

- [x] 2.1 Adicionar parâmetro `meses: Optional[List[str]] = None` à assinatura de `obter_parametros_usuario`
- [x] 2.2 Após a coleta dos campos de solver (antes de construir `ParametrosOtimizacao`), inserir bloco: se `meses` fornecido, chamar `_obter_meses_restricao(meses)`; senão, usar `[], []` e emitir aviso
- [x] 2.3 Passar `meses_recesso` e `meses_ferias_escolares` resultantes na construção de `ParametrosOtimizacao`
- [x] 2.4 Verificar que `exibir_resumo_parametros` já exibe os campos corretamente (sem alteração necessária)

## 3. main.py — inversão de ordem e derivação do período

- [x] 3.1 Mover `projetos_config = user_input.obter_projetos_usuario()` para antes de `parametros = user_input.obter_parametros_usuario()`
- [x] 3.2 Após `obter_projetos_usuario()`, inserir derivação de `meses_periodo`: `dt_min`/`dt_max` das datas dos projetos via `datetime.strptime`, seguido de `gerar_lista_meses(...)` — reutilizar import já existente
- [x] 3.3 Alterar chamada de `obter_parametros_usuario()` para `obter_parametros_usuario(meses=meses_periodo)`
- [x] 3.4 Verificar que o bloco de auto-save permanece após a coleta de ambos (`projetos_config` e `parametros`)
- [x] 3.5 Verificar que `obter_parametros_financeiros(projetos_config)` ainda é chamada após os parâmetros (ordem relativa a parâmetros mantida)

## 4. Verificação end-to-end

- [ ] 4.1 Executar `python main.py` → nova configuração → confirmar que a etapa de projetos aparece antes dos parâmetros globais
- [ ] 4.2 Confirmar que a seção "RESTRIÇÕES DE CALENDÁRIO" exibe os meses do período informado
- [ ] 4.3 Selecionar Dez/27 como recesso e Jul/27, Dez/27 como férias; verificar no JSON salvo que os campos contêm as strings corretas com o ano de 2027
- [ ] 4.4 Confirmar no log da ETAPA 2: `Meses de recesso: 1 (Dez/27)` e `Meses de férias escolares: 2 (Jul/27, Dez/27)` — aviso de "meses fora do período" não deve aparecer
- [ ] 4.5 Testar entrada inválida (número fora do range) e confirmar re-prompt sem perda de estado
- [ ] 4.6 Carregar JSON gerado em nova sessão e confirmar resumo de parâmetros correto sem re-prompt de meses
