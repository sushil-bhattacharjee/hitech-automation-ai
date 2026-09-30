"""Tool definitions — what the LLM is allowed to do in agentic mode (read-only)."""

from __future__ import annotations

from llm_providers import ToolDefinition


AGENT_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="run_show_command",
        description=(
            "Execute a read-only diagnostic command on a network device via SSH/CLI "
            "(Netmiko). Only `show`, `ping`, and `traceroute` commands are allowed — "
            "any attempt to modify configuration will be rejected. Returns the raw "
            "command output (truncated to ~150 lines if very long). Use this when "
            "you need live device state. "
            "IMPORTANT: pass device_name to target a device from the inventory "
            "(see list_devices). If device_name is omitted, the tool falls back to "
            "the device fields in the chat form, which may not be the device the "
            "user asked about."
        ),
        parameters={
            "type": "object",
            "properties": {
                "device_name": {
                    "type": "string",
                    "description": (
                        "Name of the device from inventory (e.g. 'cat8Kv71'). "
                        "Strongly recommended — call list_devices to see options. "
                        "Omit only when the user has not used a named device anywhere "
                        "in the conversation."
                    ),
                },
                "command": {
                    "type": "string",
                    "description": (
                        "The full command to execute, e.g. 'show ip bgp summary' or "
                        "'show running-config | section interface Gig0/0'. Must start "
                        "with 'show', 'ping', or 'traceroute'."
                    ),
                }
            },
            "required": ["command"],
        },
    ),

    ToolDefinition(
        name="search_corpus",
        description=(
            "Search the user's local documentation corpus (NETCONF, RESTCONF, YANG, Ansible, "
            "NX-OS, CCIE study notes, etc.) using semantic similarity. Returns the top relevant "
            "chunks with source filenames. Use this to ground your answer in the user's own "
            "reference material rather than relying on generic knowledge."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language query, e.g. 'how to delete an ACL via RESTCONF'.",
                },
                "k": {
                    "type": "integer",
                    "description": "Number of chunks to return. Default 5, max 10.",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),

    ToolDefinition(
        name="describe_device",
        description=(
            "Return metadata about the network device the user has currently configured "
            "in the chat form (host, port, device type, username — but NOT the password). "
            "Use this when you need to know what device you're working with."
        ),
        parameters={
            "type": "object",
            "properties": {},
        },
    ),

    ToolDefinition(
        name="get_current_template",
        description=(
            "Return the Jinja2 template and YAML variables the user currently has loaded "
            "in the editor. Use this when the user refers to 'my template' or 'this config' "
            "without copy-pasting it into chat."
        ),
        parameters={
            "type": "object",
            "properties": {},
        },
    ),

    ToolDefinition(
        name="read_last_result",
        description=(
            "Return the most recent direct-execute result the user ran in the Config Mgmt UI "
            "(NETCONF / RESTCONF / CLI / XPath) — i.e. the XML or text currently shown in their "
            "result pane. Use this whenever the user refers to 'the response', 'the output above', "
            "'the result I just got', or asks you to filter / format / summarize / explain it, "
            "instead of asking them to paste it. "
            "For large XML, STRONGLY PREFER extracting only the fields you need: pass row_element "
            "(a repeating element's local name, e.g. 'interface') and columns (relative '/'-separated "
            "local-name paths, e.g. ['name','state/counters/in-octets','state/counters/out-octets']). "
            "That returns a compact table instead of the full document, which is far more reliable "
            "than reading the whole dump. Omit both to get the raw result (truncated if very large)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "row_element": {
                    "type": "string",
                    "description": "Repeating XML element local name to extract one row per match (XML results only), e.g. 'interface'.",
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Relative local-name paths to pull per row, e.g. 'name' or 'state/counters/in-octets'.",
                },
            },
            "required": [],
        },
    ),
]


def get_tool_definitions() -> list[ToolDefinition]:
    """Return the canonical tool list (used by /api/chat-agent).

    v1.4.0: includes NETCONF tools alongside the v1.3 CLI/RAG tools so the
    LLM can choose the right transport. Read-only and write tools are mixed;
    the agent loop enforces the approval gate on write tools.

    v1.7.0: also includes RESTCONF tools (3rd transport).
    """
    from .netconf_tools import get_netconf_tool_definitions
    from .restconf_tools import RESTCONF_TOOLS
    return list(AGENT_TOOLS) + list(get_netconf_tool_definitions()) + list(RESTCONF_TOOLS)
