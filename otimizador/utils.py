from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional
from collections import defaultdict
import math
import pandas as pd
import numpy as np

from .data_models import (
    Projeto, ConfiguracaoProjeto, ParametrosOtimizacao,
    Instrutor, ParametrosFinanceiros
)


# =============================================================================
# GERAÇÃO E CONVERSÃO DE DATAS / MESES
# =============================================================================

def gerar_lista_meses(data_inicio: str, data_fim: str) -> List[str]:
    """Gera lista de meses entre duas datas."""
    try:
        dt_inicio = datetime.strptime(data_inicio, "%d/%m/%Y").replace(day=1)
        dt_fim = datetime.strptime(data_fim, "%d/%m/%Y").replace(day=1)
    except ValueError as e:
        raise ValueError(f"Formato de data inválido. Use DD/MM/YYYY. Erro: {e}")
    if dt_fim < dt_inicio:
        raise ValueError(
            f"Data final ({data_fim}) deve ser posterior à inicial ({data_inicio})"
        )

    meses_nomes = [
        'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
        'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'
    ]
    lista_meses = []
    data_atual = dt_inicio
    while data_atual <= dt_fim:
        lista_meses.append(
            f"{meses_nomes[data_atual.month - 1]}/{str(data_atual.year)[2:]}"
        )
        data_atual = data_atual + timedelta(days=32)
        data_atual = data_atual.replace(day=1)
    return lista_meses


def data_para_indice_mes(data: str, meses: List[str]) -> int:
    """Converte data para índice na lista de meses."""
    try:
        dt = datetime.strptime(data, "%d/%m/%Y")
        meses_map = [
            'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
            'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'
        ]
        mes_procurado = f"{meses_map[dt.month - 1]}/{str(dt.year)[2:]}"
        return meses.index(mes_procurado)
    except (ValueError, IndexError) as e:
        raise ValueError(
            f"Data {data} não está no período de análise. Erro: {e}"
        )


# =============================================================================
# CÁLCULO DE MESES ATIVOS (núcleo do sistema — não alterada)
# =============================================================================

def calcular_meses_ativos(mes_inicio: int,
                          duracao: int,
                          meses_ferias_idx: list,
                          num_meses_total: int) -> list:
    """
    Calcula os meses de calendário em que uma turma está ativa
    academicamente (pulando férias).
    """
    meses_ativos = []
    meses_letivos_contados = 0
    mes_calendario_atual = mes_inicio

    while meses_letivos_contados < duracao and \
            mes_calendario_atual < num_meses_total:
        if mes_calendario_atual not in meses_ferias_idx:
            meses_ativos.append(mes_calendario_atual)
            meses_letivos_contados += 1
        mes_calendario_atual += 1

    return meses_ativos


# =============================================================================
# JANELA DE INÍCIO E DISTRIBUIÇÃO DE TURMAS
# =============================================================================

def calcular_janela_inicio(mes_inicio_projeto: int, mes_fim_projeto: int,
                           duracao: int, meses_ferias: List[int],
                           num_meses: int,
                           meses: List[str]) -> Tuple[int, int]:
    """Calcula a janela válida de início garantindo término dentro do prazo."""
    inicio_min, inicio_max = -1, -1
    for m_inicio in range(mes_inicio_projeto,
                          min(mes_fim_projeto + 1, num_meses)):
        meses_ativos = calcular_meses_ativos(
            m_inicio, duracao, meses_ferias, num_meses
        )
        if len(meses_ativos) == duracao and \
                max(meses_ativos) <= mes_fim_projeto:
            if inicio_min == -1:
                inicio_min = m_inicio
            inicio_max = m_inicio

    if inicio_min == -1:
        raise ValueError(
            "Não há janela válida de início para um dos projetos. "
            "Verifique durações e prazos."
        )
    print(f"   Janela de início calculada: "
          f"{meses[inicio_min]} a {meses[inicio_max]}")
    return inicio_min, inicio_max


def calcular_turmas_por_projeto(limite_total: int,
                                percentual_prog: float) -> Tuple[int, int]:
    """Calcula número de turmas PROG e ROB baseado nos percentuais."""
    num_prog = round(limite_total * percentual_prog / 100)
    return num_prog, limite_total - num_prog


# =============================================================================
# CONVERSÃO DE PROJETOS PARA MODELO (não alterada)
# =============================================================================

def converter_projetos_para_modelo(projetos_config: List[ConfiguracaoProjeto],
                                   meses: List[str],
                                   meses_ferias: List[int],
                                   parametros: ParametrosOtimizacao
                                   ) -> List[Projeto]:
    """Converte configurações de projetos para estrutura do modelo."""
    print(
        "\n" + "=" * 80 +
        "\nCONVERSÃO DE PROJETOS PARA MODELO\n" +
        "=" * 80
    )
    projetos_modelo = []
    for config in projetos_config:
        print(
            f"\nProcessando {config.nome} "
            f"(PROG: {config.percentual_prog:.1f}% / "
            f"ROB: {config.percentual_rob:.1f}%)"
        )
        config.mes_inicio_idx = data_para_indice_mes(config.data_inicio, meses)
        config.mes_termino_idx = data_para_indice_mes(config.data_termino, meses)
        inicio_min, inicio_max = calcular_janela_inicio(
            config.mes_inicio_idx, config.mes_termino_idx,
            config.duracao_curso, meses_ferias, len(meses), meses
        )

        prog_total, rob_total = calcular_turmas_por_projeto(
            config.num_turmas, config.percentual_prog
        )

        print(
            f"   Total: {config.num_turmas} turmas "
            f"(PROG: {prog_total}, ROB: {rob_total}) | "
            f"Ondas: {config.ondas}"
        )

        if config.ondas == 1:
            projetos_modelo.append(
                Projeto(
                    config.nome, prog_total, rob_total,
                    config.duracao_curso, inicio_min, inicio_max,
                    config.mes_termino_idx, config.turmas_min_por_mes,
                    None  # ondas_detalhadas preenchido pelo Stage 1
                )
            )
        else:
            prog_por_onda = prog_total // config.ondas
            rob_por_onda = rob_total // config.ondas
            for onda_idx in range(config.ondas):
                prog_onda = (
                    prog_total - (prog_por_onda * (config.ondas - 1))
                    if onda_idx == config.ondas - 1
                    else prog_por_onda
                )
                rob_onda = (
                    rob_total - (rob_por_onda * (config.ondas - 1))
                    if onda_idx == config.ondas - 1
                    else rob_por_onda
                )
                nome_onda = f"{config.nome}_Onda{onda_idx + 1}"
                projetos_modelo.append(
                    Projeto(
                        nome_onda, prog_onda, rob_onda,
                        config.duracao_curso, inicio_min, inicio_max,
                        config.mes_termino_idx, config.turmas_min_por_mes,
                        None  # ondas_detalhadas preenchido pelo Stage 1
                    )
                )
                print(f"   - {nome_onda}: {prog_onda} PROG, {rob_onda} ROB")
    print("=" * 80)
    return projetos_modelo


# =============================================================================
# PÓS-PROCESSAMENTO DE INSTRUTORES (não alterada)
# =============================================================================

def renumerar_instrutores_ativos(
        atribuicoes: List[Dict]) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Renumera apenas os instrutores que receberam turmas
    e retorna a contagem por habilidade.
    """
    print("\n--- Renumerando Instrutores Ativos ---")
    instrutores_usados = sorted(
        list(set(atr['instrutor'] for atr in atribuicoes)),
        key=lambda i: (i.habilidade, int(i.id.split('_')[1]))
    )
    mapeamento, contador_por_hab = {}, defaultdict(int)

    for inst_antigo in instrutores_usados:
        hab = inst_antigo.habilidade
        contador_por_hab[hab] += 1
        prefixo = 'PROG' if hab == 'PROG' else 'ROB'
        novo_id = f'{prefixo}_{contador_por_hab[hab]}'
        mapeamento[inst_antigo.id] = Instrutor(
            novo_id, hab,
            inst_antigo.capacidade,
            inst_antigo.laboratorio_id
        )

    print("Contagem final de instrutores por habilidade:")
    for hab, count in sorted(contador_por_hab.items()):
        print(f"   • {hab}: {count} instrutores")

    atribuicoes_renumeradas = [
        {
            'turma': atr['turma'],
            'instrutor': mapeamento[atr['instrutor'].id]
        }
        for atr in atribuicoes
    ]

    return atribuicoes_renumeradas, dict(contador_por_hab)


def analisar_distribuicao_instrutores_por_projeto(
        atribuicoes: List[Dict]) -> Dict[str, Dict[str, int]]:
    """
    Analisa as atribuições para contar quantos instrutores
    únicos por projeto.
    """
    instrutores_vistos = defaultdict(lambda: defaultdict(set))
    for atr in atribuicoes:
        projeto_base_nome = atr['turma'].projeto.split('_Onda')[0]
        instrutor = atr['instrutor']
        instrutores_vistos[projeto_base_nome][instrutor.habilidade].add(
            instrutor.id
        )

    contagem_final = {
        proj: {
            'PROG': len(hab_sets.get('PROG', set())),
            'ROBOTICA': len(hab_sets.get('ROBOTICA', set()))
        }
        for proj, hab_sets in instrutores_vistos.items()
    }
    return contagem_final


# =============================================================================
# LOWER BOUNDS AUTOMÁTICOS — NOVO (Q5)
# Calcula o número mínimo teórico de instrutores por habilidade
# antes de chamar o solver. Usado pelo Stage 2 reformulado.
# =============================================================================

def calcular_lower_bounds(projetos: List[Projeto],
                          meses: List[str],
                          meses_ferias_idx: List[int],
                          capacidade: int) -> Dict[str, Dict[str, int]]:
    """
    Calcula lower bounds automáticos para o número de instrutores
    necessários por habilidade e por projeto.

    Retorna dicionário no formato:
    {
        'global': {'PROG': int, 'ROB': int},
        'por_projeto': {
            'nome_projeto': {'PROG': int, 'ROB': int}
        }
    }

    Três lower bounds são calculados e o máximo é retornado:
      LB1 — por pico de demanda simultânea (turmas ativas no mesmo mês)
      LB2 — por demanda total (turmas / capacidade total disponível)
      LB3 — por onda de maior carga (pico de uma única onda)
    """
    num_meses = len(meses)

    resultado = {
        'global': {'PROG': 0, 'ROB': 0},
        'por_projeto': {}
    }

    # -------------------------------------------------------------------------
    # LB por projeto individual
    # -------------------------------------------------------------------------
    for proj in projetos:
        nome_base = proj.nome.split('_Onda')[0]
        if nome_base not in resultado['por_projeto']:
            resultado['por_projeto'][nome_base] = {'PROG': 0, 'ROB': 0}

        for hab, total_turmas in [('PROG', proj.prog), ('ROB', proj.rob)]:
            if total_turmas == 0:
                continue

            # LB2 — por demanda total do projeto
            meses_letivos_proj = [
                m for m in range(proj.inicio_min, proj.mes_fim_projeto + 1)
                if m not in meses_ferias_idx and m < num_meses
            ]
            if not meses_letivos_proj:
                continue

            capacidade_total = capacidade * len(meses_letivos_proj)
            lb2 = math.ceil(total_turmas / capacidade_total) \
                if capacidade_total > 0 else total_turmas

            # LB3 — por pico de demanda mensal do projeto
            # Assume início mais concentrado possível (inicio_min)
            demanda_por_mes = defaultdict(int)
            # Distribui turmas uniformemente a partir do início mínimo
            turmas_restantes = total_turmas
            mes_atual = proj.inicio_min
            while turmas_restantes > 0 and mes_atual < num_meses:
                if mes_atual not in meses_ferias_idx:
                    demanda_por_mes[mes_atual] += min(
                        capacidade, turmas_restantes
                    )
                    turmas_restantes -= min(capacidade, turmas_restantes)
                mes_atual += 1

            pico_proj = max(demanda_por_mes.values()) \
                if demanda_por_mes else total_turmas
            lb3 = math.ceil(pico_proj / capacidade)

            lb_proj = max(lb2, lb3)
            resultado['por_projeto'][nome_base][hab] = max(
                resultado['por_projeto'][nome_base][hab], lb_proj
            )

    # -------------------------------------------------------------------------
    # LB global — pico simultâneo entre todos os projetos (LB1)
    # -------------------------------------------------------------------------
    for hab in ['PROG', 'ROB']:
        demanda_global = defaultdict(int)

        for proj in projetos:
            total_turmas = proj.prog if hab == 'PROG' else proj.rob
            if total_turmas == 0:
                continue

            # Distribui turmas do projeto ao longo de seus meses letivos
            meses_letivos = [
                m for m in range(proj.inicio_min, proj.mes_fim_projeto + 1)
                if m not in meses_ferias_idx and m < num_meses
            ]
            if not meses_letivos:
                continue

            turmas_por_mes = total_turmas / len(meses_letivos)
            for m in meses_letivos:
                demanda_global[m] += turmas_por_mes

        if demanda_global:
            pico_global = max(demanda_global.values())
            lb1_global = math.ceil(pico_global / capacidade)

            # Soma dos LBs por projeto como alternativa
            lb_soma_projetos = sum(
                v[hab]
                for v in resultado['por_projeto'].values()
            )

            resultado['global'][hab] = max(lb1_global, lb_soma_projetos)
        else:
            resultado['global'][hab] = 0

    # -------------------------------------------------------------------------
    # Log dos resultados
    # -------------------------------------------------------------------------
    print("\n--- Lower Bounds Calculados ---")
    print(f"   Global PROG: ≥ {resultado['global']['PROG']} instrutores")
    print(f"   Global ROB:  ≥ {resultado['global']['ROB']} instrutores")
    for proj_nome, lbs in resultado['por_projeto'].items():
        print(
            f"   {proj_nome}: "
            f"PROG ≥ {lbs['PROG']}, "
            f"ROB ≥ {lbs['ROB']}"
        )

    return resultado


# =============================================================================
# CÁLCULO FINANCEIRO (não alterado)
# =============================================================================

def calcular_fluxo_caixa_detalhado(
        atribuicoes: List[Dict],
        meses: List[str],
        meses_ferias_idx: List[int],
        parametros_financeiros: ParametrosFinanceiros,
        projeto_filtro: Optional[str] = None) -> pd.DataFrame:
    """Calcula o fluxo de caixa detalhado."""
    num_meses = len(meses)
    custos_mensais = np.zeros(num_meses)

    if not parametros_financeiros or \
            not parametros_financeiros.itens_custo:
        return pd.DataFrame()

    instrutores_ativos_no_mes = {m: set() for m in range(num_meses)}

    for atr in atribuicoes:
        t = atr['turma']
        nome_projeto_turma = t.projeto.split('_Onda')[0]

        if projeto_filtro and nome_projeto_turma != projeto_filtro:
            continue

        meses_ativos = calcular_meses_ativos(
            t.mes_inicio, t.duracao, meses_ferias_idx, num_meses
        )
        for m in meses_ativos:
            instrutores_ativos_no_mes[m].add(atr['instrutor'].id)

    for item in parametros_financeiros.itens_custo:
        if item.tipo == 'PERMANENTE':
            if projeto_filtro:
                if item.projeto == projeto_filtro:
                    custos_mensais += item.valor
            else:
                custos_mensais += item.valor

        elif item.tipo == 'INSTRUTOR':
            aplica_custo = False
            if item.projeto is None:
                aplica_custo = True
            elif projeto_filtro and item.projeto == projeto_filtro:
                aplica_custo = True
            elif not projeto_filtro and item.projeto:
                aplica_custo = True

            if aplica_custo:
                if projeto_filtro:
                    if item.projeto is None or \
                            item.projeto == projeto_filtro:
                        for m in range(num_meses):
                            qtd_ativos = len(
                                instrutores_ativos_no_mes[m]
                            )
                            custos_mensais[m] += qtd_ativos * item.valor
                else:
                    if item.projeto is None:
                        for m in range(num_meses):
                            qtd_ativos = len(
                                instrutores_ativos_no_mes[m]
                            )
                            custos_mensais[m] += qtd_ativos * item.valor
                    else:
                        ativos_proj_especifico = {
                            m: set() for m in range(num_meses)
                        }
                        for atr in atribuicoes:
                            if atr['turma'].projeto.split('_Onda')[0] \
                                    == item.projeto:
                                for m in calcular_meses_ativos(
                                    atr['turma'].mes_inicio,
                                    atr['turma'].duracao,
                                    meses_ferias_idx, num_meses
                                ):
                                    ativos_proj_especifico[m].add(
                                        atr['instrutor'].id
                                    )
                        for m in range(num_meses):
                            custos_mensais[m] += \
                                len(ativos_proj_especifico[m]) * item.valor

    for atr in atribuicoes:
        t = atr['turma']
        nome_projeto_turma = t.projeto.split('_Onda')[0]

        if projeto_filtro and nome_projeto_turma != projeto_filtro:
            continue

        meses_academicos = calcular_meses_ativos(
            t.mes_inicio, t.duracao, meses_ferias_idx, num_meses
        )
        if not meses_academicos:
            continue

        mes_inicio_real = meses_academicos[0]
        mes_fim_real = meses_academicos[-1]
        periodo_execucao = range(
            mes_inicio_real, min(mes_fim_real + 1, num_meses)
        )

        for item in parametros_financeiros.itens_custo:
            aplica_custo = (
                item.projeto is None or
                item.projeto == nome_projeto_turma
            )
            if not aplica_custo:
                continue

            if item.tipo == 'INICIAL':
                if mes_inicio_real < num_meses:
                    custos_mensais[mes_inicio_real] += item.valor
            elif item.tipo == 'ENCERRAMENTO':
                if mes_fim_real < num_meses:
                    custos_mensais[mes_fim_real] += item.valor
            elif item.tipo == 'EXECUCAO':
                for m in periodo_execucao:
                    if m < num_meses:
                        custos_mensais[m] += item.valor

    dados = []
    acumulado = 0.0
    for idx, mes in enumerate(meses):
        valor_mes = custos_mensais[idx]
        acumulado += valor_mes
        dados.append({
            'Mês': mes,
            'Custo Mensal': valor_mes,
            'Custo Acumulado': acumulado
        })

    return pd.DataFrame(dados)


def calcular_evolucao_instrutores(
        atribuicoes: List[Dict],
        meses: List[str],
        meses_ferias_idx: List[int]) -> pd.DataFrame:
    """
    Calcula a quantidade de instrutores únicos ativos por mês,
    separados por tipologia.
    """
    num_meses = len(meses)
    instrutores_ativos = {m: defaultdict(set) for m in range(num_meses)}

    for atr in atribuicoes:
        t = atr['turma']
        i = atr['instrutor']
        meses_ativos = calcular_meses_ativos(
            t.mes_inicio, t.duracao, meses_ferias_idx, num_meses
        )
        for m in meses_ativos:
            instrutores_ativos[m][i.habilidade].add(i.id)

    dados = []
    for m_idx, mes_nome in enumerate(meses):
        qtd_prog = len(instrutores_ativos[m_idx].get('PROG', set()))
        qtd_rob = len(instrutores_ativos[m_idx].get('ROBOTICA', set()))
        dados.append({
            'Mes': mes_nome,
            'Instrutores_PROG': qtd_prog,
            'Instrutores_ROB': qtd_rob,
            'Total': qtd_prog + qtd_rob
        })

    return pd.DataFrame(dados)