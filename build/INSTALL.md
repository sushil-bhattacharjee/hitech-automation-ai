# hiTech Automation AI — Install & Setup

## 0. Fresh install — choose AI or no-AI (v1.47.0+)

The network-automation workspace (NETCONF, RESTCONF, CLI, XPath, and the full
YANG workspace) has **no LLM dependency**. The AI features (AI Chat, agent
tools, RAG) are optional and pull in heavier packages. Pick one:

```bash
git clone <repo> hitech-automation-ai && cd hitech-automation-ai
python3 -m venv .venv && source .venv/bin/activate

# ---- Path A: network automation only (no AI) -----------------------------
pip install -r build/requirements.txt

# ---- Path B: everything, including AI Chat / agent / RAG ------------------
pip install -r build/requirements.txt -r build/requirements-ai.txt
```

Then run it:

```bash
cd build
python -m uvicorn main:app --host 0.0.0.0 --port 7071
# open http://<host>:7071
```

| | Path A (core) | Path B (with AI) |
|---|---|---|
| NETCONF / RESTCONF / CLI / XPath / YANG workspace | ✅ full | ✅ full |
| AI Chat, agent tools, RAG | greyed out with an install hint | ✅ enabled |
| Extra packages | — | `chromadb`, `anthropic` |
| Server starts? | ✅ yes | ✅ yes |

Check which mode you are in:

```bash
curl -s localhost:7071/api/health | python3 -m json.tool
#   "ai_available": false,
#   "ai_import_error": "ModuleNotFoundError: No module named 'chromadb'"
```

**Ollama note:** the Ollama provider needs no extra Python package (it is plain
HTTP), but AI Chat as a whole is gated on the AI extras. Install Path B to use
either Ollama or Anthropic.

---

## 0b. Two ways to RUN it — systemd or Docker (pick one)

Both serve the app on **port 7071** and share the **same state directory**
(`~/.hitech_automation_ai`), so devices, YANG repos and collections are
identical either way. **Run only one at a time** — they would fight over the
port.

### Option 1 — systemd (recommended for development)

Fast: unzip a new build and restart in seconds; no image rebuild.

```bash
# one-time
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/hitech_automation_ai.service <<'EOF'
[Unit]
Description=hiTech Automation AI
After=network-online.target

[Service]
WorkingDirectory=%h/DevnetExpert/mock3/software_ai/build
ExecStart=%h/DevnetExpert/mock3/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 7071
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now hitech_automation_ai
loginctl enable-linger $USER          # keep it running after logout / across reboots

# every upgrade after that
unzip -o hitech_automation_ai.<version>.zip
systemctl --user restart hitech_automation_ai
journalctl --user -u hitech_automation_ai -f
```

### Option 2 — Docker (recommended for distribution / a clean box)

One command, no Python setup at all.

```bash
# core, no AI
docker compose -f docker/docker-compose.yml up -d --build

# with AI (installs chromadb + anthropic into the image)
WITH_AI=1 docker compose -f docker/docker-compose.yml up -d --build

docker logs -f hitech_automation_ai      # → http://<host>:7071
docker compose -f docker/docker-compose.yml down
```

The compose file is configured for a lab:

| Setting | Why |
|---|---|
| `network_mode: host` | the container reaches `192.168.89.x` devices and Ollama exactly as the host does — no NAT, no port mapping |
| `~/.hitech_automation_ai` bind-mounted | your existing `devices.yaml`, secrets, YANG repositories and collections are used as-is; anything written persists on the host |
| `restart: unless-stopped` | **after a reboot the app comes back on its own** — no command needed (Docker itself must start on boot: `sudo systemctl enable docker`). It stays down only if *you* ran `docker compose down`. |
| port **7071** | same as systemd, so bookmarks and scripts don't change |

**Switching between them**

```bash
systemctl --user stop hitech_automation_ai            # before starting the container
# ...or...
docker compose -f docker/docker-compose.yml down      # before starting systemd
```

Keeping both installed is fine — and useful: systemd for fast iteration, Docker
for a reproducible deploy.

## 1. Upgrade from any earlier version

```bash
systemctl --user stop hitech_automation_ai

# Optional backup
cp -r ~/DevnetExpert/mock3/software_ai/build \
      ~/DevnetExpert/mock3/software_ai/build.bak

cd ~/DevnetExpert/mock3/software_ai
unzip -o /path/to/hitech_automation_ai.<version>.zip

source ~/DevnetExpert/mock3/.venv/bin/activate
pip install -r build/requirements.txt            # add -r build/requirements-ai.txt for AI

systemctl --user restart hitech_automation_ai
```

**Upgrading from v1.7.0:** the version-mismatch auto-reload from v1.7 handles cache busting — the page detects the new version and reloads itself. If still stuck, one hard refresh (Ctrl+Shift+R).

**Navigation:** a left sidebar switches between sections. The default view is **Config Mgmt** (direct-execute NETCONF / RESTCONF / CLI / XPath). AI Chat and Docs live under separate nav items. (The old "Classic UI" was removed in v1.8.2.)

## 2. Inventory is upgrade-safe

Your inventory lives **outside** the build directory and is **never touched** by a zip upgrade:

```
~/.hitech_automation_ai/
├── devices.yaml      ← preserved across upgrades
└── audit.log         ← preserved across upgrades
```

The zip only writes into `~/DevnetExpert/mock3/software_ai/build/`. You can verify before each upgrade:

```bash
unzip -l hitech_automation_ai.1.5.0.zip | grep -v '^.*build/' | head
# expected output: nothing (every line should match `build/...`)
```

## 3. Inventory formats

`~/.hitech_automation_ai/devices.yaml` accepts two formats. The loader auto-detects which one you're using.

### Format A — flat list (simplest, recommended for new users)

```yaml
devices:
  - name: cat8Kv71
    host: 192.168.89.71
    port_netconf: 830
    port_ssh: 22
    username: expert
    password: $env:CAT8KV71_PASSWORD    # or plaintext (lab only)
    device_type: cisco-iosxe            # cisco-iosxe | cisco-nxos | cisco-iosxr | juniper-junos
    read_only: false                    # writes allowed when false (default true)
    default: true                       # fallback device when LLM doesn't specify
```

### Format B — pyATS testbed (industry-standard, reusable across Genie / Ansible)

```yaml
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
      cli:
        protocol: ssh
        ip: "%ENV{CAT8KV71}"
        port: 22
      netconf:
        protocol: netconf
        ip: "%ENV{CAT8KV71}"
        port: 830
    custom:                  # hitech-automation-ai extras
      read_only: false
      default: true

  cat8Kv72:
    os: iosxe
    # ... same shape
```

## 4. Passwords via environment variables

Three syntaxes are expanded at load time, in precedence order:

| Syntax | Looks in | Where it appears | Notes |
|---|---|---|---|
| `$secret:VAR_NAME` | `~/.hitech_automation_ai/secrets.yaml` | Whole-string only | **v1.7.0**; recommended for production |
| `$env:VAR_NAME` | `os.environ` | Whole-string only | v1.4.0 shorthand; still works |
| `%ENV{VAR_NAME}` | `secrets.yaml`, then `os.environ` | Anywhere in a string | pyATS standard |

If `secrets.yaml` and an env var both define the same name, **the secrets file wins** (precedence is intentional — matches the Ansible Vault pattern).

### 4a. Environment-variable approach (existing)

Set the variables where the service starts. The drop-in file:

```bash
nano ~/.config/systemd/user/hitech_automation_ai.service.d/secrets.conf
```

```ini
[Service]
Environment="ANTHROPIC_API_KEY=sk-ant-..."

Environment="CAT8KV71=192.168.89.71"
Environment="CAT8KV71_USERNAME=expert"
Environment="CAT8KV71_PASSWORD=1234QWer!"

Environment="CAT8KV72=192.168.89.72"
Environment="CAT8KV72_USERNAME=expert"
Environment="CAT8KV72_PASSWORD=1234QWer!"

Environment="NX9K73=192.168.89.73"
Environment="NX9K73_USERNAME=expert"
Environment="NX9K73_PASSWORD=1234QWer!"
```

Apply:

```bash
systemctl --user daemon-reload
systemctl --user restart hitech_automation_ai
```

Verify systemd sees the vars:

```bash
systemctl --user show hitech_automation_ai -p Environment | tr ' ' '\n' | grep CAT8KV71
# expected: Environment=CAT8KV71=192.168.89.71 (and similar lines)
```

> **Note:** `systemctl show` displays values containing special chars (like `!`) wrapped in quotes. That's just display formatting — the actual value the process receives is unquoted.

### 4b. secrets.yaml approach (v1.7.0, recommended)

Cleaner alternative to systemd env vars — secrets live in a file the service reads directly. No systemd reload required when you rotate a password.

```bash
nano ~/.hitech_automation_ai/secrets.yaml
chmod 600 ~/.hitech_automation_ai/secrets.yaml
```

```yaml
# Plain key: value pairs. Referenced from devices.yaml as $secret:NAME.
cat8Kv71_password: 1234QWer!
cat8Kv72_password: 1234QWer!
nx9K73_password:   1234QWer!
```

In `devices.yaml`:

```yaml
devices:
  - name: cat8Kv71
    host: 192.168.89.71
    username: expert
    password: $secret:cat8Kv71_password
```

After editing `secrets.yaml`, click **↻ Reload** in the Manage Devices panel — no service restart needed. Reload also re-reads `secrets.yaml`.

> **Why chmod 600?** Secrets sit at rest in plain YAML. Tight file permissions are the first line of defence. For higher-assurance environments, source the values from a real vault (HashiCorp Vault, AWS Secrets Manager) into env vars and use `$env:` instead.

## 5. Inventory location override

By default the loader uses `~/.hitech_automation_ai/devices.yaml`. To point elsewhere:

```ini
Environment="INVENTORY_FILE=/etc/netauto/inventory.yaml"
```

## 6. Verify the install

```bash
# Service running, version 1.5.0
curl -s http://localhost:7071/api/chat-config | python3 -m json.tool | grep app_version

# Devices loaded
curl -s http://localhost:7071/api/devices | python3 -m json.tool

# Expected output excerpt:
#   "count": 3,
#   "inventory_path": "/home/sushil/.hitech_automation_ai/devices.yaml",
#   "devices": [
#     { "name": "cat8Kv71", "host": "192.168.89.71", "port_netconf": 830, ... },
#     ...
#   ]
```

Or in the GUI: open the chat drawer, expand the system status bar, look for the `📋 Devices` section showing your inventory.

## 7. Using the device picker

In the main Device Info section, the new "📋 From inventory" dropdown lists everything from your inventory file. Picking a device:

- Fills the **host**, **port**, **username**, and (for CLI transport) **device_type** fields
- **Does not** fill the password — keep typing it, or rely on the agent's NETCONF tools to read it server-side from the inventory
- Re-applies when you switch the transport radio between NETCONF and CLI (the port adjusts 830 ↔ 22 automatically)

For inventory edits made on disk, click `↻` next to the picker or `↻ Reload` in the sysbar's Devices section — no service restart needed.

## 8. Audit log

All agent activity is appended to `~/.hitech_automation_ai/audit.log` as JSON lines:

```bash
tail -20 ~/.hitech_automation_ai/audit.log | jq
# or
curl -s http://localhost:7071/api/agent/audit?n=20 | jq
```

Rotate with `logrotate` if you expect heavy use:

```
# /etc/logrotate.d/hitech_automation_ai-audit
/home/sushil/.hitech_automation_ai/audit.log {
    weekly
    rotate 8
    compress
    missingok
    notifempty
    copytruncate
}
```

## 9. First test — recommended sequence

1. Open the chat panel
2. Verify the sysbar `📋 Devices` section shows your devices (count > 0, no `(empty)` host)
3. In the Device Info section, pick a device from the dropdown — confirm the fields auto-fill
4. Type your password in the password field (the picker won't fill it)
5. Tick **🤖 Agentic** + switch model to `claude-sonnet-4-6` (qwen 7B is unreliable for multi-step agentic flows)
6. Try: `List my devices` → calls `list_devices`, returns the inventory
7. Try: `Get the running config interfaces from cat8Kv71` → calls `get_running_config` with a subtree filter
8. For a write test against `cat8Kv71` (only if `read_only: false`), ask for a config change — the approval modal opens with a diff before commit

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `count: 0` and `devices: []` in `/api/devices` | YAML parse error (check `journalctl --user -u hitech_automation_ai` for warnings) or the env vars aren't set in the service environment |
| Devices listed but `host: ""` or `password_configured: false` | env var is unset; check `systemctl --user show hitech_automation_ai -p Environment` |
| Dropdown empty in the GUI but `/api/devices` returns devices | Browser cache; hard refresh (Ctrl+Shift+R) once after upgrading to v1.7.0 — future upgrades self-heal |
| Agent says "device not in inventory" | Check spelling; the device name is case-sensitive |
| qwen agent produces fake tool-call JSON instead of running them | qwen 7B can't reliably emit tool_calls; use `claude-sonnet-4-6` for agentic work |
| Approval modal never opens | Agent used a read-only tool instead; re-prompt asking explicitly to "propose an edit-config change" |
| `ncclient` connection refused on port 830 | NETCONF not enabled on device (`netconf-yang` on IOS-XE, `feature netconf` on NX-OS), or firewall blocks port 830 |
| RESTCONF returns `404 Not Found` | Either the device hasn't enabled RESTCONF (see Section 11) or the YANG path is wrong — try `restconf_list_capabilities` to see what's actually exposed |
| RESTCONF returns `401 Unauthorized` | Bad credentials, or on IOS-XE the local user doesn't have privilege 15 — `username expert privilege 15 ...` |
| `[RESTCONF connection error] SSLCertVerificationError` | Lab device using self-signed cert; set `restconf_verify_tls: false` in the device entry (already the default) |
| "TransportError: Not connected" once, then succeeds | Normal — v1.7.0 auto-retries this transient flake. If it happens on every call, check device-side: `show netconf-yang sessions` |
| Edit / Delete button greyed out in Manage Devices | Inventory is in pyATS format. Edit `devices.yaml` directly, or migrate to flat format (loses the pyATS-specific keys) |

## 11. Device prerequisites for RESTCONF (v1.7.0)

RESTCONF is HTTPS-based and requires explicit enablement on the device. Defaults assume port 443; override per device with `port_restconf` in `devices.yaml`.

### IOS-XE (Catalyst 8000v, ISR4k, ASR1k, CSR1000v)

```
configure terminal
 ip http server
 ip http secure-server
 ip http authentication local
 aaa new-model
 aaa authentication login default local
 aaa authorization exec default local
 restconf
end
write memory
```

Verify:

```
show platform software yang-management process
 confd            : Running     ← required
 nginx            : Running     ← required for RESTCONF (HTTPS termination)
 ncsshd           : Running     ← required for NETCONF

show running | include ^restconf
 restconf
```

Quick smoke test from the hitech_automation_ai host:

```bash
curl -k -u expert:'1234QWer!' \
     -H 'Accept: application/yang-data+json' \
     https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/hostname
# Expected: {"Cisco-IOS-XE-native:hostname":"cat8Kv71"}
```

### NX-OS (Nexus 9000v)

```
configure terminal
 feature nxapi
 nxapi https port 443
 nxapi use-vrf management
end
copy running-config startup-config
```

Verify:

```
show feature | include nxapi
 nxapi                 1          enabled

show nxapi
 nxapi enabled
 HTTPS Listen on port 443
```

Quick smoke test:

```bash
curl -k -u admin:'1234QWer!' \
     -H 'Accept: application/yang-data+json' \
     https://192.168.89.73/restconf/data/Cisco-NX-OS-device:System/sys-items
```

### Adding a device with RESTCONF

Once the device is configured, add it to `devices.yaml`:

```yaml
devices:
  - name: cat8Kv71
    host: 192.168.89.71
    port_netconf: 830
    port_ssh: 22
    port_restconf: 443           # v1.7.0
    restconf_root: /restconf/data
    restconf_verify_tls: false   # lab default; flip to true in prod
    username: expert
    password: $secret:cat8Kv71_password
    device_type: cisco-iosxe
    read_only: false
```

Reload from the Manage Devices panel. Test from the agent chat:

```
list the YANG modules supported on cat8Kv71 via RESTCONF
```

The agent should call `restconf_list_capabilities` and return a summary with OpenConfig modules highlighted.

## 12. v1.8.0 — Left navigation & Configuration Management

### Left nav

Three destinations down the left side:

- **Config Mgmt** (default) — direct-execute transports (NETCONF / RESTCONF / CLI / XPath)
- **AI Chat** — pointer to the existing chat drawer
- **Docs** — inline references

Click the **≡** button at the top of the sidebar to collapse it (38px width); the main content shifts to use the freed space. Collapsed/expanded state and active section persist in localStorage.

### Configuration Management — four tabs

Direct-execute transports, no LLM in the loop. Each tab targets a different transport / workflow.

#### NETCONF

- **Jinja2 template mode:** Variables (YAML) → Jinja2 template → Render → Send. Click *Render* to preview the XML before sending; *Send* renders then ships in one click.
- **XML payload mode:** Paste raw XML, pick device, send. For ad-hoc payloads when you already have the XML.

#### RESTCONF

- **https-restconf** (Postman-style):
  - Top bar: method + URI + Send button
  - Six tabs: Params, Headers, Vars, Auth, Payload, Response
  - **Auth → Use inventory device:** picks credentials from `devices.yaml`. If the URI starts with `/` or doesn't include `http`, the device's base URL is prepended automatically.
  - **Vars:** Jinja2 variables applied to URI, headers, payload before sending. Useful for parameterized tests.
  - Response tab pretty-prints JSON automatically.
- **curl-restconf:** Paste a full curl command (multi-line with `\` continuation works). The server runs it via subprocess. Captures stdout, stderr, exit code, and timing. Only commands starting with `curl` are accepted — defence-in-depth against arbitrary command execution.

#### CLI

- **Jinja2 template mode:** Same pattern as NETCONF Jinja2, but sends via Netmiko instead of NETCONF.
- **Raw CLI mode:** Paste commands one per line, pick device, send via Netmiko. Returns the device output as-is.

#### XPath

Direct NETCONF XPath query — no model in the loop. Pick a device, choose source (operational state or running-config), type an XPath expression, get raw XML back. Example XPaths:

```
/bgp-state-data/neighbors/neighbor[neighbor-id='10.44.10.1']
/interfaces/interface[name='GigabitEthernet1']/oper-status
/native/router/router-bgp
```

### Stop button & run-id badge

When you click Send in the AI Chat drawer with Agentic mode on, the composer now shows two extras:

- **⏹ Stop** — clickable while the run is in progress; click to cancel at the next iteration boundary. Any tool call already in flight will finish; the loop exits with `stopped_reason="cancelled"` immediately after.
- **Run-id badge** — shows the active `run_id` while the run is in progress, useful for correlating with `journalctl --user -u hitech_automation_ai` server-side logs.

Both disappear when the run completes.

### RAG-in-agentic

When you have both **Agentic** and **Use RAG** checked, the server now pre-fetches the top-5 corpus chunks for your prompt and prepends them to the system prompt before the agent loop starts. The agent's `search_corpus` tool is still available for follow-up queries — but the corpus is **always** in context now, regardless of whether the model proactively searches it.

This was a deliberate change from v1.7 behavior, where "Use RAG" + Agentic just exposed `search_corpus` as a tool the LLM could choose to call (or not). Small models often chose not to.

### Troubleshooting (v1.8)

| Symptom | Fix |
|---|---|
| Left nav doesn't appear | Hard refresh (Ctrl+Shift+R). The version-mismatch auto-reload usually handles this, but on first install from v1.7 you may need a manual refresh. |
| Stop button doesn't appear | The chat drawer hasn't been opened yet on this page load; close the drawer once, reopen it, then click Send. |
| `curl-execute` returns "curl binary not found" | Install curl: `sudo apt install curl` on Ubuntu. |
| RESTCONF Postman-style "verify TLS" failures | Lab devices use self-signed certs. Leave "Verify TLS" unchecked. |
| XPath returns empty XML but Yang library shows the path exists | The XPath syntax may be subtly wrong (Cisco's XPath support is partial). Try the equivalent subtree filter via the NETCONF tab. |
| RAG-in-agentic doesn't seem to fire | Check the server log for "agent: RAG pre-fetch added N chunks". If you see "RAG pre-fetch failed", the corpus may not be loaded — check the RAG status in the AI Chat status bar. |
