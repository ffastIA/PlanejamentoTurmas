from typing import List, NamedTuple, Optional

class ParametrosOtimizacao(NamedTuple):
    capacidade_max_instrutor: int
    spread_maximo: int
    meses_ferias: List[str]
    meses_ferias_idx: List[int]
    timeout_segundos: int
    peso_instrutores: int
    peso_spread: int
    pico_maximo_turmas: int
    # NOVOS CAMPOS V5.0 (Monotonia e Penalidades)
    peso_penalidade_alvo: int = 100
    peso_monotonia_projeto: int = 50
    presenca_minima_projeto: int = 2

class Instrutor(NamedTuple):
    id: str
    habilidade: str
    capacidade: int

class Projeto(NamedTuple):
    nome: str
    data_inicio: str
    data_termino: str
    num_turmas: int
    duracao_curso: int
    ondas: int
    percentual_prog: float
    turmas_min_por_mes: int
    mes_inicio_idx: int
    mes_termino_idx: int
    habilidade: str = "PROG"

# Alias para compatibilidade com códigos que ainda buscam ConfiguracaoProjeto
ConfiguracaoProjeto = Projeto

class Turma(NamedTuple):
    id: int
    projeto: str
    mes_inicio: int
    duracao: int
    habilidade: str

class ItemCusto(NamedTuple):
    tipo: str
    descricao: str
    valor: float
    projeto: Optional[str] = None

class ParametrosFinanceiros(NamedTuple):
    itens_custo: List[ItemCusto]
    moeda: str = "BRL"