"""v1.30.0: YANG file storage (repositories) for the YANG Explorer.

v1 scope: upload-only. A "repository" is a folder of .yang files. Later versions
add Git and NETCONF <get-schema> import, plus named module "sets".

Layout (under ~/.hitech_automation_ai/, survives zip upgrades):
  yang/repos/<repo>/<module>.yang        -> uploaded YANG source files
  yang/repos/<repo>/_meta.json           -> {"name", "created", "modules": [...]}

Mirrors the existing *_store.py conventions (STATE_DIR, atomic writes, safe names).
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from tools.state_dir import STATE_DIR

YANG_DIR = STATE_DIR / "yang"
REPOS_DIR = YANG_DIR / "repos"


def _safe(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._@ -]", "_", (name or "").strip())  # v1.32.0: allow @ for name@revision.yang
    return (s or "untitled")[:120]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def list_repos() -> list[dict]:
    if not REPOS_DIR.exists():
        return []
    out = []
    for d in sorted(REPOS_DIR.iterdir()):
        if d.is_dir():
            meta = _read_meta(d.name)
            out.append({"name": d.name, "modules": meta.get("modules", [])})
    return out


def _repo_path(repo: str) -> Path:
    return REPOS_DIR / _safe(repo)


def _read_meta(repo: str) -> dict:
    p = _repo_path(repo) / "_meta.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"name": repo, "modules": []}


def _write_meta(repo: str, meta: dict) -> None:
    _atomic_write(_repo_path(repo) / "_meta.json", json.dumps(meta, indent=2))


def create_repo(repo: str) -> dict:
    name = _safe(repo)
    p = _repo_path(name)
    p.mkdir(parents=True, exist_ok=True)
    meta = _read_meta(name)
    meta.setdefault("name", name)
    meta.setdefault("created", time.strftime("%Y-%m-%d %H:%M:%S"))
    meta.setdefault("modules", [])
    _write_meta(name, meta)
    return {"name": name, "modules": meta["modules"]}


def delete_repo(repo: str) -> None:
    import shutil
    p = _repo_path(repo)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)


def add_module(repo: str, filename: str, content: str) -> dict:
    """Save an uploaded .yang file into the repo. Returns the module name."""
    name = _safe(repo)
    _repo_path(name).mkdir(parents=True, exist_ok=True)
    fn = _safe(filename)
    if not fn.endswith(".yang"):
        fn += ".yang"
    _atomic_write(_repo_path(name) / fn, content)
    # module name = filename without .yang (before any @revision)
    modname = fn[:-5].split("@")[0]
    # v1.32.0: first revision statement in the source (for "module @ revision" display)
    rev_m = re.search(r'revision\s+"?([0-9]{4}-[0-9]{2}-[0-9]{2})"?', content or "")
    revision = fn[:-5].split("@")[1] if "@" in fn[:-5] else (rev_m.group(1) if rev_m else "")
    meta = _read_meta(name)
    mods = {m["file"]: m for m in meta.get("modules", [])}
    mods[fn] = {"file": fn, "module": modname, "revision": revision}
    meta["modules"] = sorted(mods.values(), key=lambda m: m["file"])
    _write_meta(name, meta)
    return {"file": fn, "module": modname}


def repo_dir(repo: str) -> Path:
    return _repo_path(repo)


def module_path(repo: str, filename: str) -> Path:
    return _repo_path(repo) / _safe(filename)


def read_module(repo: str, filename: str) -> str:
    return module_path(repo, filename).read_text(encoding="utf-8")


def delete_module(repo: str, filename: str) -> bool:
    """v1.32.0: remove a .yang file from the repo (file + meta entry)."""
    p = module_path(repo, filename)
    removed = False
    if p.exists() and p.suffix == ".yang":
        p.unlink()
        removed = True
    meta = _read_meta(_safe(repo))
    mods = [m for m in meta.get("modules", []) if m["file"] != _safe(filename)]
    if len(mods) != len(meta.get("modules", [])):
        removed = True
    meta["modules"] = mods
    _write_meta(_safe(repo), meta)
    return removed


# ------------------------------------------------------------------ #
# v1.33.0: YANG module sets — a named subset of a repository that is  #
# parsed as ONE pyang context (imports + augments resolve across the  #
# whole set, like Cisco YANG Suite's "YANG module sets").             #
# ------------------------------------------------------------------ #

def _sets_path() -> Path:
    return REPOS_DIR.parent / "sets.json"


def _read_sets() -> dict:
    p = _sets_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _write_sets(data: dict):
    REPOS_DIR.parent.mkdir(parents=True, exist_ok=True)
    tmp = _sets_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(_sets_path())


def list_sets() -> list[dict]:
    return [{"name": k, **v} for k, v in sorted(_read_sets().items())]


def save_set(name: str, repo: str, modules: list[str]):
    """Create/replace a set. modules = repo .yang filenames."""
    name = _safe(name)
    if not name:
        raise ValueError("set name required")
    data = _read_sets()
    data[name] = {"repo": _safe(repo), "modules": sorted(set(modules))}
    _write_sets(data)
    return {"name": name, **data[name]}


def delete_set(name: str) -> bool:
    data = _read_sets()
    if _safe(name) in data:
        del data[_safe(name)]
        _write_sets(data)
        return True
    return False


def get_set(name: str) -> dict | None:
    v = _read_sets().get(_safe(name))
    return {"name": _safe(name), **v} if v else None


# ------------------------------------------------------------------ #
# v1.34.0: saved API operations generated from Explore-YANG           #
# kind=restconf: {method, uri, payload, note}                         #
# kind=netconf:  {operation, payload(XML), note}                      #
# ------------------------------------------------------------------ #

def _apis_path() -> Path:
    return REPOS_DIR.parent / "apis.json"


def _read_apis() -> list:
    p = _apis_path()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


def _write_apis(items: list):
    REPOS_DIR.parent.mkdir(parents=True, exist_ok=True)
    tmp = _apis_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(items, indent=1))
    tmp.replace(_apis_path())


def list_apis() -> list:
    return _read_apis()


def add_apis(items: list[dict]) -> list:
    """Append items; each gets an id + created ts. Returns stored items."""
    data = _read_apis()
    nid = (max([i.get("id", 0) for i in data]) + 1) if data else 1
    out = []
    for it in items:
        rec = {"id": nid, "created": int(time.time()), **it}
        data.append(rec)
        out.append(rec)
        nid += 1
    _write_apis(data)
    return out


def update_api(api_id: int, fields: dict) -> bool:
    data = _read_apis()
    for it in data:
        if it.get("id") == api_id:
            it.update({k: v for k, v in fields.items()
                       if k in ("method", "uri", "payload", "note", "operation", "target")})
            _write_apis(data)
            return True
    return False


def delete_apis(ids: list[int]) -> int:
    data = _read_apis()
    keep = [i for i in data if i.get("id") not in set(ids)]
    _write_apis(keep)
    return len(data) - len(keep)
