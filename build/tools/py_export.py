"""v1.48.0: generate a runnable ncclient script from what the user built in the UI.

One generator, two entry points (the XPath module and the NETCONF-YANG tab), so
the two exports can never drift apart.

Shape follows the user's own working scripts:
  * `Device.__init__` — explicit args win, otherwise environment variables (no Vault)
  * `session = manager.connect(...)` at module level (not a `with` block)
  * `reply = session.get(filter=(...))` -> `fromstring(reply.data_xml.encode())`
  * the raw XML dump is present but COMMENTED OUT (replies can be huge)
  * namespace dict + `xpath_extract` as named variables
  * per-column `entry.find(...)` with an "N/A" fallback for optional elements
  * `session.close_session()` commented at the end
"""
from __future__ import annotations

import re

_NC_PORT_DEFAULT = 830


def _env_prefix(device_name: str) -> str:
    """cat8Kv71 -> CAT8KV71"""
    return re.sub(r"[^A-Za-z0-9]", "_", device_name or "device").upper()


def _py_str(s: str) -> str:
    """String literal, preferring single quotes (XPath predicates use ")."""
    if "'" not in s:
        return "'" + s + "'"
    return '"' + s.replace('"', '\\"') + '"'


def normalize_xpath(expr: str) -> str:
    """v1.48.1: collapse newlines/indentation that the textarea preserved.

    A user can type an XPath across several lines for readability. That newline
    then travelled all the way to the device (which returned an empty <data/>)
    and into the generated script (producing an unterminated string literal).
    XPath treats whitespace between tokens as insignificant, so collapsing it is
    safe — but we must NOT touch whitespace inside quoted literals.
    """
    expr = (expr or "").strip()
    out, i, n = [], 0, len(expr)
    while i < n:
        ch = expr[i]
        if ch in "\"'":                       # copy a quoted literal verbatim
            q = ch
            j = expr.find(q, i + 1)
            if j == -1:
                out.append(expr[i:])
                break
            out.append(expr[i:j + 1])
            i = j + 1
            continue
        if ch in " \t\r\n":                    # collapse a whitespace run
            while i < n and expr[i] in " \t\r\n":
                i += 1
            # keep a single space only where it is syntactically needed
            if out and out[-1] and out[-1][-1] not in "[]()/=<>!," and i < n \
               and expr[i] not in "[]()/=<>!,":
                out.append(" ")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _wrap_expr(expr: str, indent: str = "    ") -> str:
    """Split a long XPath into implicitly-concatenated chunks at ][ boundaries."""
    expr = normalize_xpath(expr)
    if len(expr) <= 88:
        return _py_str(expr)
    parts = re.split(r"(?<=\])(?=\[)", expr)
    if len(parts) == 1:
        return _py_str(expr)
    return "(\n" + "\n".join(f"{indent}{_py_str(p)}" for p in parts) + "\n)"


def _prefix_from(namespace: str, module: str = "") -> str:
    """Short lxml prefix for the reply namespace: intf / bgp / ospf / oc-if / ios."""
    hay = f"{module} {namespace}".lower()
    for key, pfx in (
        ("openconfig.net/yang/interfaces", "oc-if"),
        ("interfaces-oper", "intf"),
        ("bgp-oper", "bgp"),
        ("ospf-oper", "ospf"),
        ("-native", "ios"),
        ("bgp", "bgp"),
        ("ospf", "ospf"),
        ("interfaces", "intf"),
    ):
        if key in hay:
            return pfx
    tail = (namespace or "m").rstrip("/").rsplit("/", 1)[-1]
    tail = re.sub(r"^Cisco-IOS-XE-", "", tail)
    return (re.sub(r"[^A-Za-z0-9]", "", tail).lower()[:6]) or "m"


def _extract_block(ns_uri: str, pfx: str, row: str, columns: list[dict]) -> str:
    """Client-side extraction — mirrors the 'Extract fields -> table' panel."""
    head = [
        "# ---------------------------------------------------------------------------",
        "# EXTRACT — client-side (mirrors the \u201cExtract fields \u2192 table\u201d panel)",
        "# ---------------------------------------------------------------------------",
        f'ns = {{"{pfx}": "{ns_uri}"}}',
    ]
    if not row or not columns:
        head += [
            f'xpath_extract = "//{pfx}:<row-element>"',
            "",
            "for entry in xml_rsp.xpath(xpath_extract, namespaces=ns):",
            f'    el = entry.find("{pfx}:<leaf>", ns)',
            '    print(el.text if el is not None else "N/A")',
        ]
        return "\n".join(head) + "\n"

    head += [
        f'xpath_extract = "//{pfx}:{row}"',
        "",
        "data = xml_rsp.xpath(xpath_extract, namespaces=ns)",
        "for entry in data:",
    ]
    names = []
    for col in columns:
        label = (col.get("label") or col.get("path") or "value").strip()
        path = (col.get("path") or label).strip().strip("/")
        var = re.sub(r"[^A-Za-z0-9]", "_", label).strip("_").lower() or "value"
        while var in names:
            var += "_"
        names.append(var)
        find_path = "/".join(f"{pfx}:{seg}" for seg in path.split("/") if seg)
        head.append(f'    {var}_el = entry.find("{find_path}", ns)')
        head.append(f'    {var} = {var}_el.text if {var}_el is not None else "N/A"')
    head.append("")
    fmt = " | ".join(f"{(c.get('label') or v)}={{{v}}}" for c, v in zip(columns, names))
    head.append(f'    print(f"{fmt}")')
    return "\n".join(head) + "\n"


def generate(
    *,
    device_name: str,
    host: str,
    source: str = "get",            # get | get-config
    filter_type: str = "xpath",     # xpath | subtree | edit-config
    xpath: str = "",
    subtree_xml: str = "",
    config_xml: str = "",
    namespace: str = "",
    module: str = "",
    row_element: str = "",
    columns: list[dict] | None = None,
    port: int = _NC_PORT_DEFAULT,
) -> str:
    columns = columns or []
    xpath = normalize_xpath(xpath)          # v1.48.1
    envp = _env_prefix(device_name)
    pfx = _prefix_from(namespace, module)
    what = {"xpath": "XPath filter", "subtree": "Subtree filter",
            "edit-config": "edit-config"}.get(filter_type, filter_type)
    src = "operational state (<get>)" if source == "get" else "configuration (<get-config>)"

    head = f'''"""
{what} \u2014 {device_name} ({host})
Generated by hiTech Automation AI.

  Source : {src}
  Model  : {module or namespace or "(see the namespace below)"}

Credentials come from environment variables by default:
    export {envp}_HOST={host}
    export {envp}_USER=<username>
    export {envp}_PASS=<password>

\u2026or pass them explicitly:  Device(host="{host}", username="\u2026", password="\u2026")
"""
import os

from ncclient import manager
from lxml.etree import fromstring, tostring


# ---------------------------------------------------------------------------
# DEVICE CONNECTION
# ---------------------------------------------------------------------------
class Device:
    """Credentials: whatever you pass in wins; anything left as None comes from
    the environment. Edit the defaults below to hard-code them instead."""

    def __init__(self, host=None, username=None, password=None):
        self.host = host or os.environ.get("{envp}_HOST", "{host}")
        self.username = username or os.environ.get("{envp}_USER")
        self.password = password or os.environ.get("{envp}_PASS")

        if not self.username or not self.password:
            raise SystemExit(
                "No credentials. Either export {envp}_USER / {envp}_PASS, "
                'or call Device(username="...", password="...").'
            )


dev = Device()
session = manager.connect(
    host=dev.host,
    port={port},
    username=dev.username,
    password=dev.password,
    hostkey_verify=False,
)

'''

    if filter_type == "edit-config":
        return head + f'''
# ---------------------------------------------------------------------------
# EDIT-CONFIG
# ---------------------------------------------------------------------------
config = """
{(config_xml or "").strip()}
"""

reply = session.edit_config(target="running", config=config)
print(reply)

# session.close_session()
'''

    if filter_type == "subtree":
        call = ('session.get(filter=("subtree", subtree_filter))' if source == "get"
                else 'session.get_config(source="running", filter=("subtree", subtree_filter))')
        query = f'''
# ---------------------------------------------------------------------------
# QUERY \u2014 subtree filter
# ---------------------------------------------------------------------------
subtree_filter = """
{(subtree_xml or "").strip()}
"""

reply = {call}
xml_rsp = fromstring(reply.data_xml.encode())

# Uncomment to dump the raw device response (it can be very large):
# print(tostring(xml_rsp, pretty_print=True, encoding="unicode"))

# NOTE: a subtree filter matches values EXACTLY \u2014 it cannot express OR or a
# numeric comparison. Do that locally inside the loop below, e.g.:
#     state = entry.find("{pfx}:connection/{pfx}:state", ns)
#     if state is None or state.text != "established":
#         continue

'''
    else:
        call = ('session.get(filter=("xpath", xpath_filter))' if source == "get"
                else 'session.get_config(source="running", filter=("xpath", xpath_filter))')
        query = f'''
# ---------------------------------------------------------------------------
# QUERY \u2014 XPath filter (evaluated on the device)
# ---------------------------------------------------------------------------
xpath_filter = {_wrap_expr(xpath)}

reply = {call}
xml_rsp = fromstring(reply.data_xml.encode())

# Uncomment to dump the raw device response (it can be very large):
# print(tostring(xml_rsp, pretty_print=True, encoding="unicode"))

'''

    return head + query + _extract_block(namespace, pfx, row_element, columns) + \
        "\n# session.close_session()\n"
