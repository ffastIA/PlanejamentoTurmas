# otimizador/core/stage_1.py
# Versão final com uniformidade suave da demanda (estratégia B), corrigindo erro do OR-Tools e mantendo compatibilidade total.

from ortools.linear_solver import pywraplp
from typing import List, Dict, Any
from ..data_models import Projeto, ParametrosOtimizacao
from ..utils import calcular_meses_ativos


def otimizar_curva_demanda(
    projetos: List[Projeto],
    meses: List[str],
    parametros: ParametrosOtimizacao
) -> Dict[str, Any]:
    """
    Stage 1: Otimização de cronograma com ondas explícitas e
    uniformidade suave da demanda ao longo do tempo.

    Esta versão preserva os contratos originais do projeto e corrige:
    - limite superior de x por projeto
    - sequencialidade entre ondas do mesmo projeto pai
    - mínimo por mês aplicado sobre turmas ativas no mês
    - aceitação de solução OPTIMAL ou FEASIBLE
    """

    print("\n" + "=" * 80)
    print("STAGE 1: OTIMIZAÇÃO DE CRONOGRAMA (Uniformidade Suave)")
    print("=" * 80)

    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        print("[ERRO] Solver SCIP não encontrado.")
        return None

    solver.SetTimeLimit(parametros.timeout_segundos * 1000)
    num_meses = len(meses)

    meses_ferias_idx = [
        meses.index(m)
        for m in parametros.meses_ferias
        if m in meses
    ]

    print("\nParâmetros:")
    print(f"  Período:         {meses[0]} a {meses[-1]} ({num_meses} meses)")
    print(f"  Férias:          {[meses[i] for i in meses_ferias_idx]}")
    print(f"  Pico máx:        {parametros.pico_maximo_turmas} turmas")
    print(f"  Ondas:           {len(projetos)} entidades")
    print(f"  Peso monotonia:  {parametros.peso_monotonia}")

    # Diagnóstico estrutural mínimo por projeto
    for proj in projetos:
        limite_superior = min(proj.mes_fim_projeto, num_meses - 1)
        meses_obrigatorios = [
            m for m in range(proj.inicio_min, limite_superior + 1)
            if m not in meses_ferias_idx
        ]
        capacidade_total_de_atividade = (proj.prog + proj.rob) * proj.duracao
        demanda_minima_exigida = len(meses_obrigatorios) * proj.min_turmas

        if proj.min_turmas > 0 and capacidade_total_de_atividade < demanda_minima_exigida:
            print(
                f"\n[ERRO] Inviabilidade estrutural em {proj.nome}: "
                f"capacidade={capacidade_total_de_atividade} < "
                f"demanda mínima exigida={demanda_minima_exigida}"
            )
            return None

    # Variáveis de decisão
    # x[i, j] = quantidade de turmas do projeto i iniciando no mês j
    # y[i, j] = 1 se o projeto i tem início no mês j
    x = {}
    y = {}
    for i, proj in enumerate(projetos):
        total_onda = proj.prog + proj.rob
        for j in range(num_meses):
            x[i, j] = solver.IntVar(0, total_onda, f'x_{i}_{j}')
            y[i, j] = solver.BoolVar(f'y_{i}_{j}')

            if proj.inicio_min <= j <= proj.inicio_max:
                solver.Add(x[i, j] <= total_onda * y[i, j])
                solver.Add(x[i, j] >= y[i, j])
            else:
                solver.Add(x[i, j] == 0)
                solver.Add(y[i, j] == 0)

    # Restrição total por onda/projeto
    for i, proj in enumerate(projetos):
        total_onda = proj.prog + proj.rob
        solver.Add(
            solver.Sum([x[i, j] for j in range(num_meses)]) == total_onda
        )

    # Agrupar por projeto pai
    projetos_por_pai: Dict[str, List[tuple]] = {}
    for i, proj in enumerate(projetos):
        projetos_por_pai.setdefault(proj.projeto_pai, []).append((i, proj))

    BIG_M = num_meses + 2

    # Sequencialidade entre ondas do mesmo projeto pai
    for pai, ondas_lista in projetos_por_pai.items():
        ondas_ord = sorted(ondas_lista, key=lambda t: t[1].onda_idx)

        if len(ondas_ord) < 2:
            continue

        print(f"\n  Sequencialidade: {pai} ({len(ondas_ord)} ondas)")

        for k in range(len(ondas_ord) - 1):
            i_ant, proj_ant = ondas_ord[k]
            i_pos, proj_pos = ondas_ord[k + 1]

            for s_ant in range(proj_ant.inicio_min, proj_ant.inicio_max + 1):
                ma_ant = calcular_meses_ativos(
                    s_ant,
                    proj_ant.duracao,
                    meses_ferias_idx,
                    num_meses
                )
                if not ma_ant:
                    continue

                primeiro_mes_pos = ma_ant[-1] + 1

                for s_pos in range(proj_pos.inicio_min, proj_pos.inicio_max + 1):
                    if s_pos < primeiro_mes_pos:
                        solver.Add(y[i_ant, s_ant] + y[i_pos, s_pos] <= 1)

    # Demanda mensal
    demanda_mensal_valores = [[] for _ in range(num_meses)]

    for i, proj in enumerate(projetos):
        for start_month in range(proj.inicio_min, proj.inicio_max + 1):
            ma = calcular_meses_ativos(
                start_month,
                proj.duracao,
                meses_ferias_idx,
                num_meses
            )
            for m_ativo in ma:
                demanda_mensal_valores[m_ativo].append(x[i, start_month])

    demanda_expr_por_mes = []
    for m in range(num_meses):
        if demanda_mensal_valores[m]:
            demanda_expr_por_mes.append(solver.Sum(demanda_mensal_valores[m]))
        else:
            demanda_expr_por_mes.append(0)

    print(f"\n  Pico máximo: {parametros.pico_maximo_turmas} turmas")
    for m in range(num_meses):
        if demanda_mensal_valores[m]:
            solver.Add(demanda_expr_por_mes[m] <= parametros.pico_maximo_turmas)

    # Restrição de mínimo por mês (sobre turmas ativas no mês)
    for i, proj in enumerate(projetos):
        if proj.min_turmas <= 0:
            continue

        for m in range(proj.inicio_min, min(proj.mes_fim_projeto, num_meses - 1) + 1):
            if m in meses_ferias_idx:
                continue

            vars_ativas = []
            for s in range(proj.inicio_min, proj.inicio_max + 1):
                ma = calcular_meses_ativos(s, proj.duracao, meses_ferias_idx, num_meses)
                if m in ma:
                    vars_ativas.append(x[i, s])

            if vars_ativas:
                solver.Add(solver.Sum(vars_ativas) >= proj.min_turmas)
            else:
                print(
                    f"\n[ERRO] Inviabilidade estrutural em {proj.nome}: "
                    f"não existe início válido que mantenha turma ativa em {meses[m]}.")
                return None

    # Queda entre meses letivos adjacentes
    queda = {}
    for m in range(num_meses - 1):
        if m in meses_ferias_idx or (m + 1) in meses_ferias_idx:
            continue

        D_m = demanda_expr_por_mes[m] if demanda_mensal_valores[m] else 0
        D_m1 = demanda_expr_por_mes[m + 1] if demanda_mensal_valores[m + 1] else 0

        queda[m] = solver.NumVar(0, parametros.pico_maximo_turmas, f'queda_{m}')
        solver.Add(queda[m] >= D_m - D_m1)

    # Estratégia B: uniformidade suave da demanda
    meses_monitorados = [
        m for m in range(num_meses)
        if m not in meses_ferias_idx and demanda_mensal_valores[m]
    ]

    total_demanda_ativa = sum(
        (proj.prog + proj.rob) * proj.duracao for proj in projetos
    )
    alvo_demanda = (
        total_demanda_ativa / len(meses_monitorados)
        if meses_monitorados else 0
    )

    desvio_alvo = {}
    for m in meses_monitorados:
        D_m = demanda_expr_por_mes[m]
        desvio_alvo[m] = solver.NumVar(0, parametros.pico_maximo_turmas, f'desvio_alvo_{m}')
        solver.Add(desvio_alvo[m] >= D_m - alvo_demanda)
        solver.Add(desvio_alvo[m] >= alvo_demanda - D_m)

    variacao_suave = {}
    for idx in range(len(meses_monitorados) - 1):
        m_prev = meses_monitorados[idx]
        m = meses_monitorados[idx + 1]
        D_prev = demanda_expr_por_mes[m_prev]
        D_m = demanda_expr_por_mes[m]
        variacao_suave[(m_prev, m)] = solver.NumVar(
            0,
            parametros.pico_maximo_turmas,
            f'variacao_suave_{m_prev}_{m}'
        )
        solver.Add(variacao_suave[(m_prev, m)] >= D_m - D_prev)
        solver.Add(variacao_suave[(m_prev, m)] >= D_prev - D_m)

    peso_uniformidade = max(
        10,
        parametros.peso_monotonia if parametros.peso_monotonia > 0 else 10
    )
    peso_variacao = max(5, peso_uniformidade // 2)

    termos_objetivo = []
    termos_objetivo.extend([
        peso_uniformidade * desvio_alvo[m]
        for m in desvio_alvo
    ])
    termos_objetivo.extend([
        peso_variacao * variacao_suave[k]
        for k in variacao_suave
    ])
    termos_objetivo.extend([
        parametros.peso_monotonia * queda[m]
        for m in queda
    ])

    if termos_objetivo:
        solver.Minimize(solver.Sum(termos_objetivo))
    else:
        zero_obj = solver.NumVar(0, 0, 'zero_obj')
        solver.Minimize(zero_obj)

    print("\nResolvendo...")
    status_solver = solver.Solve()

    if status_solver not in [
        pywraplp.Solver.OPTIMAL,
        pywraplp.Solver.FEASIBLE
    ]:
        print("\n[ERRO] Solver não encontrou solução viável.")
        print("Possíveis causas:")
        print("  1. Ondas com janela inválida")
        print("  2. Pico máximo muito baixo para o volume de turmas")
        print("  3. Período insuficiente para acomodar todas as ondas")
        print("  4. Mínimo por mês acima da capacidade estrutural da onda")
        return None

    status_str = (
        'ÓTIMO'
        if status_solver == pywraplp.Solver.OPTIMAL
        else 'VIÁVEL'
    )
    print(f"✓ Solução encontrada! [{status_str}]")

    cronograma = []
    for i, proj in enumerate(projetos):
        total_onda = proj.prog + proj.rob
        for j in range(num_meses):
            qtd_total = int(round(x[i, j].solution_value()))
            if qtd_total <= 0:
                continue

            if total_onda > 0:
                qtd_prog = round(qtd_total * proj.prog / total_onda)
                qtd_rob = qtd_total - qtd_prog
            else:
                qtd_prog = 0
                qtd_rob = 0

            if qtd_prog > 0:
                cronograma.append({
                    'projeto_idx': i,
                    'projeto_nome': proj.nome,
                    'projeto_pai': proj.projeto_pai,
                    'onda_idx': proj.onda_idx,
                    'mes_inicio': j,
                    'qtd': qtd_prog,
                    'duracao': proj.duracao,
                    'habilidade': 'PROG'
                })

            if qtd_rob > 0:
                cronograma.append({
                    'projeto_idx': i,
                    'projeto_nome': proj.nome,
                    'projeto_pai': proj.projeto_pai,
                    'onda_idx': proj.onda_idx,
                    'mes_inicio': j,
                    'qtd': qtd_rob,
                    'duracao': proj.duracao,
                    'habilidade': 'ROBOTICA'
                })

    demanda_final = []
    for m in range(num_meses):
        val = sum(int(round(v.solution_value())) for v in demanda_mensal_valores[m])
        demanda_final.append(val)

    pico_real = max(demanda_final) if demanda_final else 0

    if meses_monitorados:
        desvio_total = sum(desvio_alvo[m].solution_value() for m in desvio_alvo)
        variacao_total = sum(variacao_suave[k].solution_value() for k in variacao_suave)
        print(f"  Alvo demanda: {alvo_demanda:.2f}")
        print(f"  Desvio total: {desvio_total:.2f}")
        print(f"  Variação total: {variacao_total:.2f}")

    print(f"\n[✓] Resultados Stage 1:")
    print(f"  Pico real:    {pico_real} turmas")
    print(f"  Limite:       {parametros.pico_maximo_turmas} turmas")
    print(f"  Itens:        {len(cronograma)}")
    print(f"  Total turmas: {sum(item['qtd'] for item in cronograma)}")

    print("\n  Análise de monotonidade:")
    total_queda = sum(queda[m].solution_value() for m in queda)
    print(f"  Total de queda penalizada: {total_queda:.2f}")
    for m in sorted(queda.keys()):
        if queda[m].solution_value() > 0:
            print(
                f"    {meses[m]} ({demanda_final[m]}) -> "
                f"{meses[m + 1]} ({demanda_final[m + 1]}): "
                f"queda {queda[m].solution_value():.2f}"
            )

    print("\n  Verificação sequencialidade:")
    for pai, ondas_lista in projetos_por_pai.items():
        if len(ondas_lista) < 2:
            continue
        ondas_ord = sorted(ondas_lista, key=lambda t: t[1].onda_idx)
        for k in range(len(ondas_ord) - 1):
            i_ant, _ = ondas_ord[k]
            i_pos, _ = ondas_ord[k + 1]
            s_ant_list = [
                item['mes_inicio'] for item in cronograma
                if item['projeto_idx'] == i_ant
            ]
            s_pos_list = [
                item['mes_inicio'] for item in cronograma
                if item['projeto_idx'] == i_pos
            ]
            if s_ant_list and s_pos_list:
                s_a = min(s_ant_list)
                s_p = min(s_pos_list)
                ok = '✓' if s_p > s_a else '⚠'
                print(f"  {ok} {pai}: Onda{k+1}={meses[s_a]}, Onda{k+2}={meses[s_p]}")

    print("\n  Demanda mensal:")
    for m, dem in enumerate(demanda_final):
        if dem == 0:
            continue
        ok = '✓' if dem <= parametros.pico_maximo_turmas else '✗'
        tendencia = ''
        if m > 0 and demanda_final[m - 1] > 0:
            if m not in meses_ferias_idx and (m - 1) not in meses_ferias_idx:
                diff = dem - demanda_final[m - 1]
                if diff > 0:
                    tendencia = f' ↑(+{diff})'
                elif diff < 0:
                    tendencia = f' ↓({diff})'
                else:
                    tendencia = ' →(=)'
        print(f"    {ok} {meses[m]}: {dem} turmas{tendencia}")

    return {
        'status': 'otimo',
        'cronograma': cronograma,
        'pico_max': pico_real,
        'demanda_mensal': demanda_final,
        'meses_ferias': meses_ferias_idx
    }