---
tags: [odoo, odoo17, orm, core]
---

# BaseModel — ORM Foundation

**File:** `odoo/odoo/models.py`

All Odoo models inherit from `BaseModel`. It provides the ORM layer over PostgreSQL.

## Model Definition

```python
from odoo import models

class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model'
    _order = 'name asc'
    _inherit = 'mail.thread'  # optional mixin
```

## Key Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `_name` | str | required | Unique model identifier |
| `_description` | str | None | Human-readable name |
| `_order` | str | `'id'` | Default ordering |
| `_inherit` | str/list | None | Parent model(s) to extend |
| `_inherits` | dict | None | Delegation inheritance |
| `_rec_name` | str | `'name'` | Field used for display name |
| `_table` | str | computed | SQL table name |
| `_sql_constraints` | list | [] | SQL constraints |

## CRUD Methods

| Method | Description |
|--------|-------------|
| `search(domain)` | Returns recordset matching domain |
| `browse(ids)` | Returns recordset for given IDs |
| `create(vals)` | Creates new record, returns it |
| `write(vals)` | Updates matching records |
| `unlink()` | Deletes matching records |
| `read(fields)` | Reads field values |
| `mapped(func)` | Applies function to all records |
| `filtered(func)` | Filters recordset |
| `sorted(key)` | Sorts recordset |

## API Decorators

- `@api.model` — No active record, runs as superuser
- `@api.depends(*fields)` — Triggers recompute on change
- `@api.onchange(*fields)` — Dynamic form behavior
- `@api.constrains(*fields)` — Validation on write/create
- `@api.returns('model')` — Returns model or id+model pair

## See Also
- [Core/API](Core/API.md) — Decorator details
- [Core/Fields](Core/Fields.md) — Field types
- [Tools/ORM Operations](Tools/ORM-Operations.md) — Domain operators
- [Patterns/Inheritance Patterns](Patterns/Inheritance-Patterns.md) — _inherit vs _inherits
