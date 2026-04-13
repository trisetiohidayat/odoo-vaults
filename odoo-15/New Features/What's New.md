# What's New — Odoo 15

## Key Changes in Odoo 15

## New Features

### 1. Studio & Customization
- Enhanced Studio UI
- Better layout customization
- Universal search improvements

### 2. Approval Workflow
- New approval system
- Multi-level approval routing
- `approval` and `approval_routing` modules

### 3. Document Management
- `documents` module
- Document workspace
- Tags, folders, access control

### 4. Spreadsheet
- Built-in spreadsheet engine
- `spreadsheet` module
- `spreadsheet_account` for financial charts

### 5. Barcode (Native)
- Native barcode scanner in web client
- Works on mobile browsers

### 6. Portal Improvements
- Better portal UI
- Document sharing
- Real-time collaboration

### 7. Discuss (New Mail UI)
- Improved messaging interface
- Channel management
- Mobile-friendly

## Technical Changes

### Decorators
```python
# Odoo 15 decorators
@api.model
@api.depends('field1', 'field2')
@api.onchange('field')
@api.constrains('field')
@api.returns(model, func)
@api.model_create_multi  # batch create
```

### Field Types (Same as before)
- Char, Text, Html, Integer, Float, Monetary
- Boolean, Selection, Date, Datetime
- Many2one, One2many, Many2many
- Binary, Image, Serialized

### Computed Fields
```python
# Pattern unchanged from Odoo 13/14
amount = fields.Float(compute='_compute_amount', store=True)

@api.depends('price', 'quantity')
def _compute_amount(self):
    for record in self:
        record.amount = record.price * record.quantity
```

### Portal Mixin
```python
# Portal access control
from odoo.addons.portal.models.portal_mixin import PortalMixin

class MyModel(models.Model, PortalMixin):
    _name = 'my.model'
    _inherit = ['portal.mixin', ...]
    # Provides _compute_access_url()
```

### Website Trackers
- Google Analytics 4 support
- Google Maps API key
- Social links per website

## Removed / Deprecated

### Deprecated Methods (still work)
- `@api.one` — Deprecated, use record iteration
- `Warning` exception → use `UserError`

## Compatibility Notes

- Python 3.8+ recommended
- PostgreSQL 10+
- Odoo 15 uses `markupsafe` instead of `jinja2`-related escaping
- Field `translate=True` works for Char/Text fields

## Key Module Updates

| Module | New in Odoo 15 |
|---|---|
| `documents` | NEW — Document management |
| `approval` | NEW — Approval workflow |
| `spreadsheet` | NEW — Spreadsheet |
| `website_livechat` | Enhanced |
| `mail` | Discuss UI redesign |
| `project` | Timesheet integration |

## See Also
- [[Core/BaseModel]] — ORM foundation
- [[Core/API]] — API decorators
- [[Tools/ORM Operations]] — Search, browse, CRUD