---
type: tools
name: ORM Operations
version: Odoo 18
tags: [tools, orm, search, domain]
source: ~/odoo/odoo18/odoo/odoo/models.py
---

# ORM Operations

Complete reference for Odoo ORM methods.

## Environment

```python
env = self.env                    # current environment
env.cr                            # database cursor
env.uid                           # current user ID
env.user                         # current user record
env.company                      # current company
env.companies                    # current companies (multi-company)
env.lang                         # current language
env.context                      # current context dict

# Switching context
env['res.partner'].with_context(tz='UTC').browse(1)
env['res.partner'].sudo()        # as superuser
env['res.partner'].with_user(user_id)
env['res.partner'].with_company(company_id)
```

---

## Search Operations

```python
# Basic search
recs = env['model'].search([('state', '=', 'done')])

# With pagination
recs = env['model'].search(domain, offset=0, limit=100, order='id desc')

# Count
count = env['model'].search_count([('active', '=', True)])

# Search + Read
dicts = env['model'].search_read(
    domain,
    fields=['name', 'state'],
    offset=0,
    limit=50,
    order='create_date desc'
)

# Name search (autocomplete)
pairs = env['model'].name_search('keyword', operator='ilike', limit=10)

# Browse
rec = env['model'].browse([1, 2, 3])  # from IDs
rec = env['model'].browse()           # empty recordset
```

---

## Recordset Operations

```python
# Filtering
draft_orders = orders.filtered(lambda o: o.state == 'draft')

# Mapping
names = orders.mapped('partner_id.name')

# Sorted
sorted_orders = orders.sorted(key=lambda o: o.date_order, reverse=True)

# Concatenation
combined = recs1 + recs2

# Subset
subset = recs[:5]  # first 5

# Boolean checks
recs.ids          # list of IDs
len(recs)         # count
bool(recs)        # False if empty

# ensure_one — assert single record
rec.ensure_one()  # raises ValueError if >1 or 0
```

---

## Write Operations

```python
# Single write
rec.write({'field': 'value'})

# Multiple writes
recs.write({'state': 'done'})

# With context flag
rec.with_context(tracking_disable=True).write({'state': 'done'})

# Computed field trigger (with context)
rec.with_context(compute_remaining=True).write({'qty': 5})
```

---

## Create Operations

```python
# Single record
rec = env['sale.order'].create({'partner_id': 1, 'date_order': today})

# Batch creation
recs = env['sale.order'].create([{
    'partner_id': 1, 'date_order': today
}, {
    'partner_id': 2, 'date_order': today
}])

# New (in-memory, not persisted)
rec = env['sale.order'].new({'partner_id': 1})
# Use to prepopulate forms or simulate reads
```

---

## Unlink

```python
recs.unlink()  # returns bool
# Raises AccessError if user lacks unlink permission
# Runs @api.ondelete handlers first
```

---

## execute_kw (low-level XML-RPC)

```python
# Via XML-RPC
models.execute_kw(db, uid, password, 'sale.order', 'search_read',
    [['state', '=', 'sale'](['state',-'=',-'sale'.md)],
    {'fields': ['name', 'state'], 'limit': 5}
)
```

---

## Related Links
- [Core/BaseModel](odoo-18/Core/BaseModel.md) — Full model reference
- [Core/Fields](odoo-18/Core/Fields.md) — Field types
