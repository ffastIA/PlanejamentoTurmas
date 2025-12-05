# ARQUIVO: otimizador/core/stage_2.py

from collections import defaultdict
from typing import List, Dict, Optional
from ortools.sat.python import cp_model
import time  # <<< ALTERAÇÃO >>>
import sys  # <<< ALTERAÇÃO >>>

# Import relativo para acessar modelos de dados e utils
from ..data_models import Projeto, ParametrosOtimizacao, Turma, Instrutor
from ..utils import calcular_meses_ativos


# <<< ALTERAÇÃO: INÍCIO DA DEFINIÇÃO DO CALLBACK >>>
class Stage2Callback(cp_model.CpSolverSolutionCallback):
    """Callback para monitorar o progresso da alocação de instrutores."""

    def __init__(self, total_instrutores_var, spread_var):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__total_instrutores = total_instrutores_var
        self.__spread = spread_var
        self.__solution_count = 0
        self.__start_time = time.time()
        print("\n[Callback] Monitorando o progresso da otimização do Estágio 2...")

    def on_solution_callback(self):
        """Chamado a cada nova solução encontrada."""
        current_time = time.time()
        instrutores = self.Value(self.__total_instrutores)
        spread = self.Value(self.__spread)

        self.__solution_count += 1

        # O 'flush=True' força a impressão imediata no terminal, evitando problemas de buffer.
        print(f"\n  >>> NOVA SOLUÇÃO #{self.__solution_count} ({current_time - self.__start_time:.2f}s) | "
              f"Instrutores: {instrutores} | "
              f"Spread: {spread} <<<\n", flush=True)

    def solution_count(self):
        return self.__solution_count


# <<< ALTERAÇÃO: FIM DA DEFINIÇÃO DO CALLBACK >>>


def otimizar_atribuicao_e_carga(cronograma_flexivel: Dict,
                                projetos: List[Projeto],
                                meses: List[str],
                                meses_ferias: List[int],
                                parametros: ParametrosOtimizacao) -> Optional[Dict]:
    """
    Aloca turmas a instrutores com restrição de spread máximo.
    (Versão Corrigida)
    """
    print("\n" + "=" * 80)
    print("ESTÁGIO 2: Alocação de Instrutores")
    print("=" * 80)
    print(f"Capacidade máxima por instrutor: {parametros.capacidade_max_instrutor} turmas/mês")
    print(f"Spread máximo configurado: {parametros.spread_maximo}\n")

    # 1. Criação de Turmas a partir do cronograma do Estágio 1
    all_turmas, turma_counter = [], 0
    projetos_dict = {p.nome: p for p in projetos}
    for proj_nome, cronogramas in cronograma_flexivel.items():
        proj_details = projetos_dict.get(proj_nome)
        if not proj_details: continue
        for crono in cronogramas:
            habilidade_str = crono.get('habilidade', 'PROG')
            habilidade = 'PROG' if habilidade_str == 'PROG' else 'ROBOTICA'
            for _ in range(crono['num_turmas']):
                all_turmas.append(
                    Turma(f'{proj_nome}_{habilidade[:3]}_{turma_counter}', proj_nome, habilidade,
                          crono['mes_inicio'], proj_details.duracao)
                )
                turma_counter += 1
    print(f"Total de turmas criadas: {len(all_turmas)}")

    # 2. Criação do Pool de Instrutores
    num_max_instrutores_flex = 80
    all_instrutores = [
        Instrutor(id=f'{hab}_{i}', habilidade=hab, capacidade=parametros.capacidade_max_instrutor, laboratorio_id=None)
        for hab in ['PROG', 'ROBOTICA'] for i in range(num_max_instrutores_flex)]
    print(f"Pool de instrutores: {len(all_instrutores)}\n")

    # 3. Construção do Modelo de Otimização
    model = cp_model.CpModel()
    num_meses = len(meses)
    turmas_por_habilidade = defaultdict(list)
    for t in all_turmas: turmas_por_habilidade[t.habilidade].append(t)
    instrutores_por_habilidade = defaultdict(list)
    for i in all_instrutores: instrutores_por_habilidade[i.habilidade].append(i)

    assign = {}
    for habilidade, turmas in turmas_por_habilidade.items():
        for t in turmas:
            for i in instrutores_por_habilidade.get(habilidade, []):
                assign[(t.id, i.id)] = model.NewBoolVar(f'assign_{t.id[:15]}_{i.id}')

    for t_list in turmas_por_habilidade.values():
        for t in t_list:
            model.AddExactlyOne(assign[(t.id, i.id)] for i in instrutores_por_habilidade[t.habilidade])

    for i in all_instrutores:
        for m in range(num_meses):
            carga_mensal = []
            for t in turmas_por_habilidade[i.habilidade]:
                meses_ativos = calcular_meses_ativos(t.mes_inicio, t.duracao, meses_ferias, num_meses)
                if m in meses_ativos:
                    carga_mensal.append(assign[(t.id, i.id)])
            if carga_mensal:
                model.Add(sum(carga_mensal) <= i.capacidade)

    cargas_totais, instrutores_usados = [], []
    for i in all_instrutores:
        usado = model.NewBoolVar(f'usado_{i.id}')
        carga_total = model.NewIntVar(0, 300, f'carga_{i.id}')
        turmas_do_instrutor = [assign.get((t.id, i.id)) for t in turmas_por_habilidade[i.habilidade] if
                               assign.get((t.id, i.id)) is not None]

        if turmas_do_instrutor:
            model.Add(sum(turmas_do_instrutor) == carga_total)
            model.Add(carga_total > 0).OnlyEnforceIf(usado)
            model.Add(carga_total == 0).OnlyEnforceIf(usado.Not())
            cargas_totais.append(carga_total)
            instrutores_usados.append(usado)

    total_instrutores = model.NewIntVar(0, len(instrutores_usados), 'total_instrutores')
    if instrutores_usados:
        model.Add(total_instrutores == sum(instrutores_usados))

    spread_var = model.NewIntVar(0, 300, 'spread_obj')
    if cargas_totais:
        max_carga = model.NewIntVar(0, 300, 'max_carga')
        min_carga_usada = model.NewIntVar(0, 300, 'min_carga_usada')
        model.AddMaxEquality(max_carga, cargas_totais)
        cargas_ajustadas = []
        for i, carga in enumerate(cargas_totais):
            carga_ajustada = model.NewIntVar(0, 300, f'carga_ajustada_{i}')
            model.Add(carga_ajustada == carga).OnlyEnforceIf(instrutores_usados[i])
            model.Add(carga_ajustada == max_carga).OnlyEnforceIf(instrutores_usados[i].Not())
            cargas_ajustadas.append(carga_ajustada)
        model.AddMinEquality(min_carga_usada, cargas_ajustadas)
        model.Add(spread_var == max_carga - min_carga_usada)
        model.Add(spread_var <= parametros.spread_maximo)
    else:
        model.Add(spread_var == 0)

    model.Minimize(total_instrutores * 10000 + spread_var)

    # 4. Resolução do Modelo
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(parametros.timeout_segundos)

    # <<< ALTERAÇÃO: ATIVAR O LOG PADRÃO PARA SEMPRE TER SAÍDA >>>
    solver.parameters.log_search_progress = True

    print("Resolvendo alocação... (com log de progresso ativado)")

    # <<< ALTERAÇÃO: INSTANCIAR E PASSAR O CALLBACK >>>
    callback = Stage2Callback(total_instrutores, spread_var)
    status = solver.Solve(model, callback)

    # ... (o resto do código permanece o mesmo) ...

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"\n[✓] SUCESSO! Status: {solver.StatusName(status)}")

        atribuicoes = []
        for t in all_turmas:
            for i in instrutores_por_habilidade[t.habilidade]:
                if solver.Value(assign.get((t.id, i.id), 0)):
                    atribuicoes.append({'turma': t, 'instrutor': i})
                    break

        carga_por_instrutor = defaultdict(int)
        for atr in atribuicoes:
            carga_por_instrutor[atr['instrutor'].id] += 1

        cargas_ativas_vals = list(carga_por_instrutor.values())
        spread_real_calculado = max(cargas_ativas_vals) - min(cargas_ativas_vals) if cargas_ativas_vals else 0

        return {
            "status": "sucesso",
            "atribuicoes": atribuicoes,
            "total_instrutores_flex": len(cargas_ativas_vals),
            "carga_por_instrutor": dict(carga_por_instrutor),
            "spread_carga": spread_real_calculado,
            "turmas": all_turmas,
            "instrutores": all_instrutores,
            "capacidade_max": parametros.capacidade_max_instrutor
        }
    else:
        print(f"\n[✗] FALHA na Alocação: {solver.StatusName(status)}")
        print("Sugestões: Aumente o 'Spread máximo' ou o 'Timeout do solver'.")
        return {"status": "falha"}
