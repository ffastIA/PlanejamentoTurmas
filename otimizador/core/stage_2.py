"""
Stage 2: Alocação de Instrutores — Modelo Direto por Turma

Versão 5.4 — Adição de R2b (consolidação mensal):
  - Nova restrição soft via variáveis y_im (instrutor ativo no mês m)
  - Penalidade no objetivo: peso_instrutores × Σ y_im
  - Força consolidação de turmas nos meses com baixa demanda,
    evitando que 1 turma/instrutor seja a solução ótima quando
    o pool tem instrutores sobrando.
  - Correção do problema: Jan/26 e Fev/26 com 6 instrutores
    para 6 turmas (deveria ser 1 instrutor).
  - Todo o restante da v5.3 preservado integralmente.
"""

from ortools.linear_solver import pywraplp
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
import math

from ..data_models import Projeto, Turma, Instrutor, ParametrosOtimizacao
from ..utils import calcular_meses_ativos


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def otimizar_atribuicao_e_carga(
    cronograma_estagio1: List[Dict],
    projetos: List[Projeto],
    meses: List[str],
    meses_ferias_idx: List[int],
    parametros: ParametrosOtimizacao
) -> Dict[str, Any]:

    print("\n" + "=" * 80)
    print("STAGE 2: ALOCAÇÃO DE INSTRUTORES — Modelo Direto (v5.4)")
    print("=" * 80)

    if not pywraplp.Solver.CreateSolver('SCIP'):
        return {"status": "falha", "erro": "Solver SCIP não encontrado"}

    num_meses = len(meses)

    # =========================================================================
    # 1. CRIAÇÃO DAS TURMAS
    # =========================================================================
    turmas_objetos: List[Turma] = []
    for item in cronograma_estagio1:
        hab = str(item.get('habilidade', '')).upper()
        if hab not in ['PROG', 'ROBOTICA']:
            print(f"  [AVISO] Habilidade inválida '{hab}' — ignorado.")
            continue
        for _ in range(item['qtd']):
            turmas_objetos.append(Turma(
                id=len(turmas_objetos),
                projeto=item['projeto_nome'],
                habilidade=hab,
                mes_inicio=item['mes_inicio'],
                duracao=item['duracao']
            ))

    num_turmas_total = len(turmas_objetos)
    if num_turmas_total == 0:
        return {"status": "falha", "erro": "Nenhuma turma para alocar"}

    turmas_prog = [t for t in turmas_objetos if t.habilidade == 'PROG']
    turmas_rob  = [t for t in turmas_objetos if t.habilidade == 'ROBOTICA']

    print(f"\n  Total de turmas: {num_turmas_total}")
    print(f"    PROG:     {len(turmas_prog)}")
    print(f"    ROBOTICA: {len(turmas_rob)}")

    # =========================================================================
    # 2. DIMENSIONAMENTO DO POOL
    # =========================================================================
    pool_prog = _dimensionar_pool(
        turmas_prog, meses_ferias_idx, num_meses,
        parametros.capacidade_max_instrutor, 'PROG'
    )
    pool_rob = _dimensionar_pool(
        turmas_rob, meses_ferias_idx, num_meses,
        parametros.capacidade_max_instrutor, 'ROBOTICA'
    )

    instrutores: List[Instrutor] = []
    for k in range(pool_prog):
        instrutores.append(Instrutor(
            id=f"PROG_{k + 1}",
            habilidade='PROG',
            capacidade=parametros.capacidade_max_instrutor,
            laboratorio_id="LAB_PADRAO"
        ))
    for k in range(pool_rob):
        instrutores.append(Instrutor(
            id=f"ROB_{k + 1}",
            habilidade='ROBOTICA',
            capacidade=parametros.capacidade_max_instrutor,
            laboratorio_id="LAB_PADRAO"
        ))

    print(f"\n  Pool de instrutores: {len(instrutores)}")
    print(f"    PROG:     {pool_prog}")
    print(f"    ROBOTICA: {pool_rob}")

    # =========================================================================
    # 3. RESOLVER SUBPROBLEMAS INDEPENDENTES
    # =========================================================================
    atribuicoes_prog, desvio_prog = _resolver_subproblema(
        habilidade='PROG',
        turmas=turmas_prog,
        instrutores=[i for i in instrutores if i.habilidade == 'PROG'],
        meses=meses,
        meses_ferias_idx=meses_ferias_idx,
        parametros=parametros
    )

    atribuicoes_rob, desvio_rob = _resolver_subproblema(
        habilidade='ROBOTICA',
        turmas=turmas_rob,
        instrutores=[i for i in instrutores if i.habilidade == 'ROBOTICA'],
        meses=meses,
        meses_ferias_idx=meses_ferias_idx,
        parametros=parametros
    )

    # =========================================================================
    # 4. CONSOLIDAR RESULTADOS
    # =========================================================================
    if atribuicoes_prog is None and atribuicoes_rob is None:
        return {
            "status": "falha",
            "erro":   "Nenhum subproblema encontrou solução viável."
        }

    atribuicoes_total = []
    if atribuicoes_prog:
        atribuicoes_total.extend(atribuicoes_prog)
    if atribuicoes_rob:
        atribuicoes_total.extend(atribuicoes_rob)

    desvio_max = max(
        desvio_prog if desvio_prog is not None else 0,
        desvio_rob  if desvio_rob  is not None else 0
    )

    inst_prog_ativos = len({
        a['instrutor'].id for a in atribuicoes_total
        if a['instrutor'].habilidade == 'PROG'
    })
    inst_rob_ativos = len({
        a['instrutor'].id for a in atribuicoes_total
        if a['instrutor'].habilidade == 'ROBOTICA'
    })

    print(f"\n[✓] Resultados Stage 2:")
    print(f"  Atribuições totais:   {len(atribuicoes_total)}")
    print(f"  Instrutores PROG:     {inst_prog_ativos}")
    print(f"  Instrutores ROBOTICA: {inst_rob_ativos}")
    print(f"  Desvio PROG:          {desvio_prog}")
    print(f"  Desvio ROBOTICA:      {desvio_rob}")
    print(f"  Desvio máximo:        {desvio_max}")

    return {
        "status":                  "sucesso",
        "atribuicoes":             atribuicoes_total,
        "turmas":                  turmas_objetos,
        "spread_carga":            desvio_max,
        "capacidade_max_instrutor": parametros.capacidade_max_instrutor,
        "spread_detalhado": {
            "PROG": desvio_prog if desvio_prog is not None else 0,
            "ROB":  desvio_rob  if desvio_rob  is not None else 0
        }
    }


# =============================================================================
# DIMENSIONAMENTO DO POOL
# =============================================================================

def _dimensionar_pool(
    turmas: List[Turma],
    meses_ferias_idx: List[int],
    num_meses: int,
    capacidade: int,
    habilidade: str
) -> int:
    """
    Calcula o tamanho do pool baseado no pico real de demanda
    mensal + margem de 30%.
    """
    if not turmas:
        return 0

    demanda_por_mes: Dict[int, int] = defaultdict(int)
    for t in turmas:
        for m in calcular_meses_ativos(
            t.mes_inicio, t.duracao, meses_ferias_idx, num_meses
        ):
            demanda_por_mes[m] += 1

    if not demanda_por_mes:
        return math.ceil(len(turmas) / capacidade) + 2

    pico   = max(demanda_por_mes.values())
    minimo = math.ceil(pico / capacidade)
    pool   = minimo + max(2, math.ceil(minimo * 0.30))

    print(
        f"\n  Pool {habilidade}: pico={pico} turmas/mês → "
        f"mínimo={minimo} instrutores → pool={pool} (margem 30%)"
    )
    return pool


# =============================================================================
# SUBPROBLEMA POR HABILIDADE
# =============================================================================

def _resolver_subproblema(
    habilidade: str,
    turmas: List[Turma],
    instrutores: List[Instrutor],
    meses: List[str],
    meses_ferias_idx: List[int],
    parametros: ParametrosOtimizacao
) -> Tuple[Optional[List[Dict]], Optional[int]]:
    """
    Resolve o subproblema de alocação para uma habilidade.

    MUDANÇAS v5.4:
    Adição de R2b — consolidação mensal via y_im:

      y_im ∈ {0,1} — instrutor i tem ao menos 1 turma ativa no mês m

      Derivação:
        y_im >= x[i,t] / n_turmas_no_mes_m  ∀ t ativo em m
        → y_im = 1 se qualquer x[i,t] = 1 para t ativo em m
        → y_im = 0 se nenhuma turma de i está ativa em m

      Penalidade no objetivo:
        peso_instrutores × Σ_{i,m} y_im
        → solver prefere concentrar turmas em menos instrutores
          por mês, evitando 1 turma/instrutor quando possível

      Efeito corrigido:
        Jan/26: 6 turmas DD1 → 1 instrutor (não 6)
        pois: 6 × peso_instrutores × y_im(inst1,jan)
              < 6 × peso_instrutores × Σ y_im(inst_k,jan) para k=1..6
    """

    if not turmas:
        print(f"\n  [{habilidade}] Sem turmas — ignorado.")
        return [], 0

    if not instrutores:
        print(f"\n  [{habilidade}] Pool vazio.")
        return None, None

    print(f"\n{'=' * 60}")
    print(f"  Subproblema: {habilidade}")
    print(
        f"  Turmas: {len(turmas)} | "
        f"Instrutores no pool: {len(instrutores)}"
    )

    solver = pywraplp.Solver.CreateSolver('SCIP')
    solver.SetTimeLimit(parametros.timeout_segundos * 1000)

    num_meses  = len(meses)
    num_turmas = len(turmas)
    num_inst   = len(instrutores)

    meses_letivos = [
        m for m in range(num_meses)
        if m not in meses_ferias_idx
    ]

    # Pré-calcular meses ativos por turma
    meses_ativos_turma: Dict[int, List[int]] = {}
    for t_idx, t in enumerate(turmas):
        meses_ativos_turma[t_idx] = calcular_meses_ativos(
            t.mes_inicio, t.duracao, meses_ferias_idx, num_meses
        )

    # Pré-calcular turmas ativas por mês
    turmas_no_mes: Dict[int, List[int]] = defaultdict(list)
    for t_idx, ma in meses_ativos_turma.items():
        for m in ma:
            turmas_no_mes[m].append(t_idx)

    # Log de projetos presentes
    projetos_presentes: Dict[str, int] = defaultdict(int)
    for t in turmas:
        projetos_presentes[t.projeto.split('_Onda')[0]] += 1
    print(f"  Projetos com turmas {habilidade}:")
    for pai, qtd in sorted(projetos_presentes.items()):
        print(f"    {pai}: {qtd} turmas")

    # =========================================================================
    # VARIÁVEIS PRINCIPAIS
    # =========================================================================

    # x[i, t] — instrutor i ministra turma t
    x = {}
    for i in range(num_inst):
        for t in range(num_turmas):
            x[i, t] = solver.BoolVar(f'x_{i}_{t}')

    # ativo[i] — instrutor recebeu ao menos 1 turma (global)
    ativo = [solver.BoolVar(f'ativo_{i}') for i in range(num_inst)]

    # spread
    max_carga = solver.IntVar(0, num_turmas, 'max_carga')
    min_carga = solver.IntVar(0, num_turmas, 'min_carga')
    spread_v  = solver.IntVar(0, num_turmas, 'spread')

    # =========================================================================
    # VARIÁVEIS R2b — y_im: instrutor i ativo no mês m  (NOVO v5.4)
    # =========================================================================
    y = {}
    for i in range(num_inst):
        for m in meses_letivos:
            t_no_mes = turmas_no_mes.get(m, [])
            if t_no_mes:
                y[i, m] = solver.BoolVar(f'y_{i}_{m}')

    # =========================================================================
    # RESTRIÇÕES
    # =========================================================================

    # R1: Cobertura — cada turma tem exatamente 1 instrutor
    for t in range(num_turmas):
        solver.Add(
            solver.Sum([x[i, t] for i in range(num_inst)]) == 1
        )

    # R2: Capacidade mensal — carga ≤ capacidade_max por mês letivo
    for i in range(num_inst):
        for m in meses_letivos:
            t_no_mes = turmas_no_mes.get(m, [])
            if t_no_mes:
                solver.Add(
                    solver.Sum([x[i, t] for t in t_no_mes])
                    <= parametros.capacidade_max_instrutor
                )

    # R2b: Derivação de y_im — NOVO v5.4
    # y[i,m] = 1 ↔ instrutor i tem ao menos 1 turma ativa no mês m
    #
    # Formulação:
    #   y[i,m] >= x[i,t] / n   ∀ t ativo em m  → y[i,m]*n >= x[i,t]
    #   y[i,m] <= Σ x[i,t]     (se nenhuma turma → y=0)
    for i in range(num_inst):
        for m in meses_letivos:
            t_no_mes = turmas_no_mes.get(m, [])
            if not t_no_mes or (i, m) not in y:
                continue

            n = len(t_no_mes)

            # y[i,m] >= x[i,t] / n  →  y[i,m] * n >= x[i,t]
            for t in t_no_mes:
                solver.Add(y[i, m] * n >= x[i, t])

            # y[i,m] <= Σ x[i,t]  (y só pode ser 1 se há turma)
            solver.Add(
                y[i, m] <= solver.Sum([x[i, t] for t in t_no_mes])
            )

    # R3: Férias — sem turmas em meses de férias
    for i in range(num_inst):
        for m in meses_ferias_idx:
            t_no_mes = turmas_no_mes.get(m, [])
            if t_no_mes:
                solver.Add(
                    solver.Sum([x[i, t] for t in t_no_mes]) == 0
                )

    # R4: Ativação global
    for i in range(num_inst):
        carga_total = solver.Sum([x[i, t] for t in range(num_turmas)])
        solver.Add(carga_total <= num_turmas * ativo[i])
        solver.Add(carga_total >= ativo[i])

    # R5: Spread sobre carga total
    for i in range(num_inst):
        carga_total = solver.Sum([x[i, t] for t in range(num_turmas)])
        solver.Add(max_carga >= carga_total)
        solver.Add(
            min_carga <= carga_total + (1 - ativo[i]) * num_turmas
        )
    solver.Add(spread_v == max_carga - min_carga)

    # =========================================================================
    # FUNÇÃO OBJETIVO — ESTENDIDA v5.4
    #
    # Termo 1: peso_spread × spread_v
    #          homogeneidade de carga total entre instrutores
    #
    # Termo 2: peso_instrutores × Σ ativo[i]
    #          minimiza instrutores usados no período todo
    #
    # Termo 3 (NOVO): peso_instrutores × Σ y[i,m]   ← R2b
    #          minimiza instrutores ativos por mês
    #          força consolidação: 6 turmas em 1 instrutor/mês
    #          custa 1 × peso vs. 6 turmas em 6 instrutores/mês
    #          que custa 6 × peso → solver consolida
    # =========================================================================
    termos_objetivo = [
        parametros.peso_spread    * spread_v,
        parametros.peso_instrutores * solver.Sum(ativo)
    ]

    if y:
        termos_objetivo.append(
            parametros.peso_instrutores
            * solver.Sum(list(y.values()))
        )

    solver.Minimize(solver.Sum(termos_objetivo))

    # =========================================================================
    # RESOLUÇÃO
    # =========================================================================
    print(f"  Resolvendo subproblema {habilidade}...")
    status = solver.Solve()

    if status not in [
        pywraplp.Solver.OPTIMAL,
        pywraplp.Solver.FEASIBLE
    ]:
        print(f"  [ERRO] Subproblema {habilidade} sem solução viável.")
        return None, None

    status_str = (
        "ÓTIMO" if status == pywraplp.Solver.OPTIMAL else "VIÁVEL"
    )
    print(f"  ✓ Solução {habilidade} encontrada! [{status_str}]")

    # =========================================================================
    # EXTRAÇÃO DAS ATRIBUIÇÕES
    # =========================================================================
    atribuicoes: List[Dict] = []
    for i in range(num_inst):
        for t_idx in range(num_turmas):
            if x[i, t_idx].solution_value() > 0.5:
                atribuicoes.append({
                    'instrutor': instrutores[i],
                    'turma':     turmas[t_idx]
                })

    # ── Estatísticas ─────────────────────────────────────────────────────────
    desvio_real = int(spread_v.solution_value())
    inst_ativos = sum(
        1 for i in range(num_inst)
        if ativo[i].solution_value() > 0.5
    )

    cargas = [
        int(sum(x[i, t].solution_value() for t in range(num_turmas)))
        for i in range(num_inst)
        if ativo[i].solution_value() > 0.5
    ]
    if cargas:
        print(f"\n  Distribuição de carga {habilidade}:")
        print(
            f"    Min: {min(cargas)} | Max: {max(cargas)} | "
            f"Média: {sum(cargas) / len(cargas):.1f} turmas/instrutor"
        )

    # Verificação da consolidação mensal (R2b)
    print(f"\n  Verificação de consolidação mensal {habilidade}:")
    for m in sorted(meses_letivos):
        t_no_mes = turmas_no_mes.get(m, [])
        if not t_no_mes:
            continue
        inst_no_mes = sum(
            1 for i in range(num_inst)
            if any(
                x[i, t].solution_value() > 0.5
                for t in t_no_mes
            )
        )
        n_turmas_mes = len(t_no_mes)
        minimo_teorico = math.ceil(
            n_turmas_mes / parametros.capacidade_max_instrutor
        )
        ok = "✓" if inst_no_mes <= minimo_teorico + 1 else "⚠"
        print(
            f"    {ok} {meses[m]}: {n_turmas_mes} turmas → "
            f"{inst_no_mes} instrutores "
            f"(mín teórico: {minimo_teorico})"
        )

    # Distribuição por projeto
    print(f"\n  Atribuições por projeto {habilidade}:")
    proj_inst: Dict[str, set] = defaultdict(set)
    for atr in atribuicoes:
        pai = atr['turma'].projeto.split('_Onda')[0]
        proj_inst[pai].add(atr['instrutor'].id)
    for pai, inst_set in sorted(proj_inst.items()):
        print(
            f"    {pai}: {len(inst_set)} instrutor(es) → "
            f"{sorted(inst_set)}"
        )

    print(f"\n  Instrutores ativos ({habilidade}): {inst_ativos}")
    print(f"  Spread {habilidade}:                {desvio_real}")
    print(f"  Atribuições {habilidade}:            {len(atribuicoes)}")

    return atribuicoes, desvio_real