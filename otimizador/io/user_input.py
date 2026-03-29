from datetime import datetime
from typing import List, Tuple
from ..data_models import ParametrosOtimizacao, Projeto, ParametrosFinanceiros, ItemCusto


def obter_parametros_usuario() -> ParametrosOtimizacao:
    print("\n--- Parâmetros de Otimização ---")
    cap = int(input("Capacidade máx. por instrutor [6]: ") or 6)
    spread = int(input("Spread máximo permitido [10]: ") or 10)
    timeout = int(input("Timeout do solver (segundos) [180]: ") or 180)

    return ParametrosOtimizacao(
        capacidade_max_instrutor=cap,
        spread_maximo=spread,
        meses_ferias=["Jul/26", "Dez/26", "Jul/27", "Dez/27"],
        meses_ferias_idx=[],
        timeout_segundos=timeout,
        peso_instrutores=1000,
        peso_spread=10,
        pico_maximo_turmas=300
    )


def obter_projetos_usuario() -> List[Projeto]:
    projetos = []
    while True:
        nome = input("\nNome do projeto (ou Enter para finalizar): ")
        if not nome: break

        turmas = int(input(f"Número de turmas para {nome}: "))
        duracao = int(input(f"Duração de cada turma (meses): "))
        ondas = int(input(f"Número de ondas: "))
        ini = input("Data início (DD/MM/AAAA): ")
        fim = input("Data término (DD/MM/AAAA): ")

        projetos.append(Projeto(
            nome=nome, data_inicio=ini, data_termino=fim,
            num_turmas=turmas, duracao_curso=duracao, ondas=ondas,
            percentual_prog=70.0, turmas_min_por_mes=10,
            mes_inicio_idx=0, mes_termino_idx=0
        ))
    return projetos