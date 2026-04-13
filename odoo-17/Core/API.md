---
tags: [odoo, odoo17, api, orm]
---

# API — Decorators & Context

**File:** `odoo/odoo/models.py` (api.* decorators)

## @api.model

Method runs with no active record. Use for:
- Default value computation
- Autocomplete searches
- Low-level record creation

```python
@api.model
def _get_default_company(self):
    return self.env.company
```

Runs as superuser (bypasses ACL). Does NOT trigger `@api.depends`.

## @api.depends

Recomputes when any listed field changes.

```python
@api.depends('list_price', 'standard_price')
def _compute_margin(self):
    for rec in self:
        rec.margin = rec.list_price - rec.standard_price
```

Can also track related fields: `@api.depends('partner_id.name')`

## @api.onchange

Triggers in the UI when any listed field changes.

```python
@api.onchange('partner_id')
def _onchange_partner(self):
    self.address = self.partner_id.address
```

只能在form视图中触发。关联字段变化时也触发（通过`related`自动）。

## @api.constrains

Raises `ValidationError` if constraint is violated.

```python
@api.constrains('date_start', 'date_end')
def _check_dates(self):
    if self.date_start > self.date_end:
        raise ValidationError('Start must be before end')
```

Runs after `write()`/`create()` completes.

## @api.depends_context

Adds cache invalidation hint based on context key.

```python
@api.depends('company_id')
@api.depends_context('company_id')
def _compute_something(self):
    # Automatically invalidated when company context changes
```

## See Also
- [Core/BaseModel](odoo-18/Core/BaseModel.md) — Full model reference
- [Core/Fields](odoo-18/Core/Fields.md) — Field parameters
- [Tools/ORM Operations](odoo-18/Tools/ORM Operations.md) — Domain operators
