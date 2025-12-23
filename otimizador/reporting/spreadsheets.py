import pandas as pd
from typing import List, Dict, Any
from ..utils import calcular_meses_ativos
from ..data_models import ParametrosFinanceiros


def gerar_planilha_consolidada_instrutor(atribuicoes: List[Dict]) -> pd.DataFrame:
    """
    Gera um DataFrame com o resumo de turmas por instrutor.
    """
    dados = []
    for atr in atribuicoes:
        instrutor = atr['instrutor']
        turma = atr['turma']
        dados.append({
            'Instrutor_ID': instrutor.id,
            'Habilidade': instrutor.habilidade,
            'Turma_ID': turma.id,
            'Projeto': turma.projeto,
            'Mes_Inicio_Idx': turma.mes_inicio,
            'Duracao': turma.duracao
        })

    df = pd.DataFrame(dados)
    if df.empty:
        return pd.DataFrame(columns=['Instrutor_ID', 'Total_Turmas'])

    resumo = df.groupby('Instrutor_ID').agg(
        Total_Turmas=('Turma_ID', 'count'),
        Projetos=('Projeto', lambda x: ', '.join(sorted(set(x)))),
        Habilidade=('Habilidade', 'first')
    ).reset_index()

    # Ordenar por habilidade e depois por ID (numérico)
    try:
        resumo['Num_ID'] = resumo['Instrutor_ID'].apply(lambda x: int(x.split('_')[1]) if '_' in x else 0)
        resumo = resumo.sort_values(['Habilidade', 'Num_ID']).drop('Num_ID', axis=1)
    except:
        resumo = resumo.sort_values(['Habilidade', 'Instrutor_ID'])

    return resumo


def gerar_planilha_detalhada(atribuicoes: List[Dict], meses: List[str], meses_ferias_idx: List[int],
                             parametros_financeiros: ParametrosFinanceiros = None):
    """
    Gera um arquivo Excel com duas abas:
    1. Detalhamento das alocações.
    2. Fluxo de Caixa (se parâmetros financeiros forem fornecidos).
    """
    # --- Aba 1: Detalhada ---
    dados_detalhados = []
    for atr in atribuicoes:
        t = atr['turma']
        i = atr['instrutor']

        dados_detalhados.append({
            'Instrutor': i.id,
            'Habilidade': i.habilidade,
            'Turma': t.id,
            'Projeto': t.projeto,
            'Inicio': meses[t.mes_inicio],
            'Duracao_Meses': t.duracao
        })

    df_detalhado = pd.DataFrame(dados_detalhados)

    # --- Aba 2: Fluxo de Caixa (Novo) ---
    df_financeiro = pd.DataFrame()
    if parametros_financeiros:
        custo_mensal = parametros_financeiros.custo_mensal_instrutor
        num_meses = len(meses)

        # Dicionário para guardar o conjunto de instrutores ativos em cada mês
        instrutores_ativos_por_mes = {m: set() for m in range(num_meses)}

        for atr in atribuicoes:
            t = atr['turma']
            i = atr['instrutor']
            # Calcula exatamente em quais meses essa turma acontece (pulando férias)
            meses_ativos_turma = calcular_meses_ativos(t.mes_inicio, t.duracao, meses_ferias_idx, num_meses)

            for m in meses_ativos_turma:
                instrutores_ativos_por_mes[m].add(i.id)

        # Monta a tabela financeira
        dados_fin = []
        custo_acumulado = 0.0

        for m_idx, nome_mes in enumerate(meses):
            qtd_instrutores = len(instrutores_ativos_por_mes[m_idx])
            custo_mes = qtd_instrutores * custo_mensal
            custo_acumulado += custo_mes

            dados_fin.append({
                'Mês': nome_mes,
                'Qtd. Instrutores': qtd_instrutores,
                'Custo Unitário': custo_mensal,
                'Custo Mensal Total': custo_mes,
                'Custo Acumulado': custo_acumulado
            })

        df_financeiro = pd.DataFrame(dados_fin)

    # --- Salvando o Excel ---
    try:
        with pd.ExcelWriter('resultados_otimizacao/Detalhamento_Completo.xlsx', engine='openpyxl') as writer:
            df_detalhado.to_excel(writer, sheet_name='Alocacoes', index=False)

            if not df_financeiro.empty:
                df_financeiro.to_excel(writer, sheet_name='Fluxo de Caixa', index=False)

                # Formatação básica
                workbook = writer.book
                worksheet = writer.sheets['Fluxo de Caixa']
                # Formata colunas de valor (D e E)
                for row in worksheet.iter_rows(min_row=2, min_col=4, max_col=5):
                    for cell in row:
                        cell.number_format = '#,##0.00'

        print("  ✓ Planilha 'Detalhamento_Completo.xlsx' gerada com sucesso.")
    except Exception as e:
        print(f"  [ERRO] Falha ao gerar Excel detalhado: {e}")