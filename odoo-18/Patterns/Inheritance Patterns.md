---
type: pattern
name: Inheritance Patterns
version: Odoo 18
tags: [patterns, inheritance, orm]
---

# Inheritance Patterns

## Pattern 1: Classic Extension (`_inherit`)

```python
class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = 'sale.order.line'  # same name = extension

    # Add new field
    margin = fields.Float(string='Margin', compute='_compute_margin')

    # Override existing method
    def _prepare_invoice_line(self, invoice, **kwargs):
        vals = super()._prepare_invoice_line(invoice, **kwargs)
        vals['margin'] = self.margin
        return vals
```

**When to use:** Add fields, methods, or override behavior of an existing model.

---

## Pattern 2: Delegation (`_inherits`)

```python
class ResPartner(models.Model):
    _name = 'res.partner'
    _inherits = {'res.users': 'user_id'}  # creates user_id Many2one

    # Partner automatically has all res.users fields (name, email, login, etc.)
    # The user_id field holds the FK to res.users
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
```

**When to use:** Model that "is also" another model (e.g., partner = user + contact info).

---

## Pattern 3: Prototype Extension (`_inherit` with different `_name`)

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'mail.thread', 'mail.activity.mixin']

    # Creates new model combining sale.order + mail behaviors
    # No database extension — mixin methods become available
    activity_ids = fields.One2many('mail.activity', ...)
    message_follower_ids = fields.Many2many(...)
```

**When to use:** Add shared behaviors from mixins (mail, tracking, activity, etc.).

---

## Pattern 4: Abstract Model Mixin

```python
# Base abstract model
class DocumentOwner(models.AbstractModel):
    _name = 'document.owner'
    _description = 'Document Owner Mixin'

    owner_id = fields.Many2one('res.partner', string='Owner')
    owner_name = fields.Char(related='owner_id.name')

# Use in concrete model
class AccountInvoice(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'document.owner']
```

---

## Comparison

| Pattern | `_name` | `_inherit` | DB Table |
|---------|---------|-----------|----------|
| Extend | same as parent | `['parent']` | Same table |
| Delegation | new name | `{parent: fk_field}` | New + FK to parent |
| Mixin | new abstract | `['mixin1', 'mixin2']` | No table (abstract) |

---

## Related Links
- [Core/BaseModel](Core/BaseModel.md) — Model attributes
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) — State machines
