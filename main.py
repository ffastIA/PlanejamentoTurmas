"""
Sistema de Otimização de Alocação de Instrutores
Versão 2.8 - Com Relatórios Financeiros Completos
Autor: Sistema Idear
"""

import sys
import os
from datetime import datetime
from pathlib import Path
import pandas as pd

# Importações dos módulos internos
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
    """Função principal do sistema de otimização."""
    print("=" * 80)
    print("SISTEMA DE OTIMIZAÇÃO DE ALOCAÇÃO DE INSTRUTORES")
    print("Versão 2.8 (Com Relatórios Financeiros)")
    print("=" * 80)

    try:
        # ===========================
        # ETAPA 1: GERENCIAMENTO E OBTENÇÃO DE CONFIGURAÇÕES
        # ===========================
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
                print(f"\n[Financeiro] Custo Instrutor: R$ {parametros_financeiros.custo_mensal_instrutor:.2f}")

        # ===========================
        # ETAPA 2: PREPARAÇÃO DE DADOS
        # ===========================
        print("\n--- Etapa 2: Preparação de Dados ---")

        dt_min = min(datetime.strptime(p.data_inicio, "%d/%m/%Y") for p in projetos_config)
        dt_max = max(datetime.strptime(p.data_termino, "%d/%m/%Y") for p in projetos_config)

        print(f"Período total: {dt_min.strftime('%d/%m/%Y')} até {dt_max.strftime('%d/%m/%Y')}")

        meses = gerar_lista_meses(
            dt_min.strftime("%d/%m/%Y"),
            dt_max.strftime("%d/%m/%Y")
        )
        print(f"Total de meses: {len(meses)}")

        meses_ferias_idx = [meses.index(m) for m in parametros.meses_ferias if m in meses]
        if meses_ferias_idx:
            print(f"Meses de férias identificados: {len(meses_ferias_idx)}")

        # ===========================
        # ETAPA 3: CONVERSÃO PARA MODELO OTIMIZADO
        # ===========================
        print("\n--- Etapa 3: Conversão de Projetos ---")
        projetos_modelo = converter_projetos_para_modelo(
            projetos_config,
            meses,
            meses_ferias_idx,
            parametros
        )
        print(f"Projetos convertidos: {len(projetos_modelo)}")

        # ===========================
        # ETAPA 4: OTIMIZAÇÃO - ESTÁGIO 1
        # ===========================
        print("\n" + "=" * 80)
        print("ESTÁGIO 1: OTIMIZAÇÃO DO CRONOGRAMA")
        print("=" * 80)

        resultados_estagio1 = stage_1.otimizar_curva_demanda(
            projetos_modelo,
            meses,
            parametros
        )

        if not resultados_estagio1:
            print("\n[ERRO CRÍTICO] O Estágio 1 FALHOU.")
            sys.exit(1)

        resultados_estagio1['periodo'] = f"{dt_min.strftime('%d/%m/%Y')} a {dt_max.strftime('%d/%m/%Y')}"
        resultados_estagio1['meses_total'] = len(meses)

        print("\n✓ Estágio 1 concluído com sucesso!")

        # ===========================
        # ETAPA 5: OTIMIZAÇÃO - ESTÁGIO 2
        # ===========================
        print("\n" + "=" * 80)
        print("ESTÁGIO 2: ATRIBUIÇÃO DE INSTRUTORES")
        print("=" * 80)

        resultados_estagio2 = stage_2.otimizar_atribuicao_e_carga(
            resultados_estagio1['cronograma'],
            projetos_modelo,
            meses,
            meses_ferias_idx,
            parametros
        )

        resultados_estagio2['spread_max_permitido'] = parametros.spread_maximo

        if not resultados_estagio2 or resultados_estagio2.get("status") == "falha":
            print("\n[ERRO] Falha no Estágio 2.")
            sys.exit(1)

        print("\n✓ Estágio 2 concluído com sucesso!")

        # ===========================
        # ETAPA 6: PÓS-PROCESSAMENTO E FINANCEIRO
        # ===========================
        print("\n--- Etapa 6: Pós-processamento ---")

        resultados_estagio2['atribuicoes'], contagem_instrutores_hab = renumerar_instrutores_ativos(
            resultados_estagio2['atribuicoes']
        )
        print("✓ Instrutores renumerados")

        distribuicao_por_projeto = analisar_distribuicao_instrutores_por_projeto(
            resultados_estagio2['atribuicoes']
        )
        print("✓ Distribuição por projeto calculada")

        # --- MÓDULO FINANCEIRO (INPUT) ---
        if parametros_financeiros is None:
            print("\n" + "*" * 60)
            print("COLETA DE DADOS FINANCEIROS")
            print("*" * 60)
            parametros_financeiros = user_input.obter_parametros_financeiros()

            salvar = input("\nDeseja salvar esta configuração completa? (S/N) [S]: ").strip().upper()
            if salvar in ('', 'S'):
                config_manager.salvar_configuracao(parametros, projetos_config, parametros_financeiros)

        # ===========================
        # ETAPA 7: GERAÇÃO DE RELATÓRIOS
        # ===========================
        print("\n" + "=" * 80)
        print("GERANDO VISUALIZAÇÕES E RELATÓRIOS")
        print("=" * 80)

        output_dir = Path("resultados_otimizacao")
        output_dir.mkdir(exist_ok=True)
        print(f"Diretório de saída: {output_dir.absolute()}")

        print("\n1. Gerando planilhas Excel...")
        df_consolidada_instrutor = spreadsheets.gerar_planilha_consolidada_instrutor(
            resultados_estagio2['atribuicoes']
        )
        # Passamos os parametros_financeiros aqui para gerar a aba extra
        spreadsheets.gerar_planilha_detalhada(
            resultados_estagio2['atribuicoes'],
            meses,
            meses_ferias_idx,
            parametros_financeiros
        )

        print("\n2. Gerando gráficos...")
        graficos = {}

        # Gráficos padrão
        try:
            graficos['projeto_mes'] = plotting.gerar_grafico_turmas_projeto_mes(
                resultados_estagio2['turmas'], projetos_modelo, meses, meses_ferias_idx)
            print("  ✓ Gráfico turmas/projeto/mês")
        except Exception as e:
            print(f"  ⚠ Erro: {e}")

        try:
            graficos['instrutor_projeto'] = plotting.gerar_grafico_turmas_instrutor_tipologia_projeto(
                resultados_estagio2['atribuicoes'])
            print("  ✓ Gráfico turmas/instrutor/projeto")
        except Exception as e:
            print(f"  ⚠ Erro: {e}")

        try:
            graficos['carga_instrutor'] = plotting.gerar_grafico_carga_por_instrutor(
                resultados_estagio2['atribuicoes'])
            print("  ✓ Gráfico carga/instrutor")
        except Exception as e:
            print(f"  ⚠ Erro: {e}")

        try:
            graficos['prog_rob'], serie_temporal_df = plotting.gerar_grafico_demanda_prog_rob(
                resultados_estagio2['turmas'], projetos_modelo, meses, meses_ferias_idx)
            print("  ✓ Gráfico demanda PROG/ROB")
        except Exception as e:
            print(f"  ⚠ Erro: {e}")
            serie_temporal_df = pd.DataFrame()

        try:
            graficos['conclusoes'] = plotting.plotar_conclusoes_por_mes(
                resultados_estagio2['turmas'], projetos_modelo, meses, meses_ferias_idx)
            print("  ✓ Gráfico conclusões/mês")
        except Exception as e:
            print(f"  ⚠ Erro: {e}")

        # --- GRÁFICO FINANCEIRO (NOVO) ---
        if parametros_financeiros:
            try:
                graficos['financeiro'] = plotting.gerar_grafico_fluxo_caixa(
                    resultados_estagio2['atribuicoes'],
                    meses,
                    meses_ferias_idx,
                    parametros_financeiros
                )
                print("  ✓ Gráfico Fluxo de Caixa")
            except Exception as e:
                print(f"  ⚠ Erro no gráfico financeiro: {e}")
                graficos['financeiro'] = None

        print("\n3. Gerando relatório PDF...")
        pdf_generator.gerar_relatorio_pdf(
            projetos_config=projetos_config,
            resultados_estagio1=resultados_estagio1,
            resultados_estagio2=resultados_estagio2,
            graficos_paths=graficos,
            serie_temporal_df=serie_temporal_df,
            df_consolidada_instrutor=df_consolidada_instrutor,
            contagem_instrutores_hab=contagem_instrutores_hab,
            distribuicao_por_projeto=distribuicao_por_projeto,
            pico_maximo_limite=parametros.pico_maximo_turmas,
            parametros_financeiros=parametros_financeiros  # Passando o novo parâmetro
        )

        print("\n4. Limpando arquivos temporários...")
        for path in graficos.values():
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"  ⚠ Não foi possível remover {path}: {e}")

        print("\n" + "=" * 80)
        print("✓✓✓ PROCESSO CONCLUÍDO COM SUCESSO! ✓✓✓")
        print("=" * 80)

    except KeyboardInterrupt:
        print("\n\n[!] Operação cancelada pelo usuário.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERRO CRÍTICO] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()