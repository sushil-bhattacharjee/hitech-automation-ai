# hiTech Automation AI

Network automation in one web app: **NETCONF, RESTCONF, CLI, XPath, YANG Explorer and
certificates (PKI)**, with Python and Ansible runners and an optional **AI assistant with
RAG** over network-automation study material. FastAPI, served on port **7071**.

## Try it online — no install

**[software-automation.hitech007.ai](https://software-automation.hitech007.ai)**

- Free, no sign-up: RESTCONF, NETCONF, XPath, YANG and certificates against devices and
  APIs on the public internet, in a temporary workspace of your own.
- Signed in: the AI assistant, Python, Ansible, a workspace that keeps your work, and your
  own lab routers, switches and APIC (with a lab account at
  [lab-automation.hitech007.ai](https://lab-automation.hitech007.ai)).

## Run it yourself

Docker Compose or a Python venv with systemd — see **[INSTALL.md](INSTALL.md)**.

```bash
git clone https://github.com/sushil-bhattacharjee/hitech-automation-ai.git ~/hitech-automation-ai
cd ~/hitech-automation-ai
# then follow INSTALL.md (Method B — Docker Compose — is the quickest)
```

Then open `http://<host>:7071`. Add your devices in the app or in
`~/.hitech_automation_ai/devices.yaml`.

## Documentation

| File | What |
|---|---|
| [INSTALL.md](INSTALL.md) | installation (Docker or systemd), troubleshooting, updates |
| [operation.md](operation.md) | using every feature |
| [ai_architecture.md](ai_architecture.md) | how the AI assistant, agent tools and RAG fit together |
| [build/CHANGELOG.md](build/CHANGELOG.md) | what changed in each version |

## More from hiTech007

- [hitech007.ai](https://hitech007.ai) — training in network automation and agentic AI
- [automation.hitech007.ai](https://automation.hitech007.ai) — CCIE / CCNP Automation study guides and mock exams
- [lab-automation.hitech007.ai](https://lab-automation.hitech007.ai) — your own cloud lab: workstation, CML routers/switches, ACI
- [ccie-docs.hitech007.ai](https://ccie-docs.hitech007.ai) — CCIE Automation lab reference documentation
