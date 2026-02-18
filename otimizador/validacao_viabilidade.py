"""
Módulo de Validação de Viabilidade
Detecta conflitos de restrições antes de chamar o solver
"""

from typing import List, Tuple
from .data_models import ConfiguracaoProjeto, ParametrosOtimizacao
from .utils import gerar_lista_meses, data_para_indice_mes


def validar_viabilidade_configuracao(projetos_config: List[ConfiguracaoProjeto],
                                     parametros: ParametrosOtimizacao,
                                     meses: List[str]) -> Tuple[bool, List[str]]:
    """
    Valida se a configuração é viável antes de chamar o solver.
    Retorna (é_viável, lista_de_avisos)
    """

    avisos = []

    print("\n" + "=" * 80)
    print("VALIDAÇÃO DE VIABILIDADE DA CONFIGURAÇÃO")
    print("=" * 80)

    # --- 1. VALIDAÇÃO POR PROJETO ---
    for proj in projetos_config:
        print(f"\n[Validando] {proj.nome}")

        # Converter datas para índices
        try:
            mes_inicio_idx = data_para_indice_mes(proj.data_inicio, meses)
            mes_fim_idx = data_para_indice_mes(proj.data_termino, meses)
        except:
            avisos.append(f"❌ {proj.nome}: Datas inválidas ou fora do período")
            continue

        duracao_meses_calendario = mes_fim_idx - mes_inicio_idx + 1

        # Calcular meses de férias no período
        meses_ferias_no_periodo = sum(1 for m in parametros.meses_ferias
                                      if m in meses[mes_inicio_idx:mes_fim_idx + 1])

        duracao_meses_letivos = duracao_meses_calendario - meses_ferias_no_periodo

        print(f"  Período: {proj.data_inicio} a {proj.data_termino}")
        print(f"  Meses calendário: {duracao_meses_calendario}")
        print(f"  Meses de férias: {meses_ferias_no_periodo}")
        print(f"  Meses letivos: {duracao_meses_letivos}")
        print(f"  Duração curso: {proj.duracao_curso} meses")
        print(f"  Ondas: {proj.ondas}")
        print(f"  Turmas: {proj.num_turmas}")
        print(f"  Mínimo/mês: {proj.turmas_min_por_mes}")

        # --- VALIDAÇÃO 1: Duração do curso vs. período ---
        if proj.duracao_curso > duracao_meses_letivos:
            avisos.append(
                f"❌ {proj.nome}: Duração do curso ({proj.duracao_curso} meses) "
                f"maior que período disponível ({duracao_meses_letivos} meses letivos)"
            )

        # --- VALIDAÇÃO 2: Janela de início por onda ---
        meses_disponiveis_para_inicio = duracao_meses_letivos - proj.duracao_curso + 1

        if meses_disponiveis_para_inicio <= 0:
            avisos.append(
                f"❌ {proj.nome}: Sem janela de início viável. "
                f"Período ({duracao_meses_letivos}) < Duração ({proj.duracao_curso})"
            )
            continue

        print(f"  Meses disponíveis para início: {meses_disponiveis_para_inicio}")

        # --- VALIDAÇÃO 3: Distribuição de ondas ---
        if proj.ondas > 1:
            meses_por_onda = meses_disponiveis_para_inicio / proj.ondas
            print(f"  Meses por onda: {meses_por_onda:.2f}")

            if meses_por_onda < 1:
                avisos.append(
                    f"⚠️  {proj.nome}: Muitas ondas ({proj.ondas}) para o período. "
                    f"Apenas {meses_disponiveis_para_inicio} mês(es) disponível(is). "
                    f"Recomendação: Reduzir ondas para {max(1, meses_disponiveis_para_inicio)}"
                )

        # --- VALIDAÇÃO 4: Mínimo de turmas por mês ---
        turmas_por_onda = proj.num_turmas / proj.ondas
        min_turmas_total = proj.turmas_min_por_mes * duracao_meses_letivos

        print(f"  Turmas por onda: {turmas_por_onda:.1f}")
        print(f"  Mínimo total exigido: {min_turmas_total} turmas")
        print(f"  Total disponível: {proj.num_turmas} turmas")

        if proj.num_turmas < min_turmas_total:
            avisos.append(
                f"❌ {proj.nome}: Impossível atender mínimo. "
                f"Exigido: {min_turmas_total}, Disponível: {proj.num_turmas}. "
                f"Recomendação: Reduzir 'turmas_min_por_mes' para {proj.num_turmas // duracao_meses_letivos}"
            )

        # --- VALIDAÇÃO 5: Conflito de mínimo com ondas ---
        if proj.ondas > 1 and proj.turmas_min_por_mes > 0:
            # Cada onda precisa ter turmas começando
            # Se há mínimo de turmas/mês, cada onda precisa contribuir
            turmas_min_por_onda_por_mes = proj.turmas_min_por_mes / proj.ondas

            if turmas_min_por_onda_por_mes < 1 and proj.turmas_min_por_mes > 0:
                avisos.append(
                    f"⚠️  {proj.nome}: Mínimo de turmas ({proj.turmas_min_por_mes}) "
                    f"não é divisível por ondas ({proj.ondas}). "
                    f"Isso pode causar inviabilidade. "
                    f"Recomendação: Ajustar mínimo para múltiplo de {proj.ondas}"
                )

        # --- VALIDAÇÃO 6: Pico teórico POR ONDA (CORRIGIDO) ---
        # CORREÇÃO CRÍTICA: Comparar pico por onda, não total
        pico_teorico_por_onda = turmas_por_onda

        print(f"  Pico teórico por onda: {pico_teorico_por_onda:.1f}")

        if pico_teorico_por_onda > parametros.pico_maximo_turmas:
            avisos.append(
                f"❌ {proj.nome}: Pico por onda ({pico_teorico_por_onda:.1f}) "
                f"ultrapassa limite ({parametros.pico_maximo_turmas}). "
                f"Recomendação: Aumentar 'pico_maximo_turmas' ou aumentar número de ondas"
            )
        else:
            print(
                f"  ✓ Pico por onda ({pico_teorico_por_onda:.1f}) está dentro do limite ({parametros.pico_maximo_turmas})")

    # --- 2. VALIDAÇÃO GLOBAL ---
    print(f"\n[Validando] Parâmetros Globais")

    total_turmas = sum(p.num_turmas for p in projetos_config)
    total_ondas = sum(p.ondas for p in projetos_config)

    print(f"  Total de turmas: {total_turmas}")
    print(f"  Total de ondas: {total_ondas}")
    print(f"  Pico máximo: {parametros.pico_maximo_turmas}")
    print(f"  Capacidade instrutor: {parametros.capacidade_max_instrutor}")

    instrutores_necessarios = total_turmas / parametros.capacidade_max_instrutor
    print(f"  Instrutores necessários (mínimo): {instrutores_necessarios:.1f}")

    # --- VALIDAÇÃO GLOBAL: Pico consolidado ---
    # O pico consolidado é a soma de todas as ondas ativas simultaneamente
    # Pior caso: todas as ondas começam no mesmo mês
    pico_consolidado_maximo = total_turmas

    print(f"  Pico consolidado máximo (todas as ondas simultâneas): {pico_consolidado_maximo}")

    if pico_consolidado_maximo > parametros.pico_maximo_turmas:
        avisos.append(
            f"⚠️  GLOBAL: Pico consolidado ({pico_consolidado_maximo}) "
            f"ultrapassa limite ({parametros.pico_maximo_turmas}). "
            f"Isso é esperado com múltiplas ondas. "
            f"O solver distribuirá as ondas para respeitar o limite."
        )

    # --- RESULTADO ---
    print("\n" + "=" * 80)

    if avisos:
        print(f"\n⚠️  AVISOS DETECTADOS ({len(avisos)}):\n")
        for i, aviso in enumerate(avisos, 1):
            print(f"{i}. {aviso}\n")

        # Verificar se há erros críticos
        erros_criticos = [a for a in avisos if a.startswith("❌")]

        if erros_criticos:
            print("\n" + "!" * 80)
            print("❌ CONFIGURAÇÃO INVIÁVEL - Erros críticos detectados")
            print("!" * 80)
            return False, avisos
        else:
            print("\n✓ Configuração pode ser viável")
            return True, avisos
    else:
        print("✓ Configuração validada com sucesso!")
        return True, avisos