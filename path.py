from pathlib import Path


def gerar_arvore(diretorio, prefixo=""):
    """
    Gera uma visualização em árvore de um diretório,
    ignorando arquivos/pastas ocultos (.git, etc) e pastas de ambiente/cache.
    """
    caminho = Path(diretorio)

    # 1. Definimos um set (O(1) para busca) com pastas de sistema/cache que queremos ignorar
    IGNORAR_NOMES = {
        '__pycache__', 'venv', 'env', 'node_modules', 'dist', 'build', '.pytest_cache'
    }

    # 2. Filtramos os itens ANTES de processar
    itens = [
        item for item in caminho.iterdir()
        if not item.name.startswith('.')  # Ignora TUDO que for oculto (ex: .git, .env, .vscode, .idea)
           and item.name not in IGNORAR_NOMES  # Ignora caches e ambientes virtuais
    ]

    # 3. Ordenar (pastas primeiro, depois arquivos alfabeticamente)
    itens.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

    total_itens = len(itens)

    for index, item in enumerate(itens):
        e_ultimo = (index == total_itens - 1)

        # Define os conectores visuais
        conector = "└── " if e_ultimo else "├── "

        print(f"{prefixo}{conector}{item.name}")

        # Se for diretório, entra recursivamente
        if item.is_dir():
            novo_prefixo = prefixo + ("    " if e_ultimo else "│   ")
            gerar_arvore(item, novo_prefixo)


# --- Como Executar ---
if __name__ == "__main__":
    print(f"📦 Estrutura do Projeto (Clean):")
    # Substitua '.' pelo caminho da pasta que deseja mapear
    gerar_arvore('.')