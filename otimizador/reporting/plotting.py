import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from ..utils import calcular_meses_ativos, calcular_fluxo_caixa_detalhado
from ..data_models import Projeto, Turma, ParametrosFinanceiros

plt.style.use('ggplot')


def gerar_grafico_turmas_projeto_mes(turmas: List[Turma], projetos: List[Projeto], meses: List[str],
                                     meses_ferias_idx: List[int]) -> str:
    num_meses = len(meses)
    dados = {p.nome: np.zeros(num_meses) for p in projetos}
    for t in turmas:
        for m in calcular_meses_ativos(t.mes_inicio, t.duracao, meses_ferias_idx, num_meses):
            dados[t.projeto.split('_Onda')[0]][m] += 1

    fig, ax = plt.subplots(figsize=(14, 7))
    bottom = np.zeros(num_meses)
    for nome, vals in dados.items():
        ax.bar(meses, vals, bottom=bottom, label=nome, alpha=0.8)
        bottom += vals

    ax.set_title('Turmas Ativas por Projeto');
    ax.legend()
    plt.xticks(rotation=45, ha='right');
    plt.tight_layout()
    path = "resultados_otimizacao/grafico_turmas_projeto.png"
    plt.savefig(path);
    plt.close();
    return path


def gerar_grafico_turmas_instrutor_tipologia_projeto(atribuicoes: List[Dict]) -> str:
    dados = {}
    for atr in atribuicoes:
        i, p = atr['instrutor'].id, atr['turma'].projeto.split('_Onda')[0]
        if i not in dados: dados[i] = {}
        dados[i][p] = dados[i].get(p, 0) + 1

    insts = sorted(dados.keys())
    projs = sorted(list({p for d in dados.values() for p in d}))

    fig, ax = plt.subplots(figsize=(15, 8))
    bottom = np.zeros(len(insts))
    for p in projs:
        vals = [dados[i].get(p, 0) for i in insts]
        ax.bar(insts, vals, bottom=bottom, label=p)
        bottom += np.array(vals)

    ax.set_title('Turmas por Instrutor');
    ax.legend();
    plt.xticks(rotation=90);
    plt.tight_layout()
    path = "resultados_otimizacao/grafico_instrutor_projeto.png"
    plt.savefig(path);
    plt.close();
    return path


def gerar_grafico_carga_por_instrutor(atribuicoes: List[Dict]) -> str:
    cargas = {}
    for atr in atribuicoes: cargas[atr['instrutor'].id] = cargas.get(atr['instrutor'].id, 0) + 1
    vals = list(cargas.values())

    plt.figure(figsize=(10, 6))
    plt.hist(vals, bins=range(min(vals), max(vals) + 2), align='left', rwidth=0.8, color='skyblue', edgecolor='black')
    plt.title('Histograma de Carga');
    plt.tight_layout()
    path = "resultados_otimizacao/grafico_carga_instrutores.png"
    plt.savefig(path);
    plt.close();
    return path


def gerar_grafico_demanda_prog_rob(turmas: List[Turma], projetos: List[Projeto], meses: List[str],
                                   meses_ferias_idx: List[int]) -> Tuple[str, pd.DataFrame]:
    prog, rob = np.zeros(len(meses)), np.zeros(len(meses))
    for t in turmas:
        for m in calcular_meses_ativos(t.mes_inicio, t.duracao, meses_ferias_idx, len(meses)):
            if t.habilidade == 'PROG':
                prog[m] += 1
            else:
                rob[m] += 1

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(meses, prog, label='PROG', marker='o');
    ax.plot(meses, rob, label='ROB', marker='s')
    ax.set_title('Demanda por Habilidade');
    ax.legend();
    plt.xticks(rotation=45);
    plt.tight_layout()
    path = "resultados_otimizacao/grafico_demanda_habilidade.png"
    plt.savefig(path);
    plt.close()
    return path, pd.DataFrame({'Mes': meses, 'Demanda_PROG': prog, 'Demanda_ROB': rob, 'Total': prog + rob})


def plotar_conclusoes_por_mes(turmas: List[Turma], projetos: List[Projeto], meses: List[str],
                              meses_ferias_idx: List[int]) -> str:
    conclusoes = np.zeros(len(meses))
    for t in turmas:
        ativos = calcular_meses_ativos(t.mes_inicio, t.duracao, meses_ferias_idx, len(meses))
        if ativos: conclusoes[ativos[-1]] += 1

    plt.figure(figsize=(12, 6))
    plt.bar(meses, conclusoes, color='green', alpha=0.6)
    plt.title('Conclusões por Mês');
    plt.xticks(rotation=45);
    plt.tight_layout()
    path = "resultados_otimizacao/grafico_conclusoes.png"
    plt.savefig(path);
    plt.close();
    return path


def gerar_grafico_fluxo_caixa(atribuicoes: List[Dict], meses: List[str], meses_ferias_idx: List[int],
                              parametros_financeiros: ParametrosFinanceiros) -> str:
    """Gera gráfico financeiro usando a lógica unificada de custos."""
    df = calcular_fluxo_caixa_detalhado(atribuicoes, meses, meses_ferias_idx, parametros_financeiros)
    if df.empty: return None

    fig, ax1 = plt.subplots(figsize=(14, 7))

    ax1.bar(df['Mês'], df['Custo Mensal'], color='tab:blue', alpha=0.6, label='Mensal')
    ax1.set_ylabel('Custo Mensal (R$)', color='tab:blue')
    ax1.tick_params(axis='y', labelcolor='tab:blue')
    plt.xticks(rotation=45, ha='right')

    ax2 = ax1.twinx()
    ax2.plot(df['Mês'], df['Custo Acumulado'], color='tab:red', marker='o', linewidth=2, label='Acumulado')
    ax2.set_ylabel('Acumulado (R$)', color='tab:red')
    ax2.tick_params(axis='y', labelcolor='tab:red')

    plt.title('Fluxo de Caixa Projetado (Todos os Custos)', fontsize=16)
    fig.tight_layout()
    path = "resultados_otimizacao/grafico_fluxo_caixa.png"
    plt.savefig(path);
    plt.close();
    return path