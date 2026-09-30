"""Tools the LLM can invoke during agentic mode.

v1.3.0 — read-only CLI/RAG tools (run_show_command, search_corpus,
         describe_device, get_current_template)
v1.4.0 — adds NETCONF tools (list_devices, get_running_config, get_state,
         validate_config_xml, propose_edit_config, apply_edit_config)
         and human-in-the-loop approval workflow for write tools.
"""

from .definitions import AGENT_TOOLS, get_tool_definitions
from .executor import execute_tool, DeviceContext
from . import audit, inventory, netconf_tools

__all__ = [
    "AGENT_TOOLS",
    "get_tool_definitions",
    "execute_tool",
    "DeviceContext",
    "audit",
    "inventory",
    "netconf_tools",
]
