# API Changes — Odoo 15 vs Previous

## Compatibility

Odoo 15 maintains backward compatibility with Odoo 14 patterns. Key changes:

## New Decorators in Odoo 15

### @api.model_create_multi

Batch creation, returns recordset.

```python
@api.model_create_multi
def create(self, vals_list):
    # vals_list: list of dicts
    return super().create(vals_list)

# Usage
records = self.env['my.model'].create([
    {'name': 'A'},
    {'name': 'B'},
])
```

## Portal Mixin

```python
from odoo.addons.portal.models.portal_mixin import PortalMixin

class MyModel(models.Model, PortalMixin):
    _name = 'my.model'
    _inherit = ['portal.mixin', ...]

    # Auto-provides:
    # - access_url (compute)
    # - _compute_access_url()
    # - portal_layout()
```

## Mail Thread Changes

```python
# Standard mail.thread inheritance (same as 14)
class MyModel(models.Model):
    _name = 'my.model'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    message_follower_ids = fields.Many2many(...)
    message_ids = fields.One2many(...)
    activity_ids = fields.One2many(...)
```

## Deprecated Patterns

| Old | New | Notes |
|---|---|---|
| `@api.one` | record iteration | Deprecated, still works |
| `Warning` | `UserError` | Same behavior |
| `fields.binary('binary')` | `fields.Binary()` | Same |

## Field Changes

### Image Attachment

```python
# Same pattern as before
image = fields.Binary("Image", attachment=True)
```

### Monetary

```python
# Always pair with currency_field
amount = fields.Monetary('Amount', currency_field='currency_id')
currency_id = fields.Many2one('res.currency')
```

## See Also
- [Core/API](API.md) — Full decorator reference
- [Core/BaseModel](BaseModel.md) — Model definition
- [Core/Fields](Fields.md) — Field types