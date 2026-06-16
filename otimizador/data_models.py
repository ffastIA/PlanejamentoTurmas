from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

# =============================================================================
# ESTRUTURAS DO MODELO DE OTIMIZAÇÃO
# =============================================================================

Projeto = namedtuple('Projeto', [
    'nome',            # str  — ex: "DD2_Onda1"
    'prog',            # int  — turmas PROG desta onda
    'rob',             # int  — turmas ROB desta onda
    'duracao',         # int  — duração em meses letivos
    'inicio_min',      # int  — índice mínimo de início
    'inicio_max',      # int  — índice máximo de início
    'mes_fim_projeto', # int  — índice do mês de término do projeto pai
    'min_turmas',      # int  — mínimo de turmas ativas por mês
    'projeto_pai',     # str  — nome do projeto original (sem sufixo _OndaX)
    'onda_idx'         # int  — índice da onda (0-based) dentro do projeto pai
])

Instrutor = namedtuple('Instrutor', [
    'id', 'habilidade', 'capacidade', 'laboratorio_id'
])

Turma = namedtuple('Turma', [
    'id', 'projeto', 'habilidade', 'mes_inicio', 'duracao'
])


# =============================================================================
# CONFIGURAÇÃO DE PROJETOS
# =============================================================================

@dataclass
class ConfiguracaoProjeto:
    """Configuração completa de um projeto educacional."""
    nome: str
    data_inicio: str
    data_termino: str
    num_turmas: int
    duracao_curso: int
    ondas: int = 1
    percentual_prog: float = 60.0
    turmas_min_por_mes: int = 1

    mes_inicio_idx: int = field(default=None, init=False)
    mes_termino_idx: int = field(default=None, init=False)

    def __post_init__(self):
        self._validar_dados()

    def _validar_dados(self):
        if not self.nome or not isinstance(self.nome, str):
            raise ValueError(f"Nome do projeto inválido: {self.nome}")

        try:
            dt_inicio  = datetime.strptime(self.data_inicio,  "%d/%m/%Y")
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
                f"Número de turmas inválido para {self.nome}: "
                f"{self.num_turmas}"
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
# PARÂMETROS GLOBAIS DE OTIMIZAÇÃO
# =============================================================================

@dataclass
class ParametrosOtimizacao:
    """Parâmetros globais para otimização."""
    capacidade_max_instrutor: int   = 6
    spread_maximo: int              = 4
    meses_ferias: List[str]         = field(
        default_factory=lambda: ['Jul/26', 'Dez/26']
    )
    timeout_segundos: int           = 180
    peso_instrutores: int           = 10000
    peso_spread: int                = 1
    pico_maximo_turmas: int         = 60

    # ── NOVO v2.3 ─────────────────────────────────────────────────────────────
    # peso_monotonia: penaliza quedas na demanda mensal no Stage 1.
    # Soft constraint — não impede solução, apenas orienta o solver
    # a preferir cronogramas com picos crescentes.
    #
    # Calibração sugerida:
    #   0        → comportamento idêntico à v2.1 (monotonia desativada)
    #   1–100    → leve preferência por crescimento
    #   500      → preferência moderada (padrão)
    #   >10000   → monotonia dominante sobre alisamento (não recomendado)
    peso_monotonia: int             = 500

    # peso_spread_mensal: penaliza a diferença entre o mês mais carregado e
    # o menos carregado de cada instrutor ativo (spread intra-período).
    # Calibração sugerida:
    #   0        → distribuição intra-período desativada
    #   50–200   → preferência moderada por carga uniforme (padrão: 100)
    #   >1000    → uniformidade intra-período dominante
    peso_spread_mensal: int         = 100
    # ─────────────────────────────────────────────────────────────────────────

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
            raise ValueError(
                "Timeout deve estar entre 10 e 3600 segundos."
            )
        if not isinstance(self.peso_instrutores, int) or \
                not (1 <= self.peso_instrutores <= 100000):
            raise ValueError(
                "Peso instrutores deve estar entre 1 e 100000."
            )
        if not isinstance(self.peso_spread, int) or \
                not (0 <= self.peso_spread <= 10000):
            raise ValueError(
                "Peso spread deve estar entre 0 e 10000."
            )
        if not isinstance(self.pico_maximo_turmas, int) or \
                not (1 <= self.pico_maximo_turmas <= 500):
            raise ValueError(
                "Pico máximo deve estar entre 1 e 500."
            )
        if not isinstance(self.peso_monotonia, int) or \
                not (0 <= self.peso_monotonia <= 100000):
            raise ValueError(
                "Peso monotonia deve estar entre 0 e 100000."
            )
        if not isinstance(self.peso_spread_mensal, int) or \
                not (0 <= self.peso_spread_mensal <= 100000):
            raise ValueError(
                "Peso spread mensal deve estar entre 0 e 100000."
            )


# =============================================================================
# PARÂMETROS FINANCEIROS
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
    """Parâmetros para o módulo financeiro."""
    itens_custo: List[ItemCusto] = field(default_factory=list)
    moeda: str = "BRL"

    def adicionar_custo(
        self,
        tipo: str,
        descricao: str,
        valor: float,
        projeto: Optional[str] = None
    ):
        self.itens_custo.append(
            ItemCusto(tipo, descricao, valor, projeto)
        )