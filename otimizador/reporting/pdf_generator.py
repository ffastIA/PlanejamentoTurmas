from fpdf import FPDF
from datetime import datetime
from typing import Dict, List
import pandas as pd
from ..data_models import ConfiguracaoProjeto, ParametrosFinanceiros
from ..utils import calcular_fluxo_caixa_detalhado, calcular_meses_ativos


class PDFRelatorio(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Relatorio de Planejamento de Turmas e Instrutores', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}/{{nb}} - Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0,
                  0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(220, 230, 240)
        self.cell(0, 10, title, 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, body)
        self.ln()

    def add_image_centered(self, image_path, width=170):
        if image_path:
            if self.get_y() + (width * 0.6) > 270:
                self.add_page()
            self.image(image_path, x=(210 - width) / 2, w=width)
            self.ln(5)

    def create_table(self, header, data, col_widths):
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
                texto = str(item).encode('latin-1', 'replace').decode('latin-1')
                self.cell(width, 6, texto, 1, 0, 'C', fill)
            self.ln()


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
    pdf = PDFRelatorio()
    pdf.alias_nb_pages()
    pdf.add_page()

    # 1. RESUMO
    pdf.chapter_title("1. Resumo Executivo")
    total_turmas = len(resultados_estagio2['turmas'])
    total_instrutores = resultados_estagio2['total_instrutores_flex']

    texto_resumo = (
        f"Este documento apresenta o planejamento otimizado para o periodo de {resultados_estagio1['periodo']}.\n\n"
        f"- Total de Projetos: {len(projetos_config)}\n"
        f"- Total de Turmas Alocadas: {total_turmas}\n"
        f"- Quadro de Instrutores Necessario (Pico): {total_instrutores}\n"
        f"- Spread de Carga (Equilibrio): {resultados_estagio2['spread_carga']} (Max permitido: {resultados_estagio2['spread_max_permitido']})"
    )
    pdf.chapter_body(texto_resumo)

    # 2. PROJETOS
    pdf.chapter_title("2. Projetos Configurados")
    for proj in projetos_config:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 5, f"- {proj.nome}", 0, 1)
        pdf.set_font('Arial', '', 9)
        pdf.cell(5)
        pdf.cell(0, 5, f"Turmas: {proj.num_turmas} | Duracao: {proj.duracao_curso} meses | Ondas: {proj.ondas}", 0, 1)
        pdf.cell(5)
        pdf.cell(0, 5, f"Periodo: {proj.data_inicio} a {proj.data_termino}", 0, 1)
        pdf.ln(2)
    pdf.ln()

    # 3. CRONOGRAMA DE EXECUÇÃO
    pdf.add_page()
    pdf.chapter_title("3. Analise de Demanda e Cronograma")

    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5,
                   f"O pico maximo de turmas simultaneas identificado foi de {resultados_estagio1['pico_max']} turmas (Limite configurado: {pico_maximo_limite}).")
    pdf.ln(2)

    # 3.1 Consolidado
    if graficos_paths.get('cronograma_consolidado'):
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "3.1. Cronograma de Execucao CONSOLIDADO", 0, 1)
        pdf.add_image_centered(graficos_paths['cronograma_consolidado'], width=180)

    # 3.2 Individuais por Projeto (LOOP)
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

    # 3.3 Demanda por Habilidade
    if graficos_paths.get('prog_rob'):
        pdf.add_page()
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "3.3. Curva de Demanda por Habilidade (PROG vs ROB)", 0, 1)
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

    # 4. EQUIPE
    pdf.add_page()
    pdf.chapter_title("4. Dimensionamento da Equipe")

    texto_equipe = "Distribuicao do quadro de instrutores por habilidade:"
    pdf.chapter_body(texto_equipe)

    pdf.set_font('Arial', '', 9)
    for hab, count in contagem_instrutores_hab.items():
        pdf.cell(10)
        pdf.cell(0, 5, f"- {hab}: {count} instrutores", 0, 1)
    pdf.ln(2)

    if graficos_paths.get('carga_instrutor'):
        pdf.add_image_centered(graficos_paths['carga_instrutor'], width=150)

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

    # 5. CONCLUSÕES
    pdf.add_page()
    pdf.chapter_title("5. Previsao de Conclusoes")
    pdf.chapter_body("Volume de turmas encerrando suas atividades mes a mes.")
    if graficos_paths.get('conclusoes'):
        pdf.add_image_centered(graficos_paths['conclusoes'], width=180)

    # 6. FINANCEIRO
    if parametros_financeiros:
        pdf.add_page()
        pdf.chapter_title("6. Analise Financeira e Fluxo de Caixa")

        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "Premissas de Custos Configuradas:", 0, 1)
        pdf.set_font('Arial', '', 9)
        for item in parametros_financeiros.itens_custo:
            escopo = f"[{item.projeto}]" if item.projeto else "[GLOBAL]"
            pdf.cell(5)
            pdf.cell(0, 5, f"- {escopo} {item.tipo} - {item.descricao}: R$ {item.valor:,.2f}", 0, 1)
        pdf.ln(5)

        # 6.1 Detalhamento por Projeto
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "6.1. Detalhamento por Projeto", 0, 1)

        meses = serie_temporal_df['Mes'].tolist()

        for proj in projetos_config:
            df_proj = calcular_fluxo_caixa_detalhado(
                resultados_estagio2['atribuicoes'],
                meses,
                resultados_estagio1['meses_ferias'],
                parametros_financeiros,
                projeto_filtro=proj.nome
            )

            if not df_proj.empty and df_proj['Custo Mensal'].sum() > 0:
                if pdf.get_y() > 220: pdf.add_page()

                pdf.set_font('Arial', 'B', 11)
                pdf.set_fill_color(245, 245, 245)
                pdf.cell(0, 8, f"Projeto: {proj.nome}", 1, 1, 'L', 1)

                chave_grafico = f"financeiro_{proj.nome}"
                if graficos_paths.get(chave_grafico):
                    pdf.add_image_centered(graficos_paths[chave_grafico], width=160)

                pdf.ln(2)
                data = [[r['Mês'], f"R$ {r['Custo Mensal']:,.2f}", f"R$ {r['Custo Acumulado']:,.2f}"] for _, r in
                        df_proj.iterrows()]
                pdf.create_table(['Mes', 'Custo Mensal', 'Acumulado'], data, [50, 60, 60])
                pdf.ln(5)

        # 6.2 Consolidado
        pdf.add_page()
        pdf.chapter_title("6.2. Fluxo de Caixa CONSOLIDADO")
        pdf.chapter_body("Visao total incluindo custos diretos dos projetos e custos globais/permanentes.")

        if graficos_paths.get('financeiro_consolidado'):
            pdf.add_image_centered(graficos_paths['financeiro_consolidado'], width=180)

        df_fin = calcular_fluxo_caixa_detalhado(
            resultados_estagio2['atribuicoes'],
            meses,
            resultados_estagio1['meses_ferias'],
            parametros_financeiros
        )

        if not df_fin.empty:
            pdf.ln(5)
            data = [[r['Mês'], f"R$ {r['Custo Mensal']:,.2f}", f"R$ {r['Custo Acumulado']:,.2f}"] for _, r in
                    df_fin.iterrows()]
            pdf.create_table(['Mes', 'Custo Mensal', 'Acumulado'], data, [50, 60, 60])

    nome_arquivo = "resultados_otimizacao/Relatorio_Otimizacao_Completo.pdf"
    pdf.output(nome_arquivo)
    print(f"  ✓ Relatório PDF gerado com sucesso: {nome_arquivo}")