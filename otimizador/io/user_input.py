import sys
from datetime import datetime
from typing import List, Optional

# Import relativo
from ..data_models import ParametrosOtimizacao, ConfiguracaoProjeto, ParametrosFinanceiros, ItemCusto


def obter_parametros_usuario() -> ParametrosOtimizacao:
    """Solicita parâmetros de otimização ao usuário via CLI."""
    print("\n" + "=" * 80)
    print("CONFIGURAÇÃO DE PARÂMETROS GLOBAIS DE OTIMIZAÇÃO")
    print("=" * 80)
    print("\nDefina os parâmetros globais da otimização:")
    print("(Pressione Enter para usar valores padrão)")
    print("(Digite 'sair' para cancelar)\n")

    try:
        capacidade_max = _obter_int_usuario("Capacidade máxima de turmas por instrutor/mês [padrão: 8]: ", 8, 1, 20,
                                            "Capacidade")
        spread_maximo = _obter_int_usuario("Spread máximo permitido entre instrutores [padrão: 16]: ", 16, 0, 50,
                                           "Spread Máximo")
        timeout = _obter_int_usuario("Timeout do solver em segundos [padrão: 180]: ", 180, 10, 3600, "Timeout")
        peso_instrutores = _obter_int_usuario("Peso minimização instrutores [padrão: 10000]: ", 10000, 1, 100000,
                                              "Peso Instrutores")
        peso_spread = _obter_int_usuario("Peso spread de carga [padrão: 1]: ", 1, 0, 10000, "Peso Spread")
        pico_maximo = _obter_int_usuario("Pico máximo de turmas simultâneas [padrão: 100]: ", 100, 1, 500,
                                         "Pico Máximo")

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


def obter_parametros_financeiros(projetos_disponiveis: List[ConfiguracaoProjeto]) -> ParametrosFinanceiros:
    """Solicita múltiplos custos ao usuário via CLI, permitindo alocação por projeto."""
    print("\n" + "=" * 80)
    print("CONFIGURAÇÃO DO MÓDULO FINANCEIRO")
    print("=" * 80)
    print("Defina os custos. Você pode definir custos GLOBAIS ou ESPECÍFICOS por projeto.\n")

    params_fin = ParametrosFinanceiros()

    tipos_map = {
        '1': 'INICIAL',
        '2': 'ENCERRAMENTO',
        '3': 'EXECUCAO',
        '4': 'PERMANENTE'
    }

    while True:
        print("\n--- Adicionar Novo Custo ---")
        print("Tipos disponíveis:")
        print("  [1] INICIAL      (Início da turma)")
        print("  [2] ENCERRAMENTO (Final da turma)")
        print("  [3] EXECUÇÃO     (Mensal durante a turma)")
        print("  [4] PERMANENTE   (Mensal durante todo o projeto/vigência)")
        print("  [S] Sair / Concluir")

        escolha = input("\nEscolha o tipo [1-4] ou S para concluir: ").strip().upper()

        if escolha == 'S':
            break

        if escolha not in tipos_map:
            print("[!] Opção inválida.")
            continue

        tipo_selecionado = tipos_map[escolha]

        # Seleção de Escopo (Global ou Projeto)
        projeto_selecionado = None
        print("\nEscopo do Custo:")
        print("  [G] GLOBAL (Aplica a todos os projetos/turmas)")
        if projetos_disponiveis:
            for idx, p in enumerate(projetos_disponiveis, 1):
                print(f"  [{idx}] Projeto: {p.nome}")

        escopo = input("Escolha o escopo [G ou número do projeto]: ").strip().upper()

        if escopo != 'G':
            try:
                idx_proj = int(escopo) - 1
                if 0 <= idx_proj < len(projetos_disponiveis):
                    projeto_selecionado = projetos_disponiveis[idx_proj].nome
                    print(f"   -> Selecionado: {projeto_selecionado}")
                else:
                    print("[!] Projeto inválido. Definindo como GLOBAL.")
            except ValueError:
                print("[!] Opção inválida. Definindo como GLOBAL.")
        else:
            print("   -> Selecionado: GLOBAL")

        descricao = input(f"Descrição do custo (ex: 'Salário', 'Licença SW'): ").strip()
        if not descricao:
            print("[!] Descrição obrigatória.")
            continue

        valor = _obter_float_usuario(f"Valor do custo (R$): ", None, 0.0, 1000000.0, "Valor")

        params_fin.adicionar_custo(tipo_selecionado, descricao, valor, projeto_selecionado)

        escopo_str = f"PROJETO {projeto_selecionado}" if projeto_selecionado else "GLOBAL"
        print(f"[✓] Adicionado: [{escopo_str}] {tipo_selecionado} - {descricao} - R$ {valor:.2f}")

    print(f"\n[✓] Configuração financeira concluída. Total de itens: {len(params_fin.itens_custo)}")
    return params_fin


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
    """Configura um projeto interativamente."""
    is_editing = projeto_existente is not None
    title = "EDITAR PROJETO" if is_editing else "ADICIONAR NOVO PROJETO"
    print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)
    if is_editing: print("[INFO] Deixe em branco para manter o valor atual.")

    try:
        nome_prompt = f"Nome do projeto [{projeto_existente.nome if is_editing else ''}]: "
        nome = input(nome_prompt).strip() or (projeto_existente.nome if is_editing else '')
        if not nome: return _configurar_projeto_interativo(projeto_existente)

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

        projeto = ConfiguracaoProjeto(nome=nome, data_inicio=data_inicio_str, data_termino=data_termino_str,
                                      num_turmas=num_turmas, duracao_curso=duracao_curso, ondas=ondas,
                                      percentual_prog=perc_prog)
        confirma = input("\nConfirmar? (S/N) [S]: ").strip().upper()
        return projeto if confirma in ('', 'S') else None
    except (KeyboardInterrupt, TypeError, ValueError) as e:
        print(f"\n[ERRO] Configuração inválida: {e}")
        return None


def _editar_projeto_interativo(projetos: List[ConfiguracaoProjeto]) -> List[ConfiguracaoProjeto]:
    for idx, proj in enumerate(projetos, 1): print(f"  {idx}. {proj.nome}")
    escolha = input(f"\nNúmero do projeto a editar [1-{len(projetos)}] ou 'C' para cancelar: ").strip()
    if escolha.upper() == 'C': return projetos
    try:
        idx = int(escolha) - 1
        if 0 <= idx < len(projetos): projetos[idx] = _configurar_projeto_interativo(projetos[idx]) or projetos[idx]
    except ValueError:
        pass
    return projetos


def _remover_projeto_interativo(projetos: List[ConfiguracaoProjeto]) -> List[ConfiguracaoProjeto]:
    for idx, proj in enumerate(projetos, 1): print(f"  {idx}. {proj.nome}")
    escolha = input(f"\nNúmero do projeto a remover [1-{len(projetos)}] ou 'C' para cancelar: ").strip()
    if escolha.upper() == 'C': return projetos
    try:
        idx = int(escolha) - 1
        if 0 <= idx < len(projetos):
            if input(f"Remover '{projetos[idx].nome}'? (S/N) [N]: ").strip().upper() == 'S': projetos.pop(idx)
    except ValueError:
        pass
    return projetos


def _confirmar_configuracao(projetos: List[ConfiguracaoProjeto]) -> bool:
    exibir_resumo_projetos(projetos)
    return input("\nConfirmar? (S/N) [S]: ").strip().upper() in ('', 'S')


def _obter_projetos_padrao() -> List[ConfiguracaoProjeto]:
    return [
        ConfiguracaoProjeto('DD1', '15/01/2026', '31/03/2026', 8, 2, 1, 100.0),
        ConfiguracaoProjeto('DD2', '01/04/2026', '31/03/2027', 110, 4, 2, 60.0),
        ConfiguracaoProjeto('IdearTec', '01/04/2026', '31/03/2027', 110, 4, 2, 50.0)
    ]


def _obter_int_usuario(prompt: str, valor_padrao: Optional[int], minimo: int, maximo: int, nome_parametro: str) -> \
Optional[int]:
    while True:
        entrada = input(prompt).strip()
        if entrada.lower() == 'sair': raise KeyboardInterrupt()
        if entrada == "" and valor_padrao is not None: return valor_padrao
        if entrada == "" and valor_padrao is None:
            print(f"[!] {nome_parametro} obrigatório.");
            continue
        try:
            val = int(entrada)
            if minimo <= val <= maximo: return val
            print(f"[!] {nome_parametro} entre {minimo} e {maximo}.")
        except:
            print("[!] Digite um inteiro.")


def _obter_float_usuario(prompt: str, valor_padrao: Optional[float], minimo: float, maximo: float,
                         nome_parametro: str) -> float:
    while True:
        entrada = input(prompt).strip()
        if entrada.lower() == 'sair': raise KeyboardInterrupt()
        if entrada == "" and valor_padrao is not None: return valor_padrao
        if entrada == "" and valor_padrao is None:
            print(f"[!] {nome_parametro} obrigatório.");
            continue
        try:
            val = float(entrada.replace(',', '.'))
            if minimo <= val <= maximo: return val
            print(f"[!] {nome_parametro} entre {minimo} e {maximo}.")
        except:
            print("[!] Digite um número.")


def exibir_resumo_parametros(params: ParametrosOtimizacao):
    print("\n" + "=" * 80 + "\nPARÂMETROS GLOBAIS\n" + "=" * 80)
    print(
        f"  • Capacidade: {params.capacidade_max_instrutor} | Spread: {params.spread_maximo} | Timeout: {params.timeout_segundos}s")
    print(f"  • Pesos: Instrutores={params.peso_instrutores}, Spread={params.peso_spread}")


def exibir_resumo_projetos(projetos: List[ConfiguracaoProjeto]):
    print("\n" + "=" * 80 + "\nPROJETOS\n" + "=" * 80)
    if not projetos: print("  Nenhum projeto."); return
    for p in projetos:
        print(f"\n  {p.nome}: {p.num_turmas} turmas, {p.duracao_curso} meses, {p.data_inicio}-{p.data_termino}")
    print(f"\n  TOTAL: {sum(p.num_turmas for p in projetos)} turmas.")