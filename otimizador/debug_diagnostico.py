"""
Script de Diagnóstico - Rastreia o fluxo de dados entre Stage 1 e Stage 2
"""

from typing import List, Dict, Any
import pandas as pd
from .data_models import Projeto, Turma
from .utils import calcular_meses_ativos


def diagnosticar_fluxo_dados(cronograma_stage1: List[Dict],
                             turmas_stage2: List[Turma],
                             meses: List[str],
                             meses_ferias_idx: List[int]) -> Dict[str, Any]:
    """
    Diagnóstico completo do fluxo de dados entre Stage 1 e Stage 2.
    Retorna um relatório detalhado das discrepâncias.
    """

    num_meses = len(meses)

    print("\n" + "=" * 80)
    print("DIAGNÓSTICO DETALHADO: FLUXO DE DADOS ENTRE STAGE 1 E STAGE 2")
    print("=" * 80)

    # --- 1. ANÁLISE DO CRONOGRAMA DO STAGE 1 ---
    print("\n[1] ANÁLISE DO CRONOGRAMA (Stage 1)")
    print("-" * 80)

    total_turmas_stage1 = sum(item['qtd'] for item in cronograma_stage1)
    print(f"Total de turmas no cronograma Stage 1: {total_turmas_stage1}")
    print(f"Número de itens de início: {len(cronograma_stage1)}")

    # Calcular demanda mensal conforme Stage 1
    demanda_stage1 = [0] * num_meses
    for item in cronograma_stage1:
        qtd = item['qtd']
        mes_inicio = item['mes_inicio']
        duracao = item['duracao']

        meses_ativos = calcular_meses_ativos(mes_inicio, duracao, meses_ferias_idx, num_meses)
        for m in meses_ativos:
            demanda_stage1[m] += qtd

    pico_stage1 = max(demanda_stage1) if demanda_stage1 else 0
    print(f"Pico calculado a partir do cronograma: {pico_stage1} turmas")
    print(f"Mês do pico: {meses[demanda_stage1.index(pico_stage1)]}")

    # Mostrar cronograma por projeto
    print("\nDetalhamento por Projeto:")
    projetos_unicos = set(item['projeto_nome'] for item in cronograma_stage1)
    for proj in sorted(projetos_unicos):
        itens_proj = [item for item in cronograma_stage1 if item['projeto_nome'] == proj]
        qtd_total = sum(item['qtd'] for item in itens_proj)
        print(f"  {proj}: {qtd_total} turmas em {len(itens_proj)} itens de início")

    # --- 2. ANÁLISE DAS TURMAS DO STAGE 2 ---
    print("\n[2] ANÁLISE DAS TURMAS (Stage 2)")
    print("-" * 80)

    print(f"Total de turmas em Stage 2: {len(turmas_stage2)}")

    # Calcular demanda mensal conforme Stage 2
    demanda_stage2 = [0] * num_meses
    for turma in turmas_stage2:
        meses_ativos = calcular_meses_ativos(turma.mes_inicio, turma.duracao, meses_ferias_idx, num_meses)
        for m in meses_ativos:
            demanda_stage2[m] += 1

    pico_stage2 = max(demanda_stage2) if demanda_stage2 else 0
    print(f"Pico calculado a partir das turmas: {pico_stage2} turmas")
    print(f"Mês do pico: {meses[demanda_stage2.index(pico_stage2)]}")

    # Mostrar turmas por projeto
    print("\nDetalhamento por Projeto:")
    projetos_turmas = {}
    for turma in turmas_stage2:
        proj = turma.projeto.split('_Onda')[0]
        if proj not in projetos_turmas:
            projetos_turmas[proj] = 0
        projetos_turmas[proj] += 1

    for proj in sorted(projetos_turmas.keys()):
        print(f"  {proj}: {projetos_turmas[proj]} turmas")

    # --- 3. COMPARAÇÃO ---
    print("\n[3] COMPARAÇÃO STAGE 1 vs STAGE 2")
    print("-" * 80)

    diferenca_turmas = len(turmas_stage2) - total_turmas_stage1
    diferenca_pico = pico_stage2 - pico_stage1

    print(f"Diferença de turmas totais: {diferenca_turmas}")
    print(f"  Stage 1: {total_turmas_stage1}")
    print(f"  Stage 2: {len(turmas_stage2)}")

    print(f"\nDiferença de pico: {diferenca_pico}")
    print(f"  Stage 1: {pico_stage1}")
    print(f"  Stage 2: {pico_stage2}")

    # --- 4. ANÁLISE MENSAL DETALHADA ---
    print("\n[4] ANÁLISE MENSAL DETALHADA")
    print("-" * 80)

    df_comparacao = pd.DataFrame({
        'Mês': meses,
        'Stage1': demanda_stage1,
        'Stage2': demanda_stage2,
        'Diferença': [s2 - s1 for s1, s2 in zip(demanda_stage1, demanda_stage2)]
    })

    print(df_comparacao.to_string(index=False))

    # Identificar meses com maior discrepância
    meses_problema = df_comparacao[df_comparacao['Diferença'] != 0]
    if not meses_problema.empty:
        print(f"\n⚠️  Meses com discrepância:")
        for _, row in meses_problema.iterrows():
            print(
                f"  {row['Mês']}: Stage1={int(row['Stage1'])}, Stage2={int(row['Stage2'])}, Diff={int(row['Diferença'])}")

    # --- 5. DIAGNÓSTICO DE CAUSA ---
    print("\n[5] DIAGNÓSTICO DE CAUSA")
    print("-" * 80)

    if diferenca_turmas > 0:
        print(f"❌ PROBLEMA: Stage 2 tem {diferenca_turmas} turmas A MAIS que Stage 1")
        print("   Possível causa: Turmas estão sendo criadas fora do cronograma otimizado")
    elif diferenca_turmas < 0:
        print(f"❌ PROBLEMA: Stage 2 tem {abs(diferenca_turmas)} turmas A MENOS que Stage 1")
        print("   Possível causa: Turmas estão sendo perdidas durante a alocação")
    else:
        print("✓ Número de turmas está consistente")

    if diferenca_pico > 0:
        print(f"\n❌ PROBLEMA: Pico em Stage 2 é {diferenca_pico} turmas MAIOR que Stage 1")
        print("   Possível causa: Turmas estão sendo concentradas em poucos meses")
    elif diferenca_pico < 0:
        print(f"\n❌ PROBLEMA: Pico em Stage 2 é {abs(diferenca_pico)} turmas MENOR que Stage 1")
        print("   Possível causa: Distribuição melhorou (improvável)")
    else:
        print("\n✓ Pico está consistente")

    # --- 6. RECOMENDAÇÕES ---
    print("\n[6] RECOMENDAÇÕES")
    print("-" * 80)

    if diferenca_turmas != 0 or diferenca_pico > 5:
        print("⚠️  AÇÃO NECESSÁRIA:")
        print("1. Verificar se Stage 2 está usando o cronograma correto")
        print("2. Confirmar que nenhuma turma extra está sendo criada")
        print("3. Validar a função calcular_meses_ativos()")
        print("4. Revisar a lógica de distribuição PROG/ROB")
    else:
        print("✓ Sistema está funcionando corretamente")

    print("\n" + "=" * 80)

    return {
        'pico_stage1': pico_stage1,
        'pico_stage2': pico_stage2,
        'turmas_stage1': total_turmas_stage1,
        'turmas_stage2': len(turmas_stage2),
        'demanda_stage1': demanda_stage1,
        'demanda_stage2': demanda_stage2,
        'df_comparacao': df_comparacao
    }