---
type: pattern
tags: [odoo, odoo19, security, acl, access, record-rules]
created: 2026-04-06
---

# Security Patterns

## Overview

Multi-layer security system for Odoo.

## Access Control List (ACL)

**File:** `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sale_order_user,sale.order user,model_sale_order,base.group_user,1,1,1,0
access_sale_order_manager,sale.order manager,model_sale_order,sales_team.group_sale_manager,1,1,1,1
access_my_model_user,my.model user,model_my_model,base.group_user,1,1,1,1
```

## Record Rules

**File:** `security/ir.rule.xml`

```xml
<record id="sale_order_rule_user" model="ir.rule">
    <field name="name">Sale Order: user: own only</field>
    <field name="model_id" ref="model_sale_order"/>
    <field name="domain_force">[('user_id', '=', user.id)]</field>
    <field name="groups" eval="[(4, ref('base.group_user'))]"/>
</record>

<record id="sale_order_rule_manager" model="ir.rule">
    <field name="name">Sale Order: manager: all</field>
    <field name="model_id" ref="model_sale_order"/>
    <field name="domain_force">[(1, '=', 1)]</field>
    <field name="groups" eval="[(4, ref('sales_team.group_sale_manager'))]"/>
</record>
```

## Groups in Code

```python
# Check in model
if self.user_has_groups('base.group_system'):
    # Admin only
    pass

if not self.user_has_groups('base.group_user'):
    raise AccessError('Access denied!')

# Groups attribute on field
custom_field = fields.Char(
    'Custom',
    groups='base.group_user'
)

# Field only for managers
secret_field = fields.Char(
    'Secret',
    groups='base.group_system'
)
```

## Security Layers

| Layer | File | Purpose |
|-------|------|---------|
| Groups | `res.groups` | Feature access |
| ACL | `ir.model.access.csv` | Model CRUD |
| Record Rules | `ir.rule` | Record filtering |
| Field Groups | `groups=` | Field visibility |

## Sudo Mode

```python
# Bypass ACL temporarily
records = self.env['restricted.model'].sudo().search([])

# With user context
admin_env = self.env(user=1)  # User ID 1
records = admin_env['model'].search([])
```

## Related

- [[Core/BaseModel]] - Model access
- [[Core/API]] - @api.model for superuser
- [[Core/Exceptions]] - AccessError
- [[Patterns/Workflow Patterns]] - State-based security
