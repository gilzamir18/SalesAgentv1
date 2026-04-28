from agenticblocks import as_tool
from collections import namedtuple
import time

# ── Estado de conversa ─────────────────────────────────────────────────────


@as_tool(name="print_agent_response",
         description="Entrega a resposta final ao cliente.")
def print_agent_response(response: str) -> str:
    # Esta é a ÚNICA fonte de impressão da fala do agente.
    print(f"Agent: {response}")
    chat_history.append(f"Agent: {response}")
    return "ok"

chat_history = []

# ── Dados do domínio ───────────────────────────────────────────────────────

Produto = namedtuple('Produto', ['id', 'nome', 'descricao', 'preco', 'quantidade_em_estoque',
                                 'negociavel', 'precoMin', 'condicaoNegociacao'])

produtos: dict[int, Produto] = {
    0: Produto(0, 'cheeseburger',
               'Cheeseburger com pão sem gergelim, queijo mussarela, ovo estrelado, cebola e alface',
               15.0, 10, False, 15.0, ""),
    1: Produto(1, 'suco de laranja',
               'Suco de laranja, copo de 250 ml sem açúcar.',
               8.0, 100, False, 8.0, ""),
    2: Produto(2, 'suco de polpa',
               '250 ml de suco de polpa. Opções disponíveis: abacaxi, goiaba, acerola e caju',
               6.0, 100, False, 6.0, ""),
    3: Produto(3, 'coxinha de frango',
               'Coxinha de frango',
               6.0, 10, False, 6.0, ""),
    4: Produto(4, 'pudim de leite',
               'Porção de 100g de pudim de leite',
               10.0, 10, True, 8.0,
               "Apenas para clientes que tenham comprado um cheeseburger e um suco de laranja."),
}

# carrinho_ativo mapeia produto_id → quantidade pedida
carrinho_ativo: dict[int, int] = {}

# checkout_info guarda dados necessários antes de fechar o pedido
checkout_info: dict[str, str] = {}   # chaves: "endereco", "pagamento"

# estado_pedido rastreia se o pedido foi fechado e aguarda confirmação do usuário
estado_pedido: dict[str, bool] = {"fechado": False}


# ── Carrinho de Compras ────────────────────────────────────────────────────

def _qtd_no_carrinho(produto_id: int) -> int:
    return carrinho_ativo.get(produto_id, 0)


def _buscar_produto(nome: str) -> Produto | None:
    nome_up = nome.strip().upper()
    for p in produtos.values():
        if nome_up == p.nome.upper() or nome_up in p.nome.upper() or nome_up in p.descricao.upper():
            return p
    return None


@as_tool(name="adicionar_item")
def _adicionar_item(item: str, quantidade: int = 1) -> str:
    """Adiciona itens ao carrinho."""
    p = _buscar_produto(item)
    if p is None:
        return f"Item '{item}' não encontrado no cardápio."
    disponivel = p.quantidade_em_estoque - _qtd_no_carrinho(p.id)
    if quantidade > disponivel:
        return f"Estoque insuficiente: apenas {disponivel} unidade(s) de '{p.nome}' disponíveis."
    carrinho_ativo[p.id] = _qtd_no_carrinho(p.id) + quantidade
    subtotal = carrinho_ativo[p.id] * p.preco
    return f"Adicionado: {quantidade}x {p.nome} (R$ {p.preco:.2f} cada). Subtotal: R$ {subtotal:.2f}."


@as_tool(name="remover_item")
def _remover_item(item: str, quantidade: int = 1) -> str:
    """Remove itens do carrinho."""
    p = _buscar_produto(item)
    if p is None:
        return f"Item '{item}' não encontrado."
    no_carrinho = _qtd_no_carrinho(p.id)
    if no_carrinho == 0:
        return f"'{p.nome}' não está no carrinho."
    nova_qtd = no_carrinho - quantidade
    if nova_qtd <= 0:
        del carrinho_ativo[p.id]
        return f"'{p.nome}' removido do carrinho."
    carrinho_ativo[p.id] = nova_qtd
    return f"Removido {quantidade}x '{p.nome}'. Ainda {nova_qtd} no carrinho."


def _listar_carrinho() -> str:
    """Lógica pura de listagem do carrinho (sem decorador)."""
    if not carrinho_ativo:
        return "Carrinho vazio."
    lines = ["Seu carrinho:"]
    total = 0.0
    for pid, qtd in carrinho_ativo.items():
        p = produtos[pid]
        subtotal = qtd * p.preco
        total += subtotal
        lines.append(f"  {qtd}x {p.nome} – R$ {p.preco:.2f} cada = R$ {subtotal:.2f}")
    lines.append(f"Total: R$ {total:.2f}")
    return "\n".join(lines)


@as_tool(name="ver_carrinho")
def _ver_carrinho() -> str:
    """Mostra o conteúdo atual do carrinho."""
    return _listar_carrinho()


@as_tool(name="registrar_endereco")
def _registrar_endereco(endereco: str) -> str:
    """Registra o endereço de entrega do pedido."""
    checkout_info["endereco"] = endereco.strip()
    return f"Endereço de entrega registrado: {checkout_info['endereco']}"


@as_tool(name="registrar_pagamento")
def _registrar_pagamento(forma: str) -> str:
    """Registra a forma de pagamento (ex: pix, cartão, dinheiro)."""
    checkout_info["pagamento"] = forma.strip()
    return f"Forma de pagamento registrada: {checkout_info['pagamento']}"


@as_tool(name="fechar_pedido")
def _fechar_pedido() -> str:
    """Fecha o pedido após confirmar endereço e pagamento."""
    if not carrinho_ativo:
        return "Carrinho vazio. Adicione itens antes de fechar o pedido."
    faltando = [f for f in ("endereco", "pagamento") if f not in checkout_info]
    if faltando:
        labels = {"endereco": "endereço de entrega", "pagamento": "forma de pagamento"}
        pendentes = " e ".join(labels[f] for f in faltando)
        return f"Pedido não finalizado. Ainda falta informar: {pendentes}."
    numero_pedido = int(time.time() * 1000) % 1_000_000
    resumo = _listar_carrinho()
    for pid, qtd in carrinho_ativo.items():
        p = produtos[pid]
        produtos[pid] = p._replace(quantidade_em_estoque=p.quantidade_em_estoque - qtd)
    carrinho_ativo.clear()
    endereco  = checkout_info.pop("endereco")
    pagamento = checkout_info.pop("pagamento")
    estado_pedido["fechado"] = True
    return (
        f"Pedido confirmado! Número do pedido: #{numero_pedido:06d}\n{resumo}\n"
        f"Entrega em: {endereco}\n"
        f"Pagamento: {pagamento}\n"
        "Por favor, confirme seu pedido respondendo 'sim' ou 'ok'."
    )


# ── Consulta ao Cardápio ───────────────────────────────────────────────────

@as_tool(name="consultar_item")
def _consultar_item(item: str) -> str:
    p = _buscar_produto(item)
    if p is None:
        return f"Item '{item}' não encontrado no cardápio."
    if p.quantidade_em_estoque > 0:
        return f"{p.nome}: {p.quantidade_em_estoque} unidade(s) disponível(is), R$ {p.preco:.2f} cada."
    return f"{p.nome}: indisponível no momento."


@as_tool(name="get_cardapio")
def _get_cardapio() -> str:
    lines = ["Cardápio do TasteFast:"]
    for p in produtos.values():
        status = f"{p.quantidade_em_estoque} disponível(is)" if p.quantidade_em_estoque > 0 else "indisponível"
        lines.append(f"  - {p.nome} | R$ {p.preco:.2f} | {status}")
    return "\n".join(lines)


def _itens_validos_set() -> set:
    return {p.descricao.lower() for p in produtos.values()}


# ── Validador de resposta ──────────────────────────────────────────────────

def validate_reply(reply: str, observations: list) -> tuple[bool, str]:
    if not reply or not reply.strip():
        return False, "Resposta vazia."

    reply_low = reply.lower()
    itens_cardapio = _itens_validos_set()

    suspeitos = ["salada", "tomate", "batata", "refrigerante", "pizza", "lasanha", "sushi", "sorvete"]
    invadidos = [s for s in suspeitos if s in reply_low]
    invadidos_validos = [s for s in invadidos if any(s in item for item in itens_cardapio)]
    invasao = [s for s in invadidos if s not in invadidos_validos]
    if invasao:
        return False, (
            f"A resposta menciona itens que NÃO estão no cardápio: {invasao}. "
            "Use APENAS os itens fornecidos nas observações."
        )
    return True, "ok"
