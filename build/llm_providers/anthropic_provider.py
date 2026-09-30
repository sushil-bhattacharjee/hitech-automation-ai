"""Anthropic provider — talks to the Claude API."""

from __future__ import annotations

import os
import time
from typing import Optional

from .base import (
    ChatMessage,
    ChatProvider,
    ChatResponse,
    ProviderError,
    ToolCall,
    ToolDefinition,
)

try:
    import anthropic
    _ANTHROPIC_SDK_AVAILABLE = True
except ImportError:
    _ANTHROPIC_SDK_AVAILABLE = False


# Pricing in USD per million tokens (May 2026)
PRICING = {
    "claude-haiku-4-5":  {"input": 1.0,  "output": 5.0},
    "claude-sonnet-4-6": {"input": 3.0,  "output": 15.0},
    "claude-opus-4-7":   {"input": 5.0,  "output": 25.0},
    "claude-opus-4-6":   {"input": 5.0,  "output": 25.0},
}

SUPPORTED_MODELS = [
    "claude-haiku-4-5",
    "claude-sonnet-4-6",
    "claude-opus-4-7",
]

# Newer reasoning-focused models manage their own sampling internally and
# reject the `temperature` parameter with a 400. Add new model strings here
# if Anthropic deprecates temperature for more models in the future.
NO_TEMPERATURE_MODELS = (
    "claude-opus-4-7",
)


class AnthropicProvider(ChatProvider):

    def __init__(self) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        self._client = None
        if _ANTHROPIC_SDK_AVAILABLE and self.api_key:
            # v1.4.0: 600s timeout aligns with the Ollama provider so the UI
            # behaves consistently across providers for very long responses.
            _uds = os.environ.get("ANTHROPIC_UDS", "")
            if _uds:
                # Public site: Claude goes through the gateway's unix socket, which
                # adds the real key; this process only holds a per-user token.
                import httpx
                self._client = anthropic.AsyncAnthropic(
                    api_key=self.api_key, timeout=600.0, base_url="http://claude-gateway",
                    http_client=httpx.AsyncClient(
                        transport=httpx.AsyncHTTPTransport(uds=_uds), timeout=600.0))
            else:
                self._client = anthropic.AsyncAnthropic(api_key=self.api_key, timeout=600.0)

    @property
    def name(self) -> str:
        return "anthropic"

    def is_available(self) -> bool:
        return bool(_ANTHROPIC_SDK_AVAILABLE and self.api_key and self._client)

    async def list_models(self) -> list[str]:
        # ANTHROPIC_MODELS (set by the public site's gateway) overrides the list
        env = [m.strip() for m in os.environ.get("ANTHROPIC_MODELS", "").split(",") if m.strip()]
        return (env or list(SUPPORTED_MODELS)) if self.is_available() else []

    def _to_anthropic_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    def _to_anthropic_messages(self, messages: list[ChatMessage]) -> tuple[str, list[dict]]:
        """
        Claude's API takes system messages in a separate parameter, not in messages.
        Also, when there are tool calls/results, the message content becomes a
        structured list of blocks rather than a plain string.
        Returns: (system_prompt, chat_messages_list).
        """
        system_parts: list[str] = []
        out: list[dict] = []

        for m in messages:
            if m.role == "system":
                if m.content.strip():
                    system_parts.append(m.content)
                continue

            if m.role == "assistant" and m.tool_calls:
                # Assistant message with tool calls — must be a content block list:
                #   [text block?, tool_use block(s)]
                blocks: list[dict] = []
                if m.content and m.content.strip():
                    blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                out.append({"role": "assistant", "content": blocks})
                continue

            if m.role == "tool":
                # Tool result — Claude wants role="user" with a tool_result block
                out.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id or "",
                        "content": m.content,
                    }],
                })
                continue

            # Plain user or assistant text message
            if m.role in ("user", "assistant"):
                out.append({"role": m.role, "content": m.content})

        # Claude requires the first message to be from the user
        while out and out[0]["role"] == "assistant":
            out.pop(0)

        full_system = "\n\n".join(system_parts) if system_parts else ""
        return full_system, out

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        tools: Optional[list[ToolDefinition]] = None,
    ) -> ChatResponse:
        if not _ANTHROPIC_SDK_AVAILABLE:
            raise ProviderError(
                "anthropic SDK not installed. Run: pip install anthropic",
                status_code=500,
            )
        if not self.api_key:
            raise ProviderError(
                "ANTHROPIC_API_KEY is not set. Set it via direnv or systemd override.",
                status_code=401,
            )

        full_system, chat_msgs = self._to_anthropic_messages(messages)

        if not chat_msgs:
            raise ProviderError("No user messages to send.", status_code=400)

        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            messages=chat_msgs,
        )
        # Only pass temperature for models that still accept it (Opus 4.7+ rejects it)
        if not any(model.startswith(prefix) for prefix in NO_TEMPERATURE_MODELS):
            kwargs["temperature"] = temperature
        if full_system:
            kwargs["system"] = full_system
        if tools:
            kwargs["tools"] = self._to_anthropic_tools(tools)

        t0 = time.time()
        try:
            response = await self._client.messages.create(**kwargs)
        except anthropic.AuthenticationError as e:
            raise ProviderError(
                f"Claude API key rejected. Check ANTHROPIC_API_KEY. ({e.message})",
                status_code=401,
            )
        except anthropic.RateLimitError as e:
            raise ProviderError(
                f"Claude API rate limit hit. Try a smaller model or wait. ({e.message})",
                status_code=429,
            )
        except anthropic.APIConnectionError as e:
            raise ProviderError(
                f"Cannot reach Claude API. Check internet connectivity. ({e})",
                status_code=503,
            )
        except anthropic.APIError as e:
            raise ProviderError(f"Claude API error: {e.message}", status_code=502)

        # Parse response blocks
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=dict(block.input) if block.input else {},
                ))

        usage = response.usage
        cost = self.estimate_cost(model, usage.input_tokens, usage.output_tokens)

        return ChatResponse(
            content="".join(text_parts),
            model=response.model,
            provider=self.name,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost,
            eval_duration_ms=(time.time() - t0) * 1000.0,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
        )

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
        for canonical, rates in PRICING.items():
            if model.startswith(canonical):
                input_cost  = (input_tokens  / 1_000_000) * rates["input"]
                output_cost = (output_tokens / 1_000_000) * rates["output"]
                return round(input_cost + output_cost, 6)
        return None
