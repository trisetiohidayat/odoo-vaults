---
type: core
module: base
tags: [odoo, odoo19, orm, model, base]
created: 2026-04-06
---

# BaseModel

## Overview

`BaseModel` adalah fondasi ORM Odoo. Semua model mewarisi dari class ini.

**Location:** `~/odoo/odoo19/odoo/odoo/models.py`

## Key Attributes

| Attribute | Description | Example |
|-----------|-------------|---------|
| `_name` | Model name (required) | `_name = 'sale.order'` |
| `_inherit` | Parent model(s) | `_inherit = 'sale.order'` |
| `_description` | Display name | `_description = 'Sales Order'` |
| `_order` | Default sort | `_order = 'date_order desc'` |
| `_rec_name` | Display field | `_rec_name = 'name'` |
| `_table` | SQL table name | `_table = 'sale_order'` |
| `_sql_constraints` | DB constraints | `_sql_constraints = [...]` |

## Essential Methods

| Method | Purpose |
|--------|---------|
| `search()` | Find records matching domain |
| `browse()` | Get records by IDs |
| `create()` | Create new record |
| `write()` | Update records |
| `unlink()` | Delete records |
| `read()` | Read field values |
| `mapped()` | Get field values as list |
| `filtered()` | Filter recordset |
| `sorted()` | Sort recordset |
| `copy()` | Duplicate record |

## Recordset Operations

```python
# Search
records = self.env['model.name'].search([
    ('field', '=', 'value'),
    ('active', '=', True),
])

# Browse
record = self.env['model.name'].browse(1)

# Create
record = self.env['model.name'].create({
    'name': 'New',
    'value': 100,
})

# Write
record.write({'name': 'Updated'})

# Unlink
record.unlink()
```

## Related

- [Core/Fields](Core/Fields.md) - Field types
- [Core/API](Core/API.md) - Decorators
- [Core/HTTP Controller](Core/HTTP-Controller.md) - Controllers
- [Core/Exceptions](Core/Exceptions.md) - Error handling
- [Patterns/Inheritance Patterns](Patterns/Inheritance-Patterns.md) - _inherit
