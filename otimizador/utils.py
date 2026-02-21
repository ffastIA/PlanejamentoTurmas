from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional
from collections import defaultdict
import pandas as pd
import numpy as np
import math

from .data_models import (
    Projeto, ConfiguracaoProjeto, ParametrosOtimizacao,
    Instrutor, ParametrosFinanceiros
)


# =============================================================================
# FUNÇÕES EXISTENTES — INALTERADAS
# =============================================================================

def gerar_lista_meses(data_inicio: str, data_fim: str) -> List[str]:
    """Gera lista de meses entre duas datas."""
    try:
        dt_inicio = datetime.strptime(data_inicio, "%d/%m/%Y").replace(day=1)
        dt_fim    = datetime.strptime(data_fim,    "%d/%m/%Y").replace(day=1)
    except ValueError as e:
        raise ValueError(
            f"Formato de data inválido. Use DD/MM/YYYY. Erro: {e}"
        )
    if dt_fim < dt_inicio:
        raise ValueError(
            f"Data final ({data_fim}) deve ser posterior "
            f"à inicial ({data_inicio})"
        )
    meses_nomes = [
        'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
        'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'
    ]
    lista_meses = []
    data_atual  = dt_inicio
    while data_atual <= dt_fim:
        lista_meses.append(
            f"{meses_nomes[data_atual.month - 1]}"
            f"/{str(data_atual.year)[2:]}"
        )
        data_atual = (data_atual + timedelta(days=32)).replace(day=1)
    return lista_meses


def data_para_indice_mes(data: str, meses: List[str]) -> int:
    """Converte data para índice na lista de meses."""
    try:
        dt = datetime.strptime(data, "%d/%m/%Y")
        meses_map = [
            'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
            'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'
        ]
        mes_procurado = (
            f"{meses_map[dt.month - 1]}/{str(dt.year)[2:]}"
        )
        return meses.index(mes_procurado)
    except (ValueError, IndexError) as e:
        raise ValueError(
            f"Data {data} não está no período de análise. Erro: {e}"
        )


def calcular_meses_ativos(
    mes_inicio: int,
    duracao: int,
    meses_ferias_idx: list,
    num_meses_total: int
) -> list:
    """
    Calcula os meses de calendário em que uma turma está ativa
    academicamente (pulando férias).
    """
    meses_ativos           = []
    meses_letivos_contados = 0
    mes_calendario_atual   = mes_inicio

    while (meses_letivos_contados < duracao
           and mes_calendario_atual < num_meses_total):
        if mes_calendario_atual not in meses_ferias_idx:
            meses_ativos.append(mes_calendario_atual)
            meses_letivos_contados += 1
        mes_calendario_atual += 1

    return meses_ativos


def calcular_janela_inicio(
    mes_inicio_projeto: int,
    mes_fim_projeto: int,
    duracao: int,
    meses_ferias: List[int],
    num_meses: int,
    meses: List[str]
) -> Tuple[int, int]:
    """
    Calcula a janela válida de início garantindo término
    dentro do prazo.
    """
    inicio_min, inicio_max = -1, -1
    for m_inicio in range(
        mes_inicio_projeto,
        min(mes_fim_projeto + 1, num_meses)
    ):
        meses_ativos = calcular_meses_ativos(
            m_inicio, duracao, meses_ferias, num_meses
        )
        if (len(meses_ativos) == duracao
                and max(meses_ativos) <= mes_fim_projeto):
            if inicio_min == -1:
                inicio_min = m_inicio
            inicio_max = m_inicio

    if inicio_min == -1:
        raise ValueError(
            "Não há janela válida de início para um dos projetos. "
            "Verifique durações e prazos."
        )
    print(
        f"   Janela global de início: "
        f"{meses[inicio_min]} a {meses[inicio_max]}"
    )
    return inicio_min, inicio_max


def calcular_turmas_por_projeto(
    limite_total: int,
    percentual_prog: float
) -> Tuple[int, int]:
    """Calcula número de turmas PROG e ROB baseado nos percentuais."""
    num_prog = round(limite_total * percentual_prog / 100)
    return num_prog, limite_total - num_prog


# =============================================================================
# FUNÇÕES AUXILIARES PARA JANELAS ESCALONADAS — CORRIGIDAS
# =============================================================================

def _calcular_inicio_max_onda(
    inicio_min_onda: int,
    mes_termino_projeto: int,
    duracao_curso: int,
    ondas_restantes: int,
    meses_ferias: List[int],
    num_meses: int
) -> int:
    """
    Calcula o início máximo de uma onda garantindo que todas as
    ondas restantes (incluindo esta) caibam no período do projeto.

    CORREÇÃO v2.2:
    O loop de varredura reversa agora atualiza limite_superior
    a cada mês letivo contado — não apenas ao atingir o total.
    Isso garante que o limite seja corretamente posicionado mesmo
    quando o horizonte é exatamente suficiente (margem = 0).

    Parâmetros:
        inicio_min_onda     : índice mínimo de início desta onda
        mes_termino_projeto : índice do último mês do projeto pai
        duracao_curso       : duração em meses letivos de cada onda
        ondas_restantes     : ondas que ainda precisam caber
                              (incluindo a onda atual)
        meses_ferias        : índices dos meses de férias
        num_meses           : total de meses no horizonte
    """
    # Meses letivos a reservar para ondas POSTERIORES a esta
    letivos_para_reservar = duracao_curso * (ondas_restantes - 1)

    if letivos_para_reservar == 0:
        # Última onda: pode começar até onde cabe dentro do período
        inicio_max = -1
        for candidato in range(
            inicio_min_onda,
            min(mes_termino_projeto + 1, num_meses)
        ):
            ma = calcular_meses_ativos(
                candidato, duracao_curso, meses_ferias, num_meses
            )
            if (len(ma) == duracao_curso
                    and ma[-1] <= mes_termino_projeto):
                inicio_max = candidato
        return max(inicio_min_onda, inicio_max if inicio_max != -1
                   else inicio_min_onda)

    # ── VARREDURA REVERSA CORRIGIDA ──────────────────────────────────────────
    # Percorre de trás para frente contando meses letivos.
    # limite_superior é atualizado a cada mês letivo encontrado,
    # de forma que ao contar letivos_para_reservar meses,
    # limite_superior aponta para o mês imediatamente anterior
    # ao início da "zona reservada".
    letivos_contados = 0
    limite_superior  = -1   # ← inicializado como inválido (não como mes_termino)

    m = mes_termino_projeto
    while m >= inicio_min_onda:
        if m not in meses_ferias:
            letivos_contados += 1
            if letivos_contados == letivos_para_reservar:
                # O mês m é o primeiro mês da zona reservada.
                # limite_superior = mês anterior a m
                limite_superior = m - 1
                break
        m -= 1

    # Se não conseguiu reservar espaço suficiente, o projeto
    # é estruturalmente inviável — retorna inicio_min para
    # que o Stage 1 detecte e reporte adequadamente
    if limite_superior == -1:
        print(
            f"   ⚠ AVISO: Não há espaço para reservar "
            f"{letivos_para_reservar} meses letivos posteriores. "
            f"Projeto pode ser inviável."
        )
        return inicio_min_onda

    # ── ENCONTRAR inicio_max VÁLIDO DENTRO DO limite_superior ────────────────
    inicio_max = -1
    for candidato in range(
        inicio_min_onda,
        min(limite_superior + 1, num_meses)
    ):
        ma = calcular_meses_ativos(
            candidato, duracao_curso, meses_ferias, num_meses
        )
        if (len(ma) == duracao_curso
                and ma[-1] <= limite_superior):
            inicio_max = candidato

    if inicio_max == -1:
        print(
            f"   ⚠ AVISO: Nenhum início válido encontrado "
            f"até limite_superior={limite_superior}. "
            f"Usando inicio_min_onda como fallback."
        )
        return inicio_min_onda

    return inicio_max


def _avancar_inicio_min_pos_onda(
    inicio_min_onda_atual: int,
    duracao_curso: int,
    meses_ferias: List[int],
    num_meses: int
) -> int:
    """
    Calcula o início mínimo da onda seguinte posicionando-a
    imediatamente após o término mínimo da onda atual.
    """
    meses_ativos = calcular_meses_ativos(
        inicio_min_onda_atual, duracao_curso, meses_ferias, num_meses
    )
    if meses_ativos:
        return meses_ativos[-1] + 1
    return inicio_min_onda_atual + duracao_curso


# =============================================================================
# CONVERSÃO DE PROJETOS — JANELAS ESCALONADAS (inalterada exceto dependência)
# =============================================================================

def converter_projetos_para_modelo(
    projetos_config: List[ConfiguracaoProjeto],
    meses: List[str],
    meses_ferias: List[int],
    parametros: ParametrosOtimizacao
) -> List[Projeto]:
    """
    Converte configurações de projetos para estrutura do modelo.

    Projetos com múltiplas ondas recebem janelas ESCALONADAS:
      - Onda 1: [inicio_min_global .. inicio_max_calculado]
      - Onda N: início mínimo = término mínimo da Onda N-1 + 1 mês
    """
    print(
        "\n" + "=" * 80 +
        "\nCONVERSÃO DE PROJETOS PARA MODELO "
        "(v2.2 — Janelas Escalonadas Corrigidas)\n" +
        "=" * 80
    )
    projetos_modelo = []

    for config in projetos_config:
        print(
            f"\nProcessando '{config.nome}' "
            f"(PROG: {config.percentual_prog:.1f}% / "
            f"ROB:  {config.percentual_rob:.1f}% | "
            f"Ondas: {config.ondas})"
        )

        config.mes_inicio_idx  = data_para_indice_mes(
            config.data_inicio, meses
        )
        config.mes_termino_idx = data_para_indice_mes(
            config.data_termino, meses
        )

        inicio_min_global, inicio_max_global = calcular_janela_inicio(
            config.mes_inicio_idx,
            config.mes_termino_idx,
            config.duracao_curso,
            meses_ferias,
            len(meses),
            meses
        )

        prog_total, rob_total = calcular_turmas_por_projeto(
            config.num_turmas, config.percentual_prog
        )

        print(
            f"   Total: {config.num_turmas} turmas "
            f"(PROG: {prog_total}, ROB: {rob_total})"
        )

        # ── PROJETO DE 1 ONDA ────────────────────────────────────────────────
        if config.ondas == 1:
            projetos_modelo.append(Projeto(
                config.nome,
                prog_total,
                rob_total,
                config.duracao_curso,
                inicio_min_global,
                inicio_max_global,
                config.mes_termino_idx,
                config.turmas_min_por_mes,
                config.nome,
                0
            ))
            print(
                f"   ✓ {config.nome}: {prog_total} PROG, {rob_total} ROB | "
                f"janela: {meses[inicio_min_global]} "
                f"a {meses[inicio_max_global]}"
            )

        # ── PROJETO COM MÚLTIPLAS ONDAS ──────────────────────────────────────
        else:
            prog_por_onda  = prog_total // config.ondas
            rob_por_onda   = rob_total  // config.ondas
            inicio_min_onda = inicio_min_global

            for onda_idx in range(config.ondas):
                eh_ultima = (onda_idx == config.ondas - 1)

                prog_onda = (
                    prog_total - prog_por_onda * (config.ondas - 1)
                    if eh_ultima else prog_por_onda
                )
                rob_onda = (
                    rob_total - rob_por_onda * (config.ondas - 1)
                    if eh_ultima else rob_por_onda
                )

                ondas_restantes = config.ondas - onda_idx

                inicio_max_onda = _calcular_inicio_max_onda(
                    inicio_min_onda,
                    config.mes_termino_idx,
                    config.duracao_curso,
                    ondas_restantes,
                    meses_ferias,
                    len(meses)
                )

                nome_onda = f"{config.nome}_Onda{onda_idx + 1}"

                # Validação
                label_min = meses[min(inicio_min_onda, len(meses) - 1)]
                label_max = meses[min(inicio_max_onda, len(meses) - 1)]

                if inicio_min_onda > inicio_max_onda:
                    print(
                        f"   ⚠ {nome_onda}: janela inválida "
                        f"({label_min} > {label_max}) — "
                        f"verifique ondas vs. período disponível."
                    )
                else:
                    print(
                        f"   ✓ {nome_onda}: {prog_onda} PROG, "
                        f"{rob_onda} ROB | "
                        f"janela: {label_min} a {label_max}"
                    )

                projetos_modelo.append(Projeto(
                    nome_onda,
                    prog_onda,
                    rob_onda,
                    config.duracao_curso,
                    inicio_min_onda,
                    inicio_max_onda,
                    config.mes_termino_idx,
                    config.turmas_min_por_mes,
                    config.nome,
                    onda_idx
                ))

                # Avançar início mínimo para a próxima onda
                inicio_min_onda = _avancar_inicio_min_pos_onda(
                    inicio_min_onda,
                    config.duracao_curso,
                    meses_ferias,
                    len(meses)
                )

    print("\n" + "=" * 80)
    return projetos_modelo


# =============================================================================
# RENUMERAÇÃO — CORRIGIDA (sort por string)
# =============================================================================

def renumerar_instrutores_ativos(
    atribuicoes: List[Dict]
) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Renumera apenas os instrutores que receberam turmas
    e retorna a contagem por habilidade.
    """
    print("\n--- Renumerando Instrutores Ativos ---")
    instrutores_usados = sorted(
        list(set(atr['instrutor'] for atr in atribuicoes)),
        key=lambda i: (i.habilidade, i.id)    # ← sort por string
    )
    mapeamento       = {}
    contador_por_hab = defaultdict(int)

    for inst_antigo in instrutores_usados:
        hab    = inst_antigo.habilidade
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
            'turma':     atr['turma'],
            'instrutor': mapeamento[atr['instrutor'].id]
        }
        for atr in atribuicoes
    ]
    return atribuicoes_renumeradas, dict(contador_por_hab)


def analisar_distribuicao_instrutores_por_projeto(
    atribuicoes: List[Dict]
) -> Dict[str, Dict[str, int]]:
    """
    Conta instrutores únicos por projeto e habilidade.
    """
    instrutores_vistos = defaultdict(lambda: defaultdict(set))
    for atr in atribuicoes:
        projeto_base = atr['turma'].projeto.split('_Onda')[0]
        inst         = atr['instrutor']
        instrutores_vistos[projeto_base][inst.habilidade].add(inst.id)

    return {
        proj: {
            'PROG':     len(sets.get('PROG',     set())),
            'ROBOTICA': len(sets.get('ROBOTICA', set()))
        }
        for proj, sets in instrutores_vistos.items()
    }


# =============================================================================
# FLUXO DE CAIXA — INALTERADO
# =============================================================================

def calcular_fluxo_caixa_detalhado(
    atribuicoes: List[Dict],
    meses: List[str],
    meses_ferias_idx: List[int],
    parametros_financeiros: ParametrosFinanceiros,
    projeto_filtro: Optional[str] = None
) -> pd.DataFrame:
    """Calcula o fluxo de caixa detalhado."""
    num_meses      = len(meses)
    custos_mensais = np.zeros(num_meses)

    if not parametros_financeiros or \
            not parametros_financeiros.itens_custo:
        return pd.DataFrame()

    instrutores_ativos_no_mes = {m: set() for m in range(num_meses)}

    for atr in atribuicoes:
        t = atr['turma']
        nome_proj = t.projeto.split('_Onda')[0]
        if projeto_filtro and nome_proj != projeto_filtro:
            continue
        for m in calcular_meses_ativos(
            t.mes_inicio, t.duracao, meses_ferias_idx, num_meses
        ):
            instrutores_ativos_no_mes[m].add(atr['instrutor'].id)

    for item in parametros_financeiros.itens_custo:
        if item.tipo == 'PERMANENTE':
            if projeto_filtro:
                if item.projeto == projeto_filtro:
                    custos_mensais += item.valor
            else:
                custos_mensais += item.valor

        elif item.tipo == 'INSTRUTOR':
            aplica = (
                item.projeto is None
                or (projeto_filtro and item.projeto == projeto_filtro)
                or (not projeto_filtro and item.projeto is not None)
            )
            if not aplica:
                continue

            if projeto_filtro:
                if item.projeto is None or item.projeto == projeto_filtro:
                    for m in range(num_meses):
                        custos_mensais[m] += (
                            len(instrutores_ativos_no_mes[m]) * item.valor
                        )
            else:
                if item.projeto is None:
                    for m in range(num_meses):
                        custos_mensais[m] += (
                            len(instrutores_ativos_no_mes[m]) * item.valor
                        )
                else:
                    ativos_proj = {m: set() for m in range(num_meses)}
                    for atr in atribuicoes:
                        pn = atr['turma'].projeto.split('_Onda')[0]
                        if pn == item.projeto:
                            for m in calcular_meses_ativos(
                                atr['turma'].mes_inicio,
                                atr['turma'].duracao,
                                meses_ferias_idx, num_meses
                            ):
                                ativos_proj[m].add(atr['instrutor'].id)
                    for m in range(num_meses):
                        custos_mensais[m] += (
                            len(ativos_proj[m]) * item.valor
                        )

    for atr in atribuicoes:
        t      = atr['turma']
        nome_p = t.projeto.split('_Onda')[0]
        if projeto_filtro and nome_p != projeto_filtro:
            continue

        ma = calcular_meses_ativos(
            t.mes_inicio, t.duracao, meses_ferias_idx, num_meses
        )
        if not ma:
            continue

        m_ini = ma[0]
        m_fim = ma[-1]

        for item in parametros_financeiros.itens_custo:
            if item.projeto is not None and item.projeto != nome_p:
                continue
            if item.tipo == 'INICIAL' and m_ini < num_meses:
                custos_mensais[m_ini] += item.valor
            elif item.tipo == 'ENCERRAMENTO' and m_fim < num_meses:
                custos_mensais[m_fim] += item.valor
            elif item.tipo == 'EXECUCAO':
                for m in range(m_ini, min(m_fim + 1, num_meses)):
                    custos_mensais[m] += item.valor

    dados     = []
    acumulado = 0.0
    for idx, mes in enumerate(meses):
        v = custos_mensais[idx]
        acumulado += v
        dados.append({
            'Mês':             mes,
            'Custo Mensal':    v,
            'Custo Acumulado': acumulado
        })
    return pd.DataFrame(dados)


# =============================================================================
# EVOLUÇÃO DE INSTRUTORES — INALTERADA
# =============================================================================

def calcular_evolucao_instrutores(
    atribuicoes: List[Dict],
    meses: List[str],
    meses_ferias_idx: List[int]
) -> pd.DataFrame:
    """
    Quantidade de instrutores únicos ativos por mês, por tipologia.
    """
    num_meses          = len(meses)
    instrutores_ativos = {m: defaultdict(set) for m in range(num_meses)}

    for atr in atribuicoes:
        t = atr['turma']
        i = atr['instrutor']
        for m in calcular_meses_ativos(
            t.mes_inicio, t.duracao, meses_ferias_idx, num_meses
        ):
            instrutores_ativos[m][i.habilidade].add(i.id)

    dados = []
    for m_idx, mes_nome in enumerate(meses):
        qp = len(instrutores_ativos[m_idx].get('PROG',     set()))
        qr = len(instrutores_ativos[m_idx].get('ROBOTICA', set()))
        dados.append({
            'Mes':              mes_nome,
            'Instrutores_PROG': qp,
            'Instrutores_ROB':  qr,
            'Total':            qp + qr
        })
    return pd.DataFrame(dados)


# =============================================================================
# LOWER BOUNDS — INALTERADA
# =============================================================================

def calcular_lower_bounds(
    projetos: List[Projeto],
    meses: List[str],
    meses_ferias_idx: List[int],
    capacidade: int
) -> Dict[str, Dict[str, int]]:
    """
    Calcula lower bounds automáticos por habilidade/projeto pai.
    Retorna: {projeto_pai: {'PROG': lb, 'ROBOTICA': lb}}
    """
    num_meses        = len(meses)
    projetos_pai_set = list({p.projeto_pai for p in projetos})
    resultado        = {}

    print("\n  Lower Bounds por projeto/habilidade:")

    for pai in projetos_pai_set:
        ondas_pai = [p for p in projetos if p.projeto_pai == pai]

        for hab in ['PROG', 'ROBOTICA']:
            total_hab = sum(
                (p.prog if hab == 'PROG' else p.rob) for p in ondas_pai
            )
            if total_hab == 0:
                resultado.setdefault(pai, {})[hab] = 0
                continue

            demanda_por_mes = defaultdict(int)
            for p in ondas_pai:
                qtd = p.prog if hab == 'PROG' else p.rob
                if qtd == 0:
                    continue
                for m in calcular_meses_ativos(
                    p.inicio_min, p.duracao, meses_ferias_idx, num_meses
                ):
                    demanda_por_mes[m] += qtd

            pico = (
                max(demanda_por_mes.values())
                if demanda_por_mes else total_hab
            )
            lb1 = math.ceil(pico / capacidade)

            meses_letivos_proj = sum(
                1 for m in range(num_meses)
                if m not in meses_ferias_idx
                and any(p.inicio_min <= m <= p.mes_fim_projeto
                        for p in ondas_pai)
            )
            cap_total = capacidade * meses_letivos_proj
            lb2 = math.ceil(total_hab / cap_total) if cap_total > 0 else 1
            lb3 = 1

            lb_final = max(lb1, lb2, lb3)
            resultado.setdefault(pai, {})[hab] = lb_final

            print(
                f"    [{pai}][{hab}]: "
                f"LB1={lb1} (pico={pico}), "
                f"LB2={lb2} (letivos={meses_letivos_proj}), "
                f"→ LB_final={lb_final}"
            )

    return resultado