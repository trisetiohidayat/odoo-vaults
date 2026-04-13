---
tags: [odoo, odoo17, exceptions]
---

# Exceptions

**File:** `odoo/odoo/exceptions.py`

## Exception Types

| Exception | Use Case |
|-----------|----------|
| `ValidationError` | User input validation (shown as validation error) |
| `UserError` | General user-facing errors (shown as error dialog) |
| `AccessError` | Permission denied |
| `AccessDenied` | Login failed / forbidden |
| `MissingError` | Referenced record doesn't exist |
| `RedirectWarning` | Redirect user to another page |

## Usage

```python
from odoo import _
from odoo.exceptions import ValidationError, UserError

# Validation (red warning on field)
raise ValidationError(_('End date must be after start date'))

# User Error (popup dialog)
raise UserError(_('Cannot delete this record'))

# Redirect Warning (redirect to another view)
raise RedirectWarning(
    _('Record not found'),
    '/' + 'web' + '/#id=' + str(record.id),
    _('Go to record'),
    'try_value'
)
```

## See Also
- [Core/API](core/api.md) — @api.constrains
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md)
