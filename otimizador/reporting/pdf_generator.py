from fpdf import FPDF
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd
from ..data_models import ConfiguracaoProjeto, ParametrosFinanceiros
from ..utils import calcular_meses_ativos


class PDFRelatorio(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Relatório de Planejamento de Turmas e Instrutores', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}} - Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0,
                  0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 10, title, 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, body)
        self.ln()

    def add_image_centered(self, image_path, width=170):
        if image_path:
            self.image(image_path, x=(210 - width) / 2, w=width)
            self.ln(5)

    def create_table(self, header, data, col_widths):
        """Cria uma tabela simples no PDF."""
        self.set_font('Arial', 'B', 9)
        self.set_fill_color(240, 240, 240)

        # Header
        for col, width in zip(header, col_widths):
            self.cell(width, 7, col, 1, 0, 'C', 1)
        self.ln()

        # Data
        self.set_font('Arial', '', 8)
        fill = False
        for row in data:
            for item, width in zip(row, col_widths):
                self.cell(width, 6, str(item), 1, 0, 'C', fill)
            self.ln()
            fill = not fill  # Zebra striping


def gerar_relatorio_pdf(projetos_config: List[ConfiguracaoProjeto],
                        resultados_estagio1: Dict,
                        resultados_estagio2: Dict,
                        graficos_paths: Dict[str, str],
                        serie_temporal_df: pd.DataFrame,
                        df_consolidada_instrutor: pd.DataFrame,
                        contagem_instrutores_hab: Dict,
                        distribuicao_por_projeto: Dict,
                        pico_maximo_limite: int,
                        parametros_financeiros: ParametrosFinanceiros = None):
    """Gera o relatório PDF completo com tabelas detalhadas restauradas."""

    pdf = PDFRelatorio()
    pdf.alias_nb_pages()
    pdf.add_page()

    # 1. Resumo Executivo
    pdf.chapter_title("1. Resumo Executivo")
    total_turmas = len(resultados_estagio2['turmas'])
    total_instrutores = resultados_estagio2['total_instrutores_flex']

    texto_resumo = (
        f"Este relatório apresenta o plano otimizado para o período de {resultados_estagio1['periodo']}.\n"
        f"Foram alocadas {total_turmas} turmas distribuídas em {len(projetos_config)} projetos.\n"
        f"A solução requer um quadro de {total_instrutores} instrutores ativos no pico máximo.\n"
        f"O spread (desequilíbrio) de carga entre instrutores foi de {resultados_estagio2['spread_carga']} turmas "
        f"(Máximo permitido: {resultados_estagio2['spread_max_permitido']})."
    )
    pdf.chapter_body(texto_resumo)

    # 2. Configuração dos Projetos
    pdf.chapter_title("2. Projetos Configurados")
    for proj in projetos_config:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 5, f"- {proj.nome}", 0, 1)
        pdf.set_font('Arial', '', 9)
        pdf.cell(10)
        pdf.cell(0, 5, f"Turmas: {proj.num_turmas} | Duração: {proj.duracao_curso} meses | Ondas: {proj.ondas}", 0, 1)
        pdf.cell(10)
        pdf.cell(0, 5, f"Período: {proj.data_inicio} a {proj.data_termino}", 0, 1)
        pdf.ln(2)
    pdf.ln()

    # 3. Análise de Demanda (Estágio 1)
    pdf.add_page()
    pdf.chapter_title("3. Análise de Demanda Temporal")
    pdf.chapter_body(
        f"O pico máximo de turmas simultâneas foi de {resultados_estagio1['pico_max']} "
        f"(Limite configurado: {pico_maximo_limite})."
    )

    if graficos_paths.get('projeto_mes'):
        pdf.add_image_centered(graficos_paths['projeto_mes'])

    # Tabela de Demanda (RESTAURADA)
    if not serie_temporal_df.empty:
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 5, "Detalhamento da Demanda Mensal:", 0, 1)
        pdf.ln(2)

        header = ['Mês', 'Demanda PROG', 'Demanda ROB', 'Total']
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

    # 4. Alocação de Instrutores (Estágio 2)
    pdf.add_page()
    pdf.chapter_title("4. Dimensionamento da Equipe")

    texto_equipe = "Distribuição de instrutores por habilidade:\n"
    for hab, count in contagem_instrutores_hab.items():
        texto_equipe += f" - {hab}: {count} instrutores\n"
    pdf.chapter_body(texto_equipe)

    if graficos_paths.get('carga_instrutor'):
        pdf.add_image_centered(graficos_paths['carga_instrutor'], width=140)

    # Tabela de Instrutores (RESTAURADA)
    if not df_consolidada_instrutor.empty:
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 5, "Lista de Instrutores Alocados:", 0, 1)
        pdf.ln(2)

        header = ['ID', 'Habilidade', 'Total Turmas', 'Projetos']
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

    # 5. Previsão de Conclusões
    pdf.add_page()
    pdf.chapter_title("5. Previsão de Conclusões")
    if graficos_paths.get('conclusoes'):
        pdf.add_image_centered(graficos_paths['conclusoes'])

    # 6. Análise Financeira (NOVO)
    if parametros_financeiros and graficos_paths.get('financeiro'):
        pdf.add_page()
        pdf.chapter_title("6. Análise Financeira (Fluxo de Caixa)")
        pdf.chapter_body(
            f"Considerando um custo médio mensal de R$ {parametros_financeiros.custo_mensal_instrutor:.2f} por instrutor.\n"
        )
        pdf.add_image_centered(graficos_paths['financeiro'])

        # Tabela Financeira Mensal (NOVA)
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 5, "Detalhamento do Fluxo de Caixa Mensal:", 0, 1)
        pdf.ln(2)

        # Recalcular dados financeiros para a tabela (para não depender de passar outro DF)
        meses = serie_temporal_df['Mes'].tolist()
        meses_ferias_idx = resultados_estagio1['meses_ferias']
        custo_unitario = parametros_financeiros.custo_mensal_instrutor

        # Calcular instrutores ativos por mês
        instrutores_ativos_por_mes = {m: set() for m in range(len(meses))}
        for atr in resultados_estagio2['atribuicoes']:
            t = atr['turma']
            i = atr['instrutor']
            meses_ativos = calcular_meses_ativos(t.mes_inicio, t.duracao, meses_ferias_idx, len(meses))
            for m in meses_ativos:
                instrutores_ativos_por_mes[m].add(i.id)

        header = ['Mês', 'Instrutores', 'Custo Mensal', 'Acumulado']
        widths = [40, 30, 50, 50]
        data = []
        acumulado = 0.0

        for m_idx, mes_nome in enumerate(meses):
            qtd = len(instrutores_ativos_por_mes[m_idx])
            custo_mes = qtd * custo_unitario
            acumulado += custo_mes

            data.append([
                mes_nome,
                str(qtd),
                f"R$ {custo_mes:,.2f}",
                f"R$ {acumulado:,.2f}"
            ])

        pdf.create_table(header, data, widths)

    # Salvar
    nome_arquivo = "resultados_otimizacao/Relatorio_Otimizacao_Completo.pdf"
    pdf.output(nome_arquivo)
    print(f"  ✓ Relatório PDF gerado: {nome_arquivo}")