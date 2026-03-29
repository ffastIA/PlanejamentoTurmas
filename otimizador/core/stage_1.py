"""
Módulo de Otimização - Estágio 1 (Cronograma de Demanda)
Versão 5.2 - Implementação de Monotonia de Ponte (Bridge Monotony)
"""

from ortools.sat.python import cp_model
from typing import List, Dict, Optional
from ..data_models import Projeto, ParametrosOtimizacao
from ..utils import calcular_meses_ativos


def otimizar_curva_demanda(projetos: List[Projeto], meses: List[str], parametros: ParametrosOtimizacao) -> Optional[
    Dict]:
    model = cp_model.CpModel()
    num_meses = len(meses)
    pico_maximo = parametros.pico_maximo_turmas

    # Pesos
    w_alvo = parametros.peso_penalidade_alvo
    w_mono_proj = parametros.peso_monotonia_projeto
    w_mono_global = parametros.peso_spread
    p_min = parametros.presenca_minima_projeto

    # 1. VARIÁVEIS
    x = {}
    for p_idx, proj in enumerate(projetos):
        for t_idx in range(proj.num_turmas):
            x[(p_idx, t_idx)] = model.NewIntVar(proj.mes_inicio_idx, proj.mes_termino_idx, f'x_p{p_idx}_t{t_idx}')

    turmas_projeto = {}
    for p_idx in range(len(projetos)):
        for m in range(num_meses):
            turmas_projeto[(p_idx, m)] = model.NewIntVar(0, pico_maximo, f'tp_p{p_idx}_m{m}')

    # 2. MAPEAMENTO
    for p_idx, proj in enumerate(projetos):
        for m in range(num_meses):
            ativas = []
            for t_idx in range(proj.num_turmas):
                ativa = model.NewBoolVar(f'a_p{p_idx}_t{t_idx}_m{m}')
                validos = [s for s in range(proj.mes_inicio_idx, proj.mes_termino_idx + 1)
                           if m in calcular_meses_ativos(s, proj.duracao_curso, parametros.meses_ferias_idx, num_meses)]
                if validos:
                    dom = cp_model.Domain.FromValues(validos)
                    model.AddLinearExpressionInDomain(x[(p_idx, t_idx)], dom).OnlyEnforceIf(ativa)
                    model.AddLinearExpressionInDomain(x[(p_idx, t_idx)], dom.complement()).OnlyEnforceIf(ativa.Not())
                else:
                    model.Add(ativa == 0)
                ativas.append(ativa)
            model.Add(turmas_projeto[(p_idx, m)] == sum(ativas))

    # 3. PENALIDADES E MONOTONIA DE PONTE
    folga_alvo = {}
    diff_projeto = []

    for p_idx, proj in enumerate(projetos):
        for m in range(num_meses):
            if m in parametros.meses_ferias_idx:
                model.Add(turmas_projeto[(p_idx, m)] == 0)
            else:
                if proj.mes_inicio_idx <= m <= proj.mes_termino_idx:
                    model.Add(turmas_projeto[(p_idx, m)] >= p_min)
                folga = model.NewIntVar(0, proj.turmas_min_por_mes, f'f_p{p_idx}_m{m}')
                model.Add(turmas_projeto[(p_idx, m)] + folga >= proj.turmas_min_por_mes)
                folga_alvo[(p_idx, m)] = folga

            # LÓGICA DE PONTE: Compara m com o próximo mês letivo disponível
            proximo_m = m + 1
            while proximo_m < num_meses and proximo_m in parametros.meses_ferias_idx:
                proximo_m += 1

            if proximo_m < num_meses and m not in parametros.meses_ferias_idx:
                diff = model.NewIntVar(0, pico_maximo, f'd_p{p_idx}_m{m}')
                model.AddAbsEquality(diff, turmas_projeto[p_idx, m] - turmas_projeto[p_idx, proximo_m])
                diff_projeto.append(diff)

    # 4. MONOTONIA GLOBAL
    diff_global = []
    for m in range(num_meses):
        proximo_m = m + 1
        while proximo_m < num_meses and proximo_m in parametros.meses_ferias_idx:
            proximo_m += 1
        if proximo_m < num_meses and m not in parametros.meses_ferias_idx:
            t_m = sum(turmas_projeto[p_idx, m] for p_idx in range(len(projetos)))
            t_next = sum(turmas_projeto[p_idx, proximo_m] for p_idx in range(len(projetos)))
            dg = model.NewIntVar(0, pico_maximo, f'dg_m{m}')
            model.AddAbsEquality(dg, t_m - t_next)
            diff_global.append(dg)

    model.Minimize(
        sum(folga_alvo.values()) * w_alvo + sum(diff_projeto) * w_mono_proj + sum(diff_global) * w_mono_global)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = parametros.timeout_segundos
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        cronograma = []
        for (p_idx, t_idx), var in x.items():
            cronograma.append({'projeto': projetos[p_idx].nome, 'turma_id': t_idx, 'mes_inicio': solver.Value(var),
                               'habilidade': projetos[p_idx].habilidade})
        return {'cronograma': cronograma, 'status': 'sucesso', 'periodo': f"{meses[0]} a {meses[-1]}",
                'meses_ferias': parametros.meses_ferias}
    return None