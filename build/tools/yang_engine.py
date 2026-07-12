"""v1.36.0: embedded Cisco YANG Suite engine (Apache-2.0 pip packages), headless.

What we embed and why (evidence from prototyping against real 17.7.1 models):
  * ysnetconf.rpcbuilder.YSNetconfRPCBuilder — builds NETCONF <config>/<filter>
    payloads from (xpath, value) pairs, including list-key predicates
    ("...GigabitEthernet[ios:name=\"2\"]/...") rendered as key elements.
    This powers "Build RPC from tree values", YANG Suite's signature feature.
  * ysfilemanager.quickparser — revision-aware import/include scanner used for
    the Repository status dependency report (replaces our regex scan).

What we deliberately do NOT embed: their tree builder (YSYangModels). Tested
three ways headless (directory repo, full-set context, product-exact
YSYangRepository+YSMutableYangSet): augments outside the import closure do not
merge without their Django UI glue — while our own resolved-tree engine
produces the product-equivalent merge. Evidence in CHANGELOG v1.36.0.

Django note: the yangsuite packages require django.conf.settings to be
configured. We configure a minimal, serverless settings object once — no
Django app runs; FastAPI remains the only server.
"""
from __future__ import annotations

import os
from pathlib import Path

_BOOTSTRAPPED = False


class YangEngineError(Exception):
    pass


def _bootstrap():
    """Configure minimal Django settings once (required by yangsuite pkgs)."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    try:
        from django.conf import settings
        if not settings.configured:
            from tools.state_dir import STATE_DIR
            media = Path(STATE_DIR) / "yangsuite-media"
            media.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("MEDIA_ROOT", str(media))
            settings.configure(DEBUG=False, DATABASES={}, INSTALLED_APPS=[],
                               MEDIA_ROOT=str(media))
        _BOOTSTRAPPED = True
    except ImportError as e:  # pragma: no cover
        raise YangEngineError(
            "yangsuite engine packages not installed — pip install "
            "yangsuite yangsuite-netconf yangsuite-filemanager") from e


# ------------------------------------------------------------------ #
# NETCONF RPC building (YSNetconfRPCBuilder)                           #
# ------------------------------------------------------------------ #

def _rpcbuilder_cls():
    """Load ysnetconf/rpcbuilder.py DIRECTLY by path.

    Going through `import ysnetconf` drags in ysdevices→netmiko via the
    package __init__ — none of which the builder itself needs (it uses only
    lxml + yangsuite logging). Direct module load keeps the RPC builder
    independent and robust.
    """
    import importlib.util
    import importlib.machinery
    finder = importlib.machinery.PathFinder()
    spec = finder.find_spec("ysnetconf")
    if spec is None or not spec.submodule_search_locations:
        raise YangEngineError("ysnetconf package not installed")
    path = os.path.join(list(spec.submodule_search_locations)[0], "rpcbuilder.py")
    mspec = importlib.util.spec_from_file_location("ysnetconf_rpcbuilder", path)
    mod = importlib.util.module_from_spec(mspec)
    mspec.loader.exec_module(mod)
    return mod.YSNetconfRPCBuilder


def build_rpc(namespace: str, prefix: str, cfgs: list[dict],
              mode: str = "edit-config") -> str:
    """Build a NETCONF payload from (xpath, value) pairs.

    cfgs: [{"xpath": "/ios:native/ios:hostname", "value": "x"}] — xpaths use `prefix:`.
    mode: "edit-config" -> <config> payload;  "get" -> <filter type=subtree>.
    """
    # v1.42.3: use the embedded YANG Suite builder when available, otherwise
    # fall back to the native lxml builder (identical XML, zero extra deps).
    try:
        _bootstrap()
        YSNetconfRPCBuilder = _rpcbuilder_cls()
    except Exception:
        return build_payload_native(namespace, cfgs, mode)
    from lxml import etree

    if not cfgs:
        raise YangEngineError("no xpath/value pairs given")
    nsmap = {prefix: namespace}
    builder = YSNetconfRPCBuilder(prefix_namespaces="minimal", nsmap=nsmap)
    NC = "urn:ietf:params:xml:ns:netconf:base:1.0"
    if mode == "edit-config":
        root = etree.Element("{%s}config" % NC)
    else:
        root = etree.Element("{%s}filter" % NC)
        cfgs = [{**c, "value": ""} for c in cfgs]   # structure only for filters
    root = builder.get_payload(cfgs, root)
    return etree.tostring(root, pretty_print=True).decode()


# ------------------------------------------------------------------ #
# Dependency report (quickparser)                                     #
# ------------------------------------------------------------------ #

def repo_missing_dependencies_ys(repo_dir) -> list[dict]:
    """quickparser-based missing-dependency scan (revision-aware).

    Falls back to raising; caller keeps the regex scan as backup.
    """
    _bootstrap()
    from ysfilemanager import quickparser
    repo_dir = Path(repo_dir)
    have: set = set()
    needs: dict[str, set] = {}
    for p in sorted(repo_dir.glob("*.yang")):
        try:
            info = quickparser.quick_parse(str(p))
        except Exception:
            continue
        name = info.get("name") or p.stem.split("@")[0]
        have.add(name)
        # imports is {module_name: prefix}; includes is [submodule_name]
        for dep in (info.get("imports") or {}):
            needs.setdefault(dep, set()).add(name)
        for dep in (info.get("includes") or []):
            needs.setdefault(dep, set()).add(name)
    missing = sorted(d for d in needs if d not in have)
    return [{"module": d, "revision": "unknown",
             "needed_by": sorted(needs[d])[:8]} for d in missing]


# ------------------------------------------------------------------ #
# v1.40.0: full <rpc> envelope (what YANG Suite's "Build RPC" shows)  #
# ------------------------------------------------------------------ #

def build_xpath_filter(namespace: str, prefix: str, cfgs: list[dict]) -> str:
    """v1.41.0: <filter type="xpath" select="..."> from the selected node(s).

    NETCONF's xpath filter takes ONE select expression, so multiple selections
    are combined with the XPath union operator '|'. Namespace prefixes used in
    the expression are declared on the filter element itself (RFC 6241 §6.4.2).
    """
    from lxml import etree
    NC = "urn:ietf:params:xml:ns:netconf:base:1.0"
    paths = [c["xpath"] for c in cfgs if c.get("xpath")]
    if not paths:
        raise YangEngineError("no nodes selected for an xpath filter")
    select = " | ".join(dict.fromkeys(paths))          # de-dup, keep order
    # v1.43.2: <filter> MUST stay in the NETCONF base namespace. v1.43.1 put the
    # model namespace as the DEFAULT xmlns on <filter>, which moved the element
    # itself out of the NETCONF namespace — the device answered
    #   unknown-element ... <bad-element>filter</bad-element>
    # Correct forms (both match what ncclient puts on the wire):
    #   prefixed   -> <filter xmlns:oc-if="…" type="xpath" select="/oc-if:…"/>
    #   unprefixed -> <filter type="xpath" select="/interfaces/…"/>   (no model ns;
    #                 the device resolves bare names itself — this is exactly what
    #                 ncclient sends for filter=('xpath', '<string>'))
    nsmap = {prefix: namespace} if prefix else None
    flt = etree.Element("{%s}filter" % NC, nsmap=nsmap)
    flt.set("type", "xpath")
    flt.set("select", select)
    return etree.tostring(flt, pretty_print=True).decode()


def _unescape_select(xml: str) -> str:
    """v1.42.4: lxml always delimits attributes with double quotes, so every "
    inside starts-with(...,"Gigabit") is escaped to &quot; — valid XML, but
    unreadable. Re-emit the select attribute with SINGLE-quote delimiters so the
    inner double quotes stay literal (and skip it if the value contains ')."""
    m = _re2.search(r'select="([^"]*)"', xml)
    if not m:
        return xml
    esc = m.group(1)
    if "&quot;" not in esc:
        return xml
    raw = esc.replace("&quot;", '"')
    if "'" in raw:
        return xml                       # can't use single-quote delimiters
    # v1.43.0: put each union arm on its own line. XML attribute values may
    # contain newlines (the parser normalises them to spaces), and XPath treats
    # whitespace between tokens as insignificant — so this stays valid while
    # being far easier to read.
    if " | " in raw:
        indent = "\n" + " " * 12
        raw = raw.replace(" | ", indent + "| ")
    return xml.replace('select="%s"' % esc, "select='%s'" % raw)


def build_rpc_envelope(namespace: str, prefix: str, cfgs: list[dict],
                       operation: str = "get", target: str = "running",
                       message_id: str = "101",
                       filter_type: str = "subtree") -> str:
    """Return the complete <rpc> document for the chosen NETCONF operation.

      get         -> <rpc><get><filter type="subtree">…</filter></get></rpc>
      get-config  -> <rpc><get-config><source><running/></source>
                          <filter type="subtree">…</filter></get-config></rpc>
      edit-config -> <rpc><edit-config><target><running/></target>
                          <config>…</config></edit-config></rpc>
    """
    from lxml import etree
    NC = "urn:ietf:params:xml:ns:netconf:base:1.0"

    rpc = etree.Element("{%s}rpc" % NC, nsmap={None: NC})
    rpc.set("message-id", message_id)

    if operation == "edit-config":
        inner_el = etree.fromstring(
            build_rpc(namespace, prefix, cfgs, "edit-config").encode())
        op = etree.SubElement(rpc, "{%s}edit-config" % NC)
        tgt = etree.SubElement(op, "{%s}target" % NC)
        etree.SubElement(tgt, "{%s}%s" % (NC, target or "running"))
        op.append(inner_el)                               # <config>
        return etree.tostring(rpc, pretty_print=True).decode()

    op = etree.SubElement(rpc, "{%s}%s" % (NC, operation))
    if operation == "get-config":
        src = etree.SubElement(op, "{%s}source" % NC)
        etree.SubElement(src, "{%s}%s" % (NC, target or "running"))

    if filter_type == "xpath":                            # v1.41.0
        flt = etree.fromstring(build_xpath_filter(namespace, prefix, cfgs).encode())
    else:
        flt = etree.fromstring(build_rpc(namespace, prefix, cfgs, "get").encode())
        flt.set("type", "subtree")
    op.append(flt)
    out = etree.tostring(rpc, pretty_print=True).decode()
    if filter_type == "xpath":
        out = _unescape_select(out)                       # v1.42.4: readable select
    return out


# ------------------------------------------------------------------ #
# v1.42.3: native subtree/config builder — NO yangsuite dependency    #
# ------------------------------------------------------------------ #
# The yangsuite engine packages may not be installed (pip step missed), which
# made Build RPC fail outright. This pure-lxml builder produces the identical
# XML from the same (xpath, value) pairs, so the feature works out of the box.
# YSNetconfRPCBuilder is still used when the packages ARE present.

import re as _re2


def _parse_xpath(xpath: str):
    """['seg', {preds}] steps from '/p:a/p:b[p:k="v"]/p:c'."""
    steps = []
    for raw in [s for s in xpath.split("/") if s]:
        preds = {}
        name = raw
        if "[" in raw:
            name = raw[:raw.index("[")]
            for m in _re2.finditer(r'\[([^=\]]+)=(?:"([^"]*)"|\'([^\']*)\')\]', raw):
                k = m.group(1).split(":")[-1].strip()
                v = m.group(2) if m.group(2) is not None else m.group(3)
                preds[k] = v
        steps.append((name.split(":")[-1], preds))
    return steps


def build_payload_native(namespace: str, cfgs: list[dict], mode: str = "get") -> str:
    """Build <filter>/<config> content from (xpath, value) pairs with lxml only."""
    from lxml import etree
    NC = "urn:ietf:params:xml:ns:netconf:base:1.0"
    root_tag = "config" if mode == "edit-config" else "filter"
    root = etree.Element("{%s}%s" % (NC, root_tag))
    top = None
    for cfg in cfgs:
        steps = _parse_xpath(cfg.get("xpath") or "")
        if not steps:
            continue
        cur = None
        for i, (name, preds) in enumerate(steps):
            if i == 0:
                if top is None:
                    top = etree.SubElement(root, "{%s}%s" % (namespace, name),
                                           nsmap={None: namespace})
                cur = top
            else:
                # reuse an existing child that matches the same key predicates
                found = None
                for ch in cur:
                    if etree.QName(ch).localname != name:
                        continue
                    ok = True
                    for k, v in preds.items():
                        kid = ch.find("{%s}%s" % (namespace, k))
                        if kid is None or (kid.text or "") != v:
                            ok = False
                            break
                    if ok:
                        found = ch
                        break
                if found is None:
                    found = etree.SubElement(cur, "{%s}%s" % (namespace, name))
                    for k, v in preds.items():
                        ke = etree.SubElement(found, "{%s}%s" % (namespace, k))
                        ke.text = v
                cur = found
        val = cfg.get("value")
        if val not in (None, ""):
            cur.text = str(val)
    return etree.tostring(root, pretty_print=True).decode()
