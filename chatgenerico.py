import asyncio
import os
import sys
from agenticblocks.core.graph import WorkflowGraph
from agenticblocks.runtime.executor import WorkflowExecutor
from agenticblocks.blocks.llm.agent import LLMAgentBlock
from agenticblocks import as_tool
from agenticblocks.blocks.llm.agent import LLMAgentBlock, AgentInput, AgentOutput


def build_chat_prompt(orig, iteration, producer, feedback):
    lines = feedback.splitlines()
    last_user = next((l for l in reversed(lines) if l.startswith("User:")), "")
    return (
        f"{feedback}\n\n"
        f"[Focus on answering: {last_user}]"
    )

class ObservableLLMAgent(LLMAgentBlock):
    async def run(self, input: AgentInput) -> AgentOutput:
        print("----------------------------------------------------------------------------------------------")
        print(f"[{self.name}] Prompt recebido: {input.prompt}")
        print("----------------------------------------------------------------------------------------------")
        return await super().run(input)

chat_history = []

@as_tool(name="check_done")
def check_done(last_message: str) -> dict:
    if last_message and "/bye" in last_message:
        return {"is_valid": True, "feedback": ""}
    hist = "\n".join(chat_history)
    return {"is_valid": False, "feedback": f"history: {hist}"}

@as_tool(name="get_user_input")
def get_user_input() -> dict :
    print("Yocê: ", end="")
    user_input = input()
    chat_history.append(f"User: {user_input}")
    return {"prompt":user_input}

@as_tool(name="print_agent_response", description="Imprime a resposta do agente e adiciona ao histórico de chat")
def print_agent_response(response: str):
    print(f"Agent: {response}")
    chat_history.append(f"Agent: {response}")
    
async def main():
    # Cria o grafo de workflow
    graph = WorkflowGraph()

    # Adiciona o bloco de agente ao grafo
    agent_block = ObservableLLMAgent(
        name="chat_agent",
        model="ollama/mistral-nemo:latest",
        description="Agente de chat para responder perguntas do usuário",
        system_prompt="""Você é um assistente de chat pronto para ajudar com os mais diversos tópicos.
        Use o teu conhecimento intrínseco para responder às perguntas do usuário.
        Você vai ser o primeiro a falar, dê as boas vindas e pergunte:
        Sobre o que minha divindade quer saber?""",
        tools=[print_agent_response],
        max_iterations=1,
        litellm_kwargs={"temperature": 0.7, "tool_choice": {"type": "function", "function": {"name": "print_agent_response"}}}
    )

    graph.add_block(agent_block)
    graph.add_block(get_user_input)
    graph.add_block(check_done)

    graph.add_cycle(
        name="chat_loop",
        sequence=["chat_agent", "get_user_input", "check_done"],
        condition_block="check_done",
        max_iterations=1000,
        augment_fn=build_chat_prompt
    )

    # Cria o executor do workflow
    executor = WorkflowExecutor(graph, verbose=True)

    # Executa o workflow com dados de entrada
    ctx = await executor.run(initial_input={"prompt": "Você está em uma conversa contínua. Responda à mensagem mais recente do histórico."})
    cr  = ctx.cycle_results.get("chat_loop")
    if cr:
        print("Chat session result: ", cr.output)

if __name__ == "__main__":
    asyncio.run(main())