import sys
import os
import pandas as pd
from datetime import datetime
from otimizador.io import config_manager, user_input
from otimizador.utils import (
    gerar_lista_meses, converter_projetos_para_modelo,
    calcular_evolucao_instrutores, analisar_distribuicao_instrutores_por_projeto,
    renumerar_instrutores_ativos, calcular_meses_ativos, calcular_turmas_abertas_por_mes,
    calcular_fluxo_caixa_detalhado
)
from otimizador.core import stage_1, stage_2
from otimizador.reporting import plotting, pdf_generator


def main():
    print("=" * 55 + "\n  SISTEMA DE OTIMIZAÇÃO V5.5 - FINANCEIRO REAL\n" + "=" * 55)
    params, projs_config, fin = config_manager.menu_gerenciar_configuracoes()
    if not params:
        params = user_input.obter_parametros_usuario();
        projs_config = user_input.obter_projetos_usuario();
        fin = None

    dt_min = min(datetime.strptime(p.data_inicio, "%d/%m/%Y") for p in projs_config)
    dt_max = max(datetime.strptime(p.data_termino, "%d/%m/%Y") for p in projs_config)
    meses = gerar_lista_meses(dt_min.strftime("%d/%m/%Y"), dt_max.strftime("%d/%m/%Y"))
    ferias_idx = [meses.index(m) for m in params.meses_ferias if m in meses]
    params = params._replace(meses_ferias_idx=ferias_idx)
    projs_modelo = converter_projetos_para_modelo(projs_config, meses, ferias_idx, params)

    print(f"\n[ESTÁGIO 1] Otimizando Demanda...")
    res1 = stage_1.otimizar_curva_demanda(projs_modelo, meses, params)
    if not res1: return

    print("[ESTÁGIO 2] Alocando Instrutores...")
    res2 = stage_2.otimizar_atribuicao_e_carga(res1['cronograma'], projs_modelo, meses, ferias_idx, params)
    if not res2: return

    # Processamento de Dados
    df_evolucao = calcular_evolucao_instrutores(res2['atribuicoes'], meses, ferias_idx)
    demanda_data = []
    for m_idx, mes in enumerate(meses):
        p = sum(1 for t in res2['turmas'] if m_idx in calcular_meses_ativos(t.mes_inicio, t.duracao, ferias_idx,
                                                                            len(meses)) and t.habilidade == 'PROG')
        r = sum(1 for t in res2['turmas'] if m_idx in calcular_meses_ativos(t.mes_inicio, t.duracao, ferias_idx,
                                                                            len(meses)) and t.habilidade == 'ROB')
        demanda_data.append({'Mes': mes, 'Demanda_PROG': p, 'Demanda_ROB': r, 'Total': p + r})
    serie_temporal_df = pd.DataFrame(demanda_data)

    atribuicoes_limpas, hab_count = renumerar_instrutores_ativos(res2['atribuicoes'])
    res2['atribuicoes'] = atribuicoes_limpas

    instrutores_resumo = []
    for i_id in sorted(list(set(a['instrutor'].id for a in atribuicoes_limpas))):
        atrs = [a for a in atribuicoes_limpas if a['instrutor'].id == i_id]
        instrutores_resumo.append(
            {'Instrutor_ID': i_id, 'Habilidade': atrs[0]['instrutor'].habilidade, 'Total_Turmas': len(atrs),
             'Projetos': ", ".join(set(a['turma'].projeto for a in atrs))})
    df_consolidada = pd.DataFrame(instrutores_resumo)

    df_turmas_abertas = calcular_turmas_abertas_por_mes(res2['turmas'], meses, ferias_idx)
    dist_proj = analisar_distribuicao_instrutores_por_projeto(atribuicoes_limpas)

    # Cálculo Financeiro para o Gráfico
    df_fin = calcular_fluxo_caixa_detalhado(res2['atribuicoes'], meses, ferias_idx, fin)

    print("[GRÁFICOS] Gerando imagens...")
    graficos = {
        'cronograma_consolidado': plotting.gerar_grafico_turmas_projeto_mes(res2['turmas'], projs_modelo, meses,
                                                                            ferias_idx),
        'turmas_abertas': plotting.gerar_grafico_turmas_abertas_mes(res2['turmas'], meses, ferias_idx),
        'evolucao_instrutores': plotting.gerar_grafico_evolucao_instrutores(res2['atribuicoes'], meses, ferias_idx)[0],
        'pagamentos_mensais': plotting.gerar_grafico_pagamentos_mensais(df_fin)  # NOVO
    }
    for p in projs_config:
        graficos[f"cronograma_{p.nome}"] = plotting.gerar_grafico_turmas_projeto_mes(res2['turmas'], projs_modelo,
                                                                                     meses, ferias_idx, p.nome)

    print("[RELATÓRIO] Gerando PDF...")
    pdf_path = pdf_generator.gerar_relatorio_pdf(projs_config, res1, res2, graficos, serie_temporal_df, df_consolidada,
                                                 hab_count, dist_proj, params.pico_maximo_turmas, fin, df_evolucao,
                                                 df_turmas_abertas)
    print(f"\n✅ SUCESSO! Relatório em: {pdf_path}")


if __name__ == "__main__": main()