# ORM Operations

Dokumentasi Odoo 15 untuk ORM search, browse, domain operations. Source: `odoo/odoo/models.py`

## Search

```python
# Basic search
self.env['my.model'].search([('field', '=', value)])

# With domain
records = self.env['sale.order'].search([
    ('state', 'in', ['draft', 'sent']),
    ('partner_id', '=', partner.id),
])

# Count
count = self.env['my.model'].search_count([('active', '=', True)])

# Ordered
records = self.env['my.model'].search([], order='sequence, name desc')

# Limit
records = self.env['my.model'].search([], limit=100)

# Offset (pagination)
page2 = self.env['my.model'].search([], offset=100, limit=100)

# Empty search = all records
all_records = self.env['my.model'].search([])

# False domain = all records (no filter)
unfiltered = self.env['my.model'].search(False)
```

## Browse

```python
# Browse by IDs
record = self.env['my.model'].browse(1)
records = self.env['my.model'].browse([1, 2, 3])

# Chained browse
line = self.env['sale.order.line'].browse(5)
order = line.order_id  # goes through Many2one
```

## Domain Operators

| Operator | SQL Equivalent | Example |
|---|---|---|
| `=` | `=` | `[('state', '=', 'draft')]` |
| `!=` | `<>` | `[('active', '!=', False)]` |
| `>` | `>` | `[('amount', '>', 100)]` |
| `<` | `<` | `[('date', '<', today)]` |
| `>=` | `>=` | `[('priority', '>=', 3)]` |
| `<=` | `<=` | `[('price', '<=', 50)]` |
| `like` | `LIKE` | `[('name', 'like', 'test%')]` |
| `ilike` | `ILIKE` | `[('name', 'ilike', 'test')]` |
| `not like` | `NOT LIKE` | `[('name', 'not like', 'test')]` |
| `=like` | `LIKE` (regex) | `[('code', '=like', 'A%B')]` |
| `in` | `IN` | `[('state', 'in', ['a', 'b'])]` |
| `not in` | `NOT IN` | `[('type', 'not in', ['cancel'])]` |
| `child_of` | hierarchy | `[('parent_id', 'child_of', parent.id)]` |
| `parent_of` | hierarchy | `[('category_id', 'parent_of', category.id)]` |

## Complex Domains

```python
# AND (implicit)
[('a', '=', 1), ('b', '=', 2)]
# SQL: WHERE a = 1 AND b = 2

# OR
domains = ['|', ('a', '=', 1), ('b', '=', 2)]
# SQL: WHERE a = 1 OR b = 2

# NOT
['!', ('active', '=', True)]
# SQL: WHERE NOT active = True

# Combining
['&', ('a', '=', 1), '|', ('b', '=', 2), ('c', '=', 3)]
# SQL: WHERE a = 1 AND (b = 2 OR c = 3)

# Domain keywords
['&',  # AND (default)
 ('state', '=', 'draft'),
 '|',  # OR
 ('type', '=', 'a'),
 ('type', '=', 'b'),
 '!',  # NOT
 ('active', '=', False),
]

# Equivalent to: (state = 'draft') AND ((type = 'a') OR (type = 'b')) AND (NOT active = False)
```

## Read

```python
# Read specific fields
records.read(['name', 'code', 'state'])

# Read all fields (not recommended)
records.read()

# Read with computed/large dataset
for record in records:
    name = record.name  # Access, uses prefetch
```

## Write

```python
# Single field
record.write({'name': 'New Name'})

# Multiple fields
record.write({
    'name': 'Updated',
    'code': 'UPD001',
    'active': False,
})

# Multi-write on recordset
records.write({'active': False})

# Write with ids only
self.env['my.model'].browse([1, 2]).write({'active': False})
```

## Create

```python
# Single record
record = self.env['my.model'].create({'name': 'Test'})

# Batch create (Odoo 15+)
records = self.env['my.model'].create([
    {'name': 'Record 1', 'code': '001'},
    {'name': 'Record 2', 'code': '002'},
    {'name': 'Record 3', 'code': '003'},
])

# With context
record = self.env['my.model'].with_context(tracking_disable=True).create(vals)
```

## Unlink

```python
# Delete records
record.unlink()

# Delete with IDs
self.env['my.model'].browse([1, 2, 3]).unlink()

# Check access rights first
if self.env.user.has_group('base.group_system'):
    records.unlink()
```

## Copy

```python
# Duplicate record
new_record = record.copy()

# Copy with default values
new_record = record.copy(default={'code': 'NEW001'})
```

## Filter

```python
# Filter recordset
draft_records = records.filtered(lambda r: r.state == 'draft')

# Filter with field check
has_lines = records.filtered(lambda r: r.line_ids)

# Complex filter
important = records.filtered(lambda r: r.amount > 1000 and r.state == 'done')
```

## Mapped

```python
# Get field values as list
names = records.mapped('name')

# Method call on each record
names = records.mapped(lambda r: r.name)

# Nested mapped
partner_ids = records.mapped('partner_id.id')

# Nested relation
order_lines = orders.mapped('line_ids.price')
```

## Sorted

```python
# Sort recordset
sorted_records = records.sorted(lambda r: r.sequence)

# With key and reverse
sorted_records = records.sorted(lambda r: r.date_deadline, reverse=True)

# Sort by field name string
sorted_records = records.sorted('sequence')
sorted_records = records.sorted('sequence', reverse=True)
```

## Recordset Boolean

```python
# Check if empty
if records:
    pass

if not records:
    return False

# Check if single
record.ensure_one()

# Count
count = len(records)
count = records.ids and len(records) or 0

# IDs
ids = records.ids
```

## Read Group

```python
# Group by field with aggregation
data = self.env['sale.report'].read_group(
    domain=[('state', '=', 'done')],
    fields=['amount_total', 'partner_id'],
    groupby=['partner_id'],
)

# With aggregate functions
data = self.env['account.move.line'].read_group(
    [],
    fields=['debit:sum', 'credit:sum', 'account_id:count'],
    groupby=['account_id', 'date:month'],
    lazy=False,  # All groupby fields in row
)
```

## Name Search

```python
# Autocomplete-style search
results = self.env['res.partner'].name_search(
    'Acme',  # search term
    args=[('is_company', '=', True)],  # domain filter
    limit=10,
)

# Returns: [(id, display_name), ...]
```

## Ref / External ID

```python
# Get record by module.xml_id
record = self.env.ref('module.external_id')

# Get from XML
from odoo.tools import convert
record_id = convert.get_id(self, 'module.external_id')

# In controller
record = request.env.ref('module.xml_id')
```

## Environment Helpers

```python
# Clear cache
self.invalidate_cache()

# Flush pending writes
self.flush()

# Refresh from DB
self.invalidate_cache(['field_name'])

# With context
records = self.with_context(tracking_disable=True).search([...])

# Sudo (bypass ACL)
records = self.env['my.model'].sudo().search([...])
```

## See Also
- [Core/BaseModel](Core/BaseModel.md) — CRUD operations
- [Core/Fields](Core/Fields.md) — Field types
- [Core/API](Core/API.md) — @api.depends