"""Device inventory loader.

v1.5.0 — supports two file formats:

  1. Flat list (v1.4.0 style, simplest)
     devices:
       - name: cat8Kv71
         host: 192.168.89.71
         port_netconf: 830
         port_ssh: 22
         username: expert
         password: $env:CAT8KV71_PASSWORD
         device_type: cisco-iosxe
         read_only: false
         default: true

  2. pyATS testbed style (industry-standard, reusable across Ansible/Genie)
     devices:
       cat8Kv71:
         os: iosxe
         type: router
         platform: cat8kv
         credentials:
           default:
             username: "%ENV{CAT8KV71_USERNAME}"
             password: "%ENV{CAT8KV71_PASSWORD}"
         connections:
           cli:     {protocol: ssh,     ip: "%ENV{CAT8KV71}", port: 22}
           netconf: {protocol: netconf, ip: "%ENV{CAT8KV71}", port: 830}
         custom:                  # hitech-automation-ai-specific extras
           read_only: false
           default: true

The loader auto-detects which format the file uses by checking whether
`devices:` is a list (flat) or a mapping (pyATS).

Both `%ENV{VAR}` (pyATS standard) and `$env:VAR` (v1.4.0 syntax) are
expanded against `os.environ` at load time. Empty resolution leaves the
field blank — the agent will report the device as unusable when invoked.

The inventory file lives outside the application directory at
~/.hitech_automation_ai/devices.yaml so it is preserved across zip upgrades.
The path can be overridden with the INVENTORY_FILE environment variable.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("agent.inventory")

# Default location — overridable via env var for power users
from tools.state_dir import STATE_DIR
INVENTORY_DIR = STATE_DIR
DEFAULT_INVENTORY_FILE = INVENTORY_DIR / "devices.yaml"


def _resolve_inventory_path() -> Path:
    """Honour the INVENTORY_FILE env var if set, else use the default."""
    override = os.environ.get("INVENTORY_FILE", "").strip()
    if override:
        return Path(override).expanduser()
    return DEFAULT_INVENTORY_FILE


# Re-evaluated on every load() so tests / env changes can redirect it
INVENTORY_FILE = _resolve_inventory_path()


SAMPLE_INVENTORY = """# NETCONF Sender device inventory
# Located at ~/.hitech_automation_ai/devices.yaml (override with INVENTORY_FILE env var)
#
# This file supports two formats. Pick the one you prefer; the loader detects
# automatically based on whether `devices:` is a list or a mapping.
#
# ---------- Format A: flat list (simplest, recommended for new users) ----------
#
# devices:
#   - name: cat8Kv71
#     host: 192.168.89.71
#     port_netconf: 830      # NETCONF over SSH (ncclient)
#     port_ssh: 22           # CLI over SSH (netmiko)
#     username: expert
#     password: $env:CAT8KV71_PASSWORD   # or plaintext (lab only)
#     device_type: cisco-iosxe           # cisco-iosxe | cisco-nxos | cisco-iosxr | juniper-junos
#     read_only: false                   # writes ALLOWED when false (default true)
#     default: true                      # used as the fallback device
#
# ---------- Format B: pyATS testbed (industry-standard, reusable) -------------
#
# devices:
#   cat8Kv71:
#     os: iosxe
#     type: router
#     platform: cat8kv
#     credentials:
#       default:
#         username: "%ENV{CAT8KV71_USERNAME}"
#         password: "%ENV{CAT8KV71_PASSWORD}"
#     connections:
#       cli:
#         protocol: ssh
#         ip: "%ENV{CAT8KV71}"
#         port: 22
#       netconf:
#         protocol: netconf
#         ip: "%ENV{CAT8KV71}"
#         port: 830
#     custom:                  # hitech-automation-ai extras
#       read_only: false
#       default: true
#
# Env vars: both %ENV{VAR} (pyATS) and $env:VAR (v1.4.0) are expanded.
# Set them in the systemd drop-in at:
#   ~/.config/systemd/user/hitech_automation_ai.service.d/secrets.conf
#
# To allow writes on a device, set read_only: false. The approval modal
# still requires human confirmation before any commit.

devices: []
"""


@dataclass
class Device:
    """One inventory entry, normalised regardless of source format."""
    name: str
    host: str
    port_netconf: int = 830
    port_ssh: int = 22
    port_restconf: int = 443          # v1.7.0: RESTCONF (HTTPS)
    restconf_root: str = "/restconf/data"  # v1.7.0
    restconf_verify_tls: bool = False  # v1.7.0: lab default; document
    username: str = ""
    password: str = ""
    device_type: str = "cisco-iosxe"
    read_only: bool = True
    default: bool = False

    # Diagnostics — for the "Manage Devices" UI panel
    raw_password_ref: str = ""        # original spec string, e.g. "%ENV{VAR}"
    source_format: str = "flat"       # "flat" | "pyats"

    # Backward compat: netconf_tools.py originally read `.port`
    @property
    def port(self) -> int:
        return self.port_netconf


# Module-level cache; reloaded on mtime change or explicit reload
_inventory_cache: Optional[list[Device]] = None
_inventory_mtime: float = 0.0


# ----------------------------------------------------------------- #
# Environment interpolation                                          #
# ----------------------------------------------------------------- #

_ENV_PATTERN = re.compile(r"%ENV\{([A-Za-z_][A-Za-z0-9_]*)\}")

# v1.7.0: secrets file at ~/.hitech_automation_ai/secrets.yaml (chmod 600 recommended).
# Values from this file take precedence over $env:VAR. Loaded lazily on first
# reference, cached for the life of the process. Reload by re-saving devices.yaml
# (forces full inventory reload, which clears this cache too).
SECRETS_FILE = INVENTORY_DIR / "secrets.yaml"
_secrets_cache: Optional[dict] = None


def _load_secrets() -> dict:
    """Load ~/.hitech_automation_ai/secrets.yaml if present. Returns {} otherwise."""
    global _secrets_cache
    if _secrets_cache is not None:
        return _secrets_cache
    if not SECRETS_FILE.exists():
        _secrets_cache = {}
        return _secrets_cache
    try:
        import yaml
        with open(SECRETS_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            log.warning("secrets.yaml: must be a mapping; ignoring")
            _secrets_cache = {}
        else:
            _secrets_cache = data
            log.info("secrets.yaml: loaded %d secret(s)", len(data))
    except Exception as e:
        log.warning("secrets.yaml: failed to parse: %s", e)
        _secrets_cache = {}
    return _secrets_cache


def _expand_env(value: Any) -> str:
    """Expand env-var references inside a string. Three syntaxes supported.

    Precedence (highest first):
    - `$secret:VAR` — looks in ~/.hitech_automation_ai/secrets.yaml; whole-string only
    - `$env:VAR`    — looks in os.environ; whole-string only
    - `%ENV{VAR}`   — pyATS standard; can appear anywhere; checks secrets first, then env

    Returns the empty string if the variable is missing (with a log warning).
    Non-string values are converted to string.
    """
    if value is None:
        return ""
    s = str(value)

    # $secret:VAR — secrets file only
    if s.startswith("$secret:"):
        var = s[8:].strip()
        secrets = _load_secrets()
        resolved = secrets.get(var, "")
        if not resolved:
            log.warning("inventory: $secret:%s not found in %s", var, SECRETS_FILE)
        return str(resolved)

    # Public site: server environment variables are never readable through the
    # inventory (they hold the server's own settings). Only secrets.yaml counts.
    _public = os.environ.get("PUBLIC_MODE", "") == "1"
    _getenv = (lambda var, default="": default) if _public else os.environ.get

    # $env:VAR — env vars only
    if s.startswith("$env:"):
        var = s[5:].strip()
        resolved = _getenv(var, "")
        if not resolved:
            log.warning("inventory: $env:%s is unset", var)
        return resolved

    # %ENV{VAR} — pyATS standard; checks secrets first, then env (any mid-string)
    if "%ENV{" in s:
        secrets = _load_secrets()
        def _sub(m):
            var = m.group(1)
            # Precedence: secrets file > os.environ
            resolved = secrets.get(var) or _getenv(var, "")
            if not resolved:
                log.warning("inventory: %%ENV{%s} is unset", var)
            return str(resolved)
        return _ENV_PATTERN.sub(_sub, s)

    return s


# ----------------------------------------------------------------- #
# Format detection + parsing                                         #
# ----------------------------------------------------------------- #

# Map pyATS `os:` field to ncclient device_params name (and our device_type)
_OS_TO_DEVICE_TYPE = {
    "iosxe":      "cisco-iosxe",
    "ios-xe":     "cisco-iosxe",
    "ios":        "cisco-iosxe",       # treat generic IOS as iosxe-ish
    "nxos":       "cisco-nxos",
    "nx-os":      "cisco-nxos",
    "iosxr":      "cisco-iosxr",
    "xr":         "cisco-iosxr",
    "junos":      "juniper-junos",
}


def _parse_flat_entry(item: dict, index: int) -> Optional[Device]:
    """Parse one entry from the flat list format."""
    name = str(item.get("name", "")).strip()
    host_raw = str(item.get("host", "")).strip()
    if not name or not host_raw:
        log.warning("inventory: device #%d missing name or host, skipping", index)
        return None

    raw_pw = item.get("password", "")
    # `port` (old single-port) maps to port_netconf for backward compat
    port_netconf = int(item.get("port_netconf") or item.get("port") or 830)
    port_ssh = int(item.get("port_ssh") or 22)
    # v1.7.0: RESTCONF
    port_restconf = int(item.get("port_restconf") or 443)
    restconf_root = str(item.get("restconf_root") or "/restconf/data")
    restconf_verify_tls = bool(item.get("restconf_verify_tls", False))

    return Device(
        name=name,
        host=_expand_env(host_raw),
        port_netconf=port_netconf,
        port_ssh=port_ssh,
        port_restconf=port_restconf,
        restconf_root=restconf_root,
        restconf_verify_tls=restconf_verify_tls,
        username=_expand_env(item.get("username", "")),
        password=_expand_env(raw_pw),
        device_type=str(item.get("device_type", "cisco-iosxe")).strip(),
        read_only=bool(item.get("read_only", True)),
        default=bool(item.get("default", False)),
        raw_password_ref=str(raw_pw),
        source_format="flat",
    )


def _parse_pyats_entry(name: str, item: dict) -> Optional[Device]:
    """Parse one entry from the pyATS testbed format."""
    if not isinstance(item, dict):
        log.warning("inventory: pyATS device %r is not a mapping, skipping", name)
        return None

    # credentials.default.{username,password}
    creds = (item.get("credentials") or {}).get("default") or {}
    username_raw = creds.get("username", "")
    password_raw = creds.get("password", "")

    # connections: cli (for ssh/netmiko), netconf (for ncclient), restconf (for httpx)
    conns = item.get("connections") or {}
    cli_conn = conns.get("cli") or {}
    nc_conn = conns.get("netconf") or {}
    rc_conn = conns.get("restconf") or {}

    # Host: prefer cli.ip, fall back to netconf.ip / restconf.ip
    host_raw = cli_conn.get("ip") or nc_conn.get("ip") or rc_conn.get("ip") or ""
    if not host_raw:
        log.warning("inventory: pyATS device %r has no connections.cli.ip / .netconf.ip / .restconf.ip, skipping", name)
        return None

    # Ports
    try:
        port_ssh = int(cli_conn.get("port", 22))
    except (TypeError, ValueError):
        port_ssh = 22
    try:
        port_netconf = int(nc_conn.get("port", 830))
    except (TypeError, ValueError):
        port_netconf = 830
    try:
        port_restconf = int(rc_conn.get("port", 443))
    except (TypeError, ValueError):
        port_restconf = 443

    # device_type from os field
    os_field = str(item.get("os", "")).strip().lower()
    device_type = _OS_TO_DEVICE_TYPE.get(os_field, "cisco-iosxe")

    # custom.* extras
    custom = item.get("custom") or {}
    read_only = bool(custom.get("read_only", True))
    is_default = bool(custom.get("default", False))
    # v1.7.0: RESTCONF custom fields
    restconf_root = str(custom.get("restconf_root") or rc_conn.get("root") or "/restconf/data")
    restconf_verify_tls = bool(custom.get("restconf_verify_tls", False))

    return Device(
        name=name,
        host=_expand_env(host_raw),
        port_netconf=port_netconf,
        port_ssh=port_ssh,
        port_restconf=port_restconf,
        restconf_root=restconf_root,
        restconf_verify_tls=restconf_verify_tls,
        username=_expand_env(username_raw),
        password=_expand_env(password_raw),
        device_type=device_type,
        read_only=read_only,
        default=is_default,
        raw_password_ref=str(password_raw),
        source_format="pyats",
    )


def _load_from_disk(path: Path) -> list[Device]:
    """Read and parse the YAML inventory. Returns [] on missing/malformed."""
    try:
        import yaml
    except ImportError:
        log.warning("inventory: PyYAML not installed — install with: pip install pyyaml")
        return []

    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        log.warning("inventory: failed to parse %s: %s", path, e)
        return []

    raw_devices = data.get("devices")
    if raw_devices is None:
        log.warning("inventory: no 'devices' key in %s", path)
        return []

    devices: list[Device] = []

    # Format detection: list = flat, dict/mapping = pyATS
    if isinstance(raw_devices, list):
        for i, item in enumerate(raw_devices):
            if not isinstance(item, dict):
                log.warning("inventory: device #%d is not a mapping, skipping", i)
                continue
            d = _parse_flat_entry(item, i)
            if d:
                devices.append(d)
        log.info("inventory: parsed %d device(s) from flat-format file %s", len(devices), path)

    elif isinstance(raw_devices, dict):
        for name, item in raw_devices.items():
            d = _parse_pyats_entry(str(name), item)
            if d:
                devices.append(d)
        log.info("inventory: parsed %d device(s) from pyATS testbed %s", len(devices), path)

    else:
        log.warning("inventory: 'devices' must be a list (flat) or mapping (pyATS), got %s",
                    type(raw_devices).__name__)
        return []

    return devices


def _ensure_sample_exists(path: Path) -> None:
    """Create the inventory file with a commented sample if missing."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SAMPLE_INVENTORY, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    log.info("inventory: created sample at %s", path)


# ----------------------------------------------------------------- #
# Public API                                                         #
# ----------------------------------------------------------------- #

def load_devices(force: bool = False) -> list[Device]:
    """Return device list, reloading from disk if the file changed (mtime)."""
    global _inventory_cache, _inventory_mtime, INVENTORY_FILE

    INVENTORY_FILE = _resolve_inventory_path()
    _ensure_sample_exists(INVENTORY_FILE)

    try:
        mtime = INVENTORY_FILE.stat().st_mtime
    except OSError:
        mtime = 0.0

    if force or _inventory_cache is None or mtime != _inventory_mtime:
        _inventory_cache = _load_from_disk(INVENTORY_FILE)
        _inventory_mtime = mtime

    return list(_inventory_cache)


def reload_devices() -> list[Device]:
    """Force a reload from disk, ignoring the cache. Used by /api/devices/reload."""
    global _secrets_cache
    _secrets_cache = None    # v1.7.0: also re-read secrets.yaml on next access
    return load_devices(force=True)


def get_device(name: str) -> Optional[Device]:
    for d in load_devices():
        if d.name == name:
            return d
    return None


def get_default_device() -> Optional[Device]:
    devs = load_devices()
    for d in devs:
        if d.default:
            return d
    return devs[0] if devs else None


def list_device_names() -> list[str]:
    return [d.name for d in load_devices()]


def safe_describe(d: Device) -> dict:
    """Public-safe dict (no password) for sending over the API and UI."""
    return {
        "name": d.name,
        "host": d.host,
        "port_netconf": d.port_netconf,
        "port_ssh": d.port_ssh,
        "port_restconf": d.port_restconf,            # v1.7.0
        "restconf_root": d.restconf_root,            # v1.7.0
        "restconf_verify_tls": d.restconf_verify_tls,  # v1.7.0
        "username": d.username,
        "device_type": d.device_type,
        "read_only": d.read_only,
        "default": d.default,
        "source_format": d.source_format,
        "password_configured": bool(d.password),
        "password_ref": (
            d.raw_password_ref
            if any(tok in d.raw_password_ref for tok in ("$env:", "$secret:", "%ENV{"))
            else "(inline)" if d.raw_password_ref else "(empty)"
        ),
    }


# ----------------------------------------------------------------- #
# v1.7.0: Inventory CRUD — used by the Manage Devices GUI panel.    #
# Atomic file writes (via temp + rename) with .bak backups.         #
# Always writes in FLAT format, even if the existing file was pyATS #
# (mixing formats is not allowed — we warn before overwriting).     #
# ----------------------------------------------------------------- #

def _file_is_pyats_format(path: Path) -> bool:
    """Detect if the existing file uses pyATS mapping format."""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return isinstance(data.get("devices"), dict)
    except Exception:
        return False


def _atomic_write_devices_yaml(devices: list[Device]) -> None:
    """Write the inventory to disk atomically. Always uses flat format."""
    import yaml
    path = INVENTORY_FILE
    bak_path = path.with_suffix(path.suffix + ".bak")

    # Backup current file
    if path.exists():
        try:
            import shutil
            shutil.copy2(path, bak_path)
        except Exception as e:
            log.warning("inventory: failed to back up to %s: %s", bak_path, e)

    # Build serialisable dict
    payload = {
        "devices": [
            {
                "name": d.name,
                "host": d.host,
                "port_netconf": d.port_netconf,
                "port_ssh": d.port_ssh,
                "port_restconf": d.port_restconf,
                "restconf_root": d.restconf_root,
                "restconf_verify_tls": d.restconf_verify_tls,
                "username": d.username,
                "password": d.raw_password_ref or d.password,
                "device_type": d.device_type,
                "read_only": d.read_only,
                "default": d.default,
            }
            for d in devices
        ]
    }
    # Strip default-valued optional fields to keep the file tidy
    for entry in payload["devices"]:
        if entry["restconf_root"] == "/restconf/data":
            del entry["restconf_root"]
        if entry["restconf_verify_tls"] is False:
            del entry["restconf_verify_tls"]

    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    tmp.replace(path)
    log.info("inventory: wrote %d device(s) to %s (backup at %s)", len(devices), path, bak_path)


def add_or_update_device(new_device_dict: dict, force_format_switch: bool = False) -> Device:
    """Insert a new device or replace an existing one (matched by name).

    Returns the resulting Device. Raises ValueError on validation errors.

    If the existing file is in pyATS format, refuses unless force_format_switch=True;
    rewriting in flat format would lose any pyATS-specific keys you've added.
    """
    name = (new_device_dict.get("name") or "").strip()
    host = (new_device_dict.get("host") or "").strip()
    if not name or not host:
        raise ValueError("name and host are required")

    if INVENTORY_FILE.exists() and _file_is_pyats_format(INVENTORY_FILE) and not force_format_switch:
        raise ValueError(
            "Existing inventory is in pyATS format. Editing it from the UI would "
            "rewrite it in flat format. Pass force_format_switch=true to confirm, "
            "or edit the YAML by hand."
        )

    # Parse into a Device using the flat parser so all validation runs the same way
    proto = _parse_flat_entry(new_device_dict, 0)
    if proto is None:
        raise ValueError("Could not parse the supplied device fields")

    # Build new list: keep all others, replace if name matches
    current = load_devices(force=True)
    others = [d for d in current if d.name != name]
    # If marking as default, clear default from all others
    if proto.default:
        for d in others:
            d.default = False
    new_list = others + [proto]
    _atomic_write_devices_yaml(new_list)
    reload_devices()
    return proto


def delete_device(name: str) -> bool:
    """Remove a device by name. Returns True if found and removed."""
    if INVENTORY_FILE.exists() and _file_is_pyats_format(INVENTORY_FILE):
        raise ValueError(
            "Existing inventory is in pyATS format. Deleting from the UI would "
            "rewrite it in flat format. Edit the YAML by hand."
        )
    current = load_devices(force=True)
    new_list = [d for d in current if d.name != name]
    if len(new_list) == len(current):
        return False
    _atomic_write_devices_yaml(new_list)
    reload_devices()
    return True
