import json
import os
import sys  # Adicionado para corrigir o erro de referência
from pathlib import Path
from datetime import datetime
from typing import Tuple, List, Optional
from ..data_models import ParametrosOtimizacao, Projeto, ParametrosFinanceiros, ItemCusto


def carregar_configuracao(caminho: str) -> Tuple[ParametrosOtimizacao, List[Projeto], Optional[ParametrosFinanceiros]]:
    """Carrega os parâmetros e projetos do arquivo JSON."""
    with open(caminho, 'r', encoding='utf-8') as f:
        data = json.load(f)

    p_data = data['parametros']

    # Mapeamento garantindo que o JSON sobrescreve os defaults do data_models
    parametros = ParametrosOtimizacao(
        capacidade_max_instrutor=p_data.get('capacidade_max_instrutor', 6),
        spread_maximo=p_data.get('spread_maximo', 10),
        meses_ferias=p_data.get('meses_ferias', []),
        meses_ferias_idx=p_data.get('meses_ferias_idx', []),
        timeout_segundos=p_data.get('timeout_segundos', 180),
        peso_instrutores=p_data.get('peso_instrutores', 1000),
        peso_spread=p_data.get('peso_spread', 10),
        pico_maximo_turmas=p_data.get('pico_maximo_turmas', 300),
        peso_penalidade_alvo=p_data.get('peso_penalidade_alvo', 100),
        peso_monotonia_projeto=p_data.get('peso_monotonia_projeto', 50),
        presenca_minima_projeto=p_data.get('presenca_minima_projeto', 2)
    )

    projetos = []
    for p in data['projetos']:
        projetos.append(Projeto(
            nome=p['nome'],
            data_inicio=p['data_inicio'],
            data_termino=p['data_termino'],
            num_turmas=p['num_turmas'],
            duracao_curso=p['duracao_curso'],
            ondas=p['ondas'],
            percentual_prog=p.get('percentual_prog', 70.0),
            turmas_min_por_mes=p.get('turmas_min_por_mes', 10),
            mes_inicio_idx=p.get('mes_inicio_idx', 0),
            mes_termino_idx=p.get('mes_termino_idx', 0),
            habilidade=p.get('habilidade', "PROG")
        ))

    financeiro = None
    if data.get('financeiro'):
        itens = [ItemCusto(**i) for i in data['financeiro']['itens_custo']]
        financeiro = ParametrosFinanceiros(
            itens_custo=itens,
            moeda=data['financeiro'].get('moeda', 'BRL')
        )

    return parametros, projetos, financeiro


def salvar_configuracao(parametros: ParametrosOtimizacao, projetos: List[Projeto],
                        financeiro: ParametrosFinanceiros = None):
    """Salva a configuração atual em um novo arquivo JSON."""
    config_dir = Path("configuracoes_otimizacao")
    config_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%H%M%S")
    nome_arquivo = f"config_V5_{timestamp}.json"
    caminho = config_dir / nome_arquivo

    data = {
        "parametros": parametros._asdict(),
        "projetos": [p._asdict() for p in projetos],
        "financeiro": {
            "itens_custo": [i._asdict() for i in financeiro.itens_custo],
            "moeda": financeiro.moeda
        } if financeiro else None
    }

    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return str(caminho)


def menu_gerenciar_configuracoes() -> Tuple[
    Optional[ParametrosOtimizacao], Optional[List[Projeto]], Optional[ParametrosFinanceiros]]:
    """Exibe menu para seleção de arquivos de configuração existentes."""
    config_dir = Path("configuracoes_otimizacao")
    config_dir.mkdir(exist_ok=True)

    # Ordena por data de modificação (mais recentes primeiro)
    arquivos = sorted(list(config_dir.glob("*.json")), key=os.path.getmtime, reverse=True)

    if not arquivos:
        return None, None, None

    print("\n" + "=" * 40)
    print("  SELECIONE UMA CONFIGURAÇÃO (JSON)")
    print("=" * 40)
    for i, arq in enumerate(arquivos):
        print(f" [{i + 1}] {arq.name}")

    print(" [N] Criar nova configuração manual")
    print(" [C] Cancelar e sair")

    escolha = input("\nOpção: ").strip().upper()

    if escolha == 'N':
        return None, None, None
    if escolha == 'C':
        sys.exit(0)  # Agora a referência 'sys' está resolvida

    try:
        idx = int(escolha) - 1
        if 0 <= idx < len(arquivos):
            return carregar_configuracao(str(arquivos[idx]))
    except ValueError:
        pass

    print("⚠️ Opção inválida. Iniciando modo manual.")
    return None, None, None