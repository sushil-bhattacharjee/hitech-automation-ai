# e2-exam-RESTCONF

> **YANG Model Reference**: Two YANG modules mirror the exact Cisco structure:
> 
> | Module | Namespace | Prefix |
> |--------|-----------|--------|
> | `Cisco-IOS-XE-native.yang` | `http://cisco.com/ns/yang/Cisco-IOS-XE-native` | `ios` |
> | `Cisco-IOS-XE-acl.yang` | `http://cisco.com/ns/yang/Cisco-IOS-XE-acl` | `ios-acl` |
> 
> **JSON Payload Prefixes**:
> - Container path: `Cisco-IOS-XE-native:native/ip/access-list`
> - ACL lists: `Cisco-IOS-XE-acl:standard`, `Cisco-IOS-XE-acl:extended`
> 
> **Validation**: `pyang --strict Cisco-IOS-XE-native.yang Cisco-IOS-XE-acl.yang`

---
## ACL CRUD Brief
> ##### **GET can operate uri with list woKEY/list wKEY/container
> ##### **POST only container in uri and list with new key in the payload
> ##### **PUT uri and payload must be same, 201 for new resource and 204 if replaced
> ##### **PATCH uri and payload must be same, 204 for new or replaced
> ##### **DELETE can be container or list must be with key
---
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

### Prefix to JSON Mapping

| YANG Tree Prefix | JSON Payload Prefix |
|------------------|---------------------|
| `native` | `Cisco-IOS-XE-native:native` |
| `ios-acl:standard` | `Cisco-IOS-XE-acl:standard` |
| `ios-acl:extended` | `Cisco-IOS-XE-acl:extended` |

For IOSXE Cisco Catalyst 8000V: 17.5, there is a bit of limitations for POST/PUT.
Cisco Catalyst 8000V: 17.5 is mandated for DevnetExpert Exam. Not any earlier or later version.

## Current Config:

### TEST-1: GET: list in uri without key
```bash
curl -i -k -X GET 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ=='
```
<details>
<summary>CLICK TO CHECK RESULT</summary>

RESULT : GET: It can work for list with or without key and container too in the uri
```json
{
    "Cisco-IOS-XE-acl:extended": [
        {
            "name": "challenge-207-pod-10",
            "access-list-seq-rule": [
                {
                    "sequence": "10",
                    "ace-rule": {
                        "action": "permit",
                        "protocol": "tcp",
                        "any": [
                            null
                        ],
                        "src-gt": 100,
                        "dest-ipv4-address": "203.36.36.32",
                        "dest-mask": "0.0.0.15",
                        "dst-eq": 636
                    }
                },
                {
                    "sequence": "20",
                    "ace-rule": {
                        "action": "deny",
                        "protocol": "ip",
                        "host-address": "198.51.100.6",
                        "dst-any": [
                            null
                        ]
                    }
                }
            ]
        }
    ]
}
```
</details>

### TEST-2: POST: uri and payload contain same container



```bash
curl -i -k -X POST 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "Cisco-IOS-XE-native:access-list": {
        "Cisco-IOS-XE-acl:standard": [
            {
                "name": "Pod10_Task043",
                "access-list-seq-rule": [
                    {
                        "sequence": "5",
                        "permit": {
                            "std-ace": {
                                "host-address": "203.0.113.2"
                            }
                        }
                    }
                ]
            }
        ]
    }
}'
```

<details>
<summary>CLICK TO CHECK RESULT</summary>

### RESULT: POST: ❌ FAILED - Payload Contains Parent Container Name
```json
{
  "ietf-restconf:errors": {
    "error": [
      {
        "error-type": "application",
        "error-tag": "malformed-message",
        "error-path": "/Cisco-IOS-XE-native:native/ip/access-list",
        "error-message": "unknown element: access-list in /ios:native/ios:ip/ios:access-list/ios:access-list"
      }
    ]
  }
}
```
**RFC 8040 Violation:** The message-body MUST contain exactly one instance of the **child resource** to create within the parent. Here, the payload incorrectly includes `"Cisco-IOS-XE-native:access-list"` which is the **parent container** (target URI), not the child resource.

**Rule:** POST payload should contain only the **child element** (e.g., `Cisco-IOS-XE-acl:standard`), not the parent container name.

</details>

### TEST-3: POST: container in uri with children container in the payload which is existing
```bash
curl -i -k -X POST 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "Cisco-IOS-XE-native:access-list": {
        "Cisco-IOS-XE-acl:standard": [
            {
                "name": "Pod10_Task043",
                "access-list-seq-rule": [
                    {
                        "sequence": "5",
                        "permit": {
                            "std-ace": {
                                "host-address": "203.0.113.2"
                            }
                        }
                    }
                ]
            }
        ]
    }
}'
```
<details>
<summary>CLICK HERE TO DISPLAY RESULT</summary>

### RESULT: ❌ FAILED - Resource Already Exists (409 Conflict)
```json
{
  "ietf-restconf:errors": {
    "error": [
      {
        "error-type": "application",
        "error-tag": "data-exists",
        "error-path": "/Cisco-IOS-XE-native:native/ip",
        "error-message": "object already exists: /ios:native/ios:ip/ios:access-list"
      }
    ]
  }
}
```
---
**RFC 8040 Section 4.4:** *"If the data resource already exists, then the POST request MUST fail and a '409 Conflict' status-line MUST be returned. The error-tag value 'resource-denied' is used in this case."*

**Explanation:** POST to `/ip` with payload `access-list` attempts to create the `access-list` container. Since `access-list` already exists (contains other ACLs), the server returns `409 Conflict` with error-tag `data-exists`.

**Solution:** Use PATCH to merge new ACL into existing container, or use PUT to replace specific ACL.
---

</details>


### TEST-4: POST:container in uri and new child list in payload

```bash
curl -i -k -X POST 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list' \
    --header 'Accept: application/yang-data+json' \
    --header 'Content-Type: application/yang-data+json' \
    --header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
    --data '{
    "Cisco-IOS-XE-acl:extended": [
        {
            "name": "challenge-207-pod-10",
            "access-list-seq-rule": [
                {
                    "sequence": "10",
                    "ace-rule": {
                        "action": "permit",
                        "protocol": "tcp",
                        "any": [
                            null
                        ],
                        "src-gt": 100,
                        "dest-ipv4-address": "203.36.36.32",
                        "dest-mask": "0.0.0.15",
                        "dst-eq": 636
                    }
                },
                {
                    "sequence": "20",
                    "ace-rule": {
                        "action": "deny",
                        "protocol": "ip",
                        "host-address": "198.51.100.6",
                        "dst-any": [
                            null
                        ]
                    }
                }
            ]
        }
    ]
}'
```
<details>
<summary>CLICK HERE TO DISPLAY RESULT</summary>

#### RESUTL POST: ✅ PASSED - Create When Container is Empty

**RFC 8040 Section 4.4:** POST succeeds when target parent has no existing data for the child resource being created. All existing ACLs were removed first, allowing POST to create new ACL.
</details>


### TEST-5: POST: list and existing list in payload

```bash
curl -i -k -X POST 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "Cisco-IOS-XE-acl:extended": [
        {
            "name": "exam2-netconf-create-16",
            "access-list-seq-rule": [
                {
                    "sequence": "16",
                    "ace-rule": {
                        "action": "permit",
                        "protocol": "tcp",
                        "host-address": "198.51.100.16",
                        "dst-host-address": "203.0.113.16"

                    }

                }

            ]

        }

    ]

}'
```
<details>
<summary>CLICK HERE TO DISPLAY RESULT</summary>

#### RESULT POST: ❌ FAILED - Cannot POST to Existing Container (409 Conflict)
```json
{
  "ietf-restconf:errors": {
    "error": [
      {
        "error-type": "application",
        "error-tag": "malformed-message",
        "error-path": "/Cisco-IOS-XE-native:native/ip/access-list/Cisco-IOS-XE-acl:extended",
        "error-message": "POST on list must be on list element"
      }
    ]
  }
}
```

**RFC 8040 Section 4.4:** POST creates a child resource within the parent. If the target container already has data, POST fails because it cannot create a resource that would conflict with existing data.

**Explanation:** POST to `/access-list` when other ACLs already exist in the container fails with `data-exists`. The server interprets this as attempting to create the entire `extended` list which conflicts with existing data.

**IOS-XE 17.5 Behavior:** Returns error-tag `data-exists` instead of standard `resource-denied`.


</details>

### TEST-6: POST: list in uri and key in payload

```bash
curl -i -k -X POST 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "name": "exam2-netconf-create-16",
    "access-list-seq-rule": [
        {
            "sequence": "16",
            "ace-rule": {
                "action": "permit",
                "protocol": "tcp",
                "host-address": "198.51.100.16",
                "dst-host-address": "203.0.113.16"
            }
        }
    ]
}'
```
<details>
<summary>CLICK HERE TO DISPLAY RESULT</summary>

#### RESULT 
```json
{
  "ietf-restconf:errors": {
    "error": [
      {
        "error-type": "application",
        "error-tag": "malformed-message",
        "error-path": "/Cisco-IOS-XE-native:native/ip/access-list/Cisco-IOS-XE-acl:extended",
        "error-message": "POST on list must be on list element"
      }
    ]
  }
}
```
POST: ❌ FAILED - Missing List Wrapper in Payload (Malformed Message)

**RFC 8040 Section 4.4:** *"The message-body MUST contain exactly one instance of the expected data resource. The data model for the child tree is the subtree, as defined by YANG for the child resource."*

**Explanation:** When POST target is a list (`/extended`), the payload must include the list wrapper `"Cisco-IOS-XE-acl:extended": [...]`. Providing only the list element content (name, access-list-seq-rule) without the list wrapper is malformed.

**Error:** `POST on list must be on list element` - Payload must wrap content in the list-name container.
</details>



### TEST-7: POST: container in uri and new list payload in the body

```bash
curl -i -k -X POST 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "Cisco-IOS-XE-acl:extended": [
        {
            "name": "exam2-netconf-create-16",
            "access-list-seq-rule": [
                {
                    "sequence": "16",
                    "ace-rule": {
                        "action": "permit",
                        "protocol": "tcp",
                        "host-address": "198.51.100.16",
                        "dst-host-address": "203.0.113.16"

                    }

                }

            ]

        }

    ]

}'
```
<details>
<summary>CLICK HERE TO DISPLAY RESULT</summary>

#### RESULT: POST: ✅ PASSED - Create with Correct Child Resource Payload

**RFC 8040 Section 4.4:** *"The message-body MUST contain exactly one instance of the expected data resource."* Container was empty, payload contains child resource `Cisco-IOS-XE-acl:extended` correctly.
Note: It requires to set the url up to the container which is "access-list", not the list.
Payload should include the "list-name" and "key" of the list. Here "extended" is a list.
Only create new one and fails if there is one.
</details>

### Current Device ACL
```json
{
    "Cisco-IOS-XE-native:access-list": {
        "Cisco-IOS-XE-acl:extended": [
            {
                "name": "challenge-207-pod-10",
                "access-list-seq-rule": [
                    {
                        "sequence": "10",
                        "ace-rule": {
                            "action": "permit",
                            "protocol": "tcp",
                            "any": [
                                null
                            ],
                            "src-gt": 100,
                            "dest-ipv4-address": "203.36.36.32",
                            "dest-mask": "0.0.0.15",
                            "dst-eq": 636
                        }
                    },
                    {
                        "sequence": "20",
                        "ace-rule": {
                            "action": "deny",
                            "protocol": "ip",
                            "host-address": "198.51.100.6",
                            "dst-any": [
                                null
                            ]
                        }
                    }
                ]
            },
            {
                "name": "exam2-netconf-create-16",
                "access-list-seq-rule": [
                    {
                        "sequence": "16",
                        "ace-rule": {
                            "action": "permit",
                            "protocol": "tcp",
                            "host-address": "198.51.100.16",
                            "dst-host-address": "203.0.113.16"
                        }
                    }
                ]
            }
        ]
    }
}
```

### TEST-8: PUT: container in uri and list in payload
```bash
curl -i -k -X PUT 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "Cisco-IOS-XE-acl:extended": [
        {
            "name": "exam2-netconf-create-15",
            "access-list-seq-rule": [
                {
                    "sequence": "16",
                    "ace-rule": {
                        "action": "permit",
                        "protocol": "tcp",
                        "host-address": "198.51.100.16",
                        "dst-host-address": "203.0.113.16"

                    }

                }

            ]

        }

    ]

}'
```

#### RESULT

<details>
<summary>CLICK HERE TO DISPLAY RESULT</summary>

```json
{
  "ietf-restconf:errors": {
    "error": [
      {
        "error-type": "application",
        "error-tag": "malformed-message",
        "error-path": "/Cisco-IOS-XE-native:native/ip/access-list",
        "error-message": "mismatched keypaths: /ios:native/ios:ip/ios:extended , /ios:native/ios:ip/ios:access-list"
      }
    ]
  }
}
```
PUT: ❌ FAILED - Mismatched URI and Payload (Malformed Message)

**RFC 8040 Section 4.5:** *"The target resource for the PUT method for resource creation is the new resource."* The payload must represent the **same resource** as the target URI.

**Explanation:** URI targets `/access-list` (container), but payload contains `Cisco-IOS-XE-acl:extended` (list). The server expects payload to match the URI target - container payload for container URI.

**Error:** `mismatched keypaths` - URI path and payload path don't match. 

</details>



### TEST-9: PUT: list in uri and key in payload
```bash
curl -i -k -X PUT 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "name": "exam2-create-1115",
    "access-list-seq-rule": [
        {
            "sequence": "16",
            "ace-rule": {
                "action": "permit",
                "protocol": "tcp",
                "host-address": "198.51.100.16",
                "dst-host-address": "203.0.113.16"
            }
        }
    ]
}'
```
#### RESULT
<details>
<summary>CLICK HERE TO DISPLAY RESULT</summary>

### TEST-9: PUT: ❌ FAILED - PUT to List Without Key (405 Method Not Allowed)

**RFC 8040 Section 4.5:** PUT requires the target URI to be the **resource itself**. For a list, this means the URI must include the list key.

**Explanation:** URI `/extended` targets the list without a key. PUT cannot operate on a list without specifying which list instance (key) to create or replace. The payload also lacks the required list wrapper.
</details>


### TEST-10: PUT: container in uri and list in payload
```bash
curl -i -k -X PUT 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "Cisco-IOS-XE-acl:extended": [
        {
            "name": "exam2-netconf-create-16",
            "access-list-seq-rule": [
                {
                    "sequence": "16",
                    "ace-rule": {
                        "action": "permit",
                        "protocol": "ucp",
                        "host-address": "198.51.100.16",
                        "dst-host-address": "203.0.113.16"
                    }
                }
            ]
        }
    ]
}'
```
#### RESULT 
<details>
<summary>CLICK HERE TO DISPLAY RESULT</summary>

```json
{
  "ietf-restconf:errors": {
    "error": [
      {
        "error-type": "application",
        "error-tag": "malformed-message",
        "error-path": "/Cisco-IOS-XE-native:native/ip/access-list",
        "error-message": "mismatched keypaths: /ios:native/ios:ip/ios:extended , /ios:native/ios:ip/ios:access-list"
      }
    ]
  }
}
```
#### PUT: ❌ FAILED - Container URI with List Payload (Mismatched Keypaths)

**RFC 8040 Section 4.5:** *"A PUT on a data resource only replaces that data resource within the datastore."* The payload must represent the **exact same resource** as the URI target.

**Explanation:** URI targets `/access-list` (container), but payload is `Cisco-IOS-XE-acl:extended` (list). To replace the entire container, payload must be `Cisco-IOS-XE-native:access-list` with full container structure.

**Correct Approach:** To replace container, use container wrapper. To replace specific ACL, use URI with key (`/extended=ACL-NAME`).
</details>


### TEST-11: PUT: list with key in uri and payload

**RFC 8040 Section 4.5:** *"A PUT on a data resource only replaces that data resource within the datastore."* URI includes list key, payload contains matching list wrapper.
```bash
curl -i -k -X PUT 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended=exam2-netconf-create-16' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "Cisco-IOS-XE-acl:extended": [
        {
            "name": "exam2-netconf-create-16",
            "access-list-seq-rule": [
                {
                    "sequence": "16",
                    "ace-rule": {
                        "action": "permit",
                        "protocol": "udp",
                        "src-eq": 636,
                        "host-address": "198.51.100.16",
                        "dst-host-address": "203.0.113.16",
                        "dst-eq": 6000
                    }
                }
            ]
        }
    ]
}'
```
#### RESULT
<details>
<summary>CLICK HERE TO DISPLAY RESULT</summary>

PUT: ✅ SUCCESSFUL - Replace List Instance with Key in URI

**RFC 8040 Section 4.5:** *"A PUT on a data resource only replaces that data resource within the datastore."* URI includes list key, payload contains matching list wrapper.
</details>

### TEST-12: PUT: container in uri and payload

**RFC 8040 Section 4.5:** *"A PUT on the datastore resource is used to replace the entire contents of the datastore."* URI targets container, payload is full container structure with `Cisco-IOS-XE-native:access-list` wrapper. Replaces ALL ACLs.
```bash
curl -i -k -X PUT 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "Cisco-IOS-XE-native:access-list": {
        "Cisco-IOS-XE-acl:extended": [
            {
                "name": "challenge-207-pod-10",
                "access-list-seq-rule": [
                    {
                        "sequence": "10",
                        "ace-rule": {
                            "action": "permit",
                            "protocol": "tcp",
                            "any": [
                                null
                            ],
                            "src-gt": 100,
                            "dest-ipv4-address": "203.36.36.32",
                            "dest-mask": "0.0.0.15",
                            "dst-eq": 636
                        }
                    },
                    {
                        "sequence": "20",
                        "ace-rule": {
                            "action": "deny",
                            "protocol": "ip",
                            "host-address": "198.51.100.6",
                            "dst-any": [
                                null
                            ]
                        }
                    }
                ]
            },
            {
                "name": "exam2-netconf-create-16",
                "access-list-seq-rule": [
                    {
                        "sequence": "16",
                        "ace-rule": {
                            "action": "permit",
                            "protocol": "tcp",
                            "host-address": "198.51.100.16",
                            "dst-host-address": "203.0.113.16"
                        }
                    }
                ]
            }
        ]
    }
}'
```
#### RESULT
<details>
<summary>CLICK TO DISPLAY RESULT</summary>

PUT: ✅ SUCCESSFUL - Replace Entire Container

**RFC 8040 Section 4.5:** *"A PUT on the datastore resource is used to replace the entire contents of the datastore."* URI targets container, payload is full container structure with `Cisco-IOS-XE-native:access-list` wrapper. Replaces ALL ACLs.
</details>

### TEST-13: PATCH: list with key in uri and payload with key but without list
```bash
curl -i -k -X PATCH 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended=exam2-netconf-create-16' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '
        {
            "name": "exam2-netconf-create-16",
            "access-list-seq-rule": [
                {
                    "sequence": "16",
                    "ace-rule": {
                        "action": "permit",
                        "protocol": "udp",
                        "host-address": "16.16.16.16",
                        "dst-host-address": "16.16.16.16"
                    }
                }
            ]
        }'
```
#### RESULT
<details>
<summary>CLICK TO DISPLAY RESULT</summary>

```
HTTP/1.1 400 Bad Request
Server: openresty
Date: Mon, 15 Dec 2025 13:32:25 GMT
Content-Type: application/yang-data+json
Transfer-Encoding: chunked
Connection: keep-alive
Cache-Control: private, no-cache, must-revalidate, proxy-revalidate
Vary: Accept-Encoding
Pragma: no-cache
```
```json
{
  "ietf-restconf:errors": {
    "error": [
      {
        "error-type": "application",
        "error-tag": "malformed-message",
        "error-path": "/Cisco-IOS-XE-native:native/ip/access-list/Cisco-IOS-XE-acl:extended[name='exam2-netconf-create-16']",
        "error-message": "missing element: extended in /ios:native/ios:ip/ios:access-list/ios-acl:extended[ios-acl:name='exam2-netconf-create-16']"
      }
    ]
  }
}
```
PATCH: ❌ FAILED - Missing List Wrapper in Payload (Malformed Message)

**RFC 8040 Section 4.6.1:** *"The message-body for a plain patch MUST be present and MUST be represented by the media type 'application/yang-data+xml' or 'application/yang-data+json'."*

**RFC 8040 Section 4.6.1:** *"If the target resource represents a YANG list instance, then the key leaf values, in message-body representation, MUST be the same as the key leaf values in the request URI."*

**Explanation:** Even though URI includes the key (`/extended=exam2-netconf-create-16`), the payload must still include the list wrapper `"Cisco-IOS-XE-acl:extended": [...]`. Providing only the list element content without the wrapper is malformed.

**Error:** `missing element: extended` - Payload requires list-name wrapper even when key is in URI.
</details>


### TEST-14: PATCH: ✅ SUCCESSFUL - Merge with List Wrapper at Specific Sequence

**RFC 8040 Section 4.6.1:** Plain patch merges the contents of the message-body with the target resource. Payload includes the child list wrapper `access-list-seq-rule`.
```bash
curl -i -k -X PATCH 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended=exam2-netconf-create-16/access-list-seq-rule=16' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "access-list-seq-rule": [
        {
            "sequence": "16",
            "ace-rule": {
                "action": "permit",
                "protocol": "udp",
                "host-address": "25.25.25.25",
                "dst-host-address": "25.25.25.25"
            }
        }
    ]
}'
```

### TEST-15: PATCH: ✅ SUCCESSFUL - Merge Extended ACL with Key and List Wrapper

**RFC 8040 Section 4.6.1:** *"Plain patch can be used to create or update, but not delete, a child resource within the target resource."* Payload includes `Cisco-IOS-XE-acl:extended` wrapper with matching key.
```bash
curl -i -k -X PATCH 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended=exam2-netconf-create-16' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "Cisco-IOS-XE-acl:extended": [
        {
            "name": "exam2-netconf-create-16",
            "access-list-seq-rule": [
                {
                    "sequence": "16",
                    "ace-rule": {
                        "action": "permit",
                        "protocol": "udp",
                        "host-address": "16.16.16.16",
                        "dst-host-address": "16.16.16.16"
                    }
                }
            ]
        }
    ]
}'
```
```
HTTP/1.1 204 No Content
Server: openresty
Date: Mon, 15 Dec 2025 13:26:22 GMT
Content-Type: text/html
Content-Length: 0
Connection: keep-alive
Last-Modified: Mon, 15 Dec 2025 13:26:22 GMT
Cache-Control: private, no-cache, must-revalidate, proxy-revalidate
Etag: "1765-805182-191526"
Pragma: no-cache
```



### TEST-16: PATCH: ✅ SUCCESSFUL - Merge to List Without Key in URI (List-Name in Payload)

**RFC 8040 Section 4.6.1:** Plain patch merges contents with target. Unlike POST, PATCH can target a list without key in URI when payload includes the list wrapper with key inside. This is useful for adding new entries to existing data.
```bash
curl -i -k -X PATCH 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "Cisco-IOS-XE-acl:extended": [
        {
            "name": "exam2-netconf-create-16",
            "access-list-seq-rule": [
                {
                    "sequence": "16",
                    "ace-rule": {
                        "action": "permit",
                        "protocol": "udp",
                        "host-address": "198.51.100.16",
                        "dst-host-address": "203.0.113.16"
                    }
                }
            ]
        }
    ]
}'
```
```
HTTP/1.1 204 No Content
Server: openresty
Date: Mon, 15 Dec 2025 13:28:00 GMT
Content-Type: text/html
Content-Length: 0
Connection: keep-alive
Last-Modified: Mon, 15 Dec 2025 13:28:00 GMT
Cache-Control: private, no-cache, must-revalidate, proxy-revalidate
Etag: "1765-805280-387361"
Pragma: no-cache
```



### TEST-17: GET: list with key in uri
```bash
curl -i -k -X GET 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended=exam2-netconf-create-16' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ=='
```

RESULT:
```json
{
    "Cisco-IOS-XE-acl:extended": [
        {
            "name": "exam2-netconf-create-16",
            "access-list-seq-rule": [
                {
                    "sequence": "16",
                    "ace-rule": {
                        "action": "permit",
                        "protocol": "udp",
                        "host-address": "198.51.100.16",
                        "dst-host-address": "203.0.113.16"
                    }
                }
            ]
        }
    ]
}
```



### TEST-18: DELETE: ❌ FAILED - Cannot DELETE List Without Key (Operation Not Allowed)

**RFC 8040 Section 4.7:** DELETE is used to delete the target resource. For a YANG list, the target must be a **specific list instance** identified by its key.

**Explanation:** URI `/extended` targets the entire list type, not a specific list instance. DELETE requires the list key to identify which instance to delete (e.g., `/extended=ACL-NAME`).

**IOS-XE Behavior:** Returns `Operation not allowed` when attempting to DELETE a list without specifying the key.

**Valid DELETE Targets:**
- `/extended=ACL-NAME` - Delete specific ACL ✅
- `/access-list` - Delete entire container (all ACLs) ✅
- `/extended` - Delete list type without key ❌ 
```bash
curl -i -k -X DELETE 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ=='
```
```json
{
  "ietf-restconf:errors": {
    "error": [
      {
        "error-type": "application",
        "error-tag": "malformed-message",
        "error-message": "Operation not allowed."
      }
    ]
  }
}
```

### TEST-19: DELETE: ✅ SUCCESSFUL - Delete Specific List Instance with Key

**RFC 8040 Section 4.7:** DELETE with list key removes the specific list instance.
```bash
curl -i -k -X DELETE 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended=exam2-netconf-create-16' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ=='
```

### TEST-20: DELETE: ✅ SUCCESSFUL - Delete Entire Container

**RFC 8040 Section 4.7:** DELETE on a container removes the entire container and all its contents.
```bash
curl -i -k -X DELETE 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ=='
```

---

## Quick Reference Table (Additional)
##### **GET can operate uri with list woKEY/list wKEY/container
##### **POST only container in uri and list with new key in the payload
##### **PUT uri and payload must be same, 201 for new resource and 204 if replaced
##### **PATCH uri and payload must be same, 204 for new or replaced
##### **DELETE can be container or list must be with key

| Method | URI Target | Payload Wrapper | Result |
|--------|------------|-----------------|--------|
| **GET** | `/extended` (list) | N/A | ✅ |
| **GET** | `/extended=KEY` | N/A | ✅ |
| **POST** | `/access-list` (container) | `Cisco-IOS-XE-acl:extended` **with new key | ✅ |
| **POST** | `/access-list` (container) | `Cisco-IOS-XE-acl:extended` **with existing key | ❌ data-exists |
| **POST** | `/extended` (list) | any | ❌ POST on list must be on list element |
| **PUT** | `/access-list` (container) | `Cisco-IOS-XE-native:access-list` | ✅ replaces all |
| **PUT** | `/extended=KEY` | `Cisco-IOS-XE-acl:extended` **with same key | ✅ |
| **PUT** | `/extended` (list, no key) | any | ❌ |
| **PATCH** | `/extended=KEY` | `Cisco-IOS-XE-acl:extended` | ✅ |
| **PATCH** | `/extended` (list) | `Cisco-IOS-XE-acl:extended` | ✅ |
| **PATCH** | `/extended=KEY/access-list-seq-rule=SEQ` | `access-list-seq-rule` | ✅ |
| **DELETE** | `/access-list` (container) | N/A | ✅ deletes all |
| **DELETE** | `/extended=KEY` | N/A | ✅ |
| **DELETE** | `/extended` (list, no key) | N/A | ❌ Operation not allowed |

---

## POST vs PUT vs PATCH - RFC 8040 Explanation

> Reference: RFC 8040 - RESTCONF Protocol, Sections 4.4, 4.5, and 4.6

### Key Differences Summary

| Aspect | POST | PUT | PATCH |
|--------|------|-----|-------|
| **RFC Section** | 4.4 | 4.5 | 4.6 |
| **Purpose** | Create only | Create OR Replace | Merge/Update only |
| **Target Resource** | Parent of new resource | The resource itself | The resource itself |
| **Key in URI?** | ❌ No (key in payload) | ✅ Yes (must match payload) | ✅ Yes |
| **If Target Doesn't Exist** | ✅ Creates it | ✅ Creates it | ❌ **MUST NOT create** |
| **If Target Exists** | ❌ `409 Conflict` | ✅ Replaces entirely | ✅ Merges/Updates |
| **Child Resources** | Created with parent | **Replaced** with payload | Can create/update (**not delete**) |
| **Message Body** | Required (child resource) | Required (new data) | Required (merge data) |
| **Success Response** | `201 Created` + Location header | `204 No Content` or `201 Created` | `204 No Content` or `200 OK` |
| **Idempotent?** | ❌ No | ✅ Yes | ✅ Yes |

---

### POST - Create Resource (RFC 8040 Section 4.4)

#### RFC 8040 Key Points:

| # | Key Point | Description |
|---|-----------|-------------|
| 1 | **Target = Parent** | Target resource is the **parent** of the new resource |
| 2 | **No Key in URI** | Client does NOT provide resource identifier in URI; key is in payload |
| 3 | **Message Body Required** | MUST contain exactly one instance of the expected data resource |
| 4 | **Create Only** | Used to create a data resource (not update) |
| 5 | **Fails if Exists** | If data resource already exists, MUST fail with `409 Conflict` |
| 6 | **Success Response** | `201 Created` with `Location` header identifying created resource |
| 7 | **Error: Exists** | Error-tag: `resource-denied` when resource already exists |
| 8 | **Error: Unauthorized** | `403 Forbidden` with error-tag: `access-denied` |

#### RFC 8040 Quote:
> *"The difference is that for POST, the client does not provide the resource identifier for the resource that will be created. The target resource for the POST method for resource creation is the parent of the new resource."*
>
> *"If the data resource already exists, then the POST request MUST fail and a '409 Conflict' status-line MUST be returned."*

#### Example:

```bash
# POST to PARENT container - key "NEW-ACL" is in payload, NOT in URI
curl -i -k -X POST 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "Cisco-IOS-XE-acl:extended": [
        {
            "name": "NEW-ACL",
            "access-list-seq-rule": [
                {
                    "sequence": "10",
                    "ace-rule": {
                        "action": "permit",
                        "protocol": "tcp",
                        "any": [null],
                        "dst-any": [null]
                    }
                }
            ]
        }
    ]
}'
```

| Condition | HTTP Response | Explanation |
|-----------|---------------|-------------|
| `NEW-ACL` does not exist | ✅ `201 Created` | Resource created successfully |
| `NEW-ACL` already exists | ❌ `409 Conflict` | error-tag: `resource-denied` |
| Other ACLs exist in container | ❌ `409 Conflict` | IOS-XE 17.5: error-tag: `data-exists` |

---

### PUT - Create OR Replace Resource (RFC 8040 Section 4.5)

#### RFC 8040 Key Points:

| # | Key Point | Description |
|---|-----------|-------------|
| 1 | **Target = Resource** | Target resource is the **new resource itself** (not parent) |
| 2 | **Key in URI** | Client provides resource identifier (key) in URI |
| 3 | **Message Body Required** | MUST be present representing the new data resource |
| 4 | **Create OR Replace** | Creates if not exists; **replaces entirely** if exists |
| 5 | **Full Replacement** | PUT on a data resource **replaces that entire data resource** |
| 6 | **Datastore Replace** | PUT on datastore resource replaces **entire contents** of datastore |
| 7 | **URI = Payload** | Key in URI must match key in payload |
| 8 | **Success Response** | `204 No Content` (updated) or `201 Created` (new) |
| 9 | **Error: No Body** | `400 Bad Request` with error-tag: `invalid-value` if no message body |

#### RFC 8040 Quote:
> *"The PUT method is sent by the client to create or replace the target data resource. A request message-body MUST be present, representing the new data resource."*
>
> *"The target resource for the PUT method for resource creation is the new resource."*
>
> *"A PUT on a data resource only replaces that data resource within the datastore."*

#### Example:

```bash
# PUT to TARGET resource - key "NEW-ACL" is in URI AND payload
curl -i -k -X PUT 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended=NEW-ACL' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "Cisco-IOS-XE-acl:extended": [
        {
            "name": "NEW-ACL",
            "access-list-seq-rule": [
                {
                    "sequence": "10",
                    "ace-rule": {
                        "action": "permit",
                        "protocol": "tcp",
                        "any": [null],
                        "dst-any": [null]
                    }
                }
            ]
        }
    ]
}'
```

| Condition | HTTP Response | Explanation |
|-----------|---------------|-------------|
| `NEW-ACL` does not exist | ✅ `201 Created` | Resource created |
| `NEW-ACL` exists | ✅ `204 No Content` | **Entire** ACL replaced |
| `NEW-ACL` had seq 10,20,30; PUT with seq 10 only | ✅ `204 No Content` | **Only** seq 10 remains (20,30 deleted) |
| URI key ≠ payload key | ❌ `400 Bad Request` | Mismatched keys |

---

### PATCH - Merge/Update Resource (RFC 8040 Section 4.6)

#### RFC 8040 Key Points:

| # | Key Point | Description |
|---|-----------|-------------|
| 1 | **Target = Resource** | Target resource is the resource to be patched |
| 2 | **MUST NOT Create** | If target resource does NOT exist, server **MUST NOT create it** |
| 3 | **Merge Operation** | Plain patch **merges** contents of message-body with target resource |
| 4 | **Create Child** | Can **create** child resources within target resource |
| 5 | **Update Child** | Can **update** child resources within target resource |
| 6 | **Cannot Delete Child** | Plain PATCH **cannot delete** child resources (use YANG Patch for delete) |
| 7 | **Key Immutable** | PATCH **MUST NOT** change key leaf values of a data resource instance |
| 8 | **Message Body Required** | MUST be present with media type `application/yang-data+json` or `+xml` |
| 9 | **Success Response** | `200 OK` (with body) or `204 No Content` (no body) |
| 10 | **Leaf-List** | PATCH MUST NOT change the value of leaf-list instance |

#### RFC 8040 Quote:
> *"If the target resource instance does not exist, the server MUST NOT create it."*
>
> *"The plain patch mechanism merges the contents of the message-body with the target resource."*
>
> *"Plain patch can be used to create or update, but not delete, a child resource within the target resource."*
>
> *"The PATCH method MUST NOT be used to change the key leaf values for a data resource instance."*

#### Example:

```bash
# PATCH to TARGET resource - merges seq 40 into existing ACL
curl -i -k -X PATCH 'https://192.168.89.71/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/extended=EXISTING-ACL' \
--header 'Accept: application/yang-data+json' \
--header 'Content-Type: application/yang-data+json' \
--header 'Authorization: Basic ZXhwZXJ0OjEyMzRRV2VyIQ==' \
--data '{
    "Cisco-IOS-XE-acl:extended": [
        {
            "name": "EXISTING-ACL",
            "access-list-seq-rule": [
                {
                    "sequence": "40",
                    "ace-rule": {
                        "action": "deny",
                        "protocol": "udp",
                        "any": [null],
                        "dst-any": [null]
                    }
                }
            ]
        }
    ]
}'
```

| Condition | HTTP Response | Explanation |
|-----------|---------------|-------------|
| `EXISTING-ACL` does not exist | ❌ Error | **MUST NOT create** - target must exist |
| `EXISTING-ACL` exists, adding seq 40 | ✅ `204 No Content` | seq 40 **merged** into ACL |
| ACL had seq 10,20,30; PATCH with seq 40 | ✅ `204 No Content` | Now has seq 10,20,30 **and** 40 |
| ACL had seq 10; PATCH with updated seq 10 | ✅ `204 No Content` | seq 10 **updated** (merged) |
| Try to change ACL name (key) | ❌ Error | Cannot change key values |

---

### Side-by-Side Comparison: Same ACL, Different Methods

**Scenario:** ACL `TEST-ACL` exists with sequence rules 10 and 20.

| Method | URI | Payload | Result | Final State |
|--------|-----|---------|--------|-------------|
| **POST** | `/access-list` | `"name": "TEST-ACL", seq 30` | ❌ `409 Conflict` | Unchanged (seq 10, 20) |
| **PUT** | `/extended=TEST-ACL` | seq 30 only | ✅ `204 No Content` | **Only** seq 30 (replaced) |
| **PATCH** | `/extended=TEST-ACL` | seq 30 only | ✅ `204 No Content` | seq 10, 20, **and** 30 (merged) |

---

### Visual Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RESTCONF OPERATIONS COMPARISON                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  POST (Create Only)                                                         │
│  ══════════════════                                                         │
│  URI: /access-list  (parent)         Payload: { "extended": [{"name":"X"}]} │
│                                                                             │
│  Before: [ACL-A, ACL-B]              After: [ACL-A, ACL-B, X] ✅            │
│  Before: [ACL-X exists]              After: 409 Conflict ❌                 │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PUT (Create or Replace)                                                    │
│  ═══════════════════════                                                    │
│  URI: /extended=X  (target)          Payload: { "extended": [{"name":"X"}]} │
│                                                                             │
│  Before: X not exists                After: X created ✅                    │
│  Before: X has [seq10, seq20]        After: X has [seq30] only ✅           │
│          Payload: [seq30]                   (REPLACED entirely)             │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PATCH (Merge Only)                                                         │
│  ══════════════════                                                         │
│  URI: /extended=X  (target)          Payload: { "extended": [{"name":"X"}]} │
│                                                                             │
│  Before: X not exists                After: Error ❌ (MUST NOT create)      │
│  Before: X has [seq10, seq20]        After: X has [seq10, seq20, seq30] ✅  │
│          Payload: [seq30]                   (MERGED)                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Decision Flow

```
What do you want to do?
│
├─► CREATE new resource (fail if exists)?
│   └─► Use POST to parent URI
│       • URI: /access-list (parent container)
│       • Key in PAYLOAD only
│       • Fails with 409 if resource exists
│       • Returns: 201 Created + Location header
│
├─► CREATE or REPLACE entire resource?
│   └─► Use PUT to target URI with key
│       • URI: /extended=ACL-NAME (target resource)
│       • Key in URI AND payload (must match)
│       • Creates if not exists
│       • REPLACES ALL content if exists
│       • Returns: 201 Created or 204 No Content
│
├─► UPDATE/MERGE into existing resource?
│   └─► Use PATCH to target URI with key
│       • URI: /extended=ACL-NAME (target resource)
│       • Target MUST exist (won't create)
│       • MERGES changes (keeps existing data)
│       • Can add/update children, CANNOT delete
│       • Returns: 200 OK or 204 No Content
│
└─► DELETE resource?
    └─► Use DELETE to target URI with key
        • URI: /extended=ACL-NAME
        • Returns: 204 No Content
```

---

### IOS-XE 17.5 Practical Recommendations

| Scenario | Recommended Method | Why |
|----------|-------------------|-----|
| Create ACL when container is empty | POST | Standard create operation |
| Create ACL when other ACLs exist | PATCH (to existing) or PUT | POST fails with `data-exists` on 17.5 |
| Replace entire ACL content | PUT | Complete replacement guaranteed |
| Add new sequence to existing ACL | PATCH | Merges without deleting existing sequences |
| Modify specific sequence rule | PATCH | Updates only specified fields |
| Delete specific ACL | DELETE | Only way to remove |
| Delete all ACLs | DELETE to container | Removes entire access-list container |

---

### Key Takeaways

1. **POST** only works on empty containers - use PATCH for adding to existing data
2. **PUT** requires exact URI-to-payload match (container→container, list+key→list)
3. **PATCH** is most flexible - works with or without key in URI
4. **DELETE** on list requires key; on container deletes everything
5. Always use `-i` flag to see HTTP status codes (204 = success)