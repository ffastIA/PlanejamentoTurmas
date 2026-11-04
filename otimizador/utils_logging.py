"""
Sistema de logging para capturar todas as saídas do CLI
"""

import sys
import logging
from pathlib import Path
from datetime import datetime


class DualStreamHandler(logging.StreamHandler):
    """Handler que escreve simultaneamente em arquivo e console"""

    def __init__(self, log_file):
        super().__init__()
        self.log_file = log_file
        self.console_stream = sys.stdout

    def emit(self, record):
        try:
            msg = self.format(record)
        except Exception:
            return

        # Escrever no console, com fallback seguro para caracteres não
        # suportados pelo codec do console (ex.: emojis no cp1252 do Windows).
        # Nunca delegar para handleError/sys.stderr aqui: sys.stderr é
        # redirecionado para este mesmo logger, o que causaria recursão infinita.
        try:
            self.console_stream.write(msg + '\n')
            self.console_stream.flush()
        except UnicodeEncodeError:
            encoding = getattr(self.console_stream, 'encoding', None) or 'utf-8'
            safe_msg = (msg + '\n').encode(encoding, errors='replace').decode(encoding, errors='replace')
            try:
                self.console_stream.write(safe_msg)
                self.console_stream.flush()
            except Exception:
                pass
        except Exception:
            pass

        # Escrever no arquivo (sempre UTF-8)
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except Exception:
            pass


def configurar_logging(nome_simulacao: str = None) -> str:
    """
    Configura o sistema de logging para capturar todas as saídas

    Args:
        nome_simulacao: Nome da simulação (opcional)

    Returns:
        Caminho do arquivo de log
    """

    # Criar diretório de logs
    log_dir = Path("resultados_otimizacao/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Gerar nome do arquivo de log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if nome_simulacao:
        log_file = log_dir / f"log_{nome_simulacao}_{timestamp}.txt"
    else:
        log_file = log_dir / f"log_{timestamp}.txt"

    # Configurar logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Remover handlers existentes
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Criar formato
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Adicionar handler dual (console + arquivo)
    handler = DualStreamHandler(str(log_file))
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Redirecionar print para logging
    class PrintToLogger:
        def __init__(self, logger, level):
            self.logger = logger
            self.level = level
            self.linebuf = ''

        def write(self, buf):
            for line in buf.rstrip().splitlines():
                self.logger.log(self.level, line)

        def flush(self):
            pass

    sys.stdout = PrintToLogger(logger, logging.INFO)
    sys.stderr = PrintToLogger(logger, logging.ERROR)

    # Log inicial
    logger.info("=" * 80)
    logger.info("SISTEMA DE OTIMIZAÇÃO DE ALOCAÇÃO DE INSTRUTORES")
    logger.info("Versão 3.8 (Com Logging e Gráficos Melhorados)")
    logger.info("=" * 80)
    logger.info(f"Arquivo de log: {log_file}")

    return str(log_file)