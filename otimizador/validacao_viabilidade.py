"""
Módulo de Validação de Viabilidade
Versão 5.0 - Padronização para 'Projeto'
"""

from typing import List
from .data_models import Projeto, ParametrosOtimizacao

def validar_viabilidade_configuracao(projetos: List[Projeto], parametros: ParametrosOtimizacao, meses: List[str]):
    print("\n--- Validando Viabilidade ---")
    for p in projetos:
        if p.num_turmas <= 0:
            print(f"⚠️ Aviso: Projeto {p.nome} não possui turmas configuradas.")
        if p.mes_inicio_idx >= p.mes_termino_idx:
            print(f"❌ Erro: Data de início após data de término no projeto {p.nome}.")
    print("✅ Validação concluída.")