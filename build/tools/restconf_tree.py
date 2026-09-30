"""v1.19.0: Bruno-style nested collection tree for saved RESTCONF requests.

Replaces the flat Project/Saved model. A single JSON document holds an unlimited-depth
tree of folders and requests:

  node = {
    "id": "<uuid>",
    "type": "folder" | "request",
    "name": "...",
    "children": [ ... ]        # folders only
    "request": { native request dict }   # requests only
  }

Stored at ~/.hitech_automation_ai/restconf_tree.json (survives zip upgrades). The native
request dict is the exact shape the app's send path uses (method/uri/params/headers/
vars/auth/payload), so load is lossless.

On first run (no tree file yet) we MIGRATE the existing flat Postman collections from
restconf_store: each project -> a top-level folder, each saved request -> a child. The
old collection files are left untouched (export still works), we just seed the tree once.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from tools.state_dir import STATE_DIR
BASE_DIR = STATE_DIR
TREE_PATH = BASE_DIR / "restconf_tree.json"   # legacy/back-compat (restconf)

# v1.21.0: per-transport collection trees. Each scope is a separate JSON file.
SCOPES = ("restconf", "netconf", "cli", "xpath", "python")

def _tree_path(scope: str) -> Path:
    if scope not in SCOPES:
        raise ValueError(f"unknown scope {scope!r}")
    if scope == "restconf":
        return TREE_PATH                       # keep the original filename
    return BASE_DIR / f"{scope}_tree.json"


def _atomic_write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _new_id() -> str:
    return "n" + uuid.uuid4().hex[:12]


def _empty_tree(scope: str = "restconf") -> dict:
    return {"version": 1, "scope": scope,
            "root": {"id": "root", "type": "folder",
                     "name": scope.upper(), "children": []}}


# ----------------------------- migration ----------------------------- #

def _migrate_from_flat() -> dict:
    """Build a tree from the existing flat restconf_store projects (one-time seed)."""
    tree = _empty_tree()
    try:
        from tools import restconf_store as _rc
        for proj in _rc.list_projects():
            folder = {"id": _new_id(), "type": "folder", "name": proj["name"], "children": []}
            for req in _rc.get_project_requests(proj["name"]):
                folder["children"].append({
                    "id": _new_id(), "type": "request",
                    "name": req.get("name") or "Request", "request": req,
                })
            tree["root"]["children"].append(folder)
    except Exception:
        pass  # migration is best-effort; an empty tree is fine
    return tree


# ----------------------------- load / save ----------------------------- #

def load_tree(scope: str = "restconf") -> dict:
    path = _tree_path(scope)
    if path.exists():
        try:
            t = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(t, dict) and isinstance(t.get("root"), dict):
                return t
        except Exception:
            pass
    # first run for this scope -> seed (migrate where we can), persist, return
    if scope == "restconf":
        t = _migrate_from_flat()
    elif scope == "xpath":
        t = _migrate_xpath_queries()
    else:
        t = _empty_tree(scope)
    _atomic_write(path, t)
    return t


def save_tree(tree: dict, scope: str = "restconf") -> None:
    if not isinstance(tree, dict) or not isinstance(tree.get("root"), dict):
        raise ValueError("invalid tree")
    _sanitize(tree["root"], is_root=True)
    _atomic_write(_tree_path(scope), tree)


def _migrate_xpath_queries() -> dict:
    """Seed the xpath tree from the legacy 'saved queries' store (xpath_store), if present."""
    tree = _empty_tree("xpath")
    try:
        from tools import xpath_store as _xq
        projects = _xq.list_projects() if hasattr(_xq, "list_projects") else []
        for proj in projects:
            pname = proj["name"] if isinstance(proj, dict) else proj
            folder = {"id": _new_id(), "type": "folder", "name": pname, "children": []}
            queries = _xq.get_queries(pname) if hasattr(_xq, "get_queries") else []
            for q in (queries or []):
                folder["children"].append({
                    "id": _new_id(), "type": "request",
                    "name": q.get("name") or "query",
                    "request": {"kind": "xpath",
                                "device_name": q.get("device") or "",
                                "source": q.get("source") or "state",
                                "expr": q.get("xpath") or ""},
                })
            tree["root"]["children"].append(folder)
    except Exception:
        pass
    return tree


def _sanitize(node: dict, is_root: bool = False) -> None:
    """Ensure ids/types exist and structure is well-formed before persisting."""
    if not node.get("id"):
        node["id"] = "root" if is_root else _new_id()
    if node.get("type") not in ("folder", "request"):
        node["type"] = "folder" if "children" in node else "request"
    if node["type"] == "folder":
        node.setdefault("children", [])
        seen = set()
        for ch in node["children"]:
            if not ch.get("id") or ch["id"] in seen:
                ch["id"] = _new_id()
            seen.add(ch["id"])
            _sanitize(ch)
        node.pop("request", None)
    else:  # request
        node.setdefault("request", {})
        node.pop("children", None)


# --------------------------- node operations --------------------------- #
# These operate on an in-memory tree; caller persists with save_tree().

def _walk(node, parent=None):
    yield node, parent
    if node.get("type") == "folder":
        for ch in node.get("children", []):
            yield from _walk(ch, node)


def _find(tree, node_id):
    for n, p in _walk(tree["root"]):
        if n.get("id") == node_id:
            return n, p
    return None, None


def add_folder(tree: dict, parent_id: str, name: str) -> dict:
    parent, _ = _find(tree, parent_id)
    if not parent or parent.get("type") != "folder":
        raise ValueError("parent folder not found")
    node = {"id": _new_id(), "type": "folder", "name": (name or "New folder").strip(), "children": []}
    parent.setdefault("children", []).append(node)
    return node


def add_request(tree: dict, parent_id: str, name: str, request: dict) -> dict:
    parent, _ = _find(tree, parent_id)
    if not parent or parent.get("type") != "folder":
        raise ValueError("parent folder not found")
    node = {"id": _new_id(), "type": "request",
            "name": (name or request.get("name") or "Request").strip(),
            "request": request or {}}
    parent.setdefault("children", []).append(node)
    return node


def update_request(tree: dict, node_id: str, request: dict, name: str | None = None) -> dict:
    node, _ = _find(tree, node_id)
    if not node or node.get("type") != "request":
        raise ValueError("request node not found")
    node["request"] = request or {}
    if name:
        node["name"] = name.strip()
    return node


def rename_node(tree: dict, node_id: str, name: str) -> dict:
    node, _ = _find(tree, node_id)
    if not node:
        raise ValueError("node not found")
    if node.get("id") == "root":
        raise ValueError("cannot rename root")
    node["name"] = (name or "").strip() or node["name"]
    return node


def delete_node(tree: dict, node_id: str) -> None:
    if node_id == "root":
        raise ValueError("cannot delete root")
    node, parent = _find(tree, node_id)
    if not node or not parent:
        raise ValueError("node not found")
    parent["children"] = [c for c in parent.get("children", []) if c.get("id") != node_id]


def move_node(tree: dict, node_id: str, new_parent_id: str, index: int | None = None) -> None:
    """Move a node into new_parent at optional index. Guards against moving into self/descendant."""
    if node_id == "root":
        raise ValueError("cannot move root")
    node, old_parent = _find(tree, node_id)
    new_parent, _ = _find(tree, new_parent_id)
    if not node or not old_parent:
        raise ValueError("node not found")
    if not new_parent or new_parent.get("type") != "folder":
        raise ValueError("target is not a folder")
    # prevent dropping a folder into itself or one of its own descendants
    for desc, _p in _walk(node):
        if desc.get("id") == new_parent_id:
            raise ValueError("cannot move a folder into itself")
    old_parent["children"] = [c for c in old_parent.get("children", []) if c.get("id") != node_id]
    children = new_parent.setdefault("children", [])
    if index is None or index < 0 or index > len(children):
        children.append(node)
    else:
        children.insert(index, node)


# ----------------------------- import ----------------------------- #

def import_postman_collection(tree: dict, collection: dict) -> dict:
    """Import a Postman v2.1 collection as a new top-level folder, preserving nested
    folders. Reuses restconf_store._item_to_request for the per-request conversion so
    foreign Postman/Bruno exports load with the same fidelity as elsewhere."""
    from tools import restconf_store as _rc
    info = (collection or {}).get("info") or {}
    root_name = info.get("name") or "Imported"

    def conv_items(items):
        out = []
        for it in (items or []):
            if not isinstance(it, dict):
                continue
            if isinstance(it.get("item"), list):          # a folder
                out.append({"id": _new_id(), "type": "folder",
                            "name": it.get("name") or "Folder",
                            "children": conv_items(it["item"])})
            else:                                          # a request
                req = _rc._item_to_request(it)
                out.append({"id": _new_id(), "type": "request",
                            "name": it.get("name") or req.get("name") or "Request",
                            "request": req})
        return out

    folder = {"id": _new_id(), "type": "folder", "name": root_name,
              "children": conv_items((collection or {}).get("item"))}
    tree["root"].setdefault("children", []).append(folder)
    return folder
