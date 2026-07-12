"""v1.31.0: YANG parser for the YANG Explorer.

Uses pyang (pure-Python, same engine as Cisco YANG Suite) to parse a .yang module
and produce a normalized JSON tree of nodes, each carrying the detail fields
shown in a node-detail popup (name, keyword, datatype, description, key, config,
namespace, prefix, xpath, restconf path) plus YANGSuite-legend metadata
(presence, mandatory, must, when, leafref target, status).

Kept behind a small interface so a faster backend (libyang) can be added later
without changing yang_generate.py or the routes.

v1.31.0: full YANGSuite legend coverage — rpc/action/input/output/notification/
anydata/anyxml nodes; presence / mandatory / must / when / leafref badges.
Deviation (not-supported) rendering is deferred to v2.
"""
from __future__ import annotations

from pathlib import Path

# pyang is imported lazily so the app still boots if it isn't installed yet
# (the YANG routes will report a clear error instead of crashing at import).

# Nodes that form the *data* tree (contribute to XPath / RESTCONF data paths)
_DATA_KEYWORDS = {"container", "list", "leaf", "leaf-list", "anydata", "anyxml"}
# Everything we render in the schema tree (YANGSuite "Display all nodes")
_TREE_KEYWORDS = {
    "container", "list", "leaf", "leaf-list", "choice", "case",
    "rpc", "action", "input", "output", "notification", "anydata", "anyxml",
}


class YangParseError(Exception):
    pass


def _load_pyang():
    try:
        from pyang import repository, context
        return repository, context
    except Exception as e:  # pragma: no cover
        raise YangParseError(
            "pyang is not installed. Add 'pyang' to requirements.txt and "
            "pip install it into the venv."
        ) from e


def parse_module(yang_path: str, search_dirs: list[str] | None = None):
    """Parse a .yang file. Returns (ctx, module, errors[])."""
    repository, context = _load_pyang()
    search = [str(Path(yang_path).parent)] + (search_dirs or [])
    repo = repository.FileRepository(":".join(search))
    ctx = context.Context(repo)
    text = Path(yang_path).read_text(encoding="utf-8")
    module = ctx.add_module(yang_path, text)
    if module is None:
        # collect fatal parse errors
        errs = [f"{e[1]}: {e[2]}" for e in ctx.errors]
        raise YangParseError("Failed to parse module. " + ("; ".join(errs) if errs else ""))
    ctx.validate()
    errors = []
    for epos, etag, eargs in ctx.errors:
        try:
            msg = str(etag)
            errors.append(f"{epos}: {msg} {eargs}")
        except Exception:
            errors.append(str(etag))
    return ctx, module, errors


def _leaf_type(stmt) -> str | None:
    t = stmt.search_one("type")
    return t.arg if t else None


def _type_info(stmt) -> dict:
    """Return {base, enums:[...], is_bool, leafref_path, range, pattern} for a
    leaf/leaf-list.

    v1.44.0: the type may be a TYPEDEF that resolves to an enumeration in
    another module (e.g. Cisco-IOS-XE-interfaces-oper's `intf-state`). Previously
    we only looked for a literal `type enumeration`, so those leaves rendered as
    a plain text box instead of a dropdown. We now use pyang's RESOLVED type
    spec (i_type_spec), which follows typedefs and unions for us.
    """
    t = stmt.search_one("type")
    if not t:
        return {}
    base = t.arg
    info = {"base": base}

    spec = getattr(t, "i_type_spec", None)
    enums = []

    def _collect(sp):
        """Harvest enum names from a (possibly union/typedef) type spec."""
        if sp is None:
            return
        vals = getattr(sp, "enums", None)          # EnumTypeSpec
        if vals:
            for v in vals:
                name = v[0] if isinstance(v, (list, tuple)) else v
                if name not in enums:
                    enums.append(name)
        # UnionTypeSpec.types holds type STATEMENTS — recurse into their specs
        for sub in (getattr(sp, "types", None) or []):
            _collect(getattr(sub, "i_type_spec", None) if hasattr(sub, "i_type_spec") else sub)

    _collect(spec)
    if enums:
        info["enums"] = enums
    elif base == "enumeration":                    # fallback: literal enumeration
        info["enums"] = [e.arg for e in t.substmts if e.keyword == "enum"]

    if base == "boolean" or type(spec).__name__ == "BooleanTypeSpec":
        info["is_bool"] = True
    if base == "leafref":
        p = t.search_one("path")
        if p:
            info["leafref_path"] = p.arg

    # v1.44.0: identityref -> offer the derived identities as options
    if base.endswith("identityref"):
        b = t.search_one("base")
        ident = getattr(b, "i_identity", None) if b is not None else None
        derived = getattr(ident, "i_derived", None) if ident is not None else None
        if derived:
            names = sorted(derived.keys() if hasattr(derived, "keys") else
                           [d.arg for d in derived])
            if names:
                info["enums"] = names

    # v1.44.0: restrictions worth showing as an input hint
    def _restr(node, kw):
        r = node.search_one(kw)
        if r is not None:
            return r.arg
        td = getattr(node, "i_typedef", None)
        if td is not None:
            tt = td.search_one("type")
            if tt is not None:
                rr = tt.search_one(kw)
                if rr is not None:
                    return rr.arg
        return None

    rng = _restr(t, "range")
    if rng:
        info["range"] = rng
    ln = _restr(t, "length")
    if ln:
        info["length"] = ln
    pat = _restr(t, "pattern")
    if pat:
        info["pattern"] = pat
    return info


def _desc(stmt) -> str:
    d = stmt.search_one("description")
    return (d.arg or "").strip() if d else ""


def build_tree(module, depth_limit: int = 0):
    """Walk the module into a nested JSON tree of schema nodes.

    depth_limit: 0 = unlimited; otherwise stop descending beyond that depth.
    """
    ns = module.search_one("namespace")
    prefix = module.search_one("prefix")
    namespace = ns.arg if ns else ""
    modprefix = prefix.arg if prefix else ""
    modname = module.arg

    def walk(stmt, depth, xpath_parts, restconf_parts):
        nodes = []
        for s in stmt.substmts:
            # expand 'uses <grouping>' inline (pyang keeps it as a separate stmt)
            if s.keyword == "uses":
                grp = getattr(s, "i_grouping", None)
                if grp is not None:
                    nodes.extend(walk(grp, depth, xpath_parts, restconf_parts))
                continue
            if s.keyword not in _TREE_KEYWORDS:
                continue
            is_data = s.keyword in _DATA_KEYWORDS
            # input/output have no name arg in pyang (arg is None)
            name = s.arg if s.arg else s.keyword
            xp = xpath_parts + ([name] if is_data else [])
            if is_data:
                rc = [f"{modname}:{name}"] if not restconf_parts else restconf_parts + [name]
            else:
                rc = restconf_parts
            key = s.search_one("key")
            cfg = s.search_one("config")
            status_stmt = s.search_one("status")
            status = status_stmt.arg if status_stmt else "current"
            # v1.31.0 legend metadata
            presence = s.search_one("presence") is not None
            mand_stmt = s.search_one("mandatory")
            mandatory = bool(mand_stmt and mand_stmt.arg == "true")
            musts = [m.arg for m in s.search("must")]
            when_stmt = s.search_one("when")
            when = when_stmt.arg if when_stmt else None
            tinfo = _type_info(s) if s.keyword in ("leaf", "leaf-list") else {}
            node = {
                "name": name,
                "keyword": s.keyword,
                "datatype": _leaf_type(s),
                "typeinfo": tinfo,
                "is_key": False,  # set below when a parent list declares keys
                "key": key.arg if key else None,
                "config": (cfg.arg != "false") if cfg else True,
                "status": status,
                "presence": presence,
                "mandatory": mandatory,
                "must": musts,
                "when": when,
                "leafref": tinfo.get("leafref_path"),
                "description": _desc(s)[:200],
                "namespace": namespace,
                "prefix": modprefix,
                "module": modname,
                "xpath": "/" + "/".join(xp) if xp else "/",
                "restconf": "/".join(rc) if rc else "",
                "children": [],
            }
            if depth_limit == 0 or depth < depth_limit:
                node["children"] = walk(s, depth + 1, xp, rc)
                # mark key leaves for list nodes
                if s.keyword == "list" and node.get("key"):
                    keyset = set(node["key"].split())
                    for ch in node["children"]:
                        if ch["name"] in keyset:
                            ch["is_key"] = True
            else:
                node["truncated"] = True
            nodes.append(node)
        return nodes

    rev = module.search_one("revision")
    return {
        "module": modname,
        "namespace": namespace,
        "prefix": modprefix,
        "revision": rev.arg if rev else "",
        "children": walk(module, 1, [], []),
    }


# ------------------------------------------------------------------ #
# v1.33.0: module-set parsing context (Cisco YANG Suite semantics)    #
# ------------------------------------------------------------------ #
# All modules of a set are added to ONE pyang context and validated   #
# together, so imports resolve and AUGMENTS FROM OTHER MODULES are    #
# merged into the target tree (pyang's i_children). This is what      #
# makes /native/router show the BGP/OSPF/EIGRP/... containers that    #
# live in separate Cisco-IOS-XE-* modules.                            #
# ------------------------------------------------------------------ #

import re as _re

_SET_CACHE: dict = {}   # set_name -> {"sig": str, "ctx": ..., "mods": {file: module}}


def _set_signature(repo_dir, files: list[str]) -> str:
    parts = []
    for f in sorted(files):
        p = repo_dir / f
        try:
            parts.append(f + str(p.stat().st_mtime_ns))
        except OSError:
            parts.append(f + "missing")
    return str(hash("|".join(parts)))


def _dedupe_latest(files: list[str]):
    """Keep only the newest revision per module name.

    Two revisions of the same module in one pyang context break prefix→module
    resolution and flood the set with 'node X is not found in module Y' errors
    (and augment merging dies, so trees render without children). Filenames
    carry the revision (name@YYYY-MM-DD.yang); revisionless names sort oldest.
    """
    by_name: dict = {}
    for f in files:
        stem = f[:-5] if f.endswith(".yang") else f
        name, _, rev = stem.partition("@")
        cur = by_name.get(name)
        if cur is None or rev > cur[1]:
            by_name[name] = (f, rev)
    keep = {v[0] for v in by_name.values()}
    skipped = sorted(set(files) - keep)
    return [f for f in files if f in keep], skipped


def parse_set(repo_dir, files: list[str], set_name: str):
    """Parse all files as one context. Returns (mods{file:module}, errors[]).
    Cached per set until any file's mtime changes. Duplicate module names are
    reduced to the newest revision (v1.34.1) and reported as warnings."""
    repository, context = _load_pyang()
    repo_dir = Path(repo_dir)
    sig = _set_signature(repo_dir, files)
    c = _SET_CACHE.get(set_name)
    if c and c["sig"] == sig:
        return c["mods"], c["errors"]
    files, skipped = _dedupe_latest(files)
    repo = repository.FileRepository(str(repo_dir))
    ctx = context.Context(repo)
    mods = {}
    for f in files:
        p = repo_dir / f
        if not p.exists():
            continue
        try:
            m = ctx.add_module(str(p), p.read_text(encoding="utf-8", errors="replace"))
            if m is not None:
                mods[f] = m
        except Exception:
            continue
    ctx.validate()
    errors = []
    for epos, etag, eargs in ctx.errors:
        try:
            from pyang import error as _perr
            level = _perr.err_level(etag)
            msg = _perr.err_to_str(etag, eargs)
            kind = "error" if _perr.is_error(level) else "warning"
        except Exception:
            msg, kind = str(etag), "error"
        errors.append({"pos": str(epos), "kind": kind, "msg": msg})
    for f in skipped:
        errors.insert(0, {"pos": f, "kind": "warning",
                          "msg": "duplicate module name — older revision SKIPPED "
                                 "(newest revision kept; delete older duplicates "
                                 "in the Repo tab to silence this)"})
    _SET_CACHE[set_name] = {"sig": sig, "ctx": ctx, "mods": mods, "errors": errors}
    return mods, errors


def build_tree_resolved(module, depth_limit: int = 0):
    """Walk pyang's RESOLVED tree (i_children): groupings expanded and
    augments from other modules merged in. Same node schema as build_tree."""
    ns = module.search_one("namespace")
    prefix = module.search_one("prefix")
    namespace = ns.arg if ns else ""
    modprefix = prefix.arg if prefix else ""
    modname = module.arg

    def node_of(s, depth, xpath_parts, restconf_parts):
        is_data = s.keyword in _DATA_KEYWORDS
        name = s.arg if s.arg else s.keyword
        # nodes augmented in from another module keep their own module/prefix
        owner = getattr(s, "i_module", None)
        owner_name = owner.arg if owner is not None else modname
        xp = xpath_parts + ([name] if is_data else [])
        if is_data:
            seg = f"{owner_name}:{name}" if (not restconf_parts or owner_name != modname) else name
            first = f"{owner_name}:{name}"
            rc = [first] if not restconf_parts else restconf_parts + [seg if owner_name != modname else name]
        else:
            rc = restconf_parts
        key = s.search_one("key")
        cfg = getattr(s, "i_config", None)
        status_stmt = s.search_one("status")
        status = status_stmt.arg if status_stmt else "current"
        presence = s.search_one("presence") is not None
        mand_stmt = s.search_one("mandatory")
        mandatory = bool(mand_stmt and mand_stmt.arg == "true")
        musts = [m.arg for m in s.search("must")]
        when_stmt = s.search_one("when")
        when = when_stmt.arg if when_stmt else None
        tinfo = _type_info(s) if s.keyword in ("leaf", "leaf-list") else {}
        # v1.34.3: COMPACT node — omit defaults and anything the client can
        # derive from the parent chain (xpath/restconf/module/namespace).
        # Cuts native@depth8 from ~77MB to a fraction; lazy DOM does the rest.
        node = {"name": name, "keyword": s.keyword}
        dt = _leaf_type(s)
        if dt: node["datatype"] = dt
        if tinfo: node["typeinfo"] = tinfo
        if getattr(s, "i_is_key", False): node["is_key"] = True
        if key: node["key"] = key.arg
        if cfg is False: node["config"] = False
        if status != "current": node["status"] = status
        if presence: node["presence"] = True
        if mandatory: node["mandatory"] = True
        if musts: node["must"] = musts
        if when: node["when"] = when
        if tinfo.get("leafref_path"): node["leafref"] = tinfo["leafref_path"]
        if owner_name != modname: node["augmented_from"] = owner_name
        desc = _desc(s)[:200]
        if desc: node["description"] = desc
        kids = getattr(s, "i_children", None) or []
        if depth_limit == 0 or depth < depth_limit:
            ch = [node_of(c, depth + 1, xp, rc)
                  for c in kids if c.keyword in _TREE_KEYWORDS]
            if ch: node["children"] = ch
        elif kids:
            node["truncated"] = True
        return node

    rev = module.search_one("revision")
    top = getattr(module, "i_children", None) or []
    return {
        "module": modname,
        "namespace": namespace,
        "prefix": modprefix,
        "revision": rev.arg if rev else "",
        "children": [node_of(c, 1, [], []) for c in top
                     if c.keyword in _TREE_KEYWORDS],
    }


# ------------------------------------------------------------------ #
# v1.33.0: repository status — missing dependencies                   #
# ------------------------------------------------------------------ #

_IMPORT_RE = _re.compile(r'^\s*(?:import|include)\s+([A-Za-z0-9._-]+)', _re.M)


def repo_missing_dependencies(repo_dir) -> list[dict]:
    """Fast regex scan: every import/include target not present in the repo.
    Matches YANG Suite's 'missing modules' report (revision shown as unknown)."""
    repo_dir = Path(repo_dir)
    have = set()
    deps: dict[str, set] = {}
    for p in repo_dir.glob("*.yang"):
        modname = p.stem.split("@")[0]
        have.add(modname)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dep in _IMPORT_RE.findall(text):
            deps.setdefault(dep, set()).add(modname)
    missing = sorted(d for d in deps if d not in have)
    return [{"module": d, "revision": "unknown",
             "needed_by": sorted(deps[d])[:8]} for d in missing]


# ------------------------------------------------------------------ #
# v1.34.2: findings triage — group by pattern, tag known-benign ones  #
# ------------------------------------------------------------------ #
# Proven against real Cisco IOS-XE 17.7.1 models (637 modules): pyang
# reports 1400+ findings, yet the resolved tree (augments merged) is
# complete and correct. These patterns are inherent to Cisco's models
# and are also visible in Cisco YANG Suite's own validation page.

_BENIGN_PATTERNS = [
    ("is not found in module",
     "Cross-module XPath/leafref reference inside a grouping — pyang cannot "
     "resolve /ios:native/... paths at the grouping's definition site. Normal "
     "for Cisco IOS-XE models; tree building and augment merging are UNAFFECTED."),
    ("in the path for",
     "Leafref path inside a grouping referencing another module's tree — same "
     "root cause as above. Normal for Cisco IOS-XE models; tree building and "
     "augment merging are UNAFFECTED (verified against real 17.7.1 models)."),
    ("the escape sequence",
     "Style warning about \\ escapes in double-quoted strings in Cisco/openconfig "
     "sources. Harmless."),
    ("not used",
     "A module imports something it doesn't reference. Harmless."),
    ("is not found",
     "Deviation/augment target could not be resolved (typically Cisco's "
     "openconfig deviation modules). Those deviations are not applied; the "
     "Cisco-IOS-XE-native tree is unaffected."),
    ("syntax error in pattern",
     "A leaf's XSD regex pattern is stricter than pyang's validator accepts. "
     "Affects validation of that one pattern only; the tree still builds."),
    ("duplicate module name",
     "Older revision skipped automatically — use Repo → Delete older duplicate "
     "revisions to clean the repository."),
]


def _finding_signature(msg: str) -> str:
    """Collapse paths, line numbers, and quoted names so identical problem
    shapes group together."""
    s = _re.sub(r"/[^\s:]+\.yang", "<file>", msg)
    s = _re.sub(r":\d+", ":<line>", s)
    s = _re.sub(r'"[^"]*"', '"<name>"', s)
    s = _re.sub(r"in the path for \S+", "in the path for <name>", s)
    return s.strip()


def triage_findings(errors: list[dict]) -> dict:
    """Group raw findings; tag known-benign patterns.

    Returns {errors_total, warnings_total, benign_total, blocking_total,
             groups: [{kind, benign, explanation, count, sample, positions[:3]}]}
    sorted with blocking (non-benign) groups first.
    """
    groups: dict = {}
    for e in errors:
        msg = e.get("msg", "")
        benign_expl = next((expl for pat, expl in _BENIGN_PATTERNS if pat in msg), None)
        sig = _finding_signature(msg)
        g = groups.setdefault(sig, {"kind": e.get("kind", "error"),
                                    "benign": benign_expl is not None,
                                    "explanation": benign_expl or "",
                                    "count": 0, "sample": msg, "positions": []})
        g["count"] += 1
        if e.get("kind") == "error":
            g["kind"] = "error"   # group severity = worst member
        if len(g["positions"]) < 3:
            g["positions"].append(e.get("pos", ""))
    glist = sorted(groups.values(),
                   key=lambda g: (g["benign"], g["kind"] != "error", -g["count"]))
    errors_total = sum(1 for e in errors if e.get("kind") == "error")
    benign_total = sum(g["count"] for g in glist if g["benign"])
    return {
        "errors_total": errors_total,
        "warnings_total": len(errors) - errors_total,
        "benign_total": benign_total,
        "blocking_total": len(errors) - benign_total,
        "groups": glist[:60],
    }


# ------------------------------------------------------------------ #
# v1.42.0: augment-only modules                                       #
# ------------------------------------------------------------------ #
# A module like openconfig-if-ethernet has NO top-level data nodes — it only
# augments another module (openconfig-interfaces). Rendering it alone yields an
# empty tree. Cisco YANG Suite shows the augment TARGET's tree alongside it.
# We detect the case and report which modules the selection augments so the
# caller can load those instead/as well.

def augment_targets(module) -> list[str]:
    """Module names that `module` augments (via its top-level augment stmts)."""
    targets: list[str] = []
    for aug in module.search("augment"):
        arg = aug.arg or ""
        # "/oc-if:interfaces/oc-if:interface" -> prefix of the first step
        first = arg.lstrip("/").split("/", 1)[0]
        if ":" not in first:
            continue
        pfx = first.split(":", 1)[0]
        # map prefix -> imported module name
        for imp in module.search("import"):
            p = imp.search_one("prefix")
            if p is not None and p.arg == pfx:
                if imp.arg not in targets:
                    targets.append(imp.arg)
                break
    return targets


def has_data_nodes(module) -> bool:
    """True if the module contributes any top-level schema node of its own."""
    kids = getattr(module, "i_children", None) or []
    return any(c.keyword in _TREE_KEYWORDS for c in kids)
