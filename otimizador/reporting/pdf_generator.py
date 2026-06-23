"""
Módulo de geração de relatórios PDF
Versão 4.1 — Novo indicador: Ociosidade Mensal (Seção 7)
             Seção financeira renumerada para 8
"""

from fpdf import FPDF
from datetime import datetime
from typing import Dict, List
import pandas as pd
from ..data_models import ConfiguracaoProjeto, ParametrosFinanceiros
from ..utils import calcular_fluxo_caixa_detalhado, calcular_meses_ativos


class PDFRelatorio(FPDF):
    """Classe para geração de relatórios PDF"""

    def header(self):
        """Cabeçalho das páginas"""
        self.set_font('Arial', 'B', 14)
        self.cell(
            0, 10,
            'Relatorio de Planejamento de Turmas e Instrutores',
            0, 1, 'C'
        )
        self.ln(5)

    def footer(self):
        """Rodapé das páginas"""
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(
            0, 10,
            f'Pagina {self.page_no()}/{{nb}} - '
            f'Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}',
            0, 0, 'C'
        )

    def chapter_title(self, title):
        """Título de seção"""
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(220, 230, 240)
        self.cell(0, 10, title, 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, body):
        """Corpo de texto"""
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, body)
        self.ln()

    def add_image_centered(self, image_path, width=170):
        """Adiciona imagem centralizada"""
        if image_path:
            if self.get_y() + (width * 0.6) > 270:
                self.add_page()
            self.image(image_path, x=(210 - width) / 2, w=width)
            self.ln(5)

    def create_table(self, header, data, col_widths):
        """Cria tabela no PDF"""
        estimativa_altura = len(data) * 6 + 10
        if self.get_y() + estimativa_altura > 270:
            self.add_page()

        self.set_font('Arial', 'B', 9)
        self.set_fill_color(240, 240, 240)
        for col, width in zip(header, col_widths):
            self.cell(width, 7, col, 1, 0, 'C', 1)
        self.ln()

        self.set_font('Arial', '', 8)
        fill = False
        for row in data:
            for item, width in zip(row, col_widths):
                texto = (
                    str(item)
                    .encode('latin-1', 'replace')
                    .decode('latin-1')
                )
                self.cell(width, 6, texto, 1, 0, 'C', fill)
            self.ln()
            fill = not fill


# =============================================================================
# FUNÇÃO AUXILIAR — CÁLCULO DE OCIOSIDADE MENSAL
# =============================================================================

def _calcular_ociosidade_mensal(
    df_evolucao_instrutores: pd.DataFrame,
    serie_temporal_df: pd.DataFrame,
    capacidade_max_instrutor: int
) -> pd.DataFrame:
    """
    Calcula o indicador de ociosidade mensal global.

    Fórmula:
      capacidade_total[m] = instrutores_ativos[m] × capacidade_max
      turmas_ativas[m]    = demanda total do mês (PROG + ROB)
      ocioso_abs[m]       = capacidade_total[m] - turmas_ativas[m]
      ocioso_pct[m]       = ocioso_abs[m] / capacidade_total[m]

    Fontes:
      df_evolucao_instrutores → coluna 'Total' (instrutores ativos/mês)
      serie_temporal_df       → coluna 'Total' (turmas ativas/mês)

    Retorna DataFrame com colunas:
      Mes, Instrutores_Ativos, Capacidade_Total,
      Turmas_Ativas, Ociosidade_Abs, Ociosidade_Pct
    """
    if df_evolucao_instrutores is None \
            or df_evolucao_instrutores.empty \
            or serie_temporal_df is None \
            or serie_temporal_df.empty:
        return pd.DataFrame()

    # Alinhar pelos meses presentes em ambos os DataFrames
    df_evo  = df_evolucao_instrutores.set_index('Mes')
    df_dem  = serie_temporal_df.set_index('Mes')
    meses_comuns = df_evo.index.intersection(df_dem.index)

    registros = []
    for mes in meses_comuns:
        inst_ativos     = int(df_evo.loc[mes, 'Total'])
        turmas_ativas   = int(df_dem.loc[mes, 'Total'])
        cap_total       = inst_ativos * capacidade_max_instrutor

        if cap_total == 0:
            # Mês sem instrutores ativos — ociosidade indefinida
            continue

        ocioso_abs = max(0, cap_total - turmas_ativas)
        ocioso_pct = ocioso_abs / cap_total * 100

        registros.append({
            'Mes':              mes,
            'Instrutores_Ativos': inst_ativos,
            'Capacidade_Total': cap_total,
            'Turmas_Ativas':    turmas_ativas,
            'Ociosidade_Abs':   ocioso_abs,
            'Ociosidade_Pct':   round(ocioso_pct, 1)
        })

    return pd.DataFrame(registros)


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def gerar_relatorio_pdf(
    projetos_config: List[ConfiguracaoProjeto],
    resultados_estagio1: Dict,
    resultados_estagio2: Dict,
    graficos_paths: Dict[str, str],
    serie_temporal_df: pd.DataFrame,
    df_consolidada_instrutor: pd.DataFrame,
    contagem_instrutores_hab: Dict,
    distribuicao_por_projeto: Dict,
    pico_maximo_limite: int,
    parametros_financeiros: ParametrosFinanceiros = None,
    df_evolucao_instrutores: pd.DataFrame = None
):
    """
    Gera relatório PDF completo de otimização.

    v4.1:
      - Seção 7 (NOVA): Ociosidade Mensal — indicador global,
        absoluto e percentual, derivado de df_evolucao_instrutores
        e serie_temporal_df. Nenhum parâmetro novo na assinatura.
      - Seção 8: Análise Financeira (era seção 7 na v4.0)
      - Todo o restante do relatório permanece 100% inalterado.
      - Nome com timestamp preservado da v4.0.
    """

    pdf = PDFRelatorio()
    pdf.alias_nb_pages()
    pdf.add_page()

    # =========================================================================
    # PRÉ-CÁLCULO: Pico correto de instrutores (v3.9)
    # =========================================================================
    pico_instrutores_real = 0
    mes_pico              = "desconhecido"
    instrutores_prog_pico = 0
    instrutores_rob_pico  = 0

    if (df_evolucao_instrutores is not None
            and not df_evolucao_instrutores.empty):
        pico_idx              = df_evolucao_instrutores['Total'].idxmax()
        pico_instrutores_real = int(
            df_evolucao_instrutores.loc[pico_idx, 'Total']
        )
        mes_pico              = df_evolucao_instrutores.loc[pico_idx, 'Mes']
        instrutores_prog_pico = int(
            df_evolucao_instrutores.loc[pico_idx, 'Instrutores_PROG']
        )
        instrutores_rob_pico  = int(
            df_evolucao_instrutores.loc[pico_idx, 'Instrutores_ROB']
        )
    else:
        pico_instrutores_real = sum(contagem_instrutores_hab.values())
        for hab, count in contagem_instrutores_hab.items():
            if hab == 'PROG':
                instrutores_prog_pico = count
            elif hab == 'ROBOTICA':
                instrutores_rob_pico = count

    # =========================================================================
    # PRÉ-CÁLCULO: Ociosidade Mensal (v4.1)
    # Derivado exclusivamente de fontes já disponíveis na assinatura
    # =========================================================================
    capacidade_max = resultados_estagio2.get(
        'capacidade_max_instrutor',
        # Fallback: inferir da contagem de instrutores e spread
        8  # valor padrão do sistema
    )

    # Tentar obter capacidade_max_instrutor do resultado do stage 2
    # Se não disponível no dict, usar o atributo dos instrutores
    atribuicoes = resultados_estagio2.get('atribuicoes', [])
    if atribuicoes:
        capacidade_max = atribuicoes[0]['instrutor'].capacidade

    df_ociosidade = _calcular_ociosidade_mensal(
        df_evolucao_instrutores,
        serie_temporal_df,
        capacidade_max
    )

    # =========================================================================
    # 1. RESUMO EXECUTIVO — INALTERADO
    # =========================================================================
    pdf.chapter_title("1. Resumo Executivo")
    total_turmas = len(resultados_estagio2['turmas'])

    texto_resumo = (
        f"Este documento apresenta o planejamento otimizado para o "
        f"periodo de {resultados_estagio1['periodo']}.\n\n"
        f"- Total de Projetos: {len(projetos_config)}\n"
        f"- Total de Turmas Alocadas: {total_turmas}\n"
        f"- Quadro de Instrutores Necessario (Pico): "
        f"{pico_instrutores_real}\n"
        f"  (Pico em {mes_pico}: "
        f"{instrutores_prog_pico} PROG + {instrutores_rob_pico} ROB)\n"
        f"- Spread de Carga (Equilibrio): "
        f"{resultados_estagio2['spread_carga']} "
        f"(Max permitido: {resultados_estagio2['spread_max_permitido']})\n"
        f"- Capacidade de turmas por instrutor: "
        f"{capacidade_max} turmas/instrutor"
    )
    pdf.chapter_body(texto_resumo)

    # =========================================================================
    # 2. PROJETOS CONFIGURADOS — INALTERADO
    # =========================================================================
    pdf.chapter_title("2. Projetos Configurados")
    for proj in projetos_config:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 5, f"- {proj.nome}", 0, 1)
        pdf.set_font('Arial', '', 9)
        pdf.cell(5)
        pdf.cell(
            0, 5,
            f"Turmas: {proj.num_turmas} | "
            f"Duracao: {proj.duracao_curso} meses | "
            f"Ondas: {proj.ondas}",
            0, 1
        )
        pdf.cell(5)
        pdf.cell(
            0, 5,
            f"Periodo: {proj.data_inicio} a {proj.data_termino}",
            0, 1
        )
        pdf.ln(2)
    pdf.ln()

    # =========================================================================
    # 3. ANÁLISE DE DEMANDA E CRONOGRAMA — INALTERADO
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("3. Analise de Demanda e Cronograma")
    pdf.set_font('Arial', '', 10)

    pico_turmas = 0
    if not serie_temporal_df.empty:
        pico_turmas = int(serie_temporal_df['Total'].max())

    pdf.multi_cell(
        0, 5,
        f"O pico maximo de turmas simultaneas identificado foi de "
        f"{pico_turmas} turmas "
        f"(Limite configurado: {pico_maximo_limite})."
    )
    pdf.ln(2)

    if graficos_paths.get('cronograma_consolidado'):
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "3.1. Cronograma de Execucao CONSOLIDADO", 0, 1)
        pdf.add_image_centered(
            graficos_paths['cronograma_consolidado'], width=180
        )

    pdf.ln(5)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, "3.2. Detalhamento de Execucao por Projeto", 0, 1)
    for proj in projetos_config:
        chave = f"cronograma_{proj.nome}"
        if graficos_paths.get(chave):
            pdf.set_font('Arial', 'I', 10)
            pdf.cell(0, 8, f"- Projeto: {proj.nome}", 0, 1)
            pdf.add_image_centered(graficos_paths[chave], width=160)
            pdf.ln(2)

    if graficos_paths.get('prog_rob'):
        pdf.add_page()
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(
            0, 8,
            "3.3. Curva de Demanda por Habilidade (PROG vs ROB)",
            0, 1
        )
        pdf.add_image_centered(graficos_paths['prog_rob'], width=180)

    if not serie_temporal_df.empty:
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "Tabela de Demanda Mensal Consolidada", 0, 1)
        header = ['Mes', 'Demanda PROG', 'Demanda ROB', 'Total Turmas']
        widths = [40, 40, 40, 40]
        data = []
        for _, row in serie_temporal_df.iterrows():
            data.append([
                row['Mes'],
                int(row['Demanda_PROG']),
                int(row['Demanda_ROB']),
                int(row['Total'])
            ])
        pdf.create_table(header, data, widths)

    # =========================================================================
    # 4. DIMENSIONAMENTO DA EQUIPE — INALTERADO
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("4. Dimensionamento da Equipe")
    pdf.chapter_body(
        "Distribuicao do quadro de instrutores por habilidade:"
    )

    pdf.set_font('Arial', '', 9)
    for hab, count in contagem_instrutores_hab.items():
        pdf.cell(10)
        pdf.cell(0, 5, f"- {hab}: {count} instrutores", 0, 1)
    pdf.ln(2)

    if graficos_paths.get('carga_instrutor'):
        pdf.add_image_centered(
            graficos_paths['carga_instrutor'], width=150
        )

    if not df_consolidada_instrutor.empty:
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "Relacao de Instrutores Alocados", 0, 1)
        header = ['ID', 'Habilidade', 'Total Turmas', 'Projetos Atendidos']
        widths = [30, 30, 30, 100]
        data = []
        for _, row in df_consolidada_instrutor.iterrows():
            data.append([
                row['Instrutor_ID'],
                row['Habilidade'],
                row['Total_Turmas'],
                row['Projetos']
            ])
        pdf.create_table(header, data, widths)

    # =========================================================================
    # 5. PREVISÃO DE CONCLUSÕES — INALTERADO
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("5. Previsao de Conclusoes")
    pdf.chapter_body(
        "Volume de turmas encerrando suas atividades mes a mes."
    )
    if graficos_paths.get('conclusoes'):
        pdf.add_image_centered(graficos_paths['conclusoes'], width=180)

    # =========================================================================
    # 6. EVOLUÇÃO MENSAL DA EQUIPE — INALTERADO
    # =========================================================================
    if (df_evolucao_instrutores is not None
            and not df_evolucao_instrutores.empty):
        pdf.add_page()
        pdf.chapter_title("6. Evolucao Mensal da Equipe")
        pdf.chapter_body(
            "Analise da quantidade de instrutores ativos por mes, "
            "segregados por tipologia."
        )

        if graficos_paths.get('evolucao_instrutores'):
            pdf.add_image_centered(
                graficos_paths['evolucao_instrutores'], width=180
            )

        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "Tabela de Instrutores Ativos por Mes", 0, 1)
        header = ['Mes', 'Instrutores PROG', 'Instrutores ROB', 'Total']
        widths = [40, 45, 45, 30]
        data = []
        for _, row in df_evolucao_instrutores.iterrows():
            data.append([
                row['Mes'],
                int(row['Instrutores_PROG']),
                int(row['Instrutores_ROB']),
                int(row['Total'])
            ])
        pdf.create_table(header, data, widths)

    # =========================================================================
    # 7. OCIOSIDADE MENSAL — NOVO v4.1
    #
    # Indicador global (não por projeto).
    # Ociosidade = razão entre capacidade ociosa e capacidade total.
    #
    # Coluna "Ociosidade Abs": turmas que poderiam ser absorvidas
    #   mas não estão sendo utilizadas naquele mês.
    # Coluna "Ociosidade (%)": percentual da capacidade ociosa.
    #
    # Fórmula:
    #   capacidade_total[m] = instrutores_ativos[m] × cap_max_instrutor
    #   ociosidade_abs[m]   = capacidade_total[m] - turmas_ativas[m]
    #   ociosidade_pct[m]   = ociosidade_abs[m] / capacidade_total[m]
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("7. Ociosidade Mensal")
    pdf.chapter_body(
        "Analise global da ociosidade da equipe de instrutores mes a mes.\n"
        "A ociosidade e definida como a razao entre a capacidade nao "
        "utilizada e a capacidade total disponivel no mes.\n\n"
        f"Capacidade por instrutor: {capacidade_max} turmas/mes\n"
        "Capacidade Total (mes) = Instrutores Ativos x Capacidade Max\n"
        "Ociosidade Abs = Capacidade Total - Turmas Ativas\n"
        "Ociosidade (%) = Ociosidade Abs / Capacidade Total x 100"
    )

    if not df_ociosidade.empty:
        # ── Indicadores de síntese ────────────────────────────────────────────
        ocio_media  = df_ociosidade['Ociosidade_Pct'].mean()
        ocio_max    = df_ociosidade['Ociosidade_Pct'].max()
        mes_ocio_max = df_ociosidade.loc[
            df_ociosidade['Ociosidade_Pct'].idxmax(), 'Mes'
        ]
        ocio_min    = df_ociosidade['Ociosidade_Pct'].min()
        mes_ocio_min = df_ociosidade.loc[
            df_ociosidade['Ociosidade_Pct'].idxmin(), 'Mes'
        ]

        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "Sintese de Ociosidade:", 0, 1)
        pdf.set_font('Arial', '', 9)
        pdf.cell(10)
        pdf.cell(
            0, 5,
            f"- Media mensal:  {ocio_media:.1f}%",
            0, 1
        )
        pdf.cell(10)
        pdf.cell(
            0, 5,
            f"- Maior ociosidade: {ocio_max:.1f}% em {mes_ocio_max}",
            0, 1
        )
        pdf.cell(10)
        pdf.cell(
            0, 5,
            f"- Menor ociosidade: {ocio_min:.1f}% em {mes_ocio_min}",
            0, 1
        )
        pdf.ln(5)

        # ── Tabela detalhada mês a mês ────────────────────────────────────────
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "Detalhamento Mensal:", 0, 1)

        header = [
            'Mes',
            'Inst. Ativos',
            'Cap. Total',
            'Turmas Ativas',
            'Ociosidade Abs',
            'Ociosidade (%)'
        ]
        widths = [28, 28, 28, 35, 38, 33]
        data = []
        for _, row in df_ociosidade.iterrows():
            data.append([
                row['Mes'],
                int(row['Instrutores_Ativos']),
                int(row['Capacidade_Total']),
                int(row['Turmas_Ativas']),
                int(row['Ociosidade_Abs']),
                f"{row['Ociosidade_Pct']:.1f}%"
            ])
        pdf.create_table(header, data, widths)

    else:
        pdf.chapter_body(
            "Dados insuficientes para calcular ociosidade mensal.\n"
            "Verifique se df_evolucao_instrutores e "
            "serie_temporal_df estao disponiveis."
        )

    # =========================================================================
    # 8. ANÁLISE FINANCEIRA E FLUXO DE CAIXA — era seção 7, inalterada
    # =========================================================================
    if parametros_financeiros:
        pdf.add_page()
        pdf.chapter_title("8. Analise Financeira e Fluxo de Caixa")

        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "Premissas de Custos Configuradas:", 0, 1)
        pdf.set_font('Arial', '', 9)
        for item in parametros_financeiros.itens_custo:
            escopo = (
                f"[{item.projeto}]" if item.projeto else "[GLOBAL]"
            )
            pdf.cell(5)
            pdf.cell(
                0, 5,
                f"- {escopo} {item.tipo} - {item.descricao}: "
                f"R$ {item.valor:,.2f}",
                0, 1
            )
        pdf.ln(5)

        # 8.1 Detalhamento por Projeto
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "8.1. Detalhamento por Projeto", 0, 1)

        meses = (
            serie_temporal_df['Mes'].tolist()
            if not serie_temporal_df.empty else []
        )

        for proj in projetos_config:
            df_proj = calcular_fluxo_caixa_detalhado(
                resultados_estagio2['atribuicoes'],
                meses,
                resultados_estagio1.get('meses_ferias', []),
                parametros_financeiros,
                projeto_filtro=proj.nome
            )

            if (not df_proj.empty
                    and df_proj['Custo Mensal'].sum() > 0):
                if pdf.get_y() > 220:
                    pdf.add_page()

                pdf.set_font('Arial', 'B', 11)
                pdf.set_fill_color(245, 245, 245)
                pdf.cell(
                    0, 8, f"Projeto: {proj.nome}", 1, 1, 'L', 1
                )

                chave_grafico = f"financeiro_{proj.nome}"
                if graficos_paths.get(chave_grafico):
                    pdf.add_image_centered(
                        graficos_paths[chave_grafico], width=160
                    )

                pdf.ln(2)
                data = [
                    [
                        r['Mês'],
                        f"R$ {r['Custo Mensal']:,.2f}",
                        f"R$ {r['Custo Acumulado']:,.2f}"
                    ]
                    for _, r in df_proj.iterrows()
                ]
                pdf.create_table(
                    ['Mes', 'Custo Mensal', 'Acumulado'],
                    data, [50, 60, 60]
                )
                pdf.ln(5)

        # 8.2 Fluxo de Caixa Consolidado
        pdf.add_page()
        pdf.chapter_title("8.2. Fluxo de Caixa CONSOLIDADO")
        pdf.chapter_body(
            "Visao total incluindo custos diretos dos projetos "
            "e custos globais/permanentes."
        )

        if graficos_paths.get('financeiro_consolidado'):
            pdf.add_image_centered(
                graficos_paths['financeiro_consolidado'], width=180
            )

        df_fin = calcular_fluxo_caixa_detalhado(
            resultados_estagio2['atribuicoes'],
            meses,
            resultados_estagio1.get('meses_ferias', []),
            parametros_financeiros
        )

        if not df_fin.empty:
            pdf.ln(5)
            data = [
                [
                    r['Mês'],
                    f"R$ {r['Custo Mensal']:,.2f}",
                    f"R$ {r['Custo Acumulado']:,.2f}"
                ]
                for _, r in df_fin.iterrows()
            ]
            pdf.create_table(
                ['Mes', 'Custo Mensal', 'Acumulado'],
                data, [50, 60, 60]
            )

    # =========================================================================
    # GERAR PDF — timestamp no nome (v4.0)
    # =========================================================================
    timestamp    = datetime.now().strftime("%y%m%d_%H%M%S")
    nome_arquivo = (
        f"resultados_otimizacao/"
        f"Relatorio_Otimizacao_Completo_{timestamp}.pdf"
    )

    pdf.output(nome_arquivo)

    print(f"  ✓ Relatório PDF gerado: {nome_arquivo}")
    print(
        f"    [v3.9] Pico de instrutores: {pico_instrutores_real} "
        f"(máximo simultâneo em {mes_pico})"
    )
    if not df_ociosidade.empty:
        print(
            f"    [v4.1] Ociosidade média: "
            f"{df_ociosidade['Ociosidade_Pct'].mean():.1f}%"
        )

    return nome_arquivo