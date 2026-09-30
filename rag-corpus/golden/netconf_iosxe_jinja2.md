# IOS-XE Extended ACL — NETCONF Jinja2 Template (VERIFIED on cat8Kv71)

> Status: VERIFIED working. Structure confirmed against a live `get-config` from cat8Kv71
> (IOS-XE, Cisco-IOS-XE-native + Cisco-IOS-XE-acl YANG models) and a correct
> claude-opus generation. Use this document as ground truth for extended ACL payloads.
> Do NOT generate IOS-XE ACL XML from memory — copy the structure here.

---

## Correct YANG tree location (most common mistake)

Extended ACLs do **NOT** live at the top of the model. The full ancestor chain is:

```
native  (http://cisco.com/ns/yang/Cisco-IOS-XE-native)
└── ip
    └── access-list
        └── extended            (http://cisco.com/ns/yang/Cisco-IOS-XE-acl)
            ├── name                          ← list key
            └── access-list-seq-rule          ← one per rule (wrapper is REQUIRED)
                ├── sequence
                └── ace-rule
                    ├── action / protocol
                    ├── source qualifiers
                    └── destination qualifiers
```

- NETCONF edit-config payloads must include the whole chain: `<native><ip><access-list><extended>…`
- RESTCONF path: `Cisco-IOS-XE-native:native/ip/access-list/Cisco-IOS-XE-acl:extended=<NAME>`
  (the `/ip/` level is mandatory — `native/access-list` returns 204 No Content)
- Device-side NETCONF XPath filters are **unprefixed**: `/native/ip/access-list/extended`
  (prefixed XPath like `Cisco-IOS-XE-native:access-list` → `RPCError: Invalid namespace prefix`)
- get-config subtree filter for the whole ACL block:

```xml
<filter>
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <ip><access-list/></ip>
  </native>
</filter>
```

## Wrong vs right element names (hallucination trap list)

LLMs repeatedly invent these. The left column is WRONG and must never be used:

| WRONG (hallucinated)                       | RIGHT (actual device model)                    |
|--------------------------------------------|------------------------------------------------|
| `<Cisco-IOS-XE-native:access-list>` at top | `<native>/<ip>/<access-list>/<extended>` chain |
| `<access-list-entry>` or flat `<sequence>` | `<access-list-seq-rule>` wrapper, then `<sequence>` |
| `<src-any/>`                               | `<any/>` (source "any" has no src- prefix)     |
| `<src-host>`                               | `<host-address>` (device also writes sibling `<host>`) |
| `<type>extended</type>`                    | no such leaf — the list itself is `<extended>` |
| `operation="replace"` (bare attribute)     | `nc:operation="replace"` with `xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"` |
| `</% endif %}` (broken Jinja)              | `{% endif %}`                                  |

Destination side: `dest-ipv4-address`, `dest-mask`, `dst-host-address` (+ sibling `dst-host`),
`dst-any`, `dst-eq`, `dst-gt`, `dst-lt` are correct. Source network uses `ipv4-address` + `mask`
(no src- prefix); source ports use `src-eq` / `src-gt` / `src-lt`.

## ace-rule leaf reference

| Purpose            | Source leaf                         | Destination leaf                                   |
|--------------------|-------------------------------------|----------------------------------------------------|
| any                | `<any/>`                            | `<dst-any/>`                                        |
| host               | `<host-address>` (+ `<host>`)       | `<dst-host-address>` (+ `<dst-host>`)               |
| network + wildcard | `<ipv4-address>` + `<mask>`         | `<dest-ipv4-address>` + `<dest-mask>`               |
| port eq            | `<src-eq>`                          | `<dst-eq>`                                          |
| port gt            | `<src-gt>`                          | `<dst-gt>`                                          |
| port lt            | `<src-lt>`                          | `<dst-lt>`                                          |

`<action>` = permit | deny. `<protocol>` = ip | tcp | udp | icmp | …
Element order inside `ace-rule`: action, protocol, source qualifiers, destination qualifiers.

## nc:operation semantics (scope matters)

- Put `nc:operation="replace"` on the `<extended>` **list entry** (keyed by `<name>`) to fully
  replace ONE named ACL while leaving sibling ACLs untouched.
- Putting replace higher (e.g. on `<access-list>`) wipes ALL ACLs on the device — almost never wanted.
- Omit the attribute (default merge) to add/update rules without removing existing ones.
- `create` fails if the ACL exists; `delete` removes the named ACL.
- An empty/204 read response does NOT prove the feature is unconfigured — verify the query path
  first (see gotchas above) before designing a replace.

## VERIFIED Jinja2 template (extended ACL, per-ACL replace)

```jinja2
<config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
        xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <ip>
      <access-list>
        {% for acl in access_lists %}
        <extended xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-acl"
                  nc:operation="replace">
          <name>{{ acl.name }}</name>
          {% for rule in acl.rules %}
          <access-list-seq-rule>
            <sequence>{{ rule.seq_num }}</sequence>
            <ace-rule>
              <action>{{ rule.action }}</action>
              <protocol>{{ rule.protocol }}</protocol>

              {# ---------- SOURCE ---------- #}
              {% if rule.src_any is defined and rule.src_any %}
              <any/>
              {% endif %}
              {% if rule.src_host is defined %}
              <host-address>{{ rule.src_host }}</host-address>
              <host>{{ rule.src_host }}</host>
              {% endif %}
              {% if rule.src_network is defined %}
              <ipv4-address>{{ rule.src_network }}</ipv4-address>
              <mask>{{ rule.src_mask }}</mask>
              {% endif %}
              {% if rule.src_eq is defined %}<src-eq>{{ rule.src_eq }}</src-eq>{% endif %}
              {% if rule.src_gt is defined %}<src-gt>{{ rule.src_gt }}</src-gt>{% endif %}
              {% if rule.src_lt is defined %}<src-lt>{{ rule.src_lt }}</src-lt>{% endif %}

              {# ---------- DESTINATION ---------- #}
              {% if rule.dst_any is defined and rule.dst_any %}
              <dst-any/>
              {% endif %}
              {% if rule.dst_host is defined %}
              <dst-host-address>{{ rule.dst_host }}</dst-host-address>
              <dst-host>{{ rule.dst_host }}</dst-host>
              {% endif %}
              {% if rule.dst_network is defined %}
              <dest-ipv4-address>{{ rule.dst_network }}</dest-ipv4-address>
              <dest-mask>{{ rule.dst_mask }}</dest-mask>
              {% endif %}
              {% if rule.dst_eq is defined %}<dst-eq>{{ rule.dst_eq }}</dst-eq>{% endif %}
              {% if rule.dst_gt is defined %}<dst-gt>{{ rule.dst_gt }}</dst-gt>{% endif %}
              {% if rule.dst_lt is defined %}<dst-lt>{{ rule.dst_lt }}</dst-lt>{% endif %}
            </ace-rule>
          </access-list-seq-rule>
          {% endfor %}
        </extended>
        {% endfor %}
      </access-list>
    </ip>
  </native>
</config>
```

## Example variables (source of truth, YAML)

```yaml
access_lists:
  - name: challenge-207-pod-10
    rules:
      - seq_num: 10
        action: permit
        protocol: tcp
        src_any: true
        src_gt: 100
        dst_network: 203.36.36.32
        dst_mask: 0.0.0.15
        dst_eq: 636
      - seq_num: 20
        action: deny
        protocol: ip
        src_host: 198.51.100.6
        dst_any: true
```

CLI equivalent of this source of truth:

```
ip access-list extended challenge-207-pod-10
 10 permit tcp any gt 100 203.36.36.32 0.0.0.15 eq 636
 20 deny ip host 198.51.100.6 any
```

## Rendered payload (verified)

```xml
<config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
        xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <ip>
      <access-list>
        <extended xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-acl"
                  nc:operation="replace">
          <name>challenge-207-pod-10</name>
          <access-list-seq-rule>
            <sequence>10</sequence>
            <ace-rule>
              <action>permit</action>
              <protocol>tcp</protocol>
              <any/>
              <src-gt>100</src-gt>
              <dest-ipv4-address>203.36.36.32</dest-ipv4-address>
              <dest-mask>0.0.0.15</dest-mask>
              <dst-eq>636</dst-eq>
            </ace-rule>
          </access-list-seq-rule>
          <access-list-seq-rule>
            <sequence>20</sequence>
            <ace-rule>
              <action>deny</action>
              <protocol>ip</protocol>
              <host-address>198.51.100.6</host-address>
              <host>198.51.100.6</host>
              <dst-any/>
            </ace-rule>
          </access-list-seq-rule>
        </extended>
      </access-list>
    </ip>
  </native>
</config>
```

## Workflow rule (for agents and humans)

1. NEVER write IOS-XE config XML from memory. Retrieve first:
   `get-config` with the subtree filter above, or this document.
2. If the read returns empty/204, suspect a wrong path before concluding "not configured"
   (check `/ip/` level, unprefixed XPath, correct namespace).
3. Build the Jinja2 template by templatizing retrieved/verified XML — substitute values with
   `{{ vars }}`, wrap repeats in `{% for %}` — do not invent element names.
4. Scope `nc:operation` as narrowly as possible (the named `<extended>` entry).
5. Verify after push: re-run the same get-config and diff against the rendered payload.