import pytest
from otimizador.data_models import Projeto, ParametrosOtimizacao, Turma, Instrutor

# Lista de 14 meses: Jan/26 a Fev/27
MESES_14 = [
    'Jan/26', 'Fev/26', 'Mar/26', 'Abr/26', 'Mai/26', 'Jun/26', 'Jul/26',
    'Ago/26', 'Set/26', 'Out/26', 'Nov/26', 'Dez/26', 'Jan/27', 'Fev/27'
]

# Jul/26 = idx 6, Dez/26 = idx 11
FERIAS_IDX = [6, 11]


@pytest.fixture
def parametros_teste():
    return ParametrosOtimizacao(
        capacidade_max_instrutor=6,
        spread_maximo=4,
        meses_ferias_escolares=['Jul/26', 'Dez/26'],
        timeout_segundos=60,
        peso_instrutores=1000,
        peso_spread=1,
        peso_spread_mensal=100,
        pico_maximo_turmas=30,
        peso_monotonia=100,
    )


@pytest.fixture
def projeto_unico():
    """Projeto simples: 12 turmas, duração 2 meses, janela Mar/26–Out/26 (idx 2–9).
    mes_fim_projeto=10 (Nov/26): última turma começa em Out/26 e termina em Nov/26."""
    return Projeto(
        nome='TEST',
        prog=8,
        rob=4,
        duracao=2,
        inicio_min=2,
        inicio_max=9,
        mes_fim_projeto=10,
        min_turmas=1,
        projeto_pai='TEST',
        onda_idx=0,
    )


@pytest.fixture
def projeto_curto():
    """Projeto com turmas de duração 1 mês, janela Mai/26–Out/26 (idx 4–9)."""
    return Projeto(
        nome='CURTO',
        prog=6,
        rob=0,
        duracao=1,
        inicio_min=4,
        inicio_max=9,
        mes_fim_projeto=13,
        min_turmas=0,
        projeto_pai='CURTO',
        onda_idx=0,
    )
