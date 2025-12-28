"""
Sistema de Otimização de Alocação de Instrutores
Versão 3.2 - Gráficos Individuais e Consolidados
Autor: Sistema Idear
"""

import sys
import os
from datetime import datetime
from pathlib import Path
import pandas as pd

from otimizador.io import user_input, config_manager
from otimizador.utils import (
    gerar_lista_meses,
    converter_projetos_para_modelo,
    renumerar_instrutores_ativos,
    analisar_distribuicao_instrutores_por_projeto
)
from otimizador.core import stage_1, stage_2
from otimizador.reporting import plotting, spreadsheets, pdf_generator
from otimizador.data_models import ParametrosFinanceiros


def main():
    print("=" * 80)
    print("SISTEMA DE OTIMIZAÇÃO DE ALOCAÇÃO DE INSTRUTORES")
    print("Versão 3.2 (Correção de Gráficos)")
    print("=" * 80)

    try:
        # ETAPA 1
        print("\n--- Etapa 1: Configuração ---")
        parametros, projetos_config, parametros_financeiros = config_manager.menu_gerenciar_configuracoes()

        if not (parametros and projetos_config):
            print("\nCriando nova configuração...")
            parametros = user_input.obter_parametros_usuario()
            projetos_config = user_input.obter_projetos_usuario()
            parametros_financeiros = None
        else:
            print("\nConfigurações carregadas:")
            user_input.exibir_resumo_parametros(parametros)
            user_input.exibir_resumo_projetos(projetos_config)
            if parametros_financeiros:
                print(f"\n[Financeiro] {len(parametros_financeiros.itens_custo)} itens de custo configurados.")

        # ETAPA 2
        print("\n--- Etapa 2: Preparação de Dados ---")
        dt_min = min(datetime.strptime(p.data_inicio, "%d/%m/%Y") for p in projetos_config)
        dt_max = max(datetime.strptime(p.data_termino, "%d/%m/%Y") for p in projetos_config)
        print(f"Período: {dt_min.strftime('%d/%m/%Y')} a {dt_max.strftime('%d/%m/%Y')}")
        meses = gerar_lista_meses(dt_min.strftime("%d/%m/%Y"), dt_max.strftime("%d/%m/%Y"))
        meses_ferias_idx = [meses.index(m) for m in parametros.meses_ferias if m in meses]

        # ETAPA 3
        print("\n--- Etapa 3: Conversão ---")
        projetos_modelo = converter_projetos_para_modelo(projetos_config, meses, meses_ferias_idx, parametros)

        # ETAPA 4
        print("\n--- Etapa 4: Otimização Estágio 1 ---")
        resultados_estagio1 = stage_1.otimizar_curva_demanda(projetos_modelo, meses, parametros)
        if not resultados_estagio1: sys.exit(1)
        resultados_estagio1['periodo'] = f"{dt_min.strftime('%d/%m/%Y')} a {dt_max.strftime('%d/%m/%Y')}"
        resultados_estagio1['meses_total'] = len(meses)

        # ETAPA 5
        print("\n--- Etapa 5: Otimização Estágio 2 ---")
        resultados_estagio2 = stage_2.otimizar_atribuicao_e_carga(resultados_estagio1['cronograma'], projetos_modelo,
                                                                  meses, meses_ferias_idx, parametros)
        resultados_estagio2['spread_max_permitido'] = parametros.spread_maximo
        if not resultados_estagio2 or resultados_estagio2.get("status") == "falha": sys.exit(1)

        # ETAPA 6
        print("\n--- Etapa 6: Pós-processamento ---")
        resultados_estagio2['atribuicoes'], contagem_instrutores_hab = renumerar_instrutores_ativos(
            resultados_estagio2['atribuicoes'])
        distribuicao_por_projeto = analisar_distribuicao_instrutores_por_projeto(resultados_estagio2['atribuicoes'])

        if parametros_financeiros is None:
            print("\n" + "*" * 60 + "\nCOLETA DE DADOS FINANCEIROS\n" + "*" * 60)
            parametros_financeiros = user_input.obter_parametros_financeiros(projetos_config)
            if input("\nSalvar configuração completa? (S/N) [S]: ").strip().upper() in ('', 'S'):
                config_manager.salvar_configuracao(parametros, projetos_config, parametros_financeiros)

        # ETAPA 7
        print("\n" + "=" * 80 + "\nGERANDO RELATÓRIOS\n" + "=" * 80)
        output_dir = Path("resultados_otimizacao");
        output_dir.mkdir(exist_ok=True)

        print("1. Excel...")
        df_consolidada = spreadsheets.gerar_planilha_consolidada_instrutor(resultados_estagio2['atribuicoes'])
        spreadsheets.gerar_planilha_detalhada(resultados_estagio2['atribuicoes'], meses, meses_ferias_idx,
                                              parametros_financeiros)

        print("2. Gráficos Operacionais...")
        graficos = {}

        # 2.1 Cronograma Consolidado
        try:
            graficos['cronograma_consolidado'] = plotting.gerar_grafico_turmas_projeto_mes(
                resultados_estagio2['turmas'], projetos_modelo, meses, meses_ferias_idx, projeto_filtro=None
            )
            print("  ✓ Cronograma Consolidado")
        except Exception as e:
            print(f"  ⚠ Erro Cronograma Consolidado: {e}")

        # 2.2 Cronograma Individual por Projeto (NOVO)
        for proj in projetos_config:
            try:
                path = plotting.gerar_grafico_turmas_projeto_mes(
                    resultados_estagio2['turmas'], projetos_modelo, meses, meses_ferias_idx, projeto_filtro=proj.nome
                )
                if path: graficos[f'cronograma_{proj.nome}'] = path
                print(f"  ✓ Cronograma {proj.nome}")
            except Exception as e:
                print(f"  ⚠ Erro Cronograma {proj.nome}: {e}")

        # Outros gráficos padrão
        try:
            graficos['instrutor_projeto'] = plotting.gerar_grafico_turmas_instrutor_tipologia_projeto(
                resultados_estagio2['atribuicoes'])
        except Exception as e:
            print(f"  ⚠ Erro gráfico instrutor: {e}")

        try:
            graficos['carga_instrutor'] = plotting.gerar_grafico_carga_por_instrutor(resultados_estagio2['atribuicoes'])
        except Exception as e:
            print(f"  ⚠ Erro gráfico carga: {e}")

        try:
            graficos['prog_rob'], serie_temporal_df = plotting.gerar_grafico_demanda_prog_rob(
                resultados_estagio2['turmas'], projetos_modelo, meses, meses_ferias_idx)
        except Exception as e:
            serie_temporal_df = pd.DataFrame()

        try:
            graficos['conclusoes'] = plotting.plotar_conclusoes_por_mes(resultados_estagio2['turmas'], projetos_modelo,
                                                                        meses, meses_ferias_idx)
        except Exception as e:
            pass

        if parametros_financeiros:
            print("3. Gráficos Financeiros...")
            try:
                graficos['financeiro_consolidado'] = plotting.gerar_grafico_fluxo_caixa(
                    resultados_estagio2['atribuicoes'], meses, meses_ferias_idx, parametros_financeiros)
            except Exception as e:
                print(f"  ⚠ Erro fin consolidado: {e}")

            for proj in projetos_config:
                try:
                    path = plotting.gerar_grafico_fluxo_caixa(resultados_estagio2['atribuicoes'], meses,
                                                              meses_ferias_idx, parametros_financeiros,
                                                              projeto_filtro=proj.nome)
                    if path: graficos[f'financeiro_{proj.nome}'] = path
                except Exception as e:
                    print(f"  ⚠ Erro fin {proj.nome}: {e}")

        print("4. PDF...")
        pdf_generator.gerar_relatorio_pdf(
            projetos_config, resultados_estagio1, resultados_estagio2, graficos, serie_temporal_df,
            df_consolidada, contagem_instrutores_hab, distribuicao_por_projeto, parametros.pico_maximo_turmas,
            parametros_financeiros
        )

        print("5. Limpeza...")
        for path in graficos.values():
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

        print("\n" + "=" * 80 + "\n✓ SUCESSO! Relatórios gerados em 'resultados_otimizacao/'\n" + "=" * 80)

    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        import traceback;
        traceback.print_exc();
        sys.exit(1)


if __name__ == "__main__":
    main()