---
tags: [odoo, odoo17, module, auth, totp, security]
research_depth: medium
---

# Auth TOTP Module — Deep Reference

**Source:** `addons/auth_totp/models/`

## Overview

Two-Factor Authentication (2FA) using Time-based One-Time Passwords (TOTP). Compatible with Google Authenticator, Authy, FreeOTP, and any RFC 6238-compliant authenticator app. The module adds a second authentication factor during login and on sensitive actions.

## Key Models

### auth_totp.device — Trusted Device

Inherits from `res.users.apikeys`. Stores trusted devices so users don't re-enter TOTP code on every login from the same browser.

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `user_id` | Many2one | Owner of the device |
| `key` | Char | Encrypted device key (via apikeys mixin) |

The model overrides `_check_credentials_for_uid(scope, key, uid)` to validate the device key for a given user, enabling the "trusted device" flow.

**Garbage collection** — `@api.autovacuum` method `_gc_device()` deletes devices older than `TRUSTED_DEVICE_AGE` (configured in `auth_totp.controllers.home`).

### res.users — TOTP Extension

The `auth_totp` module extends `res.users` with three fields:

| Field | Type | Description |
|-------|------|-------------|
| `totp_secret` | Char (copy=False, NO_ACCESS) | Base32-encoded TOTP secret key |
| `totp_enabled` | Boolean (compute) | True when `totp_secret` is set |
| `totp_trusted_device_ids` | One2many → `auth_totp.device` | Trusted devices for this user |

The `totp_secret` column is added dynamically via `init()` on the `res.users` model — not a migration, but a live `ALTER TABLE` during module init to avoid requiring migration scripts.

**Computed fields:**
- `_compute_totp_enabled` — reads `totp_secret` via `sudo()` (stored unencrypted in DB, but field ACL prevents normal users from reading it)
- `_compute_totp_secret` — direct SQL read from `res_users.totp_secret`; this is the "getter" used by the preference form
- `_inverse_token` — direct SQL write to `res_users.totp_secret`

## TOTP Flow

### Enable Flow (User initiates)

1. User clicks "Enable Two-Factor Authentication" in Preferences → Security tab
2. `action_totp_enable_wizard` (protected by `@check_identity`) generates a random 80-bit secret: `os.urandom(10)` → base32-encoded, formatted with spaces every 4 chars
3. A `auth_totp.wizard` form is opened showing the secret as a QR code URI (`otpauth://totp/...?secret=...&issuer=...`)
4. User scans the QR code with their authenticator app
5. User enters the first 6-digit code from the app
6. `_totp_try_setting(secret, code)` validates the code via `TOTP(key).match(code)`
7. If valid, `totp_secret` is written to the user record; session token is updated to avoid logout

### Login Flow

1. User enters login + password → standard `_check_credentials`
2. If password succeeds and user has `totp_enabled`, Odoo redirects to `/web/login/totp`
3. User enters the 6-digit TOTP code from their app
4. `Users._totp_check(code)` reads `totp_secret` via sudo and validates via `TOTP(key).match(code)`
5. On failure: `AccessDenied` raised with translated message
6. On success: login proceeds; trusted device cookie (`td_id`) may be set if "Remember this device" selected

### `@check_identity` — Sensitive Action Re-verification

The base `@check_identity` decorator (from `base.models.res_users`) forces re-entry of the TOTP code before executing sensitive operations. Auth TOTP overrides `Users._mfa_type()` to return `'totp'` when enabled, and `Users._mfa_url()` to return `/web/login/totp`. Actions protected by this decorator on a TOTP-enabled user will trigger the TOTP re-verification screen.

### Password Change Revokes Devices

When a user changes their password via `change_password()`, `_revoke_all_devices()` is called automatically, invalidating all trusted devices. This is a security measure — device theft is assumed if the password changed.

### MFA and API Keys

If `totp_enabled`, the user cannot use password-based RPC via XML-RPC or JSON-RPC. `_rpc_api_keys_only()` returns `True`, forcing API key usage for external integrations.

## TOTP Algorithm (RFC 6238)

The module uses the `TOTP` class defined in `models/totp.py`:

```python
# Time step = 30 seconds
# Secret = base32-encoded 80-bit key
# Output = 6-digit decimal code (HOTP with counter = floor(unix_now / 30))
TOTP(secret_key).match(user_code)  # returns True/False
```

The `TOTP_SECRET_SIZE` constant (80 bits) is used when generating new secrets.

## Trusted Device Cookie Flow

In `res_users.py`:
- `_should_alert_new_device()` checks for a cookie `td_id` and validates it via `auth_totp.device._check_credentials_for_uid(scope="browser", key=..., uid=...)`
- If 2FA is enabled but the cookie is absent or invalid, the user sees a "new device login" alert email
- If the device key validates, no alert is sent (known device)

## XML Security Groups

The module defines access rights in `ir.model.access.csv`:
- `group_user` can read/write own TOTP device
- Only admin can unlink devices

## See Also

- [Modules/auth_signup](modules/auth_signup.md) — user registration and signup
- [Modules/auth_oauth](modules/auth_oauth.md) — OAuth2 single sign-on
- [Modules/base](modules/base.md) — `@check_identity` decorator and user model foundation