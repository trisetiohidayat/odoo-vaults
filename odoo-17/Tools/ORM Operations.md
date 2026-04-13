---
tags: [odoo, odoo17, orm, tools]
---

# ORM Operations — search(), browse(), domains

**File:** `odoo/odoo/models.py`

## search()

```python
self.env['model.name'].search(domain)
```

Returns a `recordset`. Empty recordset is falsy but equals `self.env['model.name']`.

## browse()

```python
self.env['model.name'].browse([1, 2, 3])
```

Returns recordset for given IDs. `browse(False)` returns empty recordset.

## create()

```python
self.env['model.name'].create({'field': value})
```

Creates record, returns new record.

## write()

```python
records.write({'field': value})
```

Modifies matching records. Returns `True`.

## Domain Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `=` | equals | `('state', '=', 'draft')` |
| `!=` | not equals | `('active', '!=', False)` |
| `>` `<` `>=` `<=` | numeric comparison | `('amount', '>', 100)` |
| `like` | case-insensitive match | `('name', 'like', 'acme')` |
| `ilike` | case-insensitive (no wildcards) | `('name', 'ilike', 'acme')` |
| `=like` | SQL LIKE with `%` wildcards | `('code', '=like', 'A%')` |
| `in` | value in list | `('id', 'in', [1, 2, 3])` |
| `not in` | value not in list | `('state', 'not in', ['canc')` |
| `child_of` | record + children | `('partner_id', 'child_of', 1)` |
| `parent_of` | record + parents | `('partner_id', 'parent_of', 1)` |

## Logical Operators

```python
# AND (default — comma or '&')
['&', ('state', '=', 'draft'), ('user_id', '=', 1)]

# OR
['|', ('state', '=', 'done'), ('priority', '=', 'high')]

# NOT
['!', ('active', '=', False)]
```

## Environment

```python
self.env['model.name']          # current user's env
self.sudo()                     # superuser env (bypasses ACL)
self.with_context(lang='en_US') # context override
self.with_company(company_id)   # company context
self.env.ref('xml_id')          # resolve external ref
```

## See Also
- [Core/BaseModel](Core/BaseModel.md) — CRUD methods
- [Core/API](Core/API.md) — @api.depends
- [Core/Fields](Core/Fields.md) — Field types
