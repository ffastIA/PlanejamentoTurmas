import math
import pytest
from otimizador.utils import calcular_meses_ativos, calcular_janela_inicio
from otimizador.data_models import Turma
from otimizador.core.stage_2 import _dimensionar_pool

from tests.conftest import MESES_14, FERIAS_IDX


# =============================================================================
# calcular_meses_ativos
# =============================================================================

def test_meses_ativos_sem_ferias():
    assert calcular_meses_ativos(2, 3, [], 14) == [2, 3, 4]


def test_meses_ativos_pula_ferias_simples():
    # Início Jun/26 (idx 5), duração 3, férias Jul/26 (idx 6)
    assert calcular_meses_ativos(5, 3, [6], 14) == [5, 7, 8]


def test_meses_ativos_pula_ferias_duplas():
    # Início Nov/26 (idx 10), duração 3, férias Dez/26 (idx 11)
    assert calcular_meses_ativos(10, 3, [11], 14) == [10, 12, 13]


def test_meses_ativos_dois_blocos_ferias():
    # Início Mai/26 (idx 4), duração 4, férias Jul/26 (6) e Dez/26 (11)
    resultado = calcular_meses_ativos(4, 4, [6, 11], 14)
    assert 6 not in resultado
    assert 11 not in resultado
    assert len(resultado) == 4


def test_meses_ativos_inicio_em_ferias():
    # Começar no próprio mês de férias: idx 6 (Jul/26)
    resultado = calcular_meses_ativos(6, 2, [6], 14)
    # Mês 6 é férias — não conta; deve pular e contar 7 e 8
    assert resultado == [7, 8]


def test_meses_ativos_duracao_um():
    assert calcular_meses_ativos(3, 1, [6, 11], 14) == [3]


def test_meses_ativos_sem_meses_suficientes():
    # Horizonte de 3 meses, início idx 1, duração 3, sem férias
    resultado = calcular_meses_ativos(1, 3, [], 3)
    assert resultado == [1, 2]  # só 2 meses disponíveis


# =============================================================================
# calcular_janela_inicio
# =============================================================================

def test_janela_inicio_basica():
    # Projeto Mar/26–Out/26 (idx 2–9), duração 2, sem férias no período
    ini, fim = calcular_janela_inicio(2, 9, 2, [6, 11], 14, MESES_14)
    assert ini <= fim
    assert ini >= 2


def test_janela_inicio_invalida_levanta_excecao():
    # Duração maior que o período disponível
    with pytest.raises(ValueError):
        calcular_janela_inicio(2, 3, 4, [], 14, MESES_14)


# =============================================================================
# _dimensionar_pool (nova margem 15%)
# =============================================================================

def test_pool_margem_15pct_basico():
    """Pool = minimo + max(1, ceil(minimo * 0.15))."""
    turmas = [Turma(id=i, projeto='T', habilidade='PROG', mes_inicio=2, duracao=2)
              for i in range(12)]
    pool = _dimensionar_pool(turmas, [], FERIAS_IDX, 14, 6, 'PROG')
    # Todas começam no mesmo mês (idx 2), ativas em 2 e 3 → pico = 12
    pico = 12
    minimo = math.ceil(pico / 6)  # = 2
    esperado = minimo + max(1, math.ceil(minimo * 0.15))  # 2 + max(1,1) = 3
    assert pool == esperado


def test_pool_sem_turmas():
    assert _dimensionar_pool([], [], FERIAS_IDX, 14, 6, 'PROG') == 0


def test_pool_pico_distribuido():
    """Turmas em meses distintos: pico = 1, pool = 2."""
    turmas = [
        Turma(id=0, projeto='T', habilidade='PROG', mes_inicio=2, duracao=1),
        Turma(id=1, projeto='T', habilidade='PROG', mes_inicio=3, duracao=1),
        Turma(id=2, projeto='T', habilidade='PROG', mes_inicio=4, duracao=1),
    ]
    pool = _dimensionar_pool(turmas, [], FERIAS_IDX, 14, 6, 'PROG')
    # pico = 1, minimo = 1, margem = max(1, ceil(0.15)) = 1 → pool = 2
    assert pool == 2


def test_pool_nao_excede_margem_antiga():
    """Com 15%, pool deve ser menor ou igual ao pool com 30%."""
    turmas = [Turma(id=i, projeto='T', habilidade='PROG', mes_inicio=2, duracao=3)
              for i in range(18)]
    pool_novo = _dimensionar_pool(turmas, [], FERIAS_IDX, 14, 6, 'PROG')
    pico = 18
    minimo = math.ceil(pico / 6)  # = 3
    pool_antigo = minimo + max(2, math.ceil(minimo * 0.30))  # 3 + 2 = 5
    assert pool_novo <= pool_antigo
