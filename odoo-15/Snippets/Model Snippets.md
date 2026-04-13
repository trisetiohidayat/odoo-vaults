# Model Snippets

Code templates untuk membuat model Odoo 15.

## Basic Model

```python
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char('Name', required=True, index=True, copy=False)
    code = fields.Char('Code', index=True, copy=False)
    active = fields.Boolean('Active', default=True, copy=False)
    sequence = fields.Integer('Sequence', default=10)
    company_id = fields.Many2one(
        'res.company', 'Company',
        index=True, ondelete='restrict',
        default=lambda self: self.env.company,
    )

    # ─────────────────────────────────────────────
    # Defaults
    # ─────────────────────────────────────────────

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        defaults['active'] = True
        return defaults

    # ─────────────────────────────────────────────
    # SQL Constraints
    # ─────────────────────────────────────────────

    _sql_constraints = [
        ('code_unique', 'UNIQUE (code, company_id)',
         'Code must be unique per company'),
    ]

    # ─────────────────────────────────────────────
    # Compute Methods
    # ─────────────────────────────────────────────

    amount = fields.Float('Amount', digits='Product Price')
    quantity = fields.Float('Quantity', default=1.0)
    total = fields.Float('Total', compute='_compute_total', store=True)

    @api.depends('amount', 'quantity')
    def _compute_total(self):
        for record in self:
            record.total = record.amount * record.quantity

    # ─────────────────────────────────────────────
    # Onchange
    # ─────────────────────────────────────────────

    @api.onchange('amount')
    def _onchange_amount(self):
        if self.amount < 0:
            return {
                'warning': {
                    'title': _('Warning'),
                    'message': _('Amount cannot be negative'),
                    'type': 'notification',
                }
            }

    # ─────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────

    @api.constrains('code')
    def _check_code(self):
        for record in self:
            if record.code and len(record.code) < 3:
                raise ValidationError(_('Code must be at least 3 characters'))

    # ─────────────────────────────────────────────
    # Action Methods
    # ─────────────────────────────────────────────

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', index=True, copy=False, readonly=True,
       track_visibility='onchange')

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Can only confirm draft records'))
        self.write({'state': 'confirm'})
        return True

    def action_done(self):
        self.write({'state': 'done'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True

    def action_draft(self):
        self.write({'state': 'draft'})
        return True

    # ─────────────────────────────────────────────
    # CRUD Overrides
    # ─────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code(vals.get('name', ''))
        return super().create(vals_list)

    def write(self, vals):
        # Track changes
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.state == 'done':
                raise UserError(_('Cannot delete done records'))
        return super().unlink()
```

## One2many / Many2many Lines

```python
class MyOrder(models.Model):
    _name = 'my.order'
    _description = 'My Order'

    name = fields.Char('Order Reference', required=True,
                       copy=False, readonly=True, default='New')

    line_ids = fields.One2many('my.order.line', 'order_id', string='Order Lines')

    amount_total = fields.Monetary('Total', compute='_compute_amount_total',
                                   store=True, currency_field='currency_id')

    currency_id = fields.Many2one('res.currency', 'Currency',
                                  default=lambda self: self.env.company.currency_id)

    @api.depends('line_ids.price', 'line_ids.quantity')
    def _compute_amount_total(self):
        for order in self:
            order.amount_total = sum(order.line_ids.mapped('price_total'))


class MyOrderLine(models.Model):
    _name = 'my.order.line'
    _description = 'My Order Line'

    order_id = fields.Many2one('my.order', 'Order', required=True,
                                ondelete='cascade', index=True, copy=False)

    product_id = fields.Many2one('product.product', 'Product',
                                  domain=[('type', '!=', 'service')])
    name = fields.Char('Description')
    quantity = fields.Float('Quantity', default=1.0, digits='Product Unit of Measure')
    uom_id = fields.Many2one('uom.uom', 'Unit of Measure',
                              related='product_id.uom_id', readonly=True)
    price_unit = fields.Float('Unit Price', digits='Product Price')
    price_subtotal = fields.Monetary('Subtotal', compute='_compute_price_subtotal',
                                      store=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', 'Currency',
                                  related='order_id.currency_id', readonly=True)

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id:
            self.name = self.product_id.name
            self.price_unit = self.product_id.list_price
```

## Wizard (TransientModel)

```python
class ConfirmWizard(models.TransientModel):
    _name = 'my.confirm.wizard'
    _description = 'Confirmation Wizard'

    @api.model
    def _default_active_records(self):
        return self.env[self.env.context.get('active_model')].browse(
            self.env.context.get('active_ids', [])
        )

    active_record_ids = fields.Many2many(
        comodel_name=self.env.context.get('active_model', 'my.model'),
        relation='my_confirm_wizard_rel',
        column1='wizard_id',
        column2='record_id',
        string='Records',
        default=_default_active_records,
    )

    note = fields.Text('Notes')

    def action_confirm(self):
        for record in self.active_record_ids:
            record.write({'state': 'confirm'})
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
```

## See Also
- [Core/BaseModel](Core/BaseModel.md) — Model definition
- [Core/Fields](Core/Fields.md) — Field types
- [Core/API](Core/API.md) — Decorators
- [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) — State machine