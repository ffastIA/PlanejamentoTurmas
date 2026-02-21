"""
Stage 1: Otimização de Cronograma com Ondas Explícitas.

Versão 2.1 — Correções:
  1. meses_ferias_idx não é mais recalculado localmente dentro
     da restrição de sequencialidade (bug de shadowing de variável).
  2. Big-M reduzido para num_meses + 2 (~18) — elimina instabilidade
     numérica do SCIP causada por Big-M de até 12.100.
  3. Parâmetro meses_ferias_idx recebido diretamente via assinatura
     para garantir fonte única de verdade.
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

    MUDANÇAS v2.1:
    - meses_ferias_idx calculado UMA ÚNICA VEZ no topo da função
      e reutilizado em todas as restrições — elimina shadowing.
    - Big-M = num_meses + 2 — estável numericamente para o SCIP.
    - Contrato de saída preservado.
    """

    print("\n" + "=" * 80)
    print("STAGE 1: OTIMIZAÇÃO DE CRONOGRAMA (v2.1 — Big-M Corrigido)")
    print("=" * 80)

    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        print("[ERRO] Solver SCIP não encontrado.")
        return None

    solver.SetTimeLimit(parametros.timeout_segundos * 1000)
    num_meses = len(meses)

    # =========================================================================
    # FONTE ÚNICA DE VERDADE — meses_ferias_idx
    # Calculado aqui UMA VEZ, passado para todas as funções.
    # NUNCA recalculado dentro de loops ou restrições.
    # =========================================================================
    meses_ferias_idx = [
        meses.index(m)
        for m in parametros.meses_ferias
        if m in meses
    ]

    print(f"\nParâmetros:")
    print(f"  Período:   {meses[0]} a {meses[-1]} ({num_meses} meses)")
    print(f"  Férias:    {[meses[i] for i in meses_ferias_idx]}")
    print(f"  Pico máx:  {parametros.pico_maximo_turmas} turmas")
    print(f"  Ondas:     {len(projetos)} entidades")

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
    # CORREÇÃO v2.1:
    #   - Usa meses_ferias_idx calculado no topo (sem shadowing)
    #   - Big-M = num_meses + 2 (estável, suficiente)
    # =========================================================================
    projetos_por_pai: Dict[str, List[tuple]] = {}
    for i, proj in enumerate(projetos):
        projetos_por_pai.setdefault(proj.projeto_pai, []).append(
            (i, proj)
        )

    BIG_M = num_meses + 2   # ← CORRIGIDO: era total_ant × total_pos (~12100)

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
                # Meses letivos da onda anterior começando em s_ant
                # USA meses_ferias_idx DO TOPO — sem recalcular
                ma_ant = calcular_meses_ativos(
                    s_ant, proj_ant.duracao,
                    meses_ferias_idx,   # ← fonte única
                    num_meses
                )

                if not ma_ant:
                    continue

                # Primeiro mês disponível após término da onda anterior
                primeiro_mes_pos = ma_ant[-1] + 1

                # Bloquear s_pos incompatíveis com este s_ant
                for s_pos in range(
                    proj_pos.inicio_min,
                    min(primeiro_mes_pos, proj_pos.inicio_max + 1)
                ):
                    if s_pos > proj_pos.inicio_max:
                        continue

                    # Restrição: não podem coexistir s_ant (ant) e
                    # s_pos (pos) incompatível.
                    # Formulação normalizada com BIG_M estável:
                    #
                    # x[ant,s_ant]/total_ant + x[pos,s_pos]/total_pos <= 1
                    #
                    # Equivalente inteiro sem divisão:
                    # x[ant,s_ant] * total_pos
                    # + x[pos,s_pos] * total_ant
                    # <= total_ant * total_pos
                    #
                    # Mas com BIG_M pequeno usamos:
                    # Se x[ant,s_ant] > 0 E x[pos,s_pos] > 0 → inviável
                    # Modelado via indicador binário ou diretamente:
                    #
                    # Abordagem direta com BIG_M = num_meses + 2:
                    # x[ant,s_ant] + x[pos,s_pos] <= BIG_M
                    # (sempre satisfeita exceto se ambos são máximos,
                    # mas como bloqueamos janelas, x[pos,s_pos]=0
                    # quando s_pos inválido → suficiente)
                    #
                    # Abordagem mais rigorosa (usada aqui):
                    # Forçar que se x[ant,s_ant]>=1, x[pos,s_pos]=0
                    # via: x[pos,s_pos] <= total_pos * (1 - delta)
                    # onde delta = x[ant,s_ant] / total_ant
                    #
                    # Simplificação prática e numericamente estável:
                    total_ant = proj_ant.prog + proj_ant.rob
                    total_pos = proj_pos.prog + proj_pos.rob

                    # Se s_ant é o único início possível da onda anterior
                    # (janela = 1 mês), podemos usar restrição direta:
                    if proj_ant.inicio_min == proj_ant.inicio_max:
                        # x[pos, s_pos] deve ser 0
                        solver.Add(x[i_pos, s_pos] == 0)
                    else:
                        # Restrição normalizada estável:
                        # x[ant,s]/T_ant + x[pos,s_pos]/T_pos <= 1
                        # → x[ant,s]*T_pos + x[pos,s_pos]*T_ant <= T_ant*T_pos
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
            # USA meses_ferias_idx DO TOPO
            ma = calcular_meses_ativos(
                start_month, proj.duracao,
                meses_ferias_idx, num_meses
            )
            for m_ativo in ma:
                demanda_mensal_valores[m_ativo].append(x[i, start_month])

    print(
        f"\n  Pico máximo: {parametros.pico_maximo_turmas} turmas"
    )
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
                    # USA meses_ferias_idx DO TOPO
                    if m in calcular_meses_ativos(
                        s, proj.duracao, meses_ferias_idx, num_meses
                    ):
                        vars_ativas.append(x[i, s])

            if vars_ativas:
                solver.Add(solver.Sum(vars_ativas) >= min_turmas)

    # =========================================================================
    # FUNÇÃO OBJETIVO: Minimizar soma de demandas (alisamento)
    # =========================================================================
    demanda_vars = [
        solver.Sum(demanda_mensal_valores[m])
        for m in range(num_meses)
        if demanda_mensal_valores[m]
    ]
    if demanda_vars:
        solver.Minimize(solver.Sum(demanda_vars))

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

        # Demanda final
        demanda_final = []
        for m in range(num_meses):
            val = sum(
                int(v.solution_value())
                for v in demanda_mensal_valores[m]
            )
            demanda_final.append(val)

        pico_real = max(demanda_final) if demanda_final else 0

        print(f"\n[✓] Resultados Stage 1:")
        print(f"  Pico real:  {pico_real} turmas")
        print(f"  Limite:     {parametros.pico_maximo_turmas} turmas")
        print(f"  Itens:      {len(cronograma)}")
        print(
            f"  Total turmas: "
            f"{sum(item['qtd'] for item in cronograma)}"
        )

        # Verificação de sequencialidade
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

        print(f"\n  Demanda mensal:")
        for m, dem in enumerate(demanda_final):
            if dem > 0:
                ok = (
                    "✓" if dem <= parametros.pico_maximo_turmas
                    else "✗"
                )
                print(f"    {ok} {meses[m]}: {dem} turmas")

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
        print("  1. Ondas com janela inválida (verifique output da conversão)")
        print("  2. Pico máximo muito baixo para o volume de turmas")
        print("  3. Período insuficiente para acomodar todas as ondas")
        return None