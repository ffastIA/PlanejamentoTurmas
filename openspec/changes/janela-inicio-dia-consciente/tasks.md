## 1. Implementação em utils.py

- [x] 1.1 Adicionar função auxiliar `_adicionar_meses(d: date, n: int) -> date` em `otimizador/utils.py` usando aritmética de meses sem dependência externa (logo antes de `_ultimo_mes_inicio_valido`)
- [x] 1.2 Adicionar função `_ultimo_mes_inicio_valido(data_termino_str: str, duracao_meses: int, meses: List[str]) -> int` em `otimizador/utils.py`: percorre `meses` de trás para frente e retorna o índice do último mês M onde `_adicionar_meses(date(ano_M, mes_M, 1), duracao_meses) <= parse(data_termino_str).date()`
- [x] 1.3 Em `converter_projetos_para_modelo`, substituir `config.mes_termino_idx = data_para_indice_mes(config.data_termino, meses)` por `config.mes_termino_idx = _ultimo_mes_inicio_valido(config.data_termino, config.duracao_curso, meses)`

## 2. Testes

- [x] 2.1 Adicionar teste `test_ultimo_mes_inicio_valido_periodo_30_dias`: período 11/01/2027–10/02/2027, duração 1 — espera índice de Jan/27 (Fev/27 excluído)
- [x] 2.2 Adicionar teste `test_ultimo_mes_inicio_valido_termino_fim_mes`: `data_termino = "31/01/2027"`, duração 1 — espera índice de Jan/27
- [x] 2.3 Adicionar teste `test_ultimo_mes_inicio_valido_3_meses`: `data_termino = "15/06/2027"`, duração 3, meses inclui Jan–Jun/27 — espera índice de Mar/27
- [x] 2.4 Verificar que testes existentes em `tests/test_utils.py` continuam passando (`pytest tests/`)

## 3. Validação manual

- [ ] 3.1 Configurar projeto com `data_inicio = "11/01/2027"`, `data_termino = "10/02/2027"`, `duracao_curso = 1`, `turmas_min_por_mes = 2`, `num_turmas = 2` e confirmar que o Stage 1 não gera infeasibility
- [ ] 3.2 Confirmar no log que `Janela global de início` exibe apenas Jan/27 (não Fev/27)
- [ ] 3.3 Rodar simulação completa com `config_20261104_180710.json` e confirmar que o resultado não regrediu (pico e distribuição compatíveis com execuções anteriores)
