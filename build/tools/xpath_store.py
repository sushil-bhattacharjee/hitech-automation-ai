"""v1.14.0: persistent saved XPath queries — plain JSON on disk, organized by project.

Layout (under ~/.hitech_automation_ai/, so it survives zip upgrades):
  xpath/<project>.json  ->  {"name": "<project>",
                             "queries": [{"name","device","source","xpath"}, ...]}

No Postman/Bruno format here — an XPath query isn't an HTTP request, so there's no
external tool to interop with; Export/Import is just JSON backup/share.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from tools.state_dir import STATE_DIR
BASE_DIR = STATE_DIR
XPATH_DIR = BASE_DIR / "xpath"


def _safe(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._ -]", "_", (name or "").strip())
    s = s.lstrip(".")   # no ".", ".." or hidden names: they would climb out of the folder
    return (s or "untitled")[:120]


def _atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _project_files():
    if not XPATH_DIR.exists():
        return []
    return sorted(XPATH_DIR.glob("*.json"))


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _find_project_path(name: str):
    for p in _project_files():
        if _load(p).get("name") == name:
            return p
    return None


def list_projects() -> list:
    out = []
    for p in _project_files():
        d = _load(p)
        if d.get("name"):
            out.append({"name": d["name"], "count": len(d.get("queries") or [])})
    return sorted(out, key=lambda x: x["name"].lower())


def create_project(name: str) -> None:
    name = (name or "").strip()
    if not name:
        raise ValueError("project name required")
    if _find_project_path(name):
        raise ValueError(f"project {name!r} already exists")
    _atomic_write_json(XPATH_DIR / f"{_safe(name)}.json", {"name": name, "queries": []})


def delete_project(name: str) -> None:
    p = _find_project_path(name)
    if p and p.exists():
        p.unlink()


def get_queries(name: str) -> list:
    p = _find_project_path(name)
    if not p:
        return []
    out = []
    for q in (_load(p).get("queries") or []):
        if isinstance(q, dict) and q.get("name"):
            out.append({
                "name": q.get("name", ""),
                "device": q.get("device", ""),
                "source": q.get("source", "state"),
                "xpath": q.get("xpath", ""),
            })
    return out


def save_query(project: str, query: dict) -> None:
    """Upsert a query (by name) into a project, creating the project if needed."""
    if not (query or {}).get("name"):
        raise ValueError("query.name is required")
    p = _find_project_path(project)
    d = _load(p) if p else {"name": project, "queries": []}
    d.setdefault("name", project)
    d.setdefault("queries", [])
    rec = {
        "name": query.get("name", ""),
        "device": query.get("device", ""),
        "source": query.get("source", "state"),
        "xpath": query.get("xpath", ""),
    }
    for i, q in enumerate(d["queries"]):
        if isinstance(q, dict) and q.get("name") == rec["name"]:
            d["queries"][i] = rec
            break
    else:
        d["queries"].append(rec)
    _atomic_write_json(p or (XPATH_DIR / f"{_safe(project)}.json"), d)


def delete_query(project: str, name: str) -> None:
    p = _find_project_path(project)
    if not p:
        return
    d = _load(p)
    d["queries"] = [q for q in (d.get("queries") or [])
                    if not (isinstance(q, dict) and q.get("name") == name)]
    _atomic_write_json(p, d)


def export_project(name: str) -> dict:
    p = _find_project_path(name)
    if not p:
        raise ValueError(f"unknown project {name!r}")
    return _load(p)


def import_project(obj: dict, name: str = None) -> str:
    if not isinstance(obj, dict) or "queries" not in obj:
        raise ValueError("not an XPath project (missing 'queries')")
    nm = (name or obj.get("name") or "Imported").strip()
    obj["name"] = nm
    _atomic_write_json(XPATH_DIR / f"{_safe(nm)}.json", obj)
    return nm
