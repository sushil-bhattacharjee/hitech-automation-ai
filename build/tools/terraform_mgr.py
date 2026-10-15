"""
v1.53.0: Terraform — projects, files, init / plan / apply / destroy, and a CLI.

Versions follow the CCIE Automation v1.1 exam: Terraform 1.13.3 with the
CiscoDevNet/aci provider 2.17.0 (tools/terraform_install.py installs exactly these).

Layout
------
  <software_ai>/.vterraform/                 bin/terraform, mirror/ (aci provider), terraformrc
  ~/.hitech_automation_ai/terraform/projects/<project>/
      main.tf variables.tf outputs.tf terraform.tfvars   (starter: one ACI tenant)
      terraform.tfstate  .terraform.lock.hcl             (written by terraform)

Design rules
------------
* argv only, no shell; the CLI accepts only `terraform <subcommand>`.
* Providers come only from the local mirror (terraformrc) — never downloaded at run time.
* Every action that needs providers runs `terraform init` first. Locally .terraform/ stays
  in the project; on the public site each run is a fresh folder on the runner, whose
  `terraform` wrapper runs init itself, and the state comes back with the project files.
* One job per project at a time (two runs on one state file would corrupt it).
* Public site: TF_VAR_apic_url points at the user's own running APIC.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from .state_dir import STATE_DIR
from . import ansible_mgr as _jobs            # Job machinery + remote streaming
from . import terraform_install as _inst

REMOTE = _jobs.REMOTE
_remote = _jobs._remote

TF_DIR = STATE_DIR / "terraform"
PROJECTS = TF_DIR / "projects"

_BUILD_DIR = Path(__file__).resolve().parent.parent          # .../software_ai/build
VTF = Path(os.environ.get("HITECH_VTERRAFORM", str(_BUILD_DIR.parent / ".vterraform")))
TF_VERSION, ACI_VERSION = _inst.TF_VERSION, _inst.ACI_VERSION
APIC_LAB_IP = "192.168.89.95"

_PROJ_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SEG_RE = re.compile(r"^[A-Za-z0-9_.+@-][A-Za-z0-9_.+@ -]{0,127}$")
MAX_EDIT = 2 * 1024 * 1024
_HIDDEN = {".terraform"}

# action -> (argv after `terraform`, needs init)
ACTIONS = {
    "init":      (["init", "-input=false", "-no-color"], False),
    "fmt":       (["fmt", "-no-color"], False),
    "validate":  (["validate", "-no-color"], True),
    "plan":      (["plan", "-input=false", "-no-color"], True),
    "apply":     (["apply", "-input=false", "-no-color", "-auto-approve"], True),
    "destroy":   (["destroy", "-input=false", "-no-color", "-auto-approve"], True),
    "output":    (["output", "-no-color"], True),
    "show":      (["show", "-no-color"], True),
    "state":     (["state", "list"], True),
    "providers": (["providers", "-no-color"], True),
    "version":   (["version"], False),
}
NO_INIT = {"init", "fmt", "version", "-version", "--version", "-help", "--help", "-h", "help"}
CLI_SUBCOMMANDS = {"init", "validate", "plan", "apply", "destroy", "fmt", "output", "show",
                   "state", "providers", "version", "graph", "import", "refresh",
                   "taint", "untaint", "workspace", "test", "get", "-version", "--version",
                   "-help", "--help", "help"}
_SHELL_TOKENS = {"|", "||", "&&", ";", "&", ">", ">>", "<", "<<", "`"}
_NO_COLOR = {"init", "validate", "plan", "apply", "destroy", "refresh", "import", "show",
             "output", "providers", "fmt", "test"}


class TfError(ValueError):
    """User-facing error."""


# ------------------------------------------------------------------ paths

def _ensure() -> None:
    PROJECTS.mkdir(parents=True, exist_ok=True)


def project_dir(name: str) -> Path:
    if not _PROJ_RE.match(name or ""):
        raise TfError(f"Invalid project name {name!r} (letters, digits, . _ - ; max 64)")
    return PROJECTS / name


def existing_project(name: str) -> Path:
    p = project_dir(name)
    if not p.is_dir():
        raise TfError(f"Project {name!r} not found")
    return p


def safe_path(project: str, rel: str) -> Path:
    base = existing_project(project)
    rel = (rel or "").strip().strip("/")
    if not rel:
        raise TfError("Path is required")
    for seg in rel.split("/"):
        if seg in ("", ".", "..") or not _SEG_RE.match(seg):
            raise TfError(f"Invalid path segment {seg!r} in {rel!r}")
        if seg in _HIDDEN:
            raise TfError(".terraform is managed by terraform init")
    p = (base / rel).resolve()
    if base.resolve() not in p.parents:
        raise TfError("Path escapes the project")
    return p


# ------------------------------------------------------------------ binary & environment

def _local_bin() -> Optional[str]:
    for n in ("terraform", "terraform.exe"):
        p = VTF / "bin" / n
        if p.exists():
            return str(p)
    return shutil.which("terraform")


def _bin() -> str:
    if REMOTE:
        return "terraform"            # the runner's wrapper (init first, then the command)
    b = _local_bin()
    if not b:
        raise TfError("terraform not found — click ⚙ Install / repair first")
    return b


def lab_apic() -> Optional[str]:
    """Public site: the address of the user's running APIC (written by the gateway)."""
    try:
        ip = json.loads((STATE_DIR / ".lab-devices.json").read_text()).get("apic")
        return ip if ip and re.fullmatch(r"[0-9.]{7,15}", ip) else None
    except Exception:
        return None


_BAD_USER = ("TF_CLI_CONFIG_FILE", "TF_PLUGIN", "TF_DATA_DIR", "TF_CLI_ARGS", "TF_LOG_PATH",
             "TF_REATTACH_PROVIDERS", "TF_SKIP_PROVIDER", "TF_WORKSPACE")


def run_env(extra: Optional[dict] = None) -> dict:
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("TF_"):
            env.pop(k)                # nothing from this process's own environment
    env.update({"TF_IN_AUTOMATION": "1", "CHECKPOINT_DISABLE": "1", "TF_INPUT": "0"})
    rc = VTF / "terraformrc"
    if not REMOTE and rc.exists():
        env["TF_CLI_CONFIG_FILE"] = str(rc)
    if REMOTE:
        ip = lab_apic()
        if ip:
            env["TF_VAR_apic_url"] = f"https://{ip}"
    for k, v in (extra or {}).items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k or ""):
            raise TfError(f"Invalid environment variable name {k!r}")
        if k.upper().startswith(_BAD_USER):
            raise TfError(f"{k} is set by the app")
        env[k] = "" if v is None else str(v)
    return env


# ------------------------------------------------------------------ status & install

def status() -> dict:
    base = {"ok": True, "projects_dir": str(PROJECTS), "remote": REMOTE,
            "expected": {"terraform": TF_VERSION, "aci": ACI_VERSION}}
    if REMOTE:
        try:
            st = _remote.status()
            base.update({"installed": bool(st.get("terraform")), "terraform": st.get("terraform"),
                         "providers": st.get("terraform_providers") or {}, "where": "runner (public site)"})
        except Exception as e:
            base.update({"installed": False, "error": f"runner: {e}"})
        ip = lab_apic()
        base["apic"] = f"https://{ip}" if ip else None
        return base
    b = _local_bin()
    base.update({"installed": bool(b), "where": b or str(VTF),
                 "bundled": bool(b) and Path(b).parent == VTF / "bin",
                 "mirror": (VTF / "terraformrc").exists()})
    if not b:
        return base
    try:
        cp = subprocess.run([b, "version", "-json"], capture_output=True, text=True,
                            env=run_env(), timeout=30)
        m = re.search(r'"terraform_version":\s*"([^"]+)"', cp.stdout or "")
        base["terraform"] = m.group(1) if m else "?"
    except Exception as e:
        base["error"] = str(e)
    prov = {}
    mdir = VTF / "mirror" / "registry.terraform.io"
    if mdir.is_dir():
        for v in mdir.glob("*/*/*"):
            prov[f"{v.parent.parent.name}/{v.parent.name}"] = v.name
    base["providers"] = prov
    return base


def setup_steps() -> list[list[str]]:
    if REMOTE:
        raise TfError("Terraform is already installed on the public site")
    return [[sys.executable, str(Path(_inst.__file__).resolve()), str(VTF)]]


# ------------------------------------------------------------------ projects & files

STARTER = {
    "main.tf": f'''terraform {{
  required_version = "~> 1.13.0"
  required_providers {{
    aci = {{
      source  = "CiscoDevNet/aci"
      version = "{ACI_VERSION}"
    }}
  }}
}}

provider "aci" {{
  username = var.apic_username
  password = var.apic_password
  url      = var.apic_url
  insecure = true
}}

resource "aci_tenant" "demo" {{
  name        = var.tenant_name
  description = "created by Terraform"
}}

resource "aci_vrf" "demo" {{
  tenant_dn = aci_tenant.demo.id
  name      = "${{var.tenant_name}}-vrf"
}}
''',
    "variables.tf": f'''variable "apic_url" {{
  description = "APIC address (on the public site it is set to your running APIC)"
  type        = string
  default     = "https://{APIC_LAB_IP}"
}}

variable "apic_username" {{
  type    = string
  default = "admin"
}}

variable "apic_password" {{
  type      = string
  sensitive = true
}}

variable "tenant_name" {{
  type    = string
  default = "tf-demo"
}}
''',
    "outputs.tf": '''output "tenant_dn" {
  value = aci_tenant.demo.id
}

output "vrf_dn" {
  value = aci_vrf.demo.id
}
''',
    "terraform.tfvars": 'apic_username = "admin"\napic_password = "1234QWer!"\n',
}

FILE_TEMPLATES = {
    "tf": "",
    "tenant": 'resource "aci_tenant" "example" {\n  name = "example"\n}\n',
    "variable": 'variable "example" {\n  type    = string\n  default = ""\n}\n',
    "output": 'output "example" {\n  value = ""\n}\n',
    "tfvars": "",
    "empty": "",
}


def list_projects() -> list[str]:
    _ensure()
    return sorted(p.name for p in PROJECTS.iterdir() if p.is_dir())


def create_project(name: str, starter: bool = True) -> None:
    _ensure()
    p = project_dir(name)
    if p.exists():
        raise TfError(f"Project {name!r} already exists")
    p.mkdir(parents=True)
    if starter:
        for f, body in STARTER.items():
            (p / f).write_text(body)
        os.chmod(p / "terraform.tfvars", 0o600)


def delete_project(name: str) -> None:
    p = existing_project(name)
    with _LOCK:
        if busy(name):
            raise TfError("a run is going in this project — stop it first")
        shutil.rmtree(p)


def tree(project: str) -> dict:
    base = existing_project(project)
    files, dirs = [], []
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base).as_posix()
        if any(seg in _HIDDEN for seg in rel.split("/")):
            continue
        if p.is_dir():
            dirs.append(rel)
        else:
            files.append({"path": rel, "size": p.stat().st_size})
    has_state = (base / "terraform.tfstate").exists()
    return {"ok": True, "project": project, "files": files, "dirs": dirs,
            "state": has_state, "busy": busy(project)}


def read_file(project: str, rel: str) -> dict:
    p = safe_path(project, rel)
    if not p.is_file():
        raise TfError(f"{rel} not found")
    if p.stat().st_size > MAX_EDIT:
        raise TfError(f"{rel} is larger than 2 MB — not opened in the editor")
    raw = p.read_bytes()
    if b"\x00" in raw[:4096]:
        return {"ok": True, "path": rel, "binary": True, "content": ""}
    return {"ok": True, "path": rel, "binary": False, "content": raw.decode("utf-8", "replace")}


def _check_writable(project: str, rel: str) -> None:
    name = rel.strip("/").split("/")[-1]
    if name.startswith("terraform.tfstate") and busy(project):
        raise TfError("a run is going in this project — the state file is in use")


def write_file(project: str, rel: str, content: str, create_only: bool = False) -> None:
    p = safe_path(project, rel)
    _check_writable(project, rel)
    if create_only and p.exists():
        raise TfError(f"{rel} already exists")
    if p.is_dir():
        raise TfError(f"{rel} is a folder")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    if p.name.endswith((".tfvars", ".tfstate", ".key", ".pem")):
        os.chmod(p, 0o600)


def write_bytes(project: str, rel: str, data: bytes) -> None:
    p = safe_path(project, rel)
    _check_writable(project, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    if p.name.endswith((".tfvars", ".tfstate", ".key", ".pem")):
        os.chmod(p, 0o600)


def make_dir(project: str, rel: str) -> None:
    safe_path(project, rel).mkdir(parents=True, exist_ok=True)


def delete_path(project: str, rel: str) -> None:
    p = safe_path(project, rel)
    _check_writable(project, rel)
    if p.is_dir():
        shutil.rmtree(p)
    elif p.exists():
        p.unlink()
    else:
        raise TfError(f"{rel} not found")


# ------------------------------------------------------------------ runs

_RUNNING: dict[str, str] = {}          # project -> job id
_VALIDATING: dict[str, threading.Lock] = {}   # project -> lock held while the editor's validate runs
_VAL_LAST: dict[str, float] = {}       # project -> time of the last validate (throttle)
VALIDATE_MIN_GAP = 3.0
_SUB: dict[str, str] = {}              # job id -> terraform subcommand
_LOCK = threading.Lock()
STOP_GRACE = 30                        # s after Ctrl-C before a kill (terraform saves its state)
_CHANGES = {"apply", "destroy", "import", "refresh", "state", "taint", "untaint"}


def busy(project: str) -> bool:
    jid = _RUNNING.get(project)
    if not jid:
        return False
    j = _jobs._JOBS.get(jid)
    return bool(j and not j.done)


def _argv_list(argv: list[str]) -> list[list[str]]:
    """Locally: `terraform init` first when the command needs providers.
    Public site: the runner's terraform wrapper does that in the same fresh folder."""
    if REMOTE or (argv[1] if len(argv) > 1 else "") in NO_INIT:
        return [argv]
    return [[argv[0]] + ACTIONS["init"][0], argv]


def _start(project: str, kind: str, label: str, argv: list[str], env: dict):
    base = existing_project(project)
    st = base / "terraform.tfstate"
    if REMOTE and st.exists() and st.stat().st_size > _remote.MAX_FILE:
        raise TfError("terraform.tfstate is larger than 5 MB — too large to run on the public site")
    vl = _VALIDATING.get(project)              # an editor validate may be doing init in .terraform
    if vl and vl.acquire(timeout=90):
        vl.release()
    with _LOCK:
        if busy(project):
            raise TfError("a run is already going in this project — wait for it or stop it")
        # a lock left by an interrupted run must not block the next one (deleted when the job ends)
        job = _jobs.start_job(kind, label, _argv_list(argv), base, env,
                              cleanup=[base / ".terraform.tfstate.lock.info"])
        _RUNNING[project] = job.id
        _SUB[job.id] = argv[1] if len(argv) > 1 else ""
    return job


def cancel(job_id: str) -> None:
    """Ctrl-C first, so terraform finishes in-flight calls and writes its state."""
    j = _jobs._JOBS.get(job_id)
    if not j:
        raise TfError("unknown job")
    if j.done:
        return
    if REMOTE and _SUB.get(job_id) in _CHANGES:
        raise TfError("apply / destroy cannot be stopped safely on the public site (the state would be lost) — "
                      "it ends on its own; run plan afterwards")
    j.cancelled = True
    if REMOTE or not j.proc:
        return                          # remote: closing the stream stops it (read-only commands only)

    def stop(proc=j.proc):
        try:
            os.killpg(proc.pid, signal.SIGINT)
            proc.wait(STOP_GRACE)
        except subprocess.TimeoutExpired:
            _jobs._kill(j)
        except Exception:
            pass
    threading.Thread(target=stop, daemon=True).start()


def action_argv(action: str, opts: Optional[dict] = None) -> list[str]:
    if action not in ACTIONS:
        raise TfError(f"unknown action {action!r}")
    opts = opts or {}
    argv = [_bin()] + list(ACTIONS[action][0])
    if action in ("plan", "apply", "destroy"):
        for t in opts.get("targets") or []:
            if not re.fullmatch(r"[A-Za-z0-9_.\[\]\"-]{1,200}", str(t)):
                raise TfError(f"invalid -target {t!r}")
            argv.append(f"-target={t}")
        vf = opts.get("var_file") or ""
        if vf:
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}\.tfvars(\.json)?", vf) or ".." in vf:
                raise TfError(f"invalid var file {vf!r}")
            argv.append(f"-var-file={vf}")
    if action == "fmt" and opts.get("recursive"):
        argv.append("-recursive")
    if action == "output" and opts.get("as_json"):
        argv.append("-json")
    return argv


def run_action(project: str, action: str, opts: Optional[dict] = None, env: Optional[dict] = None):
    argv = action_argv(action, opts)
    return _start(project, "run", action, argv, run_env(env))


def parse_cli(line: str) -> list[str]:
    line = (line or "").strip()
    if not line:
        raise TfError("empty command")
    if re.search(r"[|;&`<>]|\$\(", line):
        raise TfError("shell operators are not allowed (| ; && ` $( ) < >) — commands run directly, not through bash")
    try:
        argv = shlex.split(line)
    except ValueError as e:
        raise TfError(f"cannot parse command: {e}")
    if argv[0] != "terraform":
        raise TfError("only terraform commands are allowed here")
    if any(t in _SHELL_TOKENS for t in argv):
        raise TfError("shell operators are not allowed")
    if len(argv) > 1 and argv[1] == "console":
        raise TfError("terraform console is interactive — not available here")
    if len(argv) < 2 or argv[1] not in CLI_SUBCOMMANDS:
        raise TfError("allowed: terraform " + " | ".join(sorted(s for s in CLI_SUBCOMMANDS if not s.startswith("-"))))
    for i, a in enumerate(argv[1:], 1):
        if not a.startswith("-"):
            continue
        key, _, val = a.lstrip("-").partition("=")
        if key.startswith(("chdir", "plugin-dir", "state", "backup")):
            raise TfError("-chdir / -plugin-dir / -state / -backup options are not allowed here")
        if key in ("out", "var-file", "json-into", "generate-config-out"):
            if not val and i + 1 < len(argv):
                val = argv[i + 1]
            if val.startswith(("/", "~")) or ".." in val.split("/"):
                raise TfError(f"-{key} must be a path inside the project")
    if REMOTE and argv[1] == "workspace" and len(argv) > 2 and argv[2] in ("new", "select", "delete"):
        raise TfError("workspaces are not kept between runs on the public site — use the default workspace "
                      "(or separate projects)")
    if argv[1] in ("apply", "destroy") and "-auto-approve" not in argv:
        argv.append("-auto-approve")      # nothing to type "yes" into
    if argv[1] in ("plan", "apply", "destroy", "import", "refresh", "init") and \
            not any(a.startswith("-input") for a in argv):
        argv.insert(2, "-input=false")
    if argv[1] in _NO_COLOR and "-no-color" not in argv:
        argv.insert(2, "-no-color")       # plain text in the page (no ANSI colour codes)
    argv[0] = _bin()
    return argv


def _validate_json(text: str) -> Optional[dict]:
    """The -json document in the output (init / wrapper lines may come first)."""
    m = re.search(r'\{\s*"format_version"', text or "")
    if not m:
        return None
    try:
        return json.loads(text[m.start():])
    except ValueError:
        try:
            return json.JSONDecoder().raw_decode(text[m.start():])[0]
        except ValueError:
            return None


def validate(project: str, env: Optional[dict] = None) -> dict:
    """v1.54.0: `terraform validate -json` for the editor — diagnostics per file and line.
    Runs init first (locally only when .terraform is missing; the runner's wrapper always does)."""
    base = existing_project(project)
    if busy(project):
        return {"ok": True, "skipped": "a run is going in this project", "diagnostics": []}
    if not any(base.glob("*.tf")):
        return {"ok": True, "valid": True, "diagnostics": []}
    import time as _t
    with _LOCK:
        lock = _VALIDATING.setdefault(project, threading.Lock())
        if _t.monotonic() - _VAL_LAST.get(project, 0) < VALIDATE_MIN_GAP or not lock.acquire(blocking=False):
            return {"ok": True, "skipped": "checked a moment ago — save again in a few seconds", "diagnostics": []}
        _VAL_LAST[project] = _t.monotonic()
    try:
        return _validate(base, env)
    finally:
        lock.release()


def _validate(base: Path, env: Optional[dict]) -> dict:
    e = run_env(env)
    argv = [_bin(), "validate", "-json", "-no-color"]
    if REMOTE:
        try:
            r = _remote.call("terraform", argv[1:], {k: v for k, v in e.items() if os.environ.get(k) != v},
                             tree_dir=base, timeout=120)
        except Exception as ex:
            raise TfError(f"runner: {ex}")
        out, err = r.get("stdout", ""), r.get("stderr", "")
    else:
        if not (base / ".terraform").is_dir():
            init = subprocess.run([argv[0]] + ACTIONS["init"][0], cwd=str(base), env=e,
                                  capture_output=True, text=True, timeout=120)
            if init.returncode != 0:
                msg = (init.stderr or init.stdout).strip().splitlines()
                return {"ok": True, "valid": False, "init_failed": True, "diagnostics": [
                    {"severity": "error", "summary": "terraform init failed", "detail": "\n".join(msg[-6:]),
                     "file": "", "line": 1, "column": 1}]}
        cp = subprocess.run(argv, cwd=str(base), env=e, capture_output=True, text=True, timeout=120)
        out, err = cp.stdout, cp.stderr
    doc = _validate_json(out)
    if doc is None:
        tail = (err or out).strip().splitlines()
        return {"ok": True, "valid": False, "diagnostics": [
            {"severity": "error", "summary": "terraform validate did not run", "detail": "\n".join(tail[-6:]),
             "file": "", "line": 1, "column": 1}]}
    diags = []
    for d in doc.get("diagnostics") or []:
        rng = d.get("range") or {}
        start, end = rng.get("start") or {}, rng.get("end") or {}
        diags.append({"severity": d.get("severity", "error"), "summary": d.get("summary", ""),
                      "detail": d.get("detail", ""), "file": rng.get("filename", ""),
                      "line": start.get("line", 1), "column": start.get("column", 1),
                      "end_line": end.get("line"), "end_column": end.get("column")})
    return {"ok": True, "valid": bool(doc.get("valid")), "diagnostics": diags}


def run_cli(project: str, line: str, env: Optional[dict] = None):
    argv = parse_cli(line)
    return _start(project, "cli", line[:80], argv, run_env(env))


def run_setup():
    _ensure()
    return _jobs.start_job("setup", "install / repair", setup_steps(), TF_DIR, run_env())
