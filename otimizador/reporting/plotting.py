# ARQUIVO: otimizador/reporting/plotting.py
"""
Módulo responsável pela geração de gráficos e visualizações.
Versão 3.3 - Correção Final de Sintaxe
"""

import os
from collections import defaultdict
from typing import List, Dict, Tuple
import calendar

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

# Import relativo
from ..data_models import Turma, Projeto


def gerar_grafico_turmas_projeto_mes(turmas: List[Turma], projetos: List[Projeto], meses: List[str],
                                     meses_ferias: List[int]) -> str:
    """
    Gera gráfico de turmas por projeto ao longo dos meses.
    """
    dados = []
    for turma in turmas:
        duracao = turma.duracao
        projeto_base_nome = turma.projeto.split('_Onda')[0]

        for mes_idx in range(turma.mes_inicio, turma.mes_inicio + duracao):
            if mes_idx < len(meses):
                dados.append({
                    'Projeto': projeto_base_nome,
                    'Mes': meses[mes_idx],
                })

    if not dados:
        return _gerar_grafico_vazio("Turmas por Projeto/Mês")

    df = pd.DataFrame(dados)
    df['Mes'] = pd.Categorical(df['Mes'], categories=meses, ordered=True)
    pivot = df.groupby(['Projeto', 'Mes'], observed=False).size().unstack(fill_value=0)

    fig, ax = plt.subplots(figsize=(16, 8))
    pivot.T.plot(kind='bar', stacked=True, ax=ax, colormap='tab20')

    ax.set_xlabel('Mês', fontsize=12, fontweight='bold')
    ax.set_ylabel('Número de Turmas Ativas', fontsize=12, fontweight='bold')
    ax.set_title('Turmas Ativas por Projeto ao Longo do Tempo', fontsize=14, fontweight='bold')
    ax.legend(title='Projetos', bbox_to_anchor=(1.05, 1), loc='upper left')

    for mes_ferias_idx in meses_ferias:
        if mes_ferias_idx < len(meses):
            ax.axvline(x=meses.index(meses[mes_ferias_idx]), color='red', linestyle='--', alpha=0.5, linewidth=1.5)

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    caminho = "grafico_turmas_projeto_mes.png"
    plt.savefig(caminho, dpi=300, bbox_inches='tight')
    plt.close()
    return caminho


def gerar_grafico_turmas_instrutor_tipologia_projeto(atribuicoes: List[Dict]) -> str:
    """
    Gera gráfico de turmas por instrutor e projeto. (Função já estava correta)
    """
    if not atribuicoes:
        return _gerar_grafico_vazio("Turmas por Instrutor/Projeto")

    contagem = defaultdict(lambda: defaultdict(int))
    for atr in atribuicoes:
        instrutor_id = atr['instrutor'].id
        projeto = atr['turma'].projeto.split('_Onda')[0]
        contagem[instrutor_id][projeto] += 1

    df = pd.DataFrame(contagem).T.fillna(0)
    fig, ax = plt.subplots(figsize=(14, max(8, len(df) * 0.3)))
    df.plot(kind='barh', stacked=True, ax=ax, colormap='Set3')

    ax.set_xlabel('Número de Turmas', fontsize=12, fontweight='bold')
    ax.set_ylabel('Instrutor', fontsize=12, fontweight='bold')
    ax.set_title('Distribuição de Turmas por Instrutor e Projeto', fontsize=14, fontweight='bold')
    ax.legend(title='Projetos', bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.tight_layout()
    caminho = "grafico_turmas_instrutor_projeto.png"
    plt.savefig(caminho, dpi=300, bbox_inches='tight')
    plt.close()
    return caminho


def gerar_grafico_demanda_prog_rob(turmas: List[Turma], projetos: List[Projeto], meses: List[str],
                                   meses_ferias: List[int]) -> Tuple[str, pd.DataFrame]:
    """
    Gera gráfico de demanda por habilidade (PROG vs ROBOTICA).
    """
    demanda_prog = [0] * len(meses)
    demanda_rob = [0] * len(meses)

    for turma in turmas:
        duracao = turma.duracao

        for mes_idx in range(turma.mes_inicio, turma.mes_inicio + duracao):
            if mes_idx < len(meses):
                if turma.habilidade == 'PROG':
                    demanda_prog[mes_idx] += 1
                else:
                    demanda_rob[mes_idx] += 1

    df_serie = pd.DataFrame({'Mes': meses, 'Programacao': demanda_prog, 'Robotica': demanda_rob,
                             'Total': [p + r for p, r in zip(demanda_prog, demanda_rob)]})

    fig, ax = plt.subplots(figsize=(16, 8))
    x = np.arange(len(meses))
    largura = 0.35
    ax.bar(x - largura / 2, demanda_prog, largura, label='Programação', color='#2E86AB')
    ax.bar(x + largura / 2, demanda_rob, largura, label='Robótica', color='#A23B72')

    ax.set_xlabel('Mês', fontsize=12, fontweight='bold')
    ax.set_ylabel('Número de Turmas Ativas', fontsize=12, fontweight='bold')
    ax.set_title('Demanda Mensal por Habilidade', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(meses, rotation=45, ha='right')
    ax.grid(axis='y', alpha=0.3)

    for mes_ferias_idx in meses_ferias:
        if mes_ferias_idx < len(meses):
            ax.axvline(x=mes_ferias_idx, color='red', linestyle='--', alpha=0.5, linewidth=2)

    ferias_patch = mpatches.Patch(color='red', alpha=0.5, linestyle='--', label='Férias')
    handles, labels = ax.get_legend_handles_labels()
    handles.append(ferias_patch)
    ax.legend(handles=handles)

    plt.tight_layout()
    caminho = "grafico_demanda_prog_rob.png"
    plt.savefig(caminho, dpi=300, bbox_inches='tight')
    plt.close()
    return caminho, df_serie


def gerar_grafico_carga_por_instrutor(atribuicoes: List[Dict]) -> str:
    """
    Gera gráfico de carga de trabalho por instrutor. (Função já estava correta)
    """
    if not atribuicoes:
        return _gerar_grafico_vazio("Carga por Instrutor")

    carga = defaultdict(int)
    habilidades = {}
    for atr in atribuicoes:
        instrutor_id = atr['instrutor'].id
        carga[instrutor_id] += 1
        habilidades[instrutor_id] = atr['instrutor'].habilidade

    instrutores_ordenados = sorted(carga.keys(), key=lambda x: carga[x], reverse=True)
    cargas_ordenadas = [carga[inst] for inst in instrutores_ordenados]
    cores = ['#2E86AB' if habilidades[inst] == 'PROG' else '#A23B72' for inst in instrutores_ordenados]

    fig, ax = plt.subplots(figsize=(14, max(8, len(instrutores_ordenados) * 0.3)))
    barras = ax.barh(instrutores_ordenados, cargas_ordenadas, color=cores, edgecolor='black', linewidth=0.5)

    ax.set_xlabel('Número de Turmas', fontsize=12, fontweight='bold')
    ax.set_ylabel('Instrutor', fontsize=12, fontweight='bold')
    ax.set_title('Carga de Trabalho por Instrutor', fontsize=14, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)

    for barra, carga_val in zip(barras, cargas_ordenadas):
        largura = barra.get_width()
        ax.text(largura + 0.3, barra.get_y() + barra.get_height() / 2, str(int(carga_val)), va='center', fontsize=9,
                fontweight='bold')

    prog_patch = mpatches.Patch(color='#2E86AB', label='Programação')
    rob_patch = mpatches.Patch(color='#A23B72', label='Robótica')
    ax.legend(handles=[prog_patch, rob_patch])

    plt.tight_layout()
    caminho = "grafico_carga_instrutor.png"
    plt.savefig(caminho, dpi=300, bbox_inches='tight')
    plt.close()
    return caminho


def plotar_conclusoes_por_mes(turmas: List[Turma], projetos: List[Projeto], data_inicio, meses_total: int,
                              caminho_saida: str) -> str:
    """
    Gera gráfico de barras empilhadas mostrando quantas turmas finalizam por mês, por projeto.
    """
    from datetime import timedelta

    conclusoes = defaultdict(lambda: defaultdict(int))

    for turma in turmas:
        duracao = turma.duracao
        projeto_base_nome = turma.projeto.split('_Onda')[0]

        mes_fim = turma.mes_inicio + duracao - 1

        if 0 <= mes_fim < meses_total:
            conclusoes[mes_fim][projeto_base_nome] += 1

    meses_labels = []
    for i in range(meses_total):
        ano = data_inicio.year + (data_inicio.month + i - 1) // 12
        mes = (data_inicio.month + i - 1) % 12 + 1
        mes_nome = calendar.month_abbr[mes]
        meses_labels.append(f"{mes_nome}/{ano}")

    todos_projetos = set()
    for meses_dict in conclusoes.values():
        todos_projetos.update(meses_dict.keys())
    projetos_unicos = sorted(todos_projetos)

    if not projetos_unicos:
        return _gerar_grafico_vazio("Turmas Concluídas por Mês", caminho_saida)

    dados_por_projeto = {}
    for projeto_nome in projetos_unicos:
        dados_por_projeto[projeto_nome] = [conclusoes[mes].get(projeto_nome, 0) for mes in range(meses_total)]

    fig, ax = plt.subplots(figsize=(16, 8))
    cores = plt.get_cmap('tab20')(np.linspace(0, 1, len(projetos_unicos)))
    x_pos = range(meses_total)
    bottom = np.zeros(meses_total)

    for idx, projeto_nome in enumerate(projetos_unicos):
        valores = np.array(dados_por_projeto[projeto_nome])
        ax.bar(x_pos, valores, bottom=bottom, label=projeto_nome, color=cores[idx], edgecolor='white', linewidth=0.5)
        bottom += valores

    ax.set_xlabel('Mês de Conclusão', fontsize=12, fontweight='bold')
    ax.set_ylabel('Quantidade de Turmas Concluídas', fontsize=12, fontweight='bold')
    ax.set_title('Cumprimento de Metas: Turmas Concluídas por Mês', fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(meses_labels, rotation=45, ha='right')
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
    return caminho_saida


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

    if not caminho:
        caminho = f"grafico_vazio_{titulo.replace(' ', '_').lower()}.png"

    plt.savefig(caminho, dpi=150, bbox_inches='tight')
    plt.close()
    return caminho