"""v1.56.2: download / upload a whole Ansible or Terraform project as a .zip.

export_zip(base, skip)            -> bytes of <project>/... (in memory, size-capped)
import_zip(data, skip, exists, write, overwrite)
                                  -> {"ok", "saved", "skipped", "conflicts"}

The caller (ansible_mgr / terraform_mgr) passes its own safe `write(rel, bytes)` and
`exists(rel)`, so every path still goes through that manager's checks (segments,
no escaping the project, Terraform's "state in use" lock).

Import rules:
  - a single top folder in the zip (full-aci-ansible/...) is stripped
  - folders, symlinks, __MACOSX/, .DS_Store and the caller's skip list are ignored
  - limits: zip 20 MB, 50 MB unpacked, 2000 files, 10 MB per file
  - overwrite=False and some files already exist -> nothing is written, the
    conflicts are returned so the page can ask first
"""
from __future__ import annotations

import io
import re
import stat
import zipfile
from pathlib import Path
from typing import Callable

MAX_ZIP = 20 * 1024 * 1024
MAX_TOTAL = 50 * 1024 * 1024
MAX_FILES = 2000
MAX_ONE = 10 * 1024 * 1024
_JUNK = re.compile(r"(^|/)(__MACOSX|\.DS_Store|Thumbs\.db|__pycache__)(/|$)")


class ZipError(ValueError):
    """User-facing error."""


def _skipped(rel: str, skip: Callable[[str], bool]) -> bool:
    return bool(_JUNK.search(rel)) or skip(rel)


def export_zip(base: Path, skip: Callable[[str], bool]) -> bytes:
    buf = io.BytesIO()
    total = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(base).as_posix()
            if p.is_symlink() or not p.is_file() or _skipped(rel, skip):
                continue
            total += p.stat().st_size
            if total > MAX_TOTAL:
                raise ZipError("project is larger than 50 MB — too big to download as one zip")
            z.write(p, f"{base.name}/{rel}")
    return buf.getvalue()


def _entries(z: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, str]]:
    out = []
    for info in z.infolist():
        name = info.filename.replace("\\", "/")
        if info.is_dir() or name.endswith("/"):
            continue
        if stat.S_ISLNK(info.external_attr >> 16):
            continue
        name = name.lstrip("/")
        if not name:
            continue
        out.append((info, name))
    return out


def _strip_top(names: list[str]) -> str:
    """'proj/' when every file sits under one top folder, else ''."""
    tops = {n.split("/", 1)[0] for n in names}
    if len(tops) == 1 and all("/" in n for n in names):
        return tops.pop() + "/"
    return ""


def import_zip(data: bytes, skip: Callable[[str], bool], exists: Callable[[str], bool],
               write: Callable[[str, bytes], None], overwrite: bool = False) -> dict:
    if len(data) > MAX_ZIP:
        raise ZipError("zip is larger than 20 MB")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ZipError("not a .zip file")
    with z:
        entries = _entries(z)
        top = _strip_top([n for _, n in entries if not _JUNK.search(n)])
        todo, skipped = [], []
        total = 0
        for info, name in entries:
            rel = name[len(top):] if top and name.startswith(top) else name
            if not rel or _skipped(rel, skip):
                skipped.append(rel or name)
                continue
            if ".." in rel.split("/"):
                raise ZipError(f"unsafe path in zip: {name}")
            if info.file_size > MAX_ONE:
                raise ZipError(f"{rel} is larger than 10 MB")
            total += info.file_size
            if total > MAX_TOTAL:
                raise ZipError("zip unpacks to more than 50 MB")
            todo.append((info, rel))
        if len(todo) > MAX_FILES:
            raise ZipError(f"zip has {len(todo)} files — the limit is {MAX_FILES}")
        if not todo:
            raise ZipError("nothing to import in this zip")
        conflicts = [rel for _, rel in todo if exists(rel)]
        if conflicts and not overwrite:
            return {"ok": True, "saved": [], "skipped": skipped, "conflicts": conflicts}
        saved = []
        for info, rel in todo:
            with z.open(info) as f:
                body = f.read(MAX_ONE + 1)
            if len(body) > MAX_ONE:
                raise ZipError(f"{rel} is larger than 10 MB")
            write(rel, body)
            saved.append(rel)
    return {"ok": True, "saved": saved, "skipped": skipped, "conflicts": conflicts}
