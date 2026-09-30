# Challenge 103: Spare Parts API (Exam Version)

## Tasks

### Models

| TODO | Model Name | Task |
|------|------------|------|
| 1a | `error_model` | Define an error model named `Status` with two fields: `success` (boolean) and `message` (string) — see Swagger preview |
| 1b | `part_model` | Define a minimal part model that **renames** internal `name` → `"Product Name"` and `price` → `"Unit Price"` using `attribute=` |
| 1c | `parts_model` | Define a model that wraps a list of `part_model`. Include `example=[...]` with two sample entries |
| 1d | `part_full_model` | Define a complete part model — renamed name/price plus `category` and `qty` |

### Parsers

| TODO | Endpoint | Task |
|------|----------|------|
| 2a | `/parts` | Add a category parameter restricted to `cooling`, `power`, `networking`, `compute`, `all` |
| 2b | `/part` | Add a `part_id` parameter (string) |
| 2c | `/part` | Build a POST parser that reuses the GET parser and adds `name`, `category`, `qty`, `price` |
| 2d | `/part` | Build a PUT parser that reuses the POST parser |
| 2e | `/part` | Build a DELETE parser that reuses the GET parser |

### Endpoints — Decorators & Logic

| TODO | Endpoint | Method | Task |
|------|----------|--------|------|
| 3a | `/parts` | GET | Auto-format the response using `parts_model` |
| 3b | `/parts` | GET | Filter by category using a comprehension. Return all if `category=all` or not provided. Shape must be `{'parts': data}` |
| 4a | `/part` | GET | Auto-format success with `part_full_model` |
| 4b | `/part` | GET | Document the 404 error response with `error_model` |
| 4c | `/part` | GET | Handle not found — **`raise PartIDNotFound`** (caught by `@api.errorhandler`) |
| 4d | `/part` | GET | Return the matching part |
| 5a | `/part` | POST | Use `@api.marshal_with(part_full_model, code=201, description="...")` for both formatting and Swagger docs |
| 5b | `/part` | POST | Store the new part. Return the part dict with status `201` |
| 6a | `/part` | PUT | Document the 204 success response |
| 6b | `/part` | PUT | Document the 404 error response with `error_model` |
| 6c | `/part` | PUT | Handle not found — **`return marshal({...}, error_model), 404`** |
| 6d | `/part` | PUT | Update the existing part. Return `{}, 204` |
| 7a | `/part` | DELETE | Document the 204 success response |
| 7b | `/part` | DELETE | Document the 404 error response with `error_model` |
| 7c | `/part` | DELETE | Handle not found — **plain dict return** `return {"error": "..."}, 404` (no marshal) |
| 7d | `/part` | DELETE | Remove the part. Return `{}, 204` |
| 8a | `/part/legacy` | — | Mark this endpoint as deprecated |
| 8b | `/part/legacy` | GET | Auto-format with the minimal `part_model` |
| 8c | `/part/legacy` | GET | Document the 404 error response |
| 8d | `/part/legacy` | GET | Handle not found — **`api.abort(404, "...")`** |
| 8e | `/part/legacy` | GET | Return the part data |

> **Note:** TODOs 4c, 6c, 7c, 8d each use a **different** error-return pattern by design — see *Error Pattern Practice* below.

---

## Swagger Model Preview

### error_model

Used by: 404 responses (documented for all; actually produced by GET and PUT)

```
Status {
  success*              boolean
                        Operation status

  message*              string
                        Status message
}
```

```json
{ "success": false, "message": "Part SP999 not found" }
```

### part_model

Used by: `/parts` GET (inner) and `/part/legacy` GET (minimal)

```
Part {
  Product Name*         string
                        Unique Product Name in the Stocks

  Unit Price*           float
                        Unit price of the item
}
```

```json
{ "Product Name": "Fan Module", "Unit Price": 250.0 }
```

### parts_model

Used by: `/parts` GET (wraps a list of `part_model`, with example data)

```
Parts {
  parts                 [
                        List of parts

                        Part {
                          Product Name*    string
                          Unit Price*      float
                        }]
}
```

```json
{
  "parts": [
    {"Product Name": "Fan Module", "Unit Price": 250.0},
    {"Product Name": "Power Supply", "Unit Price": 450.0}
  ]
}
```

### part_full_model

Used by: `/part` GET / POST (all fields)

```
PartFull {
  Product Name*         string
                        Unique Product Name in the Stocks

  category              string
  qty                   integer

  Unit Price*           float
                        Unit price of the item
}
```

```json
{
  "Product Name": "Fan Module",
  "category": "cooling",
  "qty": 15,
  "Unit Price": 250.0
}
```

---

## Swagger Response Examples

### GET /parts?category=cooling → 200

```json
{
  "parts": [
    {"Product Name": "Fan Module", "Unit Price": 250.0},
    {"Product Name": "CPU Heatsink", "Unit Price": 85.0}
  ]
}
```

### GET /part?part_id=SP001 → 200

```json
{
  "Product Name": "Fan Module",
  "category": "cooling",
  "qty": 15,
  "Unit Price": 250.0
}
```

### GET /part?part_id=SP999 → 404 *(raise + errorhandler)*

```json
{ "success": false, "message": "Part ID SP999 Not Found" }
```

### PUT /part?part_id=SP999 → 404 *(marshal + error_model)*

```json
{ "success": false, "message": "Part ID SP999 Not Found" }
```

### DELETE /part?part_id=SP999 → 404 *(plain dict — different shape!)*

```json
{ "error": "Part ID SP999 Not Found" }
```

### GET /part/legacy?part_id=SP999 → 404 *(api.abort — Flask-RESTX default)*

```json
{ "message": "Part ID SP999 Not Found" }
```

### GET /part/legacy?part_id=SP001 → 200 (deprecated)

```json
{ "Product Name": "Fan Module", "Unit Price": 250.0 }
```

*Only renamed name/price returned — minimal model filters out category/qty.*

---

## Error Pattern Practice

This challenge deliberately uses **four different** error-return styles. Each suits a different scenario:

| Method | Pattern | When it fits |
|--------|---------|--------------|
| GET `/part` | `raise PartIDNotFound` + `@api.errorhandler` | Method has `@api.marshal_with` — exception bypasses the decorator |
| PUT `/part` | `return marshal({...}, error_model), 404` | No `marshal_with` on method — explicit error formatting |
| DELETE `/part` | `return {"error": "..."}, 404` | Quick + simple, no model enforcement (note: doesn't match `error_model` shape) |
| GET `/part/legacy` | `api.abort(404, "...")` | Built-in helper; raises HTTPException, bypasses `marshal_with` |

Response body shape differs per pattern (Status vs `error` key vs default) — see *Swagger Response Examples* above.

---

## Initial File: p1_e5_flask_spareparts.py

```python
from flask import Flask
from flask_restx import Resource, Api, reqparse, fields, marshal

app = Flask(__name__)
app.config['ERROR_404_HELP'] = False  #! Must come BEFORE Api(app)
api = Api(app)

# Initial inventory
parts_inventory = {
    "SP001": {"name": "Fan Module", "category": "cooling", "qty": 15, "price": 250.00},
    "SP002": {"name": "Power Supply", "category": "power", "qty": 8, "price": 450.00},
    "SP003": {"name": "SFP Transceiver", "category": "networking", "qty": 50, "price": 75.00},
    "SP004": {"name": "Memory Module", "category": "compute", "qty": 20, "price": 320.00},
    "SP005": {"name": "CPU Heatsink", "category": "cooling", "qty": 12, "price": 85.00}
}

# ============================================================
# MODELS
# ============================================================

# Custom exception + handler (used by TODO-4c)
class PartIDNotFound(Exception):
    pass

@api.errorhandler(PartIDNotFound)
def handle_part_not_found(error):
    return {"success": False, "message": error.args[0]}, 404

# TODO-1a: Define a Status model — `success` (Boolean) + `message` (String)


# TODO-1b: Define a minimal part model — rename `name` → "Product Name", `price` → "Unit Price"


# TODO-1c: Define a parts wrapper. Include `example=[...]` with two sample entries


# TODO-1d: Define a full part model — renamed name/price plus `category` and `qty`


# ============================================================
# PARSERS
# ============================================================

# TODO-2a: category parameter with choices
parts_parser = reqparse.RequestParser()


# TODO-2b: part_id parameter
part_parser_get = reqparse.RequestParser()


# TODO-2c: POST parser (inherit from GET, add name/category/qty/price)


# TODO-2d: PUT parser (inherit from POST)


# TODO-2e: DELETE parser (inherit from GET)


# ============================================================
# ENDPOINTS
# ============================================================

@api.route('/parts')
class PartsList(Resource):
    # TODO-3a, 3b
    def get(self):
        pass


@api.route('/part')
class Part(Resource):
    # TODO-4a–4d (GET): use raise + errorhandler
    def get(self):
        pass

    # TODO-5a, 5b (POST): use marshal_with(code=201)
    def post(self):
        pass

    # TODO-6a–6d (PUT): use return marshal + error_model
    def put(self):
        pass

    # TODO-7a–7d (DELETE): use plain dict return
    def delete(self):
        pass


# TODO-8a: mark deprecated
@api.route('/part/legacy')
class PartLegacy(Resource):
    # TODO-8b–8e (GET): use api.abort
    def get(self):
        pass


if __name__ == '__main__':
    app.run(debug=True)
```

---

## Quick Reference

| Concept | Syntax |
|---------|--------|
| Status / error model | `api.model('Status', {'success': fields.Boolean, 'message': fields.String})` |
| Field renaming | `fields.String(attribute='internal_key')` — input key → output key |
| List of nested | `fields.List(fields.Nested(model))` |
| Multiple examples in list | `fields.List(..., example=[{...}, {...}])` |
| Auto marshal (success) | `@api.marshal_with(model)` — **once** per method |
| Override status code | `@api.marshal_with(model, code=201, description='...')` |
| Manual marshal (error) | `return marshal({...}, error_model), 404` |
| Doc-only response | `@api.response(404, 'Not Found', error_model)` |
| Deprecated | `@api.deprecated` placed **below** `@api.route` on the class |
| Parser inheritance | `new_parser = base_parser.copy()` |
| Choices | `choices=('a', 'b', 'all')` |

---

<details>
<summary><strong>📖 Solution (Click to expand)</strong></summary>

```python
from flask import Flask
from flask_restx import Resource, Api, reqparse, fields, marshal

app = Flask(__name__)
app.config['ERROR_404_HELP'] = False  #! Must come BEFORE Api(app)
api = Api(app)

# Initial inventory
parts_inventory = {
    "SP001": {"name": "Fan Module", "category": "cooling", "qty": 15, "price": 250.00},
    "SP002": {"name": "Power Supply", "category": "power", "qty": 8, "price": 450.00},
    "SP003": {"name": "SFP Transceiver", "category": "networking", "qty": 50, "price": 75.00},
    "SP004": {"name": "Memory Module", "category": "compute", "qty": 20, "price": 320.00},
    "SP005": {"name": "CPU Heatsink", "category": "cooling", "qty": 12, "price": 85.00}
}

# ============================================================
# MODELS
# ============================================================

class PartIDNotFound(Exception):
    pass

@api.errorhandler(PartIDNotFound)
def handle_part_not_found(error):
    return {"success": False, "message": error.args[0]}, 404

# TODO-1a
error_model = api.model("Status", {
    "success": fields.Boolean(required=True, description="Operation status"),
    "message": fields.String(required=True, description="Status message")
})

# TODO-1b
part_model = api.model("Part", {
    "Product Name": fields.String(attribute="name", required=True,
                                  description="Unique Product Name in the Stocks"),
    "Unit Price":   fields.Float(attribute="price", required=True,
                                 description="Unit price of the item")
})

# TODO-1c
parts_model = api.model("Parts", {
    "parts": fields.List(
        fields.Nested(part_model),
        example=[
            {"Product Name": "Fan Module",   "Unit Price": 250.0},
            {"Product Name": "Power Supply", "Unit Price": 450.0}
        ]
    )
})

# TODO-1d
part_full_model = api.model("PartFull", {
    "Product Name": fields.String(attribute="name", required=True,
                                  description="Unique Product Name in the Stocks"),
    "category":     fields.String,
    "qty":          fields.Integer,
    "Unit Price":   fields.Float(attribute="price", required=True,
                                 description="Unit price of the item")
})

# ============================================================
# PARSERS
# ============================================================

# TODO-2a
parts_parser = reqparse.RequestParser()
parts_parser.add_argument('category',
    choices=('cooling', 'power', 'networking', 'compute', 'all'))

# TODO-2b
part_parser_get = reqparse.RequestParser()
part_parser_get.add_argument('part_id', type=str)

# TODO-2c
part_parser_post = part_parser_get.copy()
part_parser_post.add_argument('name', type=str)
part_parser_post.add_argument('category', type=str)
part_parser_post.add_argument('qty', type=int)
part_parser_post.add_argument('price', type=float)

# TODO-2d
part_parser_put = part_parser_post.copy()

# TODO-2e
part_parser_delete = part_parser_get.copy()

# ============================================================
# ENDPOINTS
# ============================================================

@api.route('/parts')
class PartsList(Resource):

    @api.marshal_with(parts_model)               # TODO-3a
    @api.expect(parts_parser)
    def get(self):
        args = parts_parser.parse_args()
        # TODO-3b
        if args.category == 'all' or args.category is None:
            data = list(parts_inventory.values())
        else:
            data = [v for v in parts_inventory.values()
                    if args.category == v['category']]
        return {'parts': data}


@api.route('/part')
class Part(Resource):

    @api.marshal_with(part_full_model)               # TODO-4a
    @api.response(404, 'Not Found', error_model)     # TODO-4b
    @api.expect(part_parser_get)
    def get(self):
        args = part_parser_get.parse_args()
        # TODO-4c — raise + errorhandler
        if args.part_id not in parts_inventory:
            raise PartIDNotFound(f"Part ID {args.part_id} Not Found")
        # TODO-4d
        return parts_inventory[args.part_id]

    # TODO-5a — marshal_with overrides the documented status code
    @api.marshal_with(part_full_model, code=201, description="Successfully Created")
    @api.expect(part_parser_post)
    def post(self):
        args = part_parser_post.parse_args()
        # TODO-5b
        parts_inventory[args.part_id] = {
            "name": args.name, "category": args.category,
            "qty": args.qty,   "price": args.price
        }
        return parts_inventory[args.part_id], 201

    @api.response(204, "Successfully updated")       # TODO-6a
    @api.response(404, "Not Found", error_model)     # TODO-6b
    @api.expect(part_parser_put)
    def put(self):
        args = part_parser_put.parse_args()
        # TODO-6c — return marshal + error_model
        if args.part_id not in parts_inventory:
            return marshal(
                {"success": False, "message": f"Part ID {args.part_id} Not Found"},
                error_model), 404
        # TODO-6d
        parts_inventory[args.part_id] = {
            "name": args.name, "category": args.category,
            "qty": args.qty,   "price": args.price
        }
        return {}, 204

    @api.response(204, "Successfully deleted")       # TODO-7a
    @api.response(404, "Not Found", error_model)     # TODO-7b
    @api.expect(part_parser_delete)
    def delete(self):
        args = part_parser_delete.parse_args()
        # TODO-7c — plain dict (intentionally different shape)
        if args.part_id not in parts_inventory:
            return {"error": f"Part ID {args.part_id} Not Found"}, 404
        # TODO-7d
        parts_inventory.pop(args.part_id)
        return {}, 204


# TODO-8a
@api.route('/part/legacy')
@api.deprecated
class PartLegacy(Resource):

    @api.marshal_with(part_model)                    # TODO-8b
    @api.response(404, "Not Found", error_model)     # TODO-8c
    @api.expect(part_parser_get)
    def get(self):
        args = part_parser_get.parse_args()
        # TODO-8d — api.abort
        if args.part_id not in parts_inventory:
            api.abort(404, f"Part ID {args.part_id} Not Found")
        # TODO-8e
        return parts_inventory[args.part_id], 200


if __name__ == '__main__':
    app.run(debug=True)
```

</details>

---

<details>
<summary><strong>🧪 Test Script (Click to expand)</strong></summary>

Save as `test_e5.py` and run:

```bash
uv pip install requests          # one-time
python test_e5.py p5_flask_spareparts.py
```

The script spawns the solution as a subprocess, waits for Flask to come up on `127.0.0.1:5000`, exercises every TODO via HTTP (including the four error patterns and the `deprecated` flag in `swagger.json`), and tears the server down cleanly. Exits `0` on all-pass, `1` on any failure.

```python
#!/usr/bin/env python3
"""
Test runner for the e5 Spare Parts Flask-RESTX challenge.

Usage:
    python test_e5.py <path-to-solution.py>
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed.  Run: uv pip install requests")

BASE_URL = "http://127.0.0.1:5000"
STARTUP_TIMEOUT_S = 10
REQUEST_TIMEOUT_S = 5


class C:
    G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"
    BOLD = "\033[1m"; DIM = "\033[2m"; X = "\033[0m"


results = {"pass": 0, "fail": 0}


def section(title):
    print(f"\n{C.BOLD}{C.B}━━━ {title} ━━━{C.X}")


def ok(msg):
    results["pass"] += 1
    print(f"  {C.G}✓{C.X} {msg}")


def bad(msg, expected=None, actual=None):
    results["fail"] += 1
    print(f"  {C.R}✗ {msg}{C.X}")
    if expected is not None:
        print(f"    {C.DIM}expected:{C.X} {expected}")
    if actual is not None:
        print(f"    {C.DIM}actual:  {C.X} {actual}")


def start_server(script_path: Path) -> subprocess.Popen:
    print(f"{C.B}Starting {script_path}…{C.X}")
    proc = subprocess.Popen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    deadline = time.time() + STARTUP_TIMEOUT_S
    while time.time() < deadline:
        if proc.poll() is not None:
            out, err = proc.communicate(timeout=1)
            sys.exit(
                f"{C.R}Server exited early.{C.X}\n"
                f"STDOUT:\n{out.decode(errors='replace')}\n"
                f"STDERR:\n{err.decode(errors='replace')}"
            )
        try:
            requests.get(f"{BASE_URL}/parts", timeout=0.5)
            print(f"{C.G}Server is up.{C.X}")
            return proc
        except requests.RequestException:
            time.sleep(0.3)
    proc.terminate()
    sys.exit(f"{C.R}Server failed to come up within {STARTUP_TIMEOUT_S}s.{C.X}")


def stop_server(proc: subprocess.Popen):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def call(method, path):
    try:
        r = requests.request(method, f"{BASE_URL}{path}", timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException as e:
        return None, str(e)
    try:
        body = r.json() if r.text else {}
    except ValueError:
        body = r.text
    return r.status_code, body


def expect_status(label, method, path, want):
    status, body = call(method, path)
    if status == want:
        ok(f"{label}: {method} {path} → {want}")
    else:
        bad(f"{label}: {method} {path}",
            f"status {want}", f"status {status} body={body!r:.200}")
    return status, body


def run_tests():
    # TODO 3a, 3b
    section("TODO 3a, 3b — GET /parts (parts_model, category filter)")
    _, body = expect_status("3a/3b no filter", "GET", "/parts", 200)
    if isinstance(body, dict) and "parts" in body:
        ok("response shape is {'parts': [...]}")
        parts = body["parts"]
        if len(parts) == 5:
            ok("returns all 5 initial parts")
        else:
            bad("parts count", 5, len(parts))
        first = parts[0] if parts else {}
        if "Product Name" in first and "Unit Price" in first:
            ok("uses renamed fields 'Product Name' + 'Unit Price'")
        else:
            bad("renamed fields", "{'Product Name','Unit Price'}", list(first.keys()))
        if "category" not in first and "qty" not in first:
            ok("part_model filtered out 'category' and 'qty'")

    _, body = expect_status("3b cooling filter", "GET", "/parts?category=cooling", 200)
    if isinstance(body, dict) and len(body.get("parts", [])) == 2:
        ok("cooling filter returns 2 parts (SP001, SP005)")

    _, body = expect_status("3b category=all", "GET", "/parts?category=all", 200)
    if isinstance(body, dict) and len(body.get("parts", [])) == 5:
        ok("category=all returns all 5 parts")

    expect_status("2a choices validation", "GET", "/parts?category=invalid", 400)

    # TODO 4
    section("TODO 4a–4d — GET /part (part_full_model, raise + errorhandler)")
    _, body = expect_status("4a/4d existing", "GET", "/part?part_id=SP001", 200)
    if isinstance(body, dict):
        wanted = {"Product Name", "Unit Price", "category", "qty"}
        if wanted.issubset(body.keys()):
            ok("part_full_model returns all 4 fields")
        else:
            bad("part_full_model fields", wanted, set(body.keys()))

    _, body = expect_status("4b/4c missing → 404", "GET", "/part?part_id=SP999", 404)
    if isinstance(body, dict):
        if body.get("success") is False and "message" in body:
            ok("errorhandler returns {success:false, message:...}")
        else:
            bad("error body", "{success:false, message:'...'}", body)

    # TODO 5
    section("TODO 5a, 5b — POST /part (@api.marshal_with code=201)")
    _, body = expect_status("5a/5b create", "POST",
        "/part?part_id=SP010&name=Test+Part&category=compute&qty=5&price=99.99", 201)
    if isinstance(body, dict) and body.get("Product Name") == "Test Part":
        ok("response body marshalled with renamed fields")

    _, body = call("GET", "/part?part_id=SP010")
    if isinstance(body, dict) and body.get("Product Name") == "Test Part":
        ok("POST persisted into inventory")

    # TODO 6
    section("TODO 6a–6d — PUT /part (return marshal + error_model)")
    expect_status("6a/6d update", "PUT",
        "/part?part_id=SP001&name=Updated+Fan&category=cooling&qty=20&price=300", 204)
    _, body = call("GET", "/part?part_id=SP001")
    if isinstance(body, dict) and body.get("Product Name") == "Updated Fan":
        ok("PUT update persisted")

    _, body = expect_status("6b/6c missing → 404", "PUT",
        "/part?part_id=SP999&name=x&category=cooling&qty=1&price=1", 404)
    if isinstance(body, dict):
        if body.get("success") is False and "message" in body:
            ok("marshal + error_model → {success:false, message:...}")

    # TODO 7
    section("TODO 7a–7d — DELETE /part (plain dict error)")
    expect_status("7a/7d delete", "DELETE", "/part?part_id=SP002", 204)
    expect_status("delete persisted", "GET", "/part?part_id=SP002", 404)

    _, body = expect_status("7b/7c missing → 404", "DELETE", "/part?part_id=SP999", 404)
    if isinstance(body, dict) and "error" in body:
        ok("plain dict pattern uses 'error' key")

    # TODO 8
    section("TODO 8a–8e — GET /part/legacy (deprecated, api.abort)")
    _, body = expect_status("8b/8e existing", "GET", "/part/legacy?part_id=SP003", 200)
    if isinstance(body, dict):
        if "Product Name" in body and "Unit Price" in body:
            ok("part_model returns renamed fields")
        if "category" not in body and "qty" not in body:
            ok("part_model filtered out category/qty")

    _, body = expect_status("8c/8d missing → abort 404", "GET",
        "/part/legacy?part_id=SP999", 404)
    if isinstance(body, dict) and "message" in body:
        ok("api.abort returns Flask-RESTX default {'message': '...'}")

    # TODO 8a in swagger.json
    section("TODO 8a — deprecated flag in swagger.json")
    try:
        r = requests.get(f"{BASE_URL}/swagger.json", timeout=REQUEST_TIMEOUT_S)
        if r.status_code == 200:
            spec = r.json()
            legacy = spec.get("paths", {}).get("/part/legacy", {})
            if legacy.get("get", {}).get("deprecated") is True:
                ok("/part/legacy GET marked deprecated:true")
            else:
                bad("deprecated flag", True, legacy.get("get", {}).get("deprecated"))
    except Exception as e:
        bad("swagger.json fetch", "available", str(e))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", help="Path to solution .py file")
    args = ap.parse_args()

    script = Path(args.script).resolve()
    if not script.exists():
        sys.exit(f"{C.R}Script not found: {script}{C.X}")

    proc = start_server(script)
    try:
        run_tests()
    finally:
        stop_server(proc)

    total = results["pass"] + results["fail"]
    print(f"\n{C.BOLD}{'━' * 60}{C.X}")
    if results["fail"] == 0:
        print(f"{C.G}{C.BOLD}All {total} checks passed.{C.X}")
        sys.exit(0)
    else:
        pct = (results["pass"] / total * 100) if total else 0
        print(f"{C.Y}{C.BOLD}Results: {results['pass']}/{total} passed "
              f"({pct:.0f}%) — {results['fail']} failure(s){C.X}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Coverage map:**

| TODO | Tested by |
|------|-----------|
| 1a–1d (models) | Indirectly via response shape (renamed fields, filtering) |
| 2a (choices) | `?category=invalid` → 400 |
| 3a/3b | `/parts` full / cooling / all filters |
| 4a–4d | Success body, 404 via `raise` → `{success:false, message:...}` |
| 5a/5b | POST 201 + marshalled body, persistence check |
| 6a–6d | PUT 204, persistence check, 404 via `marshal(error_model)` |
| 7a–7d | DELETE 204, gone check, 404 plain dict with `error` key |
| 8a | `swagger.json` → `deprecated: true` on `/part/legacy` GET |
| 8b–8e | Minimal `part_model` filtering, `api.abort` produces `{message:...}` |

</details>