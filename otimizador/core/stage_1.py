# otimizador/core/stage_1.py
# CP-SAT — uniformidade suave da demanda com busca paralela.

from ortools.sat.python import cp_model
from typing import List, Dict, Any
from ..data_models import Projeto, ParametrosOtimizacao
from ..utils import calcular_meses_ativos

# Fator para converter peso 0.2 (cruzamento de férias) em inteiro:
# peso_variacao * _W  →  normal
# peso_variacao * 2   →  cruza férias  (0.2 * 10 = 2)
_W = 10


def otimizar_curva_demanda(
    projetos: List[Projeto],
    meses: List[str],
    parametros: ParametrosOtimizacao
) -> Dict[str, Any]:
    """
    Stage 1: Otimização de cronograma via CP-SAT.

    Minimiza desvio da demanda mensal em relação ao alvo proporcional,
    penaliza variações bruscas e quedas entre meses letivos consecutivos.
    Aceita solução OPTIMAL ou FEASIBLE.
    """

    print("\n" + "=" * 80)
    print("STAGE 1: OTIMIZAÇÃO DE CRONOGRAMA (CP-SAT)")
    print("=" * 80)

    model = cp_model.CpModel()
    num_meses = len(meses)
    pico_max = parametros.pico_maximo_turmas

    meses_ferias_idx = [
        meses.index(m) for m in parametros.meses_ferias if m in meses
    ]

    print("\nParâmetros:")
    print(f"  Período:         {meses[0]} a {meses[-1]} ({num_meses} meses)")
    print(f"  Férias:          {[meses[i] for i in meses_ferias_idx]}")
    print(f"  Pico máx:        {pico_max} turmas")
    print(f"  Ondas:           {len(projetos)} entidades")
    print(f"  Peso monotonia:  {parametros.peso_monotonia}")

    # Diagnóstico estrutural mínimo por projeto
    for proj in projetos:
        limite_superior = min(proj.mes_fim_projeto, num_meses - 1)
        meses_obrigatorios = [
            m for m in range(proj.inicio_min, limite_superior + 1)
            if m not in meses_ferias_idx
        ]
        capacidade_total = (proj.prog + proj.rob) * proj.duracao
        demanda_min = len(meses_obrigatorios) * proj.min_turmas
        if proj.min_turmas > 0 and capacidade_total < demanda_min:
            print(
                f"\n[ERRO] Inviabilidade estrutural em {proj.nome}: "
                f"capacidade={capacidade_total} < demanda mínima={demanda_min}"
            )
            return None

    # -------------------------------------------------------------------------
    # Variáveis de decisão
    # x[i, j] = turmas do projeto i iniciando no mês j
    # y[i, j] = 1 se o projeto i inicia no mês j
    # -------------------------------------------------------------------------
    x = {}
    y = {}
    for i, proj in enumerate(projetos):
        total_onda = proj.prog + proj.rob
        for j in range(num_meses):
            x[i, j] = model.NewIntVar(0, total_onda, f'x_{i}_{j}')
            y[i, j] = model.NewBoolVar(f'y_{i}_{j}')

            if proj.inicio_min <= j <= proj.inicio_max:
                model.Add(x[i, j] <= total_onda * y[i, j])
                model.Add(x[i, j] >= y[i, j])
            else:
                model.Add(x[i, j] == 0)
                model.Add(y[i, j] == 0)

    # Total por onda/projeto
    for i, proj in enumerate(projetos):
        total_onda = proj.prog + proj.rob
        model.Add(sum(x[i, j] for j in range(num_meses)) == total_onda)

    # -------------------------------------------------------------------------
    # Sequencialidade entre ondas do mesmo projeto pai
    # -------------------------------------------------------------------------
    projetos_por_pai: Dict[str, List[tuple]] = {}
    for i, proj in enumerate(projetos):
        projetos_por_pai.setdefault(proj.projeto_pai, []).append((i, proj))

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
                    s_ant, proj_ant.duracao, meses_ferias_idx, num_meses
                )
                if not ma_ant:
                    continue
                primeiro_mes_pos = ma_ant[-1] + 1

                for s_pos in range(proj_pos.inicio_min, proj_pos.inicio_max + 1):
                    if s_pos < primeiro_mes_pos:
                        model.Add(y[i_ant, s_ant] + y[i_pos, s_pos] <= 1)

    # -------------------------------------------------------------------------
    # Demanda mensal como IntVar (facilita uso em AddAbsEquality e objetivo)
    # -------------------------------------------------------------------------
    demanda_mensal_valores = [[] for _ in range(num_meses)]
    for i, proj in enumerate(projetos):
        for s in range(proj.inicio_min, proj.inicio_max + 1):
            ma = calcular_meses_ativos(s, proj.duracao, meses_ferias_idx, num_meses)
            for m in ma:
                demanda_mensal_valores[m].append(x[i, s])

    demanda_mensal_vars: Dict[int, cp_model.IntVar] = {}
    for m in range(num_meses):
        if demanda_mensal_valores[m]:
            dv = model.NewIntVar(0, pico_max, f'dem_{m}')
            model.Add(dv == sum(demanda_mensal_valores[m]))
            demanda_mensal_vars[m] = dv

    # Restrição de pico máximo
    for m, dv in demanda_mensal_vars.items():
        model.Add(dv <= pico_max)

    # -------------------------------------------------------------------------
    # Restrição de mínimo por mês (sobre turmas ativas no mês)
    # -------------------------------------------------------------------------
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
                model.Add(sum(vars_ativas) >= proj.min_turmas)
            else:
                print(
                    f"\n[ERRO] Inviabilidade em {proj.nome}: "
                    f"sem início válido que mantenha turma ativa em {meses[m]}."
                )
                return None

    # -------------------------------------------------------------------------
    # Meses monitorados e alvos variáveis
    # -------------------------------------------------------------------------
    meses_monitorados = [
        m for m in range(num_meses)
        if m not in meses_ferias_idx and m in demanda_mensal_vars
    ]

    total_demanda_ativa = sum(
        (proj.prog + proj.rob) * proj.duracao for proj in projetos
    )
    capacidade_factivel = {
        m: sum(
            proj.prog + proj.rob for proj in projetos
            if proj.inicio_min <= m <= proj.mes_fim_projeto
        )
        for m in meses_monitorados
    }
    total_factivel = sum(capacidade_factivel.values())
    if total_factivel > 0:
        fator = total_demanda_ativa / total_factivel
        alvo_por_mes = {
            m: int(round(capacidade_factivel[m] * fator))
            for m in meses_monitorados
        }
    else:
        alvo_por_mes = {m: 0 for m in meses_monitorados}

    # -------------------------------------------------------------------------
    # Pesos inteiros (_W=10 elimina o fator 0.2 fracionário)
    # -------------------------------------------------------------------------
    peso_uniformidade = max(10, int(parametros.peso_monotonia)) if parametros.peso_monotonia > 0 else 10
    peso_variacao = max(5, peso_uniformidade // 2)
    peso_monotonia_int = int(parametros.peso_monotonia)

    # -------------------------------------------------------------------------
    # Variáveis auxiliares da função objetivo
    # -------------------------------------------------------------------------

    # Desvio em relação ao alvo proporcional
    desvio_alvo: Dict[int, cp_model.IntVar] = {}
    for m in meses_monitorados:
        dv = demanda_mensal_vars[m]
        alvo = alvo_por_mes[m]
        dev = model.NewIntVar(0, pico_max + 1, f'dev_{m}')
        model.Add(dev >= dv - alvo)
        model.Add(dev >= alvo - dv)
        desvio_alvo[m] = dev

    # Penalização de quedas entre meses letivos adjacentes
    queda: Dict[int, cp_model.IntVar] = {}
    for m in range(num_meses - 1):
        if m in meses_ferias_idx or (m + 1) in meses_ferias_idx:
            continue
        if m not in demanda_mensal_vars or (m + 1) not in demanda_mensal_vars:
            continue
        q = model.NewIntVar(0, pico_max, f'queda_{m}')
        model.Add(q >= demanda_mensal_vars[m] - demanda_mensal_vars[m + 1])
        queda[m] = q

    # Variação suave entre meses monitorados consecutivos
    variacao_suave: Dict[tuple, cp_model.IntVar] = {}
    pesos_variacao_suave: Dict[tuple, int] = {}
    for idx in range(len(meses_monitorados) - 1):
        m_prev = meses_monitorados[idx]
        m = meses_monitorados[idx + 1]

        # AddAbsEquality: vs = |dem[m] - dem[m_prev]|
        diff = model.NewIntVar(-pico_max, pico_max, f'diff_{m_prev}_{m}')
        model.Add(diff == demanda_mensal_vars[m] - demanda_mensal_vars[m_prev])
        vs = model.NewIntVar(0, pico_max, f'vs_{m_prev}_{m}')
        model.AddAbsEquality(vs, diff)

        variacao_suave[(m_prev, m)] = vs
        cruza_ferias = (m - m_prev) > 1
        # Sem cruzamento: peso * _W; cruzando férias: peso * 2  (0.2 * _W = 2)
        pesos_variacao_suave[(m_prev, m)] = (
            peso_variacao * 2 if cruza_ferias else peso_variacao * _W
        )

    # -------------------------------------------------------------------------
    # Função objetivo
    # -------------------------------------------------------------------------
    obj_vars: List[cp_model.IntVar] = []
    obj_coefs: List[int] = []

    for m, dev in desvio_alvo.items():
        obj_vars.append(dev)
        obj_coefs.append(peso_uniformidade * _W)

    for k, vs in variacao_suave.items():
        obj_vars.append(vs)
        obj_coefs.append(pesos_variacao_suave[k])

    for m, q in queda.items():
        obj_vars.append(q)
        obj_coefs.append(peso_monotonia_int * _W)

    if obj_vars:
        model.Minimize(cp_model.LinearExpr.WeightedSum(obj_vars, obj_coefs))

    # -------------------------------------------------------------------------
    # Solver CP-SAT com busca paralela
    # -------------------------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = parametros.timeout_segundos
    solver.parameters.num_search_workers = 4
    solver.parameters.log_search_progress = False

    print("\nResolvendo...")
    status = solver.Solve(model)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print("\n[ERRO] Solver não encontrou solução viável.")
        print("Possíveis causas:")
        print("  1. Ondas com janela inválida")
        print("  2. Pico máximo muito baixo para o volume de turmas")
        print("  3. Período insuficiente para acomodar todas as ondas")
        print("  4. Mínimo por mês acima da capacidade estrutural da onda")
        return None

    status_str = 'ÓTIMO' if status == cp_model.OPTIMAL else 'VIÁVEL'
    print(f"✓ Solução encontrada! [{status_str}]")

    # -------------------------------------------------------------------------
    # Extração do cronograma
    # -------------------------------------------------------------------------
    cronograma = []
    for i, proj in enumerate(projetos):
        total_onda = proj.prog + proj.rob
        for j in range(num_meses):
            qtd_total = solver.Value(x[i, j])
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

    demanda_final = [
        solver.Value(demanda_mensal_vars[m]) if m in demanda_mensal_vars else 0
        for m in range(num_meses)
    ]
    pico_real = max(demanda_final) if demanda_final else 0

    # -------------------------------------------------------------------------
    # Relatório de diagnóstico
    # -------------------------------------------------------------------------
    if meses_monitorados:
        desvio_total = sum(solver.Value(desvio_alvo[m]) for m in desvio_alvo)
        variacao_total = sum(solver.Value(variacao_suave[k]) for k in variacao_suave)
        alvo_medio = sum(alvo_por_mes.values()) / len(alvo_por_mes)
        print(f"  Alvo demanda (médio): {alvo_medio:.2f}")
        print(f"  Desvio total:         {desvio_total}")
        print(f"  Variação total:       {variacao_total}")

    print(f"\n[✓] Resultados Stage 1:")
    print(f"  Pico real:    {pico_real} turmas")
    print(f"  Limite:       {pico_max} turmas")
    print(f"  Itens:        {len(cronograma)}")
    print(f"  Total turmas: {sum(item['qtd'] for item in cronograma)}")

    print("\n  Análise de monotonidade:")
    total_queda = sum(solver.Value(queda[m]) for m in queda)
    print(f"  Total de queda penalizada: {total_queda}")
    for m in sorted(queda.keys()):
        if solver.Value(queda[m]) > 0:
            print(
                f"    {meses[m]} ({demanda_final[m]}) -> "
                f"{meses[m + 1]} ({demanda_final[m + 1]}): "
                f"queda {solver.Value(queda[m])}"
            )

    print("\n  Verificação sequencialidade:")
    for pai, ondas_lista in projetos_por_pai.items():
        if len(ondas_lista) < 2:
            continue
        ondas_ord = sorted(ondas_lista, key=lambda t: t[1].onda_idx)
        for k in range(len(ondas_ord) - 1):
            i_ant, _ = ondas_ord[k]
            i_pos, _ = ondas_ord[k + 1]
            s_ant_list = [item['mes_inicio'] for item in cronograma if item['projeto_idx'] == i_ant]
            s_pos_list = [item['mes_inicio'] for item in cronograma if item['projeto_idx'] == i_pos]
            if s_ant_list and s_pos_list:
                s_a = min(s_ant_list)
                s_p = min(s_pos_list)
                ok = '✓' if s_p > s_a else '⚠'
                print(f"  {ok} {pai}: Onda{k+1}={meses[s_a]}, Onda{k+2}={meses[s_p]}")

    print("\n  Demanda mensal:")
    for m, dem in enumerate(demanda_final):
        if dem == 0:
            continue
        ok = '✓' if dem <= pico_max else '✗'
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
