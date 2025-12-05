# ARQUIVO: otimizador/core/stage_1.py

from collections import defaultdict
from typing import List, Dict, Optional
from ortools.sat.python import cp_model

# Import relativo para acessar modelos de dados e utils
from ..data_models import Projeto, ParametrosOtimizacao
from ..utils import calcular_meses_ativos  # GARANTA QUE ESTA IMPORTAÇÃO ESTEJA AQUI


def otimizar_curva_demanda(projetos_flexiveis: List[Projeto],
                           meses: List[str],
                           parametros: ParametrosOtimizacao) -> Optional[Dict]:
    """Otimiza o cronograma de início das turmas minimizando pico de demanda."""
    print("\n" + "=" * 80 + "\nESTÁGIO 1: Otimização da Curva de Demanda\n" + "=" * 80)
    model = cp_model.CpModel()
    num_meses = len(meses)
    meses_ferias_idx = [meses.index(m) for m in parametros.meses_ferias if m in meses]

    # --- Variáveis de Decisão (Início das turmas) ---
    inicio_vars_prog, inicio_vars_rob = {}, {}
    for proj in projetos_flexiveis:
        for m in range(proj.inicio_min, proj.inicio_max + 1):
            if proj.prog > 0: inicio_vars_prog[(proj.nome, m)] = model.NewIntVar(0, proj.prog, f'p_{proj.nome}_{m}')
            if proj.rob > 0: inicio_vars_rob[(proj.nome, m)] = model.NewIntVar(0, proj.rob, f'r_{proj.nome}_{m}')

    # --- Restrição 1: Total de Turmas por Projeto ---
    # Garante que o número total de turmas iniciadas seja igual ao necessário.
    for proj in projetos_flexiveis:
        if proj.prog > 0: model.Add(sum(
            inicio_vars_prog.get((proj.nome, m), 0) for m in range(proj.inicio_min, proj.inicio_max + 1)) == proj.prog)
        if proj.rob > 0: model.Add(sum(
            inicio_vars_rob.get((proj.nome, m), 0) for m in range(proj.inicio_min, proj.inicio_max + 1)) == proj.rob)

    # --- Restrição 2: Proibir INÍCIO de turmas nas férias ---
    # Esta é uma das regras corrigidas e fundamentais.
    for mes_ferias in meses_ferias_idx:
        for proj in projetos_flexiveis:
            # Proíbe o início de turmas de programação no mês de férias
            if proj.prog > 0 and (proj.nome, mes_ferias) in inicio_vars_prog:
                model.Add(inicio_vars_prog[(proj.nome, mes_ferias)] == 0)

            # Proíbe o início de turmas de robótica no mês de férias
            if proj.rob > 0 and (proj.nome, mes_ferias) in inicio_vars_rob:
                model.Add(inicio_vars_rob[(proj.nome, mes_ferias)] == 0)

    # --- Restrição 3: Cálculo da Demanda usando a nova lógica de "pulo" ---
    demanda_total_prog, demanda_total_rob = {}, {}
    for m in range(num_meses):
        # Para cada mês do calendário 'm', verificamos quais turmas estão ativas.
        # A lógica agora está encapsulada e corrigida em `calcular_meses_ativos`.

        demanda_m_prog_list = [
            inicio_vars_prog[(p.nome, m_i)]
            for p in projetos_flexiveis if p.prog > 0
            for m_i in range(p.inicio_min, p.inicio_max + 1)
            if m in calcular_meses_ativos(m_i, p.duracao, meses_ferias_idx, num_meses)
        ]

        demanda_m_rob_list = [
            inicio_vars_rob[(p.nome, m_i)]
            for p in projetos_flexiveis if p.rob > 0
            for m_i in range(p.inicio_min, p.inicio_max + 1)
            if m in calcular_meses_ativos(m_i, p.duracao, meses_ferias_idx, num_meses)
        ]

        demanda_total_prog[m] = model.NewIntVar(0, 300, f'dt_prog_{m}')
        demanda_total_rob[m] = model.NewIntVar(0, 300, f'dt_rob_{m}')
        model.Add(demanda_total_prog[m] == sum(demanda_m_prog_list))
        model.Add(demanda_total_rob[m] == sum(demanda_m_rob_list))

    # --- Definição do Objetivo e Resolução ---
    pico_prog = model.NewIntVar(0, 300, 'pico_prog')
    pico_rob = model.NewIntVar(0, 300, 'pico_rob')

    # Restrição de pico máximo global de turmas
    pico_consolidado_total = parametros.pico_maximo_turmas
    for m in range(num_meses):
        model.Add(demanda_total_prog[m] + demanda_total_rob[m] <= pico_consolidado_total)

    model.AddMaxEquality(pico_prog, list(demanda_total_prog.values()))
    model.AddMaxEquality(pico_rob, list(demanda_total_rob.values()))

    # Minimiza a soma dos picos de cada habilidade.
    model.Minimize(pico_prog + pico_rob)

    # --- Resolução do Modelo ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(parametros.timeout_segundos)
    print("Resolvendo modelo...")
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"\n[✓] SUCESSO! Status: {solver.StatusName(status)}")
        cronograma_flexivel = defaultdict(list)
        for proj in projetos_flexiveis:
            for hab_flag, vars_dict, hab_nome in [('prog', inicio_vars_prog, 'PROG'), ('rob', inicio_vars_rob, 'ROB')]:
                if getattr(proj, hab_flag) > 0:
                    for m in range(proj.inicio_min, proj.inicio_max + 1):
                        num_turmas = solver.Value(vars_dict.get((proj.nome, m), 0))
                        if num_turmas > 0:
                            cronograma_flexivel[proj.nome].append({'mes_inicio': m, 'num_turmas': num_turmas, 'habilidade': hab_nome})
        return {
            "cronograma": dict(cronograma_flexivel),
            "pico_max": solver.Value(pico_prog) + solver.Value(pico_rob), # Corrigido para refletir o pico real
            "pico_prog": solver.Value(pico_prog),
            "pico_rob": solver.Value(pico_rob),
            "meses_ferias": meses_ferias_idx,
            "parametros": parametros
        }
    else:
        print(f"\n[✗] FALHA: Status {solver.StatusName(status)}")
        return None