"""v1.38.5: OpenAPI 3.0.3 generator from a YANG node subtree (YANG Suite parity).

Rewritten path construction after v1.38.4 produced malformed paths
(double key predicates `bgp={id}={id}`, and every child re-prefixed) that
exploded a 50-path spec to 12k+. This version builds each segment exactly
once with the correct module-prefix rule and single key predicate.

Segment prefix rule (matches YANG Suite):
  * top node of the whole doc  -> "<module>:<name>"
  * a node whose owning module differs from its parent (augment/first child of
    an augmented subtree) -> "<owner-module>:<name>"
  * otherwise -> bare "<name>"
We approximate "owner module changes" with the compact tree's `augmented_from`
field (set by the parser when a node was merged in from another module).

Method sets per node type (decoded from YANG Suite's exported JSON):
  container -> GET POST PUT PATCH DELETE
  list (collection, no key) -> GET POST PUT PATCH
  list (instance, ={key})   -> GET DELETE
  leaf / leaf-list          -> GET PUT PATCH DELETE
  key leaf                  -> path emitted, no operations
"""
from __future__ import annotations

_DATA_KW = {"container", "list", "leaf", "leaf-list", "anydata", "anyxml"}

_VERB_HTTP = {"View": "GET", "Add": "POST", "Replace": "PUT",
              "Modify": "PATCH", "Remove": "DELETE"}


def _seg(node: dict, module: str, first: bool, parent_module: str | None) -> str:
    """Segment text with YANG-Suite-style prefixing."""
    if first:
        return f"{module}:{node['name']}"
    owner = node.get("augmented_from")
    if owner and owner != parent_module:
        return f"{owner}:{node['name']}"
    return node["name"]


def _leaf_schema(node: dict) -> dict:
    ti = node.get("typeinfo") or {}
    dt = node.get("datatype") or ""
    if ti.get("is_bool"):
        s = {"type": "boolean"}
    elif ti.get("enums"):
        s = {"type": "string", "enum": list(ti["enums"])}
    elif any(t in dt for t in ("int", "byte")):
        s = {"type": "integer"}
    elif "decimal" in dt:
        s = {"type": "number"}
    else:
        s = {"type": "string"}
    if node.get("description"):
        s["description"] = node["description"][:120]
    return s


def _obj_schema(node: dict, depth: int = 0) -> dict:
    kw = node["keyword"]
    if kw == "leaf":
        return _leaf_schema(node)
    if kw == "leaf-list":
        return {"type": "array", "items": _leaf_schema(node)}
    props = {}
    if depth < 3:
        for c in node.get("children", []):
            if c["keyword"] not in _DATA_KW:
                continue
            k = (c.get("augmented_from") + ":" + c["name"]) if c.get("augmented_from") else c["name"]
            props[k] = _obj_schema(c, depth + 1)
    obj = {"type": "object"}
    if props:
        obj["properties"] = props
    return {"type": "array", "items": obj} if kw == "list" else obj


def _body(node: dict, root_key: str) -> dict:
    schema = _obj_schema(node)
    wrapped = {"type": "object", "properties": {root_key: schema}}
    return {"required": True,
            "content": {"application/yang-data+json": {"schema": wrapped}}}


def _responses(node, root_key):
    body = _body(node, root_key)["content"]["application/yang-data+json"]["schema"]
    return {"200": {"description": "OK",
                    "content": {"application/yang-data+json": {"schema": body}}},
            "201": {"description": "Created"}, "204": {"description": "No Content"},
            "400": {"description": "Bad Request"}, "401": {"description": "Unauthorized"},
            "404": {"description": "Not Found"}}


def _op(verb_word, node, name, params, with_body, root_key):
    title = name.replace("-", " ").title()
    o = {"summary": f'{_VERB_HTTP.get(verb_word, verb_word)} operation on "{name}"',
         "description": f'{verb_word} operation on "{name}"',
         "tags": [f"{verb_word} {title}"],
         "operationId": f"{verb_word.lower()}_{name.replace('-', '_')}",
         "responses": _responses(node, root_key)}
    if params:
        o["parameters"] = list(params)
    if with_body:
        o["requestBody"] = _body(node, root_key)
    return o


_CONTAINER_METHODS = [("get", "View"), ("post", "Add"), ("put", "Replace"),
                      ("patch", "Modify"), ("delete", "Remove")]
_LISTCOLL_METHODS = [("get", "View"), ("post", "Add"), ("put", "Replace"), ("patch", "Modify")]
_LISTINST_METHODS = [("get", "View"), ("delete", "Remove")]
_LEAF_METHODS = [("get", "View"), ("put", "Replace"), ("patch", "Modify"), ("delete", "Remove")]


def _walk(node, prefix_path, params, module, parent_module, first, paths, depth):
    """Emit path(s) for `node` (whose segment is already in prefix_path) and
    recurse. `params` = accumulated path params from list ancestors."""
    kw = node["keyword"]
    name = node["name"]
    root_key = (node.get("augmented_from") or module) + ":" + name
    my_module = node.get("augmented_from") or parent_module or module

    if kw == "list":
        # collection path
        ops = {verb: _op(word, node, name, params, verb in ("post", "put", "patch"), root_key)
               for verb, word in _LISTCOLL_METHODS}
        paths[prefix_path] = ops
        # keyed instance path (single predicate)
        inst_params = list(params)
        preds = ""
        for k in (node.get("key") or "").split():
            pname = f"{name}-{k}"
            preds += "={%s}" % pname
            inst_params.append({"name": pname, "in": "path", "required": True,
                                "schema": {"type": "string"},
                                "description": f"Key '{k}' of list '{name}'"})
        inst_path = prefix_path + preds
        paths[inst_path] = {verb: _op(word, node, name, inst_params, False, root_key)
                            for verb, word in _LISTINST_METHODS}
        if depth < 15:
            for c in node.get("children", []):
                if c["keyword"] not in _DATA_KW:
                    continue
                cseg = _seg(c, module, False, my_module)
                if c.get("is_key"):
                    paths[prefix_path + "/" + cseg] = {}   # key leaf under collection
                    continue
                _walk(c, inst_path + "/" + cseg, inst_params, module, my_module,
                      False, paths, depth + 1)
        return

    # container / leaf / leaf-list
    if node.get("is_key"):
        paths[prefix_path] = {}
    elif kw in ("leaf", "leaf-list"):
        paths[prefix_path] = {verb: _op(word, node, name, params, verb in ("put", "patch"), root_key)
                              for verb, word in _LEAF_METHODS}
    else:  # container / anydata / anyxml
        paths[prefix_path] = {verb: _op(word, node, name, params, verb in ("post", "put", "patch"), root_key)
                              for verb, word in _CONTAINER_METHODS}

    if kw in ("container", "anydata", "anyxml") and depth < 15:
        for c in node.get("children", []):
            if c["keyword"] not in _DATA_KW:
                continue
            cseg = _seg(c, module, False, my_module)
            if c.get("is_key"):
                paths[prefix_path + "/" + cseg] = {}
                continue
            _walk(c, prefix_path + "/" + cseg, params, module, my_module,
                  False, paths, depth + 1)


def generate_openapi(node: dict, node_chain: list[dict], meta: dict,
                     host: str = "") -> dict:
    module = meta.get("module", "module")
    name = node["name"]

    # Build the ancestor prefix (everything ABOVE the selected node), inserting
    # each ancestor list's single key predicate exactly once.
    parts = []
    params = []
    parent_module = None
    for i, n in enumerate(node_chain[:-1]):     # ancestors only
        seg = _seg(n, module, i == 0, parent_module)
        if n["keyword"] == "list" and n.get("key"):
            for k in n["key"].split():
                pname = f"{n['name']}-{k}"
                seg += "={%s}" % pname
                params.append({"name": pname, "in": "path", "required": True,
                               "schema": {"type": "string"},
                               "description": f"Key '{k}' of list '{n['name']}'"})
        parts.append(seg)
        parent_module = n.get("augmented_from") or parent_module or module

    first = len(node_chain) == 1
    node_seg = _seg(node, module, first, parent_module)
    node_prefix = "/data/" + "/".join(parts + [node_seg])

    paths: dict = {}
    _walk(node, node_prefix, params, module, parent_module, first, paths, 0)

    title = name.replace("-", " ").title()
    servers = [{"url": f"https://{host}/restconf", "description": "Device RESTCONF endpoint"}] if host \
        else [{"url": "https://{host}/restconf", "variables": {"host": {"default": "device"}}}]
    return {
        "openapi": "3.0.3",
        "info": {"title": f"{module} — {title} RESTCONF API", "version": "1.0.0",
                 "description": f'RESTCONF operations for "{name}" and its subtree '
                                f'({len(paths)} resources), generated from YANG by '
                                f'hiTech Automation AI.'},
        "servers": servers,
        "security": [{"basicAuth": []}],
        "components": {"securitySchemes": {"basicAuth": {"type": "http", "scheme": "basic"}}},
        "paths": paths,
    }
