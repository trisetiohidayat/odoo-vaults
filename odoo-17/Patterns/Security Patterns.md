---
tags: [odoo, odoo17, patterns, security]
---

# Security Patterns

> **Source:** `/Users/tri-mac/odoo/odoo17/odoo/odoo/addons/base/models/ir_rule.py`

## Overview

Odoo 17 security operates at three layers:

1. **Model access (`ir.model.access`)** — CRUD permissions per model ( CSV-based)
2. **Record rules (`ir.rule`)** — Record-level domain filtering
3. **Field groups (`groups` attribute)** — Field visibility on forms

---

## ir.model.access CSV

Defined in `security/ir.model.access.csv` within each module.

### File Format

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
```

### Columns

| Column | Description |
|--------|-------------|
| `id` | Unique XML ID (e.g. `module.access_res_partner_user`) |
| `name` | Human-readable name |
| `model_id:id` | Fully-qualified model reference (e.g. `base.model_res_partner`) |
| `group_id:id` | Group XML ID, or `base.group_user` for all users |
| `perm_read` | 1 = allow read, 0 = deny |
| `perm_write` | 1 = allow write, 0 = deny |
| `perm_create` | 1 = allow create, 0 = deny |
| `perm_unlink` | 1 = allow unlink, 0 = deny |

### Example

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_res_partner_user,res.partner.user,base.model_res_partner,base.group_user,1,1,1,0
```

---

## ir.rule — Record-Level Security

> **Model:** `ir.rule` (line 12)
> **File:** `ir_rule.py`

Record rules apply a `domain_force` filter to every CRUD operation. They complement model-level access controls.

### Model Definition

```python
class IrRule(models.Model):
    _name = 'ir.rule'
    _description = 'Record Rule'
    _order = 'model_id DESC, id'
    _MODES = ('read', 'write', 'create', 'unlink')
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Human-readable rule name |
| `active` | Boolean | Disable without deleting (default True) |
| `model_id` | Many2one | Target model (required, cascade delete) |
| `groups` | Many2many | Group(s) this rule applies to; empty = global |
| `global` | Boolean (computed) | True if no groups assigned |
| `domain_force` | Text | Domain expression as Python literal |
| `perm_read` | Boolean | Apply on read (default True) |
| `perm_write` | Boolean | Apply on write (default True) |
| `perm_create` | Boolean | Apply on create (default True) |
| `perm_unlink` | Boolean | Apply on delete (default True) |

### SQL Constraint (line 29-33)

```python
_sql_constraints = [
    ('no_access_rights',
     'CHECK (perm_read!=False or perm_write!=False or perm_create!=False or perm_unlink!=False)',
     'Rule must have at least one checked access right!'),
]
```

### Global vs Group Rules

| Type | `groups` | Combination Logic |
|------|----------|-------------------|
| Global | Empty | AND-ed with all other global rules |
| Group | Assigned | OR-ed with other group rules; only active if user is in group |

**Final domain formula (lines 139-167):**

```python
expression.AND(global_domains + [expression.OR(group_domains)])
```

All global rules are AND-ed together. All group rules are OR-ed, and that result is AND-ed with the global part.

### Evaluation Context (lines 36-50)

The `domain_force` is evaluated with this context:

```python
{
    'user': self.env.user.with_context({}),   # no context deps
    'time': time,
    'company_ids': self.env.companies.ids,      # active companies
    'company_id': self.env.company.id,          # current company
}
```

### `_compute_domain` (lines 139-167)

Cached method (ormcache) returns the combined domain for a given model and operation mode. Also includes rules for parent models via `_inherits`.

### `_get_rules` (lines 112-131)

Raw SQL query to fetch rules for the current user:

```sql
SELECT r.id FROM ir_rule r JOIN ir_model m ON (r.model_id=m.id)
  WHERE m.model=%s AND r.active AND r.perm_{mode}
    AND (r.id IN (SELECT rule_group_id FROM rule_group_rel rg
                  JOIN res_groups_users_rel gu ON (rg.group_id=gu.gid)
                  WHERE gu.uid=%s)
         OR r.global)
  ORDER BY r.id
```

### Cache Invalidation (lines 179-200)

Any `create`, `write`, or `unlink` on `ir.rule` clears the registry cache. This ensures domain changes take effect immediately.

### Access Error Messages (lines 202-253)

When a record rule blocks access, `_make_access_error` generates a detailed `AccessError`. In debug mode (user has `base.group_no_one`), it includes:
- The failing records (up to 6)
- The names of the rules that blocked access
- A note about multi-company issues if `company_id` appears in any failing rule

### Common Domain Patterns

**Only own records:**
```python
[('user_id', '=', user.id)]
```

**Only records in user's companies:**
```python
[('company_id', 'in', company_ids)]
```

**Partners accessible to all internal users:**
```python
[('active', '=', True), '|', ('user_id', '=', user.id), ('user_id', '=', False)]
```

---

## Field Groups — `groups` Attribute

Fields on a model can restrict visibility using the `groups` attribute:

```python
secret_field = fields.Char(groups='base.group_system')
```

The `groups` value is a comma-separated list of XML group IDs (e.g. `'base.group_user,base.group_system'`).

### How it Works

The ORM silently drops fields from `read()` and `write()` results when the current user lacks the required group. On the client side, form views use `groups_id` on `<field>` elements to show/hide widgets.

---

## See Also
- [Core/BaseModel](BaseModel.md) — ORM access rights internals
- [Modules/base](base.md) — res.users, res.company, res.groups
- [Modules/ir_actions](ir_actions.md) — server actions and report actions
