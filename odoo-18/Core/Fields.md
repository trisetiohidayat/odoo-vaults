---
type: core
name: Fields
version: Odoo 18
tags: [core, fields, orm]
source: ~/odoo/odoo18/odoo/odoo/fields.py
---

# Fields

Field type reference for Odoo 18 models.

## Primitive Fields

### Char
```python
name = fields.Char(string='Name', size=128, trim=True, index=True)
# size=None → unlimited
# trim=True → strips whitespace (default in Odoo 12+)
```

### Text
```python
description = fields.Text(string='Description')
# Text — unlimited length, no size limit, not indexed by default
```

### Integer
```python
nbr = fields.Integer(string='Number', default=0, group_operator='sum')
```

### Float
```python
price = fields.Float(string='Price', digits=(16, 2))
# digits=(precision, scale) — precision=total digits, scale=decimal places
```

### Boolean
```python
active = fields.Boolean(string='Active', default=True)
```

### Date / Datetime
```python
date_start = fields.Date(string='Start Date')
datetime_start = fields.Datetime(string='Start DateTime', default=lambda self: fields.Datetime.now())
# Related helpers:
fields.Date.today()       # returns date string 'YYYY-MM-DD'
fields.Date.context_today(self)  # respects user timezone
fields.Datetime.now()     # returns datetime string
```

### Binary
```python
data = fields.Binary(string='File', attachment=True)
# attachment=True → stored as ir_attachment (efficient for large files)
```

### Html
```python
description = fields.Html(string='Description', sanitize=True, sanitize_tags=False)
# sanitize=True (default) → strips malicious tags
# sanitize_tags=True → also strips tag content
```

### Selection
```python
state = fields.Selection([
    ('draft', 'Draft'),
    ('confirm', 'Confirmed'),
    ('done', 'Done'),
], string='State', default='draft', tracking=True)
```

---

## Relational Fields

### Many2one
```python
partner_id = fields.Many2one('res.partner', string='Customer',
                              required=True, ondelete='restrict',
                              index=True, tracking=True)
# ondelete: 'cascade' | 'set null' | 'restrict' | 'no action'
```

### One2many
```python
line_ids = fields.One2many('sale.order.line', 'order_id',
                            string='Order Lines', copy=True)
# Inverse of Many2one on child model
```

### Many2many
```python
tag_ids = fields.Many2many('res.partner.category', string='Tags')
# Creates intermediate table: rel_sale_order_res_partner_category
```

### Reference
```python
ref = fields.Reference([('sale.order', 'Sales Order'),
                         ('purchase.order', 'Purchase Order')], string='Reference')
```

---

## Special Fields

### Computed
```python
amount_total = fields.Float(compute='_compute_amount',
                             inverse='_inverse_amount',
                             store=False,   # not stored in DB
                             compute_sudo=True)  # run as superuser
```

### Related
```python
partner_name = fields.Char(related='partner_id.name', store=True, readonly=True)
```

### Monetary
```python
amount = fields.Monetary(string='Amount', currency_field='currency_id')
# currency_field defaults to 'currency_id'
# Automatically applies company-dependent rounding
```

### JSON
```python
data = fields.Json(string='Metadata', precompute=True)
# Odoo 13+: stores arbitrary JSON in a column
# precompute=True: compute on create, not stored (like computed)
```

---

## Field Parameters Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `string` | str | field name | Label shown in UI |
| `help` | str | — | Tooltip description |
| `readonly` | bool | False | Prevent user editing |
| `required` | bool | False | Mandatory field |
| `index` | bool | False | Create database index |
| `copy` | bool | True | Copied when duplicating record |
| `default` | callable/any | None | Default value |
| `states` | dict | — | State-dependent attrs |
| `groups` | str | — | XML group IDs with access |
| `company_dependent` | bool | False | Value differs per company |
| `tracking` | bool/int | False | Enable mail tracking |
| `precompute` | bool | False | Compute on create (not stored) |

---

## Related Links
- [[Core/BaseModel]] — Model foundation
- [[Core/API]] — @api.depends, @api.onchange
