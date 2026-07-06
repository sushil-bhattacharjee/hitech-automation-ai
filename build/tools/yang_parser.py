"""v1.30.0: YANG parser for the YANG Explorer.

Uses pyang (pure-Python, same engine as Cisco YANG Suite) to parse a .yang module
and produce a normalized JSON tree of data nodes, each carrying the detail fields
shown in a node-detail popup (name, keyword, datatype, description, key, config,
namespace, prefix, xpath, restconf path).

Kept behind a small interface so a faster backend (libyang) can be added later
without changing yang_generate.py or the routes.

v1: parses a single module (upload-only). Import/include resolution comes in v2.
"""
from __future__ import annotations

from pathlib import Path

# pyang is imported lazily so the app still boots if it isn't installed yet
# (the YANG routes will report a clear error instead of crashing at import).
_DATA_KEYWORDS = {"container", "list", "leaf", "leaf-list"}
_TREE_KEYWORDS = {"container", "list", "leaf", "leaf-list", "choice", "case"}


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


def _desc(stmt) -> str:
    d = stmt.search_one("description")
    return (d.arg or "").strip() if d else ""


def build_tree(module, depth_limit: int = 0):
    """Walk the module into a nested JSON tree of data nodes.

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
            if s.keyword not in _TREE_KEYWORDS:
                continue
            is_data = s.keyword in _DATA_KEYWORDS
            xp = xpath_parts + ([s.arg] if is_data else [])
            if is_data:
                rc = [f"{modname}:{s.arg}"] if not restconf_parts else restconf_parts + [s.arg]
            else:
                rc = restconf_parts
            key = s.search_one("key")
            cfg = s.search_one("config")
            node = {
                "name": s.arg,
                "keyword": s.keyword,
                "datatype": _leaf_type(s),
                "key": key.arg if key else None,
                "config": (cfg.arg != "false") if cfg else True,
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
