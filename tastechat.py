import asyncio
import json
import re
from agenticblocks.core.graph import WorkflowGraph
from agenticblocks.runtime.executor import WorkflowExecutor
from agenticblocks.blocks.llm.agent import LLMAgentBlock, AgentInput, AgentOutput
from agenticblocks import as_tool
from agenticblocks.utils.parsers import extract_json_plan
from agenticblocks.blocks.patterns.plan_executor import PlanExecutorBlock, PlanExecutorInput


# ── Dados do domínio ───────────────────────────────────────────────────────

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


# ── Funções de domínio (Blocos de Ferramenta) ──────────────────────────────
# Estas são chamadas DIRETAMENTE pelo PlanExecutorBlock.

@as_tool(name="consultar_item")
def _consultar_item(item: str) -> str:
    item_upper = item.strip().upper()
    for k in quantidade:
        if item_upper == k.upper() or item_upper in k.upper() or k.upper() in item_upper:
            qty = quantidade[k]
            price = preco[k]
            if qty > 0:
                return f"{k}: {qty} unidade(s) disponível(is), R$ {price:.2f} cada."
            return f"{k}: indisponível no momento."
    return f"Item '{item}' não encontrado no cardápio."

@as_tool(name="get_cardapio")
def _get_cardapio() -> str:
    lines = ["Cardápio do TasteFast:"]
    for item in quantidade:
        qty = quantidade[item]
        price = preco[item]
        status = f"{qty} disponível(is)" if qty > 0 else "indisponível"
        lines.append(f"  - {item} | R$ {price:.2f} | {status}")
    return "\n".join(lines)


def _itens_validos_set() -> set:
    """Conjunto de nomes de itens em lowercase, para validação."""
    return {k.lower() for k in quantidade}


# ── Estado de conversa ─────────────────────────────────────────────────────

chat_history = []


@as_tool(name="print_agent_response",
         description="Entrega a resposta final ao cliente.")
def print_agent_response(response: str) -> str:
    # Esta é a ÚNICA fonte de impressão da fala do agente.
    print(f"Agent: {response}")
    chat_history.append(f"Agent: {response}")
    return "ok"


# ── Observabilidade ────────────────────────────────────────────────────────

class ObservableLLMAgent(LLMAgentBlock):
    async def run(self, input: AgentInput) -> AgentOutput:
        #print("-" * 90)
        #print(f"[{self.name}] Prompt:\n{input.prompt}")
        #print("-" * 90)
        return await super().run(input)


# Removido extract_json_plan local, agora importado de agenticblocks.utils.parsers
# Removido PlanExecutor local, agora usamos PlanExecutorBlock de agenticblocks.blocks.patterns.plan_executor

# ── Validador determinístico (Output-Gated Loop, Cap. 2.4) ─────────────────

def validate_reply(reply: str, observations: list) -> tuple[bool, str]:
    """
    Confere que a resposta do executor não inventa itens fora do cardápio.
    Retorna (is_valid, feedback).
    """
    if not reply or not reply.strip():
        return False, "Resposta vazia."

    reply_low = reply.lower()
    itens_cardapio = _itens_validos_set()

    # Heurística simples: procurar nomes de itens "fantasma" comuns.
    suspeitos = [
        "frango", "salada", "alface", "tomate", "batata", "refrigerante",
        "pizza", "lasanha", "sushi", "sorvete",
    ]
    invadidos = [s for s in suspeitos if s in reply_low]
    invadidos_validos = [s for s in invadidos
                         if any(s in item for item in itens_cardapio)]
    invasao = [s for s in invadidos if s not in invadidos_validos]
    if invasao:
        return False, (
            f"A resposta menciona itens que NÃO estão no cardápio: {invasao}. "
            f"Use APENAS os itens fornecidos nas observações."
        )

    return True, "ok"



# ── Bloco que roda um turno (plan + execute) ───────────────────────────────

def make_turn_block(planner_agent: LLMAgentBlock, plan_executor: PlanExecutorBlock):

    @as_tool(name="plan_and_execute_turn",
             description="Gera plano JSON e executa.")
    async def plan_and_execute_turn(user_message: str) -> str:
        # Garante que user_message seja string limpa, não dict.
        if isinstance(user_message, dict):
            user_message = user_message.get("user_message") or str(user_message)
        user_message = str(user_message).strip()

        chat_history.append(f"User: {user_message}")

        history_str = "\n".join(chat_history[-8:])
        planner_prompt = (
            f"HISTÓRICO RECENTE:\n{history_str}\n\n"
            f"MENSAGEM DO USUÁRIO: {user_message}\n\n"
            "Produza APENAS o JSON do plano. Sem texto antes ou depois."
        )

        plan_result = await planner_agent.run(AgentInput(prompt=planner_prompt))
        raw = getattr(plan_result, "response", str(plan_result))
        #print(f"\n[Planner bruto]:\n{raw}\n")

        plan = extract_json_plan(raw)
        if plan is None:
            print("[Planner] JSON inválido. Usando fallback.")
            plan = {
                "thought": "fallback",
                "steps": [
                    {"action": "get_cardapio", "args": {}},
                    {"action": "reply", "args": {
                        "message": "Apresente o cardápio ao cliente."
                    }},
                ],
            }

        #print(f"[Plano]:\n{json.dumps(plan, indent=2, ensure_ascii=False)}\n")
        output = await plan_executor.run(PlanExecutorInput(plan=plan, history=history_str))
        return output.response

    return plan_and_execute_turn


# ── Loop ───────────────────────────────────────────────────────────────────

@as_tool(name="get_user_input")
def get_user_input() -> dict:
    print("Você: ", end="", flush=True)
    user_input = input().strip()
    return {"user_message": user_input}


@as_tool(name="check_done")
def check_done(last_message: str = "") -> dict:
    # Decide pelo último input do usuário, lendo do histórico.
    last_user = ""
    for line in reversed(chat_history):
        if line.startswith("User:"):
            last_user = line[len("User:"):].strip()
            break
    if last_user and ("/bye" in last_user.lower() or
                      last_user.lower() in {"sair", "tchau", "fim"}):
        return {"is_valid": True, "feedback": "encerrado"}
    return {"is_valid": False, "feedback": "continuar"}


def build_chat_prompt(orig, iteration, producer, feedback):
    return feedback or ""


# ── Main ───────────────────────────────────────────────────────────────────

async def main():
    print("Bem-vindo ao TasteChat! Pergunte sobre nosso cardápio ou faça seu pedido. ")
    executor_agent = ObservableLLMAgent(
        name="executor_agent",
        model="ollama/mistral-nemo:latest",
        description="Redige a fala final ao cliente, usando exclusivamente os dados fornecidos.",
        system_prompt=(
            "Você é a voz do TasteFast (lanchonete).\n"
            "REGRAS ABSOLUTAS:\n"
            "1. Você SÓ pode mencionar itens, preços e disponibilidade que "
            "apareçam EXATAMENTE em 'DADOS REAIS A USAR'. NUNCA invente itens.\n"
            "2. Copie nomes e preços literalmente. Não traduza, não adapte.\n"
            "3. Se 'DADOS REAIS A USAR' está vazio, peça mais informações ao "
            "cliente em vez de inventar.\n"
            "4. Sempre entregue a resposta chamando a tool "
            "'print_agent_response' UMA única vez.\n"
            "5. Seja breve, amigável, em português brasileiro."
        ),
        tools=[print_agent_response],
        max_tools_calls=1,
        max_iterations=1,
        litellm_kwargs={"temperature": 0.0},
    )

    planner_agent = ObservableLLMAgent(
        name="planner_agent",
        model="ollama/mistral-nemo:latest",
        description="Gera plano JSON.",
        system_prompt=(
            "Você é o Planejador do TasteFast. NÃO fala com o cliente. NÃO chama "
            "ferramentas. Sua ÚNICA saída é um JSON válido.\n\n"
            "Formato OBRIGATÓRIO (apenas JSON, nada mais):\n"
            "{\n"
            '  "thought": "raciocínio breve",\n'
            '  "steps": [ {"action": "<nome>", "args": { ... }} ]\n'
            "}\n\n"
            "AÇÕES DISPONÍVEIS:\n"
            '  - "get_cardapio": args = {}. Retorna o cardápio completo.\n'
            '  - "consultar_item": args = {"item": "<nome>"}. Consulta um item.\n'
            '  - "reply": args = {"message": "<briefing curto para o executor>"}. '
            "SEMPRE o último passo.\n\n"
            "REGRAS:\n"
            "1. SEMPRE termine com um passo 'reply'.\n"
            "2. Se o cliente pediu o cardápio/menu/opções, inclua 'get_cardapio' "
            "antes do 'reply'.\n"
            "3. Se perguntou sobre um item específico, use 'consultar_item'.\n"
            "4. Se for saudação/despedida/agradecimento, vá direto ao 'reply'.\n"
            "5. Nunca invente ações fora da lista acima.\n"
            "6. Saída: APENAS o JSON, sem ```, sem comentários, sem texto extra."
        ),
        tools=[],
        max_iterations=1,
        litellm_kwargs={"temperature": 0.0},
    )

    plan_executor = PlanExecutorBlock(
        executor_agent=executor_agent, 
        tools=[_get_cardapio, _consultar_item],
        validator_fn=validate_reply,
        max_reply_retries=2,
        reply_prompt_template=(
            "BRIEFING DO PLANNER:\n{briefing}\n\n"
            "DADOS REAIS A USAR (copie nomes e preços EXATAMENTE como aparecem):\n{observations}\n\n"
            "HISTÓRICO RECENTE:\n{history}\n\n"
            "{extra_instruction}\n"
            "Agora chame a tool 'print_agent_response' UMA vez com a mensagem final ao cliente."
        )
    )
    turn_block = make_turn_block(planner_agent, plan_executor)

    graph = WorkflowGraph()
    graph.add_block(get_user_input)
    graph.add_block(turn_block)
    graph.add_block(check_done)

    graph.add_cycle(
        name="chat_loop",
        sequence=["get_user_input", "plan_and_execute_turn", "check_done"],
        condition_block="check_done",
        max_iterations=1000,
        augment_fn=build_chat_prompt,
    )

    executor = WorkflowExecutor(graph, verbose=False) #change to True for more logs
    await executor.run(initial_input={"prompt": "início"})


if __name__ == "__main__":
    asyncio.run(main())
