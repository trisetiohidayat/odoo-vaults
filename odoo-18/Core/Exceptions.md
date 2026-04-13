---
type: core
name: Exceptions
version: Odoo 18
tags: [core, exceptions, error-handling]
source: ~/odoo/odoo18/odoo/odoo/exceptions.py
---

# Exceptions

## Validation / User Errors

```python
from odoo.exceptions import (
    ValidationError, UserError, AccessError,
    AccessDenied, MissingError, RedirectWarning
)

# UserError — blocks operation with a clear message (most common)
raise UserError('You cannot delete a confirmed order.')

# ValidationError — field validation (from @api.constrains or in Python)
raise ValidationError('Start date must be before end date.')

# AccessError — permission denied
raise AccessError('You do not have access to this document.')
```

## System Errors

```python
# AccessDenied — full lockout (no retry option)
raise AccessDenied()

# MissingError — referenced record does not exist
raise MissingError('Record not found')

# RedirectWarning — warns user and redirects to another record
raise RedirectWarning(
    'You must first cancel related entries.',
    action_id,  # ir.actions.act_window ID to redirect to
    'View Entries'
)
```

## Cache Error

```python
from odoo.exceptions import CacheMiss

try:
    value = rec.name  # may raise CacheMiss if field not in cache
except CacheMiss:
    value = rec._fetch_access_error()
```

---

## Related Links
- [Core/API](Core/API.md) — Decorators that raise ValidationError
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — AccessError context
