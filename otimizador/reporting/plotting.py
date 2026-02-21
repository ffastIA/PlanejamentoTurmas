"""
Módulo de geração de gráficos com alta legibilidade
Versão 4.7 - Legenda, eixo X e eixo Y adicionados ao gráfico
             "Turmas por Instrutor e Projeto"
"""

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from ..utils import calcular_meses_ativos, calcular_fluxo_caixa_detalhado
from ..data_models import Projeto, Turma, ParametrosFinanceiros

# Paleta de cores vibrantes
CORES_VIBRANTES = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
    '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88B', '#A8E6CF',
    '#FFD3B6', '#FFAAA5', '#FF8B94', '#A8D8EA', '#AA96DA', '#FCBAD3'
]

# --- CONFIGURAÇÃO GLOBAL DE ESTILO ---
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor']   = '#EAEAF2'
plt.rcParams['axes.grid']        = True
plt.rcParams['grid.color']       = 'white'
plt.rcParams['grid.linestyle']   = ':'
plt.rcParams['grid.linewidth']   = 1.0


def obter_cor(indice: int) -> str:
    return CORES_VIBRANTES[indice % len(CORES_VIBRANTES)]


def configurar_eixos(ax):
    """Aplica estilo de grade e fundo em cada gráfico."""
    ax.set_axisbelow(True)
    ax.grid(True, which='major', linestyle=':', color='white', alpha=1.0)


# =============================================================================
# FUNÇÕES AUXILIARES — LABELS NAS BARRAS (v4.6)
# =============================================================================

def _adicionar_labels_barras_empilhadas(ax, meses, dados_dict,
                                        bottom_acumulado):
    """
    Adiciona o label do TOTAL no topo de cada barra empilhada.
    """
    for idx_m in range(len(meses)):
        total = bottom_acumulado[idx_m]
        if total > 0:
            ax.text(
                idx_m, total + 0.3,
                str(int(total)),
                ha='center', va='bottom',
                fontsize=7, fontweight='bold',
                color='#333333'
            )


def _adicionar_labels_barras_simples(ax, barras, fmt='{:.0f}',
                                     offset_y=0.3, fontsize=8,
                                     color='#333333'):
    """
    Adiciona label no topo de cada barra de gráfico simples.
    """
    for barra in barras:
        altura = barra.get_height()
        if altura > 0:
            ax.text(
                barra.get_x() + barra.get_width() / 2,
                altura + offset_y,
                fmt.format(altura),
                ha='center', va='bottom',
                fontsize=fontsize, fontweight='bold',
                color=color
            )


def _adicionar_labels_barras_agrupadas(ax, barras, fmt='{:.0f}',
                                       offset_y=0.3, fontsize=7,
                                       color='#333333'):
    """
    Adiciona label no topo de cada barra em gráficos agrupados.
    """
    for barra in barras:
        altura = barra.get_height()
        if altura > 0:
            ax.text(
                barra.get_x() + barra.get_width() / 2,
                altura + offset_y,
                fmt.format(altura),
                ha='center', va='bottom',
                fontsize=fontsize, fontweight='bold',
                color=color
            )


# =============================================================================
# GRÁFICO: CRONOGRAMA POR PROJETO / CONSOLIDADO
# =============================================================================

def gerar_grafico_turmas_projeto_mes(
    turmas: List[Turma],
    projetos: List[Projeto],
    meses: List[str],
    meses_ferias_idx: List[int],
    projeto_filtro: str = None
) -> str:
    num_meses = len(meses)

    if projeto_filtro:
        dados = {projeto_filtro: np.zeros(num_meses)}
        turmas_filtradas = [
            t for t in turmas
            if t.projeto.split('_Onda')[0] == projeto_filtro
        ]
    else:
        projetos_base = sorted(list(set(
            t.projeto.split('_Onda')[0] for t in turmas
        )))
        dados = {proj: np.zeros(num_meses) for proj in projetos_base}
        turmas_filtradas = turmas

    for t in turmas_filtradas:
        nome_proj = t.projeto.split('_Onda')[0]
        if nome_proj in dados:
            meses_at = calcular_meses_ativos(
                t.mes_inicio, t.duracao, meses_ferias_idx, num_meses
            )
            for m in meses_at:
                dados[nome_proj][m] += 1

    fig, ax = plt.subplots(figsize=(16, 8))
    configurar_eixos(ax)
    bottom = np.zeros(num_meses)

    for idx, (nome, vals) in enumerate(sorted(dados.items())):
        if np.sum(vals) > 0:
            ax.bar(
                meses, vals, bottom=bottom,
                label=nome, color=obter_cor(idx),
                alpha=0.9, edgecolor='white', linewidth=0.5
            )
            bottom += vals

    _adicionar_labels_barras_empilhadas(ax, meses, dados, bottom)

    ax.set_title(
        f'Cronograma: {projeto_filtro or "Consolidado"}',
        fontsize=16, fontweight='bold', pad=20
    )
    ax.set_xlabel('Mês', fontweight='bold')
    ax.set_ylabel('Turmas Ativas', fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    if not projeto_filtro:
        ax.legend(
            title='Projeto',
            title_fontsize=9,
            fontsize=8,
            loc='upper left',
            frameon=True,
            facecolor='white'
        )

    path = (
        f"resultados_otimizacao/grafico_cronograma_"
        f"{projeto_filtro or 'CONSOLIDADO'}.png"
    )
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    return path


# =============================================================================
# GRÁFICO: TURMAS POR INSTRUTOR E PROJETO  (seção 4 do relatório)
# CORREÇÃO v4.7: legenda com título, eixo X e eixo Y adicionados
# =============================================================================

def gerar_grafico_turmas_instrutor_tipologia_projeto(
    atribuicoes: List[Dict]
) -> str:
    dados = {}
    for atr in atribuicoes:
        i = atr['instrutor'].id
        p = atr['turma'].projeto.split('_Onda')[0]
        if i not in dados:
            dados[i] = {}
        dados[i][p] = dados[i].get(p, 0) + 1

    insts = sorted(dados.keys())
    projs = sorted(list(set(
        p for d in dados.values() for p in d
    )))

    fig, ax = plt.subplots(figsize=(16, 9))
    configurar_eixos(ax)
    bottom = np.zeros(len(insts))

    for idx, p in enumerate(projs):
        vals = [dados[i].get(p, 0) for i in insts]
        ax.bar(
            insts, vals, bottom=bottom,
            label=p, color=obter_cor(idx),
            alpha=0.9, edgecolor='white'
        )
        bottom += np.array(vals)

    _adicionar_labels_barras_empilhadas(ax, insts, dados, bottom)

    ax.set_title(
        'Turmas por Instrutor e Projeto',
        fontsize=16, fontweight='bold'
    )
    ax.set_xlabel('Instrutor', fontweight='bold')       # ← NOVO v4.7
    ax.set_ylabel('Total de Turmas', fontweight='bold') # ← NOVO v4.7
    ax.legend(
        title='Projeto',           # ← NOVO v4.7
        title_fontsize=9,
        fontsize=8,
        facecolor='white',
        loc='upper right',
        frameon=True
    )
    plt.xticks(rotation=90)
    plt.tight_layout()

    path = "resultados_otimizacao/grafico_instrutor_projeto.png"
    plt.savefig(path, dpi=300)
    plt.close()
    return path


# =============================================================================
# GRÁFICO: DISTRIBUIÇÃO DE CARGA POR INSTRUTOR
# =============================================================================

def gerar_grafico_carga_por_instrutor(atribuicoes: List[Dict]) -> str:
    cargas = {}
    for atr in atribuicoes:
        cargas[atr['instrutor'].id] = (
            cargas.get(atr['instrutor'].id, 0) + 1
        )

    vals = list(cargas.values())
    fig, ax = plt.subplots(figsize=(12, 7))
    configurar_eixos(ax)

    n, bins, patches = ax.hist(
        vals,
        bins=range(min(vals), max(vals) + 2),
        align='left', rwidth=0.8, edgecolor='white'
    )
    for idx, patch in enumerate(patches):
        patch.set_facecolor(obter_cor(idx))

    for count, patch in zip(n, patches):
        if count > 0:
            ax.text(
                patch.get_x() + patch.get_width() / 2,
                count + 0.1,
                str(int(count)),
                ha='center', va='bottom',
                fontsize=8, fontweight='bold',
                color='#333333'
            )

    ax.set_title(
        'Distribuição de Carga',
        fontsize=16, fontweight='bold'
    )
    ax.set_xlabel('Total de Turmas', fontweight='bold')
    ax.set_ylabel('Quantidade de Instrutores', fontweight='bold')

    path = "resultados_otimizacao/grafico_carga_instrutores.png"
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    return path


# =============================================================================
# GRÁFICO 3.3: DEMANDA MENSAL DE TURMAS POR HABILIDADE
# CORREÇÃO v4.6: título reflete TURMAS (não instrutores)
# =============================================================================

def gerar_grafico_demanda_prog_rob(
    turmas: List[Turma],
    projetos: List[Projeto],
    meses: List[str],
    meses_ferias_idx: List[int]
) -> Tuple[str, pd.DataFrame]:

    num_meses = len(meses)
    prog = np.zeros(num_meses)
    rob  = np.zeros(num_meses)

    for t in turmas:
        meses_at = calcular_meses_ativos(
            t.mes_inicio, t.duracao, meses_ferias_idx, num_meses
        )
        for m in meses_at:
            if t.habilidade == 'PROG':
                prog[m] += 1
            else:
                rob[m] += 1

    fig, ax = plt.subplots(figsize=(14, 8))
    configurar_eixos(ax)

    ax.plot(
        meses, prog,
        label='PROGRAMAÇÃO',
        marker='o', linewidth=3,
        color='#FF6B6B'
    )
    ax.plot(
        meses, rob,
        label='ROBÓTICA',
        marker='s', linewidth=3,
        color='#4ECDC4'
    )
    ax.fill_between(
        range(num_meses), prog, alpha=0.15, color='#FF6B6B'
    )
    ax.fill_between(
        range(num_meses), rob, alpha=0.15, color='#4ECDC4'
    )

    for idx_m, valor in enumerate(prog):
        if valor > 0:
            ax.annotate(
                str(int(valor)),
                xy=(idx_m, valor),
                xytext=(0, 7),
                textcoords='offset points',
                ha='center', va='bottom',
                fontsize=7, fontweight='bold',
                color='#FF6B6B'
            )

    for idx_m, valor in enumerate(rob):
        if valor > 0:
            ax.annotate(
                str(int(valor)),
                xy=(idx_m, valor),
                xytext=(0, -14),
                textcoords='offset points',
                ha='center', va='top',
                fontsize=7, fontweight='bold',
                color='#4ECDC4'
            )

    ax.set_title(
        'Demanda Mensal de Turmas por Habilidade (PROG vs ROB)',
        fontsize=16, fontweight='bold'
    )
    ax.set_xlabel('Mês', fontweight='bold')
    ax.set_ylabel('Turmas Ativas', fontweight='bold')
    ax.legend(
        title='Habilidade',
        title_fontsize=9,
        fontsize=8,
        facecolor='white',
        frameon=True
    )
    plt.xticks(rotation=45, ha='right')

    path = "resultados_otimizacao/grafico_demanda_habilidade.png"
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()

    return path, pd.DataFrame({
        'Mes':          meses,
        'Demanda_PROG': prog,
        'Demanda_ROB':  rob,
        'Total':        prog + rob
    })


# =============================================================================
# GRÁFICO: CONCLUSÕES DE TURMAS POR MÊS
# =============================================================================

def plotar_conclusoes_por_mes(
    turmas: List[Turma],
    projetos: List[Projeto],
    meses: List[str],
    meses_ferias_idx: List[int]
) -> str:
    num_meses  = len(meses)
    conclusoes = np.zeros(num_meses)

    for t in turmas:
        meses_at = calcular_meses_ativos(
            t.mes_inicio, t.duracao, meses_ferias_idx, num_meses
        )
        if meses_at:
            conclusoes[meses_at[-1]] += 1

    fig, ax = plt.subplots(figsize=(14, 7))
    configurar_eixos(ax)

    barras = ax.bar(
        meses, conclusoes,
        color='#45B7D1', alpha=0.9, edgecolor='white'
    )

    _adicionar_labels_barras_simples(ax, barras)

    ax.set_title(
        'Conclusões de Turmas por Mês',
        fontsize=16, fontweight='bold'
    )
    ax.set_xlabel('Mês', fontweight='bold')
    ax.set_ylabel('Turmas Concluídas', fontweight='bold')
    plt.xticks(rotation=45, ha='right')

    path = "resultados_otimizacao/grafico_conclusoes.png"
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    return path


# =============================================================================
# GRÁFICO: EVOLUÇÃO DO QUADRO DE INSTRUTORES
# =============================================================================

def gerar_grafico_evolucao_instrutores(
    atribuicoes: List[Dict],
    meses: List[str],
    meses_ferias_idx: List[int]
) -> Tuple[str, pd.DataFrame]:
    from ..utils import calcular_evolucao_instrutores
    df = calcular_evolucao_instrutores(
        atribuicoes, meses, meses_ferias_idx
    )
    if df.empty:
        return None, df

    fig, ax = plt.subplots(figsize=(14, 8))
    configurar_eixos(ax)

    x     = np.arange(len(df))
    width = 0.35

    barras_prog = ax.bar(
        x - width / 2,
        df['Instrutores_PROG'],
        width,
        label='Programação',
        color='#FF6B6B',
        edgecolor='white'
    )
    barras_rob = ax.bar(
        x + width / 2,
        df['Instrutores_ROB'],
        width,
        label='Robótica',
        color='#4ECDC4',
        edgecolor='white'
    )

    _adicionar_labels_barras_agrupadas(ax, barras_prog)
    _adicionar_labels_barras_agrupadas(ax, barras_rob)

    ax.set_title(
        'Evolução do Quadro de Instrutores',
        fontsize=16, fontweight='bold'
    )
    ax.set_xlabel('Mês', fontweight='bold')
    ax.set_ylabel('Instrutores Ativos', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(df['Mes'], rotation=45, ha='right')
    ax.legend(
        title='Habilidade',
        title_fontsize=9,
        fontsize=8,
        facecolor='white',
        frameon=True
    )

    path = "resultados_otimizacao/grafico_evolucao_instrutores.png"
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    return path, df


# =============================================================================
# GRÁFICO: FLUXO DE CAIXA
# =============================================================================

def gerar_grafico_fluxo_caixa(
    atribuicoes: List[Dict],
    meses: List[str],
    meses_ferias_idx: List[int],
    parametros_financeiros: ParametrosFinanceiros,
    projeto_filtro: str = None
) -> str:
    df = calcular_fluxo_caixa_detalhado(
        atribuicoes, meses, meses_ferias_idx,
        parametros_financeiros, projeto_filtro
    )
    if df.empty:
        return None

    fig, ax1 = plt.subplots(figsize=(14, 8))
    configurar_eixos(ax1)

    barras = ax1.bar(
        df['Mês'], df['Custo Mensal'],
        color='#FF6B6B', alpha=0.6,
        label='Custo Mensal', edgecolor='white'
    )
    ax1.set_xlabel('Mês', fontweight='bold')
    ax1.set_ylabel(
        'Custo Mensal (R$)', color='#FF6B6B', fontweight='bold'
    )

    for barra in barras:
        altura = barra.get_height()
        if altura > 0:
            ax1.text(
                barra.get_x() + barra.get_width() / 2,
                altura * 1.01,
                f'R${altura:,.0f}',
                ha='center', va='bottom',
                fontsize=6, fontweight='bold',
                color='#FF6B6B', rotation=45
            )

    ax2 = ax1.twinx()
    ax2.plot(
        df['Mês'], df['Custo Acumulado'],
        color='#4ECDC4', marker='o',
        linewidth=3, label='Acumulado'
    )
    ax2.set_ylabel(
        'Custo Acumulado (R$)', color='#4ECDC4', fontweight='bold'
    )

    for idx_m, valor in enumerate(df['Custo Acumulado']):
        if valor > 0:
            ax2.annotate(
                f'R${valor:,.0f}',
                xy=(idx_m, valor),
                xytext=(0, 8),
                textcoords='offset points',
                ha='center', va='bottom',
                fontsize=6, fontweight='bold',
                color='#4ECDC4', rotation=45
            )

    plt.title(
        f'Fluxo de Caixa: {projeto_filtro or "Consolidado"}',
        fontsize=16, fontweight='bold'
    )
    ax1.tick_params(axis='x', rotation=45)

    path = (
        f"resultados_otimizacao/grafico_fluxo_caixa_"
        f"{projeto_filtro or 'CONSOLIDADO'}.png"
    )
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    return path