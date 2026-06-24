"""
hiTech Automation AI — FastAPI web GUI

vi.netconfsw.1.8.0: Major UX release. Three big themes:

  THEME A — Visibility & control over agent runs
    - Stop button cancels in-flight agent at next iteration boundary
    - SSE streaming endpoint surfaces iter-by-iter progress to the UI
    - Run-id badge visible during a run for log correlation

  THEME B — UI restructure
    - Left navigation replaces top-tab structure (hidable, localStorage-persisted)
    - New "Configuration Management" section with four transport options:
        * NETCONF  : Jinja2-template path OR direct XML payload
        * RESTCONF : https-restconf (Postman-style) OR curl-restconf (paste)
        * CLI      : Jinja2-template path OR raw CLI commands
        * XPath    : direct NETCONF XPath query

  THEME C — Smarter defaults
    - RAG checkbox in agentic mode now auto-prepends top-K corpus chunks
      to the system prompt (was: gated behind a tool call the LLM had
      to choose to make). Mirrors non-agentic chat behavior.
    - RESTCONF 204 No Content responses include a diagnostic hint about
      likely-wrong paths.

Inventory lives outside the build directory at ~/.hitech_automation_ai/devices.yaml
so it survives zip upgrades. Secrets at ~/.hitech_automation_ai/secrets.yaml.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import sys
import uuid
from typing import Optional

import httpx
import yaml
from fastapi import FastAPI, HTTPException, Request

# RAG (optional — works without the vector DB built)
import rag_retriever

# LLM providers (v1.2.0)
from llm_providers import (
    AnthropicProvider,
    ChatMessage as ProviderChatMessage,
    OllamaProvider,
    ProviderError,
)
from llm_providers.ollama_provider import set_runtime_num_ctx  # v1.10.0 (issue-5)

# Agent + tools (v1.3.0; v1.4.0 added NETCONF + approval; v1.5.0 added pyATS inventory)
import agent as agent_mod
from tools import DeviceContext

# ----------------------------- version ----------------------------- #
APP_VERSION = "hitech_automation_ai.1.29.0"
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, StrictUndefined, TemplateSyntaxError
from lxml import etree
from ncclient import manager
from ncclient.operations.rpc import RPCError
from ncclient.transport.errors import AuthenticationError, SSHError
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("hitech_automation_ai")

app = FastAPI(title="hiTech_Automation_AI", version="1.0")
templates = Jinja2Templates(directory="templates")

# v1.15.0: serve vendored assets (CodeMirror for the Python pane). Optional dir —
# the app still boots if ./static is missing; the Python editor falls back to a textarea.
from fastapi.staticfiles import StaticFiles as _StaticFiles
if os.path.isdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")):
    app.mount("/static", _StaticFiles(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")), name="static")

# Jinja2 environment for *user's NETCONF templates* (not the HTML UI template)
netconf_env = Environment(
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)

NC_NS = "urn:ietf:params:xml:ns:netconf:base:1.0"

# ----------------------------- Ollama config ----------------------------- #
# Override via environment variables if your Ollama lives elsewhere or you
# want a different model. Defaults assume Ollama runs on the same host as
# this app (which is the case for your Ubuntu VM setup).
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")

SYSTEM_PROMPT = (
    "You are a Cisco network automation expert helping a network engineer. "
    "Templates in this app are Jinja2 and can render either NETCONF XML "
    "payloads OR plain device CLI commands. "
    "When asked for a NETCONF template: wrap config in "
    "<config xmlns=\"urn:ietf:params:xml:ns:netconf:base:1.0\"> and use the "
    "correct Cisco-IOS-XE / NX-OS YANG namespaces. "
    "When asked for a CLI template: emit Cisco CLI commands line-by-line, "
    "no XML, suitable for `send_config_set`. "
    "When asked for variables: produce YAML at the top level. "
    "Keep answers concise. Put code in fenced code blocks tagged with the "
    "language (jinja2, yaml, xml, cli, python)."
)

# Agentic mode primes the model to use tools rather than hallucinate device state
AGENT_SYSTEM_PROMPT = (
    "You are a Cisco network automation expert with access to TOOLS that let you "
    "query LIVE device state and search the engineer's local documentation.\n"
    "\n"
    "TOOL USAGE PRINCIPLES:\n"
    "  - Prefer using tools over guessing.\n"
    "  - When the user names a device (e.g. 'cat8Kv71'), ALWAYS pass it as the "
    "device_name argument. Never assume a default device.\n"
    "  - Use ONLY tool names from the registered tool list. Never invent tool names.\n"
    "  - If you have data from a previous tool call that already answers the "
    "question, USE IT — do not call more tools just to be thorough.\n"
    "  - Never call search_corpus for live device state. Use run_show_command, "
    "get_running_config, get_state, or restconf_get for device facts.\n"
    "  - For templates and code, use fenced code blocks tagged with the language.\n"
    "\n"
    "TRANSPORT CHOICE — NETCONF vs RESTCONF vs CLI:\n"
    "  - Modern reads on IOS-XE 16.6+, NX-OS 9+, IOS-XR 7+: prefer RESTCONF "
    "(JSON, smaller, faster than NETCONF XML).\n"
    "  - Multi-step transactions or candidate-datastore commits: use NETCONF.\n"
    "  - Anything legacy or operational (show version, ping, traceroute): use "
    "run_show_command (CLI/Netmiko).\n"
    "  - When both OpenConfig and native YANG paths exist, PREFER OpenConfig — "
    "it's vendor-neutral and more portable.\n"
    "\n"
    "NETCONF FILTER CHOICE:\n"
    "  - For surgical queries (one counter, one leaf): use filter_type='xpath' "
    "with xpath_filter, e.g. '/bgp-state-data/neighbors/neighbor/neighbor-id'.\n"
    "  - For tree-shaped queries (all interfaces, all neighbors): use "
    "filter_type='subtree' with subtree_filter_xml.\n"
    "  - For tiny configs only: filter_type='none' (returns everything).\n"
    "\n"
    "RAW OUTPUT HANDLING:\n"
    "  When a tool returns text wrapped between [RAW_CLI_OUTPUT ...] / "
    "[END_RAW_CLI_OUTPUT], or [RAW_XML_OUTPUT ...] / [END_RAW_XML_OUTPUT], "
    "or [RAW_RESTCONF_OUTPUT ...] / [END_RAW_RESTCONF_OUTPUT] markers, that is "
    "raw text from the device. Echo it back to the user inside a fenced code "
    "block VERBATIM when they ask for raw / xml / json / payload output. "
    "Otherwise you may summarise, but the raw text remains available if needed.\n"
    "\n"
    "AVAILABLE TOOLS:\n"
    "  CLI / general:\n"
    "    - run_show_command       — SSH/CLI show/ping/traceroute on a named device\n"
    "    - search_corpus          — Search the engineer's local doc corpus\n"
    "    - describe_device        — Show what device is configured in the chat form\n"
    "    - get_current_template   — See the user's current Jinja2 template + variables\n"
    "    - list_devices           — List devices from the inventory\n"
    "  NETCONF:\n"
    "    - get_running_config     — NETCONF get-config; supports xpath/subtree/none\n"
    "    - get_state              — NETCONF get (operational state); same filters\n"
    "    - validate_config_xml    — Validate a NETCONF payload before propose\n"
    "    - propose_edit_config    — Propose NETCONF change (REQUIRES approval)\n"
    "    - apply_edit_config      — Commit a previously approved NETCONF proposal\n"
    "  RESTCONF (v1.7.0):\n"
    "    - restconf_get                — HTTP GET; JSON; prefer for simple reads\n"
    "    - restconf_list_capabilities  — Discover which YANG modules the device exposes\n"
    "    - propose_restconf_post       — Create resource (REQUIRES approval)\n"
    "    - propose_restconf_put        — Replace resource (REQUIRES approval)\n"
    "    - propose_restconf_patch      — Merge into resource (REQUIRES approval)\n"
    "    - propose_restconf_delete     — Delete resource (REQUIRES approval)\n"
    "    - apply_restconf_change       — Commit an approved RESTCONF proposal\n"
    "\n"
    "Plan briefly, call the tool(s) you need, then summarise the findings clearly. "
    "When you have enough information, stop calling tools and give a final answer. "
    "Don't call more than 3-4 tools per question — keep things focused. "
    "If a tool returns an error, READ THE ERROR before retrying. Don't repeat "
    "the same broken call twice."
)


# ----------------------------- Helpers ----------------------------- #

def parse_vars(text: str, fmt: str) -> dict:
    text = text.strip()
    if not text:
        return {}
    if fmt == "yaml":
        data = yaml.safe_load(text)
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ValueError(f"YAML must be a mapping at the top level, got {type(data).__name__}")
        return data
    return json.loads(text)


def pretty_xml(xml_str: str) -> str:
    try:
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(xml_str.encode("utf-8"), parser)
        return etree.tostring(tree, pretty_print=True, encoding="unicode")
    except Exception:
        return xml_str


def rewrite_nc_operation(xml_str: str, new_op: str) -> str:
    """Set nc:operation='<new_op>' on every element that already has the attribute."""
    tree = etree.fromstring(xml_str.encode("utf-8"))
    attr = f"{{{NC_NS}}}operation"
    touched = 0
    for elem in tree.iter():
        if attr in elem.attrib:
            elem.attrib[attr] = new_op
            touched += 1
    if touched == 0:
        raise ValueError(
            "delete-then-create needs at least one nc:operation attribute in your template "
            "(typically on <extended>). I rewrite that attribute for each step."
        )
    return etree.tostring(tree, pretty_print=True, encoding="unicode")


# ----------------------------- Models ----------------------------- #

class RenderRequest(BaseModel):
    template: str
    variables: str = ""
    format: str = Field("yaml", pattern="^(yaml|json)$")


class DeviceInfo(BaseModel):
    host: str
    port: int = 830
    username: str
    password: str
    device_params: str = "default"
    hostkey_verify: bool = False
    timeout: int = 30


class SendRequest(BaseModel):
    device: DeviceInfo
    operation: str = Field(pattern="^(edit-config|get-config|get)$")
    mode: str = Field("single", pattern="^(single|delete-then-create)$")
    target: str = "running"
    source: str = "running"
    config_xml: str
    default_operation: Optional[str] = None   # null => omit (match user's working script)
    test_option: Optional[str] = None
    error_option: Optional[str] = None
    step1_op: str = "remove"
    step2_op: str = "create"


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: Optional[str] = None     # override default if provided
    context: Optional[str] = None   # optional: current template/variables to attach as context
    use_rag: bool = False           # if true, retrieve from corpus and prepend
    max_tokens: int = Field(default=2048, ge=128, le=16384)  # v1.7.0
    num_ctx: int = Field(default=0, ge=0, le=131072)  # v1.10.0 (issue-5): 0 = Ollama default


class ChatCompareRequest(BaseModel):
    """Send same messages to two models, return both responses side-by-side."""
    messages: list[ChatMessage]
    model_a: str
    model_b: str
    context: Optional[str] = None
    use_rag: bool = False
    num_ctx: int = Field(default=0, ge=0, le=131072)  # v1.10.0 (issue-5)


class AgentDeviceInfo(BaseModel):
    """Device credentials passed from the chat panel for agentic tool calls.

    Sent over HTTPS to the local app only; never logged. Used by run_show_command.
    """
    host: str = ""
    port: int = 22
    username: str = ""
    password: str = ""
    device_type: str = "cisco_xe"
    secret: Optional[str] = None
    timeout: int = 30


class ChatAgentRequest(BaseModel):
    """Agentic chat — LLM can invoke read-only tools to inspect device state."""
    messages: list[ChatMessage]
    model: str
    device_info: Optional[AgentDeviceInfo] = None
    template: Optional[str] = None        # current editor template (for get_current_template)
    variables: Optional[str] = None       # current editor variables
    max_iterations: int = Field(default=8, ge=1, le=15)
    max_tokens: int = Field(default=2048, ge=128, le=16384)  # v1.7.0: per-request override
    use_rag: bool = False                 # v1.8.0: auto-prepend top-K corpus chunks
    num_ctx: int = Field(default=0, ge=0, le=131072)  # v1.10.0 (issue-5)
    run_id: Optional[str] = None          # v1.8.0: caller-provided id for cancel/SSE


class AgentCancelRequest(BaseModel):
    """Posted to /api/agent-cancel to mark a run for cancellation."""
    run_id: str


# Initialize providers at module load (cheap; checks credentials)
_ollama = OllamaProvider(url=OLLAMA_URL)
_anthropic = AnthropicProvider()

# Cache the agent tool count for startup logging
from tools import get_tool_definitions as _get_tools
_tools_count_cache = _get_tools()

log.info("Providers initialized: ollama=%s, anthropic=%s, agent_tools=%d",
         _ollama.is_available(), _anthropic.is_available(), len(_tools_count_cache))

# v1.5.0: log inventory state at startup for visibility
try:
    from tools import inventory as _inventory_boot
    _boot_devs = _inventory_boot.load_devices()
    log.info(
        "Inventory: %d device(s) loaded from %s (formats: %s)",
        len(_boot_devs),
        _inventory_boot.INVENTORY_FILE,
        ", ".join(sorted({d.source_format for d in _boot_devs})) or "(file empty or sample only)",
    )
except Exception as e:
    log.warning("Inventory boot-time load failed: %s", e)


# ----- CLI / Netmiko models ----- #

class CliDeviceInfo(BaseModel):
    host: str
    port: int = 22
    username: str
    password: str
    device_type: str = "cisco_xe"   # netmiko device_type
    timeout: int = 30
    secret: Optional[str] = None    # enable secret if needed


class CliSendRequest(BaseModel):
    device: CliDeviceInfo
    mode: str = Field(pattern="^(config_set|send_command)$")
    payload: str                    # rendered text (config commands OR show command(s))
    save_config: bool = False       # 'write memory' after config_set


# ----------------------------- Endpoints ----------------------------- #

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    response = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_version": APP_VERSION,  # v1.3.3: version available for cache-busting
        },
    )
    # v1.6.1 cache-busting — full-strength.
    # The v1.3.3 headers weren't enough to defeat Chrome's back-forward cache
    # (bfcache), which keeps the entire DOM in memory and bypasses Cache-Control
    # in some navigation scenarios. The combination below forces a fresh fetch:
    #   - no-store + private        → no caching, intermediate or local
    #   - ETag tied to APP_VERSION  → browser sees a new resource per upgrade
    #   - Vary: *                   → response treated as uncacheable
    #   - Last-Modified: now        → invalidates stored entries on next compare
    #   - Clear-Site-Data NOT used  → nuclear, would also wipe localStorage
    import datetime
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0, private, proxy-revalidate"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Vary"] = "*"
    response.headers["ETag"] = f'"{APP_VERSION}"'
    response.headers["Last-Modified"] = datetime.datetime.utcnow().strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    return response


@app.post("/api/render")
def api_render(req: RenderRequest):
    try:
        variables = parse_vars(req.variables, req.format)
        rendered = netconf_env.from_string(req.template).render(**variables)
        return {"rendered_xml": pretty_xml(rendered)}
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Invalid JSON: {e}")
    except yaml.YAMLError as e:
        raise HTTPException(400, f"Invalid YAML: {e}")
    except TemplateSyntaxError as e:
        raise HTTPException(400, f"Jinja2 syntax error: {e}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Render error: {e}")


def _connect_kwargs(device: DeviceInfo) -> dict:
    return {
        "host": device.host,
        "port": device.port,
        "username": device.username,
        "password": device.password,
        "device_params": {"name": device.device_params},
        "hostkey_verify": device.hostkey_verify,
        "look_for_keys": False,
        "allow_agent": False,
        "timeout": device.timeout,
    }


def _edit_config_kwargs(req: SendRequest, config_xml: str) -> dict:
    """Build edit_config kwargs, omitting protocol-default knobs unless explicitly set
    (matches the user's working script which passes only target= and config=)."""
    k = {"target": req.target, "config": config_xml}
    if req.default_operation:
        k["default_operation"] = req.default_operation
    if req.test_option:
        k["test_option"] = req.test_option
    if req.error_option:
        k["error_option"] = req.error_option
    return k


@app.post("/api/send")
def api_send(req: SendRequest):
    """Send NETCONF RPC(s) to the device. Returns step-by-step results."""
    out_log: list[str] = []
    steps: list[dict] = []

    try:
        # Pre-build two-step payloads (so XML errors surface before opening SSH)
        s1_xml = s2_xml = None
        if req.operation == "edit-config" and req.mode == "delete-then-create":
            s1_xml = rewrite_nc_operation(req.config_xml, req.step1_op)
            s2_xml = rewrite_nc_operation(req.config_xml, req.step2_op)

        out_log.append(f"Connecting to {req.device.host}:{req.device.port} as {req.device.username}")
        with manager.connect(**_connect_kwargs(req.device)) as m:
            out_log.append(f"Connected. session-id={m.session_id}")

            if req.operation == "edit-config":
                if req.mode == "delete-then-create":
                    out_log.append(f"Step 1/2: edit-config nc:operation='{req.step1_op}'")
                    r1 = m.edit_config(**_edit_config_kwargs(req, s1_xml))
                    steps.append({
                        "label": f"Step 1: nc:operation={req.step1_op}",
                        "sent_xml": s1_xml,
                        "reply_xml": pretty_xml(r1.xml),
                    })
                    out_log.append("Step 1 OK")

                    out_log.append(f"Step 2/2: edit-config nc:operation='{req.step2_op}'")
                    r2 = m.edit_config(**_edit_config_kwargs(req, s2_xml))
                    steps.append({
                        "label": f"Step 2: nc:operation={req.step2_op}",
                        "sent_xml": s2_xml,
                        "reply_xml": pretty_xml(r2.xml),
                    })
                    out_log.append("Step 2 OK")
                else:
                    out_log.append(f"edit-config to {req.target}")
                    r = m.edit_config(**_edit_config_kwargs(req, req.config_xml))
                    steps.append({
                        "label": "edit-config",
                        "sent_xml": pretty_xml(req.config_xml),
                        "reply_xml": pretty_xml(r.xml),
                    })
                    out_log.append("edit-config OK")

            elif req.operation == "get-config":
                out_log.append(f"get-config from {req.source}")
                r = m.get_config(source=req.source, filter=req.config_xml)
                steps.append({
                    "label": "get-config",
                    "sent_xml": pretty_xml(req.config_xml),
                    "reply_xml": pretty_xml(r.xml),
                })
                out_log.append("get-config OK")

            elif req.operation == "get":
                out_log.append("get")
                r = m.get(filter=req.config_xml)
                steps.append({
                    "label": "get",
                    "sent_xml": pretty_xml(req.config_xml),
                    "reply_xml": pretty_xml(r.xml),
                })
                out_log.append("get OK")

        return {"ok": True, "steps": steps, "log": out_log}

    except AuthenticationError:
        out_log.append("Authentication failed")
        return {"ok": False, "error": "Authentication failed", "steps": steps, "log": out_log}
    except SSHError as e:
        out_log.append(f"SSH error: {e}")
        return {"ok": False, "error": f"SSH: {e}", "steps": steps, "log": out_log}
    except RPCError as e:
        out_log.append(f"RPCError: {e}")
        return {"ok": False, "error": str(e), "steps": steps, "log": out_log}
    except ValueError as e:
        out_log.append(f"ValueError: {e}")
        return {"ok": False, "error": str(e), "steps": steps, "log": out_log}
    except Exception as e:
        log.exception("send failed")
        out_log.append(f"{type(e).__name__}: {e}")
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "steps": steps, "log": out_log}


# ----------------------------- CLI / Netmiko endpoints ----------------------------- #

def _netmiko_kwargs(device: CliDeviceInfo) -> dict:
    k = {
        "device_type": device.device_type,
        "host": device.host,
        "port": device.port,
        "username": device.username,
        "password": device.password,
        "timeout": device.timeout,
        "fast_cli": False,
    }
    if device.secret:
        k["secret"] = device.secret
    return k


@app.post("/api/send-cli")
def api_send_cli(req: CliSendRequest):
    """Send CLI payload via Netmiko. Returns the device output."""
    out_log: list[str] = []
    steps: list[dict] = []

    try:
        out_log.append(f"Connecting to {req.device.host}:{req.device.port} as {req.device.username} ({req.device.device_type})")
        with ConnectHandler(**_netmiko_kwargs(req.device)) as conn:
            if req.device.secret:
                conn.enable()
            prompt = conn.find_prompt()
            out_log.append(f"Connected. prompt={prompt}")

            if req.mode == "config_set":
                # Split payload into list of commands, drop blank lines
                cmds = [ln.rstrip() for ln in req.payload.splitlines() if ln.strip()]
                out_log.append(f"send_config_set with {len(cmds)} commands")
                output = conn.send_config_set(cmds, cmd_verify=False)
                steps.append({
                    "label": "send_config_set",
                    "sent_xml": "\n".join(cmds),     # reuse same UI fields; it's text not xml
                    "reply_xml": output,
                })
                if req.save_config:
                    out_log.append("Saving config: write memory")
                    save_out = conn.save_config()
                    steps.append({
                        "label": "save_config",
                        "sent_xml": "write memory",
                        "reply_xml": save_out,
                    })
                out_log.append("send_config_set OK")

            else:  # send_command — payload is one or more show commands
                cmds = [ln.strip() for ln in req.payload.splitlines() if ln.strip()]
                if not cmds:
                    raise ValueError("send_command requires at least one command in the payload")
                for cmd in cmds:
                    out_log.append(f"send_command: {cmd}")
                    output = conn.send_command(cmd, read_timeout=req.device.timeout)
                    steps.append({
                        "label": f"send_command: {cmd}",
                        "sent_xml": cmd,
                        "reply_xml": output,
                    })
                out_log.append("send_command(s) OK")

        return {"ok": True, "steps": steps, "log": out_log}

    except NetmikoAuthenticationException:
        out_log.append("Authentication failed")
        return {"ok": False, "error": "Authentication failed", "steps": steps, "log": out_log}
    except NetmikoTimeoutException as e:
        out_log.append(f"Timeout: {e}")
        return {"ok": False, "error": f"Timeout: {e}", "steps": steps, "log": out_log}
    except ValueError as e:
        out_log.append(f"ValueError: {e}")
        return {"ok": False, "error": str(e), "steps": steps, "log": out_log}
    except Exception as e:
        log.exception("send-cli failed")
        out_log.append(f"{type(e).__name__}: {e}")
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "steps": steps, "log": out_log}


# ----------------------------- v1.8.1: thin send endpoints ----------------------------- #
# The v1.8 Config Mgmt panes (NETCONF XML payload / Jinja, CLI Raw / Jinja) call these.
# They resolve the device — including its secret — from inventory server-side, so the
# browser never has to hold the password, then delegate to the same battle-tested cores
# as the classic /api/send and /api/send-cli. (Pre-v1.8.1 the front-end POSTed to
# /api/netconf-send and /api/cli-send, which never existed → HTTP 404.)

_NETMIKO_TYPE_MAP = {
    "cisco-iosxe": "cisco_xe",
    "cisco-nxos":  "cisco_nxos",
    "cisco-iosxr": "cisco_xr",
    "cisco-ios":   "cisco_ios",
}


class NetconfSendThin(BaseModel):
    device_name: str
    payload: str
    operation: str = Field("get", pattern="^(edit-config|get-config|get)$")
    target: str = "running"
    source: str = "running"


class CliSendThin(BaseModel):
    device_name: str
    commands: str
    mode: str = Field("send_command", pattern="^(config_set|send_command)$")
    save_config: bool = False


@app.post("/api/netconf-send")
def api_netconf_send(req: NetconfSendThin):
    """Resolve device from inventory, then run the NETCONF op. Returns {ok, response}."""
    d = _inventory.get_device(req.device_name)
    if not d:
        raise HTTPException(400, f"unknown device {req.device_name!r}")
    from tools import netconf_tools as _nctools
    device = DeviceInfo(
        host=d.host,
        port=d.port_netconf,
        username=d.username,
        password=d.password,
        device_params=_nctools._ncclient_device_name(d.device_type),
    )
    sr = SendRequest(
        device=device,
        operation=req.operation,
        mode="single",
        target=req.target,
        source=req.source,
        config_xml=req.payload,
    )
    res = api_send(sr)
    if isinstance(res, dict) and res.get("ok"):
        reply = "\n\n".join(s.get("reply_xml", "") for s in res.get("steps", []) if s.get("reply_xml"))
        from tools.ui_results import set_last_result
        set_last_result("netconf", reply or "", device=req.device_name,
                        query=req.operation, kind="xml")
        return {"ok": True, "response": reply or "(empty reply)", "log": res.get("log", [])}
    err = res.get("error") if isinstance(res, dict) else "send failed"
    log_lines = res.get("log", []) if isinstance(res, dict) else []
    return JSONResponse({"ok": False, "error": err, "log": log_lines}, status_code=200)


class NetconfValidateThin(BaseModel):
    device_name: str
    payload: str   # full <config>…</config> XML


@app.post("/api/netconf-validate")
def api_netconf_validate(req: NetconfValidateThin):
    """v1.17.0 (issue-2): NETCONF <validate> of a config payload BEFORE pushing.

    The device's own YANG engine checks the payload — invented leaves / wrong nesting
    are rejected here without touching the running config. Requires the :validate
    capability (IOS-XE has it); falls back with a clear message if unsupported.
    """
    d = _inventory.get_device(req.device_name)
    if not d:
        raise HTTPException(400, f"unknown device {req.device_name!r}")
    if not (req.payload or "").strip():
        raise HTTPException(400, "payload is empty")
    from tools import netconf_tools as _nctools
    device = DeviceInfo(
        host=d.host,
        port=d.port_netconf,
        username=d.username,
        password=d.password,
        device_params=_nctools._ncclient_device_name(d.device_type),
    )
    log_lines: list[str] = []
    try:
        log_lines.append(f"Connecting to {device.host}:{device.port} as {device.username}")
        with manager.connect(**_connect_kwargs(device)) as m:
            log_lines.append(f"Connected. session-id={m.session_id}")
            caps = " ".join(m.server_capabilities)
            if ":validate" not in caps:
                return {"ok": False, "supported": False, "log": log_lines,
                        "error": "device does not advertise the :validate capability"}
            from lxml import etree as _vet
            try:
                _vet.fromstring(req.payload.encode())
            except Exception as xe:
                return {"ok": False, "supported": True, "log": log_lines,
                        "error": f"payload is not well-formed XML: {xe}"}
            log_lines.append("Sending <validate> with the given <config>")
            r = m.validate(source=req.payload)
            _audit.log_event("netconf_validate_ui", device=req.device_name, ok=True)
            return {"ok": True, "supported": True, "log": log_lines,
                    "response": pretty_xml(r.xml)}
    except Exception as e:
        _audit.log_event("netconf_validate_ui", device=req.device_name, ok=False,
                         error=f"{type(e).__name__}")
        log_lines.append(f"validate failed: {type(e).__name__}: {e}")
        return {"ok": False, "supported": True, "log": log_lines,
                "error": f"{type(e).__name__}: {e}"}


@app.post("/api/cli-send")
def api_cli_send(req: CliSendThin):
    """Resolve device from inventory, then run the CLI op via Netmiko. Returns {ok, output}."""
    d = _inventory.get_device(req.device_name)
    if not d:
        raise HTTPException(400, f"unknown device {req.device_name!r}")
    device = CliDeviceInfo(
        host=d.host,
        port=d.port_ssh,
        username=d.username,
        password=d.password,
        device_type=_NETMIKO_TYPE_MAP.get(d.device_type, "cisco_xe"),
    )
    cr = CliSendRequest(
        device=device,
        mode=req.mode,
        payload=req.commands,
        save_config=req.save_config,
    )
    res = api_send_cli(cr)
    if isinstance(res, dict) and res.get("ok"):
        output = "\n\n".join(s.get("reply_xml", "") for s in res.get("steps", []) if s.get("reply_xml"))
        from tools.ui_results import set_last_result
        set_last_result("cli", output or "", device=req.device_name,
                        query=req.commands, kind="text")
        return {"ok": True, "output": output or "(empty output)", "log": res.get("log", [])}
    err = res.get("error") if isinstance(res, dict) else "send-cli failed"
    log_lines = res.get("log", []) if isinstance(res, dict) else []
    return JSONResponse({"ok": False, "error": err, "log": log_lines}, status_code=200)


# ----------------------------- v1.26.0: interactive CLI sessions ----------------------------- #
# A persistent Netmiko channel kept open server-side so the user can answer device
# confirmation prompts (reload (y/n)?, no username X [confirm], copy run start, etc.).
import time as _time
import threading as _threading

_CLI_SESSIONS: dict = {}          # session_id -> {conn, device_name, last_used, lock}
_CLI_SESSIONS_LOCK = _threading.Lock()
_CLI_IDLE_SECONDS = 300           # reap sessions idle longer than this

# Patterns that mean "the command finished and we're back at the device prompt".
_PROMPT_TAIL_RE = re.compile(r"[\r\n][\w.\-]+(?:\([^)]*\))?[#>]\s*$")
# Pager line — auto-advance.
_PAGER_RE = re.compile(r"--\s*more\s*--", re.IGNORECASE)


def _reap_idle_cli_sessions():
    now = _time.time()
    dead = []
    with _CLI_SESSIONS_LOCK:
        for sid, s in list(_CLI_SESSIONS.items()):
            if now - s["last_used"] > _CLI_IDLE_SECONDS:
                dead.append(sid)
                _CLI_SESSIONS.pop(sid, None)
    for sid in dead:
        try:
            s = None
            # conn already popped; best-effort close happens below if still referenced
        except Exception:
            pass
    return dead


def _read_until_quiet(conn, quiet=0.4, overall=15.0):
    """Read from the channel until it stays silent for `quiet` seconds (or overall timeout)."""
    buf = ""
    start = _time.time()
    last_data = _time.time()
    while True:
        chunk = ""
        try:
            # use check_data_available() when present (avoids blocking reads)
            if hasattr(conn, "check_data_available") and not conn.check_data_available():
                chunk = ""
            else:
                chunk = conn.read_channel()
        except Exception:
            break
        if chunk:
            buf += chunk
            last_data = _time.time()
            # auto-advance pager so long outputs complete on their own
            if _PAGER_RE.search(chunk):
                try:
                    conn.write_channel(" ")
                except Exception:
                    break
        else:
            if _time.time() - last_data >= quiet:
                break
        if _time.time() - start > overall:
            break
        _time.sleep(0.05)
    return buf


def _looks_done(text: str) -> bool:
    """True if the tail looks like a normal device prompt (command finished)."""
    tail = text.rstrip()[-120:] if text else ""
    return bool(_PROMPT_TAIL_RE.search("\n" + tail))


class CliInteractiveOpen(BaseModel):
    device_name: str

class CliInteractiveSend(BaseModel):
    session_id: str
    text: str
    add_newline: bool = True

class CliInteractiveId(BaseModel):
    session_id: str


@app.post("/api/cli-interactive/open")
def api_cli_interactive_open(req: CliInteractiveOpen):
    try:
        return _cli_interactive_open_impl(req)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("cli-interactive/open failed")
        return JSONResponse({"ok": False, "error": f"{type(e).__name__}: {e}"}, status_code=200)


def _cli_interactive_open_impl(req: CliInteractiveOpen):
    _reap_idle_cli_sessions()
    d = _inventory.get_device(req.device_name)
    if not d:
        raise HTTPException(400, f"unknown device {req.device_name!r}")
    if getattr(d, "read_only", True):
        raise HTTPException(403, f"device {req.device_name!r} is read-only; interactive CLI (which can run reload/erase/config) is blocked. Set read_only: false to allow.")
    device = CliDeviceInfo(
        host=d.host, port=d.port_ssh, username=d.username, password=d.password,
        device_type=_NETMIKO_TYPE_MAP.get(d.device_type, "cisco_xe"),
    )
    try:
        conn = ConnectHandler(**_netmiko_kwargs(device))
        if device.secret:
            conn.enable()
        banner = ""
        try:
            conn.write_channel("terminal length 0\n")   # disable pager where supported
            banner = _read_until_quiet(conn, quiet=0.3, overall=4.0)
        except Exception:
            pass
        try:
            prompt = conn.find_prompt()
        except Exception:
            # find_prompt can fail on some platforms; fall back to the read banner tail
            prompt = (banner.strip().splitlines()[-1] if banner.strip() else "") or "(connected)"
    except NetmikoAuthenticationException:
        raise HTTPException(401, "Authentication failed")
    except NetmikoTimeoutException as e:
        raise HTTPException(504, f"Timeout connecting: {e}")
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")

    sid = uuid.uuid4().hex
    with _CLI_SESSIONS_LOCK:
        _CLI_SESSIONS[sid] = {"conn": conn, "device_name": req.device_name,
                              "last_used": _time.time(), "lock": _threading.Lock()}
    return {"ok": True, "session_id": sid, "prompt": prompt, "device": req.device_name}


@app.post("/api/cli-interactive/send")
def api_cli_interactive_send(req: CliInteractiveSend):
    try:
        return _cli_interactive_send_impl(req)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("cli-interactive/send failed")
        return JSONResponse({"ok": False, "error": f"{type(e).__name__}: {e}"}, status_code=200)


def _cli_interactive_send_impl(req: CliInteractiveSend):
    with _CLI_SESSIONS_LOCK:
        s = _CLI_SESSIONS.get(req.session_id)
    if not s:
        raise HTTPException(404, "session not found or expired — open a new interactive session")
    conn = s["conn"]
    with s["lock"]:
        s["last_used"] = _time.time()
        try:
            payload = req.text + ("\n" if req.add_newline else "")
            conn.write_channel(payload)
        except Exception as e:
            # writing failed — channel likely gone (e.g. after reload confirm)
            with _CLI_SESSIONS_LOCK:
                _CLI_SESSIONS.pop(req.session_id, None)
            try: conn.disconnect()
            except Exception: pass
            return {"ok": True, "output": "", "closed": True,
                    "note": f"channel closed ({type(e).__name__}) — device may be reloading/disconnecting"}
        out = _read_until_quiet(conn)
        # detect socket/EOF closure (reload tears the session down)
        closed = False
        try:
            if hasattr(conn, "remote_conn") and conn.remote_conn is not None:
                if getattr(conn.remote_conn, "closed", False):
                    closed = True
        except Exception:
            closed = True
        done = _looks_done(out) and not closed
        if closed:
            with _CLI_SESSIONS_LOCK:
                _CLI_SESSIONS.pop(req.session_id, None)
            try: conn.disconnect()
            except Exception: pass
        return {"ok": True, "output": out, "done": done,
                "awaiting_input": (not done and not closed), "closed": closed}


@app.post("/api/cli-interactive/close")
def api_cli_interactive_close(req: CliInteractiveId):
    with _CLI_SESSIONS_LOCK:
        s = _CLI_SESSIONS.pop(req.session_id, None)
    if s:
        try: s["conn"].disconnect()
        except Exception: pass
    return {"ok": True}


@app.get("/api/cli-interactive/list")
def api_cli_interactive_list():
    _reap_idle_cli_sessions()
    with _CLI_SESSIONS_LOCK:
        return {"ok": True, "sessions": [{"session_id": k, "device": v["device_name"]} for k, v in _CLI_SESSIONS.items()]}


@app.get("/api/ollama-models")
async def list_ollama_models():
    """Legacy endpoint kept for compatibility — returns the same as /api/models filtered to Ollama."""
    models = await _ollama.list_models()
    return {"models": models, "all": models}


@app.get("/api/models")
async def list_all_models():
    """Return models from every available provider, with metadata for the UI."""
    ollama_models = await _ollama.list_models() if _ollama.is_available() else []
    claude_models = await _anthropic.list_models() if _anthropic.is_available() else []
    return {
        "providers": {
            "ollama": {
                "available": _ollama.is_available(),
                "models": ollama_models,
                "label": "Local (Ollama)",
                "is_cloud": False,
            },
            "anthropic": {
                "available": _anthropic.is_available(),
                "models": claude_models,
                "label": "Cloud (Claude)",
                "is_cloud": True,
                "unavailable_reason": (
                    "" if _anthropic.is_available()
                    else "ANTHROPIC_API_KEY not set — see INSTALL.md"
                ),
            },
        },
    }


@app.get("/api/chat-config")
def chat_config():
    """Expose runtime config so the UI can render correctly."""
    return {
        "ollama_url": OLLAMA_URL,
        "default_model": OLLAMA_MODEL,
        "rag_available": rag_retriever.rag_available(),
        "rag_db_path": rag_retriever.rag_db_path(),
        "rag_chunk_count": rag_retriever.rag_chunk_count(),
        "app_version": APP_VERSION,
        "anthropic_available": _anthropic.is_available(),
    }


def _resolve_provider(model: str):
    """Pick a provider based on the model name. Claude models start with 'claude-'."""
    if model.startswith("claude-"):
        if not _anthropic.is_available():
            raise HTTPException(
                401,
                "Claude model requested but ANTHROPIC_API_KEY is not configured. "
                "See INSTALL.md for setup."
            )
        return _anthropic
    return _ollama


async def _do_chat(
    messages: list["ChatMessage"],
    model: str,
    use_rag: bool,
    context: Optional[str],
    max_tokens: int = 2048,        # v1.7.0
) -> dict:
    """Shared chat machinery: build messages list, call provider, return dict.

    Used by both /api/chat (single model) and /api/chat-compare (two models).
    """
    if not messages:
        raise HTTPException(400, "messages cannot be empty")

    # ---- assemble system + RAG + context messages ----
    provider_msgs: list[ProviderChatMessage] = [
        ProviderChatMessage(role="system", content=SYSTEM_PROMPT),
    ]
    rag_meta: dict = {"used": False, "sources": [], "chunks_retrieved": 0}

    # RAG retrieval against the most recent user message
    if use_rag:
        last_user = next((m for m in reversed(messages) if m.role == "user"), None)
        if last_user:
            chunks = await rag_retriever.retrieve(_condition_rag_query(last_user.content), k=8)  # v1.16.3
            chunks = _expand_golden_chunks(chunks)  # v1.17.0
            if chunks:
                rag_meta["used"] = True
                rag_meta["chunks_retrieved"] = len(chunks)
                rag_meta["sources"] = sorted({c["source"] for c in chunks})
                provider_msgs.append(ProviderChatMessage(
                    role="system",
                    content=rag_retriever.format_for_prompt(chunks),
                ))

    # User-provided current template + variables, attached as system context
    if context and context.strip():
        provider_msgs.append(ProviderChatMessage(
            role="system",
            content=f"User's current template and variables for reference:\n\n{context}",
        ))

    # Then the actual conversation history
    for m in messages:
        provider_msgs.append(ProviderChatMessage(role=m.role, content=m.content))

    # Resolve provider + call
    provider = _resolve_provider(model)
    try:
        resp = await provider.chat(provider_msgs, model=model, max_tokens=max_tokens)
    except ProviderError as e:
        raise HTTPException(e.status_code, str(e))

    return {
        "role": "assistant",
        "content": resp.content,
        "model": resp.model,
        "provider": resp.provider,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "cost_usd": resp.cost_usd,
        "eval_duration_ms": resp.eval_duration_ms,
        "rag": rag_meta,
    }


@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    """Send messages to one model. Returns a normalized response across providers."""
    set_runtime_num_ctx(req.num_ctx)  # v1.10.0 (issue-5)
    model = req.model or OLLAMA_MODEL
    return await _do_chat(
        messages=req.messages,
        model=model,
        use_rag=req.use_rag,
        context=req.context,
        max_tokens=req.max_tokens,
    )


@app.post("/api/chat-compare")
async def api_chat_compare(req: ChatCompareRequest):
    """Send the same prompt to two models and return both responses.

    Used by the UI's 'Compare' mode for side-by-side A/B testing.
    """
    if not req.model_a or not req.model_b:
        raise HTTPException(400, "Both model_a and model_b are required")
    set_runtime_num_ctx(req.num_ctx)  # v1.10.0 (issue-5)

    # Run both calls in parallel
    import asyncio
    results = await asyncio.gather(
        _do_chat(req.messages, req.model_a, req.use_rag, req.context),
        _do_chat(req.messages, req.model_b, req.use_rag, req.context),
        return_exceptions=True,
    )

    def _normalize(r):
        if isinstance(r, Exception):
            return {"error": str(r), "content": "", "model": None}
        return r

    return {
        "a": _normalize(results[0]),
        "b": _normalize(results[1]),
    }


@app.post("/api/chat-agent")
async def api_chat_agent(req: ChatAgentRequest):
    """Agentic chat — LLM can call read-only tools to inspect device state.

    Differs from /api/chat in that the LLM is given a tools list and may
    invoke them in a ReAct loop. Returns the final answer + full trace
    of tool calls/results for the UI to render.

    v1.8.0: when req.use_rag=True, the server pre-fetches top-K corpus chunks
    for the latest user message and prepends them to the system prompt. This
    makes the corpus part of every iteration's context rather than gated
    behind a tool call (which small models sometimes decline to make).
    """
    if not req.messages:
        raise HTTPException(400, "messages cannot be empty")
    set_runtime_num_ctx(req.num_ctx)  # v1.10.0 (issue-5)

    provider = _resolve_provider(req.model)

    # Build the device context for tool execution
    di = req.device_info
    ctx = DeviceContext(
        host=(di.host if di else ""),
        port=(di.port if di else 22),
        username=(di.username if di else ""),
        password=(di.password if di else ""),
        device_type=(di.device_type if di else "cisco_xe"),
        secret=(di.secret if di else None),
        timeout=(di.timeout if di else 30),
        template=req.template or "",
        variables=req.variables or "",
    )

    # Map our wire ChatMessage to the provider type
    history = [ProviderChatMessage(role=m.role, content=m.content) for m in req.messages]

    # v1.8.0 — RAG pre-fetch when the checkbox is on.
    # Take the last user message, embed it, fetch top-K chunks from the corpus,
    # prepend them to the system prompt as reference material. The agent's
    # search_corpus tool is still available for follow-up queries.
    system_prompt = AGENT_SYSTEM_PROMPT
    if req.use_rag:
        try:
            from rag_retriever import retrieve as _retrieve_chunks
            last_user = next((m.content for m in reversed(req.messages)
                              if m.role == "user" and m.content.strip()), "")
            if last_user:
                chunks = await _retrieve_chunks(_condition_rag_query(last_user), k=8)  # v1.16.3
                chunks = _expand_golden_chunks(chunks)  # v1.17.0
                if chunks:
                    rag_block = "\n\n".join(
                        f"--- Reference excerpt {i+1} (source: {c.get('source','unknown')}) ---\n{c.get('text','').strip()}"
                        for i, c in enumerate(chunks)
                    )
                    system_prompt = (
                        AGENT_SYSTEM_PROMPT
                        + "\n\n"
                        + "REFERENCE DOCUMENTATION (pre-fetched from local corpus):\n"
                        + "Treat the excerpts below as authoritative for YANG paths, "
                        + "RESTCONF endpoints, NETCONF schemas, and CLI syntax. "
                        + "Live device state still comes from tools.\n\n"
                        + rag_block
                    )
                    log.info("agent: RAG pre-fetch added %d chunks (~%d chars)",
                             len(chunks), len(rag_block))
        except Exception as e:
            log.warning("agent: RAG pre-fetch failed, continuing without: %s", e)

    # v1.8.0 — caller-provided run_id (or generate one). The UI uses it
    # to drive the cancel button and SSE correlation.
    import uuid as _uuid
    run_id = req.run_id or ("run_" + _uuid.uuid4().hex[:12])

    log.info(
        "agent.start model=%s iter_cap=%d device=%s tools_avail=%d use_rag=%s run_id=%s",
        req.model, req.max_iterations,
        ctx.host or "(none)", len(_tools_count_cache),
        req.use_rag, run_id,
    )

    try:
        result = await agent_mod.run_agent(
            provider=provider,
            model=req.model,
            user_messages=history,
            system_prompt=system_prompt,
            device_ctx=ctx,
            max_iterations=req.max_iterations,
            max_tokens=req.max_tokens,
            external_run_id=run_id,
        )
    except ProviderError as e:
        raise HTTPException(e.status_code, str(e))

    return agent_mod.result_to_dict(result)


@app.post("/api/agent-cancel")
async def api_agent_cancel(req: AgentCancelRequest):
    """Mark an agent run for cancellation. Run exits at next iteration boundary."""
    ok = agent_mod.request_cancel(req.run_id)
    return {"ok": ok, "run_id": req.run_id}


@app.get("/api/agent-tools")
async def list_agent_tools():
    """Return the tool definitions for inspection (UI uses this for tooltips)."""
    from tools import get_tool_definitions
    return {
        "tools": [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in get_tool_definitions()
        ]
    }


# ============================================================ #
# v1.4.0 endpoints: device inventory, approval workflow, audit
# ============================================================ #

from pydantic import BaseModel as _BaseModel
from tools import audit as _audit, inventory as _inventory
from tools.netconf_tools import (
    get_proposal as _get_proposal,
    list_pending_proposals as _list_pending,
)


@app.get("/api/devices")
async def api_list_devices():
    """Return the device inventory (passwords stripped)."""
    devs = _inventory.load_devices()
    return {
        "devices": [_inventory.safe_describe(d) for d in devs],
        "inventory_path": str(_inventory.INVENTORY_FILE),
        "count": len(devs),
    }


@app.post("/api/devices/reload")
async def api_reload_devices():
    """Force-reload the inventory from disk without restarting the service.

    Useful after editing devices.yaml or changing the systemd Environment vars
    (which still needs a `systemctl --user restart` to actually re-read the env).
    """
    devs = _inventory.reload_devices()
    log.info("inventory: reloaded on demand, %d device(s) loaded", len(devs))
    return {
        "ok": True,
        "count": len(devs),
        "inventory_path": str(_inventory.INVENTORY_FILE),
    }


# v1.7.0: device CRUD from the Manage Devices GUI panel.
# These routes refuse to overwrite a file in pyATS format unless force=true.
class DeviceUpsert(BaseModel):
    name: str
    host: str
    port_netconf: Optional[int] = 830
    port_ssh: Optional[int] = 22
    port_restconf: Optional[int] = 443
    restconf_root: Optional[str] = "/restconf/data"
    restconf_verify_tls: Optional[bool] = False
    username: Optional[str] = ""
    password: Optional[str] = ""
    device_type: Optional[str] = "cisco-iosxe"
    read_only: Optional[bool] = True
    default: Optional[bool] = False
    force_format_switch: Optional[bool] = False


@app.post("/api/devices")
async def api_upsert_device(payload: DeviceUpsert):
    """Add a new device or update an existing one (matched by name)."""
    try:
        d = _inventory.add_or_update_device(
            payload.model_dump(exclude={"force_format_switch"}),
            force_format_switch=bool(payload.force_format_switch),
        )
        return {"ok": True, "device": _inventory.safe_describe(d)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/devices/{name}")
async def api_delete_device(name: str):
    """Remove a device from the inventory by name."""
    try:
        ok = _inventory.delete_device(name)
        if not ok:
            raise HTTPException(status_code=404, detail=f"device {name!r} not found")
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/devices/connect-info/{name}")
async def api_device_connect_info(name: str, transport: str = "netconf"):
    """Return non-password connection info for a named device.

    Used by the GUI's "Pick device" dropdown to auto-fill host/port/username
    fields. The password is NEVER returned — the form keeps the user's
    typed password (or empty for them to type).

    `transport` is "netconf" (default, port 830) or "cli" (port 22).
    """
    d = _inventory.get_device(name)
    if not d:
        raise HTTPException(404, f"No device named {name!r}")
    port = d.port_netconf if transport == "netconf" else d.port_ssh
    return {
        "name": d.name,
        "host": d.host,
        "port": port,
        "port_netconf": d.port_netconf,
        "port_ssh": d.port_ssh,
        "username": d.username,
        "device_type": d.device_type,
        "read_only": d.read_only,
        "password_configured": bool(d.password),
    }


class AgentApproveRequest(_BaseModel):
    run_id: str
    approved: bool


@app.post("/api/agent/approve")
async def api_agent_approve(req: AgentApproveRequest):
    """Resume a paused agent run after the user approves or rejects a write proposal."""
    if not req.run_id:
        raise HTTPException(400, "run_id is required")

    try:
        result = await agent_mod.continue_agent(req.run_id, req.approved)
    except ProviderError as e:
        raise HTTPException(e.status_code, str(e))

    return agent_mod.result_to_dict(result)


@app.get("/api/agent/proposals")
async def api_list_proposals():
    """Return all currently-pending and recently-decided proposals (in memory)."""
    return {"proposals": _list_pending()}


@app.get("/api/agent/proposal/{proposal_id}")
async def api_get_proposal(proposal_id: str):
    """Return one proposal's diff + xml for the approval modal."""
    p = _get_proposal(proposal_id)
    if not p:
        raise HTTPException(404, f"No proposal with id {proposal_id!r}")
    return {
        "proposal_id": p.proposal_id,
        "device_name": p.device_name,
        "summary": p.summary,
        "diff_text": p.diff_text,
        "config_xml": p.config_xml,
        "approved": p.approved,
    }


@app.get("/api/agent/audit")
async def api_agent_audit(n: int = 50):
    """Return the last n events from the agent audit log."""
    n = max(1, min(n, 500))
    return {
        "events": _audit.read_recent(n),
        "audit_path": _audit.file_path(),
    }


# ============================================================ #
# v1.3.3 endpoints: RAM management, RAG rebuild, system metrics
# ============================================================ #

import asyncio
import subprocess
import time as _time

# Module-level state for async RAG rebuild
_rag_rebuild_state = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "output_tail": [],     # last 50 lines
    "exit_code": None,
    "error": None,
}


@app.get("/api/ollama-loaded")
async def ollama_loaded():
    """Return models currently loaded in Ollama RAM (parses `ollama ps`).

    Returns: {models: [{name, size_gb, processor, context, until}], total_size_gb}
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_URL}/api/ps")
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        return {"models": [], "total_size_gb": 0.0, "error": str(e), "available": False}

    models = []
    total_bytes = 0
    for m in data.get("models", []):
        size = m.get("size", 0)
        total_bytes += size
        # Compute idle/active state
        expires_at = m.get("expires_at", "")
        models.append({
            "name": m.get("name") or m.get("model", ""),
            "size_gb": round(size / (1024**3), 2),
            "size_bytes": size,
            "context": m.get("context_length") or m.get("size_vram", 0),
            "expires_at": expires_at,
            "details": m.get("details", {}),
        })
    return {
        "models": models,
        "count": len(models),
        "total_size_gb": round(total_bytes / (1024**3), 2),
        "available": True,
    }


@app.post("/api/ollama-unload")
async def ollama_unload(body: dict):
    """Unload a specific model from RAM, or unload all chat models.

    Body: {model: "<name>" }                  → unload that model
          {model: "*", keep: ["embed", ...]}  → unload all NOT in keep list
    """
    model = (body.get("model") or "").strip()
    keep_list = body.get("keep", ["nomic-embed-text"])
    if not model:
        return JSONResponse({"ok": False, "error": "model is required"}, status_code=400)

    # Get currently loaded models
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_URL}/api/ps")
            r.raise_for_status()
            loaded = [m.get("name") or m.get("model", "") for m in r.json().get("models", [])]
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"could not list models: {e}"}, status_code=502)

    # Determine targets
    if model == "*":
        targets = [m for m in loaded if not any(k in m for k in keep_list)]
    else:
        targets = [m for m in loaded if m == model]
        if not targets:
            return {"ok": True, "unloaded": [], "note": f"{model} was not loaded"}

    # Unload each: Ollama unloads when keep_alive=0 on a no-op generate
    unloaded = []
    errors = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        for t in targets:
            try:
                r = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": t, "prompt": "", "keep_alive": 0, "stream": False},
                )
                # 200 means it processed (possibly empty) — model unloaded
                unloaded.append(t)
            except Exception as e:
                errors.append({"model": t, "error": str(e)})

    return {"ok": True, "unloaded": unloaded, "errors": errors}


@app.post("/api/ollama-warm")
async def ollama_warm(body: dict):
    """Pre-load a model into RAM by sending an empty generate request.

    Body: {model: "<name>", keep_alive: "10m" (optional)}
    """
    model = (body.get("model") or "").strip()
    keep_alive = body.get("keep_alive", "5m")
    if not model:
        return JSONResponse({"ok": False, "error": "model is required"}, status_code=400)

    t0 = _time.time()
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": keep_alive, "stream": False},
            )
            r.raise_for_status()
    except httpx.ReadTimeout:
        return JSONResponse(
            {"ok": False, "error": f"timeout warming {model}; likely loading from disk still"},
            status_code=504,
        )
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=502)

    return {
        "ok": True,
        "model": model,
        "keep_alive": keep_alive,
        "elapsed_s": round(_time.time() - t0, 1),
    }


@app.post("/api/rag-rebuild")
async def rag_rebuild(body: dict):
    """Kick off rag_builder.py asynchronously. Body: {rebuild: bool} for full wipe."""
    if _rag_rebuild_state["running"]:
        return JSONResponse(
            {"ok": False, "error": "rebuild already running"},
            status_code=409,
        )

    rebuild_flag = bool(body.get("rebuild", False))
    cmd = ["python", "rag_builder.py"]
    if rebuild_flag:
        cmd.append("--rebuild")

    _rag_rebuild_state.update({
        "running": True,
        "started_at": _time.time(),
        "finished_at": None,
        "output_tail": [],
        "exit_code": None,
        "error": None,
    })

    async def runner():
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(Path(__file__).parent),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            assert proc.stdout is not None
            async for raw_line in proc.stdout:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                _rag_rebuild_state["output_tail"].append(line)
                _rag_rebuild_state["output_tail"] = _rag_rebuild_state["output_tail"][-50:]
            _rag_rebuild_state["exit_code"] = await proc.wait()
        except Exception as e:
            _rag_rebuild_state["error"] = str(e)
            _rag_rebuild_state["exit_code"] = -1
        finally:
            _rag_rebuild_state["finished_at"] = _time.time()
            _rag_rebuild_state["running"] = False
            # Force rag_retriever to re-read the collection
            try:
                rag_retriever.reset_cache()
            except Exception:
                pass

    asyncio.create_task(runner())
    return {"ok": True, "started": True, "rebuild_full_wipe": rebuild_flag}


@app.get("/api/rag-rebuild-status")
async def rag_rebuild_status():
    """Poll endpoint for the running rebuild."""
    s = dict(_rag_rebuild_state)
    s["chunk_count"] = rag_retriever.rag_chunk_count()
    s["rag_db_path"] = rag_retriever.rag_db_path()
    return s


@app.get("/api/process-memory")
async def process_memory():
    """Top 10 memory-using processes (best-effort, Linux only)."""
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid,rss,comm", "--sort=-rss"],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.strip().split("\n")[1:11]  # skip header, take top 10
        procs = []
        for line in lines:
            parts = line.strip().split(None, 2)
            if len(parts) >= 3:
                try:
                    procs.append({
                        "pid": int(parts[0]),
                        "rss_mb": round(int(parts[1]) / 1024, 1),
                        "command": parts[2][:50],
                    })
                except ValueError:
                    pass

        # Also get memory totals
        mem_result = subprocess.run(["free", "-b"], capture_output=True, text=True, timeout=5)
        mem_info = {}
        for line in mem_result.stdout.splitlines():
            if line.startswith("Mem:"):
                vals = line.split()
                if len(vals) >= 7:
                    mem_info = {
                        "total_gb": round(int(vals[1]) / (1024**3), 1),
                        "used_gb":  round(int(vals[2]) / (1024**3), 1),
                        "free_gb":  round(int(vals[3]) / (1024**3), 1),
                        "buff_cache_gb": round(int(vals[5]) / (1024**3), 1),
                        "available_gb": round(int(vals[6]) / (1024**3), 1),
                    }
                break

        return {"processes": procs, "memory": mem_info, "ok": True}
    except Exception as e:
        return {"processes": [], "memory": {}, "ok": False, "error": str(e)}


# ============================================================ #
# v1.8.0 — Configuration Management endpoints
# ============================================================ #
# These power the new "Configuration Management" section in the left nav:
#   - /api/restconf-execute   : Postman-style RESTCONF request from the UI
#   - /api/curl-execute       : paste a curl command, run it via subprocess
#   - /api/netconf-xpath      : direct NETCONF XPath query
# All three are direct user actions — no LLM in the loop. They sit alongside
# the existing /api/netconf-send and /api/cli-send endpoints.

class RestconfExecuteRequest(BaseModel):
    """Postman-style RESTCONF request. Either device_name (use inventory creds
    & host) OR explicit host+credentials. Variables get applied to URI / headers /
    payload as Jinja2 templates before sending."""
    method: str = Field(default="GET", pattern="^(GET|POST|PUT|PATCH|DELETE|HEAD)$")
    uri: str                              # full URL, may contain Jinja2 {{vars}}
    headers: dict = Field(default_factory=dict)
    params: dict = Field(default_factory=dict)
    variables: dict = Field(default_factory=dict)
    auth_type: str = Field(default="basic", pattern="^(none|basic|bearer|inventory)$")
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None
    auth_token: Optional[str] = None      # for bearer
    device_name: Optional[str] = None     # for auth_type=inventory
    payload: Optional[str] = None         # JSON body for write methods
    verify_tls: bool = False              # lab default
    restconf_defaults: bool = False       # v1.28.0 issue-1: if True, add Accept/Content-Type yang-data defaults; default OFF (emit only headers the user set)


def _build_export_snippets(method: str, url: str, headers: dict,
                           params: dict, body, verify: bool) -> dict:
    """build-1: generate copy-paste-runnable request snippets from the fully-resolved
    request (real URL, headers incl. Authorization, body, verify flag). Creds are inlined
    (option-b) since they're already resolved in `headers`."""
    import json as _json
    from urllib.parse import urlencode

    method = (method or "GET").upper()
    headers = dict(headers or {})
    params = dict(params or {})
    full_url = url
    if params:
        sep = "&" if ("?" in full_url) else "?"
        full_url = full_url + sep + urlencode(params)

    # ---- curl (runnable as-is: -s always, -k when verify is off -> normally -sk) ----
    flags = "-s" + ("k" if not verify else "")
    curl_lines = [f"curl {flags} -X {method} '{full_url}'"]
    for k, v in headers.items():
        curl_lines.append(f'  -H "{k}: {v}"')
    if body:
        safe = str(body).replace("'", "'\\''")
        curl_lines.append(f"  --data '{safe}'")
    curl = " \\\n".join(curl_lines)

    # ---- python-requests ----
    rq = ["import requests"]
    if not verify:
        rq += ["import urllib3",
               "urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)"]
    rq.append("")
    rq.append(f"url = {_json.dumps(full_url)}")
    rq.append(f"headers = {_json.dumps(headers, indent=4)}")
    data_arg = ""
    if body:
        rq.append(f"data = {_json.dumps(str(body))}")
        data_arg = ", data=data"
    rq.append("")
    rq.append(f"resp = requests.request({_json.dumps(method)}, url, headers=headers{data_arg}, verify={verify})")
    rq.append("print(resp.status_code)")
    rq.append("print(resp.text)")
    requests_code = "\n".join(rq)

    # ---- python http.client (stdlib only) ----
    hc = ["import http.client", "import ssl", "from urllib.parse import urlparse", ""]
    hc.append(f"url = {_json.dumps(full_url)}")
    hc.append("u = urlparse(url)")
    hc.append("port = u.port or (443 if u.scheme == 'https' else 80)")
    if not verify:
        hc.append("ctx = ssl._create_unverified_context()")
        hc.append("conn = http.client.HTTPSConnection(u.hostname, port, context=ctx)")
    else:
        hc.append("conn = http.client.HTTPSConnection(u.hostname, port)")
    hc.append(f"headers = {_json.dumps(headers, indent=4)}")
    if body:
        hc.append(f"body = {_json.dumps(str(body))}")
    hc.append("path = u.path + (('?' + u.query) if u.query else '')")
    body_arg = "body=body, " if body else ""
    hc.append(f"conn.request({_json.dumps(method)}, path, {body_arg}headers=headers)")
    hc.append("resp = conn.getresponse()")
    hc.append("print(resp.status, resp.reason)")
    hc.append("print(resp.read().decode())")
    httpclient_code = "\n".join(hc)

    return {"curl": curl, "requests": requests_code, "httpclient": httpclient_code}


@app.post("/api/restconf-execute")
async def api_restconf_execute(req: RestconfExecuteRequest):
    """Execute a Postman-style RESTCONF request. Returns response + headers + timing."""
    import time
    import httpx
    from jinja2 import Template, TemplateError

    # Render Jinja2 in URI, headers, payload if variables provided
    def _render(s: str) -> str:
        if not s or "{{" not in s:
            return s or ""
        try:
            return Template(s).render(**(req.variables or {}))
        except TemplateError as e:
            raise HTTPException(400, f"Jinja2 render error: {e}")

    final_uri = _render(req.uri)
    final_payload = _render(req.payload) if req.payload else None
    final_headers = {k: _render(v) for k, v in (req.headers or {}).items()}

    # Resolve auth
    headers_out = dict(final_headers)
    if req.auth_type == "basic":
        u = _render(req.auth_username)   # v1.12.3: resolve {{vars}}/env vars in auth fields too
        p = _render(req.auth_password)
        if u or p:
            token = base64.b64encode(f"{u}:{p}".encode()).decode()
            headers_out["Authorization"] = f"Basic {token}"
    elif req.auth_type == "bearer":
        tok = _render(req.auth_token)    # v1.12.3
        if tok:
            headers_out["Authorization"] = f"Bearer {tok}"
    elif req.auth_type == "inventory":
        if not req.device_name:
            raise HTTPException(400, "auth_type=inventory requires device_name")
        d_match = next((d for d in _inventory.load_devices() if d.name == req.device_name), None)
        if not d_match:
            raise HTTPException(400, f"unknown device {req.device_name!r}")
        token = base64.b64encode(f"{d_match.username}:{d_match.password}".encode()).decode()
        headers_out["Authorization"] = f"Basic {token}"
        # If URI is just a path, prepend the device base URL
        if final_uri.startswith("/") or not final_uri.startswith("http"):
            base = f"https://{d_match.host}:{d_match.port_restconf}"
            final_uri = base + (final_uri if final_uri.startswith("/") else "/" + final_uri)

    # v1.28.0 issue-1: do NOT auto-inject RESTCONF defaults unless explicitly requested.
    # Emit only the headers the user actually set (matters for APIC/ACI which isn't YANG).
    if req.restconf_defaults:
        headers_out.setdefault("Accept", "application/yang-data+json")
        if final_payload:
            headers_out.setdefault("Content-Type", "application/yang-data+json")

    _audit.log_event("restconf_execute_ui",
                    method=req.method, uri=final_uri,
                    device=req.device_name or "(explicit)")

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(verify=req.verify_tls, timeout=30.0) as client:
            r = await client.request(
                req.method, final_uri,
                headers=headers_out,
                params=req.params or None,
                content=final_payload,
            )
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            from tools.ui_results import set_last_result
            set_last_result("restconf", r.text or "", device=getattr(req, "device_name", None),
                            query=final_uri,
                            kind=("xml" if (r.text or "").lstrip().startswith("<") else "text"))
            export = _build_export_snippets(req.method, final_uri, headers_out,
                                            dict(req.params or {}), final_payload, req.verify_tls)
            return {
                "ok": True,
                "status_code": r.status_code,
                "headers": dict(r.headers),
                "body": r.text,
                "elapsed_ms": elapsed_ms,
                "request_url": final_uri,
                "export": export,
            }
    except httpx.RequestError as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "elapsed_ms": elapsed_ms,
            "request_url": final_uri,
        }


class CurlExecuteRequest(BaseModel):
    """Paste a curl command and execute it as a subprocess. Output captured."""
    curl_command: str
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    env_vars: dict = Field(default_factory=dict)   # v1.28.0 issue-2: Environment vars → process env ($VAR)


class PythonExecuteRequest(BaseModel):
    """build-2: paste a Python script and run it on the host via `python3 -`.

    v1.16.0 (issue-1c): optional env_text — .env-style KEY=VALUE lines that override the
    service environment for this run only (box -> service env -> fail). Values are never
    written to logs; the audit entry records keys only."""
    code: str
    env_text: str = ""
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    env_vars: dict = Field(default_factory=dict)   # v1.28.0 issue-2: Environment vars → os.environ


@app.post("/api/curl-execute")
async def api_curl_execute(req: CurlExecuteRequest):
    """Run the pasted text through the host shell (bash -lc). Captures stdout, stderr,
    exit code, timing.

    v1.8.1: this pane mirrors a terminal on the host VM. The text is handed verbatim to
    `bash -lc`, so pipes (| jq), command substitution $( ), variables ($VAR / export),
    and && chains all work exactly as they would in the user's shell. Because each Run is
    a fresh `bash -lc`, variables only persist *within a single paste* — to chain an ACI
    login → token → call, paste the whole script in one go.

    NOTE: this executes arbitrary shell on the host as the service user. It is intended
    for a single-user localhost deployment; do not expose port 7071 to untrusted networks.
    """
    import asyncio
    import time
    import os as _os
    import re as _re
    import tempfile as _tf

    cmd_text = req.curl_command.strip()
    if not cmd_text:
        raise HTTPException(400, "command is empty")

    # v1.18.0 (issue-1): capture response headers per curl invocation. We append
    # `-D <tmpfile>` to each `curl ...` so headers are dumped to a file without
    # disturbing the user's own flags/output. One temp file per curl, in order.
    _hdr_files: list[str] = []
    def _inject_dump(m):
        f = _tf.NamedTemporaryFile(prefix="curlhdr_", suffix=".txt", delete=False)
        f.close()
        _hdr_files.append(f.name)
        return m.group(0) + f" -D {f.name} "
    # match a curl command token at start of line or after a shell separator
    instrumented = _re.sub(r'(?m)(?:^|(?<=[;&|]))\s*curl\b', _inject_dump, cmd_text)

    # First non-empty, non-comment token — for the audit log only (no longer a guard).
    first_tok = ""
    for line in cmd_text.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            first_tok = s.split()[0] if s.split() else ""
            break

    _audit.log_event("curl_execute_ui", shell="bash -lc", first_token=first_tok,
                     length=len(cmd_text))

    # v1.28.0 issue-2: inject the active Environment's vars into the process env so the
    # pasted command can reference $APIC_HOST etc. The shell text itself can still export/
    # override its own vars (those win, since they run inside the shell).
    _merged_env = dict(_os.environ)
    for _k, _v in (req.env_vars or {}).items():
        if _k:
            _merged_env[str(_k)] = str(_v)

    t0 = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash", "-lc", instrumented,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_merged_env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=req.timeout_seconds
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return {
                "ok": False,
                "error": f"timeout after {req.timeout_seconds}s",
                "elapsed_ms": elapsed_ms,
            }

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        # v1.18.0 (issue-1): collect captured headers, in invocation order
        header_blocks = []
        for i, hf in enumerate(_hdr_files):
            try:
                with open(hf, "r", encoding="utf-8", errors="replace") as fh:
                    raw = fh.read().strip()
            except Exception:
                raw = ""
            if raw:
                # a -D dump may contain multiple status lines on redirects; keep last block
                blocks = [b for b in raw.split("\n\n") if b.strip()]
                header_blocks.append({"index": i + 1, "raw": (blocks[-1] if blocks else raw).strip()})
        for hf in _hdr_files:
            try: _os.unlink(hf)
            except OSError: pass
        return {
            "ok": True,
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "elapsed_ms": elapsed_ms,
            "header_blocks": header_blocks,   # [{index, raw}], one per curl
        }
    except FileNotFoundError:
        raise HTTPException(500, "bash not found on server")
    except Exception as e:
        for hf in _hdr_files:
            try: _os.unlink(hf)
            except OSError: pass
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "elapsed_ms": elapsed_ms,
        }


# ============================================================
# v1.18.0 (issue-2b) — server-side jq filtering
# ============================================================
class JqRequest(BaseModel):
    json_text: str
    filter: str
    raw_output: bool = False   # jq -r


@app.post("/api/jq")
async def api_jq(req: JqRequest):
    """Run the system `jq` binary on supplied JSON. Used by the https-restconf response
    filter when the user picks the 'Server (system jq)' engine.

    Safety: the filter is passed as a single argv (no shell) so it cannot inject commands;
    JSON is fed on stdin; size-capped and time-limited.
    """
    import asyncio
    import shutil as _sh

    if not req.filter.strip():
        raise HTTPException(400, "empty filter")
    if len(req.json_text) > 8_000_000:
        raise HTTPException(413, "JSON too large for server-side jq (>8 MB)")
    if _sh.which("jq") is None:
        return {"ok": False, "error": "`jq` is not installed on the server — use the Browser (wasm) engine instead."}

    argv = ["jq"]
    if req.raw_output:
        argv.append("-r")
    argv.append(req.filter)   # single arg → no shell injection

    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(
            proc.communicate(input=req.json_text.encode()), timeout=15)
    except asyncio.TimeoutError:
        return {"ok": False, "error": "jq timed out (15s)"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    if proc.returncode != 0:
        return {"ok": False, "error": err.decode("utf-8", "replace").strip() or "jq error"}
    return {"ok": True, "output": out.decode("utf-8", "replace")}


@app.post("/api/python-execute")
async def api_python_execute(req: PythonExecuteRequest):
    """build-2: run a pasted Python script on the host via `python3 -` (program on stdin).

    Mirrors /api/curl-execute: captures stdout, stderr, exit code, timing. Same execution
    model — arbitrary code as the service user, intended for single-user localhost only;
    do not expose port 7071. `requests` must be pip-installed on the VM for the requests
    snippet; the stdlib http.client path needs nothing.
    """
    import asyncio
    import time

    code = req.code
    if not code.strip():
        raise HTTPException(400, "code is empty")

    user_env = _py_parse_env_text(req.env_text)
    # v1.28.0 issue-2: layering — service env < Environment vars < pane env-box (most local wins)
    _env_layer = {str(k): str(v) for k, v in (req.env_vars or {}).items() if k}
    _audit.log_event("python_execute_ui", length=len(code),
                     env_keys=sorted(set(list(user_env.keys()) + list(_env_layer.keys()))))  # keys only

    t0 = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-",
            env={**os.environ, **_env_layer, **user_env},  # pane box > Environment > service
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=code.encode("utf-8")), timeout=req.timeout_seconds
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return {"ok": False, "error": f"timeout after {req.timeout_seconds}s",
                    "elapsed_ms": elapsed_ms}

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {
            "ok": True,
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "elapsed_ms": elapsed_ms,
        }
    except FileNotFoundError:
        raise HTTPException(500, "python3 not found on server")
    except Exception as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "elapsed_ms": elapsed_ms,
        }


# ============================================================
# v1.15.0 — Python pane: multi-file runner + env vars + lint
# ============================================================
import re as _py_re
import shutil as _py_shutil
import tempfile as _py_tempfile

_PYFILE_NAME_RE = _py_re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


class PyFile(BaseModel):
    name: str
    content: str = ""


class PythonRunRequest(BaseModel):
    """v1.15.0: run a multi-file Python project in a throwaway temp dir.

    All files are written into one fresh directory and the entry file is executed with
    cwd=that dir, so `import otherfile` between pasted files works exactly like files
    sitting in the same folder on the VM. env_text is .env-style KEY=VALUE lines; those
    override the service environment for this run only (box -> service env -> fail).
    """
    files: list[PyFile]
    entry: str
    env_text: str = ""
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class PythonLintRequest(BaseModel):
    files: list[PyFile]


def _py_parse_env_text(env_text: str) -> dict:
    """Parse .env-style lines. Ignores blanks/#comments; strips optional quotes."""
    out: dict[str, str] = {}
    for raw in (env_text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key:
            out[key] = val
    return out


def _py_validate_files(files: list[PyFile], entry: str | None = None) -> None:
    if not files:
        raise HTTPException(400, "no files")
    names = set()
    for f in files:
        if not _PYFILE_NAME_RE.match(f.name) or ".." in f.name:
            raise HTTPException(400, f"bad filename: {f.name!r} (letters/digits/._- only, no paths)")
        if f.name in names:
            raise HTTPException(400, f"duplicate filename: {f.name}")
        names.add(f.name)
    if entry is not None:
        if entry not in names:
            raise HTTPException(400, f"entry file {entry!r} is not among the files")
        if not entry.endswith(".py"):
            raise HTTPException(400, "entry file must be a .py file")


@app.post("/api/python-run")
async def api_python_run(req: PythonRunRequest):
    """v1.15.0: multi-file run. Same trust model as /api/python-execute (arbitrary code
    as the service user; single-user localhost only — do not expose port 7071).

    Audit: file names, entry and env KEYS are logged; env VALUES are never logged
    (Issue-1: tokens/secrets must not land in logs in any readable form).
    """
    import asyncio
    import time

    _py_validate_files(req.files, req.entry)
    user_env = _py_parse_env_text(req.env_text)

    _audit.log_event(
        "python_run_ui",
        entry=req.entry,
        files=[f.name for f in req.files],
        env_keys=sorted(user_env.keys()),  # keys only — values intentionally omitted
        total_bytes=sum(len(f.content) for f in req.files),
    )

    tmpdir = _py_tempfile.mkdtemp(prefix="pyrun_")
    t0 = time.monotonic()
    try:
        for f in req.files:
            with open(os.path.join(tmpdir, f.name), "w", encoding="utf-8") as fh:
                fh.write(f.content)

        run_env = {**os.environ, **user_env}  # box overrides service; service is fallback

        proc = await asyncio.create_subprocess_exec(
            sys.executable, req.entry,
            cwd=tmpdir,
            env=run_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=req.timeout_seconds
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {"ok": False, "error": f"timeout after {req.timeout_seconds}s",
                    "elapsed_ms": int((time.monotonic() - t0) * 1000)}

        return {
            "ok": True,
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "elapsed_ms": int((time.monotonic() - t0) * 1000),
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "elapsed_ms": int((time.monotonic() - t0) * 1000)}
    finally:
        _py_shutil.rmtree(tmpdir, ignore_errors=True)


@app.post("/api/python-lint")
async def api_python_lint(req: PythonLintRequest):
    """v1.15.0: static checks on the pasted files, before running.

    Prefers ruff (pip install ruff into the venv), falls back to pyflakes, else reports
    that no linter is installed. Returns [{file, line, col, code, message}].
    """
    import asyncio
    import json as _json

    _py_validate_files(req.files)
    py_files = [f for f in req.files if f.name.endswith(".py")]
    if not py_files:
        return {"ok": True, "linter": None, "issues": []}

    tmpdir = _py_tempfile.mkdtemp(prefix="pylint_")
    try:
        for f in py_files:
            with open(os.path.join(tmpdir, f.name), "w", encoding="utf-8") as fh:
                fh.write(f.content)

        async def _run(*argv):
            proc = await asyncio.create_subprocess_exec(
                *argv, cwd=tmpdir,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, err = await asyncio.wait_for(proc.communicate(), timeout=30)
            return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

        # --- ruff (preferred) ---
        try:
            rc, out, err = await _run(sys.executable, "-m", "ruff", "check",
                                      "--output-format=json", "--exit-zero", ".")
            issues = []
            for item in _json.loads(out or "[]"):
                issues.append({
                    "file": os.path.basename(item.get("filename", "")),
                    "line": (item.get("location") or {}).get("row", 1),
                    "col": (item.get("location") or {}).get("column", 1),
                    "code": item.get("code") or "",
                    "message": item.get("message") or "",
                })
            return {"ok": True, "linter": "ruff", "issues": issues}
        except (FileNotFoundError, _json.JSONDecodeError, ModuleNotFoundError):
            pass
        except Exception:
            pass  # fall through to pyflakes

        # --- pyflakes fallback ---
        try:
            rc, out, err = await _run(sys.executable, "-m", "pyflakes",
                                      *[f.name for f in py_files])
            issues = []
            pat = _py_re.compile(r"^(?P<file>[^:]+):(?P<line>\d+):(?:(?P<col>\d+):)?\s*(?P<msg>.*)$")
            for line in (out + "\n" + err).splitlines():
                m = pat.match(line.strip())
                if m:
                    issues.append({
                        "file": os.path.basename(m.group("file")),
                        "line": int(m.group("line")),
                        "col": int(m.group("col") or 1),
                        "code": "pyflakes",
                        "message": m.group("msg"),
                    })
            return {"ok": True, "linter": "pyflakes", "issues": issues}
        except Exception:
            pass

        return {"ok": False, "linter": None, "issues": [],
                "error": "no linter found — install one into the venv: pip install ruff"}
    finally:
        _py_shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================
# v1.16.0 (issue-5) — RAG corpus browser (read-only)
# ============================================================
from pathlib import Path as _RagPath

_RAG_CORPUS_DIR = _RagPath(os.environ.get(
    "RAG_CORPUS_DIR", "~/DevnetExpert/mock3/software_ai/rag-corpus")).expanduser()


@app.get("/api/rag-files")
async def api_rag_files():
    """List files in the RAG corpus directory (recursive). Read-only browser, phase 1."""
    if not _RAG_CORPUS_DIR.is_dir():
        return {"ok": False, "dir": str(_RAG_CORPUS_DIR), "files": [],
                "error": "corpus directory not found"}
    files = []
    for p in sorted(_RAG_CORPUS_DIR.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        st = p.stat()
        files.append({
            "name": str(p.relative_to(_RAG_CORPUS_DIR)),
            "size": st.st_size,
            "mtime": int(st.st_mtime),
        })
    chunk_count = None
    try:
        chunk_count = rag_retriever.rag_chunk_count()
    except Exception:
        pass
    return {"ok": True, "dir": str(_RAG_CORPUS_DIR), "files": files,
            "chunk_count": chunk_count}


@app.get("/api/rag-file")
async def api_rag_file(name: str):
    """Return one corpus file's text. Path-validated: must resolve inside the corpus dir."""
    if not name or name.startswith("/") or ".." in name.split("/"):
        raise HTTPException(400, "bad name")
    target = (_RAG_CORPUS_DIR / name).resolve()
    try:
        target.relative_to(_RAG_CORPUS_DIR.resolve())
    except ValueError:
        raise HTTPException(400, "path escapes corpus directory")
    if not target.is_file():
        raise HTTPException(404, "file not found")
    if target.stat().st_size > 2_000_000:
        raise HTTPException(413, "file too large for the viewer (>2 MB)")
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(500, f"read failed: {type(e).__name__}: {e}")
    return {"ok": True, "name": name, "content": text}




# ============================================================
# v1.16.3 — RAG query conditioning + v1.17.0 golden whole-file injection
# ============================================================
import re as _ragre

def _condition_rag_query(text: str, cap: int = 400) -> str:
    """v1.16.3 (issue-4): build a clean embedding query from a chat message.

    User messages often carry large YAML/code blocks (source-of-truth data). Embedding
    all of it dilutes the semantic signal and retrieval drifts to generic course files.
    Strategy: drop fenced ``` blocks, drop data-looking lines (indented, list items,
    bare key: value), keep the instruction prose, cap the length.
    """
    if not text:
        return text
    t = _ragre.sub(r"```.*?```", " ", text, flags=_ragre.S)      # fenced blocks
    kept = []
    for line in t.splitlines():
        if not line.strip():
            continue
        if line[:1] in (" ", "\t"):          # indented => data block
            continue
        s = line.strip()
        if s.startswith("- "):                # YAML list item
            continue
        if _ragre.match(r"^[A-Za-z0-9_.-]+:\s*\S*$", s):   # bare key: value
            continue
        kept.append(s)
    out = " ".join(kept).strip() or text.strip()
    return out[:cap]


def _expand_golden_chunks(chunks: list) -> list:
    """v1.17.0 (issue-1): if a retrieved chunk comes from rag-corpus/golden/, replace all
    of that file's chunks with ONE entry holding the ENTIRE file. Golden docs are small,
    curated, verified ground truth — partial chunks invite the model to fill gaps from
    memory, which is exactly the failure mode they exist to prevent.
    """
    golden_dir = _RAG_CORPUS_DIR / "golden"
    seen_golden: dict[str, str] = {}
    out: list = []
    for c in chunks:
        src_name = (c.get("source") or "").strip()
        fp = golden_dir / src_name
        try:
            is_golden = bool(src_name) and fp.is_file() and fp.stat().st_size <= 131072
        except OSError:
            is_golden = False
        if not is_golden:
            out.append(c)
            continue
        if src_name in seen_golden:
            continue  # whole file already injected once
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            out.append(c)
            continue
        seen_golden[src_name] = content
        nc = dict(c)
        nc["source"] = f"golden/{src_name} (FULL FILE — verified ground truth)"
        nc["text"] = content
        out.append(nc)
    return out


# ============================================================
# v1.12.0 — RESTCONF collections + environments (Postman-format JSON on disk)
# ============================================================
from tools import restconf_store as _rc_store
from tools import restconf_tree as _rc_tree   # v1.19.0: nested collection tree


# ===================== v1.19.0: RESTCONF collection tree =====================
def _scope_of(req) -> str:
    s = getattr(req, "scope", None) or "restconf"
    if s not in _rc_tree.SCOPES:
        raise HTTPException(400, f"unknown scope {s!r}")
    return s


class RcTreeAddFolder(BaseModel):
    parent_id: str
    name: str = "New folder"
    scope: str = "restconf"

class RcTreeAddRequest(BaseModel):
    parent_id: str
    name: str
    request: dict
    scope: str = "restconf"

class RcTreeUpdateRequest(BaseModel):
    node_id: str
    request: dict
    name: Optional[str] = None
    scope: str = "restconf"

class RcTreeRename(BaseModel):
    node_id: str
    name: str
    scope: str = "restconf"

class RcTreeId(BaseModel):
    node_id: str
    scope: str = "restconf"

class RcTreeMove(BaseModel):
    node_id: str
    new_parent_id: str
    index: Optional[int] = None
    scope: str = "restconf"


@app.get("/api/rc-tree")
def api_rc_tree(scope: str = "restconf"):
    if scope not in _rc_tree.SCOPES:
        raise HTTPException(400, f"unknown scope {scope!r}")
    return {"ok": True, "tree": _rc_tree.load_tree(scope), "scope": scope}


@app.post("/api/rc-tree/add-folder")
def api_rc_tree_add_folder(req: RcTreeAddFolder):
    scope = _scope_of(req); tree = _rc_tree.load_tree(scope)
    try:
        node = _rc_tree.add_folder(tree, req.parent_id, req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _rc_tree.save_tree(tree, scope)
    return {"ok": True, "node": node, "tree": tree}


@app.post("/api/rc-tree/add-request")
def api_rc_tree_add_request(req: RcTreeAddRequest):
    scope = _scope_of(req); tree = _rc_tree.load_tree(scope)
    try:
        node = _rc_tree.add_request(tree, req.parent_id, req.name, req.request)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _rc_tree.save_tree(tree, scope)
    return {"ok": True, "node": node, "tree": tree}


@app.post("/api/rc-tree/update-request")
def api_rc_tree_update_request(req: RcTreeUpdateRequest):
    scope = _scope_of(req); tree = _rc_tree.load_tree(scope)
    try:
        _rc_tree.update_request(tree, req.node_id, req.request, req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _rc_tree.save_tree(tree, scope)
    return {"ok": True, "tree": tree}


@app.post("/api/rc-tree/rename")
def api_rc_tree_rename(req: RcTreeRename):
    scope = _scope_of(req); tree = _rc_tree.load_tree(scope)
    try:
        _rc_tree.rename_node(tree, req.node_id, req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _rc_tree.save_tree(tree, scope)
    return {"ok": True, "tree": tree}


@app.post("/api/rc-tree/delete")
def api_rc_tree_delete(req: RcTreeId):
    scope = _scope_of(req); tree = _rc_tree.load_tree(scope)
    try:
        _rc_tree.delete_node(tree, req.node_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _rc_tree.save_tree(tree, scope)
    return {"ok": True, "tree": tree}


class RcTreeImport(BaseModel):
    collection: dict
    scope: str = "restconf"


@app.post("/api/rc-tree/import-collection")
def api_rc_tree_import(req: RcTreeImport):
    scope = _scope_of(req); tree = _rc_tree.load_tree(scope)
    try:
        _rc_tree.import_postman_collection(tree, req.collection)
    except Exception as e:
        raise HTTPException(400, f"import failed: {e}")
    _rc_tree.save_tree(tree, scope)
    return {"ok": True, "tree": tree}


@app.post("/api/rc-tree/move")
def api_rc_tree_move(req: RcTreeMove):
    scope = _scope_of(req); tree = _rc_tree.load_tree(scope)
    try:
        _rc_tree.move_node(tree, req.node_id, req.new_parent_id, req.index)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _rc_tree.save_tree(tree, scope)
    return {"ok": True, "tree": tree}


class RcNameReq(BaseModel):
    name: str


class RcRenameReq(BaseModel):
    old: str
    new: str


class RcRequestSaveReq(BaseModel):
    project: str
    request: dict


class RcRequestDeleteReq(BaseModel):
    project: str
    name: str


class RcImportReq(BaseModel):
    collection: dict
    name: Optional[str] = None


class RcEnvSaveReq(BaseModel):
    name: str
    vars: dict = Field(default_factory=dict)


class RcEnvImportReq(BaseModel):
    environment: dict
    name: Optional[str] = None


@app.get("/api/rc-projects")
def api_rc_projects():
    return {"ok": True, "projects": _rc_store.list_projects()}


@app.post("/api/rc-project-create")
def api_rc_project_create(req: RcNameReq):
    try:
        _rc_store.create_project(req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/rc-project-delete")
def api_rc_project_delete(req: RcNameReq):
    _rc_store.delete_project(req.name)
    return {"ok": True}


@app.post("/api/rc-project-rename")
def api_rc_project_rename(req: RcRenameReq):
    try:
        _rc_store.rename_project(req.old, req.new)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.get("/api/rc-project-requests")
def api_rc_project_requests(name: str):
    return {"ok": True, "requests": _rc_store.get_project_requests(name)}


@app.post("/api/rc-request-save")
def api_rc_request_save(req: RcRequestSaveReq):
    if not (req.request or {}).get("name"):
        raise HTTPException(400, "request.name is required")
    _rc_store.save_request(req.project, req.request)
    return {"ok": True}


@app.post("/api/rc-request-delete")
def api_rc_request_delete(req: RcRequestDeleteReq):
    _rc_store.delete_request(req.project, req.name)
    return {"ok": True}


@app.get("/api/rc-project-export")
def api_rc_project_export(name: str):
    try:
        return _rc_store.export_project(name)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/api/rc-import")
def api_rc_import(req: RcImportReq):
    try:
        nm = _rc_store.import_collection(req.collection, req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "name": nm}


@app.get("/api/rc-envs")
def api_rc_envs():
    return {"ok": True, "envs": _rc_store.list_environments()}


@app.get("/api/rc-env")
def api_rc_env(name: str):
    return {"ok": True, **_rc_store.get_environment(name)}


@app.post("/api/rc-env-save")
def api_rc_env_save(req: RcEnvSaveReq):
    try:
        _rc_store.save_environment(req.name, req.vars)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/rc-env-delete")
def api_rc_env_delete(req: RcNameReq):
    _rc_store.delete_environment(req.name)
    return {"ok": True}


@app.get("/api/rc-env-export")
def api_rc_env_export(name: str):
    try:
        return _rc_store.export_environment(name)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/api/rc-env-import")
def api_rc_env_import(req: RcEnvImportReq):
    try:
        nm = _rc_store.import_environment(req.environment, req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "name": nm}


class XPathTestRequest(BaseModel):
    """v1.13.0: run a real XPath 1.0 expression against given XML (the XPath Result pane)."""
    xml: str
    expr: str
    ignore_ns: bool = True


@app.post("/api/xpath-test")
def api_xpath_test(req: XPathTestRequest):
    """v1.13.0: evaluate a real XPath 1.0 expression (predicates, //, @attr, functions,
    and/or, positions) against the supplied XML using lxml. With ignore_ns (default) the
    tree's namespaces are stripped so unprefixed expressions just work on RESTCONF/NETCONF
    XML; otherwise the document's declared namespaces are available (default ns as 'ns')."""
    from lxml import etree

    xml = (req.xml or "").strip()
    expr = (req.expr or "").strip()
    if not xml:
        raise HTTPException(400, "no XML to filter — run an XPath query first")
    if not expr:
        raise HTTPException(400, "empty XPath expression")

    try:
        root = etree.fromstring(xml.encode("utf-8"), parser=etree.XMLParser(recover=True))
    except etree.XMLSyntaxError as e:
        raise HTTPException(400, f"XML parse error: {e}")
    if root is None:
        raise HTTPException(400, "could not parse XML")

    nsmap = None
    if req.ignore_ns:
        for el in root.iter():
            if isinstance(el.tag, str) and "}" in el.tag:
                el.tag = el.tag.split("}", 1)[1]
            for name in list(el.attrib):
                if "}" in name:
                    el.attrib[name.split("}", 1)[1]] = el.attrib.pop(name)
        etree.cleanup_namespaces(root)
    else:
        nsmap = {(k or "ns"): v for k, v in (root.nsmap or {}).items()}

    try:
        result = root.xpath(expr, namespaces=nsmap)
    except etree.XPathEvalError as e:
        raise HTTPException(400, f"XPath error: {e}")
    except Exception as e:
        raise HTTPException(400, f"XPath error: {type(e).__name__}: {e}")

    matches = []
    if isinstance(result, list):
        count = len(result)
        rtype = "nodeset"
        for item in result:
            if isinstance(item, etree._Element):
                matches.append(etree.tostring(item, pretty_print=True, encoding="unicode").rstrip())
            else:
                matches.append(str(item))
    else:
        count = 1
        rtype = type(result).__name__  # bool / float / str
        matches = [str(result)]

    return {"ok": True, "count": count, "type": rtype, "matches": matches}


# ============================================================
# v1.14.0 — saved XPath queries (plain JSON projects on disk)
# ============================================================
from tools import xpath_store as _xq_store


class XqNameReq(BaseModel):
    name: str


class XqSaveReq(BaseModel):
    project: str
    query: dict


class XqDeleteReq(BaseModel):
    project: str
    name: str


class XqImportReq(BaseModel):
    data: dict
    name: Optional[str] = None


@app.get("/api/xq-projects")
def api_xq_projects():
    return {"ok": True, "projects": _xq_store.list_projects()}


@app.post("/api/xq-project-create")
def api_xq_project_create(req: XqNameReq):
    try:
        _xq_store.create_project(req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/xq-project-delete")
def api_xq_project_delete(req: XqNameReq):
    _xq_store.delete_project(req.name)
    return {"ok": True}


@app.get("/api/xq-queries")
def api_xq_queries(name: str):
    return {"ok": True, "queries": _xq_store.get_queries(name)}


@app.post("/api/xq-save")
def api_xq_save(req: XqSaveReq):
    if not (req.query or {}).get("name"):
        raise HTTPException(400, "query.name is required")
    _xq_store.save_query(req.project, req.query)
    return {"ok": True}


@app.post("/api/xq-delete")
def api_xq_delete(req: XqDeleteReq):
    _xq_store.delete_query(req.project, req.name)
    return {"ok": True}


@app.get("/api/xq-export")
def api_xq_export(name: str):
    try:
        return _xq_store.export_project(name)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/api/xq-import")
def api_xq_import(req: XqImportReq):
    try:
        nm = _xq_store.import_project(req.data, req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "name": nm}


class NetconfXpathRequest(BaseModel):
    """Direct NETCONF XPath query — no LLM. Returns XML."""
    device_name: str
    xpath: str
    source: str = Field(default="state", pattern="^(state|config)$")
    timeout_seconds: int = Field(default=60, ge=5, le=300)


@app.post("/api/netconf-xpath")
async def api_netconf_xpath(req: NetconfXpathRequest):
    """Execute an XPath query against the device via NETCONF.

    source='state' uses NETCONF <get> (operational state).
    source='config' uses NETCONF <get-config source=running> (configuration).
    """
    devs = {d.name: d for d in _inventory.load_devices()}
    d = devs.get(req.device_name)
    if not d:
        raise HTTPException(400, f"unknown device {req.device_name!r}")

    _audit.log_event("netconf_xpath_ui",
                    device=d.name, source=req.source, xpath=req.xpath)

    # Reuse the existing _sync_get_state / _sync_get_config with filter_type=xpath
    from tools import netconf_tools as _nctools
    import time, asyncio

    t0 = time.monotonic()
    try:
        if req.source == "state":
            result = await asyncio.get_event_loop().run_in_executor(
                None, _nctools._sync_get_state, d, "xpath", "", req.xpath
            )
        else:
            result = await asyncio.get_event_loop().run_in_executor(
                None, _nctools._sync_get_config, d, "xpath", "", req.xpath
            )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        pretty = pretty_xml(result)
        from tools.ui_results import set_last_result
        set_last_result("netconf-xpath", pretty, device=d.name,
                        query=req.xpath, source=req.source, kind="xml")
        return {
            "ok": True,
            "result_xml": pretty,
            "elapsed_ms": elapsed_ms,
            "device": d.name,
            "source": req.source,
            "xpath": req.xpath,
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "elapsed_ms": elapsed_ms,
            "device": d.name,
        }


@app.get("/api/health")
def health():
    return {"ok": True, "version": APP_VERSION}
