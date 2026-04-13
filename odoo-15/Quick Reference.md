# Odoo 15 Vault — Quick Reference

Fast lookup for common patterns in Odoo 15.

## Quick Snippets

### Create a Model
```python
from odoo import api, fields, models

class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model'
    _inherit = None

    name = fields.Char('Name', required=True)
    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', 'Company',
                                 default=lambda self: self.env.company)
```

### Add Computed Field
```python
total = fields.Float(compute='_compute_total', store=True)

@api.depends('price', 'quantity')
def _compute_total(self):
    for rec in self:
        rec.total = rec.price * rec.quantity
```

### Add Onchange
```python
@api.onchange('partner_id')
def _onchange_partner(self):
    if self.partner_id:
        self.address = self.partner_id.street
```

### Search Records
```python
records = self.env['my.model'].search([
    ('state', '=', 'done'),
    ('company_id', '=', self.env.company.id),
])
```

### Create Record
```python
record = self.env['my.model'].create({
    'name': 'Test',
    'active': True,
})
```

### Browse by ID
```python
record = self.env['my.model'].browse(record_id)
```

### Write to Record
```python
record.write({'name': 'New Name', 'state': 'done'})
```

### HTTP Controller
```python
from odoo import http

class MyController(http.Controller):
    @http.route('/my/page', type='http', auth='user', website=True)
    def page(self, **kwargs):
        return http.request.render('my_module.template', {})
```

### Raise ValidationError
```python
from odoo.exceptions import ValidationError
from odoo import _

raise ValidationError(_('Error message here'))
```

### Raise UserError
```python
from odoo.exceptions import UserError
raise UserError(_('Cannot delete this record'))
```

### Portal Mixin
```python
from odoo.addons.portal.models.portal_mixin import PortalMixin

class MyModel(models.Model, PortalMixin):
    _name = 'my.model'
    _inherit = ['portal.mixin', 'mail.thread']
```

### Mail Thread
```python
class MyModel(models.Model):
    _name = 'my.model'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    message_follower_ids = fields.Many2many(
        'mail.followers', 'res_id', 'message_ids',
        domain=[('res_model', '=', 'my.model')],
        auto_join=True,
    )
```

### State Machine Action
```python
def action_confirm(self):
    for rec in self:
        if rec.state != 'draft':
            raise UserError(_('Only draft can be confirmed'))
    self.write({'state': 'confirm'})
    return True
```

### Wizard (TransientModel)
```python
class ConfirmWizard(models.TransientModel):
    _name = 'confirm.wizard'

    def action_confirm(self):
        active_ids = self.env.context.get('active_ids', [])
        self.env[self.env.context.get('active_model')].browse(
            active_ids
        ).write({'state': 'done'})
        return {'type': 'ir.actions.act_window_close'}
```

### Call Wizard
```python
def action_confirm_wizard(self):
    return {
        'name': _('Confirm'),
        'type': 'ir.actions.act_window',
        'res_model': 'confirm.wizard',
        'view_mode': 'form',
        'target': 'new',
        'context': {
            'active_model': self._name,
            'active_ids': self.ids,
        },
    }
```

### Override Create
```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if not vals.get('name'):
            vals['name'] = 'Auto Generated'
    return super().create(vals_list)
```

### Check Company Consistency
```python
class MyModel(models.Model):
    _name = 'my.model'
    _check_company_auto = True

    company_id = fields.Many2one('res.company')
    line_ids = fields.One2many('my.model.line', 'parent_id')

    @api.constrains('company_id', 'line_ids')
    def _check_company(self):
        for rec in self:
            if rec.line_ids:
                if rec.line_ids.company_id != rec.company_id:
                    raise ValidationError(_('Company mismatch'))
```

### SQL Constraint
```python
_sql_constraints = [
    ('code_unique', 'UNIQUE (code, company_id)', 'Code must be unique'),
]
```

### Group-based Field
```python
secret = fields.Char('Secret', groups='base.group_system')
```

### Sudo Access
```python
# Bypass ACL
records = self.env['my.model'].sudo().search([...])

# Sudo as specific user
records = self.env['my.model'].sudo(user_id).search([...])
```

## Common Model Paths

| Model | Source Path |
|---|---|
| `sale.order` | `addons/sale/models/sale_order.py` |
| `stock.picking` | `addons/stock/models/stock_picking.py` |
| `account.move` | `addons/account/models/account_move.py` |
| `purchase.order` | `addons/purchase/models/purchase.py` |
| `crm.lead` | `addons/crm/models/crm_lead.py` |
| `project.project` | `addons/project/models/project.py` |
| `mrp.production` | `addons/mrp/models/mrp_production.py` |
| `product.template` | `addons/product/models/product_template.py` |
| `res.partner` | `odoo/addons/base/models/res_partner.py` |
| `res.users` | `odoo/addons/base/models/res_users.py` |

## Field Type Quick Ref

| Type | Usage |
|---|---|
| `fields.Char` | Text, short |
| `fields.Text` | Long text, no limit |
| `fields.Integer` | Whole numbers |
| `fields.Float` | Decimal numbers |
| `fields.Boolean` | True/False |
| `fields.Selection` | Dropdown choices |
| `fields.Date` | Date |
| `fields.Datetime` | Date + time |
| `fields.Many2one` | FK to another model |
| `fields.One2many` | Inverse of M2O |
| `fields.Many2many` | M2M relationship |
| `fields.Monetary` | Money (needs currency_field) |
| `fields.Binary` | File/blob data |
| `fields.Html` | HTML content |

## Decorator Quick Ref

| Decorator | Use Case |
|---|---|
| `@api.model` | No record needed (empty self) |
| `@api.depends(f1,f2)` | Recompute when fields change |
| `@api.onchange(f1,f2)` | UI event handler |
| `@api.constrains(f1,f2)` | Validation on save |
| `@api.model_create_multi` | Batch create |

## Exception Quick Ref

| Exception | Use |
|---|---|
| `ValidationError` | Field validation, constraints |
| `UserError` | Business logic errors |
| `AccessError` | Permission denied |
| `MissingError` | Record not found |
| `AccessDenied` | Login/auth failure |

## See Also
- [[Core/BaseModel]] — Full model reference
- [[Core/Fields]] — Field types detail
- [[Core/API]] — Decorators detail
- [[Snippets/Model Snippets]] — Full code templates