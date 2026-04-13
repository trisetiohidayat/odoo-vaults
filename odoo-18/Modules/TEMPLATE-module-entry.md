---
type: module
name: {module_name}
version: Odoo 18
tags: [module, {module}]
source: ~/odoo/odoo18/odoo/addons/{module}/
---

# {Module Name}

> Replace this template with actual documentation after researching the module.

## Overview

**Module:** `{module}`
**Location:** `~/odoo/odoo18/odoo/addons/{module}/`
**Models:** (list model names here)
**Depends:** (list dependencies)

## Models

### `{model.name}`

```python
class ModelName(models.Model):
    _name = '{model.name}'
    _description = '...'
    _inherit = [...]
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | — |
| `active` | Boolean | — |

## Methods

### `action_*`

```python
def action_*(self):
    """Description."""
    for rec in self:
        rec.write({'state': 'done'})
    return True
```

## Workflow

```
draft ──[confirm]──→ confirmed ──[done]──→ done
  │                      │
  └──[cancel]──→ cancelled ←──[cancel]──┘
```

## Dependencies

- [Modules/{}](Modules/{}.md)
- [Modules/{}](Modules/{}.md)

## Related Links
- [Tools/Modules Inventory](Modules Inventory.md)
- [Patterns/Workflow Patterns](Workflow Patterns.md)
