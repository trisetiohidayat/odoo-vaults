---
tags: [odoo, odoo17, fields, orm]
---

# Fields — Field Types & Parameters

**File:** `odoo/odoo/fields.py`

## Common Field Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `string` | str | None | Field label |
| `help` | str | None | Tooltip text |
| `required` | bool | False | Mandatory field |
| `readonly` | bool | False | Non-editable |
| `default` | value/callable | None | Default value |
| `index` | bool | False | Add database index |
| `copy` | bool | True | Copy on duplicate |
| `tracking` | bool/int | False | Track changes in chatter |
| `groups` | str | None | XML groups for visibility |
| `states` | dict | None | State-dependent attrs |

## Field Types

### Char — Single-line text
```python
name = fields.Char(string='Name', size=50, index=True)
```

### Text — Multi-line text
```python
description = fields.Text(string='Description')
```

### Integer / Float
```python
quantity = fields.Integer(string='Qty', default=0)
price = fields.Float(string='Price', digits=(10,2))
```

### Boolean
```python
active = fields.Boolean(string='Active', default=True)
```

### Date / Datetime
```python
start_date = fields.Date(string='Start Date')
end_datetime = fields.Datetime(string='End DateTime')
```

### HTML
```python
notes = fields.Html(string='Notes', sanitize=False)
```

### Binary
```python
data = fields.Binary(string='File Data', attachment=True)
```

### Selection
```python
state = fields.Selection([
    ('draft', 'Draft'),
    ('done', 'Done'),
], string='State', default='draft')
```

## Relational Fields

### Many2one — Reference to one record
```python
partner_id = fields.Many2one('res.partner', string='Partner')
```

### One2many — Inverse of Many2one
```python
line_ids = fields.One2many('sale.order.line', 'order_id', string='Lines')
```

### Many2many — N:N relationship
```python
tag_ids = fields.Many2many('sale.order.tag', string='Tags')
```

### Reference — Dynamic model reference
```python
ref_id = fields.Reference([('model1', 'Model1'), ('model2', 'Model2')], string='Reference')
```

## Computed Fields

```python
total = fields.Float(compute='_compute_total', store=True, readonly=True)

@api.depends('price_unit', 'quantity')
def _compute_total(self):
    for rec in self:
        rec.total = rec.price_unit * rec.quantity
```

## See Also
- [Core/BaseModel](Core/BaseModel.md) — Model definition
- [Core/API](Core/API.md) — @api.depends
- [Patterns/Inheritance Patterns](Patterns/Inheritance-Patterns.md)
