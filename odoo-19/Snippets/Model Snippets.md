---
type: snippet
tags: [odoo, odoo19, snippet, model, template, code]
created: 2026-04-06
---

# Model Snippets

## Basic Model

```python
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(default=True)
    date = fields.Date(string='Date')
    partner_id = fields.Many2one('res.partner', string='Partner')
    line_ids = fields.One2many('my.model.line', 'parent_id', string='Lines')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], default='draft')
    amount = fields.Monetary(string='Amount')
    currency_id = fields.Many2one('res.currency')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Name must be unique!'),
    ]

    @api.constrains('name')
    def _check_name(self):
        for rec in self:
            if len(rec.name) < 3:
                raise ValidationError('Name must be at least 3 characters!')

    def action_done(self):
        for rec in self:
            rec.write({'state': 'done'})
        return True
```

## Computed Field

```python
margin = fields.Float(
    string='Margin',
    compute='_compute_margin',
    store=True,
    readonly=True,
)

@api.depends('list_price', 'standard_price')
def _compute_margin(self):
    for rec in self:
        rec.margin = rec.list_price - rec.standard_price
```

## Related Field

```python
partner_name = fields.Char(
    string='Partner Name',
    related='partner_id.name',
    readonly=True,
)
```

## One2many with Default

```python
line_ids = fields.One2many(
    'my.model.line',
    'parent_id',
    string='Lines',
    default=lambda self: self._default_lines()
)

def _default_lines(self):
    return [(0, 0, {'name': 'Line 1'})]
```

## Action Button

```python
def action_confirm(self):
    self.ensure_one()
    if self.state != 'draft':
        return False

    self.write({'state': 'confirmed'})

    # Send notification
    self.message_post(
        body=f'Order {self.name} confirmed',
        message_type='notification'
    )

    return True
```

## Related

- [Core/BaseModel](Core/BaseModel.md) - Model foundation
- [Core/Fields](Core/Fields.md) - Field types
- [Core/API](Core/API.md) - Decorators
- [Core/Exceptions](Core/Exceptions.md) - Validation
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) - State transitions
