# Challenge 103: Spare Parts API (Exam Version)

## Tasks

### Models

| TODO | Model Name | Task |
|------|------------|------|
| 1a | `error_model` | Define a model for error responses — see Swagger preview below |
| 1b | `part_model` | Define a minimal part model — see Swagger preview below |
| 1c | `parts_model` | Define a model that wraps a collection of parts — see Swagger preview below |
| 1d | `part_full_model` | Define a complete part model with all fields — see Swagger preview below |

### Parsers

| TODO | Endpoint | Task |
|------|----------|------|
| 2a | `/parts` | Add a category parameter that restricts input to valid categories: `cooling`, `power`, `networking`, `compute`, `all` |
| 2b | `/part` | Add a part identifier parameter `part_id` as string |
| 2c | `/part` | Build a POST parser that reuses the GET parser and adds fields for part creation: `name`, `category`, `qty`, `price` |
| 2d | `/part` | Build a PUT parser that reuses an existing parser |
| 2e | `/part` | Build a DELETE parser that reuses an existing parser |

### Endpoints — Decorators & Logic

| TODO | Endpoint | Method | Task |
|------|----------|--------|------|
| 3a | `/parts` | GET | Auto-format the response using `parts_model` |
| 3b | `/parts` | GET | Filter by category using dict comprehension. Return all if `category=all` or not provided. Return value must match the `parts_model` shape `{'parts': data}` |
| 4a | `/part` | GET | Auto-format the success response using `part_full_model` |
| 4b | `/part` | GET | Document the 404 error response in Swagger |
| 4c | `/part` | GET | Handle part not found — return formatted error with 404 |
| 4d | `/part` | GET | Return the matching part |
| 5a | `/part` | POST | Document the 201 success response in Swagger |
| 5b | `/part` | POST | Store the new part in inventory. Return `{}, 201` |
| 6a | `/part` | PUT | Document the 200 PUT success response in Swagger |
| 6b | `/part` | PUT | Document the 404 error response in Swagger |
| 6c | `/part` | PUT | Handle part not found — return formatted error |
| 6d | `/part` | PUT | Update the existing part with new values. Return `{}, 200` |
| 7a | `/part` | DELETE | Document the 204 success response in Swagger |
| 7b | `/part` | DELETE | Document the 404 error response in Swagger |
| 7c | `/part` | DELETE | Handle part not found — return formatted error |
| 7d | `/part` | DELETE | Remove the part from inventory. Return `{}, 204` |
| 8a | `/part/legacy` | — | Mark this endpoint as deprecated in Swagger |
| 8b | `/part/legacy` | GET | Auto-format the response using the minimal `part_model` |
| 8c | `/part/legacy` | GET | Document the 404 error response in Swagger |
| 8d | `/part/legacy` | GET | Handle part not found — return formatted error |
| 8e | `/part/legacy` | GET | Return the part data |

---

## Swagger Model Preview

### error_model

Used by: all 404 responses

```
Error {
  message               string
                        Error message
}
```

```json
{
  "message": "Part SP999 not found"
}
```

### part_model

Used by: `/part/legacy` GET (minimal — only name and price)

```
Part {
  Product Name*         string
                        Unique Product Name in the Stocks

  Unit Price*           float
                        Unit price of the item
}
```

```json
{
  "Product Name": "Fan Module",
  "Unit Price": 250.0
}
```

### parts_model

Used by: `/parts` GET (wraps a list of `part_model`)

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

Used by: `/part` GET (all fields)

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
    {"name": "Fan Module", "price": 250.0},
    {"name": "CPU Heatsink", "price": 85.0}
  ]
}
```

### GET /part?part_id=SP001 → 200

```json
{
  "name": "Fan Module",
  "category": "cooling",
  "qty": 15,
  "price": 250.0
}
```

### GET /part?part_id=SP999 → 404

```json
{
  "message": "Part SP999 not found"
}
```

### GET /part/legacy?part_id=SP001 (deprecated) → 200

```json
{
  "name": "Fan Module",
  "price": 250.0
}
```

*Note: Only name/price returned — model filters out category/qty*

---

## Initial File: p1_e5_flask_spareparts.py

```python
from flask import Flask
from flask_restx import Resource, Api, reqparse, fields, marshal

app = Flask(__name__)
app.config['ERROR_404_HELP'] = False #! Added for errorhandler
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
# Define exception (before endpoints)
class PartIDNotFound(Exception):
    pass
# Register error handler (before endpoints)
#** Without an error handler, this just returns a generic 500 Internal Server Error. You #** need to register a handler.
@api.errorhandler(PartIDNotFound)       #! Added for errorhandler
def handle_part_not_found(error):
    return {"message": error.args[0]}, 404

# TODO-1a: Define a model for error responses (see Swagger preview) with "error" as attribute


# TODO-1b: Define a minimal part model (see Swagger preview)


# TODO-1c: Define a model that wraps a collection of parts (see Swagger preview)


# TODO-1d: Define a complete part model with all fields (see Swagger preview)


# ============================================================
# PARSERS
# ============================================================

# TODO-2a: Add a category parameter that restricts input to valid categories 'cooling', 'power', 'networking', 'compute', 'all'
parts_parser = reqparse.RequestParser()


# TODO-2b: Add a part identifier parameter part_id as string
part_parser_get = reqparse.RequestParser()


# TODO-2c: Build a POST parser that reuses the GET parser and adds fields for part creation name, category, qty, price


# TODO-2d: Build a PUT parser that reuses an existing POST parser 


# TODO-2e: Build a DELETE parser that reuses an existing GET parser


# ============================================================
# ENDPOINTS
# ============================================================

@api.route('/parts')
class PartsList(Resource):
    
    # TODO-3a: Auto-format the response using parts_model
    @api.expect(parts_parser)
    def get(self):
        args = parts_parser.parse_args()
        
        # TODO-3b: Filter by category using dict comprehension. Return all if category=all or not provided
        #          Return value must match the parts_model shape {'parts': data}
        return {}


@api.route('/part')
class Part(Resource):
    
    # TODO-4a: Auto-format the success response using part_full_model
    # TODO-4b: Document the 404 error response in Swagger with error_model
    @api.expect(part_parser_get)
    def get(self):
        args = part_parser_get.parse_args()
        
        # TODO-4c: Handle part not found — raise PartIDNotFound error with 404
        """
        Response body
            {
            "message": "Part ID AP001 Not Found"
            }
        """
        
        # TODO-4d: Return the matching part
        return {}
    
    # TODO-5a: Document the 201 success response in Swagger with returned data as part_full_model
    # TODO-5a: with description "Successfully created"
    @api.expect(part_parser_post)
    def post(self):
        args = part_parser_post.parse_args()
        
        # TODO-5b: Store the new part in inventory. Return {}, 201
        return {}
    
    # TODO-6a: Document the 204 PUT success response in Swagger
    # TODO-6b: Document the 404 error response in Swagger with error_model
    @api.expect(part_parser_put)
    def put(self):
        args = part_parser_put.parse_args()
        
        # TODO-6c: Handle part not found — return formatted error using error_model with 404
        
        # TODO-6d: Update the existing part with new values. Return {}, 204
        return {}
    
    # TODO-7a: Document the 204 success response in Swagger
    # TODO-7b: Document the 404 error response in Swagger with error_model
    @api.expect(part_parser_delete)
    def delete(self):
        args = part_parser_delete.parse_args()
        
        # TODO-7c: Handle part not found — return formatted error  with 404
        if args.part_id not in parts_inventory:
            return {"error": f"Part ID {args.part_id} Not Found"},
        
        # TODO-7d: Remove the part from inventory. Return {}, 204
        return {}


# ============================================================
# DEPRECATED ENDPOINT
# ============================================================

# TODO-8a: Mark this endpoint as deprecated in Swagger
@api.route('/part/legacy')
class PartLegacy(Resource):
    
    # TODO-8b: Auto-format the response using the minimal part_model
    # TODO-8c: Document the 404 error response in Swagger with error_model
    @api.expect(part_parser_get)
    def get(self):
        args = part_parser_get.parse_args()
        
        # TODO-8d: Handle part not found — return formatted error using api.abort
        """
        Response body
            {
            "message": "Part ID AP001 Not Found"
            }
        """
        
        # TODO-8e: Return the part data
        return {}


if __name__ == '__main__':
    app.run(debug=True)
```

---

## Quick Reference

| Concept | Syntax |
|---------|--------|
| Error model | `api.model('Error', {'message': fields.String})` |
| List of nested | `fields.List(fields.Nested(model))` |
| Auto marshal (success) | `@api.marshal_with(model)` — default code=200, can only use **once** per method |
| Manual marshal (error) | `return marshal({'error': '...'}, error_model), 404` |
| Response doc only | `@api.response(404, 'Not found', error_model)` — Swagger docs only, no formatting |
| Deprecated | `@api.deprecated` on **class** (not method) |
| Parser inheritance | `new_parser = base_parser.copy()` |
| Choices | `choices=('cooling', 'power', 'all')` |

---

<details>
<summary><strong>📖 Solution (Click to expand)</strong></summary>

```python
from flask import Flask
from flask_restx import Resource, Api, reqparse, fields, marshal

app = Flask(__name__)
app.config['ERROR_404_HELP'] = False #! Added for errorhandler
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
# Define exception (before endpoints)
class PartIDNotFound(Exception):
    pass
# Register error handler (before endpoints)
#** Without an error handler, this just returns a generic 500 Internal Server Error. You #** need to register a handler.
@api.errorhandler(PartIDNotFound)       #! Added for errorhandler
def handle_part_not_found(error):
    return {"message": error.args[0]}, 404

# TODO-1a: Define a model for error responses (see Swagger preview) with "error" as attribute
error_model=api.model("Error",
                    {
                        "message": fields.String(attribute="error", description="Error message")
                    })

# TODO-1b: Define a minimal part model (see Swagger preview)
part_model=api.model("Part",
                    {
                        "Product Name": fields.String(attribute="name", required=True, description="Unique Product Name in the Stocks"),
                        "Unit Price": fields.Float(attribute="price", required=True, description="Unit price of the item")
                    })

# TODO-1c: Define a model that wraps a collection of parts (see Swagger preview)
parts_model=api.model("Parts",
                    {
                        "parts":fields.List(fields.Nested(part_model))
                    })

# TODO-1d: Define a complete part model with all fields (see Swagger preview)
part_full_model=api.model("PartFull",
                        {
                            "Product Name": fields.String(attribute="name", required=True, description="Unique Product Name in the Stocks"),
                            "category": fields.String,
                            "qty": fields.Integer,
                            "Unit Price": fields.Float(attribute="price", required=True, description="Unit price of the item")
                        })

# ============================================================
# PARSERS
# ============================================================

# TODO-2a: Add a category parameter that restricts input to valid categories 'cooling', 'power', 'networking', 'compute', 'all'
parts_parser = reqparse.RequestParser()
parts_parser.add_argument('category', choices=('cooling', 'power', 'networking', 'compute', 'all'))

# TODO-2b: Add a part identifier parameter part_id as string
part_parser_get = reqparse.RequestParser()
part_parser_get.add_argument('part_id', type=str)

# TODO-2c: Build a POST parser that reuses the GET parser and adds fields for part creation name, category, qty, price
part_parser_post=part_parser_get.copy()
part_parser_post.add_argument('name', type=str)
part_parser_post.add_argument('category', type=str)
part_parser_post.add_argument('qty', type=int)
part_parser_post.add_argument('price', type=float)

# TODO-2d: Build a PUT parser that reuses an existing POST parser 
part_parser_put=part_parser_post.copy()

# TODO-2e: Build a DELETE parser that reuses an existing GET parser
part_parser_delete=part_parser_get.copy()

# ============================================================
# ENDPOINTS
# ============================================================

@api.route('/parts')
class PartsList(Resource):
    
    # TODO-3a: Auto-format the response using parts_model
    @api.marshal_with(parts_model)
    @api.expect(parts_parser)
    def get(self):
        args = parts_parser.parse_args()
        
        # TODO-3b: Filter by category using dict comprehension. Return all if category=all or not provided
        #          Return value must match the parts_model shape {'parts': data}
        if args.category=='all' or args.category is None:
            data=list(parts_inventory.values())
        else:
            data=[v for v in parts_inventory.values() if args.category==v['category']]
        return {'parts': data}


@api.route('/part')
class Part(Resource):
    
    # TODO-4a: Auto-format the success response using part_full_model
    @api.marshal_with(part_full_model)
    # TODO-4b: Document the 404 error response in Swagger with error_model
    @api.response(404, 'Not Found', error_model)
    @api.expect(part_parser_get)
    def get(self):
        args = part_parser_get.parse_args()
        
        # TODO-4c: Handle part not found — raise PartIDNotFound error with 404
        """
        Response body
            {
            "message": "Part ID AP001 Not Found"
            }
        """
        if args.part_id not in parts_inventory:
            raise PartIDNotFound(f"Part ID {args.part_id} Not Found")
        # TODO-4d: Return the matching part
        return parts_inventory[args.part_id]
    
    # TODO-5a: Document the 201 success response in Swagger with returned data as part_full_model
    # TODO-5a: with description "Successfully created"
    @api.marshal_with(part_full_model, code=201, description="Successfully Created")
    @api.expect(part_parser_post)
    def post(self):
        args = part_parser_post.parse_args()
        
        # TODO-5b: Store the new part in inventory. Return {}, 201
        parts_inventory[args.part_id]={
            "name": args.name,
            "category": args.category,
            "qty": args.qty,
            "price": args.price
        }
        return parts_inventory[args.part_id], 201
    
    # TODO-6a: Document the 204 PUT success response in Swagger
    @api.response(204, "Sucessfully updated")
    # TODO-6b: Document the 404 error response in Swagger with error_model
    @api.response(404, "Not Found", error_model)
    @api.expect(part_parser_put)
    def put(self):
        args = part_parser_put.parse_args()
        
        # TODO-6c: Handle part not found — return formatted error using error_model with 404
        if args.part_id not in parts_inventory:
            return marshal({"error": f"Part ID {args.part_id} Not Found"}, error_model), 404
        
        # TODO-6d: Update the existing part with new values. Return {}, 204
        parts_inventory[args.part_id]={
            "name": args.name,
            "category": args.category,
            "qty": args.qty,
            "price": args.price
        }
        return {}, 204
    
    # TODO-7a: Document the 204 success response in Swagger
    @api.response(204, "Successfully deleted")
    # TODO-7b: Document the 404 error response in Swagger with error_model
    @api.response(404, "Not Found", error_model)
    @api.expect(part_parser_delete)
    def delete(self):
        args = part_parser_delete.parse_args()
        
        # TODO-7c: Handle part not found — return formatted error  with 404
        if args.part_id not in parts_inventory:
            return {"error": f"Part ID {args.part_id} Not Found"}, 
        
        # TODO-7d: Remove the part from inventory. Return {}, 204
        parts_inventory.pop(args.part_id)
        return {}, 204


# ============================================================
# DEPRECATED ENDPOINT
# ============================================================

# TODO-8a: Mark this endpoint as deprecated in Swagger
@api.route('/part/legacy')
@api.deprecated
class PartLegacy(Resource):
    
    # TODO-8b: Auto-format the response using the minimal part_model
    @api.marshal_with(part_model)
    # TODO-8c: Document the 404 error response in Swagger with error_model
    @api.response(404, "Not Found", error_model)
    @api.expect(part_parser_get)
    def get(self):
        args = part_parser_get.parse_args()
        
        # TODO-8d: Handle part not found — return formatted error using api.abort
        """
        Response body
            {
            "message": "Part ID AP001 Not Found"
            }
        """
        if args.part_id not in parts_inventory:
            api.abort(404, f"Part ID {args.part_id} Not Found")
        # TODO-8e: Return the part data
        return parts_inventory[args.part_id], 200


if __name__ == '__main__':
    app.run(debug=True)
```

</details>