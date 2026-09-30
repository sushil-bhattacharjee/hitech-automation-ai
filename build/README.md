# hiTech Automation AI Web — hitech_automation_ai.1.3.0

Local FastAPI web UI for sending NETCONF/CLI configs to network devices, with
an integrated **agentic AI assistant** that can use local Ollama models OR
the cloud Claude API as its "brain", and call read-only tools to investigate
device state before answering.

## What's new in 1.3.0

🤖 **Agentic mode** — the LLM gets tools:

- `run_show_command` — SSH/CLI to your device, read-only (`show/ping/traceroute` only)
- `search_corpus` — semantic search over your RAG-indexed docs
- `describe_device` — what device is currently configured (no secrets exposed)
- `get_current_template` — your live editor state

Tick the 🤖 Agentic checkbox in chat, ask a question that needs live data
("check why BGP isn't coming up on R1"), and watch the LLM call tools, read
the output, and synthesise an answer. Trace shows every tool call.

## Full feature set

- **NETCONF mode** — Jinja2 → XML → ncclient (port 830)
- **CLI mode** — Jinja2 → CLI → Netmiko (port 22)
- **💬 Chat with AI** with five modes that combine freely (mostly):
  - 📚 **RAG grounding** (chunks from local corpus prepended)
  - ☁️ **Cloud Claude** (Haiku / Sonnet / Opus) OR **local Ollama** (per-message)
  - ⚖️ **Compare** — same prompt to two models, side-by-side
  - 🤖 **Agentic** — LLM calls read-only tools to investigate
  - Cost + token tracking on every response
- **Cloud warning banner** when Claude is selected
- **Resizable chat drawer** + ⛶ Max button

## Quick reference

```bash
systemctl --user start hitech_automation_ai
journalctl --user -u hitech_automation_ai -f
curl -s http://localhost:7071/api/health
# {"ok":true,"version":"hitech_automation_ai.1.3.0"}
```

## Architecture (v1.3.0)

```
build/
├── main.py                       # FastAPI app, routes
├── agent.py                      # ReAct loop orchestrator (NEW in 1.3.0)
├── llm_providers/
│   ├── base.py                   # ChatProvider interface, ToolDefinition, ToolCall
│   ├── ollama_provider.py        # local Ollama HTTP API + tool calling
│   └── anthropic_provider.py     # Claude SDK + tool_use blocks
├── tools/                        # NEW in 1.3.0
│   ├── definitions.py            # tool schemas (read-only)
│   └── executor.py               # actual tool runners (with safety guards)
├── rag_builder.py / rag_retriever.py
└── templates/index.html
```

### Tool calling flow

```
1. User ticks 🤖 Agentic, types: "Why is BGP not coming up on R1?"
2. Frontend POSTs to /api/chat-agent with messages + device_info + template
3. main.py builds a DeviceContext and hands off to agent.run_agent()
4. Loop:
   a) provider.chat(messages, tools=[run_show_command, search_corpus, ...])
   b) if response has tool_calls:
        - execute each via tools/executor.py (with safety + timeout)
        - append tool_result message to history
        - go to (a)
      else:
        - this is the final answer; return
5. Frontend renders the trace + final answer
```

## What's planned next

**hitech_automation_ai.1.4.0** — Write tools + human approval:
- New tools: `propose_netconf_push`, `propose_cli_push`
- Approval modal in UI with full diff before execution
- Audit log: every approved/rejected action saved to a file

See `CHANGELOG.md` for the full version history.
