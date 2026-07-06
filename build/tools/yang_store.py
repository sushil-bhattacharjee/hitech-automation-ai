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
    s = re.sub(r"[^A-Za-z0-9._ -]", "_", (name or "").strip())
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
    meta = _read_meta(name)
    mods = {m["file"]: m for m in meta.get("modules", [])}
    mods[fn] = {"file": fn, "module": modname}
    meta["modules"] = sorted(mods.values(), key=lambda m: m["file"])
    _write_meta(name, meta)
    return {"file": fn, "module": modname}


def repo_dir(repo: str) -> Path:
    return _repo_path(repo)


def module_path(repo: str, filename: str) -> Path:
    return _repo_path(repo) / _safe(filename)


def read_module(repo: str, filename: str) -> str:
    return module_path(repo, filename).read_text(encoding="utf-8")
