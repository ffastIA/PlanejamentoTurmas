import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from ..utils import calcular_meses_ativos
from ..data_models import Projeto, Turma, ParametrosFinanceiros

# Configuração de estilo para gráficos mais profissionais
plt.style.use('ggplot')


def gerar_grafico_turmas_projeto_mes(turmas: List[Turma], projetos: List[Projeto],
                                     meses: List[str], meses_ferias_idx: List[int]) -> str:
    """Gera gráfico de barras empilhadas: Turmas por Projeto por Mês."""
    num_meses = len(meses)
    dados_projeto = {p.nome: np.zeros(num_meses) for p in projetos}

    for t in turmas:
        # Usa a função utilitária para considerar o "pulo" das férias
        meses_ativos = calcular_meses_ativos(t.mes_inicio, t.duracao, meses_ferias_idx, num_meses)
        for m in meses_ativos:
            # Remove sufixos de onda para agrupar no gráfico (ex: DD2_Onda1 -> DD2)
            nome_proj_base = t.projeto.split('_Onda')[0]
            if nome_proj_base in dados_projeto:
                dados_projeto[nome_proj_base][m] += 1

    fig, ax = plt.subplots(figsize=(14, 7))
    bottom = np.zeros(num_meses)

    # Cores distintas para projetos
    cores = plt.cm.tab20(np.linspace(0, 1, len(projetos)))

    for (nome_proj, valores), cor in zip(dados_projeto.items(), cores):
        ax.bar(meses, valores, bottom=bottom, label=nome_proj, color=cor, alpha=0.8)
        bottom += valores

    ax.set_title('Evolução da Quantidade de Turmas Ativas por Projeto', fontsize=14)
    ax.set_ylabel('Quantidade de Turmas')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    caminho = "resultados_otimizacao/grafico_turmas_projeto.png"
    plt.savefig(caminho, dpi=300, bbox_inches='tight')
    plt.close()
    return caminho


def gerar_grafico_turmas_instrutor_tipologia_projeto(atribuicoes: List[Dict]) -> str:
    """Gera gráfico de barras: Turmas por Instrutor (dividido por projeto)."""
    # Organizar dados
    dados = {}  # {instrutor_id: {proj1: count, proj2: count}}
    todos_projetos = set()

    for atr in atribuicoes:
        inst_id = atr['instrutor'].id
        proj_nome = atr['turma'].projeto.split('_Onda')[0]
        todos_projetos.add(proj_nome)

        if inst_id not in dados: dados[inst_id] = {}
        dados[inst_id][proj_nome] = dados[inst_id].get(proj_nome, 0) + 1

    # Ordenar instrutores por ID numérico
    instrutores_ordenados = sorted(dados.keys(), key=lambda x: (x.split('_')[0], int(x.split('_')[1])))
    projetos_ordenados = sorted(list(todos_projetos))

    fig, ax = plt.subplots(figsize=(15, 8))
    bottom = np.zeros(len(instrutores_ordenados))

    for proj in projetos_ordenados:
        valores = [dados[i].get(proj, 0) for i in instrutores_ordenados]
        ax.bar(instrutores_ordenados, valores, bottom=bottom, label=proj)
        bottom += np.array(valores)

    ax.set_title('Distribuição de Turmas por Instrutor e Projeto', fontsize=14)
    ax.set_ylabel('Total de Turmas Atribuídas')
    plt.xticks(rotation=90)
    ax.legend()
    plt.tight_layout()

    caminho = "resultados_otimizacao/grafico_instrutor_projeto.png"
    plt.savefig(caminho, dpi=300, bbox_inches='tight')
    plt.close()
    return caminho


def gerar_grafico_carga_por_instrutor(atribuicoes: List[Dict]) -> str:
    """Gera histograma da carga de trabalho dos instrutores."""
    cargas = {}
    for atr in atribuicoes:
        inst_id = atr['instrutor'].id
        cargas[inst_id] = cargas.get(inst_id, 0) + 1

    valores_carga = list(cargas.values())

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(valores_carga, bins=range(min(valores_carga), max(valores_carga) + 2),
            align='left', rwidth=0.8, color='skyblue', edgecolor='black')

    ax.set_title('Histograma de Carga de Trabalho (Turmas por Instrutor)', fontsize=14)
    ax.set_xlabel('Número de Turmas')
    ax.set_ylabel('Quantidade de Instrutores')
    ax.set_xticks(range(min(valores_carga), max(valores_carga) + 1))
    plt.grid(axis='y', alpha=0.5)
    plt.tight_layout()

    caminho = "resultados_otimizacao/grafico_carga_instrutores.png"
    plt.savefig(caminho, dpi=300)
    plt.close()
    return caminho


def gerar_grafico_demanda_prog_rob(turmas: List[Turma], projetos: List[Projeto],
                                   meses: List[str], meses_ferias_idx: List[int]) -> Tuple[str, pd.DataFrame]:
    """Gera gráfico de linha comparando demanda PROG vs ROB ao longo do tempo."""
    num_meses = len(meses)
    demanda_prog = np.zeros(num_meses)
    demanda_rob = np.zeros(num_meses)

    for t in turmas:
        meses_ativos = calcular_meses_ativos(t.mes_inicio, t.duracao, meses_ferias_idx, num_meses)
        for m in meses_ativos:
            if t.habilidade == 'PROG':
                demanda_prog[m] += 1
            else:
                demanda_rob[m] += 1

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(meses, demanda_prog, label='Programação', marker='o', linewidth=2, color='blue')
    ax.plot(meses, demanda_rob, label='Robótica', marker='s', linewidth=2, color='orange')

    # Marcar meses de férias
    for ferias_idx in meses_ferias_idx:
        if ferias_idx < num_meses:
            ax.axvspan(ferias_idx - 0.5, ferias_idx + 0.5, color='gray', alpha=0.2,
                       label='Férias' if ferias_idx == meses_ferias_idx[0] else "")

    ax.set_title('Evolução da Demanda por Habilidade (Turmas Simultâneas)', fontsize=14)
    ax.set_ylabel('Quantidade de Turmas')
    ax.legend()
    plt.xticks(rotation=45, ha='right')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    caminho = "resultados_otimizacao/grafico_demanda_habilidade.png"
    plt.savefig(caminho, dpi=300)
    plt.close()

    # Retorna também os dados para uso no relatório PDF
    df_dados = pd.DataFrame({
        'Mes': meses,
        'Demanda_PROG': demanda_prog,
        'Demanda_ROB': demanda_rob,
        'Total': demanda_prog + demanda_rob
    })

    return caminho, df_dados


def plotar_conclusoes_por_mes(turmas: List[Turma], projetos: List[Projeto],
                              meses: List[str], meses_ferias_idx: List[int]) -> str:
    """Gera gráfico de barras mostrando quantas turmas concluem em cada mês."""
    num_meses = len(meses)
    conclusoes = np.zeros(num_meses)

    for t in turmas:
        # Calcula o mês real de término considerando os "pulos" das férias
        meses_ativos = calcular_meses_ativos(t.mes_inicio, t.duracao, meses_ferias_idx, num_meses)
        if meses_ativos:
            ultimo_mes_ativo = meses_ativos[-1]
            # A conclusão ocorre no mês SEGUINTE ao último mês de aula, ou no próprio mês se for o fim do contrato
            # Aqui vamos considerar o último mês de aula como o mês de "formatura"
            conclusoes[ultimo_mes_ativo] += 1

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(meses, conclusoes, color='green', alpha=0.6)

    ax.set_title('Previsão de Conclusão de Turmas por Mês', fontsize=14)
    ax.set_ylabel('Turmas Concluídas')
    plt.xticks(rotation=45, ha='right')

    # Adicionar valores no topo das barras
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width() / 2., height,
                    f'{int(height)}',
                    ha='center', va='bottom')

    plt.tight_layout()
    caminho = "resultados_otimizacao/grafico_conclusoes.png"
    plt.savefig(caminho, dpi=300)
    plt.close()
    return caminho


def gerar_grafico_fluxo_caixa(atribuicoes: List[Dict], meses: List[str],
                              meses_ferias_idx: List[int], parametros_financeiros: ParametrosFinanceiros) -> str:
    """
    Gera gráfico financeiro combinado:
    - Barras: Custo Mensal
    - Linha: Custo Acumulado
    """
    custo_mensal_unitario = parametros_financeiros.custo_mensal_instrutor
    num_meses = len(meses)

    # Calcular instrutores ativos por mês
    instrutores_ativos_por_mes = {m: set() for m in range(num_meses)}
    for atr in atribuicoes:
        t = atr['turma']
        i = atr['instrutor']
        meses_ativos = calcular_meses_ativos(t.mes_inicio, t.duracao, meses_ferias_idx, num_meses)
        for m in meses_ativos:
            instrutores_ativos_por_mes[m].add(i.id)

    custos_mensais = []
    custos_acumulados = []
    acumulado = 0

    for m in range(num_meses):
        qtd = len(instrutores_ativos_por_mes[m])
        custo = qtd * custo_mensal_unitario
        acumulado += custo
        custos_mensais.append(custo)
        custos_acumulados.append(acumulado)

    # Plotagem
    fig, ax1 = plt.subplots(figsize=(14, 7))

    # Eixo 1: Barras (Custo Mensal)
    color_bar = 'tab:blue'
    ax1.set_xlabel('Mês')
    ax1.set_ylabel('Custo Mensal (R$)', color=color_bar)
    bars = ax1.bar(meses, custos_mensais, color=color_bar, alpha=0.6, label='Custo Mensal')
    ax1.tick_params(axis='y', labelcolor=color_bar)
    plt.xticks(rotation=45, ha='right')

    # Eixo 2: Linha (Acumulado)
    ax2 = ax1.twinx()
    color_line = 'tab:red'
    ax2.set_ylabel('Custo Acumulado (R$)', color=color_line)
    ax2.plot(meses, custos_acumulados, color=color_line, linewidth=2, marker='o', label='Acumulado')
    ax2.tick_params(axis='y', labelcolor=color_line)

    # Formatação de valores no topo das barras (abreviado, ex: 50k)
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax1.text(bar.get_x() + bar.get_width() / 2., height,
                     f'R${height / 1000:.0f}k',
                     ha='center', va='bottom', fontsize=8)

    plt.title('Fluxo de Caixa Projetado: Mensal vs Acumulado', fontsize=16)
    fig.tight_layout()

    caminho = "resultados_otimizacao/grafico_fluxo_caixa.png"
    plt.savefig(caminho, dpi=300)
    plt.close()
    return caminho