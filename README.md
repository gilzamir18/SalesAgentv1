# SalesAgent v1 — TasteChat

Agente conversacional de atendimento para uma lanchonete fictícia chamada **TasteFast**. O cliente interage em linguagem natural para consultar o cardápio, montar o carrinho, informar endereço e forma de pagamento, e fechar o pedido — tudo via chat no terminal.

## Como funciona

A aplicação usa a biblioteca **agenticblocks** para orquestrar dois agentes LLM em pipeline:

```
Entrada do usuário
      │
      ▼
┌─────────────┐      JSON (plano de ações)     ┌─────────────────┐
│  Planner    │ ──────────────────────────────► │  Plan Executor  │
│  Agent      │                                 │  + Ferramentas  │
└─────────────┘                                 └────────┬────────┘
                                                         │ dados reais
                                                         ▼
                                                ┌─────────────────┐
                                                │ Executor Agent  │
                                                │ (voz do chat)   │
                                                └────────┬────────┘
                                                         │
                                                         ▼
                                                  Resposta ao cliente
```

- **Planner Agent**: recebe a mensagem do usuário e produz um plano em JSON com as ações a executar (ex.: `get_cardapio`, `adicionar_item`, `fechar_pedido`).
- **Plan Executor**: executa cada ação do plano chamando as ferramentas Python (`utils.py`) e coleta os resultados reais.
- **Executor Agent**: recebe o briefing do Planner + os dados reais e redige a resposta final ao cliente.

### Ferramentas disponíveis

| Ferramenta          | Descrição                                      |
|---------------------|------------------------------------------------|
| `get_cardapio`      | Lista todos os itens e preços                  |
| `consultar_item`    | Verifica disponibilidade e preço de um item    |
| `adicionar_item`    | Adiciona item ao carrinho                      |
| `remover_item`      | Remove item do carrinho                        |
| `ver_carrinho`      | Exibe o carrinho atual com totais              |
| `registrar_endereco`| Registra o endereço de entrega                 |
| `registrar_pagamento`| Registra a forma de pagamento (pix/cartão/dinheiro) |
| `fechar_pedido`     | Finaliza o pedido (exige endereço e pagamento) |

## Pré-requisitos

- Python 3.11+
- [agenticblocks](https://github.com/gilzamir18/agenticblocks)
- [LiteLLM](https://docs.litellm.ai/) (instalado como dependência do agenticblocks)

Instale as dependências:

```bash
pip install agenticblocks.io litellm
```

## Executando a aplicação

```bash
python app.py
```

Por padrão, a aplicação usa o modelo **`ollama/mistral-nemo:latest`** rodando localmente via [Ollama](https://ollama.com). Certifique-se de que o servidor Ollama está ativo antes de executar.

---

## Usando um modelo comercial (ex.: Google Gemini)

Para trocar o modelo local por um modelo comercial, basta alterar o parâmetro `model` nos dois agentes em [app.py](app.py) e fornecer a API key correspondente.

### 1. Alterar o modelo em `app.py`

Substitua `"ollama/mistral-nemo:latest"` pelo identificador do modelo desejado. Exemplos com Gemini:

```python
# Antes
model="ollama/mistral-nemo:latest"

# Depois — Gemini via LiteLLM
model="gemini/gemini-2.0-flash"
```

> O LiteLLM suporta vários provedores. Consulte a [lista completa de modelos](https://docs.litellm.ai/docs/providers).

### 2. Configurar a API Key

#### Linux / macOS

Adicione a variável de ambiente ao seu shell (`.bashrc`, `.zshrc` ou `.profile`):

```bash
export GEMINI_API_KEY="sua-chave-aqui"
```

Recarregue o shell:

```bash
source ~/.bashrc   # ou source ~/.zshrc
```

Para definir apenas na sessão atual (sem persistir):

```bash
export GEMINI_API_KEY="sua-chave-aqui"
python app.py
```

#### Windows

**Prompt de Comando (cmd) — sessão atual:**

```cmd
set GEMINI_API_KEY=sua-chave-aqui
python app.py
```

**PowerShell — sessão atual:**

```powershell
$env:GEMINI_API_KEY = "sua-chave-aqui"
python app.py
```

**Definir de forma permanente (via interface gráfica):**

1. Pressione `Win + S` e pesquise por **"Variáveis de ambiente"**.
2. Clique em **"Editar as variáveis de ambiente do sistema"**.
3. Na aba **Avançado**, clique em **"Variáveis de Ambiente..."**.
4. Em **Variáveis do usuário**, clique em **Novo** e preencha:
   - Nome: `GEMINI_API_KEY`
   - Valor: `sua-chave-aqui`
5. Clique em **OK** e reinicie o terminal.

### 3. Outras API keys suportadas pelo LiteLLM

| Provedor        | Variável de ambiente      | Prefixo do modelo         |
|-----------------|---------------------------|---------------------------|
| Google Gemini   | `GEMINI_API_KEY`          | `gemini/...`              |
| OpenAI          | `OPENAI_API_KEY`          | `gpt-4o`, `gpt-4o-mini`   |
| Anthropic Claude| `ANTHROPIC_API_KEY`       | `claude-opus-4-7`, etc.   |
| Groq            | `GROQ_API_KEY`            | `groq/llama-3.1-8b-instant` |

---

## Estrutura do projeto

```
SalesAgentv1/
├── app.py        # Orquestração dos agentes e loop de chat
└── utils.py      # Ferramentas do domínio (cardápio, carrinho, pedido)
```

## Licença

Distribuído para fins educacionais e de demonstração.
