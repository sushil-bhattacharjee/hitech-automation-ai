"""
Public mode (PUBLIC_MODE=1) — guards for a worker process that serves ONE
signed-in user of software-automation.hitech007.ai.

The gateway (gateway.py) starts one worker per user with its own state folder,
so users never share files or in-memory caches. This module adds what a
single-user install never needed:

* Network guard — every outbound TCP connection made from Python (ncclient,
  netmiko/paramiko, httpx) is checked: private, loopback, link-local (incl. the
  cloud metadata server 169.254.169.254), multicast and reserved addresses are
  refused. Claude is reached over the gateway's unix socket, not TCP.
* check_url / check_host — the same rule for the few places that hand a URL
  to a subprocess (curl, git), which the socket guard cannot see.
* require_worker_key — only the gateway may talk to a worker.

Nothing here runs unless PUBLIC_MODE=1, so the workstation and .98 installs
behave exactly as before.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlsplit

PUBLIC_MODE = os.environ.get("PUBLIC_MODE", "") == "1"
WORKER_KEY = os.environ.get("WORKER_KEY", "")
# The user's own lab devices (their CML/APIC in the lab VPC): exact address+port
# pairs the gateway writes here while their devices run. Owned by the gateway
# (root), readable by the worker, so a user cannot add to it.
ALLOW_FILE = os.environ.get("ALLOW_FILE", "")
_allow_cache: tuple[float, frozenset] = (-1.0, frozenset())


def allowed_pairs() -> frozenset:
    """{(ip, port)} this user may reach although the address is private."""
    global _allow_cache
    if not ALLOW_FILE:
        return frozenset()
    try:
        mtime = os.stat(ALLOW_FILE).st_mtime
    except OSError:
        return frozenset()
    if mtime != _allow_cache[0]:
        try:
            import json
            data = json.load(open(ALLOW_FILE))
            pairs = frozenset((str(ip), int(port)) for ip, port in data.get("allow", []))
        except Exception:
            pairs = frozenset()
        _allow_cache = (mtime, pairs)
    return _allow_cache[1]


class BlockedAddress(ConnectionRefusedError):
    """Raised when a public-mode worker tries to reach a non-public address."""


def _ip_is_public(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped:
        a = a.ipv4_mapped
    return a.is_global and not (a.is_multicast or a.is_reserved)


def check_host(host: str, port: int | None = None) -> None:
    """Resolve host; raise BlockedAddress unless every address is public."""
    if not host:
        raise BlockedAddress("no host given")
    try:
        infos = socket.getaddrinfo(host, port or 0, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise BlockedAddress(f"cannot resolve {host}: {e}") from None
    for info in infos:
        ip = info[4][0]
        if port and (ip, int(port)) in allowed_pairs():
            continue
        if not _ip_is_public(ip):
            raise BlockedAddress(
                f"{host} ({ip}) is a private or reserved address — the public "
                "version only connects to devices on the public internet")


def check_url(url: str, schemes=("http", "https")) -> tuple[str, int, str]:
    """Allow only the given schemes and a public host (for curl/git subprocesses).

    Returns (host, port, ip) of the address that was checked, so a caller can pin
    the subprocess to it (curl --resolve) and a DNS answer cannot change between
    the check and the connection.
    """
    parts = urlsplit(url or "")
    scheme = parts.scheme.lower()
    if scheme not in schemes:
        raise BlockedAddress(f"only {', '.join(schemes)} URLs are allowed here")
    host = parts.hostname or ""
    port = parts.port or (443 if scheme == "https" else 80)
    check_host(host, port)
    ip = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)[0][4][0]
    if not _ip_is_public(ip) and (ip, int(port)) not in allowed_pairs():
        raise BlockedAddress(f"{host} ({ip}) is a private or reserved address")
    return host, port, ip


# --------------------------------------------------------------- socket guard
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


def _allowed(sock, address) -> None:
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return                                   # unix sockets etc.
    host, port = address[0], address[1]
    try:
        ipaddress.ip_address(str(host).split("%", 1)[0])
        ips = [str(host)]
    except ValueError:                           # a name: resolve like connect would
        ips = [i[4][0] for i in socket.getaddrinfo(host, port, sock.family)]
    for ip in ips:
        if _ip_is_public(ip) or (ip, int(port)) in allowed_pairs():
            continue
        raise BlockedAddress(
            f"connection to {ip}:{port} refused — the public version only "
            "connects to devices on the public internet")


def _guarded_connect(self, address):
    _allowed(self, address)
    return _real_connect(self, address)


def _guarded_connect_ex(self, address):
    try:
        _allowed(self, address)
    except BlockedAddress:
        import errno
        return errno.ECONNREFUSED
    return _real_connect_ex(self, address)


def install() -> None:
    if PUBLIC_MODE and socket.socket.connect is _real_connect:
        socket.socket.connect = _guarded_connect
        socket.socket.connect_ex = _guarded_connect_ex


install()


# --------------------------------------------------------------- denied features
# Features that run arbitrary code or commands, or manage the local AI/RAG
# stack. They stay in the installable version; the public site refuses them.
DENIED_PATHS = frozenset({
    "/api/python-execute",      # runs a pasted Python script
    "/api/python-run",          # runs Python
    "/api/curl-execute",        # runs a pasted curl command line
    "/api/rag-rebuild",         # rebuilds the local vector DB
    "/api/process-memory",      # host process list
    "/api/jq",                  # runs the jq binary (its env/$ENV would show settings)
    "/api/ollama-unload", "/api/ollama-warm", "/api/ollama-loaded",
})
# Whole feature areas refused on the public site.
DENIED_PREFIXES = (
    "/api/ansible/",            # v1.50.0 Ansible: playbooks run any module (shell, local
                                # connection) in a subprocess the socket guard cannot see
)
DENIED_MESSAGE = ("This feature runs code on the server, so it is switched off on "
                  "the public site. Install the software to use it.")


def is_denied(path: str) -> bool:
    p = path.rstrip("/")
    return p in DENIED_PATHS or (p + "/").startswith(DENIED_PREFIXES)


# --------------------------------------------------------------- worker key
def require_worker_key(app) -> None:
    """Reject any request that does not carry the gateway's per-worker key."""
    if not PUBLIC_MODE:
        return
    import hmac
    from fastapi.responses import JSONResponse

    @app.middleware("http")
    async def _worker_key(request, call_next):
        got = request.headers.get("x-worker-key", "")
        if not WORKER_KEY or not hmac.compare_digest(got, WORKER_KEY):
            return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
        if is_denied(request.url.path):
            return JSONResponse({"ok": False, "error": DENIED_MESSAGE}, status_code=403)
        return await call_next(request)
