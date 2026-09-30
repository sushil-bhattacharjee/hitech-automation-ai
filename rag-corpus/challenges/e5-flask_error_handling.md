# Flask-RESTX Error Handling

## When to Use What

| Situation | Use |
|-----------|-----|
| No `@api.marshal_with` on the method (POST/PUT/DELETE) | `return marshal({...}, error_model), 404` |
| GET with `@api.marshal_with`, quick solution | `api.abort(404, "...")` |
| GET with `@api.marshal_with`, needs `raise` | Custom exception + `@api.errorhandler` |

---

## The Problem

When `@api.marshal_with` is on a method, it reformats **every** return — including error responses.

```python
@api.marshal_with(part_full_model)
@api.response(404, "Not Found", error_model)
def get(self):
    if args.part_id not in parts_inventory:
        return marshal({"error": "Part ID SP001 Not Found"}, error_model), 404
    return parts_inventory[args.part_id]
```

### What You Expect

```json
{"message": "Part ID SP001 Not Found"}
```

### What You Actually Get

```json
{"name": null, "category": null, "qty": null, "price": null}
```

### Why?

```
Step 1: marshal() runs correctly
        {"error": "Part ID SP001 Not Found"} → {"message": "Part ID SP001 Not Found"}

Step 2: @api.marshal_with(part_full_model) intercepts the output
        It sees: {"message": "Part ID SP001 Not Found"}
        It applies part_full_model which expects: name, category, qty, price
        None of those keys exist → all become null

Step 3: Final output
        {"name": null, "category": null, "qty": null, "price": null}
```

The 404 status code still comes through, but the body is wrong.

---

## Three Solutions

### 1. `marshal()` Pattern (Training Materials)

```python
@api.marshal_with(part_full_model)
@api.response(404, "Not Found", error_model)
def get(self):
    if args.part_id not in parts_inventory:
        return marshal({"error": "Not Found"}, error_model), 404
    return parts_inventory[args.part_id]
```

- ✅ Swagger docs show correct 404 shape
- ✅ Status code 404 works
- ❌ Error body gets overwritten by `@api.marshal_with`
- Used by: exam training materials

---

### 2. `api.abort()` 

```python
@api.marshal_with(part_full_model)
@api.response(404, "Not Found", error_model)
def get(self):
    if args.part_id not in parts_inventory:
        api.abort(404, f"Part ID {args.part_id} Not Found")
    return parts_inventory[args.part_id]
```

Returns:

```json
{"message": "Part ID SP001 Not Found"}
```

- ✅ Correct error body
- ✅ Bypasses `@api.marshal_with`
- ✅ Status code 404 works
- ❌ Doesn't use your `error_model`
- ❌ `@api.response(404, ..., error_model)` is Swagger docs only

---

### 3. Custom Exception + `@api.errorhandler` (Cleanest)

```python
# Define exception
class PartIDNotFound(Exception):
    pass

# Register handler — sits OUTSIDE the class, so @api.marshal_with never touches it
@api.errorhandler(PartIDNotFound)
def handle_part_not_found(error):
    return {"message": error.args[0]}, 404
```

```python
@api.marshal_with(part_full_model)
@api.response(404, "Not Found", error_model)
def get(self):
    if args.part_id not in parts_inventory:
        raise PartIDNotFound(f"Part ID {args.part_id} Not Found")
    return parts_inventory[args.part_id]
```

Returns:

```json
{"message": "Part ID SP001 Not Found"}
```

- ✅ Correct error body
- ✅ Bypasses `@api.marshal_with`
- ✅ Status code 404 works
- ✅ Reusable across multiple endpoints
- ❌ Without the handler, raises a generic 500 Internal Server Error

This is what Challenge 102 uses with `CertificationNotFound`.

---

## `app.config['ERROR_404_HELP'] = False`

Flask-RESTX appends URI suggestions to 404 error messages by default:

```json
{"message": "Part ID SP008 Not Found. You have requested this URI [/part] but did you mean /part or /parts ?"}
```

To suppress this, add **before** `Api(app)`:

```python
app = Flask(__name__)
app.config['ERROR_404_HELP'] = False    # Must be BEFORE Api(app)
api = Api(app)
```

After fix:

```json
{"message": "Part ID SP008 Not Found"}
```

---

## `@api.response()` vs `@api.marshal_with()`

```python
@api.marshal_with(part_full_model)     # Formats ALL returns from this method
@api.response(404, "Not Found", error_model)  # Swagger docs ONLY — no runtime effect
```

- `@api.marshal_with` — auto-formats response, can only use **once** per method
- `@api.response` — documentation only, does NOT format anything

---

## Quick Reference

| Pattern | Error Body Correct? | Bypasses marshal_with? | Uses error_model? |
|---------|---------------------|------------------------|-------------------|
| `marshal() + error_model` | ❌ Overwritten | ❌ No | ✅ Yes |
| `api.abort(404, "...")` | ✅ Yes | ✅ Yes | ❌ No |
| `raise Exception + errorhandler` | ✅ Yes | ✅ Yes | ❌ No (manual format) |

---

## Complete Example

```python
from flask import Flask
from flask_restx import Resource, Api, reqparse, fields, marshal

app = Flask(__name__)
app.config['ERROR_404_HELP'] = False
api = Api(app)

# Exception
class PartIDNotFound(Exception):
    pass

# Error handler — bypasses @api.marshal_with
@api.errorhandler(PartIDNotFound)
def handle_part_not_found(error):
    return {"message": error.args[0]}, 404

# Models
error_model = api.model('Error', {
    'message': fields.String(attribute='error', description='Error message')
})

part_full_model = api.model('PartFull', {
    'name': fields.String,
    'category': fields.String,
    'qty': fields.Integer,
    'price': fields.Float
})

# Parser
part_parser_get = reqparse.RequestParser()
part_parser_get.add_argument('part_id', type=str)

# Data
parts_inventory = {
    "SP001": {"name": "Fan Module", "category": "cooling", "qty": 15, "price": 250.00}
}

@api.route('/part')
class Part(Resource):

    @api.marshal_with(part_full_model)
    @api.response(404, "Not Found", error_model)
    @api.expect(part_parser_get)
    def get(self):
        args = part_parser_get.parse_args()

        if args.part_id not in parts_inventory:
            raise PartIDNotFound(f"Part ID {args.part_id} Not Found")

        return parts_inventory[args.part_id]


if __name__ == '__main__':
    app.run(debug=True)
```