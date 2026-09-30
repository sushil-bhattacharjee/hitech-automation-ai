# ACI Variables Handling
<details>
<summary>Click to Display</summary>

# Terraform Looping and Dynamic Resource Creation Study Guide

## Table of Contents
1. [For_each Fundamentals](#1-for_each-fundamentals)
2. [Working with Lists](#2-working-with-lists)
3. [Working with Maps](#3-working-with-maps)
4. [List of Objects to Map Conversion](#4-list-of-objects-to-map-conversion)
5. [Flatten for Nested Structures](#5-flatten-for-nested-structures)
6. [Dynamic Blocks](#6-dynamic-blocks)
7. [String Interpolation](#7-string-interpolation)
8. [Terraform Console](#8-terraform-console)
9. [ACI Provider 2.17.0 Syntax](#9-aci-provider-2170-syntax)
10. [Best Practices](#10-best-practices)
11. [MCQ Practice Questions](#11-mcq-practice-questions)
12. [Hands-on Exercises](#12-hands-on-exercises)
13. [Quick Reference Tables](#13-quick-reference-tables)
14. [Common Mistakes and Fixes](#14-common-mistakes-and-fixes)
15. [Attribute Types: List vs Block/Object](#15-attribute-types-list-vs-blockobject)
16. [Resource Reference vs Hardcoded Values](#16-resource-reference-vs-hardcoded-values)
17. [Complete Example: Putting It All Together](#17-complete-example-putting-it-all-together)

---

## 1. For_each Fundamentals

### What is `for_each`?
`for_each` is a meta-argument that allows you to create multiple instances of a resource based on a set or map.

### Key Rules
- `for_each` accepts **set** or **map** only (NOT lists directly)
- Each instance gets a unique identifier based on the key
- Access current item using `each.key` and `each.value`

### For_each vs Count

| Feature | `for_each` | `count` |
|---------|-----------|---------|
| Input type | Set or Map | Number |
| Identifier | String key | Numeric index |
| Deletion handling | Removes specific resource | Re-indexes everything |
| Recommended | ✅ Yes | ⚠️ Use sparingly |

---

## 2. Working with Lists

### Problem: Lists are NOT directly allowed in `for_each`

```hcl
variable "vrfs" {
  default = ["Production", "Development", "Testing"]
}

# ❌ This fails
resource "aci_vrf" "vrfs" {
  for_each = var.vrfs  # Error: list not allowed
}

# ✅ Convert to set using toset()
resource "aci_vrf" "vrfs" {
  for_each  = toset(var.vrfs)
  parent_dn = aci_tenant.my_tenant.id
  name      = each.value
}
```

### Understanding `each.key` vs `each.value` with Sets

For sets, **both are identical**:

```hcl
toset(["Production", "Development", "Testing"])
```

| Iteration | `each.key` | `each.value` |
|-----------|------------|--------------|
| 1st | "Production" | "Production" |
| 2nd | "Development" | "Development" |
| 3rd | "Testing" | "Testing" |

### Why `toset()` is Required

| Feature | List | Set |
|---------|------|-----|
| Duplicates | Allowed | Removed automatically |
| Ordered | Yes | No |
| Index access | `list[0]` | Not available |
| for_each compatible | ❌ No | ✅ Yes |

**Python analogy:**
```python
# Python List - keeps duplicates
my_list = ["A", "B", "A"]  # ['A', 'B', 'A']

# Python Set - removes duplicates
my_set = set(["A", "B", "A"])  # {'A', 'B'}
```

---

## 3. Working with Maps

Maps work directly with `for_each` - no conversion needed.

```hcl
variable "bridge_domains" {
  default = {
    "Web-BD"  = "Production-VRF"
    "App-BD"  = "Production-VRF"
    "DB-BD"   = "Development-VRF"
  }
}

resource "aci_bridge_domain" "bds" {
  for_each  = var.bridge_domains
  parent_dn = aci_tenant.my_tenant.id
  name      = each.key
  relation_to_vrf = { 
    vrf_name = aci_vrf.vrfs[each.value].name
  }
}
```

### Understanding `each.key` vs `each.value` with Maps

```hcl
{
  "Web-BD"  = "Production-VRF"
  "App-BD"  = "Production-VRF"
}
```

| Iteration | `each.key` | `each.value` |
|-----------|------------|--------------|
| 1st | "Web-BD" | "Production-VRF" |
| 2nd | "App-BD" | "Production-VRF" |

**Key insight:** For maps, `each.key` and `each.value` are DIFFERENT!

---

## 4. List of Objects to Map Conversion

### The Problem
```hcl
variable "filters" {
  default = [
    { name = "HTTP", port = 80 },
    { name = "HTTPS", port = 443 }
  ]
}

# ❌ This fails - list not allowed
for_each = var.filters
```

### The Solution: Convert to Map
```hcl
# ✅ Convert list of objects to map
for_each = { for entry in var.filters : entry.name => entry }
```

### How the Conversion Works

**Input (list of objects):**
```hcl
[
  { name = "HTTP", port = 80 },
  { name = "HTTPS", port = 443 }
]
```

**Output (map):**
```hcl
{
  "HTTP"  = { name = "HTTP", port = 80 }
  "HTTPS" = { name = "HTTPS", port = 443 }
}
```

### Complete Example
```hcl
resource "aci_filter_entry" "entries" {
  for_each    = { for entry in var.filters : entry.name => entry }
  filter_dn   = aci_filter.my_filter.id
  name        = each.key           # "HTTP", "HTTPS"
  d_from_port = each.value.port    # 80, 443
  d_to_port   = each.value.port    # 80, 443
}
```

### For Expression Syntax

| Output Type | Syntax | Example |
|-------------|--------|---------|
| List | `[for ...]` | `[for x in list : x.name]` |
| Map | `{for ...}` | `{for x in list : x.key => x}` |

---

## 5. Flatten for Nested Structures

### The Problem: Nested Data
```hcl
variable "apps" {
  default = {
    "CORP" = [
      { name = "SHAREPOINT", bd = "NET-10.10.10.0" },
      { name = "EXCHANGE", bd = "NET-10.10.10.0" }
    ],
    "DMZ" = [
      { name = "WEBSITE", bd = "NET-198.51.100.0" },
      { name = "API", bd = "NET-203.0.113.0" }
    ]
  }
}
```

### The Solution: Flatten
```hcl
locals {
  corp_dmz_epgs = flatten([
    for key, value in var.apps : [
      for entry in value : {
        app_name = key 
        epg_name = entry.name 
        bd_name  = entry.bd 
        key      = "${key}-${entry.name}"
      }
    ]
  ])
}
```

### How Flatten Works

**Step 1: Nested for loops create nested list**
```hcl
[
  [  # CORP
    { app_name = "CORP", epg_name = "SHAREPOINT", ... },
    { app_name = "CORP", epg_name = "EXCHANGE", ... }
  ],
  [  # DMZ
    { app_name = "DMZ", epg_name = "WEBSITE", ... },
    { app_name = "DMZ", epg_name = "API", ... }
  ]
]
```

**Step 2: flatten() converts to single list**
```hcl
[
  { app_name = "CORP", epg_name = "SHAREPOINT", bd_name = "NET-10.10.10.0", key = "CORP-SHAREPOINT" },
  { app_name = "CORP", epg_name = "EXCHANGE", bd_name = "NET-10.10.10.0", key = "CORP-EXCHANGE" },
  { app_name = "DMZ", epg_name = "WEBSITE", bd_name = "NET-198.51.100.0", key = "DMZ-WEBSITE" },
  { app_name = "DMZ", epg_name = "API", bd_name = "NET-203.0.113.0", key = "DMZ-API" }
]
```

### Using Flattened Data in Resources
```hcl
resource "aci_application_epg" "corp_dmz_epgs" {
  for_each  = { for entry in local.corp_dmz_epgs : entry.key => entry }
  parent_dn = aci_application_profile.corp_dmz_apps[each.value.app_name].id
  name      = each.value.epg_name
  relation_to_bridge_domain = {
    bridge_domain_name = aci_bridge_domain.bridge_domains[each.value.bd_name].name
  }
}
```

---

## 6. Dynamic Blocks

### What are Dynamic Blocks?
Dynamic blocks create **multiple nested blocks** inside a single resource.

### Two Types of `for_each`

| Location | Purpose | Creates |
|----------|---------|---------|
| Resource `for_each` | Multiple resource instances | Multiple resources |
| Dynamic block `for_each` | Multiple nested blocks | Multiple blocks in ONE resource |

### Example Without Dynamic (Manual)
```hcl
resource "aci_contract_subject" "subject" {
  contract_dn = aci_contract.contracts["Web"].id
  name        = "permit"
  
  consumer_to_provider {
    relation_vz_rs_filt_att {
      action    = "permit"
      filter_dn = aci_filter.filters["HTTP"].id
    }
    relation_vz_rs_filt_att {
      action    = "permit"
      filter_dn = aci_filter.filters["HTTPS"].id
    }
  }
}
```

### Example With Dynamic (Automated)
```hcl
variable "contracts" {
  default = [
    { name = "Web", filters = ["HTTP", "HTTPS"] }
  ]
}

resource "aci_contract_subject" "subjects" {
  for_each    = { for entry in var.contracts : entry.name => entry }
  contract_dn = aci_contract.contracts[each.key].id
  name        = "permit"
  
  consumer_to_provider {
    prio        = "unspecified"
    target_dscp = "unspecified"
    
    dynamic "relation_vz_rs_filt_att" {
      for_each = each.value.filters    # ["HTTP", "HTTPS"]
      content {
        action    = "permit"
        filter_dn = aci_filter.filters[relation_vz_rs_filt_att.value].id
      }
    }
  }
}
```

### Understanding Dynamic Block Variables

When iterating over a list in dynamic block:

```hcl
each.value.filters = ["HTTP", "HTTPS"]

dynamic "relation_vz_rs_filt_att" {
  for_each = each.value.filters
  content {
    filter_dn = aci_filter.filters[relation_vz_rs_filt_att.value].id
  }
}
```

| Iteration | `relation_vz_rs_filt_att.key` | `relation_vz_rs_filt_att.value` |
|-----------|-------------------------------|----------------------------------|
| 1st | 0 | "HTTP" |
| 2nd | 1 | "HTTPS" |

**Key insight:** Use `.value` to get the actual item, `.key` gives the index!

### Why No Curly Braces in Dynamic for_each?

```hcl
# Already a list - use directly
for_each = each.value.filters

# Transforming to map - needs curly braces
for_each = { for entry in var.list : entry.name => entry }
```

---

## 7. String Interpolation

### Correct Syntax
```hcl
key = "${entry.app}-${entry.name}"
```

### Common Mistakes

| Incorrect | Correct |
|-----------|---------|
| `${a-$b}` | `"${a}-${b}"` |
| `$entry.name` | `"${entry.name}"` |
| `${var}-text` | `"${var}-text"` |
| `key=${a}-${b}` | `key = "${a}-${b}"` |

### Rules
- Entire string must be in quotes `"..."`
- Each variable needs `${...}` wrapper
- Literal characters (like `-`) go outside `${}`

---

## 8. Terraform Console

### What Works vs Doesn't Work

| Works | Doesn't Work |
|-------|--------------|
| `var.apps` | `variable "x" { }` |
| `local.epg_map` | `locals { }` |
| `[for ...]` expressions | `resource { }` |
| Functions like `flatten()` | `for_each` meta-argument |
| Literal values `[{...}]` | `dynamic` blocks |

### Testing Expressions

**Can't do this:**
```bash
> locals { epg_map = flatten([...]) }
# Error
```

**Do this instead:**
```bash
> flatten([for entry in var.apps : ...])
# Returns result
```

### Workflow for Testing Locals

1. Test expression directly in console
2. Once working, wrap in locals block in .tf file
3. Reference via `local.variable_name`

---

## 9. ACI Provider 2.17.0 Syntax

### relation_to_vrf (Bridge Domain to VRF)

**Old syntax (0.7.0):**
```hcl
relation_fv_rs_ctx = aci_vrf.my_vrf.id
```

**New syntax (2.17.0):**
```hcl
relation_to_vrf = {
  vrf_name = aci_vrf.my_vrf.name
}
```

### relation_to_bridge_domain (EPG to BD)

**Old syntax (0.7.0):**
```hcl
relation_fv_rs_bd = aci_bridge_domain.my_bd.id
```

**New syntax (2.17.0):**
```hcl
relation_to_bridge_domain = {
  bridge_domain_name = aci_bridge_domain.my_bd.name
}
```

### Contract Subject Filters

**Old syntax (still works):**
```hcl
relation_vz_rs_subj_filt_att = [
  aci_filter.http.id,
  aci_filter.https.id
]
```

**New syntax with directional filters:**
```hcl
apply_both_directions = "no"

consumer_to_provider {
  dynamic "relation_vz_rs_filt_att" {
    for_each = each.value.filters
    content {
      action    = "permit"
      filter_dn = aci_filter.filters[relation_vz_rs_filt_att.value].id
    }
  }
}

provider_to_consumer {
  dynamic "relation_vz_rs_filt_att" {
    for_each = each.value.filters
    content {
      action    = "permit"
      filter_dn = aci_filter.filters[relation_vz_rs_filt_att.value].id
    }
  }
}
```

---

## 10. Best Practices

### 1. Always Reference Actual Resources

```hcl
# ✅ Good - creates dependency
vrf_name = aci_vrf.vrfs[each.value].name

# ⚠️ Works but risky - no dependency
vrf_name = each.value
```

### 2. Use Composite Keys for Uniqueness

```hcl
key = "${app_name}-${epg_name}"
```

### 3. Avoid Redundant Conversions

```hcl
# ❌ Redundant - var.apps is already a map
for_each = tomap(var.apps)

# ✅ Clean
for_each = var.apps
```

### 4. Name Loop Variables Distinctly

```hcl
# ❌ Confusing - bd vs bds
locals {
  bds = flatten([for bd in var.bds : ...])
}

# ✅ Clear - bd_entry vs bds
locals {
  bds = flatten([for bd_entry in var.bridge_domains : ...])
}
```

### 5. Multiple .tf Files

Terraform loads **all `.tf` files** in a directory:

```
my-folder/
├── main.tf           # Provider, tenant, VRFs
├── networking.tf     # BDs, subnets
├── apps.tf           # App profiles, EPGs
├── contracts.tf      # Filters, contracts
├── variables.tf      # All variables
├── outputs.tf        # All outputs
└── terraform.tfvars  # Variable values
```

---

## 11. MCQ Practice Questions

### Question 1: toset() Usage
Which statement correctly creates VRFs from a list?

```hcl
variable "vrfs" {
  default = ["Prod", "Dev", "Test"]
}
```

A) `for_each = var.vrfs`
B) `for_each = toset(var.vrfs)`
C) `for_each = tomap(var.vrfs)`
D) `for_each = tolist(var.vrfs)`

<details>
<summary>Answer</summary>
<b>B) for_each = toset(var.vrfs)</b>

for_each requires a set or map. Lists must be converted using toset().
</details>

---

### Question 2: each.key vs each.value
Given this code, what is `each.value`?

```hcl
variable "bds" {
  default = {
    "Web-BD" = "Prod-VRF"
    "App-BD" = "Dev-VRF"
  }
}

resource "aci_bridge_domain" "bds" {
  for_each = var.bds
  name     = each.key
}
```

A) "Web-BD" or "App-BD"
B) "Prod-VRF" or "Dev-VRF"
C) The entire map
D) The index number

<details>
<summary>Answer</summary>
<b>B) "Prod-VRF" or "Dev-VRF"</b>

For maps, each.key is the map key, each.value is the map value.
</details>

---

### Question 3: List to Map Conversion
Which converts a list of objects to a map correctly?

```hcl
variable "filters" {
  default = [
    { name = "HTTP", port = 80 },
    { name = "HTTPS", port = 443 }
  ]
}
```

A) `{ for f in var.filters : f.name }`
B) `[ for f in var.filters : f.name => f ]`
C) `{ for f in var.filters : f.name => f }`
D) `tomap(var.filters)`

<details>
<summary>Answer</summary>
<b>C) { for f in var.filters : f.name => f }</b>

Use curly braces {} to create a map, with key => value syntax.
</details>

---

### Question 4: Dynamic Block Variable
In this dynamic block, what is `relation_vz_rs_filt_att.value`?

```hcl
each.value.filters = ["HTTP", "HTTPS"]

dynamic "relation_vz_rs_filt_att" {
  for_each = each.value.filters
  content {
    filter_dn = aci_filter.filters[relation_vz_rs_filt_att.value].id
  }
}
```

A) 0 or 1 (index)
B) "HTTP" or "HTTPS" (actual filter name)
C) The entire list
D) each.value

<details>
<summary>Answer</summary>
<b>B) "HTTP" or "HTTPS" (actual filter name)</b>

When iterating over a list, .value gives the item, .key gives the index.
</details>

---

### Question 5: Flatten Purpose
What does `flatten()` do?

```hcl
[
  ["A", "B"],
  ["C", "D"]
]
```

A) Converts to a set
B) Converts to a map
C) Converts nested list to single flat list `["A", "B", "C", "D"]`
D) Removes duplicates

<details>
<summary>Answer</summary>
<b>C) Converts nested list to single flat list ["A", "B", "C", "D"]</b>

flatten() removes nesting from lists.
</details>

---

### Question 6: String Interpolation
Which is the correct syntax?

A) `key = ${app}-${epg}`
B) `key = "${app-$epg}"`
C) `key = "${app}-${epg}"`
D) `key = $app-$epg`

<details>
<summary>Answer</summary>
<b>C) key = "${app}-${epg}"</b>

Each variable needs ${}, entire string needs quotes, literal - goes between.
</details>

---

### Question 7: Terraform Console
Which can you run in terraform console?

A) `variable "x" { default = "test" }`
B) `locals { my_var = "test" }`
C) `flatten([for x in var.list : x.name])`
D) `resource "null_resource" "test" {}`

<details>
<summary>Answer</summary>
<b>C) flatten([for x in var.list : x.name])</b>

Console only evaluates expressions, not configuration blocks.
</details>

---

### Question 8: ACI Provider 2.17.0
Which is correct for BD to VRF relationship in provider 2.17.0?

A) `relation_fv_rs_ctx = aci_vrf.my_vrf.id`
B) `relation_to_vrf = aci_vrf.my_vrf.id`
C) `relation_to_vrf = { vrf_name = aci_vrf.my_vrf.name }`
D) `vrf_dn = aci_vrf.my_vrf.id`

<details>
<summary>Answer</summary>
<b>C) relation_to_vrf = { vrf_name = aci_vrf.my_vrf.name }</b>

Provider 2.17.0 uses block syntax with vrf_name attribute.
</details>

---

### Question 9: Dynamic Block for_each
Why doesn't dynamic for_each need curly braces here?

```hcl
dynamic "relation_vz_rs_filt_att" {
  for_each = each.value.filters  # ["HTTP", "HTTPS"]
  content { ... }
}
```

A) It's a bug
B) `each.value.filters` is already a list, no transformation needed
C) Dynamic blocks don't support maps
D) Curly braces are optional

<details>
<summary>Answer</summary>
<b>B) each.value.filters is already a list, no transformation needed</b>

You only need {} when transforming data. Direct list/set/map can be used as-is.
</details>

---

### Question 10: Resource Dependencies
Which creates proper dependency between BD and VRF?

A) `vrf_name = "Production-VRF"`
B) `vrf_name = var.vrf_name`
C) `vrf_name = each.value.vrf`
D) `vrf_name = aci_vrf.vrfs[each.value.vrf].name`

<details>
<summary>Answer</summary>
<b>D) vrf_name = aci_vrf.vrfs[each.value.vrf].name</b>

Referencing the actual resource creates an implicit dependency, ensuring VRF is created before BD.
</details>

---

## 12. Hands-on Exercises

### Exercise 1: Basic for_each
Create VRFs from this list:
```hcl
variable "vrfs" {
  default = ["Internal", "External", "Management"]
}
```

<details>
<summary>Solution</summary>

```hcl
resource "aci_vrf" "vrfs" {
  for_each  = toset(var.vrfs)
  parent_dn = aci_tenant.my_tenant.id
  name      = each.value
}
```
</details>

---

### Exercise 2: List of Objects
Create filters from this variable:
```hcl
variable "filters" {
  default = [
    { name = "SSH", port = 22 },
    { name = "RDP", port = 3389 }
  ]
}
```

<details>
<summary>Solution</summary>

```hcl
resource "aci_filter" "filters" {
  for_each  = { for f in var.filters : f.name => f }
  tenant_dn = aci_tenant.my_tenant.id
  name      = each.key
}

resource "aci_filter_entry" "entries" {
  for_each    = { for f in var.filters : f.name => f }
  filter_dn   = aci_filter.filters[each.key].id
  name        = "TCP_${each.value.port}"
  ether_t     = "ip"
  prot        = "tcp"
  d_from_port = each.value.port
  d_to_port   = each.value.port
}
```
</details>

---

### Exercise 3: Flatten Nested Data
Flatten this structure and create EPGs:
```hcl
variable "apps" {
  default = [
    { name = "Web", epgs = ["Frontend", "Backend"] },
    { name = "DB", epgs = ["Primary", "Replica"] }
  ]
}
```

<details>
<summary>Solution</summary>

```hcl
locals {
  epg_map = flatten([
    for app in var.apps : [
      for epg in app.epgs : {
        app_name = app.name
        epg_name = epg
        key      = "${app.name}-${epg}"
      }
    ]
  ])
}

resource "aci_application_epg" "epgs" {
  for_each  = { for entry in local.epg_map : entry.key => entry }
  parent_dn = aci_application_profile.apps[each.value.app_name].id
  name      = each.value.epg_name
}
```
</details>

---

### Exercise 4: Dynamic Block
Create contract subject with dynamic filters:
```hcl
variable "contracts" {
  default = [
    { name = "Web", filters = ["HTTP", "HTTPS", "SSH"] }
  ]
}
```

<details>
<summary>Solution</summary>

```hcl
resource "aci_contract_subject" "subjects" {
  for_each    = { for c in var.contracts : c.name => c }
  contract_dn = aci_contract.contracts[each.key].id
  name        = "permit"
  
  apply_both_directions = "yes"
  
  consumer_to_provider {
    prio        = "unspecified"
    target_dscp = "unspecified"
    
    dynamic "relation_vz_rs_filt_att" {
      for_each = each.value.filters
      content {
        action    = "permit"
        filter_dn = aci_filter.filters[relation_vz_rs_filt_att.value].id
      }
    }
  }
}
```
</details>

---

## 13. Quick Reference Tables

### For Expression Syntax

| Output | Syntax | Example |
|--------|--------|---------|
| List | `[for ...]` | `[for x in list : x.name]` |
| Map | `{for ...}` | `{for x in list : x.key => x}` |

### each.key vs each.value

| Input Type | `each.key` | `each.value` |
|------------|------------|--------------|
| Set | Item itself | Item itself |
| Map | Map key | Map value |
| List of objects (converted) | Defined key | Full object |

### Dynamic Block Variables

| Variable | Meaning |
|----------|---------|
| `block_name.key` | Index (for lists) or key (for maps) |
| `block_name.value` | Actual item |

### ACI Provider 2.17.0 Changes

| Relationship | Old Syntax | New Syntax |
|--------------|-----------|------------|
| BD → VRF | `relation_fv_rs_ctx = vrf.id` | `relation_to_vrf = { vrf_name = vrf.name }` |
| EPG → BD | `relation_fv_rs_bd = bd.id` | `relation_to_bridge_domain = { bridge_domain_name = bd.name }` |

### Terraform Console Rules

| Works | Doesn't Work |
|-------|--------------|
| `var.variable_name` | `variable {}` block |
| `local.local_name` | `locals {}` block |
| `[for ...]` expressions | `resource {}` block |
| `flatten()`, `toset()` | `for_each` meta-argument |

---

## 14. Common Mistakes and Fixes

### Mistake 1: Wrong parent_dn for EPG

EPGs belong under Application Profiles, not Tenants.

**❌ Incorrect:**
```hcl
resource "aci_application_epg" "corp_dmz_epgs" {
  for_each  = {for entry in local.corp_dmz_epgs: entry.unique => entry}
  parent_dn = aci_tenant.devnet_tenant.id    # Wrong - Tenant is not EPG parent
  name      = each.value.epg_name
}
```

**✅ Correct:**
```hcl
resource "aci_application_epg" "corp_dmz_epgs" {
  for_each  = {for entry in local.corp_dmz_epgs: entry.unique => entry}
  parent_dn = aci_application_profile.corp_dmz_apps[each.value.app_name].id   # Correct
  name      = each.value.epg_name
}
```

**ACI Hierarchy:**
```
Tenant
└── Application Profile  ← EPG parent (parent_dn)
    └── EPG
```

---

### Mistake 2: Using `each.value` without `for_each`

`each.key` and `each.value` only exist when resource has `for_each`.

**❌ Incorrect:**
```hcl
resource "aci_contract_subject" "subjects" {
  contract_dn = aci_contract.contracts["Web"].id
  name        = "permit"
  
  dynamic "relation_vz_rs_filt_att" {
    for_each = each.value.filters    # Error: "each" doesn't exist
    content { ... }
  }
}
```

**✅ Correct - Option 1: Add resource for_each**
```hcl
resource "aci_contract_subject" "subjects" {
  for_each    = { for entry in var.contracts : entry.name => entry }
  contract_dn = aci_contract.contracts[each.key].id
  name        = "permit"
  
  dynamic "relation_vz_rs_filt_att" {
    for_each = each.value.filters    # Now "each" exists
    content { ... }
  }
}
```

**✅ Correct - Option 2: Direct variable reference**
```hcl
resource "aci_contract_subject" "subjects" {
  contract_dn = aci_contract.contracts["Web"].id
  name        = "permit"
  
  dynamic "relation_vz_rs_filt_att" {
    for_each = var.contracts[0].filters    # Direct reference
    content { ... }
  }
}
```

---

### Mistake 3: Nested `for` without `flatten()`

You cannot nest `for` expressions directly.

**❌ Incorrect:**
```hcl
for_each = [for entry in var.contracts: for filter in entry.filters]
# Syntax error
```

**✅ Correct:**
```hcl
for_each = flatten([for entry in var.contracts : entry.filters])
```

**How it works:**
```hcl
# Step 1: Inner for creates nested list
[for entry in var.contracts : entry.filters]
# Result: [["HTTP", "HTTPS"], ["SSH"]]

# Step 2: flatten() removes nesting
flatten([["HTTP", "HTTPS"], ["SSH"]])
# Result: ["HTTP", "HTTPS", "SSH"]
```

---

## 15. Attribute Types: List vs Block/Object

### Understanding `relation_vz_rs_subj_filt_att` (List)

This attribute expects a **list of filter IDs**:

```hcl
variable "contracts" {
  default = [
    { name = "Web", filters = ["HTTP", "HTTPS"] }
  ]
}

resource "aci_contract_subject" "contract_subject" {
  for_each    = {for entry in var.contracts: entry.name => entry}
  contract_dn = aci_contract.contracts[each.key].id
  name        = "permit"
  
  # List attribute - uses [ ] brackets
  relation_vz_rs_subj_filt_att = [for filter in each.value.filters : aci_filter.tcp_filters[filter].id]
}
```

**Step-by-step for "Web" contract:**

```
each.key = "Web"
each.value = { name = "Web", filters = ["HTTP", "HTTPS"] }
each.value.filters = ["HTTP", "HTTPS"]

[for filter in each.value.filters : aci_filter.tcp_filters[filter].id]
     │
     ├── filter = "HTTP"  → aci_filter.tcp_filters["HTTP"].id
     └── filter = "HTTPS" → aci_filter.tcp_filters["HTTPS"].id

Result:
relation_vz_rs_subj_filt_att = [
  "uni/tn-tenant/flt-HTTP",
  "uni/tn-tenant/flt-HTTPS"
]
```

---

### Understanding `relation_to_bridge_domain` (Block/Object)

This attribute expects an **object with predefined keys**:

```hcl
resource "aci_application_epg" "epg" {
  parent_dn = aci_application_profile.app.id
  name      = "Web-EPG"
  
  # Block/Object attribute - uses { } braces with predefined keys
  relation_to_bridge_domain = {
    bridge_domain_name = aci_bridge_domain.devnet_vrf_bd.name
  }
}
```

---

### Map vs Object/Block

| Type | Keys | Example |
|------|------|---------|
| **Map** | Dynamic - you define them | `{ "Web-BD" = "Prod-VRF", "App-BD" = "Dev-VRF" }` |
| **Object/Block** | Fixed - provider defines them | `{ bridge_domain_name = "BD-name" }` |

**Map - Any keys allowed:**
```hcl
variable "bridge_domains" {
  default = {
    "anything"    = "value1"    # Your choice
    "any_key"     = "value2"    # Your choice
    "your_choice" = "value3"    # Your choice
  }
}
```

**Object/Block - Only predefined keys:**
```hcl
relation_to_bridge_domain = {
  bridge_domain_name = "..."   # Required - provider schema
  annotation         = "..."   # Optional - provider schema
}

# ❌ This fails - "my_custom_key" not in provider schema
relation_to_bridge_domain = {
  my_custom_key = "value"
}
```

---

### Attribute Type Reference

| Syntax | Type | Example |
|--------|------|---------|
| `attribute = "value"` | String | `name = "Web"` |
| `attribute = 123` | Number | `port = 80` |
| `attribute = [...]` | List | `relation_vz_rs_subj_filt_att = [id1, id2]` |
| `attribute = {...}` | Object/Block | `relation_to_vrf = { vrf_name = "..." }` |
| `dynamic "attr" {...}` | Multiple Blocks | Multiple `relation_vz_rs_filt_att` blocks |

---

## 16. Resource Reference vs Hardcoded Values

### The Problem

Given this setup:
```hcl
resource "aci_bridge_domain" "devnet_vrf_bd" {
  parent_dn = aci_tenant.devnet_tenant.id
  name      = "Devnet-BD"    # Actual name in ACI
}
```

**Two ways to reference the BD:**

```hcl
# Solution 1: Resource reference
relation_to_bridge_domain = {
  bridge_domain_name = aci_bridge_domain.devnet_vrf_bd.name
}

# Solution 2: Hardcoded value
relation_to_bridge_domain = {
  bridge_domain_name = "Devnet-BD"
}
```

---

### Why Resource Reference is Better

| Aspect | Resource Reference | Hardcoded |
|--------|-------------------|-----------|
| Creates dependency | ✅ Yes | ❌ No |
| Auto-updates on change | ✅ Yes | ❌ No |
| Risk of typo | ✅ Low | ⚠️ High |
| Maintainability | ✅ Better | ⚠️ Risky |

---

### Resource Name vs Actual Name

```hcl
resource "aci_bridge_domain" "devnet_vrf_bd" {   # ← Terraform resource name
  name = "Devnet-BD"                              # ← Actual name in ACI
}
```

| Reference | Returns |
|-----------|---------|
| `aci_bridge_domain.devnet_vrf_bd.name` | `"Devnet-BD"` ✅ |
| `"devnet_vrf_bd"` | Wrong - this is resource name ❌ |

---

### Dependency Visualization

```
With Resource Reference:
┌─────────────────┐      ┌─────────────────┐
│  Bridge Domain  │ ───► │      EPG        │
│  (created 1st)  │      │  (created 2nd)  │
└─────────────────┘      └─────────────────┘
     Terraform knows BD must exist before EPG

With Hardcoded Value:
┌─────────────────┐      ┌─────────────────┐
│  Bridge Domain  │  ?   │      EPG        │
│    (order?)     │      │   (order?)      │
└─────────────────┘      └─────────────────┘
     No dependency - may fail if BD doesn't exist
```

---

### Example: What Happens When Name Changes

```hcl
# If you change BD name:
resource "aci_bridge_domain" "devnet_vrf_bd" {
  name = "New-BD-Name"    # Changed from "Devnet-BD"
}

# Resource Reference: Automatically uses "New-BD-Name" ✅
bridge_domain_name = aci_bridge_domain.devnet_vrf_bd.name

# Hardcoded: Still uses old name - BROKEN ❌
bridge_domain_name = "Devnet-BD"
```

---

### Best Practice Summary

```hcl
# ✅ Always use resource references
relation_to_bridge_domain = {
  bridge_domain_name = aci_bridge_domain.devnet_vrf_bd.name
}

relation_to_vrf = {
  vrf_name = aci_vrf.devnet_vrf.name
}

parent_dn = aci_application_profile.apps[each.value.app_name].id

filter_dn = aci_filter.tcp_filters[relation_vz_rs_filt_att.value].id

# ❌ Avoid hardcoding
bridge_domain_name = "Devnet-BD"
vrf_name = "Devnet-vrf"
parent_dn = "uni/tn-tenant/ap-App1"
```

---

## 17. Complete Example: Putting It All Together

```hcl
# =============================================================================
# VARIABLES
# =============================================================================
variable "apps_and_epgs" {
  default = [
    { prf_name = "App1", epgs = ["A", "B"] },
    { prf_name = "App2", epgs = ["C", "A"] }
  ]
}

variable "contracts" {
  default = [
    { name = "Web", filters = ["HTTP", "HTTPS"] },
    { name = "Custom_Web", filters = ["Custom_HTTP", "Custom_HTTPS"] }
  ]
}

# =============================================================================
# TENANT AND VRF
# =============================================================================
resource "aci_tenant" "devnet_tenant" {
  name        = "Devnet-tenant"
  description = "Created by Terraform"
}

resource "aci_vrf" "devnet_vrf" {
  parent_dn = aci_tenant.devnet_tenant.id
  name      = "Devnet-vrf"
}

# =============================================================================
# BRIDGE DOMAIN
# =============================================================================
resource "aci_bridge_domain" "devnet_vrf_bd" {
  parent_dn = aci_tenant.devnet_tenant.id
  name      = "Devnet-BD"
  relation_to_vrf = { 
    vrf_name = aci_vrf.devnet_vrf.name    # Resource reference
  }
}

# =============================================================================
# APPLICATION PROFILES (from list of objects)
# =============================================================================
resource "aci_application_profile" "apps" {
  for_each  = { for entry in var.apps_and_epgs : entry.prf_name => entry }
  parent_dn = aci_tenant.devnet_tenant.id
  name      = each.key
}

# =============================================================================
# FLATTEN NESTED DATA FOR EPGs
# =============================================================================
locals {
  epg_map = flatten([
    for entry in var.apps_and_epgs : [
      for epg in entry.epgs : {
        epg_name = epg 
        app_name = entry.prf_name 
        key      = "${entry.prf_name}-${epg}"
      }
    ]
  ])
}

# =============================================================================
# EPGs (from flattened data)
# =============================================================================
resource "aci_application_epg" "structured_epgs" {
  for_each  = { for entry in local.epg_map : entry.key => entry }
  parent_dn = aci_application_profile.apps[each.value.app_name].id   # Correct parent
  name      = each.value.epg_name
  relation_to_bridge_domain = {
    bridge_domain_name = aci_bridge_domain.devnet_vrf_bd.name   # Resource reference
  }      
}

# =============================================================================
# FILTERS (from list of objects)
# =============================================================================
variable "tcp_filters" {
  default = [
    { name = "HTTP", port = 80 },
    { name = "HTTPS", port = 443 }
  ]
}

resource "aci_filter" "tcp_filters" {
  for_each  = { for entry in var.tcp_filters : entry.name => entry }
  tenant_dn = aci_tenant.devnet_tenant.id
  name      = each.key
}

resource "aci_filter_entry" "tcp_filter_entries" {
  for_each    = { for entry in var.tcp_filters : entry.name => entry }
  filter_dn   = aci_filter.tcp_filters[each.key].id
  name        = "TCP_${each.value.port}"
  ether_t     = "ip"
  prot        = "tcp"
  d_from_port = each.value.port
  d_to_port   = each.value.port
}

# =============================================================================
# CONTRACTS AND SUBJECTS (with dynamic blocks)
# =============================================================================
resource "aci_contract" "contracts" {
  for_each  = { for entry in var.contracts : entry.name => entry }
  tenant_dn = aci_tenant.devnet_tenant.id
  name      = each.key
}

resource "aci_contract_subject" "contract_subjects" {
  for_each              = { for entry in var.contracts : entry.name => entry }
  contract_dn           = aci_contract.contracts[each.key].id
  name                  = "permit"
  apply_both_directions = "yes"
  
  consumer_to_provider {
    prio        = "unspecified"
    target_dscp = "unspecified"
    
    dynamic "relation_vz_rs_filt_att" {
      for_each = each.value.filters
      content {
        action    = "permit"
        filter_dn = aci_filter.tcp_filters[relation_vz_rs_filt_att.value].id
      }
    }
  }
}

# =============================================================================
# OUTPUTS
# =============================================================================
output "epg_map_debug" {
  description = "Shows the flattened EPG map structure"
  value       = local.epg_map
}

output "created_epgs" {
  value = { for k, v in aci_application_epg.structured_epgs : k => v.id }
}
```

---

## Additional Resources

- [Terraform for_each Documentation](https://developer.hashicorp.com/terraform/language/meta-arguments/for_each)
- [Terraform for Expressions](https://developer.hashicorp.com/terraform/language/expressions/for)
- [Terraform Dynamic Blocks](https://developer.hashicorp.com/terraform/language/expressions/dynamic-blocks)
- [Terraform Functions](https://developer.hashicorp.com/terraform/language/functions)
- [ACI Terraform Provider Registry](https://registry.terraform.io/providers/CiscoDevNet/aci/latest/docs)

---

*Document created for CCIE Automation / DevNet Expert exam preparation*
*Last updated: April 2026*

</details>



# ACI Terraform Practice Exam - E1

## TODO List

- **TODO-1:** Rename `secrets.tfvars` so that Terraform loads it automatically
- **TODO-2:** Create tenant `e1-sim-Devnet-tenant` and three VRFs: `Devnet-vrf`, `INTERNAL`, `EXTERNAL`
- **TODO-3:** Create bridge domains - standalone `Devnet-BD` (related to devnet_vrf) and from `var.bridgedomains` (related to internal/external VRFs)
- **TODO-4:** Create application profile `Devnet-app` and app profiles from `var.apps_and_epgs`
- **TODO-5:** Create 3 EPGs from `var.epgs` list under `devnet_app`
- **TODO-6:** Restructure `var.apps_and_epgs` into `local.epg_map` with unique keys, create `structured_epgs`
- **TODO-7:** Create `aci_filter` and `aci_filter_entry` from `var.tcp_filters` (entry names: TCP_80, TCP_443, etc.)
- **TODO-8:** Create `aci_contract` and `aci_contract_subject` from `var.contracts` with filter associations
- **TODO-9:** Create CORP/DMZ app profiles and EPGs from `var.apps`, restructure into `local.corp_dmz_epgs`
- **TODO-10:** Allocate contracts - Web to `structured_epgs["App1-A"]`, Custom_Web to `corp_dmz_epgs["DMZ-WEBSITE"]`

---

## Initial Files

### e1-sim-main.tf

<details>
<summary>Click to Display</summary>

```hcl
terraform {
  required_providers {
    aci = {
      source  = "CiscoDevNet/aci"
      version = "2.17.0"
    }
  }
}

provider "aci" {
  username = var.apic_username
  password = var.apic_password
  url      = "https://192.168.89.95"
  insecure = true
}

# === VARIABLES ===
# =============================================================================
# TODO-1: There is APIC secrets file named secrets.tfvars. Change the file name
# So that terraform take the secrets from that file automatically
# =============================================================================
variable "apic_username" {
  type      = string
  sensitive = true
}

variable "apic_password" {
  type      = string
  sensitive = true
}

variable "tcp_filters" {
  type = list(object({
    name = string
    port = number
  }))
}

variable "contracts" {
  type = list(object({
    name    = string
    filters = list(string)
  }))
}

variable "bridgedomains" {
  type = list(object({
    vrf  = string
    name = string
  }))
}

variable "apps" {
  type = map(list(object({
    name = string
    bd   = string
  })))
}



# =============================================================================
# TODO-2: TENANT AND VRFs
# Create tenant=e2-sim-Devnet-tenant
# Create three VRFs "Devnet-vrf", "INTERNAL" and "EXTERNAL" [using manual method]
# =============================================================================

resource "aci_tenant" "devnet_tenant" {
  name        = 
  description = 
}

resource "aci_vrf" "devnet_vrf" {
  parent_dn = 
  name      = 
}

resource "aci_vrf" "internal" {
  parent_dn =  
  name      = 
}

resource "aci_vrf" "external" {
  parent_dn =    # use manual method uni/
  name      = 
}
# =============================================================================
# TODO-3: BRIDGE DOMAINS
# =============================================================================
# Create a standalone bridgedomain name=Devnet-BD and relate it to "devnet_vrf", 
# that was created at the begining
resource "aci_bridge_domain" "devnet_vrf_bd" {
  parent_dn = 
  name               = 
  relation_to_vrf = { 
    vrf_name = 
  }
}
# Crate bridgedomain using variable "var.bridgedomains", and relate to vrf.internal/external
resource "aci_bridge_domain" "bridge_domains" {
  for_each           = 
  parent_dn          = 
  name               = 
  relation_to_vrf = {
    vrf_name = each.value.vrf == "INTERNAL" ? aci_vrf.internal.name : aci_vrf.external.name
    }
}

# =============================================================================
# TODO-4: APPLICATION PROFILES
# Crate application-profile=Devnet-app
# =============================================================================

resource "aci_application_profile" "devnet_app" {
  parent_dn =  
  name      = 
}

variable "apps_and_epgs" {
  default = [
    { prf_name = "App1", epgs = ["A", "B"] },
    { prf_name = "App2", epgs = ["C", "A"] }
  ]
}

# Create App Profiles from structured var.apps_epgs data using for_each
resource "aci_application_profile" "apps" {
  for_each  = 
  parent_dn = 
  name      = 
}


# # =============================================================================
# # TODO-5: EPGs FROM LIST
# # Create 3-epgs from var.epgs and keep them under "aci_application_profile" "devnet_app"
# # =============================================================================
variable "epgs" {
  default = ["Associate", "Professional", "Expert"]
}
resource "aci_application_epg" "simple_epgs" {
  for_each               = 
  parent_dn              = 
  name                   = 
}


# # =============================================================================
# # TODO-6: EPGs FROM NESTED DATA (flatten)
# # Restructure the var.apps_and_epgs ==> local.epg_map with unique key
# # =============================================================================
# /*
# variable "apps_and_epgs" {
#   default = [
#     { prf_name = "App1", epgs = ["A", "B"] },
#     { prf_name = "App2", epgs = ["C", "A"] }
#   ]
# }
# */
locals {
  epg_map = 
}
# Create application_epg using local.epg_map, and keep them under "aci_application_profile" "apps"
# Create the relation_to_bridge_domain with "aci_bridge_domain" "devnet_vrf_bd", which created under TODO-3
resource "aci_application_epg" "structured_epgs" {
  for_each               = 
  parent_dn              =  
  name                   = 
  relation_to_bridge_domain = {
    bridge_domain_name = 
  }      
}

# # =============================================================================
# # TODO-7: FILTERS AND FILTER ENTRIES
# # Create aci_filter and aci_filter_entry based on tcp_filters
# # Each filter_entry name would be TCP_port, where port=80,443 etc
# # destination and source ports are same as var.tcp_filters
# # =============================================================================

resource "aci_filter" "tcp_filters" {
  for_each  = 
  tenant_dn = 
  name      = 
}

resource "aci_filter_entry" "tcp_filter_entries" {
  for_each    = 
  filter_dn   = 
  name        = 
  ether_t     = "ip"
  prot        = "tcp"
  d_from_port = 
  d_to_port   = 
}

# # =============================================================================
# # TODO-8: CONTRACTS AND SUBJECTS
# # Create aci_contract and aci_contract_subject based on variable "contracts"
# # relation_vz_rs_subj_filt_att with "aci_filter" "tcp_filters" for contract_subject
# # =============================================================================

resource "aci_contract" "contracts" {
  for_each  = 
  tenant_dn = 
  name      = 
}

resource "aci_contract_subject" "contract_subjects" {
  for_each    = 
  contract_dn = 
  name        = "permit"
  apply_both_directions = "no"
  consumer_to_provider {
    prio        = "unspecified"
    target_dscp = "unspecified"
    dynamic "relation_vz_rs_filt_att" {
    for_each =
    content {
        action = "permit"
        filter_dn = 
        }
    }
  } 
    provider_to_consumer {
    prio        = "unspecified"
    target_dscp = "unspecified"
    
    dynamic "relation_vz_rs_filt_att" {
      for_each = 
      content {
        action    = 
        filter_dn = 
      }
    }
  }
}

# ****OLD WAY STILL WORKS
# relation_vz_rs_subj_filt_att = [for filter in each.value.filters : aci_filter.tcp_filters[filter].id]

# # =============================================================================
# # TODO-9: CORP/DMZ APP PROFILES AND EPGs
# # =============================================================================
# Create application profile using variable var.apps
resource "aci_application_profile" "corp_dmz_apps" {
  for_each  = 
  parent_dn = 
  name      = 
}
# Restructure the var.apps under local.corp_dmz_epgs with unique key; so that it creates list of objects
locals {
  corp_dmz_epgs = 
}
# Create aci_aaplication_epg and fill the relation with bridgedomain in TODO-3;
# "aci_bridge_domain" "bridge_domains" 
resource "aci_application_epg" "corp_dmz_epgs" {
  for_each               = 
  parent_dn              = 
  name                   = 
  relation_to_bridge_domain      = {
    bridge_domain_name=
  }
}


# # =============================================================================
# # TODO-10: CONTRACT ALLOCATIONS
# # =============================================================================

# Allocate Web contract to structured_epgs["App1-A"] [TODO-6, application_epgs]as consumer
resource "aci_epg_to_contract" "web_contract_app1_a" {
  application_epg_dn = 
  contract_dn        = 
  contract_type      = 
}

# Allocate Custom_Web contract to corp_dmz_epgs["DMZ-WEBSITE"] as consumer
resource "aci_epg_to_contract" "custom_web_website" {
  application_epg_dn = 
  contract_dn        = 
  contract_type      = 
}


# # =============================================================================
# # OUTPUTS
# # =============================================================================

output "tenant_id" {
  value = aci_tenant.devnet_tenant.id
}

output "vrf_ids" {
  value = {
    devnet   = aci_vrf.devnet_vrf.id
    internal = aci_vrf.internal.id
    external = aci_vrf.external.id
  }
}

output "application_profiles" {
  value = { for k, v in aci_application_profile.apps : k => v.id }
}

output "epg_map_debug" {
  description = "Shows the flattened EPG map structure"
  value       = local.epg_map
}

output "corp_dmz_epgs_debug" {
  description = "Shows the flattened CORP/DMZ EPG structure"
  value       = local.corp_dmz_epgs
}
```
</details>

### terraform.tfvars

```hcl
tcp_filters = [
  { name = "HTTP", port = 80 },
  { name = "HTTPS", port = 443 },
  { name = "Custom_HTTP", port = 8080 },
  { name = "Custom_HTTPS", port = 8443 }
]

contracts = [
  { name = "Web", filters = ["HTTP", "HTTPS"] },
  { name = "Custom_Web", filters = ["Custom_HTTP", "Custom_HTTPS"] }
]

bridgedomains = [
  { vrf = "INTERNAL", name = "NET-10.10.10.0" },
  { vrf = "EXTERNAL", name = "NET-198.51.100.0" },
  { vrf = "EXTERNAL", name = "NET-203.0.113.0" }
]

apps = {
  "CORP" = [
    { name = "SHAREPOINT", bd = "NET-10.10.10.0" },
    { name = "EXCHANGE", bd = "NET-10.10.10.0" }
  ],
  "DMZ" = [
    { name = "WEBSITE", bd = "NET-198.51.100.0" },
    { name = "API", bd = "NET-203.0.113.0" }
  ]
}
```

### secrets.tfvars

```hcl
apic_username = "admin"
apic_password = "1234QWer!"
```

---

## Solution (Last Resort)

<details>
<summary>sol-e1-sim-main.tf (click to expand)</summary>

```hcl
terraform {
  required_providers {
    aci = {
      source  = "CiscoDevNet/aci"
      version = "2.17.0"
    }
  }
}

provider "aci" {
  username = var.apic_username
  password = var.apic_password
  url      = "https://192.168.89.95"
  insecure = true
}

# === VARIABLES ===
# =============================================================================
# TODO-1: There is APIC secrets file named secrets.tfvars. Change the file name
# So that terraform take the secrets from that file automatically
# =============================================================================
variable "apic_username" {
  type      = string
  sensitive = true
}

variable "apic_password" {
  type      = string
  sensitive = true
}

variable "tcp_filters" {
  type = list(object({
    name = string
    port = number
  }))
}

variable "contracts" {
  type = list(object({
    name    = string
    filters = list(string)
  }))
}

variable "bridgedomains" {
  type = list(object({
    vrf  = string
    name = string
  }))
}

variable "apps" {
  type = map(list(object({
    name = string
    bd   = string
  })))
}



# =============================================================================
# TODO-2: TENANT AND VRFs
# Create tenant=e2-sim-Devnet-tenant
# Create three VRFs "Devnet-vrf", "INTERNAL" and "EXTERNAL" [using manual method]
# =============================================================================

resource "aci_tenant" "devnet_tenant" {
  name        = "e2-sim-Devnet-tenant"
  description = "P5 Creation"
}

resource "aci_vrf" "devnet_vrf" {
  parent_dn = aci_tenant.devnet_tenant.id
  name      = "Devnet-vrf"
}

resource "aci_vrf" "internal" {
  parent_dn =  aci_tenant.devnet_tenant.id
  name      = "INTERNAL"
}

resource "aci_vrf" "external" {
  parent_dn = "uni/tn-e2-sim-Devnet-tenant"    # use manual method uni/
  name      = "EXTERNAL"
}
# =============================================================================
# TODO-3: BRIDGE DOMAINS
# =============================================================================
# Create a standalone bridgedomain name=Devnet-BD and relate it to "devnet_vrf", 
# that was created at the begining
resource "aci_bridge_domain" "devnet_vrf_bd" {
  parent_dn = aci_tenant.devnet_tenant.id
  name               = "Devnet-BD"
  relation_to_vrf = { 
    vrf_name = aci_vrf.devnet_vrf.name
  }
}
# Crate bridgedomain using variable "var.bridgedomains", and relate to vrf.internal/external
resource "aci_bridge_domain" "bridge_domains" {
  for_each           = { for entry in var.bridgedomains: entry.name=>entry }
  parent_dn          = aci_tenant.devnet_tenant.id
  name               = each.key
  relation_to_vrf = {
    vrf_name = each.value.vrf == "INTERNAL" ? aci_vrf.internal.name : aci_vrf.external.name
    }
}

# =============================================================================
# TODO-4: APPLICATION PROFILES
# Crate application-profile=Devnet-app
# =============================================================================

resource "aci_application_profile" "devnet_app" {
  parent_dn =  aci_tenant.devnet_tenant.id
  name      = "Devnet-app"
}

variable "apps_and_epgs" {
  default = [
    { prf_name = "App1", epgs = ["A", "B"] },
    { prf_name = "App2", epgs = ["C", "A"] }
  ]
}

# Create App Profiles from structured var.apps_epgs data using for_each
resource "aci_application_profile" "apps" {
  for_each  = {for entry in var.apps_and_epgs: entry.prf_name=> entry}
  parent_dn = aci_tenant.devnet_tenant.id
  name      = each.key
}


# # =============================================================================
# # TODO-5: EPGs FROM LIST
# # Create 3-epgs from var.epgs and keep them under "aci_application_profile" "devnet_app"
# # =============================================================================
variable "epgs" {
  default = ["Associate", "Professional", "Expert"] 
}
resource "aci_application_epg" "simple_epgs" {
  for_each               = toset(var.epgs)
  parent_dn              = aci_application_profile.devnet_app.id
  name                   = each.key
}

#! toset() converts a list to a set because for_each requires either a set or a map, not a list.
#! For a set, each.key and each.value are identical:
#! List (has order, allows duplicates) - NOT allowed for for_each
#! ["Associate", "Professional", "Expert"]

#! Set (no order, unique values) - Allowed for for_each
#! toset(["Associate", "Professional", "Expert"])

# # =============================================================================
# # TODO-6: EPGs FROM NESTED DATA (flatten)
# # Restructure the var.apps_and_epgs ==> local.epg_map with unique key
# # =============================================================================
# /*
# variable "apps_and_epgs" {
#   default = [
#     { prf_name = "App1", epgs = ["A", "B"] },
#     { prf_name = "App2", epgs = ["C", "A"] }
#   ]
# }
# */
locals {
  epg_map = flatten([
    for entry in var.apps_and_epgs: [
        for epg in entry.epgs: {
            epg_name=epg 
            app_name=entry.prf_name 
            key="${entry.prf_name}-${epg}"
        }
    ]
  ])
}
# Create application_epg using local.epg_map, and keep them under "aci_application_profile" "apps"
# Create the relation_to_bridge_domain with "aci_bridge_domain" "devnet_vrf_bd", which created under TODO-3
resource "aci_application_epg" "structured_epgs" {
  for_each               = {for entry in local.epg_map: entry.key=>entry}
  parent_dn              =  aci_application_profile.apps[each.value.app_name].id
  name                   = each.value.epg_name
  relation_to_bridge_domain = {
    bridge_domain_name = aci_bridge_domain.devnet_vrf_bd.name
  }      
}

# # =============================================================================
# # TODO-7: FILTERS AND FILTER ENTRIES
# # Create aci_filter and aci_filter_entry based on tcp_filters
# # Each filter_entry name would be TCP_port, where port=80,443 etc
# # destination and source ports are same as var.tcp_filters
# # =============================================================================

resource "aci_filter" "tcp_filters" {
  for_each  = {for entry in var.tcp_filters: entry.name=>entry}
  tenant_dn = aci_tenant.devnet_tenant.id
  name      = each.key
}

resource "aci_filter_entry" "tcp_filter_entries" {
  for_each    = {for entry in var.tcp_filters: entry.name=>entry}
  filter_dn   = aci_filter.tcp_filters[each.key].id
  name        = "TCP_${each.value.port}"
  ether_t     = "ip"
  prot        = "tcp"
  d_from_port = each.value.port
  d_to_port   = each.value.port
}

# # =============================================================================
# # TODO-8: CONTRACTS AND SUBJECTS
# # Create aci_contract and aci_contract_subject based on variable "contracts"
# # relation_vz_rs_subj_filt_att with "aci_filter" "tcp_filters" for contract_subject
# # =============================================================================

resource "aci_contract" "contracts" {
  for_each  = {for entry in var.contracts: entry.name=>entry}
  tenant_dn = aci_tenant.devnet_tenant.id
  name      = each.key
}

resource "aci_contract_subject" "contract_subjects" {
  for_each    = {for entry in var.contracts: entry.name=>entry}
  contract_dn = aci_contract.contracts[each.key].id
  name        = "permit"
  apply_both_directions = "no"
  consumer_to_provider {
    prio        = "unspecified"
    target_dscp = "unspecified"
    dynamic "relation_vz_rs_filt_att" {
    for_each = each.value.filters   # ["HTTP", "HTTPS", "Custom_HTTP", "Custom_HTTPS"]
    content {
        action = "permit"
        filter_dn = aci_filter.tcp_filters[relation_vz_rs_filt_att.value].id
        }
    }
  } 
    provider_to_consumer {
    prio        = "unspecified"
    target_dscp = "unspecified"
    
    dynamic "relation_vz_rs_filt_att" {
      for_each = each.value.filters     # ["HTTP", "HTTPS", "Custom_HTTP", "Custom_HTTPS"]
      content {
        action    = "permit"
        filter_dn = aci_filter.tcp_filters[relation_vz_rs_filt_att.value].id
      }
    }
  }
}


# # ****OLD WAY STILL WORKS
# resource "aci_contract_subject" "contract_subject" {
#   for_each = {for entry in var.contracts: entry.name=>entry}
#   contract_dn = aci_contract.contracts[each.key].id
#   name= "permit"
#   relation_vz_rs_subj_filt_att = [for filter in each.value.filters : aci_filter.tcp_filters[filter].id]
# }


# # =============================================================================
# # TODO-9: CORP/DMZ APP PROFILES AND EPGs
# # =============================================================================
# Create application profile using variable var.apps
resource "aci_application_profile" "corp_dmz_apps" {
  for_each  = tomap(var.apps)
  parent_dn = aci_tenant.devnet_tenant.id
  name      = each.key
}
# Restructure the var.apps under local.corp_dmz_epgs with unique key; so that it creates list of objects
locals {
  corp_dmz_epgs = flatten([
    for key, value in var.apps: [
        for entry in value: {
            app_name=key 
            epg_name=entry.name 
            bd_name=entry.bd 
            unique="${key}-${entry.name}"
        }
    ]
  ])
}
# Create aci_aaplication_epg and fill the relation with bridgedomain in TODO-3;
# "aci_bridge_domain" "bridge_domains" 
resource "aci_application_epg" "corp_dmz_epgs" {
  for_each               = {for entry in local.corp_dmz_epgs: entry.unique=>entry}
  parent_dn              = aci_application_profile.corp_dmz_apps[each.value.app_name].id
  name                   = each.value.epg_name
  relation_to_bridge_domain      = {
    bridge_domain_name=aci_bridge_domain.bridge_domains[each.value.bd_name].name
  }
}


# # =============================================================================
# # TODO-10: CONTRACT ALLOCATIONS
# # =============================================================================

# Allocate Web contract to structured_epgs["App1-A"] [TODO-6, application_epgs]as consumer
resource "aci_epg_to_contract" "web_contract_app1_a" {
  application_epg_dn = aci_application_epg.structured_epgs["App1-A"].id
  contract_dn        = aci_contract.contracts["Web"].id
  contract_type      = "consumer"
}

# Allocate Custom_Web contract to corp_dmz_epgs["DMZ-WEBSITE"] as consumer
resource "aci_epg_to_contract" "custom_web_website" {
  application_epg_dn = aci_application_epg.corp_dmz_epgs["DMZ-WEBSITE"].id
  contract_dn        = aci_contract.contracts["Custom_Web"].id
  contract_type      = "consumer"
}


# # =============================================================================
# # OUTPUTS
# # =============================================================================

output "tenant_id" {
  value = aci_tenant.devnet_tenant.id
}

output "vrf_ids" {
  value = {
    devnet   = aci_vrf.devnet_vrf.id
    internal = aci_vrf.internal.id
    external = aci_vrf.external.id
  }
}

output "application_profiles" {
  value = { for k, v in aci_application_profile.apps : k => v.id }
}

output "epg_map_debug" {
  description = "Shows the flattened EPG map structure"
  value       = local.epg_map
}

output "corp_dmz_epgs_debug" {
  description = "Shows the flattened CORP/DMZ EPG structure"
  value       = local.corp_dmz_epgs
}

```

</details>

<details>
<summary>secrets.auto.tfvars (click to expand)</summary>

```hcl
apic_username = "admin"
apic_password = "1234QWer!"
```

</details>