---
type: core
module: fields
tags: [odoo, odoo19, fields, orm]
created: 2026-04-06
---

# Fields

## Overview

Semua field types untuk model Odoo 19.

**Location:** `~/odoo/odoo19/odoo/odoo/fields.py`

## Value Fields

| Field Type | Description | Example |
|------------|-------------|---------|
| `Char` | Single line text | `name = fields.Char('Name')` |
| `Text` | Multi-line text | `description = fields.Text()` |
| `Html` | Rich text | `content = fields.Html()` |
| `Integer` | Whole number | `qty = fields.Integer()` |
| `Float` | Decimal | `price = fields.Float()` |
| `Boolean` | True/False | `active = fields.Boolean()` |
| `Date` | Date only | `date = fields.Date()` |
| `Datetime` | Date + time | `datetime = fields.Datetime()` |
| `Binary` | File/data | `file = fields.Binary()` |
| `Selection` | Dropdown | `state = fields.Selection([...])` |
| `Monetary` | Currency | `amount = fields.Monetary()` |

## Relational Fields

| Field Type | Description | Syntax |
|------------|-------------|--------|
| `Many2one` | One-to-One | `partner_id = fields.Many2one('res.partner')` |
| `One2many` | One-to-Many | `line_ids = fields.One2many('model.line', 'parent_id')` |
| `Many2many` | Many-to-Many | `tag_ids = fields.Many2many('tag.model')` |

## Special Fields

| Field Type | Description |
|------------|-------------|
| `Many2oneReference` | Dynamic reference |
| `Reference` | Record reference |
| `Json` | JSON data (NEW in 17+) |
| `Image` | Image with resize |
| `Binary` | File storage |
| `Cast` | Type casting |

## Field Attributes

```python
name = fields.Char(
    string='Display Name',     # Label
    required=True,              # Required field
    readonly=False,             # Read-only
    default=_default_func,      # Default value
    help='Help text',          # Tooltip
    index=True,                 # Database index
    copy=False,                 # Exclude from copy
    tracking=True,              # Track changes
    groups='base.group_user',   # Field visibility
)
```

## Related

- [Core/BaseModel](Core/BaseModel.md) - Using fields in models
- [Core/API](Core/API.md) - Computed fields, onchange
- [Tools/ORM Operations](odoo-18/Tools/ORM Operations.md) - Reading/writing fields
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) - Field-level security
