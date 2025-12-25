from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any
from collections import defaultdict
import pandas as pd
import numpy as np

# Import relativo para acessar os modelos de dados
from .data_models import Projeto, ConfiguracaoProjeto, ParametrosOtimizacao, Instrutor, ParametrosFinanceiros


def gerar_lista_meses(data_inicio: str, data_fim: str) -> List[str]:
    """Gera lista de meses entre duas datas."""
    try:
        dt_inicio = datetime.strptime(data_inicio, "%d/%m/%Y").replace(day=1)
        dt_fim = datetime.strptime(data_fim, "%d/%m/%Y").replace(day=1)
    except ValueError as e:
        raise ValueError(f"Formato de data inválido. Use DD/MM/YYYY. Erro: {e}")
    if dt_fim < dt_inicio:
        raise ValueError(f"Data final ({data_fim}) deve ser posterior à inicial ({data_inicio})")

    meses_nomes = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    lista_meses = []
    data_atual = dt_inicio
    while data_atual <= dt_fim:
        lista_meses.append(f"{meses_nomes[data_atual.month - 1]}/{str(data_atual.year)[2:]}")
        data_atual = data_atual + timedelta(days=32)
        data_atual = data_atual.replace(day=1)
    return lista_meses


def data_para_indice_mes(data: str, meses: List[str]) -> int:
    """Converte data para índice na lista de meses."""
    try:
        dt = datetime.strptime(data, "%d/%m/%Y")
        meses_map = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        mes_procurado = f"{meses_map[dt.month - 1]}/{str(dt.year)[2:]}"
        return meses.index(mes_procurado)
    except (ValueError, IndexError) as e:
        raise ValueError(f"Data {data} ({mes_procurado}) não está no período de análise. Erro: {e}")


def calcular_meses_ativos(mes_inicio: int,
                          duracao: int,
                          meses_ferias_idx: list,
                          num_meses_total: int) -> list:
    """
    Calcula os meses de calendário em que uma turma está ativa ACADEMICAMENTE (pulando férias).
    """
    meses_ativos = []
    meses_letivos_contados = 0
    mes_calendario_atual = mes_inicio

    while meses_letivos_contados < duracao and mes_calendario_atual < num_meses_total:
        if mes_calendario_atual not in meses_ferias_idx:
            meses_ativos.append(mes_calendario_atual)
            meses_letivos_contados += 1
        mes_calendario_atual += 1

    return meses_ativos


def calcular_janela_inicio(mes_inicio_projeto: int, mes_fim_projeto: int, duracao: int, meses_ferias: List[int],
                           num_meses: int, meses: List[str]) -> Tuple[int, int]:
    """Calcula a janela válida de início garantindo término dentro do prazo."""
    inicio_min, inicio_max = -1, -1
    for m_inicio in range(mes_inicio_projeto, min(mes_fim_projeto + 1, num_meses)):
        meses_ativos = calcular_meses_ativos(m_inicio, duracao, meses_ferias, num_meses)
        if len(meses_ativos) == duracao and max(meses_ativos) <= mes_fim_projeto:
            if inicio_min == -1: inicio_min = m_inicio
            inicio_max = m_inicio

    if inicio_min == -1:
        raise ValueError("Não há janela válida de início para um dos projetos. Verifique durações e prazos.")
    print(f"   Janela de início calculada: {meses[inicio_min]} a {meses[inicio_max]}")
    return inicio_min, inicio_max


def calcular_turmas_por_projeto(limite_total: int, percentual_prog: float) -> Tuple[int, int]:
    """Calcula número de turmas PROG e ROB baseado nos percentuais."""
    num_prog = round(limite_total * percentual_prog / 100)
    return num_prog, limite_total - num_prog


def converter_projetos_para_modelo(projetos_config: List[ConfiguracaoProjeto], meses: List[str],
                                   meses_ferias: List[int], parametros: ParametrosOtimizacao) -> List[Projeto]:
    """Converte configurações de projetos para estrutura do modelo."""
    print("\n" + "=" * 80 + "\nCONVERSÃO DE PROJETOS PARA MODELO\n" + "=" * 80)
    projetos_modelo = []
    for config in projetos_config:
        print(f"\nProcessando {config.nome} (PROG: {config.percentual_prog:.1f}% / ROB: {config.percentual_rob:.1f}%)")
        config.mes_inicio_idx = data_para_indice_mes(config.data_inicio, meses)
        config.mes_termino_idx = data_para_indice_mes(config.data_termino, meses)
        inicio_min, inicio_max = calcular_janela_inicio(config.mes_inicio_idx, config.mes_termino_idx,
                                                        config.duracao_curso, meses_ferias, len(meses), meses)

        prog_total, rob_total = calcular_turmas_por_projeto(config.num_turmas, config.percentual_prog)

        print(f"   Total: {config.num_turmas} turmas (PROG: {prog_total}, ROB: {rob_total}) | Ondas: {config.ondas}")

        if config.ondas == 1:
            projetos_modelo.append(
                Projeto(config.nome, prog_total, rob_total, config.duracao_curso, inicio_min, inicio_max,
                        config.mes_termino_idx))
        else:
            prog_por_onda, rob_por_onda = prog_total // config.ondas, rob_total // config.ondas
            for onda_idx in range(config.ondas):
                prog_onda = prog_total - (
                        prog_por_onda * (config.ondas - 1)) if onda_idx == config.ondas - 1 else prog_por_onda
                rob_onda = rob_total - (
                        rob_por_onda * (config.ondas - 1)) if onda_idx == config.ondas - 1 else rob_por_onda
                nome_onda = f"{config.nome}_Onda{onda_idx + 1}"
                projetos_modelo.append(
                    Projeto(nome_onda, prog_onda, rob_onda, config.duracao_curso, inicio_min, inicio_max,
                            config.mes_termino_idx))
                print(f"   - {nome_onda}: {prog_onda} PROG, {rob_onda} ROB")
    print("=" * 80)
    return projetos_modelo


def renumerar_instrutores_ativos(atribuicoes: List[Dict]) -> Tuple[List[Dict], Dict[str, int]]:
    """Renumera apenas os instrutores que receberam turmas e retorna a contagem por habilidade."""
    print("\n--- Renumerando Instrutores Ativos ---")
    instrutores_usados = sorted(list(set(atr['instrutor'] for atr in atribuicoes)),
                                key=lambda i: (i.habilidade, int(i.id.split('_')[1])))
    mapeamento, contador_por_hab = {}, defaultdict(int)

    for inst_antigo in instrutores_usados:
        hab = inst_antigo.habilidade
        contador_por_hab[hab] += 1
        prefixo = 'PROG' if hab == 'PROG' else 'ROB'
        novo_id = f'{prefixo}_{contador_por_hab[hab]}'
        mapeamento[inst_antigo.id] = Instrutor(novo_id, hab, inst_antigo.capacidade, inst_antigo.laboratorio_id)

    print("Contagem final de instrutores por habilidade:")
    for hab, count in sorted(contador_por_hab.items()): print(f"   • {hab}: {count} instrutores")

    atribuicoes_renumeradas = [{'turma': atr['turma'], 'instrutor': mapeamento[atr['instrutor'].id]} for atr in
                               atribuicoes]

    return atribuicoes_renumeradas, dict(contador_por_hab)


def analisar_distribuicao_instrutores_por_projeto(atribuicoes: List[Dict]) -> Dict[str, Dict[str, int]]:
    """Analisa as atribuições para contar quantos instrutores únicos por projeto."""
    instrutores_vistos = defaultdict(lambda: defaultdict(set))
    for atr in atribuicoes:
        projeto_base_nome = atr['turma'].projeto.split('_Onda')[0]
        instrutor = atr['instrutor']
        instrutores_vistos[projeto_base_nome][instrutor.habilidade].add(instrutor.id)

    contagem_final = {
        proj: {
            'PROG': len(hab_sets.get('PROG', set())),
            'ROBOTICA': len(hab_sets.get('ROBOTICA', set()))
        }
        for proj, hab_sets in instrutores_vistos.items()
    }
    return contagem_final


def calcular_fluxo_caixa_detalhado(atribuicoes: List[Dict],
                                   meses: List[str],
                                   meses_ferias_idx: List[int],
                                   parametros_financeiros: ParametrosFinanceiros) -> pd.DataFrame:
    """
    Calcula o fluxo de caixa detalhado baseado nos 4 tipos de custos.
    Retorna um DataFrame com o custo total mês a mês.
    """
    num_meses = len(meses)
    # Inicializa array de custos por mês
    custos_mensais = np.zeros(num_meses)

    # Se não houver custos configurados, retorna vazio
    if not parametros_financeiros or not parametros_financeiros.itens_custo:
        return pd.DataFrame()

    # 1. Processar Custos PERMANENTES (Independente de turmas)
    # Aplica-se a todos os meses da vigência do projeto (assumindo vigência = lista de meses gerada)
    for item in parametros_financeiros.itens_custo:
        if item.tipo == 'PERMANENTE':
            custos_mensais += item.valor

    # 2. Processar Custos Vinculados a Turmas (INICIAL, ENCERRAMENTO, EXECUCAO)
    for atr in atribuicoes:
        t = atr['turma']

        # Identificar meses academicamente ativos
        meses_academicos = calcular_meses_ativos(t.mes_inicio, t.duracao, meses_ferias_idx, num_meses)

        if not meses_academicos:
            continue

        mes_inicio_real = meses_academicos[0]
        mes_fim_real = meses_academicos[-1]  # Último mês de aula

        # Definição do período de EXECUÇÃO (Calendário corrido, inclui férias)
        # Vai do mês de início até o mês de término, inclusive
        periodo_execucao = range(mes_inicio_real, min(mes_fim_real + 1, num_meses))

        for item in parametros_financeiros.itens_custo:
            if item.tipo == 'INICIAL':
                # Aplica apenas no mês de início
                if mes_inicio_real < num_meses:
                    custos_mensais[mes_inicio_real] += item.valor

            elif item.tipo == 'ENCERRAMENTO':
                # Aplica apenas no mês de término
                if mes_fim_real < num_meses:
                    custos_mensais[mes_fim_real] += item.valor

            elif item.tipo == 'EXECUCAO':
                # Aplica em todos os meses do período de execução (incluindo férias)
                for m in periodo_execucao:
                    if m < num_meses:
                        custos_mensais[m] += item.valor

    # Montar DataFrame
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