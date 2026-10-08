"""
Public site (software-automation.hitech007.ai): run Python and Ansible on the
separate runner service instead of on this server.

A worker has RUNNER_UDS (a unix socket to the gateway) and RUNNER_TOKEN (its own
per-worker token) in its environment only on the public site; the gateway checks
the token, adds the runner's secret and forwards. Everywhere else ENABLED is
False and the app runs things locally, exactly as before.

What goes to the runner for one job: the job's own folder (a Python run's files,
or an Ansible project), loose files it needs (a generated inventory, extra-vars),
the command, and ONLY the variables the user typed — never this process's
environment, which holds the worker's keys.

    call(tool, args, env, tree_dir=..., extra=[...], stdin=..., timeout=...)  -> dict
    stream(...)                                                              -> iterator of dicts
    status()                                                                 -> dict
    extract_tree(b64, dest)   writes files the job made or changed back into dest
"""
from __future__ import annotations

import base64
import io
import json
import os
import tarfile
from pathlib import Path
from typing import Iterator, Optional

UDS = os.environ.get("RUNNER_UDS", "")
TOKEN = os.environ.get("RUNNER_TOKEN", "")
ENABLED = bool(UDS and TOKEN)

MAX_FILE = 5 * 1024 * 1024        # a single file larger than this is left out
MAX_TREE = 20 * 1024 * 1024       # whole job, compressed
_SKIP_DIRS = {".git", "__pycache__", ".venv", ".vansible", "node_modules"}


class RemoteError(RuntimeError):
    pass


def _tar_dir(d: Optional[Path]) -> str:
    if not d:
        return ""
    d = Path(d)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x not in _SKIP_DIRS and not os.path.islink(os.path.join(root, x))]
            for name in files:
                p = Path(root) / name
                if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_FILE:
                    continue
                tf.add(p, arcname=str(p.relative_to(d)), recursive=False)
    raw = buf.getvalue()
    if len(raw) > MAX_TREE:
        raise RemoteError("these files are too large to run on the public site (20 MB)")
    return base64.b64encode(raw).decode()


def _tar_files(paths) -> tuple[str, dict]:
    """Loose files -> (b64 tar, {original path: '{X}/name'})."""
    mapping: dict[str, str] = {}
    if not paths:
        return "", mapping
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for i, p in enumerate(paths):
            p = Path(p)
            if not p.is_file():
                continue
            name = f"{i}_{p.name}"
            tf.add(p, arcname=name, recursive=False)
            mapping[str(p)] = "{X}/" + name
    return base64.b64encode(buf.getvalue()).decode(), mapping


def _rewrite(args, tree_dir: Optional[Path], mapping: dict) -> list[str]:
    out = []
    for a in args:
        a = str(a)
        for orig, new in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
            a = a.replace(orig, new)
        if tree_dir:
            a = a.replace(str(Path(tree_dir)), "{W}")
        out.append(a)
    return out


def _payload(tool, args, env, tree_dir, extra, stdin, timeout, stream, return_tree, cwd):
    tree = _tar_dir(tree_dir)
    xtar, mapping = _tar_files(extra or [])
    rel = ""
    if cwd and tree_dir:
        rel = os.path.relpath(str(cwd), str(tree_dir))
        if rel.startswith(".."):
            rel = ""
    return {"tool": tool, "args": _rewrite(args, tree_dir, mapping),
            "env": {str(k): str(v) for k, v in (env or {}).items()},
            "tree": tree, "extra": xtar, "stdin": stdin, "timeout": int(timeout),
            "stream": stream, "return_tree": return_tree, "cwd": rel}


def _client(timeout: float):
    import httpx
    return httpx.Client(transport=httpx.HTTPTransport(uds=UDS), timeout=timeout,
                        headers={"x-api-key": TOKEN})


def _error_text(r) -> str:
    try:
        d = r.json()
        return str(d.get("detail") or d.get("error") or d)
    except Exception:
        return r.text[:300]


def call(tool: str, args, env=None, tree_dir=None, extra=None, stdin=None, timeout: int = 30,
         return_tree: bool = False, cwd=None) -> dict:
    body = _payload(tool, args, env, tree_dir, extra, stdin, timeout, False, return_tree, cwd)
    with _client(timeout + 60) as c:
        r = c.post("http://runner/exec", json=body)
    if r.status_code != 200:
        raise RemoteError(_error_text(r))
    return r.json()


async def acall(tool: str, args, env=None, tree_dir=None, extra=None, stdin=None, timeout: int = 30,
                return_tree: bool = False, cwd=None) -> dict:
    import asyncio
    return await asyncio.to_thread(call, tool, args, env, tree_dir, extra, stdin, timeout, return_tree, cwd)


def stream(tool: str, args, env=None, tree_dir=None, extra=None, stdin=None, timeout: int = 1800,
           return_tree: bool = False, cwd=None) -> Iterator[dict]:
    body = _payload(tool, args, env, tree_dir, extra, stdin, timeout, True, return_tree, cwd)
    with _client(timeout + 60) as c:
        with c.stream("POST", "http://runner/exec", json=body) as r:
            if r.status_code != 200:
                r.read()
                raise RemoteError(_error_text(r))
            for line in r.iter_lines():
                if line.strip():
                    yield json.loads(line)


def status() -> dict:
    with _client(120) as c:
        r = c.get("http://runner/status")
    if r.status_code != 200:
        raise RemoteError(_error_text(r))
    return r.json()


def extract_tree(b64: str, dest: Path) -> int:
    """Write back regular files the job created or changed under dest. Never deletes."""
    if not b64:
        return 0
    dest = Path(dest)
    root = dest.resolve()
    n = 0
    with tarfile.open(fileobj=io.BytesIO(base64.b64decode(b64)), mode="r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile():
                continue
            target = (dest / m.name).resolve()
            if root not in target.parents:
                continue
            data = tf.extractfile(m).read()
            if target.is_symlink():
                continue
            if target.is_file() and target.read_bytes() == data:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            n += 1
    return n
