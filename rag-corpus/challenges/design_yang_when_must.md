# YANG "when" and "must" Statements - Reference Guide

## Quick Summary

| Statement | Purpose | Effect when FALSE | Use Case |
|-----------|---------|-------------------|----------|
| **when** | Controls node **existence** | Node doesn't exist in data tree | Conditional configuration options |
| **must** | Validates node **values** | Configuration rejected with error | Business logic validation |

---

## The "when" Statement

### Purpose
Controls whether a data node exists in the configuration tree based on a condition.

### Syntax
```yang
when 'xpath-expression';
```

### Simple Example 1: Basic Conditional Leaf

```yang
container interface {
  leaf type {
    type enumeration {
      enum ethernet;
      enum serial;
      enum loopback;
    }
  }
  
  // This leaf ONLY exists when interface type is ethernet
  leaf duplex {
    when '../type = "ethernet"';
    type enumeration {
      enum half;
      enum full;
      enum auto;
    }
  }
  
  // This leaf ONLY exists when interface type is serial
  leaf clock-rate {
    when '../type = "serial"';
    type uint32;
  }
}
```

**Result:**
- Configure `type = "ethernet"` → `duplex` leaf appears, `clock-rate` doesn't exist
- Configure `type = "serial"` → `clock-rate` leaf appears, `duplex` doesn't exist
- Configure `type = "loopback"` → neither `duplex` nor `clock-rate` exist

### Simple Example 2: Protocol Enable/Disable

```yang
container bgp {
  leaf enabled {
    type boolean;
    default false;
  }
  
  // BGP AS number only exists when BGP is enabled
  leaf as-number {
    when '../enabled = "true"';
    type uint32;
    mandatory true;
  }
  
  // BGP neighbors only exist when BGP is enabled
  list neighbor {
    when '../../enabled = "true"';
    key "address";
    
    leaf address {
      type inet:ip-address;
    }
    
    leaf remote-as {
      type uint32;
    }
  }
}
```

**Result:**
- `enabled = false` → Only the `enabled` leaf exists, no `as-number` or `neighbor` nodes
- `enabled = true` → All BGP configuration nodes become available

### Simple Example 3: Augmentation with when

```yang
module base-interface {
  list interface {
    key "name";
    
    leaf name {
      type string;
    }
    
    leaf type {
      type identityref {
        base interface-type;
      }
    }
  }
}

module ethernet-extension {
  import base-interface { prefix base; }
  
  // Add ethernet-specific config ONLY to ethernet interfaces
  augment "/base:interface" {
    when 'type = "ethernet"';
    
    container ethernet {
      leaf speed {
        type enumeration {
          enum 10M;
          enum 100M;
          enum 1G;
          enum 10G;
        }
      }
      
      leaf duplex {
        type enumeration {
          enum half;
          enum full;
        }
      }
    }
  }
}
```

**Result:**
- Interface with `type = "ethernet"` → Gets `ethernet` container with `speed` and `duplex`
- Interface with `type = "serial"` → No `ethernet` container exists

---

## The "must" Statement

### Purpose
Validates that data values satisfy business logic constraints.

### Syntax
```yang
must 'xpath-expression' {
  error-message "Error description";
  error-app-tag "error-tag";
}
```

### Simple Example 1: Value Range Validation

```yang
container interface {
  leaf type {
    type enumeration {
      enum ethernet;
      enum atm;
    }
  }
  
  leaf mtu {
    type uint32;
  }
  
  // If ethernet, MTU must be 1500
  must 'type != "ethernet" or mtu = 1500' {
    error-message "Ethernet MTU must be 1500";
  }
  
  // If ATM, MTU must be in range 64-17966
  must 'type != "atm" or (mtu >= 64 and mtu <= 17966)' {
    error-message "ATM MTU must be between 64 and 17966";
  }
}
```

**Result:**
- Try to set `type = "ethernet"` and `mtu = 9000` → **REJECTED** with error message
- Set `type = "ethernet"` and `mtu = 1500` → **ACCEPTED**
- Set `type = "atm"` and `mtu = 1000` → **ACCEPTED**

### Simple Example 2: Cross-Field Validation

```yang
container bgp {
  leaf local-as {
    type uint32;
  }
  
  list neighbor {
    key "address";
    
    leaf address {
      type inet:ip-address;
    }
    
    leaf remote-as {
      type uint32;
    }
    
    leaf peer-type {
      type enumeration {
        enum internal;
        enum external;
      }
    }
    
    // IBGP neighbors must have same AS as local
    must 'peer-type != "internal" or remote-as = ../../local-as' {
      error-message "IBGP neighbor must have same AS as local AS";
    }
    
    // EBGP neighbors must have different AS from local
    //If peer-type = "external" THEN remote-as ≠ local-as
    //But XPath doesn't have "if-then", so we use the logical equivalent: NOT(peer-type = "external") OR (remote-as ≠ local-as)
    // Which is: peer-type != "external" or remote-as != ../../local-as
    //must 'A != X or B != Y'; read it as: "If A equals X, then B must not equal Y"
    must 'peer-type != "external" or remote-as != ../../local-as' {
      error-message "EBGP neighbor must have different AS from local AS";
    }
  }
}
```

**Result:**
- `local-as = 65001`, neighbor with `peer-type = "internal"` and `remote-as = 65002` → **REJECTED**
- `local-as = 65001`, neighbor with `peer-type = "internal"` and `remote-as = 65001` → **ACCEPTED**
- `local-as = 65001`, neighbor with `peer-type = "external"` and `remote-as = 65001` → **REJECTED**

### Simple Example 3: Dependency Validation

```yang
container access-list {
  list rule {
    key "sequence";
    
    leaf sequence {
      type uint32;
    }
    
    leaf action {
      type enumeration {
        enum permit;
        enum deny;
      }
    }
    
    leaf protocol {
      type enumeration {
        enum ip;
        enum tcp;
        enum udp;
        enum icmp;
      }
    }
    
    leaf src-port {
      type uint16;
    }
    
    leaf dst-port {
      type uint16;
    }
    
    // Ports are only valid for TCP/UDP protocols
    must 'not(src-port) or protocol = "tcp" or protocol = "udp"' {
      error-message "Source port can only be specified for TCP or UDP";
    }
    
    must 'not(dst-port) or protocol = "tcp" or protocol = "udp"' {
      error-message "Destination port can only be specified for TCP or UDP";
    }
  }
}
```

**Result:**
- `protocol = "icmp"` with `src-port = 80` → **REJECTED** (ICMP doesn't use ports)
- `protocol = "tcp"` with `src-port = 80` → **ACCEPTED**
- `protocol = "ip"` with no ports → **ACCEPTED**

---

## when vs must: Side-by-Side Comparison

### Scenario: BGP Configuration

```yang
container bgp {
  leaf enabled {
    type boolean;
    default false;
  }
  
  // Using "when" - node only exists when BGP is enabled
  leaf as-number {
    when '../enabled = "true"';
    type uint32;
  }
  
  // This would be WRONG - don't use "must" for existence control
  // leaf as-number {
  //   type uint32;
  //   must '../enabled = "true"' {
  //     error-message "BGP must be enabled to configure AS number";
  //   }
  // }
  
  list neighbor {
    when '../../enabled = "true"';  // "when" controls existence
    key "address";
    
    leaf address {
      type inet:ip-address;
    }
    
    leaf remote-as {
      type uint32;
      must '. >= 1 and . <= 4294967295' {  // "must" validates range
        error-message "AS number must be 1-4294967295";
      }
    }
  }
}
```

**Behavior:**
1. **when**: `enabled = false` → `as-number` and `neighbor` nodes don't exist (no error, just absent)
2. **must**: If `neighbor` exists, validates that `remote-as` is in valid range (error if invalid)

---

## Combined Example: Complete Network Configuration

```yang
module network-config {
  yang-version 1.1;
  namespace "http://example.com/network";
  prefix net;

  container routing {
    // Protocol enablement
    container protocols {
      leaf ospf-enabled {
        type boolean;
        default false;
      }
      
      leaf bgp-enabled {
        type boolean;
        default false;
      }
    }
    
    // OSPF configuration - only exists when enabled
    container ospf {
      when '../protocols/ospf-enabled = "true"';
      
      leaf process-id {
        type uint32;
        mandatory true;
      }
      
      list area {
        key "area-id";
        
        leaf area-id {
          type uint32;
        }
        
        leaf type {
          type enumeration {
            enum normal;
            enum stub;
            enum nssa;
          }
        }
        
        // Stub areas cannot be area 0
        must 'type != "stub" or area-id != 0' {
          error-message "Area 0 cannot be a stub area";
        }
        
        // NSSA areas cannot be area 0
        must 'type != "nssa" or area-id != 0' {
          error-message "Area 0 cannot be an NSSA area";
        }
      }
    }
    
    // BGP configuration - only exists when enabled
    container bgp {
      when '../protocols/bgp-enabled = "true"';
      
      leaf as-number {
        type uint32;
        mandatory true;
        must '. >= 1 and . <= 4294967295' {
          error-message "AS number must be in range 1-4294967295";
        }
      }
      
      list neighbor {
        key "address";
        
        leaf address {
          type inet:ip-address;
        }
        
        leaf remote-as {
          type uint32;
          must '. >= 1 and . <= 4294967295' {
            error-message "Remote AS must be in range 1-4294967295";
          }
        }
        
        leaf ebgp-multihop {
          when '../remote-as != ../../as-number';  // Only for EBGP
          type uint8 {
            range "1..255";
          }
        }
        
        // EBGP peers in different AS need multihop if TTL > 1
        must 'remote-as = ../../as-number or ebgp-multihop or 
              not(ebgp-multihop)' {
          error-message "EBGP neighbors should configure multihop if needed";
        }
      }
    }
  }
}
```

---

## Key Restrictions

### when Statement Restrictions

1. **Cannot use on list keys:**
   ```yang
   list interface {
     key "name";
     leaf name {
       // ILLEGAL: when 'some-condition';  ❌
       type string;
     }
   }
   ```

2. **Cannot use on uses with key leafs:**
   ```yang
   grouping interface-key {
     leaf name { type string; }
   }
   
   list interface {
     key "name";
     // ILLEGAL: uses interface-key { when 'condition'; }  ❌
     uses interface-key;
   }
   ```

### must Statement Restrictions

1. **No circular dependencies in when statements:**
   ```yang
   leaf a {
     when '../b = "foo"';
   }
   
   leaf b {
     when '../a = "bar"';  // ❌ Circular dependency!
   }
   ```

---

## Practical Tips

### Use "when" for:
- ✅ Protocol-specific configuration (only show BGP config when BGP is enabled)
- ✅ Interface-type-specific settings (duplex only on ethernet)
- ✅ Feature flags (advanced options only when advanced mode enabled)
- ✅ Conditional augmentations (add nodes only to specific node instances)

### Use "must" for:
- ✅ Value range validation (MTU must be 1500 for ethernet)
- ✅ Cross-field validation (IBGP peer AS must equal local AS)
- ✅ Business logic rules (area 0 cannot be stub)
- ✅ Dependency validation (ports only valid for TCP/UDP)

### Don't use "when" for:
- ❌ Value validation (use must instead)
- ❌ Mandatory field checking (use mandatory true)

### Don't use "must" for:
- ❌ Controlling node existence (use when instead)
- ❌ Optional features (use when for conditional presence)

---

## XPath Context Quick Reference

### when Statement Context

```yang
container parent {
  leaf sibling { type string; }
  
  container child {
    when '../sibling = "active"';  // Context: parent container
    leaf data { type string; }
  }
}
```

### must Statement Context

```yang
container parent {
  leaf sibling { type uint32; }
  
  leaf child {
    type string;
    must '../sibling > 0';  // Context: parent container (can access siblings)
  }
}
```

---

## Detailed XPath Relative Path Navigation

### BGP Example Tree Structure (pyang tree view)

```
module: bgp-correct-example
  +--rw routing
     +--rw bgp
        +--rw as-number?   uint32              ← ../../as-number from neighbor context
        +--rw neighbor* [address]              ← ../ from leaf context
           +--rw address          inet:ip-address
           +--rw remote-as?       uint32       ← remote-as (sibling)
           +--rw peer-type?       enumeration
           +--rw ebgp-multihop?   uint8
```

### Understanding XPath Paths from Different Context Nodes

**Context node: neighbor entry** (where must/when statements are evaluated)

```
'remote-as != ../../as-number'
    │           │  │
    │           │  └─ Leaf in bgp container
    │           └─ bgp container (grandparent)
    └─ Leaf in current neighbor entry

'peer-type = "internal"'
    └─ Leaf in current neighbor entry (sibling)

'peer-type != "external" or remote-as != ../../as-number'
    │                        │            │  │
    │                        │            │  └─ Leaf in bgp container
    │                        │            └─ Up 2 levels to bgp
    │                        └─ Sibling leaf in neighbor
    └─ Sibling leaf in neighbor
```

### Visual Path Traversal Diagram

```
                    ┌─────────────────────────────┐
                    │   bgp container (Level 2)   │
                    │   ../../                     │
                    │                              │
                    │   +--rw as-number            │ ← ../../as-number
                    └──────────┬──────────────────┘
                               │
                     ┌─────────▼──────────────────┐
                     │  neighbor list (Level 1)   │
                     │  ../                        │
                     └──────────┬─────────────────┘
                                │
                     ┌──────────▼─────────────────────────┐
                     │  neighbor entry (Level 0 - CONTEXT)│
                     │                                     │
                     │  +--rw address         (sibling)   │
                     │  +--rw remote-as       (sibling)   │ ← remote-as
                     │  +--rw peer-type       (sibling)   │ ← peer-type
                     │  +--rw ebgp-multihop   (sibling)   │ ← ebgp-multihop
                     │                                     │
                     │  [must statement evaluated HERE]   │
                     └─────────────────────────────────────┘
```

### XPath Navigation Summary Table

**From neighbor list entry context:**

| XPath Expression | Target Node | Description | Levels Up |
|-----------------|-------------|-------------|-----------|
| `.` | Current node | The neighbor entry itself | 0 |
| `address` | Sibling leaf | Neighbor's IP address | 0 |
| `remote-as` | Sibling leaf | Neighbor's remote AS | 0 |
| `ebgp-multihop` | Sibling leaf | Multihop configuration | 0 |
| `peer-type` | Sibling leaf | Peer type (internal/external) | 0 |
| `../` | Parent node | The neighbor list container | 1 |
| `../../` | Grandparent | The bgp container | 2 |
| `../../as-number` | Grandparent's leaf | Local BGP AS number | 2 |
| `../../neighbor` | Sibling list | The neighbor list itself | 2 |

### Step-by-Step Path Traversal Example

**Expression: `../../as-number`**

Starting from: **neighbor entry** (the context node)

```
Step 1: First '../' - Navigate up one level
  Current: neighbor entry
    ↑
    │ ../ (go to parent)
    │
  Result: neighbor list

Step 2: Second '../' - Navigate up another level  
  Current: neighbor list
    ↑
    │ ../ (go to parent)
    │
  Result: bgp container

Step 3: Access 'as-number' - Get child leaf
  Current: bgp container
    │
    └─→ as-number (child leaf)
  
  Result: Value of as-number leaf
```

**Visual representation:**

```
bgp container (../../)              ← STEP 2: Second ../ brings you here
  ├── as-number                      ← STEP 3: Access this leaf
  └── neighbor list (../)            ← STEP 1: First ../ brings you here
        └── neighbor entry           ← START: Context node (you are here)
              ├── address
              ├── remote-as
              ├── peer-type
              └── ebgp-multihop
```

### Common XPath Patterns in YANG

#### Pattern 1: Sibling Access (Same Level)
```yang
container config {
  leaf enabled { type boolean; }
  leaf mode {
    type string;
    when '../enabled = "true"';  // Access sibling directly
  }
}
```

#### Pattern 2: Parent Access (One Level Up)
```yang
list interface {
  leaf name { type string; }
  container ipv4 {
    must '../name != "loopback0"';  // Go up 1 level to access sibling
    leaf address {
      type inet:ipv4-address;
    }
  }
}
```

#### Pattern 3: Grandparent Access (Two Levels Up)
```yang
list interface {
  leaf name { type string; }
  container ipv4 {
    leaf address {
      type inet:ipv4-address;
      must '../../name != "loopback0"';  // Go up 2 levels to access list key
    }
  }
}
```

#### Pattern 4: Cross-Ancestor Validation
```yang
container bgp {
  leaf local-as { type uint32; }
  list neighbor {
    leaf remote-as { type uint32; }
    must '. != ../../local-as' {  // Compare with grandparent's leaf
      error-message "Remote AS cannot equal local AS";
    }
  }
}
```

#### Pattern 5: Cross-Branch Navigation
```yang
container routing {
  container protocols {
    leaf bgp-enabled { type boolean; }
  }
  container bgp {
    when '../protocols/bgp-enabled = "true"';  // Navigate up, then into sibling
    leaf as-number { type uint32; }
  }
}
```

---

## DevNet Expert Exam Tips

1. **Remember the fundamental difference:**
   - `when` = existence control
   - `must` = value validation

2. **XPath navigation:**
   - `../` moves up one level
   - Use `.` to reference current node value
   - Understand context node for different statement types

3. **Error handling:**
   - `when = false`: No error, node just doesn't exist
   - `must = false`: RPC error with error-message returned to client

4. **Validation tools:**
   - `pyang` checks basic YANG syntax
   - `yanglint` validates XPath expressions and constraints
   - Test with real NETCONF/RESTCONF payloads

5. **Common patterns in Cisco YANG models:**
   - Feature flags with when statements
   - Protocol enable/disable with conditional containers
   - Cross-validation with must statements

---

## References

- RFC 7950: The YANG 1.1 Data Modeling Language
  - Section 7.21.5: The "when" Statement
  - Section 7.5.4: The "must" Statement
- XPath 1.0 Specification (for expression syntax)