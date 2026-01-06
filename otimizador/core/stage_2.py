from ortools.linear_solver import pywraplp
from collections import defaultdict
import numpy as np
from typing import List, Dict, Any

from ..data_models import Projeto, Instrutor, Turma, ParametrosOtimizacao
from ..utils import calcular_meses_ativos


def otimizar_atribuicao_e_carga(cronograma_entrada: Any,
                                projetos_modelo: List[Projeto],
                                meses: List[str],
                                meses_ferias_idx: List[int],
                                parametros: ParametrosOtimizacao) -> Dict[str, Any]:
    """
    Estágio 2: Atribui instrutores às turmas definidas no Estágio 1.
    Objetivo: Balancear carga e respeitar habilidades.
    """

    # --- 1. PREPARAÇÃO DOS DADOS (CORREÇÃO DO ERRO) ---
    # O Estágio 1 retorna uma lista plana. Convertendo para dicionário agrupado.
    cronograma_agrupado = defaultdict(list)

    if isinstance(cronograma_entrada, list):
        for item in cronograma_entrada:
            cronograma_agrupado[item['projeto_nome']].append(item)
    else:
        # Fallback caso venha como dicionário no futuro
        cronograma_agrupado = cronograma_entrada

    # Achatar todas as turmas para criar variáveis de decisão
    todas_turmas = []
    turma_counter = 0

    # Mapeamento para saber qual projeto exige qual habilidade
    for proj in projetos_modelo:
        itens_cronograma = cronograma_agrupado.get(proj.nome, [])

        # O Estágio 1 diz: "Começam X turmas em Jan".
        # Precisamos decidir quantas são PROG e quantas são ROB.
        # Heurística: Distribuir proporcionalmente à definição do projeto.

        total_prog_necessario = proj.prog
        total_rob_necessario = proj.rob

        # Ordenar cronograma por mês para distribuição consistente
        itens_cronograma.sort(key=lambda x: x['mes_inicio'])

        prog_alocados = 0
        rob_alocados = 0

        for item in itens_cronograma:
            qtd = item['qtd']
            mes_inicio = item['mes_inicio']
            duracao = item['duracao']

            for _ in range(qtd):
                # Decide habilidade da turma
                if prog_alocados < total_prog_necessario:
                    habilidade = 'PROG'
                    prog_alocados += 1
                else:
                    habilidade = 'ROBOTICA'
                    rob_alocados += 1

                turma_obj = Turma(
                    id=f"T{turma_counter}_{proj.nome}",
                    projeto=proj.nome,
                    habilidade=habilidade,
                    mes_inicio=mes_inicio,
                    duracao=duracao
                )
                todas_turmas.append(turma_obj)
                turma_counter += 1

    # Criar pool de instrutores (Genéricos para dimensionamento)
    # Estimativa: Total turmas / Capacidade média (com folga)
    num_meses = len(meses)
    total_turmas_count = len(todas_turmas)

    # Criamos instrutores "virtuais" suficientes para cobrir a demanda
    # Identificamos IDs como PROG_1, PROG_2... e ROB_1, ROB_2...
    if total_turmas_count > 0:
        num_instrutores_est = int(total_turmas_count / parametros.capacidade_max_instrutor) + 10
    else:
        num_instrutores_est = 2

    instrutores = []
    for i in range(1, num_instrutores_est + 1):
        instrutores.append(Instrutor(f"PROG_{i}", "PROG", parametros.capacidade_max_instrutor, None))
        instrutores.append(Instrutor(f"ROB_{i}", "ROBOTICA", parametros.capacidade_max_instrutor, None))

    # --- 2. MODELAGEM (OR-TOOLS) ---
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver: return {'status': 'falha', 'motivo': 'Solver SCIP não encontrado'}

    solver.SetTimeLimit(parametros.timeout_segundos * 1000)

    # Variáveis: y[instrutor, turma] = 1 se instrutor assume a turma
    y = {}

    # Mapeamento de compatibilidade
    candidatos_por_turma = defaultdict(list)

    for t_idx, turma in enumerate(todas_turmas):
        for i_idx, instr in enumerate(instrutores):
            # Validação de Habilidade
            if instr.habilidade == turma.habilidade:
                var = solver.BoolVar(f'y_{instr.id}_{turma.id}')
                y[(instr.id, turma.id)] = var
                candidatos_por_turma[turma.id].append(instr)

    # Restrição 1: Cada turma deve ter exatamente 1 instrutor
    for turma in todas_turmas:
        candidatos = [y[(i.id, turma.id)] for i in candidatos_por_turma[turma.id]]
        if not candidatos:
            print(f"[AVISO] Sem instrutores compatíveis para turma {turma.id} ({turma.habilidade})")
            continue
        solver.Add(solver.Sum(candidatos) == 1)

    # Restrição 2: Capacidade Mensal do Instrutor
    # Precisamos saber quais turmas estão ativas em cada mês
    turmas_ativas_por_mes = defaultdict(list)  # {mes_idx: [turma_obj, ...]}
    for t in todas_turmas:
        meses_ativos = calcular_meses_ativos(t.mes_inicio, t.duracao, meses_ferias_idx, num_meses)
        for m in meses_ativos:
            turmas_ativas_por_mes[m].append(t)

    # Variáveis auxiliares para uso do instrutor: usado[instrutor]
    instrutor_usado = {}

    for instr in instrutores:
        instrutor_usado[instr.id] = solver.BoolVar(f'usado_{instr.id}')

        vars_instrutor = []

        for m in range(num_meses):
            # Turmas ativas neste mês que podem ser deste instrutor
            turmas_no_mes = [t for t in turmas_ativas_por_mes[m] if (instr.id, t.id) in y]

            if turmas_no_mes:
                carga_mes = solver.Sum([y[(instr.id, t.id)] for t in turmas_no_mes])
                vars_instrutor.extend([y[(instr.id, t.id)] for t in turmas_no_mes])

                # Restrição de Capacidade
                solver.Add(carga_mes <= instr.capacidade)

        if vars_instrutor:
            # Se a soma das atribuições > 0, então usado deve ser 1
            # M * usado >= soma
            solver.Add(solver.Sum(vars_instrutor) <= 1000 * instrutor_usado[instr.id])

    # Função Objetivo: Minimizar número de instrutores usados
    obj_instrutores = solver.Sum(instrutor_usado.values())
    solver.Minimize(obj_instrutores * parametros.peso_instrutores)

    status = solver.Solve()

    if status in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
        atribuicoes_finais = []

        # Coletar resultados
        for t in todas_turmas:
            for i in candidatos_por_turma[t.id]:
                if y[(i.id, t.id)].solution_value() > 0.5:
                    atribuicoes_finais.append({
                        'turma': t,
                        'instrutor': i
                    })
                    break

        # Calcular métricas finais
        total_instrutores = sum(1 for i in instrutores if instrutor_usado[i.id].solution_value() > 0.5)

        # Cálculo simplificado de spread (apenas para relatório)
        cargas = defaultdict(int)
        for atr in atribuicoes_finais:
            cargas[atr['instrutor'].id] += 1
        vals = list(cargas.values())
        spread = (max(vals) - min(vals)) if vals else 0

        return {
            'status': 'sucesso',
            'atribuicoes': atribuicoes_finais,
            'turmas': todas_turmas,
            'total_instrutores_flex': total_instrutores,
            'spread_carga': spread
        }
    else:
        return {'status': 'falha', 'motivo': 'Inviável'}