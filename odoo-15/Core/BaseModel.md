# BaseModel — ORM Foundation

Dokumentasi Odoo 15 untuk fundamental ORM. Source: `odoo/odoo/models.py`

## Model Definition

```python
from odoo import models, fields, api

class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model Description'
    _inherit = None  # or list of parent models
    _order = 'sequence, name'
    _rec_name = 'name'  # field to use for display_name, default 'name'
    _table = None  # auto-generated from _name
    _sql_constraints = []  # [(name, sql_def, message)]
    _log_access = True  # create inherit breadcrumbs columns: create_uid, create_date, write_uid, write_date
```

## Key Attributes

| Attribute | Description | Default |
|---|---|---|
| `_name` | Internal model name (dot notation, lowercase) | **Required** |
| `_description` | Human-readable label | None |
| `_inherit` | Parent model(s) to inherit | None |
| `_inherits` | Delegation inheritance (dict `{model_name: field_name}`) | None |
| `_order` | Default sorting (SQL order by clause) | `id` |
| `_rec_name` | Field used for display_name | `name` |
| `_table` | PostgreSQL table name | auto from _name |
| `_log_access` | Auto-add access log fields | True |
| `_auto` | Auto-create table | True |
| `_constraints` | Python constraints (deprecated, use `_sql_constraints`) | [] |
| `_parent_name` | Field for parent_id (tree structure) | `parent_id` |
| `_parent_store` | Compute and store parent_path | False |
| `_translate` | Model values are translatable | True |

## Model Classes

Odoo 15 menyediakan dua kelas model utama:

- **`models.Model`** — Persistent model (stored in database)
- **`models.TransientModel`** — Temporary data, auto-cleaned by `ir.cron`

### BaseModel Class Structure

```
BaseModel
├── models.Model
├── models.TransientModel
└── models.MappedModel (abstract helper)
```

### MetaModel Metaclass

Located at `odoo/odoo/models.py:149` — `MetaModel(api.Meta)`:

- Auto-decorates traditional-style methods with `@api`
- Implements decorator inheritance via `propagate()`
- Collects inherited attrs from parent classes

## CRUD Operations

### Read (search/browse)

```python
# Search records
records = self.env['my.model'].search([
    ('field', 'operator', value),
    ('state', '=', 'done'),
], order='sequence, name desc', limit=100)

# Browse by IDs
records = self.env['my.model'].browse([1, 2, 3])

# Read with fields
records.read(['name', 'code'])
```

**Domain operators:**
- `=`, `!=`, `<`, `>`, `<=`, `>=`
- `=like`, `=ilike` (SQL LIKE patterns)
- `like`, `not like` (case-sensitive, %pattern%)
- `ilike`, `not ilike` (case-insensitive)
- `in`, `not in` (value in list)
- `=of`, `child_of` (parent_id hierarchy)

### Create

```python
# Single record
record = self.env['my.model'].create({'name': 'Test', 'code': '123'})

# Multi (browse returned recordset, call write once)
vals_list = [{'name': f'Test {i}'} for i in range(5)]
records = self.env['my.model'].create(vals_list)  # Odoo 15 batch create
```

### Write

```python
record.write({'name': 'Updated', 'state': 'done'})

# Multi-write on recordset
records.write({'active': False})
```

### Unlink (Delete)

```python
record.unlink()  # Returns boolean

# With unlink checks via @ondelete
```

## Environment & Context

```python
self.env                      # Environment (cr, uid, context, su)
self.env.cr                   # Cursor (database connection)
self.env.uid                  # Current user ID
self.env.user                 # Current user record
self.env.ref('module.xml_id') # Get record by external ID
self.env.company              # Current company recordset
self.env.companies            # All allowed companies

# Context (dict, passed in RPC calls)
self.env.context              # Current context dict
self.with_context(dict)      # New env with merged context
self.with_context(ir_filter=1)  # Apply saved filter
self.with_user(uid)           # Switch user for access rights
self.sudo()                   # Switch to superuser (bypasses ACL)
self.sudo(uid)                # Sudo as specific user

# Caching
self.invalidate_cache()       # Force cache invalidation
self.flush()                  # Flush pending writes
```

## Recordset Operations

```python
# Filter
records.filtered(lambda r: r.state == 'draft')

# Map / Transform
records.mapped('name')  # returns list of names
records.mapped(lambda r: r.name)

# Sorted
records.sorted(lambda r: r.sequence)

# Concatenation
rec1 + rec2

# Set operations
records | other_records
records & other_records
records - other_records

# Count
len(records)  # uses prefetch
records.ids   # list of IDs

# Boolean checks
bool(records)  # False if empty
if records:
    pass

# Ensure single
record.ensure_one()  # raises ValueError if not exactly 1 record

# First / Last
records[:1]   # first record
records[-1:]  # last record
```

## Special Fields (Auto-created)

Odoo auto-creates these fields on all models:

| Field | Type | Description |
|---|---|---|
| `id` | Integer | Primary key |
| `create_uid` | Many2one(res.users) | Creator |
| `create_date` | Datetime | Creation timestamp |
| `write_uid` | Many2one(res.users) | Last writer |
| `write_date` | Datetime | Last write timestamp |

With `_log_access=True` (default).

## Computed Fields

```python
amount = fields.Float(compute='_compute_amount', store=True, readonly=True)

@api.depends('price', 'quantity')
def _compute_amount(self):
    for record in self:
        record.amount = record.price * record.quantity
```

## Related Fields

```python
partner_name = fields.Char(related='partner_id.name', readonly=True)
```

## Protected Fields

```python
partner_name = fields.Char(related='partner_id.name', readonly=True,
                           inverse='_inverse_partner_name')
```

## Onchange

```python
@api.onchange('partner_id')
def _onchange_partner(self):
    if self.partner_id:
        self.address = self.partner_id.address
```

## Inheritance Patterns

### Extension (_inherit)

```python
class ExtendedModel(models.Model):
    _name = 'original.model'  # same name = extend
    _inherit = 'original.model'

    new_field = fields.Char('New Field')
    # Override existing methods
    def some_method(self):
        super().some_method()
        # extension logic
```

### Parallel (_inherit with different name)

```python
class MyModel(models.Model):
    _name = 'my.model'
    _inherit = ['original.model', 'another.model']
```

### Delegation (_inherits)

```python
class ChildModel(models.Model):
    _name = 'child.model'
    _inherits = {'parent.model': 'parent_id'}

    # Child has all parent fields, accessed via parent_id
    # Access parent field: self.parent_id.name
```

## Magic Fields

| Field | Auto-behavior |
|---|---|
| `create_date` | Set on create |
| `create_uid` | Set on create |
| `write_date` | Updated on every write |
| `write_uid` | Updated on every write |
| `__last_update` | Datetime (for web cache) |

## Mapped Model

For functional fields with complex aggregation:

```python
class MyModel(models.Model):
    _name = 'my.model'

    line_ids = fields.One2many('my.model.line', 'model_id')

    @api.depends('line_ids.price')
    def _compute_total(self):
        MappedModel = self.env['my.model.line'].sudo()
        for record in self:
            record.total = sum(MappedModel.browse(record.line_ids).mapped('price'))
```

## Prefetching

Odoo auto-prefetch records for performance. Accessing a field on one record
loads it for all records in the same recordset. Use `with_context(prefetch_fields=False)`
to disable if needed.

## See Also
- [Core/Fields](Core/Fields.md) — Field types
- [Core/API](Core/API.md) — Decorators (@api.depends, @api.onchange, @api.constrains)
- [Patterns/Inheritance Patterns](odoo-18/Patterns/Inheritance Patterns.md) — _inherit vs _inherits vs mixin