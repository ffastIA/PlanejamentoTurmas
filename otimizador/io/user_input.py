import sys
from datetime import datetime
from typing import List, Optional

# Import relativo para acessar os modelos de dados do mesmo pacote
from ..data_models import ParametrosOtimizacao, ConfiguracaoProjeto, ParametrosFinanceiros


def obter_parametros_usuario() -> ParametrosOtimizacao:
    """Solicita parâmetros de otimização ao usuário via CLI."""
    print("\n" + "=" * 80)
    print("CONFIGURAÇÃO DE PARÂMETROS GLOBAIS DE OTIMIZAÇÃO")
    print("=" * 80)
    print("\nDefina os parâmetros globais da otimização:")
    print("(Pressione Enter para usar valores padrão)")
    print("(Digite 'sair' para cancelar)\n")

    try:
        capacidade_max = _obter_int_usuario(
            prompt="Capacidade máxima de turmas por instrutor/mês [padrão: 8]: ",
            valor_padrao=8, minimo=1, maximo=20, nome_parametro="Capacidade"
        )
        spread_maximo = _obter_int_usuario(
            prompt="Spread máximo permitido entre instrutores [padrão: 16]: ",
            valor_padrao=16, minimo=0, maximo=50, nome_parametro="Spread Máximo"
        )
        timeout = _obter_int_usuario(
            prompt="Timeout do solver em segundos [padrão: 180]: ",
            valor_padrao=180, minimo=10, maximo=3600, nome_parametro="Timeout"
        )

        peso_instrutores = _obter_int_usuario(
            prompt="Peso minimização instrutores [padrão: 10000]: ",
            valor_padrao=10000, minimo=1, maximo=100000, nome_parametro="Peso Instrutores"
        )

        peso_spread = _obter_int_usuario(
            prompt="Peso spread de carga [padrão: 1]: ",
            valor_padrao=1, minimo=0, maximo=10000, nome_parametro="Peso Spread"
        )

        pico_maximo = _obter_int_usuario(
            prompt="Pico máximo de turmas simultâneas [padrão: 100]: ",
            valor_padrao=100, minimo=1, maximo=500, nome_parametro="Pico Máximo"
        )

        parametros = ParametrosOtimizacao(
            capacidade_max_instrutor=capacidade_max,
            spread_maximo=spread_maximo,
            timeout_segundos=timeout,
            peso_instrutores=peso_instrutores,
            peso_spread=peso_spread,
            pico_maximo_turmas=pico_maximo
        )
        exibir_resumo_parametros(parametros)
        return parametros
    except KeyboardInterrupt:
        print("\n\n[!] Operação cancelada pelo usuário.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERRO] Falha ao obter parâmetros: {e}")
        sys.exit(1)


def obter_parametros_financeiros() -> ParametrosFinanceiros:
    """Solicita parâmetros financeiros ao usuário via CLI."""
    print("\n" + "=" * 80)
    print("CONFIGURAÇÃO DO MÓDULO FINANCEIRO")
    print("=" * 80)
    print("\nInforme os dados para cálculo do fluxo de caixa:")

    try:
        custo_mensal = _obter_float_usuario(
            prompt="Custo mensal médio por instrutor (R$) [padrão: 5000.00]: ",
            valor_padrao=5000.00,
            minimo=0.0,
            maximo=100000.0,
            nome_parametro="Custo Mensal"
        )

        params_fin = ParametrosFinanceiros(custo_mensal_instrutor=custo_mensal)
        print(f"\n[✓] Parâmetros financeiros definidos: Custo R$ {params_fin.custo_mensal_instrutor:.2f}/mês")
        return params_fin

    except KeyboardInterrupt:
        print("\n\n[!] Operação cancelada. Usando valores padrão (R$ 0,00).")
        return ParametrosFinanceiros()
    except Exception as e:
        print(f"\n[ERRO] Falha ao obter dados financeiros: {e}")
        return ParametrosFinanceiros()


def obter_projetos_usuario() -> List[ConfiguracaoProjeto]:
    """Solicita configuração de projetos ao usuário."""
    print("\n" + "=" * 80)
    print("CONFIGURAÇÃO DE PROJETOS")
    print("=" * 80)
    print("\nEscolha o modo de configuração:")
    print("  [1] Usar configuração PADRÃO (recomendado)")
    print("  [2] Configuração CUSTOMIZADA (avançado)")
    print("  [S] Sair")

    while True:
        escolha = input("\nOpção [1/2/S]: ").strip().upper()
        if escolha == 'S' or escolha == 'SAIR':
            raise KeyboardInterrupt()
        elif escolha == '' or escolha == '1':
            projetos = _obter_projetos_padrao()
            print("\n[✓] Usando configuração padrão dos projetos.")
            exibir_resumo_projetos(projetos)
            return projetos
        elif escolha == '2':
            projetos = _obter_projetos_customizados()
            # O resumo já é exibido dentro de _obter_projetos_customizados se concluído
            return projetos
        else:
            print("[!] Opção inválida. Digite 1, 2 ou S.")


def _obter_projetos_customizados() -> List[ConfiguracaoProjeto]:
    """Interface interativa para configuração customizada de projetos."""
    print("\n" + "=" * 80)
    print("CONFIGURAÇÃO CUSTOMIZADA DE PROJETOS")
    print("=" * 80)
    projetos = []
    while True:
        print("\n" + "-" * 80)
        print("MENU DE CONFIGURAÇÃO")
        print(f"Projetos configurados: {len(projetos)}")
        if projetos:
            for idx, proj in enumerate(projetos, 1):
                print(f"  {idx}. {proj.nome} ({proj.num_turmas} turmas, {proj.percentual_prog:.0f}% PROG)")
        print("\nOpções:\n  [A] Adicionar novo projeto")
        if projetos:
            print("  [E] Editar projeto existente\n  [R] Remover projeto\n  [C] Concluir e continuar")
        print("  [P] Usar configuração padrão\n  [S] Sair")

        opcao = input("\nEscolha uma opção: ").strip().upper()
        if opcao == 'S' or opcao == 'SAIR':
            raise KeyboardInterrupt()
        elif opcao == 'P':
            return _obter_projetos_padrao()
        elif opcao == 'A':
            novo_projeto = _configurar_projeto_interativo()
            if novo_projeto:
                projetos.append(novo_projeto)
                print(f"\n[✓] Projeto '{novo_projeto.nome}' adicionado com sucesso!")
        elif opcao == 'E' and projetos:
            projetos = _editar_projeto_interativo(projetos)
        elif opcao == 'R' and projetos:
            projetos = _remover_projeto_interativo(projetos)
        elif opcao == 'C' and projetos:
            if _confirmar_configuracao(projetos):
                return projetos
        else:
            print("[!] Opção inválida. Tente novamente.")


def _configurar_projeto_interativo(projeto_existente: Optional[ConfiguracaoProjeto] = None) -> Optional[
    ConfiguracaoProjeto]:
    """Configura um projeto interativamente, ou edita um existente."""
    is_editing = projeto_existente is not None
    title = "EDITAR PROJETO" if is_editing else "ADICIONAR NOVO PROJETO"
    print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)
    if is_editing: print("[INFO] Deixe em branco para manter o valor atual.")

    try:
        nome_prompt = f"Nome do projeto [{projeto_existente.nome if is_editing else ''}]: "
        nome = input(nome_prompt).strip() or (projeto_existente.nome if is_editing else '')
        if not nome:
            print("[!] Nome não pode ser vazio.")
            # Permite ao usuário tentar novamente sem sair da função
            return _configurar_projeto_interativo(projeto_existente)

        data_inicio_str = input(
            f"Data início (DD/MM/YYYY) [{projeto_existente.data_inicio if is_editing else ''}]: ").strip() or (
                              projeto_existente.data_inicio if is_editing else '')
        data_termino_str = input(
            f"Data término (DD/MM/YYYY) [{projeto_existente.data_termino if is_editing else ''}]: ").strip() or (
                               projeto_existente.data_termino if is_editing else '')

        num_turmas = _obter_int_usuario(f"Número de turmas [{projeto_existente.num_turmas if is_editing else ''}]: ",
                                        projeto_existente.num_turmas if is_editing else None, 1, 500, "Turmas")
        duracao_curso = _obter_int_usuario(
            f"Duração (meses) [{projeto_existente.duracao_curso if is_editing else ''}]: ",
            projeto_existente.duracao_curso if is_editing else None, 1, 12, "Duração")
        ondas = _obter_int_usuario(f"Número de ondas [{projeto_existente.ondas if is_editing else ''}]: ",
                                   projeto_existente.ondas if is_editing else 1, 1, 10, "Ondas")

        perc_prog = _obter_float_usuario(
            f"Percentual PROG (%) [{projeto_existente.percentual_prog if is_editing else 60}]: ",
            projeto_existente.percentual_prog if is_editing else 60.0, 0.0, 100.0, "Percentual PROG")

        projeto = ConfiguracaoProjeto(
            nome=nome, data_inicio=data_inicio_str, data_termino=data_termino_str,
            num_turmas=num_turmas, duracao_curso=duracao_curso, ondas=ondas, percentual_prog=perc_prog
        )
        print(
            f"\nRESUMO DO PROJETO:\n  Nome: {projeto.nome}\n  Período: {projeto.data_inicio} a {projeto.data_termino}\n  Turmas: {projeto.num_turmas}\n  Duração: {projeto.duracao_curso} meses\n  Ondas: {projeto.ondas}\n  Proporção: {projeto.percentual_prog:.1f}% PROG / {projeto.percentual_rob:.1f}% ROB")
        confirma = input("\nConfirmar? (S/N) [S]: ").strip().upper()
        return projeto if confirma in ('', 'S') else None
    except (KeyboardInterrupt, TypeError, ValueError) as e:
        print(f"\n[ERRO] Configuração inválida: {e}")
        return None


def _editar_projeto_interativo(projetos: List[ConfiguracaoProjeto]) -> List[ConfiguracaoProjeto]:
    """Interface para selecionar e editar um projeto."""
    for idx, proj in enumerate(projetos, 1):
        print(f"  {idx}. {proj.nome}")
    escolha = input(f"\nNúmero do projeto a editar [1-{len(projetos)}] ou 'C' para cancelar: ").strip()
    if escolha.upper() == 'C':
        return projetos
    try:
        idx = int(escolha) - 1
        if not (0 <= idx < len(projetos)):
            print("[!] Número inválido.")
            return projetos

        print(f"\nEditando o projeto '{projetos[idx].nome}'...")
        projeto_editado = _configurar_projeto_interativo(projetos[idx])
        if projeto_editado:
            projetos[idx] = projeto_editado
            print(f"\n[✓] Projeto '{projeto_editado.nome}' atualizado.")
        else:
            print("\nEdição cancelada.")

    except ValueError:
        print("[!] Digite um número válido.")
    return projetos


def _remover_projeto_interativo(projetos: List[ConfiguracaoProjeto]) -> List[ConfiguracaoProjeto]:
    """Interface para selecionar e remover um projeto."""
    print("\n" + "-" * 80)
    print("REMOVER PROJETO")
    for idx, proj in enumerate(projetos, 1):
        print(f"  {idx}. {proj.nome}")

    escolha = input(f"\nNúmero do projeto a remover [1-{len(projetos)}] ou 'C' para cancelar: ").strip()
    if escolha.upper() == 'C':
        return projetos

    try:
        idx = int(escolha) - 1
        if not (0 <= idx < len(projetos)):
            print("[!] Número inválido.")
            return projetos

        nome_removido = projetos[idx].nome
        confirma = input(f"Tem certeza que deseja remover o projeto '{nome_removido}'? (S/N) [N]: ").strip().upper()
        if confirma == 'S':
            projetos.pop(idx)
            print(f"\n[✓] Projeto '{nome_removido}' removido com sucesso!")
        else:
            print("\nOperação de remoção cancelada.")

    except ValueError:
        print("[!] Digite um número válido.")

    return projetos


def _confirmar_configuracao(projetos: List[ConfiguracaoProjeto]) -> bool:
    """Exibe o resumo final e pede confirmação para continuar."""
    exibir_resumo_projetos(projetos)
    confirma = input("\nConfirmar e continuar com esta configuração? (S/N) [S]: ").strip().upper()
    return confirma in ('', 'S')


def _obter_projetos_padrao() -> List[ConfiguracaoProjeto]:
    """Retorna a configuração padrão dos projetos para demonstração."""
    try:
        # A configuração padrão dos projetos que você forneceu.
        return [
            ConfiguracaoProjeto(nome='DD1', data_inicio='15/01/2026', data_termino='31/03/2026', num_turmas=8,
                                duracao_curso=2, ondas=1, percentual_prog=100.0),
            ConfiguracaoProjeto(nome='DD2', data_inicio='01/04/2026', data_termino='31/03/2027', num_turmas=110,
                                duracao_curso=4, ondas=2, percentual_prog=60.0),
            ConfiguracaoProjeto(nome='IdearTec', data_inicio='01/04/2026', data_termino='31/03/2027', num_turmas=110,
                                duracao_curso=4, ondas=2, percentual_prog=50.0)
        ]
    except ValueError as e:
        print(f"[ERRO CRÍTICO] A configuração padrão dos projetos é inválida: {e}")
        print("Por favor, corrija o código-fonte em _obter_projetos_padrao().")
        sys.exit(1)


def _obter_int_usuario(prompt: str, valor_padrao: Optional[int], minimo: int, maximo: int, nome_parametro: str) -> \
Optional[int]:
    """Solicita entrada inteira do usuário com validação robusta."""
    while True:
        entrada = input(prompt).strip()
        if entrada.lower() == 'sair':
            raise KeyboardInterrupt()
        if entrada == "" and valor_padrao is not None:
            return valor_padrao

        # Adicionado para casos onde um valor padrão não existe (edição de projeto)
        if entrada == "" and valor_padrao is None:
            print(f"[!] {nome_parametro} é um campo obrigatório.")
            continue

        try:
            valor = int(entrada)
            if minimo <= valor <= maximo:
                return valor
            else:
                print(f"[!] {nome_parametro} deve estar entre {minimo} e {maximo}.")
        except (ValueError, TypeError):
            print(f"[!] Valor inválido. Digite um número inteiro.")


def _obter_float_usuario(prompt: str, valor_padrao: float, minimo: float, maximo: float, nome_parametro: str) -> float:
    """Solicita entrada decimal (float) do usuário com validação robusta."""
    while True:
        entrada = input(prompt).strip()
        if entrada.lower() == 'sair':
            raise KeyboardInterrupt()
        if entrada == "" and valor_padrao is not None:
            return valor_padrao

        # Adicionado para casos onde um valor padrão não existe (edição de projeto)
        if entrada == "" and valor_padrao is None:
            print(f"[!] {nome_parametro} é um campo obrigatório.")
            continue

        try:
            # Substitui vírgula por ponto para aceitar ambos os formatos
            valor = float(entrada.replace(',', '.'))
            if minimo <= valor <= maximo:
                return valor
            else:
                print(f"[!] {nome_parametro} deve estar entre {minimo:.1f} e {maximo:.1f}.")
        except (ValueError, TypeError):
            print("[!] Valor inválido. Digite um número.")


def exibir_resumo_parametros(params: ParametrosOtimizacao):
    """Exibe um resumo claro e formatado dos parâmetros de otimização configurados."""
    print("\n" + "=" * 80)
    print("PARÂMETROS GLOBAIS CONFIGURADOS")
    print("=" * 80)
    print(f"  • Capacidade máxima por instrutor: {params.capacidade_max_instrutor} turmas/mês")
    print(f"  • Spread Máximo: {params.spread_maximo} turmas")
    print(f"  • Timeout do Solver: {params.timeout_segundos} segundos")
    print(f"  • Meses de Férias: {', '.join(params.meses_ferias)}")

    # Adicionando a exibição dos novos parâmetros
    print(f"  • Peso Minimização Instrutores: {params.peso_instrutores}")
    print(f"  • Peso Spread de Carga: {params.peso_spread}")
    print(f"  • Pico Máximo de Turmas: {params.pico_maximo_turmas}")

    print("=" * 80)


def exibir_resumo_projetos(projetos: List[ConfiguracaoProjeto]):
    """Exibe um resumo claro e formatado dos projetos configurados."""
    print("\n" + "=" * 80)
    print("PROJETOS CONFIGURADOS")
    print("=" * 80)

    if not projetos:
        print("\n  Nenhum projeto configurado ainda.")
    else:
        total_turmas = sum(p.num_turmas for p in projetos)
        total_prog = sum(p.num_turmas * (p.percentual_prog / 100.0) for p in projetos)
        total_rob = sum(p.num_turmas * (p.percentual_rob / 100.0) for p in projetos)

        for proj in projetos:
            print(f"\n  {proj.nome}:")
            print(f"    - Período: {proj.data_inicio} a {proj.data_termino}")
            print(f"    - Turmas: {proj.num_turmas} | Duração: {proj.duracao_curso} meses | Ondas: {proj.ondas}")
            print(f"    - Proporção: {proj.percentual_prog:.1f}% PROG / {proj.percentual_rob:.1f}% ROB")

        print("\n" + "-" * 80)
        print(f"\n  TOTAIS:")
        print(f"    • Total de Projetos: {len(projetos)}")
        print(f"    • Total de Turmas: {total_turmas}")
        print(f"    • Turmas PROG: {int(total_prog)}")
        print(f"    • Turmas ROB: {int(total_rob)}")

    print("\n" + "=" * 80)