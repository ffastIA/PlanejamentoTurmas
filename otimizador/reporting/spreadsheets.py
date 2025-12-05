# ARQUIVO: otimizador/reporting/spreadsheets.py

from collections import defaultdict
from typing import List, Dict
import pandas as pd

# Import relativo
from ..data_models import Turma, Instrutor
from ..utils import calcular_meses_ativos


def gerar_planilha_detalhada(atribuicoes: List[Dict], meses: List[str], meses_ferias: List[int]) -> pd.DataFrame:
    """Gera planilha detalhada com a carga horária."""
    print("\n--- Gerando Planilha Detalhada ---")
    if not atribuicoes: return pd.DataFrame()

    carga_data = []
    num_meses = len(meses)
    for atr in atribuicoes:
        turma, instrutor = atr['turma'], atr['instrutor']
        for mes_idx in calcular_meses_ativos(turma.mes_inicio, turma.duracao, meses_ferias, num_meses):
            carga_data.append({
                "Instrutor": instrutor.id, "Mes": meses[mes_idx], "Habilidade": instrutor.habilidade,
                "Projeto": turma.projeto, "Turma_ID": turma.id, "Carga": 1
            })

    if not carga_data: return pd.DataFrame()
    df = pd.DataFrame(carga_data).sort_values(by=["Instrutor", "Mes"])
    df.to_excel('1_carga_horaria_detalhada.xlsx', index=False, engine='openpyxl')
    print("Planilha salva: '1_carga_horaria_detalhada.xlsx'")
    return df


def gerar_planilha_consolidada_instrutor(atribuicoes: List[Dict]) -> pd.DataFrame:
    """Gera planilha consolidada por instrutor e projeto."""
    print("\n--- Gerando Planilha Consolidada por Instrutor ---")
    if not atribuicoes: return pd.DataFrame()

    dados = defaultdict(lambda: defaultdict(int))
    projetos_unicos = sorted(list(set(atr['turma'].projeto for atr in atribuicoes)))

    for atr in atribuicoes:
        dados[atr['instrutor'].id][atr['turma'].projeto] += 1

    rows = []
    for instrutor_id, proj_dict in sorted(dados.items()):
        row = {'Instrutor': instrutor_id, **{proj: proj_dict.get(proj, 0) for proj in projetos_unicos}}
        row['Total'] = sum(proj_dict.values())
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_excel('2_consolidado_instrutor_projeto.xlsx', index=False, engine='openpyxl')
    print("Planilha salva: '2_consolidado_instrutor_projeto.xlsx'")
    return df