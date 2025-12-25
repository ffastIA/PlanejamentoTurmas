from fpdf import FPDF
from datetime import datetime
from typing import Dict, List
import pandas as pd
from ..data_models import ConfiguracaoProjeto, ParametrosFinanceiros
from ..utils import calcular_fluxo_caixa_detalhado, calcular_meses_ativos


class PDFRelatorio(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Relatório de Planejamento Financeiro e Operacional', 0, 1, 'C');
        self.ln(5)

    def footer(self):
        self.set_y(-15);
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pág {self.page_no()}/{{nb}} - {datetime.now().strftime("%d/%m/%Y")}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12);
        self.set_fill_color(200, 220, 255)
        self.cell(0, 10, title, 0, 1, 'L', 1);
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10);
        self.multi_cell(0, 5, body);
        self.ln()

    def add_image_centered(self, path, w=170):
        if path: self.image(path, x=(210 - w) / 2, w=w); self.ln(5)

    def create_table(self, header, data, widths):
        self.set_font('Arial', 'B', 9);
        self.set_fill_color(240, 240, 240)
        for col, w in zip(header, widths): self.cell(w, 7, col, 1, 0, 'C', 1)
        self.ln();
        self.set_font('Arial', '', 8);
        fill = False
        for row in data:
            for item, w in zip(row, widths): self.cell(w, 6, str(item), 1, 0, 'C', fill)
            self.ln();
            fill = not fill


def gerar_relatorio_pdf(projetos_config: List[ConfiguracaoProjeto], resultados_estagio1: Dict,
                        resultados_estagio2: Dict, graficos_paths: Dict, serie_temporal_df: pd.DataFrame,
                        df_consolidada_instrutor: pd.DataFrame, contagem_instrutores_hab: Dict,
                        distribuicao_por_projeto: Dict, pico_maximo_limite: int,
                        parametros_financeiros: ParametrosFinanceiros = None):
    pdf = PDFRelatorio();
    pdf.alias_nb_pages();
    pdf.add_page()

    pdf.chapter_title("1. Resumo Executivo")
    pdf.chapter_body(
        f"Plano otimizado para {resultados_estagio1['periodo']}.\nTurmas: {len(resultados_estagio2['turmas'])} | Instrutores no pico: {resultados_estagio2['total_instrutores_flex']}")

    pdf.chapter_title("2. Projetos")
    for p in projetos_config:
        pdf.set_font('Arial', 'B', 10);
        pdf.cell(0, 5, f"- {p.nome}", 0, 1)
        pdf.set_font('Arial', '', 9);
        pdf.cell(10);
        pdf.cell(0, 5, f"{p.num_turmas} turmas | {p.duracao_curso} meses", 0, 1);
        pdf.ln(2)
    pdf.ln()

    pdf.add_page();
    pdf.chapter_title("3. Demanda Temporal")
    if graficos_paths.get('projeto_mes'): pdf.add_image_centered(graficos_paths['projeto_mes'])
    if not serie_temporal_df.empty:
        pdf.ln(2);
        pdf.set_font('Arial', 'B', 10);
        pdf.cell(0, 5, "Demanda Mensal:", 0, 1);
        pdf.ln(2)
        data = [[r['Mes'], int(r['Demanda_PROG']), int(r['Demanda_ROB']), int(r['Total'])] for _, r in
                serie_temporal_df.iterrows()]
        pdf.create_table(['Mês', 'PROG', 'ROB', 'Total'], data, [40, 40, 40, 40])

    pdf.add_page();
    pdf.chapter_title("4. Equipe")
    if graficos_paths.get('carga_instrutor'): pdf.add_image_centered(graficos_paths['carga_instrutor'], w=140)
    if not df_consolidada_instrutor.empty:
        pdf.ln(5);
        pdf.set_font('Arial', 'B', 10);
        pdf.cell(0, 5, "Instrutores Alocados:", 0, 1);
        pdf.ln(2)
        data = [[r['Instrutor_ID'], r['Habilidade'], r['Total_Turmas'], r['Projetos']] for _, r in
                df_consolidada_instrutor.iterrows()]
        pdf.create_table(['ID', 'Hab', 'Turmas', 'Projetos'], data, [30, 20, 20, 100])

    pdf.add_page();
    pdf.chapter_title("5. Conclusões");
    if graficos_paths.get('conclusoes'): pdf.add_image_centered(graficos_paths['conclusoes'])

    if parametros_financeiros and graficos_paths.get('financeiro'):
        pdf.add_page();
        pdf.chapter_title("6. Fluxo de Caixa Detalhado")

        # Listar custos configurados
        pdf.set_font('Arial', 'B', 10);
        pdf.cell(0, 5, "Itens de Custo Configurados:", 0, 1)
        pdf.set_font('Arial', '', 9)
        for item in parametros_financeiros.itens_custo:
            pdf.cell(10);
            pdf.cell(0, 5, f"- [{item.tipo}] {item.descricao}: R$ {item.valor:,.2f}", 0, 1)
        pdf.ln(5)

        pdf.add_image_centered(graficos_paths['financeiro'])

        # Tabela Financeira
        meses = serie_temporal_df['Mes'].tolist()
        df_fin = calcular_fluxo_caixa_detalhado(resultados_estagio2['atribuicoes'], meses,
                                                resultados_estagio1['meses_ferias'], parametros_financeiros)

        if not df_fin.empty:
            pdf.ln(5);
            pdf.set_font('Arial', 'B', 10);
            pdf.cell(0, 5, "Projeção Mensal:", 0, 1);
            pdf.ln(2)
            data = [[r['Mês'], f"R$ {r['Custo Mensal']:,.2f}", f"R$ {r['Custo Acumulado']:,.2f}"] for _, r in
                    df_fin.iterrows()]
            pdf.create_table(['Mês', 'Custo Mensal', 'Acumulado'], data, [50, 60, 60])

    pdf.output("resultados_otimizacao/Relatorio_Otimizacao_Completo.pdf")
    print("  ✓ PDF gerado.")