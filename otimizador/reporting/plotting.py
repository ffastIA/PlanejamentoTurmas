# ARQUIVO: otimizador/reporting/plotting.py
"""
Módulo responsável pela geração de gráficos e visualizações.
Versão 4.0 - Lógica de Férias Sincronizada
"""

import os
from collections import defaultdict
from typing import List, Dict, Tuple
import calendar

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from pathlib import Path

# --- Importações Corrigidas ---
from ..data_models import Turma, Projeto
# Importa a função central que contém a lógica de "pular" as férias
from ..utils import calcular_meses_ativos

def _gerar_grafico_vazio(titulo: str, caminho: str = None) -> str:
    """
    Gera um gráfico vazio com mensagem de ausência de dados.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.text(0.5, 0.5, 'Sem dados disponíveis para este gráfico', ha='center', va='center', fontsize=14, color='gray')
    ax.set_title(titulo, fontsize=14, fontweight='bold')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')

    output_dir = Path("resultados_otimizacao")
    output_dir.mkdir(exist_ok=True)

    if not caminho:
        # Garante um nome de arquivo válido
        nome_arquivo = f"grafico_vazio_{titulo.replace(' ', '_').replace('/', '').lower()}.png"
        caminho = str(output_dir / nome_arquivo)

    plt.savefig(caminho, dpi=150, bbox_inches='tight')
    plt.close()
    return caminho


def gerar_grafico_turmas_projeto_mes(turmas: List[Turma], projetos: List[Projeto], meses: List[str],
                                     meses_ferias: List[int]) -> str:
    """
    CORRIGIDO: Gera gráfico de turmas por projeto, respeitando a lógica de pular férias.
    """
    print("  Calculando gráfico de turmas por projeto/mês (Lógica de Férias Sincronizada)...")
    dados = []
    num_meses_total = len(meses)

    for turma in turmas:
        projeto_base_nome = turma.projeto.split('_Onda')[0]

        # --- Lógica Corrigida ---
        # Usa a função central para obter os meses de atividade real
        meses_ativos_reais = calcular_meses_ativos(turma.mes_inicio, turma.duracao, meses_ferias, num_meses_total)

        for mes_idx in meses_ativos_reais:
            dados.append({
                'Projeto': projeto_base_nome,
                'Mes': meses[mes_idx],
            })

    if not dados:
        return _gerar_grafico_vazio("Turmas por Projeto/Mês")

    df = pd.DataFrame(dados)
    df['Mes'] = pd.Categorical(df['Mes'], categories=meses, ordered=True)
    pivot = df.groupby(['Projeto', 'Mes'], observed=False).size().unstack(fill_value=0)

    # Garante que todos os meses do calendário apareçam no gráfico na ordem correta
    pivot = pivot.reindex(columns=meses, fill_value=0)

    fig, ax = plt.subplots(figsize=(16, 8))
    pivot.T.plot(kind='bar', stacked=True, ax=ax, colormap='tab20', width=0.8)

    ax.set_xlabel('Mês', fontsize=12, fontweight='bold')
    ax.set_ylabel('Número de Turmas Ativas', fontsize=12, fontweight='bold')
    ax.set_title('Turmas Ativas por Projeto ao Longo do Tempo', fontsize=14, fontweight='bold')
    ax.legend(title='Projetos', bbox_to_anchor=(1.05, 1), loc='upper left')

    # Destaca as colunas dos meses de férias para verificação visual
    for mes_idx in meses_ferias:
        ax.get_xticklabels()[mes_idx].set_color("red")
        ax.get_xticklabels()[mes_idx].set_fontweight('bold')

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    output_dir = Path("resultados_otimizacao")
    output_dir.mkdir(exist_ok=True)
    caminho = str(output_dir / "grafico_turmas_projeto_mes.png")

    plt.savefig(caminho, dpi=300, bbox_inches='tight')
    plt.close()
    return caminho


def gerar_grafico_demanda_prog_rob(turmas: List[Turma], projetos: List[Projeto], meses: List[str],
                                   meses_ferias_idx: List[int]) -> Tuple[str, pd.DataFrame]:
    """
    CORRIGIDO: Gera gráfico da demanda mensal por habilidade, respeitando a lógica de pular férias.
    """
    print("  Calculando demanda mensal por habilidade (Lógica de Férias Sincronizada)...")
    output_dir = Path("resultados_otimizacao")
    output_dir.mkdir(exist_ok=True)
    caminho_grafico = str(output_dir / "grafico_demanda_prog_rob.png")

    num_meses_total = len(meses)
    demanda = {"Mês": meses, "PROG": [0] * num_meses_total, "ROB": [0] * num_meses_total}

    for turma in turmas:
        tipo = turma.habilidade

        # --- Lógica Corrigida ---
        # Usa a função central para obter os meses de atividade real
        meses_ativos_reais = calcular_meses_ativos(turma.mes_inicio, turma.duracao, meses_ferias_idx, num_meses_total)

        # Adiciona demanda apenas nos meses de atividade real
        for mes_idx in meses_ativos_reais:
            if tipo == 'PROG':
                demanda["PROG"][mes_idx] += 1
            else:
                demanda["ROB"][mes_idx] += 1

    df = pd.DataFrame(demanda)
    df.rename(columns={'PROG': 'Demanda PROG', 'ROB': 'Demanda ROB'}, inplace=True)

    # O código de plotagem a partir daqui permanece o mesmo, mas agora opera sobre os dados corretos
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(16, 8))
    ax.plot(df['Mês'], df['Demanda PROG'], marker='o', linestyle='-', label='Demanda PROG', color='royalblue')
    ax.plot(df['Mês'], df['Demanda ROB'], marker='s', linestyle='--', label='Demanda ROB', color='firebrick')

    for i, txt in enumerate(df['Demanda PROG']):
        if txt > 0: ax.annotate(txt, (df['Mês'][i], df['Demanda PROG'][i]), textcoords="offset points", xytext=(0, 5),
                                ha='center', fontsize=8)
    for i, txt in enumerate(df['Demanda ROB']):
        if txt > 0: ax.annotate(txt, (df['Mês'][i], df['Demanda ROB'][i]), textcoords="offset points", xytext=(0, 5),
                                ha='center', fontsize=8)

    for mes_idx in meses_ferias_idx:
        ax.axvspan(mes_idx - 0.5, mes_idx + 0.5, color='gold', alpha=0.3, zorder=0,
                   label='Férias' if mes_idx == meses_ferias_idx[0] else "")

    ax.set_title('Demanda Mensal de Turmas por Habilidade (PROG vs ROB)', fontsize=16, pad=20)
    ax.set_xlabel('Mês', fontsize=12)
    ax.set_ylabel('Número de Turmas Ativas', fontsize=12)
    ax.tick_params(axis='x', rotation=45, labelsize=9)
    ax.legend()
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.tight_layout()
    fig.savefig(caminho_grafico)
    plt.close(fig)
    print(f"    - Gráfico salvo em: {caminho_grafico}")

    return caminho_grafico, df

def gerar_grafico_turmas_instrutor_tipologia_projeto(atribuicoes: List[Dict]) -> str:
    """
    Gera gráfico de turmas por instrutor e projeto. (Lógica original mantida)
    """
    if not atribuicoes:
        return _gerar_grafico_vazio("Turmas por Instrutor/Projeto")

    contagem = defaultdict(lambda: defaultdict(int))
    for atr in atribuicoes:
        instrutor_id = atr['instrutor'].id
        projeto = atr['turma'].projeto.split('_Onda')[0]
        contagem[instrutor_id][projeto] += 1

    # Ordena os instrutores para uma visualização consistente
    df = pd.DataFrame(contagem).T.fillna(0).sort_index()
    fig, ax = plt.subplots(figsize=(14, max(8, len(df) * 0.4)))
    df.plot(kind='barh', stacked=True, ax=ax, colormap='tab20b')

    ax.set_xlabel('Número de Turmas', fontsize=12, fontweight='bold')
    ax.set_ylabel('Instrutor', fontsize=12, fontweight='bold')
    ax.set_title('Distribuição de Turmas por Instrutor e Projeto', fontsize=14, fontweight='bold')
    ax.legend(title='Projetos', bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.tight_layout()
    output_dir = Path("resultados_otimizacao")
    output_dir.mkdir(exist_ok=True)
    caminho = str(output_dir / "grafico_turmas_instrutor_projeto.png")
    plt.savefig(caminho, dpi=300, bbox_inches='tight')
    plt.close()
    return caminho


def gerar_grafico_carga_por_instrutor(atribuicoes: List[Dict]) -> str:
    """
    Gera gráfico de carga de trabalho por instrutor. (Lógica original mantida)
    """
    if not atribuicoes:
        return _gerar_grafico_vazio("Carga por Instrutor")

    carga = defaultdict(int)
    habilidades = {}
    for atr in atribuicoes:
        instrutor_id = atr['instrutor'].id
        carga[instrutor_id] += 1
        habilidades[instrutor_id] = atr['instrutor'].habilidade

    # Ordena os instrutores alfabeticamente para consistência
    instrutores_ordenados = sorted(carga.keys(), key=lambda x: (isinstance(x, str), x))
    cargas_ordenadas = [carga[inst] for inst in instrutores_ordenados]
    cores = ['#2E86AB' if habilidades[inst] == 'PROG' else '#A23B72' for inst in instrutores_ordenados]

    fig, ax = plt.subplots(figsize=(14, max(8, len(instrutores_ordenados) * 0.4)))
    barras = ax.barh(instrutores_ordenados, cargas_ordenadas, color=cores, edgecolor='black', linewidth=0.5)

    ax.set_xlabel('Número de Turmas', fontsize=12, fontweight='bold')
    ax.set_ylabel('Instrutor', fontsize=12, fontweight='bold')
    ax.set_title('Carga de Trabalho por Instrutor', fontsize=14, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)

    for barra, carga_val in zip(barras, cargas_ordenadas):
        largura = barra.get_width()
        ax.text(largura + 0.3, barra.get_y() + barra.get_height() / 2, str(int(carga_val)), va='center', fontsize=9, fontweight='bold')

    prog_patch = mpatches.Patch(color='#2E86AB', label='Programação')
    rob_patch = mpatches.Patch(color='#A23B72', label='Robótica')
    ax.legend(handles=[prog_patch, rob_patch])

    plt.tight_layout()
    output_dir = Path("resultados_otimizacao")
    output_dir.mkdir(exist_ok=True)
    caminho = str(output_dir / "grafico_carga_instrutor.png")
    plt.savefig(caminho, dpi=300, bbox_inches='tight')
    plt.close()
    return caminho

def plotar_conclusoes_por_mes(turmas: List[Turma],
                              projetos: List[Projeto],
                              meses: List[str],
                              meses_ferias_idx: List[int]) -> str:
    """
    CORRIGIDO: Gera gráfico de turmas concluídas por mês, respeitando a lógica de pular férias.
    """
    print("  Calculando gráfico de conclusões por mês (Lógica de Férias Sincronizada)...")
    conclusoes = defaultdict(lambda: defaultdict(int))
    num_meses_total = len(meses)

    for turma in turmas:
        projeto_base_nome = turma.projeto.split('_Onda')[0]

        # --- Lógica Corrigida ---
        # Usa a função central para obter os meses de atividade real
        meses_ativos_reais = calcular_meses_ativos(turma.mes_inicio, turma.duracao, meses_ferias_idx, num_meses_total)

        # O mês de conclusão é o último mês na lista de meses ativos
        if meses_ativos_reais:
            mes_fim = meses_ativos_reais[-1]
            conclusoes[mes_fim][projeto_base_nome] += 1

    todos_projetos = set()
    for meses_dict in conclusoes.values():
        todos_projetos.update(meses_dict.keys())
    projetos_unicos = sorted(todos_projetos)

    output_dir = Path("resultados_otimizacao")
    output_dir.mkdir(exist_ok=True)
    caminho_saida = str(output_dir / "grafico_conclusoes_por_mes.png")

    if not projetos_unicos:
        return _gerar_grafico_vazio("Turmas Concluídas por Mês", caminho_saida)

    dados_por_projeto = {}
    for projeto_nome in projetos_unicos:
        dados_por_projeto[projeto_nome] = [conclusoes[mes].get(projeto_nome, 0) for mes in range(num_meses_total)]

    fig, ax = plt.subplots(figsize=(16, 8))
    cores = plt.get_cmap('tab20')(np.linspace(0, 1, len(projetos_unicos)))
    x_pos = range(num_meses_total)
    bottom = np.zeros(num_meses_total)

    for idx, projeto_nome in enumerate(projetos_unicos):
        valores = np.array(dados_por_projeto[projeto_nome])
        ax.bar(x_pos, valores, bottom=bottom, label=projeto_nome, color=cores[idx], edgecolor='white', linewidth=0.5)
        bottom += valores

    ax.set_xlabel('Mês de Conclusão', fontsize=12, fontweight='bold')
    ax.set_ylabel('Quantidade de Turmas Concluídas', fontsize=12, fontweight='bold')
    ax.set_title('Cumprimento de Metas: Turmas Concluídas por Mês', fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(meses, rotation=45, ha='right')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.legend(title='Projetos', bbox_to_anchor=(1.05, 1), loc='upper left', frameon=True, shadow=True)

    for i, total in enumerate(bottom):
        if total > 0:
            ax.text(i, total, f'{int(total)}', ha='center', va='bottom', fontsize=9, fontweight='bold',
                    bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', boxstyle='round,pad=0.2'))

    plt.tight_layout()
    plt.savefig(caminho_saida, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"    - Gráfico salvo em: {caminho_saida}")
    return caminho_saida
