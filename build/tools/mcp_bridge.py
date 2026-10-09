"""MCP bridge — tools from an external MCP server for the agent (v1.51.0).

First server: cml-mcp (Cisco Modeling Labs, https://pypi.org/project/cml-mcp).
Its tools appear to the agent as ``cml_<tool>``. Reads run straight away;
anything that changes the lab goes through the same approval modal as the
NETCONF/RESTCONF writes. Destructive and admin tools (delete/wipe, users,
licensing, building topologies) are never offered.

A small built-in MCP client (JSON-RPC 2.0) speaks two transports, so nothing
new has to be installed in this app's Python:

  stdio  starts the server itself, default ``uvx --python 3.12 cml-mcp[pyats]``
         (cml-mcp needs Python 3.12+; uv fetches it), CML login passed as env
  http   an already running cml-mcp in HTTP mode (CML_MCP_TRANSPORT=http);
         the CML address and login travel as X-CML-URL / X-Authorization

Configuration — ~/.hitech_automation_ai/cml_mcp.yaml (or environment):

  enabled: true
  cml_url: https://192.168.89.100        # env CML_URL
  username: admin                        # env CML_USERNAME
  password: ...                          # env CML_PASSWORD (prefer env)
  verify_ssl: false                      # CML ships a self-signed certificate
  transport: stdio                       # or http
  command: uvx --python 3.12 cml-mcp[pyats]
  http_url: http://127.0.0.1:9000/mcp    # env CML_MCP_URL (transport http)
  tools: safe                            # safe (default) | read | all-safe-and-writes list…

Public site (PUBLIC_MODE=1, v1.52.0): no server is ever started in a worker and
no CML login is ever seen by it. When the gateway hands the worker CML_MCP_UDS +
CML_MCP_TOKEN (signed-in users with lab access only), the worker speaks MCP to
the gateway's unix socket; the gateway runs cml-mcp for THAT user's own CML,
offers only the safe tools (no console CLI) and refuses everything else.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx

from llm_providers import ToolDefinition

log = logging.getLogger("agent.mcp")

PREFIX = "cml_"
PROTOCOL_VERSION = "2025-06-18"
CALL_TIMEOUT = float(os.environ.get("CML_MCP_CALL_TIMEOUT", "180"))   # pyATS logins are slow
START_TIMEOUT = float(os.environ.get("CML_MCP_START_TIMEOUT", "180"))  # first uvx run downloads
MAX_RESULT_CHARS = 12_000
MAX_DESC_CHARS = 900          # every tool description is sent with every request

# What the agent may use. Everything else cml-mcp offers is never shown to the model.
READ_TOOLS = {
    "get_cml_labs", "get_cml_lab_by_title", "get_nodes_for_cml_lab", "get_all_links_for_lab",
    "get_interfaces_for_node", "get_console_log", "get_cml_status", "get_cml_information",
    "check_packet_capture_status", "get_captured_packet_overview",
}
WRITE_TOOLS = {          # need the user's approval, every time
    "start_cml_node", "stop_cml_node", "start_cml_link", "stop_cml_link",
    "apply_link_conditioning", "start_packet_capture", "stop_packet_capture",
    "start_cml_lab", "stop_cml_lab",
}
# send_cli_command: show/ping/traceroute only run straight away; config mode or any
# other command needs approval.
CLI_TOOL = "send_cli_command"
_READ_CLI = ("show ", "ping ", "traceroute ", "dir ", "more ")
NEVER = {                # not offered even if asked for
    "delete_cml_lab", "wipe_cml_lab", "wipe_cml_node", "delete_cml_node", "create_cml_user",
    "delete_cml_user", "create_cml_group", "delete_cml_group", "set_cml_lab_permissions",
}

APPROVAL_PENDING = "_approval_pending"      # same marker as tools.netconf_tools

SYSTEM_HINT = (
    "\n\nCISCO MODELING LABS (cml_* tools):\n"
    "  - These act on the CML server itself (labs, nodes, links, consoles, packet "
    "captures), not on devices from the inventory.\n"
    "  - Start with cml_get_cml_labs to find the lab id, then cml_get_nodes_for_cml_lab "
    "for node labels and states. Nodes are named by label (e.g. cat8Kv71).\n"
    "  - Call cml_get_cml_labs WITHOUT arguments and match the lab by its title "
    "(lab_title). Its 'user' argument filters by lab OWNER — a lab title is not a user name.\n"
    "  - cml_send_cli_command runs show/ping/traceroute on a node's console directly; "
    "configuration (config_command=true) or other commands need the user's approval, "
    "as do starting/stopping nodes, links and labs, link conditioning and packet captures.\n"
    "  - Prefer the inventory tools (run_show_command, restconf_get, NETCONF) for device "
    "state when the device is in the inventory; use CML tools for the lab itself or for "
    "nodes that are not reachable over the network."
)


# ------------------------------------------------------------------ configuration
@dataclass
class Settings:
    enabled: bool = False
    cml_url: str = ""
    username: str = ""
    password: str = ""
    verify_ssl: bool = False
    transport: str = "stdio"
    command: str = "uvx --python 3.12 cml-mcp[pyats]"
    http_url: str = "http://127.0.0.1:9000/mcp"
    tools: str = "safe"                       # safe | read


def _state_dir() -> Path:
    try:
        from tools.state_dir import STATE_DIR
        return Path(STATE_DIR)
    except Exception:
        return Path.home() / ".hitech_automation_ai"


def load_settings() -> Settings:
    if _public_mode():
        # never the yaml or CML_* env here — only the gateway socket, if the gateway offered it
        uds, tok = os.environ.get("CML_MCP_UDS", ""), os.environ.get("CML_MCP_TOKEN", "")
        return Settings(enabled=bool(uds and tok), transport="gateway",
                        cml_url="your lab's CML", http_url=uds, tools="safe")
    s = Settings()
    f = _state_dir() / "cml_mcp.yaml"
    if f.exists():
        try:
            import yaml
            data = yaml.safe_load(f.read_text()) or {}
            for k, v in data.items():
                if hasattr(s, k) and v is not None:
                    setattr(s, k, v)
        except Exception as e:
            log.warning("cml_mcp.yaml unreadable: %s", e)
    env = os.environ
    s.cml_url = env.get("CML_URL", s.cml_url)
    s.username = env.get("CML_USERNAME", s.username)
    s.password = env.get("CML_PASSWORD", s.password)
    s.http_url = env.get("CML_MCP_URL", s.http_url)
    if env.get("CML_MCP_TRANSPORT_CLIENT"):
        s.transport = env["CML_MCP_TRANSPORT_CLIENT"]
    if env.get("HITECH_CML_MCP") in ("1", "true", "on"):
        s.enabled = True
    if env.get("HITECH_CML_MCP") in ("0", "false", "off"):
        s.enabled = False
    s.enabled = bool(s.enabled) and bool(s.cml_url)
    if _public_mode():
        s.enabled = False
    return s


def _public_mode() -> bool:
    if os.environ.get("PUBLIC_MODE") == "1":
        return True
    try:
        import public_guard
        return bool(public_guard.PUBLIC_MODE)
    except Exception:
        return False


# ------------------------------------------------------------------ transports
class MCPError(RuntimeError):
    pass


class _StdioTransport:
    def __init__(self, argv: list[str], env: dict):
        self.argv, self.env = argv, env
        self.proc: Optional[asyncio.subprocess.Process] = None
        self._pending: dict[int, asyncio.Future] = {}
        self._reader: Optional[asyncio.Task] = None
        self._stderr_tail: list[str] = []

    async def start(self):
        self.proc = await asyncio.create_subprocess_exec(
            *self.argv, env=self.env, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            limit=16 * 1024 * 1024)
        self._reader = asyncio.create_task(self._read_stdout())
        asyncio.create_task(self._read_stderr())

    async def _read_stderr(self):
        assert self.proc and self.proc.stderr
        async for line in self.proc.stderr:
            t = line.decode(errors="replace").rstrip()
            self._stderr_tail = (self._stderr_tail + [t])[-20:]
            log.debug("cml-mcp: %s", t)

    async def _read_stdout(self):
        assert self.proc and self.proc.stdout
        async for line in self.proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            await self._dispatch(msg)
        err = MCPError("cml-mcp exited: " + " | ".join(self._stderr_tail[-3:]))
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(err)
        self._pending.clear()

    async def _dispatch(self, msg: dict):
        if "id" in msg and ("result" in msg or "error" in msg):
            fut = self._pending.pop(msg["id"], None)
            if fut and not fut.done():
                fut.set_result(msg)
        elif "id" in msg and "method" in msg:          # server→client request: not supported
            await self.send({"jsonrpc": "2.0", "id": msg["id"],
                             "error": {"code": -32601, "message": "not supported"}})

    def alive(self) -> bool:
        return bool(self.proc and self.proc.returncode is None)

    async def send(self, msg: dict):
        if not self.alive():
            raise MCPError("cml-mcp is not running")
        self.proc.stdin.write((json.dumps(msg) + "\n").encode())
        await self.proc.stdin.drain()

    async def request(self, msg: dict, timeout: float) -> dict:
        fut = asyncio.get_running_loop().create_future()
        self._pending[msg["id"]] = fut
        await self.send(msg)
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self._pending.pop(msg["id"], None)

    async def close(self):
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), 5)
            except asyncio.TimeoutError:
                self.proc.kill()


class _HttpTransport:
    """MCP 'streamable HTTP': JSON-RPC POSTs; answers come as JSON or as SSE."""

    def __init__(self, url: str, headers: dict, verify: bool = True, transport=None):
        self.url, self.headers = url, dict(headers)
        self.session_id: Optional[str] = None
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(CALL_TIMEOUT, connect=10),
                                        verify=verify, transport=transport, trust_env=False)

    async def start(self):
        pass

    def alive(self) -> bool:
        return True

    def _h(self) -> dict:
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
             "MCP-Protocol-Version": PROTOCOL_VERSION, **self.headers}
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    async def send(self, msg: dict):
        r = await self.client.post(self.url, json=msg, headers=self._h())
        if r.status_code >= 400:
            raise MCPError(f"HTTP {r.status_code} from cml-mcp: {r.text[:200]}")

    async def request(self, msg: dict, timeout: float) -> dict:
        r = await asyncio.wait_for(self.client.post(self.url, json=msg, headers=self._h()), timeout)
        if r.headers.get("mcp-session-id"):
            self.session_id = r.headers["mcp-session-id"]
        if r.status_code == 403:
            raise MCPError("cml-mcp refused this tool (ACL)")
        if r.status_code >= 400:
            raise MCPError(f"HTTP {r.status_code} from cml-mcp: {r.text[:200]}")
        ctype = r.headers.get("content-type", "")
        if "text/event-stream" in ctype:
            for block in r.text.split("\n\n"):
                data = "\n".join(l[5:].lstrip() for l in block.splitlines() if l.startswith("data:"))
                if not data:
                    continue
                try:
                    m = json.loads(data)
                except ValueError:
                    continue
                if m.get("id") == msg["id"]:
                    return m
            raise MCPError("no answer in cml-mcp's event stream")
        return r.json()

    async def close(self):
        await self.client.aclose()


class _GatewayTransport:
    """Public site: MCP JSON-RPC to the gateway's unix socket (per-worker token).

    The gateway answers 409 while the user has no running routers/switches lab,
    or while its CML is still booting; then this transport counts as down, so the
    next agent run asks again and the cml_* tools appear once the lab is up."""

    def __init__(self, uds: str, token: str):
        self.token, self.ok = token, False
        self.client = httpx.AsyncClient(
            base_url="http://gateway", trust_env=False,
            timeout=httpx.Timeout(CALL_TIMEOUT + 30, connect=5),
            transport=httpx.AsyncHTTPTransport(uds=uds))

    async def start(self):
        self.ok = True

    def alive(self) -> bool:
        return self.ok

    async def _post(self, msg: dict) -> httpx.Response:
        r = await self.client.post("/rpc", json=msg, headers={"x-api-key": self.token})
        if r.status_code >= 400:
            self.ok = False
            try:
                detail = r.json().get("error") or r.text
            except ValueError:
                detail = r.text
            raise MCPError(str(detail)[:300])
        return r

    async def send(self, msg: dict):
        await self._post(msg)

    async def request(self, msg: dict, timeout: float) -> dict:
        r = await asyncio.wait_for(self._post(msg), timeout + 30)
        return r.json()

    async def close(self):
        self.ok = False
        await self.client.aclose()


# ------------------------------------------------------------------ client
class MCPClient:
    def __init__(self, transport):
        self.t = transport
        self._id = 0
        self._lock = asyncio.Lock()
        self.tools: list[dict] = []

    async def _call(self, method: str, params: Optional[dict] = None, timeout: float = CALL_TIMEOUT):
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            msg["params"] = params
        resp = await self.t.request(msg, timeout)
        if "error" in resp:
            e = resp["error"]
            raise MCPError(f"{e.get('message', 'error')} ({e.get('code')})")
        return resp.get("result", {})

    async def start(self):
        await self.t.start()
        await self._call("initialize", {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "hitech-automation-ai", "version": "1.51"}}, timeout=START_TIMEOUT)
        await self.t.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools, cursor = [], None
        while True:
            res = await self._call("tools/list", {"cursor": cursor} if cursor else {})
            tools += res.get("tools", [])
            cursor = res.get("nextCursor")
            if not cursor:
                break
        self.tools = tools

    async def call_tool(self, name: str, args: dict) -> tuple[str, bool]:
        async with self._lock:          # one call at a time per server
            res = await self._call("tools/call", {"name": name, "arguments": args})
        parts = []
        for c in res.get("content") or []:
            if c.get("type") == "text":
                parts.append(c.get("text", ""))
            else:
                parts.append(f"[{c.get('type')} content omitted]")
        text = "\n".join(p for p in parts if p)
        if not text and res.get("structuredContent") is not None:
            text = json.dumps(res["structuredContent"], indent=1)
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + f"\n… [truncated, {len(text)} chars]"
        return text or "(no output)", bool(res.get("isError"))

    def alive(self) -> bool:
        return self.t.alive()

    async def close(self):
        await self.t.close()


# ------------------------------------------------------------------ the bridge
_client: Optional[MCPClient] = None
_client_key: Optional[tuple] = None
_start_lock: Optional[asyncio.Lock] = None
_last_error = ""


def _allowed(name: str, mode: str) -> bool:
    if name in NEVER:
        return False
    if mode == "read":
        return name in READ_TOOLS or name == CLI_TOOL
    return name in READ_TOOLS or name in WRITE_TOOLS or name == CLI_TOOL


def _make_transport(s: Settings):
    if s.transport == "gateway":
        return _GatewayTransport(s.http_url, os.environ.get("CML_MCP_TOKEN", ""))
    if s.transport == "http":
        cred = f"{s.username}:{s.password}" if s.username else ""
        headers = {"X-CML-URL": s.cml_url}
        if cred:
            headers["X-Authorization"] = cred
        return _HttpTransport(s.http_url, headers)
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "TMPDIR", "UV_CACHE_DIR", "XDG_CACHE_HOME")}
    env.update({"CML_URL": s.cml_url, "CML_USERNAME": s.username, "CML_PASSWORD": s.password,
                "CML_VERIFY_SSL": "true" if s.verify_ssl else "false",
                "PYATS_USERNAME": os.environ.get("PYATS_USERNAME", ""),
                "PYATS_PASSWORD": os.environ.get("PYATS_PASSWORD", ""),
                "PYATS_AUTH_PASS": os.environ.get("PYATS_AUTH_PASS", "")})
    return _StdioTransport(shlex.split(s.command), env)


async def ensure_ready() -> bool:
    """Connect (or reconnect) when enabled. Never raises; False = no CML tools."""
    global _client, _client_key, _start_lock, _last_error
    s = load_settings()
    if not s.enabled:
        if _client:
            await _client.close()
            _client = None
        return False
    key = (s.transport, s.command, s.http_url, s.cml_url, s.username, s.password, s.verify_ssl, s.tools)
    if _client and _client.alive() and _client_key == key:
        return True
    if _start_lock is None:
        _start_lock = asyncio.Lock()
    async with _start_lock:
        if _client and _client.alive() and _client_key == key:
            return True
        if _client:
            await _client.close()
        c = MCPClient(_make_transport(s))
        try:
            await c.start()
        except Exception as e:
            _last_error = f"{type(e).__name__}: {e}"
            log.warning("cml-mcp unavailable: %s", _last_error)
            await c.close()
            _client = None
            return False
        _client, _client_key, _last_error = c, key, ""
        log.info("cml-mcp connected: %d tools, %d offered to the agent",
                 len(c.tools), len(_offered(c, s)))
        return True


def _offered(c: MCPClient, s: Settings) -> list[dict]:
    return [t for t in c.tools if _allowed(t.get("name", ""), s.tools)]


def _clean_schema(schema: Any) -> Any:
    """Tool input schema as the LLM providers want it (no titles, nothing called ctx)."""
    if isinstance(schema, dict):
        out = {k: _clean_schema(v) for k, v in schema.items() if k != "title"}
        if isinstance(out.get("properties"), dict):
            out["properties"].pop("ctx", None)
            if isinstance(out.get("required"), list):
                out["required"] = [r for r in out["required"] if r != "ctx"]
        return out
    if isinstance(schema, list):
        return [_clean_schema(x) for x in schema]
    return schema


def tool_definitions() -> list[ToolDefinition]:
    """The cml_* tools for this agent run (empty when off or not connected)."""
    if not (_client and _client.alive()):
        return []
    s = load_settings()
    out = []
    for t in _offered(_client, s):
        name = t["name"]
        desc = (t.get("description") or "").strip()
        if len(desc) > MAX_DESC_CHARS:
            desc = desc[:MAX_DESC_CHARS] + " …"
        if name in WRITE_TOOLS:
            desc = "[Changes the lab — the user must approve it first.] " + desc
        elif name == CLI_TOOL:
            desc = ("[show/ping/traceroute run directly; config_command=true or any other command "
                    "needs the user's approval.] " + desc)
        schema = _clean_schema(t.get("inputSchema") or {"type": "object", "properties": {}})
        schema.setdefault("type", "object")
        out.append(ToolDefinition(name=PREFIX + name, description="Cisco Modeling Labs: " + desc,
                                  parameters=schema))
    return out


def handles(tool_name: str) -> bool:
    n = tool_name[len(PREFIX):]
    return tool_name.startswith(PREFIX) and (n in READ_TOOLS or n in WRITE_TOOLS or n == CLI_TOOL)


def _needs_approval(name: str, args: dict) -> bool:
    if name in WRITE_TOOLS:
        return True
    if name == CLI_TOOL:
        if args.get("config_command"):
            return True
        cmds = [c.strip().lower() for c in str(args.get("commands", "")).splitlines() if c.strip()]
        return not cmds or not all(c.startswith(_READ_CLI) or c in ("show", "ping", "traceroute") for c in cmds)
    return False


# pending approvals: proposal id -> (tool, args, decision)
@dataclass
class _Proposal:
    proposal_id: str
    tool: str
    args: dict
    summary: str
    approved: Optional[bool] = None
    applied: bool = False


_PENDING: dict[str, _Proposal] = {}


def _summary(name: str, args: dict) -> str:
    if name == CLI_TOOL:
        mode = "configuration" if args.get("config_command") else "exec"
        return f"Send {mode} commands to node {args.get('label', '?')}"
    what = name.replace("_cml_", " ").replace("_", " ")
    target = args.get("label") or args.get("node_id") or args.get("link_id") or args.get("lab_id") or ""
    return f"{what} {target}".strip()


async def execute(tool_name: str, args: dict) -> tuple[str, bool]:
    """Run a cml_* tool, or stage it for approval. Returns (text, is_error)."""
    name = tool_name[len(PREFIX):]
    s = load_settings()
    if not _allowed(name, s.tools):
        return f"[error] {tool_name} is not available here", True
    if not await ensure_ready():
        return f"[error] Cisco Modeling Labs is not reachable: {_last_error or 'not configured'}", True
    if _needs_approval(name, args):
        pid = "mcpprop_" + uuid.uuid4().hex[:12]
        p = _Proposal(pid, name, dict(args), _summary(name, args))
        _PENDING[pid] = p
        try:
            from tools import audit
            audit.log_event("approval_request", proposal_id=pid, device="CML", summary=p.summary,
                            config_xml_preview=json.dumps(args)[:1500])
        except Exception:
            pass
        return json.dumps({
            APPROVAL_PENDING: True, "proposal_id": pid, "device_name": "Cisco Modeling Labs",
            "summary": p.summary,
            "diff_text": f"tool: {name}\n" + "\n".join(f"{k}: {v}" for k, v in args.items()),
            "config_xml": json.dumps(args, indent=2),
        }), False
    try:
        text, err = await _client.call_tool(name, args)
        # small models put the lab TITLE into get_cml_labs' owner filter ("user"); when that
        # finds nothing, show every lab instead so the model can match the title itself
        if name == "get_cml_labs" and args.get("user") and not err and _empty(text):
            full, err2 = await _client.call_tool(name, {k: v for k, v in args.items() if k != "user"})
            if not err2 and not _empty(full):
                return (f"No labs are OWNED by user '{args['user']}' (the user argument filters by "
                        f"owner, not by lab title). All labs on this CML:\n{full}"), False
        return text, err
    except Exception as e:
        return f"[CML error] {type(e).__name__}: {e}", True


def _empty(text: str) -> bool:
    """True when a tool result holds no items ([], {}, {"result": []}, no output)."""
    t = (text or "").strip()
    if t in ("", "(no output)", "[]", "{}", "null"):
        return True
    try:
        v = json.loads(t)
    except ValueError:
        return False
    if isinstance(v, dict) and len(v) == 1:
        v = next(iter(v.values()))
    return v in ([], {}, None)


def is_proposal(proposal_id: str) -> bool:
    return proposal_id.startswith("mcpprop_")


def get_proposal(proposal_id: str) -> Optional[_Proposal]:
    return _PENDING.get(proposal_id)


async def decide(proposal_id: str, approved: bool) -> tuple[str, bool]:
    """Record the user's decision; on approval run the staged call. Returns (message, is_error)."""
    p = _PENDING.get(proposal_id)
    if not p:
        return f"[error] unknown proposal {proposal_id}", True
    p.approved = approved
    try:
        from tools import audit
        audit.log_event("approval_decision", proposal_id=proposal_id, device="CML", approved=approved)
    except Exception:
        pass
    if not approved:
        return (f"User REJECTED {p.summary} ({proposal_id}). Do NOT retry the same change. "
                "Explain what was rejected and ask how they'd like to proceed."), False
    if p.applied:
        return f"[error] {proposal_id} was already applied", True
    if not await ensure_ready():
        return f"[error] Cisco Modeling Labs is not reachable: {_last_error}", True
    p.applied = True
    try:
        text, err = await _client.call_tool(p.tool, p.args)
    except Exception as e:
        return f"[CML error] {type(e).__name__}: {e}", True
    return f"User approved {proposal_id}. {p.tool} result: {text}", err


async def shutdown() -> None:
    """Stop cml-mcp cleanly (app shutdown)."""
    global _client
    if _client:
        try:
            await _client.close()
        finally:
            _client = None


def status() -> dict:
    s = load_settings()
    return {"public": _public_mode(), "enabled": s.enabled, "connected": bool(_client and _client.alive()),
            "transport": s.transport, "cml_url": s.cml_url,
            "tools": [PREFIX + t["name"] for t in (_offered(_client, s) if _client else [])],
            "error": _last_error}
