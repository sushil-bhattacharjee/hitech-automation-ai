# BGP Process - Cisco IOS-XE YANG Model

**Module:** Cisco-IOS-XE-bgp  
**Namespace:** `http://cisco.com/ns/yang/Cisco-IOS-XE-native`  
**Path:** `/native/router/bgp`  
**Device Ready:** ✅ Direct deployment to Cisco IOS-XE routers

---

## 📊 YANG Tree Structure

```
module: Cisco-IOS-XE-bgp
  +--rw native
     +--rw router
        +--rw bgp* [id]
           +--rw id                   uint32
           +--rw bgp
           |  +--rw log-neighbor-changes?   boolean
           |  +--rw router-id
           |     +--rw ip-id?   string
           +--rw neighbor* [id]
           |  +--rw id             string
           |  +--rw remote-as      uint32
           |  +--rw description?   string
           |  +--rw update-source
           |     +--rw interface
           |        +--rw Loopback?          uint32
           |        +--rw GigabitEthernet?   string
           +--rw address-family
              +--rw no-vrf
                 +--rw ipv4* [af-name]
                    +--rw af-name        enumeration
                    +--rw ipv4-unicast
                       +--rw neighbor* [id]
                       |  +--rw id                      leafref
                       |  +--rw activate*               empty
                       |  +--rw soft-reconfiguration?   enumeration
                       |  +--rw maximum-prefix
                       |  |  +--rw max-prefix-no?   uint32
                       |  +--rw prefix-list* [inout]
                       |  |  +--rw inout               enumeration
                       |  |  +--rw prefix-list-name?   string
                       |  +--rw route-map* [inout]
                       |     +--rw inout             enumeration
                       |     +--rw route-map-name?   string
                       +--rw network
                       |  +--rw with-mask* [number]
                       |  |  +--rw number    string
                       |  |  +--rw mask?     string
                       |  +--rw no-mask* [number]
                       |     +--rw number    string
                       +--rw redistribute
                          +--rw ospf* [id]
                          |  +--rw id        uint16
                          |  +--rw non-vrf
                          |     +--rw metric?      uint32
                          |     +--rw route-map?   string
                          +--rw static!
                             +--rw ip
                                +--rw metric?      uint32
                                +--rw route-map?   string
```

**Legend:**
- `+--rw` = read-write node
- `?` = optional node
- `!` = presence container
- `*` = list (multiple instances)
- `[key]` = list key

---

## 📋 Node Types and Data Types Summary

| Node Type | Count | Examples |
|-----------|-------|----------|
| **container** | 10 | `bgp`, `router-id`, `update-source`, `interface`, `address-family`, `no-vrf`, `ipv4-unicast`, `network`, `redistribute`, `ip` |
| **list** | 7 | `bgp`, `neighbor` (global), `ipv4`, `neighbor` (af), `prefix-list`, `route-map`, `ospf`, `with-mask`, `no-mask` |
| **leaf** | 15 | `id`, `log-neighbor-changes`, `ip-id`, `remote-as`, `description`, `Loopback`, `GigabitEthernet`, `af-name`, `soft-reconfiguration`, `max-prefix-no`, `inout`, `prefix-list-name`, `route-map-name`, `number`, `mask`, `metric` |
| **leaf-list** | 1 | `activate` |
| **grouping** | 2 | `update-source-grouping`, `redistribute-params` |

### Data Types Used

| Data Type | Usage | Examples |
|-----------|-------|----------|
| **uint32** | AS numbers, process IDs, metrics, prefix counts | `id`, `remote-as`, `max-prefix-no`, `metric`, `Loopback` |
| **uint16** | OSPF process IDs | `ospf/id` |
| **string** | IP addresses, names, descriptions | `neighbor/id`, `ip-id`, `description`, `prefix-list-name`, `route-map-name`, `GigabitEthernet` |
| **boolean** | Flags | `log-neighbor-changes` |
| **enumeration** | Limited choice sets | `af-name` (unicast/multicast), `inout` (in/out), `soft-reconfiguration` (inbound/outbound) |
| **empty** | Presence indicators | `activate` |
| **leafref** | References to other nodes | `address-family neighbor/id` → `global neighbor/id` |

### Special YANG Statements

| Statement | Purpose | Example |
|-----------|---------|---------|
| **when** | Conditional existence | `ipv4-unicast` exists only when `af-name='unicast'` |
| **leafref** | Data integrity constraint | AF neighbor must reference global neighbor |
| **presence** | Empty container has meaning | `static` container enables static redistribution |
| **uses** | Include grouping | `uses update-source-grouping` |
| **key** | Unique identifier | `neighbor[id]`, `ospf[id]` |
| **mandatory** | Required field | `bgp/id`, `neighbor/id`, `neighbor/remote-as` |

---

## 🔧 Validation Commands

### Using yanglint

```bash
# Validate YANG module syntax
yanglint Cisco-IOS-XE-bgp.yang

# Validate XML against YANG (data type)
yanglint -t data Cisco-IOS-XE-bgp.yang bgp-xml-validation.xml

# Validate XML against YANG (config type)
yanglint -t config Cisco-IOS-XE-bgp.yang bgp-xml-config.xml

# Validate JSON against YANG
yanglint -t data -f json Cisco-IOS-XE-bgp.yang bgp-json-config.json
```

### Using yang2dsdl

```bash
# Generate validation schemas and validate XML
yang2dsdl -v bgp-xml-validation.xml Cisco-IOS-XE-bgp.yang

# This creates:
# - Cisco-IOS-XE-bgp-gdefs-config.rng
# - Cisco-IOS-XE-bgp-rng.xml
# - Cisco-IOS-XE-bgp.sch
# - Cisco-IOS-XE-bgp.dsrl
```

### Using pyang

```bash
# Validate YANG syntax
pyang --strict Cisco-IOS-XE-bgp.yang

# Generate full tree view
pyang -f tree Cisco-IOS-XE-bgp.yang

# Generate tree view starting from BGP (no augmentation shown)
pyang -f tree --tree-path /native/router/bgp Cisco-IOS-XE-bgp.yang

# Generate HTML documentation
pyang -f jstree Cisco-IOS-XE-bgp.yang -o bgp-model.html
```

### RESTCONF URIs

```bash
# Base path for BGP configuration (unified namespace)
/restconf/data/Cisco-IOS-XE-native:native/router/bgp=65001

# Get specific neighbor
/restconf/data/Cisco-IOS-XE-native:native/router/bgp=65001/neighbor=192.168.1.2

# Get address-family configuration
/restconf/data/Cisco-IOS-XE-native:native/router/bgp=65001/address-family

# Get specific neighbor in address-family
/restconf/data/Cisco-IOS-XE-native:native/router/bgp=65001/address-family/no-vrf/ipv4=unicast/ipv4-unicast/neighbor=192.168.1.3
```

---

## 📁 File Contents

<details>
<summary><b>Cisco-IOS-XE-bgp.yang</b> - YANG Model Definition (Unified Native Structure)</summary>

```yang
module Cisco-IOS-XE-bgp {
  namespace "http://cisco.com/ns/yang/Cisco-IOS-XE-native";
  prefix ios;

  organization "Cisco Systems, Inc.";
  contact "Cisco Systems, Inc. Customer Service";
  
  description
    "Cisco XE Native Border Gateway Protocol (BGP) Yang model.
     Copyright (c) 2024 by Cisco Systems, Inc.
     All rights reserved.";

  revision 2024-12-17 {
    description "BGP configuration model for DevNet Expert";
  }

  // Grouping for update-source interface
  grouping update-source-grouping {
    container update-source {
      description "Source of routing updates";
      container interface {
        description "Interface for update source";
        leaf Loopback {
          type uint32;
          description "Loopback interface number";
        }
        leaf GigabitEthernet {
          type string;
          description "GigabitEthernet interface";
        }
      }
    }
  }

  // Grouping for redistribution parameters
  grouping redistribute-params-grouping {
    leaf metric {
      type uint32;
      description "Metric for redistributed routes";
    }
    leaf route-map {
      type string;
      description "Route map reference";
    }
  }

  // Root container
  container native {
    description "Native configuration commands";
    
    container router {
      description "Enable a routing process";
      
      list bgp {
        key "id";
        description "BGP configuration commands";
        
        leaf id {
          type uint32;
          description "Autonomous system number";
        }
        
        container bgp {
          description "BGP specific commands";
          
          leaf log-neighbor-changes {
            type boolean;
            default false;
            description "Log neighbor up/down and reset reason";
          }
          
          container router-id {
            description "Override configured router identifier";
            leaf ip-id {
              type string;
              description "Manually configured router identifier";
            }
          }
        }
        
        // BGP neighbor configuration
        list neighbor {
          key "id";
          description "Specify a neighbor router";
          
          leaf id {
            type string;
            description "Neighbor address";
          }
          
          leaf remote-as {
            type uint32;
            description "Specify AS number of BGP neighbor";
          }
          
          leaf description {
            type string;
            description "Neighbor specific description";
          }
          
          uses update-source-grouping;
        }
        
        // Address family configuration
        container address-family {
          description "Enter Address Family command mode";
          
          container no-vrf {
            description "Address family configuration for non-VRF";
            
            list ipv4 {
              key "af-name";
              description "Address family";
              
              leaf af-name {
                type enumeration {
                  enum unicast {
                    description "Address Family modifier";
                  }
                  enum multicast {
                    description "Address Family modifier";
                  }
                }
                description "Address family name";
              }
              
              container ipv4-unicast {
                when "../af-name = 'unicast'";
                description "Address Family configuration";
                
                // Per-neighbor address-family configuration
                list neighbor {
                  key "id";
                  description "Specify a neighbor router";
                  
                  leaf id {
                    type leafref {
                      path "../../../../../../neighbor/id";
                    }
                    description "Neighbor address - must reference global neighbor";
                  }
                  
                  leaf-list activate {
                    type empty;
                    description "Enable the Address Family for this Neighbor";
                  }
                  
                  leaf soft-reconfiguration {
                    type enumeration {
                      enum inbound {
                        description "Allow inbound soft reconfiguration";
                      }
                      enum outbound {
                        description "Allow outbound soft reconfiguration";
                      }
                    }
                    description "Per neighbor soft reconfiguration";
                  }
                  
                  container maximum-prefix {
                    description "Maximum number of prefix accept from this peer";
                    leaf max-prefix-no {
                      type uint32;
                      description "Maximum prefix number";
                    }
                  }
                  
                  list prefix-list {
                    key "inout";
                    description "Filter updates to/from this neighbor";
                    
                    leaf inout {
                      type enumeration {
                        enum in {
                          description "Filter incoming updates";
                        }
                        enum out {
                          description "Filter outgoing updates";
                        }
                      }
                      description "Filter direction";
                    }
                    
                    leaf prefix-list-name {
                      type string;
                      description "Name of a prefix list";
                    }
                  }
                  
                  list route-map {
                    key "inout";
                    description "Apply route map to neighbor";
                    
                    leaf inout {
                      type enumeration {
                        enum in {
                          description "Apply to incoming routes";
                        }
                        enum out {
                          description "Apply to outbound routes";
                        }
                      }
                      description "Route-map direction";
                    }
                    
                    leaf route-map-name {
                      type string;
                      description "Name of route map";
                    }
                  }
                }
                
                // Network advertisement configuration
                container network {
                  description "Specify a network to announce via BGP";
                  
                  list with-mask {
                    key "number";
                    description "Network with mask";
                    
                    leaf number {
                      type string;
                      description "Network number";
                    }
                    
                    leaf mask {
                      type string;
                      description "Network mask";
                    }
                  }
                  
                  list no-mask {
                    key "number";
                    description "Network without mask";
                    
                    leaf number {
                      type string;
                      description "Network address";
                    }
                  }
                }
                
                // Route redistribution configuration
                container redistribute {
                  description "Redistribute information from another routing protocol";
                  
                  list ospf {
                    key "id";
                    description "Open Shortest Path First (OSPF)";
                    
                    leaf id {
                      type uint16;
                      description "Process ID";
                    }
                    
                    container non-vrf {
                      description "Non-VRF OSPF redistribution";
                      uses redistribute-params-grouping;
                    }
                  }
                  
                  container static {
                    presence "Enable static route redistribution";
                    description "Static routes";
                    
                    container ip {
                      description "IP static route redistribution";
                      uses redistribute-params-grouping;
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

**Key Features:**
- Unified namespace: `http://cisco.com/ns/yang/Cisco-IOS-XE-native`
- Direct structure: `/native/router/bgp` (no augmentation)
- Single module design
- Device-ready for NETCONF/RESTCONF deployment

</details>

<details>
<summary><b>bgp-xml-validation.xml</b> - XML with &lt;data&gt; wrapper (for yang2dsdl)</summary>

```xml
<?xml version="1.0" encoding="UTF-8"?>
<data xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <router>
      <bgp>
        <id>65001</id>
        <bgp>
          <log-neighbor-changes>true</log-neighbor-changes>
          <router-id>
            <ip-id>10.0.0.71</ip-id>
          </router-id>
        </bgp>
        
        <!-- Global BGP Neighbors -->
        <neighbor>
          <id>10.44.10.2</id>
          <remote-as>65002</remote-as>
          <description>cat8Kv72</description>
          <update-source>
            <interface>
              <Loopback>404</Loopback>
            </interface>
          </update-source>
        </neighbor>
        
        <neighbor>
          <id>192.168.1.2</id>
          <remote-as>65002</remote-as>
          <description>cat8Kv72_thru_nx9K73</description>
        </neighbor>
        
        <neighbor>
          <id>192.168.1.3</id>
          <remote-as>65003</remote-as>
          <description>nx9Kv73</description>
        </neighbor>
        
        <!-- Address Family Configuration -->
        <address-family>
          <no-vrf>
            <ipv4>
              <af-name>unicast</af-name>
              <ipv4-unicast>
                <neighbor>
                  <id>10.44.10.2</id>
                  <activate/>
                  <soft-reconfiguration>inbound</soft-reconfiguration>
                </neighbor>
                
                <neighbor>
                  <id>192.168.1.2</id>
                  <activate/>
                  <maximum-prefix>
                    <max-prefix-no>100</max-prefix-no>
                  </maximum-prefix>
                  <prefix-list>
                    <inout>in</inout>
                    <prefix-list-name>LIMIT</prefix-list-name>
                  </prefix-list>
                </neighbor>
                
                <neighbor>
                  <id>192.168.1.3</id>
                  <activate/>
                  <maximum-prefix>
                    <max-prefix-no>100</max-prefix-no>
                  </maximum-prefix>
                  <route-map>
                    <inout>in</inout>
                    <route-map-name>cat71-nx73</route-map-name>
                  </route-map>
                </neighbor>
                
                <network>
                  <with-mask>
                    <number>10.10.10.0</number>
                    <mask>255.255.255.0</mask>
                  </with-mask>
                  <no-mask>
                    <number>172.16.0.0</number>
                  </no-mask>
                </network>
                
                <redistribute>
                  <ospf>
                    <id>1</id>
                    <non-vrf>
                      <metric>100</metric>
                    </non-vrf>
                  </ospf>
                  <ospf>
                    <id>111</id>
                    <non-vrf>
                      <metric>100</metric>
                    </non-vrf>
                  </ospf>
                  <static>
                    <ip>
                      <metric>1</metric>
                    </ip>
                  </static>
                </redistribute>
              </ipv4-unicast>
            </ipv4>
          </no-vrf>
        </address-family>
      </bgp>
    </router>
  </native>
</data>
```

**Usage:**
```bash
yang2dsdl -v bgp-xml-validation.xml Cisco-IOS-XE-bgp.yang
```

**Key Points:**
- Single namespace: `xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"`
- Path: `<native><router><bgp>`
- No namespace prefixes needed inside BGP elements

</details>

<details>
<summary><b>bgp-xml-config.xml</b> - XML with &lt;config&gt; wrapper (for device deployment)</summary>

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <router>
      <bgp>
        <id>65001</id>
        <bgp>
          <log-neighbor-changes>true</log-neighbor-changes>
          <router-id>
            <ip-id>10.0.0.71</ip-id>
          </router-id>
        </bgp>
        
        <neighbor>
          <id>10.44.10.2</id>
          <remote-as>65002</remote-as>
          <description>cat8Kv72</description>
          <update-source>
            <interface>
              <Loopback>404</Loopback>
            </interface>
          </update-source>
        </neighbor>
        
        <neighbor>
          <id>192.168.1.2</id>
          <remote-as>65002</remote-as>
          <description>cat8Kv72_thru_nx9K73</description>
        </neighbor>
        
        <neighbor>
          <id>192.168.1.3</id>
          <remote-as>65003</remote-as>
          <description>nx9Kv73</description>
        </neighbor>
        
        <address-family>
          <no-vrf>
            <ipv4>
              <af-name>unicast</af-name>
              <ipv4-unicast>
                <neighbor>
                  <id>10.44.10.2</id>
                  <activate/>
                  <soft-reconfiguration>inbound</soft-reconfiguration>
                </neighbor>
                
                <neighbor>
                  <id>192.168.1.2</id>
                  <activate/>
                  <maximum-prefix>
                    <max-prefix-no>100</max-prefix-no>
                  </maximum-prefix>
                  <prefix-list>
                    <inout>in</inout>
                    <prefix-list-name>LIMIT</prefix-list-name>
                  </prefix-list>
                </neighbor>
                
                <neighbor>
                  <id>192.168.1.3</id>
                  <activate/>
                  <maximum-prefix>
                    <max-prefix-no>100</max-prefix-no>
                  </maximum-prefix>
                  <route-map>
                    <inout>in</inout>
                    <route-map-name>cat71-nx73</route-map-name>
                  </route-map>
                </neighbor>
                
                <network>
                  <with-mask>
                    <number>10.10.10.0</number>
                    <mask>255.255.255.0</mask>
                  </with-mask>
                  <no-mask>
                    <number>172.16.0.0</number>
                  </no-mask>
                </network>
                
                <redistribute>
                  <ospf>
                    <id>1</id>
                    <non-vrf>
                      <metric>100</metric>
                    </non-vrf>
                  </ospf>
                  <ospf>
                    <id>111</id>
                    <non-vrf>
                      <metric>100</metric>
                    </non-vrf>
                  </ospf>
                  <static>
                    <ip>
                      <metric>1</metric>
                    </ip>
                  </static>
                </redistribute>
              </ipv4-unicast>
            </ipv4>
          </no-vrf>
        </address-family>
      </bgp>
    </router>
  </native>
</config>
```

**NETCONF Deployment:**
```python
from ncclient import manager

m = manager.connect(
    host='192.168.1.1',
    port=830,
    username='admin',
    password='cisco',
    hostkey_verify=False
)

with open('bgp-xml-config.xml') as f:
    config = f.read()

m.edit_config(target='running', config=config)
m.close_session()
```

**Key Points:**
- Single namespace throughout
- No namespace prefixes on child elements
- Direct path: `native/router/bgp`

</details>

<details>
<summary><b>bgp-json-config.json</b> - JSON config (for RESTCONF)</summary>

```json
{
  "Cisco-IOS-XE-native:native": {
    "router": {
      "bgp": [
        {
          "id": 65001,
          "bgp": {
            "log-neighbor-changes": true,
            "router-id": {
              "ip-id": "10.0.0.71"
            }
          },
          "neighbor": [
            {
              "id": "10.44.10.2",
              "remote-as": 65002,
              "description": "cat8Kv72",
              "update-source": {
                "interface": {
                  "Loopback": 404
                }
              }
            },
            {
              "id": "192.168.1.2",
              "remote-as": 65002,
              "description": "cat8Kv72_thru_nx9K73"
            },
            {
              "id": "192.168.1.3",
              "remote-as": 65003,
              "description": "nx9Kv73"
            }
          ],
          "address-family": {
            "no-vrf": {
              "ipv4": [
                {
                  "af-name": "unicast",
                  "ipv4-unicast": {
                    "neighbor": [
                      {
                        "id": "10.44.10.2",
                        "activate": [null],
                        "soft-reconfiguration": "inbound"
                      },
                      {
                        "id": "192.168.1.2",
                        "activate": [null],
                        "maximum-prefix": {
                          "max-prefix-no": 100
                        },
                        "prefix-list": [
                          {
                            "inout": "in",
                            "prefix-list-name": "LIMIT"
                          }
                        ]
                      },
                      {
                        "id": "192.168.1.3",
                        "activate": [null],
                        "maximum-prefix": {
                          "max-prefix-no": 100
                        },
                        "route-map": [
                          {
                            "inout": "in",
                            "route-map-name": "cat71-nx73"
                          }
                        ]
                      }
                    ],
                    "network": {
                      "with-mask": [
                        {
                          "number": "10.10.10.0",
                          "mask": "255.255.255.0"
                        }
                      ],
                      "no-mask": [
                        {
                          "number": "172.16.0.0"
                        }
                      ]
                    },
                    "redistribute": {
                      "ospf": [
                        {
                          "id": 1,
                          "non-vrf": {
                            "metric": 100
                          }
                        },
                        {
                          "id": 111,
                          "non-vrf": {
                            "metric": 100
                          }
                        }
                      ],
                      "static": {
                        "ip": {
                          "metric": 1
                        }
                      }
                    }
                  }
                }
              ]
            }
          }
        }
      ]
    }
  }
}
```

**RESTCONF Deployment:**
```bash
curl -X PUT \
  https://192.168.1.1/restconf/data/Cisco-IOS-XE-native:native/router/bgp=65001 \
  -H 'Content-Type: application/yang-data+json' \
  -H 'Accept: application/yang-data+json' \
  -u admin:cisco \
  --data @bgp-json-config.json
```

**Key Points:**
- Single namespace prefix: `Cisco-IOS-XE-native`
- No additional prefixes for `bgp` or child elements
- Simplified structure: `native/router/bgp`

</details>

<details>
<summary><b>soth_nei_cat72.yml</b> - Neighbor 192.168.1.2 YAML config (with prefix-list)</summary>

```yaml
---
# BGP Neighbor Configuration: cat8Kv72_thru_nx9K73 (192.168.1.2)
# Neighbor with prefix-list

bgp:
  - id: 65001
    
    # Global neighbor definition
    neighbor:
      - id: "192.168.1.2"
        remote-as: 65002
        description: "cat8Kv72_thru_nx9K73"
    
    # Address-family configuration
    address-family:
      no-vrf:
        ipv4:
          - af-name: "unicast"
            ipv4-unicast:
              neighbor:
                - id: "192.168.1.2"
                  activate:
                    - null
                  maximum-prefix:
                    max-prefix-no: 100
                  prefix-list:
                    - inout: "in"
                      prefix-list-name: "LIMIT"
```

**CLI Equivalent:**
```
router bgp 65001
 neighbor 192.168.1.2 remote-as 65002
 neighbor 192.168.1.2 description cat8Kv72_thru_nx9K73
 !
 address-family ipv4
  neighbor 192.168.1.2 activate
  neighbor 192.168.1.2 prefix-list LIMIT in
  neighbor 192.168.1.2 maximum-prefix 100
 exit-address-family
```

</details>

<details>
<summary><b>soth_nei_nx73.yml</b> - Neighbor 192.168.1.3 YAML config (with route-map)</summary>

```yaml
---
# BGP Neighbor Configuration: nx9Kv73 (192.168.1.3)
# Neighbor with route-map policy

bgp:
  - id: 65001
    
    # Global neighbor definition
    neighbor:
      - id: "192.168.1.3"
        remote-as: 65003
        description: "nx9Kv73"
    
    # Address-family configuration
    address-family:
      no-vrf:
        ipv4:
          - af-name: "unicast"
            ipv4-unicast:
              neighbor:
                - id: "192.168.1.3"
                  activate:
                    - null
                  maximum-prefix:
                    max-prefix-no: 100
                  route-map:
                    - inout: "in"
                      route-map-name: "cat71-nx73"
```

**CLI Equivalent:**
```
router bgp 65001
 neighbor 192.168.1.3 remote-as 65003
 neighbor 192.168.1.3 description nx9Kv73
 !
 address-family ipv4
  neighbor 192.168.1.3 activate
  neighbor 192.168.1.3 route-map cat71-nx73 in
  neighbor 192.168.1.3 maximum-prefix 100
 exit-address-family
```

</details>

<details>
<summary><b>cat8Kv71_soth_bgp.yml</b> - Complete BGP Source of Truth for cat8Kv71</summary>

```yaml
---
# Source of Truth: cat8Kv71 BGP Configuration
# Device: cat8Kv71
# AS Number: 65001

BGP:
  ASN: 65001
  ROUTER_ID: 10.0.0.71
  LOG_NEIGHBOR_CHANGES: true

  NEIGHBORS:
    - IP: 10.44.10.2
      REMOTE_AS: 65002
      DESCRIPTION: cat8Kv72
      UPDATE_SOURCE: Loopback404
      SOFT_RECONFIGURATION: inbound
    - IP: 192.168.1.2
      REMOTE_AS: 65002
      DESCRIPTION: cat8Kv72_thru_nx9K73
      PREFIX_LIST_IN: LIMIT
      MAX_PREFIX: 100
    - IP: 192.168.1.3
      REMOTE_AS: 65003
      DESCRIPTION: nx9Kv73
      ROUTE_MAP_IN: cat71-nx73
      MAX_PREFIX: 100

  ADDRESS_FAMILY:
    ipv4:
      NETWORKS:
        - PREFIX: 10.10.10.0
          MASK: 255.255.255.0
        - PREFIX: 172.16.0.0
          MASK: 255.255.0.0

  # Redistribute OSPF processes
  REDISTRIBUTE_OSPF:
    - PROCESS_ID: 1
      METRIC: 100
    - PROCESS_ID: 111
      METRIC: 100

  # Redistribute static routes
  REDISTRIBUTE_STATIC:
    METRIC: 1

  # Route-map configuration
  ROUTE_MAPS:
    - NAME: cat71-nx73
      DESCRIPTION: Route-map for neighbor 192.168.1.3
    - NAME: LIMIT
      DESCRIPTION: Prefix-list based route-map

  # Prefix-list configuration
  PREFIX_LISTS:
    - NAME: LIMIT
      DESCRIPTION: Limit prefixes from neighbors
```

**CLI Equivalent:**
```
router bgp 65001
 bgp router-id 10.0.0.71
 bgp log-neighbor-changes
 neighbor 10.44.10.2 remote-as 65002
 neighbor 10.44.10.2 description cat8Kv72
 neighbor 10.44.10.2 update-source Loopback404
 neighbor 192.168.1.2 remote-as 65002
 neighbor 192.168.1.2 description cat8Kv72_thru_nx9K73
 neighbor 192.168.1.3 remote-as 65003
 neighbor 192.168.1.3 description nx9Kv73
 !
 address-family ipv4
  network 10.10.10.0 mask 255.255.255.0
  network 172.16.0.0
  redistribute static metric 1
  redistribute ospf 111 metric 100
  redistribute ospf 1 metric 100
  neighbor 10.44.10.2 activate
  neighbor 10.44.10.2 soft-reconfiguration inbound
  neighbor 192.168.1.2 activate
  neighbor 192.168.1.2 prefix-list LIMIT in
  neighbor 192.168.1.2 maximum-prefix 100
  neighbor 192.168.1.3 activate
  neighbor 192.168.1.3 route-map cat71-nx73 in
  neighbor 192.168.1.3 maximum-prefix 100
 exit-address-family
```

</details>

<details>
<summary><b>cat8Kv72_soth_bgp.yml</b> - Complete BGP Source of Truth for cat8Kv72</summary>

```yaml
---
# Source of Truth: cat8Kv72 BGP Configuration
# Device: cat8Kv72
# AS Number: 65002

BGP:
  ASN: 65002
  ROUTER_ID: 10.0.0.72
  LOG_NEIGHBOR_CHANGES: true

  NEIGHBORS:
    - IP: 10.44.10.1
      REMOTE_AS: 65001
      UPDATE_SOURCE: Loopback404
      SOFT_RECONFIGURATION: inbound
    - IP: 192.168.1.1
      REMOTE_AS: 65001
      DESCRIPTION: BGP Peer to AS 65001
      PREFIX_LIST_IN: LIMIT
      MAX_PREFIX: 100

  ADDRESS_FAMILY:
    ipv4:
      NETWORKS:
        - PREFIX: 192.168.1.0
          MASK: 255.255.255.0

  # Redistribute OSPF processes
  REDISTRIBUTE_OSPF:
    - PROCESS_ID: 1
      METRIC: 100
    - PROCESS_ID: 10
      METRIC: 100
    - PROCESS_ID: 111
      METRIC: 100

  # Prefix-list configuration
  PREFIX_LISTS:
    - NAME: LIMIT
      DESCRIPTION: Limit prefixes from neighbors
```

**CLI Equivalent:**
```
router bgp 65002
 bgp router-id 10.0.0.72
 bgp log-neighbor-changes
 neighbor 10.44.10.1 remote-as 65001
 neighbor 10.44.10.1 update-source Loopback404
 neighbor 192.168.1.1 remote-as 65001
 neighbor 192.168.1.1 description BGP Peer to AS 65001
 !
 address-family ipv4
  network 192.168.1.0
  redistribute ospf 111 metric 100
  redistribute ospf 1 metric 100
  redistribute ospf 10 metric 100
  neighbor 10.44.10.1 activate
  neighbor 10.44.10.1 soft-reconfiguration inbound
  neighbor 192.168.1.1 activate
  neighbor 192.168.1.1 prefix-list LIMIT in
  neighbor 192.168.1.1 maximum-prefix 100
 exit-address-family
```

</details>

<details>
<summary><b>nei_cat71.xml</b> - Neighbor 192.168.1.2 config (with prefix-list)</summary>

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <bgp xmlns="urn:example:bgp">
    <id>65001</id>
    
    <!-- Global neighbor definition -->
    <neighbor>
      <id>192.168.1.2</id>
      <remote-as>65002</remote-as>
      <description>cat8Kv72_thru_nx9K73</description>
    </neighbor>
    
    <!-- Address-family configuration for this neighbor -->
    <address-family>
      <no-vrf>
        <ipv4>
          <af-name>unicast</af-name>
          <ipv4-unicast>
            <neighbor>
              <id>192.168.1.2</id>
              <activate/>
              <maximum-prefix>
                <max-prefix-no>100</max-prefix-no>
              </maximum-prefix>
              <prefix-list>
                <inout>in</inout>
                <prefix-list-name>LIMIT</prefix-list-name>
              </prefix-list>
            </neighbor>
          </ipv4-unicast>
        </ipv4>
      </no-vrf>
    </address-family>
  </bgp>
</config>
```

**CLI Equivalent:**
```
router bgp 65001
 neighbor 192.168.1.2 remote-as 65002
 neighbor 192.168.1.2 description cat8Kv72_thru_nx9K73
 !
 address-family ipv4
  neighbor 192.168.1.2 activate
  neighbor 192.168.1.2 prefix-list LIMIT in
  neighbor 192.168.1.2 maximum-prefix 100
 exit-address-family
```

</details>

<details>
<summary><b>nei_nx73.xml</b> - Neighbor 192.168.1.3 config (with route-map)</summary>

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <bgp xmlns="urn:example:bgp">
    <id>65001</id>
    
    <!-- Global neighbor definition -->
    <neighbor>
      <id>192.168.1.3</id>
      <remote-as>65003</remote-as>
      <description>nx9Kv73</description>
    </neighbor>
    
    <!-- Address-family configuration for this neighbor -->
    <address-family>
      <no-vrf>
        <ipv4>
          <af-name>unicast</af-name>
          <ipv4-unicast>
            <neighbor>
              <id>192.168.1.3</id>
              <activate/>
              <maximum-prefix>
                <max-prefix-no>100</max-prefix-no>
              </maximum-prefix>
              <route-map>
                <inout>in</inout>
                <route-map-name>cat71-nx73</route-map-name>
              </route-map>
            </neighbor>
          </ipv4-unicast>
        </ipv4>
      </no-vrf>
    </address-family>
  </bgp>
</config>
```

**CLI Equivalent:**
```
router bgp 65001
 neighbor 192.168.1.3 remote-as 65003
 neighbor 192.168.1.3 description nx9Kv73
 !
 address-family ipv4
  neighbor 192.168.1.3 activate
  neighbor 192.168.1.3 route-map cat71-nx73 in
  neighbor 192.168.1.3 maximum-prefix 100
 exit-address-family
```

</details>

---

## 🔑 Key Differences: prefix-list vs route-map

### Neighbor 192.168.1.2 (cat71) - Uses prefix-list
```xml
<prefix-list>
  <inout>in</inout>
  <prefix-list-name>LIMIT</prefix-list-name>
</prefix-list>
```
- **Purpose**: Simple IP prefix filtering
- **Use case**: Allow/deny specific networks
- **Configuration**: Prefix-list "LIMIT" must be defined separately

### Neighbor 192.168.1.3 (nx73) - Uses route-map
```xml
<route-map>
  <inout>in</inout>
  <route-map-name>cat71-nx73</route-map-name>
</route-map>
```
- **Purpose**: Advanced policy-based routing
- **Use case**: Modify attributes (AS-PATH, local-pref, communities)
- **Configuration**: Route-map "cat71-nx73" must be defined separately

---

## 📝 CLI to YANG Mapping Reference

| CLI Command | YANG Path |
|-------------|-----------|
| `router bgp 65001` | `/native/router/bgp/id = 65001` |
| `bgp router-id 10.0.0.71` | `/native/router/bgp/bgp/router-id/ip-id` |
| `bgp log-neighbor-changes` | `/native/router/bgp/bgp/log-neighbor-changes = true` |
| `neighbor 192.168.1.2 remote-as 65002` | `/native/router/bgp/neighbor[id='192.168.1.2']/remote-as` |
| `neighbor 192.168.1.2 description ...` | `/native/router/bgp/neighbor/description` |
| `neighbor 10.44.10.2 update-source Loopback404` | `/native/router/bgp/neighbor/update-source/interface/Loopback` |
| `address-family ipv4` | `/native/router/bgp/address-family/no-vrf/ipv4[af-name='unicast']` |
| `neighbor 192.168.1.2 activate` | `/native/router/bgp/.../ipv4-unicast/neighbor/activate` |
| `neighbor 192.168.1.2 prefix-list LIMIT in` | `/native/router/bgp/.../neighbor/prefix-list[inout='in']/prefix-list-name` |
| `neighbor 192.168.1.3 route-map cat71-nx73 in` | `/native/router/bgp/.../neighbor/route-map[inout='in']/route-map-name` |
| `network 10.10.10.0 mask 255.255.255.0` | `/native/router/bgp/.../network/with-mask[number='10.10.10.0']/mask` |
| `redistribute ospf 111 metric 100` | `/native/router/bgp/.../redistribute/ospf[id=111]/non-vrf/metric` |
| `redistribute static metric 1` | `/native/router/bgp/.../redistribute/static/ip/metric` |

---

## 🚀 Quick Start Guide

### 1. Validate the YANG Model
```bash
yanglint bgp-process-v4.yang
# OR
pyang --strict bgp-process-v4.yang
```

### 2. Validate XML Payload
```bash
# Using yanglint
yanglint -t data bgp-process-v4.yang bgp_xml_validation.xml

# Using yang2dsdl
yang2dsdl -v bgp_xml_validation.xml bgp-process-v4.yang
```

### 3. Deploy to Device (NETCONF)
```python
from ncclient import manager

# Connect to device
m = manager.connect(
    host='192.168.1.1',
    port=830,
    username='admin',
    password='cisco',
    hostkey_verify=False
)

# Load config
with open('bgp_xml_config.xml') as f:
    config = f.read()

# Send config
m.edit_config(target='running', config=config)
m.close_session()
```

### 4. Deploy to Device (RESTCONF)
```bash
curl -X PUT \
  https://192.168.1.1/restconf/data/bgp \
  -H 'Content-Type: application/yang-data+json' \
  -H 'Accept: application/yang-data+json' \
  -u admin:cisco \
  --data @bgp_json_config.json
```

---

## 📚 Additional Resources

- **YANG RFC**: [RFC 7950](https://tools.ietf.org/html/rfc7950)
- **NETCONF RFC**: [RFC 6241](https://tools.ietf.org/html/rfc6241)
- **RESTCONF RFC**: [RFC 8040](https://tools.ietf.org/html/rfc8040)
- **Cisco IOS-XE YANG Models**: [GitHub Repository](https://github.com/YangModels/yang/tree/master/vendor/cisco/xe)

---

**Version**: 4.0  
**Last Updated**: 2024-12-17  
**Author**: DevNet Expert Preparation