---
type: core
name: BaseModel
version: Odoo 18
tags: [core, orm, base]
source: ~/odoo/odoo18/odoo/odoo/models.py
---

# BaseModel

Base class for all Odoo models. All `osv.Model` subclasses inherit from this.

## Key Attributes

```python
class BaseModel(models.Model):
    _name: str          # Internal model name (e.g., 'sale.order')
    _inherit: str|list  # Parent model(s) to inherit from
    _description: str  # Human-readable model name
    _order: str         # Default ordering (e.g., 'date_order desc, id desc')
    _rec_name: str      # Field to use for display name (default: 'name')
    _table: str         # SQL table name (auto-derived from _name)
    _sql_constraints: list  # SQL-level constraints
    _depends: dict     # Dependencies on other models (field triggers)
    _inherits: dict     # Delegation inheritance: {'parent.model': 'field_name'}
```

## Lifecycle Hooks

| Method | When Called |
|--------|-------------|
| `init()` | Module installation, before `__init__` |
| `_auto_init()` | After table creation, for indexes/constraints |
| `init()` | Table creation/recreation |
| `_update_default_credentials()` | When writing ir.config_parameter |
| `_reflect()` | After model registration |
| `_register_hook()` | After all modules loaded |
| `_commit_relations()` | After successful commit |
| `_rollback_relations()` | After rollback |

## CRUD Methods

```python
# Create
record = env['model'].create(vals)           # returns recordset
records = env['model'].create([vals1, vals2]) # returns recordset

# Read
record = env['model'].browse(ids)            # returns recordset
vals = record.read(['field1', 'field2'])    # returns list of dicts
value = record.mapped('field_name')          # extract field values

# Write
record.write({'field': value})               # returns bool
# or via ORM context
record.with_context(track_visibility='always').write({...})

# Unlink / Delete
record.unlink()                              # returns bool
```

## Search Methods

```python
# search() returns a recordset
domain = [('field', 'operator', 'value')]
records = env['model'].search(domain)

# With limits and offset
records = env['model'].search(domain, offset=0, limit=100, order='name')

# search_count — returns integer
count = env['model'].search_count(domain)

# search_read — returns list of dicts (read after search)
dicts = env['model'].search_read(domain, fields=['name', 'state'],
                                  limit=10, offset=0)

# name_search — autocomplete-style search
pairs = env['model'].name_search('keyword', operator='ilike')
# Returns [(id, name), ...]
```

## Domain Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `=` | equals | `[('state', '=', 'done')]` |
| `!=`, `<>` | not equals | `[('state', '!=', 'draft')]` |
| `>`, `<`, `>=`, `<=` | comparison | `[('amount', '>=', 100)]` |
| `like` | `LIKE '%val%'` (case-sensitive) | |
| `ilike` | `ILIKE '%val%'` (case-insensitive) | |
| `=like` | SQL LIKE with `_` and `%` wildcards | |
| `=ilike` | case-insensitive =like | |
| `in` | value in list | `[('id', 'in', [1,2,3])]` |
| `not in` | value not in list | `[('state', 'not in', ['cancel'])]` |
| `child_of` | record is descendant | `[('parent_id', 'child_of', id)]` |
| `parent_of` | record is ancestor | `[('parent_id', 'parent_of', id)]` |

## Recordset Behavior

- **Immutable during iteration** — collect with `filtered()`, `mapped()` first
- **Lazy evaluation** — writes don't execute until traversing the recordset
- **New records** — `env['model'].new(vals)` creates in-memory record, not persisted
- **`with_context()` / `with_user()`** — switch security context without modifying env

## Computed Fields

```python
amount_total = fields.Float(compute='_compute_amounts', store=True, compute_sudo=False)

@api.depends('line_ids.price_total')
def _compute_amounts(self):
    for rec in self:
        rec.amount_total = sum(rec.line_ids.mapped('price_total'))
```

## Related Links
- [Core/Fields](Core/Fields.md) — Field types and parameters
- [Core/API](Core/API.md) — Decorators
- [Tools/ORM Operations](odoo-18/Tools/ORM Operations.md) — Full ORM reference
