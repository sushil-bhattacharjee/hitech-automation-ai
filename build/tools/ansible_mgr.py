"""
v1.50.0: Ansible — projects, files, roles, runs, CLI, and the separate .vansible venv.

Layout
------
  <software_ai>/.vansible/                 Ansible's own venv (NOT the app venv)
  ~/.hitech_automation_ai/ansible/
      projects/<project>/...               playbooks, roles, inventories, vars, templates, keys
      collections/ansible_collections/...  cisco.ios / cisco.nxos / cisco.aci / netcommon / utils
      runs/                                transient extra-vars / generated inventories (0600, deleted)

Design rules
------------
* Everything runs as argv (no shell). The CLI accepts only ansible* commands;
  shell operators are refused so intent is explicit. NOTE: Ansible itself can
  execute commands on localhost (shell/command modules) — this is a lab tool
  running as your user, not a sandbox.
* Runs execute with cwd = project dir, so relative paths in playbooks
  (admin.key, config.yml, templates) resolve exactly like at the terminal.
* Long jobs (runs, setup) are background threads; the UI polls output lines.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

import yaml

from .state_dir import STATE_DIR

try:                                  # public site: Ansible runs on the separate runner
    import remote_exec as _remote
    REMOTE = _remote.ENABLED
except Exception:                     # pragma: no cover
    _remote, REMOTE = None, False

ANS_DIR = STATE_DIR / "ansible"
PROJECTS = ANS_DIR / "projects"
COLL_DIR = ANS_DIR / "collections"
RUNS_DIR = ANS_DIR / "runs"

_BUILD_DIR = Path(__file__).resolve().parent.parent          # .../software_ai/build
VENV = Path(os.environ.get("HITECH_VANSIBLE", str(_BUILD_DIR.parent / ".vansible")))
VBIN = VENV / "bin"
REQ_FILE = _BUILD_DIR / "requirements-ansible.txt"
COLL_REQ = _BUILD_DIR / "ansible-collections.yml"

CLI_ALLOWED = ("ansible", "ansible-playbook", "ansible-galaxy", "ansible-inventory",
               "ansible-doc", "ansible-vault", "ansible-config", "ansible-lint")
_SHELL_TOKENS = {"|", "||", "&&", ";", "&", ">", ">>", "<", "<<", "`"}

_PROJ_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SEG_RE = re.compile(r"^[A-Za-z0-9_.+@-][A-Za-z0-9_.+@ -]{0,127}$")
MAX_EDIT = 2 * 1024 * 1024
JOB_TIMEOUT = 30 * 60


class AnsError(ValueError):
    """User-facing error."""


# ------------------------------------------------------------------ paths

def _ensure() -> None:
    for d in (PROJECTS, COLL_DIR, RUNS_DIR):
        d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(RUNS_DIR, 0o700)
    except Exception:
        pass


def project_dir(name: str) -> Path:
    if not _PROJ_RE.match(name or ""):
        raise AnsError(f"Invalid project name {name!r} (letters, digits, . _ - ; max 64)")
    return PROJECTS / name


def _existing_project(name: str) -> Path:
    p = project_dir(name)
    if not p.is_dir():
        raise AnsError(f"Project {name!r} not found")
    return p


def safe_path(project: str, rel: str) -> Path:
    """Resolve a project-relative path; refuse anything escaping the project."""
    base = _existing_project(project)
    rel = (rel or "").strip().strip("/")
    if not rel:
        raise AnsError("Path is required")
    parts = rel.split("/")
    for seg in parts:
        if seg in ("", ".", "..") or not _SEG_RE.match(seg):
            raise AnsError(f"Invalid path segment {seg!r} in {rel!r}")
    p = (base / rel).resolve()
    if base.resolve() not in p.parents and p != base.resolve():
        raise AnsError("Path escapes the project")
    return p


# ------------------------------------------------------------------ environment for every ansible call

def run_env(extra: Optional[dict] = None, project: Optional[Path] = None) -> dict:
    env = dict(os.environ)
    env.update({
        "PATH": f"{VBIN}:{env.get('PATH', '')}",
        "VIRTUAL_ENV": str(VENV),
        "PYTHONUNBUFFERED": "1",
        "ANSIBLE_FORCE_COLOR": "0",
        "ANSIBLE_NOCOLOR": "1",
        "ANSIBLE_HOST_KEY_CHECKING": "False",
        "ANSIBLE_RETRY_FILES_ENABLED": "False",
        # app collections first, then the user's own ~/.ansible/collections
        "ANSIBLE_COLLECTIONS_PATH": f"{COLL_DIR}:{Path.home() / '.ansible' / 'collections'}",
    })
    env.pop("PYTHONPATH", None)            # never leak the app venv's paths into Ansible
    if project is not None:
        env["ANSIBLE_ROLES_PATH"] = f"{project}:{project / 'roles'}"
    for k, v in (extra or {}).items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k or ""):
            raise AnsError(f"Invalid environment variable name {k!r}")
        env[k] = "" if v is None else str(v)
    return env


_RUN_KEYS = {"PATH", "VIRTUAL_ENV", "PYTHONUNBUFFERED", "ANSIBLE_FORCE_COLOR", "ANSIBLE_NOCOLOR",
             "ANSIBLE_HOST_KEY_CHECKING", "ANSIBLE_RETRY_FILES_ENABLED",
             "ANSIBLE_COLLECTIONS_PATH", "ANSIBLE_ROLES_PATH"}


def _user_env(env: dict) -> dict:
    """The variables the user added — not this process's own environment."""
    return {k: v for k, v in (env or {}).items()
            if k not in _RUN_KEYS and os.environ.get(k) != v}


def run_capture(argv: list[str], cwd: Path, env: dict, root: Path, timeout: int = 60,
                return_tree: bool = False) -> subprocess.CompletedProcess:
    """subprocess.run(capture_output) here, or on the runner (public site). With
    return_tree, files the command made under root (e.g. a new role) come back."""
    if not REMOTE:
        return subprocess.run(argv, cwd=str(cwd), env=env, capture_output=True, text=True, timeout=timeout)
    try:
        r = _remote.call(os.path.basename(argv[0]), argv[1:], _user_env(env), tree_dir=root,
                         timeout=timeout, return_tree=return_tree, cwd=cwd)
    except Exception as e:
        raise AnsError(f"runner: {e}")
    if r.get("tree"):
        _remote.extract_tree(r["tree"], root)
    rc = r.get("rc")
    return subprocess.CompletedProcess(argv, 124 if rc is None else rc,
                                       r.get("stdout", ""), r.get("stderr", "") or ("timeout" if rc is None else ""))


def _bin(name: str) -> str:
    if REMOTE:
        return name                   # resolved on the runner
    p = VBIN / name
    if not p.exists():
        raise AnsError(f"{name} not found in {VENV} — click ⚙ Install / repair first")
    return str(p)


# ------------------------------------------------------------------ status

def status() -> dict:
    if REMOTE:
        try:
            out = _remote.status()
        except Exception as e:
            out = {"ok": True, "installed": False, "error": f"runner: {e}"}
        out.update({"venv": "runner (public site)", "remote": True,
                    "collections_dir": "runner (public site)", "projects_dir": str(PROJECTS)})
        return out
    out = {"ok": True, "venv": str(VENV), "installed": (VBIN / "ansible-playbook").exists(),
           "collections_dir": str(COLL_DIR), "projects_dir": str(PROJECTS)}
    if not out["installed"]:
        return out
    try:
        v = subprocess.run([_bin("ansible"), "--version"], capture_output=True, text=True,
                           env=run_env(), timeout=40)
        m = re.search(r"core ([\d.]+)", v.stdout)
        py = re.search(r"python version = ([\d.]+)", v.stdout)
        out["ansible"] = m.group(1) if m else "?"
        out["python"] = py.group(1) if py else "?"
    except Exception as e:
        out["ansible_error"] = str(e)
    try:
        c = subprocess.run([_bin("ansible-galaxy"), "collection", "list", "--format", "json"],
                           capture_output=True, text=True, env=run_env(), timeout=60)
        cols = {}
        for path, items in (json.loads(c.stdout or "{}") or {}).items():
            if "_internal" in path:
                continue
            for name, meta in items.items():
                cols.setdefault(name, {"version": meta.get("version"), "path": path})
        out["collections"] = cols
    except Exception as e:
        out["collections"] = {}
        out["collections_error"] = str(e)
    return out


def _pick_python() -> str:
    for c in ("/usr/bin/python3.13", "/usr/bin/python3.12", "/usr/bin/python3.11"):
        if Path(c).exists():
            return c
    raise AnsError("No system Python 3.11–3.13 in /usr/bin (ansible-core 2.19 needs one)")


def setup_steps() -> list[list[str]]:
    """The exact commands 'Install / repair' runs, in order."""
    if REMOTE:
        raise AnsError("Ansible and its collections are already installed on the public site")
    py = os.environ.get("HITECH_VANSIBLE_PYTHON") or _pick_python()
    steps = []
    if not (VBIN / "python").exists():
        steps.append([py, "-m", "venv", str(VENV)])
    steps.append([str(VBIN / "python"), "-m", "pip", "install", "--upgrade", "pip"])
    steps.append([str(VBIN / "python"), "-m", "pip", "install", "-r", str(REQ_FILE)])
    steps.append([str(VBIN / "ansible-galaxy"), "collection", "install", "--upgrade",
                  "-r", str(COLL_REQ), "-p", str(COLL_DIR)])
    return steps


# ------------------------------------------------------------------ projects & files

def list_projects() -> list[str]:
    _ensure()
    return sorted(p.name for p in PROJECTS.iterdir() if p.is_dir())


def create_project(name: str) -> None:
    _ensure()
    p = project_dir(name)
    if p.exists():
        raise AnsError(f"Project {name!r} already exists")
    p.mkdir(parents=True)
    (p / "site.yml").write_text(
        "- name: First play\n  hosts: all\n  gather_facts: false\n  tasks:\n"
        "    - name: Hello\n      debug:\n        msg: \"hello from {{ inventory_hostname }}\"\n"
        "      tags: debug\n")
    (p / "inventory.yml").write_text("all:\n  hosts:\n    localhost:\n      ansible_connection: local\n")


def delete_project(name: str) -> None:
    shutil.rmtree(_existing_project(name))


def _is_role_dir(d: Path) -> bool:
    return any((d / s / "main.yml").exists() or (d / s / "main.yaml").exists()
               for s in ("tasks", "meta", "defaults", "handlers"))


def tree(project: str) -> dict:
    base = _existing_project(project)
    files, dirs, roles = [], [], []
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base).as_posix()
        if any(seg.startswith(".") for seg in rel.split("/")) and not rel.endswith(".keep"):
            continue
        if p.is_dir():
            dirs.append(rel)
            parent = p.parent.relative_to(base).as_posix()
            if parent in (".", "roles") and _is_role_dir(p):
                roles.append(rel)
        else:
            files.append({"path": rel, "size": p.stat().st_size})
    return {"ok": True, "project": project, "files": files, "dirs": dirs, "roles": roles}


def read_file(project: str, rel: str) -> dict:
    p = safe_path(project, rel)
    if not p.is_file():
        raise AnsError(f"{rel} not found")
    if p.stat().st_size > MAX_EDIT:
        raise AnsError(f"{rel} is larger than 2 MB — not opened in the editor")
    raw = p.read_bytes()
    if b"\x00" in raw[:4096]:
        return {"ok": True, "path": rel, "binary": True, "content": ""}
    return {"ok": True, "path": rel, "binary": False, "content": raw.decode("utf-8", "replace")}


def write_file(project: str, rel: str, content: str, create_only: bool = False) -> None:
    p = safe_path(project, rel)
    if create_only and p.exists():
        raise AnsError(f"{rel} already exists")
    if p.is_dir():
        raise AnsError(f"{rel} is a folder")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    if p.suffix in (".key", ".pem"):
        os.chmod(p, 0o600)


def write_bytes(project: str, rel: str, data: bytes) -> None:
    p = safe_path(project, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    if p.suffix in (".key", ".pem"):
        os.chmod(p, 0o600)


def make_dir(project: str, rel: str) -> None:
    safe_path(project, rel).mkdir(parents=True, exist_ok=True)


def delete_path(project: str, rel: str) -> None:
    p = safe_path(project, rel)
    if p.is_dir():
        shutil.rmtree(p)
    elif p.exists():
        p.unlink()
    else:
        raise AnsError(f"{rel} not found")


FILE_TEMPLATES = {
    "playbook": "- name: New play\n  hosts: all\n  gather_facts: false\n  tasks:\n"
                "    - name: Debug\n      debug:\n        msg: \"{{ inventory_hostname }}\"\n      tags: debug\n",
    "inventory-yaml": "all:\n  hosts:\n    cat8Kv71:\n      ansible_host: 192.168.89.71\n",
    "inventory-ini": "[iosxe]\ncat8Kv71 ansible_host=192.168.89.71\n",
    "vars": "---\n",
    "jinja2": "{# Jinja2 template #}\n",
    "empty": "",
}


# ------------------------------------------------------------------ hiTech-devices inventory

_CONN = {
    "cisco-iosxe": {"ansible_connection": "ansible.netcommon.network_cli", "ansible_network_os": "cisco.ios.ios"},
    "cisco-nxos": {"ansible_connection": "ansible.netcommon.network_cli", "ansible_network_os": "cisco.nxos.nxos"},
    "cisco-apic": {"ansible_connection": "local"},
}
_GROUP = {"cisco-iosxe": "iosxe", "cisco-nxos": "nxos", "cisco-apic": "apic"}


def devices_inventory(devices) -> str:
    """YAML inventory from hiTech's devices.yaml (credentials included — callers write it 0600)."""
    groups: dict = {}
    for d in devices:
        g = _GROUP.get(d.device_type, "other")
        hv = {"ansible_host": d.host, "ansible_user": d.username, "ansible_password": d.password,
              "ansible_port": d.port_ssh}
        hv.update(_CONN.get(d.device_type, {}))
        if d.device_type == "cisco-apic":
            hv.pop("ansible_port", None)
            hv["apic_hostname"] = d.host
        groups.setdefault(g, {"hosts": {}})["hosts"][d.name] = hv
    return yaml.safe_dump({"all": {"children": groups}}, sort_keys=False)


# ------------------------------------------------------------------ jobs (runs, CLI, setup)

class Job:
    def __init__(self, kind: str, label: str):
        self.id = "ans_" + uuid.uuid4().hex[:12]
        self.kind, self.label = kind, label
        self.lines: list[str] = []
        self.done = False
        self.rc: Optional[int] = None
        self.proc: Optional[subprocess.Popen] = None
        self.started = time.time()
        self.cancelled = False
        self.cleanup: list[Path] = []
        self.lock = threading.Lock()

    def add(self, line: str) -> None:
        with self.lock:
            self.lines.append(line.rstrip("\n"))


_JOBS: dict[str, Job] = {}


def _gc_jobs() -> None:
    now = time.time()
    for k in [k for k, j in _JOBS.items() if j.done and now - j.started > 3600]:
        _JOBS.pop(k, None)


def _stream(job: Job, argv_list: list[list[str]], cwd: Path, env: dict) -> None:
    try:
        for argv in argv_list:
            if job.cancelled:
                break
            job.add("$ " + shlex.join(argv))
            if REMOTE:
                job.rc = _stream_remote(job, argv, cwd, env)
                if job.rc != 0:
                    break
                continue
            job.proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, bufsize=1,
                                        start_new_session=True)
            deadline = job.started + JOB_TIMEOUT
            for line in job.proc.stdout:
                job.add(line)
                if time.time() > deadline:
                    job.add(f"✖ timeout after {JOB_TIMEOUT // 60} min — stopping")
                    _kill(job)
                    break
            job.rc = job.proc.wait()
            if job.rc != 0:
                break
    except FileNotFoundError as e:
        job.add(f"✖ {e}")
        job.rc = 127
    except Exception as e:
        job.add(f"✖ {type(e).__name__}: {e}")
        job.rc = 1
    finally:
        for f in job.cleanup:
            try:
                f.unlink()
            except Exception:
                pass
        if job.cancelled:
            job.add("■ stopped by user")
        job.done = True


def _stream_remote(job: Job, argv: list[str], cwd: Path, env: dict) -> int:
    """One command on the runner, output line by line into the job. Files the run
    made or changed in the project (backups, vault edits, new roles) come back."""
    rc = 1
    try:
        for d in _remote.stream(os.path.basename(argv[0]), argv[1:], _user_env(env), tree_dir=cwd,
                                extra=job.cleanup, timeout=JOB_TIMEOUT, return_tree=True):
            if "o" in d:
                job.add(d["o"])
            if "rc" in d:
                rc = 1 if d["rc"] is None else d["rc"]
                if d.get("tree"):
                    _remote.extract_tree(d["tree"], cwd)
            if job.cancelled:          # closing the connection stops it on the runner
                break
    except Exception as e:
        job.add(f"✖ runner: {e}")
    return rc


def _kill(job: Job) -> None:
    if job.proc and job.proc.poll() is None:
        try:
            os.killpg(job.proc.pid, signal.SIGTERM)
            time.sleep(1.5)
            if job.proc.poll() is None:
                os.killpg(job.proc.pid, signal.SIGKILL)
        except Exception:
            pass


def start_job(kind: str, label: str, argv_list: list[list[str]], cwd: Path, env: dict,
              cleanup: Optional[list[Path]] = None) -> Job:
    _gc_jobs()
    job = Job(kind, label)
    job.cleanup = cleanup or []
    _JOBS[job.id] = job
    threading.Thread(target=_stream, args=(job, argv_list, cwd, env), daemon=True).start()
    return job


def job_poll(job_id: str, since: int) -> dict:
    j = _JOBS.get(job_id)
    if not j:
        raise AnsError("unknown job (expired or server restarted)")
    with j.lock:
        lines = j.lines[since:]
        n = len(j.lines)
    return {"ok": True, "lines": lines, "next": n, "done": j.done, "rc": j.rc,
            "elapsed": round(time.time() - j.started, 1)}


def job_cancel(job_id: str) -> None:
    j = _JOBS.get(job_id)
    if not j:
        raise AnsError("unknown job")
    j.cancelled = True
    _kill(j)


# ------------------------------------------------------------------ building runs

def _temp_file(name: str, content: str) -> Path:
    _ensure()
    p = RUNS_DIR / f"{uuid.uuid4().hex[:10]}_{name}"
    p.write_text(content)
    os.chmod(p, 0o600)
    return p


def build_playbook_argv(project: str, req: dict, devices=None) -> tuple[list[str], list[Path], Path]:
    """Form run -> argv. Returns (argv, temp files to delete, cwd)."""
    base = _existing_project(project)
    pb = req.get("playbook") or ""
    safe_path(project, pb)  # validates
    argv = [_bin("ansible-playbook")]
    cleanup: list[Path] = []
    inv = req.get("inventory") or ""
    if inv == "__hitech__":
        if devices is None:
            raise AnsError("hiTech device inventory unavailable")
        t = _temp_file("hitech_inventory.yml", devices_inventory(devices))
        cleanup.append(t)
        argv += ["-i", str(t)]
    elif inv:
        safe_path(project, inv)
        argv += ["-i", inv]
    argv.append(pb)
    tags = [t for t in (req.get("tags") or []) if re.fullmatch(r"[A-Za-z0-9_.:-]+", t)]
    skip = [t for t in (req.get("skip_tags") or []) if re.fullmatch(r"[A-Za-z0-9_.:-]+", t)]
    if tags:
        argv += ["--tags", ",".join(tags)]
    if skip:
        argv += ["--skip-tags", ",".join(skip)]
    if req.get("limit"):
        argv += ["--limit", str(req["limit"])]
    if req.get("check"):
        argv.append("--check")
    if req.get("diff"):
        argv.append("--diff")
    v = req.get("verbosity") or ""
    if v in ("-v", "-vv", "-vvv", "-vvvv"):
        argv.append(v)
    ev = (req.get("extra_vars") or "").strip()
    if ev:
        try:
            parsed = yaml.safe_load(ev)
        except yaml.YAMLError as e:
            raise AnsError(f"Extra vars is not valid YAML: {e}")
        if parsed is not None and not isinstance(parsed, dict):
            raise AnsError("Extra vars must be a YAML mapping (key: value)")
        t = _temp_file("extra_vars.yml", ev + "\n")
        cleanup.append(t)
        argv += ["-e", "@" + str(t)]
    mode = req.get("mode") or "run"
    if mode == "syntax":
        argv.append("--syntax-check")
    elif mode == "tasks":
        argv.append("--list-tasks")
    elif mode == "hosts":
        argv.append("--list-hosts")
    elif mode == "tags":
        argv.append("--list-tags")
    return argv, cleanup, base


def parse_cli(project: str, line: str) -> tuple[list[str], Path]:
    base = _existing_project(project)
    line = (line or "").strip()
    if not line:
        raise AnsError("empty command")
    if re.search(r"[|;&`<>]|\$\(", line):
        raise AnsError("shell operators are not allowed (| ; && ` $( ) < >) — commands run directly, not through bash")
    try:
        argv = shlex.split(line)
    except ValueError as e:
        raise AnsError(f"cannot parse command: {e}")
    if argv[0] not in CLI_ALLOWED:
        raise AnsError(f"'{argv[0]}' is not allowed here — only: {', '.join(CLI_ALLOWED)}")
    if any(t in _SHELL_TOKENS for t in argv):
        raise AnsError("shell operators are not allowed")
    argv[0] = _bin(argv[0])
    return argv, base


def list_tags(project: str, playbook: str, inventory: str, devices=None) -> list[str]:
    argv, cleanup, base = build_playbook_argv(
        project, {"playbook": playbook, "inventory": inventory, "mode": "tags"}, devices)
    try:
        if REMOTE:
            r = _remote.call(os.path.basename(argv[0]), argv[1:], {}, tree_dir=base,
                             extra=cleanup, timeout=90)
            cp = subprocess.CompletedProcess(argv, r.get("rc") or 0, r.get("stdout", ""), r.get("stderr", ""))
        else:
            cp = subprocess.run(argv, cwd=str(base), env=run_env(project=base),
                                capture_output=True, text=True, timeout=90)
    finally:
        for f in cleanup:
            try:
                f.unlink()
            except Exception:
                pass
    tags = set()
    for m in re.finditer(r"(?:TASK TAGS|TAGS): \[([^\]]*)\]", cp.stdout):
        for t in m.group(1).split(","):
            t = t.strip()
            if t:
                tags.add(t)
    if cp.returncode != 0 and not tags:
        err = (cp.stderr or cp.stdout).strip().splitlines()
        raise AnsError("could not read tags: " + (err[-1] if err else f"exit {cp.returncode}"))
    return sorted(tags)
