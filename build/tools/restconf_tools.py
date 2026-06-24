"""
RESTCONF tool implementations for the agentic loop (v1.7.0).

These tools mirror the NETCONF flow but use HTTPS + JSON instead of SSH + XML.
RESTCONF is generally easier for agents because:
  - JSON payloads are smaller and less error-prone than XML
  - HTTP verbs (GET/POST/PUT/PATCH/DELETE) map cleanly to NETCONF operations
  - Discovery is simpler via ietf-yang-library

Tool list:
  - restconf_get                   : read state/config (HTTP GET)
  - restconf_list_capabilities     : list YANG modules supported by device
  - propose_restconf_post          : create new resource (approval-gated)
  - propose_restconf_put           : replace resource (approval-gated)
  - propose_restconf_patch         : merge into resource (approval-gated)
  - propose_restconf_delete        : remove resource (approval-gated)
  - apply_restconf_change          : commit an approved proposal

Write operations follow the same approval flow as NETCONF: propose_* returns
a proposal_id, the GUI shows a diff modal, the user approves/rejects, then
apply_restconf_change commits.

Device prerequisites:
  IOS-XE:    `restconf` + `ip http secure-server` + `aaa new-model`
  NX-OS:     `feature nxapi` + `nxapi https port 443`

Lab default: restconf_verify_tls=False (self-signed certs are common in labs).
Production: set restconf_verify_tls=True after installing a real CA cert.
"""

import asyncio
import base64
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from tools import inventory, audit

log = logging.getLogger(__name__)


# ----------------------------------------------------------------- #
# Tool definitions for the agent registry                           #
# ----------------------------------------------------------------- #

# These mirror the ToolDefinition shape in netconf_tools.py. Imported by
# tools.definitions and exposed to the LLM through the tool schema.

from tools.netconf_tools import ToolDefinition  # reuse the same dataclass


RESTCONF_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="restconf_get",
        description=(
            "Retrieve state or config from a device via RESTCONF (HTTP GET). "
            "Returns JSON. Prefer this over NETCONF for simple reads — JSON is "
            "smaller and easier to parse than XML. Prefer OpenConfig YANG paths "
            "over native Cisco-IOS-XE-* paths when both are available."
        ),
        parameters={
            "type": "object",
            "properties": {
                "device_name": {
                    "type": "string",
                    "description": "Device name from list_devices.",
                },
                "yang_path": {
                    "type": "string",
                    "description": (
                        "YANG path relative to restconf_root, e.g. "
                        "'Cisco-IOS-XE-native:native/router/router-bgp/bgp' or "
                        "'openconfig-bgp:bgp/neighbors'. Do NOT include a leading slash. "
                        "NOTE: this is a full RESTCONF data path and DOES use the module "
                        "prefix (unlike on-device NETCONF XPath, which is unprefixed). Get "
                        "the container nesting right — e.g. ACLs live under "
                        "'Cisco-IOS-XE-native:native/ip/access-list', not directly under "
                        "'native/access-list'. If a GET 404s, the path nesting is usually "
                        "the cause; verify against the device's YANG model."
                    ),
                },
                "depth": {
                    "type": "integer",
                    "description": (
                        "Optional depth limit (RESTCONF ?depth=N query parameter). "
                        "Use small values like 3-5 to keep responses manageable."
                    ),
                },
            },
            "required": ["device_name", "yang_path"],
        },
    ),
    ToolDefinition(
        name="restconf_list_capabilities",
        description=(
            "List YANG modules supported by a device via RESTCONF "
            "(ietf-yang-library:modules-state). Use this to discover what "
            "models are available before crafting RESTCONF paths."
        ),
        parameters={
            "type": "object",
            "properties": {
                "device_name": {"type": "string"},
            },
            "required": ["device_name"],
        },
    ),
    ToolDefinition(
        name="propose_restconf_post",
        description=(
            "Propose a RESTCONF POST (create new resource). Requires user "
            "approval before being applied. Returns a proposal_id."
        ),
        parameters={
            "type": "object",
            "properties": {
                "device_name": {"type": "string"},
                "yang_path": {
                    "type": "string",
                    "description": "Parent path under which to create the new resource.",
                },
                "json_payload": {
                    "type": "string",
                    "description": "JSON body to POST. Must be valid JSON.",
                },
                "summary": {
                    "type": "string",
                    "description": "One-sentence human description of what this change does.",
                },
            },
            "required": ["device_name", "yang_path", "json_payload", "summary"],
        },
    ),
    ToolDefinition(
        name="propose_restconf_put",
        description=(
            "Propose a RESTCONF PUT (replace resource). Requires approval. "
            "Use this to fully replace a resource — semantics differ from PATCH."
        ),
        parameters={
            "type": "object",
            "properties": {
                "device_name": {"type": "string"},
                "yang_path": {"type": "string"},
                "json_payload": {"type": "string"},
                "summary": {"type": "string"},
            },
            "required": ["device_name", "yang_path", "json_payload", "summary"],
        },
    ),
    ToolDefinition(
        name="propose_restconf_patch",
        description=(
            "Propose a RESTCONF PATCH (merge into resource). Requires approval. "
            "Use this to add/modify specific leaves without replacing siblings."
        ),
        parameters={
            "type": "object",
            "properties": {
                "device_name": {"type": "string"},
                "yang_path": {"type": "string"},
                "json_payload": {"type": "string"},
                "summary": {"type": "string"},
            },
            "required": ["device_name", "yang_path", "json_payload", "summary"],
        },
    ),
    ToolDefinition(
        name="propose_restconf_delete",
        description=(
            "Propose a RESTCONF DELETE (remove resource). Requires approval. "
            "BE CAREFUL — deletes are destructive."
        ),
        parameters={
            "type": "object",
            "properties": {
                "device_name": {"type": "string"},
                "yang_path": {
                    "type": "string",
                    "description": "Exact path to the resource to delete.",
                },
                "summary": {"type": "string"},
            },
            "required": ["device_name", "yang_path", "summary"],
        },
    ),
    ToolDefinition(
        name="apply_restconf_change",
        description=(
            "Apply an approved RESTCONF change by proposal_id. Only callable "
            "after the user has approved the proposal in the GUI."
        ),
        parameters={
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string"},
            },
            "required": ["proposal_id"],
        },
    ),
]


# ----------------------------------------------------------------- #
# Pending RESTCONF proposals (same approval flow as NETCONF)        #
# ----------------------------------------------------------------- #

@dataclass
class PendingRestconfProposal:
    proposal_id: str
    device_name: str
    method: str        # POST | PUT | PATCH | DELETE
    yang_path: str
    json_payload: str  # empty for DELETE
    summary: str
    approved: Optional[bool] = None
    applied: bool = False


_RESTCONF_PENDING: dict[str, PendingRestconfProposal] = {}


def get_restconf_proposal(proposal_id: str) -> Optional[PendingRestconfProposal]:
    return _RESTCONF_PENDING.get(proposal_id)


def set_restconf_decision(proposal_id: str, approved: bool) -> bool:
    p = _RESTCONF_PENDING.get(proposal_id)
    if not p:
        return False
    p.approved = approved
    return True


def list_pending_restconf() -> list[PendingRestconfProposal]:
    return [p for p in _RESTCONF_PENDING.values() if p.approved is None]


# ----------------------------------------------------------------- #
# HTTP backend                                                       #
# ----------------------------------------------------------------- #

def _basic_auth(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def _restconf_url(d: inventory.Device, yang_path: str) -> str:
    """Build the full URL for a RESTCONF request."""
    path = yang_path.lstrip("/")
    root = d.restconf_root.rstrip("/")
    return f"https://{d.host}:{d.port_restconf}{root}/{path}"


async def _http_request(
    method: str,
    url: str,
    headers: dict,
    body: Optional[str] = None,
    verify: bool = False,
    timeout: float = 30.0,
) -> tuple[int, str]:
    """Wrap httpx call. Runs in thread pool to avoid blocking."""
    import httpx

    def _sync_call() -> tuple[int, str]:
        with httpx.Client(verify=verify, timeout=timeout) as client:
            try:
                r = client.request(method, url, headers=headers, content=body)
                return r.status_code, r.text
            except httpx.RequestError as e:
                return 0, f"[RESTCONF connection error] {type(e).__name__}: {e}"

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_call)


def _resolve_device(name: str) -> tuple[Optional[inventory.Device], Optional[str]]:
    """Mirror of netconf_tools._resolve_device — kept local to avoid coupling."""
    if not name:
        return None, "device_name is required"
    devices = inventory.load_devices()
    for d in devices:
        if d.name == name:
            return d, None
    if devices:
        names = ", ".join(d.name for d in devices)
        return None, f"unknown device {name!r}. Known: {names}"
    return None, "inventory is empty"


# ----------------------------------------------------------------- #
# Tool handlers                                                      #
# ----------------------------------------------------------------- #

async def tool_restconf_get(args: dict) -> str:
    d, err = _resolve_device(args.get("device_name", ""))
    if err:
        return f"[error] {err}"

    yang_path = (args.get("yang_path") or "").strip()
    if not yang_path:
        return "[error] yang_path is required"

    depth = args.get("depth")
    url = _restconf_url(d, yang_path)
    if depth:
        try:
            url += f"?depth={int(depth)}"
        except (TypeError, ValueError):
            pass

    headers = {
        "Authorization": _basic_auth(d.username, d.password),
        "Accept": "application/yang-data+json",
    }
    audit.log_event("tool_call", tool="restconf_get",
                    device=d.name, yang_path=yang_path)

    status, body = await _http_request("GET", url, headers, verify=d.restconf_verify_tls)
    if status == 0:
        return body
    if status == 204:
        # v1.8.0 — 204 hint: the YANG path is valid in the schema but contains no data.
        # Often this means a legacy path name (e.g. "ospf" vs "router-ospf" on IOS-XE 17.x).
        return (
            f"[RAW_RESTCONF_OUTPUT device={d.name} method=GET path={yang_path} status=204]\n"
            f"HTTP 204 No Content — the YANG path is valid but the device returned no data.\n"
            f"Common causes:\n"
            f"  1. Wrong container name. On IOS-XE 16.6+, OSPF config lives at\n"
            f"     'Cisco-IOS-XE-native:native/router/router-ospf' (not 'ospf').\n"
            f"     Other renamed containers: router-bgp, router-ospfv3, router-eigrp.\n"
            f"  2. The standalone module isn't installed (e.g. 'Cisco-IOS-XE-ospf'\n"
            f"     module is missing on some cat8000v images — use the native path).\n"
            f"  3. The feature genuinely isn't configured.\n"
            f"Verify what's installed: GET /restconf/data/ietf-yang-library:modules-state\n"
            f"[END_RAW_RESTCONF_OUTPUT]"
        )
    if 200 <= status < 300:
        # Wrap with raw markers like the NETCONF tools do
        return (
            f"[RAW_RESTCONF_OUTPUT device={d.name} method=GET path={yang_path} status={status}]\n"
            f"{_truncate(body)}\n"
            f"[END_RAW_RESTCONF_OUTPUT]"
        )
    return f"[RESTCONF HTTP {status}] {_truncate(body, 1200)}"


async def tool_restconf_list_capabilities(args: dict) -> str:
    d, err = _resolve_device(args.get("device_name", ""))
    if err:
        return f"[error] {err}"

    url = _restconf_url(d, "ietf-yang-library:modules-state")
    headers = {
        "Authorization": _basic_auth(d.username, d.password),
        "Accept": "application/yang-data+json",
    }
    audit.log_event("tool_call", tool="restconf_list_capabilities", device=d.name)

    status, body = await _http_request("GET", url, headers, verify=d.restconf_verify_tls)
    if status == 0:
        return body
    if 200 <= status < 300:
        # Parse + summarize so the LLM doesn't drown in 50k+ tokens of capability data
        try:
            data = json.loads(body)
            modules = (data.get("ietf-yang-library:modules-state", {})
                          .get("module", []))
            names = sorted({m.get("name", "") for m in modules})
            # Highlight OpenConfig + commonly useful modules first
            oc = [n for n in names if n.startswith("openconfig-")]
            cisco = [n for n in names if n.startswith("Cisco-IOS-XE-")][:30]
            other = [n for n in names if not n.startswith("openconfig-")
                     and not n.startswith("Cisco-IOS-XE-")][:30]
            return (
                f"Device {d.name} supports {len(names)} YANG modules.\n\n"
                f"OpenConfig ({len(oc)}): {', '.join(oc) if oc else '(none)'}\n\n"
                f"Cisco-IOS-XE-* (first 30 of {sum(1 for n in names if n.startswith('Cisco-IOS-XE-'))}):\n"
                f"  {', '.join(cisco)}\n\n"
                f"Other (first 30): {', '.join(other)}"
            )
        except Exception as e:
            log.warning("restconf capabilities parse failed: %s", e)
            return _truncate(body, 3000)
    return f"[RESTCONF HTTP {status}] {_truncate(body, 1200)}"


async def _propose_write(args: dict, method: str) -> dict:
    """Shared core for propose_restconf_post/put/patch/delete."""
    d, err = _resolve_device(args.get("device_name", ""))
    if err:
        return {"_error": err}
    if d.read_only:
        return {"_error": f"device {d.name!r} is marked read_only=true in inventory; refusing write"}

    yang_path = (args.get("yang_path") or "").strip()
    json_payload = args.get("json_payload", "")
    summary = args.get("summary", "").strip()

    if not yang_path:
        return {"_error": "yang_path is required"}
    if method != "DELETE" and not json_payload.strip():
        return {"_error": "json_payload is required for non-DELETE methods"}
    if not summary:
        return {"_error": "summary is required (one-sentence description)"}

    # Validate JSON for non-DELETE
    if method != "DELETE":
        try:
            json.loads(json_payload)
        except json.JSONDecodeError as e:
            return {"_error": f"json_payload is not valid JSON: {e}"}

    proposal_id = "rcprop_" + uuid.uuid4().hex[:12]
    _RESTCONF_PENDING[proposal_id] = PendingRestconfProposal(
        proposal_id=proposal_id,
        device_name=d.name,
        method=method,
        yang_path=yang_path,
        json_payload=json_payload,
        summary=summary,
    )

    audit.log_event("propose_restconf",
                    proposal_id=proposal_id, device=d.name,
                    method=method, yang_path=yang_path, summary=summary)

    return {
        "_approval_pending": True,
        "proposal_id": proposal_id,
        "device_name": d.name,
        "method": method,
        "yang_path": yang_path,
        "json_payload": json_payload,
        "summary": summary,
        "url": _restconf_url(d, yang_path),
    }


async def tool_propose_restconf_post(args: dict) -> dict:
    return await _propose_write(args, "POST")


async def tool_propose_restconf_put(args: dict) -> dict:
    return await _propose_write(args, "PUT")


async def tool_propose_restconf_patch(args: dict) -> dict:
    return await _propose_write(args, "PATCH")


async def tool_propose_restconf_delete(args: dict) -> dict:
    return await _propose_write(args, "DELETE")


async def tool_apply_restconf_change(args: dict) -> str:
    proposal_id = (args.get("proposal_id") or "").strip()
    p = _RESTCONF_PENDING.get(proposal_id)
    if not p:
        return f"[error] unknown proposal_id {proposal_id!r}"
    if p.approved is not True:
        return f"[error] proposal {proposal_id!r} has not been approved (state: approved={p.approved})"
    if p.applied:
        return f"[error] proposal {proposal_id!r} was already applied"

    d, err = _resolve_device(p.device_name)
    if err:
        return f"[error] {err}"

    url = _restconf_url(d, p.yang_path)
    headers = {
        "Authorization": _basic_auth(d.username, d.password),
        "Accept": "application/yang-data+json",
        "Content-Type": "application/yang-data+json",
    }
    body = p.json_payload if p.method != "DELETE" else None

    audit.log_event("apply_restconf",
                    proposal_id=proposal_id, device=d.name,
                    method=p.method, yang_path=p.yang_path)

    status, response_body = await _http_request(
        p.method, url, headers, body=body, verify=d.restconf_verify_tls
    )

    if 200 <= status < 300:
        p.applied = True
        return f"applied {p.method} {p.yang_path} on {d.name} (HTTP {status})"
    return f"[RESTCONF apply failed] HTTP {status}: {_truncate(response_body, 800)}"


# ----------------------------------------------------------------- #
# Helpers                                                            #
# ----------------------------------------------------------------- #

def _truncate(s: str, n: int = 12_000) -> str:
    if len(s) <= n:
        return s
    return s[:n] + f"\n... [truncated, total length {len(s)}]"
