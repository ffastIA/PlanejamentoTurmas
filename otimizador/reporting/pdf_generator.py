# ARQUIVO: otimizador/reporting/pdf_generator.py
"""
Módulo responsável pela geração de relatórios em PDF.
"""

import os
from pathlib import Path
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import pandas as pd
from typing import List, Dict

# Import relativo
from ..data_models import ConfiguracaoProjeto


class PDF(FPDF):
    """Classe personalizada para geração de PDFs com formatação específica."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.alias_nb_pages()
        self.font_family = 'Helvetica'
        self.bullet = '-'

        # Tentar carregar fontes Unicode
        try:
            # O caminho correto deve ser relativo ao arquivo atual
            font_dir = Path(__file__).parent.parent.parent / "assets" / "fonts"
            self.add_font('DejaVu', '', str(font_dir / 'DejaVuSans.ttf'))
            self.add_font('DejaVu', 'B', str(font_dir / 'DejaVuSans-Bold.ttf'))
            self.add_font('DejaVu', 'I', str(font_dir / 'DejaVuSans-Oblique.ttf'))
            self.font_family = 'DejaVu'
            self.bullet = '•'
            print("[PDF] Fonte Unicode 'DejaVu' carregada com sucesso.")
        except (FileNotFoundError, RuntimeError) as e:
            print(f"\n[AVISO PDF] Fontes Unicode não encontradas. Usando fonte padrão. Erro: {e}\n")

    def header(self):
        """Cabeçalho de cada página."""
        self.set_font(self.font_family, 'B', 16)
        self.cell(0, 10, 'Relatório Executivo de Otimização',
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.set_font(self.font_family, '', 10)
        self.cell(0, 8, 'Planejamento de Alocação de Instrutores',
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.ln(5)

    def footer(self):
        """Rodapé de cada página."""
        self.set_y(-15)
        self.set_font(self.font_family, 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()} de {{nb}}', align='C')

    def chapter_title(self, title: str):
        """Adiciona um título de seção."""
        self.set_font(self.font_family, 'B', 12)
        self.set_fill_color(224, 235, 255)
        self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L', fill=True)
        self.ln(4)

    def chapter_body(self, body: str):
        """Adiciona corpo de texto."""
        self.set_font(self.font_family, '', 10)
        self.multi_cell(0, 5, body)
        self.ln()

    def metric_box(self, title: str, value: str, interpretation: str = ''):
        """Adiciona uma caixa de métrica destacada."""
        self.set_font(self.font_family, 'B', 11)
        self.cell(0, 7, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_font(self.font_family, 'B', 18)
        self.cell(0, 10, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if interpretation:
            self.set_font(self.font_family, 'I', 9)
            self.multi_cell(0, 5, interpretation)

        self.ln(5)

    def add_image_section(self, title: str, image_path: str, description: str = ''):
        """Adiciona uma seção com imagem."""
        if not image_path or not os.path.exists(image_path):
            return

        self.add_page()
        self.chapter_title(title)

        if description:
            self.set_font(self.font_family, '', 10)
            self.multi_cell(0, 5, description, align='L')
            self.ln(5)

        try:
            self.image(image_path, x=10, w=self.w - 20)
        except Exception as e:
            self.set_font(self.font_family, '', 10)
            self.multi_cell(0, 10, f"Erro ao carregar imagem: {e}", align='C')

        self.ln(5)

    def add_table_from_dataframe(self, df: pd.DataFrame, title: str, max_rows: int = 25):
        """Adiciona uma tabela a partir de um DataFrame."""
        if df.empty:
            return

        self.add_page()
        self.chapter_title(title)

        self.set_font(self.font_family, 'B', 8)
        self.set_fill_color(230, 230, 230)

        # Calcular larguras das colunas
        col_widths = {col: (self.w - 20) / len(df.columns) for col in df.columns}

        # Cabeçalho
        for col in df.columns:
            self.cell(col_widths[col], 7, str(col), border=1, align='C', fill=True)
        self.ln()

        # Dados
        self.set_font(self.font_family, '', 7)

        for idx, row in df.head(max_rows).iterrows():
            for col in df.columns:
                cell_text = str(row[col])
                if len(cell_text) > 30:
                    cell_text = cell_text[:27] + '...'

                align = 'L' if isinstance(row[col], str) else 'R'
                self.cell(col_widths[col], 6, cell_text, border=1, align=align)
            self.ln()

        # Nota se houver mais linhas
        if len(df) > max_rows:
            self.set_font(self.font_family, 'I', 8)
            self.cell(0, 6, f"... (mostrando {max_rows} de {len(df)} linhas)", align='C')
            self.ln()


# ==============================================================================
# A FUNÇÃO ABAIXO DEVE ESTAR FORA DA CLASSE PDF (SEM INDENTAÇÃO)
# ==============================================================================

def gerar_relatorio_pdf(
        projetos_config: List[ConfiguracaoProjeto],
        resultados_estagio1: Dict,
        resultados_estagio2: Dict,
        graficos_paths: Dict,
        serie_temporal_df: pd.DataFrame,
        df_consolidada_instrutor: pd.DataFrame,
        contagem_instrutores_hab: Dict[str, int],
        distribuicao_por_projeto: Dict[str, Dict[str, int]]
):
    """
    Gera o relatório executivo final em PDF.
    """
    print("\n--- Gerando Relatório Executivo PDF ---")

    pdf = PDF('P', 'mm', 'A4')
    pdf.add_page()

    bullet = pdf.bullet

    # ===========================
    # 1. SUMÁRIO EXECUTIVO
    # ===========================
    pdf.chapter_title('1. Sumário Executivo')

    total_instrutores = resultados_estagio2.get('total_instrutores_flex', 'N/A')
    spread = resultados_estagio2.get('spread_carga', 'N/A')
    pico_prog = resultados_estagio1.get('pico_prog', 'N/A')
    pico_rob = resultados_estagio1.get('pico_rob', 'N/A')

    pdf.metric_box(
        "Total de Instrutores Necessários",
        str(total_instrutores),
        "Número total de profissionais necessários para cobrir toda a demanda do planejamento."
    )

    count_prog = contagem_instrutores_hab.get('PROG', 0)
    count_rob = contagem_instrutores_hab.get('ROBOTICA', 0)

    pdf.set_font(pdf.font_family, 'B', 10)
    pdf.cell(0, 6, "Detalhamento por Habilidade:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf.font_family, '', 10)
    pdf.multi_cell(0, 5,
                   f"  {bullet} Instrutores de Programação: {count_prog}\n"
                   f"  {bullet} Instrutores de Robótica: {count_rob}"
                   )
    pdf.ln(5)

    pdf.metric_box(
        "Pico de Demanda - Programação",
        f"{pico_prog} Turmas/Mês",
        "Momento de maior necessidade de instrutores de programação no planejamento."
    )

    pdf.metric_box(
        "Pico de Demanda - Robótica",
        f"{pico_rob} Turmas/Mês",
        "Momento de maior necessidade de instrutores de robótica no planejamento."
    )

    pdf.metric_box(
        "Balanceamento de Carga (Spread)",
        str(spread),
        "Diferença entre o instrutor mais e menos sobrecarregado. Quanto menor, mais equilibrado."
    )

    # ===========================
    # 2. CONTEXTO DO PLANEJAMENTO
    # ===========================
    pdf.add_page()
    pdf.chapter_title('2. Contexto do Planejamento')

    pdf.set_font(pdf.font_family, '', 10)
    pdf.multi_cell(0, 5,
                   f"  {bullet} Período de Planejamento: {resultados_estagio1.get('periodo', 'N/A')}\n"
                   f"  {bullet} Total de Meses: {resultados_estagio1.get('meses_total', 'N/A')}\n"
                   f"  {bullet} Total de Projetos: {len(projetos_config)}\n"
                   f"  {bullet} Spread Máximo Permitido: {resultados_estagio2.get('spread_max_permitido', 'N/A')}"
                   )
    pdf.ln(5)

    # ===========================
    # 3. CONFIGURAÇÃO DOS PROJETOS
    # ===========================
    pdf.chapter_title('3. Configuração dos Projetos Analisados')

    for proj in projetos_config:
        pdf.set_font(pdf.font_family, 'B', 10)
        pdf.cell(0, 6, f"  {bullet} Projeto: {proj.nome}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font(pdf.font_family, '', 10)

        # Obter distribuição de instrutores para este projeto
        distribuicao = distribuicao_por_projeto.get(proj.nome, {'PROG': 0, 'ROBOTICA': 0})
        total_alocado = distribuicao['PROG'] + distribuicao['ROBOTICA']

        # Montar texto consolidado
        texto_projeto = (
            f"    - Período: {proj.data_inicio} a {proj.data_termino}\n"
            f"    - Turmas: {proj.num_turmas} | Duração: {proj.duracao_curso} meses | Ondas: {proj.ondas}\n"
            f"    - Proporção Alvo: {proj.percentual_prog:.1f}% PROG / {proj.percentual_rob:.1f}% ROB"
        )

        if total_alocado > 0:
            texto_projeto += (
                f"\n    - Alocação Resultante: {distribuicao['PROG']} PROG / "
                f"{distribuicao['ROBOTICA']} ROB ({total_alocado} no total)"
            )

        pdf.multi_cell(0, 5, texto_projeto)
        pdf.ln(2)

    # ===========================
    # 4. ANÁLISE GRÁFICA
    # ===========================

    # 4.1 Turmas por Projeto/Mês
    if graficos_paths.get('projeto_mes'):
        pdf.add_image_section(
            "4.1. Distribuição de Turmas por Projeto ao Longo do Tempo",
            graficos_paths['projeto_mes'],
            "Este gráfico mostra como as turmas de cada projeto estão distribuídas ao longo dos meses, "
            "permitindo identificar períodos de maior concentração e sobreposições."
        )

    # 4.2 Turmas por Instrutor/Projeto
    if graficos_paths.get('instrutor_projeto'):
        pdf.add_image_section(
            "4.2. Distribuição de Turmas por Instrutor e Projeto",
            graficos_paths['instrutor_projeto'],
            "Visualização de como as turmas foram distribuídas entre os instrutores, "
            "segmentadas por projeto."
        )

    # 4.3 Carga por Instrutor
    if graficos_paths.get('carga_instrutor'):
        pdf.add_image_section(
            "4.3. Balanceamento de Carga entre Instrutores",
            graficos_paths['carga_instrutor'],
            "Análise da carga de trabalho atribuída a cada instrutor, "
            "destacando o nível de balanceamento alcançado."
        )

    # 4.4 Demanda PROG/ROB
    if graficos_paths.get('prog_rob'):
        pdf.add_image_section(
            "4.4. Demanda Mensal por Habilidade",
            graficos_paths['prog_rob'],
            "Comparação da demanda mensal entre instrutores de Programação e Robótica, "
            "com marcação dos períodos de férias."
        )

    # 4.5 NOVO: Conclusões por Mês
    if graficos_paths.get('conclusoes'):
        pdf.add_page()
        pdf.chapter_title("4.5. Cumprimento de Metas: Turmas Concluídas por Mês")

        pdf.set_font(pdf.font_family, '', 10)
        pdf.multi_cell(
            0, 5,
            "Este gráfico mostra a evolução do cumprimento de metas ao longo do tempo, "
            "indicando quantas turmas são finalizadas em cada mês, separadas por projeto. "
            "A visualização permite identificar períodos de alta conclusão e verificar se "
            "os objetivos estão sendo atingidos conforme o planejamento.",
            align='L'
        )
        pdf.ln(5)

        if os.path.exists(graficos_paths['conclusoes']):
            try:
                pdf.image(graficos_paths['conclusoes'], x=10, w=pdf.w - 20)
            except Exception as e:
                pdf.multi_cell(0, 10, f"Erro ao carregar gráfico: {e}", align='C')
        else:
            pdf.multi_cell(0, 10, "Gráfico de conclusões não disponível.", align='C')

    # ===========================
    # 5. APÊNDICES
    # ===========================

    if not serie_temporal_df.empty:
        pdf.add_table_from_dataframe(
            serie_temporal_df,
            title="Apêndice A: Série Temporal da Demanda Mensal",
            max_rows=30
        )

    if not df_consolidada_instrutor.empty:
        pdf.add_table_from_dataframe(
            df_consolidada_instrutor,
            title="Apêndice B: Tabela Consolidada - Instrutor x Projeto",
            max_rows=30
        )

    # ===========================
    # SALVAR PDF
    # ===========================
    caminho_saida = "Relatorio_Otimizacao_Completo.pdf"

    try:
        pdf.output(caminho_saida)
        print(f"\n✓ Relatório PDF gerado com sucesso: {caminho_saida}")
    except Exception as e:
        print(f"\n✗ Erro ao salvar PDF: {e}")
        raise

    return caminho_saida