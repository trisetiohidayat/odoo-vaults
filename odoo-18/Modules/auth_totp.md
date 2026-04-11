# auth_totp Module (Odoo 18)

## Overview

The `auth_totp` module implements Time-based One-Time Password (TOTP) two-factor authentication for Odoo users. It generates and validates 6-digit TOTP codes using the pyotp library.

**Module Path:** `auth_totp/`
**Key Models:** `auth_totp.device` (trusted devices), `res.users` (extended)
**Dependencies:** `auth_totp_mail` (optional, for enforcement), `auth_totp_portal` (optional)
**Key Library:** `pyotp` (TOTP generation/validation)

---

## Architecture

```
res.users (extended)
    ├── totp_secret        (encrypted, NO_ACCESS, stored as raw SQL)
    ├── totp_enabled       (computed from totp_secret)
    └── totp_trusted_device_ids -> auth_totp.device (One2many)

auth_totp.device
    └── res.users (Many2one)

auth_totp.wizard
    └── Transient wizard for TOTP setup
```

---

## res.users Extension

The TOTP fields are added to `res.users` with special access controls.

### Fields Added

| Field | Type | Access | Description |
|-------|------|--------|-------------|
| `totp_secret` | Char | NO_ACCESS (compute/inverse only) | Base32-encoded TOTP secret |
| `totp_enabled` | Boolean | SELF_READABLE | Computed: True if secret is set |
| `totp_trusted_device_ids` | One2many | SELF_READABLE | Trusted devices for this user |

### Database Column

```sql
ALTER TABLE res_users ADD COLUMN totp_secret varchar;
```

The column is created via `init()` hook, not via ORM fields, for security:
- No direct ORM access via `SELF_READABLE_FIELDS`
- Accessed only via compute/inverse methods with raw SQL

### Self-Readable Fields Extension

```python
@property
def SELF_READABLE_FIELDS(self):
    return super().SELF_READABLE_FIELDS + ['totp_enabled', 'totp_trusted_device_ids']
```

This allows users to see their own TOTP status and trusted devices via the preferences form.

---

## TOTP Secret Management

### Secret Storage

```python
totp_secret = fields.Char(
    copy=False,
    groups=fields.NO_ACCESS,  # Not accessible via ORM
    compute='_compute_totp_secret',
    inverse='_inverse_token'
)
```

### Compute Method (Read)

```python
def _compute_totp_secret(self):
    for user in self:
        self.env.cr.execute(
            'SELECT totp_secret FROM res_users WHERE id=%s',
            (user.id,)
        )
        user.totp_secret = self.env.cr.fetchone()[0]
```

### Inverse Method (Write)

```python
def _inverse_token(self):
    for user in self:
        secret = user.totp_secret if user.totp_secret else None
        self.env.cr.execute(
            'UPDATE res_users SET totp_secret = %s WHERE id=%s',
            (secret, user.id)
        )
```

### totp_enabled Compute

```python
@api.depends('totp_secret')
def _compute_totp_enabled(self):
    for r, v in zip(self, self.sudo()):
        r.totp_enabled = bool(v.totp_secret)
```

---

## TOTP Verification

### `_totp_check(code)`

Validates a TOTP code against the user's secret.

```python
def _totp_check(self, code):
    sudo = self.sudo()
    key = base64.b32decode(sudo.totp_secret)
    match = TOTP(key).match(code)
    if match is None:
        _logger.info("2FA check: FAIL for %s %r", self, sudo.login)
        raise AccessDenied(_("Verification failed, please double-check the 6-digit code"))
    _logger.info("2FA check: SUCCESS for %s %r", self, sudo.login)
```

Uses `pyotp.TOTP.match()` which:
- Decodes the Base32 secret
- Validates against current time and a window
- Returns True if valid, None if invalid

### MFA Flow Integration

```python
def _mfa_type(self):
    r = super()._mfa_type()
    if r is not None:
        return r
    if self.totp_enabled:
        return 'totp'

def _mfa_url(self):
    r = super()._mfa_url()
    if r is not None:
        return r
    if self._mfa_type() == 'totp':
        return '/web/login/totp'
```

---

## Enabling TOTP

### `_totp_try_setting(secret, code)`

Validates and activates TOTP for a user.

```python
def _totp_try_setting(self, secret, code):
    if self.totp_enabled or self != self.env.user:
        _logger.info("2FA enable: REJECT for %s %r", self, self.login)
        return False

    # Normalize secret (remove spaces, uppercase)
    secret = compress(secret).upper()
    match = TOTP(base64.b32decode(secret)).match(code)
    if match is None:
        _logger.info("2FA enable: REJECT CODE for %s %r", self, self.login)
        return False

    # Save the secret
    self.sudo().totp_secret = secret

    # Update session token to prevent logout
    if request:
        self.env.flush_all()
        new_token = self.env.user._compute_session_token(request.session.sid)
        request.session.session_token = new_token

    _logger.info("2FA enable: SUCCESS for %s %r", self, self.login)
    return True
```

### `action_totp_enable_wizard()`

Initiates the TOTP enrollment wizard.

```python
@check_identity
def action_totp_enable_wizard(self):
    if self.env.user != self:
        raise UserError(_("Two-factor authentication can only be enabled for yourself"))
    if self.totp_enabled:
        raise UserError(_("Two-factor authentication already enabled"))

    # Generate random secret
    secret_bytes_count = TOTP_SECRET_SIZE // 8
    secret = base64.b32encode(os.urandom(secret_bytes_count)).decode()
    # Format in groups of 4 for readability
    secret = ' '.join(map(''.join, zip(*[iter(secret)]*4)))

    # Create wizard with secret
    w = self.env['auth_totp.wizard'].create({
        'user_id': self.id,
        'secret': secret,
    })
    return {
        'type': 'ir.actions.act_window',
        'target': 'new',
        'res_model': 'auth_totp.wizard',
        'name': _("Two-Factor Authentication Activation"),
        'res_id': w.id,
        'views': [(False, 'form')],
    }
```

### TOTP Secret Generation

```python
TOTP_SECRET_SIZE = 160  # bits (from totp.py)

# 20 bytes = 160 bits = 32 base32 characters
secret_bytes_count = TOTP_SECRET_SIZE // 8  # = 20
secret = base64.b32encode(os.urandom(secret_bytes_count)).decode()
```

---

## Disabling TOTP

### `action_totp_disable()`

Disables TOTP for selected users.

```python
@check_identity
def action_totp_disable(self):
    logins = ', '.join(map(repr, self.mapped('login')))
    if not (self == self.env.user or self.env.user._is_admin() or self.env.su):
        _logger.info("2FA disable: REJECT for %s (%s) by uid #%s", self, logins, self.env.user.id)
        return False

    # Revoke all trusted devices
    self.revoke_all_devices()

    # Clear the secret
    self.sudo().write({'totp_secret': False})

    # Update session token
    if request and self == self.env.user:
        self.env.flush_all()
        new_token = self.env.user._compute_session_token(request.session.sid)
        request.session.session_token = new_token

    _logger.info("2FA disable: SUCCESS for %s (%s) by uid #%s", self, logins, self.env.user.id)
    return {...}  # display_notification
```

### Password Change Revokes Devices

```python
@api.model
def change_password(self, old_passwd, new_passwd):
    self.env.user._revoke_all_devices()
    return super().change_password(old_passwd, new_passwd)
```

---

## auth_totp.device (Trusted Devices)

Stores trusted device records that bypass TOTP for 30 days.

### Model

```python
class AuthTotpDevice(models.Model):
    _name = "auth_totp.device"
    _inherit = "res.users.apikeys"  # Reuses API key infrastructure
    _description = "Authentication Device"
    _auto = False  # Uses res.users.apikeys _auto mechanism
```

Inherits from `res.users.apikeys` which:
- Creates a `auth_totp_device_key` table
- Has `key` column (stores hashed device key)
- Has `scope='browser'` for trusted browsers

### Device Verification

```python
def _check_credentials_for_uid(self, *, scope, key, uid):
    """Return True if device key matches given scope for user ID uid"""
    assert uid, "uid is required"
    return self._check_credentials(scope=scope, key=key) == uid
```

Called from `res.users._should_alert_new_device()`:
```python
def _should_alert_new_device(self):
    if request and self._mfa_type():
        key = request.cookies.get('td_id')
        if key:
            if request.env['auth_totp.device']._check_credentials_for_uid(
                scope="browser", key=key, uid=self.id):
                return False  # Trusted device, no alert
        return True  # New device, send alert
    return super()._should_alert_new_device()
```

---

## Revoking Devices

### `revoke_all_devices()`

```python
@check_identity
def revoke_all_devices(self):
    self._revoke_all_devices()

def _revoke_all_devices(self):
    self.totp_trusted_device_ids._remove()
```

---

## TOTP Algorithm (from totp.py)

### PyOTP TOTP

```python
class TOTP:
    def __init__(self, key):
        self.key = key

    def match(self, code, valid_window=1):
        # valid_window=1 allows 1 step before/after current time
        # Total validation window: 3 x 30-second periods = 90 seconds
        # This accommodates clock skew between server and authenticator
```

### Time Step

Standard TOTP uses 30-second time steps. The validation window allows:
- Current step: exact match
- Previous step: ±1 window
- Next step: ±1 window

### Base32 Encoding

TOTP secrets are Base32-encoded for compatibility with authenticator apps:
- Characters: A-Z and 2-7
- Case-insensitive
- Spacing inserted for readability (groups of 4)

---

## Session Token Handling

When TOTP is enabled/disabled, the session token must be updated to prevent logout:

```python
if request:
    self.env.flush_all()
    # Compute new session token based on user credentials
    new_token = self.env.user._compute_session_token(request.session.sid)
    request.session.session_token = new_token
```

The `_get_session_token_fields()` includes `totp_secret`:
```python
def _get_session_token_fields(self):
    return super()._get_session_token_fields() | {'totp_secret'}
```

This means the session token changes when the TOTP secret changes, preventing the cache-clearing side effect from logging out the user.

---

## Related Modules

### auth_totp_mail

Extends `auth_totp` to enforce TOTP via user groups:
- Users in `auth_totp_mail.group_totp_mail` must enable TOTP
- Enforces at login or in preferences

### auth_totp_portal

Extends `auth_totp` for portal users:
- Allows portal users to use TOTP
- Different trusted device management for portals

### auth_totp.rate_limit

Built-in rate limiting:
- Limits TOTP verification attempts
- Prevents brute-force attacks on 6-digit codes
- Combined with session management for attack mitigation

---

## Login Flow with TOTP

```
1. User submits credentials
2. Password verified normally
3. If TOTP enabled for user:
   a. User redirected to /web/login/totp
   b. User enters 6-digit code
   c. _totp_check() validates code
   d. On success: trusted device cookie set if "remember" checked
   e. Session continues

4. On subsequent logins:
   a. If trusted device cookie valid: skip TOTP
   b. Otherwise: require TOTP code
```

---

## Security Considerations

### Secret Storage

- Stored as plain Base32 in `res_users.totp_secret` column
- Not exposed via ORM except through compute/inverse
- Accessible via raw SQL (requires database access)
- In production, consider encryption at rest

### Code Validation

- `valid_window=1` provides tolerance for 90 seconds total
- Rate limiting prevents brute-force (with external rate limiter)
- 6-digit code = 1,000,000 possibilities
- At 3 attempts/second = ~93 hours to brute force
- Combined with lockout policies provides adequate security

### Session Management

- Session token changes when TOTP secret changes
- Prevents logout during enrollment
- Trusted device cookies scoped to `browser`
