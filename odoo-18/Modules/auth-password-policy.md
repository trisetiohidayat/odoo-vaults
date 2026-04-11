---
Module: auth_password_policy
Version: Odoo 18
Type: Core
Tags: #auth #security #password #orm
---

# auth_password_policy — Password Strength Policy

> Password strength enforcement module. Applies minimum-length rules at user creation and password change. Single configurable parameter: `minlength`.

**Source:** `~/odoo/odoo18/odoo/addons/auth_password_policy/`
**Manifest:** `__manifest__.py`
**Depends:** `base_setup`, `web`
**License:** LGPL-3

---

## Models

### `res.config.settings` — Password Policy Configuration

Extended from `base_setup.res.config.settings`. Stores the password policy as a system-wide `ir.config_parameter`.

**Inheritance:** `_inherit = 'res.config.settings'`

#### Fields

| Field | Type | Config Parameter | Default | Description |
|-------|------|-----------------|---------|-------------|
| `minlength` | `Integer` | `auth_password_policy.minlength` | `0` | Minimum number of characters passwords must contain. `0` disables the policy. |

#### Methods

| Method | Decorator | Notes |
|--------|-----------|-------|
| `_on_change_mins()` | `@api.onchange('minlength')` | Clamps value to `max(0, self.minlength)` — prevents negative values. |

#### L4: How the Config Parameter Works

The `minlength` field uses `config_parameter=...` which maps directly to `ir.config_parameter`. This means:
- The value is stored in the `ir_config` table as `auth_password_policy.minlength`.
- It is readable from anywhere via `self.env['ir.config_parameter'].sudo().get_param('auth_password_policy.minlength')`.
- **Install-time default:** `data/defaults.xml` sets noupdate default to `8`:

```xml
<record model="ir.config_parameter" id="minlength" forcecreate="True">
    <field name="key">auth_password_policy.minlength</field>
    <field name="value">8</field>
</record>
```

This means out of the box, Odoo 18 enforces a **minimum password length of 8 characters**.

---

### `res.users` — Password Policy Enforcement

Extended from `base.model.res.users`. Adds the password policy check method.

**Inheritance:** `_inherit = 'res.users'`

#### Methods

**`get_password_policy()`** — `@api.model`
Reads the current password policy from `ir.config_parameter` and returns it as a dict for the JS frontend.

```python
def get_password_policy(self):
    params = self.env['ir.config_parameter'].sudo()
    return {
        'minlength': int(params.get_param('auth_password_policy.minlength', default=0)),
    }
```

The frontend uses this to display a live password strength indicator on the password field.

---

**`_set_password()`** — Override
Hooks into the password-set flow. Called by the web controller when a user sets or changes their password.

```python
def _set_password(self):
    self._check_password_policy(self.mapped('password'))
    super(ResUsers, self)._set_password()
```

**Call chain:** `web` controller → `res.users._set_password()` → `_check_password_policy()` → parent's `_set_password()` writes the hashed password to the DB.

**When it runs:**
- User changes their own password from the web UI.
- Admin creates a user and sets an initial password.
- User resets password via the "Forgot Password" flow (if the reset email link is followed).

---

**`_check_password_policy(passwords)`** — Core validation method

```python
def _check_password_policy(self, passwords):
    failures = []
    params = self.env['ir.config_parameter'].sudo()

    minlength = int(params.get_param('auth_password_policy.minlength', default=0))
    for password in passwords:
        if not password:
            continue
        if len(password) < minlength:
            failures.append(_("Your password must contain at least %(minimal_length)d characters and only has %(current_count)d.",
                              minimal_length=minlength, current_count=len(password)))

    if failures:
        raise UserError(u'\n\n '.join(failures))
```

**L4: What it actually validates**

The method only enforces **minimum length**. It does NOT check:
- Uppercase letters (`minidentities`)
- Lowercase letters
- Digits
- Special characters
- Dictionary words
- Common password patterns

This is a deliberate simplification. Odoo 18's `auth_password_policy` only applies a length gate. Any complexity requirements (uppercase, symbols, etc.) must be implemented as custom modules or inherited classes.

**Key behaviors:**
1. Empty passwords are skipped — the method does not block empty passwords. This means a blank password is valid under the policy (length check is `>= 0` which anything passes, but empty strings are skipped).
2. If multiple passwords fail, all failure messages are joined with `\n\n` and raised as a single `UserError`.
3. The `UserError` is raised before `super()._set_password()` is called — so the password is never written to the DB if it fails the policy.
4. The `@api.model` decorator means `self` is a empty recordset — no actual user record is loaded.

---

## Password Change Flow (Full Sequence)

```
User submits new password (web UI)
    → res.users._set_password()
        → _check_password_policy(passwords)   ← raises UserError if too short
        → super()._set_password()             ← writes crypted password to DB
```

## L4: Customizing the Password Policy

### Option 1: Extend `_check_password_policy` via `_inherit`

```python
class ResUsers(models.Model):
    _inherit = 'res.users'

    def _check_password_policy(self, passwords):
        # Call parent first
        super()._check_password_policy(passwords)

        # Add your own checks
        for password in passwords:
            if not password:
                continue
            if not any(c.isupper() for c in password):
                raise UserError("Password must contain at least one uppercase letter")
            if not any(c.isdigit() for c in password):
                raise UserError("Password must contain at least one digit")
```

### Option 2: Add new config parameters

Extend `res.config.settings` to add more fields, then read them in `_check_password_policy`:

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    minlength = fields.Integer(
        config_parameter="auth_password_policy.minlength", default=0)
    min_upper = fields.Integer(
        config_parameter="auth_password_policy.min_upper", default=0)
    min_digit = fields.Integer(
        config_parameter="auth_password_policy.min_digit", default=0)
```

---

## What Odoo Does NOT Do

| Feature | Status |
|---------|--------|
| Minimum length (`minlength`) | Implemented (default: 8) |
| Minimum uppercase characters | NOT implemented |
| Minimum lowercase characters | NOT implemented |
| Minimum digits | NOT implemented |
| Minimum special characters | NOT implemented |
| Password history (prevent reuse) | NOT implemented |
| Account lockout after failed attempts | NOT implemented (handled by `base` module rate limiting) |
| Password expiry / aging | NOT implemented (available in Enterprise) |

---

## Related Models

- `res.users` — `_set_password()` is defined in `addons/base/models/res_users.py`. The `auth_password_policy` module overrides it to insert the policy check.
- `ir.config_parameter` — Stores `auth_password_policy.minlength` as a system-wide setting.

---

## Architecture Notes

- **No new database tables** are created by this module.
- **No `res.company` extension** — password policy is global, not per-company.
- The policy is enforced server-side only. The JS `password_policy.js` asset provides client-side feedback before form submission.
- The CSS `password_field.css` styles the live-strength indicator shown below the password field.

---

## See Also

- [[Core/API]] — `@api.model` decorator context
- [[Core/Fields]] — `config_parameter` field type
- [[Patterns/Security Patterns]] — ACL and access control in Odoo
