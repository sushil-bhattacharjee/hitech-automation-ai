"""
curl_safe.py — the "curl-restconf (paste)" pane on the public site (PUBLIC_MODE=1).

The installable app hands the pasted text to `bash -lc`. The public site cannot run a
shell for its users, so this reads the pasted curl command(s) itself and runs the real
`curl` binary with an argument list (no shell), after:

  * only curl, one or more commands (separated by new lines, `;` or `&&`), no pipes,
    no $( ), no redirection;
  * only the options below (request, headers, data, login, TLS, output format);
    nothing that reads or writes files (-o, -K, -T, -d @file …) or picks a proxy/socket;
  * every URL http(s) and checked by the network guard (public addresses, or this
    user's own lab devices), then pinned with --resolve so DNS cannot change it,
    --max-redirs 0, --proto =http,https, --noproxy '*';
  * $VAR / ${VAR} from the active Environment are filled in (as the shell would).
"""
from __future__ import annotations

import asyncio
import os
import re
import shlex
import tempfile
import time

import public_guard as _pg

# option -> takes a value?   (long and short forms)
_FLAGS_NOARG = {
    "-s", "--silent", "-S", "--show-error", "-k", "--insecure", "-i", "--include",
    "-I", "--head", "-v", "--verbose", "-f", "--fail", "-G", "--get", "--compressed",
    "-g", "--globoff", "--http1.1", "--http2", "-N", "--no-buffer", "-sk", "-ks", "-ski", "-sik",
    "-kis", "-iks", "-isk", "-ksi", "-sS", "-Ss", "-skS", "-sSk", "-ksS", "-kSs", "-Ssk", "-Sks",
    "--fail-with-body", "--location-trusted",
}
_FLAGS_ARG = {
    "-X", "--request", "-H", "--header", "-d", "--data", "--data-raw", "--data-binary",
    "--data-ascii", "--data-urlencode", "--json", "-u", "--user", "-m", "--max-time",
    "--connect-timeout", "-w", "--write-out", "-b", "--cookie", "-A", "--user-agent",
    "-e", "--referer", "--url",
}
_REFUSED = {
    "-o": "writing to files", "--output": "writing to files", "-O": "writing to files",
    "--remote-name": "writing to files", "-K": "config files", "--config": "config files",
    "-T": "uploading files", "--upload-file": "uploading files", "-F": "form file uploads",
    "--form": "form file uploads", "-x": "proxies", "--proxy": "proxies", "--unix-socket": "unix sockets",
    "--resolve": "--resolve", "--connect-to": "--connect-to", "-c": "cookie files",
    "--cookie-jar": "cookie files", "-L": "following redirects", "--location": "following redirects",
    "-D": "header files", "--dump-header": "header files", "--interface": "--interface",
}
_DATA = {"-d", "--data", "--data-raw", "--data-binary", "--data-ascii", "--data-urlencode", "--json"}
_VAR = re.compile(r"\$\{(\w+)\}|\$(\w+)")


class Refused(ValueError):
    pass


def _expand(tok: str, env: dict) -> str:
    return _VAR.sub(lambda m: str(env.get(m.group(1) or m.group(2), "")), tok)


def _newlines_to_semicolons(text: str) -> str:
    """A new line outside quotes ends a command (as in the shell); inside quotes it stays."""
    out, q, esc = [], None, False
    for ch in text:
        if esc:
            out.append(ch)
            esc = False
        elif ch == "\\" and q != "'":
            out.append(ch)
            esc = True
        elif q:
            out.append(ch)
            if ch == q:
                q = None
        elif ch in "'\"":
            out.append(ch)
            q = ch
        elif ch == "\n":
            out.append(" ; ")
        else:
            out.append(ch)
    return "".join(out)


def split_commands(text: str) -> list[list[str]]:
    """Text -> [[curl, args...], ...]. Raises Refused for anything but plain curl commands."""
    text = re.sub(r"\\\r?\n", " ", text)                                  # line continuations
    text = "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith("#"))
    if re.search(r"\$\(|`", text):
        raise Refused("$( ) and backticks are not available on the public site")
    cmds: list[list[str]] = []
    for line in [_newlines_to_semicolons(text)]:
        lex = shlex.shlex(line, posix=True, punctuation_chars=";&|<>")
        lex.whitespace_split = True
        cur: list[str] = []
        for tok in lex:
            if tok in (";", "&&"):
                if cur:
                    cmds.append(cur)
                cur = []
            elif tok and set(tok) <= set(";&|<>"):
                raise Refused("pipes and redirection (| jq, >, <) are not available on the public site — "
                              "use the response filter instead")
            else:
                cur.append(tok)
        if cur:
            cmds.append(cur)
    if not cmds:
        raise Refused("nothing to run")
    for c in cmds:
        if c[0] != "curl":
            raise Refused(f"only curl commands can run here (not {c[0]!r})")
    if len(cmds) > 10:
        raise Refused("at most 10 curl commands at a time")
    return cmds


def build_argv(cmd: list[str], env: dict, hdr_file: str) -> list[str]:
    """One parsed curl command -> a safe argv for the curl binary."""
    out: list[str] = []
    urls: list[str] = []
    args = [_expand(t, env) for t in cmd[1:]]
    i = 0
    while i < len(args):
        a = args[i]
        name, val = a, None
        if a.startswith("--") and "=" in a:
            name, val = a.split("=", 1)
        if name in _REFUSED:
            raise Refused(f"{name} ({_REFUSED[name]}) is not available on the public site")
        if name in _FLAGS_NOARG:
            out.append(name)
        elif name in _FLAGS_ARG:
            if val is None:
                i += 1
                if i >= len(args):
                    raise Refused(f"{name} needs a value")
                val = args[i]
            if name in _DATA | {"-H", "--header", "-w", "--write-out"} and val.startswith("@"):
                raise Refused("data from a file (@file) is not available on the public site")
            if name in ("-b", "--cookie") and "=" not in val:
                raise Refused("cookie files are not available on the public site (use -b 'name=value')")
            if name == "--url":
                urls.append(val)
            else:
                out += [name, val]
        elif a.startswith("-") and len(a) > 1 and not a.startswith("--") and len(a) > 2 \
                and set(a[1:]) <= set("skiSvfIGgN"):
            out.append(a)                                                        # combined short flags
        elif a.startswith("-"):
            raise Refused(f"curl option {a} is not available on the public site")
        else:
            urls.append(a)
        i += 1
    if not urls:
        raise Refused("no URL in the curl command")
    pins: list[str] = []
    for u in urls:
        try:
            host, port, ip = _pg.check_url(u)
        except _pg.BlockedAddress as e:
            raise Refused(str(e))
        pins += ["--resolve", f"{host}:{port}:{'[' + ip + ']' if ':' in ip else ip}"]
    return (["curl", "-q", "--globoff", "--proto", "=http,https", "--max-redirs", "0", "--noproxy", "*"] + pins
            + out + ["-D", hdr_file, "--"] + urls)


async def run(text: str, env: dict, timeout: int) -> dict:
    t0 = time.monotonic()
    hdr_files: list[str] = []
    try:
        try:
            cmds = split_commands(text)
            argvs = []
            for c in cmds:
                f = tempfile.NamedTemporaryFile(prefix="curlhdr_", suffix=".txt", delete=False)
                f.close()
                hdr_files.append(f.name)
                argvs.append(build_argv(c, env, f.name))
        except Refused as e:
            return {"ok": False, "error": str(e), "elapsed_ms": int((time.monotonic() - t0) * 1000)}
        stdout, stderr, rc = b"", b"", 0
        for argv in argvs:
            left = timeout - (time.monotonic() - t0)
            if left <= 0:
                return {"ok": False, "error": f"timeout after {timeout}s",
                        "elapsed_ms": int((time.monotonic() - t0) * 1000)}
            proc = await asyncio.create_subprocess_exec(
                *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tempfile.gettempdir()})
            try:
                o, e = await asyncio.wait_for(proc.communicate(), timeout=left)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {"ok": False, "error": f"timeout after {timeout}s",
                        "elapsed_ms": int((time.monotonic() - t0) * 1000)}
            stdout += o
            stderr += e
            rc = proc.returncode
            if rc != 0 and len(argvs) > 1:
                break                                        # like && : stop at the first failure
        blocks = []
        for i, hf in enumerate(hdr_files):
            try:
                raw = open(hf, encoding="utf-8", errors="replace").read().strip()
            except OSError:
                raw = ""
            if raw:
                parts = [b for b in raw.split("\n\n") if b.strip()]
                blocks.append({"index": i + 1, "raw": (parts[-1] if parts else raw).strip()})
        return {"ok": True, "exit_code": rc, "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "elapsed_ms": int((time.monotonic() - t0) * 1000), "header_blocks": blocks}
    finally:
        for hf in hdr_files:
            try:
                os.unlink(hf)
            except OSError:
                pass
