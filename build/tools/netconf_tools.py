"""NETCONF tools for v1.4.0 agentic mode.

Six tools exposed to the LLM:
  Read-only:
    - list_devices            list configured devices from inventory
    - get_running_config      pull device running-config via NETCONF
    - get_state               pull operational state (interfaces / routes / etc.)
    - validate_config_xml     validate a NETCONF payload via candidate datastore

  Write (REQUIRE APPROVAL):
    - propose_edit_config     compose an edit-config payload, return a diff
    - apply_edit_config       execute a previously approved payload

Write tools never apply changes by themselves. They return a special
APPROVAL_PENDING marker which the agent loop intercepts to pause and request
human approval via the diff modal. Only after an explicit approve event are
the changes committed.

ncclient is imported lazily so the package boots fine on machines that
don't have it installed yet (e.g., during initial setup before pip install).
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from llm_providers import ToolDefinition
from tools import audit, inventory

log = logging.getLogger("agent.netconf")


# Marker returned by write tools when human approval is needed.
# The agent loop checks for the dict shape {"_approval_pending": True, ...}.
APPROVAL_PENDING = "_approval_pending"

# Hard cap on returned config size — keeps token usage sane.
MAX_CONFIG_CHARS = 12000

# Per-tool operation timeout (seconds). Separate from HTTP timeout to the LLM.
NETCONF_TIMEOUT = 60


# ============================================================ #
# NETCONF tool definitions (LLM-facing schemas)
# ============================================================ #

NETCONF_TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="list_devices",
        description=(
            "List network devices the agent can act on, from the user's local "
            "inventory (~/.hitech_automation_ai/devices.yaml). Returns name, host, "
            "device_type, and read_only flag for each. The read_only field is "
            "important: a device marked read_only refuses all write tools."
        ),
        parameters={"type": "object", "properties": {}},
    ),

    ToolDefinition(
        name="get_running_config",
        description=(
            "Retrieve the running-config from a network device via NETCONF "
            "(get-config, running datastore). Returns the XML config; very long "
            "configs are truncated to ~12000 characters. Filter the query to "
            "keep token usage down: use 'subtree' for tree-shaped queries, "
            "'xpath' for surgical leaf queries."
        ),
        parameters={
            "type": "object",
            "properties": {
                "device_name": {
                    "type": "string",
                    "description": "Device name from list_devices, e.g. 'lab-csr1'.",
                },
                "filter_type": {
                    "type": "string",
                    "enum": ["subtree", "xpath", "none"],
                    "description": (
                        "How to interpret the filter. 'subtree' (default if XML is "
                        "supplied) returns the whole matching tree branch. 'xpath' "
                        "returns just the matching leaf nodes — preferred for surgical "
                        "queries like fetching specific counters. 'none' returns the "
                        "full running-config (use only when truly needed)."
                    ),
                },
                "subtree_filter_xml": {
                    "type": "string",
                    "description": (
                        "NETCONF subtree filter XML, used when filter_type=subtree. "
                        "Example: '<interfaces xmlns=\"...\"/>'."
                    ),
                },
                "xpath_filter": {
                    "type": "string",
                    "description": (
                        "XPath expression, used when filter_type=xpath. The XPath runs "
                        "ON THE DEVICE and must be UNPREFIXED — use element names only, "
                        "e.g. '/native/router/bgp' or '/native/ip/access-list'. Do NOT add "
                        "YANG module prefixes like 'Cisco-IOS-XE-native:' — a prefixed "
                        "XPath causes 'RPCError: invalid namespace prefix'. Device must "
                        "support XPath filtering (IOS-XE 16.6+ and NX-OS 9.x do)."
                    ),
                },
            },
            "required": ["device_name"],
        },
    ),

    ToolDefinition(
        name="get_state",
        description=(
            "Retrieve operational state from a device via NETCONF (get, not "
            "get-config). Use this for live counters, interface oper status, "
            "routing tables, BGP/OSPF neighbors. Returns XML state; truncated "
            "if very long. Use filter_type=xpath for surgical queries."
        ),
        parameters={
            "type": "object",
            "properties": {
                "device_name": {
                    "type": "string",
                    "description": "Device name from list_devices.",
                },
                "filter_type": {
                    "type": "string",
                    "enum": ["subtree", "xpath", "none"],
                    "description": (
                        "How to interpret the filter. Prefer 'xpath' for specific "
                        "leaves (e.g. one counter), 'subtree' for whole sections."
                    ),
                },
                "subtree_filter_xml": {
                    "type": "string",
                    "description": "Subtree filter XML, used when filter_type=subtree.",
                },
                "xpath_filter": {
                    "type": "string",
                    "description": (
                        "XPath expression, used when filter_type=xpath. Runs ON THE DEVICE "
                        "and must be UNPREFIXED (element names only), e.g. "
                        "'/native/ip/access-list' or '/interfaces/interface'. Do NOT use "
                        "YANG prefixes like 'Cisco-IOS-XE-native:' — prefixed XPath causes "
                        "'RPCError: invalid namespace prefix'."
                    ),
                },
            },
            "required": ["device_name"],
        },
    ),

    ToolDefinition(
        name="validate_config_xml",
        description=(
            "Validate a NETCONF edit-config payload against the device's "
            "candidate datastore WITHOUT committing. Use this to check XML "
            "well-formedness and YANG compliance before proposing changes. "
            "Returns 'valid' or the validation error message."
        ),
        parameters={
            "type": "object",
            "properties": {
                "device_name": {"type": "string"},
                "config_xml": {
                    "type": "string",
                    "description": (
                        "The <config> XML payload (inner content of edit-config), "
                        "e.g. '<interfaces xmlns=\"...\"><interface>...</interface></interfaces>'."
                    ),
                },
            },
            "required": ["device_name", "config_xml"],
        },
    ),

    ToolDefinition(
        name="propose_edit_config",
        description=(
            "Propose a NETCONF edit-config change. REQUIRES HUMAN APPROVAL — "
            "this tool does NOT commit. It returns the proposed XML and a diff "
            "(current vs proposed) to be shown to the user in an approval modal. "
            "Only call this AFTER you've inspected the running-config and "
            "validated the XML. The user must explicitly approve before the "
            "agent can call apply_edit_config."
        ),
        parameters={
            "type": "object",
            "properties": {
                "device_name": {"type": "string"},
                "config_xml": {
                    "type": "string",
                    "description": "The <config> XML payload to apply.",
                },
                "summary": {
                    "type": "string",
                    "description": (
                        "One-sentence plain-English summary of what this change does, "
                        "shown to the human in the approval modal."
                    ),
                },
            },
            "required": ["device_name", "config_xml", "summary"],
        },
    ),

    ToolDefinition(
        name="apply_edit_config",
        description=(
            "Apply a previously approved NETCONF edit-config payload. Can ONLY "
            "be called with a proposal_id returned by propose_edit_config and "
            "AFTER the user has approved that specific proposal. Commits to the "
            "running datastore."
        ),
        parameters={
            "type": "object",
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "description": "The id returned by propose_edit_config.",
                },
            },
            "required": ["proposal_id"],
        },
    ),
]


def get_netconf_tool_definitions() -> list[ToolDefinition]:
    return list(NETCONF_TOOL_DEFINITIONS)


# Set of names — used by the loop to know which tools require approval.
WRITE_TOOL_NAMES = {"propose_edit_config", "apply_edit_config"}


# ============================================================ #
# Pending-proposal store
# ============================================================ #
# Holds proposals between propose_edit_config (which returns APPROVAL_PENDING)
# and apply_edit_config (which executes the approved XML). Cleared on approval
# decision so a proposal can't be reused.

@dataclass
class PendingProposal:
    proposal_id: str
    device_name: str
    config_xml: str
    summary: str
    diff_text: str = ""
    approved: Optional[bool] = None   # None = waiting, True = approved, False = rejected
    created_at: float = field(default_factory=lambda: __import__("time").time())


_PENDING: dict[str, PendingProposal] = {}


def get_proposal(proposal_id: str) -> Optional[PendingProposal]:
    return _PENDING.get(proposal_id)


def set_proposal_decision(proposal_id: str, approved: bool) -> bool:
    p = _PENDING.get(proposal_id)
    if not p:
        return False
    p.approved = approved
    audit.log_event(
        "approval_decision",
        proposal_id=proposal_id,
        device=p.device_name,
        approved=approved,
    )
    return True


def list_pending_proposals() -> list[dict]:
    return [
        {
            "proposal_id": p.proposal_id,
            "device_name": p.device_name,
            "summary": p.summary,
            "approved": p.approved,
            "created_at": p.created_at,
        }
        for p in _PENDING.values()
    ]


# ============================================================ #
# Helpers — ncclient connection + safe XML helpers
# ============================================================ #

def _resolve_device(name: str) -> tuple[Optional[inventory.Device], str]:
    """Look up a device; return (device, error_message). On success error is empty."""
    if not name:
        return None, "device_name is required"
    d = inventory.get_device(name)
    if not d:
        names = inventory.list_device_names()
        return None, (
            f"No device named '{name}' in inventory. "
            f"Configured devices: {names}. "
            f"Edit ~/.hitech_automation_ai/devices.yaml to add devices."
        )
    if not d.password:
        return None, (
            f"Device '{name}' has no password configured. "
            f"Check {d.raw_password_ref!r} — if it's a $env:VAR reference, "
            f"make sure that variable is set in the service environment."
        )
    return d, ""


def _truncate(text: str, limit: int = MAX_CONFIG_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n... [{len(text) - limit} chars truncated]"


def _make_simple_diff(old_xml: str, new_xml: str, max_lines: int = 200) -> str:
    """Produce a small unified diff text for the approval modal.

    We use difflib instead of an XML-aware diff because (a) it's stdlib,
    (b) edit-config payloads are typically small and well-formatted, and
    (c) the human just needs to spot what's changing — not a semantic merge.
    """
    import difflib
    old_lines = old_xml.splitlines() if old_xml else []
    new_lines = new_xml.splitlines() if new_xml else []
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile="current",
        tofile="proposed",
        lineterm="",
        n=3,
    )
    out = list(diff)
    if len(out) > max_lines:
        out = out[:max_lines] + [f"... [{len(out) - max_lines} more diff lines truncated]"]
    return "\n".join(out) if out else "(no textual differences)"


# ============================================================ #
# NETCONF backend (ncclient) — wrapped to run off the event loop
# ============================================================ #

# v1.7.0 — Long-lived session pool.
# Sessions are stored keyed by (device_name, agent_run_id). The agent loop
# in agent.py calls open_session() at start of run and close_session() at
# end. Tool handlers acquire-or-reopen sessions lazily. If a session is in
# a bad state, the next tool call detects it and recreates it (the retry path).
#
# When NOT in an agent run (one-off chat or direct API call), sessions are
# opened per-call via the `with` context manager — same as v1.6.
_session_pool: dict[tuple[str, str], "object"] = {}
_session_pool_lock = None  # lazy init to avoid asyncio import at module top
_current_agent_run_id: Optional[str] = None  # set by agent.run_agent

def _ensure_lock():
    global _session_pool_lock
    if _session_pool_lock is None:
        import threading
        _session_pool_lock = threading.RLock()
    return _session_pool_lock


def set_agent_run_id(run_id: Optional[str]) -> None:
    """Called by agent.run_agent at start (with id) and end (with None)."""
    global _current_agent_run_id
    _current_agent_run_id = run_id


def _ncclient_connect(d: inventory.Device):
    """Open an ncclient Manager session. Imports ncclient lazily."""
    from ncclient import manager   # lazy import
    return manager.connect(
        host=d.host,
        port=d.port_netconf,
        username=d.username,
        password=d.password,
        hostkey_verify=False,            # lab default; document in INSTALL.md
        device_params={"name": _ncclient_device_name(d.device_type)},
        timeout=NETCONF_TIMEOUT,
        look_for_keys=False,
        allow_agent=False,
    )


def _get_or_open_session(d: inventory.Device, force_reconnect: bool = False):
    """Return a usable ncclient Manager for this device.

    If an agent run is active and a session for (device, run_id) exists and is
    alive, return it. Otherwise open a fresh one and cache it. On force_reconnect
    (used by the retry path), the existing session is discarded first.
    """
    lock = _ensure_lock()
    run_id = _current_agent_run_id
    if not run_id:
        # No agent run — return a one-shot session, caller must close it.
        return _ncclient_connect(d), True

    key = (d.name, run_id)
    with lock:
        existing = _session_pool.get(key)
        if existing is not None and not force_reconnect:
            # Probe is_alive (ncclient Manager has _session.connected attribute)
            try:
                if existing.connected:
                    return existing, False  # False = don't close after use
            except Exception:
                pass
            # Dead session — discard
            try:
                existing.close_session()
            except Exception:
                pass
            del _session_pool[key]
        elif existing is not None and force_reconnect:
            try:
                existing.close_session()
            except Exception:
                pass
            del _session_pool[key]

        m = _ncclient_connect(d)
        _session_pool[key] = m
        log.info("netconf: opened session for %s (run=%s)", d.name, run_id[:12])
        return m, False  # False = pool owns it


def close_all_sessions_for_run(run_id: str) -> int:
    """Called by agent.run_agent at end. Closes pooled sessions for this run."""
    lock = _ensure_lock()
    closed = 0
    with lock:
        for key in list(_session_pool.keys()):
            if key[1] == run_id:
                try:
                    _session_pool[key].close_session()
                except Exception:
                    pass
                del _session_pool[key]
                closed += 1
    if closed:
        log.info("netconf: closed %d pooled session(s) for run=%s", closed, run_id[:12])
    return closed


def _ncclient_device_name(device_type: str) -> str:
    """Map inventory device_type to ncclient's device_params name."""
    mapping = {
        "cisco-iosxe": "iosxe",
        "cisco-nxos": "nexus",
        "cisco-iosxr": "iosxr",
        "juniper-junos": "junos",
    }
    return mapping.get(device_type, "default")


def _build_filter(filter_type: str, subtree_xml: str, xpath: str):
    """Convert v1.7.0 filter_type + payload into ncclient's filter tuple.

    Returns None when filter_type='none' (or no filter supplied), in which case
    the caller should NOT pass a filter argument at all.
    """
    if filter_type == "none":
        return None
    if filter_type == "xpath":
        if not xpath:
            return None
        return ("xpath", xpath)
    # Default: subtree
    if subtree_xml:
        return ("subtree", subtree_xml)
    return None


# v1.7.0: retry helper used by all _sync_* operations
def _with_retry(d: inventory.Device, fn, *args, **kwargs):
    """Run `fn(manager, *args, **kwargs)` with one auto-retry on TransportError.

    Manages session lifecycle (open / reuse / close) and reconnects if the
    first attempt sees the dreaded `Not connected to NETCONF server` error.
    """
    from ncclient.transport.errors import TransportError as NcTransportError

    last_err = None
    for attempt in (1, 2):
        m, must_close = _get_or_open_session(d, force_reconnect=(attempt == 2))
        try:
            result = fn(m, *args, **kwargs)
            return result
        except NcTransportError as e:
            last_err = e
            log.warning("netconf: TransportError attempt %d on %s: %s", attempt, d.name, e)
            if attempt == 1:
                import time
                time.sleep(2)  # brief settle before retry
                continue
            raise
        finally:
            if must_close:
                try:
                    m.close_session()
                except Exception:
                    pass
    raise last_err  # unreachable, but keeps the type checker happy


def _sync_get_config(d: inventory.Device, filter_type: str, subtree_xml: str, xpath: str) -> str:
    def _op(m):
        f = _build_filter(filter_type, subtree_xml, xpath)
        if f is None:
            reply = m.get_config(source="running")
        else:
            reply = m.get_config(source="running", filter=f)
        return str(reply.data_xml)
    return _with_retry(d, _op)


def _sync_get_state(d: inventory.Device, filter_type: str, subtree_xml: str, xpath: str) -> str:
    def _op(m):
        f = _build_filter(filter_type, subtree_xml, xpath)
        if f is None:
            reply = m.get()
        else:
            reply = m.get(filter=f)
        return str(reply.data_xml)
    return _with_retry(d, _op)


def _sync_validate(d: inventory.Device, config_xml: str) -> str:
    """Validate by uploading to the candidate datastore and calling validate."""
    def _op(m):
        # Locking candidate is best-practice; ignore failure (some devices don't support it)
        try:
            m.lock("candidate")
        except Exception:
            pass
        try:
            m.discard_changes()
        except Exception:
            pass
        try:
            m.edit_config(target="candidate", config=_wrap_config(config_xml))
            m.validate(source="candidate")
            m.discard_changes()
            return "valid"
        except Exception as e:
            try:
                m.discard_changes()
            except Exception:
                pass
            return f"validation error: {type(e).__name__}: {e}"
        finally:
            try:
                m.unlock("candidate")
            except Exception:
                pass
    return _with_retry(d, _op)


def _sync_apply(d: inventory.Device, config_xml: str) -> str:
    """Commit the edit-config to running (via candidate + commit)."""
    def _op(m):
        try:
            m.lock("running")
        except Exception:
            pass
        try:
            m.edit_config(target="running", config=_wrap_config(config_xml))
            return "committed to running datastore"
        finally:
            try:
                m.unlock("running")
            except Exception:
                pass
    return _with_retry(d, _op)


def _wrap_config(inner_xml: str) -> str:
    """Wrap a payload in <config> if the user didn't include one."""
    s = inner_xml.strip()
    if s.startswith("<config"):
        return s
    return f'<config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">\n{s}\n</config>'


# ============================================================ #
# Tool implementations (async wrappers around sync ncclient calls)
# ============================================================ #

async def _run_blocking(fn, *args) -> Any:
    """Run a sync function in the default thread pool with a timeout."""
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, fn, *args),
            timeout=NETCONF_TIMEOUT + 10,
        )
    except asyncio.TimeoutError:
        return f"[NETCONF call timed out after {NETCONF_TIMEOUT + 10}s]"


async def tool_list_devices(args: dict) -> str:
    devices = inventory.load_devices()
    if not devices:
        return (
            "Inventory is empty. Edit ~/.hitech_automation_ai/devices.yaml to add "
            "devices. A sample file has been created with placeholder values."
        )
    rows = [inventory.safe_describe(d) for d in devices]
    return "\n".join(
        f"- {r['name']}: host={r['host']} netconf_port={r['port_netconf']} ssh_port={r['port_ssh']} "
        f"type={r['device_type']} user={r['username']} read_only={r['read_only']} "
        f"default={r['default']} password_ref={r['password_ref']} format={r['source_format']}"
        for r in rows
    )


async def tool_get_running_config(args: dict) -> str:
    d, err = _resolve_device(args.get("device_name", ""))
    if err:
        return f"[error] {err}"

    # v1.7.0: filter_type chooses subtree vs xpath vs none
    filter_type = (args.get("filter_type") or "").strip().lower()
    subtree_xml = (args.get("subtree_filter_xml") or "").strip()
    xpath = (args.get("xpath_filter") or "").strip()

    # Backward compat: if old single-key subtree_filter_xml is supplied and
    # filter_type wasn't specified, treat it as subtree.
    if not filter_type:
        if xpath:
            filter_type = "xpath"
        elif subtree_xml:
            filter_type = "subtree"
        else:
            filter_type = "none"

    audit.log_event("tool_call", tool="get_running_config",
                    device=d.name, filter_type=filter_type,
                    has_subtree=bool(subtree_xml), has_xpath=bool(xpath))

    try:
        result = await _run_blocking(_sync_get_config, d, filter_type, subtree_xml, xpath)
    except Exception as e:
        log.exception("get_running_config failed")
        return f"[NETCONF error] {type(e).__name__}: {e}"

    # v1.7.0: wrap with RAW_XML markers so the LLM (per system prompt) echoes
    # the XML verbatim in a code block when the user explicitly asks for it.
    truncated = _truncate(result)
    return f"[RAW_XML_OUTPUT device={d.name} op=get-config filter={filter_type}]\n{truncated}\n[END_RAW_XML_OUTPUT]"


async def tool_get_state(args: dict) -> str:
    d, err = _resolve_device(args.get("device_name", ""))
    if err:
        return f"[error] {err}"

    filter_type = (args.get("filter_type") or "").strip().lower()
    subtree_xml = (args.get("subtree_filter_xml") or "").strip()
    xpath = (args.get("xpath_filter") or "").strip()

    if not filter_type:
        if xpath:
            filter_type = "xpath"
        elif subtree_xml:
            filter_type = "subtree"
        else:
            filter_type = "none"

    audit.log_event("tool_call", tool="get_state",
                    device=d.name, filter_type=filter_type,
                    has_subtree=bool(subtree_xml), has_xpath=bool(xpath))

    try:
        result = await _run_blocking(_sync_get_state, d, filter_type, subtree_xml, xpath)
    except Exception as e:
        log.exception("get_state failed")
        return f"[NETCONF error] {type(e).__name__}: {e}"

    truncated = _truncate(result)
    return f"[RAW_XML_OUTPUT device={d.name} op=get-state filter={filter_type}]\n{truncated}\n[END_RAW_XML_OUTPUT]"


async def tool_validate_config_xml(args: dict) -> str:
    d, err = _resolve_device(args.get("device_name", ""))
    if err:
        return f"[error] {err}"

    config_xml = args.get("config_xml", "")
    if not config_xml.strip():
        return "[error] config_xml is required"

    audit.log_event("tool_call", tool="validate_config_xml", device=d.name)

    try:
        result = await _run_blocking(_sync_validate, d, config_xml)
    except Exception as e:
        log.exception("validate_config_xml failed")
        return f"[NETCONF error] {type(e).__name__}: {e}"

    return result


async def tool_propose_edit_config(args: dict) -> dict:
    """Stage an edit-config; return APPROVAL_PENDING marker for the agent loop."""
    d, err = _resolve_device(args.get("device_name", ""))
    if err:
        return {"error": err}

    config_xml = (args.get("config_xml") or "").strip()
    summary = (args.get("summary") or "").strip()

    if not config_xml:
        return {"error": "config_xml is required"}
    if d.read_only:
        return {
            "error": (
                f"Device '{d.name}' is marked read_only=true in the inventory. "
                f"To allow writes, edit ~/.hitech_automation_ai/devices.yaml and set "
                f"read_only: false for this device."
            )
        }

    # Fetch current config (best effort) for the diff display
    current_xml = ""
    try:
        current_xml = await _run_blocking(_sync_get_config, d, "none", "", "")
        current_xml = _truncate(current_xml)
    except Exception as e:
        log.warning("propose_edit_config: could not fetch current config for diff: %s", e)
        current_xml = f"(could not fetch current config: {type(e).__name__}: {e})"

    diff_text = _make_simple_diff(current_xml, config_xml)
    proposal_id = "prop_" + uuid.uuid4().hex[:12]
    _PENDING[proposal_id] = PendingProposal(
        proposal_id=proposal_id,
        device_name=d.name,
        config_xml=config_xml,
        summary=summary or "(no summary provided)",
        diff_text=diff_text,
    )

    audit.log_event(
        "approval_request",
        proposal_id=proposal_id,
        device=d.name,
        summary=summary,
        config_xml_preview=config_xml[:1500],
    )

    return {
        APPROVAL_PENDING: True,
        "proposal_id": proposal_id,
        "device_name": d.name,
        "summary": summary,
        "diff_text": diff_text,
        "config_xml": config_xml,
    }


async def tool_apply_edit_config(args: dict) -> str:
    proposal_id = (args.get("proposal_id") or "").strip()
    if not proposal_id:
        return "[error] proposal_id is required"

    p = _PENDING.get(proposal_id)
    if not p:
        return f"[error] No pending proposal with id {proposal_id!r}. "\
               f"Call propose_edit_config first."
    if p.approved is None:
        return f"[error] Proposal {proposal_id} is still awaiting human approval."
    if p.approved is False:
        return f"[error] Proposal {proposal_id} was rejected by the user."

    d, err = _resolve_device(p.device_name)
    if err:
        return f"[error] {err}"
    if d.read_only:
        return f"[error] Device '{d.name}' is read_only=true; refusing to commit."

    audit.log_event("write_applied_start", proposal_id=proposal_id, device=d.name)
    try:
        result = await _run_blocking(_sync_apply, d, p.config_xml)
    except Exception as e:
        log.exception("apply_edit_config failed")
        audit.log_event(
            "write_applied_error",
            proposal_id=proposal_id, device=d.name,
            error=f"{type(e).__name__}: {e}",
        )
        return f"[NETCONF error] {type(e).__name__}: {e}"

    audit.log_event(
        "write_applied_ok",
        proposal_id=proposal_id, device=d.name, result=result,
    )

    # Remove from pending after successful apply
    _PENDING.pop(proposal_id, None)
    return result


# ============================================================ #
# Dispatcher table — for the executor.execute_tool registry
# ============================================================ #

NETCONF_HANDLERS = {
    "list_devices":          tool_list_devices,
    "get_running_config":    tool_get_running_config,
    "get_state":             tool_get_state,
    "validate_config_xml":   tool_validate_config_xml,
    "propose_edit_config":   tool_propose_edit_config,
    "apply_edit_config":     tool_apply_edit_config,
}
