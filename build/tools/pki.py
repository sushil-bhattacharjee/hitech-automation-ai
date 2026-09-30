"""
v1.49.0: Certificates (private PKI) — CA, key + CSR, CA signing, verify, bundles.

Design rules
------------
* Every operation is built as an argv list by ONE builder function, then either
  executed (subprocess, no shell) or rendered into the exported .sh with
  shlex.join — so the exported script is exactly what ran.
* openssl conf files are rendered by ONE function each (CA.conf / leaf.conf)
  and used both on disk and in the exported heredocs.
* All files live flat in  <STATE_DIR>/pki/  (like a hand-run `e2-security/`
  folder). File names are validated; no paths, no leading dot.
* CA private keys are recorded in pki/.cas.json and are never downloadable.
* CSR extensions and signing extensions are separate sections:
    [req_ext]  -> goes INTO the CSR (no issuer exists yet)
    [v3_ext]   -> added by the CA at signing time (authorityKeyIdentifier
                  needs the issuer, so it cannot be in the CSR)
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from .state_dir import STATE_DIR

PKI_DIR = STATE_DIR / "pki"
_REG = PKI_DIR / ".cas.json"

ALGS = ("RSA 2048", "RSA 3072", "RSA 4096",
        "ECDSA P-256", "ECDSA P-384", "ECDSA P-521", "Ed25519")
PROFILES = {"server": "serverAuth", "client": "clientAuth", "both": "serverAuth, clientAuth"}

ALG_HINT = {
    "RSA 2048": "✓ universal support, minimum acceptable size",
    "RSA 3072": "✓ universal support, stronger",
    "RSA 4096": "✓ universal support, slower handshakes — common for CAs",
    "ECDSA P-256": "✓ universal TLS support, fast — recommended EC default",
    "ECDSA P-384": "✓ universal support, higher security margin",
    "ECDSA P-521": "⚠ valid, but Chrome rejects P-521 for TLS — lab / non-browser use",
    "Ed25519": "⚠ browsers don't accept Ed25519 certs — fine for mTLS / lab. No -sha256 (built-in hash)",
}

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
# DN values: keep to characters that are safe both in an openssl conf value and
# in an inline -subj string ('/', '$', '#', '=', newlines are excluded).
_DN_RE = re.compile(r"^[A-Za-z0-9 .,'()&@_+:*-]{0,64}$")
_DNS_RE = re.compile(r"^(\*\.)?([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")


class PkiError(ValueError):
    """User-facing validation / execution error."""


# ------------------------------------------------------------------ helpers

def _ensure_dir() -> Path:
    PKI_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(PKI_DIR, 0o700)
    except Exception:
        pass
    return PKI_DIR


def _fname(name: str, what: str) -> str:
    name = (name or "").strip()
    if not _NAME_RE.match(name):
        raise PkiError(f"{what}: invalid file name {name!r} "
                       "(letters, digits, . _ - only; no paths, no leading dot)")
    return name


def _dn(val: str, what: str, required: bool = False) -> str:
    val = (val or "").strip()
    if required and not val:
        raise PkiError(f"{what} is required")
    if not _DN_RE.match(val):
        raise PkiError(f"{what}: unsupported characters in {val!r}")
    return val


def _country(val: str) -> str:
    val = (val or "").strip().upper()
    if val and not re.fullmatch(r"[A-Z]{2}", val):
        raise PkiError("Country must be exactly 2 letters (e.g. AU)")
    return val


def _alg(val: str) -> str:
    if val not in ALGS:
        raise PkiError(f"Unsupported key type {val!r}")
    return val


def _days(val, what: str) -> int:
    try:
        d = int(val)
    except Exception:
        raise PkiError(f"{what} must be a number of days")
    if not 1 <= d <= 36500:
        raise PkiError(f"{what} must be between 1 and 36500")
    return d


def _sans(items) -> list[tuple[str, str]]:
    out = []
    for it in items or []:
        t = (it.get("type") or "DNS").upper()
        v = (it.get("value") or "").strip()
        if not v:
            continue
        if t == "IP":
            try:
                ipaddress.ip_address(v)
            except ValueError:
                raise PkiError(f"SAN IP {v!r} is not a valid IP address")
        elif t == "DNS":
            is_ip = True
            try:
                ipaddress.ip_address(v)
            except ValueError:
                is_ip = False
            if is_ip:
                raise PkiError(f"SAN {v!r} is an IP address — use an IP entry, not DNS")
            if not _DNS_RE.match(v) or len(v) > 253:
                raise PkiError(f"SAN DNS {v!r} is not a valid hostname")
        else:
            raise PkiError(f"SAN type must be DNS or IP, got {t!r}")
        out.append((t, v))
    if not out:
        raise PkiError("At least one Subject Alternative Name (SAN) is required")
    return out


def key_args(alg: str) -> list[str]:
    if alg.startswith("ECDSA"):
        return ["-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:" + alg.split()[1]]
    if alg == "Ed25519":
        return ["-newkey", "ed25519"]
    return ["-newkey", "rsa:" + alg.split()[1]]


def md_args(alg: str) -> list[str]:
    """Ed25519 has a built-in hash — passing a digest makes openssl fail."""
    return [] if alg == "Ed25519" else ["-sha256"]


def _load_reg() -> dict:
    try:
        return json.loads(_REG.read_text())
    except Exception:
        return {}


def _save_reg(reg: dict) -> None:
    _ensure_dir()
    _REG.write_text(json.dumps(reg, indent=2))


def _run(argv: list[str], env_extra: Optional[dict] = None, timeout: int = 60) -> subprocess.CompletedProcess:
    if not shutil.which("openssl"):
        raise PkiError("openssl binary not found on the server (apt install openssl)")
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(argv, cwd=str(_ensure_dir()), capture_output=True,
                          text=True, timeout=timeout, env=env)


def _run_ok(argv: list[str], what: str, env_extra: Optional[dict] = None) -> str:
    cp = _run(argv, env_extra)
    if cp.returncode != 0:
        err = "\n".join(l for l in (cp.stderr or "").splitlines()
                        if l.strip() and not re.fullmatch(r"[.+*\-]+", l.strip()))
        raise PkiError(f"{what} failed: {err.strip()[:800] or 'openssl exit ' + str(cp.returncode)}")
    return cp.stdout


def _signer_alg_of_key(key_file: str) -> str:
    """Detect whether a (CA) key is Ed25519 — decides whether -sha256 is allowed."""
    out = _run_ok(["openssl", "pkey", "-in", key_file, "-noout", "-text_pub"], "reading CA key")
    return "Ed25519" if "ED25519" in out.upper() else "other"


# ------------------------------------------------------------------ conf renderers

def render_ca_conf(p: dict) -> str:
    alg = p["alg"]
    lines = ["[ req ]"]
    if alg.startswith("RSA"):
        lines.append(f"default_bits       = {alg.split()[1]}")
    if alg != "Ed25519":
        lines.append("default_md         = sha256")
    lines += ["distinguished_name = ca_dn",
              "x509_extensions    = v3_ca",
              "prompt             = no",
              "",
              "[ ca_dn ]"]
    if p.get("c"):
        lines.append(f"C  = {p['c']}")
    if p.get("o"):
        lines.append(f"O  = {p['o']}")
    if p.get("ou"):
        lines.append(f"OU = {p['ou']}")
    lines.append(f"CN = {p['cn']}")
    lines += ["",
              "# these two lines are what make it a CA",
              "[ v3_ca ]",
              "basicConstraints       = critical, CA:TRUE",
              "keyUsage               = critical, keyCertSign, cRLSign",
              "subjectKeyIdentifier   = hash",
              "authorityKeyIdentifier = keyid:always"]
    return "\n".join(lines) + "\n"


def render_leaf_conf(p: dict) -> str:
    alg = p["alg"]
    ku = "critical, digitalSignature" + (", keyEncipherment" if alg.startswith("RSA") else "")
    eku = PROFILES[p["profile"]]
    lines = ["[ req ]"]
    if alg.startswith("RSA"):
        lines.append(f"default_bits       = {alg.split()[1]}")
    if alg != "Ed25519":
        lines.append("default_md         = sha256")
    lines += ["distinguished_name = req_dn",
              "req_extensions     = req_ext",
              "prompt             = no",
              "",
              "[ req_dn ]"]
    for k in ("c", "st", "l", "o", "ou"):
        if p.get(k):
            lines.append(f"{k.upper():<2} = {p[k]}")
    lines.append(f"CN = {p['cn']}")
    lines += ["",
              "# used by: openssl req  (goes INTO the CSR — no issuer exists yet)",
              "[ req_ext ]",
              "basicConstraints       = critical, CA:FALSE",
              f"keyUsage               = {ku}",
              f"extendedKeyUsage       = {eku}",
              "subjectAltName         = @alt_names",
              "",
              "# used by: openssl x509 -req  (added when the CA signs — AKI needs the issuer)",
              "[ v3_ext ]",
              "basicConstraints       = critical, CA:FALSE",
              f"keyUsage               = {ku}",
              f"extendedKeyUsage       = {eku}",
              "subjectKeyIdentifier   = hash",
              "authorityKeyIdentifier = keyid, issuer",
              "subjectAltName         = @alt_names",
              "",
              "[ alt_names ]"]
    d = i = 0
    for t, v in p["sans"]:
        if t == "IP":
            i += 1
            lines.append(f"IP.{i}  = {v}")
        else:
            d += 1
            lines.append(f"DNS.{d} = {v}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ param normalisers

def norm_ca(raw: dict) -> dict:
    return {
        "cn": _dn(raw.get("cn"), "CA Common Name", required=True),
        "o": _dn(raw.get("o"), "CA Organization"),
        "ou": _dn(raw.get("ou"), "CA Org Unit"),
        "c": _country(raw.get("c")),
        "alg": _alg(raw.get("alg") or "ECDSA P-384"),
        "days": _days(raw.get("days") or 3650, "CA validity"),
        "key_name": _fname(raw.get("key_name") or "CA.key", "CA key file"),
        "crt_name": _fname(raw.get("crt_name") or "CA.crt", "CA cert file"),
        "conf_name": _fname(raw.get("conf_name") or "CA.conf", "CA config file"),
        "style": "inline" if raw.get("style") == "inline" else "conf",
    }


def norm_leaf(raw: dict) -> dict:
    prof = raw.get("profile") or "server"
    if prof not in PROFILES:
        raise PkiError("Profile must be server, client or both")
    return {
        "profile": prof,
        "alg": _alg(raw.get("alg") or "ECDSA P-256"),
        "days": _days(raw.get("days") or 397, "Certificate validity"),
        "cn": _dn(raw.get("cn"), "Common Name (CN)", required=True),
        "o": _dn(raw.get("o"), "Organization"),
        "ou": _dn(raw.get("ou"), "Org Unit"),
        "c": _country(raw.get("c")),
        "st": _dn(raw.get("st"), "State"),
        "l": _dn(raw.get("l"), "Locality"),
        "sans": _sans(raw.get("sans")),
        "conf_name": _fname(raw.get("conf_name") or "server.conf", "Config file"),
        "key_name": _fname(raw.get("key_name") or "server.key", "Key file"),
        "csr_name": _fname(raw.get("csr_name") or "server.csr", "CSR file"),
        "crt_name": _fname(raw.get("crt_name") or "server.crt", "Certificate file"),
        "ca_key": _fname(raw.get("ca_key") or "CA.key", "CA key file"),
        "ca_crt": _fname(raw.get("ca_crt") or "CA.crt", "CA cert file"),
    }


# ------------------------------------------------------------------ argv builders (single source of truth)

def cmd_ca(p: dict) -> list[str]:
    argv = ["openssl", "req", "-x509", *key_args(p["alg"]), "-nodes", *md_args(p["alg"]),
            "-keyout", p["key_name"], "-out", p["crt_name"], "-days", str(p["days"])]
    if p["style"] == "conf":
        argv += ["-config", p["conf_name"]]
    else:
        subj = "".join(f"/{k}={p[v]}" for k, v in (("C", "c"), ("O", "o"), ("OU", "ou"), ("CN", "cn")) if p.get(v))
        argv += ["-subj", subj,
                 "-addext", "basicConstraints=critical,CA:TRUE",
                 "-addext", "keyUsage=critical,keyCertSign,cRLSign"]
    return argv


def cmd_csr(p: dict) -> list[str]:
    return ["openssl", "req", *key_args(p["alg"]), "-nodes",
            "-keyout", p["key_name"], "-out", p["csr_name"], "-config", p["conf_name"]]


def cmd_sign(p: dict, signer_alg: str) -> list[str]:
    return ["openssl", "x509", "-req", "-in", p["csr_name"],
            "-CA", p["ca_crt"], "-CAkey", p["ca_key"], "-CAcreateserial",
            "-out", p["crt_name"], "-days", str(p["days"]), *md_args(signer_alg),
            "-extfile", p["conf_name"], "-extensions", "v3_ext"]


def cmd_verify(p: dict) -> list[str]:
    return ["openssl", "verify", "-CAfile", p["ca_crt"], p["crt_name"]]


def cmd_show(crt: str) -> list[str]:
    return ["openssl", "x509", "-in", crt, "-noout", "-subject", "-issuer", "-dates",
            "-ext", "subjectAltName,extendedKeyUsage,keyUsage,basicConstraints"]


def cmd_p12(p: dict, out: str) -> list[str]:
    return ["openssl", "pkcs12", "-export", "-inkey", p["key_name"], "-in", p["crt_name"],
            "-certfile", p["ca_crt"], "-name", p["cn"], "-out", out, "-passout", "env:P12_PASS"]


# ------------------------------------------------------------------ operations

def _exists(name: str) -> bool:
    return (PKI_DIR / name).is_file()


def generate_ca(raw: dict, overwrite: bool = False) -> dict:
    p = norm_ca(raw)
    _ensure_dir()
    for f in (p["key_name"], p["crt_name"]):
        if _exists(f) and not overwrite:
            raise PkiError(f"{f} already exists — tick 'overwrite' or choose another name")
    if p["style"] == "conf":
        (PKI_DIR / p["conf_name"]).write_text(render_ca_conf(p))
    _run_ok(cmd_ca(p), "CA generation")
    os.chmod(PKI_DIR / p["key_name"], 0o600)
    reg = _load_reg()
    reg[p["crt_name"]] = {"key": p["key_name"], "cn": p["cn"], "alg": p["alg"],
                         "created": time.strftime("%Y-%m-%d %H:%M:%S"), "source": "generated"}
    _save_reg(reg)
    return {"ok": True, "ca_crt": p["crt_name"], "ca_key": p["key_name"],
            "details": _run_ok(cmd_show(p["crt_name"]), "reading CA")}


def import_ca(crt_bytes: bytes, key_bytes: bytes, crt_name: str, key_name: str,
              overwrite: bool = False) -> dict:
    crt_name = _fname(crt_name, "CA cert file")
    key_name = _fname(key_name, "CA key file")
    _ensure_dir()
    for f in (crt_name, key_name):
        if _exists(f) and not overwrite:
            raise PkiError(f"{f} already exists — tick 'overwrite' or choose another name")
    tmp_c, tmp_k = PKI_DIR / (".imp_" + crt_name), PKI_DIR / (".imp_" + key_name)
    tmp_c.write_bytes(crt_bytes)
    tmp_k.write_bytes(key_bytes)
    os.chmod(tmp_k, 0o600)
    try:
        bc = _run_ok(["openssl", "x509", "-in", tmp_c.name, "-noout", "-ext", "basicConstraints"],
                     "reading imported certificate")
        if "CA:TRUE" not in bc:
            raise PkiError("Imported certificate is not a CA (basicConstraints CA:TRUE missing)")
        a = _run_ok(["openssl", "x509", "-in", tmp_c.name, "-noout", "-pubkey"], "reading cert public key")
        b = _run_ok(["openssl", "pkey", "-in", tmp_k.name, "-pubout"], "reading private key")
        if a.strip() != b.strip():
            raise PkiError("Private key does not match the CA certificate")
        tmp_c.replace(PKI_DIR / crt_name)
        tmp_k.replace(PKI_DIR / key_name)
    finally:
        for t in (tmp_c, tmp_k):
            if t.exists():
                t.unlink()
    subj = _run_ok(["openssl", "x509", "-in", crt_name, "-noout", "-subject"], "reading CA subject")
    m = re.search(r"CN\s*=\s*([^,/\n]+)", subj)
    reg = _load_reg()
    reg[crt_name] = {"key": key_name, "cn": (m.group(1).strip() if m else crt_name),
                     "alg": "imported", "created": time.strftime("%Y-%m-%d %H:%M:%S"), "source": "imported"}
    _save_reg(reg)
    return {"ok": True, "ca_crt": crt_name, "ca_key": key_name,
            "details": _run_ok(cmd_show(crt_name), "reading CA")}


def list_cas() -> list[dict]:
    reg = _load_reg()
    out = []
    for crt, meta in reg.items():
        if _exists(crt) and _exists(meta.get("key", "")):
            out.append({"crt": crt, **meta})
    return out


def create_csr(raw: dict, overwrite: bool = False) -> dict:
    p = norm_leaf(raw)
    _ensure_dir()
    for f in (p["key_name"], p["csr_name"]):
        if _exists(f) and not overwrite:
            raise PkiError(f"{f} already exists — tick 'overwrite' or choose another name")
    (PKI_DIR / p["conf_name"]).write_text(render_leaf_conf(p))
    _run_ok(cmd_csr(p), "Key + CSR generation")
    os.chmod(PKI_DIR / p["key_name"], 0o600)
    text = _run_ok(["openssl", "req", "-in", p["csr_name"], "-noout", "-subject", "-verify"], "reading CSR")
    return {"ok": True, "key": p["key_name"], "csr": p["csr_name"], "conf": p["conf_name"],
            "details": text.strip()}


def sign_csr(raw: dict, overwrite: bool = False) -> dict:
    p = norm_leaf(raw)
    for f, what in ((p["csr_name"], "CSR"), (p["conf_name"], "Config"),
                    (p["ca_crt"], "CA certificate"), (p["ca_key"], "CA key")):
        if not _exists(f):
            raise PkiError(f"{what} {f} not found — complete the earlier step first")
    if _exists(p["crt_name"]) and not overwrite:
        raise PkiError(f"{p['crt_name']} already exists — tick 'overwrite' or choose another name")
    signer = _signer_alg_of_key(p["ca_key"])
    _run_ok(cmd_sign(p, signer), "Signing")
    return {"ok": True, "crt": p["crt_name"], "details": _run_ok(cmd_show(p["crt_name"]), "reading certificate")}


def verify(raw: dict) -> dict:
    p = norm_leaf(raw)
    for f in (p["crt_name"], p["ca_crt"]):
        if not _exists(f):
            raise PkiError(f"{f} not found")
    cp = _run(cmd_verify(p))
    chain_ok = cp.returncode == 0
    chain_msg = (cp.stdout or cp.stderr).strip().splitlines()[-1] if (cp.stdout or cp.stderr) else ""
    key_match = None
    if _exists(p["key_name"]):
        a = _run_ok(["openssl", "x509", "-in", p["crt_name"], "-noout", "-pubkey"], "reading cert public key")
        b = _run_ok(["openssl", "pkey", "-in", p["key_name"], "-pubout"], "reading key")
        key_match = a.strip() == b.strip()
    show = _run_ok(cmd_show(p["crt_name"]), "reading certificate")
    return {"ok": True, "chain_ok": chain_ok, "chain_msg": chain_msg,
            "key_match": key_match, "details": show}


def bundle(raw: dict, password: str) -> dict:
    p = norm_leaf(raw)
    for f in (p["crt_name"], p["key_name"], p["ca_crt"]):
        if not _exists(f):
            raise PkiError(f"{f} not found")
    stem = p["crt_name"].rsplit(".", 1)[0]
    fullchain = f"{stem}-fullchain.pem"
    (PKI_DIR / fullchain).write_text((PKI_DIR / p["crt_name"]).read_text().rstrip() + "\n"
                                     + (PKI_DIR / p["ca_crt"]).read_text())
    out = {"ok": True, "fullchain": fullchain}
    if password:
        p12 = f"{stem}.p12"
        _run_ok(cmd_p12(p, p12), "PKCS#12 export", env_extra={"P12_PASS": password})
        os.chmod(PKI_DIR / p12, 0o600)
        out["p12"] = p12
    return out


def list_files() -> list[dict]:
    if not PKI_DIR.exists():
        return []
    ca_keys = {m.get("key") for m in _load_reg().values()}
    out = []
    for f in sorted(PKI_DIR.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        st = f.stat()
        out.append({"name": f.name, "size": st.st_size,
                    "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
                    "ca_key": f.name in ca_keys})
    return out


def is_protected(name: str) -> bool:
    return name in {m.get("key") for m in _load_reg().values()}


def file_path(name: str) -> Path:
    name = _fname(name, "File")
    f = PKI_DIR / name
    if not f.is_file():
        raise PkiError(f"{name} not found")
    return f


def inspect(name: str) -> str:
    f = file_path(name)
    if is_protected(name) or name.endswith(".key"):
        return _run_ok(["openssl", "pkey", "-in", name, "-noout", "-text_pub"], "reading key")
    if name.endswith(".csr"):
        return _run_ok(["openssl", "req", "-in", name, "-noout", "-text"], "reading CSR")
    if name.endswith((".crt", ".pem", ".cer")):
        return _run_ok(["openssl", "x509", "-in", name, "-noout", "-text"], "reading certificate")
    if name.endswith(".p12"):
        return "(binary PKCS#12 bundle — download it and import on the target system)"
    return f.read_text(errors="replace")[:20000]


def delete(name: str) -> None:
    f = file_path(name)
    f.unlink()
    reg = _load_reg()
    if name in reg:
        reg.pop(name)
        _save_reg(reg)


# ------------------------------------------------------------------ exports

def _heredoc(name: str, body: str) -> str:
    return f"cat > {shlex.quote(name)} << 'EOF'\n{body.rstrip()}\nEOF"


def export_sh(ca_raw: dict, leaf_raw: dict, ca_mode: str) -> str:
    """Bash script = the exact argv the app runs, joined with shlex."""
    lp = norm_leaf(leaf_raw)
    j = lambda argv: shlex.join(argv)
    parts = ["#!/usr/bin/env bash",
             "# Generated by hiTech Automation AI v1.49.0 — Certificates",
             "# Every openssl command below is exactly what the app runs.",
             "set -euo pipefail", ""]
    if ca_mode == "new":
        cp = norm_ca(ca_raw)
        cp["key_name"], cp["crt_name"] = lp["ca_key"], lp["ca_crt"]
        signer = cp["alg"]
        if cp["style"] == "conf":
            parts += ["# Step-1a: CA config", _heredoc(cp["conf_name"], render_ca_conf(cp)), "",
                      "# Step-1b: CA private key + self-signed CA certificate (extensions from the conf)"]
        else:
            parts += ["# Step-1: CA private key + self-signed CA certificate (inline extensions)"]
        parts += [j(cmd_ca(cp)), f"chmod 600 {shlex.quote(cp['key_name'])}", ""]
    else:
        meta = _load_reg().get(lp["ca_crt"], {})
        if _exists(lp["ca_key"]):
            signer = _signer_alg_of_key(lp["ca_key"])
        else:
            signer = meta.get("alg", "other")
        parts += [f"# Step-1: using existing CA {lp['ca_crt']} / {lp['ca_key']}", ""]
    parts += ["# Step-2: certificate config", _heredoc(lp["conf_name"], render_leaf_conf(lp)), "",
              "# Step-3: private key + CSR", j(cmd_csr(lp)), f"chmod 600 {shlex.quote(lp['key_name'])}", "",
              "# Step-4: CA signs the CSR", j(cmd_sign(lp, signer)), "",
              "# Step-5: verify", j(cmd_verify(lp)), j(cmd_show(lp["crt_name"])),
              "diff <(" + j(["openssl", "x509", "-in", lp["crt_name"], "-noout", "-pubkey"]) + ") \\",
              "     <(" + j(["openssl", "pkey", "-in", lp["key_name"], "-pubout"]) + ") && echo \"key matches cert\"", "",
              "# Step-6 (optional): full chain + PKCS#12 bundle",
              f"cat {shlex.quote(lp['crt_name'])} {shlex.quote(lp['ca_crt'])} > "
              f"{shlex.quote(lp['crt_name'].rsplit('.', 1)[0] + '-fullchain.pem')}",
              "read -rsp 'PKCS#12 password: ' P12_PASS && echo && export P12_PASS",
              j(cmd_p12(lp, lp["crt_name"].rsplit(".", 1)[0] + ".p12"))]
    return "\n".join(parts) + "\n"


_PY_CURVE = {"P-256": "SECP256R1", "P-384": "SECP384R1", "P-521": "SECP521R1"}


def _py_keygen(alg: str) -> str:
    if alg.startswith("ECDSA"):
        return f"ec.generate_private_key(ec.{_PY_CURVE[alg.split()[1]]}())"
    if alg == "Ed25519":
        return "ed25519.Ed25519PrivateKey.generate()"
    return f"rsa.generate_private_key(public_exponent=65537, key_size={alg.split()[1]})"


def _py_name(fields: list[tuple[str, str]]) -> str:
    oid = {"C": "COUNTRY_NAME", "ST": "STATE_OR_PROVINCE_NAME", "L": "LOCALITY_NAME",
           "O": "ORGANIZATION_NAME", "OU": "ORGANIZATIONAL_UNIT_NAME", "CN": "COMMON_NAME"}
    return "x509.Name([\n" + "".join(
        f"    x509.NameAttribute(NameOID.{oid[k]}, {v!r}),\n" for k, v in fields if v) + "])"


def export_py(ca_raw: dict, leaf_raw: dict, ca_mode: str) -> str:
    """Same result via the `cryptography` library (pip install cryptography)."""
    lp = norm_leaf(leaf_raw)
    eku = {"server": "[ExtendedKeyUsageOID.SERVER_AUTH]",
           "client": "[ExtendedKeyUsageOID.CLIENT_AUTH]",
           "both": "[ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]"}[lp["profile"]]
    rsa_leaf = lp["alg"].startswith("RSA")
    sans = ",\n        ".join(
        f"x509.IPAddress(ipaddress.ip_address({v!r}))" if t == "IP" else f"x509.DNSName({v!r})"
        for t, v in lp["sans"])
    s = [f'''# Generated by hiTech Automation AI v1.49.0 — Certificates
# Same result as the .sh export, using the `cryptography` library.
# pip install cryptography
import datetime, ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec, ed25519

now = datetime.datetime.now(datetime.timezone.utc)
PEM, PKCS8, NOENC = serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()

def sign_alg(key):
    """Ed25519 signs with its own built-in hash; everything else uses SHA-256."""
    return None if isinstance(key, ed25519.Ed25519PrivateKey) else hashes.SHA256()
''']
    if ca_mode == "new":
        cp = norm_ca(ca_raw)
        s.append(f'''
# Step-1: CA private key + self-signed CA certificate
ca_key = {_py_keygen(cp["alg"])}
ca_name = {_py_name([("C", cp["c"]), ("O", cp["o"]), ("OU", cp["ou"]), ("CN", cp["cn"])])}
ca_crt = (x509.CertificateBuilder()
    .subject_name(ca_name).issuer_name(ca_name)              # self-signed: subject == issuer
    .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
    .not_valid_before(now).not_valid_after(now + datetime.timedelta(days={cp["days"]}))
    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)   # makes it a CA
    .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False, key_encipherment=False,
        data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
        encipher_only=False, decipher_only=False), critical=True)
    .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
    .sign(ca_key, sign_alg(ca_key)))
open({lp["ca_key"]!r}, "wb").write(ca_key.private_bytes(PEM, PKCS8, NOENC))
open({lp["ca_crt"]!r}, "wb").write(ca_crt.public_bytes(PEM))
''')
    else:
        s.append(f'''
# Step-1: load the existing CA
ca_key = serialization.load_pem_private_key(open({lp["ca_key"]!r}, "rb").read(), None)
ca_crt = x509.load_pem_x509_certificate(open({lp["ca_crt"]!r}, "rb").read())
''')
    s.append(f'''
# Step-3: server private key + CSR
key = {_py_keygen(lp["alg"])}
csr = (x509.CertificateSigningRequestBuilder()
    .subject_name({_py_name([("C", lp["c"]), ("ST", lp["st"]), ("L", lp["l"]), ("O", lp["o"]), ("OU", lp["ou"]), ("CN", lp["cn"])]).replace(chr(10), chr(10) + "    ")})
    .add_extension(x509.SubjectAlternativeName([
        {sans}
    ]), critical=False)
    .sign(key, sign_alg(key)))
open({lp["key_name"]!r}, "wb").write(key.private_bytes(PEM, PKCS8, NOENC))
open({lp["csr_name"]!r}, "wb").write(csr.public_bytes(PEM))

# Step-4: CA signs the CSR (extensions added at signing time, like [ v3_ext ])
crt = (x509.CertificateBuilder()
    .subject_name(csr.subject).issuer_name(ca_crt.subject)
    .public_key(csr.public_key()).serial_number(x509.random_serial_number())
    .not_valid_before(now).not_valid_after(now + datetime.timedelta(days={lp["days"]}))
    .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
    .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment={rsa_leaf},
        data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False,
        encipher_only=False, decipher_only=False), critical=True)
    .add_extension(x509.ExtendedKeyUsage({eku}), critical=False)
    .add_extension(csr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value, critical=False)
    .add_extension(x509.SubjectKeyIdentifier.from_public_key(csr.public_key()), critical=False)
    .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
    .sign(ca_key, sign_alg(ca_key)))
open({lp["crt_name"]!r}, "wb").write(crt.public_bytes(PEM))

# Step-5: verify — signature chains to the CA, and the key matches the cert
crt.verify_directly_issued_by(ca_crt)
same = crt.public_key().public_bytes(PEM, serialization.PublicFormat.SubjectPublicKeyInfo) == \\
       key.public_key().public_bytes(PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
print("✅", {lp["crt_name"]!r}, "|", crt.subject.rfc4514_string())
print("   issuer :", crt.issuer.rfc4514_string())
print("   SAN    :", crt.extensions.get_extension_for_class(x509.SubjectAlternativeName).value)
print("   chain OK, key matches cert:", same)
''')
    return "".join(s)


def export_all(ca_raw: dict, leaf_raw: dict, ca_mode: str) -> dict:
    """Everything the code panel shows. Validation errors are returned, not raised,
    so the panel can show what's wrong while the user is still typing."""
    out = {"ok": True, "hints": ALG_HINT}
    try:
        if ca_mode == "new":
            out["ca_conf"] = render_ca_conf(norm_ca(ca_raw))
        else:
            out["ca_conf"] = "# existing CA selected — no CA.conf is generated\n"
        out["leaf_conf"] = render_leaf_conf(norm_leaf(leaf_raw))
        out["sh"] = export_sh(ca_raw, leaf_raw, ca_mode)
        out["py"] = export_py(ca_raw, leaf_raw, ca_mode)
    except PkiError as e:
        out = {"ok": False, "error": str(e), "hints": ALG_HINT}
    return out
