"""
Stage 1: Otimização de Cronograma com Ondas Explícitas e
         Soft Constraint de Monotonidade de Demanda.

Versão 2.2 — Adição do objetivo de picos crescentes:
  - Nova variável queda[m]: captura reduções na demanda mensal
  - Objetivo estendido: alisamento + peso_monotonia × Σ queda[m]
  - Soft constraint — não altera viabilidade, apenas orienta o solver
  - Stage 2 (v5.3) permanece 100% inalterado
  - Todos os contratos de entrada/saída preservados
"""

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
    Estágio 1: Otimiza o cronograma de início das turmas.

    MUDANÇAS v2.2 em relação à v2.1:
    - Variáveis queda[m] adicionadas para capturar D[m] - D[m+1] > 0
    - Objetivo: Σ D[m] + peso_monotonia × Σ queda[m]
    - Se peso_monotonia = 0: comportamento idêntico à v2.1
    - meses_ferias_idx: fonte única no topo (mantido da v2.1)
    - Big-M = num_meses + 2 (mantido da v2.1)
    - Contrato de saída preservado
    """

    print("\n" + "=" * 80)
    print(
        "STAGE 1: OTIMIZAÇÃO DE CRONOGRAMA "
        "(v2.2 — Picos Crescentes)"
    )
    print("=" * 80)

    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        print("[ERRO] Solver SCIP não encontrado.")
        return None

    solver.SetTimeLimit(parametros.timeout_segundos * 1000)
    num_meses = len(meses)

    # =========================================================================
    # FONTE ÚNICA DE VERDADE — meses_ferias_idx
    # Calculado UMA VEZ no topo — nunca recalculado em loops
    # =========================================================================
    meses_ferias_idx = [
        meses.index(m)
        for m in parametros.meses_ferias
        if m in meses
    ]

    print(f"\nParâmetros:")
    print(f"  Período:       {meses[0]} a {meses[-1]} ({num_meses} meses)")
    print(f"  Férias:        {[meses[i] for i in meses_ferias_idx]}")
    print(f"  Pico máx:      {parametros.pico_maximo_turmas} turmas")
    print(f"  Ondas:         {len(projetos)} entidades")
    print(f"  Peso monotonia: {parametros.peso_monotonia}")

    if parametros.peso_monotonia == 0:
        print(
            "  [INFO] peso_monotonia=0 → "
            "comportamento idêntico à v2.1 (monotonia desativada)"
        )

    # =========================================================================
    # VARIÁVEIS: x[i, j] = turmas da onda i começando no mês j
    # =========================================================================
    x = {}
    for i, proj in enumerate(projetos):
        total_onda = proj.prog + proj.rob
        for j in range(num_meses):
            x[i, j] = solver.IntVar(0, total_onda, f'x_{i}_{j}')

    # =========================================================================
    # RESTRIÇÃO 1: Total de turmas por onda
    # =========================================================================
    for i, proj in enumerate(projetos):
        total_onda = proj.prog + proj.rob
        solver.Add(
            solver.Sum([x[i, j] for j in range(num_meses)]) == total_onda
        )

    # =========================================================================
    # RESTRIÇÃO 2: Janela de início permitida
    # =========================================================================
    for i, proj in enumerate(projetos):
        for j in range(num_meses):
            if j < proj.inicio_min or j > proj.inicio_max:
                solver.Add(x[i, j] == 0)

    # =========================================================================
    # RESTRIÇÃO 3: Sequencialidade intra-projeto
    # Big-M = num_meses + 2 (estável numericamente)
    # =========================================================================
    projetos_por_pai: Dict[str, List[tuple]] = {}
    for i, proj in enumerate(projetos):
        projetos_por_pai.setdefault(proj.projeto_pai, []).append(
            (i, proj)
        )

    BIG_M = num_meses + 2

    for pai, ondas_lista in projetos_por_pai.items():
        ondas_ord = sorted(ondas_lista, key=lambda t: t[1].onda_idx)

        if len(ondas_ord) < 2:
            continue

        print(f"\n  Sequencialidade: {pai} ({len(ondas_ord)} ondas)")

        for k in range(len(ondas_ord) - 1):
            i_ant, proj_ant = ondas_ord[k]
            i_pos, proj_pos = ondas_ord[k + 1]

            for s_ant in range(
                proj_ant.inicio_min,
                proj_ant.inicio_max + 1
            ):
                ma_ant = calcular_meses_ativos(
                    s_ant, proj_ant.duracao,
                    meses_ferias_idx,
                    num_meses
                )
                if not ma_ant:
                    continue

                primeiro_mes_pos = ma_ant[-1] + 1

                for s_pos in range(
                    proj_pos.inicio_min,
                    min(primeiro_mes_pos, proj_pos.inicio_max + 1)
                ):
                    if s_pos > proj_pos.inicio_max:
                        continue

                    total_ant = proj_ant.prog + proj_ant.rob
                    total_pos = proj_pos.prog + proj_pos.rob

                    if proj_ant.inicio_min == proj_ant.inicio_max:
                        solver.Add(x[i_pos, s_pos] == 0)
                    else:
                        solver.Add(
                            x[i_ant, s_ant] * total_pos
                            + x[i_pos, s_pos] * total_ant
                            <= total_ant * total_pos
                        )

    # =========================================================================
    # RESTRIÇÃO 4: Demanda mensal e pico máximo
    # =========================================================================
    demanda_mensal_valores = [[] for _ in range(num_meses)]

    for i, proj in enumerate(projetos):
        for start_month in range(num_meses):
            ma = calcular_meses_ativos(
                start_month, proj.duracao,
                meses_ferias_idx, num_meses
            )
            for m_ativo in ma:
                demanda_mensal_valores[m_ativo].append(
                    x[i, start_month]
                )

    print(f"\n  Pico máximo: {parametros.pico_maximo_turmas} turmas")
    for m in range(num_meses):
        if demanda_mensal_valores[m]:
            solver.Add(
                solver.Sum(demanda_mensal_valores[m])
                <= parametros.pico_maximo_turmas
            )

    # =========================================================================
    # RESTRIÇÃO 5: Mínimo de turmas por mês
    # =========================================================================
    for i, proj in enumerate(projetos):
        min_turmas = getattr(proj, 'min_turmas', 0)
        if min_turmas <= 0:
            continue

        for m in range(proj.inicio_min, proj.mes_fim_projeto + 1):
            if m >= num_meses:
                break
            if m in meses_ferias_idx:
                continue

            vars_ativas = []
            for s in range(max(0, m - proj.duracao + 1), m + 1):
                if proj.inicio_min <= s <= proj.inicio_max:
                    if m in calcular_meses_ativos(
                        s, proj.duracao, meses_ferias_idx, num_meses
                    ):
                        vars_ativas.append(x[i, s])

            if vars_ativas:
                solver.Add(solver.Sum(vars_ativas) >= min_turmas)

    # =========================================================================
    # VARIÁVEIS DE QUEDA — NOVO v2.2
    #
    # queda[m] captura a redução de demanda entre mês m e mês m+1.
    # Só criada para pares de meses letivos consecutivos
    # (ignora transições para/de meses de férias).
    #
    # queda[m] >= D[m] - D[m+1]
    # queda[m] >= 0              (IntVar com lb=0)
    #
    # Efeito: o solver paga `peso_monotonia` por cada turma de
    # redução de demanda entre meses consecutivos, sendo incentivado
    # a posicionar turmas de forma que a demanda seja crescente.
    # =========================================================================
    queda = {}

    if parametros.peso_monotonia > 0:
        print("\n  Configurando soft constraint de monotonidade...")

        for m in range(num_meses - 1):
            # Pular se m ou m+1 for mês de férias
            if m in meses_ferias_idx or (m + 1) in meses_ferias_idx:
                continue

            # Só criar queda[m] se ambos os meses têm demanda potencial
            tem_demanda_m  = bool(demanda_mensal_valores[m])
            tem_demanda_m1 = bool(demanda_mensal_valores[m + 1])

            if not tem_demanda_m or not tem_demanda_m1:
                continue

            D_m  = solver.Sum(demanda_mensal_valores[m])
            D_m1 = solver.Sum(demanda_mensal_valores[m + 1])

            queda[m] = solver.IntVar(
                0,
                parametros.pico_maximo_turmas,
                f'queda_{m}'
            )

            # queda[m] >= D[m] - D[m+1]
            # Se D[m] <= D[m+1] (crescimento): queda[m] = 0 (sem custo)
            # Se D[m] >  D[m+1] (redução):     queda[m] > 0 (penalizado)
            solver.Add(queda[m] >= D_m - D_m1)

        print(
            f"  Pares de meses monitorados: {len(queda)} "
            f"(peso={parametros.peso_monotonia})"
        )
    else:
        print("\n  Monotonidade desativada (peso_monotonia=0)")

    # =========================================================================
    # FUNÇÃO OBJETIVO — ESTENDIDA v2.2
    #
    # Termo 1 (herdado v2.1): Σ D[m] — minimiza demanda total (alisamento)
    # Termo 2 (novo v2.2):    peso_monotonia × Σ queda[m]
    #                         penaliza quedas de demanda entre meses
    #
    # O solver balanceia os dois termos:
    #   - Alisamento tende a distribuir turmas uniformemente
    #   - Monotonidade tende a concentrar picos no final
    #   - O equilíbrio depende do peso relativo configurado
    # =========================================================================
    demanda_vars = [
        solver.Sum(demanda_mensal_valores[m])
        for m in range(num_meses)
        if demanda_mensal_valores[m]
    ]

    if demanda_vars:
        objetivo = solver.Sum(demanda_vars)

        if queda:
            objetivo = solver.Sum([
                objetivo,
                solver.Sum([
                    parametros.peso_monotonia * queda[m]
                    for m in queda
                ])
            ])

        solver.Minimize(objetivo)

    # =========================================================================
    # RESOLUÇÃO
    # =========================================================================
    print("\nResolvendo...")
    status_solver = solver.Solve()

    if status_solver in [
        pywraplp.Solver.OPTIMAL,
        pywraplp.Solver.FEASIBLE
    ]:
        status_str = (
            "ÓTIMO" if status_solver == pywraplp.Solver.OPTIMAL
            else "VIÁVEL"
        )
        print(f"✓ Solução encontrada! [{status_str}]")

        # ── CONSTRUÇÃO DO CRONOGRAMA ──────────────────────────────────────────
        cronograma = []
        for i, proj in enumerate(projetos):
            total_onda = proj.prog + proj.rob
            for j in range(num_meses):
                qtd_total = int(x[i, j].solution_value())
                if qtd_total == 0:
                    continue

                if total_onda > 0:
                    qtd_prog = round(qtd_total * proj.prog / total_onda)
                    qtd_rob  = qtd_total - qtd_prog
                else:
                    qtd_prog = qtd_rob = 0

                if qtd_prog > 0:
                    cronograma.append({
                        'projeto_idx':  i,
                        'projeto_nome': proj.nome,
                        'projeto_pai':  proj.projeto_pai,
                        'onda_idx':     proj.onda_idx,
                        'mes_inicio':   j,
                        'qtd':          qtd_prog,
                        'duracao':      proj.duracao,
                        'habilidade':   'PROG'
                    })
                if qtd_rob > 0:
                    cronograma.append({
                        'projeto_idx':  i,
                        'projeto_nome': proj.nome,
                        'projeto_pai':  proj.projeto_pai,
                        'onda_idx':     proj.onda_idx,
                        'mes_inicio':   j,
                        'qtd':          qtd_rob,
                        'duracao':      proj.duracao,
                        'habilidade':   'ROBOTICA'
                    })

        # Demanda final por mês
        demanda_final = []
        for m in range(num_meses):
            val = sum(
                int(v.solution_value())
                for v in demanda_mensal_valores[m]
            )
            demanda_final.append(val)

        pico_real = max(demanda_final) if demanda_final else 0

        # ── LOG DE RESULTADOS ─────────────────────────────────────────────────
        print(f"\n[✓] Resultados Stage 1:")
        print(f"  Pico real:    {pico_real} turmas")
        print(f"  Limite:       {parametros.pico_maximo_turmas} turmas")
        print(f"  Itens:        {len(cronograma)}")
        print(
            f"  Total turmas: "
            f"{sum(item['qtd'] for item in cronograma)}"
        )

        # Log da monotonidade atingida
        if queda:
            quedas_reais = {
                m: int(queda[m].solution_value())
                for m in queda
                if queda[m].solution_value() > 0
            }
            total_queda = sum(quedas_reais.values())
            print(f"\n  Análise de monotonidade:")
            print(
                f"  Quedas penalizadas: {len(quedas_reais)} mês(es) | "
                f"Total de turmas em queda: {total_queda}"
            )
            if quedas_reais:
                print("  Detalhamento de quedas:")
                for m, q in quedas_reais.items():
                    d_m  = demanda_final[m]
                    d_m1 = demanda_final[m + 1]
                    print(
                        f"    {meses[m]} ({d_m}) → "
                        f"{meses[m + 1]} ({d_m1}): "
                        f"queda de {q} turmas"
                    )
            else:
                print(
                    "  ✓ Demanda completamente monotônica "
                    "(nenhuma queda detectada)"
                )

        # Log de sequencialidade
        print(f"\n  Verificação sequencialidade:")
        for pai, ondas_lista in projetos_por_pai.items():
            if len(ondas_lista) < 2:
                continue
            ondas_ord = sorted(
                ondas_lista, key=lambda t: t[1].onda_idx
            )
            for k in range(len(ondas_ord) - 1):
                i_ant, _ = ondas_ord[k]
                i_pos, _ = ondas_ord[k + 1]
                s_ant_list = [
                    j for j in range(num_meses)
                    if int(x[i_ant, j].solution_value()) > 0
                ]
                s_pos_list = [
                    j for j in range(num_meses)
                    if int(x[i_pos, j].solution_value()) > 0
                ]
                if s_ant_list and s_pos_list:
                    s_a = min(s_ant_list)
                    s_p = min(s_pos_list)
                    ok  = "✓" if s_p > s_a else "⚠"
                    print(
                        f"  {ok} {pai}: "
                        f"Onda{k+1}={meses[s_a]}, "
                        f"Onda{k+2}={meses[s_p]}"
                    )

        # Log de demanda mensal com indicador de tendência
        print(f"\n  Demanda mensal:")
        for m, dem in enumerate(demanda_final):
            if dem == 0:
                continue
            ok = (
                "✓" if dem <= parametros.pico_maximo_turmas else "✗"
            )
            # Indicador de tendência em relação ao mês anterior letivo
            tendencia = ""
            if m > 0 and demanda_final[m - 1] > 0:
                if m not in meses_ferias_idx \
                        and (m - 1) not in meses_ferias_idx:
                    diff = dem - demanda_final[m - 1]
                    if diff > 0:
                        tendencia = f" ↑(+{diff})"
                    elif diff < 0:
                        tendencia = f" ↓({diff})"
                    else:
                        tendencia = " →(=)"
            print(
                f"    {ok} {meses[m]}: {dem} turmas{tendencia}"
            )

        return {
            'status':         'otimo',
            'cronograma':     cronograma,
            'pico_max':       pico_real,
            'demanda_mensal': demanda_final,
            'meses_ferias':   meses_ferias_idx
        }

    else:
        print("\n[ERRO] Solver não encontrou solução viável.")
        print("Possíveis causas:")
        print(
            "  1. Ondas com janela inválida "
            "(verifique output da conversão)"
        )
        print("  2. Pico máximo muito baixo para o volume de turmas")
        print(
            "  3. Período insuficiente para acomodar todas as ondas"
        )
        return None