"""
Sistema de Otimização de Alocação de Instrutores
=================================================
Versão : 4.0.0
Data   : 2026-06-22
Autor  : Engine Tecnologia

Histórico de versões
--------------------
4.0.0  2026-06-22  Migração do solver para CP-SAT (OR-Tools); otimização em
                   duas fases no Stage 2; quebra de simetria de instrutores;
                   AddImplication/AddAbsEquality no lugar de linearizações
                   manuais; busca paralela (4 workers); peso_monotonia e
                   peso_spread_mensal expostos no menu de parâmetros.
3.9.0  2026-06    Logging completo e gráficos melhorados.
3.8.0  2026-06    Suavização temporal da equipe (Stage 2 v5.4).
3.7.0  2026-05    Redução de picos de turmas nas previsões.
3.6.0  2026-05    Solver remodelado para reduzir ociosidade da equipe.
3.5.0  2026-04    Branch Ondas — versão estável com alocação de instrutores.
"""

__version__ = "4.0.0"

import sys
import os
from datetime import datetime
from pathlib import Path
import pandas as pd

from otimizador.io import user_input, config_manager
from otimizador.utils_logging import configurar_logging
from otimizador.validacao_viabilidade import validar_viabilidade_configuracao
from otimizador.diagnostico_restricoes import diagnosticar_restricoes
from otimizador.utils import (
    gerar_lista_meses,
    converter_projetos_para_modelo,
    renumerar_instrutores_ativos,
    analisar_distribuicao_instrutores_por_projeto
)
from otimizador.core import stage_1, stage_2
from otimizador.reporting import plotting, spreadsheets, pdf_generator
from otimizador.debug_diagnostico import diagnosticar_fluxo_dados
from otimizador.data_models import ParametrosFinanceiros


def main():
    """
    Função principal do sistema de otimização
    """

    # ========================================================================
    # CONFIGURAR LOGGING (PRIMEIRO!)
    # ========================================================================
    log_file = configurar_logging("Simulacao")

    print("=" * 80)
    print("SISTEMA DE OTIMIZAÇÃO DE ALOCAÇÃO DE INSTRUTORES")
    print(f"Versão {__version__}  |  Engine Tecnologia")
    print("=" * 80)
    print(f"\n📋 Arquivo de log: {log_file}\n")

    try:
        # ========================================================================
        # ETAPA 1: CONFIGURAÇÃO
        # ========================================================================
        print("\n" + "=" * 80)
        print("ETAPA 1: CONFIGURAÇÃO")
        print("=" * 80)

        parametros, projetos_config, parametros_financeiros, arquivo_config = \
            config_manager.menu_gerenciar_configuracoes()

        if not (parametros and projetos_config):
            print("\n[INFO] Criando nova configuração...")
            parametros = user_input.obter_parametros_usuario()
            projetos_config = user_input.obter_projetos_usuario()
            parametros_financeiros = None

            # Salvar imediatamente, antes de qualquer validação ou otimização.
            # Garante que os parâmetros não se percam em caso de erro de inviabilidade.
            print("\n" + "-" * 80)
            print("[INFO] Salvando configuração antes de executar...")
            nome_auto = datetime.now().strftime("config_%Y%m%d_%H%M%S")
            if config_manager.salvar_configuracao(parametros, projetos_config, None, nome_auto):
                arquivo_config = config_manager.CONFIGS_DIR / f"{nome_auto}.json"
                print(f"[INFO] Em caso de erro, edite '{arquivo_config}' e recarregue.")
            print("-" * 80)
        else:
            print("\n[INFO] Configurações carregadas com sucesso")
            user_input.exibir_resumo_parametros(parametros)
            user_input.exibir_resumo_projetos(projetos_config)
            if parametros_financeiros:
                print(f"\n[INFO] Financeiro: {len(parametros_financeiros.itens_custo)} itens de custo configurados")

        # ========================================================================
        # ETAPA 2: PREPARAÇÃO DE DADOS
        # ========================================================================
        print("\n" + "=" * 80)
        print("ETAPA 2: PREPARAÇÃO DE DADOS")
        print("=" * 80)

        dt_min = min(datetime.strptime(p.data_inicio, "%d/%m/%Y") for p in projetos_config)
        dt_max = max(datetime.strptime(p.data_termino, "%d/%m/%Y") for p in projetos_config)
        print(f"\n[INFO] Período: {dt_min.strftime('%d/%m/%Y')} a {dt_max.strftime('%d/%m/%Y')}")

        meses = gerar_lista_meses(dt_min.strftime("%d/%m/%Y"), dt_max.strftime("%d/%m/%Y"))
        meses_ferias_idx = [meses.index(m) for m in parametros.meses_ferias if m in meses]

        print(f"[INFO] Total de meses: {len(meses)}")
        print(f"[INFO] Meses de férias: {len(meses_ferias_idx)} ({', '.join([meses[i] for i in meses_ferias_idx])})")

        # ========================================================================
        # ETAPA 2.5: VALIDAÇÃO DE VIABILIDADE
        # ========================================================================
        print("\n" + "=" * 80)
        print("ETAPA 2.5: VALIDAÇÃO DE VIABILIDADE")
        print("=" * 80)

        eh_viavel, avisos = validar_viabilidade_configuracao(projetos_config, parametros, meses)

        if not eh_viavel:
            print("\n" + "!" * 80)
            print("❌ CONFIGURAÇÃO INVIÁVEL")
            print("Corrija os erros acima antes de continuar")
            print("!" * 80)
            print(f"\n[ERRO] Verifique o arquivo de log para detalhes: {log_file}")
            sys.exit(1)

        # ========================================================================
        # ETAPA 2.6: DIAGNÓSTICO DETALHADO DE RESTRIÇÕES
        # ========================================================================
        print("\n" + "=" * 80)
        print("ETAPA 2.6: DIAGNÓSTICO DETALHADO DE RESTRIÇÕES")
        print("=" * 80)

        diagnosticar_restricoes(projetos_config, parametros, meses)

        # ========================================================================
        # ETAPA 3: CONVERSÃO DE PROJETOS PARA MODELO
        # ========================================================================
        print("\n" + "=" * 80)
        print("ETAPA 3: CONVERSÃO DE PROJETOS PARA MODELO")
        print("=" * 80)

        projetos_modelo = converter_projetos_para_modelo(projetos_config, meses, meses_ferias_idx, parametros)

        print(f"\n[✓] {len(projetos_modelo)} projetos convertidos para modelo")

        # ========================================================================
        # ETAPA 4: OTIMIZAÇÃO ESTÁGIO 1 (CRONOGRAMA)
        # ========================================================================
        print("\n" + "=" * 80)
        print("ETAPA 4: OTIMIZAÇÃO ESTÁGIO 1 (CRONOGRAMA)")
        print("=" * 80)

        resultados_estagio1 = stage_1.otimizar_curva_demanda(projetos_modelo, meses, parametros)

        if not resultados_estagio1:
            print("\n" + "!" * 80)
            print("❌ SOLVER NÃO ENCONTROU SOLUÇÃO VIÁVEL")
            print("!" * 80)
            print("\nDica: Verifique os avisos da Etapa 2.5 e 2.6 acima")
            print("\nPossíveis soluções:")
            print("  1. Aumentar 'pico_maximo_turmas'")
            print("  2. Aumentar número de 'ondas'")
            print("  3. Reduzir 'turmas_min_por_mes'")
            print("  4. Aumentar 'capacidade_max_instrutor'")
            print(f"\n[ERRO] Verifique o arquivo de log para detalhes: {log_file}")
            sys.exit(1)

        resultados_estagio1['periodo'] = f"{dt_min.strftime('%d/%m/%Y')} a {dt_max.strftime('%d/%m/%Y')}"
        resultados_estagio1['meses_total'] = len(meses)

        print(f"\n[✓] Otimização Stage 1 concluída com sucesso")

        # ========================================================================
        # ETAPA 5: OTIMIZAÇÃO ESTÁGIO 2 (ALOCAÇÃO DE INSTRUTORES)
        # ========================================================================
        print("\n" + "=" * 80)
        print("ETAPA 5: OTIMIZAÇÃO ESTÁGIO 2 (ALOCAÇÃO DE INSTRUTORES)")
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
            print("\n[ERRO] Falha na alocação de instrutores")
            print(f"[ERRO] Verifique o arquivo de log para detalhes: {log_file}")
            sys.exit(1)

        print(f"\n[✓] Otimização Stage 2 concluída com sucesso")

        # ========================================================================
        # ETAPA 6: PÓS-PROCESSAMENTO
        # ========================================================================
        print("\n" + "=" * 80)
        print("ETAPA 6: PÓS-PROCESSAMENTO")
        print("=" * 80)

        resultados_estagio2['atribuicoes'], contagem_instrutores_hab = renumerar_instrutores_ativos(
            resultados_estagio2['atribuicoes']
        )
        distribuicao_por_projeto = analisar_distribuicao_instrutores_por_projeto(
            resultados_estagio2['atribuicoes']
        )

        print(f"\n[✓] Pós-processamento concluído")
        print(f"[INFO] Instrutores por habilidade:")
        for hab, count in contagem_instrutores_hab.items():
            print(f"       - {hab}: {count} instrutores")

        # ========================================================================
        # ETAPA 6.5: COLETA DE DADOS FINANCEIROS (SE NECESSÁRIO)
        # ========================================================================
        if parametros_financeiros is None:
            print("\n" + "=" * 80)
            print("ETAPA 6.5: COLETA DE DADOS FINANCEIROS")
            print("=" * 80)

            parametros_financeiros = user_input.obter_parametros_financeiros(projetos_config)

            # Atualiza o arquivo já salvo com os dados financeiros, sem perguntar nome novamente.
            if arquivo_config and arquivo_config.exists():
                nome_existente = arquivo_config.stem
                config_manager.salvar_configuracao(
                    parametros, projetos_config, parametros_financeiros, nome_existente
                )
                print("[✓] Configuração atualizada com dados financeiros")
            else:
                if input("\nSalvar configuração completa? (S/N) [S]: ").strip().upper() in ('', 'S'):
                    config_manager.salvar_configuracao(parametros, projetos_config, parametros_financeiros)
                    print("[✓] Configuração salva com sucesso")

        # ========================================================================
        # ETAPA 7: GERAÇÃO DE RELATÓRIOS
        # ========================================================================
        print("\n" + "=" * 80)
        print("ETAPA 7: GERAÇÃO DE RELATÓRIOS")
        print("=" * 80)

        output_dir = Path("resultados_otimizacao")
        output_dir.mkdir(exist_ok=True)

        # --- 7.1 Excel ---
        print("\n[7.1] Gerando planilhas Excel...")
        try:
            df_consolidada = spreadsheets.gerar_planilha_consolidada_instrutor(
                resultados_estagio2['atribuicoes']
            )
            spreadsheets.gerar_planilha_detalhada(
                resultados_estagio2['atribuicoes'],
                meses,
                meses_ferias_idx,
                parametros_financeiros
            )
            print("      ✓ Planilhas Excel geradas com sucesso")
        except Exception as e:
            print(f"      ⚠ Erro ao gerar Excel: {e}")
            df_consolidada = pd.DataFrame()

        # --- 7.2 Gráficos Operacionais ---
        print("\n[7.2] Gerando gráficos operacionais...")
        graficos = {}

        # Gráfico consolidado
        try:
            graficos['cronograma_consolidado'] = plotting.gerar_grafico_turmas_projeto_mes(
                resultados_estagio2['turmas'],
                projetos_modelo,
                meses,
                meses_ferias_idx,
                projeto_filtro=None
            )
            print("      ✓ Cronograma Consolidado")
        except Exception as e:
            print(f"      ⚠ Erro Cronograma Consolidado: {e}")

        # Gráficos por projeto
        for proj in projetos_config:
            try:
                path = plotting.gerar_grafico_turmas_projeto_mes(
                    resultados_estagio2['turmas'],
                    projetos_modelo,
                    meses,
                    meses_ferias_idx,
                    projeto_filtro=proj.nome
                )
                if path:
                    graficos[f'cronograma_{proj.nome}'] = path
                print(f"      ✓ Cronograma {proj.nome}")
            except Exception as e:
                print(f"      ⚠ Erro Cronograma {proj.nome}: {e}")

        # Gráfico de instrutor por projeto
        try:
            graficos['instrutor_projeto'] = plotting.gerar_grafico_turmas_instrutor_tipologia_projeto(
                resultados_estagio2['atribuicoes']
            )
            print("      ✓ Gráfico Instrutor por Projeto")
        except Exception as e:
            print(f"      ⚠ Erro gráfico instrutor: {e}")

        # Gráfico de carga por instrutor
        try:
            graficos['carga_instrutor'] = plotting.gerar_grafico_carga_por_instrutor(
                resultados_estagio2['atribuicoes']
            )
            print("      ✓ Gráfico Carga por Instrutor")
        except Exception as e:
            print(f"      ⚠ Erro gráfico carga: {e}")

        # Gráfico de demanda PROG vs ROB
        serie_temporal_df = pd.DataFrame()
        try:
            graficos['prog_rob'], serie_temporal_df = plotting.gerar_grafico_demanda_prog_rob(
                resultados_estagio2['turmas'],
                projetos_modelo,
                meses,
                meses_ferias_idx
            )
            print("      ✓ Gráfico Demanda PROG vs ROB")
        except Exception as e:
            print(f"      ⚠ Erro gráfico demanda: {e}")

        # Gráfico de conclusões
        try:
            graficos['conclusoes'] = plotting.plotar_conclusoes_por_mes(
                resultados_estagio2['turmas'],
                projetos_modelo,
                meses,
                meses_ferias_idx
            )
            print("      ✓ Gráfico Conclusões por Mês")
        except Exception as e:
            print(f"      ⚠ Erro gráfico conclusões: {e}")

        # Gráfico de evolução de instrutores
        df_evolucao_instrutores = pd.DataFrame()
        try:
            graficos['evolucao_instrutores'], df_evolucao_instrutores = plotting.gerar_grafico_evolucao_instrutores(
                resultados_estagio2['atribuicoes'],
                meses,
                meses_ferias_idx
            )
            print("      ✓ Gráfico Evolução de Instrutores")
        except Exception as e:
            print(f"      ⚠ Erro Evolução Instrutores: {e}")

        # --- 7.3 Gráficos Financeiros ---
        if parametros_financeiros:
            print("\n[7.3] Gerando gráficos financeiros...")

            try:
                graficos['financeiro_consolidado'] = plotting.gerar_grafico_fluxo_caixa(
                    resultados_estagio2['atribuicoes'],
                    meses,
                    meses_ferias_idx,
                    parametros_financeiros
                )
                print("      ✓ Fluxo de Caixa Consolidado")
            except Exception as e:
                print(f"      ⚠ Erro fluxo consolidado: {e}")

            for proj in projetos_config:
                try:
                    path = plotting.gerar_grafico_fluxo_caixa(
                        resultados_estagio2['atribuicoes'],
                        meses,
                        meses_ferias_idx,
                        parametros_financeiros,
                        projeto_filtro=proj.nome
                    )
                    if path:
                        graficos[f'financeiro_{proj.nome}'] = path
                    print(f"      ✓ Fluxo de Caixa {proj.nome}")
                except Exception as e:
                    print(f"      ⚠ Erro fluxo {proj.nome}: {e}")

        # --- 7.4 Diagnóstico de Fluxo de Dados ---
        print("\n[7.4] Gerando diagnóstico de fluxo de dados...")
        try:
            diagnostico = diagnosticar_fluxo_dados(
                resultados_estagio1['cronograma'],
                resultados_estagio2['turmas'],
                meses,
                meses_ferias_idx
            )

            with open("resultados_otimizacao/diagnostico_fluxo_dados.txt", "w", encoding="utf-8") as f:
                f.write(diagnostico['df_comparacao'].to_string())
            print("      ✓ Diagnóstico de fluxo de dados salvo")
        except Exception as e:
            print(f"      ⚠ Erro diagnóstico: {e}")

        # --- 7.5 Relatório PDF ---
        print("\n[7.5] Gerando relatório PDF...")
        try:
            pdf_generator.gerar_relatorio_pdf(
                projetos_config,
                resultados_estagio1,
                resultados_estagio2,
                graficos,
                serie_temporal_df,
                df_consolidada,
                contagem_instrutores_hab,
                distribuicao_por_projeto,
                parametros.pico_maximo_turmas,
                parametros_financeiros,
                df_evolucao_instrutores
            )
            print("      ✓ Relatório PDF gerado com sucesso")
        except Exception as e:
            print(f"      ⚠ Erro ao gerar PDF: {e}")

        # --- 7.6 Limpeza de Gráficos Temporários ---
        print("\n[7.6] Limpeza de arquivos temporários...")
        for path in graficos.values():
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
        print("      ✓ Limpeza concluída")

        # ========================================================================
        # SUCESSO
        # ========================================================================
        print("\n" + "=" * 80)
        print("✅ SUCESSO!")
        print("=" * 80)
        print("\n📊 Relatórios gerados em 'resultados_otimizacao/':")
        print("   • Relatorio_Otimizacao_Completo.pdf")
        print("   • Planilha_Consolidada_Instrutores.xlsx")
        print("   • Planilha_Detalhada_Atribuicoes.xlsx")
        print("   • diagnostico_fluxo_dados.txt")
        print(f"\n📋 Log completo: {log_file}")
        print("\n" + "=" * 80)

    except KeyboardInterrupt:
        print("\n\n[!] Operação cancelada pelo usuário")
        print(f"[INFO] Verifique o arquivo de log para detalhes: {log_file}")
        sys.exit(0)
    except Exception as e:
        print("\n" + "!" * 80)
        print("[❌ ERRO NÃO TRATADO]")
        print("!" * 80)
        import traceback
        traceback.print_exc()
        print(f"\n[ERRO] Verifique o arquivo de log para detalhes: {log_file}")
        sys.exit(1)


if __name__ == "__main__":
    main()