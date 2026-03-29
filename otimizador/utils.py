"""
Módulo de Utilidades e Cálculos Auxiliares
Versão 5.5 - Correção: Multiplicação Real por Headcount no Financeiro
"""

from datetime import datetime
from typing import List, Dict, Tuple, Optional
import pandas as pd
from .data_models import Projeto, Turma, Instrutor, ParametrosOtimizacao, ParametrosFinanceiros


def gerar_lista_meses(data_inicio: str, data_fim: str) -> List[str]:
    """Gera lista de meses no formato 'Jan/26' entre duas datas."""
    inicio = datetime.strptime(data_inicio, "%d/%m/%Y")
    fim = datetime.strptime(data_fim, "%d/%m/%Y")
    meses = []
    atual = inicio
    while atual <= fim:
        meses.append(atual.strftime("%b/%y"))
        proximo_mes = atual.month % 12 + 1
        ano = atual.year + (atual.month // 12)
        atual = datetime(ano, proximo_mes, 1)
    return meses


def calcular_meses_ativos(mes_inicio_idx: int, duracao: int, ferias_idx: List[int], num_meses: int) -> List[int]:
    """Calcula os índices dos meses em que uma turma está ativa, pulando férias."""
    ativos = []
    atual = mes_inicio_idx
    contagem = 0
    while contagem < duracao and atual < num_meses:
        if atual not in ferias_idx:
            ativos.append(atual)
            contagem += 1
        atual += 1
    return ativos


def converter_projetos_para_modelo(projetos_config: List[Projeto], meses: List[str], ferias_idx: List[int],
                                   params: ParametrosOtimizacao) -> List[Projeto]:
    """Divide cada projeto em PROG e ROB com base no percentual_prog."""
    projetos_modelo = []
    for p in projetos_config:
        try:
            data_ini = datetime.strptime(p.data_inicio, "%d/%m/%Y").strftime("%b/%y")
            ini_idx = meses.index(data_ini)
            data_fim = datetime.strptime(p.data_termino, "%d/%m/%Y").strftime("%b/%y")
            fim_idx = meses.index(data_fim)
            num_prog = int(p.num_turmas * (p.percentual_prog / 100))
            num_rob = p.num_turmas - num_prog
            if num_prog > 0:
                projetos_modelo.append(
                    p._replace(nome=p.nome, num_turmas=num_prog, habilidade="PROG", mes_inicio_idx=ini_idx,
                               mes_termino_idx=fim_idx))
            if num_rob > 0:
                projetos_modelo.append(
                    p._replace(nome=p.nome, num_turmas=num_rob, habilidade="ROB", mes_inicio_idx=ini_idx,
                               mes_termino_idx=fim_idx))
        except ValueError:
            print(f"⚠️ Erro: Datas do projeto '{p.nome}' fora do intervalo.")
    return projetos_modelo


def renumerar_instrutores_ativos(atribuicoes: List[Dict]) -> Tuple[List[Dict], Dict]:
    """Renumera instrutores para I01, I02... e conta por habilidade."""
    mapa = {};
    contador = 1;
    novas = [];
    hab_count = {"PROG": 0, "ROB": 0}
    for atr in sorted(atribuicoes, key=lambda x: x['instrutor'].id):
        v_id = atr['instrutor'].id
        if v_id not in mapa:
            n_id = f"I{contador:02d}";
            mapa[v_id] = n_id;
            contador += 1
            hab_count[atr['instrutor'].habilidade] += 1
        n_inst = atr['instrutor']._replace(id=mapa[v_id])
        novas.append({**atr, 'instrutor': n_inst})
    return novas, hab_count


def analisar_distribuicao_instrutores_por_projeto(atribuicoes: List[Dict]) -> Dict:
    dist = {}
    for atr in atribuicoes:
        p = atr['turma'].projeto;
        i = atr['instrutor'].id
        if p not in dist: dist[p] = set()
        dist[p].add(i)
    return {p: len(s) for p, s in dist.items()}


def calcular_evolucao_instrutores(atribuicoes: List[Dict], meses: List[str], ferias_idx: List[int]) -> pd.DataFrame:
    dados = []
    for m_idx, mes in enumerate(meses):
        inst_p = set();
        inst_r = set()
        for atr in atribuicoes:
            t = atr['turma']
            if m_idx in calcular_meses_ativos(t.mes_inicio, t.duracao, ferias_idx, len(meses)):
                if t.habilidade == 'PROG':
                    inst_p.add(atr['instrutor'].id)
                else:
                    inst_r.add(atr['instrutor'].id)
        dados.append({'Mes': mes, 'Instrutores_PROG': len(inst_p), 'Instrutores_ROB': len(inst_r),
                      'Total': len(inst_p) + len(inst_r)})
    return pd.DataFrame(dados)


def calcular_turmas_abertas_por_mes(turmas: List[Turma], meses: List[str], ferias_idx: List[int]) -> pd.DataFrame:
    dados = []
    for m_idx, mes in enumerate(meses):
        p = sum(1 for t in turmas if t.mes_inicio == m_idx and t.habilidade == 'PROG')
        r = sum(1 for t in turmas if t.mes_inicio == m_idx and t.habilidade == 'ROB')
        dados.append({'Mes': mes, 'Abertas_PROG': p, 'Abertas_ROB': r, 'Total_Abertas': p + r})
    return pd.DataFrame(dados)


def calcular_fluxo_caixa_detalhado(atribuicoes: List[Dict], meses: List[str], ferias_idx: List[int],
                                   fin: Optional[ParametrosFinanceiros], projeto_filtro: str = None) -> pd.DataFrame:
    """Calcula custos multiplicando o valor unitário pela quantidade de instrutores ativos."""
    df_evo = calcular_evolucao_instrutores(atribuicoes, meses, ferias_idx)
    registros = []
    acumulado = 0.0

    for m_idx, row in df_evo.iterrows():
        mes_nome = row['Mes']
        custo_mes = 0.0

        # Se for mês de férias, o custo operacional é zero (ajuste conforme sua política)
        if fin and m_idx not in ferias_idx:
            for item in fin.itens_custo:
                if projeto_filtro and item.projeto and item.projeto != projeto_filtro:
                    continue

                # Lógica Robusta: Multiplica pelo headcount da habilidade
                desc = item.descricao.upper()
                if "PROG" in desc:
                    custo_mes += item.valor * row['Instrutores_PROG']
                elif "ROB" in desc:
                    custo_mes += item.valor * row['Instrutores_ROB']
                elif "SALÁRIO" in desc or "INSTRUTOR" in desc:
                    # Se não especifica habilidade mas é salário, assume total
                    custo_mes += item.valor * row['Total']
                else:
                    # Custos fixos (Infra, Licenças, etc)
                    custo_mes += item.valor

        acumulado += custo_mes
        registros.append({'Mês': mes_nome, 'Custo Mensal': custo_mes, 'Custo Acumulado': acumulado})

    return pd.DataFrame(registros)