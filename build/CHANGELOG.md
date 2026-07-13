# CHANGELOG

## hitech_automation_ai.1.48.1 — 2026-07-13

### Fixed — issue-1: a multi-line XPath returned an empty `<data/>`
The XPath textarea preserves newlines and indentation. An expression typed
across several lines was sent to the device **with the newline still in it**,
and IOS-XE answered with an empty `<data xmlns="…"/>`. Whitespace between XPath
tokens is insignificant, so `/api/netconf-xpath` now **normalizes the
expression** first (collapsing newlines and stray indentation, while leaving
whitespace *inside quoted literals* untouched).

### Fixed — issue-2: the exported script had an unterminated string literal
The same embedded newline landed inside the generated Python:

```python
xpath_filter = (
    '[oper-status="if-oper-state-ready"]
    [v4-protocol-stats/out-pkts >0 ...]'      # SyntaxError
)
```

The generator now normalizes the XPath before emitting it, so the literal is
always well-formed. Every generated variant is asserted to parse as valid
Python.

### Fixed — issue-3: editing the credential defaults had no effect (auth failed)
The generated `Device.__init__` guarded on `if host and username and password:`.
Calling `Device()` leaves `host=None`, so the guard was **False** and it fell
through to the environment variables — silently ignoring credentials edited into
the signature, and failing with `AuthenticationException`.

`Device` now resolves each field independently — *anything you pass wins, and
whatever you leave as `None` comes from the environment*:

```python
self.host     = host     or os.environ.get("CAT8KV71_HOST", "192.168.89.71")
self.username = username or os.environ.get("CAT8KV71_USER")
self.password = password or os.environ.get("CAT8KV71_PASS")
```

…and it now **fails loudly** with a clear message when no credentials are found
anywhere, instead of attempting the connection and dying inside ncclient.


## hitech_automation_ai.1.48.0 — 2026-07-13

### Added — 🐍 Export → Python (XPath module **and** NETCONF-YANG)
Turns whatever you built on screen into a **complete, runnable ncclient
script** — copy it into your own code and it works as-is.

- **XPath module**: the query + the *Extract fields → table* columns become the
  script's filter and its extraction loop.
- **NETCONF-YANG**: follows the Operation and Filter type you selected —
  `xpath`, `subtree`, or `edit-config`.

| Filter type | Source | Generated call |
|---|---|---|
| xpath | get | `session.get(filter=("xpath", xpath_filter))` |
| xpath | get-config | `session.get_config(source="running", filter=("xpath", …))` |
| subtree | get / get-config | `subtree_filter = """…"""` + the matching call |
| edit-config | — | `session.edit_config(target="running", config=config)` |

Shaped after real working scripts:
- **`Device.__init__` takes explicit args OR falls back to environment
  variables** (`CAT8KV71_HOST/_USER/_PASS`) — env is the default, no Vault.
- `session = manager.connect(...)` at module level.
- The **raw XML dump is commented out** (replies can be enormous) — uncomment
  when you want it; only the extracted table prints by default.
- Namespace dict + `xpath_extract` as named variables; a per-column
  `entry.find(...)` with an **"N/A" fallback** for optional elements.
- Long XPath expressions are split into implicitly-concatenated chunks at the
  `][` boundaries so they stay readable.
- Subtree exports carry a comment showing where to do the **local filtering**
  that subtree cannot express (OR / numeric comparisons).
- `session.close_session()` commented at the end.

Copy / Download .py from the modal. New `tools/py_export.py` (one generator,
two callers, so they cannot drift) and `/api/export/python`.
Every generated variant is verified to parse as valid Python.


## hitech_automation_ai.1.47.4 — 2026-07-13

### Fixed — leaf icon, and deprecated/obsolete colours
- **The leaf icon is now actually a leaf**: a proper blade with a darker midrib,
  instead of the thin crescent it was. `leaf-list` is the same blade, doubled.
- **status: deprecated is yellow, status: obsolete is red.** They were both
  rendering plain green because the recolor regex still targeted `#54a832` — a
  colour that no longer exists anywhere in the v1.47.1 icon set, so it replaced
  nothing. Recolouring now uses the current palette (`#8ac53e` blade,
  `#5f9224` midrib) and is applied in the tree as well as the legend;
  `deviation: not-supported` is grey.


## hitech_automation_ai.1.47.3 — 2026-07-13

### Fixed — Device reply had scrollbars instead of the RPC pane's resize grabber
- `showXml()` correctly set `class="xmlview resizable xt"` — and then
  `xtBuild()` immediately ran **`mountEl.className = 'xt'`**, which **wiped the
  `resizable` class**. So the reply pane could only scroll while the RPC
  textarea (a native `<textarea>`) kept its drag corner. The v1.46.1 "fix"
  commented the line above and never checked the line below; this is the real
  one: `classList.add('xt')` instead of replacing all classes.
- The reply `<pre>` also gets an explicit `resize: both`, and both panes now
  share the same height (340px) and minimum, so they line up and resize
  identically.


## hitech_automation_ai.1.47.2 — 2026-07-12

### Changed — one Docker setup, lab-ready, with the same AI choice as pip
- **Deleted `build/Dockerfile` and `build/docker-compose.yml`** — pre-rename
  leftovers (container still called `netconf-sender`) that copied only `main.py`
  + `templates/`, so the image would crash with
  `ModuleNotFoundError: No module named 'tools'`. They were broken and
  misleading; `docker/` is the only Docker setup now.
- **`docker/` reworked for a real lab:**
  - **port 7071** (was 8000) — same as the systemd install, so nothing else
    changes.
  - **`network_mode: host`** — the container reaches `192.168.89.x` devices and
    Ollama exactly as the host does; no NAT, no port mapping.
  - **`~/.hitech_automation_ai` bind-mounted** — your existing devices.yaml,
    secrets, YANG repositories, collections and audit log are used as-is, and
    are shared with a systemd install.
  - **`WITH_AI=1` build arg** — the container honours the same AI / no-AI choice
    as pip:
    ```
    docker compose -f docker/docker-compose.yml up -d --build            # core
    WITH_AI=1 docker compose -f docker/docker-compose.yml up -d --build  # + AI
    ```
  - `restart: unless-stopped` — the app comes back by itself after a reboot.

### Docs
- **INSTALL.md §0b — "Two ways to RUN it — systemd or Docker (pick one)"**:
  the full unit file for systemd (with `loginctl enable-linger`), the Docker
  one-liners, a table explaining each compose setting, how to switch between
  them, and the warning that both bind 7071 so only one may run at a time.


## hitech_automation_ai.1.47.1 — 2026-07-12

### Changed — icon set and legend redrawn to match Cisco YANG Suite
- All 15 node icons redrawn as **original SVG** in YANG Suite's visual style:
  circular-target *action*, green asterisk *anydata*, `</>` *anyxml*, arrow
  *case*, forked *choice*, blue open-folder *container*, bracket *input* /
  *output*, *leaf* and stacked *leaf-list*, *list* lines, three-circle *module*,
  gift-box *notification*, envelope *rpc*, 3-D cube *submodule*. (Cisco's own
  assets are under their EULA and are **not** copied.)
- The **Tree Icon Legend** popup now matches Cisco's card: cyan header bar,
  section bands (Node Icons / Node Support / Node Badges), striped rows.
- The tree uses the same icon set, so node icons update everywhere.

### Docs
- **INSTALL.md**: new §0 "Fresh install — choose AI or no-AI", documenting the
  two pip paths, what each gives you, how to check `/api/health` for
  `ai_available`, and the Docker route.
- **operation.md**: rewritten as a complete operation guide — **every module**
  (NETCONF, RESTCONF, CLI, XPath, Python, the four YANG sub-tabs, AI Chat, Docs)
  with at least one worked example against `cat8Kv71`, plus a map of where state
  lives on disk.


## hitech_automation_ai.1.47.0 — 2026-07-12

### Fixed — Build RPC failed silently
- With values filled but the list **key left empty**, the builder produced
  `[name={name}]`, hit its own placeholder guard, and aborted — but the
  explanation was written to the **Explore tab's** status line, invisible from
  NETCONF-YANG. The RPC pane just stayed empty with no message anywhere.
- **An empty list key now means "all entries"** — the predicate is simply
  omitted, so the filter builds:
  `/interfaces/interface[admin-status="if-state-up"][statistics/in-octets>0]`.
- Every bail in `collectCfgs()` is now reported in **both** status lines, so it
  can't fail silently again.

### Changed — AI is now genuinely optional (install-time choice)
Previously `main.py` hard-imported `rag_retriever` (→ chromadb) and the LLM
providers (→ anthropic). A user who wanted no AI still had to install them —
and without them the server **would not start at all**:
`ModuleNotFoundError: No module named 'chromadb'`.

```
Core only (no AI):   pip install -r requirements.txt
With AI:             pip install -r requirements.txt -r requirements-ai.txt
```

- Imports are guarded; `LLM_AVAILABLE` / `RAG_AVAILABLE` / `AI_AVAILABLE` flags
  are exposed on `/api/health`.
- The **AI Chat** entry point is greyed out with a tooltip naming the missing
  package and the exact install command, instead of failing at request time.
- **chromadb** and **anthropic** moved to the new **`requirements-ai.txt`**.
- Verified by blocking both packages at import time: the app starts, reports
  `ai_available: false`, and **all 108 routes** — NETCONF, RESTCONF, CLI, XPath,
  the whole YANG workspace — remain registered and functional.


## hitech_automation_ai.1.46.2 — 2026-07-12

### Fixed — `RPCError: Invalid name: &gt;0` when reusing an XPath in the XPath tool
An XPath copied out of an `<rpc>`'s `select="…"` attribute carries **XML
entities** with it (`in-octets&gt;0`). The XPath tool takes a **raw XPath
string, not XML**, so it forwarded `&gt;0` to the device, which rightly refused
it. Two fixes, from both ends:
- **📋 Copy XPath** button on the RPC pane copies **just the expression,
  XML-unescaped** (and re-joins the multi-line union) — paste it straight into
  the XPath tool, or into Python.
- **The XPath tool auto-decodes XML entities** on paste/typing (and once more
  before sending), showing a one-line note: *"XML entities decoded — this box
  takes a raw XPath, not XML."* The confusion can't bite again.

### Fixed — issue-1: Node detail stayed empty while working in the tree
- Ticking a checkbox or typing a value now **also selects that node** (focus and
  change both select), so Node detail, the RFC reference and the Generated paths
  reflect what you are actually working on. The empty-state text now says how:
  *"Click a node in the tree to see its properties, RFC reference and generated
  paths."*


## hitech_automation_ai.1.46.1 — 2026-07-12

### Changed — Device reply tree polish
- **2-space indent** (was 4). The dotted indent rails already carry the
  structure, so the extra width was wasted.
- **Repeated same-named siblings are colour-coded.** When a container holds
  several children with the same element name (`<interface>`, `<neighbor>`,
  `<process-id>`…), each instance gets its own left-border colour and a subtle
  tint, cycling through six hues — so you can see at a glance where
  GigabitEthernet1 ends and GigabitEthernet2 begins. Unique elements are left
  untinted.
- **The reply pane grows instead of scrolling**: taller by default (420px), no
  max-height, and the drag-corner grabber is preserved in tree view (the `.xt`
  class had been replacing `.resizable`), with the flex row aligned to the top
  so the pane can expand freely.


## hitech_automation_ai.1.46.0 — 2026-07-12

### Added — Device reply is now an interactive XML tree
- **Foldable elements**: every container/list gets a ▼/▶ caret (click the caret
  or double-click the row). Leaves render inline —
  `<in-octets>570474062</in-octets>`.
- **4-space indent + dotted indent rails**, so parents / siblings / descendants
  are unambiguous at a glance.
- **Depth control**: ⊞ all / ⊟ all, plus a depth selector (1/2/3/4/6/all) —
  collapse to level 3 to see the interfaces, then drill in.
- **Count badges** on collapsed containers (`<interface> 4 children`), so you
  know what's hidden.
- **Find in reply** with prev/next stepping (`3 / 12`): matching elements are
  highlighted, their ancestors auto-expanded and scrolled into view. Matches on
  element names AND text values, so `GigabitEthernet2` finds the entry.
- **📋 per element** — hover any row to copy just that subtree.
- **Tree / Raw toggle** keeps the previous plain view (now also 4-space
  indented); Copy + wrap unchanged.
- Self-contained (no CDN), verified in jsdom against a real IOS-XE reply.

### Changed — dependencies trimmed (as agreed)
- `requirements.txt`: the **yangsuite / yangsuite-netconf / yangsuite-filemanager
  / django** block is **removed**. They were never required — the RPC builder
  falls back to a native lxml implementation (v1.42.3) and the dependency scan
  to a regex parser. `yang_engine.py`'s docstring now says so instead of
  claiming the engine is embedded.
- **`docker/yangsuite/` deleted** — dead weight from the reverted v1.35.0
  companion-container approach. `docker/` now contains only the app's own
  Dockerfile + single-service compose.


## hitech_automation_ai.1.45.0 — 2026-07-12

### Added — collapsible sections in the YANG workspace
- Every block in **NETCONF-YANG** is now a **collapsible section** with a ▼/▶
  header, in the same style as the Filter/extract block: **RPC controls**,
  **Module loader**, **YANG tree**, **RPC & device reply**, **Filter/extract**,
  and **Saved NETCONF operations** (which starts collapsed, since it's the
  noisiest).
- **Node detail folds to a thin strip on the right edge** — click it and the
  tree pane takes the full width. Applies to Explore-YANG too.
- **⊟ Collapse all / ⊞ Expand all** buttons in the YANG sub-tab bar.
- **Layout is remembered** (localStorage), so your preferred arrangement
  survives reloads.
- Collapsing is **purely visual** — nothing is unmounted, so ticked nodes,
  filled values and the loaded tree all survive folding (verified in jsdom).


## hitech_automation_ai.1.44.2 — 2026-07-12

### Fixed — the v1.44.1 saved-payload fix never took effect
- v1.44.1 claimed to fix `XMLError: Element [{…}native] does not meet
  requirement` on ▶ Run of a saved operation, but the patch matched a
  **different copy** of the handler (the string differed by one word), so the
  live Run path still posted the bare fragment to `/api/netconf-send`.
- The **actual** saved-entry Run branch now wraps the stored fragment into a
  complete `<rpc>` (adding `<filter>` / `<config>`) and dispatches it through
  `/api/yang/run-rpc`, with the reply rendered in the pretty XML view.


## hitech_automation_ai.1.44.1 — 2026-07-12

### Added
- **XPath style is now a 3-way selector**: **no prefix (default)** | short prefix
  | module prefix. "No prefix" produces exactly the form of a hand-written
  working filter (`/interfaces/interface[admin-status="if-state-up"]…`).
  "Short prefix" uses a compact alias (`intf`, `bgp`, `ospf`, `ios`) declared on
  the filter, instead of the model's verbose prefix
  (`interfaces-ios-xe-oper:` repeated on every step).
- **Client-side XPath filter + Extract→table on the device reply** — the same
  real-XPath-1.0 tooling already available under the XPath nav, now directly
  under the NETCONF reply: run predicates / `//` / `contains()` against the
  returned XML, or extract a row element + labelled columns into a table.

### Fixed
- **`XMLError: Element [{…}native] does not meet requirement` when running a
  saved operation.** Older records stored a **bare data fragment**; ncclient
  needs `<filter>` (or `<config>`) around it. Saved payloads are now wrapped
  correctly on both ▶ Run and ⬆ Load, and an already-wrapped payload is not
  double-wrapped.
- **"➕ NETCONF get filter" appeared to do nothing.** It saved the operation
  out of view. It now also **switches to the NETCONF-YANG tab, loads the RPC
  into the editor and scrolls to it** — ready to ▶ Run.
- Legacy `undefined:` prefixes in saved operation notes are repaired on read.


## hitech_automation_ai.1.44.0 — 2026-07-11

### Fixed — no dropdown for enum leaves defined via a typedef
- `Cisco-IOS-XE-interfaces-oper`'s `admin-status` / `oper-status` are typed with
  **typedefs** (`intf-state`, `oper-state`) that resolve to an enumeration in
  another module. The parser only looked for a literal `type enumeration`, so
  those leaves rendered as a plain **text box** with the raw type name, while
  YANG Suite offered a dropdown (`if-state-up`, `if-state-down`, …).
- `_type_info()` now reads pyang's **resolved type spec** (`i_type_spec`), which
  follows typedefs for us — so enum dropdowns appear for typedef'd leaves.
  Enums inside **unions** are collected too, and **identityref** leaves offer
  their derived identities.
- Numeric / string leaves now show their **restriction as a placeholder hint**
  (`uint16 (68..9216)`, `string (len 1..64)`), with the **pattern** in the
  tooltip.


## hitech_automation_ai.1.43.2 — 2026-07-11

### Fixed — device rejected the filter: `unknown-element <bad-element>filter</bad-element>`
- v1.43.1 declared the model namespace as the **default xmlns on `<filter>`** to
  allow unprefixed steps. That moved the `<filter>` element itself **out of the
  NETCONF base namespace** into the OpenConfig one, so the device saw an unknown
  element called `filter` and refused the RPC.
- `<filter>` now always stays in the **NETCONF base namespace**:
  - **unprefixed** → `<filter type="xpath" select='/interfaces/…'/>` with **no
    model namespace declared** — byte-identical to what ncclient puts on the wire
    for `session.get(filter=('xpath', '<string>'))`, i.e. the form already proven
    to work on the lab device.
  - **use prefixes** → `<filter xmlns:oc-if="…" type="xpath" select="/oc-if:…"/>`.
- Verified by parsing both forms back and asserting the filter element resolves
  in the NETCONF namespace with the correct (or absent) nsmap.


## hitech_automation_ai.1.43.1 — 2026-07-11

### Changed — XPath filters are now written the way a human would write them
Benchmarked against a hand-written filter that works on IOS-XE. The generator
now produces **byte-for-byte the same expression**:

```
/interfaces/interface[starts-with(name,"GigabitEthernet")]
                     [state/oper-status="UP" and state/admin-status="UP"]
                     [state/counters/in-octets>0 or state/counters/out-octets>0]
```

Three changes got us there:
- **No more per-leaf union.** We used to emit one arm per selected leaf and
  repeat every condition in each arm. The device returns the whole matched block
  anyway, so we now select the **common list ancestor once**. (A union is still
  used when the selections genuinely span different branches.)
- **Unprefixed steps by default.** Prefixing every step was most of the visual
  noise. The namespace is now declared as the **default xmlns on the filter**, and
  steps are bare. A **"use prefixes"** checkbox restores the prefixed form for
  multi-namespace expressions.
- **Grouped bracket predicates** instead of one long `and` chain: keys in the
  first bracket, equality conditions in the second, comparisons in the third —
  with an **and / or** selector for the comparison group (so
  `in-octets>0 or out-octets>0` is expressible).


## hitech_automation_ai.1.43.0 — 2026-07-11

### Fixed — device reply showed raw `<style="color:…">` markup
- The XML highlighter chained `.replace()` calls that ran over **their own
  output**: the tag rule then matched inside the `<span>` tags it had just
  emitted, producing the broken `<style="color:#7dd3fc;">` text you saw.
  Rewritten as a **single-pass tokenizer** that escapes each piece exactly once.

### Fixed — Copy buttons did nothing
- The app is served over **http://**, where `navigator.clipboard` is not
  available (it requires a secure context). Copy now falls back to a hidden
  textarea + `execCommand('copy')`. **The RPC pane has its own Copy button too.**

### Fixed — xpath filter ignored values like "UP" and ">0"
- Values were only turned into predicates for **list KEY leaves**; a value on an
  ordinary leaf (oper-status, in-octets) was silently dropped. Non-key leaf
  values now become **XPath conditions on the nearest list ancestor**:
  `interface[starts-with(oc-if:name,"Gigabit") and oc-if:state/oc-if:oper-status="UP"
  and oc-if:state/oc-if:counters/oc-if:in-octets>0]/…`

### Added
- **Resizable panes** (the corner grabber): RPC editor, device reply, the YANG
  tree, and every RESTCONF result box — drag to expand/shrink.
- **Multi-line `select=`** — each union arm on its own line. XML attribute values
  may contain newlines and XPath ignores the whitespace, so this stays valid;
  verified by parsing the result back to the identical expression.


## hitech_automation_ai.1.42.5 — 2026-07-11

### Fixed — NETCONF-YANG "Load module → tree" did nothing (status lied)
- The NETCONF tab's Load button worked by **copying its selection into the
  Explore tab's dropdowns and reusing that loader**. Those dropdowns are only
  populated once the Explore tab has been opened, so going straight to
  NETCONF-YANG left them empty: setting `.value` silently failed, the loader
  bailed out — and the handler still reported **"Tree loaded"** while the pane
  showed the placeholder.
- The shared loader now takes **explicit (set, module) arguments** instead of
  reading Explore's DOM, **returns success/failure**, and the NETCONF handler
  reports the truth (and mounts the tree pane **before** rendering into it, so
  the output lands in the host you are actually looking at).
- Tree relocation between the two tabs now uses a **DOM anchor** rather than
  fragile sibling lookups, so the tree always returns to its exact place in
  Explore. Verified in jsdom: mount → render → content visible in the NC host →
  move back → content preserved.


## hitech_automation_ai.1.42.4 — 2026-07-11

### Fixed — readability of the RPC and the device reply
- **`&quot;` everywhere in the xpath filter.** lxml always delimits attributes
  with double quotes, so every `"` inside `starts-with(...,"Gigabit")` was
  escaped. The `select` attribute is now emitted with **single-quote
  delimiters**, so it reads
  `select='/oc-if:interfaces/…[starts-with(oc-if:name,"Gigabit")]/…'`
  — still valid XML, verified by parsing it back.
- **The device reply was one unreadable wall of XML.** It is now
  **pretty-printed and syntax-highlighted** (elements, attributes, values), with
  leaf text kept on one line (`<in-octets>566039686</in-octets>`), plus a
  **Copy** button and a **wrap** toggle. Self-contained highlighter — no CDN.
- **Long xpath `select=` unions** are displayed with each ` | ` arm on its own
  line, so a 4-way union is readable (the attribute itself stays one line, as
  XML requires).
- **A comparison value in a SUBTREE filter is now blocked with an explanation.**
  `>0` was silently emitted as the literal text `&gt; 0` — subtree filters match
  values exactly and cannot express comparisons. The builder now says so and
  points you to the xpath filter (or to just tick the node).


## hitech_automation_ai.1.42.3 — 2026-07-11

### Fixed — four bugs from live testing
- **Build RPC failed with "YangEngineError: yangsuite engine packages not
  installed".** The subtree/config builder hard-depended on the optional
  yangsuite pip packages. A **native lxml builder** now produces the identical
  XML (merged list entries, empty leaves, correct namespaces) and is used
  automatically when the engine isn't present — Build RPC works out of the box.
- **xpath filter produced `RPCError: XPath syntax error`.** A key value that is
  an XPath *expression* was being quoted as a literal:
  `[oc-if:name="starts-with(name,&quot;Gigabit&quot;)"]`. Expressions are now
  detected and emitted unquoted — `[starts-with(oc-if:name,"Gigabit")]` — and
  comparisons like `>0` become `[oc-if:in-octets>0]`. Plain values still quote
  normally.
- **Node detail showed a stale node from a PREVIOUS module** (openconfig tree
  displaying `Cisco-IOS-XE-bgp` / `/native/router/bgp`). Loading a tree now
  clears the selection, Node detail, RFC panel, Generated paths and API
  operations.
- **The ➕ buttons gave no feedback.** They now flash a green ✓ (or red ✕ on
  failure) for ~1.4 s when an operation is added.


## hitech_automation_ai.1.42.2 — 2026-07-11

### Added — smart path-aware node search
The find box now understands paths, not just names:

| Query | Matches |
|---|---|
| `bgp` | name contains "bgp" (as before) |
| `bgp*` / `*bgp` | name glob |
| `//bgp` | node **named** `bgp` at **any depth** (drops the `bgp-id` noise) |
| `/native/router/bgp` | **absolute path**, anchored at the tree root |
| `router/bgp` | **path suffix** — any node whose path ends with these segments |
| `/native/*/bgp` | `*` matches exactly one path segment |
| `//interface/*/mpls/bgp` | descendant + wildcard combined |

- The **exact** checkbox still forces whole-name equality for plain names.
- An absolute query that matches nothing **falls back to a suffix match** and
  says so, rather than just reporting "No match".
- Ranking unchanged: exact-name matches first, then shallowest paths.
- The matcher was verified against the *rendered* template JS (not just the
  source) to confirm the regex escaping survives templating.


## hitech_automation_ai.1.42.1 — 2026-07-11

### Changed — RESTCONF-YANG response handling
- **HTTPS mode now returns the response only** — status line, collapsible
  response headers, and the body. The curl / python-requests / http.client
  export snippets (and the curl preview block) appear **only in curl mode**,
  where they belong.
- **Format selector: JSON | XML** sets `Accept` (and `Content-Type` when a
  payload is present) to `application/yang-data+json` or
  `application/yang-data+xml`. The media type is shown in an **editable field**
  so it can be overridden by hand, and the generated curl uses it too.
- **The body is pretty-printed** — parsed and indented JSON, or indented XML —
  instead of the escaped one-line `"body": "{\n \"…\""` dump. Status code is
  colour-coded (2xx green / 4xx-5xx red) with the elapsed time.
- New backend flag `include_export` on `/api/restconf-execute`.

### Fixed
- **"undefined:process-id"** in collected operation notes — `node.module` was
  dropped from the compact tree in v1.34.3; the note now resolves the module
  from `augmented_from` / tree meta.


## hitech_automation_ai.1.42.0 — 2026-07-11

### Added — YANG tree inside NETCONF-YANG (YANG Suite layout)
- NETCONF-YANG now has its own **YANG set + module picker (with search) and
  Load button**, and the schema **tree renders right there** above the RPC
  panes. Tick nodes / fill values in that tree and Build RPC (subtree or xpath)
  uses exactly those selections — no detour through Explore-YANG.
- Implemented as **one shared tree instance that is relocated** between the
  Explore and NETCONF hosts, so there is a single renderer, a single selection
  state, and no divergent behaviour (icons, badges, lazy DOM, search all
  identical in both tabs).

### Fixed — augment-only modules rendered an empty tree
- `openconfig-if-ethernet` (and any module that only **augments** others) has no
  top-level nodes of its own, so its tree was legitimately empty — but the UI
  just showed a blank pane and blamed duplicates. The backend now detects an
  augment-only module, resolves its **augment target(s)**, and returns the
  TARGET module's tree with the augmented nodes merged in (this is what YANG
  Suite does), plus a clear note explaining the substitution. If the target
  isn't in the set, it says so and tells you to add it.
- **The misleading red banner is gone.** When a tree really does come back
  empty, the UI now lists the **actual blocking findings** from the set
  (e.g. `already a child node to "/if:interfaces/if:interface"`, missing
  `ietf-routing` types) instead of guessing "duplicate revisions".


## hitech_automation_ai.1.41.1 — 2026-07-11

### Fixed — find-node exploded the tree (200+ branches auto-expanded)
- Typing `router` matched every `*router*` node and the search **expanded the
  ancestor chain of all 200 matches**, leaving the tree unusable.
- **Search now shows a results list instead of expanding anything**: each hit
  shows its node type and full path. **Click a result to jump** — only that
  node's chain is expanded, it is highlighted, scrolled into view, and selected
  (Node detail fills in). Jumping to another hit **collapses the previous
  branch**, so the tree stays tidy.
- **Prev / Next** buttons (and Enter / Shift+Enter in the box) step through
  matches with a `3 / 47` counter.
- **exact** checkbox matches the node name exactly instead of any substring.
- Results are **ranked**: exact-name matches first, then shallowest paths — so
  `router` puts `/native/router` (container) at the top, above the dozens of
  `*-router-id` leaves.
- Clearing the box still collapses the tree back to top level.


## hitech_automation_ai.1.41.0 — 2026-07-11

### Added — subtree / xpath filter choice + selectable tree nodes
- **Filter type selector** in NETCONF-YANG: **subtree** (default, YANG Suite's
  behaviour) or **xpath**. xpath builds
  `<filter type="xpath" xmlns:pfx="…" select="…"/>` from the selected nodes
  (multiple selections joined with the XPath union `|`, prefixes declared on
  the filter element per RFC 6241 §6.4.2). The selector is disabled for
  edit-config (which carries `<config>`, not a filter).
- **:xpath capability guard** — Run RPC checks the device's advertised
  capabilities first and returns a clear "switch to subtree" message instead of
  a cryptic RPC error.
- **Selectable nodes in the tree** (the ✓ boxes YANG Suite has): containers and
  lists now have a select checkbox, and leaves get one alongside their value
  box. A node ticked WITHOUT a value emits an empty element — this is how the
  `<counters><in-octets/></counters>` "fetch this field" filter shape is built.
  `collectFilled()` now includes selected-but-valueless nodes.


## hitech_automation_ai.1.40.0 — 2026-07-11

### Added — NETCONF-YANG is now a live RPC builder (YANG Suite parity)
- **NETCONF Operation** selector (get / get-config / edit-config) + datastore
  (running / candidate) + device picker.
- **&lt;/&gt; Build RPC** renders the COMPLETE `<rpc>` document from the values you
  filled in the Explore-YANG tree — proper envelopes:
  `get` → `<get><filter type="subtree">…`, `get-config` → adds
  `<source><running/></source>`, `edit-config` → `<target>` + `<config>`.
  The XML lands in an **editable** pane (edit before sending).
- **▶ Run RPC** dispatches the raw `<rpc>` to the device via ncclient and shows
  the device reply side-by-side. **⃠ Clear RPC** resets both panes.
- Saved NETCONF operations get an **⬆ Load** button that pushes them into the
  RPC editor, wrapped in the right envelope.
- New routes `/api/yang/build-rpc-envelope` and `/api/yang/run-rpc`;
  `yang_engine.build_rpc_envelope()` builds the full document.

### Fixed
- **"undefined:bgp"** in built RPC notes — `treeMeta` was used without a guard;
  Build now refuses (with a clear message) if module metadata is missing.
- **edit-config was offered for read-only (config false) data.** Building from
  oper nodes now falls back to `get`, and edit-config is rejected outright for
  read-only selections.


## hitech_automation_ai.1.39.1 — 2026-07-10

### Fixed — XPath empty ("/") for notification / rpc / action nodes
- `xpathOf()` built the path from the DATA-node chain, which excludes
  `notification`, `rpc`, `action`, `input`, `output`, `choice`, `case`. Selecting
  a notification (e.g. `bgp-peer-state-change`) therefore showed XPath `/`
  where YANG Suite shows `/bgp-peer-state-change`.
- **XPath / Schema Node Id now use the full SCHEMA chain** (all schema
  statements), while the RESTCONF path correctly keeps using the data-node
  chain only. Non-data nodes now show "— (no RESTCONF data path for a
  notification)" instead of a misleading bare `/restconf/data/`.
- **Access / Operations** now reflect the statement type: notification →
  read-only / "notification"; rpc & action → "rpc"/"action"; config false →
  get-config/get; otherwise edit-config/get-config/get.


## hitech_automation_ai.1.39.0 — 2026-07-10

### Added — View module text + RFC reference (YANG Suite parity)
- **📄 View text** button in Explore-YANG opens the raw `.yang` source of the
  selected module in a modal: line numbers, find-in-text (highlights + scrolls),
  and Copy. New route `/api/yang/module-text`.
- **Node detail enriched** to match YANG Suite's Node Properties: added
  **Access** (read-write / read-only), **Operations** (edit-config/get-config/get
  vs get-config/get, derived from config), and **Schema Node Id**.
- **RFC 7950 reference panel** under Node detail: clicking a node shows the
  relevant statement's section (e.g. a `list` → RFC 7950 §7.8 "The list
  Statement") with a short bundled excerpt and a link to the full section on
  ietf.org. New module `tools/yang_rfc.py` (covers the ~20 core YANG
  statements) + `/api/yang/rfc/{keyword}` route.

### Note
- This build also carries the v1.38.5 OpenAPI generator fix (single-pass path
  construction; no more double-key / over-prefixed paths). APP_VERSION strings
  are normalized to 1.39.0 across main.py and the UI badge (they had lagged at
  1.38.3 in the 1.38.5 zip).


## hitech_automation_ai.1.38.5 — 2026-07-07

### Fixed — Generate API(s) produced 12,687 malformed paths (should be ~50)
- Comparing our bgp export to YANG Suite's revealed the path builder was
  broken two ways, which multiplied a 50-path spec into 12k+:
  1. **Double key predicate** — a selected list emitted `bgp={id}={id}` because
     the base-path builder and the subtree walker BOTH appended the key.
  2. **Over-prefixing** — every descendant carried `Cisco-IOS-XE-bgp:` on every
     segment (`…/Cisco-IOS-XE-bgp:bgp/Cisco-IOS-XE-bgp:aigp-rib-metric`) instead
     of only where the owning module changes (YANG Suite prints bare child
     names within the same module).
- **Path construction rewritten as a single clean pass**: each segment is
  emitted once with the correct module-prefix rule, and list keys become a
  single `={list-key}` predicate. Verified against YANG Suite's exported bgp
  JSON — path structure, prefixing, and per-node method sets all match.


## hitech_automation_ai.1.38.3 — 2026-07-07

### Fixed — Swagger grouping matches YANG Suite; render verified end-to-end
- Operations are now tagged **"<Verb> <Node>"** (Modify Bgp, View As-Path, …)
  exactly like YANG Suite, so Swagger-UI shows the same section headers
  (Modify Bgp / Replace Bgp / Add Bgp / View Bgp / Remove Bgp) instead of one
  flat group.
- **Render proven headless**: the vendored Swagger-UI bundle was run against a
  generated bgp spec in jsdom — 123 KB of real DOM with operation blocks. If
  your right-side panel was still blank, it was running a pre-1.38.2 build that
  fetched Swagger from the (blocked) CDN; deploy this build.
- Spec validated: every `{path-param}` has a matching parameter definition,
  every operation has responses.


## hitech_automation_ai.1.38.2 — 2026-07-07

### Fixed — Swagger-UI blank modal (CDN dependency removed)
- The OpenAPI modal rendered blank when the Swagger-UI CDN bundle failed to
  load (offline/filtered network or a stale CDN path). **Swagger-UI is now
  vendored locally** under `static/swagger/` and served by the app — no
  external network needed.
- The bundle loads on first modal open with a hard fallback: if assets still
  fail, the modal shows a clear message plus the raw spec (JSON) instead of a
  blank screen; ⬇ JSON / ⬇ YAML always work.
- Confirmed the generator itself was correct for `bgp` (a top-level list): the
  spec matched YANG Suite's exported JSON path-for-path; the failure was purely
  the missing renderer.


## hitech_automation_ai.1.38.1 — 2026-07-07

### Fixed — Generate API(s) now covers the WHOLE subtree (YANG Suite parity)
- v1.38.0 emitted a single path (5 methods) for the selected node. YANG Suite
  emits a path for the node **and every descendant** — router-ospf produces ~50
  resources. The generator now **recurses the full subtree** with YANG Suite's
  exact per-node-type method rules, decoded from its own exported JSON:
  container → GET/POST/PUT/PATCH/DELETE; list-collection → GET/POST/PUT/PATCH
  (no DELETE); list-instance `={key}` → GET/DELETE; leaf/leaf-list →
  GET/PUT/PATCH/DELETE (no POST); key leaves → informational path under their
  list's collection, no operations. List keys become distinct `{list-key}` path
  parameters at every level.
- Frontend now sends the node's full (depth-preserving) subtree to the
  generator, and warns if the tree was **depth-limited** (reload at
  Depth=unlimited for the complete API set).
- Verified path-for-path and method-for-method against the attached
  `Cisco-IOS-XE-ospf_router-ospf.json`.


## hitech_automation_ai.1.38.0 — 2026-07-07

### Added — Generate API(s): OpenAPI 3.0.3 + Swagger-UI (YANG Suite parity)
- **⚡ Generate API(s)** in Explore-YANG: select any data node → get a full
  **OpenAPI 3.0.3** document with all five operations on the RESTCONF data
  path, grouped exactly like YANG Suite — **View / Add / Replace / Modify /
  Remove** (GET/POST/PUT/PATCH/DELETE). List keys become `{key}` path
  parameters; request/response bodies carry a schema derived from the node's
  children (enums, booleans, ints, nested lists).
- **Swagger-UI modal** renders the spec with live **Try it out / Execute**,
  plus **⬇ JSON** and **⬇ YAML** download (matches YANG Suite's Download
  OpenAPI JSON/YAML).
- New `tools/yang_openapi.py` (spec generator, verified against the
  `router-ospf` example from the screenshots) and `/api/yang/openapi` route.


## hitech_automation_ai.1.37.0 — 2026-07-07

### Added — resizable Explore panel + HTTPS/curl in RESTCONF-YANG
- **Explore-YANG tree ↔ Node-detail split is now drag-resizable** (grab the
  handle between them; double-click resets to 420px) — the detail/Generated
  panel no longer clips on wide content.
- **RESTCONF-YANG: every operation now shows its equivalent `curl` command**
  (creds masked as `<user>:<pass>`, copy button) alongside the editable URI.
- **Run-mode toggle: HTTPS ⇄ curl.** HTTPS runs through the app's client
  (as before); curl runs the real command **on the server** with the device's
  resolved credentials and returns headers + body + exit code. New backend
  flag `as_curl` on `/api/restconf-execute` (auth/URL resolution shared with
  the HTTPS path; Authorization redacted in the echoed command).


## hitech_automation_ai.1.36.1 — 2026-07-07

### Fixed — Explore-YANG module picker is searchable
- New 🔎 search box next to "Module (from set)": type `nati` → the dropdown
  filters live to matching modules (selection preserved when still visible,
  else first match auto-selected). **Enter** in the search box loads the
  selected module straight into the tree.


## hitech_automation_ai.1.36.0 — 2026-07-07

### Added — Cisco YANG Suite engine EMBEDDED (Apache-2.0 pip packages, headless)
- **Build RPC from tree values** — YANG Suite's signature feature, powered by
  its own `YSNetconfRPCBuilder`, running inside our backend (no Django server,
  no second app). Fill values / tick checkboxes in the Explore tree (list KEY
  leaves included), then:
  - **🛠 Build edit-config from values** → one merged NETCONF `<config>` with
    correct namespaces and list-key elements
    (`GigabitEthernet><name>2</name><description>…`), or
  - **Build get filter** → subtree `<filter>` from the same selections.
  Both land in the **NETCONF-YANG tab** ready to ▶ Run against a device.
  Guard rails: refuses to build while a referenced list's key leaf is empty
  (tells you which); flags payloads containing augmented-module nodes so you
  can verify xmlns.
- **Repository status now uses YANG Suite's `quickparser`** (revision-aware
  import/include scanning) with the regex scan as automatic fallback.
- New `tools/yang_engine.py`: one-time headless Django-settings bootstrap;
  `rpcbuilder.py` loaded directly by file path (bypasses the package
  __init__ chain that would drag in ysdevices/netmiko needlessly).
- requirements: + yangsuite, yangsuite-netconf, yangsuite-filemanager, django
  (configured headless — FastAPI remains the only server).

### Decided with evidence — tree stays on OUR engine
Their headless tree builder (`YSYangModels`) was tested three ways against
real 17.7.1 models (directory repo / full-set context / product-exact
YSYangRepository+YSMutableYangSet): augments outside the import closure do not
merge without their Django UI glue, while our resolved-tree engine produces
the product-equivalent merge (router = 12 children incl. bgp/ospf/isis/lisp).
Embedding it would have been a downgrade; revisit if their packages change.


## hitech_automation_ai.1.35.1 — 2026-07-07

### Reverted — v1.35.0 launcher was the wrong delivery
- **Native YANG UI fully restored** (Repo / Explore-YANG / RESTCONF-YANG /
  NETCONF-YANG, exactly as v1.34.3). The YANG Suite *launcher* and companion
  container are removed — requirement clarified: YANG Suite's capabilities
  belong INSIDE this software, not as a dependency on another program.
- `docker/` now defines a **single service** (this app only). The Cisco
  one-container assets are dropped from the zip.
- Next (v1.36.0, awaiting go): embed YANG Suite's open-source ENGINE
  (ysyangtree / ysfilemanager pip packages, Apache-2.0) underneath the
  existing tabs — proven headless in prototyping.


## hitech_automation_ai.1.35.0 — 2026-07-07

### Changed — native YANG section REPLACED by Cisco YANG Suite (Option A)
- **New `docker/` directory** ships alongside `build/`:
  `docker-compose.yml` runs two services — **software_ai** (this app,
  containerized for the first time: python:3.11-slim, git for sparse imports,
  state in the `hitech-state` volume, `OLLAMA_URL` env-overridable) and
  **yangsuite** (Cisco's official one-container build: HTTPS UI on **8480**,
  telemetry receivers 57500/57501, `ys-data` volume, self-signed cert,
  default login developer/developer).
- **The YANG nav section is now a YANG Suite launcher**: live health pill
  (`/api/yangsuite/health`, self-signed TLS tolerated), "Open YANG Suite ↗",
  and start-up instructions shown when the container is down. The four native
  sub-tabs (Repo / Explore-YANG / RESTCONF-YANG / NETCONF-YANG) are removed
  from the UI.
- **Kept on purpose:** all `/api/yang/*` backend routes and your data under
  `~/.hitech_automation_ai/yang/` — the AI agent can still drive them; a later
  cleanup release can strip whichever routes prove dead.
- Verified: zero orphaned `yang-*` element references remain in the JS (the
  Classic-UI-removal gotcha), rendered scripts pass node --check, compose YAML
  and both Dockerfiles validate, all build contexts/paths resolve.
- Note: systemd zip deployment still works exactly as before; compose is an
  additional way to run.


## hitech_automation_ai.1.34.3 — 2026-07-07

### Fixed — Explore tree performance (minutes → instant)
- Measured on real Cisco 17.7.1 native: depth 8 = 116,765 nodes / **77 MB
  JSON**, all rendered as DOM up-front — the browser froze for minutes. Two
  fixes:
  1. **Compact tree JSON** — per-node defaults omitted; xpath/restconf/module/
     namespace no longer shipped per node (the client derives them from the
     parent chain with the same rules). Depth 8: 77 MB → **18 MB**; unlimited:
     173 MB → 38 MB.
  2. **Lazy DOM (YANGSuite-style)** — children materialize on first expand;
     the initial render is ~40 top-level rows, instant at any depth.
- **Find-in-tree rewritten** to walk the data (lazy DOM means rows may not
  exist): matches (cap 200) get their ancestor chain auto-expanded and
  highlighted, first match scrolled into view; **clearing the box collapses
  back to top level** (the v1.32.2 request, delivered).
- Node detail / Generated / API operations now compute paths client-side —
  verified identical to the backend's rules (cross-module prefixes included).


## hitech_automation_ai.1.34.2 — 2026-07-07

### Fixed — validation findings triage (the wall of warnings, explained)
- **Verified against real Cisco IOS-XE 17.7.1 models (637 modules):** pyang
  reports ~1500 findings on Cisco's own files, yet the resolved tree is
  complete and correct (router = bgp/ospf/ospfv3/eigrp/rip/lisp/isis merged
  in). The findings are inherent to Cisco/openconfig models — Cisco YANG Suite
  shows the same wall. Adding files does not (and cannot) silence them.
- **Validate now triages instead of dumping**: findings grouped by pattern
  with counts; known-benign patterns (cross-module XPath in groupings, leafref
  "in the path for", openconfig deviation targets, escape-sequence style
  warnings, unused imports, skipped duplicate revisions) are tagged **(benign)**
  with an explanation; a **verdict banner** leads: "✅ No tree-blocking
  findings — N known-benign patterns, safe to ignore", or lists the
  genuinely-actionable groups first.
- New `yang_parser.triage_findings()`; validate route returns `triage`.


## hitech_automation_ai.1.34.1 — 2026-07-07

### Fixed — duplicate module revisions were silently breaking everything
- **Root cause of "3100 errors + router won't expand":** two revisions of the
  same module (e.g. Cisco-IOS-XE-native @ 2021-07-01 AND @ 2021-08-10) in one
  pyang context break prefix→module resolution — every augment target lookup
  fails ("node …::native is not found in module …") and trees render without
  merged children.
- **parse_set now keeps only the newest revision per module name** and reports
  each skipped duplicate as a warning.
- **Repo tab: "Delete older duplicate revisions"** button removes all but the
  newest file per module; duplicated names are highlighted ⚠ amber in the list
  with a count in the header.
- **Explore now explains instead of failing silently**: if the context floods
  with errors and the tree comes back nearly empty, a red guidance banner tells
  you the cause and the fix path (Repo → dedupe → Validate → reload).
- Tree pane gets a **horizontal scrollbar** (long rows no longer clip).


## hitech_automation_ai.1.34.0 — 2026-07-07

### Added — RESTCONF-YANG and NETCONF-YANG tabs are live
- **Explore-YANG → "API operations" panel** on every data node: generated
  **GET (collection) / GET (instance) / POST / PUT / PATCH / DELETE** rows —
  URIs carry `{key}` placeholders for every list along the path (ancestors
  included), POST targets the parent path, write methods come with an editable
  **JSON payload skeleton** (keys first, enum/boolean/int example values,
  augmented children carry their `module:` prefix). ➕ per row, **Add all**,
  plus **NETCONF get filter** and **NETCONF edit-config** generators
  (subtree XML with key elements and namespace on the outermost element).
- **RESTCONF-YANG tab**: every collected operation as an editable entry
  (method badge, URI, payload, note) with 💾 save, checkbox **Delete checked**,
  and **▶ Run** against an inventory device — executes through the existing
  `/api/restconf-execute` backend (inventory auth), response shown inline.
  Refuses to run while `{key}` placeholders remain.
- **NETCONF-YANG tab**: same list for NETCONF operations — get/get-config use
  the XML as a subtree filter, edit-config wraps it in `<config>`; ▶ Run goes
  through `/api/netconf-send`.
- Collections persist server-side in `~/.hitech_automation_ai/yang/apis.json`
  (`/api/yang/apis` + add/update/delete routes).

### Notes / limitations
- NETCONF XML uses the top module's namespace on the outermost element;
  augmented subtrees that need their own xmlns may require a manual tweak (the
  payload is editable in-place).
- Unlimited operations can be collected — "as many API URIs as you want".


## hitech_automation_ai.1.33.0 — 2026-07-07

### Added — YANG Explorer restructured into sub-tabs (YANG Suite workflow)
- **New sub-tab bar under YANG: Repo | Explore-YANG** (+ RESTCONF-YANG and
  NETCONF-YANG placeholders, coming v1.34/v1.35).
- **Repo tab** = everything from v1.32 (repos, Upload/NETCONF/SCP/Git import,
  module list) **plus**:
  - **Repository status** — "Check dependencies" scans every module's
    import/include statements and reports missing modules in red as
    `Cisco-IOS-XE-features @ unknown (needed by …)`, green when complete.
  - **YANG module sets** — YANGSuite-style two-list builder: *modules in this
    set* vs *additional modules in the repository*, Add selected / **Add entire
    repository** / Remove selected / Remove all, filters, counts.
    Sets persist in `~/.hitech_automation_ai/yang/sets.json`.
  - **Validate YANG modules** — parses the entire set in ONE pyang context and
    lists per-position errors (✖ red) and warnings (⚠ amber).
- **Explore-YANG tab** — pick a set → module → load. The tree is built from
  pyang's **resolved schema (i_children)** with the whole set in context:
  **augments from other modules are merged in** — `/native/router` now shows
  the BGP/OSPF/EIGRP/LISP/… containers contributed by the separate
  Cisco-IOS-XE-* modules, which single-file parsing could never show.
  Augmented nodes carry correct cross-module RESTCONF prefixes
  (e.g. `Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-bgp:bgp`) and an
  `augmented_from` field. `config false` inheritance now uses pyang's
  `i_config` (whole read-only subtrees badge correctly).
- New routes: `/api/yang/sets` (+save/delete/validate), `/api/yang/repo/status`,
  `/api/yang/set-tree`. Set parse results are **cached** per set (invalidated
  when any member file changes) — first full-set parse of ~1400 modules takes
  a while; repeats are instant.

### Notes
- The single-file tree (`/api/yang/tree`) still works and remains the loader
  for the Repo-tab module list.
- v1.34 (next, NOT built): Explore API-URI builder — GET/POST/PUT/PATCH/DELETE
  URIs with key placeholders + JSON payload skeletons, collected into a list →
  RESTCONF-YANG tab to review/execute. v1.35: NETCONF-YANG tab.


## hitech_automation_ai.1.32.1 — 2026-07-07

### Fixed — YANG Explorer import UX (no more dead ends)
- **Auto-create repository at the point of import.** Download selected schemas /
  Copy YANG files / Import YANG files / Upload with no repository selected now
  prompt for a repo name (pre-filled with the device name for NETCONF, else
  "ios-xe"), create + select it, and proceed — instead of erroring with
  "Create/select a repository first".
- **"(no repos)" can never be a silent import target** — every import path goes
  through the ensureRepo guard.
- **Delete repo now states the blast radius**: 'Delete repository "ios-xe" and
  its 577 module file(s)? This cannot be undone.' — deleting a repo removes all
  its downloaded YANG files; this makes that unmissable.


## hitech_automation_ai.1.32.0 — 2026-07-06

### Added — YANG Explorer: add modules to repository (YANGSuite parity)
- **New "Add modules to repository" tab block: Upload | NETCONF | SCP | Git.**
- **NETCONF:** pick an inventory device → "Check device connectivity" (hello +
  netconf-monitoring capability) → "Get schema list" (ietf-netconf-monitoring
  /netconf-state/schemas) → filter, Select all/none → "Download selected schemas"
  via `<get-schema>`, saved as `<name>@<revision>.yang`. Client sends batches of
  10 with a live saved/skipped/failed counter — a full ~700-schema cat8Kv71 pull
  stays responsive and one bad schema never kills the run.
- **SCP:** host / SSH user / password / remote directory / include-subdirectories
  → paramiko SFTP copies all `*.yang` from any SSH host.
- **Git:** repository URL / branch / directory-within-repo → **shallow sparse
  clone** (`--depth 1 --filter=blob:none --sparse`) so even the multi-GB
  YangModels repo imports one vendor directory in seconds. Requires the `git`
  binary on the server.
- **"YANG modules in repository" list panel** (replaces the module dropdown):
  shows `module @ revision`, filter box, Select all / Select none /
  **Delete selected**, module count; double-click loads the tree.
- New module `tools/yang_device.py`; 6 new routes (`/api/yang/device/check`,
  `/device/schemas`, `/device/download`, `/scp/copy`, `/git/import`,
  `/module/delete`). All imports audited via audit.log. No new dependencies.

### Fixed
- `yang_store._safe()` stripped `@` from filenames, mangling `name@revision.yang`
  to `name_revision.yang` — `@` is now allowed.
- Repo metadata now records each module's **revision** (from `name@rev.yang` or
  the first `revision` statement in the source).

### Notes
- Per-schema/get-schema responses are cleaned of CDATA wrappers / XML
  declarations before saving; duplicates are skipped and counted.
- v1.33.0 (next): Repository status panel (missing-dependency report) + YANG
  module sets with pyang validation.


## hitech_automation_ai.1.31.0 — 2026-07-06

### Changed — YANG Explorer: full YANGSuite-style tree legend
- **Node icons replaced** with inline SVG matching Cisco YANG Suite shapes/palette:
  container (blue folder), list (blue lines), leaf (green), leaf-list (green multi-leaf),
  choice (split arrow), case (arrow), module, submodule, rpc (envelope), action (target),
  input, output, notification, anydata (green asterisk), anyxml (green `</>`).
- **Parser now emits rpc / action / input / output / notification / anydata / anyxml**
  nodes (previously skipped entirely). anydata/anyxml count as data nodes for
  XPath/RESTCONF path generation.
- **New node badges** (YANGSuite legend): 🔑 list key (red), presence container (green),
  ⓘ mandatory (green), 🔗 must (red, tooltip shows the constraint), 🔗 when (blue,
  tooltip shows the condition), ⧉ leafref (indigo, tooltip shows the target path).
- **Status-colored icons**: deprecated nodes render a yellow icon, obsolete render red
  (in addition to the existing strike-through + badge).
- **"ⓘ Icon legend" button** opens a YANGSuite-style popup with three sections:
  Node Icons / Node Support / Node Badges.
- **Node detail** gains Presence / Mandatory / Must / When / Leafref rows.
- **Deferred to v2:** `deviation: not-supported` rendering (needs deviation-module
  upload + application). Shown greyed in the legend as "(v2)".
- New test model `example-legend-test.yang` exercises every legend item.

## hitech_automation_ai.1.30.2 — 2026-07-06

### Fixed — YANG Explorer renderer
- **Parser reads `status`** (current/deprecated/obsolete); renderer shows struck-through
  labels + amber "deprecated" / red "obsolete" badges.
- **`uses <grouping>` now expands inline** — grouping contents were previously invisible.
- New kitchen-sink test model `example-kitchen-sink.yang`.

## hitech_automation_ai.1.30.1 — 2026-07-05

### Fixed — YANG Explorer hotfixes after first live test
- Tree rendering fixes (icons, key badges, value widgets) found during first
  on-device testing of the YANG Explorer.

## hitech_automation_ai.1.30.0 — 2026-07-05

### Added — YANG Explorer v1 (feature/yang-suite)
- New "🌲 YANG" left-nav section: create repositories, upload `.yang` files, parse with
  **pyang**, browse the schema tree, and generate a **RESTCONF path + on-device XPath**
  for any selected node.
- New modules: `tools/yang_store.py` (repo storage under `~/.hitech_automation_ai/yang/`),
  `tools/yang_parser.py` (pyang → normalized JSON tree), `tools/yang_generate.py`
  (RESTCONF path / unprefixed XPath / keyed path / NETCONF subtree-filter skeleton).
- 8 new `/api/yang/*` routes. New dependency: `pyang>=2.6`.
- v1 scope: single-module upload. Git/device import + dependency resolution = v2.


## hitech_automation_ai.1.29.0 — 2026-06-24

### Changed — better agent tool descriptions (fewer wasted iterations)
- **`get_state` / `get_running_config` (`xpath_filter`)** now spell out that the XPath runs
  ON THE DEVICE and must be **UNPREFIXED** (element names only, e.g. `/native/ip/access-list`).
  Adding a YANG module prefix like `Cisco-IOS-XE-native:` causes `RPCError: invalid namespace
  prefix`. Previously the agent (e.g. qwen3-coder) would try a prefixed XPath and burn an
  iteration on the error before correcting.
- **`restconf_get` (`yang_path`)** now clarifies the opposite: a RESTCONF data path **does** use
  the module prefix (unlike on-device NETCONF XPath), and that 404s are usually a container-nesting
  problem (e.g. ACLs live under `Cisco-IOS-XE-native:native/ip/access-list`). 

Text-only description changes — no behavior change to the tools themselves.


## hitech_automation_ai.1.28.0 — 2026-06-24

### Fixed (issue-1)
- **No more auto-injected default headers on https-restconf.** Previously `Accept:
  application/yang-data+json` (and `Content-Type` on writes) were added automatically to both
  the sent request and the "Export request → code" output — wrong for APIC/ACI (not YANG) and
  not matching what you built. Now the request sends **only the headers you set**. A new opt-in
  checkbox **"Add RESTCONF default headers (IOS-XE)"** re-adds them when you want the IOS-XE
  convenience default.

### Added (issue-2)
- **Environment variables on curl-restconf and python-restconf**, matching https. Both panes now
  have the same **Environment** selector (synced with the https one — one active environment).
  Before a run:
  - **`{{VAR}}`** in the curl command / python code is substituted from the active environment.
  - the active environment's vars are **injected into the process environment**, so curl sees
    `$APIC_HOST` (via `bash -lc`) and python sees `os.environ['APIC_HOST']`.
  - On a name clash, each pane's own env-box (`py-env`, or shell `export`s) wins — the
    Environment is the base layer.


## hitech_automation_ai.1.27.0 — 2026-06-24

### Changed — full product rename (netconf-sender → hiTech Automation AI)
- **App identity:** `APP_VERSION` is now `hitech_automation_ai.1.27.0`; page title/H1 → "hiTech
  Automation AI"; FastAPI app title, logger name, and docstrings updated. Release zips are now
  named `hitech_automation_ai.<ver>.zip`.
- **State directory renamed** `~/.netconf-sender/` → `~/.hitech_automation_ai/` (inventory,
  secrets, saved collections, audit log, vector_db). A single shared `tools/state_dir.py` now
  owns this path. **One-time auto-migration:** on first start, if the new dir is missing but the
  legacy `~/.netconf-sender/` exists, its contents are copied over automatically (the legacy dir
  is left intact) — existing installs keep their inventory and saved collections with no manual step.
- **systemd service renamed** `netconf-sender` → `hitech_automation_ai` (unit + drop-ins). Daily
  commands are now `systemctl --user restart hitech_automation_ai`.
- **Browser localStorage keys** `netconfsw.*` → `hitech.*` (panel sizes/preferences reset once;
  saved collections are server-side and unaffected).

### Migration (host, one-time)
- Rename the systemd unit + secrets drop-in and move state dir (see INSTALL.md). The app-side
  auto-migration is a safety net if the state dir wasn't moved by hand.


## hitech_automation_ai.1.26.5 — 2026-06-23

### Fixed
- **Interactive CLI: `NameError: name 'uuid' is not defined` on Open.** The session handler used
  `uuid.uuid4()` but `uuid` was never imported at module top (same class as the earlier `re` miss).
  Added `import uuid`. Open sessions now work.

### Changed
- **Renamed the CLI "Interactive" sub-mode to "Netmiko Interactive"** (radio label + pane heading)
  to reflect that it uses a persistent Netmiko channel (write_channel/read_channel/find_prompt).
- Read loop now uses Netmiko's `check_data_available()` when present (less blocking, cleaner reads).


## hitech_automation_ai.1.26.4 — 2026-06-23

### Fixed
- **Interactive CLI: "connected" then immediately "no active session" on Send.** The error
  wrapper returns HTTP 200 with `{ok:false, error:...}`, but the open/send UI only checked the
  HTTP status — so a backend error was treated as success, the session id came back undefined,
  and the next Send reported no active session (hiding the real error). The UI now treats
  `ok:false` / missing `session_id` as failure and prints the actual server error in the terminal.


## hitech_automation_ai.1.26.3 — 2026-06-23

### Fixed
- **Interactive CLI: Send appeared unresponsive + blank terminal.** If the device returned no
  prompt banner (or `find_prompt()` failed) the terminal looked empty and Send could no-op.
  Now: (1) the backend open path falls back gracefully if `find_prompt()` fails, so a session is
  always established; (2) the terminal shows a clear "connected — type a command" line when the
  banner is empty; (3) Send never fails silently — it reports "no active session" if there isn't
  one, and surfaces any error in the terminal pane.


## hitech_automation_ai.1.26.2 — 2026-06-23

### Fixed
- **Interactive CLI "JSON.parse: unexpected character" error.** The open/send endpoints could
  raise an unhandled exception that returned a plain-text 500, which the UI tried to parse as
  JSON and failed with an opaque message. Two fixes: (1) both endpoints now wrap their body and
  always return JSON `{ok:false, error:...}` with a real message; (2) the error wrapper itself
  referenced an undefined `logger` (the module's logger is named `log`) — corrected. The UI now
  reads responses defensively and shows the actual server message in the terminal pane.


## hitech_automation_ai.1.26.1 — 2026-06-23

### Fixed
- **Startup crash in 1.26.0** — `NameError: name 're' is not defined`. The new interactive-CLI
  code used `re.compile(...)` at module load, but `re` was only imported inside two helper
  functions, never at module top. Added a top-level `import re`. Service starts normally again.


## hitech_automation_ai.1.26.0 — 2026-06-23

### Added
- **Interactive CLI sessions** (new "Interactive" sub-mode on the CLI transport). Opens a
  persistent Netmiko SSH channel held open server-side, so you can answer device confirmation
  prompts live — `reload` → `(y/n)?`, `no username X` → `[confirm]`, `copy run start`,
  `delete flash:`, etc. The terminal pane shows whatever the device prints; when it stops at a
  prompt instead of returning to `hostname#`, a reply box lets you type your answer (e.g. `y`)
  and continue. Works for both IOS-XE and NX-OS prompt styles.
  - Backend: server-side session registry with open/send/close endpoints
    (`/api/cli-interactive/*`), a read-until-quiet loop with pager auto-advance, prompt-vs-await
    detection, EOF/closure detection (a confirmed `reload` drops the session — reported cleanly),
    and a 5-minute idle reaper.
  - **Safety:** interactive mode is **blocked on read-only devices** (set `read_only: false` to
    use it), since it can run `reload`/`erase`/config. `terminal length 0` is set on open to
    avoid pager stalls.

### Notes
- Interactive sessions are live channels and can't be saved as collection nodes.
- Single-user/localhost design: sessions live in server memory.


## hitech_automation_ai.1.25.0 — 2026-06-23

### Added
- **VS Code-style formatted, foldable JSON/XML response view** on every result pane
  (https-restconf, curl, python, XPath, NETCONF, CLI). Built once in the shared renderer:
  - **Collapsible folding** — a caret on every JSON object/array and every XML element with
    children; folded nodes show a hint (e.g. `… 3 keys`). **⊟ collapse-all / ⊞ expand-all**
    buttons in the pane toolbar.
  - **Line-number gutter + indent guides** for an editor-like view; reuses the existing
    2-space pretty-print and JSON/XML token colors.
  - **Bracket/tag-pair hover** — hovering a JSON `{`/`[` or an XML open/close tag highlights its
    matching partner (and the gutter), so you can see the block span.
  - **🔎 Find** is tree-aware: a match inside a folded node auto-expands its ancestors to reveal it.
  - **Lazy fold for big payloads** — responses over ~400 lines auto-collapse below depth 2 to stay snappy.
  - Falls back to flat colorized text if the body can't be parsed; plain-text panes are unaffected.
  - Copy (📋) still copies the raw response text.


## hitech_automation_ai.1.24.0 — 2026-06-23

### Changed
- **Graphical Save dialog** replaces the old type-a-number prompt for "Save current →" on every
  transport (RESTCONF/NETCONF/CLI/XPath/Python). One modal: click the destination folder to
  select it (highlights), type the request name, hit Save (Enter works; Esc / click-outside /
  Cancel dismiss). Existing folders only — create new folders with the sidebar's + Folder.


## hitech_automation_ai.1.23.1 — 2026-06-23

### Fixed
- **Startup 500 / Internal Server Error introduced in 1.23.0.** Three JavaScript comments in the
  new pretty-print function contained literal `{{ }}` text, which the Jinja2 template engine tried
  to evaluate while rendering index.html, raising TemplateSyntaxError. Reworded the comments
  (no functional change). Page renders normally again.


## hitech_automation_ai.1.23.0 — 2026-06-22

### Added
- **Saved requests now persist their post-response filters.**
  - **RESTCONF (https):** the jq filter bar (expression, `-r`, engine) is saved with the node and
    restored when you open it — pre-filled so it applies on your next Apply.
  - **XPath:** both client-side filters are saved — the **XPath filter** (expression + namespace-aware
    flag) and the **Extract fields → table** (row element + columns). On opening a saved XPath node,
    the query auto-runs and the saved filter auto-applies (watched via a result observer, with a
    safety timeout) so you get the customized output in one click.

### Notes
- curl and python nodes need no extra filter capture — their filtering lives in the saved command/code.
- Existing saved nodes without a `filters` blob load fine (filters simply start empty).


## hitech_automation_ai.1.22.0 — 2026-06-22

### Added
- **Pretty-print button on the RESTCONF Payload** — reformats the JSON body with 2-space
  indentation in place. Template vars like `{{APIC_HOST}}` are masked before parsing and
  restored after, so var-bearing bodies format fine; invalid JSON shows an inline error.
- **🔎 Find in response** on every result pane (RESTCONF/curl/python/XPath/NETCONF/CLI) via the
  shared pane toolbar. Highlights matches over the raw text, match count + next/prev (Enter /
  Shift-Enter), case-sensitive toggle, and a regex toggle that covers wildcard search (Bruno-style).

### Fixed
- **Duplicate** now clears the request's saved-node link, so saving a duplicated request no
  longer overwrites the original's node.
- **Save →** on an https request opened from a saved node no longer overwrites silently — it
  asks **Update** vs **Save as new** (Postman pattern). Right-click → New folder/Save current
  stays the always-new path.


## hitech_automation_ai.1.21.0 — 2026-06-22

### Added
- **Per-transport collection trees.** Every transport now has its own Bruno-style collection
  tree in the sidebar — NETCONF, RESTCONF, CLI, XPath, and Python — and the one for the active
  nav transport is shown. Each is stored in its own file under `~/.hitech_automation_ai/`
  (`<scope>_tree.json`). All share the same engine: unlimited folders, right-click
  (new folder / save current / rename / delete), drag-and-drop, per-section ▾ collapse.
  - **NETCONF:** saves Jinja2 (vars+template+op) or XML payload nodes; clicking **loads only**
    (device writes never auto-run) — review then Validate/Send.
  - **CLI:** saves Jinja2 or Raw command nodes; **load only**.
  - **XPath:** saves device+source+expression; clicking **auto-runs** the query (read-only).
    Existing "Saved queries" are migrated into the XPath tree on first load.
  - **Python:** saves the full multi-file project (files + entry + env); clicking loads the
    project (press Run).
  - **RESTCONF:** unchanged (https/curl/python kinds, curl/python auto-run).

### Changed
- Tree engine generalized to a scope-aware controller; `/api/rc-tree*` endpoints take a `scope`.


## hitech_automation_ai.1.20.1 — 2026-06-22

### Changed
- **Merged the RESTCONF collections tree into the single left sidebar.** The separate docked
  panel is gone; the tree now lives directly under the nav items (under RESTCONF), in one column.
  A single drag bar on the sidebar's right edge resizes the whole sidebar (180–520px); width
  persists; double-click resets to 240px. The ▾/▸ toggle hides/shows the tree in place.
  Collapsing the nav (≡) shrinks the whole bar and restores your width on expand.
- All v1.20.0 behavior (kind-aware save/load/auto-run for https/curl/python, badges, right-click,
  drag-drop, colorful JSON) is unchanged.


## hitech_automation_ai.1.20.0 — 2026-06-22

### Added
- **Docked, resizable RESTCONF collection panel (Bruno-style)** — the collection tree moved
  out of the content area into a dedicated panel right of the icon nav, **always visible**
  across all sections. A vertical drag bar resizes it (160px up to 50% of the window); width
  persists; double-click the bar resets to default. Collapse with ⟨, reveal with the 📁 button.
- **Save / load / auto-run curl & python in the tree** — request nodes are now kind-aware
  (`https` / `curl` / `python`). On curl-restconf or python-restconf, "Save current" stores the
  command / code (+ python env box) under any folder with a name (e.g. `curl-xe-native-get`).
  Clicking a curl or python node switches to that submode, loads the content, and **auto-runs**
  it; https nodes load into the builder as before. Node badges show kind (`curl`, `py`, or the
  HTTP method).
- **Colorful JSON in curl & python output panes** too (parity with the https response).

### Notes
- Existing saved nodes default to kind `https` — fully backward compatible.


## hitech_automation_ai.1.19.0 — 2026-06-22

### Added
- **Bruno-style collection tree for RESTCONF** — replaces the flat Project/Saved dropdowns
  with an unlimited-depth folder tree. Click a request to load it; right-click any node for
  New folder / New request here / Save current here / Rename / Delete; drag-and-drop to move
  requests and folders between folders (drop on empty space = move to root). Stored at
  `~/.hitech_automation_ai/restconf_tree.json` (survives upgrades). Existing Postman collections are
  migrated into the tree on first run; Postman/Bruno collection import adds a new top-level folder.
- **Colorful JSON responses** — https-restconf JSON responses are now syntax-highlighted
  (keys / strings / numbers / booleans / null), matching the existing XML coloring. String
  contents (e.g. dotted IPs) are protected so they are never mis-tokenized as numbers.

### Changed
- New backend: `tools/restconf_tree.py` + `/api/rc-tree[...]` endpoints (get / add-folder /
  add-request / update-request / rename / delete / move / import-collection).


## hitech_automation_ai.1.18.0 — 2026-06-22

### Added
- **curl-restconf response headers** — each `curl` invocation in the pasted snippet is
  auto-instrumented (`-D <tmpfile>`) so its response headers are captured without altering
  the command. A collapsible "Response headers" block mirrors the https-restconf one;
  multiple curls show sequential `── curl #N ──` blocks in order.
- **jq filter on https-restconf response** — a filter bar appears under the Response when the
  body is JSON. Two selectable engines: **Browser (wasm)** runs vendored jq in-page (instant,
  offline; `static/jq/jq.js` + `jq.wasm`); **Server (system jq)** posts to `/api/jq` and runs
  the VM's real `jq` (matches your terminal exactly). `-r` toggle, Enter to apply, Raw to reset.

### Notes
- `/api/jq` passes the filter as a single argv (no shell) — no injection; 8 MB input cap, 15 s
  timeout; if `jq` is absent it nudges you to the Browser engine.


## hitech_automation_ai.1.14.0 — 2026-06-01

### Added
- **Saved XPath queries.** A "📁 Saved queries" panel on the XPath pane lets you organize device queries into projects (folders) and save them by name (Save / Save As), with Delete and project create/delete. Selecting a saved query fills the query box, Device, and Source — the device is pre-filled but you can switch to another before running. Stored as plain JSON at `~/.hitech_automation_ai/xpath/<project>.json` (outside `build/`, survives upgrades); Export/Import for backup/share (no Postman wrapper — XPath isn't an HTTP request). Endpoints: `/api/xq-projects`, `/api/xq-project-create`, `/api/xq-project-delete`, `/api/xq-queries`, `/api/xq-save`, `/api/xq-delete`, `/api/xq-export`, `/api/xq-import`.

### Changed
- **Device XPath query box is now multiline** — converted from a single-line input to a textarea so long expressions can span lines (Enter = newline; run via the button). The text is sent verbatim; XPath ignores whitespace between steps/predicates, so multiline just works.

## hitech_automation_ai.1.13.0 — 2026-06-01

### Added
- **XPath filter on the Result(XML)** — a new "🔎 XPath filter (real XPath 1.0)" tool sits alongside "Extract fields → table" under the XPath Result pane; both run against the same query output, so you pick table-extraction or a raw XPath filter. Unlike the table tool's local-name chain, this is **real XPath 1.0** via server-side lxml: predicates `[...]`, `//`, `@attr`, functions (`contains()`, `text()`, `local-name()`, `count()`, ...), `and`/`or`, positions. Element matches render as pretty XML, value/attribute/number/boolean results as text, with a match count and Copy. New endpoint `POST /api/xpath-test {xml, expr, ignore_ns}`.
- Namespaces are **ignored by default** (stripped server-side) so unprefixed expressions just work on RESTCONF/NETCONF XML; a "namespace-aware" checkbox switches to using the document's declared namespaces (default ns as `ns`).
- The filter input is a multiline textarea (Enter = newline; run via the button), passed to the engine verbatim — XPath is whitespace-insensitive between steps/predicates, so long expressions can span lines.

## hitech_automation_ai.1.12.3 — 2026-06-01

### Fixed
- **RESTCONF auth fields now resolve `{{ }}` variables / environment vars.** Previously the server rendered Jinja only in the URL, header values, and body — the Basic-auth username/password and the bearer token were taken literally, so `{{username}}` / `{{password}}` (e.g. from an active environment) were sent verbatim and the device returned 401. `_render()` is now applied to `auth_username`, `auth_password`, and `auth_token` as well. As a side effect, "Export request → code" now shows the resolved credentials instead of literal `{{vars}}`.

## hitech_automation_ai.1.12.2 — 2026-06-01

### Changed
- Renamed the product display name from "hiTech Automation AI" to **hiTech_Network_Automation_Tool_AI** — browser tab title, the main header (`<h1>`), and the FastAPI app title (shown at `/docs`). Display-only: the NETCONF *protocol* labels, the `netconf-sender` systemd service id, and the `hitech_automation_ai.` version/zip-naming scheme are unchanged.

## hitech_automation_ai.1.12.1 — 2026-06-01

Hotfix for v1.12.0.

### Fixed
- **500 Internal Server Error on every page load.** `index.html` is rendered through Jinja2, and the v1.12.0 environment-vars hint contained a literal `{{ ... }}` sequence in its JavaScript, which Jinja tried to evaluate as a template expression (`TemplateSyntaxError: unexpected char '$'`) — killing the render before any HTML was sent. Wrapped the literal-brace spots in `{% raw %}…{% endraw %}` so Jinja emits them verbatim.
- Same fix applied to the new environment-editor help text and placeholder (`{{key}}`, `{{host}}`), which were rendering blank.
- Also fixed two pre-existing placeholders that had silently rendered blank for the same reason: the RESTCONF URL box (`{{device_host}}`) and the CLI Jinja-template box (`{{ name }} {{ ip }} {{ mask }}`).

## hitech_automation_ai.1.12.0 — 2026-06-01

RESTCONF persistent storage — collections + environments, Postman/Bruno compatible.

### Added
- **Collections (projects).** Save https-restconf requests into named projects that persist on disk. Each project is one **Postman Collection v2.1 JSON** file at `~/.hitech_automation_ai/restconf/<project>.postman_collection.json` (outside `build/`, so it survives zip upgrades). UI: a "📁 Collections & environments" panel on the RESTCONF https tab with Project + Saved-request dropdowns and New / Save / Save As / Delete. Opening a saved request loads it into the active request tab.
- **Environments.** Named variable bags (e.g. per host) stored as **Postman Environment JSON** at `~/.hitech_automation_ai/restconf-environments/<env>.postman_environment.json`. Pick an active environment from a dropdown and edit its vars (`key = value` lines). At send time the active env's vars merge into the request's variables (request-level vars win), so `{{host}}`, `{{base}}`, `{{token}}` resolve via the existing Jinja rendering.
- **Export / Import.** Export a project or environment to its JSON file (download) — already in Postman format, so it imports directly into **Postman or Bruno** (Bruno's JSON import reads Postman collections/environments). Import accepts a Postman/Bruno-exported collection or environment back into the app.

### Notes
- Storage is plain JSON files on the VM's local filesystem (atomic writes, same pattern as `devices.yaml`) — no database, no container/volume. Credentials are stored inline in plaintext, consistent with `devices.yaml`; keep port 7071 unexposed.
- Saved requests carry a private `_netconfsw` key for lossless round-trip in this app; Postman/Bruno ignore unknown keys, so files stay fully importable there.

## hitech_automation_ai.1.11.0 — 2026-06-01

Two RESTCONF features.

### Added
- **build-1 — Export request → code.** After a successful https-restconf query, a "🧬 Export request → code" panel offers the equivalent request as **curl**, **python-requests**, and **python http.client**, with Copy. Generated server-side from the fully-resolved request (real URL with vars/device-host rendered, headers, body) and creds inlined, so each snippet runs as-is. curl uses `-sk` (silent + skip-verify) when TLS verify is off (the lab default); params are baked into the URL. Reflects the active request tab; export is not persisted to localStorage (it contains credentials).
- **build-2 — python-restconf sub-mode.** A third RESTCONF mode beside https/curl: write or paste Python and Run it on the VM via `python3` (stdin), with stdout/stderr captured. Mirrors curl-restconf's execution model (host execution, single-user localhost). Pairs with build-1 — generate a snippet, paste it here, run/tweak. `requests` must be pip-installed on the VM; the http.client snippet needs nothing.

## hitech_automation_ai.1.10.1 — 2026-05-31

### Fixed
- XPath "Extract fields → table": the result no longer goes stale. Running a new XPath query now clears the previous extraction (table + row count), and clicking Extract with an empty Row element or no columns clears the old table instead of leaving it on screen. (Reminder: Row element + column paths must match the current XML's schema — the interface defaults are just an example.)

## hitech_automation_ai.1.10.0 — 2026-05-31

Batch of five next-release items.

### Added
- **XPath field extractor (client-side).** Under the XPath result pane, a "Extract fields → table" panel: give a row element (e.g. `interface`) and columns as `label = path` local-name chains (e.g. `in-octets = state/counters/in-octets`), get a copyable table (Copy TSV). Namespace-agnostic, runs entirely in the browser.
- **Agent can read the last result.** New read-only agent tool `read_last_result`: the server caches the latest direct-execute result (NETCONF / RESTCONF / CLI / XPath) and the agent can read it — or extract specific fields from XML by passing `row_element` + `columns` (returns a compact table, avoiding huge-context problems). Ask the agentic bot e.g. "filter the last response for interface name | in-octets | out-octets".
- **`num_ctx` control** in the chat panel (before `max_tokens`): pick the Ollama input context window (default / 4K…128K). Persisted; applies to local chat + agent. Cloud models ignore it.

### Changed
- **XPath result XML is now pretty-printed** (multiline + indented) — server-side `pretty_xml()`, matching NETCONF replies.
- **Config Mgmt content is left-aligned** against the nav (no longer centered), so it sits beside the chat drawer instead of being pushed to the middle.

### Notes
- `num_ctx` sets the *input* window; `max_tokens` still caps *output*. They share the window: keep `num_ctx ≥ input + max_tokens`.

## hitech_automation_ai.1.9.2 — 2026-05-31

**Stylesheet cleanup (no UI change).** Removed orphaned CSS rules left behind by the v1.8.2 Classic UI removal — selectors whose classes/ids no longer exist anywhere in the markup or JS: `#conn-status` (+ .ok/.err), `.grid-2`/`.grid-3` (+ their @media), `.tab-pane`, `.step-block`/`.step-header`/`.step-section` (+ `.step-block pre.output`), `.log-line`, `.alert` (+ .success/.error/.info), `.copy-btn`, `.output-wrapper`, and `.hint`. Verified each was unused before deletion; no live styles touched.


## hitech_automation_ai.1.9.1 — 2026-05-31  (v1.9.0-B)

**Multiple HTTPS RESTCONF requests.** The https-restconf builder now keeps several independent requests, each with its own method, URL, params, headers, vars, auth, payload, and response. A request tab bar sits at the top of the RESTCONF view.

### Added
- Request tabs with **+ Request** (new), **⧉ Duplicate** (clone the current one), close (×) per tab, and rename (double-click a tab).
- Each request's inputs persist across reloads (localStorage). Responses are kept in memory for the session (switching tabs preserves them); they are not written to disk.
- The active request and last edits are saved on tab switch and on page unload.

### Changed
- Dropped the "Postman-style" wording; the structured builder is now labelled "https-restconf (build a request)". Internal sub-tab classes were renamed off the `postman-*` names (no behaviour change).
- The curl-restconf paste mode is unchanged (single request).


## hitech_automation_ai.1.9.0 — 2026-05-31

**Config Mgmt transports are now left-nav items.** NETCONF, RESTCONF, CLI, and XPath moved out of the horizontal tab strip inside Config Mgmt and up into the left sidebar, each as its own nav entry (grouped under a "Config Mgmt" caption, with AI Chat and Docs below). Clicking one shows that transport directly — one fewer click, and the active transport survives reloads.

### Changed
- Left nav: **NETCONF / RESTCONF / CLI / XPath / AI Chat / Docs** (was Config Mgmt / AI Chat / Docs).
- The horizontal Config Mgmt tab strip and its switching logic are gone; the nav drives the panes. Each transport's own sub-controls (Jinja vs XML, RESTCONF params/headers/auth/body, etc.) are unchanged.
- Default view is **NETCONF**. Returning users whose saved view was the old "Config Mgmt" (or "Classic") are routed to NETCONF automatically.

### Removed
- Dead `.cfgmgmt-tabs` / `.cfgmgmt-tab` styles and the tab-click wiring.


## hitech_automation_ai.1.8.2 — 2026-05-31

**Removed the Classic UI.** The original v1.7 layout (the "Classic UI" nav section) is gone, along with everything only it used — lighter app, no dead code. **Config Mgmt is now the default screen.** The shared backend is untouched: `/api/send`, `/api/send-cli`, and `/api/render` stay (Config Mgmt's NETCONF/CLI/Jinja panes run on them).

### Removed
- The Classic panel markup, its nav item, and all Classic-only JavaScript (render/test/send handlers, transport toggle, tab logic, sample-data block, `setStatus`/`showAlert`).
- Backend endpoints `/api/test-connection` and `/api/test-connection-cli` (only the Classic "Test Connection" button called them), plus the now-unused server-side sample-data constants.
- Two AI-Chat hooks that were wired to the Classic editors and would otherwise have been orphaned: the "Insert into Template/Variables" buttons on chat code blocks, and the "Attach context" checkbox (which sent the Classic template/variables to the model). Chat code blocks keep their Copy button.
- The static "● Not connected" badge in the header (it was only ever updated by the Classic Test Connection).

### Changed
- Left nav is now **Config Mgmt / AI Chat / Docs**. Returning users whose saved view was "Classic" are routed to Config Mgmt automatically.


## hitech_automation_ai.1.8.1.4 — 2026-05-31

**Follow-ups to issue-4 + resize.** (1) Added a Copy button to the curl-restconf paste box too. (2) Removed the height *cap* on output panes: they now start at a sensible height, scroll if the content is longer, and drag freely taller (and wider) from the start — like the input textareas. The ⤢ button still toggles a one-click "show everything" in place. No backend changes.


## hitech_automation_ai.1.8.1.3 — 2026-05-31

**Issue-4: Copy buttons on input fields.** A hover Copy button now appears on every input box (previously copy only existed on output/response panes): NETCONF Variables / Jinja2 template / XML payload; RESTCONF URL / Payload / Vars; CLI Variables / Jinja2 template / Raw CLI commands; XPath query. Front-end only — each button copies that field's current value. (The curl-restconf paste box was not in the request, so it has no copy button yet.) No backend changes.


## hitech_automation_ai.1.8.1.2 — 2026-05-31

**UX patch.** Result panes now expand **in place** instead of opening a separate overlay window: the ⤢ button toggles the pane open (grows to fit the full response), and panes are drag-resizable in both directions (corner handle). Removed the pop-up overlay entirely. RESTCONF response body and curl stdout are now **syntax-highlighted when they're XML** (same sky/amber/mint/slate scheme as the NETCONF and XPath panes); JSON stays pretty-printed. No backend changes.


## hitech_automation_ai.1.8.1.1 — 2026-05-31

**UX patch.** Config Mgmt result panes (NETCONF / RESTCONF / CLI / XPath) now wrap long XML/text in place (`white-space: pre-wrap`), so the colorful multi-line output is readable directly in the main pane — no need to open the Expand overlay just to see it. Expand is still there for a full-screen view. No backend changes.


## hitech_automation_ai.1.8.1 — 2026-05-31

**Bug-fix + polish release for the v1.8 Config Mgmt section.** Seven items, front-end-heavy with two new thin backend endpoints. Backward-compatible; the Classic UI and all v1.7/v1.8 endpoints are unchanged.

### Fixed

- **Jinja render returned a blank box (and Send then sent nothing).** The Config Mgmt Jinja panes read `data.rendered` from `/api/render`, but the endpoint returns `rendered_xml`. Both the NETCONF and CLI Jinja "Render" and "Send" buttons were affected. Now read the correct field via a shared helper.
- **NETCONF Send and CLI Send returned 404.** The front-end posted to `/api/netconf-send` and `/api/cli-send`, which did not exist — the real routes (`/api/send`, `/api/send-cli`) expect a fully-populated device + secret from the client. Added two thin endpoints, `POST /api/netconf-send` and `POST /api/cli-send`, that take only a `device_name` (plus payload/commands and an operation/mode), resolve the device and its secret from inventory **server-side**, and delegate to the existing send logic. The client no longer handles credentials for these panes.

### Added

- **Operation / mode selectors** on the Config Mgmt send panes: NETCONF Jinja2 → operation (default `edit-config`); NETCONF XML (direct) → operation (default `get`); CLI Jinja2 → mode (default `config_set`); Raw CLI → mode (default `send_command`).
- **YAML / JSON toggle** for the NETCONF Jinja2 variables input. `/api/render` already accepted `format=yaml|json`; the toggle now surfaces it (default YAML).
- **Colorful XML** in the NETCONF and XPath result panes — tags, attributes, attribute values and brackets are syntax-highlighted. Escaping is applied first, so the highlighter is XSS-safe and preserves the literal source representation.
- **Copy 📋 and Expand ⤢ toolbar** on every Config Mgmt result pane (all 11: NETCONF rendered/response, NETCONF XML response, RESTCONF body/headers, curl stdout/stderr, CLI rendered/response, raw-CLI response, XPath result). Copy uses the raw (un-highlighted) text; Expand maximizes the pane into a full-screen overlay (Esc or click-outside to close).
- **Header key/value dropdowns** in the RESTCONF (Postman) Headers table. Common keys (Accept, Content-Type, Cookie, Authorization, X-Auth-Token) and values (`application/yang-data+json`, `application/yang-data+xml`, `application/json`, `APIC-cookie=`, …) are seeded as `<datalist>` suggestions; any new key/value typed is remembered in localStorage and offered next time.

### Changed

- **curl-restconf pane now runs through the host shell.** The pasted text is handed verbatim to `bash -lc` instead of being `shlex.split` + exec'd, and the "must start with curl" guard is removed. Pipes (`| jq`), command substitution `$( )`, variables (`$VAR` / `export`) and `&&` chains now work exactly as they do in a terminal on the VM. Each Run is a fresh shell, so variables persist only **within a single paste** — to chain an ACI login → token → call, paste the whole script at once.
  - This pane executes arbitrary shell on the host as the service user. It is intended for the single-user localhost deployment; **do not expose port 7071 to untrusted networks.** Requires `jq` on the VM for the common `| jq` idiom (`sudo apt install jq`).

## hitech_automation_ai.1.8.0 — 2026-05-30

**Major UX release.** Three big themes: visibility & control over agent runs, top-level UI restructure, and smarter defaults. ~1500 lines of new and changed code across 4 files; backward-compatible with v1.7 — all existing tabs continue to work as before, accessible via the new left nav under "Classic UI".

### Added — Stop & visibility (Group F)

- **Stop button** in the chat composer cancels in-flight agent runs at the next iteration boundary. Implemented via a server-side cancellation registry (`_CANCELLED_RUNS`) checked at the top of each iteration and at each tool-dispatch boundary. Cancels also apply on the resume path (after-approval continuation).
- **Run-id badge** appears next to the Stop button while a run is in progress, showing the active `run_id` for log correlation.
- New endpoint: `POST /api/agent-cancel` accepting `{run_id}`. Returns immediately; the agent loop exits cleanly with `stopped_reason="cancelled"` at the next checkpoint.
- `AgentResult.run_id` is now populated on all return paths (completed, error, max_iterations, awaiting_approval, cancelled).
- `run_agent()` and `_continue_loop()` accept `external_run_id` from the caller, so the UI-generated run_id flows through the whole run lifecycle.

### Added — Left navigation & UI restructure (Group G)

- **Left sidebar** with collapsible navigation. Four top-level destinations: Classic UI, Config Mgmt, AI Chat, Docs. State (active section, collapsed/expanded) persisted in localStorage.
- Width animation between 180px (expanded) and 38px (collapsed). Main content area shifts accordingly via `body { margin-left }`.
- Existing v1.7 layout is wrapped in `#v18-classic-wrap` and surfaced as the default "Classic UI" section — no v1.7 features lost.

### Added — Configuration Management section (Group H)

Direct-execute transports under the new left-nav "Config Mgmt" item. Four tabs:

- **NETCONF** with two sub-modes:
  - *Jinja2 template:* device picker → variables (YAML) → template editor → render → send. Uses `/api/render`; send path corrected in 1.8.1 (see above).
  - *XML payload (direct):* device picker → paste XML → send. For ad-hoc payloads without a template.
- **RESTCONF** with two sub-modes:
  - *https-restconf (Postman-style):* method dropdown, URI, Params/Headers tables, Variables block (Jinja2-templated against URI/headers/payload), Auth (Basic / Bearer / "use inventory device" / None), Payload, Response tab with status line + body + headers details. New endpoint: `POST /api/restconf-execute`.
  - *curl-restconf:* paste a full curl command, execute via subprocess. Multi-line `\` continuation handled. New endpoint: `POST /api/curl-execute`. Defence-in-depth: subprocess uses `shlex.split` (no shell expansion); refuses commands that don't start with `curl`.
- **CLI** with two sub-modes:
  - *Jinja2 template:* same pattern as NETCONF Jinja2.
  - *Raw CLI:* device picker → paste commands one per line → send via Netmiko.
- **XPath:** direct NETCONF XPath query. Device picker, source toggle (operational state `<get>` vs running-config `<get-config>`), XPath input, raw XML result. New endpoint: `POST /api/netconf-xpath`. Reuses v1.7's `_sync_get_state` / `_sync_get_config` with `filter_type=xpath`.

### Added — RAG in agentic mode (Group I)

- When `use_rag=True` is sent with `/api/chat-agent`, the server fetches top-5 corpus chunks for the latest user message and prepends them to the system prompt as "Reference documentation excerpts." The agent's `search_corpus` tool remains available for follow-up queries.
- Frontend automatically forwards the existing "Use RAG" checkbox state when in agentic mode (via a `window.fetch` monkey-patch that intercepts `/api/chat-agent` POSTs).
- Previously, "Use RAG" + agentic just exposed `search_corpus` as a tool — which small models (gpt-oss:20b) often declined to call, leaving the corpus untouched. Now the corpus is always in context.

### Added — RESTCONF 204 hint (Group J)

- `restconf_get` now detects HTTP 204 No Content responses and emits a diagnostic block listing the three common causes: wrong container name (e.g. `ospf` vs `router-ospf` on IOS-XE 17.x), missing standalone module (e.g. `Cisco-IOS-XE-ospf` not installed on some cat8000v images), or genuinely no config. Includes a `curl` snippet for discovering installed modules via `ietf-yang-library:modules-state`.

### Changed

- `APP_VERSION` → `hitech_automation_ai.1.8.0`. Header docstring rewritten.
- `ChatAgentRequest` gains `use_rag: bool` and `run_id: Optional[str]` fields.
- `agent.run_agent()` signature adds `external_run_id: Optional[str]` parameter (default `None` — backward compatible).
- `agent.AgentResult.stopped_reason` adds `"cancelled"` to the enum docstring.
- Agent system prompt unchanged from v1.7.0 (no model-side prompt changes in this release).

### Backward compatibility

- All v1.7 endpoints unchanged. All v1.7 tabs continue to work — accessible via the "Classic UI" left-nav item, which is the default landing area.
- `run_agent()` without `external_run_id` generates one internally (matches v1.7 behavior).
- `/api/chat-agent` requests without `use_rag` field default to `False` (matches v1.7 behavior).

---

## hitech_automation_ai.1.7.0 — 2026-05-30

**Major release.** RESTCONF as third transport, long-lived NETCONF sessions, XPath filters, inventory CRUD from the GUI, and a swag of smaller quality-of-life improvements. ~1700 lines of new and changed code across 9 files; backward-compatible with v1.5/v1.6 inventories.

### Added — RESTCONF transport (Group B)

- New `tools/restconf_tools.py` with seven tools:
  - `restconf_get` — read state/config via HTTP GET, returns JSON. Supports `?depth=N`.
  - `restconf_list_capabilities` — list YANG modules via `ietf-yang-library:modules-state`, with OpenConfig modules highlighted.
  - `propose_restconf_post` / `_put` / `_patch` / `_delete` — approval-gated write tools. Same approval flow as NETCONF: returns `{_approval_pending: True, proposal_id, ...}` and pauses the agent.
  - `apply_restconf_change` — commits an approved proposal.
- Inventory schema gains `port_restconf` (default 443), `restconf_root` (default `/restconf/data`), and `restconf_verify_tls` (default false for lab use). Configurable via flat YAML or pyATS `connections.restconf` / `custom.restconf_*`.
- System prompt updated: agents are instructed to prefer OpenConfig YANG over native Cisco-IOS-XE-* when both exist, and to prefer RESTCONF for simple reads.
- Tool results wrapped with `[RAW_RESTCONF_OUTPUT ...]` / `[END_RAW_RESTCONF_OUTPUT]` markers so the LLM echoes them verbatim on "show me raw" requests.

### Added — NETCONF polish (Group A)

- **XPath filter support** on `get_running_config` and `get_state`. New parameter `filter_type` accepts `subtree` | `xpath` | `none`. Old `subtree_filter_xml` calls still work (auto-detected and treated as subtree). Surgical queries like `xpath_filter="/bgp-state-data/neighbors/neighbor/neighbor-id"` now return only the matching leaves instead of whole subtrees.
- **Auto-retry on `TransportError: Not connected`** — one retry with 2s backoff. Masks the transient flake we hit during v1.6 testing where rapid back-to-back NETCONF calls occasionally returned "Not connected" despite the device being healthy.
- **Better Ollama timeout error message** — when a 600s ReadTimeout fires, the message now lists the four most likely causes (cold load, model too big for hardware, prompt too long, max_tokens too high) instead of a single generic line.
- **Raw NETCONF XML markers** — `get_running_config` and `get_state` results are wrapped with `[RAW_XML_OUTPUT ...]` markers. When the user asks "show me raw" / "xml payload", the LLM (per system prompt) echoes the XML verbatim instead of summarising it.

### Added — Long-lived NETCONF sessions (Group D)

- ncclient sessions are now pooled per-(device, agent-run) instead of per-tool-call. `run_agent` opens a session lazily on first NETCONF tool call and closes it when the run finishes — mirroring how YangSuite works.
- Cuts NETCONF latency dramatically on multi-tool agent runs (TCP handshake + SSH key exchange + NETCONF capability exchange happens once per run, not per call).
- `_continue_loop` (post-approval resumes) gets its own fresh session pool.
- Session pool is cleaned up at every agent exit point: completed, max_iterations, awaiting_approval, provider error.

### Added — Cache busting (Group C)

- Stronger HTTP cache headers on `/`: `no-store, no-cache, must-revalidate, private, proxy-revalidate`, `Vary: *`, ETag tied to APP_VERSION, dynamic `Last-Modified`.
- `<meta http-equiv>` cache tags inside the HTML head (belt-and-braces for browsers that ignore HTTP headers in some scenarios).
- `pageshow` event listener forces reload when the page is restored from Chrome's back-forward cache (bfcache).
- Client-side version-mismatch auto-reload: page polls `/api/chat-config` once, compares server version vs `body[data-app-version]`, reloads once per session if they differ. Defeats the "I have to use incognito to see the new UI" problem.

### Added — Inventory CRUD & secrets (Group E)

- **Add / Edit / Delete device buttons** in the Manage Devices sysbar panel. Inline form with all fields (name, host, ports, credentials, device type, read_only, default). Save writes `devices.yaml` atomically via temp+rename, with `.bak` backup. Refuses to overwrite pyATS-format files unless `force_format_switch=true`.
- **External secrets file** at `~/.hitech_automation_ai/secrets.yaml`. New `$secret:VAR` syntax in inventory looks up plain key→value pairs from this file. Precedence: `$secret:` > `$env:` > `%ENV{}`. Recommended `chmod 600`. Cached and invalidated on inventory reload.
- New endpoints: `POST /api/devices`, `DELETE /api/devices/{name}`.

### Added — Sysbar features (Group E)

- **`max_tokens` slider** (256-8192, step 128). Threaded through `/api/chat`, `/api/chat-agent`, `run_agent`, `_continue_loop`, and both providers. "auto" button picks a sensible default based on the current model (qwen-7b→1536, gpt-oss-20b→2048, gpt-oss-120b→4096, claude→4096).
- **Watchdog timeout dropdown** (60s / 120s / 180s / 300s / 600s / Never). Client-side fetch abort timer — independent of Ollama's own 600s timeout.
- **🔥 Warm embed button** — pre-loads `nomic-embed-text` so the first RAG query doesn't pay the cold-load cost.
- **localStorage persistence** for sysbar toggles (auto-warm, pin-models, fallback-claude) plus max_tokens slider value and watchdog selection. Settings persist across page reloads.

### Changed

- `APP_VERSION` → `hitech_automation_ai.1.7.0`.
- Main module docstring rewritten to reflect v1.7 scope.
- `executor.py` dispatches RESTCONF tools alongside NETCONF tools; unknown-tool error message now suggests closest match across all three transports.
- `definitions.py` exposes all 17 tools (5 CLI/general + 5 NETCONF + 7 RESTCONF).

### Backward compatibility

- v1.5 and v1.6 inventory files load unchanged. The new RESTCONF and secrets fields are optional and default to safe values.
- Existing `subtree_filter_xml` calls without `filter_type` are auto-detected as subtree.
- The approval modal is unchanged; new RESTCONF proposals reuse it.

---

## hitech_automation_ai.1.6.1 — 2026-05-29 (hotfix)

**Fixes** the long-running browser cache issue where upgrading required opening a private window to see the new UI. Chrome's back-forward cache (bfcache) was bypassing the v1.3.3 cache headers.

### Changed

- Stronger HTTP cache-busting headers on `/`: `private`, `proxy-revalidate`, `Vary: *`, ETag tied to app version, dynamic Last-Modified.
- Belt-and-braces `<meta http-equiv>` tags inside the HTML head.
- Client-side `pageshow` listener forces a reload when restored from bfcache.
- One-time version-check on page load: if `body[data-app-version]` doesn't match `/api/chat-config.app_version`, auto-reload (once per session, prevents loops).

Direct upgrade from v1.6.0 — no other changes.

---

## hitech_automation_ai.1.6.0 — 2026-05-29

UX & agent-loop polish. Eight small improvements driven by real-world gpt-oss:20b testing of v1.5.1.

### Added

- **Enter sends, Shift+Enter newline.** Chat input now sends on Enter (like Slack/most chat apps). Use Shift+Enter for newlines. IME composition is respected (CJK input methods aren't affected).
- **`device_name` parameter for `run_show_command`.** The tool now accepts a `device_name` from the inventory. Resolution order: explicit `device_name` → inventory lookup → chat-form fallback. Caught a real bug where gpt-oss:20b would omit the device and silently hit whatever was in the chat form.
- **Per-iteration timing in the trace.** Every agent step shows `(N.Ns)` next to its iteration header, plus a total wall-clock time in the footer. Useful for spotting which iteration is slow on CPU.
- **Closest-match suggestion for unknown tool errors.** When the LLM calls a non-existent tool (gpt-oss:20b sometimes hallucinates `search` instead of `search_corpus`), the error message now says "Did you mean `search_corpus`?" so the model can self-correct.
- **Focus injection at context >10k tokens or iteration >4.** A one-time system message is appended saying "use what you have, stop calling more tools, only use registered tool names." Combats two failure modes seen in production with smaller models: drift (forgetting the original question) and tool-name hallucination (inventing names under context pressure).
- **Raw CLI output preservation.** `run_show_command` now wraps its output in `[RAW_CLI_OUTPUT ... END_RAW_CLI_OUTPUT]` markers. The agent system prompt instructs the LLM to echo this VERBATIM in a fenced code block — preserving the columns, spacing, and exact wording instead of reformatting into markdown tables.
- **Chat input can now shrink.** The textarea was previously locked at a 140px minimum; you could grow it but not shrink it. Now the floor is 40px (about one line). Drag the top-left handle in either direction.

### Changed

- **Agent system prompt rewritten** for clarity. Explicit instruction to pass `device_name` when the user names a device. Explicit list of available tools to discourage hallucination. Explicit "don't repeat the same broken call twice" guidance after seeing 20b do exactly that with malformed NETCONF XML.
- The "📋 From inventory" picker default height is unchanged; only the user-resizable floor moved.

### Why these changes

This release is a direct response to two field-test sessions with gpt-oss:20b on CPU:

1. A `run_show_command` request to cat8Kv72 silently ran on cat8Kv71 because the tool schema had no way to specify a device, and the model couldn't override the chat-form fallback. **Fixed by item 3.**
2. A 6-iteration NETCONF run that successfully self-corrected XML errors in early iterations then hallucinated `search` (non-existent tool) once the context grew past 17k tokens, and never produced a final answer. **Mitigated by items 5, 6, 7.**

The architecture is sound — these are the small rough edges that surface only under real local-LLM load.

### Not in this release (planned v1.7)

- RESTCONF CRUD as a third transport (parked until GPU lands; reasoning model needed for reliable YANG/RESTCONF authoring)
- GUI Add/Edit/Delete device buttons
- External `secrets.yaml` file
- HTML cache-busting via `?v=` query

---

## hitech_automation_ai.1.5.1 — 2026-05-29 (hotfix)

**Fixes** `KeyError: 'port'` raised by `list_devices` agent tool when called against any v1.5.0 inventory. The tool was still reading the old single `port` field from `safe_describe()` output instead of the new `port_netconf` / `port_ssh` pair. Output is now richer too — includes both ports, default flag, and source format.

No other changes vs v1.5.0. Direct upgrade from v1.4.0 is fine.

---

## hitech_automation_ai.1.5.0 — 2026-05-29

Inventory upgrade. Reads pyATS testbed format alongside the v1.4.0 flat format, adds a device picker in the GUI, and surfaces inventory state in the system status bar.

### Added — pyATS testbed format support

`~/.hitech_automation_ai/devices.yaml` now accepts **both** formats. The loader auto-detects which one your file uses by checking whether `devices:` is a list (flat) or a mapping (pyATS).

```yaml
# pyATS — reusable with Genie / Ansible
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
      cli:     {protocol: ssh,     ip: "%ENV{CAT8KV71}", port: 22}
      netconf: {protocol: netconf, ip: "%ENV{CAT8KV71}", port: 830}
    custom:
      read_only: false
      default: true
```

Both `%ENV{VAR}` (pyATS standard) and `$env:VAR` (v1.4.0 shorthand) are expanded at load time.

### Added — Two ports per device

Each device now tracks `port_netconf` (default 830) and `port_ssh` (default 22). NETCONF tools (ncclient) use `port_netconf`; CLI tools (netmiko) use `port_ssh`. In pyATS format, both come from the respective `connections.cli` / `connections.netconf` blocks. Old `port:` fields in flat-format files continue to work — they map to `port_netconf`.

### Added — Device picker in the GUI

The Device Info section now has a "📋 From inventory" dropdown. Picking a device auto-fills host, port, username, and the netmiko device_type. The password field is intentionally **not** populated — the form keeps whatever you typed (and the agent's NETCONF tools always read the password directly from the inventory file server-side, never via the API).

When you switch the transport radio between NETCONF and CLI, the port field updates automatically (830 ↔ 22) to match.

### Added — Manage Devices panel in the system status bar

Expand the sysbar to see a `📋 Devices` section with:
- Count of loaded devices and the inventory file path
- Compact table: name, host, NETCONF/SSH ports, device type, read-only flag, password-resolved indicator, source format (flat or pyATS)
- `↻ Reload` button — re-reads `devices.yaml` from disk without restarting the service
- Collapsible "How to add devices" with copy-paste snippets for both formats

### Added — New endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/devices/reload` | Re-read inventory from disk; returns new count |
| `GET /api/devices/connect-info/{name}?transport=netconf\|cli` | Non-password connection info for picker auto-fill |

`GET /api/devices` now also returns a `count` field.

### Added — Inventory state in startup log

```
INFO Inventory: 3 device(s) loaded from /home/sushil/.netconf-sender/devices.yaml (formats: pyats)
```

Visible in `journalctl --user -u hitech_automation_ai`.

### Changed — Inventory upgrade safety

Reiterated: `~/.hitech_automation_ai/devices.yaml`, `audit.log`, and any secrets are all outside the build directory. **Zip-based upgrades never touch them.** Documented in INSTALL.md.

### Migration notes

- v1.4.0 flat-format files keep working unchanged. The old `port:` field is now treated as `port_netconf`.
- If you're using `$env:VAR` from v1.4.0, it still works. New deployments using pyATS testbeds should prefer `%ENV{VAR}` for consistency with other pyATS tooling.
- No breaking schema changes. The Device dataclass exposes `port_netconf` and `port_ssh`; the legacy `.port` attribute remains as an alias for `port_netconf`.

### Not in this release (planned v1.6+)

- GUI Add/Edit/Delete device buttons (writing back to YAML)
- External `secrets.yaml` file with `$secret:VAR` precedence
- Per-model intelligent `max_tokens` defaults
- Configurable watchdog timeout
- Stronger HTML cache-busting via `?v=` query param

---

## hitech_automation_ai.1.4.0 — 2026-05-29

NETCONF write mode with human approval workflow, plus critical LLM fixes carried forward from the v1.3.3 manual patches.

### Added — NETCONF agent tools (six new tools)

The agent can now act on devices via NETCONF (ncclient), not just CLI/show:

| Tool | Type | Description |
|---|---|---|
| `list_devices` | read | Lists devices from `~/.hitech_automation_ai/devices.yaml` |
| `get_running_config` | read | Pulls running-config via NETCONF (optional subtree filter) |
| `get_state` | read | Pulls operational state (interfaces, routes, BGP, OSPF) |
| `validate_config_xml` | read | Validates a payload via candidate datastore without committing |
| `propose_edit_config` | **write** | Proposes a change; returns diff for the approval modal |
| `apply_edit_config` | **write** | Commits a previously approved payload |

Both write tools route through a mandatory human-in-the-loop approval gate. The agent cannot commit without an explicit user click.

### Added — Device inventory file

On first run the app creates `~/.hitech_automation_ai/devices.yaml` with a sample entry. Each device has:

- `read_only: true` (default) — write tools refuse to commit
- `password: $env:VAR_NAME` — keeps secrets out of the YAML file
- `device_type` mapping for ncclient (`cisco-iosxe`, `cisco-nxos`, etc.)

### Added — Approval modal (diff & commit)

When the LLM proposes a write, the UI opens a modal showing:
- Device name + summary line (LLM-supplied plain English)
- Unified diff (current vs proposed XML)
- Full proposed NETCONF `<config>` payload
- **Approve & Commit** / **Reject** buttons

Closing the modal with ✕ or Esc leaves the run paused server-side; you can decide later. Reject feeds a rejection message back to the agent so it explains and stops, rather than retrying the same change.

### Added — Audit log

Every significant agent event is appended as one JSON line to `~/.hitech_automation_ai/audit.log`:

- `tool_call` — every NETCONF tool invocation
- `approval_request` — when the agent proposes a write
- `approval_decision` — user's approve/reject
- `write_applied_ok` / `write_applied_error` — outcome of commits

New endpoint `GET /api/agent/audit?n=50` returns recent entries.

### Added — New endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/devices` | Inventory (passwords stripped) |
| `POST /api/agent/approve` | Resume paused run with `{run_id, approved}` |
| `GET /api/agent/proposals` | List pending/decided proposals |
| `GET /api/agent/proposal/{id}` | Fetch one proposal's diff + XML |
| `GET /api/agent/audit?n=50` | Recent audit events |

### Fixed — Carry-forward LLM fixes from v1.3.3 manual patch ⭐

These were diagnosed during v1.3.3 production use by `journalctl -u ollama` analysis showing `requested context size too large for model` warnings, and applied as a hotfix:

- **Removed forced `num_ctx`** from Ollama payload. v1.3.1 had set a minimum of 8192, which exceeded the native training context of `nomic-embed-text` (2048) and forced extra KV-cache allocation on chat models. Letting Ollama use each model's native default is faster and produces no warnings.
- **Lowered `max_tokens` default 4096 → 2048**. For CPU inference at 5-8 tok/s, 4096 output tokens needs ~500-650s — well over the HTTP timeout. 2048 fits comfortably and is sufficient for most NETCONF/Jinja2 template generations.
- **Bumped HTTP timeout 300s → 600s** in both Ollama and Claude providers. Allows 14b/20b dense models and reasoning models (gpt-oss) to complete on CPU when the user is willing to wait.
- **Cleaned orphan `num_ctx` references** in the Ollama provider's success and ReadTimeout paths (would have raised `NameError` after the fix above).

### Changed

- `tools/definitions.py` returns the union of v1.3 CLI tools + v1.4 NETCONF tools.
- Approval-paused agent runs are stored in-memory keyed by `run_id`. They survive provider errors but not server restarts.

### Not in this release (planned v1.4.1+)

- Per-model intelligent `max_tokens` defaults (CPU-qwen vs GPU-qwen vs Claude)
- UI slider for `max_tokens` override
- Configurable watchdog timeout (currently hard-coded 120s)
- Audit log rotation (use `logrotate` manually for now)
- NSO integration

### Migration notes

- If you applied the v1.3.3 hotfix manually to `llm_providers/ollama_provider.py`, the v1.4.0 source matches your edits — overwriting is safe.
- First run will create `~/.hitech_automation_ai/devices.yaml` with a sample. Edit it before using NETCONF tools.
- For env-var passwords, restart `hitech_automation_ai.service` after exporting the variables so systemd inherits them.

---

## hitech_automation_ai.1.3.3 — 2026-05-28

Biggest visibility/control release. Adds a comprehensive system status bar inside the chat panel.

### Added — System status bar (collapsible)

A new bar between the controls and chat history. Click to expand for full details. Header always shows three live indicators:

- **💾 RAM**: count and total GB of models currently loaded in Ollama
- **📚 RAG**: chunk count or "not built"
- **🧠 Memory**: system memory used/total

Expanded view shows:
- **Loaded models** with individual `⏹ Unload` buttons + bulk **"Unload all chat models"** (keeps nomic-embed-text)
- **RAG database** with path, chunk count, status — and `↻ Rebuild (incremental)` and `🗑️ Full rebuild` buttons
- **Memory dashboard** showing total/used/free + top 10 memory-using processes
- **Performance toggles**: Auto pre-warm on model change, Pin current model (10m keep-alive), Suggest Claude fallback on long requests

### Added — In-UI RAG rebuild

No more SSH-ing in to run `rag_builder.py`. Click `↻ Rebuild` in the system status bar:
- Async background execution — UI stays responsive
- Live output streamed into a console-style box
- Toast notification on completion
- Auto-refresh of chunk count when done

### Added — Cold-load warning icon ⚡

Next to the model dropdown badge, a small ⚡ icon appears when the selected model is NOT currently in Ollama RAM. Hover for tooltip with expected delay.

### Added — Cancel button during requests

A `✕ Cancel` button appears next to Send while a chat request is in flight. Aborts the underlying fetch. Restores normal state. Shows toast "Request cancelled".

### Added — Slow request watchdog with Claude fallback

When using a local Ollama model, if a request runs >120s the UI prompts:

> ⚠️ {model} is taking longer than 120s.
> Would you like to CANCEL this request and retry with claude-sonnet-4-6 instead?

Click yes → request aborts, model dropdown switches to claude-sonnet-4-6, ready to resend. Toggleable in the sysbar.

### Added — Auto pre-warm on model change

Sysbar checkbox. When ticked, changing the model dropdown to a non-loaded local model triggers an async `/api/ollama-warm` call. By the time you finish typing the prompt, the model is in RAM.

### Added — Pin current model toggle

Sysbar checkbox. When ticked, warmed models use `keep_alive=10m` instead of the default `5m`. Useful for "I'm testing this model intensively for the next 30 minutes."

### Added — Cache-busting headers

The root HTML now serves with `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` and `Pragma: no-cache`. **Prevents the stale-HTML-in-incognito issue** you experienced upgrading from 1.3.1 → 1.3.2.

### Added — Six new backend endpoints

- `GET /api/ollama-loaded` — current loaded models from Ollama's `/api/ps`
- `POST /api/ollama-unload` — unload one or all (with `keep` list to protect embeddings)
- `POST /api/ollama-warm` — pre-load a model with custom keep-alive
- `POST /api/rag-rebuild` — async kick off `rag_builder.py`
- `GET /api/rag-rebuild-status` — poll rebuild progress + tail output
- `GET /api/process-memory` — `ps`-based top 10 memory hogs + `free -h` totals (Linux only)

### Fixed — Attach checkbox layout

`📎 Attach context` (renamed from the longer label) is now grouped with the other action checkboxes (Use RAG, Agentic, Compare) rather than pushed to the far right via `margin-left: auto`. The `🗑️ Clear` button now occupies the far-right position. **The Attach checkbox can no longer fall off-screen** at any reasonable chat panel width.

### Migration notes

- **No new pip dependencies**
- **No new env vars required**
- All v1.3.2 features (vector_db outside build, top-left resize handle, auto-migration) intact
- The hard-refresh-after-upgrade habit is no longer required — cache-busting handles it automatically

---

## hitech_automation_ai.1.3.2 — 2026-05-28

Fixed RAG persistence bug — vector_db moved from `build/vector_db/` to `../vector_db/` (sibling of build) so it survives code upgrades. Auto-migration on first import. Added top-left resize handle on chat input.

## hitech_automation_ai.1.3.1 — 2026-05-27

Claude Opus 4.7 temperature fix. Resume capability + retry + pre-warm for rag_builder.py. Better Ollama error messages. Auto-bump num_ctx. Token counter in chat input. 📋 Copy button on user messages. New LLM_INTEGRATION.md.

## hitech_automation_ai.1.3.0 — 2026-05-27

Agentic tool calling with ReAct loop. Read-only tools. Safety guards.

## hitech_automation_ai.1.2.0 — 2026-05-27

Claude API integration. Provider abstraction. Compare mode. Cost+token footer.

## hitech_automation_ai.1.1.0 — 2026-05-26

Model dropdown, resizable drawer, RAG builder fixes.

## hitech_automation_ai.1.0.0 — 2026-05-25

Initial RAG via Ollama embeddings + ChromaDB.
