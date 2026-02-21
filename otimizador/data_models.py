from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

# =============================================================================
# ESTRUTURAS DO MODELO DE OTIMIZAÇÃO
# =============================================================================

# Projeto: representa uma onda de um projeto (PROG ou ROB separados em utils.py)
# NOVO CAMPO: 'habilidade' — identifica explicitamente se é PROG ou ROBOTICA
Projeto = namedtuple('Projeto', [
    'nome',           # str  — ex: "DD2_Onda1"
    'prog',           # int  — turmas PROG desta onda
    'rob',            # int  — turmas ROB desta onda
    'duracao',        # int  — duração em meses letivos
    'inicio_min',     # int  — índice mínimo de início
    'inicio_max',     # int  — índice máximo de início
    'mes_fim_projeto',# int  — índice do mês de término do projeto pai
    'min_turmas',     # int  — mínimo de turmas ativas por mês
    'projeto_pai',    # str  — nome do projeto original (sem sufixo _OndaX)
    'onda_idx'        # int  — índice da onda (0-based) dentro do projeto pai
])

Instrutor = namedtuple('Instrutor', [
    'id', 'habilidade', 'capacidade', 'laboratorio_id'
])

Turma = namedtuple('Turma', [
    'id', 'projeto', 'habilidade', 'mes_inicio', 'duracao'
])


# =============================================================================
# CONFIGURAÇÃO DE PROJETOS (entrada do usuário — inalterada)
# =============================================================================

@dataclass
class ConfiguracaoProjeto:
    """
    Configuração completa de um projeto educacional.
    """
    nome: str
    data_inicio: str
    data_termino: str
    num_turmas: int
    duracao_curso: int
    ondas: int = 1
    percentual_prog: float = 60.0
    turmas_min_por_mes: int = 1

    # Campos calculados — preenchidos por utils.converter_projetos_para_modelo()
    mes_inicio_idx: int = field(default=None, init=False)
    mes_termino_idx: int = field(default=None, init=False)

    def __post_init__(self):
        self._validar_dados()

    def _validar_dados(self):
        if not self.nome or not isinstance(self.nome, str):
            raise ValueError(f"Nome do projeto inválido: {self.nome}")

        try:
            dt_inicio = datetime.strptime(self.data_inicio, "%d/%m/%Y")
            dt_termino = datetime.strptime(self.data_termino, "%d/%m/%Y")
        except ValueError as e:
            raise ValueError(
                f"Formato de data inválido para {self.nome}. "
                f"Use DD/MM/YYYY. Erro: {e}"
            )

        if dt_termino <= dt_inicio:
            raise ValueError(
                f"Data de término ({self.data_termino}) deve ser posterior "
                f"à de início ({self.data_inicio}) para {self.nome}"
            )

        if not isinstance(self.num_turmas, int) or self.num_turmas <= 0:
            raise ValueError(
                f"Número de turmas inválido para {self.nome}: {self.num_turmas}"
            )

        if not isinstance(self.percentual_prog, (int, float)) or \
                not (0 <= self.percentual_prog <= 100):
            raise ValueError(
                f"Percentual de programação para '{self.nome}' "
                f"deve estar entre 0 e 100."
            )

    @property
    def percentual_rob(self) -> float:
        return 100.0 - self.percentual_prog


# =============================================================================
# PARÂMETROS GLOBAIS DE OTIMIZAÇÃO (inalterados)
# =============================================================================

@dataclass
class ParametrosOtimizacao:
    """
    Parâmetros globais para otimização.
    """
    capacidade_max_instrutor: int = 6
    spread_maximo: int = 4
    meses_ferias: List[str] = field(
        default_factory=lambda: ['Jul/26', 'Dez/26']
    )
    timeout_segundos: int = 180

    # Pesos — reutilizados no novo Stage 2
    # peso_instrutores: não mais usado como objetivo primário,
    #                   mantido por compatibilidade com main.py e pdf_generator
    peso_instrutores: int = 10000
    peso_spread: int = 1
    pico_maximo_turmas: int = 60

    def __post_init__(self):
        self._validar_parametros()

    def _validar_parametros(self):
        if not isinstance(self.capacidade_max_instrutor, int) or \
                not (1 <= self.capacidade_max_instrutor <= 20):
            raise ValueError("Capacidade deve estar entre 1 e 20.")
        if not isinstance(self.spread_maximo, int) or \
                not (0 <= self.spread_maximo <= 50):
            raise ValueError("Spread deve estar entre 0 e 50.")
        if not isinstance(self.timeout_segundos, int) or \
                not (10 <= self.timeout_segundos <= 3600):
            raise ValueError("Timeout deve estar entre 10 e 3600 segundos.")
        if not isinstance(self.peso_instrutores, int) or \
                not (1 <= self.peso_instrutores <= 100000):
            raise ValueError(
                "Peso instrutores deve estar entre 1 e 100000."
            )
        if not isinstance(self.peso_spread, int) or \
                not (0 <= self.peso_spread <= 10000):
            raise ValueError("Peso spread deve estar entre 0 e 10000.")
        if not isinstance(self.pico_maximo_turmas, int) or \
                not (1 <= self.pico_maximo_turmas <= 500):
            raise ValueError("Pico máximo deve estar entre 1 e 500.")


# =============================================================================
# PARÂMETROS FINANCEIROS (inalterados)
# =============================================================================

@dataclass
class ItemCusto:
    """Representa um item de custo individual."""
    tipo: str
    descricao: str
    valor: float
    projeto: Optional[str] = None


@dataclass
class ParametrosFinanceiros:
    """
    Parâmetros para o módulo financeiro (Lista de Custos).
    """
    itens_custo: List[ItemCusto] = field(default_factory=list)
    moeda: str = "BRL"

    def adicionar_custo(
        self,
        tipo: str,
        descricao: str,
        valor: float,
        projeto: Optional[str] = None
    ):
        self.itens_custo.append(ItemCusto(tipo, descricao, valor, projeto))