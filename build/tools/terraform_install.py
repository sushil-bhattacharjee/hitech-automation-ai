"""
v1.53.0: install Terraform + the ACI provider for this app — the CCIE Automation
v1.1 exam versions — into one folder, with no system changes:

    <dest>/bin/terraform                       Terraform 1.13.3
    <dest>/mirror/registry.terraform.io/ciscodevnet/aci/2.17.0/linux_amd64/...
    <dest>/terraformrc                         installs providers ONLY from that mirror

    python3 terraform_install.py <dest>        (the ⚙ Install button runs this)

Both downloads are checked against their published SHA256SUMS (integrity; no GPG check). Standard library
only, so it runs before anything else is installed. Used by the installable app
(.98, Docker); the public site's runner image does the same in its Dockerfile.
"""
import hashlib
import io
import os
import platform
import stat
import sys
import urllib.request
import zipfile
from pathlib import Path

TF_VERSION = "1.13.3"
ACI_VERSION = "2.17.0"


def _arch() -> str:
    m = platform.machine().lower()
    return {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(m, m)


def _get(url: str) -> bytes:
    print(f"  downloading {url}", flush=True)
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def _checked(url: str, sums_url: str, name: str) -> bytes:
    data = _get(url)
    sums = _get(sums_url).decode()
    want = next((l.split()[0] for l in sums.splitlines() if l.strip().endswith(name)), None)
    got = hashlib.sha256(data).hexdigest()
    if want != got:
        sys.exit(f"✖ checksum mismatch for {name}: expected {want}, got {got}")
    print(f"  ✔ sha256 ok ({name})", flush=True)
    return data


def install(dest: Path) -> None:
    arch = _arch()
    osname = {"linux": "linux", "darwin": "darwin", "windows": "windows"}.get(platform.system().lower(), "linux")
    exe = "terraform.exe" if osname == "windows" else "terraform"
    dest = dest.resolve()
    (dest / "bin").mkdir(parents=True, exist_ok=True)

    print(f"== Terraform {TF_VERSION} ({osname}_{arch})", flush=True)
    base = f"https://releases.hashicorp.com/terraform/{TF_VERSION}"
    name = f"terraform_{TF_VERSION}_{osname}_{arch}.zip"
    data = _checked(f"{base}/{name}", f"{base}/terraform_{TF_VERSION}_SHA256SUMS", name)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        (dest / "bin" / exe).write_bytes(z.read(exe))
    os.chmod(dest / "bin" / exe, 0o755)

    print(f"== provider CiscoDevNet/aci {ACI_VERSION}", flush=True)
    base = f"https://github.com/CiscoDevNet/terraform-provider-aci/releases/download/v{ACI_VERSION}"
    name = f"terraform-provider-aci_{ACI_VERSION}_{osname}_{arch}.zip"
    data = _checked(f"{base}/{name}", f"{base}/terraform-provider-aci_{ACI_VERSION}_SHA256SUMS", name)
    pdir = dest / "mirror" / "registry.terraform.io" / "ciscodevnet" / "aci" / ACI_VERSION / f"{osname}_{arch}"
    pdir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(pdir)
    for p in pdir.iterdir():
        if p.name.startswith("terraform-provider-"):
            p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    (dest / "terraformrc").write_text(terraformrc(dest / "mirror"))
    print(f"== done: {dest}/bin/terraform, provider mirror and terraformrc", flush=True)


def terraformrc(mirror: Path) -> str:
    """Providers come only from the local mirror — never downloaded at run time."""
    return (
        "# written by hiTech Automation AI — providers only from the local mirror\n"
        "disable_checkpoint = true\n"
        "provider_installation {\n"
        "  filesystem_mirror {\n"
        f'    path    = "{mirror}"\n'
        '    include = ["registry.terraform.io/ciscodevnet/aci"]\n'
        "  }\n"
        "}\n"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: terraform_install.py <dest>")
    install(Path(sys.argv[1]))
