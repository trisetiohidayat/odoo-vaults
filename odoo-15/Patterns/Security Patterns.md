# Security Patterns

Dokumentasi Odoo 15 untuk access control dan security.

## Access Control List (ACL) — CSV Files

File: `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_my_model_user,my.model user,model_my_model,base.group_user,1,1,0,0
access_my_model_manager,my.model manager,model_my_model,base.group_system,1,1,1,1
access_my_model_admin,my.model admin,model_my_model,,1,1,1,1
```

**Columns:**
- `id` — unique identifier (access_my_model_user)
- `name` — display name
- `model_id:id` — model external ID (model_my_model)
- `group_id:id` — group external ID (empty = global)
- `perm_read/perm_write/perm_create/perm_unlink` — 1=yes, 0=no

### Access Levels

| Flag | CRUD Operation |
|---|---|
| `perm_read` | `read()` — browse, read field values |
| `perm_write` | `write()` — update fields |
| `perm_create` | `create()` — new records |
| `perm_unlink` | `unlink()` — delete records |

### Group-based ACL

```csv
# User access (via base.group_user)
access_sale_order_user,sale order user,model_sale_order,base.group_user,1,1,1,0

# Manager access (via sales_team.group_sale_manager)
access_sale_order_manager,sale order manager,model_sale_order,sales_team.group_sale_manager,1,1,1,1
```

## Record Rules (ir.rule)

Filter records accessible based on domain.

```python
# In Python (model definition)
class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model'

    # Automatic record rules based on company field
    _check_company_auto = True

# Or in XML:
<record id="rule_my_model_user" model="ir.rule">
    <field name="name">My Model: user can only see own records</field>
    <field name="model_id" ref="model_my_model"/>
    <field name="groups" eval="[ref('base.group_user')]"/>
    <field name="domain_force">[('user_id', '=', user.id)]</field>
</record>
```

### Record Rule Domain

```python
# Owner only
[('user_id', '=', user.id)]

# Company-based
[('company_id', 'in', user.company_ids.ids)]

# Public (no restriction)
[(1, '=', 1)]

# Partner-based
[('partner_id', 'child_of', user.partner_id.ids)]
```

## Field Groups (groups)

```python
# Restrict field visibility
api_key = fields.Char('API Key', groups='base.group_system')
secret_field = fields.Char('Secret', groups='base.group_system')

# Field-only writeable by admin
admin_field = fields.Char('Admin Field', groups='base.group_system')

# Web-readable by user, admin-only write
```

## Method Groups

```python
# Controller
@http.route('/api/admin/action', auth='user', methods=['POST'])
def admin_action(self, **kwargs):
    if not request.env.user.has_group('base.group_system'):
        raise AccessError(_('Admin access required'))
    # proceed
```

## Portal / Public Access

### Public Controller

```python
class PublicController(http.Controller):
    @http.route('/public/page', type='http', auth='public', website=True)
    def public_page(self):
        # Accessible without login
        return request.render('my_module.public_page', {})
```

### Portal Inheritance

```python
class SaleOrderExt(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'

    # Portal: user can only see their own orders
    portal_share_url = fields.Char('Portal URL', compute='_compute_portal_url')

    def _compute_portal_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            record.portal_share_url = f"{base_url}/my/orders/{record.id}"
```

## Security Checklist

```python
# 1. Define model
class MyModel(models.Model):
    _name = 'my.model'

    # 2. Add security field
    company_id = fields.Many2one('res.company', 'Company',
                                 index=True, ondelete='restrict')

    # 3. Automatic company filtering
    _check_company_auto = True

    # 4. Create ACL CSV:
    # access_my_model_user,my.model user,model_my_model,base.group_user,1,1,1,0

    # 5. Create record rules:
    # domain_force: [('company_id', 'in', user.company_ids.ids)]
```

## SQL Constraints (Security)

```python
_sql_constraints = [
    ('name_unique', 'UNIQUE (name, company_id)',
     'Name must be unique per company'),
]
```

## Superuser Mode (Bypass ACL)

```python
# Sudo mode — bypass all access rights
self.env['my.model'].sudo().search([...])

# Sudo as specific user
self.env['my.model'].sudo(user_id).search([...])

# For web controllers
request.env['my.model'].sudo().create(vals)
```

## Button Security (XML)

```xml
<!-- Only visible to system admin -->
<button name="action_admin_only" string="Admin Action"
        type="object" groups="base.group_system"/>

<!-- Only visible to manager -->
<button name="action_manager" string="Manager Action"
        type="object" groups="sales_team.group_sale_manager"/>
```

## See Also
- [Core/BaseModel](Core/BaseModel.md) — Model definition
- [Core/HTTP Controller](Core/HTTP Controller.md) — Auth types
- [Core/Exceptions](Core/Exceptions.md) — AccessError
- [Modules/res.partner](Modules/res.partner.md) — Partner security