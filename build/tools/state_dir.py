"""
v1.27.0: single source of truth for the private state directory.

State (inventory, secrets, saved collections, audit log, vector_db) lives outside
the build/ tree so it survives zip upgrades. As of v1.27.0 the directory is
~/.hitech_automation_ai/ (renamed from ~/.netconf-sender/).

A one-time auto-migration runs on import: if the new dir does not exist but the
legacy ~/.netconf-sender/ does, its contents are copied over — so existing
installs keep their inventory and saved collections with no manual step.
"""
import os
import shutil
from pathlib import Path

_NEW = Path.home() / ".hitech_automation_ai"
_LEGACY = Path.home() / ".netconf-sender"


def _migrate_if_needed() -> None:
    try:
        if _NEW.exists():
            return
        if _LEGACY.exists() and _LEGACY.is_dir():
            shutil.copytree(_LEGACY, _NEW)
    except Exception:
        # never let migration crash startup; fall back to creating an empty dir
        pass


_migrate_if_needed()

# Allow an explicit override (used by power users / tests).
STATE_DIR = Path(os.environ.get("HITECH_STATE_DIR", str(_NEW)))
try:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
