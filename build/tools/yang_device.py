"""v1.32.0: YANG Explorer — import modules into a repository from external sources.

Three sources, mirroring Cisco YANG Suite's "Add modules to repository":
  * NETCONF  — list the device's schemas (ietf-netconf-monitoring) and pull
               selected ones with <get-schema>.
  * SCP/SFTP — copy *.yang files from a directory on any SSH host (paramiko).
  * Git      — shallow *sparse* clone of a repo subdirectory (the YangModels
               repo is multi-GB; sparse-checkout pulls just vendor/cisco/xe/<ver>).

All saves go through yang_store.add_module so repo metadata stays consistent.
No new dependencies: ncclient + paramiko ship with the app already (netmiko).
"""
from __future__ import annotations

import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from tools import yang_store

_MONITORING_NS = "urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring"
_SCHEMAS_FILTER = (
    "subtree",
    f'<netconf-state xmlns="{_MONITORING_NS}"><schemas/></netconf-state>',
)


class YangImportError(Exception):
    pass


# ----------------------------------------------------------------- #
# NETCONF                                                            #
# ----------------------------------------------------------------- #

def _connect(host: str, port: int, username: str, password: str, device_name: str):
    from ncclient import manager
    return manager.connect(
        host=host, port=port, username=username, password=password,
        hostkey_verify=False, allow_agent=False, look_for_keys=False,
        device_params={"name": device_name or "csr"}, timeout=30,
    )


def netconf_check(host: str, port: int, username: str, password: str,
                  device_name: str = "csr") -> dict:
    """Quick hello: connect, count capabilities, report monitoring support."""
    with _connect(host, port, username, password, device_name) as m:
        caps = list(m.server_capabilities)
        has_mon = any(_MONITORING_NS in c for c in caps)
        return {"connected": True, "capabilities": len(caps),
                "netconf_monitoring": has_mon}


def netconf_schema_list(host: str, port: int, username: str, password: str,
                        device_name: str = "csr") -> list[dict]:
    """Read /netconf-state/schemas -> [{identifier, version, format}] (yang only)."""
    from lxml import etree
    with _connect(host, port, username, password, device_name) as m:
        reply = m.get(filter=_SCHEMAS_FILTER)
        root = etree.fromstring(reply.data_xml.encode())
    ns = {"m": _MONITORING_NS}
    out = []
    for s in root.findall(f".//m:schema", ns):
        ident = s.findtext("m:identifier", default="", namespaces=ns)
        ver = s.findtext("m:version", default="", namespaces=ns)
        fmt = s.findtext("m:format", default="", namespaces=ns)
        # format element text may be prefixed (e.g. "ncm:yang") — match on suffix
        if ident and fmt.split(":")[-1] == "yang":
            out.append({"identifier": ident, "version": ver})
    out.sort(key=lambda x: (x["identifier"], x["version"]))
    return out


def _clean_schema_text(text: str) -> str:
    """get-schema data may arrive wrapped in CDATA or with an XML declaration."""
    t = (text or "").strip()
    if t.startswith("<![CDATA[") and t.endswith("]]>"):
        t = t[9:-3].strip()
    if t.startswith("<?xml"):
        t = t.split("?>", 1)[-1].strip()
    return t


def netconf_download(repo: str, host: str, port: int, username: str,
                     password: str, identifiers: list[dict],
                     device_name: str = "csr") -> dict:
    """<get-schema> each identifier and save into the repo.

    identifiers: [{identifier, version}]. One connection for the whole batch.
    Per-schema failures are recorded, not fatal. Returns
    {saved:[file...], skipped:[...], failed:[{identifier, error}]}.
    """
    saved, skipped, failed = [], [], []
    existing = {m["file"] for m in _repo_modules(repo)}
    with _connect(host, port, username, password, device_name) as m:
        for item in identifiers:
            ident = (item.get("identifier") or "").strip()
            ver = (item.get("version") or "").strip()
            if not ident:
                continue
            fn = f"{ident}@{ver}.yang" if ver else f"{ident}.yang"
            if fn in existing:
                skipped.append(fn)
                continue
            try:
                reply = m.get_schema(ident, version=ver or None, format="yang")
                text = _clean_schema_text(getattr(reply, "data", None) or str(reply))
                if not text or "module" not in text[:2000]:
                    raise YangImportError("empty or non-YANG schema returned")
                info = yang_store.add_module(repo, fn, text)
                saved.append(info["file"])
                existing.add(info["file"])
            except Exception as e:
                failed.append({"identifier": ident, "error": f"{type(e).__name__}: {e}"})
    return {"saved": saved, "skipped": skipped, "failed": failed}


def _repo_modules(repo: str) -> list[dict]:
    for r in yang_store.list_repos():
        if r["name"] == repo:
            return r["modules"]
    return []


# ----------------------------------------------------------------- #
# SCP / SFTP                                                         #
# ----------------------------------------------------------------- #

def scp_copy(repo: str, host: str, username: str, password: str,
             remote_dir: str, recursive: bool = True, port: int = 22) -> dict:
    """Copy *.yang files from a remote directory over SFTP into the repo."""
    import paramiko
    saved, skipped, failed = [], [], []
    existing = {m["file"] for m in _repo_modules(repo)}
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=username, password=password,
                   allow_agent=False, look_for_keys=False, timeout=20)
    try:
        sftp = client.open_sftp()

        def walk(d: str):
            try:
                entries = sftp.listdir_attr(d)
            except IOError as e:
                raise YangImportError(f"cannot list {d!r}: {e}")
            for a in entries:
                p = d.rstrip("/") + "/" + a.filename
                if stat.S_ISDIR(a.st_mode):
                    if recursive:
                        walk(p)
                elif a.filename.endswith(".yang"):
                    if a.filename in existing:
                        skipped.append(a.filename)
                        continue
                    try:
                        with sftp.open(p, "r") as f:
                            text = f.read().decode("utf-8", errors="replace")
                        info = yang_store.add_module(repo, a.filename, text)
                        saved.append(info["file"])
                        existing.add(info["file"])
                    except Exception as e:
                        failed.append({"identifier": a.filename,
                                       "error": f"{type(e).__name__}: {e}"})

        walk(remote_dir)
    finally:
        client.close()
    return {"saved": saved, "skipped": skipped, "failed": failed}


# ----------------------------------------------------------------- #
# Git (shallow sparse clone)                                         #
# ----------------------------------------------------------------- #

def git_import(repo: str, url: str, branch: str = "", subdir: str = "",
               recursive: bool = True, timeout: int = 300) -> dict:
    """Sparse-clone <url>[<branch>] and import *.yang from <subdir>.

    The YangModels repo is multi-GB; --depth 1 --filter=blob:none --sparse
    with a sparse-checkout of just <subdir> pulls only what's needed.
    """
    if not re.match(r"^(https?://|git@)", (url or "").strip()):
        raise YangImportError("repository URL must start with http(s):// or git@")
    if shutil.which("git") is None:
        raise YangImportError("git binary not found on the server")
    saved, skipped, failed = [], [], []
    existing = {m["file"] for m in _repo_modules(repo)}
    tmp = Path(tempfile.mkdtemp(prefix="hitech_yang_git_"))
    try:
        cmd = ["git", "clone", "--depth", "1", "--filter=blob:none",
               "--sparse", "--quiet"]
        if branch:
            cmd += ["--branch", branch]
        cmd += [url.strip(), str(tmp / "clone")]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            raise YangImportError(f"git clone failed: {r.stderr.strip()[:400]}")
        clone = tmp / "clone"
        if subdir:
            r = subprocess.run(
                ["git", "-C", str(clone), "sparse-checkout", "set", subdir.strip("/")],
                capture_output=True, text=True, timeout=timeout)
            if r.returncode != 0:
                raise YangImportError(f"sparse-checkout failed: {r.stderr.strip()[:400]}")
            base = clone / subdir.strip("/")
            if not base.exists():
                raise YangImportError(
                    f"directory {subdir!r} not found in the repository. "
                    "Check the exact path/case (e.g. YangModels uses 'standard/', "
                    "not 'standards/'). Note: some YangModels vendor dirs "
                    "(juniper, huawei, nokia, ...) are git submodules — import "
                    "from that vendor's own repo URL instead. vendor/cisco is "
                    "in-tree and works directly.")
        else:
            subprocess.run(["git", "-C", str(clone), "sparse-checkout", "disable"],
                           capture_output=True, text=True, timeout=timeout)
            base = clone
        files = base.rglob("*.yang") if recursive else base.glob("*.yang")
        for p in sorted(files):
            if p.name in existing:
                skipped.append(p.name)
                continue
            try:
                info = yang_store.add_module(
                    repo, p.name, p.read_text(encoding="utf-8", errors="replace"))
                saved.append(info["file"])
                existing.add(info["file"])
            except Exception as e:
                failed.append({"identifier": p.name,
                               "error": f"{type(e).__name__}: {e}"})
    except subprocess.TimeoutExpired:
        raise YangImportError(f"git operation timed out after {timeout}s")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"saved": saved, "skipped": skipped, "failed": failed}
