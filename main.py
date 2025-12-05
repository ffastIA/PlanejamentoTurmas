# ARQUIVO: main.py
"""
Sistema de Otimização de Alocação de Instrutores
Versão 2.6 - Corrigida
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


def main():
    """Função principal do sistema de otimização."""
    print("=" * 80)
    print("SISTEMA DE OTIMIZAÇÃO DE ALOCAÇÃO DE INSTRUTORES")
    print("Versão 2.6 (Corrigida)")
    print("=" * 80)

    try:
        # ===========================
        # ETAPA 1: GERENCIAMENTO E OBTENÇÃO DE CONFIGURAÇÕES
        # ===========================
        print("\n--- Etapa 1: Configuração ---")
        parametros, projetos_config = config_manager.menu_gerenciar_configuracoes()

        if not (parametros and projetos_config):
            print("\nCriando nova configuração...")
            parametros = user_input.obter_parametros_usuario()
            projetos_config = user_input.obter_projetos_usuario()

            salvar = input("\nDeseja salvar esta configuração? (S/N) [S]: ").strip().upper()
            if salvar in ('', 'S'):
                config_manager.salvar_configuracao(parametros, projetos_config)
        else:
            print("\nConfigurações carregadas:")
            user_input.exibir_resumo_parametros(parametros)
            user_input.exibir_resumo_projetos(projetos_config)

        # ===========================
        # ETAPA 2: PREPARAÇÃO DE DADOS
        # ===========================
        print("\n--- Etapa 2: Preparação de Dados ---")

        # Calcular intervalo de datas
        dt_min = min(datetime.strptime(p.data_inicio, "%d/%m/%Y") for p in projetos_config)
        dt_max = max(datetime.strptime(p.data_termino, "%d/%m/%Y") for p in projetos_config)

        print(f"Período total: {dt_min.strftime('%d/%m/%Y')} até {dt_max.strftime('%d/%m/%Y')}")

        # Gerar lista de meses
        meses = gerar_lista_meses(
            dt_min.strftime("%d/%m/%Y"),
            dt_max.strftime("%d/%m/%Y")
        )
        print(f"Total de meses: {len(meses)}")

        # Identificar índices dos meses de férias
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
        # ETAPA 4: OTIMIZAÇÃO - ESTÁGIO 1 (Nivelamento de Demanda)
        # ===========================
        print("\n" + "=" * 80)
        print("ESTÁGIO 1: OTIMIZAÇÃO DO CRONOGRAMA (Nivelamento de Demanda)")
        print("=" * 80)

        resultados_estagio1 = stage_1.otimizar_curva_demanda(
            projetos_modelo,
            meses,
            parametros
        )

        # &lt;&lt;&lt; CORREÇÃO: VERIFICAR A FALHA IMEDIATAMENTE APÓS A CHAMADA >>>
        if not resultados_estagio1:
            print("\n" + "="*80)
            print("[ERRO CRÍTICO] O Estágio 1 (Otimização de Cronograma) FALHOU.")
            print("O otimizador não conseguiu encontrar uma solução viável com as restrições atuais.")
            print("\nCAUSAS PROVÁVEIS:")
            print("  1. JANELA DE PROJETO MUITO CURTA: A duração de um projeto, somada aos meses de férias que precisam ser 'pulados', pode exceder a data de término permitida para esse projeto.")
            print("  2. MUITAS TURMAS, POUCO TEMPO: A quantidade total de turmas pode ser muito alta para ser alocada nos meses 'úteis' disponíveis.")
            print("  3. PICO MÁXIMO MUITO RESTRITIVO: O parâmetro 'pico_maximo_turmas' pode ser muito baixo para acomodar a concentração de turmas fora dos meses de férias.")
            print("\nSUGESTÕES:")
            print("  - Revise as datas de início/término e a duração dos projetos na sua configuração.")
            print("  - Considere flexibilizar (aumentar) o parâmetro 'pico_maximo_turmas'.")
            print("="*80)
            sys.exit(1) # Encerra o programa de forma controlada

        # Se chegou aqui, a otimização foi um sucesso. Agora podemos adicionar os dados.
        resultados_estagio1['periodo'] = f"{dt_min.strftime('%d/%m/%Y')} a {dt_max.strftime('%d/%m/%Y')}"
        resultados_estagio1['meses_total'] = len(meses)

        print("\n✓ Estágio 1 concluído com sucesso!")

        # ===========================
        # ETAPA 5: OTIMIZAÇÃO - ESTÁGIO 2 (Atribuição de Instrutores)
        # ===========================
        print("\n" + "=" * 80)
        print("ESTÁGIO 2: ATRIBUIÇÃO DE INSTRUTORES E BALANCEAMENTO")
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
            print("\n[ERRO] Falha no Estágio 2. Tente aumentar o spread ou o timeout.")
            sys.exit(1)

        print("\n✓ Estágio 2 concluído com sucesso!")

        # ===========================
        # ETAPA 6: PÓS-PROCESSAMENTO
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
        spreadsheets.gerar_planilha_detalhada(
            resultados_estagio2['atribuicoes'],
            meses,
            meses_ferias_idx
        )

        print("\n2. Gerando gráficos...")
        graficos = {}

        try:
            graficos['projeto_mes'] = plotting.gerar_grafico_turmas_projeto_mes(
                resultados_estagio2['turmas'],
                projetos_modelo,
                meses,
                meses_ferias_idx
            )
            print("  ✓ Gráfico turmas/projeto/mês")
        except Exception as e:
            print(f"  ⚠ Erro no gráfico turmas/projeto/mês: {e}")
            graficos['projeto_mes'] = None

        try:
            graficos['instrutor_projeto'] = plotting.gerar_grafico_turmas_instrutor_tipologia_projeto(
                resultados_estagio2['atribuicoes']
            )
            print("  ✓ Gráfico turmas/instrutor/projeto")
        except Exception as e:
            print(f"  ⚠ Erro no gráfico turmas/instrutor/projeto: {e}")
            graficos['instrutor_projeto'] = None

        try:
            graficos['carga_instrutor'] = plotting.gerar_grafico_carga_por_instrutor(
                resultados_estagio2['atribuicoes']
            )
            print("  ✓ Gráfico carga/instrutor")
        except Exception as e:
            print(f"  ⚠ Erro no gráfico carga/instrutor: {e}")
            graficos['carga_instrutor'] = None

        try:
            graficos['prog_rob'], serie_temporal_df = plotting.gerar_grafico_demanda_prog_rob(
                resultados_estagio2['turmas'],
                projetos_modelo,
                meses,
                meses_ferias_idx
            )
            print("  ✓ Gráfico demanda PROG/ROB")
        except Exception as e:
            print(f"  ⚠ Erro no gráfico demanda PROG/ROB: {e}")
            graficos['prog_rob'] = None
            serie_temporal_df = pd.DataFrame()

        try:
            grafico_conclusoes = str(output_dir / "grafico_conclusoes_mes.png")
            plotting.plotar_conclusoes_por_mes(
                resultados_estagio2['turmas'],
                projetos_modelo,
                dt_min,
                len(meses),
                grafico_conclusoes
            )
            graficos['conclusoes'] = grafico_conclusoes
            print("  ✓ Gráfico conclusões/mês")
        except Exception as e:
            print(f"  ⚠ Erro no gráfico conclusões/mês: {e}")
            graficos['conclusoes'] = None

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
            pico_maximo_limite=parametros.pico_maximo_turmas  # <<< ALTERAÇÃO >>>
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