# LLM Integration Architecture — hitech_automation_ai.1.3.x

This document explains **how the hiTech Automation AI Web app integrates with
multiple LLM providers** (currently Ollama and Anthropic Claude) and how the
chat panel can switch between them per-message. Read this if you want to
understand the codebase, add a new provider, or troubleshoot a failure.

---

## 1. The big picture

Both the chat panel UI and the agentic loop talk to a **single abstract
interface** — `ChatProvider`. The actual implementation behind that interface
is picked at runtime based on the model name you select.

```
                ┌─────────────────────────────────────┐
                │       chat panel (browser)          │
                │  picks model from dropdown:         │
                │  • qwen2.5-coder:7b   (local)       │
                │  • gpt-oss:20b        (local)       │
                │  • claude-sonnet-4-6  (cloud)       │
                │  • claude-opus-4-7    (cloud)       │
                └────────────────┬────────────────────┘
                                 │  POST /api/chat
                                 ▼
                ┌─────────────────────────────────────┐
                │           main.py (FastAPI)         │
                │  inspects model name:               │
                │   starts with "claude-" → cloud     │
                │   else → local                      │
                └────────┬─────────────────┬──────────┘
                         │                 │
            ┌────────────▼──────┐  ┌───────▼──────────────┐
            │  OllamaProvider   │  │  AnthropicProvider   │
            │  (HTTP, no auth)  │  │  (SDK, API key auth) │
            └────────┬──────────┘  └──────────┬───────────┘
                     │                        │
                     ▼                        ▼
            ┌──────────────────┐   ┌──────────────────────┐
            │  localhost:11434 │   │ api.anthropic.com    │
            │  (Ollama server) │   │ (cloud Claude API)   │
            └──────────────────┘   └──────────────────────┘
```

This is the **provider abstraction pattern**. Adding a new LLM (OpenAI,
Cohere, Mistral, local llama.cpp, etc.) means writing ~150 lines that
implement `ChatProvider` — no changes to the chat UI, RAG, or agent.

---

## 2. File map — what lives where

```
build/
├── main.py                            FastAPI app, HTTP routes
├── agent.py                           ReAct loop (tool-calling orchestrator)
├── llm_providers/                     ⬅ all LLM integration code
│   ├── __init__.py                    package init, exports
│   ├── base.py                        ChatProvider interface + data classes
│   ├── ollama_provider.py             local Ollama HTTP API
│   └── anthropic_provider.py          cloud Claude (SDK)
├── tools/                             agentic tool implementations (v1.3.0+)
│   ├── definitions.py                 JSON schemas for what the LLM can call
│   └── executor.py                    actual tool runners with safety guards
├── rag_builder.py                     standalone script: build vector DB
├── rag_retriever.py                   runtime helper: query vector DB
├── templates/index.html               chat panel UI + model dropdown
└── requirements.txt                   anthropic, httpx, chromadb, ...
```

### Where each LLM responsibility lives

| What | File | Why there |
|---|---|---|
| Decide which provider for a model name | `main.py: _resolve_provider()` | Single decision point |
| Talk to Ollama HTTP API | `llm_providers/ollama_provider.py` | Encapsulated |
| Talk to Claude API via SDK | `llm_providers/anthropic_provider.py` | Encapsulated |
| Common data shapes (`ChatMessage`, `ChatResponse`, `ToolDefinition`, `ToolCall`) | `llm_providers/base.py` | Shared by all providers |
| Multi-turn agentic loop | `agent.py` | Provider-agnostic |
| RAG retrieval (chunks from corpus) | `rag_retriever.py` | Provider-agnostic |
| Cost calculation for paid APIs | `anthropic_provider.py: PRICING` | Provider-specific |
| Where Anthropic SDK reads the API key from | `anthropic_provider.py: __init__` | Centralized |

---

## 3. The `ChatProvider` interface

This is the abstract base class every provider implements. From
`llm_providers/base.py`:

```python
class ChatProvider(ABC):

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def is_available(self) -> bool:
        """Quick check: configured and reachable?"""
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        """Models the user can pick from."""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        tools: Optional[list[ToolDefinition]] = None,
    ) -> ChatResponse:
        """Send messages, return normalized response. May emit tool calls."""
        ...

    def estimate_cost(self, model, input_tokens, output_tokens) -> Optional[float]:
        """Override for paid providers. Return None for free local models."""
        return None
```

Every method has the same signature regardless of which LLM is behind it.
That's the contract. The frontend never knows or cares which provider is
serving its request.

### The shared data shapes

```python
@dataclass
class ChatMessage:
    role: str                       # "system" | "user" | "assistant" | "tool"
    content: str
    tool_calls: list[ToolCall] = []
    tool_call_id: str | None = None

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict                # JSON schema

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class ChatResponse:
    content: str
    model: str
    provider: str                   # "ollama" | "anthropic"
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    eval_duration_ms: float | None
    tool_calls: list[ToolCall] = []
    stop_reason: str | None
```

`ChatMessage` going in, `ChatResponse` coming out. The same types are used by
every provider — the providers internally translate to and from their native
API formats.

---

## 4. The Ollama provider — `ollama_provider.py`

Ollama runs as a local HTTP server on port 11434. **No authentication.** Just
JSON over HTTP.

### How requests flow

```
chat() called
   │
   ▼
build payload:
{
  "model": "gpt-oss:20b",
  "messages": [{"role":"system","content":"..."}, ...],
  "stream": false,
  "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": 4096},
  "tools": [...]   ⬅ optional, only when agent mode
}
   │
   ▼
POST http://127.0.0.1:11434/api/chat
   │
   ▼
parse response:
{
  "message": {"role":"assistant", "content":"...", "tool_calls":[...]},
  "prompt_eval_count": 142,    ⬅ input tokens
  "eval_count": 387,           ⬅ output tokens
  ...
}
   │
   ▼
return ChatResponse with cost_usd=None (it's free)
```

### Tool calling

Ollama uses an **OpenAI-compatible** tool format:

```python
"tools": [
  {
    "type": "function",
    "function": {
      "name": "run_show_command",
      "description": "...",
      "parameters": {"type": "object", "properties": {...}}
    }
  }
]
```

Responses with tool calls look like:

```python
"message": {
  "role": "assistant",
  "content": "I'll check that...",
  "tool_calls": [
    {"function": {"name": "run_show_command", "arguments": {...}}}
  ]
}
```

Note: Ollama doesn't assign IDs to tool calls — we generate them in
`ollama_provider.py`:

```python
ToolCall(id=f"call_{uuid.uuid4().hex[:12]}", ...)
```

### No auth, but you can override the URL

```bash
# Default behaviour
OllamaProvider()  # → talks to http://127.0.0.1:11434

# Talk to Ollama on the Windows host instead
export OLLAMA_URL="http://192.168.1.10:11434"
```

---

## 5. The Anthropic provider — `anthropic_provider.py`

Anthropic uses the official `anthropic` Python SDK. **Requires an API key.**

### The API key flow — start to finish

```
┌──────────────────────────────────────────────────────────────┐
│ STEP 1: User generates key at console.anthropic.com          │
│         Format: sk-ant-api03-XXXXX (~108 characters)         │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 2: User stores key in .envrc (per-project)              │
│                                                              │
│  ~/DevnetExpert/mock3/software_ai/.envrc:                    │
│    source .../venv/bin/activate                              │
│    export ANTHROPIC_API_KEY="sk-ant-api03-..."               │
│                                                              │
│  chmod 600 .envrc       ⬅ user-only readable                │
│  echo .envrc >> .gitignore  ⬅ never commit                  │
│  direnv allow                                                │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 3: When user `cd`s into the directory:                  │
│   direnv runs .envrc → ANTHROPIC_API_KEY now in shell env    │
│                                                              │
│   But systemd doesn't inherit the shell env, so we need…     │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 4: User stores key in systemd drop-in (for the service) │
│                                                              │
│  ~/.config/systemd/user/hitech_automation_ai.service.d/            │
│      secrets.conf:                                           │
│    [Service]                                                 │
│    Environment="ANTHROPIC_API_KEY=sk-ant-api03-..."          │
│                                                              │
│  chmod 600 secrets.conf                                      │
│  systemctl --user daemon-reload                              │
│  systemctl --user restart hitech_automation_ai                     │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 5: When systemd starts uvicorn (the hitech_automation_ai service):    │
│   ANTHROPIC_API_KEY is in the process environment            │
│                                                              │
│   Python's main.py imports AnthropicProvider                 │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 6: anthropic_provider.py reads it once at import time:  │
│                                                              │
│   class AnthropicProvider:                                   │
│       def __init__(self):                                    │
│           self.api_key = os.environ.get(                     │
│               "ANTHROPIC_API_KEY", "").strip()               │
│           if self.api_key:                                   │
│               self._client = anthropic.AsyncAnthropic(       │
│                   api_key=self.api_key                       │
│               )                                              │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 7: Every Claude request goes through self._client       │
│   The SDK puts the key in the `x-api-key` HTTP header        │
│   when calling https://api.anthropic.com                     │
│                                                              │
│   (We never log the key, never echo it, never send it back   │
│    in error messages, never store it in the DB.)             │
└──────────────────────────────────────────────────────────────┘
```

### Two storage locations — why?

| Where | Used by | When loaded |
|---|---|---|
| `.envrc` (direnv) | Your interactive shell, `curl` testing, scripts run from terminal | When you `cd` into the project dir |
| `secrets.conf` (systemd drop-in) | The running `hitech_automation_ai` service | When systemd starts the service |

The service runs in its own isolated process environment, separate from your
shell. It doesn't inherit `ANTHROPIC_API_KEY` from your `~/.bashrc` or direnv.
That's why we need to tell systemd explicitly.

### How the request is sent

```python
async def chat(self, messages, model, max_tokens, temperature, tools):
    # 1. Translate ChatMessage list → Anthropic SDK format
    full_system, chat_msgs = self._to_anthropic_messages(messages)
    # Claude requires `system` as a separate parameter, not a role in messages
    
    # 2. Build kwargs
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": chat_msgs,
    }
    if not is_no_temperature_model(model):  # Opus 4.7 rejects temperature
        kwargs["temperature"] = temperature
    if full_system:
        kwargs["system"] = full_system
    if tools:
        kwargs["tools"] = self._to_anthropic_tools(tools)
    
    # 3. Call the SDK (which handles HTTP, auth header, retries)
    response = await self._client.messages.create(**kwargs)
    
    # 4. Parse the response content blocks
    #    - "text" blocks → assistant message text
    #    - "tool_use" blocks → ToolCall objects
    
    # 5. Calculate cost from usage tokens
    cost = self.estimate_cost(model, usage.input_tokens, usage.output_tokens)
    
    # 6. Return normalized ChatResponse
```

### Pricing — `PRICING` dict

```python
PRICING = {
    "claude-haiku-4-5":  {"input": 1.0,  "output": 5.0},   # $/M tokens
    "claude-sonnet-4-6": {"input": 3.0,  "output": 15.0},
    "claude-opus-4-7":   {"input": 5.0,  "output": 25.0},
}
```

When Anthropic changes prices, this is the **only file** that needs editing.
Cost is computed per-response:

```python
def estimate_cost(self, model, input_tokens, output_tokens):
    rates = PRICING[model]
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
```

### Tool calling — `tool_use` blocks

Claude's tool format is different from OpenAI/Ollama:

```python
"tools": [
  {
    "name": "run_show_command",
    "description": "...",
    "input_schema": {"type": "object", "properties": {...}}
  }
]
```

Responses with tool calls have **structured content blocks**:

```python
response.content = [
  TextBlock(text="I'll check the BGP state..."),
  ToolUseBlock(id="toolu_01abc", name="run_show_command",
               input={"command": "show ip bgp summary"})
]
```

When sending the tool's result back, we have to:
1. Echo back the original `assistant` message with its `tool_use` block(s)
2. Send a `user` message containing a `tool_result` block with the matching `tool_use_id`

This is more rigid than Ollama's flat format. The translation logic is in
`_to_anthropic_messages()` inside `anthropic_provider.py`.

---

## 6. Request routing — `main.py: _resolve_provider()`

The dropdown shows models from both providers in one list. When the user
clicks Send, the backend decides which provider to use based on the model
name.

```python
# main.py

def _resolve_provider(model: str) -> ChatProvider:
    """Pick a provider based on the model name."""
    if model.startswith("claude-"):
        return _anthropic
    return _ollama
```

This is the only place in the codebase that "knows" the difference between
providers. Everything else uses the abstract `ChatProvider` interface.

To add a new provider (say, OpenAI):

```python
def _resolve_provider(model: str) -> ChatProvider:
    if model.startswith("claude-"):
        return _anthropic
    if model.startswith("gpt-") or model.startswith("o1-") or model.startswith("o4-"):
        return _openai          # ← add this
    return _ollama
```

That's the entire integration point. No other change needed.

---

## 7. RAG works identically across providers

The RAG retrieval is provider-agnostic. The retrieved chunks are inserted as
a `system` role message in the conversation history:

```python
# main.py: _do_chat() simplified
provider_msgs = [
    ChatMessage(role="system", content=SYSTEM_PROMPT),
]
if use_rag:
    chunks = await rag_retriever.retrieve(last_user_message, k=5)
    provider_msgs.append(
        ChatMessage(role="system", content=format_for_prompt(chunks))
    )
# ... add user history ...

response = await provider.chat(provider_msgs, model=model)
```

Both `OllamaProvider` and `AnthropicProvider` handle `system` messages
correctly:

- Ollama keeps them in the `messages` array as `role:"system"`
- Anthropic moves them into the separate `system` parameter

You don't write that logic twice — each provider's `chat()` method does it
once.

---

## 8. Agentic tool calling — provider-agnostic too

The ReAct loop in `agent.py` is the same for any provider:

```python
async def run_agent(provider, model, messages, tools, max_iterations=8):
    history = messages.copy()
    
    for iteration in range(max_iterations):
        response = await provider.chat(history, model=model, tools=tools)
        
        if not response.tool_calls:
            return response.content    # final answer
        
        # Append the assistant's turn (text + tool_calls) to history
        history.append(ChatMessage(
            role="assistant",
            content=response.content,
            tool_calls=response.tool_calls,
        ))
        
        # Execute each tool, append result as a tool-role message
        for tc in response.tool_calls:
            output, is_error = await execute_tool(tc, device_ctx)
            history.append(ChatMessage(
                role="tool",
                content=output,
                tool_call_id=tc.id,
            ))
    # ... max iterations hit ...
```

The provider's `chat()` method handles the API-specific translation:

- For **Ollama**, role="tool" messages are sent natively as `role:"tool"`.
- For **Anthropic**, role="tool" messages are translated into `role:"user"` with a `tool_result` content block (because that's what Claude expects).

This translation happens entirely inside the provider — `agent.py` never sees
the API-specific shape.

---

## 9. What never crosses the LLM boundary

Some data must never reach the LLM, regardless of provider:

| Sensitive data | Where it's protected |
|---|---|
| Device passwords | `DeviceContext.password` is stored but never included in tool output. `describe_device` returns `"password is set: yes"` only. |
| API keys | Read from env, used by SDK internally. Never serialized into messages or tool output. |
| Enable secret | Same as password — held in `DeviceContext` but not echoed. |
| User's other secrets | None held by the app currently — `.envrc` is the only secret store. |

The boundary is enforced inside `tools/executor.py`:

```python
async def _tool_describe_device(args, ctx):
    return (
        f"- host: {ctx.host}\n"
        f"- username: {ctx.username}\n"
        f"- (password is set: {'yes' if ctx.password else 'no'})\n"
        # password and secret intentionally NOT included
    )
```

---

## 10. How to add a new LLM provider — step by step

Suppose you want to add **OpenAI** (or any other OpenAI-compatible API like
Together AI, Groq, OpenRouter, Mistral, etc.).

### Step 1: Create `llm_providers/openai_provider.py`

```python
from typing import Optional
from openai import AsyncOpenAI
from .base import ChatMessage, ChatProvider, ChatResponse, ProviderError

PRICING = {
    "gpt-4o":      {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
}

SUPPORTED_MODELS = ["gpt-4o", "gpt-4o-mini"]


class OpenAIProvider(ChatProvider):
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self._client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

    @property
    def name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        return bool(self.api_key and self._client)

    async def list_models(self) -> list[str]:
        return list(SUPPORTED_MODELS) if self.is_available() else []

    async def chat(self, messages, model, max_tokens=4096, temperature=0.2, tools=None):
        # ... translate ChatMessage → OpenAI format ...
        # ... call self._client.chat.completions.create(...) ...
        # ... return ChatResponse ...

    def estimate_cost(self, model, input_tokens, output_tokens):
        # ... lookup PRICING, return USD ...
```

### Step 2: Register it in `llm_providers/__init__.py`

```python
from .openai_provider import OpenAIProvider
```

### Step 3: Instantiate in `main.py`

```python
_ollama = OllamaProvider(url=OLLAMA_URL)
_anthropic = AnthropicProvider()
_openai = OpenAIProvider()      # ← add this

def _resolve_provider(model: str):
    if model.startswith("claude-"):
        return _anthropic
    if model.startswith("gpt-") or model.startswith("o1-"):
        return _openai          # ← add this
    return _ollama
```

### Step 4: Add to `/api/models` endpoint

```python
"providers": {
    "ollama": {...},
    "anthropic": {...},
    "openai": {                 # ← add this block
        "available": _openai.is_available(),
        "models": await _openai.list_models(),
        "label": "Cloud (OpenAI)",
        "is_cloud": True,
    },
},
```

### Step 5: Add to systemd secrets

```ini
# ~/.config/systemd/user/hitech_automation_ai.service.d/secrets.conf
[Service]
Environment="ANTHROPIC_API_KEY=sk-ant-..."
Environment="OPENAI_API_KEY=sk-..."          # ← add this
```

That's it. The chat UI dropdown picks it up automatically (via `/api/models`),
the badge logic recognizes the cloud nature, RAG works identically, the agent
loop works identically.

---

## 11. Common questions

### Why a provider abstraction?

Without it, every LLM-using piece of code would have provider-specific
branches:

```python
# bad — every endpoint has to know providers
if model.startswith("claude-"):
    # 50 lines of Anthropic SDK code
else:
    # 50 lines of Ollama HTTP code
```

With the abstraction, the provider details are encapsulated, and every
caller just does:

```python
response = await provider.chat(messages, model=model)
```

### Why per-message provider switching?

Because different models excel at different things:

- **Ollama gpt-oss:20b** — fast, free, offline. Good for routine work.
- **Claude Sonnet 4.6** — best accuracy on YANG / NETCONF / network gear.
  Worth paying for hard tasks.
- **Claude Opus 4.7** — frontier reasoning. Use for multi-step thinking.
- **Claude Haiku 4.5** — cheap, fast. Good for simple lookups.

Per-message switching lets the user A/B test on real work without restarting
anything.

### Why are some Claude models in the dropdown but not others?

The `SUPPORTED_MODELS` list in `anthropic_provider.py` controls what shows up.
Older models (Sonnet 3.5, Haiku 3.5) are intentionally hidden — they're
deprecated for new development. Add or remove model strings here as Anthropic
releases new ones.

### What happens if `ANTHROPIC_API_KEY` isn't set?

`AnthropicProvider.is_available()` returns `False`. The `/api/models` endpoint
omits Claude models. The dropdown only shows local Ollama models. No crash.
The app degrades gracefully.

### Can I rotate the API key without restarting?

No. The key is read once at module import time. After rotating in
`.envrc` and `secrets.conf`, you need:

```bash
direnv allow
systemctl --user daemon-reload
systemctl --user restart hitech_automation_ai
```

This is intentional — re-reading the env on every request would be a security
and performance concern.

### What if I want to use my Claude Max subscription instead of a separate API account?

You can't. The web subscription (claude.ai Pro/Max) and the API are
completely separate Anthropic products with separate billing. The API requires
its own account at console.anthropic.com with its own credit card. There's no
way to bridge them.

---

## 12. Summary — the key takeaways

1. **One interface, many implementations.** `ChatProvider` is the contract.
2. **Provider chosen per-message** by inspecting the model name prefix.
3. **Ollama** = HTTP, no auth, local, free.
4. **Anthropic** = SDK, API key in env, cloud, billed per token.
5. **API key flows** from `.envrc` (shell) → `secrets.conf` (systemd) →
   process env → `os.environ` → `AsyncAnthropic(api_key=...)`.
6. **RAG** prepends retrieved chunks as a `system` role message —
   identical handling across providers.
7. **Agent loop** is provider-agnostic; per-provider translation lives
   inside `chat()`.
8. **Sensitive data** (passwords, keys) never crosses into LLM messages
   or tool output.
9. **Adding a new provider** = ~150 lines in a new file + 4 small edits
   to `main.py` and `__init__.py`.
10. **Pricing** lives in a dict in the provider file — one place to update.

For the full code, see:

- `build/llm_providers/base.py`
- `build/llm_providers/ollama_provider.py`
- `build/llm_providers/anthropic_provider.py`
- `build/main.py` (look for `_resolve_provider` and `_do_chat`)
- `build/agent.py` (provider-agnostic agent loop)
