# hiTech Automation AI — Operation Guide

Every module, with at least one worked example against the lab device
`cat8Kv71` (192.168.89.71, IOS-XE, NETCONF 830 / RESTCONF 443).

Navigate with the left sidebar. **Config Mgmt** modules execute directly — no
LLM in the loop. **Assistant** modules (AI Chat) require the optional AI install
(see INSTALL.md §0).

---

## 1. NETCONF

Direct NETCONF operations against an inventory device.

**Example — read the running config of one interface**

1. **Device:** `cat8Kv71`
2. **Operation:** `get-config`
3. Paste the subtree filter:

```xml
<native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
  <interface>
    <GigabitEthernet>
      <name>2</name>
    </GigabitEthernet>
  </interface>
</native>
```

4. **Send** → the reply pane shows the interface's running config.

Jinja2 templating is available on this pane: put `{{ intf }}` in the payload and
supply variables as YAML or JSON, then **Render** before sending.

---

## 2. RESTCONF

Postman-style RESTCONF client with collections, environments and jq filtering.

**Example — fetch OSPF process 1**

1. **Method:** `GET`
2. **URL:** `https://{{host}}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf=1`
3. **Auth:** `inventory` → `cat8Kv71` (credentials resolved from your inventory)
4. **Headers:** `Accept: application/yang-data+json`
5. **Send** → status, headers and the JSON body.
6. Filter the body with jq: `.["Cisco-IOS-XE-ospf:ospf"].network[].ip`

Save the request into a collection folder to re-run it later. Use an
**Environment** to define `{{host}}` once and switch devices without editing URLs.

---

## 3. CLI

Interactive Netmiko sessions — the device's own CLI, in the browser.

**Example — check interface status**

1. **Device:** `cat8Kv71`
2. Type: `show ip interface brief`
3. **Send** → parsed output in the pane.
4. Follow up with `show running-config interface Gi2` in the same session
   (the connection stays open, so `enable`/config context is preserved).

---

## 4. XPath

Direct NETCONF XPath query — returns just the matching leaves. A surgical
alternative to subtree filters.

**Example — all Gigabit interfaces that are UP and passing traffic**

1. **Device:** `cat8Kv71`
2. **Source:** `operational state (<get>)`
3. **Expression:**

```
/interfaces/interface[starts-with(name,"Gigabit")][admin-status="if-state-up" and oper-status="if-oper-state-ready"][statistics/in-octets>0 or statistics/out-octets>0]
```

4. **Run XPath query** → matching XML.
5. **Extract fields → table** to turn it into columns:
   - Row element: `interface`
   - Columns:
     ```
     name       = name
     in-octets  = statistics/in-octets
     out-octets = statistics/out-octets
     ```

> This box takes a **raw XPath string, not XML**. If you paste an expression
> copied out of an `<rpc>` (`in-octets&gt;0`), it is auto-decoded to `>` for you.

Save frequently-used queries into project folders (XPath Collections).

---

## 5. Python

Run Python against the device from the browser — with the inventory already
wired in.

**Example — ncclient one-liner**

```python
from ncclient import manager
with manager.connect(host=DEVICE.host, port=830, username=DEVICE.username,
                     password=DEVICE.password, hostkey_verify=False,
                     device_params={"name": "csr"}) as m:
    print(m.get_config(source="running").data_xml[:500])
```

Pick the device from the dropdown; `DEVICE` is injected. `ruff` lints the pane
as you type.

---

## 6. YANG workspace

Four sub-tabs: **Repo → Explore-YANG → RESTCONF-YANG / NETCONF-YANG**.

### 6a. Repo — get the models onto disk

**Example — pull every schema from the device**

1. **NETCONF** tab → device `cat8Kv71` → **Check device connectivity**
2. **Get schema list** → ~577 schemas appear.
3. **Select all** → **Download selected schemas** → a repository is created
   (name it when prompted, e.g. `cat8Kv71-netconf`).
4. **Check dependencies** → green means every import resolves.
5. **+ New set** → `cat8Kv71-netconf-module` → **Add entire repository** →
   **Validate YANG modules**.

Other import sources on the same tab: **Upload** (.yang files), **SCP** (copy
`*.yang` from any SSH host), **Git** (sparse-clone a vendor directory, e.g.
`https://github.com/YangModels/yang.git`, branch `main`, dir
`vendor/cisco/xe/1771`).

> If a module was added twice at different revisions, hit **Delete older
> duplicate revisions** — two revisions of the same module break pyang's
> resolution.

### 6b. Explore-YANG — browse the schema

**Example — find the BGP container under native**

1. **YANG set:** `cat8Kv71-netconf-module`, **Module:** search `native` →
   `Cisco-IOS-XE-native`
2. **Load module → tree** (Depth: unlimited)
3. In the find box type `//bgp` → results list → click `/native/router/bgp`.
   - Path-aware search: `bgp` (substring), `//bgp` (named bgp at any depth),
     `/native/router/bgp` (absolute), `router/bgp` (suffix), `/native/*/bgp`
     (wildcard segment).
4. Click the node → **Node detail** shows type, key, config/read-only, must/when,
   module, namespace, XPath, plus the **RFC 7950 reference** for that statement.
5. **📄 View text** opens the raw `.yang` source with line numbers.
6. **ⓘ Icon legend** explains every icon and badge.

### 6c. RESTCONF-YANG — generate and run REST APIs

**Example — OpenAPI for router-ospf, then run a GET**

1. In Explore-YANG select `/native/router/router-ospf`.
2. **⚡ Generate API(s)** → an **OpenAPI 3.0.3** spec for the node *and its whole
   subtree* (~50 resources), grouped View / Add / Replace / Modify / Remove.
   Browse it in Swagger-UI; **⬇ JSON / ⬇ YAML** to download.
3. Or use **API operations** in the detail panel: ➕ the `GET` row → it lands in
   the **RESTCONF-YANG** tab.
4. There: pick device `cat8Kv71`, **Format** `JSON`, mode **HTTPS**, replace any
   `{key}` placeholders, **▶ Run** → status line + pretty-printed body.
   Switch mode to **curl** to see and run the equivalent shell command.

### 6d. NETCONF-YANG — build and run RPCs from the tree

**Example — get counters of every UP Gigabit interface**

1. **Module loader:** set `cat8Kv71-netconf-module`, module
   `Cisco-IOS-XE-interfaces-oper` → **Load module → tree**.
2. In the tree, under `interfaces/interface`:
   - `name` (the key) → leave empty for *all entries*, or enter
     `starts-with(name,"Gigabit")`
   - `admin-status` → `if-state-up` (dropdown)
   - `oper-status` → `if-oper-state-ready` (dropdown)
   - tick `statistics/in-octets` and `statistics/out-octets`
3. **Operation:** `get`, **Filter type:** `xpath`, **XPath style:** `no prefix`,
   **compare with:** `or`
4. **Build RPC** →

```xml
<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
  <get>
    <filter type="xpath" select='/interfaces/interface[admin-status="if-state-up" and oper-status="if-oper-state-ready"]'/>
  </get>
</rpc>
```

5. **▶ Run RPC** → the reply renders as a **collapsible XML tree**: fold each
   element, set the depth, search with prev/next, copy any single subtree.
   Repeated siblings (`<interface>`) are colour-coded so entries are easy to tell
   apart.
6. **📋 Copy XPath** copies just the expression, XML-unescaped — paste it straight
   into the XPath module or your Python.
7. **Filter / extract from the device reply** runs real XPath 1.0 against the
   reply, client-side, or extracts a table.

Switch **Filter type** to `subtree` for a classic skeleton filter; choose
`edit-config` to build a `<config>` payload from the values you typed (read-only
nodes are refused, as they should be).

---

## 7. AI Chat *(optional — Path B install)*

Agentic assistant with tool access to the same transports, plus RAG over the
`rag-corpus/`.

**Example**

> "Show me which interfaces on cat8Kv71 are down, then explain what `must` means
> in the BGP model."

The agent picks the transport, runs the query, and cites the RAG corpus for the
YANG question. Destructive operations require explicit approval.

If AI Chat is greyed out, you installed Path A — see INSTALL.md §0.

---

## 8. Docs

The in-app documentation viewer (this file and the install guide).

---

## Where state lives

```
~/.hitech_automation_ai/
├── devices.yaml     ← inventory (never touched by a zip upgrade)
├── secrets.yaml     ← optional password store
├── audit.log        ← every executed operation
├── yang/
│   ├── repos/       ← downloaded .yang files
│   ├── sets.json    ← module sets
│   └── apis.json    ← collected API operations
├── collections/     ← RESTCONF collections
└── xpath/           ← saved XPath queries
```
