"""
v1.56.0: starter set — saved work every install starts with.

build/starter/ (made on .98 by tools/export-starter.sh from ~/.hitech_automation_ai, secrets
blanked) holds RESTCONF / NETCONF / XPath / Python collections and environments, YANG repos,
Terraform and Ansible projects. At start-up the installed app (GitHub download, Docker image,
lab workstation) copies into its state folder every starter file it does not have yet — once
per starter VERSION, never overwriting anything the user has. The public site seeds from its
bucket instead (gateway.py, tools/publish-template.sh), so a worker there does nothing here.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .state_dir import STATE_DIR

log = logging.getLogger("hitech_automation_ai")
STARTER = Path(__file__).resolve().parent.parent / "starter"
NEVER = {"devices.yaml", "secrets.yaml", "cml_mcp.yaml", "audit.log", "pki", "vector_db",
         "yangsuite-media", "README.md", "VERSION"}
MARKER = ".starter-version"


def _empty_tree(p: Path) -> bool:
    """A saved-requests tree the app created empty is not the user's work."""
    if not p.name.endswith("_tree.json"):
        return False
    try:
        return not json.loads(p.read_text()).get("root", {}).get("children")
    except Exception:
        return False


def seed(state: Path = STATE_DIR) -> int:
    try:
        version = (STARTER / "VERSION").read_text().strip()
    except OSError:
        return 0
    marker = state / MARKER
    try:
        if marker.read_text().strip() == version:
            return 0
    except OSError:
        pass
    n = 0
    try:
        for src in sorted(STARTER.rglob("*")):
            rel = src.relative_to(STARTER)
            if rel.parts[0] in NEVER or not src.is_file() or src.is_symlink():
                continue
            dst = state / rel
            if dst.exists() and not _empty_tree(dst):
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            n += 1
        state.mkdir(parents=True, exist_ok=True)
        marker.write_text(version)
    except Exception as e:                      # never stop the app over the starter set
        log.warning("starter set: %s", e)
    if n:
        log.info("starter set %s: %d file(s) added to %s", version, n, state)
    return n
