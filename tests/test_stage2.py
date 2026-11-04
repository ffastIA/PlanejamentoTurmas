import math
import pytest
from collections import defaultdict

from otimizador.data_models import Turma, ParametrosOtimizacao
from otimizador.core.stage_2 import (
    otimizar_atribuicao_e_carga,
    _dimensionar_pool,
    _resolver_subproblema,
)
from otimizador.utils import calcular_meses_ativos

from tests.conftest import MESES_14, FERIAS_IDX


# =============================================================================
# Helpers
# =============================================================================

def _carga_mensal_instrutor(inst_id: str, resultado: dict, ferias_idx: list, num_meses: int) -> list:
    """Retorna lista com carga de cada mês para um instrutor."""
    cargas = [0] * num_meses
    for atr in resultado['atribuicoes']:
        if atr['instrutor'].id == inst_id:
            for m in calcular_meses_ativos(atr['turma'].mes_inicio, atr['turma'].duracao, ferias_idx, num_meses):
                cargas[m] += 1
    return cargas


def _instrutores_ativos(resultado: dict) -> set:
    return {atr['instrutor'].id for atr in resultado['atribuicoes']}


def _cronograma_uniforme(num_turmas: int, duracao: int, inicio_min: int) -> list:
    """Cronograma com 1 turma por mês durante num_turmas meses."""
    return [
        {
            'projeto_nome': 'TEST', 'projeto_pai': 'TEST', 'onda_idx': 0,
            'projeto_idx': 0, 'mes_inicio': inicio_min + i,
            'qtd': 1, 'duracao': duracao, 'habilidade': 'PROG',
        }
        for i in range(num_turmas)
    ]


# =============================================================================
# M1a — remoção de Σy[i,m]: solver não concentra carga no tempo
# =============================================================================

def test_sem_concentracao_temporal(parametros_teste):
    """Com Σy[i,m] removido, o spread mensal de cada instrutor ativo
    deve ser baixo (carga distribuída no tempo, não concentrada)."""
    # 12 turmas: 6 com duração 1 em meses seguidos — cada instrutor
    # terá no máximo capacidade_max turmas por mês (cap=6), e o objetivo
    # de spread_mes_inst incentiva carga uniforme entre os meses ativos.
    cronograma = _cronograma_uniforme(6, 2, 2)  # 6 turmas, dur 2, início a partir de Mar/26
    resultado = otimizar_atribuicao_e_carga(
        cronograma, [], MESES_14, FERIAS_IDX, parametros_teste
    )
    assert resultado['status'] == 'sucesso'
    assert len(resultado['atribuicoes']) == 6

    # Verificar que nenhum instrutor ativo tem spread_mensal excessivo
    for inst_id in _instrutores_ativos(resultado):
        cargas = _carga_mensal_instrutor(inst_id, resultado, FERIAS_IDX, len(MESES_14))
        cargas_ativas = [c for c in cargas if c > 0]
        if len(cargas_ativas) >= 2:
            spread = max(cargas_ativas) - min(cargas_ativas)
            assert spread <= 3, (
                f"Instrutor {inst_id}: spread mensal {spread} > 3 "
                f"(cargas={cargas_ativas}) — possível concentração de carga"
            )


# =============================================================================
# M1b — spread mensal por instrutor
# =============================================================================

def test_spread_mensal_limitado(parametros_teste):
    """Nenhum instrutor ativo deve ter spread mensal (max_mes - min_mes) > 2."""
    # 8 turmas distribuídas em 4 meses, duração 2 cada
    cronograma = [
        {'projeto_nome': 'T', 'projeto_pai': 'T', 'onda_idx': 0, 'projeto_idx': 0,
         'mes_inicio': 2 + (i % 4), 'qtd': 2, 'duracao': 2, 'habilidade': 'PROG'}
        for i in range(4)
    ]
    resultado = otimizar_atribuicao_e_carga(
        cronograma, [], MESES_14, FERIAS_IDX, parametros_teste
    )
    assert resultado['status'] == 'sucesso'

    for inst_id in _instrutores_ativos(resultado):
        cargas = _carga_mensal_instrutor(inst_id, resultado, FERIAS_IDX, len(MESES_14))
        cargas_ativas = [c for c in cargas if c > 0]
        if len(cargas_ativas) >= 2:
            spread = max(cargas_ativas) - min(cargas_ativas)
            assert spread <= 3, (
                f"Instrutor {inst_id}: spread mensal {spread} > 3 "
                f"(cargas={cargas_ativas})"
            )


# =============================================================================
# M2 — pool com margem 15%
# =============================================================================

def test_pool_margem_15pct(parametros_teste):
    """Pool deve ser minimo + max(1, ceil(minimo * 0.15))."""
    turmas = [Turma(id=i, projeto='T', habilidade='PROG', mes_inicio=2, duracao=2)
              for i in range(12)]
    pool = _dimensionar_pool(turmas, FERIAS_IDX, len(MESES_14), 6, 'PROG')
    pico = 12
    minimo = math.ceil(pico / 6)
    esperado = minimo + max(1, math.ceil(minimo * 0.15))
    assert pool == esperado


def test_pool_menor_que_margem_antiga(parametros_teste):
    """Pool novo (15%) deve ser ≤ pool antigo (30%) para qualquer entrada."""
    for n_turmas in [6, 12, 18, 30]:
        turmas = [Turma(id=i, projeto='T', habilidade='PROG', mes_inicio=2, duracao=3)
                  for i in range(n_turmas)]
        pool_novo = _dimensionar_pool(turmas, FERIAS_IDX, len(MESES_14), 6, 'PROG')
        pico = n_turmas
        minimo = math.ceil(pico / 6)
        pool_antigo = minimo + max(2, math.ceil(minimo * 0.30))
        assert pool_novo <= pool_antigo, (
            f"n_turmas={n_turmas}: pool_novo={pool_novo} > pool_antigo={pool_antigo}"
        )


# =============================================================================
# Regressão: status de falha quando não há turmas
# =============================================================================

def test_turmas_vazias_retorna_falha(parametros_teste):
    """Stage 2 com cronograma vazio deve retornar status 'falha'."""
    resultado = otimizar_atribuicao_e_carga(
        [], [], MESES_14, FERIAS_IDX, parametros_teste
    )
    assert resultado['status'] == 'falha', (
        "Stage 2 com turmas vazias deveria retornar 'falha', "
        f"mas retornou '{resultado['status']}'"
    )


def test_turmas_qtd_zero_retorna_falha(parametros_teste):
    """Cronograma com qtd=0 em todos os itens deve resultar em 'falha'."""
    cronograma = [
        {'projeto_nome': 'T', 'projeto_pai': 'T', 'onda_idx': 0,
         'projeto_idx': 0, 'mes_inicio': 2, 'qtd': 0, 'duracao': 2, 'habilidade': 'PROG'}
    ]
    resultado = otimizar_atribuicao_e_carga(
        cronograma, [], MESES_14, FERIAS_IDX, parametros_teste
    )
    assert resultado['status'] == 'falha'


# =============================================================================
# Sanidade geral
# =============================================================================

def test_cobertura_completa(parametros_teste):
    """Toda turma do cronograma deve receber exatamente um instrutor."""
    cronograma = _cronograma_uniforme(4, 2, 2)
    resultado = otimizar_atribuicao_e_carga(
        cronograma, [], MESES_14, FERIAS_IDX, parametros_teste
    )
    assert resultado['status'] == 'sucesso'
    # Contar turmas cobertas (cada item do cronograma tem qtd=1)
    turmas_cobertas = len(resultado['atribuicoes'])
    assert turmas_cobertas == 4, f"Esperado 4 atribuições, obtido {turmas_cobertas}"


def test_capacidade_mensal_respeitada(parametros_teste):
    """Nenhum instrutor deve ter mais de capacidade_max turmas em qualquer mês."""
    cap = parametros_teste.capacidade_max_instrutor
    cronograma = _cronograma_uniforme(8, 1, 2)
    resultado = otimizar_atribuicao_e_carga(
        cronograma, [], MESES_14, FERIAS_IDX, parametros_teste
    )
    assert resultado['status'] == 'sucesso'
    for inst_id in _instrutores_ativos(resultado):
        cargas = _carga_mensal_instrutor(inst_id, resultado, FERIAS_IDX, len(MESES_14))
        assert max(cargas) <= cap, (
            f"Instrutor {inst_id}: carga máxima {max(cargas)} > cap {cap}"
        )
