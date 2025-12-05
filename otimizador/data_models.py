from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

# Estruturas de dados para a lógica do otimizador
Projeto = namedtuple('Projeto', [
    'nome', 'prog', 'rob', 'duracao',
    'inicio_min', 'inicio_max', 'mes_fim_projeto'
])

Instrutor = namedtuple('Instrutor', [
    'id', 'habilidade', 'capacidade', 'laboratorio_id'
])

Turma = namedtuple('Turma', [
    'id', 'projeto', 'habilidade', 'mes_inicio', 'duracao'
])


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

    # Campos calculados
    mes_inicio_idx: int = field(default=None, init=False)
    mes_termino_idx: int = field(default=None, init=False)

    def __post_init__(self):
        """Valida os dados após inicialização"""
        self._validar_dados()

    def _validar_dados(self):
        """Valida todos os campos da configuração."""
        if not self.nome or not isinstance(self.nome, str):
            raise ValueError(f"Nome do projeto inválido: {self.nome}")

        try:
            dt_inicio = datetime.strptime(self.data_inicio, "%d/%m/%Y")
            dt_termino = datetime.strptime(self.data_termino, "%d/%m/%Y")
        except ValueError as e:
            raise ValueError(f"Formato de data inválido para {self.nome}. Use DD/MM/YYYY. Erro: {e}")

        if dt_termino <= dt_inicio:
            raise ValueError(
                f"Data de término ({self.data_termino}) deve ser posterior à de início ({self.data_inicio}) para {self.nome}")

        if not isinstance(self.num_turmas, int) or self.num_turmas <= 0:
            raise ValueError(f"Número de turmas inválido para {self.nome}: {self.num_turmas}")

        if not isinstance(self.percentual_prog, (int, float)) or not (0 <= self.percentual_prog <= 100):
            raise ValueError(f"Percentual de programação para '{self.nome}' deve estar entre 0 e 100.")

    @property
    def percentual_rob(self) -> float:
        """Calcula percentual de Robótica automaticamente"""
        return 100.0 - self.percentual_prog


@dataclass
class ParametrosOtimizacao:
    """
    Parâmetros globais para otimização.
    """
    capacidade_max_instrutor: int = 8
    spread_maximo: int = 16
    meses_ferias: List[str] = field(default_factory=lambda: ['Jul/26', 'Dez/26'])
    timeout_segundos: int = 180

    # <<< ALTERAÇÃO: Novos parâmetros de otimização >>>
    peso_instrutores: int = 10000
    peso_spread: int = 1
    pico_maximo_turmas: int = 60

    def __post_init__(self):
        """Valida os parâmetros após inicialização"""
        self._validar_parametros()

    def _validar_parametros(self):
        """Valida todos os parâmetros."""
        if not isinstance(self.capacidade_max_instrutor, int) or not (1 <= self.capacidade_max_instrutor <= 20):
            raise ValueError(f"Capacidade deve estar entre 1 e 20. Recebido: {self.capacidade_max_instrutor}")

        if not isinstance(self.spread_maximo, int) or not (0 <= self.spread_maximo <= 50):
            raise ValueError(f"Spread deve estar entre 0 e 50. Recebido: {self.spread_maximo}")

        if not isinstance(self.timeout_segundos, int) or not (10 <= self.timeout_segundos <= 3600):
            raise ValueError(f"Timeout deve estar entre 10 e 3600 segundos. Recebido: {self.timeout_segundos}")

        # <<< ALTERAÇÃO: Validação dos novos parâmetros >>>
        if not isinstance(self.peso_instrutores, int) or not (1 <= self.peso_instrutores <= 100000):
            raise ValueError(f"Peso instrutores deve estar entre 1 e 100000. Recebido: {self.peso_instrutores}")

        if not isinstance(self.peso_spread, int) or not (0 <= self.peso_spread <= 10000):
            raise ValueError(f"Peso spread deve estar entre 0 e 10000. Recebido: {self.peso_spread}")

        if not isinstance(self.pico_maximo_turmas, int) or not (1 <= self.pico_maximo_turmas <= 500):
            raise ValueError(f"Pico máximo deve estar entre 1 e 500. Recebido: {self.pico_maximo_turmas}")