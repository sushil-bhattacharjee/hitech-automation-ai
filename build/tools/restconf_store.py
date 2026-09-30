"""v1.12.0: persistent RESTCONF collections + environments, stored as Postman-format
JSON on disk so they export to / import from Postman and Bruno with no conversion.

Layout (under ~/.hitech_automation_ai/, so it survives zip upgrades):
  restconf/<project>.postman_collection.json        - Postman Collection v2.1
  restconf-environments/<env>.postman_environment.json - Postman Environment

Each saved request is a standard Postman `item` (method/header/url/auth/body) for
interoperability, PLUS a private `_netconfsw` object holding the exact native request
this app uses (lossless round-trip). Postman/Bruno ignore unknown keys, so the files
import cleanly there while we reload our own requests perfectly.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

from tools.state_dir import STATE_DIR
BASE_DIR = STATE_DIR
PROJECTS_DIR = BASE_DIR / "restconf"
ENVS_DIR = BASE_DIR / "restconf-environments"

_PM_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"


# ----------------------------- helpers ----------------------------- #

def _safe(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._ -]", "_", (name or "").strip())
    s = s.lstrip(".")   # no ".", ".." or hidden names: they would climb out of the folder
    return (s or "untitled")[:120]


def _atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# ----------------------- request <-> postman item ----------------------- #

def _request_to_item(req: dict) -> dict:
    """Native request dict -> Postman v2.1 item (+ private round-trip copy)."""
    from urllib.parse import urlencode, urlparse

    method = (req.get("method") or "GET").upper()
    uri = req.get("uri") or ""
    params = req.get("params") or {}
    headers = req.get("headers") or {}

    raw = uri
    if params:
        raw = raw + ("&" if "?" in raw else "?") + urlencode(params)
    url_obj = {"raw": raw}
    try:
        u = urlparse(uri)
        if u.scheme:
            url_obj["protocol"] = u.scheme
        if u.netloc:
            url_obj["host"] = [u.netloc]
        if u.path:
            url_obj["path"] = [p for p in u.path.split("/") if p != ""]
        if params:
            url_obj["query"] = [{"key": k, "value": str(v)} for k, v in params.items()]
    except Exception:
        pass

    request = {
        "method": method,
        "header": [{"key": k, "value": str(v)} for k, v in headers.items()],
        "url": url_obj,
    }

    at = req.get("auth_type") or "none"
    if at == "basic":
        request["auth"] = {"type": "basic", "basic": [
            {"key": "username", "value": req.get("auth_username") or "", "type": "string"},
            {"key": "password", "value": req.get("auth_password") or "", "type": "string"}]}
    elif at == "bearer":
        request["auth"] = {"type": "bearer", "bearer": [
            {"key": "token", "value": req.get("auth_token") or "", "type": "string"}]}
    else:
        request["auth"] = {"type": "noauth"}

    body = req.get("payload")
    if body:
        request["body"] = {"mode": "raw", "raw": body,
                           "options": {"raw": {"language": "json"}}}

    return {
        "name": req.get("name") or "Request",
        "request": request,
        # private, lossless copy of the exact native request (ignored by Postman/Bruno)
        "_netconfsw": {
            "name": req.get("name") or "Request",
            "method": method,
            "uri": uri,
            "params": params,
            "headers": headers,
            "auth_type": at,
            "auth_username": req.get("auth_username") or "",
            "auth_password": req.get("auth_password") or "",
            "auth_token": req.get("auth_token") or "",
            "device_name": req.get("device_name") or "",
            "payload": body or None,
            "verify_tls": bool(req.get("verify_tls")),
            "variables": req.get("variables") or {},
        },
    }


def _item_to_request(item: dict) -> dict:
    """Postman item -> native request dict. Prefer the lossless private copy; otherwise
    convert from the standard Postman fields (so foreign Postman/Bruno imports work)."""
    priv = item.get("_netconfsw")
    if isinstance(priv, dict) and priv.get("method"):
        return priv

    r = item.get("request") or {}
    if isinstance(r, str):
        r = {"method": "GET", "url": r}
    method = (r.get("method") or "GET").upper()

    url = r.get("url")
    uri, params = "", {}
    if isinstance(url, str):
        uri = url
    elif isinstance(url, dict):
        uri = url.get("raw") or ""
        for q in (url.get("query") or []):
            if q.get("key"):
                params[q["key"]] = q.get("value", "")

    headers = {}
    for h in (r.get("header") or []):
        if isinstance(h, dict) and h.get("key"):
            headers[h["key"]] = h.get("value", "")

    auth = r.get("auth") or {}
    atype = auth.get("type")
    at, user, pw, token = "none", "", "", ""
    if atype == "basic":
        at = "basic"
        for kv in auth.get("basic", []):
            if kv.get("key") == "username":
                user = kv.get("value", "")
            elif kv.get("key") == "password":
                pw = kv.get("value", "")
    elif atype == "bearer":
        at = "bearer"
        for kv in auth.get("bearer", []):
            if kv.get("key") == "token":
                token = kv.get("value", "")

    body = ""
    b = r.get("body") or {}
    if isinstance(b, dict) and b.get("mode") == "raw":
        body = b.get("raw") or ""

    return {
        "name": item.get("name") or "Request",
        "method": method, "uri": uri, "params": params, "headers": headers,
        "auth_type": at, "auth_username": user, "auth_password": pw, "auth_token": token,
        "device_name": "", "payload": body or None, "verify_tls": False, "variables": {},
    }


# ----------------------------- projects ----------------------------- #

def _project_files():
    if not PROJECTS_DIR.exists():
        return []
    return sorted(PROJECTS_DIR.glob("*.postman_collection.json"))


def _load_collection(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _find_project_path(name: str):
    for p in _project_files():
        col = _load_collection(p)
        if (col.get("info") or {}).get("name") == name:
            return p
    return None


def _new_collection(name: str) -> dict:
    return {
        "info": {"name": name, "_postman_id": str(uuid.uuid4()), "schema": _PM_SCHEMA},
        "item": [],
    }


def list_projects() -> list:
    out = []
    for p in _project_files():
        col = _load_collection(p)
        nm = (col.get("info") or {}).get("name")
        if nm:
            items = col.get("item") or []
            out.append({"name": nm, "count": len(items)})
    return sorted(out, key=lambda x: x["name"].lower())


def create_project(name: str) -> None:
    name = name.strip()
    if not name:
        raise ValueError("project name required")
    if _find_project_path(name):
        raise ValueError(f"project {name!r} already exists")
    _atomic_write_json(PROJECTS_DIR / f"{_safe(name)}.postman_collection.json",
                       _new_collection(name))


def delete_project(name: str) -> None:
    p = _find_project_path(name)
    if p and p.exists():
        p.unlink()


def rename_project(old: str, new: str) -> None:
    p = _find_project_path(old)
    if not p:
        raise ValueError(f"unknown project {old!r}")
    col = _load_collection(p)
    col.setdefault("info", {})["name"] = new.strip()
    p.unlink()
    _atomic_write_json(PROJECTS_DIR / f"{_safe(new)}.postman_collection.json", col)


def get_project_requests(name: str) -> list:
    p = _find_project_path(name)
    if not p:
        return []
    col = _load_collection(p)
    return [_item_to_request(it) for it in (col.get("item") or []) if isinstance(it, dict)]


def save_request(project: str, request: dict) -> None:
    """Upsert a request (by name) into a project collection, creating the project if needed."""
    p = _find_project_path(project)
    col = _load_collection(p) if p else _new_collection(project)
    col.setdefault("info", {}).setdefault("name", project)
    col.setdefault("item", [])
    item = _request_to_item(request)
    rname = item["name"]
    for i, existing in enumerate(col["item"]):
        if isinstance(existing, dict) and existing.get("name") == rname:
            col["item"][i] = item
            break
    else:
        col["item"].append(item)
    _atomic_write_json(p or (PROJECTS_DIR / f"{_safe(project)}.postman_collection.json"), col)


def delete_request(project: str, request_name: str) -> None:
    p = _find_project_path(project)
    if not p:
        return
    col = _load_collection(p)
    col["item"] = [it for it in (col.get("item") or [])
                   if not (isinstance(it, dict) and it.get("name") == request_name)]
    _atomic_write_json(p, col)


def export_project(name: str) -> dict:
    p = _find_project_path(name)
    if not p:
        raise ValueError(f"unknown project {name!r}")
    return _load_collection(p)


def import_collection(collection: dict, name: str = None) -> str:
    """Import a Postman collection JSON as a project. Returns the project name used."""
    if not isinstance(collection, dict) or "item" not in collection:
        raise ValueError("not a Postman collection (missing 'item')")
    nm = (name or (collection.get("info") or {}).get("name") or "Imported").strip()
    collection.setdefault("info", {})["name"] = nm
    collection["info"].setdefault("_postman_id", str(uuid.uuid4()))
    collection["info"]["schema"] = _PM_SCHEMA
    _atomic_write_json(PROJECTS_DIR / f"{_safe(nm)}.postman_collection.json", collection)
    return nm


# ----------------------------- environments ----------------------------- #

def _env_files():
    if not ENVS_DIR.exists():
        return []
    return sorted(ENVS_DIR.glob("*.postman_environment.json"))


def _find_env_path(name: str):
    for p in _env_files():
        try:
            env = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if env.get("name") == name:
            return p
    return None


def list_environments() -> list:
    out = []
    for p in _env_files():
        try:
            env = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if env.get("name"):
            out.append(env["name"])
    return sorted(out, key=str.lower)


def get_environment(name: str) -> dict:
    """Return {name, vars:{k:v}} for the named environment."""
    p = _find_env_path(name)
    if not p:
        return {"name": name, "vars": {}}
    try:
        env = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"name": name, "vars": {}}
    vars_ = {}
    for v in (env.get("values") or []):
        if isinstance(v, dict) and v.get("key") and v.get("enabled", True):
            vars_[v["key"]] = v.get("value", "")
    return {"name": env.get("name") or name, "vars": vars_}


def save_environment(name: str, vars_dict: dict) -> None:
    name = (name or "").strip()
    if not name:
        raise ValueError("environment name required")
    p = _find_env_path(name)
    env_id = str(uuid.uuid4())
    if p:
        try:
            env_id = json.loads(p.read_text(encoding="utf-8")).get("id") or env_id
        except Exception:
            pass
    env = {
        "id": env_id,
        "name": name,
        "values": [{"key": k, "value": v, "enabled": True, "type": "default"}
                   for k, v in (vars_dict or {}).items()],
        "_postman_variable_scope": "environment",
    }
    _atomic_write_json(p or (ENVS_DIR / f"{_safe(name)}.postman_environment.json"), env)


def delete_environment(name: str) -> None:
    p = _find_env_path(name)
    if p and p.exists():
        p.unlink()


def export_environment(name: str) -> dict:
    p = _find_env_path(name)
    if not p:
        raise ValueError(f"unknown environment {name!r}")
    return json.loads(p.read_text(encoding="utf-8"))


def import_environment(env: dict, name: str = None) -> str:
    if not isinstance(env, dict) or "values" not in env:
        raise ValueError("not a Postman environment (missing 'values')")
    nm = (name or env.get("name") or "Imported").strip()
    env["name"] = nm
    env.setdefault("id", str(uuid.uuid4()))
    env["_postman_variable_scope"] = "environment"
    _atomic_write_json(ENVS_DIR / f"{_safe(nm)}.postman_environment.json", env)
    return nm
