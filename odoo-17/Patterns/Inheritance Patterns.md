---
tags: [odoo, odoo17, patterns, inheritance]
---

# Inheritance Patterns

## Three Types of Inheritance

### 1. Classic (`_inherit = 'parent.model'`)

Extends an existing model by adding fields/methods.

```python
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    new_field = fields.Char('New Field')

    def new_method(self):
        pass
```

Parent model is NOT modified — fields are added in place.

### 2. Delegation (`_inherits = {...}`)

Child model stores parent fields via a `Many2one` with `delegate=True`.

```python
class ResUsers(models.Model):
    _name = 'res.users'
    _inherits = {'res.partner': 'partner_id'}

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', delegate=True)
```

Fields from `res.partner` appear on `res.users` but are stored in `res_partner` table.

### 3. Prototype (`_inherit = ['model.a', 'model.b']`)

Creates a NEW model that combines behaviors from multiple sources.

```python
class SaleOrderLine(models.Model):
    _inherit = ['sale.order.line', 'product.template']
```

## Choosing the Right Pattern

| Pattern | Use Case |
|---------|----------|
| `_inherit` | Add fields/methods to existing model |
| `_inherits` | Create a user-like model that IS a partner |
| Multi `_inherit` | Create mixin/composable behavior |

## Method Resolution Order (MRO)

Odoo uses Python's MRO. Use `super()` to call parent method.

```python
def write(self, vals):
    # Do custom stuff first
    result = super().write(vals)
    # Do custom stuff after
    return result
```

## See Also
- [Core/BaseModel](core/basemodel.md) — Model attributes
- [Core/Fields](core/fields.md) — Field types
