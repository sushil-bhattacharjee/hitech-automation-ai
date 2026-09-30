"""v1.10.0 (issue-4): in-memory cache of the most recent direct-execute result.

The Config Mgmt panes (NETCONF / RESTCONF / CLI / XPath) generate their results
server-side. We stash the latest one here so the agentic chat can read "the
response the user just got" via the read_last_result tool, instead of the user
pasting a huge XML blob into the prompt.

Single-user / localhost app, so a process-global slot (guarded by a lock) is
sufficient — no per-session bookkeeping needed.
"""

from __future__ import annotations

import time
from threading import Lock

_lock = Lock()
_last: dict = {
    "transport": None,   # 'netconf-xpath' | 'netconf' | 'restconf' | 'cli'
    "device": None,
    "query": None,       # xpath / uri / command
    "source": None,      # 'state' | 'config' | None
    "kind": "text",      # 'xml' | 'text'
    "content": "",
    "ts": 0.0,
}


def set_last_result(transport: str, content: str, *, device=None,
                    query=None, source=None, kind: str = "text") -> None:
    """Record the latest direct-execute result."""
    with _lock:
        _last.update(
            transport=transport,
            content=content or "",
            device=device,
            query=query,
            source=source,
            kind=kind,
            ts=time.time(),
        )


def get_last_result() -> dict:
    """Return a copy of the last result record (content may be '')."""
    with _lock:
        return dict(_last)
