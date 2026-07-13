"""Tool executor — runs the actual code when the LLM requests a tool call."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

try:                                   # v1.47.0: AI stack is optional
    import rag_retriever
except Exception:
    rag_retriever = None
from llm_providers import ToolCall

log = logging.getLogger("agent.tools")

# Max lines of output we'll feed back to the LLM. Long output wastes tokens
# and can cause Claude to lose focus.
MAX_OUTPUT_LINES = 150


def _closest_tool_name(query: str, candidates: list[str]) -> Optional[str]:
    """v1.6.0: suggest closest-matching tool name for unknown-tool errors.

    Uses a simple character-overlap heuristic — close enough for this purpose,
    no need for a real Levenshtein implementation.
    """
    if not query or not candidates:
        return None
    q = query.lower()
    best: tuple[float, Optional[str]] = (0.0, None)
    for c in candidates:
        cl = c.lower()
        # Prefix match is the strongest signal
        if cl.startswith(q) or q.startswith(cl):
            return c
        # Substring is the next-strongest
        if q in cl or cl in q:
            return c
        # Otherwise score by shared character ratio
        common = sum(1 for ch in set(q) if ch in cl)
        score = common / max(len(set(q)), len(set(cl)))
        if score > best[0]:
            best = (score, c)
    return best[1] if best[0] >= 0.6 else None


# Commands we allow. Strictly read-only.
READ_ONLY_PREFIXES = ("show ", "ping ", "traceroute ", "ping", "traceroute")
# Patterns we ALWAYS reject even if they start with "show" — defence in depth
BLOCKED_PATTERNS = [
    re.compile(r"\|.*?(?:debug|config|reload|copy)\b", re.IGNORECASE),
    re.compile(r";\s*\w", re.IGNORECASE),  # command stacking
]


@dataclass
class DeviceContext:
    """Information about the device the agent is acting on.

    Populated from the chat form fields the user has filled in. Credentials
    are kept here server-side; they are NEVER exposed to the LLM via tool
    output. The describe_device tool only returns non-secret metadata.
    """
    host: str = ""
    port: int = 22
    username: str = ""
    password: str = ""           # never echoed back to LLM
    device_type: str = "cisco_xe"
    secret: Optional[str] = None
    timeout: int = 30
    # Optional snapshot of the editor state so get_current_template works
    template: str = ""
    variables: str = ""

    def has_credentials(self) -> bool:
        return bool(self.host and self.username and self.password)


# ----------------------------------------------------------------- #
# Safety checks
# ----------------------------------------------------------------- #

def _validate_show_command(cmd: str) -> Optional[str]:
    """Return None if the command is allowed; an error string otherwise."""
    if not cmd or not cmd.strip():
        return "Empty command"
    lower = cmd.strip().lower()
    if not lower.startswith(READ_ONLY_PREFIXES):
        return (
            f"Refused: only 'show', 'ping', and 'traceroute' commands are allowed "
            f"in agent mode. Got: {cmd!r}"
        )
    for pattern in BLOCKED_PATTERNS:
        if pattern.search(cmd):
            return f"Refused: command contains a blocked pattern: {cmd!r}"
    return None


def _truncate(text: str, max_lines: int = MAX_OUTPUT_LINES) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    keep = max_lines - 5
    return (
        "\n".join(lines[:keep])
        + f"\n\n... [{len(lines) - keep} additional lines omitted for brevity] ..."
    )


# ----------------------------------------------------------------- #
# Tool implementations
# ----------------------------------------------------------------- #

async def _tool_run_show_command(args: dict, ctx: DeviceContext) -> str:
    cmd = args.get("command", "")
    err = _validate_show_command(cmd)
    if err:
        return err

    # v1.6.0: resolve device. Priority:
    #   1. device_name arg → look up in inventory, use those creds
    #   2. fall back to chat form context (ctx) — v1.3 behaviour
    requested_name = (args.get("device_name") or "").strip()

    if requested_name:
        from . import inventory
        d = inventory.get_device(requested_name)
        if not d:
            available = ", ".join(inventory.list_device_names()) or "(none)"
            return (
                f"[Unknown device: {requested_name!r}. "
                f"Available devices in inventory: {available}]"
            )
        if not d.host or not d.username or not d.password:
            return (
                f"[Device {requested_name!r} is in inventory but credentials are "
                f"incomplete (host/username/password missing — check env vars).]"
            )

        # Map inventory device_type (cisco-iosxe) to netmiko type (cisco_xe)
        netmiko_type_map = {
            "cisco-iosxe":   "cisco_xe",
            "cisco-nxos":    "cisco_nxos",
            "cisco-iosxr":   "cisco_xr",
            "juniper-junos": "juniper_junos",
        }
        nm_type = netmiko_type_map.get(d.device_type, "cisco_xe")

        # Build a transient context bound to the inventory device for SSH (port 22)
        eff_ctx = DeviceContext(
            host=d.host,
            port=d.port_ssh,
            username=d.username,
            password=d.password,
            device_type=nm_type,
            timeout=ctx.timeout or 30,
        )
        device_label = f"{d.name} ({d.host})"
    else:
        if not ctx.has_credentials():
            return (
                "Refused: no device specified. Either pass device_name (e.g. 'cat8Kv71') "
                "to use a device from the inventory, or have the user fill in the "
                "Host / Username / Password fields in the chat form."
            )
        eff_ctx = ctx
        device_label = f"chat-form device ({ctx.host})"

    # Lazy import: netmiko is heavy
    from netmiko import ConnectHandler
    from netmiko.exceptions import (
        NetmikoAuthenticationException,
        NetmikoTimeoutException,
    )

    def _connect_and_run():
        conn_args = {
            "device_type": eff_ctx.device_type,
            "host": eff_ctx.host,
            "username": eff_ctx.username,
            "password": eff_ctx.password,
            "port": eff_ctx.port,
            "fast_cli": False,
            "conn_timeout": eff_ctx.timeout,
        }
        if eff_ctx.secret:
            conn_args["secret"] = eff_ctx.secret

        try:
            with ConnectHandler(**conn_args) as net:
                if eff_ctx.secret:
                    net.enable()
                return net.send_command(cmd, read_timeout=eff_ctx.timeout)
        except NetmikoAuthenticationException as e:
            return f"[Auth failed] {e}"
        except NetmikoTimeoutException as e:
            return f"[Timeout] {e}"
        except Exception as e:
            return f"[{type(e).__name__}] {e}"

    # Run in thread pool — netmiko is blocking
    loop = asyncio.get_event_loop()
    try:
        output = await asyncio.wait_for(
            loop.run_in_executor(None, _connect_and_run),
            timeout=eff_ctx.timeout + 10,
        )
    except asyncio.TimeoutError:
        return f"[Tool timeout after {eff_ctx.timeout + 10}s — device unreachable or slow]"

    log.info("run_show_command device=%s cmd=%r bytes=%d", device_label, cmd, len(output or ""))

    # v1.6.0 (item 2): preserve raw CLI output verbatim. The marker tells the LLM
    # (via the system prompt) to echo this back in a fenced code block without
    # reformatting into markdown tables.
    raw = _truncate(output or "(no output)")
    return f"[RAW_CLI_OUTPUT device={device_label} command={cmd!r}]\n{raw}\n[END_RAW_CLI_OUTPUT]"


async def _tool_search_corpus(args: dict, ctx: DeviceContext) -> str:
    query = args.get("query", "").strip()
    k = min(int(args.get("k", 5) or 5), 10)

    if not query:
        return "Empty query"
    if not rag_retriever.rag_available():
        return "[RAG vector DB not built. Run python rag_builder.py first.]"

    chunks = await rag_retriever.retrieve(query, k=k)
    if not chunks:
        return f"No matching chunks found for query: {query!r}"

    return rag_retriever.format_for_prompt(chunks)


async def _tool_describe_device(args: dict, ctx: DeviceContext) -> str:
    if not ctx.has_credentials():
        return "No device is currently configured in the chat form."
    # NOTE: password / secret intentionally omitted
    return (
        f"Currently configured device:\n"
        f"- host: {ctx.host}\n"
        f"- port: {ctx.port}\n"
        f"- device_type: {ctx.device_type}\n"
        f"- username: {ctx.username}\n"
        f"- (password is set: {'yes' if ctx.password else 'no'})\n"
        f"- timeout: {ctx.timeout}s"
    )


async def _tool_get_current_template(args: dict, ctx: DeviceContext) -> str:
    if not ctx.template and not ctx.variables:
        return "No template or variables are currently loaded in the editor."
    parts = []
    if ctx.template:
        parts.append(f"=== Template (Jinja2) ===\n{ctx.template}")
    if ctx.variables:
        parts.append(f"=== Variables (YAML) ===\n{ctx.variables}")
    return "\n\n".join(parts)


# ----------------------------------------------------------------- #
# v1.10.0 (issue-4): read the last direct-execute result from the UI
# ----------------------------------------------------------------- #

def _cap_output(text: str, max_lines: int = 400) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    head = "\n".join(lines[:max_lines])
    return head + (f"\n... [truncated {len(lines) - max_lines} more lines — pass "
                   f"row_element + columns to extract just the fields you need]")


def _extract_xml_table(xml_str: str, row_element: str, columns: list) -> str:
    """Namespace-agnostic extraction: one row per <row_element>, columns are
    '/'-separated local-name chains relative to each row. Mirrors the client-side
    extractor and the user's lxml workflow."""
    from lxml import etree
    root = etree.fromstring(xml_str.encode("utf-8"))

    def lname(el):
        return etree.QName(el.tag).localname

    def kid(el, name):
        for c in el:
            if isinstance(c.tag, str) and lname(c) == name:
                return c
        return None

    def dig(el, path):
        cur = el
        for p in path.split("/"):
            cur = kid(cur, p) if cur is not None else None
            if cur is None:
                return ""
        return (cur.text or "").strip() if cur is not None else ""

    rows = [el for el in root.iter() if isinstance(el.tag, str) and lname(el) == row_element]
    if not rows:
        return f"(no <{row_element}> elements found in the last result)"
    out = [" | ".join(columns)]
    for el in rows:
        out.append(" | ".join(dig(el, c) for c in columns))
    return "\n".join(out)


async def _tool_read_last_result(args: dict, ctx: "DeviceContext") -> str:
    from .ui_results import get_last_result
    last = get_last_result()
    content = last.get("content") or ""
    if not content.strip():
        return ("[no result yet] The user hasn't run a NETCONF/RESTCONF/CLI/XPath query in the "
                "Config Mgmt UI this session, so there is nothing to read. Ask them to run one, "
                "or use the device tools to fetch the data yourself.")
    meta = (f"transport={last.get('transport')}, device={last.get('device')}, "
            f"source={last.get('source')}, query={last.get('query')}")
    row = (args or {}).get("row_element")
    cols = (args or {}).get("columns")
    if row and cols and last.get("kind") == "xml":
        try:
            table = _extract_xml_table(content, row, list(cols))
            return f"Extracted from last result ({meta}):\n{table}"
        except Exception as e:
            return (f"[extract failed: {type(e).__name__}: {e}] Raw result ({meta}), truncated:\n"
                    f"{_cap_output(content)}")
    return f"Last result ({meta}):\n{_cap_output(content)}"


# ----------------------------------------------------------------- #
# Dispatcher
# ----------------------------------------------------------------- #

_HANDLERS = {
    "run_show_command":     _tool_run_show_command,
    "search_corpus":        _tool_search_corpus,
    "describe_device":      _tool_describe_device,
    "get_current_template": _tool_get_current_template,
    "read_last_result":     _tool_read_last_result,
}


async def execute_tool(call: ToolCall, ctx: DeviceContext) -> tuple[str, bool]:
    """Execute one tool call. Returns (output_text, is_error).

    Always returns a string — we never raise out of here, because the
    LLM needs *some* text to continue the conversation, even on error.

    v1.4.0: NETCONF tools are dispatched via tools.netconf_tools.NETCONF_HANDLERS.
    The write tools (propose_edit_config, apply_edit_config) may return a dict
    with {"_approval_pending": True, ...} instead of a string — the caller
    (agent.run_agent) must detect this and pause for human approval BEFORE
    feeding the result back to the LLM. We stringify the marker here as a
    safety net only; the agent loop should intercept first.
    """
    # NETCONF tools first (v1.4.0). Lazy import to avoid circular.
    from .netconf_tools import NETCONF_HANDLERS, APPROVAL_PENDING

    # v1.7.0: RESTCONF tools dispatched alongside NETCONF
    from .restconf_tools import (
        tool_restconf_get,
        tool_restconf_list_capabilities,
        tool_propose_restconf_post,
        tool_propose_restconf_put,
        tool_propose_restconf_patch,
        tool_propose_restconf_delete,
        tool_apply_restconf_change,
    )
    RESTCONF_HANDLERS = {
        "restconf_get": tool_restconf_get,
        "restconf_list_capabilities": tool_restconf_list_capabilities,
        "propose_restconf_post": tool_propose_restconf_post,
        "propose_restconf_put": tool_propose_restconf_put,
        "propose_restconf_patch": tool_propose_restconf_patch,
        "propose_restconf_delete": tool_propose_restconf_delete,
        "apply_restconf_change": tool_apply_restconf_change,
    }

    if call.name in NETCONF_HANDLERS:
        try:
            result = await NETCONF_HANDLERS[call.name](call.arguments or {})
        except Exception as e:
            log.exception("NETCONF tool %s failed", call.name)
            return f"[Tool execution failed: {type(e).__name__}: {e}]", True

        # Approval marker passes through as a JSON string — the agent loop
        # will detect APPROVAL_PENDING and intercept.
        if isinstance(result, dict) and result.get(APPROVAL_PENDING):
            import json
            return json.dumps(result), False
        if isinstance(result, dict):
            # Plain error dicts from NETCONF tools
            import json
            return json.dumps(result), bool(result.get("error"))
        # String result
        is_error = isinstance(result, str) and result.startswith(("[error]", "[NETCONF error]"))
        return result, is_error

    if call.name in RESTCONF_HANDLERS:
        try:
            result = await RESTCONF_HANDLERS[call.name](call.arguments or {})
        except Exception as e:
            log.exception("RESTCONF tool %s failed", call.name)
            return f"[Tool execution failed: {type(e).__name__}: {e}]", True
        if isinstance(result, dict) and result.get(APPROVAL_PENDING):
            import json
            return json.dumps(result), False
        if isinstance(result, dict):
            import json
            return json.dumps(result), bool(result.get("_error"))
        is_error = isinstance(result, str) and result.startswith(("[error]", "[RESTCONF"))
        return result, is_error

    # v1.3 tools
    handler = _HANDLERS.get(call.name)
    if not handler:
        # v1.6.0 (item 5): suggest closest-match tool name
        all_tools = list(_HANDLERS) + list(NETCONF_HANDLERS) + list(RESTCONF_HANDLERS)
        suggestion = _closest_tool_name(call.name, all_tools)
        hint = f" Did you mean {suggestion!r}?" if suggestion else ""
        return (
            f"[Unknown tool: {call.name!r}.{hint} "
            f"Available tools: {all_tools}]",
            True,
        )

    try:
        result = await handler(call.arguments or {}, ctx)
        is_error = bool(result.startswith(("[Auth", "[Timeout", "[Unknown", "[RAG", "Refused", "[Tool")))
        return result, is_error
    except Exception as e:
        log.exception("Tool %s failed", call.name)
        return f"[Tool execution failed: {type(e).__name__}: {e}]", True
