import pandas as pd
from typing import List, Dict
from ..utils import calcular_fluxo_caixa_detalhado
from ..data_models import ParametrosFinanceiros


def gerar_planilha_consolidada_instrutor(atribuicoes: List[Dict]) -> pd.DataFrame:
    dados = []
    for atr in atribuicoes:
        i, t = atr['instrutor'], atr['turma']
        dados.append({'Instrutor_ID': i.id, 'Habilidade': i.habilidade, 'Turma_ID': t.id, 'Projeto': t.projeto})

    df = pd.DataFrame(dados)
    if df.empty: return pd.DataFrame(columns=['Instrutor_ID'])

    resumo = df.groupby('Instrutor_ID').agg(
        Total_Turmas=('Turma_ID', 'count'),
        Projetos=('Projeto', lambda x: ', '.join(sorted(set(x)))),
        Habilidade=('Habilidade', 'first')
    ).reset_index()
    return resumo.sort_values(['Habilidade', 'Instrutor_ID'])


def gerar_planilha_detalhada(atribuicoes: List[Dict], meses: List[str], meses_ferias_idx: List[int],
                             parametros_financeiros: ParametrosFinanceiros = None):
    # Aba 1: Detalhada
    dados = [{'Instrutor': a['instrutor'].id, 'Turma': a['turma'].id, 'Inicio': meses[a['turma'].mes_inicio]} for a in
             atribuicoes]
    df_detalhado = pd.DataFrame(dados)

    # Aba 2: Fluxo de Caixa (Usando a nova lógica centralizada)
    df_financeiro = pd.DataFrame()
    if parametros_financeiros:
        df_financeiro = calcular_fluxo_caixa_detalhado(atribuicoes, meses, meses_ferias_idx, parametros_financeiros)

    try:
        with pd.ExcelWriter('resultados_otimizacao/Detalhamento_Completo.xlsx', engine='openpyxl') as writer:
            df_detalhado.to_excel(writer, sheet_name='Alocacoes', index=False)
            if not df_financeiro.empty:
                df_financeiro.to_excel(writer, sheet_name='Fluxo de Caixa', index=False)
                # Formatação simples
                ws = writer.sheets['Fluxo de Caixa']
                for row in ws.iter_rows(min_row=2, min_col=2, max_col=3):
                    for cell in row: cell.number_format = '#,##0.00'
        print("  ✓ Planilha Excel gerada.")
    except Exception as e:
        print(f"  [ERRO] Excel: {e}")