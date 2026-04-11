---
type: core
name: API
version: Odoo 18
tags: [core, api, decorators, orm]
source: ~/odoo/odoo18/odoo/odoo/models.py
---

# API Decorators

## @api Decorators

### @api.model
```python
@api.model
def _get_default_company(self):
    # No active record — runs as superuser
    # self.env.user is the current user
    return self.env.company
```

### @api.model_create_multi
```python
@api.model_create_multi
def create(self, vals_list):
    # vals_list: list of dicts — batch creation
    # Override to add shared logic for all records
    return super().create(vals_list)
```

### @api.depends
```python
@api.depends('line_ids.amount', 'tax_ids.amount')
def _compute_amount(self):
    # Triggers recompute when any listed field changes
    # Supports dot-notation: 'line_ids.amount'
    # Supports method calls: 'line_ids.product_id.price'
    for rec in self:
        rec.amount = sum(rec.line_ids.mapped('amount'))
```

### @api.onchange
```python
@api.onchange('product_id')
def _onchange_product(self):
    # Triggers when user changes field in form view
    # Can return {'warning': {...}} to show UI warning
    if self.product_id:
        self.price_unit = self.product_id.list_price
        return {
            'warning': {'title': 'Price Updated', 'message': 'Check the price'}
        }
```

### @api.constrains
```python
@api.constrains('date_start', 'date_end')
def _check_dates(self):
    # Runs validation after write/create
    # Raise ValidationError to block the operation
    for rec in self:
        if rec.date_start > rec.date_end:
            raise ValidationError('Start date must be before end date')
```

### @api.depends_context
```python
@api.depends('price', 'currency_id', context_key='company_id')
def _compute_amount_company(self):
    # Additional context dependencies
    # Recomputes when context values change
    pass
```

### @api.ondelete
```python
@api.ondelete(at_uninstall=False)
def _unlink(self):
    # Runs before unlink
    # at_uninstall=True → also runs during module uninstall
    pass
```

---

## Environment Context

```python
# Switch user
admin_recs = recs.with_user(user_id)

# Switch company
recs = recs.with_company(company_id)

# Switch context (add keys)
recs = recs.with_context(lang='en_US', tz='America/New_York')

# sudo mode (bypass access rights)
recs = recs.sudo()  # as superuser
recs = recs.sudo(user_id)  # as specific user

# Clear cache
self.env.cache.invalidate()  # clear ORM cache
self.invalidate_model(['field_name'])  # invalidate specific fields
```

---

## Related Links
- [[Core/BaseModel]] — Model foundation
- [[Core/Fields]] — Field types
