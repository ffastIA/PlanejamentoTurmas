from ortools.linear_solver import pywraplp
from typing import List, Dict, Any
import numpy as np
from ..data_models import Projeto, ParametrosOtimizacao
from ..utils import calcular_meses_ativos


def otimizar_curva_demanda(projetos: List[Projeto], meses: List[str], parametros: ParametrosOtimizacao) -> Dict[
    str, Any]:
    """
    Estágio 1: Otimiza o cronograma de início das turmas.

    INTERPRETAÇÃO 1 (CORRETA): Cada mês deve ter PELO MENOS o mínimo especificado
    de turmas ativas do projeto.
    """

    print("\n" + "=" * 80)
    print("STAGE 1: OTIMIZAÇÃO DE CRONOGRAMA")
    print("=" * 80)

    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        print("[ERRO] Solver SCIP não encontrado.")
        return None

    solver.SetTimeLimit(parametros.timeout_segundos * 1000)
    num_meses = len(meses)

    print(f"\nParâmetros:")
    print(f"  Período: {meses[0]} a {meses[-1]} ({num_meses} meses)")
    print(f"  Pico máximo permitido: {parametros.pico_maximo_turmas} turmas")
    print(f"  Projetos: {len(projetos)}")

    # Variáveis: x[i, j] = número de turmas do projeto i começando no mês j
    x = {}
    for i, proj in enumerate(projetos):
        for j in range(num_meses):
            x[i, j] = solver.IntVar(0, proj.prog + proj.rob, f'x_{i}_{j}')

    # Restrição 1: Total de turmas deve ser cumprido
    for i, proj in enumerate(projetos):
        solver.Add(solver.Sum([x[i, j] for j in range(num_meses)]) == (proj.prog + proj.rob))

    # Restrição 2: Janela de início permitida
    for i, proj in enumerate(projetos):
        for j in range(num_meses):
            if j < proj.inicio_min or j > proj.inicio_max:
                solver.Add(x[i, j] == 0)

    # Restrição 3: Cálculo de demanda mensal
    demanda_mensal_valores = [[] for _ in range(num_meses)]

    for i, proj in enumerate(projetos):
        for start_month in range(num_meses):
            meses_ativos = calcular_meses_ativos(start_month, proj.duracao, parametros.meses_ferias, num_meses)

            for m_ativo in meses_ativos:
                demanda_mensal_valores[m_ativo].append(x[i, start_month])

    # Restrição 4: Pico máximo (HARD CONSTRAINT)
    print(f"\nAplicando restrição de pico máximo ({parametros.pico_maximo_turmas} turmas)...")
    for m in range(num_meses):
        if demanda_mensal_valores[m]:
            solver.Add(solver.Sum(demanda_mensal_valores[m]) <= parametros.pico_maximo_turmas)

    # Restrição 5: Mínimo de turmas por mês (INTERPRETAÇÃO 1 - CORRETA)
    print(f"Aplicando restrição de mínimo de turmas por mês...")

    for i, proj in enumerate(projetos):
        min_turmas = getattr(proj, 'min_turmas', 0)

        if min_turmas <= 0:
            continue

        # Para cada mês no período do projeto
        for m in range(proj.inicio_min, proj.mes_fim_projeto + 1):
            if m >= num_meses:
                break

            # Verificar se é mês de férias
            mes_nome = meses[m]
            is_ferias = any(ferias_mes == mes_nome for ferias_mes in parametros.meses_ferias)

            if is_ferias:
                continue

            # Calcular quais turmas estão ativas neste mês
            vars_ativas_no_mes = []

            # Uma turma que começou em 's' está ativa em 'm' se:
            # s <= m < s + duracao
            for s in range(max(0, m - proj.duracao + 1), m + 1):
                if s >= proj.inicio_min and s <= proj.inicio_max:
                    meses_ativos_da_turma = calcular_meses_ativos(s, proj.duracao, parametros.meses_ferias, num_meses)
                    if m in meses_ativos_da_turma:
                        vars_ativas_no_mes.append(x[i, s])

            if vars_ativas_no_mes:
                # RESTRIÇÃO CORRETA: Demanda em mês m >= mínimo
                solver.Add(solver.Sum(vars_ativas_no_mes) >= min_turmas)

    # Função Objetivo: Minimizar a soma de demandas (alisamento)
    demanda_vars = [solver.Sum(demanda_mensal_valores[m]) for m in range(num_meses) if demanda_mensal_valores[m]]

    if demanda_vars:
        objetivo = solver.Sum(demanda_vars)
        solver.Minimize(objetivo)

    print("\nResolvendo...")
    status = solver.Solve()

    if status in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
        print("✓ Solução encontrada!")

        cronograma = []
        for i, proj in enumerate(projetos):
            for j in range(num_meses):
                qtd = int(x[i, j].solution_value())
                if qtd > 0:
                    cronograma.append({
                        'projeto_idx': i,
                        'projeto_nome': proj.nome,
                        'mes_inicio': j,
                        'qtd': qtd,
                        'duracao': proj.duracao,
                        'habilidade': 'MISTA'
                    })

        # Calcular demanda final
        demanda_final = [0] * num_meses
        for m in range(num_meses):
            val = 0
            for item in demanda_mensal_valores[m]:
                val += int(item.solution_value())
            demanda_final[m] = val

        pico_real = max(demanda_final) if demanda_final else 0

        print(f"\n[✓] Resultados Stage 1:")
        print(f"  Pico real: {pico_real} turmas")
        print(f"  Limite: {parametros.pico_maximo_turmas} turmas")
        print(f"  Cronograma: {len(cronograma)} itens de início")
        print(f"  Total de turmas: {sum(item['qtd'] for item in cronograma)}")

        # Mostrar demanda por mês
        print(f"\nDemanda mensal:")
        for m, dem in enumerate(demanda_final):
            if dem > 0:
                status_str = "✓" if dem <= parametros.pico_maximo_turmas else "✗"
                print(f"  {status_str} {meses[m]}: {dem} turmas")

        return {
            'status': 'otimo',
            'cronograma': cronograma,
            'pico_max': pico_real,
            'demanda_mensal': demanda_final,
            'meses_ferias': [meses.index(m) for m in parametros.meses_ferias if m in meses]
        }
    else:
        print("\n[ERRO] Solver não encontrou solução viável")
        print("\nPossíveis causas:")
        print("  1. Mínimo de turmas/mês é muito alto")
        print("  2. Pico máximo é muito baixo")
        print("  3. Conflito entre mínimo e pico")
        return None