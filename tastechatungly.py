import asyncio
import json
import re
from agenticblocks.core.graph import WorkflowGraph
from agenticblocks.runtime.executor import WorkflowExecutor
from agenticblocks.blocks.llm.agent import LLMAgentBlock, AgentInput, AgentOutput
from agenticblocks import as_tool


chat_history: list[str] = []
_confirmed = False

# ── Banco de dados simulado ────────────────────────────────────────────────

quantidade = {
    "cheeseburger": 10,
    "Pão de Queijo": 10,
    "Suco de laranja": 1,
    "Suco de goiaba": 0,
    "Suco de Limão": 2,
}

preco = {
    "cheeseburger": 12.0,
    "Pão de Queijo": 8.0,
    "Suco de laranja": 9.0,
    "Suco de goiaba": 8.0,
    "Suco de Limão": 6.0,
}

# ── Ferramentas ────────────────────────────────────────────────────────────

@as_tool
def consultar_item(item: str) -> str:
    """Consulta disponibilidade e preço de um item do cardápio."""
    item_upper = item.strip().upper()
    for k in quantidade:
        if item_upper == k.upper() or item_upper in k.upper() or k.upper() in item_upper:
            qty = quantidade[k]
            price = preco[k]
            if qty > 0:
                return f"{k}: {qty} unidade(s) disponível(is), R$ {price:.2f} cada."
            return f"{k}: indisponível no momento."
    return f"Item '{item}' não encontrado no cardápio."


@as_tool
def exibir_menu() -> str:
    """Retorna o cardápio completo com preços e disponibilidade."""
    lines = ["=== Cardápio ==="]
    for item in quantidade:
        status = "disponível" if quantidade[item] > 0 else "indisponível"
        lines.append(f"  - {item}: R$ {preco[item]:.2f} ({status})")
    return "\n".join(lines)


@as_tool
def get_cardapio() -> str:
    """Retorna o cardápio do dia com todos os itens, preços e disponibilidade. Use sempre que o cliente perguntar sobre opções, menu ou cardápio."""
    lines = ["=== Cardápio do TasteFast ==="]
    for item in quantidade:
        qty = quantidade[item]
        price = preco[item]
        status = f"{qty} unidade(s) disponível(is)" if qty > 0 else "indisponível no momento"
        lines.append(f"  - {item}: R$ {price:.2f} — {status}")
    lines.append("\nO que você gostaria de pedir?")
    return "\n".join(lines)


@as_tool(name="get_user_input")
def get_user_input() -> str:
    """Lê a próxima mensagem do usuário e retorna o histórico completo."""
    print("\nVocê: ", end="", flush=True)
    user_input = input()
    chat_history.append(f"User: {user_input}")
    hist = "\n".join(chat_history)
    return f"{hist}\n\n>>> CLASSIFIQUE ESTA MENSAGEM: {user_input}"


@as_tool(name="check_intention")
def check_intention(last_message: str) -> dict:
    """Valida se a LLM classificou corretamente a intenção do usuário."""
    global _confirmed

    # Literal /confirm no input do usuário
    for line in reversed(chat_history):
        if line.startswith("User: "):
            if "/confirm" in line:
                _confirmed = True
                return {"is_valid": True, "feedback": "Usuário confirmou o pedido."}
            break

    if not last_message:
        return {"is_valid": False, "feedback": "Sem resposta da LLM de intenção."}

    confirmar_match = re.search(r'confirmar\s*=\s*\[([^\]]*)\]', last_message, re.IGNORECASE)
    menu_match = re.search(r'menu\s*=\s*\[([^\]]*)\]', last_message, re.IGNORECASE)
    pedido_match = re.search(r'pedido\s*=\s*\[([^\]]+)\]', last_message, re.IGNORECASE)
    consulta_match = re.search(r'consulta\s*=\s*\[([^\]]+)\]', last_message, re.IGNORECASE)

    if confirmar_match:
        _confirmed = True
        return {"is_valid": True, "feedback": "Usuário quer confirmar/fechar o pedido."}

    if menu_match:
        return {"is_valid": True, "feedback": "Exibir cardápio completo."}

    if pedido_match:
        items = [i.strip() for i in pedido_match.group(1).split(',')]
        return {"is_valid": True, "feedback": f"Pedir: {', '.join(items)}"}

    if consulta_match:
        items = [i.strip() for i in consulta_match.group(1).split(',')]
        return {"is_valid": True, "feedback": f"Consultar: {', '.join(items)}"}

    # Fallback: analisa a mensagem bruta do usuário antes de desistir
    last_user_msg = ""
    for line in reversed(chat_history):
        if line.startswith("User: "):
            last_user_msg = line[6:].lower()
            break

    _menu_keywords = [
        "cardápio", "cardapio", "menu", "opções", "opcoes",
        "o que tem", "o que vocês têm", "o que voces tem",
        "o que você serve", "o que voce serve", "quais são", "quais sao",
        "me mostra", "ver o", "ver os", "listar", "lista",
    ]
    _confirm_keywords = [
        "confirmar", "fechar", "encerrar", "finalizar", "pode fechar",
        "isso mesmo", "tá bom", "ta bom", "ok", "sim", "quero fechar",
    ]
    _pedido_keywords = ["quero", "pedir", "me dá", "me da", "me traz", "traz", "queria"]

    if any(kw in last_user_msg for kw in _confirm_keywords):
        _confirmed = True
        return {"is_valid": True, "feedback": "Usuário quer confirmar/fechar o pedido."}

    if any(kw in last_user_msg for kw in _menu_keywords):
        return {"is_valid": True, "feedback": "Exibir cardápio completo."}

    if any(kw in last_user_msg for kw in _pedido_keywords):
        return {"is_valid": True, "feedback": f"Pedir: {last_user_msg}"}

    hist = "\n".join(chat_history)
    return {
        "is_valid": False,
        "feedback": f"Intenção não identificada. Peça ao usuário para reformular.\nHistórico:\n{hist}",
    }


@as_tool(name="check_done")
def check_done() -> dict:
    """Verifica se o pedido foi confirmado (flag global ou /confirm literal)."""
    if _confirmed:
        return {"is_valid": True, "feedback": "Pedido confirmado!"}
    hist = "\n".join(chat_history)
    return {"is_valid": False, "feedback": f"Histórico:\n{hist}"}


# ── Agente com log de debug ────────────────────────────────────────────────

def _clean_response(text: str) -> str:
    """Extrai texto puro de respostas JSON acidentais como {"content": "..."}."""
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            for key in ("content", "response", "text", "message"):
                if key in data and isinstance(data[key], str):
                    return data[key]
        except (json.JSONDecodeError, ValueError):
            pass
    return text


class ObservableLLM(LLMAgentBlock):
    async def run(self, input: AgentInput) -> AgentOutput:
        output = await super().run(input)
        response = _clean_response(output.response or "")
        if response:
            print(f"\nVendedor: {response}")
            chat_history.append(f"Vendedor: {response}")
        return AgentOutput(response=response, tool_calls_made=output.tool_calls_made)


# ── Workflow ───────────────────────────────────────────────────────────────

async def main():

    model = "gemini/gemini-3-flash-preview"

    graph = WorkflowGraph()

    intention_agent = LLMAgentBlock(
        name="intention_agent",
        description="Classifica a intenção da última mensagem do usuário.",
        model=model,
        system_prompt=(
            "Você classifica a intenção do cliente em um fast food.\n\n"
            "No texto recebido há uma linha que começa com '>>> CLASSIFIQUE ESTA MENSAGEM:'. "
            "Leia APENAS essa linha e responda com UMA das quatro opções abaixo. Ignore todo o resto.\n\n"
            "FORMATOS:\n"
            "  pedido=[item1, item2, ...]   -> cliente quer COMPRAR itens\n"
            "  consulta=[item1, ...]        -> cliente pergunta se tem ou qual o preço de um item\n"
            "  menu=[]                      -> cliente quer ver o cardápio ou as opções disponíveis\n"
            "  confirmar=[]                 -> cliente quer fechar, confirmar ou encerrar o pedido\n\n"
            "EXEMPLOS:\n"
            "  'Quero um cheeseburger'        -> pedido=[cheeseburger]\n"
            "  'Me dá dois pães de queijo'    -> pedido=[Pão de Queijo, Pão de Queijo]\n"
            "  'Tem suco de laranja?'         -> consulta=[Suco de laranja]\n"
            "  'Quanto custa o suco?'         -> consulta=[suco]\n"
            "  'O que tem?'                   -> menu=[]\n"
            "  'Quero o cardápio'             -> menu=[]\n"
            "  'Me mostra as opções'          -> menu=[]\n"
            "  'Quais as opções?'             -> menu=[]\n"
            "  'Pode fechar'                  -> confirmar=[]\n"
            "  'Sim, confirma'                -> confirmar=[]\n\n"
            "REGRA FINAL: responda com UMA ÚNICA linha no formato acima. Nunca escreva texto livre."
        ),
    )

    sales_agent = ObservableLLM(
        name="sales_agent",
        description="Atendente de fast food que conversa com o cliente.",
        model=model,
        system_prompt=(
            "Você é um atendente de fast food. Seu objetivo: ajudar o cliente a comprar.\n\n"
            "Você recebe uma instrução de ação. Siga exatamente o passo a passo abaixo.\n\n"
            "SE a instrução começa com 'Pedir:':\n"
            "  1. Chame consultar_item para cada item mencionado.\n"
            "  2. Informe se está disponível e o preço.\n"
            "  3. Pergunte: 'Posso confirmar seu pedido?'\n\n"
            "SE a instrução começa com 'Consultar:':\n"
            "  1. Chame consultar_item para o item.\n"
            "  2. Informe a disponibilidade e o preço.\n"
            "  3. Pergunte: 'Quer incluir no pedido?'\n\n"
            "SE a instrução é 'Exibir cardápio completo.':\n"
            "  1. Chame get_cardapio.\n"
            "  2. Mostre os itens disponíveis.\n"
            "  3. Pergunte: 'O que você vai querer?'\n\n"
            "SE a instrução começa com 'Intenção não identificada':\n"
            "  1. Chame get_cardapio.\n"
            "  2. Mostre os itens disponíveis.\n"
            "  3. Pergunte: 'O que você gostaria de pedir?'\n\n"
            "SE a instrução é 'Usuário quer confirmar/fechar o pedido.':\n"
            "  1. Agradeça e confirme que o pedido foi registrado.\n\n"
            "IMPORTANTE:\n"
            "- Use as ferramentas ANTES de escrever sua resposta.\n"
            "- Nunca comece com 'Olá' ou cumprimentos — vá direto ao assunto.\n"
            "- Escreva apenas texto na resposta final. Nunca chame ferramentas para responder.\n"
            "- Responda sempre em português."
        ),
        tools=[consultar_item, exibir_menu, get_cardapio],
        max_iterations=4,
        max_tool_calls=3,
        on_max_iterations="return_last",
        litellm_kwargs={"temperature": 0.7},
    )

    graph.add_block(get_user_input)
    graph.add_block(intention_agent)
    graph.add_block(check_intention)
    graph.add_block(sales_agent)
    graph.add_block(check_done)

    # Loop interno: coleta input → classifica intenção → valida
    graph.add_cycle(
        name="intention_loop",
        sequence=["get_user_input", "intention_agent", "check_intention"],
        condition_block="check_intention",
        max_iterations=5,
    )

    # Loop externo: conversa até /confirm
    graph.add_cycle(
        name="chat_loop",
        sequence=["intention_loop", "sales_agent", "check_done"],
        condition_block="check_done",
        max_iterations=100,
    )

    executor = WorkflowExecutor(graph, verbose=False)

    print("=== Bem-vindo ao TasteFast! ===")
    print("Digite sua mensagem. Para confirmar o pedido, digite /confirm\n")

    ctx = await executor.run(initial_input={"prompt": ""})
    cr = ctx.cycle_results.get("chat_loop")
    if cr:
        print(cr)
        print(f"\n=== Atendimento encerrado após {cr.iterations} interação(ões). ===")


if __name__ == "__main__":
    asyncio.run(main())
