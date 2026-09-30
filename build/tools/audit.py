"""Append-only audit log for agent activity.

Each significant event is written as one JSON object per line to
~/.hitech_automation_ai/audit.log. This file is the source of truth for "what did
the agent actually do" — useful for incident review and proof of approval.

Rotation is NOT automatic. Configure logrotate or move the file periodically.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("agent.audit")

from tools.state_dir import STATE_DIR
AUDIT_DIR = STATE_DIR
AUDIT_FILE = AUDIT_DIR / "audit.log"

# Max payload chars stored per event to prevent huge XML blobs filling disk.
# Full payloads can be reconstructed from device-side logs if needed.
MAX_PAYLOAD_CHARS = 8000


def _truncate(value: Any) -> Any:
    """Trim long strings to keep the log manageable."""
    if isinstance(value, str) and len(value) > MAX_PAYLOAD_CHARS:
        return value[:MAX_PAYLOAD_CHARS] + f"\n... [{len(value) - MAX_PAYLOAD_CHARS} chars truncated]"
    return value


def log_event(event_type: str, **fields: Any) -> None:
    """Append one event to the audit log.

    event_type: short stable identifier, e.g.
        agent_start, agent_end, tool_call, approval_request,
        approval_decision, write_applied, error
    fields:    arbitrary JSON-serializable kwargs

    Never raises — audit logging failure must not break the agent.
    """
    record = {
        "ts": time.time(),
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        "event": event_type,
    }
    for k, v in fields.items():
        record[k] = _truncate(v)

    try:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception as e:
        log.warning("audit: failed to write event %s: %s", event_type, e)


def read_recent(n: int = 50) -> list[dict]:
    """Return the last n events from the audit log as parsed dicts."""
    if not AUDIT_FILE.exists():
        return []
    try:
        with open(AUDIT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        log.warning("audit: failed to read %s: %s", AUDIT_FILE, e)
        return []

    tail = lines[-n:] if n > 0 else lines
    events: list[dict] = []
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # Skip corrupted lines — don't fail the whole read
            continue
    return events


def file_path() -> str:
    return str(AUDIT_FILE)
