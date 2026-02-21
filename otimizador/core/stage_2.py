"""
Estágio 2: Alocação de Instrutores por Projeto e Habilidade
Versão 5.0 - Modelo y[i,p,h] com Homogeneidade e Permanência

MUDANÇAS EM RELAÇÃO À VERSÃO ANTERIOR:
  - Variável de decisão: x[i,t] (52.800 binárias) → y[i,p,h] (1.440 binárias)
  - Objetivo: minimizar instrutores + spread → minimizar desvio de carga (L1)
  - Permanência: instrutor vinculado ao projeto inteiro, não à turma individual
  - Compartilhamento: instrutor pode atuar em projetos distintos em meses diferentes
  - Férias: carga zero (instrutor ativo, L[i,m] = 0 em meses de férias)
  - PROG e ROB resolvidos como subproblemas independentes
  - Expansão determinística y[i,p,h] → atribuicoes individuais (contrato preservado)

CONTRATO DE SAÍDA (preservado):
  {
    'status':           str,
    'atribuicoes':      List[Dict],  ← {'instrutor': Instrutor, 'turma': Turma}
    'turmas':           List[Turma],
    'spread_carga':     int,
    'spread_detalhado': Dict         ← {'PROG': int, 'ROB': int}
  }
"""

from ortools.linear_solver import pywraplp
from typing import List, Dict, Any, Tuple
import math
from ..data_models import Projeto, Turma, Instrutor, ParametrosOtimizacao
from ..utils import calcular_meses_ativos, calcular_lower_bounds


# =============================================================================
# EXPANSÃO DETERMINÍSTICA — y[i,p,h] → atribuicoes individuais
# =============================================================================

def _expandir_atribuicoes(
        vinculacoes: List[Dict],
        turmas_objetos: List[Turma],
        meses_ferias_idx: List[int],
        num_meses: int) -> List[Dict]:
    """
    Converte vinculações de alto nível em atribuições individuais turma→instrutor.

    vinculacoes: [{'instrutor': Instrutor, 'projeto': str, 'habilidade': str}]

    Para cada projeto+habilidade, distribui as turmas igualmente entre
    os instrutores vinculados — exatamente a lógica da planilha manual.

    Retorna List[{'instrutor': Instrutor, 'turma': Turma}]
    """
    atribuicoes = []

    # Agrupar turmas por (projeto, habilidade)
    turmas_por_ph = {}
    for turma in turmas_objetos:
        chave = (turma.projeto, turma.habilidade)
        if chave not in turmas_por_ph:
            turmas_por_ph[chave] = []
        turmas_por_ph[chave].append(turma)

    # Agrupar instrutores vinculados por (projeto, habilidade)
    instrutores_por_ph = {}
    for vinc in vinculacoes:
        chave = (vinc['projeto'], vinc['habilidade'])
        if chave not in instrutores_por_ph:
            instrutores_por_ph[chave] = []
        instrutores_por_ph[chave].append(vinc['instrutor'])

    # Distribuição round-robin por mês letivo para máxima homogeneidade
    for chave, turmas in turmas_por_ph.items():
        instrutores = instrutores_por_ph.get(chave, [])
        if not instrutores:
            continue

        # Ordenar turmas por mês de início para distribuição consistente
        turmas_ordenadas = sorted(turmas, key=lambda t: t.mes_inicio)
        n_inst = len(instrutores)

        for idx_t, turma in enumerate(turmas_ordenadas):
            # Round-robin: distribui ciclicamente entre instrutores
            instrutor = instrutores[idx_t % n_inst]
            atribuicoes.append({
                'instrutor': instrutor,
                'turma': turma
            })

    return atribuicoes


# =============================================================================
# SUBPROBLEMA POR HABILIDADE
# =============================================================================

def _resolver_subproblema(
        habilidade: str,
        projetos: List[Projeto],
        turmas_h: List[Turma],
        meses: List[str],
        meses_ferias_idx: List[int],
        capacidade: int,
        lb_global: int,
        timeout_ms: int) -> Tuple[List[Dict], int]:
    """
    Resolve o subproblema de alocação para uma habilidade específica.

    Modelo:
      y[i, p] ∈ {0,1}  — instrutor i vinculado ao projeto p
      L[i, m] ≥ 0       — carga mensal do instrutor i no mês m
      d+[i,m], d-[i,m]  — desvio positivo/negativo da carga média

    Objetivo: minimizar Σ(d+[i,m] + d-[i,m])  — norma L1 (homogeneidade)
    Secundário: minimizar ociosidade (meses sem carga fora de férias)

    Retorna:
      vinculacoes: [{'instrutor': Instrutor, 'projeto': str, 'habilidade': str}]
      desvio_max:  int  (usado como spread_carga no contrato de saída)
    """
    num_meses = len(meses)

    # Projetos com turmas desta habilidade
    projetos_h = [
        p for p in projetos
        if (habilidade == 'PROG' and p.prog > 0) or
           (habilidade == 'ROB' and p.rob > 0)
    ]

    if not projetos_h or not turmas_h:
        return [], 0

    # Número de instrutores no pool: LB global + margem de segurança
    n_pool = max(lb_global + 5, len(turmas_h))
    prefixo = habilidade if habilidade == 'PROG' else 'ROB'

    instrutores_pool = [
        Instrutor(
            id=f"{prefixo}_{i + 1}",
            habilidade=habilidade,
            capacidade=capacidade,
            laboratorio_id="LAB_PADRAO"
        )
        for i in range(n_pool)
    ]

    n_inst = len(instrutores_pool)
    n_proj = len(projetos_h)

    print(f"\n  [{habilidade}] Pool: {n_inst} instrutores | "
          f"Projetos: {n_proj} | "
          f"Turmas: {len(turmas_h)} | "
          f"LB: ≥{lb_global}")

    # -------------------------------------------------------------------------
    # Pré-cálculo: carga mensal por projeto (turmas ativas em cada mês)
    # -------------------------------------------------------------------------
    # carga_projeto_mes[p_idx][m] = número de turmas ativas do projeto p no mês m
    carga_projeto_mes = {}
    for p_idx, proj in enumerate(projetos_h):
        carga_projeto_mes[p_idx] = [0] * num_meses
        for turma in turmas_h:
            nome_base = turma.projeto.split('_Onda')[0]
            proj_base = proj.nome.split('_Onda')[0]
            if nome_base != proj_base:
                continue
            meses_ativos = calcular_meses_ativos(
                turma.mes_inicio, turma.duracao,
                meses_ferias_idx, num_meses
            )
            for m in meses_ativos:
                carga_projeto_mes[p_idx][m] += 1

    # Carga média alvo por instrutor por projeto (meses letivos apenas)
    media_alvo = {}
    for p_idx, proj in enumerate(projetos_h):
        total_turmas_proj = sum(carga_projeto_mes[p_idx])
        meses_letivos = [
            m for m in range(num_meses)
            if m not in meses_ferias_idx and carga_projeto_mes[p_idx][m] > 0
        ]
        if not meses_letivos:
            media_alvo[p_idx] = 0.0
            continue
        # Será dividido pelo número de instrutores vinculados (calculado pós-solver)
        media_alvo[p_idx] = total_turmas_proj  # numerador — denominador após solver

    # -------------------------------------------------------------------------
    # SOLVER
    # -------------------------------------------------------------------------
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        raise RuntimeError("Solver SCIP não encontrado")

    solver.SetTimeLimit(timeout_ms)

    # --- Variáveis principais ---
    # y[i, p] = 1 se instrutor i está vinculado ao projeto p
    y = {}
    for i in range(n_inst):
        for p in range(n_proj):
            y[i, p] = solver.BoolVar(f'y_{i}_{p}')

    # ativo[i] = 1 se instrutor i tem pelo menos um projeto
    ativo = [solver.BoolVar(f'ativo_{i}') for i in range(n_inst)]

    # L[i, m] = carga do instrutor i no mês m (contínua, ≥ 0)
    L = {}
    for i in range(n_inst):
        for m in range(num_meses):
            L[i, m] = solver.NumVar(0, capacidade, f'L_{i}_{m}')

    # d+[i,m], d-[i,m] = desvio da carga média (norma L1)
    dp = {}
    dm = {}
    for i in range(n_inst):
        for m in range(num_meses):
            if m not in meses_ferias_idx:
                dp[i, m] = solver.NumVar(0, capacidade, f'dp_{i}_{m}')
                dm[i, m] = solver.NumVar(0, capacidade, f'dm_{i}_{m}')

    # --- R1: Ativação ---
    # Se y[i,p] = 1 para qualquer p → ativo[i] = 1
    for i in range(n_inst):
        solver.Add(
            solver.Sum([y[i, p] for p in range(n_proj)]) <=
            n_proj * ativo[i]
        )
        solver.Add(
            solver.Sum([y[i, p] for p in range(n_proj)]) >=
            ativo[i]
        )

    # --- R2: Cobertura mínima de instrutores por projeto ---
    # Cada projeto precisa de pelo menos 1 instrutor vinculado
    for p in range(n_proj):
        solver.Add(
            solver.Sum([y[i, p] for i in range(n_inst)]) >= 1
        )

    # --- R3: Definição da carga mensal ---
    # L[i,m] = Σ_p (y[i,p] * carga_projeto_mes[p][m] / n_vinculados_p)
    # Como n_vinculados é variável, usamos formulação linear:
    # L[i,m] * n_vinculados_p >= y[i,p] * carga_projeto_mes[p][m]
    # Abordagem prática: L[i,m] = Σ_p y[i,p] * (carga_projeto_mes[p][m] / LB_p)
    # onde LB_p é o lower bound de instrutores para o projeto p (piso seguro)
    for p_idx, proj in enumerate(projetos_h):
        # LB por projeto: ceil(total_turmas / capacidade)
        total_proj = sum(carga_projeto_mes[p_idx])
        lb_p = max(1, math.ceil(total_proj / capacidade))

        for i in range(n_inst):
            for m in range(num_meses):
                carga_m = carga_projeto_mes[p_idx][m]
                if carga_m == 0:
                    continue
                # Contribuição do projeto p para a carga do instrutor i no mês m
                # Usa LB como denominador conservador (evita divisão por variável)
                contribuicao = carga_m / lb_p
                solver.Add(
                    L[i, m] >= y[i, p_idx] * contribuicao
                )

    # --- R4: Capacidade mensal ---
    for i in range(n_inst):
        for m in range(num_meses):
            if m in meses_ferias_idx:
                # Férias = carga zero (Q3): instrutor ativo mas sem turmas
                solver.Add(L[i, m] == 0)
            else:
                solver.Add(L[i, m] <= capacidade * ativo[i])

    # --- R5: Linearização do desvio (norma L1) ---
    # Para meses letivos: L[i,m] - media_ref = d+[i,m] - d-[i,m]
    # media_ref: estimativa baseada em LB global
    media_ref = (
        sum(sum(carga_projeto_mes[p][m] for p in range(n_proj))
            for m in range(num_meses) if m not in meses_ferias_idx)
        / max(1, lb_global)
        / max(1, len([m for m in range(num_meses)
                      if m not in meses_ferias_idx]))
    )

    for i in range(n_inst):
        for m in range(num_meses):
            if m in meses_ferias_idx:
                continue
            # d+[i,m] - d-[i,m] = L[i,m] - media_ref * ativo[i]
            solver.Add(
                dp[i, m] - dm[i, m] ==
                L[i, m] - media_ref * ativo[i]
            )

    # --- R6: Simetria — instrutores ativos preenchem do índice 0 ---
    # Quebra de simetria: evita que o solver explore permutações equivalentes
    # Forçar ativo[0] >= ativo[1] >= ... >= ativo[n-1]
    for i in range(n_inst - 1):
        solver.Add(ativo[i] >= ativo[i + 1])

    # -------------------------------------------------------------------------
    # FUNÇÃO OBJETIVO
    # -------------------------------------------------------------------------
    # Nível 1 (peso alto): minimizar desvio L1 (homogeneidade)
    # Nível 2 (peso baixo): minimizar instrutores ativos (eficiência)
    peso_homogeneidade = 1000
    peso_instrutores = 1

    obj_homogeneidade = solver.Sum([
        dp[i, m] + dm[i, m]
        for i in range(n_inst)
        for m in range(num_meses)
        if m not in meses_ferias_idx
    ])

    obj_instrutores = solver.Sum(ativo)

    solver.Minimize(
        peso_homogeneidade * obj_homogeneidade +
        peso_instrutores * obj_instrutores
    )

    # -------------------------------------------------------------------------
    # RESOLUÇÃO
    # -------------------------------------------------------------------------
    print(f"  [{habilidade}] Resolvendo ({timeout_ms // 1000}s timeout)...")
    status_solver = solver.Solve()

    if status_solver not in [
        pywraplp.Solver.OPTIMAL,
        pywraplp.Solver.FEASIBLE
    ]:
        print(f"  [{habilidade}] ✗ Sem solução viável — usando fallback")
        # Fallback: 1 instrutor por projeto com todas as turmas
        vinculacoes_fallback = []
        for p_idx, proj in enumerate(projetos_h):
            inst = instrutores_pool[p_idx % n_pool]
            vinculacoes_fallback.append({
                'instrutor': inst,
                'projeto': proj.nome,
                'habilidade': habilidade
            })
        return vinculacoes_fallback, 0

    # Coletar vinculações
    vinculacoes = []
    instrutores_usados = set()

    for i in range(n_inst):
        for p in range(n_proj):
            if y[i, p].solution_value() > 0.5:
                vinculacoes.append({
                    'instrutor': instrutores_pool[i],
                    'projeto': projetos_h[p].nome,
                    'habilidade': habilidade
                })
                instrutores_usados.add(i)

    # Calcular desvio máximo real
    desvio_max = 0
    for i in instrutores_usados:
        for m in range(num_meses):
            if m not in meses_ferias_idx:
                d = abs(
                    dp[i, m].solution_value() -
                    dm[i, m].solution_value()
                )
                desvio_max = max(desvio_max, d)

    print(
        f"  [{habilidade}] ✓ "
        f"{len(instrutores_usados)} instrutores alocados | "
        f"Desvio máximo: {desvio_max:.2f}"
    )

    # Log de vinculações
    for v in vinculacoes:
        print(
            f"    {v['instrutor'].id} → {v['projeto']}"
        )

    return vinculacoes, int(math.ceil(desvio_max))


# =============================================================================
# FUNÇÃO PRINCIPAL — CONTRATO PRESERVADO
# =============================================================================

def otimizar_atribuicao_e_carga(
        cronograma_estagio1: List[Dict],
        projetos: List[Projeto],
        meses: List[str],
        meses_ferias_idx: List[int],
        parametros: ParametrosOtimizacao) -> Dict[str, Any]:
    """
    Estágio 2 v5.0: Aloca instrutores por projeto e habilidade.

    Modelo y[i,p,h] substitui x[i,t]:
      - 98% menos variáveis binárias
      - Homogeneidade como objetivo primário
      - Permanência por projeto implícita na variável de decisão
      - Compartilhamento entre projetos permitido (Q1)
      - Férias = carga zero (Q3)
      - PROG e ROB como subproblemas independentes (Q4)

    Contrato de saída idêntico ao Stage 2 v4.4.
    """

    print("\n" + "=" * 80)
    print("STAGE 2: ALOCAÇÃO DE INSTRUTORES (v5.0 — Modelo por Projeto)")
    print("=" * 80)

    solver_check = pywraplp.Solver.CreateSolver('SCIP')
    if not solver_check:
        return {"status": "falha", "erro": "Solver SCIP não encontrado"}

    num_meses = len(meses)
    timeout_ms = parametros.timeout_segundos * 1000

    # =========================================================================
    # 1. RECONSTRUÇÃO DE TURMAS (idêntica à versão anterior)
    #    Garante compatibilidade com o contrato de saída
    # =========================================================================
    turmas_objetos = []
    for item in cronograma_estagio1:
        hab_limpa = str(item.get('habilidade', 'PROG')).upper()
        if hab_limpa not in ['PROG', 'ROBOTICA']:
            hab_limpa = 'PROG'

        for _ in range(item['qtd']):
            t = Turma(
                id=len(turmas_objetos),
                projeto=item['projeto_nome'],
                mes_inicio=item['mes_inicio'],
                duracao=item['duracao'],
                habilidade=hab_limpa
            )
            turmas_objetos.append(t)

    num_turmas = len(turmas_objetos)
    if num_turmas == 0:
        return {"status": "falha", "erro": "Nenhuma turma para alocar"}

    # =========================================================================
    # 2. SEPARAÇÃO DE TURMAS POR HABILIDADE
    #    Nota: Stage 1 retorna habilidade 'MISTA' — distribuímos aqui
    #    proporcionalmente ao percentual_prog de cada projeto
    # =========================================================================
    # Mapear projeto → percentual_prog
    perc_prog_por_projeto = {}
    for proj in projetos:
        nome_base = proj.nome.split('_Onda')[0]
        total = proj.prog + proj.rob
        if total > 0:
            perc_prog_por_projeto[nome_base] = proj.prog / total
        else:
            perc_prog_por_projeto[nome_base] = 1.0

    # Re-atribuir habilidade MISTA baseado no percentual do projeto
    turmas_finais = []
    contagem_por_proj_hab = {}

    for turma in turmas_objetos:
        nome_base = turma.projeto.split('_Onda')[0]
        chave = (turma.projeto, 'PROG')
        chave_rob = (turma.projeto, 'ROB')

        if turma.habilidade == 'MISTA':
            perc = perc_prog_por_projeto.get(nome_base, 1.0)
            # Conta quantas já foram alocadas como PROG para este projeto
            n_prog = contagem_por_proj_hab.get(turma.projeto, {}).get('PROG', 0)
            n_rob = contagem_por_proj_hab.get(turma.projeto, {}).get('ROB', 0)
            total_proj = n_prog + n_rob

            # Decide PROG ou ROB baseado na proporção acumulada
            if total_proj == 0:
                hab_real = 'PROG' if perc >= 0.5 else 'ROBOTICA'
            else:
                perc_prog_atual = n_prog / total_proj
                hab_real = 'PROG' if perc_prog_atual < perc else 'ROBOTICA'

            if turma.projeto not in contagem_por_proj_hab:
                contagem_por_proj_hab[turma.projeto] = {'PROG': 0, 'ROB': 0}
            if hab_real == 'PROG':
                contagem_por_proj_hab[turma.projeto]['PROG'] += 1
            else:
                contagem_por_proj_hab[turma.projeto]['ROB'] += 1

            turma = Turma(
                id=turma.id,
                projeto=turma.projeto,
                habilidade=hab_real,
                mes_inicio=turma.mes_inicio,
                duracao=turma.duracao
            )

        turmas_finais.append(turma)

    turmas_prog = [t for t in turmas_finais if t.habilidade == 'PROG']
    turmas_rob = [t for t in turmas_finais if t.habilidade == 'ROBOTICA']

    print(f"\nTurmas: {len(turmas_prog)} PROG | {len(turmas_rob)} ROB")

    # =========================================================================
    # 3. LOWER BOUNDS AUTOMÁTICOS (Q5)
    # =========================================================================
    lbs = calcular_lower_bounds(
        projetos, meses, meses_ferias_idx,
        parametros.capacidade_max_instrutor
    )

    lb_prog = lbs['global']['PROG']
    lb_rob = lbs['global']['ROB']

    # =========================================================================
    # 4. RESOLVER SUBPROBLEMAS INDEPENDENTES (Q4)
    # =========================================================================
    timeout_por_subproblema = timeout_ms // 2

    print("\n[SUBPROBLEMA PROG]")
    vinculacoes_prog, desvio_prog = _resolver_subproblema(
        habilidade='PROG',
        projetos=projetos,
        turmas_h=turmas_prog,
        meses=meses,
        meses_ferias_idx=meses_ferias_idx,
        capacidade=parametros.capacidade_max_instrutor,
        lb_global=lb_prog,
        timeout_ms=timeout_por_subproblema
    )

    print("\n[SUBPROBLEMA ROB]")
    vinculacoes_rob, desvio_rob = _resolver_subproblema(
        habilidade='ROBOTICA',
        projetos=projetos,
        turmas_h=turmas_rob,
        meses=meses,
        meses_ferias_idx=meses_ferias_idx,
        capacidade=parametros.capacidade_max_instrutor,
        lb_global=lb_rob,
        timeout_ms=timeout_por_subproblema
    )

    todas_vinculacoes = vinculacoes_prog + vinculacoes_rob

    if not todas_vinculacoes:
        return {
            "status": "falha",
            "erro": "Nenhuma vinculação encontrada em ambos os subproblemas"
        }

    # =========================================================================
    # 5. EXPANSÃO DETERMINÍSTICA → atribuicoes individuais (contrato)
    # =========================================================================
    print("\n[EXPANSÃO] Distribuindo turmas entre instrutores vinculados...")

    atribuicoes = _expandir_atribuicoes(
        todas_vinculacoes,
        turmas_finais,
        meses_ferias_idx,
        num_meses
    )

    print(f"  ✓ {len(atribuicoes)} atribuições geradas")

    # =========================================================================
    # 6. RETORNO — CONTRATO PRESERVADO
    # =========================================================================
    return {
        "status":           "sucesso",
        "atribuicoes":      atribuicoes,
        "turmas":           turmas_finais,   # lista completa de Turma
        "spread_carga":     max(desvio_prog, desvio_rob),
        "spread_detalhado": {
            "PROG":     desvio_prog,
            "ROB":      desvio_rob
        }
    }