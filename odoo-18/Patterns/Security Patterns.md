---
type: pattern
name: Security Patterns
version: Odoo 18
tags: [patterns, security, acl, ir.rule]
---

# Security Patterns

## Record Rules (`ir.rule`)

```xml
<!-- res.partner — only see own contacts + all internal -->
<record id="partner_comp_rule" model="ir.rule">
    <field name="name">Partner: see only own contacts</field>
    <field name="model_id" ref="base.model_res_partner"/>
    <field name="domain_force">
        ['|', ('user_id', '=', user.id), ('user_id', '=', False)]
    </field>
</record>
```

## Field Groups

```python
# Field only visible to Settings > Users > Manage Users
user_id = fields.Many2one('res.users', string='Responsible',
                           groups='base.group_system')

# Field only for accounting managers
amount = fields.Float(string='Amount',
                       groups='account.group_account_manager')
```

## Record Rule with Company

```python
domain_force = [
    ('company_id', 'in', [user.company_id.id, False]),
    '|',
    ('company_id', '=', False),
    ('company_id', 'child_of', [user.company_id.id]),
]
```

## Access Control (CSV)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
sale_order_user,sale.order.user,base.group_user,1,1,1,1,0
sale_order_manager,sale.order.manager,base.group_sales_manager,1,1,1,1,1
```

## No-ACL Internal Models

```python
# For transient/wizard models that need no access control
class MyWizard(models.TransientModel):
    _name = 'my.wizard'
    _description = 'My Wizard'
    # TransientModel automatically has no DB table ACL
    # All users can create/unlink records (cleaned up automatically)
```

## sudo() for System Operations

```python
# Bypass ACL when doing automated operations
def _sync_partner_from_user(self):
    # System needs to write on partner during user creation
    self.sudo().write({'name': self.name, 'email': self.email})
```

---

## Related Links
- [Core/BaseModel](BaseModel.md) — CRUD access
- [Modules/Account](account.md) — Company-dependent security
