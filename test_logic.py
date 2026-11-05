# ARQUIVO: test_logic.py

def calcular_meses_ativos(mes_inicio: int,
                          duracao: int,
                          meses_ferias_idx: list,
                          num_meses_total: int) -> list:
    """
    Calcula os meses de calendário em que uma turma está ativa, pulando os meses de férias.
    """
    meses_ativos = []
    meses_letivos_contados = 0
    mes_calendario_atual = mes_inicio

    while meses_letivos_contados < duracao and mes_calendario_atual < num_meses_total:
        if mes_calendario_atual not in meses_ferias_idx:
            meses_ativos.append(mes_calendario_atual)
            meses_letivos_contados += 1

        mes_calendario_atual += 1

    return meses_ativos


# ================================================================
# Script de Teste
# ================================================================
if __name__ == "__main__":
    print("=" * 50)
    print("INICIANDO TESTE DE ISOLAMENTO DA LÓGICA DE FÉRIAS")
    print("=" * 50)

    # --- Cenário de Teste ---
    # Calendário de 12 meses (Janeiro=0 a Dezembro=11)
    num_meses_total = 12
    meses_calendario = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

    # Férias em Julho (índice 6) e Dezembro (índice 11)
    meses_ferias_idx = [6, 11]
    print(f"Calendário: {meses_calendario}")
    print(f"Meses de Férias (índices): {meses_ferias_idx} -> (Julho, Dezembro)\n")

    # --- Teste 1: O Caso Crítico ---
    print("--- Teste 1: Turma de 3 meses começando em Junho ---")
    mes_inicio_1 = 5  # Junho
    duracao_1 = 3

    resultado_1 = calcular_meses_ativos(mes_inicio_1, duracao_1, meses_ferias_idx, num_meses_total)

    print(f"Parâmetros: Início={mes_inicio_1} (Jun), Duração={duracao_1}")
    print(f"Resultado Obtido (índices): {resultado_1}")
    print(f"Resultado Obtido (meses): {[meses_calendario[i] for i in resultado_1]}")
    print("Resultado Esperado (meses): ['Jun', 'Ago', 'Set']")

    if resultado_1 == [5, 7, 8]:
        print("VEREDITO: SUCESSO! A lógica está correta.\n")
    else:
        print("VEREDITO: FALHA! A lógica está INCORRETA.\n")

    # --- Teste 2: Turma atravessando o segundo período de férias ---
    print("--- Teste 2: Turma de 2 meses começando em Novembro ---")
    mes_inicio_2 = 10  # Novembro
    duracao_2 = 2

    # (Simulando um calendário maior para este teste)
    num_meses_total_2 = 13
    meses_calendario_2 = meses_calendario + ['Jan_ano_seguinte']
    meses_ferias_idx_2 = [6, 11]

    resultado_2 = calcular_meses_ativos(mes_inicio_2, duracao_2, meses_ferias_idx_2, num_meses_total_2)

    print(f"Parâmetros: Início={mes_inicio_2} (Nov), Duração={duracao_2}")
    print(f"Resultado Obtido (índices): {resultado_2}")
    print(f"Resultado Obtido (meses): {[meses_calendario_2[i] for i in resultado_2]}")
    print("Resultado Esperado (meses): ['Nov', 'Jan_ano_seguinte']")

    if resultado_2 == [10, 12]:
        print("VEREDITO: SUCESSO! A lógica está correta.\n")
    else:
        print("VEREDITO: FALHA! A lógica está INCORRETA.\n")

    print("=" * 50)
    print("TESTE DE ISOLAMENTO CONCLUÍDO")
    print("=" * 50)
