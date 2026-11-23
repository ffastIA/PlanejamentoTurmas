## ADDED Requirements

### Requirement: Último mês de início válido respeita data real de encerramento
O sistema SHALL calcular o último mês permitido para início de uma turma como o último mês M tal que um curso iniciado no primeiro dia de M e com duração `duracao_meses` termina em data menor ou igual à data real de encerramento do projeto (campo `data_termino` em formato "DD/MM/YYYY").

#### Scenario: Curso de 1 mês com término em dia não-final do mês
- **WHEN** `data_termino = "10/02/2027"` e `duracao_meses = 1`
- **THEN** o mês de Fevereiro/27 NÃO é incluído como mês de início válido, pois 01/02 + 1 mês = 01/03 > 10/02

#### Scenario: Curso de 1 mês com término no último dia do mês
- **WHEN** `data_termino = "28/02/2027"` e `duracao_meses = 1`
- **THEN** Fevereiro/27 É incluído como mês de início válido, pois 01/02 + 1 mês = 01/03 ≤ 28/02 é falso; na prática o início em Fev gera término em Fev, que é ≤ 28/02

#### Scenario: Curso de 3 meses com término em dia intermediário
- **WHEN** `data_termino = "15/06/2027"` e `duracao_meses = 3`
- **THEN** Abril/27 é válido (01/04 + 3 meses = 01/07 > 15/06 → inválido); Março/27 é válido (01/03 + 3 meses = 01/06 ≤ 15/06 → válido)

#### Scenario: Período menor que a duração do curso
- **WHEN** `data_inicio = "11/01/2027"`, `data_termino = "10/02/2027"` e `duracao_meses = 2`
- **THEN** nenhum mês é início válido e o sistema lança ValueError com mensagem descritiva

### Requirement: Restrição turmas_min_por_mes aplicada apenas sobre meses de início válidos
O sistema SHALL aplicar a restrição de mínimo de turmas por mês (`min_turmas`) somente sobre os meses que se encontram dentro da janela `[inicio_min, inicio_max]` calculada com a nova regra dia-consciente.

#### Scenario: Dois meses no calendário mas apenas um válido para início
- **WHEN** o calendário contém Jan/27 e Fev/27, mas apenas Jan/27 é mês de início válido (Fev excluído pela regra de data real)
- **THEN** a restrição `x[i, Jan/27] >= min_turmas` é aplicada e nenhuma restrição de mínimo é aplicada a Fev/27
