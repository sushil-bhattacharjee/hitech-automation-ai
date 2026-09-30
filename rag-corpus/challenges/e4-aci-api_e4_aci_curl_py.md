# Curl Command Study Guide

<details>
<summary>Click to expand the full curl reference guide</summary>

## Authentication

### `-H` (Generic Header)

Sets any HTTP header manually. You control the full header string.

```bash
# Setting a cookie via raw header
curl -H "Cookie: APIC-cookie=${token}" https://example.com/api

# Setting auth token
curl -H "Authorization: Bearer ${token}" https://example.com/api

# Multiple headers
curl -H "Accept: application/json" \
     -H "Content-Type: application/json" \
     https://example.com/api
```

### `-b` (Cookie Shorthand)

Curl's built-in cookie mechanism. Curl constructs the `Cookie` header for you from the key=value pair.

```bash
# These two produce the exact same HTTP request:
curl -H "Cookie: APIC-cookie=${token}" https://example.com/api
curl -b "APIC-cookie=${token}" https://example.com/api

# Both send this on the wire:
#   Cookie: APIC-cookie=<your_token_value>
```

`-b` can also read cookies from a file:

```bash
curl -b cookies.txt https://example.com/api
```

### `-u` (Basic Auth)

Shorthand for HTTP Basic Authentication. Curl base64-encodes `user:password` and sends it as an `Authorization` header.

```bash
# Using -u
curl -u admin:secret https://example.com/api

# Equivalent manual header
curl -H "Authorization: Basic YWRtaW46c2VjcmV0" https://example.com/api

# Prompt for password (more secure, avoids password in shell history)
curl -u admin https://example.com/api
```

---

## Sending Data

### `-d` (POST Data)

Sends data in the request body. Automatically sets the method to POST. By default curl sets `Content-Type: application/x-www-form-urlencoded`, but `-d` itself doesn't validate or transform the data — it just sends whatever you give it as the body. You can override the Content-Type with `-H` to tell the server the actual format.

```bash
# Default Content-Type: application/x-www-form-urlencoded
curl -d '{"name":"admin"}' https://example.com/api
# Server may reject this because the header says form-urlencoded but the body is JSON

# Override to JSON — now the header matches the actual data format
curl -d '{"name":"admin"}' \
  -H "Content-Type: application/json" \
  https://example.com/api

# Embedding bash variables inside JSON (break out of single quotes)
curl -X POST https://example.com/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "aaaUser": {
      "attributes": {
        "name": "'"${APIC_USRNAME}"'",
        "pwd": "'"${APIC_PASSWORD}"'"
      }
    }
  }'
```

**Key point:** `-d` is just "send this as the body." The `-H Content-Type` header tells the **server** how to interpret that body. Curl doesn't care if they match or not.

### `--data-urlencode` (URL-Encoded Data)

Like `-d` but **automatically encodes** special characters (spaces, slashes, quotes, etc.). `-d` sends data exactly as-is with no encoding.

```bash
# -d: sends literally — the /24 goes unencoded
curl -d "filter=eq(fvSubnet.ip,10.1.7.1/24)" https://example.com/api
# Body: filter=eq(fvSubnet.ip,10.1.7.1/24)

# --data-urlencode: encodes the slash automatically
curl --data-urlencode "filter=eq(fvSubnet.ip,10.1.7.1/24)" https://example.com/api
# Body: filter=eq(fvSubnet.ip,10.1.7.1%2F24)
```

When your values contain special characters (which ACI filter expressions often do), `--data-urlencode` is safer. With `-d` you'd need to manually percent-encode them yourself.

### `-G` (Force GET with Query Parameters)

Takes data from `-d` or `--data-urlencode` and appends it to the URL as query string parameters instead of sending as POST body.

```bash
# With -G: becomes GET /api/endpoint.json?key=value&foo=bar
curl -G "https://example.com/api/endpoint.json" \
  --data-urlencode "key=value" \
  --data-urlencode "foo=bar"

# Without -G: becomes POST with body "key=value&foo=bar"
curl "https://example.com/api/endpoint.json" \
  --data-urlencode "key=value" \
  --data-urlencode "foo=bar"
```

**Why use `-G` with `--data-urlencode`?**

- Each parameter gets its own line — much more readable
- Special characters are auto-encoded (spaces, quotes, slashes)
- Easier to comment out individual parameters for debugging

---

## Query String Approaches Compared

### Approach 1: Inline Query String

Compact but you must handle encoding and escaping yourself.

```bash
curl -sk "$APIC_BASEURL/class/fvSubnet.json?query-target-filter=wcard(fvSubnet.ip,\"10.1.7.1\")" \
  -H "Cookie: APIC-cookie=${token}"
```

### Approach 2: `--data-urlencode` with `-G`

Each param on its own line, auto-encoded. More readable for complex queries.

```bash
curl -sk -G "${APIC_BASEURL}/class/fvBD.json" \
  --data-urlencode "rsp-subtree=full" \
  --data-urlencode "rsp-subtree-class=fvSubnet" \
  --data-urlencode 'rsp-subtree-filter=eq(fvSubnet.ip,"10.1.7.1/24")' \
  --data-urlencode "rsp-subtree-include=required" \
  -H "Cookie: APIC-cookie=${token}"
```

### Approach 3: Variables with Inline Query String

Store query in a variable, then interpolate. Watch out for quoting issues.

```bash
# Single quotes with literal double quotes inside — cleanest
query='query-target-filter=wcard(fvSubnet.ip,"10.1.7.1")'
curl -sk "$APIC_BASEURL/class/fvSubnet.json?${query}" \
  -H "Cookie: APIC-cookie=${token}"
```

### Approach 4: Variables with `--data-urlencode`

Store each param in a variable, pass with `--data-urlencode`.

```bash
param1='rsp-subtree=full'
param2='rsp-subtree-class=fvSubnet'
param3='rsp-subtree-filter=eq(fvSubnet.ip,"10.1.7.1/24")'
curl -sk -G "${APIC_BASEURL}/class/fvBD.json" \
  --data-urlencode "$param1" \
  --data-urlencode "$param2" \
  --data-urlencode "$param3" \
  -H "Cookie: APIC-cookie=${token}"
```

---

## Common Flags

| Flag | Purpose |
|------|---------|
| `-s` | Silent mode — hides progress bar and error messages |
| `-k` | Insecure — skip TLS certificate verification (like Python's `verify=False`) |
| `-X` | Set HTTP method explicitly (`-X POST`, `-X PUT`, `-X DELETE`) |
| `-G` | Convert POST data to GET query parameters |
| `-g` / `--globoff` | Disable URL globbing — treat `[ ] { }` in URLs literally |
| `-o` | Write output to file instead of stdout |
| `-v` | Verbose — shows full request/response headers (useful for debugging) |
| `-L` | Follow redirects |

---

## `-G` vs `-g`: Two Very Different Flags

Despite looking similar, these solve completely different problems.

`-G` (uppercase) redirects `--data-urlencode` / `-d` data from the POST body to the URL as query parameters. It affects **query parameters**.

`-g` / `--globoff` (lowercase) stops curl from interpreting `[ ]` and `{ }` in the URL path as glob patterns. It affects the **URL path**.

```bash
# -G: encodes query params and appends to URL
curl -sk -G "${APIC_BASEURL}/class/fvBD.json" \
  --data-urlencode 'rsp-subtree-filter=eq(fvSubnet.ip,"10.1.7.1/24")'

# -g: prevents curl from treating [10.1.7.1/24] as a glob range in the URL path
curl -sk -g "${APIC_BASEURL}/node/mo/uni/tn-Pod-10/subnet-[10.1.7.1/24].json"

# You may need BOTH when the URL path has brackets AND you have query params
curl -sk -g -G "${APIC_BASEURL}/node/mo/uni/tn-Pod-10/subnet-[10.1.7.1/24].json" \
  --data-urlencode "query-target=self" \
  -H "Cookie: APIC-cookie=${token}"
```

In short:

- `--data-urlencode` + `-G` → encodes special characters in **query parameters**
- `-g` / `--globoff` → protects special characters like `[ ] { }` in the **URL path**

---

## Quoting and Escaping Gotchas

### Single vs Double Quotes in Bash

```bash
# Double quotes: bash expands variables and interprets \" as literal "
query="query-target-filter=wcard(fvSubnet.ip,\"10.1.7.1\")"
# Result: query-target-filter=wcard(fvSubnet.ip,"10.1.7.1")

# Single quotes: bash does ZERO interpretation — everything is literal
query='query-target-filter=wcard(fvSubnet.ip,"10.1.7.1")'
# Result: query-target-filter=wcard(fvSubnet.ip,"10.1.7.1")

# WRONG — single quotes with backslash escapes
query='query-target-filter=wcard(fvSubnet.ip,\"10.1.7.1\")'
# Result: query-target-filter=wcard(fvSubnet.ip,\"10.1.7.1\")
# The backslashes are kept literally! This breaks the API query.
```

### Spaces in Filter Expressions

When using inline query strings (not `--data-urlencode`), spaces are NOT encoded automatically and will break the URL.

```bash
# WRONG — space after comma breaks the query
query='query-target-filter=wcard(fvSubnet.dn, "10.1.7.1")'

# CORRECT — no space
query='query-target-filter=wcard(fvSubnet.dn,"10.1.7.1")'

# With --data-urlencode, the space would be auto-encoded to %20, so it works either way
```

### Variable Syntax: `$var` vs `${var}`

```bash
token="abc123"

# Both work when variable boundary is clear
echo "$token"      # abc123
echo "${token}"    # abc123

# Braces required when followed by text with no separator
echo "${token}value"   # abc123value
echo "$tokenvalue"     # empty — bash looks for variable named tokenvalue
```

---

## Piping to jq

Curl output is raw JSON. Pipe to `jq` to extract fields.

```bash
# Extract a single field
curl -sk ... | jq -r '.imdata[0].aaaLogin.attributes.token'

# Loop over array entries
curl -sk ... | jq -r '.imdata[].fvSubnet.attributes.dn'

# Extract multiple fields per entry
curl -sk ... | jq -r '.imdata[].fvSubnet.attributes | "\(.dn)\n\(.ip)"'

# First element only
curl -sk ... | jq -r '.imdata[0].fvSubnet.attributes.dn, .imdata[0].fvSubnet.attributes.ip'
```

---

## Bash Multiline Comments

Bash has no native block comment. Use a here-document with a no-op command:

```bash
: <<'COMMENT'
This is a multiline comment.
None of this gets executed.
COMMENT
```

The single quotes around `COMMENT` prevent variable expansion inside the block. `"""` does not work in bash (that's Python).

```bash
#!/bin/bash

# Login and get token
token=$(curl -sk -X POST "${APIC_BASEURL}/aaaLogin.json" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg u "$APIC_USRNAME" --arg p "$APIC_PASSWORD" \
    '{aaaUser: {attributes: {name: $u, pwd: $p}}}')" \
  | jq -r '.imdata[0].aaaLogin.attributes.token')

# TODO-1/2: Find subnet DN with subnet=10.1.7.1/24
echo -e "\nPRINTING SUBNET DN with subnet=10.1.7.1/24"
curl -sk "${APIC_BASEURL}/class/fvSubnet.json?query-target-filter=wcard(fvSubnet.dn,\"10.1.7.1/24\")" \
  -H "Cookie: APIC-cookie=${token}" \
  | jq -r '.imdata[].fvSubnet.attributes.dn'

# TODO-3/4: Find BD DN that has child subnet=10.1.7.1/24
echo -e "\nPRINTING BRIDGE DOMAIN DN with subnet=10.1.7.1/24"
curl -sk -G "${APIC_BASEURL}/class/fvBD.json" \
  --data-urlencode "rsp-subtree=children" \
  --data-urlencode "rsp-subtree-class=fvSubnet" \
  --data-urlencode 'rsp-subtree-filter=eq(fvSubnet.ip,"10.1.7.1/24")' \
  --data-urlencode "rsp-subtree-include=required" \
  -H "Cookie: APIC-cookie=${token}" \
  | jq -r '.imdata[].fvBD.attributes.dn'
```
</details>

---

#### TODO-1: Fill the query so that it can query the filter for the dn subnet-[10.1.7.1/24]
#### TODO-2: Build the url to query the class for fvSubnet
#### TODO-3: Build the url for the class fvBD
#### TODO-4: Build the params which would query the bd-dn that has child dn subnet-[10.1.7.1/24]

## Initital File: e4_subnet_filtering.py
```python
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import os

username=os.getenv("APIC_USRNAME")
password=os.getenv("APIC_PASSWORD")
base_url=os.getenv("APIC_BASEURL")
#url = f"{base_url}/aaaLogin.json"
payload={
  "aaaUser": {
    "attributes": {
      "name": f"{username}",
      "pwd": f"{password}"
    }
  }
}

headers = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
}
response = requests.post(f"{base_url}/aaaLogin.json", headers=headers, json=payload, verify=False).json()
token=response['imdata'][0]['aaaLogin']['attributes']['token']

#TODO : Find the dn for subnet that consists subnet=10.1.7.1/24
#! EXPECTED OUTPUT: TODO-1+2
"""
TODO-2: PRINTING SUBNET DN with subnet=10.1.7.1/24
uni/tn-challenge-b6/BD-DevOps-BD/subnet-[10.1.7.1/24]
uni/tn-challenge-b6/BD-HR-BD/subnet-[10.1.7.1/24]
uni/tn-Pod-10-Challenge-408/BD-NET-10.10.10.0/subnet-[10.1.7.1/24]
"""

headers = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
  'Cookie': f"APIC-cookie={token}"
}
#TODO-1: Fill the query so that it can query the filter for the dn subnet-[10.1.7.1/24]
query='TODO-1'
#TODO-2: Build the url to query the class for fvSubnet
subnet_url=
response = requests.get(subnet_url, headers=headers, verify=False).json()
print("\nPRINTING SUBNET DN with subnet=10.1.7.1/24")
for entry in response['imdata']:
    print(entry['fvSubnet']['attributes']['dn'])

#TODO : Find the dn for BD that consists subnet=10.1.7.1/24
#! EXPECTED OUTPUT: TODO3+4
"""
TOD-4: PRINTING BRIDGE DOMAIN DN with subnet=10.1.7.1/24
uni/tn-Pod-10-Challenge-408/BD-NET-10.10.10.0
uni/tn-challenge-b6/BD-HR-BD
uni/tn-challenge-b6/BD-DevOps-BD
"""
#TODO-3: Build the url for the class fvBD
bd_url = 
#TODO-4: Build the params which would query the bd-dn that has child dn subnet-[10.1.7.1/24]


params = {



}
headers = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
  'Cookie': f"APIC-cookie={token}"
}

response = requests.get(bd_url, headers=headers, params=params, verify=False).json()
print("\nPRINTING BRIDGE DOMAIN DN with subnet=10.1.7.1/24")
for entry in response['imdata']:
    print(entry['fvBD']['attributes']['dn'])

#TODO : Fill the query and url for filtering dn BD-NET-10.10.10.0 for all subnet which has ip=10.1.7.1/24
#! EXPECTED OUTPUT: 
"""
TODO-5: PRINTING SUBNET DN with subnet=10.1.7.1/24
uni/tn-Pod-10-Challenge-408/BD-NET-10.10.10.0/subnet-[10.1.7.1/24]
10.1.7.1/24
"""

#TODO-5: Fill the query
query='TODO-5'
bd_mo_url=f"{base_url}/node/mo/uni/tn-p2-pod-10-challenge-408/BD-NET-10.10.10.0.json?{query}"
headers = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
  'Cookie': f"APIC-cookie={token}"
}
response = requests.get(bd_mo_url, headers=headers, verify=False).json()
print("\nPRINTING SUBNET DN with subnet=10.1.7.1/24")
print(response['imdata'][0]['fvSubnet']['attributes']['dn'])
print(response['imdata'][0]['fvSubnet']['attributes']['ip'])

#TODO-6 : Fill the query
#! EXPECTED OUTPUT:
"""
TODO-6: PRINTING SUBNET DN with subnet=10.1.7.1/24
uni/tn-Pod-10-Challenge-408/BD-NET-10.10.10.0/subnet-[10.1.7.1/24]
10.1.7.1/24
"""

query='TODO-6'
tenant_mo_url=f"{base_url}/node/mo/uni/tn-p2-pod-10-challenge-408.json?{query}"
headers = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
  'Cookie': f"APIC-cookie={token}"
}
response = requests.get(tenant_mo_url, headers=headers, verify=False).json()
print("\nPRINTING SUBNET DN with subnet=10.1.7.1/24")
for entry in response['imdata']:
  print(entry['fvSubnet']['attributes']['dn'])
  print(entry['fvSubnet']['attributes']['ip'])
```

## Initial File-2: e4_subnet_filter.sh
```bash
#!/bin/bash

# Login and get token
token=$(curl -sk -X POST "${APIC_BASEURL}/aaaLogin.json" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "aaaUser": {
      "attributes": {
        "name": "'"${APIC_USRNAME}"'",
        "pwd": "'"${APIC_PASSWORD}"'"
      }
    }
  }' | jq -r '.imdata[0].aaaLogin.attributes.token')

# TODO-1/2: Find subnet DN with subnet=10.1.7.1/24
: <<'COMMENT'
TODO-2: PRINTING SUBNET DN with subnet=10.1.7.1/24
uni/tn-challenge-b6/BD-DevOps-BD/subnet-[10.1.7.1/24]
uni/tn-challenge-b6/BD-HR-BD/subnet-[10.1.7.1/24]
uni/tn-Pod-10-Challenge-408/BD-NET-10.10.10.0/subnet-[10.1.7.1/24]
COMMENT

echo -e "\nTODO-1/2:PRINTING SUBNET DN with subnet=10.1.7.1/24"
#TODO-1: Fill the query so that it can query the filter for the dn subnet-[10.1.7.1/24]
query1='#TODO-1'
#TODO-2: Build the url to query the class for fvSubnet
subnet_url='#TODO-2'
curl -sk "$APIC_BASEURL/${subnet_url}?${query1}" \
  -H "Cookie: APIC-cookie=${token}" \
  | jq -r '.imdata[].fvSubnet.attributes.dn'

# TODO-3/4: Find BD DN that has child subnet=10.1.7.1/24
: <<'COMMENT'
TODO-4: PRINTING BRIDGE DOMAIN DN with subnet=10.1.7.1/24
uni/tn-Pod-10-Challenge-408/BD-NET-10.10.10.0
uni/tn-challenge-b6/BD-HR-BD
uni/tn-challenge-b6/BD-DevOps-BD
COMMENT

echo -e "\nTODO-3/4:PRINTING BRIDGE DOMAIN DN with subnet=10.1.7.1/24"
#TODO-3: Build the url for the class fvBD
todo_3_url='#TODO-3'
#TODO-4: Build the params which would query the bd-dn that has child dn subnet-[10.1.7.1/24]
param4_1='#TODO-4'
param4_2='#TODO-4'
param4_3='#TODO-4'
param4_4='#TODO-4'
curl -sk -G "${APIC_BASEURL}/$todo_3_url" \
  --data-urlencode "$param4_1" \
  --data-urlencode "$param4_2" \
  --data-urlencode "$param4_3" \
  --data-urlencode "$param4_4" \
  -H "Cookie: APIC-cookie=${token}" \
  | jq -r '.imdata[].fvBD.attributes.dn'

# TODO-5: Query specific BD MO for subnet with ip=10.1.7.1/24
: <<'COMMENT'
TODO-5: PRINTING SUBNET DN with subnet=10.1.7.1/24
uni/tn-p4-challenge-b6/BD-Staging-BD/subnet-[10.1.7.1/24]
10.1.7.1/24
COMMENT

param5_1='#TODO-5'
param5_2='#TODO-5'
param5_3='#TODO-5'
echo -e "\nTODO-5:PRINTING SUBNET DN with subnet=10.1.7.1/24"
curl -sk -G "${APIC_BASEURL}/node/mo/uni/tn-p4-challenge-b6/BD-Staging-BD.json" \
  --data-urlencode "$param5_1" \
  --data-urlencode "$param5_2" \
  --data-urlencode "$param5_3" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -b "APIC-cookie=${token}" \
  | jq -r '.imdata[0].fvSubnet.attributes.dn, .imdata[0].fvSubnet.attributes.ip'

# TODO-6: Query tenant MO subtree for subnet with ip=10.1.7.1/24
: <<'COMMENT'
TODO-6: PRINTING SUBNET DN with subnet=10.1.7.1/24
uni/tn-p4-challenge-b6/BD-Staging-BD/subnet-[10.1.7.1/24]
10.1.7.1/24
COMMENT

query6='#TODO-6'
echo -e "\nTODO-6:PRINTING SUBNET DN with subnet=10.1.7.1/24"
curl -sk "${APIC_BASEURL}/node/mo/uni/tn-p4-challenge-b6.json?${query6}" \
  -H "Cookie: APIC-cookie=${token}" \
  | jq -r '.imdata[].fvSubnet.attributes | "\(.dn)\n\(.ip)"'
```

## Expected Output
```
sushil@ubuntupro:~/DevnetExpert/mock3/e4_aci_bd$ uv run python e4_subnet_filtering.py 

PRINTING SUBNET DN with subnet=10.1.7.1/24
uni/tn-p2-pod-10-challenge-408/BD-NET-10.10.10.0/subnet-[10.1.7.1/24]
uni/tn-p2-challenge-b6/BD-DevOps-BD/subnet-[10.1.7.1/24]
uni/tn-p2-challenge-b6/BD-Staging-BD/subnet-[10.1.7.1/24]

PRINTING BRIDGE DOMAIN DN with subnet=10.1.7.1/24
uni/tn-p2-challenge-b6/BD-DevOps-BD
uni/tn-p2-challenge-b6/BD-Staging-BD
uni/tn-p2-pod-10-challenge-408/BD-NET-10.10.10.0
```

## Solution as Last resort
<details>
<summary>Click here to display</summary>

```python
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import os

username=os.getenv("APIC_USRNAME")
password=os.getenv("APIC_PASSWORD")
base_url=os.getenv("APIC_BASEURL")
#url = f"{base_url}/aaaLogin.json"
payload={
  "aaaUser": {
    "attributes": {
      "name": f"{username}",
      "pwd": f"{password}"
    }
  }
}

headers = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
}
response = requests.post(f"{base_url}/aaaLogin.json", headers=headers, json=payload, verify=False).json()
token=response['imdata'][0]['aaaLogin']['attributes']['token']

#TODO : Find the dn for subnet that consists subnet=10.1.7.1/24

headers = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
  'Cookie': f"APIC-cookie={token}"
}
#TODO-1: Fill the query so that it can query the filter for the dn subnet-[10.1.7.1/24]
query='query-target-filter=wcard(fvSubnet.dn, "10.1.7.1/24")'
#TODO-2: Build the url to query the class for fvSubnet
subnet_url=f"{base_url}/class/fvSubnet.json?{query}"
response = requests.get(subnet_url, headers=headers, verify=False).json()
print("\nTODO-2: PRINTING SUBNET DN with subnet=10.1.7.1/24")
for entry in response['imdata']:
    print(entry['fvSubnet']['attributes']['dn'])

#TODO : Find the dn for BD that consists subnet=10.1.7.1/24

#TODO-3: Build the url for the class fvBD
bd_url = f"{base_url}/class/fvBD.json"
#TODO-4: Build the params which would query the bd-dn that has child dn subnet-[10.1.7.1/24]
params = {
    "rsp-subtree": "children",
    "rsp-subtree-class": "fvSubnet",
    "rsp-subtree-filter": 'eq(fvSubnet.ip,"10.1.7.1/24")',
    "rsp-subtree-include": "required"
}
headers = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
  'Cookie': f"APIC-cookie={token}"
}

response = requests.get(bd_url, headers=headers, params=params, verify=False).json()
print("\nTODO-4: PRINTING BRIDGE DOMAIN DN with subnet=10.1.7.1/24")
for entry in response['imdata']:
    print(entry['fvBD']['attributes']['dn'])

#TODO : Fill the query and url for filtering dn BD-NET-10.10.10.0 for all subnet which has ip=10.1.7.1/24
#TODO-5: Fill the query
query='query-target=children&target-subtree-class=fvSubnet&query-target-filter=eq(fvSubnet.ip, "10.1.7.1/24")'
bd_mo_url=f"{base_url}/node/mo/uni/tn-p2-pod-10-challenge-408/BD-NET-10.10.10.0.json?{query}"
headers = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
  'Cookie': f"APIC-cookie={token}"
}
response = requests.get(bd_mo_url, headers=headers, verify=False).json()
print("\nTODO-5: PRINTING SUBNET DN with subnet=10.1.7.1/24")
print(response['imdata'][0]['fvSubnet']['attributes']['dn'])
print(response['imdata'][0]['fvSubnet']['attributes']['ip'])

#TODO-6 : Fill the query
query='query-target=subtree&target-subtree-class=fvSubnet&query-target-filter=eq(fvSubnet.ip, "10.1.7.1/24")'
tenant_mo_url=f"{base_url}/node/mo/uni/tn-p2-pod-10-challenge-408.json?{query}"
headers = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
  'Cookie': f"APIC-cookie={token}"
}
response = requests.get(tenant_mo_url, headers=headers, verify=False).json()
print("\nTODO-6: PRINTING SUBNET DN with subnet=10.1.7.1/24")
for entry in response['imdata']:
  print(entry['fvSubnet']['attributes']['dn'])
  print(entry['fvSubnet']['attributes']['ip'])

```
</details>

## Solution as Last resort for curl
<details>
<summary>Click to display</summary>

```bash
#!/bin/bash

# Login and get token
token=$(curl -sk -X POST "${APIC_BASEURL}/aaaLogin.json" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "aaaUser": {
      "attributes": {
        "name": "'"${APIC_USRNAME}"'",
        "pwd": "'"${APIC_PASSWORD}"'"
      }
    }
  }' | jq -r '.imdata[0].aaaLogin.attributes.token')

# TODO-1/2: Find subnet DN with subnet=10.1.7.1/24
echo -e "\nPRINTING SUBNET DN with subnet=10.1.7.1/24"
curl -sk "${APIC_BASEURL}/class/fvSubnet.json?query-target-filter=wcard(fvSubnet.dn,\"10.1.7.1/24\")" \
  -H "Cookie: APIC-cookie=${token}" \
  | jq -r '.imdata[].fvSubnet.attributes.dn'

# TODO-3/4: Find BD DN that has child subnet=10.1.7.1/24
echo -e "\nPRINTING BRIDGE DOMAIN DN with subnet=10.1.7.1/24"
curl -sk -G "${APIC_BASEURL}/class/fvBD.json" \
  --data-urlencode "rsp-subtree=children" \
  --data-urlencode "rsp-subtree-class=fvSubnet" \
  --data-urlencode 'rsp-subtree-filter=eq(fvSubnet.ip,"10.1.7.1/24")' \
  --data-urlencode "rsp-subtree-include=required" \
  -H "Cookie: APIC-cookie=${token}" \
  | jq -r '.imdata[].fvBD.attributes.dn'
```
</details>