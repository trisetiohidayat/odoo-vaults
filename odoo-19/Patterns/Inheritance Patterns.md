---
type: pattern
tags: [odoo, odoo19, inheritance, pattern, _inherit]
created: 2026-04-06
---

# Inheritance Patterns

## Overview

Three ways to extend models in Odoo.

## 1. Classic Inheritance (_inherit)

Extend existing model by name:

```python
class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = 'sale.order.line'

    custom_field = fields.Char('Custom Field')

    def _custom_method(self):
        # Add method to existing model
        pass
```

## 2. Delegation Inheritance (_inherits)

Access child fields through parent:

```python
class SaleOrderLine(models.Model):
    _name = 'my.order.line'
    _inherits = {'product.product': 'product_id'}

    product_id = fields.Many2one(
        'product.product',
        delegate=True,
        required=True,
        ondelete='cascade'
    )

    # Access product.product fields directly:
    # self.name, self.list_price, etc.
```

## 3. Prototype Inheritance

Create new model extending behavior:

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'mail.thread']
    # Combines sale.order with mail.thread features
```

## Comparison

| Pattern | _name | _inherit | Use Case |
|---------|-------|---------|----------|
| Classic | Same as inherit | Single/List | Add fields to existing model |
| Delegation | New name | Single | Create child with parent fields |
| Prototype | New name | List | Mixin features |

## Abstract Model (Mixin)

```python
class SaleOrderMixin(models.AbstractModel):
    _name = 'sale.mixin'
    _description = 'Sale Mixin'

    custom_field = fields.Char('Custom')

    def _custom_method(self):
        pass
```

Then use in other models:
```python
class MyModel(models.Model):
    _inherit = ['my.model', 'sale.mixin']
```

## Related

- [Core/BaseModel](Core/BaseModel.md) - Model foundation
- [Core/Fields](Core/Fields.md) - Adding fields
- [Core/API](Core/API.md) - Methods
- [Patterns/Security Patterns](Patterns/Security Patterns.md) - Inheritance with ACL
