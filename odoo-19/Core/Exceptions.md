---
type: core
module: exceptions
tags: [odoo, odoo19, exceptions, error, validation]
created: 2026-04-06
---

# Exceptions

## Overview

Custom exceptions untuk Odoo 19.

**Location:** `~/odoo/odoo19/odoo/odoo/exceptions.py`

## Exception Types

| Exception | Use Case |
|-----------|----------|
| `ValidationError` | Field validation failed |
| `UserError` | User-friendly error message |
| `AccessError` | Access rights violation |
| `MissingError` | Record not found |
| `AccessDenied` | Login denied |
| `RedirectWarning` | Redirect with warning |

## Usage Examples

### ValidationError

```python
from odoo.exceptions import ValidationError

@api.constrains('start_date', 'end_date')
def _check_dates(self):
    if self.start_date > self.end_date:
        raise ValidationError(
            'Start date must be before end date!'
        )
```

### UserError

```python
from odoo.exceptions import UserError

def action_confirm(self):
    if not self.partner_id:
        raise UserError('Please select a partner first!')
```

### AccessError

```python
from odoo.exceptions import AccessError

def check_access(self):
    if not self.env.user.has_group('base.group_user'):
        raise AccessError(
            'You do not have access to this record!'
        )
```

### RedirectWarning

```python
from odoo.exceptions import RedirectWarning

raise RedirectWarning(
    'Configuration required!',
    {
        'type': 'ir.actions.act_window',
        'res_model': 'res.config.settings',
        'target': 'new',
    },
    'Configure Settings'
)
```

## ValidationError vs UserError

| ValidationError | UserError |
|-----------------|-----------|
| `@api.constrains` | `@api.depends` or action |
| Rolls back transaction | Keeps transaction |
| Form validation | Action validation |

## Related

- [Core/BaseModel](Core/BaseModel.md) - Model methods
- [Core/API](Core/API.md) - @api.constrains
- [Patterns/Security Patterns](Patterns/Security-Patterns.md) - AccessError
- [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) - Action validation
