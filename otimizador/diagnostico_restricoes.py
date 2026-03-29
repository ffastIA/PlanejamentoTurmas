"""
Módulo de Diagnóstico de Restrições
Versão 5.0 - Padronização para 'Projeto'
"""

from typing import List
from .data_models import Projeto, ParametrosOtimizacao


def diagnosticar_restricoes(projetos: List[Projeto], parametros: ParametrosOtimizacao, meses: List[str]):
    print("\n--- Diagnóstico de Restrições ---")
    num_meses = len(meses)

    for p in projetos:
        janela_disponivel = p.mes_termino_idx - p.mes_inicio_idx + 1
        print(f"Projeto {p.nome}: Janela de {janela_disponivel} meses para {p.num_turmas} turmas.")

        if janela_disponivel < p.duracao_curso:
            print(f"❌ ERRO: Janela do projeto {p.nome} é menor que a duração do curso!")