# hiTech Automation AI — Installation Guide

FastAPI-based network automation platform (NETCONF / RESTCONF / CLI / XPath /
YANG Explorer, optional agentic AI + RAG). Serves on **port 7071**.

---

## 0. Choose ONE installation method

| | Method A — systemd | Method B — Docker Compose |
|---|---|---|
| Runs as | your user's Python venv + systemd user service | container (host networking) |
| Best for | the main lab VM, development | test laptops, quick evaluation, clean removal |
| Prereqs | python3-venv (or uv) | docker.io + docker-compose-v2 |
| Update | git pull → pip install → restart service | git pull → compose up -d --build |

**Pick one. Never run both on the same machine** — they fight over port 7071.
Switching later is fine: fully stop/disable one before starting the other.

Both methods share the same state directory on the host:
`~/.hitech_automation_ai/` (devices.yaml, RAG index, saved state). It survives
updates, reinstalls, and method switches.

---

## 1. Common first steps (both methods)

```bash
git clone https://github.com/<you>/hitech-automation-ai.git ~/hitech-automation-ai
cd ~/hitech-automation-ai
mkdir -p ~/.hitech_automation_ai
```

Create the device inventory now or later — the app starts fine without it:
`~/.hitech_automation_ai/devices.yaml`. **One format only** (flat *or* pyATS
testbed — the loader auto-detects; they cannot be mixed in one file). See
operation.md §7. Quick flat example with literal lab credentials:

```yaml
devices:
  - name: cat8Kv71
    host: 192.168.89.71
    port_netconf: 830
    port_ssh: 22
    username: expert
    password: 1234QWer!
    device_type: cisco-iosxe
    read_only: false
    default: true          # exactly ONE device may be default
```

Edits to this file never need an app restart — click ↻ Reload in the
Devices panel.

---

## 2. Method A — systemd user service

### 2.1 Python + venv

Ubuntu ships python3 without venv support; install it first (version must
match your python3 — 24.04 = 3.12):

```bash
sudo apt update
sudo apt install python3.12-venv        # 22.04: python3.10-venv
cd ~/hitech-automation-ai
python3 -m venv .softai
source .softai/bin/activate
```

Alternative without apt/sudo — uv (also faster):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
cd ~/hitech-automation-ai
uv venv .softai && source .softai/bin/activate
```

If a venv creation ever fails half-way, `rm -rf .softai` before retrying.

### 2.2 Install packages

```bash
pip install -r build/requirements.txt            # core (device tools, YANG)
pip install -r build/requirements-ai.txt         # OPTIONAL: AI/RAG (chromadb, anthropic)
```

(uv users: `uv pip install -r ...`.) The app starts and serves every route
without the AI extras; AI panels simply report the missing packages.

### 2.3 First run (foreground — verify before daemonizing)

```bash
cd ~/hitech-automation-ai/build
../.softai/bin/python -m uvicorn main:app --host 0.0.0.0 --port 7071
```

Browse to `http://<host>:7071`. Ctrl+C when satisfied.

### 2.4 Create the service

`~/.config/systemd/user/hitech_automation_ai.service`:

```ini
[Unit]
Description=hiTech Automation AI
After=network-online.target

[Service]
WorkingDirectory=%h/hitech-automation-ai/build
ExecStart=%h/hitech-automation-ai/.softai/bin/python -m uvicorn main:app --host 0.0.0.0 --port 7071
Restart=on-failure
RestartSec=3
# credentials as env vars? put them in a chmod-600 file and uncomment:
# EnvironmentFile=%h/.hitech_automation_ai/secrets.env

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now hitech_automation_ai
systemctl --user status hitech_automation_ai
loginctl enable-linger $USER        # keep it running after logout / at boot
```

Note on env-var credentials (`$env:VAR` in devices.yaml): exporting in
.bashrc does NOT reach the service — only `EnvironmentFile=` (above) does.
After editing it: `systemctl --user daemon-reload && systemctl --user restart
hitech_automation_ai`.

### 2.5 Update after git pull

```bash
cd ~/hitech-automation-ai
git pull
source .softai/bin/activate
pip install -r build/requirements.txt            # picks up dependency changes
pip install -r build/requirements-ai.txt         # only if you use the AI extras
systemctl --user restart hitech_automation_ai
systemctl --user status hitech_automation_ai     # confirm "active (running)"
```

State and devices.yaml are untouched by updates.

### 2.6 Uninstall (Method A)

```bash
systemctl --user disable --now hitech_automation_ai
rm ~/.config/systemd/user/hitech_automation_ai.service
systemctl --user daemon-reload
rm -rf ~/hitech-automation-ai                    # includes the .softai venv
rm -rf ~/.hitech_automation_ai                   # ONLY if you want state gone too
```

---

## 3. Method B — Docker Compose

### 3.1 Install Docker (once per machine)

```bash
sudo apt update                                  # REQUIRED first — stale index = 404s
sudo apt install docker.io docker-compose-v2
sudo usermod -aG docker $USER
```

Then **log out and back in** (a new terminal tab is not enough; `newgrp
docker` works for the current shell only). Verify: `docker ps` must print an
empty table with no permission error.

### 3.2 Build and start

```bash
cd ~/hitech-automation-ai/docker
docker compose up -d --build                     # add --build-arg WITH_AI=1 per docker/README if you want AI baked in
docker compose ps                                # STATUS should be "Up"
```

**Never `sudo docker compose up`.** Under sudo, `~` in the bind mount
resolves to **/root**, the container mounts /root/.hitech_automation_ai, and
your devices.yaml is silently invisible. If you already did: `docker compose
down && docker compose up -d` *without* sudo. Verify the mount:

```bash
docker inspect hitech_automation_ai --format '{{json .Mounts}}'
# Source must be /home/<you>/.hitech_automation_ai
```

The container uses host networking — it reaches the lab subnet exactly like
the host does, and the UI is at `http://<host>:7071`.

### 3.3 Update after git pull

```bash
cd ~/hitech-automation-ai
git pull
cd docker
docker compose up -d --build       # rebuilds image, recreates container
docker compose ps                  # confirm Up
docker image prune -f              # optional: drop superseded image layers
```

State and devices.yaml live on the host — untouched by rebuilds.

### 3.4 Logs / restart / stop

```bash
docker compose logs -f             # live logs
docker compose restart             # restart without rebuild
docker compose down                # stop and remove the container
```

### 3.5 Uninstall (Method B)

```bash
cd ~/hitech-automation-ai/docker
docker compose down --rmi all
rm -rf ~/hitech-automation-ai
rm -rf ~/.hitech_automation_ai                   # ONLY if you want state gone too
```

---

## 4. Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `venv ... ensurepip is not available` | `sudo apt install python3.12-venv`, then `rm -rf .softai` and recreate (or use uv) |
| apt install 404 Not Found | stale package index → `sudo apt update`, retry |
| `usermod: group 'docker' does not exist` | docker.io install failed earlier — fix apt, reinstall, re-run usermod |
| `permission denied ... docker.sock` | group not active in this session → `newgrp docker` now, full logout/login for good |
| Devices panel empty | devices.yaml in the wrong place — must be `~/.hitech_automation_ai/devices.yaml` (leading dot, underscores), NOT the repo dir; then ↻ Reload |
| Devices empty under Docker despite correct file | container created with sudo → mount Source is /root/... → `docker compose down && docker compose up -d` without sudo |
| devices.yaml rejected / odd behavior | mixed flat + pyATS formats, duplicate `name:` values, or multiple `default: true` — one format, unique names, one default |
| Env-var credentials not resolving (systemd) | vars must be in the service env: `EnvironmentFile=` in the unit, then daemon-reload + restart — .bashrc does not apply |
| Env-var credentials not resolving (Docker) | add `env_file:` to the compose service pointing at a chmod-600 file |
| Port 7071 already in use | the other install method is still running — stop/disable it (see §0) |
| UI up but device connects fail | host cannot reach the lab subnet — `ping 192.168.89.71` first; DUP! ICMP replies from the CML bridge are harmless |
| AI panels report missing packages | intentional — install the AI extras (§2.2) or rebuild with WITH_AI=1 (§3.2) |

## 5. Update quick reference

| Method | Commands |
|---|---|
| systemd | `git pull` → `pip install -r build/requirements.txt` → `systemctl --user restart hitech_automation_ai` |
| Docker | `git pull` → `docker compose up -d --build` (in docker/) |
