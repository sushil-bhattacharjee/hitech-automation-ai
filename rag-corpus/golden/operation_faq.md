# hiTech Automation AI — Operation FAQ

Task-oriented how-to for every transport and sub-mode, with minimal working
examples and the common mistakes. Lab devices used in examples:

| Name | Host | Type | NETCONF | RESTCONF | SSH |
|---|---|---|---|---|---|
| cat8Kv71 | 192.168.89.71 | cisco-iosxe | 830 | 443 | 22 |
| cat8Kv72 | 192.168.89.72 | cisco-iosxe | 830 | 443 | 22 |
| nx9K73 | 192.168.89.73 | cisco-nxos | 830 | 443 | 22 |
| apic1 | 192.168.89.95 | cisco-aci (REST) | — | 443 | — |

The app has five transports in the left navigation — **NETCONF, RESTCONF, CLI,
XPath, Python** — plus an **AI Chat** assistant. Each transport has its own
collection tree for saving requests.

---

## NETCONF

### How do I run a NETCONF get-config?
NETCONF → choose **get-config**, pick the device, supply a filter as XML in the
payload, Send. Well-formed XML is treated as a **subtree filter** automatically.

### How do I do subtree filtering in NETCONF?
Put the subtree filter XML in the payload. Example — fetch just the interfaces:
```xml
<filter type="subtree">
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <interface/>
  </native>
</filter>
```
Returns only that branch of the config.

### How do I do XPath filtering in NETCONF (surgical leaf query)?
Use the agent tool `get_state` / `get_running_config` with `filter_type=xpath`,
or the **XPath** transport for on-device queries (see XPath section). XPath is for
single counters/leaves; subtree is for whole sections.

### How do I render a Jinja2 template for NETCONF?
NETCONF → **Jinja2 template** sub-mode. Put variables (YAML or JSON) in the vars
box and the template in the template box. **Render** builds the XML; **✔ Validate**
checks it against the device (`<validate>`) without pushing; **Send** applies it.

### Common mistake: device write runs unexpectedly
NETCONF/CLI saved collection items **load only** — clicking one fills the editor
but does **not** push. You must press Send/Validate yourself. (Only XPath and
curl/python auto-run on click.)

### Known-good fact: OSPF YANG path on IOS-XE
The correct path on cat8Kv is `Cisco-IOS-XE-native:native/router/router-ospf`.
The standalone OSPF module returns 404 — use the native path.

---

## RESTCONF

RESTCONF has three sub-modes: **https-restconf** (build a request),
**curl-restconf** (paste a shell/curl snippet), **python-restconf** (run Python).

### How do I build an https-restconf GET?
RESTCONF → **https-restconf**. Set method GET, URL (may contain `{{vars}}`),
optional params/headers/auth, Send. Example URL:
```
https://{{cat8Kv71}}/restconf/data/Cisco-IOS-XE-native:native/router/bgp=65001/neighbor
```

### How do I use environment variables on the https pane?
Pick an **Environment** from the dropdown. Any `{{VAR}}` in the URL, headers,
body, or auth is substituted from that environment before sending.

### How do I pretty-print a JSON payload?
On the Payload tab click **⧉ Pretty-print**. It reformats the JSON in place;
`{{vars}}` are preserved; invalid JSON shows an inline error.

### How do I filter an https-restconf JSON response with jq?
Use the **jq filter** bar under the response. Example filter:
```
.imdata[].fvSubnet.attributes.dn
```
Toggle `-r` for raw output. Engine = Browser (jq.wasm) or Server (system jq).

### Why is my response missing — only headers I set should be sent (v1.28.0)
By default https-restconf sends **only the headers you set** — no automatic
`Accept: application/yang-data+json`. For IOS-XE convenience, tick **"Add
RESTCONF default headers (IOS-XE)"**. For APIC/ACI leave it off (ACI isn't YANG).

### How do I use environment variables in curl-restconf? (v1.28.0)
Pick an **Environment** on the curl pane. Then both forms work:
- `{{APIC_HOST}}` — substituted into the command before running.
- `$APIC_HOST` — the env var is injected into the shell, so `$VAR` resolves too.

```bash
curl -sk "https://{{APIC_HOST}}/api/class/fvBD.json" \
  -H "Cookie: APIC-cookie=$APIC_COOKIE" | jq -r '.imdata[].fvBD.attributes.name'
```

### How do I use environment variables in python-restconf? (v1.28.0)
Pick an **Environment**, then read with `os.getenv`. Two equivalent sources:

| Set in… | Read in code |
|---|---|
| 🔑 Environment variables box (`test=PRINT_ME_ENV`) | `os.getenv("test")` |
| Environment dropdown (v1.28.0) | `{{test}}` substituted, **or** `os.getenv("test")` (also injected) |

**Minimal working example:**
```python
import os
print(os.getenv("test"))
```

### Common mistake: os.getenv returns nothing / NameError
```python
print(f"{os.getenv(test)}")     # WRONG
```
Two bugs: (1) `import os` is missing; (2) `test` is a bare variable — you want the
string `"test"`. Fix:
```python
import os
print(os.getenv("test"))        # CORRECT
```

### How do I run a curl with a pipe to jq?
The curl pane runs through `bash -lc`, so pipes work — but you must actually call
`jq`:
```bash
curl -sk https://{{cat8Kv71}}/restconf/... -H "Accept: application/json" \
  | jq -r '.["Cisco-IOS-XE-native:native"].hostname'
```
**Common mistake:** piping to a bare filter string without `jq`:
```bash
... | '.imdata[].dn'            # WRONG — shell tries to run the string; fails on stderr
... | jq -r '.imdata[].dn'      # CORRECT
```
curl still dumps full output, so the missing `jq` looks like it "worked" — check
stderr.

### jq: keys with colons or dashes
Bracket-quote them: `.["Cisco-IOS-XE-bgp:neighbor"]` or `."bd-items"`. Bare
`.key` only works for plain identifiers.

---

## APIC / ACI (via RESTCONF panes)

APIC uses the **ACI REST API** (`/api/aaaLogin.json`), not YANG/RESTCONF in the
IOS-XE sense. Do **not** add a YANG `Accept` header.

### How do I log in to APIC and run a query (one paste, curl)?
The login token is a cookie that expires (~10 min). Best practice: log in and
query in one script so the token is always fresh.
```bash
APIC={{APIC_HOST}}
COOKIE=$(curl -sk "https://$APIC/api/aaaLogin.json" \
  -d '{"aaaUser":{"attributes":{"name":"{{APIC_USERNAME}}","pwd":"{{APIC_PASSWORD}}"}}}' \
  | jq -r '.imdata[0].aaaLogin.attributes.token')

curl -sk "https://$APIC/api/class/fvBD.json?query-target=subtree&target-subtree-class=fvSubnet&query-target-filter=eq(fvSubnet.ip,\"10.1.7.1/24\")" \
  -H "Cookie: APIC-cookie=$COOKIE" | jq -r '.imdata[].fvSubnet.attributes.dn'
```

### How do I log in to APIC with python (Session keeps the cookie)?
```python
import requests, urllib3, os
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
H, U, P = os.environ["APIC_HOST"], os.environ["APIC_USERNAME"], os.environ["APIC_PASSWORD"]
s = requests.Session(); s.verify = False
s.post(f"https://{H}/api/aaaLogin.json",
       json={"aaaUser": {"attributes": {"name": U, "pwd": P}}}).raise_for_status()
r = s.get(f"https://{H}/api/class/fvBD.json")
print(r.status_code); print(r.text)
```

### APIC aaaLogin payload — correct JSON
```json
{ "aaaUser": { "attributes": { "name": "{{APIC_USERNAME}}", "pwd": "{{APIC_PASSWORD}}" } } }
```
**Common mistakes:** bare words instead of quoted strings (`"name": APIC_USERNAME`
is invalid JSON); using GET instead of **POST**; forgetting `{{ }}` so vars never
substitute.

---

## CLI

CLI has three sub-modes: **Jinja2 template**, **Raw CLI**, **Netmiko Interactive**.

### How do I push raw CLI config?
CLI → **Raw CLI**, pick the device, type the commands, choose the operation
(config vs exec), Send (via Netmiko).

### How do I run a command that asks for confirmation (reload, no username)?
CLI → **Netmiko Interactive**. The device must be `read_only: false`.
1. Pick the device → **▶ Open session**.
2. Type the command (e.g. `reload`) → Enter.
3. The terminal shows the prompt, e.g. `(y/n)? [n]` or `[confirm]`.
4. Type your answer (`y` / press Enter) → Send.
5. A confirmed `reload` drops the SSH session — reported cleanly.

Example — delete a username on IOS-XE (prompts `[confirm]`):
```
no username test1
[confirm]        <- type y / Enter
```
Example — NX-OS reload (prompts unsaved-config warning then (y/n)):
```
reload
This command will reboot the system. (y/n)?  [n]   <- type n to abort, y to reload
```

### Common mistake: ReadTimeout / "Pattern not detected: hostname#"
That happens when a normal Raw-CLI send hits an interactive prompt it can't
answer. Use **Netmiko Interactive** for those commands instead.

### Common mistake: Interactive blocked (403)
The device is `read_only: true`. Set `read_only: false` in
`~/.hitech_automation_ai/devices.yaml` and click ↻ Reload.

---

## XPath

On-device XPath queries with server-side and client-side filtering.

### How do I run an XPath query?
XPath → pick device, choose source (state/config), type the expression, Run.
Example (IOS-XE, **unprefixed**):
```
/native/ip/access-list
```

### Known-good fact: XPath on IOS-XE is unprefixed
Use `/native/ip/access-list`, **not** `/Cisco-IOS-XE-native:native/...`.
Namespace prefixes cause `RPCError: invalid namespace prefix`.

### How do I filter the XPath result further (client-side)?
Use the **XPath filter** box under the Result pane (real lxml XPath 1.0 —
predicates `[]`, `//`, `@attr`, `contains()`, `text()`, `count()`, etc.). Default
is namespace-ignoring (unprefixed just works); tick "namespace-aware" to use
declared prefixes.

### How do I turn the result into a table?
Use **Extract fields → table**: set the repeating row element + the columns to
pull. Saved with the query and re-applied when you reopen it.

---

## Python (multi-file)

### How do I run a Python script?
Python → write/paste in the editor → Run. Multi-file projects supported (add
files, set the entry file). Save the whole project as one collection item.

### How do I set environment variables for the Python runner?
Use the 🔑 Environment variables box (`KEY=VALUE` per line), read with
`os.getenv("KEY")`. The Environment dropdown (v1.28.0) also injects into
`os.environ`. Pane box wins over the Environment on a name clash.

---

## Collections (all transports)

### How do I save a request?
**💾 Save →** opens a folder picker: click a folder, name it, Save. Or right-click
a folder → Save current here. Each transport has its own collection tree.

### What happens when I click a saved item?
- **RESTCONF** — loads into the builder (curl/python auto-run).
- **NETCONF / CLI** — **load only** (review, then Send/Validate).
- **XPath** — auto-runs the query, then auto-applies saved filters.
- **Python** — loads the multi-file project (then press Run).

### Are my response filters saved?
Yes. RESTCONF saves its jq filter; XPath saves the XPath-filter + Extract-fields
config — both restored/re-applied when you reopen the item.

---

## Response viewer (all panes)

JSON/XML responses render VS Code-style: line numbers, indent guides, **folding**
(click a caret; ⊟ collapse-all / ⊞ expand-all), **bracket/tag-pair hover**, and
**🔎 Find** (case + regex/wildcard toggles; reveals matches inside folded nodes).
**📋 Copy** copies the raw text.

---

## AI Chat assistant

### How do I ask the assistant to investigate live device state?
Enable **🤖 Agentic** mode. The model calls read-only tools
(`run_show_command`, `get_state`, `search_corpus`, `describe_device`, …) and shows
every tool call in the trace. Combine with **📚 RAG** to ground answers in this
corpus, and pick **local Ollama** or **cloud Claude** per message.
