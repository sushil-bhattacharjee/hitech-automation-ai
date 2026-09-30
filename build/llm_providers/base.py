"""Base classes for LLM provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ChatMessage:
    """A single chat message in a conversation."""
    role: str       # "system" | "user" | "assistant" | "tool"
    content: str
    # Used only when role=="assistant" with tool calls, or role=="tool":
    tool_calls: Optional[list["ToolCall"]] = None
    tool_call_id: Optional[str] = None  # for role=="tool"


@dataclass
class ToolDefinition:
    """Provider-agnostic tool spec. Each provider translates to its native format."""
    name: str
    description: str
    parameters: dict          # JSON schema for the tool's input


@dataclass
class ToolCall:
    """A tool invocation request emitted by the LLM."""
    id: str                   # provider-supplied id (used to correlate with the result)
    name: str
    arguments: dict           # parsed arguments from the LLM


@dataclass
class ChatResponse:
    """Normalized response from any provider — same shape for Ollama or Anthropic."""
    content: str
    model: str
    provider: str                       # "ollama" | "anthropic"
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None    # None for local (free) models
    eval_duration_ms: Optional[float] = None
    tool_calls: list[ToolCall] = field(default_factory=list)  # populated in agent mode
    stop_reason: Optional[str] = None   # "end_turn" | "tool_use" | other
    extra: dict = field(default_factory=dict)


class ProviderError(Exception):
    """Raised by providers for any user-facing error (not-set keys, API failures, etc.)."""
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class ChatProvider(ABC):
    """Abstract interface that every LLM provider must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Lowercase provider name, e.g. 'ollama' or 'anthropic'."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Quick check: is the provider configured and reachable?"""
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        """Models the user can pick from. Empty list if provider unavailable."""
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
        """Send messages, return a normalized response.

        When `tools` is provided, the model may emit tool calls in the response;
        callers should execute them and continue the conversation.
        """
        ...

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
        """Override in providers with paid models. Return None for free."""
        return None

