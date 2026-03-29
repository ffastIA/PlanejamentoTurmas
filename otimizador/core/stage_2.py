"""
Módulo de Otimização - Estágio 2 (Alocação de Instrutores)
Versão 5.7 - Correção: Criação de Instrutores PROG e ROB Proporcionalmente
"""

from ortools.sat.python import cp_model
from typing import List, Dict, Optional
from ..data_models import Projeto, Turma, Instrutor, ParametrosOtimizacao
from ..utils import calcular_meses_ativos


def otimizar_atribuicao_e_carga(
        cronograma_input: List[Dict],
        projetos_modelo: List[Projeto],
        meses: List[str],
        ferias_idx: List[int],
        parametros: ParametrosOtimizacao
) -> Optional[Dict]:
    """
    Atribui instrutores às turmas definidas no Estágio 1.
    NOVO v5.7: Cria instrutores com habilidades PROG e ROB proporcionalmente.
    """
    print("\n" + "=" * 80)
    print("  STAGE 2: ALOCAÇÃO DE INSTRUTORES — Otimização de Headcount (v5.7)")
    print("=" * 80)

    model = cp_model.CpModel()
    num_meses = len(meses)

    # 1. RECONSTRUÇÃO DAS TURMAS
    turmas = []
    for i, item in enumerate(cronograma_input):
        proj_ref = next(p for p in projetos_modelo if p.nome == item['projeto'])
        turmas.append(Turma(
            id=i,
            projeto=item['projeto'],
            mes_inicio=item['mes_inicio'],
            duracao=proj_ref.duracao_curso,
            habilidade=item.get('habilidade', 'PROG')
        ))

    # 2. CONTAGEM DE TURMAS POR HABILIDADE
    turmas_prog = sum(1 for t in turmas if t.habilidade == 'PROG')
    turmas_rob = sum(1 for t in turmas if t.habilidade == 'ROB')
    total_turmas = len(turmas)

    print(f"   Turmas PROG: {turmas_prog}")
    print(f"   Turmas ROB: {turmas_rob}")
    print(f"   Total: {total_turmas}")

    # 3. POOL DE INSTRUTORES PROPORCIONAL
    # Cria instrutores suficientes para ambas as habilidades
    max_instrutores_prog = max(turmas_prog, 1)  # Mínimo 1 se houver turmas PROG
    max_instrutores_rob = max(turmas_rob, 1)  # Mínimo 1 se houver turmas ROB
    max_instrutores_total = max_instrutores_prog + max_instrutores_rob

    instrutores_pool = []

    # Cria instrutores de Programação
    for i in range(max_instrutores_prog):
        instrutores_pool.append(Instrutor(
            id=f"INST_PROG_{i + 1:03d}",
            habilidade="PROG",
            capacidade=parametros.capacidade_max_instrutor
        ))

    # Cria instrutores de Robótica
    for i in range(max_instrutores_rob):
        instrutores_pool.append(Instrutor(
            id=f"INST_ROB_{i + 1:03d}",
            habilidade="ROB",
            capacidade=parametros.capacidade_max_instrutor
        ))

    # 4. VARIÁVEIS DE DECISÃO
    atribuicao = {}
    for t in turmas:
        for i_idx in range(len(instrutores_pool)):
            # Restrição: Só permite atribuir turma a instrutor da mesma habilidade
            if instrutores_pool[i_idx].habilidade == t.habilidade:
                atribuicao[(t.id, i_idx)] = model.NewBoolVar(f'atr_t{t.id}_i{i_idx}')

    instrutor_ativo = [model.NewBoolVar(f'ativo_i{i}') for i in range(len(instrutores_pool))]

    # 5. RESTRIÇÕES
    # Cada turma deve ter exatamente UM instrutor (da mesma habilidade)
    for t in turmas:
        turmas_possiveis = [(t.id, i_idx) for i_idx in range(len(instrutores_pool))
                            if instrutores_pool[i_idx].habilidade == t.habilidade
                            and (t.id, i_idx) in atribuicao]
        if turmas_possiveis:
            model.Add(sum(atribuicao[key] for key in turmas_possiveis) == 1)

    # Capacidade mensal do instrutor
    for i_idx in range(len(instrutores_pool)):
        for m_idx in range(num_meses):
            cargas_mes = []
            for t in turmas:
                if instrutores_pool[i_idx].habilidade == t.habilidade:
                    meses_ativos = calcular_meses_ativos(t.mes_inicio, t.duracao, ferias_idx, num_meses)
                    if m_idx in meses_ativos and (t.id, i_idx) in atribuicao:
                        cargas_mes.append(atribuicao[(t.id, i_idx)])

            if cargas_mes:
                model.Add(sum(cargas_mes) <= parametros.capacidade_max_instrutor)
                for carga_var in cargas_mes:
                    model.Add(instrutor_ativo[i_idx] >= carga_var)

    # 6. OBJETIVO: Minimizar Headcount
    model.Minimize(sum(instrutor_ativo) * parametros.peso_instrutores)

    # 7. SOLVER
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = parametros.timeout_segundos
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        atribuicoes_finais = []
        for t in turmas:
            for i_idx in range(len(instrutores_pool)):
                if (t.id, i_idx) in atribuicao and solver.Value(atribuicao[(t.id, i_idx)]):
                    atribuicoes_finais.append({
                        'turma': t,
                        'instrutor': instrutores_pool[i_idx]
                    })

        headcount_total = int(sum(solver.Value(v) for v in instrutor_ativo))
        headcount_prog = int(sum(solver.Value(instrutor_ativo[i]) for i in range(max_instrutores_prog)))
        headcount_rob = int(
            sum(solver.Value(instrutor_ativo[i]) for i in range(max_instrutores_prog, len(instrutores_pool))))

        print(f"✅ Sucesso!")
        print(f"   Headcount PROG: {headcount_prog}")
        print(f"   Headcount ROB: {headcount_rob}")
        print(f"   Total: {headcount_total}")

        return {
            'atribuicoes': atribuicoes_finais,
            'turmas': turmas,
            'status': 'sucesso',
            'spread_carga': 0,
            'spread_max_permitido': parametros.spread_maximo
        }

    print("❌ Inviável: Não foi possível alocar instrutores.")
    return None