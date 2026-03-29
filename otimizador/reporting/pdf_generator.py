"""
Módulo de geração de relatórios PDF
Versão 5.5 - Inclusão do Gráfico de Evolução de Pagamentos
"""

from fpdf import FPDF
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from ..data_models import Projeto, ParametrosFinanceiros


class PDFRelatorio(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Relatorio de Planejamento de Turmas e Instrutores', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15);
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}/{{nb}} - Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0,
                  0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12);
        self.set_fill_color(220, 230, 240)
        self.cell(0, 10, title, 0, 1, 'L', 1);
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10);
        self.multi_cell(0, 5, body);
        self.ln()

    def add_image_centered(self, image_path, width=170):
        if image_path:
            if self.get_y() + (width * 0.6) > 270: self.add_page()
            self.image(image_path, x=(210 - width) / 2, w=width);
            self.ln(5)

    def create_table(self, header, data, col_widths):
        self.set_font('Arial', 'B', 9);
        self.set_fill_color(240, 240, 240)
        for col, width in zip(header, col_widths): self.cell(width, 7, col, 1, 0, 'C', 1)
        self.ln();
        self.set_font('Arial', '', 8);
        fill = False
        for row in data:
            for item, width in zip(row, col_widths):
                self.cell(width, 6, str(item).encode('latin-1', 'replace').decode('latin-1'), 1, 0, 'C', fill)
            self.ln();
            fill = not fill


def gerar_relatorio_pdf(projetos_config, resultados_estagio1, resultados_estagio2, graficos_paths, serie_temporal_df,
                        df_consolidada_instrutor, contagem_instrutores_hab, distribuicao_por_projeto,
                        pico_maximo_limite, parametros_financeiros=None, df_evolucao_instrutores=None,
                        df_turmas_abertas=None):
    from ..utils import calcular_fluxo_caixa_detalhado
    pdf = PDFRelatorio();
    pdf.alias_nb_pages();
    pdf.add_page()

    pdf.chapter_title("1. Resumo Executivo")
    pdf.chapter_body(
        f"Planejamento para o periodo de {resultados_estagio1.get('periodo', 'N/A')}.\n- Projetos: {len(projetos_config)}\n- Turmas: {len(resultados_estagio2.get('turmas', []))}")

    pdf.chapter_title("2. Projetos Configurados")
    for proj in projetos_config: pdf.chapter_body(
        f"- {proj.nome}: {proj.num_turmas} turmas | {proj.duracao_curso} meses")

    pdf.add_page();
    pdf.chapter_title("3. Analise de Demanda e Cronograma")
    pdf.add_image_centered(graficos_paths.get('cronograma_consolidado'), 180)
    pdf.add_image_centered(graficos_paths.get('turmas_abertas'), 180)

    pdf.add_page();
    pdf.chapter_title("4. Dimensionamento da Equipe")
    for hab, count in contagem_instrutores_hab.items(): pdf.chapter_body(f"- {hab}: {count} instrutores")
    pdf.create_table(['ID', 'Habilidade', 'Turmas', 'Projetos'],
                     [[r['Instrutor_ID'], r['Habilidade'], r['Total_Turmas'], r['Projetos']] for _, r in
                      df_consolidada_instrutor.iterrows()], [30, 30, 30, 100])

    pdf.add_page();
    pdf.chapter_title("6. Evolucao Mensal da Equipe")
    pdf.add_image_centered(graficos_paths.get('evolucao_instrutores'), 180)

    # 8. FINANCEIRO (ATUALIZADO COM GRÁFICO)
    if parametros_financeiros:
        pdf.add_page();
        pdf.chapter_title("8. Analise Financeira e Fluxo de Caixa")
        if graficos_paths.get('pagamentos_mensais'):
            pdf.add_image_centered(graficos_paths['pagamentos_mensais'], 180)

        pdf.ln(5);
        pdf.set_font('Arial', 'B', 11);
        pdf.cell(0, 10, "8.1. Detalhamento de Fluxo de Caixa", 0, 1)
        meses_list = serie_temporal_df['Mes'].tolist()
        df_fin = calcular_fluxo_caixa_detalhado(resultados_estagio2['atribuicoes'], meses_list,
                                                resultados_estagio1.get('meses_ferias_idx', []), parametros_financeiros)

        data_fin = [[r['Mês'], f"R$ {r['Custo Mensal']:,.2f}", f"R$ {r['Custo Acumulado']:,.2f}"] for _, r in
                    df_fin.iterrows()]
        pdf.create_table(['Mes', 'Custo Mensal', 'Acumulado'], data_fin, [50, 60, 60])

    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    path = f"resultados_otimizacao/Relatorio_Final_{timestamp}.pdf"
    pdf.output(path);
    return path