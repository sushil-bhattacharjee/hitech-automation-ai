"""v1.30.0: generate protocol artifacts from a selected YANG node.

v1 outputs:
  - RESTCONF data path  (module-prefixed first element, e.g. mod:cont/list/leaf)
  - XPath               (unprefixed on-device form, e.g. /cont/list/leaf)

Both come from the node dict produced by yang_parser.build_tree (which already
carries 'xpath' and 'restconf'). This module adds list-key predicate handling and
a NETCONF subtree-filter skeleton (used by v2's "Send to NETCONF").

Device conventions baked in (hard-won):
  - On-device NETCONF XPath is UNPREFIXED (element names only).
  - RESTCONF data paths DO use the module prefix on the first element.
"""
from __future__ import annotations

from xml.sax.saxutils import escape


def restconf_path(node: dict, root: str = "/restconf/data/") -> str:
    """Full RESTCONF GET URL path for a node."""
    return root + (node.get("restconf") or "")


def xpath(node: dict) -> str:
    """On-device (unprefixed) XPath for a node."""
    return node.get("xpath") or "/"


def restconf_with_keys(node: dict, key_values: dict | None = None) -> str:
    """RESTCONF path where list keys are filled: list=key1,key2 style.

    key_values: {list_name: [v1, v2, ...]} — RESTCONF uses key=val,val syntax.
    (v1 returns the plain path; this is here for v2 wiring.)
    """
    path = node.get("restconf") or ""
    if not key_values:
        return "/restconf/data/" + path
    # naive: append =values to segments that are lists with provided keys
    return "/restconf/data/" + path


def netconf_subtree_filter(path_nodes: list[dict], namespace: str) -> str:
    """Build a NETCONF <filter type="subtree"> skeleton from a node ancestry list.

    path_nodes: ordered list of node dicts from root → target.
    (Used by v2's Send-to-NETCONF; included now so the interface is stable.)
    """
    if not path_nodes:
        return ""
    # nest elements; put namespace on the outermost element
    inner = ""
    for i, n in enumerate(reversed(path_nodes)):
        name = escape(n["name"])
        if i == 0:
            inner = f"<{name}/>"
        else:
            inner = f"<{name}>{inner}</{name}>"
    # apply namespace to the first (outermost) element
    first = escape(path_nodes[0]["name"])
    inner = inner.replace(f"<{first}>", f'<{first} xmlns="{escape(namespace)}">', 1)
    if inner == f"<{first}/>":
        inner = f'<{first} xmlns="{escape(namespace)}"/>'
    return f'<filter type="subtree">\n  {inner}\n</filter>'


def generate(node: dict) -> dict:
    """v1 entry point: return the generated artifacts for a node."""
    return {
        "restconf_path": restconf_path(node),
        "xpath": xpath(node),
        "keyword": node.get("keyword"),
        "list_key": node.get("key"),
        "config": node.get("config", True),
    }
