from ortools.linear_solver import pywraplp
from typing import List, Dict, Any
from ..data_models import Projeto, ParametrosOtimizacao
from ..utils import calcular_meses_ativos


def otimizar_curva_demanda(projetos: List[Projeto], meses: List[str], parametros: ParametrosOtimizacao) -> Dict[
    str, Any]:
    """
    Estágio 1: Otimiza o cronograma de início das turmas.
    Objetivo: Nivelar a demanda mensal e respeitar restrições de tempo e mínimo de atividade.
    """
    print("\nIniciando Solver (SCIP)...")
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        print("[ERRO] Solver SCIP não encontrado.")
        return None

    solver.SetTimeLimit(parametros.timeout_segundos * 1000)
    num_meses = len(meses)

    # Variáveis: x[i, j] = número de turmas do projeto i começando no mês j
    x = {}
    for i, proj in enumerate(projetos):
        for j in range(num_meses):
            x[i, j] = solver.IntVar(0, proj.prog + proj.rob, f'x_{i}_{j}')

    # Variável de pico (para minimizar o máximo)
    z = solver.IntVar(0, parametros.pico_maximo_turmas, 'z')

    # Restrição 1: Total de turmas deve ser cumprido
    for i, proj in enumerate(projetos):
        solver.Add(solver.Sum([x[i, j] for j in range(num_meses)]) == (proj.prog + proj.rob))

    # Restrição 2: Janela de início permitida
    for i, proj in enumerate(projetos):
        for j in range(num_meses):
            if j < proj.inicio_min or j > proj.inicio_max:
                solver.Add(x[i, j] == 0)

    # Restrição 3: Cálculo de demanda mensal e Limite de Pico
    demanda_mensal = [[] for _ in range(num_meses)]

    for i, proj in enumerate(projetos):
        for start_month in range(num_meses):
            # Se uma turma começa em 'start_month', em quais meses ela estará ativa?
            meses_ativos = calcular_meses_ativos(start_month, proj.duracao, parametros.meses_ferias, num_meses)

            for m_ativo in meses_ativos:
                demanda_mensal[m_ativo].append(x[i, start_month])

    for m in range(num_meses):
        if demanda_mensal[m]:
            solver.Add(solver.Sum(demanda_mensal[m]) <= z)

    # --- NOVA RESTRIÇÃO: MÍNIMO DE TURMAS POR MÊS (EXCETO FÉRIAS) ---
    print("Aplicando restrições de mínimo mensal...")

    for i, proj in enumerate(projetos):
        # Acesso seguro ao atributo min_turmas (caso namedtuple antigo esteja em cache)
        min_turmas = getattr(proj, 'min_turmas', 0)

        if min_turmas <= 0:
            continue

        # Identificar intervalo de vigência do projeto
        for m in range(proj.inicio_min, proj.mes_fim_projeto + 1):
            if m >= num_meses: break

            # EXCEÇÃO: Se for mês de férias, não aplica mínimo
            mes_nome = meses[m]
            is_ferias = False
            for ferias_mes in parametros.meses_ferias:
                if ferias_mes == mes_nome:
                    is_ferias = True
                    break

            if is_ferias:
                continue

            # Calcular quantas turmas deste projeto estão ativas no mês 'm'
            vars_ativas_no_mes = []

            start_range_min = max(0, m - proj.duracao * 2)
            start_range_max = m + 1

            for s in range(start_range_min, start_range_max):
                meses_ativos_da_turma = calcular_meses_ativos(s, proj.duracao, parametros.meses_ferias, num_meses)
                if m in meses_ativos_da_turma:
                    vars_ativas_no_mes.append(x[i, s])

            if vars_ativas_no_mes:
                # Aplica a restrição: Soma das ativas >= Mínimo Configurado
                solver.Add(solver.Sum(vars_ativas_no_mes) >= min_turmas)

    # Função Objetivo: Minimizar Pico (z)
    solver.Minimize(z)

    print("Resolvendo...")
    status = solver.Solve()

    if status in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
        print("Solução encontrada!")
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

        demanda_final = [0] * num_meses
        for m in range(num_meses):
            val = 0
            for item in demanda_mensal[m]:
                val += int(item.solution_value())
            demanda_final[m] = val

        return {
            'status': 'otimo',
            'cronograma': cronograma,
            'pico_max': int(z.solution_value()),
            'demanda_mensal': demanda_final,
            'meses_ferias': [meses.index(m) for m in parametros.meses_ferias if m in meses]
        }
    else:
        print("\n" + "!" * 60)
        print("[ERRO CRÍTICO] Otimização INVIÁVEL (Infeasible).")
        print("As restrições configuradas são matematicamente impossíveis de atender.")
        print(
            "Dica: Verifique se o 'Mínimo de turmas por mês' não é alto demais para o 'Número total de turmas' e a 'Duração'.")
        print(
            "Exemplo: Se você tem 8 turmas de 2 meses, você tem estoque para cobrir apenas 16 meses. Se o projeto dura 3 meses e exige 8 por mês, precisaria de 24 meses de estoque.")
        print("!" * 60 + "\n")
        return None