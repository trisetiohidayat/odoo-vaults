---
type: snippets
name: Model Snippets
version: Odoo 18
tags: [snippets, model, code-templates]
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

    name = fields.Char(string='Name', required=True, index=True)
    active = fields.Boolean(string='Active', default=True)
    date = fields.Date(string='Date', default=fields.Date.today)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('done', 'Done'),
    ], string='State', default='draft', copy=False, tracking=True)

    # Computed field
    amount_total = fields.Float(
        string='Total',
        compute='_compute_amount_total',
        store=True,
    )

    # SQL constraint
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Name must be unique!'),
    ]

    @api.depends('line_ids.amount')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('amount'))

    @api.constrains('date')
    def _check_date(self):
        for rec in self:
            if rec.date and rec.date > fields.Date.today():
                raise ValidationError('Date cannot be in the future.')

    def action_confirm(self):
        self.write({'state': 'confirm'})
        return True
```

## Computed Field (Stored)

```python
amount_untaxed = fields.Float(
    string='Untaxed Amount',
    compute='_compute_amount_untaxed',
    store=True,  # stored in DB, recomputed on dependency change
)

@api.depends('line_ids.price_subtotal')
def _compute_amount_untaxed(self):
    for order in self:
        order.amount_untaxed = sum(order.line_ids.mapped('price_subtotal'))
```

## Onchange Method

```python
@api.onchange('product_id')
def _onchange_product(self):
    if self.product_id:
        self.price_unit = self.product_id.list_price
        self.tax_ids = self.product_id.taxes_id
    return {
        'warning': {
            'title': 'Warning',
            'message': 'Price has been updated',
        }
    }
```

## Related Field

```python
partner_id = fields.Many2one('res.partner', string='Customer')
partner_name = fields.Char(related='partner_id.name', store=True)
partner_email = fields.Char(related='partner_id.email', readonly=True)
```

## Action Button

```python
def action_done(self):
    for rec in self:
        if rec.state == 'done':
            raise UserError('Already done.')
        rec.write({'state': 'done'})
    return True

def action_cancel(self):
    self.write({'state': 'cancel'})
    return self.env['ir.actions.act_window']._for_xml_id('module.action_wizard')
```

---

## Related Links
- [Snippets/Controller Snippets](Snippets/Controller-Snippets.md) — HTTP controllers
- [Core/API](Core/API.md) — Decorators
