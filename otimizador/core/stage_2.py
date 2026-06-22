# otimizador/core/stage_2.py
"""
Stage 2: Atribuição de instrutores e otimização de carga — CP-SAT.

Melhorias em relação à versão anterior (pywraplp/SCIP):
  • Otimização em duas fases: Fase 1 minimiza instrutores; Fase 2 minimiza
    spread/suavização dado o número ótimo encontrado na Fase 1.
  • Quebra de simetria: instrutores idênticos ordenados por carga decrescente,
    reduzindo drasticamente o espaço de busca simétrico.
  • AddImplication / AddBoolOr para derivação de y[i,m] sem linearização.
  • OnlyEnforceIf substitui big-M nas restrições condicionais de mínimo.
  • AddMaxEquality / AddAbsEquality no lugar de pares de desigualdades manuais.
  • Busca paralela (num_search_workers=4).
"""

from ortools.sat.python import cp_model
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
import math

from ..data_models import Projeto, Turma, Instrutor, ParametrosOtimizacao
from ..utils import calcular_meses_ativos


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
    print("\n=== STAGE 2: Otimização de Atribuição e Carga (CP-SAT) ===")
    print(
        f"Parâmetros: capacidade_max={parametros.capacidade_max_instrutor}, "
        f"spread_max={parametros.spread_maximo}, "
        f"timeout={parametros.timeout_segundos}s"
    )
    print(
        f"Pesos: instrutores={parametros.peso_instrutores}, "
        f"spread={parametros.peso_spread}, "
        f"monotonia={parametros.peso_monotonia}"
    )

    # Criação das turmas a partir do cronograma do Stage 1
    turmas_objetos: List[Turma] = []
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

    turmas_prog = [t for t in turmas_objetos if t.habilidade == 'PROG']
    turmas_rob = [t for t in turmas_objetos if t.habilidade == 'ROBOTICA']

    if not turmas_objetos:
        return {"status": "falha", "erro": "Nenhuma turma para alocar"}

    print(f"Turmas criadas: PROG={len(turmas_prog)}, ROB={len(turmas_rob)}")

    pool_prog = _dimensionar_pool(
        turmas_prog, meses_ferias_idx, len(meses),
        parametros.capacidade_max_instrutor, 'PROG'
    )
    pool_rob = _dimensionar_pool(
        turmas_rob, meses_ferias_idx, len(meses),
        parametros.capacidade_max_instrutor, 'ROBOTICA'
    )

    instrutores_prog = [
        Instrutor(
            id=f'PROG_{i+1}', habilidade='PROG',
            capacidade=parametros.capacidade_max_instrutor, laboratorio_id=None
        )
        for i in range(pool_prog)
    ]
    instrutores_rob = [
        Instrutor(
            id=f'ROB_{i+1}', habilidade='ROBOTICA',
            capacidade=parametros.capacidade_max_instrutor, laboratorio_id=None
        )
        for i in range(pool_rob)
    ]

    atribuicoes_prog, desvio_prog = _resolver_subproblema(
        'PROG', turmas_prog, instrutores_prog, meses, meses_ferias_idx, parametros
    )
    atribuicoes_rob, desvio_rob = _resolver_subproblema(
        'ROBOTICA', turmas_rob, instrutores_rob, meses, meses_ferias_idx, parametros
    )

    atribuicoes_total: List[Dict] = []
    if atribuicoes_prog:
        atribuicoes_total.extend(atribuicoes_prog)
    if atribuicoes_rob:
        atribuicoes_total.extend(atribuicoes_rob)

    desvio_max = max(
        desvio_prog if desvio_prog is not None else 0,
        desvio_rob if desvio_rob is not None else 0
    )

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
    if not turmas:
        return 0
    demanda_por_mes: Dict[int, int] = defaultdict(int)
    for turma in turmas:
        for mes in calcular_meses_ativos(
            turma.mes_inicio, turma.duracao, meses_ferias_idx, num_meses
        ):
            demanda_por_mes[mes] += 1
    pico = max(demanda_por_mes.values()) if demanda_por_mes else 0
    minimo = math.ceil(pico / capacidade)
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
    Resolve atribuição para uma habilidade em duas fases:
      Fase 1 — minimiza número de instrutores ativos.
      Fase 2 — fixa esse número e minimiza spread + suavização temporal.
    """
    if not turmas:
        print(f"  Subproblema {habilidade}: sem turmas")
        return [], 0

    num_turmas = len(turmas)
    num_inst = len(instrutores)
    num_meses = len(meses)
    meses_letivos = [m for m in range(num_meses) if m not in meses_ferias_idx]

    meses_ativos_turma = {
        t_idx: calcular_meses_ativos(
            turma.mes_inicio, turma.duracao, meses_ferias_idx, num_meses
        )
        for t_idx, turma in enumerate(turmas)
    }
    turmas_no_mes: Dict[int, List[int]] = defaultdict(list)
    for t_idx, ma in meses_ativos_turma.items():
        for mes in ma:
            turmas_no_mes[mes].append(t_idx)

    meses_com_turma = [m for m in meses_letivos if turmas_no_mes.get(m)]
    projetos_presentes = set(t.projeto for t in turmas)

    print(
        f"  Subproblema {habilidade}: turmas={num_turmas}, "
        f"instrutores={num_inst}, projetos={len(projetos_presentes)}"
    )

    # -------------------------------------------------------------------------
    # Modelo CP-SAT
    # -------------------------------------------------------------------------
    model = cp_model.CpModel()

    # x[i, t] = instrutor i atribuído à turma t
    x: Dict[Tuple[int, int], cp_model.IntVar] = {}
    for i in range(num_inst):
        for t in range(num_turmas):
            x[i, t] = model.NewBoolVar(f'x_{i}_{t}')

    # ativo[i] = 1 se instrutor i tem pelo menos uma atribuição
    ativo = [model.NewBoolVar(f'ativo_{i}') for i in range(num_inst)]

    # Carga total por instrutor como IntVar explícito
    carga_var = []
    for i in range(num_inst):
        cv = model.NewIntVar(0, num_turmas, f'carga_{i}')
        model.Add(cv == sum(x[i, t] for t in range(num_turmas)))
        carga_var.append(cv)

    # max e min de carga (para spread global)
    max_carga = model.NewIntVar(0, num_turmas, 'max_carga')
    min_carga = model.NewIntVar(0, num_turmas, 'min_carga')
    spread_v = model.NewIntVar(0, num_turmas, 'spread_v')

    # y[i, m] = instrutor i está ativo no mês m
    y: Dict[Tuple[int, int], cp_model.IntVar] = {}
    for i in range(num_inst):
        for m in meses_com_turma:
            y[i, m] = model.NewBoolVar(f'y_{i}_{m}')

    # -------------------------------------------------------------------------
    # R1: Cobertura — cada turma atribuída a exatamente um instrutor
    # -------------------------------------------------------------------------
    for t in range(num_turmas):
        model.Add(sum(x[i, t] for i in range(num_inst)) == 1)

    # -------------------------------------------------------------------------
    # R2: Capacidade mensal
    # -------------------------------------------------------------------------
    for i in range(num_inst):
        for m in meses_letivos:
            tm = turmas_no_mes.get(m, [])
            if tm:
                model.Add(
                    sum(x[i, t] for t in tm) <= parametros.capacidade_max_instrutor
                )

    # -------------------------------------------------------------------------
    # R2b: Derivação de y[i,m] via implicações (sem big-M)
    #   x[i,t]=1  →  y[i,m]=1   (AddImplication)
    #   y[i,m]=1  →  ∃t: x[i,t]=1  (AddBoolOr)
    # -------------------------------------------------------------------------
    for i in range(num_inst):
        for m in meses_com_turma:
            tm = turmas_no_mes[m]
            for t in tm:
                model.AddImplication(x[i, t], y[i, m])
            # y=1 → pelo menos um x=1 no mês
            model.AddBoolOr([x[i, t] for t in tm] + [y[i, m].Not()])

    # -------------------------------------------------------------------------
    # R3: Sem atribuições em meses de férias (redundante, mas explícito)
    # -------------------------------------------------------------------------
    for m in meses_ferias_idx:
        for t in turmas_no_mes.get(m, []):
            for i in range(num_inst):
                model.Add(x[i, t] == 0)

    # -------------------------------------------------------------------------
    # R4: Ligação ativo ↔ carga (OnlyEnforceIf, sem big-M)
    # -------------------------------------------------------------------------
    for i in range(num_inst):
        model.Add(carga_var[i] == 0).OnlyEnforceIf(ativo[i].Not())
        model.Add(carga_var[i] >= 1).OnlyEnforceIf(ativo[i])

    # -------------------------------------------------------------------------
    # R5: Spread global
    #   max_carga = max(carga_var)        via AddMaxEquality
    #   min_carga ≤ carga_var[i] se ativo  via OnlyEnforceIf
    #   (objetivo minimiza spread → min_carga sobe ao mínimo dos ativos)
    # -------------------------------------------------------------------------
    model.AddMaxEquality(max_carga, carga_var)
    for i in range(num_inst):
        model.Add(min_carga <= carga_var[i]).OnlyEnforceIf(ativo[i])
    model.Add(spread_v == max_carga - min_carga)

    # -------------------------------------------------------------------------
    # Quebra de simetria: instrutores homogêneos ordenados por carga decrescente
    # Elimina soluções equivalentes por permutação de instrutores.
    # -------------------------------------------------------------------------
    for i in range(num_inst - 1):
        model.Add(carga_var[i] >= carga_var[i + 1])

    # -------------------------------------------------------------------------
    # Spread mensal por instrutor (max - min de carga ao longo dos meses)
    # -------------------------------------------------------------------------
    max_mes_inst: Dict[int, cp_model.IntVar] = {}
    min_mes_inst: Dict[int, cp_model.IntVar] = {}
    spread_mes_inst: Dict[int, cp_model.IntVar] = {}
    carga_mes: Dict[Tuple[int, int], cp_model.IntVar] = {}

    cap = parametros.capacidade_max_instrutor
    for i in range(num_inst):
        max_mes_inst[i] = model.NewIntVar(0, cap, f'maxm_{i}')
        min_mes_inst[i] = model.NewIntVar(0, cap, f'minm_{i}')
        spread_mes_inst[i] = model.NewIntVar(0, cap, f'spm_{i}')

        cm_list = []
        for m in meses_com_turma:
            cm = model.NewIntVar(0, cap, f'cm_{i}_{m}')
            model.Add(cm == sum(x[i, t] for t in turmas_no_mes[m]))
            carga_mes[i, m] = cm
            cm_list.append(cm)

        if cm_list:
            model.AddMaxEquality(max_mes_inst[i], cm_list)
            for cm in cm_list:
                model.Add(min_mes_inst[i] <= cm).OnlyEnforceIf(ativo[i])

        model.Add(spread_mes_inst[i] == max_mes_inst[i] - min_mes_inst[i])

    # -------------------------------------------------------------------------
    # Suavização temporal da equipe (variação no tamanho da equipe entre meses)
    # -------------------------------------------------------------------------
    inst_ativos_mes: Dict[int, cp_model.IntVar] = {}
    for m in meses_com_turma:
        iam = model.NewIntVar(0, num_inst, f'iam_{m}')
        model.Add(iam == sum(y[i, m] for i in range(num_inst)))
        inst_ativos_mes[m] = iam

    variacao_inst_mes: Dict[Tuple[int, int], cp_model.IntVar] = {}
    for idx in range(1, len(meses_com_turma)):
        m_prev = meses_com_turma[idx - 1]
        m = meses_com_turma[idx]
        diff = model.NewIntVar(-num_inst, num_inst, f'diff_{m_prev}_{m}')
        model.Add(diff == inst_ativos_mes[m] - inst_ativos_mes[m_prev])
        var_v = model.NewIntVar(0, num_inst, f'var_{m_prev}_{m}')
        model.AddAbsEquality(var_v, diff)
        variacao_inst_mes[m_prev, m] = var_v

    variacao_total_equipe = model.NewIntVar(
        0, num_inst * len(meses_com_turma), 'var_total'
    )
    if variacao_inst_mes:
        model.Add(variacao_total_equipe == sum(variacao_inst_mes.values()))
    else:
        model.Add(variacao_total_equipe == 0)

    # -------------------------------------------------------------------------
    # FASE 1: minimizar número de instrutores ativos
    # -------------------------------------------------------------------------
    timeout_p1 = max(30, parametros.timeout_segundos // 3)
    timeout_p2 = parametros.timeout_segundos - timeout_p1

    model.Minimize(sum(ativo))

    solver_p1 = cp_model.CpSolver()
    solver_p1.parameters.max_time_in_seconds = timeout_p1
    solver_p1.parameters.num_search_workers = 4
    solver_p1.parameters.log_search_progress = False

    print(f"  [{habilidade}] Fase 1: minimizando instrutores (timeout={timeout_p1}s)...")
    status_p1 = solver_p1.Solve(model)

    if status_p1 not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print(f"  [{habilidade}] Fase 1 falhou (status={status_p1})")
        return None, None

    num_opt_inst = sum(solver_p1.Value(ativo[i]) for i in range(num_inst))
    label_p1 = 'ÓTIMO' if status_p1 == cp_model.OPTIMAL else 'VIÁVEL'
    print(f"  [{habilidade}] Fase 1: {num_opt_inst} instrutores [{label_p1}]")

    # -------------------------------------------------------------------------
    # FASE 2: fixar contagem de instrutores, minimizar spread e suavização
    # -------------------------------------------------------------------------
    model.Add(sum(ativo) == num_opt_inst)

    peso_suavizacao = max(1, parametros.peso_instrutores)

    obj2_vars = (
        [spread_v]
        + [spread_mes_inst[i] for i in range(num_inst)]
        + list(variacao_inst_mes.values())
    )
    obj2_coefs = (
        [parametros.peso_spread]
        + [parametros.peso_spread_mensal] * num_inst
        + [peso_suavizacao] * len(variacao_inst_mes)
    )
    model.Minimize(cp_model.LinearExpr.WeightedSum(obj2_vars, obj2_coefs))

    solver_p2 = cp_model.CpSolver()
    solver_p2.parameters.max_time_in_seconds = timeout_p2
    solver_p2.parameters.num_search_workers = 4
    solver_p2.parameters.log_search_progress = False

    print(f"  [{habilidade}] Fase 2: otimizando spread/equipe (timeout={timeout_p2}s)...")
    status_p2 = solver_p2.Solve(model)

    if status_p2 in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        final_solver = solver_p2
        label_p2 = 'ÓTIMO' if status_p2 == cp_model.OPTIMAL else 'VIÁVEL'
        print(
            f"  [{habilidade}] Fase 2: spread={final_solver.Value(spread_v)} [{label_p2}]"
        )
    else:
        print(f"  [{habilidade}] Fase 2 sem melhora — usando solução da Fase 1")
        final_solver = solver_p1

    print(
        f"  Variação total da equipe entre meses: "
        f"{final_solver.Value(variacao_total_equipe)}"
    )

    # -------------------------------------------------------------------------
    # Extração de atribuições
    # -------------------------------------------------------------------------
    atribuicoes: List[Dict] = []
    for i in range(num_inst):
        for t in range(num_turmas):
            if final_solver.Value(x[i, t]) > 0:
                atribuicoes.append({
                    'instrutor': instrutores[i],
                    'turma': turmas[t]
                })

    desvio_real = int(final_solver.Value(spread_v))
    return atribuicoes, desvio_real
