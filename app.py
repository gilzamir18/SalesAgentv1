import asyncio

from agenticblocks.core.graph import WorkflowGraph
from agenticblocks.runtime.executor import WorkflowExecutor
from agenticblocks.blocks.llm.agent import LLMAgentBlock, AgentInput, AgentOutput
from agenticblocks import as_tool
from agenticblocks.utils.parsers import extract_json_plan
from agenticblocks.blocks.patterns.plan_executor import PlanExecutorBlock, PlanExecutorInput

from utils import (
    _consultar_item, _get_cardapio, validate_reply, chat_history,
    _adicionar_item, _remover_item, _ver_carrinho, _fechar_pedido,
    _registrar_endereco, _registrar_pagamento,
    print_agent_response, estado_pedido
)

# ── Observabilidade ────────────────────────────────────────────────────────

class ObservableLLMAgent(LLMAgentBlock):

    async def run(self, input: AgentInput) -> AgentOutput:
        #print("-" * 90)
        #print(f"[{self.name}] Prompt:\n{input.prompt}")
        #print("-" * 90)
        output = await super().run(input)
        if self.name == "planner_agent" and False:
            print("-*-"*20, end=" output ")
            print("-*-"*20)
            print(output)
            print("-*-"*40)
        return output

# ── Loop ───────────────────────────────────────────────────────────────────

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
        #print(f"[Executor output]: {output.response}\n")
        return output.response

    return plan_and_execute_turn


@as_tool(name="get_user_input")
def get_user_input() -> dict:
    print("Você: ", end="", flush=True)
    user_input = input().strip()
    return {"user_message": user_input}


_CONFIRMACOES = {"sim", "ok", "confirmo", "confirmado", "certo", "tá", "ta",
                 "tá bom", "ta bom", "pode ser", "perfeito", "isso", "correto"}

@as_tool(name="check_done")
def check_done(last_message: str = "") -> dict:
    last_user = ""
    for line in reversed(chat_history):
        if line.startswith("User:"):
            last_user = line[len("User:"):].strip().lower()
            break
    if estado_pedido["fechado"] and last_user and (
        last_user in _CONFIRMACOES or any(c in last_user for c in _CONFIRMACOES)
    ):
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
            "Você é a voz do TasteFast (lanchonete). Seu único trabalho é chamar "
            "a tool 'print_agent_response' UMA vez com a mensagem final ao cliente.\n\n"
            "REGRAS:\n"
            "1. OBRIGATÓRIO: chame 'print_agent_response' UMA única vez. Nunca responda "
            "sem chamar essa tool.\n"
            "2. Baseie sua resposta nos 'DADOS REAIS A USAR' e no 'BRIEFING DO PLANNER'. "
            "Se os dados mostrarem confirmação de pedido, endereço, pagamento ou carrinho, "
            "comunique isso ao cliente de forma clara.\n"
            "3. Para cardápio: mencione APENAS itens que apareçam em 'DADOS REAIS A USAR'. "
            "Copie nomes e preços literalmente.\n"
            "4. Se os dados mostrarem que falta endereço ou pagamento, peça ao cliente "
            "a informação que falta.\n"
            "5. Se os dados mostrarem 'Pedido confirmado', transmita essa confirmação "
            "ao cliente com o resumo fornecido.\n"
            "6. Se 'DADOS REAIS A USAR' estiver vazio e o BRIEFING não der orientação, "
            "diga: 'Desculpe, ocorreu um erro. Por favor, repita sua solicitação.'\n"
            "7. Seja breve e amigável em português brasileiro.\n"
            "8. Se o briefing contiver 'RECUSAR', informe que você só pode ajudar "
            "com cardápio, preços e pedidos do TasteFast."
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
            '  - "consultar_item": args = {"item": "<nome>"}. Consulta disponibilidade e preço.\n'
            '  - "adicionar_item": args = {"item": "<nome>", "quantidade": <n>}. Adiciona ao carrinho.\n'
            '  - "remover_item": args = {"item": "<nome>", "quantidade": <n>}. Remove do carrinho.\n'
            '  - "ver_carrinho": args = {}. Exibe o conteúdo atual do carrinho.\n'
            '  - "registrar_endereco": args = {"endereco": "<endereço completo>"}. Registra o endereço de entrega.\n'
            '  - "registrar_pagamento": args = {"forma": "<forma de pagamento>"}. Registra a forma de pagamento (pix, cartão, dinheiro).\n'
            '  - "fechar_pedido": args = {}. Finaliza o pedido (exige endereço e pagamento já registrados).\n'
            '  - "reply": args = {"message": "<briefing curto para o executor>"}. '
            "SEMPRE o último passo.\n\n"
            "REGRAS:\n"
            "1. SEMPRE termine com um passo 'reply'.\n"
            "2. Se a mensagem mencionar cardápio, menu, opções, 'o que tem', 'o que vocês têm', "
            "inclua 'get_cardapio' antes do 'reply'. Esta regra tem prioridade sobre a regra 7.\n"
            "3. Se perguntou sobre um item específico, use 'consultar_item'.\n"
            "4. Se quiser adicionar/remover itens, use 'adicionar_item'/'remover_item'.\n"
            "5. Se quiser ver o carrinho, use 'ver_carrinho'.\n"
            "6. Se o usuário informar um endereço de entrega, use 'registrar_endereco'.\n"
            "6b. Se o usuário disser 'dinheiro', 'pix', 'cartão', 'crédito' ou 'débito', "
            "use 'registrar_pagamento' com essa forma. Depois, se endereço já foi informado no histórico, "
            "adicione 'fechar_pedido' na sequência.\n"
            "6c. Para fechar/confirmar o pedido, use 'fechar_pedido'. Se a resposta de 'fechar_pedido' "
            "indicar que falta endereço ou pagamento, inclua no 'reply' um briefing pedindo a informação "
            "que falta. NÃO chame 'fechar_pedido' novamente no mesmo plano.\n"
            "7. Se for APENAS saudação/despedida/agradecimento (sem pedido de informação), vá direto ao 'reply'.\n"
            "8. Nunca invente ações fora da lista acima.\n"
            "9. Saída: APENAS o JSON, sem ```, sem comentários, sem texto extra.\n"
            "10. Se a mensagem NÃO for relacionada à lanchonete (cardápio, pedidos, "
            "preços, carrinho), use APENAS 'reply' com briefing "
            "'RECUSAR: assunto fora do escopo da lanchonete'.\n"
            "11. Se o usuário perguntar sobre o status ou andamento do pedido "
            "(ex: 'como está meu pedido', 'o que pedi'), use 'ver_carrinho' antes do 'reply'."
        ),
        tools=[],
        max_iterations=1,
        litellm_kwargs={"temperature": 0.0},
    )

    plan_executor = PlanExecutorBlock(
        executor_agent=executor_agent, 
        tools=[_get_cardapio, _consultar_item, _adicionar_item, _remover_item, _ver_carrinho,
               _registrar_endereco, _registrar_pagamento, _fechar_pedido],
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
