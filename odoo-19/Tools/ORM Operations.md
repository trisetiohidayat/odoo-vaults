---
type: reference
tags: [odoo, odoo19, orm, search, browse, create, write]
created: 2026-04-06
---

# ORM Operations

## Quick Reference

All ORM operations work on [Core/BaseModel](core/basemodel.md) recordsets.

## Environment

```python
# Get environment
env = self.env

# Access model
Model = self.env['model.name']

# Current user
uid = self.env.uid
user = self.env.user
company = self.env.company
```

## Search

```python
# Basic search
records = self.env['model.name'].search([('field', '=', 'value')])

# Multiple conditions
records = self.env['model.name'].search([
    ('field1', '=', 'value1'),
    ('field2', '>', 100),
    '|', ('field3', '=', 'a'), ('field3', '=', 'b'),
])

# With limit
records = self.env['model.name'].search([], limit=10)

# Search all
records = self.env['model.name'].search([])

# Search count
count = self.env['model.name'].search_count([('active', '=', True)])
```

## Browse

```python
# Single ID
record = self.env['model.name'].browse(1)

# Multiple IDs
records = self.env['model.name'].browse([1, 2, 3])

# Empty recordset
empty = self.env['model.name']
```

## Create

```python
# Single record
record = self.env['model.name'].create({
    'name': 'New Record',
    'value': 100,
})

# Multiple records
records = self.env['model.name'].create([
    {'name': 'Record 1'},
    {'name': 'Record 2'},
])
```

## Write

```python
# Update single record
record.write({'name': 'Updated'})

# Update multiple records
records.write({'active': False})

# Update with search
self.env['model.name'].search([('active', '=', False)]).write({
    'active': True
})
```

## Unlink

```python
# Delete records
records.unlink()
```

## Read

```python
# Read specific fields
data = records.read(['name', 'value'])

# Read single field values
names = records.mapped('name')

# Read as dict
vals = records.read()[0]  # First record
```

## Domain Operators

| Operator | Meaning |
|----------|---------|
| `=` | Equals |
| `!=` | Not equals |
| `>`, `<` | Greater/Less than |
| `>=`, `<=` | Greater/Less or equal |
| `like` | Contains (case-sensitive) |
| `ilike` | Contains (case-insensitive) |
| `in` | In list |
| `not in` | Not in list |
| `child_of` | Child of |
| `'&'` | AND (default) |
| `'|'` | OR |
| `'!'` | NOT |

## Related

- [Core/BaseModel](core/basemodel.md) - Model operations
- [Core/API](core/api.md) - Environment access
- [Core/Fields](core/fields.md) - Field types
- [Core/Exceptions](core/exceptions.md) - Error handling
