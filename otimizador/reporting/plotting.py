"""
Módulo de Geração de Gráficos
Versão 5.4 - Inclusão de Gráfico Linear de Pagamentos Mensais
"""

import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
import os
from typing import List, Dict, Tuple, Optional

COR_PROG = '#FF6B6B';
COR_ROB = '#4ECDC4';
COR_TOTAL = '#556270';
COR_FIN = '#2E7D32'


def _salvar_grafico(fig: plt.Figure, nome_base: str) -> str:
    os.makedirs("resultados_otimizacao", exist_ok=True)
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    path = f"resultados_otimizacao/{nome_base}_{timestamp}.png"
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return path


def gerar_grafico_turmas_projeto_mes(turmas, projetos_modelo, meses, ferias_idx, projeto_filtro=None):
    from ..utils import calcular_meses_ativos
    df_data = []
    for m_idx, mes in enumerate(meses):
        prog = sum(1 for t in turmas if
                   (not projeto_filtro or t.projeto == projeto_filtro) and m_idx in calcular_meses_ativos(t.mes_inicio,
                                                                                                          t.duracao,
                                                                                                          ferias_idx,
                                                                                                          len(meses)) and t.habilidade == 'PROG')
        rob = sum(1 for t in turmas if
                  (not projeto_filtro or t.projeto == projeto_filtro) and m_idx in calcular_meses_ativos(t.mes_inicio,
                                                                                                         t.duracao,
                                                                                                         ferias_idx,
                                                                                                         len(meses)) and t.habilidade == 'ROB')
        df_data.append({'Mes': mes, 'PROG': prog, 'ROB': rob})
    df = pd.DataFrame(df_data)
    fig, ax = plt.subplots(figsize=(14, 6))
    x = range(len(df));
    width = 0.35
    ax.bar([i - width / 2 for i in x], df['PROG'], width, label='PROG', color=COR_PROG)
    ax.bar([i + width / 2 for i in x], df['ROB'], width, label='ROB', color=COR_ROB)
    ax.set_xticks(x);
    ax.set_xticklabels(df['Mes'], rotation=45, ha='right');
    ax.legend()
    ax.set_title(f'Turmas Ativas por Mês - {"Consolidado" if not projeto_filtro else projeto_filtro}')
    plt.tight_layout()
    return _salvar_grafico(fig, f"grafico_turmas_ativas_{projeto_filtro or 'consolidado'}")


def gerar_grafico_evolucao_instrutores(atribuicoes, meses, ferias_idx):
    from ..utils import calcular_evolucao_instrutores
    df_evolucao = calcular_evolucao_instrutores(atribuicoes, meses, ferias_idx)
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df_evolucao['Mes'], df_evolucao['Instrutores_PROG'], label='PROG', color=COR_PROG, marker='o')
    ax.plot(df_evolucao['Mes'], df_evolucao['Instrutores_ROB'], label='ROB', color=COR_ROB, marker='o')
    ax.plot(df_evolucao['Mes'], df_evolucao['Total'], label='Total', color=COR_TOTAL, linestyle='--', marker='x')
    ax.set_xticks(range(len(df_evolucao['Mes'])));
    ax.set_xticklabels(df_evolucao['Mes'], rotation=45, ha='right');
    ax.legend()
    ax.set_title('Evolução Mensal do Headcount de Instrutores')
    plt.tight_layout()
    return _salvar_grafico(fig, "grafico_evolucao_instrutores"), df_evolucao


def gerar_grafico_turmas_abertas_mes(turmas, meses, ferias_idx):
    from ..utils import calcular_turmas_abertas_por_mes
    df = calcular_turmas_abertas_por_mes(turmas, meses, ferias_idx)
    fig, ax = plt.subplots(figsize=(14, 6))
    x = range(len(df));
    width = 0.35
    ax.bar([i - width / 2 for i in x], df['Abertas_PROG'], width, label='PROG', color=COR_PROG)
    ax.bar([i + width / 2 for i in x], df['Abertas_ROB'], width, label='ROB', color=COR_ROB)
    ax.set_xticks(x);
    ax.set_xticklabels(df['Mes'], rotation=45, ha='right');
    ax.legend()
    ax.set_title('Novas Turmas Abertas por Mês')
    plt.tight_layout()
    return _salvar_grafico(fig, "grafico_turmas_abertas")


def gerar_grafico_pagamentos_mensais(df_financeiro: pd.DataFrame) -> str:
    """Gera gráfico linear da evolução dos custos mensais totais."""
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df_financeiro['Mês'], df_financeiro['Custo Mensal'], color=COR_FIN, marker='s', linewidth=2,
            label='Custo Mensal')

    # Adiciona labels de valor acima dos pontos
    for i, row in df_financeiro.iterrows():
        if row['Custo Mensal'] > 0:
            ax.text(i, row['Custo Mensal'], f"R$ {row['Custo Mensal']:,.0f}", ha='center', va='bottom', fontsize=8,
                    fontweight='bold', color=COR_FIN)

    ax.set_xticks(range(len(df_financeiro)));
    ax.set_xticklabels(df_financeiro['Mês'], rotation=45, ha='right')
    ax.set_title('Evolução dos Pagamentos Mensais (Operacional)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Valor (R$)', fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    return _salvar_grafico(fig, "grafico_pagamentos_mensais")