# e5 — NX-OS API (DME, RESTCONF, NX-API CLI)

---
## NX-OS-API-STUDY
<details>
<summary><h2>📘 NX-OS-API-STUDY (click to expand)</h2></summary>

---

<details>
<summary><h3>1. Three API Types on NX-OS</h3></summary>

| API | Endpoint | Auth Method | Model | Feature |
|---|---|---|---|---|
| NX-API CLI | `/ins` | Basic Auth (`-u user:pass`) | CLI over HTTP | `feature nxapi` |
| NX-API REST (DME) | `/api/mo/`, `/api/class/` | `aaaLogin.json` → `Cookie: APIC-cookie=<token>` | ACI-style MIT tree | `feature nxapi` |
| RESTCONF | `/restconf/data/` | Basic Auth (`-u user:pass`) | YANG | `feature nxapi` + `feature restconf` |

#### Enable on switch

```
switch(config)# feature nxapi
switch(config)# nxapi https port 443
switch(config)# feature restconf
```

</details>

---

<details>
<summary><h3>2. Platform API Support Matrix</h3></summary>

| Platform | NETCONF | RESTCONF | gRPC | NX-API CLI | NX-API REST (DME) |
|---|---|---|---|---|---|
| **IOS-XE** | Yes | Yes | Yes | No | No |
| **IOS-XR** | Yes | **No** | Yes | No | No |
| **NX-OS** | Yes | Yes | No | Yes | Yes |
| **ACI (APIC)** | No | No | No | No | Yes (DME) |

> IOS-XR does **NOT** support RESTCONF — only NETCONF and gRPC for YANG.

</details>

---

<details>
<summary><h3>3. Authentication Quick Reference</h3></summary>

#### NX-API REST (DME) — Token-based

```bash
# Step 1: Login (-d implies POST)
export token=$(curl -sk "https://$NXOS_URI/api/aaaLogin.json" \
  -H 'content-type: application/json' \
  -d '{
        "aaaUser" : {
            "attributes" : {
                "name" : "expert",
                "pwd" : "1234QWer!"
            }
        }
}' | jq -r '.imdata[0].aaaLogin.attributes.token')

# Step 2: Use token
curl -sk "https://$NXOS_URI/api/class/l2BD.json" \
  -H "Cookie: APIC-cookie=$token"
```

#### RESTCONF & NX-API CLI — Basic Auth

```bash
# Using -u (curl encodes for you)
curl -sk "https://192.168.89.73/restconf/data/Cisco-NX-OS-device:System" \
  -u expert:'1234QWer!'

# Using Authorization header (you encode manually)
echo -n 'expert:1234QWer!' | base64
# ZXhwZXJ0OjEyMzRRV2VyIQ==

curl -sk "https://192.168.89.73/restconf/data/Cisco-NX-OS-device:System" \
  -H 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ=='
```

> Both `-u user:pass` and `-H 'Authorization: Basic <base64>'` are identical.
> `-u` can go anywhere in the curl command — position doesn't matter.

</details>

---

<details>
<summary><h3>4. APIC (ACI) vs NX-OS (Standalone) — DME Comparison</h3></summary>

| | ACI (APIC) | NX-OS (Standalone) |
|---|---|---|
| Root DN | `uni/` | `sys/` |
| VLAN / BD | `uni/tn-X/BD-Y` | `sys/bd/bd-[vlan-X]` |
| Interface | `topology/pod-1/node-1/sys/phys-[eth1/1]` | `sys/intf/phys-[eth1/1]` |
| BD Class | `fvBD` | `l2BD` |
| Subnet Class | `fvSubnet` | — |
| Interface Class | `l1PhysIf` | `l1PhysIf` |
| SVI Class | — | `sviIf` |
| Query mechanics | `query-target`, `rsp-subtree`, filters | **Identical** |
| Filter syntax | `eq()`, `wcard()`, `and()`, `or()` | **Identical** |
| Token path | `.imdata[0].aaaLogin.attributes.token` | **Identical** |

#### Key differences
- ACI tree starts at `uni/` (tenants, APs, EPGs, BDs)
- NX-OS tree starts at `sys/` (interfaces, routing, VLANs)
- Class names are different but query patterns are the same
- Both require `--globoff` for DNs with square brackets

</details>

---

<details>
<summary><h3>5. Class vs MO — Two Ways to Query DME</h3></summary>

| | `/api/class/` | `/api/mo/` |
|---|---|---|
| Purpose | Query **all objects** of a class | Query a **specific object** by DN |
| Filter | `query-target-filter=eq(class.attr,"val")` | `query-target`, `rsp-subtree` |
| Example | `/api/class/l2BD.json` | `/api/mo/sys/bd/bd-[vlan-2110].json` |
| Needs `--globoff` | No (usually) | Yes (DNs have `[]`) |

#### Class Name vs RN (Relative Name) in MO Path

| Class Name | RN in MO Path | DN Example |
|---|---|---|
| `l2BD` | `bd-[vlan-XXXX]` | `sys/bd/bd-[vlan-2110]` |
| `l1PhysIf` | `phys-[ethX/Y]` | `sys/intf/phys-[eth1/1]` |
| `sviIf` | `svi-[vlanXXXX]` | `sys/intf/svi-[vlan2110]` |
| `pcAggrIf` | `aggr-[poX]` | `sys/intf/aggr-[po1]` |
| `l3LbRtdIf` | `lb-[loX]` | `sys/intf/lb-[lo0]` |

> **Never put class name in MO path** — `sys/intf/sviIf.json` does NOT work.
> MO path uses RN (`svi-[vlan2110]`), not class name (`sviIf`).

</details>

---

<details>
<summary><h3>6. DME vs RESTCONF vs NX-API CLI — Same Data, Different Paths</h3></summary>

#### Example: Query VLAN 2110

```bash
# DME — by MO
curl -sk --globoff "https://$NXOS_URI/api/mo/sys/bd/bd-[vlan-2110].json" \
  -H "Cookie: APIC-cookie=$token"

# DME — by class with filter
curl -sk "https://$NXOS_URI/api/class/l2BD.json?query-target-filter=eq(l2BD.id,\"2110\")" \
  -H "Cookie: APIC-cookie=$token"

# RESTCONF
curl -sk "https://$NXOS_URI/restconf/data/Cisco-NX-OS-device:System/bd-items/bd-items/BD-list=vlan-2110" \
  -H 'accept: application/yang-data+json' \
  -u $NXOS_USERNAME:$NXOS_PASSWORD

# NX-API CLI
curl -sk "https://$NXOS_URI/ins" \
  -H 'content-type: application/json' \
  -u $NXOS_USERNAME:$NXOS_PASSWORD \
  -d '{
    "ins_api": {
      "version": "1.0",
      "type": "cli_show",
      "chunk": "0",
      "sid": "1",
      "input": "show vlan id 2110",
      "output_format": "json"
    }
}'
```

#### Example: Query interface eth1/2

```bash
# DME
curl -sk --globoff "https://$NXOS_URI/api/mo/sys/intf/phys-[eth1/2].json" \
  -H "Cookie: APIC-cookie=$token"

# RESTCONF (encode slash as %2F)
curl -sk "https://$NXOS_URI/restconf/data/Cisco-NX-OS-device:System/intf-items/phys-items/PhysIf-list=eth1%2F2" \
  -H 'accept: application/yang-data+json' \
  -u $NXOS_USERNAME:$NXOS_PASSWORD

# NX-API CLI
curl -sk "https://$NXOS_URI/ins" \
  -H 'content-type: application/json' \
  -u $NXOS_USERNAME:$NXOS_PASSWORD \
  -d '{
    "ins_api": {
      "version": "1.0",
      "type": "cli_show",
      "chunk": "0",
      "sid": "1",
      "input": "show interface eth1/2",
      "output_format": "json"
    }
}'
```

</details>

---

<details>
<summary><h3>7. YANG Tree — NX-OS RESTCONF (Simplified)</h3></summary>

```
Cisco-NX-OS-device:System
│
├── bd-items
│   └── bd-items
│       └── BD-list=<vlan-XXXX>              ← VLANs (L2 Bridge Domains)
│           ├── name
│           ├── id
│           ├── fabEncap
│           └── adminSt
│
├── intf-items
│   ├── phys-items
│   │   └── PhysIf-list=<ethX/Y>            ← Physical interfaces (L2 only)
│   ├── svi-items
│   │   └── If-list=<vlanXXXX>              ← SVIs
│   ├── lb-items
│   │   └── LbRtdIf-list=<loX>             ← Loopbacks
│   └── aggr-items
│       └── AggrIf-list=<poX>              ← Port-channels
│
├── ipv4-items                               ← IP addresses (NOT under intf-items!)
│   └── inst-items
│       └── dom-items
│           └── Dom-list=<vrf>
│               └── if-items
│                   └── If-list=<intf>       ← IPv4 addresses per interface
│
├── bgp-items
│   └── inst-items
│       └── dom-items
│           └── Dom-list=<vrf>              ← BGP config
│
├── ospf-items
│   └── inst-items
│       └── Inst-list=<n>                ← OSPF instances
│
├── isis-items
│   └── inst-items
│       └── Inst-list=<n>                ← IS-IS instances
│
├── eps-items                                ← VXLAN/EVPN
├── fm-items                                 ← Feature manager
└── host-items                               ← Hostname
```

</details>

---

<details>
<summary><h3>8. RESTCONF Paths Quick Reference</h3></summary>

```
BASE: https://<switch>/restconf/data/Cisco-NX-OS-device:System

# INTERFACES
/intf-items/phys-items/PhysIf-list                          ← All physical
/intf-items/phys-items/PhysIf-list=eth1%2F1                  ← Specific (encode /)
/intf-items/svi-items/If-list                                ← All SVIs
/intf-items/svi-items/If-list=vlan2110                       ← Specific SVI
/intf-items/lb-items/LbRtdIf-list                            ← All loopbacks
/intf-items/aggr-items/AggrIf-list                           ← All port-channels

# VLANs
/bd-items                                                    ← All VLANs
/bd-items/bd-items/BD-list=vlan-2110                         ← Specific VLAN

# IP ADDRESSES
/ipv4-items/inst-items/dom-items/Dom-list=default/if-items/If-list            ← All IPv4
/ipv4-items/inst-items/dom-items/Dom-list=default/if-items/If-list=eth1%2F2   ← Specific

# ROUTING
/bgp-items/inst-items/dom-items/Dom-list=default             ← BGP
/ospf-items/inst-items/Inst-list=UNDERLAY                    ← OSPF
/isis-items/inst-items/Inst-list=ISIS                        ← IS-IS

# SYSTEM
/host-items                                                  ← Hostname
/fm-items                                                    ← Enabled features
```

</details>

---

<details>
<summary><h3>9. DME Filter Syntax Reference</h3></summary>

```bash
# query-target-filter — filters the queried objects (class queries)
/api/class/l2BD.json?query-target-filter=eq(l2BD.id,"2110")

# rsp-subtree-filter — filters children (MO queries with subtree)
/api/mo/sys/bd.json?rsp-subtree=children&rsp-subtree-class=l2BD&rsp-subtree-filter=eq(l2BD.fabEncap,"vlan-2110")&rsp-subtree-include=required

# wcard — wildcard match
?query-target-filter=wcard(l2BD.name,"Challenge")

# eq — exact match
?query-target-filter=eq(l2BD.id,"2110")
```

#### Filter gotchas
- **Double quotes** around string values — single quotes cause invalid responses
- **No space** after comma — `eq(l2BD.id,"2110")` not `eq(l2BD.id, "2110")`
- **Escape quotes** in bash — `\"2110\"` inside double-quoted URLs
- `query-target-filter` filters the class; `rsp-subtree-filter` filters children
- `rsp-subtree-include=required` filters parent objects based on matching children

</details>

---

<details>
<summary><h3>10. NX-API CLI Response Structure & jq Gotchas</h3></summary>

NX-API CLI always wraps arrays in `TABLE_*` / `ROW_*` pairs:

```json
{
  "ins_api": {
    "outputs": {
      "output": {
        "body": {
          "TABLE_intf": {
            "ROW_intf": [ ... ]
          }
        }
      }
    }
  }
}
```

#### jq gotchas
- **Hyphenated keys** need bracket syntax: `.["intf-name"]` not `.intf-name`
- **Leading dot** required: `.prefix` not `prefix`
- **No trailing comma** before `}`
- **Single result** = object, **multiple results** = array — watch for inconsistency
- **Shorthand** `{foo}` only works for simple keys, hyphenated keys need `{name: .["intf-name"]}`
- **Array iterator `[]`** must be outside quotes: `."BD-list"[]` not `."BD-list[]"`

</details>

---

<details>
<summary><h3>11. curl Tips for Exam</h3></summary>

```bash
# GET is default — no need for -X GET or --request GET
curl -sk "https://host/api/class/l2BD.json"

# -d implies POST — no need for -X POST
curl -sk "https://host/api/aaaLogin.json" -d '{...}'

# -u can go anywhere — position doesn't matter
curl -sk "https://host/ins" -H 'content-type: application/json' -u user:pass -d '{...}'

# --globoff for DNs with square brackets
curl -sk --globoff "https://host/api/mo/sys/bd/bd-[vlan-2110].json"

# URL-encode slashes in RESTCONF keys
eth1/14 → eth1%2F14

# -k skips certificate verification (lab use)
```

</details>

---

<details>
<summary><h3>12. How to Discover URIs in the Exam</h3></summary>

| Method | Use For |
|---|---|
| **NX-API Sandbox** (`https://<switch>/sandbox`) | Convert CLI → DME payload, find DNs |
| **Visore** (`https://<switch>/visore.html`) | Browse DME object tree, search by class |
| **Walk RESTCONF tree** from top | Start at `/restconf/data/Cisco-NX-OS-device:System`, drill down |
| **YANG model file** on bootflash | `grep` for keywords in `Cisco-NX-OS-device.yang` |
| **Query by class** | `curl /api/class/<className>.json` → shows all objects with their DNs |

</details>

---

</details>

---

## Initial Code

```bash
#!/bin/bash
###############################################################################
#! NX-OS has THREE API types:
#!
#! API              | Endpoint              | Auth Method                          | Model
#! -----------------|-----------------------|--------------------------------------|----------------
#! NX-API CLI       | /ins                  | Basic Auth (-u user:pass)            | CLI over HTTP
#! NX-API REST(DME) | /api/mo/, /api/class/ | aaaLogin.json -> APIC-cookie token   | ACI-style MIT
#! RESTCONF         | /restconf/data/       | Basic Auth (-u user:pass)            | YANG
#!
#! feature nxapi    -> enables NX-API CLI + NX-API REST(DME) + HTTP server
#! feature restconf -> enables RESTCONF (runs on top of nxapi HTTP server)
#!
#! switch(config)# feature nxapi
#! switch(config)# nxapi https port 443
#! switch(config)# feature restconf
###############################################################################

export NXOS_USERNAME="expert"
export NXOS_PASSWORD='1234QWer!'
export NXOS_URI="192.168.89.73"

###############################################################################
#! NX-API DME (feature nxapi) — uses APIC-cookie token
###############################################################################

#! TODO-1 : Login and extract token (-d implies POST, no need for -X POST)
export token=$(curl -sk "https://$NXOS_URI/#TODO-1" \
  -H 'content-type: application/json' \
  -d "{
        #TODO1
    }" | jq -r '.imdata[0].aaaLogin.attributes.token')

echo -e "\nTODO-1 : Printing the APIC-Cookie="$token

#! TODO-2 : Query all VLANs via DME (GET is default, no need for -X GET)
echo -e "\nTODO-2 :PRINTING ALL VLANS VIA DME"

curl -sk "https://$NXOS_URI/api/mo/sys/#TODO" \
  -H "#TODO" \
  | jq '.imdata[].bdEntity.children[].l2BD.attributes | {id, name, fabEncap}'

#! TODO-3 : Query specific VLAN 2110 via DME
echo -e "\nTODO-3 :PRINTING VLAN 2110 VIA DME"

curl -sk --globoff "https://$NXOS_URI/api/mo/#TODO" \
  -H "#TODO" | jq '.imdata[].l2BD.attributes | {id, dn, fabEncap}'

#! TODO-3a : Query specific VLAN 2110 via DME
echo -e "\nTODO-3a :PRINTING VLAN 2110 VIA DME USING class"
curl -sk "https://$NXOS_URI/api/class/#TODO" \
  -H "#TODO" | jq -r '.imdata[0].l2BD.attributes.fabEncap'

#! TODO-4 : Query all SVIs via DME
echo -e "\nTODO-4 :PRINTING ALL SVIs VIA DME"

curl -sk "https://$NXOS_URI/api/mo/#TODO" \
  -H "#TODO" | jq '.imdata[].sviIf.attributes | {id, adminSt, operSt}'

#! TODO-4a : Query all SVIs via DME USING class
echo -e "\nTODO-4a :PRINTING ALL SVIs VIA DME USING class"
curl -sk "https://$NXOS_URI/api/class/#TODO" \
  -H "Cookie: APIC-cookie=$token" | jq '.imdata[].sviIf.attributes | {id, adminSt, operSt}'

# ###############################################################################
# #! RESTCONF (feature restconf) — uses Basic Auth, no token needed
# ###############################################################################

#! TODO-5 : Query SVI via RESTCONF
echo -e "\nTODO-5 :PRINTING ALL THE SVI VIA RESTCONF"

curl -sk "https://$NXOS_URI/restconf/data/#TODO" \
  -H 'accept: application/yang.data+json' \
  -u #TODO | jq '."bd-items"."bd-items"."BD-list"[] | {fabEncap, id}'

#! TODO-5a : Query SVI vlan2110 via RESTCONF
echo -e "\nTODO-5a :PRINTING THE SVI VLAN2110 VIA RESTCONF"
curl -sk "https://$NXOS_URI/restconf/data/#TODO" \
  -H 'accept: application/yang.data+json' \
  -u #TODO | jq '#TODO'

echo -e "\nPRINTING THE SVI VLAN2110 VIA RESTCONF VLAN-NAME"
curl -sk "https://$NXOS_URI/restconf/data/#TODO" \
  -H 'accept: application/yang.data+json' \
  -u TODO | jq -r '#TODO'

# ###############################################################################
# #! NX-API CLI (feature nxapi) — uses Basic Auth, sends CLI commands over HTTP
# ###############################################################################

#! TODO-6 : "show vlan brief" via NX-API CLI (output JSON)
echo -e "\nTODO-6 :PRINTING SHOW VLAN BRIEF VIA NX-API CLI"

curl -sk "https://$NXOS_URI/ins" \
  -H 'content-type: application/json' \
  -u #TODO \
  -d '{
    "ins_api": {
      "version": "1.0",
      "type": "cli_show",
      "chunk": "0",
      "sid": "1",
      "input": "#TODO",
      "output_format": "json"
    }
}' | jq '.ins_api.outputs.output.body.TABLE_vlanbriefxbrief.ROW_vlanbriefxbrief[] | {id: .["vlanshowbr-vlanid"], name: .["vlanshowbr-vlanname"]}'

#! TODO-7 : "show ip int brief" via NX-API CLI (output JSON)
echo -e "\nTODO-7 :PRINTING SHOW IP INT BRIEF VIA NX-API CLI"

curl -sk "https://$NXOS_URI/ins" \
  -H 'content-type: application/json' \
  -u #TODO \
  -d '{
    "ins_api": {
      "version": "1.0",
      "type": "cli_show",
      "chunk": "0",
      "sid": "1",
      "input": "#TODO",
      "output_format": "json"
    }
}' | jq '.ins_api.outputs.output.body.TABLE_intf.ROW_intf[] | {name: .["intf-name"], ip: .prefix}'

#! TODO-8 : "show vlan name prod99" via NX-API CLI (output JSON)
echo -e "\nTODO-8 :PRINTING SHOW VLAN NAME PROD99 VIA NX-API CLI"

curl -sk "https://$NXOS_URI/ins" \
  -H 'content-type: application/json' \
  -u #TODO \
  -d '{
    "ins_api": {
      "version": "1.0",
      "type": "cli_show",
      "chunk": "0",
      "sid": "1",
      "input": "#TODO",
      "output_format": "json"
    }
}' | jq '{ports: .ins_api.outputs.output.body.TABLE_vlanbriefname.ROW_vlanbriefname["vlanshowplist-ifidx"], mode: .ins_api.outputs.output.body.TABLE_mtuinfoname.ROW_mtuinfoname["vlanshowinfo-vlanmode"]}'

# #! TODO-9 : "show running-config bgp" via NX-API CLI (output XML)
echo -e "\nTODO-9 :PRINTING SHOW RUNNING-CONFIG BGP VIA NX-API CLI (XML)"

curl -sk "https://$NXOS_URI/ins" \
  -H 'content-type: application/json' \
  -u #TODO \
  -d '{
    "ins_api": {
      "version": "1.0",
      "type": "cli_show_ascii",
      "chunk": "0",
      "sid": "1",
      "input": "#TODO",
      "output_format": "xml"
    }
}'
```

---
### Expected Outcome
<details>
<summary><h3>Click to display</h3></summary>

```bash
$ ./p1_nxos_api.sh 
uO9sr/mtqFrsTn8wEXH3/BWRL5+VcDryWqtpA0j2d+40JpSZX6a3q3u97K1L1+sbsjuf19GtcppFYI5NvJ/R+rvC/BfX1/aS4ByTc+Eht1PtFEzDH+O2CepVqnMlFBqBGEqw2DJ/KsaqQZsJVPWmHyOjWY5rSlO/qkAAcYx3AOLaCbp7hMK5MIHqQj7N3AnT
PRINTING ALL VLANS VIA DME
{
  "id": "3399",
  "name": "prod99",
  "fabEncap": "vlan-3399"
}
{
  "id": "2110",
  "name": "Challenge-201",
  "fabEncap": "vlan-2110"
}
{
  "id": "3299",
  "name": "test99",
  "fabEncap": "vlan-3299"
}
{
  "id": "1066",
  "name": "Pod_10_from_cli",
  "fabEncap": "vlan-1066"
}
{
  "id": "5",
  "name": "VLAN_5_Task_112",
  "fabEncap": "vlan-5"
}
{
  "id": "1174",
  "name": "pyATS_SoTH_VLAN_1174",
  "fabEncap": "vlan-1174"
}
{
  "id": "20",
  "name": "",
  "fabEncap": "vlan-20"
}
{
  "id": "1000",
  "name": "",
  "fabEncap": "vlan-1000"
}
{
  "id": "3199",
  "name": "dev99",
  "fabEncap": "vlan-3199"
}
{
  "id": "1020",
  "name": "",
  "fabEncap": "vlan-1020"
}
{
  "id": "1173",
  "name": "pyATS_VLAN-SoTH-Testing",
  "fabEncap": "vlan-1173"
}
{
  "id": "1072",
  "name": "Pod10Task72",
  "fabEncap": "vlan-1072"
}
{
  "id": "1010",
  "name": "",
  "fabEncap": "vlan-1010"
}
{
  "id": "1",
  "name": "",
  "fabEncap": "vlan-1"
}
{
  "id": "1073",
  "name": "Pod10Task73",
  "fabEncap": "vlan-1073"
}
{
  "id": "4",
  "name": "Print",
  "fabEncap": "vlan-4"
}
{
  "id": "3",
  "name": "PC",
  "fabEncap": "vlan-3"
}
{
  "id": "2",
  "name": "Server",
  "fabEncap": "vlan-2"
}
PRINTING VLAN 2110 VIA DME
{
  "id": "2110",
  "dn": "sys/bd/bd-[vlan-2110]",
  "fabEncap": "vlan-2110"
}
PRINTING VLAN 2110 VIA DME USING class
vlan-2110
PRINTING ALL SVIs VIA DME
{
  "id": "vlan1",
  "adminSt": "down",
  "operSt": "down"
}
{
  "id": "vlan2110",
  "adminSt": "up",
  "operSt": "down"
}
{
  "id": "vlan1073",
  "adminSt": "down",
  "operSt": "down"
}
{
  "id": "vlan10",
  "adminSt": "down",
  "operSt": "down"
}
{
  "id": "vlan3199",
  "adminSt": "up",
  "operSt": "down"
}
{
  "id": "vlan3299",
  "adminSt": "up",
  "operSt": "up"
}
{
  "id": "vlan3399",
  "adminSt": "up",
  "operSt": "down"
}
{
  "id": "vlan1010",
  "adminSt": "down",
  "operSt": "down"
}
{
  "id": "vlan1072",
  "adminSt": "down",
  "operSt": "down"
}
PRINTING ALL SVIs VIA DME SUING class
{
  "id": "vlan1",
  "adminSt": "down",
  "operSt": "down"
}
{
  "id": "vlan2110",
  "adminSt": "up",
  "operSt": "down"
}
{
  "id": "vlan1073",
  "adminSt": "down",
  "operSt": "down"
}
{
  "id": "vlan10",
  "adminSt": "down",
  "operSt": "down"
}
{
  "id": "vlan3199",
  "adminSt": "up",
  "operSt": "down"
}
{
  "id": "vlan3299",
  "adminSt": "up",
  "operSt": "up"
}
{
  "id": "vlan3399",
  "adminSt": "up",
  "operSt": "down"
}
{
  "id": "vlan1010",
  "adminSt": "down",
  "operSt": "down"
}
{
  "id": "vlan1072",
  "adminSt": "down",
  "operSt": "down"
}
PRINTING ALL THE SVI VIA RESTCONF
{
  "fabEncap": "vlan-3399",
  "id": 3399
}
{
  "fabEncap": "vlan-2110",
  "id": 2110
}
{
  "fabEncap": "vlan-3299",
  "id": 3299
}
{
  "fabEncap": "vlan-1066",
  "id": 1066
}
{
  "fabEncap": "vlan-5",
  "id": 5
}
{
  "fabEncap": "vlan-1174",
  "id": 1174
}
{
  "fabEncap": "vlan-20",
  "id": 20
}
{
  "fabEncap": "vlan-1000",
  "id": 1000
}
{
  "fabEncap": "vlan-3199",
  "id": 3199
}
{
  "fabEncap": "vlan-1020",
  "id": 1020
}
{
  "fabEncap": "vlan-1173",
  "id": 1173
}
{
  "fabEncap": "vlan-1072",
  "id": 1072
}
{
  "fabEncap": "vlan-1010",
  "id": 1010
}
{
  "fabEncap": "vlan-1",
  "id": 1
}
{
  "fabEncap": "vlan-1073",
  "id": 1073
}
{
  "fabEncap": "vlan-4",
  "id": 4
}
{
  "fabEncap": "vlan-3",
  "id": 3
}
{
  "fabEncap": "vlan-2",
  "id": 2
}
PRINTING ALL SVI VLAN2110 VIA RESTCONF
{
  "fabEncap": "vlan-1010",
  "id": 1010
}
PRINTING ALL SVI VLAN2110 VIA RESTCONF VLAN-NAME
vlan-1010
PRINTING SHOW VLAN BRIEF VIA NX-API CLI
{
  "id": "1",
  "name": "default"
}
{
  "id": "2",
  "name": "Server"
}
{
  "id": "3",
  "name": "PC"
}
{
  "id": "4",
  "name": "Print"
}
{
  "id": "5",
  "name": "VLAN_5_Task_112"
}
{
  "id": "20",
  "name": "VLAN0020"
}
{
  "id": "1000",
  "name": "VLAN1000"
}
{
  "id": "1010",
  "name": "VLAN1010"
}
{
  "id": "1020",
  "name": "VLAN1020"
}
{
  "id": "1066",
  "name": "Pod_10_from_cli"
}
{
  "id": "1072",
  "name": "Pod10Task72"
}
{
  "id": "1073",
  "name": "Pod10Task73"
}
{
  "id": "1173",
  "name": "pyATS_VLAN-SoTH-Testing"
}
{
  "id": "1174",
  "name": "pyATS_SoTH_VLAN_1174"
}
{
  "id": "2110",
  "name": "Challenge-201"
}
{
  "id": "3199",
  "name": "dev99"
}
{
  "id": "3299",
  "name": "test99"
}
{
  "id": "3399",
  "name": "prod99"
}
PRINTING SHOW IP INT BRIEF VIA NX-API CLI
{
  "name": "Vlan10",
  "ip": "192.168.22.3"
}
{
  "name": "Vlan2110",
  "ip": "201.201.201.201"
}
{
  "name": "Vlan3199",
  "ip": "10.31.99.1"
}
{
  "name": "Vlan3299",
  "ip": "10.32.99.1"
}
{
  "name": "Vlan3399",
  "ip": "10.33.99.1"
}
{
  "name": "Lo0",
  "ip": "10.0.0.73"
}
{
  "name": "Eth1/2",
  "ip": "10.0.13.31"
}
{
  "name": "Eth1/3",
  "ip": "10.4.0.73"
}
{
  "name": "Eth1/4",
  "ip": "10.1.0.73"
}
PRINTING SHOW VLAN NAME PROD99 VIA NX-API CLI
{
  "ports": "Ethernet1/30,Ethernet1/50",
  "mode": "ce-vlan"
}
PRINTING SHOW RUNNING-CONFIG BGP VIA NX-API CLI (XML)
<?xml version="1.0"?>
<ins_api>
  <type>cli_show_ascii</type>
  <version>1.0</version>
  <sid>eoc</sid>
  <outputs>
    <output>
      <body>
!Command: show running-config bgp
!No configuration change since last restart
!Time: Sat Apr 11 03:56:01 2026

version 9.3(8) Bios:version  
feature bgp

router bgp 65003
  router-id 10.0.0.73
  address-family ipv4 unicast
    redistribute static route-map nx9K73_BGP_to_cat8Kv71
    redistribute ospf 111 route-map nx9K73_BGP_to_cat8Kv71
  neighbor 10.0.13.13
    remote-as 65001
    address-family ipv4 unicast
      route-map nx9K73_BGP_to_cat8Kv71 in
      route-map nx9K73_BGP_to_cat8Kv71 out
vrf context challenge-309
  rd 309:309
vrf context challenge-309_2
  rd 99:99
vrf context challenge-309_3
  rd 3093:3093
vrf context challenge-A5
  rd 53:53


</body>
      <input>show running-config bgp</input>
      <msg>Success</msg>
      <code>200</code>
    </output>
  </outputs>
</ins_api>
```

</details>

---

## Solution Code

<details>
<summary>Click to Display</summary>

```bash
#!/bin/bash
###############################################################################
#! NX-OS has THREE API types:
#!
#! API              | Endpoint              | Auth Method                          | Model
#! -----------------|-----------------------|--------------------------------------|----------------
#! NX-API CLI       | /ins                  | Basic Auth (-u user:pass)            | CLI over HTTP
#! NX-API REST(DME) | /api/mo/, /api/class/ | aaaLogin.json -> APIC-cookie token   | ACI-style MIT
#! RESTCONF         | /restconf/data/       | Basic Auth (-u user:pass)            | YANG
#!
#! feature nxapi    -> enables NX-API CLI + NX-API REST(DME) + HTTP server
#! feature restconf -> enables RESTCONF (runs on top of nxapi HTTP server)
#!
#! switch(config)# feature nxapi
#! switch(config)# nxapi https port 443
#! switch(config)# feature restconf
###############################################################################

export NXOS_USERNAME="expert"
export NXOS_PASSWORD='1234QWer!'
export NXOS_URI="192.168.89.73"

###############################################################################
#! NX-API DME (feature nxapi) — uses APIC-cookie token
###############################################################################

#! TODO-1 : Login and extract token (-d implies POST, no need for -X POST)
export token=$(curl -sk "https://$NXOS_URI/api/aaaLogin.json" \
  -H 'content-type: application/json' \
  -d "{
        \"aaaUser\" : {
            \"attributes\" : {
                \"name\" : "$NXOS_USERNAME",
                \"pwd\" : "$NXOS_PASSWORD"
            }
        }
    }" | jq -r '.imdata[0].aaaLogin.attributes.token')

echo $token

#! TODO-2 : Query all VLANs via DME (GET is default, no need for -X GET)
echo "PRINTING ALL VLANS VIA DME"

curl -sk --globoff "https://$NXOS_URI/api/mo/sys/bd.json?rsp-subtree=children&rsp-subtree-filter=wcard(l2BD.fabEncap,\"vlan\")&rsp-subtree-include=required&rsp-subtree-class=l2BD" \
  -H "Cookie: APIC-cookie=$token" \
  | jq '.imdata[].bdEntity.children[].l2BD.attributes | {id, name, fabEncap}'

#! TODO-3 : Query specific VLAN 2110 via DME
echo "PRINTING VLAN 2110 VIA DME"

curl -sk --globoff "https://$NXOS_URI/api/mo/sys/bd/bd-[vlan-2110].json" \
  -H "Cookie: APIC-cookie=$token" | jq '.imdata[].l2BD.attributes | {id, dn, fabEncap}'

echo "PRINTING VLAN 2110 VIA DME USING class"
curl -sk "https://$NXOS_URI/api/class/l2BD.json?query-target-filter=eq(l2BD.id,\"2110\")" \
  -H "Cookie: APIC-cookie=$token" | jq -r '.imdata[0].l2BD.attributes.fabEncap'

#! TODO-4 : Query all SVIs via DME
echo "PRINTING ALL SVIs VIA DME"

curl -sk "https://$NXOS_URI/api/mo/sys/intf.json?query-target=subtree&target-subtree-class=sviIf" \
  -H "Cookie: APIC-cookie=$token" | jq '.imdata[].sviIf.attributes | {id, adminSt, operSt}'

echo "PRINTING ALL SVIs VIA DME SUING class"
curl -sk "https://$NXOS_URI/api/class/sviIf.json" \
  -H "Cookie: APIC-cookie=$token" | jq '.imdata[].sviIf.attributes | {id, adminSt, operSt}'

# ###############################################################################
# #! RESTCONF (feature restconf) — uses Basic Auth, no token needed
# ###############################################################################

#! TODO-5 : Query SVI vlan2110 via RESTCONF
echo "PRINTING ALL THE SVI VIA RESTCONF"

curl -sk "https://$NXOS_URI/restconf/data/Cisco-NX-OS-device:System/bd-items" \
  -H 'accept: application/yang.data+json' \
  -u $NXOS_USERNAME:$NXOS_PASSWORD | jq '."bd-items"."bd-items"."BD-list"[] | {fabEncap, id}'

echo "PRINTING ALL SVI VLAN2110 VIA RESTCONF"
curl -sk "https://$NXOS_URI/restconf/data/Cisco-NX-OS-device:System/bd-items/bd-items/BD-list=vlan-1010" \
  -H 'accept: application/yang.data+json' \
  -u $NXOS_USERNAME:$NXOS_PASSWORD | jq '."BD-list"[] | {fabEncap, id}'

echo "PRINTING ALL SVI VLAN2110 VIA RESTCONF VLAN-NAME"
curl -sk "https://$NXOS_URI/restconf/data/Cisco-NX-OS-device:System/bd-items/bd-items/BD-list=vlan-1010" \
  -H 'accept: application/yang.data+json' \
  -u $NXOS_USERNAME:$NXOS_PASSWORD | jq -r '."BD-list"[0].fabEncap'

# ###############################################################################
# #! NX-API CLI (feature nxapi) — uses Basic Auth, sends CLI commands over HTTP
# ###############################################################################

#! TODO-6 : "show vlan brief" via NX-API CLI (output JSON)
echo "PRINTING SHOW VLAN BRIEF VIA NX-API CLI"

curl -sk "https://$NXOS_URI/ins" \
  -H 'content-type: application/json' \
  -u $NXOS_USERNAME:$NXOS_PASSWORD \
  -d '{
    "ins_api": {
      "version": "1.0",
      "type": "cli_show",
      "chunk": "0",
      "sid": "1",
      "input": "show vlan brief",
      "output_format": "json"
    }
}' | jq '.ins_api.outputs.output.body.TABLE_vlanbriefxbrief.ROW_vlanbriefxbrief[] | {id: .["vlanshowbr-vlanid"], name: .["vlanshowbr-vlanname"]}'

#! TODO-7 : "show ip int brief" via NX-API CLI (output JSON)
echo "PRINTING SHOW IP INT BRIEF VIA NX-API CLI"

curl -sk "https://$NXOS_URI/ins" \
  -H 'content-type: application/json' \
  -u $NXOS_USERNAME:$NXOS_PASSWORD \
  -d '{
    "ins_api": {
      "version": "1.0",
      "type": "cli_show",
      "chunk": "0",
      "sid": "1",
      "input": "show ip interface brief",
      "output_format": "json"
    }
}' | jq '.ins_api.outputs.output.body.TABLE_intf.ROW_intf[] | {name: .["intf-name"], ip: .prefix}'

#! TODO-8 : "show vlan name prod99" via NX-API CLI (output JSON)
echo "PRINTING SHOW VLAN NAME PROD99 VIA NX-API CLI"

curl -sk "https://$NXOS_URI/ins" \
  -H 'content-type: application/json' \
  -u $NXOS_USERNAME:$NXOS_PASSWORD \
  -d '{
    "ins_api": {
      "version": "1.0",
      "type": "cli_show",
      "chunk": "0",
      "sid": "1",
      "input": "show vlan name prod99",
      "output_format": "json"
    }
}' | jq '{ports: .ins_api.outputs.output.body.TABLE_vlanbriefname.ROW_vlanbriefname["vlanshowplist-ifidx"], mode: .ins_api.outputs.output.body.TABLE_mtuinfoname.ROW_mtuinfoname["vlanshowinfo-vlanmode"]}'

# #! TODO-9 : "show running-config bgp" via NX-API CLI (output XML)
echo "PRINTING SHOW RUNNING-CONFIG BGP VIA NX-API CLI (XML)"

curl -sk "https://$NXOS_URI/ins" \
  -H 'content-type: application/json' \
  -u $NXOS_USERNAME:$NXOS_PASSWORD \
  -d '{
    "ins_api": {
      "version": "1.0",
      "type": "cli_show_ascii",
      "chunk": "0",
      "sid": "1",
      "input": "show running-config bgp",
      "output_format": "xml"
    }
}'
```
</details>
---