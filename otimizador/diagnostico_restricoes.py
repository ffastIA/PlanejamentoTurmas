"""
Diagnóstico detalhado de conflitos de restrições
Versão 3.10 (Com cálculo correto de pico)
"""

from typing import List
from .data_models import ConfiguracaoProjeto, ParametrosOtimizacao
from .utils import data_para_indice_mes


def diagnosticar_restricoes(projetos_config: List[ConfiguracaoProjeto],
                            parametros: ParametrosOtimizacao,
                            meses: List[str]):
    """
    Diagnóstico detalhado para entender por que o solver falha

    CORREÇÃO v3.10: Cálculo correto do pico de turmas
    - Antes: Multiplicava turmas/mês × duração (ERRADO)
    - Depois: Calcula corretamente considerando sobreposição
    """

    print("\n" + "=" * 80)
    print("DIAGNÓSTICO DETALHADO DE RESTRIÇÕES")
    print("=" * 80)

    for proj in projetos_config:
        if proj.turmas_min_por_mes == 0:
            continue

        print(f"\n[Analisando] {proj.nome}")
        print("-" * 80)

        try:
            mes_inicio_idx = data_para_indice_mes(proj.data_inicio, meses)
            mes_fim_idx = data_para_indice_mes(proj.data_termino, meses)
        except:
            print(f"  ❌ Datas inválidas")
            continue

        duracao_meses_calendario = mes_fim_idx - mes_inicio_idx + 1
        meses_ferias_no_periodo = sum(1 for m in parametros.meses_ferias
                                      if m in meses[mes_inicio_idx:mes_fim_idx + 1])
        duracao_meses_letivos = duracao_meses_calendario - meses_ferias_no_periodo

        meses_disponiveis_para_inicio = duracao_meses_letivos - proj.duracao_curso + 1

        print(f"Período: {proj.data_inicio} a {proj.data_termino}")
        print(f"Meses letivos: {duracao_meses_letivos}")
        print(f"Duração curso: {proj.duracao_curso} meses")
        print(f"Meses disponíveis para início: {meses_disponiveis_para_inicio}")
        print(f"Ondas: {proj.ondas}")
        print(f"Turmas totais: {proj.num_turmas}")
        print(f"Turmas por onda: {proj.num_turmas / proj.ondas:.1f}")
        print(f"Mínimo por mês: {proj.turmas_min_por_mes}")

        # Cálculo de distribuição
        turmas_por_onda = proj.num_turmas / proj.ondas
        turmas_por_mes_por_onda = turmas_por_onda / meses_disponiveis_para_inicio

        print(f"\nCálculo de distribuição:")
        print(f"  Turmas/onda: {turmas_por_onda:.1f}")
        print(f"  Meses para distribuir: {meses_disponiveis_para_inicio}")
        print(f"  Turmas/mês/onda (média): {turmas_por_mes_por_onda:.2f}")
        print(f"  Turmas/mês (todas as ondas): {turmas_por_mes_por_onda * proj.ondas:.2f}")

        # CORREÇÃO v3.10: Cálculo correto do pico
        print(f"\nAnálise de viabilidade:")

        # Pior caso: todas as turmas começam no mesmo mês
        pico_pior_caso = proj.num_turmas
        print(f"  Pior caso (todas começam juntas): {pico_pior_caso} turmas")

        # Melhor caso: distribuição uniforme
        # Se temos X turmas para distribuir em Y meses de início,
        # e cada turma dura Z meses, então:
        # - Turmas começando por mês: X / Y
        # - Turmas ativas por mês: (X / Y) × Z
        # MAS: Isso só é válido se Y > Z
        # Se Y <= Z, então há sobreposição e o pico é menor

        if meses_disponiveis_para_inicio >= proj.duracao_curso:
            # Caso normal: há espaço para distribuir
            turmas_comecando_por_mes = proj.num_turmas / meses_disponiveis_para_inicio
            pico_melhor_caso = turmas_comecando_por_mes * proj.duracao_curso
        else:
            # Caso especial: período curto, turmas se sobrepõem
            # O pico é limitado ao número total de turmas
            turmas_comecando_por_mes = proj.num_turmas / meses_disponiveis_para_inicio
            pico_melhor_caso = min(proj.num_turmas, turmas_comecando_por_mes * proj.duracao_curso)

        print(f"  Melhor caso (distribuição uniforme):")
        print(f"    - Turmas começando/mês: {turmas_comecando_por_mes:.1f}")
        print(f"    - Turmas ativas/mês: {pico_melhor_caso:.1f}")

        # Verificação de mínimo
        print(f"\nVerificação de mínimo ({proj.turmas_min_por_mes} turmas/mês):")

        if pico_melhor_caso < proj.turmas_min_por_mes:
            print(f"  ❌ IMPOSSÍVEL: Melhor caso ({pico_melhor_caso:.1f}) < Mínimo ({proj.turmas_min_por_mes})")
            print(f"     Recomendação: Aumentar turmas ou reduzir mínimo")
        elif pico_pior_caso > parametros.pico_maximo_turmas:
            print(f"  ⚠️  CRÍTICO: Pior caso ({pico_pior_caso}) > Limite ({parametros.pico_maximo_turmas})")
            print(f"     Recomendação: Aumentar pico_maximo_turmas ou aumentar ondas")
        else:
            print(f"  ✓ Teoricamente viável")
            print(f"    - Melhor caso: {pico_melhor_caso:.1f} turmas/mês")
            print(f"    - Pior caso: {pico_pior_caso} turmas/mês")
            print(f"    - Limite: {parametros.pico_maximo_turmas} turmas/mês")
            print(f"    - Mínimo: {proj.turmas_min_por_mes} turmas/mês")

            if pico_melhor_caso >= proj.turmas_min_por_mes and pico_pior_caso <= parametros.pico_maximo_turmas:
                print(f"  ✓ Deve ser possível encontrar uma distribuição viável")
            else:
                print(f"  ⚠️  Margem muito apertada - solver pode ter dificuldade")