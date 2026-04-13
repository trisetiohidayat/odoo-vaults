# Exceptions

Dokumentasi Odoo 15 untuk exception types. Source: `odoo/odoo/exceptions.py`

## Exception Hierarchy

```
Exception
├── odoo.exceptions.ValidationError
├── odoo.exceptions.UserError
├── odoo.exceptions.AccessError
├── odoo.exceptions.AccessDenied
├── odoo.exceptions.MissingError
├── odoo.exceptions.RedirectWarning
├── odoo.exceptions.Warning
└── odoo.tools.exceptions.AccessDenied (no DB)
```

## ValidationError

Field validation / constraint violation. User salah input.

```python
from odoo.exceptions import ValidationError
from odoo import _

raise ValidationError(_('Validation message here'))

# In @api.constrains
@api.constrains('start_date', 'end_date')
def _check_dates(self):
    for record in self:
        if record.start_date > record.end_date:
            raise ValidationError(_('Start Date must be before End Date'))

# With field context
raise ValidationError(_('Field X is required'))

# Multi-line
raise ValidationError(_(
    'Error line 1\n'
    'Error line 2\n'
    'Error line 3'
))
```

**Behavior:**
- Displayed as user-friendly error message in UI
- Does NOT rollback the transaction (caller handles it)
- Used in `@api.constrains`, `@api.onchange`, `write()`, `create()`

## UserError

General user-level error. Biasa untuk business logic errors.

```python
from odoo.exceptions import UserError

raise UserError(_('Cannot delete this record because it is referenced'))

# In workflow / action method
@api.multi
def action_cancel(self):
    if self.filtered(lambda r: r.state == 'done'):
        raise UserError(_('Cannot cancel a done record'))
    self.write({'state': 'cancel'})

# With context
raise UserError(_('Operation not allowed: %s') % reason)
```

**Note:** `UserError` sudah termasuk yang sebelumnya dikenal sebagai `Warning` di Odoo versi lama.

## AccessError

Access rights violation (read/write/unlink tidak diizinkan).

```python
from odoo.exceptions import AccessError

raise AccessError(_('You do not have access to this record'))

# Usually raised by ORM internally
# Manual raise only in special cases:
if not user.has_group('base.group_system'):
    raise AccessError(_('Administrator access required'))
```

**Note:** Jangan confuse dengan `AccessDenied` — `AccessError` ditampilkan ke user,
`AccessDenied` digunakan untuk login/auth failures.

## AccessDenied

Authentication / login failure. Tidak bisa akses sistem.

```python
from odoo.tools.exceptions import AccessDenied

raise AccessDenied()

# In auth methods
# This will redirect to login page with "Access Denied" message
```

## MissingError

Record tidak ditemukan saat browse/read.

```python
from odoo.exceptions import MissingError

raise MissingError(_('Record not found'))

# ORM raises this internally when:
# self.env['model'].browse([999]).name
# -> record deleted between read and access
```

## RedirectWarning

Redirect user ke halaman lain (biasanya login atau setup wizard).

```python
from odoo.exceptions import RedirectWarning

raise RedirectWarning(
    _('Please configure your company data'),
    5,  # action ID to redirect to
    _('Go to Settings'),
)

# Parameters: message, action_id, button_text, additional_context
```

## Warning (Deprecated)

Alias lama untuk `UserError`. **Deprecated, use UserError**.

```python
from odoo.exceptions import Warning  # Deprecated

raise Warning(_('This is deprecated'))
# Shows deprecation warning in logs
```

## Traceback Utilities

```python
from odoo.tools import format_exception

# Format exception for logging
error_info = format_exception(*sys.exc_info())
```

## Exception Usage in Code

### In Model Methods

```python
@api.multi
def unlink(self):
    for record in self:
        if record.has_children():
            raise UserError(
                _('Cannot delete %s because it has child records.')
                % record.name
            )
    return super().unlink()

@api.constrains('code')
def _check_code(self):
    for record in self:
        if not record.code:
            raise ValidationError(_('Code is required'))
```

### In Controllers

```python
@http.route('/my/action', auth='user')
def my_action(self, **kwargs):
    try:
        self.env['my.model'].browse(kwargs['id']).unlink()
    except UserError as e:
        return request.render('my_module.error', {
            'error': str(e),
        })
```

## See Also
- [Core/API](Core/API.md) — @api.constrains decorator
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — Access rights, groups
- [Core/BaseModel](Core/BaseModel.md) — CRUD operations