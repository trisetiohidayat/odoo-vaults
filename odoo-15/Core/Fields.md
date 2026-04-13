# Fields — Field Types Reference

Dokumentasi Odoo 15 untuk semua field types. Source: `odoo/odoo/fields.py`

## Common Parameters

All fields accept these base parameters:

```python
fields.Char(string='Label', ...)          # string: field label (required for most)
fields.Char('Label')                       # positional also works
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `string` | str | None | Human-readable label |
| `help` | str | None | Tooltip description |
| `readonly` | bool | False | Cannot be edited in UI |
| `required` | bool | False | Mandatory field |
| `index` | bool | False | Create database index |
| `default` | value/callable | None | Default value (value or lambda function) |
| `states` | dict | None | State-dependent attributes |
| `groups` | str | None | Comma-separated XML group IDs |
| `copy` | bool | True | Copied by duplicate (ir.model.*) |
| `store` | bool | True | Stored in DB (computed fields only) |
| `track_visibility` | str | None | 'always', 'onchange', or False |
| `compute` | str | None | Compute method name |
| `inverse` | str | None | Inverse compute method |
| `search` | str | None | Custom search method |
| `related` | str | None | Related field path (dot notation) |
| `company_dependent` | bool | False | Value depends on company |
| `translate` | bool | False | Field values are translatable |
| `precompute` | bool | False | Compute on new records before save |

## Primitive Types

### Char

```python
name = fields.Char('Name', size=256, index=True)
description = fields.Char('Description')  # No size limit

# With selection constraint
state = fields.Selection([
    ('draft', 'Draft'),
    ('done', 'Done'),
], string='State', default='draft')
```

### Text

```python
notes = fields.Text('Notes')  # Unlimited size, no index
```

### Html

```python
notes = fields.Html('Notes', sanitize=True, strip_classes=True, strip_style=True)

# sanitize options
fields.Html(sanitize=False)  # No sanitization
fields.Html(sanitize=True)   # Strip dangerous tags (default)
fields.Html(sanitize_attributes=False)  # Keep all attributes
```

### Integer

```python
sequence = fields.Integer('Sequence', default=0, index=True)
```

### Float

```python
amount = fields.Float('Amount', digits=(16, 2), default=0.0)

# digits tuple: (precision, scale)
# (16, 2) = 14 integer digits + 2 decimal places
# 99999999999999.99 max
```

### Monetary

```python
amount = fields.Monetary('Amount', currency_field='currency_id')

# Requires: currency_id = fields.Many2one('res.currency')
# Automatically uses company currency context
```

### Boolean

```python
active = fields.Boolean('Active', default=True)
```

### Date

```python
from odoo.fields import Date
from datetime import date

start_date = fields.Date('Start Date', default=date.today())

# Reading
Date.to_string(record.date_field)  # '2024-01-01'
Date.from_string('2024-01-01')    # datetime.date(2024, 1, 1)

# Domain
[('date_field', '>=', fields.Date.today())]
```

### Datetime

```python
from odoo.fields import Datetime
from datetime import datetime

start_date = fields.Datetime('Start Date', default=datetime.now())

# Reading
Datetime.to_string(dt)              # '2024-01-01 00:00:00'
Datetime.from_string('2024-01-01 00:00:00')  # datetime.datetime
Datetime.now()                      # Current datetime

# With timezone
record.date_begin = Datetime.now()   # Set to current time
```

### Binary

```python
data = fields.Binary('File Data', attachment=True)
```

### Selection

```python
state = fields.Selection([
    ('draft', 'Draft'),
    ('confirm', 'Confirmed'),
    ('done', 'Done'),
    ('cancel', 'Cancelled'),
], string='State', default='draft', index=True, readonly=True,
   track_visibility='onchange')

# Dynamic selection
priority = fields.Selection(
    selection='_selection_priority',
    compute='_compute_priority',
)

@api.model
def _selection_priority(self):
    return [(code, label) for code, label in self._get_priority_options()]
```

### Integer/Select Selection (Integer enum)

```python
priority = fields.Selection([
    (1, 'Low'),
    (2, 'Medium'),
    (3, 'High'),
], 'Priority')
```

## Relational Fields

### Many2one

```python
partner_id = fields.Many2one('res.partner', string='Partner',
                             ondelete='restrict')

# ondelete options: 'cascade', 'restrict', 'set null', 'set default', None

# Related
country_id = fields.Many2one('res.country', 'Country')

# Domain filter
user_id = fields.Many2one('res.users', string='Responsible',
                          domain="[('partner_id', '=', partner_id)]")
```

### One2many

```python
line_ids = fields.One2many('my.model.line', 'parent_id', string='Lines',
                           inverse_name='parent_id')

# Inverse_name points to Many2one back-reference on child model
# Not stored, always computed
```

### Many2many

```python
tag_ids = fields.Many2many('my.model.tag', 'my_model_tag_rel',
                            'model_id', 'tag_id', string='Tags')

# Three parts: relation table, left FK, right FK
# Can use string label only:
tag_ids = fields.Many2many('my.model.tag', string='Tags')  # auto-generated table

# With company domain
warehouse_ids = fields.Many2many('stock.warehouse', string='Warehouses',
                                  company_dependent=True)
```

### Reference

```python
reference = fields.Reference([
    ('account.move', 'Journal Entry'),
    ('res.partner', 'Partner'),
], string='Reference')
```

## Special Fields

### Computed Fields

```python
# Standard compute
amount = fields.Float(compute='_compute_amount',
                      store=True,  # store in DB
                      readonly=True)

@api.depends('price', 'quantity')
def _compute_amount(self):
    for record in self:
        record.amount = record.price * record.quantity

# With search capability (writable computed field)
list_price = fields.Float(
    compute='_compute_list_price',
    inverse='_inverse_list_price',
    search='_search_list_price',
    store=True,
)

def _search_list_price(self, operator, value):
    return [('lst_price', operator, value)]
```

### Related Fields

```python
# Simple related
street = fields.Char(related='partner_id.street', readonly=True)

# With store (computed + stored)
city = fields.Char(related='partner_id.city', store=True, readonly=True)
```

### Binary (attachment)

```python
# Store as attachment (efficient for large files)
datas = fields.Binary('File', attachment=True)

# Attachment stored in ir.attachment table
# Saves file path in database, actual file on disk
```

### Serialized

```python
data = fields.Serialized('JSON Data')

# Stores Python dict as JSON string
# Useful for arbitrary data storage
```

### Image

```python
image = fields.Binary('Image', attachment=True)
image_medium = fields.Binary('Medium Image', compute='_compute_images')
image_small = fields.Binary('Small Image', compute='_compute_images')

@api.depends('image')
def _compute_images(self):
    for record in self:
        record.image_medium = tools.image_resize_image_medium(record.image)
        record.image_small = tools.image_resize_image_small(record.image)
```

### Property (ir.property based)

```python
property_product_pricelist = fields.Many2one(
    'product.pricelist', 'Pricelist',
    company_dependent=True,
)
```

## Field Attributes & Hints

### String

Label untuk field, digunakan di UI. Bisa juga di-set via `_column` dict di old-style.

### Help

Tooltip yang muncul saat hover.

### Index

Buat database index untuk query performance. Boleh juga pake `index=True`.

### States

State-dependent field attributes:

```python
fields.Char('Name', states={
    'draft': [('readonly', False)],
    'done': [('readonly', True)],
})
```

### Groups

Field visibility berdasarkan security group:

```python
fields.Char('Admin Field', groups='base.group_system')
```

### Company Dependent

Value berbeda per company:

```python
journal_id = fields.Many2one('account.journal', company_dependent=True)
```

### Copy

Disable copying di duplicate operation:

```python
sequence = fields.Integer('Sequence', copy=False)
```

## See Also
- [Core/BaseModel](Core/BaseModel.md) — Model definition, CRUD
- [Core/API](Core/API.md) — @api.depends decorator
- [Tools/ORM Operations](Tools/ORM Operations.md) — search(), browse(), domain operators