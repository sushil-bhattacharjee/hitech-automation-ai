# Flask-RESTX Marshal Quick Reference

## ðŸŽ¯ What is Marshalling?

**Marshalling** = Filtering and formatting output data according to a defined model.

```python
from flask_restx import fields, marshal
import json

# Raw data (has extra fields)
data = {"name": "Alice", "age": 30, "secret": "password123"}

# Define model (only these fields will appear)
model = {
    'name': fields.String,
    'age': fields.Integer
}

# Marshal filters out 'secret'
result = marshal(data, model)
# Result: {"name": "Alice", "age": 30}
```

---

## ðŸš¨ Common Mistake: Using `list(dict.values())`

### âŒ WRONG - Breaks Structure

```python
device_data = {"hostname": "R1", "ip": "10.1.1.1", "type": "router"}

# WRONG: list() destroys keys!
list(device_data.values())  
# Returns: ['R1', '10.1.1.1', 'router']  â† Just strings, no keys!

marshal(list(device_data.values()), model)
# Result: All null values - can't find keys in plain strings
```

### âœ… CORRECT - Preserve Structure

```python
# CORRECT: Marshal the dictionary directly
marshal(device_data, model)
# Result: {"hostname": "R1", "ip": "10.1.1.1", "type": "router"}
```

### When `.values()` IS Correct

```python
# When dict values are THEMSELVES dicts:
peers = {
    "peer1": {"ip": "192.168.1.1", "as": 65001},
    "peer2": {"ip": "192.168.1.2", "as": 65002}
}

# This works because values still have keys inside!
list(peers.values())
# Returns: [{"ip": "192.168.1.1", "as": 65001}, {"ip": "192.168.1.2", "as": 65002}]

marshal(list(peers.values()), model)  # âœ… Works!
```

---

## ðŸ“‹ Field Types Reference

```python
from flask_restx import fields

# Basic types
fields.String          # Text
fields.Integer         # Numbers (int)
fields.Float           # Numbers (decimal)
fields.Boolean         # True/False
fields.DateTime        # Timestamps

# Special types
fields.Raw             # Pass-through (no filtering/validation)
fields.List(fields.String)  # Array of items
fields.Nested(model)   # Nested object
fields.Wildcard(...)   # Dynamic keys

# Field with attribute mapping
fields.String(attribute='original_name')  # Rename field in output
```

---

## ðŸ”¹ Basic Example

```python
# Data
device = {
    "hostname": "R1",
    "ip": "10.1.1.1",
    "type": "router",
    "password": "secret",  # Will be filtered
    "api_key": "xyz123"    # Will be filtered
}

# Model (only define what you want to show)
device_model = {
    'hostname': fields.String,
    'ip': fields.String,
    'type': fields.String
}

# Marshal
result = marshal(device, device_model)
print(json.dumps(result, indent=2))
```

**Output:**
```json
{
  "hostname": "R1",
  "ip": "10.1.1.1",
  "type": "router"
}
```

---

## ðŸ”¸ Nested Example

```python
# Data with nested structure
bgp_peer = {
    "peer_ip": "192.168.1.1",
    "remote_as": 65001,
    "state": "Established",
    "stats": {
        "prefixes_received": 150,
        "prefixes_sent": 75
    },
    "uptime": "5d 12h",      # Will be filtered
    "internal_id": "abc123"  # Will be filtered
}

# Define nested model (innermost)
stats_model = {
    'prefixes_received': fields.Integer,
    'prefixes_sent': fields.Integer
}

# Define peer model (outermost)
peer_model = {
    'peer_ip': fields.String,
    'remote_as': fields.Integer,
    'state': fields.String,
    'stats': fields.Nested(stats_model)
}

# Marshal
result = marshal(bgp_peer, peer_model)
print(json.dumps(result, indent=2))
```

**Output:**
```json
{
  "peer_ip": "192.168.1.1",
  "remote_as": 65001,
  "state": "Established",
  "stats": {
    "prefixes_received": 150,
    "prefixes_sent": 75
  }
}
```

---

## ðŸŒŸ Dynamic Keys with `fields.Wildcard()`

### Problem: Hardcoded Keys Don't Scale

```python
# âŒ WRONG: Must define every interface
interfaces_model = {
    'GigE0/0': fields.Nested(interface_model),
    'GigE0/1': fields.Nested(interface_model),
    # What if GigE0/2 exists? It won't be included!
}
```

### Solution: Use Wildcard

```python
# Data with dynamic interface names
router = {
    "hostname": "R1",
    "interfaces": {
        "GigE0/0": {"ip": "10.1.1.1", "status": "up", "speed": 1000},
        "GigE0/1": {"ip": "10.1.2.1", "status": "down", "speed": 1000},
        "GigE0/99": {"ip": "10.1.99.1", "status": "up", "speed": 10000}
    },
    "chassis_id": "FOC12345"  # Will be filtered
}

# Define interface model (applied to ANY interface)
interface_model = {
    'ip': fields.String,
    'status': fields.String,
    'speed': fields.Integer
}

# Define router model using Wildcard
router_model = {
    'hostname': fields.String,
    'interfaces': fields.Wildcard(fields.Nested(interface_model))
}

# Marshal - works for ANY interface name!
result = marshal(router, router_model)
print(json.dumps(result, indent=2))
```

**Output:**
```json
{
  "hostname": "R1",
  "interfaces": {
    "GigE0/0": {
      "ip": "10.1.1.1",
      "status": "up",
      "speed": 1000
    },
    "GigE0/1": {
      "ip": "10.1.2.1",
      "status": "down",
      "speed": 1000
    },
    "GigE0/99": {
      "ip": "10.1.99.1",
      "status": "up",
      "speed": 10000
    }
  }
}
```

---

## ðŸ”„ Attribute Mapping (Renaming Fields)

```python
# Data with one field name
data = {
    "peer_ip": "192.168.1.1",
    "remote_as": 65001,
    "state": "Established"
}

# Model that renames fields in output
mapped_model = {
    'ip': fields.String(attribute='peer_ip'),       # Rename peer_ip â†’ ip
    'as_number': fields.Integer(attribute='remote_as'),  # Rename remote_as â†’ as_number
    'status': fields.String(attribute='state')      # Rename state â†’ status
}

result = marshal(data, mapped_model)
print(json.dumps(result, indent=2))
```

**Output:**
```json
{
  "ip": "192.168.1.1",
  "as_number": 65001,
  "status": "Established"
}
```

---

## ðŸ“Š Comparison: Field Types for Nested Data

| Field Type | Use Case | Example Data Structure |
|------------|----------|------------------------|
| `fields.Nested(model)` | Fixed nested object | `{"address": {"street": "...", "city": "..."}}` |
| `fields.Wildcard(fields.Nested(model))` | Dynamic keys (dict) | `{"GigE0/0": {...}, "GigE0/1": {...}}` |
| `fields.List(fields.Nested(model))` | Array of objects | `[{...}, {...}, {...}]` |
| `fields.Raw` | Pass-through (no validation) | Any structure |

---

## ðŸ§ª Complete REPL Practice Session

```python
from flask_restx import fields, marshal
import json

# Example 1: Basic marshalling
device = {"hostname": "R1", "ip": "10.1.1.1", "password": "secret"}
device_model = {'hostname': fields.String, 'ip': fields.String}
print(json.dumps(marshal(device, device_model), indent=2))

# Example 2: Nested structure
bgp_peer = {
    "peer_ip": "192.168.1.1",
    "stats": {"prefixes_rx": 150, "prefixes_tx": 75},
    "internal_id": "xyz"  # Filtered out
}

stats_model = {'prefixes_rx': fields.Integer, 'prefixes_tx': fields.Integer}
peer_model = {'peer_ip': fields.String, 'stats': fields.Nested(stats_model)}
print(json.dumps(marshal(bgp_peer, peer_model), indent=2))

# Example 3: Dynamic keys (Wildcard)
router = {
    "hostname": "R1",
    "interfaces": {
        "GigE0/0": {"ip": "10.1.1.1", "status": "up"},
        "GigE0/1": {"ip": "10.1.2.1", "status": "down"}
    }
}

int_model = {'ip': fields.String, 'status': fields.String}
router_model = {
    'hostname': fields.String,
    'interfaces': fields.Wildcard(fields.Nested(int_model))
}
print(json.dumps(marshal(router, router_model), indent=2))

# Example 4: List of objects
peers_dict = {
    "peer1": {"ip": "192.168.1.1", "as": 65001},
    "peer2": {"ip": "192.168.1.2", "as": 65002}
}

peer_simple_model = {'ip': fields.String, 'as': fields.Integer}
# Convert dict values to list, then marshal
print(json.dumps(marshal(list(peers_dict.values()), peer_simple_model), indent=2))
```

---

## ðŸŽ¯ Decision Tree: When to Use What

```
Is your data a single dictionary?
â”œâ”€ YES â†’ marshal(data, model)
â””â”€ NO â†’ Is it a list of dictionaries?
    â”œâ”€ YES â†’ marshal(data_list, model)
    â””â”€ NO â†’ Is it a dict where values are dicts?
        â””â”€ YES â†’ marshal(list(data.values()), model)

Does your nested data have fixed keys?
â”œâ”€ YES â†’ Use fields.Nested(model)
â””â”€ NO (dynamic keys) â†’ Use fields.Wildcard(fields.Nested(model))

Do you want to filter nested fields?
â”œâ”€ YES â†’ Use fields.Nested() or fields.Wildcard()
â””â”€ NO (pass everything) â†’ Use fields.Raw
```

---

## ðŸš€ Flask-RESTX Integration

```python
from flask import Flask
from flask_restx import Resource, Api, fields, marshal

app = Flask(__name__)
api = Api(app)

# Define model using api.model() for Swagger docs
device_model = api.model('Device', {
    'hostname': fields.String,
    'ip': fields.String,
    'type': fields.String
})

devices_data = {
    "R1": {"hostname": "R1", "ip": "10.1.1.1", "type": "router", "password": "secret"},
    "R2": {"hostname": "R2", "ip": "10.1.1.2", "type": "router", "password": "cisco"}
}

@api.route('/devices')
class DeviceList(Resource):
    @api.marshal_with(device_model, as_list=True)  # List of devices
    def get(self):
        return list(devices_data.values())

@api.route('/device/<string:hostname>')
class Device(Resource):
    @api.marshal_with(device_model)  # Single device
    def get(self, hostname):
        if hostname not in devices_data:
            api.abort(404, f"Device {hostname} not found")
        return devices_data[hostname]
```

---

## ðŸ“ Key Takeaways

1. **Marshal filters output** - only returns fields defined in model
2. **Preserve dictionary structure** - don't use `list(dict.values())` on single objects
3. **Use `fields.Wildcard()`** for dynamic keys (interfaces, peers, etc.)
4. **Use `fields.Nested()`** for fixed nested structures
5. **`@api.marshal_with(model)`** automatically marshals Flask-RESTX responses
6. **`as_list=True`** when returning arrays, `as_list=False` (default) for single objects

---

## âš¡ Quick Syntax Reference

```python
# Single object
marshal(data_dict, model)

# List of objects
marshal(data_list, model)
marshal(list(dict_of_dicts.values()), model)

# In Flask-RESTX
@api.marshal_with(model)               # Single object
@api.marshal_with(model, as_list=True) # List of objects

# Field definitions
model = {
    'field1': fields.String,
    'field2': fields.Integer,
    'nested': fields.Nested(nested_model),
    'dynamic': fields.Wildcard(fields.Nested(item_model)),
    'renamed': fields.String(attribute='original_name')
}
```

---

**Practice makes perfect! Try the examples in Python REPL.** ðŸ