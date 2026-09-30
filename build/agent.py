"""Agent orchestrator — runs a ReAct loop with whichever provider is selected."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import AsyncIterator, Optional

from llm_providers import (
    ChatMessage,
    ChatProvider,
    ChatResponse,
    ProviderError,
    ToolCall,
    ToolDefinition,
)
from tools import DeviceContext, execute_tool, get_tool_definitions

log = logging.getLogger("agent")


# Max ReAct iterations. Each iteration = one LLM call + zero-or-more tool calls.
# Anthropic Sonnet typically converges in 2-4 iterations; gpt-oss:20b can take 4-6.
# A runaway agent loop is expensive on Claude (input tokens grow each turn).
DEFAULT_MAX_ITERATIONS = 8


# v1.8.0 — Run cancellation registry.
# When the user clicks Stop in the UI, the cancel endpoint adds the run_id
# to this set. The agent loop checks it at every iteration boundary and at
# tool-call boundaries; if present, it exits cleanly with stopped_reason="cancelled".
# Cleared automatically when the run finishes (success or otherwise).
_CANCELLED_RUNS: set[str] = set()

def request_cancel(run_id: str) -> bool:
    """Mark a run as cancelled. Returns True if the run_id was previously valid."""
    if not run_id:
        return False
    _CANCELLED_RUNS.add(run_id)
    log.info("agent: cancel requested for run_id=%s", run_id)
    return True

def is_cancelled(run_id: str) -> bool:
    return bool(run_id) and run_id in _CANCELLED_RUNS

def _clear_cancel(run_id: str) -> None:
    _CANCELLED_RUNS.discard(run_id)


@dataclass
class AgentStep:
    """One step in the agent's reasoning trace, sent to the UI."""
    kind: str                              # "llm_text" | "tool_call" | "tool_result" | "final"
    iteration: int
    text: Optional[str] = None             # for llm_text and final
    tool_name: Optional[str] = None        # for tool_call and tool_result
    tool_args: Optional[dict] = None       # for tool_call
    tool_result: Optional[str] = None      # for tool_result
    is_error: bool = False                 # for tool_result
    # Per-iteration cost / tokens (rolled into total at the end too)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    model: Optional[str] = None
    # v1.6.0: per-iteration / per-step timing
    elapsed_seconds: Optional[float] = None  # how long this step took


@dataclass
class AgentResult:
    final_answer: str
    trace: list[AgentStep] = field(default_factory=list)
    iterations: int = 0
    stopped_reason: str = "completed"      # "completed" | "max_iterations" | "error" | "awaiting_approval" | "cancelled"
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    # v1.4.0 — populated when stopped_reason == "awaiting_approval"
    run_id: Optional[str] = None
    pending_proposal: Optional[dict] = None


# ----------------------------------------------------------------- #
# v1.4.0 — Resumable run state (for write-tool approval workflow)
# ----------------------------------------------------------------- #
# When a write tool returns APPROVAL_PENDING, we snapshot the loop state
# into _PAUSED_RUNS keyed by run_id and return to the caller. The UI shows
# the approval modal, the user approves/rejects, and then continue_agent()
# pops the snapshot and resumes.

from typing import Any as _Any  # avoid shadowing the user-facing 'Any'

@dataclass
class _PausedRun:
    run_id: str
    provider: _Any
    model: str
    history: list                          # list[ChatMessage]
    trace: list                            # list[AgentStep]
    iteration: int
    max_iterations: int
    device_ctx: _Any
    total_in: int
    total_out: int
    total_cost: float
    pending_tool_call_id: str
    pending_proposal_id: str
    max_tokens: int = 2048                 # v1.7.0

_PAUSED_RUNS: dict[str, _PausedRun] = {}


async def run_agent(
    provider: ChatProvider,
    model: str,
    user_messages: list[ChatMessage],
    system_prompt: str,
    device_ctx: DeviceContext,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    max_tokens: int = 2048,                  # v1.7.0: per-request override
    external_run_id: Optional[str] = None,   # v1.8.0: caller-provided for cancel/SSE
) -> AgentResult:
    """ReAct loop. Returns the final answer plus the full trace.

    user_messages should contain just the chat history (no system message — that's
    passed separately so we can append/normalize it here). The system prompt
    primes the LLM to use tools.

    v1.8.0: pass external_run_id if you want to be able to cancel this run via
    request_cancel() from another coroutine (e.g. the /api/agent-cancel endpoint).
    When omitted, a private UUID is used.
    """

    tools = get_tool_definitions()
    history: list[ChatMessage] = []

    # System message goes first; both providers handle it correctly via their
    # respective adapter logic in _to_anthropic_messages / _to_ollama_message.
    if system_prompt.strip():
        history.append(ChatMessage(role="system", content=system_prompt))

    # User-provided conversation history follows
    history.extend(user_messages)

    trace: list[AgentStep] = []
    total_in = 0
    total_out = 0
    total_cost = 0.0

    # v1.7.0: register this run with the NETCONF session pool so tools can reuse
    # one long-lived ncclient session per device per run.
    # v1.8.0: if the caller passed external_run_id, use it so the cancel endpoint
    # can find the run. Otherwise generate one for internal correlation.
    agent_run_uuid = external_run_id or ("run_" + uuid.uuid4().hex[:12])
    try:
        from tools import netconf_tools as _nctools
        _nctools.set_agent_run_id(agent_run_uuid)
    except Exception:
        _nctools = None

    def _cleanup_run():
        if _nctools is not None:
            try:
                _nctools.close_all_sessions_for_run(agent_run_uuid)
                _nctools.set_agent_run_id(None)
            except Exception:
                pass
        # v1.8.0: clear cancellation flag at end of run
        _clear_cancel(agent_run_uuid)

    def _make_cancelled_result(iteration: int) -> AgentResult:
        """Build a stopped-by-user result. Called when cancellation is detected."""
        trace.append(AgentStep(
            kind="final",
            iteration=iteration,
            text="⏹ Cancelled by user.",
            is_error=False,
        ))
        _cleanup_run()
        return AgentResult(
            final_answer="⏹ Cancelled by user.",
            trace=trace,
            iterations=iteration,
            stopped_reason="cancelled",
            total_input_tokens=total_in,
            total_output_tokens=total_out,
            total_cost_usd=total_cost,
            run_id=agent_run_uuid,
        )

    # v1.6.0 (item 6): focus-injection trigger.
    # Once context grows large OR we've used many iterations, inject a system
    # nudge into the history telling the model to stop calling more tools and
    # produce a final answer from data it already has. This combats two failure
    # modes seen with small models (gpt-oss:20b):
    #   - drift: model forgets the original question after many turns
    #   - tool hallucination: model invents non-existent tool names under load
    FOCUS_INJECTION_FIRED = False
    FOCUS_TOKEN_THRESHOLD = 10_000
    FOCUS_ITERATION_THRESHOLD = 4

    import time

    for iteration in range(1, max_iterations + 1):
        # v1.8.0 — cancellation check at top of each iteration
        if is_cancelled(agent_run_uuid):
            return _make_cancelled_result(iteration)

        # v1.6.0 (item 6): inject a focusing system message if either threshold trips,
        # but only once per run to avoid spamming the context.
        if (
            not FOCUS_INJECTION_FIRED
            and (total_in >= FOCUS_TOKEN_THRESHOLD or iteration > FOCUS_ITERATION_THRESHOLD)
        ):
            history.append(ChatMessage(
                role="system",
                content=(
                    "FOCUS REMINDER: You have already gathered substantial data via tool calls. "
                    "Now produce the final answer using only what you already have. "
                    "Do not call more tools unless absolutely necessary. "
                    "Only call exact tool names from the registered tool list — never invent names."
                ),
            ))
            FOCUS_INJECTION_FIRED = True
            log.info("agent iter=%d focus-injection fired (in_tokens=%d)", iteration, total_in)

        iter_start = time.monotonic()
        try:
            resp: ChatResponse = await provider.chat(
                messages=history,
                model=model,
                tools=tools,
                max_tokens=max_tokens,
            )
        except ProviderError as e:
            trace.append(AgentStep(
                kind="final",
                iteration=iteration,
                text=f"⚠️ Provider error: {e}",
                is_error=True,
                elapsed_seconds=round(time.monotonic() - iter_start, 2),
            ))
            _cleanup_run()
            return AgentResult(
                final_answer=f"⚠️ {e}",
                trace=trace,
                iterations=iteration,
                stopped_reason="error",
                total_input_tokens=total_in,
                total_output_tokens=total_out,
                total_cost_usd=total_cost,
                run_id=agent_run_uuid,
            )

        llm_elapsed = round(time.monotonic() - iter_start, 2)

        # Roll up token usage
        if resp.input_tokens:  total_in  += resp.input_tokens
        if resp.output_tokens: total_out += resp.output_tokens
        if resp.cost_usd:      total_cost += resp.cost_usd

        # Record any text the model produced as part of this turn
        if resp.content and resp.content.strip():
            trace.append(AgentStep(
                kind="llm_text",
                iteration=iteration,
                text=resp.content,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                cost_usd=resp.cost_usd,
                model=resp.model,
                elapsed_seconds=llm_elapsed,
            ))

        # If no tool calls, this is the final answer
        if not resp.tool_calls:
            trace.append(AgentStep(
                kind="final",
                iteration=iteration,
                text=resp.content,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                cost_usd=resp.cost_usd,
                model=resp.model,
                elapsed_seconds=llm_elapsed,
            ))
            _cleanup_run()
            return AgentResult(
                final_answer=resp.content,
                trace=trace,
                iterations=iteration,
                stopped_reason="completed",
                total_input_tokens=total_in,
                total_output_tokens=total_out,
                total_cost_usd=total_cost,
                run_id=agent_run_uuid,
            )

        # Append the assistant turn (with tool calls) to history
        history.append(ChatMessage(
            role="assistant",
            content=resp.content,
            tool_calls=resp.tool_calls,
        ))

        # Execute each tool call, append a tool-role message per result
        for tc in resp.tool_calls:
            # v1.8.0 — cancellation check inside the tool loop
            if is_cancelled(agent_run_uuid):
                return _make_cancelled_result(iteration)

            trace.append(AgentStep(
                kind="tool_call",
                iteration=iteration,
                tool_name=tc.name,
                tool_args=tc.arguments,
            ))
            log.info("agent iter=%d tool=%s args=%s", iteration, tc.name, tc.arguments)

            tool_start = time.monotonic()
            output, is_error = await execute_tool(tc, device_ctx)
            tool_elapsed = round(time.monotonic() - tool_start, 2)

            # v1.4.0 — write tools may return the APPROVAL_PENDING marker.
            # When we see it, snapshot the run state and return paused.
            pending_info = _extract_approval_pending(output)
            if pending_info is not None:
                run_id = "run_" + uuid.uuid4().hex[:12]
                # Record what the LLM proposed in the trace, but DON'T feed back yet
                trace.append(AgentStep(
                    kind="tool_result",
                    iteration=iteration,
                    tool_name=tc.name,
                    tool_result=f"⏸ Awaiting human approval (proposal_id={pending_info.get('proposal_id')})",
                    is_error=False,
                ))
                _PAUSED_RUNS[run_id] = _PausedRun(
                    run_id=run_id,
                    provider=provider,
                    model=model,
                    history=list(history),     # snapshot
                    trace=list(trace),
                    iteration=iteration,
                    max_iterations=max_iterations,
                    device_ctx=device_ctx,
                    total_in=total_in,
                    total_out=total_out,
                    total_cost=total_cost,
                    pending_tool_call_id=tc.id,
                    pending_proposal_id=pending_info.get("proposal_id", ""),
                    max_tokens=max_tokens,
                )
                log.info("agent paused for approval run_id=%s proposal=%s",
                         run_id, pending_info.get("proposal_id"))
                _cleanup_run()
                return AgentResult(
                    final_answer="⏸ Awaiting your approval for the proposed change.",
                    trace=trace,
                    iterations=iteration,
                    stopped_reason="awaiting_approval",
                    total_input_tokens=total_in,
                    total_output_tokens=total_out,
                    total_cost_usd=total_cost,
                    run_id=run_id,
                    pending_proposal=pending_info,
                )

            trace.append(AgentStep(
                kind="tool_result",
                iteration=iteration,
                tool_name=tc.name,
                tool_result=output,
                is_error=is_error,
                elapsed_seconds=tool_elapsed,
            ))

            history.append(ChatMessage(
                role="tool",
                content=output,
                tool_call_id=tc.id,
            ))

    # Max iterations exceeded
    trace.append(AgentStep(
        kind="final",
        iteration=max_iterations,
        text=(
            f"⚠️ Agent reached max_iterations ({max_iterations}) without producing a final "
            f"answer. The model may be looping. Try rephrasing the question or use a stronger model."
        ),
        is_error=True,
    ))
    _cleanup_run()
    return AgentResult(
        final_answer=f"⚠️ Max iterations ({max_iterations}) reached without a final answer.",
        trace=trace,
        iterations=max_iterations,
        stopped_reason="max_iterations",
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_cost_usd=total_cost,
        run_id=agent_run_uuid,
    )


# ----------------------------------------------------------------- #
# JSON serialization for the API response
# ----------------------------------------------------------------- #

def step_to_dict(s: AgentStep) -> dict:
    d = asdict(s)
    return {k: v for k, v in d.items() if v is not None or k in ("text", "tool_result")}


def result_to_dict(r: AgentResult) -> dict:
    out = {
        "final_answer": r.final_answer,
        "trace": [step_to_dict(s) for s in r.trace],
        "iterations": r.iterations,
        "stopped_reason": r.stopped_reason,
        "total_input_tokens": r.total_input_tokens,
        "total_output_tokens": r.total_output_tokens,
        "total_cost_usd": r.total_cost_usd,
    }
    if r.run_id:
        out["run_id"] = r.run_id
    if r.pending_proposal:
        out["pending_proposal"] = r.pending_proposal
    return out


# ----------------------------------------------------------------- #
# v1.4.0 — approval-pause helpers
# ----------------------------------------------------------------- #

def _extract_approval_pending(tool_output: str) -> Optional[dict]:
    """If the tool output is a JSON string carrying the approval marker, parse and return it."""
    if not tool_output or not tool_output.lstrip().startswith("{"):
        return None
    try:
        parsed = json.loads(tool_output)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(parsed, dict) and parsed.get("_approval_pending"):
        return parsed
    return None


async def continue_agent(run_id: str, approved: bool) -> AgentResult:
    """Resume a paused agent run after the user approves/rejects the proposal.

    The agent loop picks up where it left off, feeding the LLM either the
    apply_edit_config result (on approve) or a rejection message (on reject),
    and continues iterating until completion, another approval point, or
    max_iterations.
    """
    from tools.netconf_tools import (
        set_proposal_decision, tool_apply_edit_config, get_proposal,
    )
    from tools import audit

    paused = _PAUSED_RUNS.pop(run_id, None)
    if not paused:
        return AgentResult(
            final_answer=f"⚠️ No paused run with id {run_id!r}. It may have expired or already resumed.",
            trace=[],
            iterations=0,
            stopped_reason="error",
        )

    # Record decision in the netconf module's pending store
    set_proposal_decision(paused.pending_proposal_id, approved)
    audit.log_event(
        "agent_resumed",
        run_id=run_id,
        proposal_id=paused.pending_proposal_id,
        approved=approved,
    )

    # Build the tool-result message the LLM will see for its pending tool call
    if approved:
        # Actually apply the change now
        apply_result = await tool_apply_edit_config({"proposal_id": paused.pending_proposal_id})
        tool_message = (
            f"User approved proposal {paused.pending_proposal_id}. "
            f"apply_edit_config result: {apply_result}"
        )
        is_apply_error = isinstance(apply_result, str) and apply_result.startswith("[")
        paused.trace.append(AgentStep(
            kind="tool_result",
            iteration=paused.iteration,
            tool_name="apply_edit_config",
            tool_result=tool_message,
            is_error=is_apply_error,
        ))
    else:
        p = get_proposal(paused.pending_proposal_id)
        device_name = p.device_name if p else "(unknown)"
        tool_message = (
            f"User REJECTED proposal {paused.pending_proposal_id} for device "
            f"{device_name}. Do NOT retry the same change. Explain to the user "
            f"what was rejected and ask how they'd like to proceed."
        )
        paused.trace.append(AgentStep(
            kind="tool_result",
            iteration=paused.iteration,
            tool_name="propose_edit_config",
            tool_result=tool_message,
            is_error=False,
        ))

    # Feed the tool result back to the LLM with the original tool_call_id
    paused.history.append(ChatMessage(
        role="tool",
        content=tool_message,
        tool_call_id=paused.pending_tool_call_id,
    ))

    # Continue the loop from iteration+1
    return await _continue_loop(paused)


async def _continue_loop(paused: _PausedRun) -> AgentResult:
    """The same logic as run_agent's main loop, but starting from a snapshot."""
    tools = get_tool_definitions()
    history = paused.history
    trace = paused.trace
    total_in = paused.total_in
    total_out = paused.total_out
    total_cost = paused.total_cost

    # v1.7.0: fresh session pool for the resumed run
    cont_run_uuid = "run_" + uuid.uuid4().hex[:12]
    try:
        from tools import netconf_tools as _nctools
        _nctools.set_agent_run_id(cont_run_uuid)
    except Exception:
        _nctools = None

    def _cleanup_cont():
        if _nctools is not None:
            try:
                _nctools.close_all_sessions_for_run(cont_run_uuid)
                _nctools.set_agent_run_id(None)
            except Exception:
                pass

    for iteration in range(paused.iteration + 1, paused.max_iterations + 1):
        # v1.8.0 — cancellation check on the resume path too
        if is_cancelled(cont_run_uuid):
            trace.append(AgentStep(
                kind="final", iteration=iteration,
                text="⏹ Cancelled by user.", is_error=False,
            ))
            _cleanup_cont()
            return AgentResult(
                final_answer="⏹ Cancelled by user.",
                trace=trace, iterations=iteration,
                stopped_reason="cancelled",
                total_input_tokens=total_in,
                total_output_tokens=total_out,
                total_cost_usd=total_cost,
                run_id=cont_run_uuid,
            )

        try:
            resp: ChatResponse = await paused.provider.chat(
                messages=history,
                model=paused.model,
                tools=tools,
                max_tokens=paused.max_tokens,
            )
        except ProviderError as e:
            trace.append(AgentStep(kind="final", iteration=iteration,
                                   text=f"⚠️ Provider error: {e}", is_error=True))
            _cleanup_cont()
            return AgentResult(
                final_answer=f"⚠️ {e}", trace=trace, iterations=iteration,
                stopped_reason="error",
                total_input_tokens=total_in, total_output_tokens=total_out,
                total_cost_usd=total_cost,
            )

        if resp.input_tokens:  total_in  += resp.input_tokens
        if resp.output_tokens: total_out += resp.output_tokens
        if resp.cost_usd:      total_cost += resp.cost_usd

        if resp.content and resp.content.strip():
            trace.append(AgentStep(
                kind="llm_text", iteration=iteration, text=resp.content,
                input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
                cost_usd=resp.cost_usd, model=resp.model,
            ))

        if not resp.tool_calls:
            trace.append(AgentStep(
                kind="final", iteration=iteration, text=resp.content,
                input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
                cost_usd=resp.cost_usd, model=resp.model,
            ))
            _cleanup_cont()
            return AgentResult(
                final_answer=resp.content, trace=trace, iterations=iteration,
                stopped_reason="completed",
                total_input_tokens=total_in, total_output_tokens=total_out,
                total_cost_usd=total_cost,
            )

        history.append(ChatMessage(role="assistant", content=resp.content,
                                   tool_calls=resp.tool_calls))

        for tc in resp.tool_calls:
            trace.append(AgentStep(kind="tool_call", iteration=iteration,
                                   tool_name=tc.name, tool_args=tc.arguments))
            output, is_error = await execute_tool(tc, paused.device_ctx)

            pending_info = _extract_approval_pending(output)
            if pending_info is not None:
                run_id = "run_" + uuid.uuid4().hex[:12]
                trace.append(AgentStep(
                    kind="tool_result", iteration=iteration, tool_name=tc.name,
                    tool_result=f"⏸ Awaiting human approval (proposal_id={pending_info.get('proposal_id')})",
                ))
                _PAUSED_RUNS[run_id] = _PausedRun(
                    run_id=run_id, provider=paused.provider, model=paused.model,
                    history=list(history), trace=list(trace), iteration=iteration,
                    max_iterations=paused.max_iterations, device_ctx=paused.device_ctx,
                    total_in=total_in, total_out=total_out, total_cost=total_cost,
                    pending_tool_call_id=tc.id,
                    pending_proposal_id=pending_info.get("proposal_id", ""),
                    max_tokens=paused.max_tokens,
                )
                _cleanup_cont()
                return AgentResult(
                    final_answer="⏸ Awaiting your approval for the proposed change.",
                    trace=trace, iterations=iteration,
                    stopped_reason="awaiting_approval",
                    total_input_tokens=total_in, total_output_tokens=total_out,
                    total_cost_usd=total_cost,
                    run_id=run_id, pending_proposal=pending_info,
                )

            trace.append(AgentStep(kind="tool_result", iteration=iteration,
                                   tool_name=tc.name, tool_result=output,
                                   is_error=is_error))
            history.append(ChatMessage(role="tool", content=output, tool_call_id=tc.id))

    trace.append(AgentStep(
        kind="final", iteration=paused.max_iterations,
        text=f"⚠️ Agent reached max_iterations ({paused.max_iterations}).",
        is_error=True,
    ))
    _cleanup_cont()
    return AgentResult(
        final_answer=f"⚠️ Max iterations ({paused.max_iterations}) reached.",
        trace=trace, iterations=paused.max_iterations,
        stopped_reason="max_iterations",
        total_input_tokens=total_in, total_output_tokens=total_out,
        total_cost_usd=total_cost,
    )
