"""
Estágio 2: Alocação de Instrutores e Equilíbrio de Carga (Spread)
Versão 4.4 - Correção de Inviabilidade e Spread por Tipologia (Soft)
"""

from ortools.linear_solver import pywraplp
from typing import List, Dict, Any
from ..data_models import Projeto, Turma, Instrutor, ParametrosOtimizacao
from ..utils import calcular_meses_ativos


def otimizar_atribuicao_e_carga(cronograma_estagio1: List[Dict],
                                projetos: List[Projeto],
                                meses: List[str],
                                meses_ferias_idx: List[int],
                                parametros: ParametrosOtimizacao) -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print("STAGE 2: ALOCAÇÃO DE INSTRUTORES E EQUILÍBRIO DE CARGA")
    print("=" * 80)

    # Inicializa o solver SCIP
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        return {"status": "falha", "erro": "Solver SCIP não encontrado"}

    solver.SetTimeLimit(parametros.timeout_segundos * 1000)

    num_meses = len(meses)

    # 1. CRIAÇÃO DAS TURMAS (CORRIGIDO: Garante Habilidade PROG ou ROBOTICA)
    turmas_objetos = []
    for item in cronograma_estagio1:
        # IMPORTANTE: O Estágio 1 deve enviar 'PROG' ou 'ROBOTICA'
        # Se vier algo diferente, forçamos para PROG para evitar Inviabilidade
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

    # 2. POOL DE INSTRUTORES (CORRIGIDO: Construtor com 4 argumentos)
    # Criamos um pool robusto para garantir que sempre haja instrutores disponíveis
    num_max_instrutores = num_turmas + 10
    instrutores = []
    for i in range(num_max_instrutores):
        hab = 'PROG' if i < (num_max_instrutores // 2) else 'ROBOTICA'
        instrutores.append(Instrutor(
            id=f"{hab}_{i + 1}",
            habilidade=hab,
            capacidade=parametros.capacidade_max_instrutor,
            laboratorio_id="LAB_PADRAO"
        ))

    num_instrutores = len(instrutores)

    # 3. VARIÁVEIS DE DECISÃO
    x = {}  # x[instrutor, turma]
    for i in range(num_instrutores):
        for t in range(num_turmas):
            x[i, t] = solver.BoolVar(f'x_{i}_{t}')

    # Variável para saber se o instrutor está sendo usado
    instrutor_ativo = [solver.BoolVar(f'ativo_{i}') for i in range(num_instrutores)]

    # 4. RESTRIÇÕES

    # R1: Cada turma DEVE ter exatamente 1 instrutor
    for t in range(num_turmas):
        solver.Add(solver.Sum([x[i, t] for i in range(num_instrutores)]) == 1)

    # R2: Compatibilidade de Habilidade (Rígida)
    for i in range(num_instrutores):
        for t in range(num_turmas):
            if instrutores[i].habilidade != turmas_objetos[t].habilidade:
                solver.Add(x[i, t] == 0)

    # R3: Capacidade Mensal e Ativação
    for i in range(num_instrutores):
        # Carga total do instrutor
        carga_total = solver.Sum([x[i, t] for t in range(num_turmas)])

        # Se carga > 0, então ativo = 1
        solver.Add(carga_total <= num_turmas * instrutor_ativo[i])

        # Restrição de Capacidade por Mês
        for m in range(num_meses):
            turmas_no_mes = []
            for t_idx, t in enumerate(turmas_objetos):
                if m in calcular_meses_ativos(t.mes_inicio, t.duracao, meses_ferias_idx, num_meses):
                    turmas_no_mes.append(x[i, t_idx])

            if turmas_no_mes:
                solver.Add(solver.Sum(turmas_no_mes) <= instrutores[i].capacidade)

    # --- 5. LÓGICA DE SPREAD POR TIPOLOGIA (SOFT CONSTRAINT - CORRIGIDA) ---

    def criar_spread_tipologia(indices, nome):
        if not indices: return solver.IntVar(0, 0, f'spread_{nome}_vazio')

        max_v = solver.IntVar(0, num_turmas, f'max_{nome}')
        min_v = solver.IntVar(0, num_turmas, f'min_{nome}')
        spread_v = solver.IntVar(0, num_turmas, f'spread_{nome}')

        for i in indices:
            carga = solver.Sum([x[i, t] for t in range(num_turmas)])
            solver.Add(max_v >= carga)
            # Big-M: Se o instrutor está ativo, min_v <= carga. Se não, min_v <= total (ignora)
            solver.Add(min_v <= carga + (1 - instrutor_ativo[i]) * num_turmas)

        solver.Add(spread_v == max_v - min_v)
        return spread_v

    idx_prog = [i for i, inst in enumerate(instrutores) if inst.habilidade == 'PROG']
    idx_rob = [i for i, inst in enumerate(instrutores) if inst.habilidade == 'ROBOTICA']

    spread_prog = criar_spread_tipologia(idx_prog, 'prog')
    spread_rob = criar_spread_tipologia(idx_rob, 'rob')

    # --- 6. FUNÇÃO OBJETIVO ---
    # Minimiza instrutores ativos + Spreads (com peso alto)
    solver.Minimize(
        parametros.peso_instrutores * solver.Sum(instrutor_ativo) +
        parametros.peso_spread * (spread_prog + spread_rob)
    )

    # --- 7. RESOLUÇÃO ---
    print(f"Iniciando alocação de {num_turmas} turmas...")
    status = solver.Solve()

    if status in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
        print("✓ Solução encontrada!")
        atribuicoes = []
        for i in range(num_instrutores):
            for t in range(num_turmas):
                if x[i, t].solution_value() > 0.5:
                    atribuicoes.append({'instrutor': instrutores[i], 'turma': turmas_objetos[t]})

        s_p = int(spread_prog.solution_value())
        s_r = int(spread_rob.solution_value())

        return {
            "status": "sucesso",
            "atribuicoes": atribuicoes,
            "turmas": turmas_objetos,
            "spread_carga": max(s_p, s_r),
            "spread_detalhado": {"PROG": s_p, "ROB": s_r}
        }

    return {"status": "falha", "erro": "O solver não conseguiu encontrar uma solução viável."}