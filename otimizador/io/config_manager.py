import json
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional, Dict

from ..data_models import ParametrosOtimizacao, ConfiguracaoProjeto, ParametrosFinanceiros, ItemCusto

CONFIGS_DIR = Path("configuracoes_otimizacao")


def inicializar_diretorio_configs():
    CONFIGS_DIR.mkdir(exist_ok=True)


def salvar_configuracao(parametros: ParametrosOtimizacao, projetos: List[ConfiguracaoProjeto],
                        financeiro: Optional[ParametrosFinanceiros] = None, nome_config: str = None) -> bool:
    try:
        inicializar_diretorio_configs()
        if not nome_config:
            sugestao = datetime.now().strftime("config_%Y%m%d_%H%M%S")
            nome_config = (input(f"Nome [{sugestao}]: ").strip() or sugestao)
            nome_config = "".join(c for c in nome_config if c.isalnum() or c in ('_', '-'))

        config_data = {
            "metadata": {"nome": nome_config, "data_criacao": datetime.now().isoformat(), "versao": "3.1"},
            "parametros": parametros.__dict__,
            "projetos": [p.__dict__ for p in projetos]
        }

        # Serialização manual dos itens de custo para garantir formato correto
        if financeiro:
            fin_dict = financeiro.__dict__.copy()
            fin_dict['itens_custo'] = [item.__dict__ for item in financeiro.itens_custo]
            config_data["financeiro"] = fin_dict

        arquivo = CONFIGS_DIR / f"{nome_config}.json"
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        print(f"\n[✓] Salvo: {arquivo}")
        return True
    except Exception as e:
        print(f"\n[ERRO] Salvar: {e}");
        return False


def listar_configuracoes_salvas() -> List[Path]:
    inicializar_diretorio_configs()
    return sorted(CONFIGS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)


def exibir_preview_configuracao(arquivo: Path):
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            data = json.load(f)
        meta = data.get("metadata", {})
        fin = data.get("financeiro", {})
        itens = fin.get("itens_custo", [])
        print(f"\n   Nome: {meta.get('nome')} | Criado: {meta.get('data_criacao')[:19]}")
        print(f"   Projetos: {len(data.get('projetos', []))} | Custos Configurados: {len(itens)}")
    except:
        pass


def carregar_configuracao(arquivo: Optional[Path] = None) -> Tuple[
    Optional[ParametrosOtimizacao], Optional[List[ConfiguracaoProjeto]], Optional[ParametrosFinanceiros]]:
    try:
        if arquivo is None:
            configs = listar_configuracoes_salvas()
            if not configs: print("\n[!] Nenhuma config."); return None, None, None
            print("\n--- CONFIGURAÇÕES SALVAS ---")
            for i, c in enumerate(configs, 1): print(f"{i}. {c.stem}"); exibir_preview_configuracao(c)
            escolha = input("\nEscolha [N] ou C cancelar: ").strip()
            if escolha.upper() == 'C': return None, None, None
            arquivo = configs[int(escolha) - 1]

        with open(arquivo, 'r', encoding='utf-8') as f:
            data = json.load(f)

        params = ParametrosOtimizacao(**data.get("parametros", {}))

        projs = []
        ignore = {'mes_inicio_idx', 'mes_termino_idx'}
        for p in data.get("projetos", []):
            projs.append(ConfiguracaoProjeto(**{k: v for k, v in p.items() if k not in ignore}))

        fin_data = data.get("financeiro")
        fin = None
        if fin_data:
            itens_raw = fin_data.pop('itens_custo', [])
            fin = ParametrosFinanceiros(**fin_data)
            # Reconstrói os objetos ItemCusto corretamente
            fin.itens_custo = [ItemCusto(**item) for item in itens_raw]

        print(f"\n[✓] Carregado: {arquivo.stem}")
        return params, projs, fin
    except Exception as e:
        print(f"\n[ERRO] Carregar: {e}");
        return None, None, None


def deletar_configuracao():
    print("Funcionalidade não implementada.")


def menu_gerenciar_configuracoes():
    print("\n" + "=" * 80 + "\nGERENCIAMENTO DE CONFIGURAÇÕES\n" + "=" * 80)
    configs = listar_configuracoes_salvas()
    print(f"Configurações salvas: {len(configs)}\n")

    # --- CORREÇÃO: As opções de print foram recolocadas aqui ---
    print("Opções:")
    print("  [1] Nova configuração (padrão ou customizada)")
    if configs:
        print("  [2] Carregar configuração salva")
        print("  [3] Deletar configuração salva")
    print("  [S] Sair")
    # -----------------------------------------------------------

    while True:
        opt = input("\nOpção: ").strip().upper()
        if opt == 'S': raise KeyboardInterrupt()
        if opt == '1': return None, None, None
        if opt == '2' and configs:
            res = carregar_configuracao()
            if res[0]: return res
        elif opt == '3' and configs:
            deletar_configuracao()
            return menu_gerenciar_configuracoes()
        else:
            print("[!] Opção inválida.")