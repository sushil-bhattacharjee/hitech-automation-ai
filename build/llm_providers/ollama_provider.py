"""Ollama provider — talks to a local Ollama server (HTTP)."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Optional

import httpx

from .base import (
    ChatMessage,
    ChatProvider,
    ChatResponse,
    ProviderError,
    ToolCall,
    ToolDefinition,
)


# Approximate characters-per-token ratio (English text averages 4 chars/token).
# Used for the auto-bump heuristic so we can pick a context size that's likely
# to fit the input without overflowing.
CHARS_PER_TOKEN = 4

# Default context window. Most models support up to 128K but allocating that
# much eats RAM, so we tier the value based on actual input size.
DEFAULT_NUM_CTX = 8192

# v1.10.0 (issue-5): user-chosen context window from the chat panel. 0 = let Ollama
# use the model's default. Single-user/localhost app, so a module-level setting set
# per-request by the chat endpoints is sufficient (no per-call threading needed).
_RUNTIME_NUM_CTX = 0


def set_runtime_num_ctx(n: int) -> None:
    """Set the num_ctx applied to subsequent Ollama chat calls (0 disables)."""
    global _RUNTIME_NUM_CTX
    try:
        _RUNTIME_NUM_CTX = max(0, int(n or 0))
    except (TypeError, ValueError):
        _RUNTIME_NUM_CTX = 0


def _estimate_tokens(messages: list[ChatMessage]) -> int:
    """Rough token estimate for the message list."""
    total_chars = sum(len(m.content or "") for m in messages)
    # Add overhead for role tags, system, etc.
    return (total_chars // CHARS_PER_TOKEN) + 100 * len(messages)


def _choose_num_ctx(estimated_input_tokens: int, headroom: int = 2048) -> int:
    """Pick a context size large enough for the input plus generation headroom.

    Returns the smallest standard size (8K / 16K / 32K / 64K) that fits.
    Bigger num_ctx = more RAM, so we only use what's needed.
    """
    needed = estimated_input_tokens + headroom
    if needed <= 8192:   return 8192
    if needed <= 16384:  return 16384
    if needed <= 32768:  return 32768
    if needed <= 65536:  return 65536
    return 131072  # 128K max for most modern models


class OllamaProvider(ChatProvider):

    def __init__(self, url: Optional[str] = None) -> None:
        self.url = (url or os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")).rstrip("/")

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        try:
            r = httpx.get(f"{self.url}/api/tags", timeout=3.0)
            return r.status_code == 200
        except httpx.RequestError:
            return False

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.url}/api/tags")
                r.raise_for_status()
                data = r.json()
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                return sorted(m for m in models if "embed" not in m.lower())
        except httpx.RequestError:
            return []

    def _to_ollama_message(self, m: ChatMessage) -> dict:
        d: dict = {"role": m.role, "content": m.content}
        if m.role == "assistant" and m.tool_calls:
            d["tool_calls"] = [
                {"function": {"name": tc.name, "arguments": tc.arguments}}
                for tc in m.tool_calls
            ]
        return d

    def _to_ollama_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
        tools: Optional[list[ToolDefinition]] = None,
    ) -> ChatResponse:
        # v1.4.0: do NOT force num_ctx. The v1.3.1 forced minimum of 8192 caused two issues:
        #   (1) embedding models like nomic-embed-text (n_ctx_train=2048) emit "context size
        #       too large for model" warnings and run inefficiently;
        #   (2) chat models with 8K num_ctx use more KV cache => slower per-token generation.
        # Letting Ollama pick the model's native default is faster and avoids the warnings.
        # _choose_num_ctx() is kept available for callers that want explicit control.
        est_input = _estimate_tokens(messages)

        payload = {
            "model": model,
            "messages": [self._to_ollama_message(m) for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        # v1.10.0 (issue-5): honor a user-chosen context window when set (>0).
        if _RUNTIME_NUM_CTX > 0:
            payload["options"]["num_ctx"] = _RUNTIME_NUM_CTX
        if tools:
            payload["tools"] = self._to_ollama_tools(tools)

        t0 = time.time()
        try:
            # v1.4.0: 600s timeout gives CPU-bound 14b/20b models room to finish.
            async with httpx.AsyncClient(timeout=600.0) as client:
                r = await client.post(f"{self.url}/api/chat", json=payload)
                r.raise_for_status()
                data = r.json()
        except httpx.ConnectError as e:
            raise ProviderError(
                f"Cannot reach Ollama at {self.url} — is the server running? "
                f"Try: systemctl status ollama   ({e})",
                status_code=503,
            )
        except httpx.ReadTimeout:
            raise ProviderError(
                f"Ollama timed out after 600s. Most common causes:\n"
                f"  1. Model is cold-loading from disk (first call after idle). "
                f"Run `ollama ps` — if the model isn't listed, tick the sysbar "
                f"\"Pin current model (10m keep-alive)\" and pre-warm before retrying.\n"
                f"  2. Model is too large for the hardware (CPU-bound). "
                f"Try a smaller model (e.g. switch from gpt-oss:20b to qwen2.5-coder:7b "
                f"for read-only tasks).\n"
                f"  3. Prompt is too long. Estimated input: {est_input} tokens.\n"
                f"  4. Agentic loop produced a very large response. Lower max_tokens.",
                status_code=504,
            )
        except httpx.HTTPStatusError as e:
            # Try to extract Ollama's error body — much more informative than just the code
            body = ""
            try:
                body = e.response.json().get("error", "")
            except Exception:
                body = e.response.text[:300]
            hint = ""
            if "model not found" in body.lower() or "not found" in body.lower():
                hint = f" — try: ollama pull {model}"
            elif "context length" in body.lower() or "too long" in body.lower():
                hint = (
                    f" — your input (~{est_input} tokens) exceeds the model's context. "
                    f"Untick 'Attach current template + variables' or switch to a "
                    f"Claude model (200K context)."
                )
            elif e.response.status_code == 500:
                hint = (
                    " — Ollama internal error. Often means the model crashed or "
                    "OOMed. Try: ollama stop <other models>, free RAM, retry."
                )
            raise ProviderError(
                f"Ollama returned {e.response.status_code}: {body}{hint}",
                status_code=502,
            )
        except httpx.RequestError as e:
            raise ProviderError(
                f"Ollama request failed: {type(e).__name__}: {e}",
                status_code=502,
            )

        # Validate response shape — Ollama can return 200 with garbage on some errors
        if not isinstance(data, dict) or "message" not in data:
            raise ProviderError(
                f"Unexpected Ollama response shape (no 'message' key). "
                f"Raw: {str(data)[:200]}",
                status_code=502,
            )

        msg = data.get("message", {}) or {}

        tool_calls: list[ToolCall] = []
        for raw in (msg.get("tool_calls") or []):
            fn = raw.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            tool_calls.append(ToolCall(
                id=f"call_{uuid.uuid4().hex[:12]}",
                name=fn.get("name", ""),
                arguments=args,
            ))

        stop = "tool_use" if tool_calls else "end_turn"

        return ChatResponse(
            content=msg.get("content", ""),
            model=data.get("model", model),
            provider=self.name,
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
            cost_usd=None,
            eval_duration_ms=(time.time() - t0) * 1000.0,
            tool_calls=tool_calls,
            stop_reason=stop,
            extra={"estimated_input_tokens": est_input},
        )
