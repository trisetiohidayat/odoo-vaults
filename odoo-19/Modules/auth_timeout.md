# Auth Timeout

**Module:** `auth_timeout`
**Category:** Hidden/Tools
**Depends:** `auth_totp`, `auth_totp_mail`, `auth_passkey`, `bus`
**Auto-install:** True
**License:** LGPL-3

## Overview

Enforces session timeout (re-authentication) after a period of user inactivity or maximum session duration. When a timeout threshold is reached, the user is asked to re-confirm their identity (with password, TOTP, or passkey) before continuing. Supports both session-based logout and MFA re-verification flows.

## Dependencies

- [Modules/auth_totp](modules/auth_totp.md) - TOTP support
- [Modules/auth_totp_mail](modules/auth_totp_mail.md) - Mail-based TOTP
- [Modules/auth_passkey](modules/auth_passkey.md) - Passkey authentication
- [Modules/bus](modules/bus.md) - Real-time bus for presence/inactivity updates

## Models

### `res.groups` (inherited)

Extends `res.groups` with session timeout configuration fields.

| Field | Type | Description |
|-------|------|-------------|
| `lock_timeout` | Integer | Session timeout in minutes (max session duration before re-auth) |
| `lock_timeout_mfa` | Boolean | Require MFA on session timeout |
| `lock_timeout_inactivity` | Integer | Inactivity timeout in minutes |
| `lock_timeout_inactivity_mfa` | Boolean | Require MFA on inactivity timeout |

**UI-only computed fields:**
| Field | Type | Description |
|-------|------|-------------|
| `has_lock_timeout` | Boolean | Toggle session timeout |
| `lock_timeout_delay_unit` | Selection | min/hr/day |
| `lock_timeout_delay_in_unit` | Integer | Timeout value |
| `lock_timeout_2fa_selection` | Selection | Logout vs 2FA |
| `has_lock_timeout_inactivity` | Boolean | Toggle inactivity timeout |
| `lock_timeout_inactivity_delay_unit` | Selection | min/hr/day |
| `lock_timeout_inactivity_delay_in_unit` | Integer | Inactivity value |
| `lock_timeout_inactivity_2fa_selection` | Selection | Screen lock vs 2FA |

**Key Methods:**
- `_get_lock_timeouts()` — Returns the shortest applicable timeouts across all user's groups, cached per group ID. Returns dict with `lock_timeout` and `lock_timeout_inactivity` keys, each a list of (seconds, requires_mfa) tuples sorted shortest-first.

### `res.users` (inherited)

| Method | Description |
|--------|-------------|
| `_get_auth_methods()` | Returns enabled auth methods for user: webauthn, mfa_type, password |
| `_get_lock_timeouts()` | Delegates to group-level `_get_lock_timeouts()` |
| `_get_lock_timeout_inactivity()` | Returns shortest inactivity timeout in seconds |

### `auth_totp.device` (inherited)

| Method | Description |
|--------|-------------|
| `_get_trusted_device_age()` | Caps trusted device age by the shortest MFA session timeout |

---

## Technical Implementation

### `ir.http` (inherited)

The module extends `ir.http` to intercept requests and enforce timeouts.

| Method | Description |
|--------|-------------|
| `_must_check_identity()` | Checks session timestamps vs both timeout types; returns `{logout}`, `{check_identity}`, or `{mfa}` dict |
| `_check_identity(credential)` | Handles re-auth flow: totp/totp_mail token normalization, MFA chaining, session token updates |
| `_set_session_inactivity(session, inactivity_period, force)` | Called from JS presence events or WS close; sets `identity-check-next` on session |
| `_authenticate(endpoint)` | Raises `SessionExpiredException` (logout) or `CheckIdentityException` (re-auth) |
| `_handle_error(exception)` | Redirects HTTP requests with `CheckIdentityException` to `/auth-timeout/check-identity` |
| `session_info()` | Adds `lock_timeout_inactivity` to backend session info |
| `get_frontend_session_info()` | Adds `lock_timeout_inactivity` to frontend session info |

### `ir.websocket` (inherited)

| Method | Description |
|--------|-------------|
| `_update_mail_presence(inactivity_period)` | Tracks inactivity via WebSocket presence updates |
| `_on_websocket_closed(cookies)` | Marks session inactive when WS connection closes (last tab closed) |

### `CheckIdentityException`

Custom exception subclass of `SessionExpiredException`, raised when the user must re-authenticate without a full logout.

### Timeout Logic

1. **Session timeout** (`lock_timeout`): maximum session duration. Compare `time.time() - session.create_time > threshold`.
2. **Inactivity timeout** (`lock_timeout_inactivity`): user idle time. Compare `time.time() - session['identity-check-next'] > threshold`. Set by JS client sending presence events or when WS closes.

### Cache Invalidation

`_get_lock_timeouts()` is `@ormcache`-decorated on group IDs. The cache is invalidated in `res.groups` `create()`, `write()`, and `unlink()` when timeout fields are modified.

---

## Related

- [Modules/auth_totp](modules/auth_totp.md) - TOTP authentication
- [Modules/auth_passkey](modules/auth_passkey.md) - Passkey authentication
- [Modules/bus](modules/bus.md) - WebSocket presence
