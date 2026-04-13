---
type: new-feature
tags: [odoo, odoo19, api, changes, migration]
created: 2026-04-06
---

# API Changes (Odoo 18 → 19)

## Overview

API changes and new features in Odoo 19.

## New Field Types

### Json Field

```python
# NEW in Odoo 17+
data = fields.Json('Data')

# Usage
record.data = {'key': 'value'}
```

### Cast Field

```python
# Type casting field
amount = fields.Float()
amount_display = fields.Char(compute='_compute_display')

@api.depends('amount')
def _compute_display(self):
    for rec in self:
        rec.amount_display = str(rec.amount)
```

## New Decorators

### @api.model_create_multi

```python
@api.model_create_multi
def create(self, vals_list):
    # More efficient batch creation
    return super().create(vals_list)
```

## Deprecated Patterns

| Old | New | Notes |
|-----|-----|-------|
| `@api.multi` | (removed) | Default behavior |
| `@api.one` | (removed) | Use loop instead |
| `self.ensure_one()` | `self.ensure_one()` | Still available |

## Compute Store

```python
# Compute and store in DB
total = fields.Float(
    compute='_compute_total',
    store=True,  # Now more efficient
)
```

## Onchange Improvements

```python
# Still works same
@api.onchange('field1')
def _onchange_field1(self):
    # Return warning or domain
    return {
        'warning': {
            'title': 'Warning',
            'message': 'Message',
        }
    }
```

## Related

- [New Features/What's New](odoo-18/New Features/What's New.md) - Overview of new features
- [New Features/New Modules](odoo-18/New Features/New Modules.md) - New module details
- [Core/BaseModel](odoo-18/Core/BaseModel.md) - Core model API
- [Core/Fields](odoo-18/Core/Fields.md) - Field types
- [Core/API](odoo-18/Core/API.md) - Decorators
