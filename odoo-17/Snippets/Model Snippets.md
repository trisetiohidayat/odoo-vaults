---
tags: [odoo, odoo17, snippets]
---

# Model Snippets

## Basic Model

```python
from odoo import models, fields, api

class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model'
    _order = 'name asc'

    name = fields.Char(string='Name', required=True, index=True)
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one('res.company', string='Company',
        default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='Responsible',
        default=lambda self: self.env.user)
```

## Computed Field

```python
total = fields.Float(compute='_compute_total', store=True)

@api.depends('unit_price', 'quantity')
def _compute_total(self):
    for rec in self:
        rec.total = rec.unit_price * rec.quantity
```

## Related Field

```python
partner_name = fields.Char(related='partner_id.name', string='Partner Name', store=True)
```

## Onchange Method

```python
@api.onchange('partner_id')
def _onchange_partner(self):
    if self.partner_id:
        self.user_id = self.partner_id.user_id
```

## Constraint

```python
@api.constrains('start_date', 'end_date')
def _check_dates(self):
    for rec in self:
        if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
            raise ValidationError('Start must be before end')
```

## Action Method

```python
def action_done(self):
    for rec in self:
        rec.write({'state': 'done'})
    return True
```

## See Also
- [Core/BaseModel](core/basemodel.md) — Full model reference
- [Core/API](core/api.md) — Decorators
- [Core/Fields](core/fields.md) — Field types
