import os


def verificar():
    # Nomes que não devem mais ser usados no código (exceto no data_models como alias)
    proibido = ["ConfiguracaoProjeto"]

    # Caminho do arquivo de modelos
    data_models_path = os.path.join("otimizador", "data_models.py")

    print("=" * 50)
    print("VERIFICADOR DE INTEGRIDADE V5.0")
    print("=" * 50)

    # 1. Validar se as classes essenciais existem no data_models
    if os.path.exists(data_models_path):
        with open(data_models_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            classes_obrigatorias = ["class Instrutor", "class Projeto", "class Turma"]
            for cls in classes_obrigatorias:
                if cls in content:
                    print(f"✅ {cls} encontrado.")
                else:
                    print(f"❌ ERRO: {cls} NÃO encontrado no data_models.py")
    else:
        print(f"⚠️ AVISO: {data_models_path} não encontrado para verificação.")

    print("\n--- Iniciando varredura de arquivos ---")

    # Pastas para ignorar (evita erros de permissão e arquivos binários)
    pastas_ignoradas = [".venv", "venv", "__pycache__", ".git", ".idea", "resultados_otimizacao"]

    for root, dirs, files in os.walk("."):
        # Filtra as pastas ignoradas
        dirs[:] = [d for d in dirs if d not in pastas_ignoradas]

        for file in files:
            # Analisa apenas arquivos Python, ignorando o próprio script e o data_models
            if file.endswith(".py") and file not in ["data_models.py", "integridade.py", "verificar_integridade.py"]:
                path = os.path.join(root, file)
                try:
                    # 'errors=ignore' evita o crash de UnicodeDecodeError
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        c = f.read()
                        for p in proibido:
                            if p in c:
                                print(f"⚠️ AVISO: '{p}' ainda usado em: {path}")
                except Exception as e:
                    print(f"Critico: erro ao ler {path}: {e}")

    print("\n✅ Verificação de integridade concluída.")


if __name__ == "__main__":
    verificar()