# ===== ARQUIVO: otimizador/core/stage_2.py =====
"""
Otimizador de Atribuição e Carga - Estágio 2
Versão final com suavização temporal da equipe preservando v5.4.
"""

from ortools.linear_solver import pywraplp
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
import math

from ..data_models import Projeto, Turma, Instrutor, ParametrosOtimizacao
from ..utils import calcular_meses_ativos


"""
Módulo Stage 2: Otimização de Atribuição e Carga

Este módulo implementa a segunda etapa do otimizador, focada na atribuição de instrutores às turmas
e na otimização da carga de trabalho, considerando restrições de capacidade mensal, spread de carga
e suavização temporal da equipe. A versão final adiciona suavização temporal da equipe preservando a v5.4.

Principais funcionalidades:
- Criação de turmas a partir do cronograma do Stage 1.
- Dimensionamento de pools de instrutores por habilidade.
- Resolução de subproblemas de atribuição com restrições mensais de capacidade.
- Otimização com pesos para spread, número de instrutores e variação temporal.
"""


def otimizar_atribuicao_e_carga(
    cronograma_estagio1: List[Dict],
    projetos: List[Projeto],
    meses: List[str],
    meses_ferias_idx: List[int],
    parametros: ParametrosOtimizacao
) -> Dict[str, Any]:
    """
    Otimiza a atribuição de instrutores às turmas e a carga de trabalho,
    considerando restrições de capacidade mensal e suavização temporal.
    """
    print("\n=== STAGE 2: Otimização de Atribuição e Carga ===")
    print(f"Parâmetros: capacidade_max={parametros.capacidade_max_instrutor}, spread_max={parametros.spread_maximo}, timeout={parametros.timeout_segundos}s")
    print(f"Pesos: instrutores={parametros.peso_instrutores}, spread={parametros.peso_spread}, monotonia={parametros.peso_monotonia}")

    # Criação das turmas a partir do cronograma do Stage 1
    turmas_objetos = []
    for item in cronograma_estagio1:
        for _ in range(item['qtd']):
            turma = Turma(
                id=len(turmas_objetos),
                projeto=item['projeto_nome'],
                habilidade=item['habilidade'],
                mes_inicio=item['mes_inicio'],
                duracao=item['duracao']
            )
            turmas_objetos.append(turma)

    # Separação por habilidade
    turmas_prog = [t for t in turmas_objetos if t.habilidade == 'PROG']
    turmas_rob = [t for t in turmas_objetos if t.habilidade == 'ROBOTICA']

    if not turmas_objetos:
        return {"status": "falha", "erro": "Nenhuma turma para alocar"}

    print(f"Turmas criadas: PROG={len(turmas_prog)}, ROB={len(turmas_rob)}")

    # Dimensionamento dos pools
    pool_prog = _dimensionar_pool(turmas_prog, meses_ferias_idx, len(meses), parametros.capacidade_max_instrutor, 'PROG')
    pool_rob = _dimensionar_pool(turmas_rob, meses_ferias_idx, len(meses), parametros.capacidade_max_instrutor, 'ROBOTICA')

    # Criação dos pools de instrutores
    instrutores_prog = [Instrutor(id=f'PROG_{i+1}', habilidade='PROG', capacidade=parametros.capacidade_max_instrutor, laboratorio_id=None) for i in range(pool_prog)]
    instrutores_rob = [Instrutor(id=f'ROB_{i+1}', habilidade='ROBOTICA', capacidade=parametros.capacidade_max_instrutor, laboratorio_id=None) for i in range(pool_rob)]

    # Resolução dos subproblemas
    atribuicoes_prog, desvio_prog = _resolver_subproblema('PROG', turmas_prog, instrutores_prog, meses, meses_ferias_idx, parametros)
    atribuicoes_rob, desvio_rob = _resolver_subproblema('ROBOTICA', turmas_rob, instrutores_rob, meses, meses_ferias_idx, parametros)

    # Consolidação dos resultados
    atribuicoes_total = []
    if atribuicoes_prog:
        atribuicoes_total.extend(atribuicoes_prog)
    if atribuicoes_rob:
        atribuicoes_total.extend(atribuicoes_rob)

    desvio_max = max(desvio_prog if desvio_prog is not None else 0, desvio_rob if desvio_rob is not None else 0)

    print(f"Atribuições totais: {len(atribuicoes_total)}")
    print(f"Spread máximo: {desvio_max}")

    return {
        "status": "sucesso",
        "atribuicoes": atribuicoes_total,
        "turmas": turmas_objetos,
        "spread_carga": desvio_max,
        "capacidade_max_instrutor": parametros.capacidade_max_instrutor,
        "spread_detalhado": {
            "PROG": desvio_prog if desvio_prog is not None else 0,
            "ROB": desvio_rob if desvio_rob is not None else 0
        }
    }


def _dimensionar_pool(
    turmas: List[Turma],
    meses_ferias_idx: List[int],
    num_meses: int,
    capacidade: int,
    habilidade: str
) -> int:
    """
    Dimensiona o pool de instrutores necessário para cobrir a demanda mensal.
    """
    if not turmas:
        return 0

    demanda_por_mes = defaultdict(int)
    for turma in turmas:
        meses_ativos = calcular_meses_ativos(turma.mes_inicio, turma.duracao, meses_ferias_idx, num_meses)
        for mes in meses_ativos:
            demanda_por_mes[mes] += 1

    pico = max(demanda_por_mes.values()) if demanda_por_mes else 0
    minimo = math.ceil(pico / capacidade)
    # Margem de 15% (era 30%) para pressionar o solver a distribuir melhor
    pool = minimo + max(1, math.ceil(minimo * 0.15))

    print(f"Pool {habilidade}: pico={pico}, mínimo={minimo}, pool={pool}")
    return pool


def _resolver_subproblema(
    habilidade: str,
    turmas: List[Turma],
    instrutores: List[Instrutor],
    meses: List[str],
    meses_ferias_idx: List[int],
    parametros: ParametrosOtimizacao
) -> Tuple[Optional[List[Dict]], Optional[int]]:
    """
    Resolve o subproblema de atribuição para uma habilidade específica.
    """
    if not turmas:
        print(f"  Subproblema {habilidade}: sem turmas")
        return [], 0

    num_turmas = len(turmas)
    num_instrutores = len(instrutores)
    num_meses = len(meses)

    # Meses letivos (excluindo férias)
    meses_letivos = [m for m in range(num_meses) if m not in meses_ferias_idx]

    # Meses ativos por turma
    meses_ativos_turma = {}
    for t_idx, turma in enumerate(turmas):
        meses_ativos_turma[t_idx] = calcular_meses_ativos(turma.mes_inicio, turma.duracao, meses_ferias_idx, num_meses)

    # Turmas ativas por mês
    turmas_no_mes = defaultdict(list)
    for t_idx, meses_ativos in meses_ativos_turma.items():
        for mes in meses_ativos:
            turmas_no_mes[mes].append(t_idx)

    # Projetos presentes
    projetos_presentes = set(t.projeto for t in turmas)

    print(f"  Subproblema {habilidade}: turmas={num_turmas}, instrutores={num_instrutores}, projetos={len(projetos_presentes)}")

    # Solver
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        print(f"  Erro: solver não criado para {habilidade}")
        return None, None
    solver.SetTimeLimit(parametros.timeout_segundos * 1000)

    # Variáveis
    x = {}
    for i in range(num_instrutores):
        for t in range(num_turmas):
            x[i, t] = solver.BoolVar(f'x_{i}_{t}')

    ativo = [solver.BoolVar(f'ativo_{i}') for i in range(num_instrutores)]
    max_carga = solver.IntVar(0, num_turmas, 'max_carga')
    min_carga = solver.IntVar(0, num_turmas, 'min_carga')
    spread_v = solver.IntVar(0, num_turmas, 'spread_v')

    y = {}
    for i in range(num_instrutores):
        for m in meses_letivos:
            if turmas_no_mes.get(m, []):
                y[i, m] = solver.BoolVar(f'y_{i}_{m}')

    # R1: Cobertura - cada turma deve ser atribuída a exatamente um instrutor
    for t in range(num_turmas):
        solver.Add(solver.Sum([x[i, t] for i in range(num_instrutores)]) == 1)

    # R2: Capacidade mensal - para cada instrutor e mês letivo, soma das turmas ativas <= capacidade
    for i in range(num_instrutores):
        for m in meses_letivos:
            turmas_mes = turmas_no_mes.get(m, [])
            if turmas_mes:
                solver.Add(solver.Sum([x[i, t] for t in turmas_mes]) <= parametros.capacidade_max_instrutor)

    # R2b: Derivação de y - y[i,m] indica se o instrutor está ativo no mês
    for i in range(num_instrutores):
        for m in meses_letivos:
            turmas_mes = turmas_no_mes.get(m, [])
            if turmas_mes:
                n = len(turmas_mes)
                for t in turmas_mes:
                    solver.Add(y[i, m] * n >= x[i, t])
                solver.Add(y[i, m] <= solver.Sum([x[i, t] for t in turmas_mes]))

    # R3: Férias - se houver turmas em mês de férias, forçar soma zero (mas como meses_ativos já exclui, pode ser redundante)
    for m in meses_ferias_idx:
        if turmas_no_mes.get(m, []):
            for i in range(num_instrutores):
                solver.Add(solver.Sum([x[i, t] for t in turmas_no_mes[m]]) == 0)

    # R4: Ativação global - carga total deve estar entre 1 e num_turmas se ativo
    for i in range(num_instrutores):
        carga_total = solver.Sum([x[i, t] for t in range(num_turmas)])
        solver.Add(carga_total <= num_turmas * ativo[i])
        solver.Add(carga_total >= ativo[i])

    # R5: Spread - max_carga e min_carga para calcular spread
    for i in range(num_instrutores):
        carga_total = solver.Sum([x[i, t] for t in range(num_turmas)])
        solver.Add(max_carga >= carga_total)
        solver.Add(min_carga <= carga_total + (1 - ativo[i]) * num_turmas)
    solver.Add(spread_v == max_carga - min_carga)

    # Spread mensal por instrutor: penaliza diferença entre mês mais e menos carregado
    max_mes_inst = {}
    min_mes_inst = {}
    spread_mes_inst = {}
    meses_com_turma = [m for m in meses_letivos if turmas_no_mes.get(m, [])]
    for i in range(num_instrutores):
        max_mes_inst[i] = solver.IntVar(0, parametros.capacidade_max_instrutor, f'max_mes_{i}')
        min_mes_inst[i] = solver.IntVar(0, parametros.capacidade_max_instrutor, f'min_mes_{i}')
        spread_mes_inst[i] = solver.IntVar(0, parametros.capacidade_max_instrutor, f'spread_mes_{i}')
        for m in meses_com_turma:
            carga_m = solver.Sum([x[i, t] for t in turmas_no_mes.get(m, [])])
            solver.Add(max_mes_inst[i] >= carga_m)
            solver.Add(min_mes_inst[i] <= carga_m + (1 - ativo[i]) * parametros.capacidade_max_instrutor)
        solver.Add(spread_mes_inst[i] == max_mes_inst[i] - min_mes_inst[i])

    # Estratégia B: Suavização temporal da equipe
    inst_ativos_mes = {}
    for m in meses_com_turma:
        inst_ativos_mes[m] = solver.Sum([y[i, m] for i in range(num_instrutores)])

    variacao_inst_mes = {}
    for idx in range(1, len(meses_com_turma)):
        m_prev = meses_com_turma[idx-1]
        m = meses_com_turma[idx]
        variacao_inst_mes[(m_prev, m)] = solver.IntVar(0, num_instrutores, f'var_{m_prev}_{m}')
        solver.Add(variacao_inst_mes[(m_prev, m)] >= inst_ativos_mes[m] - inst_ativos_mes[m_prev])
        solver.Add(variacao_inst_mes[(m_prev, m)] >= inst_ativos_mes[m_prev] - inst_ativos_mes[m])

    variacao_total_equipe = solver.Sum(list(variacao_inst_mes.values()))

    # Objetivo
    # Nota: Σy[i,m] foi removido — penalizava instrutores ativos em muitos meses,
    # incentivando concentração de carga no tempo (oposto à uniformidade desejada).
    peso_suavizacao_temporal = max(1, parametros.peso_instrutores)
    termos_objetivo = [
        parametros.peso_spread * spread_v,
        parametros.peso_instrutores * solver.Sum(ativo),
        parametros.peso_spread_mensal * solver.Sum([spread_mes_inst[i] for i in range(num_instrutores)]),
        peso_suavizacao_temporal * variacao_total_equipe
    ]
    solver.Minimize(solver.Sum(termos_objetivo))

    # Resolver
    status = solver.Solve()
    if status not in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
        print(f"  Subproblema {habilidade}: status {status} (falha)")
        return None, None

    print(f"  Subproblema {habilidade}: status {status}, spread={spread_v.solution_value()}")
    print(f"  Variação total da equipe entre meses: {variacao_total_equipe.solution_value()}")

    # Extrair atribuições
    atribuicoes = []
    for i in range(num_instrutores):
        for t in range(num_turmas):
            if x[i, t].solution_value() > 0.5:
                atribuicoes.append({
                    'instrutor': instrutores[i],
                    'turma': turmas[t]
                })

    desvio_real = int(spread_v.solution_value())
    return atribuicoes, desvio_real
