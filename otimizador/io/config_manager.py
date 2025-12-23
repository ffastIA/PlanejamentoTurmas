import json
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional, Dict

# Import relativo para acessar os modelos de dados
from ..data_models import ParametrosOtimizacao, ConfiguracaoProjeto, ParametrosFinanceiros

CONFIGS_DIR = Path("configuracoes_otimizacao")


def inicializar_diretorio_configs():
    """Cria diretório de configurações se não existir"""
    CONFIGS_DIR.mkdir(exist_ok=True)


def salvar_configuracao(parametros: ParametrosOtimizacao,
                        projetos: List[ConfiguracaoProjeto],
                        financeiro: Optional[ParametrosFinanceiros] = None,
                        nome_config: str = None) -> bool:
    """Salva configuração completa em arquivo JSON."""
    try:
        inicializar_diretorio_configs()
        if not nome_config:
            sugestao = datetime.now().strftime("config_%Y%m%d_%H%M%S")
            nome_config_input = input(f"Nome para esta configuração [padrão: {sugestao}]: ").strip()
            nome_config = nome_config_input or sugestao
            nome_config = "".join(c for c in nome_config if c.isalnum() or c in ('_', '-'))

        config_data = {
            "metadata": {"nome": nome_config, "data_criacao": datetime.now().isoformat(), "versao": "2.2"},
            "parametros": parametros.__dict__,
            "projetos": [p.__dict__ for p in projetos]
        }

        if financeiro:
            config_data["financeiro"] = financeiro.__dict__

        arquivo = CONFIGS_DIR / f"{nome_config}.json"
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        print(f"\n[✓] Configuração salva com sucesso: {arquivo}")
        return True
    except Exception as e:
        print(f"\n[ERRO] Falha ao salvar configuração: {e}")
        return False


def listar_configuracoes_salvas() -> List[Path]:
    """Lista todas as configurações salvas."""
    inicializar_diretorio_configs()
    return sorted(CONFIGS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)


def exibir_preview_configuracao(arquivo: Path) -> Optional[Dict]:
    """Exibe preview de uma configuração."""
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        metadata = config_data.get("metadata", {})
        parametros = config_data.get("parametros", {})
        financeiro = config_data.get("financeiro", {})

        print(f"\n   Nome: {metadata.get('nome', 'N/A')}")
        print(f"   Criado em: {metadata.get('data_criacao', 'N/A')[:19]}")
        print(f"   Projetos: {len(config_data.get('projetos', []))}")
        print(
            f"   Capacidade: {parametros.get('capacidade_max_instrutor', 'N/A')} | Spread: {parametros.get('spread_maximo', 'N/A')}")
        if financeiro:
            print(f"   Financeiro: R$ {financeiro.get('custo_mensal_instrutor', 0):.2f}/mês")

        return config_data
    except Exception as e:
        print(f"   [ERRO] Não foi possível ler: {e}")
        return None


def carregar_configuracao(arquivo: Optional[Path] = None) -> Tuple[
    Optional[ParametrosOtimizacao], Optional[List[ConfiguracaoProjeto]], Optional[ParametrosFinanceiros]]:
    """Carrega configuração de arquivo JSON."""
    try:
        if arquivo is None:
            configs = listar_configuracoes_salvas()
            if not configs:
                print("\n[!] Nenhuma configuração salva encontrada.")
                return None, None, None

            print("\n" + "=" * 80 + "\nCONFIGURAÇÕES SALVAS\n" + "=" * 80)
            for idx, config_path in enumerate(configs, 1):
                print(f"\n{idx}. {config_path.stem}")
                exibir_preview_configuracao(config_path)

            while True:
                escolha = input(f"\nEscolha uma configuração [1-{len(configs)}] ou 'C' para cancelar: ").strip()
                if escolha.upper() == 'C': return None, None, None
                try:
                    idx = int(escolha) - 1
                    if 0 <= idx < len(configs):
                        arquivo = configs[idx]
                        break
                except ValueError:
                    print("[!] Digite um número válido.")

        with open(arquivo, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        parametros = ParametrosOtimizacao(**config_data.get("parametros", {}))

        # CORREÇÃO: Filtra campos internos que não devem ser passados para o __init__
        projetos = []
        campos_ignorados = {'mes_inicio_idx', 'mes_termino_idx'}
        for p_data in config_data.get("projetos", []):
            dados_limpos = {k: v for k, v in p_data.items() if k not in campos_ignorados}
            projetos.append(ConfiguracaoProjeto(**dados_limpos))

        financeiro_data = config_data.get("financeiro")
        financeiro = ParametrosFinanceiros(**financeiro_data) if financeiro_data else None

        print(f"\n[✓] Configuração carregada com sucesso: {arquivo.stem}")
        return parametros, projetos, financeiro
    except Exception as e:
        print(f"\n[ERRO] Falha ao carregar configuração: {e}")
        return None, None, None


def deletar_configuracao() -> bool:
    """Deleta uma configuração salva."""
    print("[INFO] Deleção de configurações ainda não implementada.")
    return False


def menu_gerenciar_configuracoes() -> Tuple[
    Optional[ParametrosOtimizacao], Optional[List[ConfiguracaoProjeto]], Optional[ParametrosFinanceiros]]:
    """Menu principal para gerenciar configurações."""
    print("\n" + "=" * 80 + "\nGERENCIAMENTO DE CONFIGURAÇÕES\n" + "=" * 80)
    configs = listar_configuracoes_salvas()
    print(f"Configurações salvas: {len(configs)}\n")
    print("Opções:\n  [1] Nova configuração (padrão ou customizada)")
    if configs:
        print("  [2] Carregar configuração salva\n  [3] Deletar configuração salva")
    print("  [S] Sair")

    while True:
        escolha = input("\nEscolha uma opção: ").strip().upper()
        if escolha == 'S' or escolha == 'SAIR':
            raise KeyboardInterrupt()
        elif escolha in ('', '1'):
            return None, None, None
        elif escolha == '2' and configs:
            params, projs, fin = carregar_configuracao()
            if params and projs: return params, projs, fin
        elif escolha == '3' and configs:
            deletar_configuracao()
            return menu_gerenciar_configuracoes()
        else:
            print("[!] Opção inválida.")