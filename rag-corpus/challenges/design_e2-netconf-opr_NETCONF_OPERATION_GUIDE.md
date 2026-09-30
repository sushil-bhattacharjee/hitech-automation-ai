## YANG TREE

> **Note**: Generated with `pyang -f tree Cisco-IOS-XE-native.yang Cisco-IOS-XE-acl.yang`
> - `ios-acl:` prefix maps to `Cisco-IOS-XE-acl:` in JSON payloads
> - Root path: `Cisco-IOS-XE-native:native/ip/access-list`

```
module: Cisco-IOS-XE-native
  +--rw native
     +--rw ip
        +--rw access-list
           +--rw ios-acl:standard* [name]
           |  +--rw ios-acl:name                    std-acl-type
           |  +--rw ios-acl:access-list-seq-rule* [sequence]
           |     +--rw ios-acl:sequence        acl-sequence
           |     +--rw (ios-acl:action)?
           |        +--:(ios-acl:permit-action)
           |        |  +--rw ios-acl:permit
           |        |     +--rw ios-acl:std-ace
           |        |        +--rw (ios-acl:source)?
           |        |           +--:(ios-acl:any-source)
           |        |           |  +--rw ios-acl:any?            empty
           |        |           +--:(ios-acl:host-source)
           |        |           |  +--rw ios-acl:host-address?   inet:ipv4-address
           |        |           +--:(ios-acl:network-source)
           |        |              +--rw ios-acl:ipv4-address?   inet:ipv4-address
           |        |              +--rw ios-acl:mask?           inet:ipv4-address
           |        +--:(ios-acl:deny-action)
           |           +--rw ios-acl:deny
           |              +--rw ios-acl:std-ace
           |                 +--rw (ios-acl:source)?
           |                    +--:(ios-acl:any-source)
           |                    |  +--rw ios-acl:any?            empty
           |                    +--:(ios-acl:host-source)
           |                    |  +--rw ios-acl:host-address?   inet:ipv4-address
           |                    +--:(ios-acl:network-source)
           |                       +--rw ios-acl:ipv4-address?   inet:ipv4-address
           |                       +--rw ios-acl:mask?           inet:ipv4-address
           +--rw ios-acl:extended* [name]
              +--rw ios-acl:name                    ext-acl-type
              +--rw ios-acl:access-list-seq-rule* [sequence]
                 +--rw ios-acl:sequence    acl-sequence
                 +--rw ios-acl:ace-rule
                    +--rw ios-acl:action?                    acl-action
                    +--rw ios-acl:protocol?                  protocol-type
                    +--rw (ios-acl:source)?
                    |  +--:(ios-acl:any-source)
                    |  |  +--rw ios-acl:any?                 empty
                    |  +--:(ios-acl:host-source)
                    |  |  +--rw ios-acl:host-address?        inet:ipv4-address
                    |  +--:(ios-acl:network-source)
                    |     +--rw ios-acl:ipv4-address?        inet:ipv4-address
                    |     +--rw ios-acl:mask?                inet:ipv4-address
                    +--rw (ios-acl:src-port-match)?
                    |  +--:(ios-acl:src-equal)
                    |  |  +--rw ios-acl:src-eq?              acl-port-type
                    |  +--:(ios-acl:src-not-equal)
                    |  |  +--rw ios-acl:src-neq?             acl-port-type
                    |  +--:(ios-acl:src-greater-than)
                    |  |  +--rw ios-acl:src-gt?              acl-port-type
                    |  +--:(ios-acl:src-less-than)
                    |  |  +--rw ios-acl:src-lt?              acl-port-type
                    |  +--:(ios-acl:src-range)
                    |     +--rw ios-acl:src-range1?          acl-port-type
                    |     +--rw ios-acl:src-range2?          acl-port-type
                    +--rw (ios-acl:destination)?
                    |  +--:(ios-acl:any-destination)
                    |  |  +--rw ios-acl:dst-any?             empty
                    |  +--:(ios-acl:host-destination)
                    |  |  +--rw ios-acl:dst-host-address?    inet:ipv4-address
                    |  +--:(ios-acl:network-destination)
                    |     +--rw ios-acl:dest-ipv4-address?   inet:ipv4-address
                    |     +--rw ios-acl:dest-mask?           inet:ipv4-address
                    +--rw (ios-acl:dst-port-match)?
                       +--:(ios-acl:dst-equal)
                       |  +--rw ios-acl:dst-eq?              acl-port-type
                       +--:(ios-acl:dst-not-equal)
                       |  +--rw ios-acl:dst-neq?             acl-port-type
                       +--:(ios-acl:dst-greater-than)
                       |  +--rw ios-acl:dst-gt?              acl-port-type
                       +--:(ios-acl:dst-less-than)
                       |  +--rw ios-acl:dst-lt?              acl-port-type
                       +--:(ios-acl:dst-range)
                          +--rw ios-acl:dst-range1?          acl-port-type
                          +--rw ios-acl:dst-range2?          acl-port-type
```

# NETCONF Operations Guide

## Overview

NETCONF operations control **how** configuration data is applied to network devices. The operation is specified using the `nc:operation` attribute in your XML payload.

**Default Behavior:** If no operation is specified, `merge` is used automatically.

---

## The Four Main Operations

### 1. CREATE (like REST POST)
- **Behavior:** Creates new configuration **only**
- **Fails if:** Element already exists
- **Use case:** Safety check - ensure you're creating something new
- **Idempotent:** ❌ No (fails on second run)

```xml
<access-list-seq-rule nc:operation="create">
    <sequence>45</sequence>
    <ace-rule>
        <action>permit</action>
        <protocol>tcp</protocol>
        <any/>
        <dst-any/>
    </ace-rule>
</access-list-seq-rule>
```

**Result:** Creates sequence 45. Fails if sequence 45 already exists.

---

### 2. MERGE (like REST PATCH - Default)
- **Behavior:** Creates new elements OR updates existing ones
- **Fails if:** Never (always succeeds)
- **Use case:** Idempotent scripts, ensure desired state
- **Idempotent:** ✅ Yes (safe to run multiple times)

```xml
<access-list-seq-rule nc:operation="merge">
    <sequence>45</sequence>
    <ace-rule>
        <action>permit</action>
        <protocol>tcp</protocol>
        <any/>
        <dst-any/>
    </ace-rule>
</access-list-seq-rule>
```

**Result:** 
- If sequence 45 exists: Updates it
- If sequence 45 doesn't exist: Creates it

---

### 3. REPLACE (like REST PUT)
- **Behavior:** Replaces entire container/entry with your config
- **Deletes:** Everything not mentioned at that level
- **Use case:** Set exact state - "I want exactly this, nothing else"
- **Idempotent:** ✅ Yes

```xml
<extended nc:operation="replace">
    <name>MY-ACL</name>
    <access-list-seq-rule>
        <sequence>10</sequence>
        <ace-rule>
            <action>permit</action>
            <protocol>ip</protocol>
            <any/>
            <dst-any/>
        </ace-rule>
    </access-list-seq-rule>
</extended>
```

**Result:** MY-ACL will have **ONLY** sequence 10. Any other sequences are deleted.

---

### 4. DELETE
- **Behavior:** Removes specified elements
- **Fails if:** Element doesn't exist
- **Use case:** Explicitly remove configuration
- **Idempotent:** ❌ No (fails if already deleted)

```xml
<access-list-seq-rule nc:operation="delete">
    <sequence>45</sequence>
</access-list-seq-rule>
```

**Result:** Deletes sequence 45 from the ACL.

---

## REST API Analogy

| NETCONF Operation | REST Equivalent | Behavior | Idempotent |
|-------------------|-----------------|----------|------------|
| `create` | POST | Create only (fail if exists) | ❌ No |
| `merge` | PATCH | Create or update | ✅ Yes |
| `replace` | PUT | Replace entire resource | ✅ Yes |
| `delete` | DELETE | Remove resource | ❌ No |

---

## Operation Hierarchy

Operations can be placed at different XML levels, affecting different scopes:

```xml
<config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
        <ip>
            <!-- Container: Rarely used (too broad) -->
            <access-list>
                
                <!-- LEVEL 1: Entire ACL -->
                <extended nc:operation="replace">
                    <name>ACL-NAME</name>  <!-- KEY: Identifies which ACL -->
                    
                    <!-- LEVEL 2: Single Rule -->
                    <access-list-seq-rule nc:operation="create">
                        <sequence>10</sequence>  <!-- KEY: Identifies which rule -->
                        
                        <!-- DATA: Inherits operation from parent -->
                        <ace-rule>
                            <action>permit</action>
                            <protocol>tcp</protocol>
                        </ace-rule>
                    </access-list-seq-rule>
                </extended>
            </access-list>
        </ip>
    </native>
</config>
```

### Operation Scope

| Level | Scope | Typical Use |
|-------|-------|-------------|
| `<extended>` or `<standard>` | Entire ACL | ✅ Common |
| `<access-list-seq-rule>` | Single rule | ✅ Very common |
| `<access-list>` | All ACLs (standard + extended) | ⚠️ Rare (dangerous) |

---

## Element Types and Operations

Different XML element types have different rules for operations:

```
Element Type          Operations Allowed?    Common Usage
═══════════════════════════════════════════════════════════════
Container             ✅ Yes                 Rare (broad scope)
List                  ✅ Yes                 Common
List Entry            ✅ Yes                 Very Common  
Key Leaf              ❌ No                  Never
Regular Leaf          ✅ Yes                 Sometimes useful
                                             (often unnecessary)
```

### Explanation

- **Container** (e.g., `<access-list>`) - Groups related elements. Operations affect everything inside.
- **List** (e.g., `<extended>`, `<standard>`) - Collection of entries. Operations affect all entries.
- **List Entry** (e.g., `<access-list-seq-rule>`) - Single instance. Operations affect this entry only.
- **Key Leaf** (e.g., `<name>`, `<sequence>`) - Identifies entries. No operations (used for selection).
- **Regular Leaf** (e.g., `<action>`, `<protocol>`) - Data values. Operations possible but usually inherit from parent.

---

## Key vs. Data Elements

### Keys (Identifiers)
- **Purpose:** Identify WHICH element to operate on
- **Immutable:** Cannot be changed (must delete and recreate)
- **No operations:** Operations go on the parent, not the key itself

**Examples:**
- `<name>` - Identifies which ACL
- `<sequence>` - Identifies which rule

### Data Elements
- **Purpose:** Actual configuration values
- **Mutable:** Can be updated with operations
- **Inherits operations:** From parent container/list entry

**Examples:**
- `<action>permit</action>`
- `<protocol>tcp</protocol>`
- `<host>198.36.36.36</host>`

---

## Changing a Key Value (Rename Pattern)

**You CANNOT directly change a key.** Keys are immutable identifiers.

To "change" a key, use delete + create:

```xml
<config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
        <ip>
            <access-list>
                <extended xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-acl"
                          xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
                    <name>OLD-ACL-NAME</name>
                    
                    <!-- Step 1: Delete old entry -->
                    <access-list-seq-rule nc:operation="delete">
                        <sequence>10</sequence>
                    </access-list-seq-rule>
                    
                    <!-- Step 2: Create new entry with different key -->
                    <access-list-seq-rule nc:operation="create">
                        <sequence>20</sequence>  <!-- New sequence number -->
                        <ace-rule>
                            <action>permit</action>
                            <protocol>tcp</protocol>
                            <any/>
                            <dst-any/>
                        </ace-rule>
                    </access-list-seq-rule>
                </extended>
            </access-list>
        </ip>
    </native>
</config>
```

---

## Operations on Leaf Elements

**Leaf elements CAN have operations, but it's usually unnecessary.**

### When Operations on Leaves Are Useful:

1. **DELETE operation** - Remove optional configuration
2. **Explicit clarity** - Make intent clear in code

```xml
<!-- Useful: Delete optional leaf -->
<description nc:operation="delete"/>

<!-- Unnecessary but valid: Replace leaf value -->
<protocol nc:operation="replace">udp</protocol>

<!-- Same result without operation (merge handles it) -->
<protocol>udp</protocol>
```

**Bottom line:** For simple value updates, omit the operation and let default `merge` handle it.

---

## Reference Example: replace_seq_payload.xml

```xml
<config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
        <ip>
            <access-list> <!-- Container: Organizational structure, operations rarely placed here -->
                <extended xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-acl"> <!-- CREATE/REPLACE/DELETE/MERGE --> 
                    <n>exam2-netconf-create-15</n> <!-- KEY: Immutable and Identifies which ACL. No operations here. -->
                    <access-list-seq-rule xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0" nc:operation="replace"> <!-- CREATE/REPLACE/DELETE/MERGE --> 
                        <sequence>35</sequence> <!-- KEY: Immutable and Identifies which rule. No operations here. -->
                        <ace-rule>
                            <action>permit</action> <!-- limited! CREATE/REPLACE/DELETE/MERGE! DATA: Inherits operation from parent -->
                            <protocol>tcp</protocol> <!-- limited! CREATE/REPLACE/DELETE/MERGE! DATA: Inherits operation from parent -->
                            <host>198.36.36.36</host><!-- limited! CREATE/REPLACE/DELETE/MERGE! DATA: Inherits operation from parent -->
                            <src-eq>636</src-eq> <!-- limited! CREATE/REPLACE/DELETE/MERGE! DATA: Inherits operation from parent -->
                            <dest-ipv4-address>203.36.36.32</dest-ipv4-address> <!-- limited! CREATE/REPLACE/DELETE/MERGE! DATA: Inherits operation from parent -->
                            <dest-mask>0.0.0.15</dest-mask> <!-- limited! CREATE/REPLACE/DELETE/MERGE! DATA: Inherits operation from parent -->
                            <dst-gt>636</dst-gt> <!-- limited! CREATE/REPLACE/DELETE/MERGE! DATA: Inherits operation from parent -->
                        </ace-rule>
                    </access-list-seq-rule>
                </extended>
            </access-list>
        </ip>
    </native>
</config>
<!-- If no operation is defined, then default operation="merge"-->
```

**What this does:**
1. Finds ACL named "exam2-netconf-create-15"
2. Finds sequence 35 within that ACL
3. **Replaces** the entire content of sequence 35 with the new ace-rule
4. Other sequences in the ACL remain unchanged

---

## Quick Decision Guide

### Which Operation Should I Use?

| Scenario | Operation | Why |
|----------|-----------|-----|
| Ensure config exists (run multiple times) | `merge` | Idempotent, safe |
| Add new rule, prevent overwrite | `create` | Safety check |
| Set exact state for ACL | `replace` on `<extended>` | Removes unmentioned rules |
| Update existing rule | `merge` or delete+create | Flexible or explicit |
| Remove specific rule | `delete` | Explicit removal |
| Change key value (e.g., sequence 10→20) | delete old + create new | Keys are immutable |

---

## Common Patterns

### Pattern 1: Idempotent ACL Rule
```xml
<!-- Safe to run multiple times -->
<access-list-seq-rule nc:operation="merge">
    <sequence>10</sequence>
    <ace-rule>...</ace-rule>
</access-list-seq-rule>
```

### Pattern 2: Safety-Checked Creation
```xml
<!-- Fails if rule already exists -->
<access-list-seq-rule nc:operation="create">
    <sequence>10</sequence>
    <ace-rule>...</ace-rule>
</access-list-seq-rule>
```

### Pattern 3: Exact State for ACL
```xml
<!-- ACL will have ONLY these rules -->
<extended nc:operation="replace">
    <name>MY-ACL</name>
    <access-list-seq-rule>
        <sequence>10</sequence>
        <ace-rule>...</ace-rule>
    </access-list-seq-rule>
    <access-list-seq-rule>
        <sequence>20</sequence>
        <ace-rule>...</ace-rule>
    </access-list-seq-rule>
</extended>
```

### Pattern 4: Mixed Operations
```xml
<!-- Different operations on different rules -->
<extended>
    <name>MY-ACL</name>
    
    <access-list-seq-rule nc:operation="delete">
        <sequence>10</sequence>
    </access-list-seq-rule>
    
    <access-list-seq-rule nc:operation="create">
        <sequence>20</sequence>
        <ace-rule>...</ace-rule>
    </access-list-seq-rule>
    
    <access-list-seq-rule nc:operation="merge">
        <sequence>30</sequence>
        <ace-rule>...</ace-rule>
    </access-list-seq-rule>
</extended>
```

---

## Summary Table

| Operation | If Exists | If Missing | Deletes Unmentioned | Best For |
|-----------|-----------|------------|---------------------|----------|
| **create** | ❌ Fails | ✅ Creates | N/A | New config with safety |
| **merge** | ✅ Updates | ✅ Creates | ❌ No | Idempotent scripts |
| **replace** | ✅ Replaces | ✅ Creates | ✅ Yes (at that level) | Exact state |
| **delete** | ✅ Deletes | ❌ Fails | N/A | Remove config |

---

## Key Takeaways

1. **Operations target containers/lists**, not individual keys or (typically) leaf elements
2. **Keys are identifiers** - they specify WHICH element to operate on
3. **Data elements inherit** operations from their parent container
4. **MERGE = PATCH** - Create or update (most flexible)
5. **CREATE = POST** - Create only (safety check)
6. **REPLACE = PUT** - Set exact state (removes unmentioned items)
7. **Default is merge** - If you omit `nc:operation`, merge is used
8. **To change a key** - Delete old entry and create new one (keys are immutable)

---

## Best Practices

✅ **DO:**
- Use `merge` for idempotent automation scripts
- Use `create` when you want to prevent accidental overwrites
- Use `replace` at ACL level to ensure exact state
- Use candidate datastore with confirmed commit for critical changes
- Test operations in lab environment first

❌ **DON'T:**
- Put operations on key elements (`<name>`, `<sequence>`)
- Use `replace` on `<access-list>` container (affects ALL ACLs)
- Try to change key values directly (delete + create instead)
- Forget that `replace` deletes unmentioned config at that level
- Skip validation before committing to production devices