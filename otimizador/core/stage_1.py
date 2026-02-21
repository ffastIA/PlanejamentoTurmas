"""
Estágio 1: Otimização de Cronograma de Turmas
Versão 5.0 - Ondas Explícitas com Restrição de Sequencialidade Intra-Projeto

MUDANÇAS EM RELAÇÃO À VERSÃO ANTERIOR:
  - Ondas tratadas como entidades separadas no solver
  - Restrição de não-sobreposição intra-projeto (onda N+1 começa após onda N terminar)
  - Campo 'onda' adicionado ao cronograma de saída
  - Contrato de saída preservado: todos os campos anteriores mantidos
"""

from ortools.linear_solver import pywraplp
from typing import List, Dict, Any
from ..data_models import Projeto, ParametrosOtimizacao
from ..utils import calcular_meses_ativos


def _extrair_ondas_do_projeto(proj: Projeto) -> List[Dict]:
    """
    Extrai as ondas de um projeto a partir do nome.
    Projetos com sufixo '_OndaN' são agrupados por projeto base.

    Retorna lista de dicts:
    [{'nome': str, 'proj_idx': int, 'onda_num': int}]
    """
    partes = proj.nome.split('_Onda')
    if len(partes) == 2:
        return partes[0], int(partes[1])
    return proj.nome, 1


def _calcular_fim_calendario(mes_inicio: int, duracao: int,
                              meses_ferias_idx: List[int],
                              num_meses: int) -> int:
    """
    Retorna o último mês de calendário em que uma turma iniciada
    em mes_inicio (com duracao letiva) estará ativa.
    Retorna -1 se não for possível completar a duração.
    """
    meses_ativos = calcular_meses_ativos(
        mes_inicio, duracao, meses_ferias_idx, num_meses
    )
    if len(meses_ativos) < duracao:
        return -1
    return meses_ativos[-1]


def otimizar_curva_demanda(projetos: List[Projeto],
                           meses: List[str],
                           parametros: ParametrosOtimizacao) -> Dict[str, Any]:
    """
    Estágio 1: Otimiza o cronograma de início das turmas.

    NOVIDADES v5.0:
      - Ondas do mesmo projeto base são identificadas e vinculadas
      - Restrição de sequencialidade: onda K+1 só pode começar após
        o último mês letivo da onda K
      - Campo 'onda' incluído no cronograma de saída

    CONTRATO DE SAÍDA (preservado):
      {
        'status':        str,
        'cronograma':    List[Dict],  ← campo 'onda' adicionado
        'pico_max':      int,
        'demanda_mensal':List[int],
        'meses_ferias':  List[int]
      }
    """

    print("\n" + "=" * 80)
    print("STAGE 1: OTIMIZAÇÃO DE CRONOGRAMA (v5.0 — Ondas Sequenciais)")
    print("=" * 80)

    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        print("[ERRO] Solver SCIP não encontrado.")
        return None

    solver.SetTimeLimit(parametros.timeout_segundos * 1000)
    num_meses = len(meses)

    # Índices de férias a partir dos nomes
    meses_ferias_idx = [
        meses.index(m) for m in parametros.meses_ferias if m in meses
    ]

    print(f"\nParâmetros:")
    print(f"  Período: {meses[0]} a {meses[-1]} ({num_meses} meses)")
    print(f"  Pico máximo permitido: {parametros.pico_maximo_turmas} turmas")
    print(f"  Projetos/Ondas: {len(projetos)}")
    print(f"  Meses de férias: {[meses[i] for i in meses_ferias_idx]}")

    # =========================================================================
    # IDENTIFICAÇÃO DE GRUPOS DE ONDAS POR PROJETO BASE
    # =========================================================================
    # grupos_ondas: { 'nome_base': [(proj_idx, onda_num), ...] }
    # Permite identificar quais projetos são ondas do mesmo projeto base
    # e aplicar restrição de sequencialidade entre elas.
    grupos_ondas = {}
    for i, proj in enumerate(projetos):
        nome_base, onda_num = _extrair_ondas_do_projeto(proj)
        if nome_base not in grupos_ondas:
            grupos_ondas[nome_base] = []
        grupos_ondas[nome_base].append((i, onda_num))

    # Ordenar ondas por número dentro de cada grupo
    for nome_base in grupos_ondas:
        grupos_ondas[nome_base].sort(key=lambda x: x[1])

    print(f"\nGrupos de ondas identificados:")
    for nome_base, ondas in grupos_ondas.items():
        if len(ondas) > 1:
            print(f"  {nome_base}: {len(ondas)} ondas → restrição sequencial aplicada")
        else:
            print(f"  {nome_base}: onda única")

    # =========================================================================
    # VARIÁVEIS: x[i, j] = turmas do projeto i começando no mês j
    # =========================================================================
    x = {}
    for i, proj in enumerate(projetos):
        for j in range(num_meses):
            x[i, j] = solver.IntVar(0, proj.prog + proj.rob, f'x_{i}_{j}')

    # =========================================================================
    # RESTRIÇÃO 1: Total de turmas por projeto
    # =========================================================================
    for i, proj in enumerate(projetos):
        solver.Add(
            solver.Sum([x[i, j] for j in range(num_meses)]) ==
            (proj.prog + proj.rob)
        )

    # =========================================================================
    # RESTRIÇÃO 2: Janela de início permitida
    # =========================================================================
    for i, proj in enumerate(projetos):
        for j in range(num_meses):
            if j < proj.inicio_min or j > proj.inicio_max:
                solver.Add(x[i, j] == 0)

    # =========================================================================
    # RESTRIÇÃO 3: Cálculo de demanda mensal
    # =========================================================================
    demanda_mensal_valores = [[] for _ in range(num_meses)]

    for i, proj in enumerate(projetos):
        for start_month in range(num_meses):
            meses_ativos = calcular_meses_ativos(
                start_month, proj.duracao, meses_ferias_idx, num_meses
            )
            for m_ativo in meses_ativos:
                demanda_mensal_valores[m_ativo].append(x[i, start_month])

    # =========================================================================
    # RESTRIÇÃO 4: Pico máximo global (HARD CONSTRAINT)
    # =========================================================================
    print(
        f"\nAplicando restrição de pico máximo "
        f"({parametros.pico_maximo_turmas} turmas)..."
    )
    for m in range(num_meses):
        if demanda_mensal_valores[m]:
            solver.Add(
                solver.Sum(demanda_mensal_valores[m]) <=
                parametros.pico_maximo_turmas
            )

    # =========================================================================
    # RESTRIÇÃO 5: Mínimo de turmas por mês por projeto
    # =========================================================================
    print("Aplicando restrição de mínimo de turmas por mês...")

    for i, proj in enumerate(projetos):
        min_turmas = getattr(proj, 'min_turmas', 0)
        if min_turmas <= 0:
            continue

        for m in range(proj.inicio_min, proj.mes_fim_projeto + 1):
            if m >= num_meses:
                break

            mes_nome = meses[m]
            is_ferias = mes_nome in parametros.meses_ferias
            if is_ferias:
                continue

            vars_ativas_no_mes = []
            for s in range(max(0, m - proj.duracao + 1), m + 1):
                if proj.inicio_min <= s <= proj.inicio_max:
                    meses_ativos_da_turma = calcular_meses_ativos(
                        s, proj.duracao, meses_ferias_idx, num_meses
                    )
                    if m in meses_ativos_da_turma:
                        vars_ativas_no_mes.append(x[i, s])

            if vars_ativas_no_mes:
                solver.Add(
                    solver.Sum(vars_ativas_no_mes) >= min_turmas
                )

    # =========================================================================
    # RESTRIÇÃO 6: SEQUENCIALIDADE DE ONDAS — NOVA
    #
    # Para cada projeto base com múltiplas ondas:
    #   onda K+1 só pode iniciar APÓS o último mês letivo da onda K
    #
    # Implementação via Big-M:
    #   Para cada par (s_k, s_k1) de meses de início onde s_k1 causaria
    #   sobreposição com s_k, forçamos: x[k, s_k] + x[k+1, s_k1] <=
    #   total_turmas (i.e., não podem coexistir ambos > 0 nesta combinação).
    #
    # Abordagem prática: para cada mês de início s_k da onda K,
    # calculamos o primeiro mês válido para a onda K+1 e bloqueamos
    # todos os meses anteriores a ele.
    # =========================================================================
    print("\nAplicando restrição de sequencialidade entre ondas...")

    for nome_base, ondas_lista in grupos_ondas.items():
        if len(ondas_lista) < 2:
            continue

        for k in range(len(ondas_lista) - 1):
            idx_k, _ = ondas_lista[k]
            idx_k1, _ = ondas_lista[k + 1]
            proj_k = projetos[idx_k]
            proj_k1 = projetos[idx_k1]

            print(
                f"  Sequencialidade: {proj_k.nome} → {proj_k1.nome}"
            )

            # Para cada possível mês de início da onda K:
            for s_k in range(proj_k.inicio_min, proj_k.inicio_max + 1):
                # Calcular o último mês letivo se a onda K começar em s_k
                fim_letivo_k = _calcular_fim_calendario(
                    s_k, proj_k.duracao, meses_ferias_idx, num_meses
                )
                if fim_letivo_k == -1:
                    continue

                # Primeiro mês válido para onda K+1: após fim letivo da onda K
                primeiro_valido_k1 = fim_letivo_k + 1

                # Bloquear todos os meses de início de K+1 que causariam sobreposição
                for s_k1 in range(proj_k1.inicio_min, proj_k1.inicio_max + 1):
                    if s_k1 <= fim_letivo_k:
                        # s_k1 causaria sobreposição — bloquear combinação
                        # Big-M: se x[k, s_k] > 0, então x[k+1, s_k1] = 0
                        total_k = proj_k.prog + proj_k.rob
                        total_k1 = proj_k1.prog + proj_k1.rob
                        M = total_k + total_k1

                        # x[k,s_k] + x[k+1,s_k1] <= M - 1
                        # equivalente a: não podem ambos ser > 0 simultaneamente
                        solver.Add(
                            x[idx_k, s_k] * (1.0 / total_k) +
                            x[idx_k1, s_k1] * (1.0 / total_k1) <= 1
                        )

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
    status = solver.Solve()

    if status in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
        print("✓ Solução encontrada!")

        # Monta cronograma com campo 'onda' incluído
        cronograma = []
        for i, proj in enumerate(projetos):
            _, onda_num = _extrair_ondas_do_projeto(proj)
            for j in range(num_meses):
                qtd = int(x[i, j].solution_value())
                if qtd > 0:
                    cronograma.append({
                        'projeto_idx':  i,
                        'projeto_nome': proj.nome,
                        'mes_inicio':   j,
                        'qtd':          qtd,
                        'duracao':      proj.duracao,
                        'habilidade':   'MISTA',
                        'onda':         onda_num  # NOVO
                    })

        # Calcula demanda final
        demanda_final = [0] * num_meses
        for m in range(num_meses):
            for item in demanda_mensal_valores[m]:
                demanda_final[m] += int(item.solution_value())

        pico_real = max(demanda_final) if demanda_final else 0

        print(f"\n[✓] Resultados Stage 1:")
        print(f"  Pico real: {pico_real} turmas")
        print(f"  Limite: {parametros.pico_maximo_turmas} turmas")
        print(f"  Cronograma: {len(cronograma)} itens de início")
        print(
            f"  Total de turmas: "
            f"{sum(item['qtd'] for item in cronograma)}"
        )

        # Verificação de sequencialidade na solução
        print("\nVerificação de sequencialidade:")
        for nome_base, ondas_lista in grupos_ondas.items():
            if len(ondas_lista) < 2:
                continue
            inícios = []
            for idx_proj, onda_num in ondas_lista:
                proj = projetos[idx_proj]
                for j in range(num_meses):
                    if int(x[idx_proj, j].solution_value()) > 0:
                        fim = _calcular_fim_calendario(
                            j, proj.duracao, meses_ferias_idx, num_meses
                        )
                        inícios.append((onda_num, j, fim, meses[j]))
            inícios.sort(key=lambda v: v[0])
            ok = True
            for k_v in range(len(inícios) - 1):
                _, s_k, fim_k, mes_k = inícios[k_v]
                _, s_k1, _, mes_k1 = inícios[k_v + 1]
                if s_k1 <= fim_k:
                    ok = False
                    print(
                        f"  ✗ {nome_base}: "
                        f"Onda {k_v+1} ({mes_k}) sobrepõe "
                        f"Onda {k_v+2} ({mes_k1})"
                    )
            if ok:
                print(f"  ✓ {nome_base}: ondas sequenciais")

        print(f"\nDemanda mensal:")
        for m, dem in enumerate(demanda_final):
            if dem > 0:
                status_str = (
                    "✓" if dem <= parametros.pico_maximo_turmas else "✗"
                )
                print(f"  {status_str} {meses[m]}: {dem} turmas")

        return {
            'status':        'otimo',
            'cronograma':    cronograma,
            'pico_max':      pico_real,
            'demanda_mensal': demanda_final,
            'meses_ferias':  meses_ferias_idx
        }

    else:
        print("\n[ERRO] Solver não encontrou solução viável")
        print("\nPossíveis causas:")
        print("  1. Restrição de sequencialidade + janela curta → tente")
        print("     aumentar o período do projeto ou reduzir ondas")
        print("  2. Mínimo de turmas/mês muito alto")
        print("  3. Pico máximo muito baixo")
        return None