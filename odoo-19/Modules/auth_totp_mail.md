# auth_totp_mail

Odoo 19 Security/Authentication Module

## Overview

`auth_totp_mail` provides **two-factor authentication via email** (TOTP Mail) for internal Odoo users. It extends `auth_totp` with the ability to send time-based one-time codes by email when logging in from a new device, and allows administrators to invite users to enable 2FA.

## Module Details

- **Category**: Extra Tools
- **Depends**: `auth_totp`, `mail`
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Auto-install**: Yes

## Key Features

### TOTP via Email (TOTP Mail)

When a user logs in from a new device, a 6-digit TOTP code is sent by email. The code is valid for 1 hour (HOTP with timestep=3600, counter-based). This is an alternative to authenticator apps (Google Authenticator, etc.).

### 2FA Policy Enforcement

Administrators can enforce 2FA via `auth_totp.policy` config parameter:
- `employee_required` — Employees must use 2FA.
- `all_required` — All users must use 2FA.

### Invite to 2FA

Admins can invite users via email to activate 2FA using the `action_totp_invite()` action.

## Key Components

### Models

#### `res.users` (Inherited)

Key methods:
- `_mfa_type()` — Returns `'totp_mail'` when the policy requires it for this user.
- `_mfa_url()` — Returns `/web/login/totp` for TOTP mail users.
- `_check_credentials(credentials, env)` — Verifies TOTP mail codes using HOTP with HMAC.
- `_get_totp_mail_key()` — Derives the TOTP key from user ID, login, and login date.
- `_get_totp_mail_code()` — Generates the 6-digit code using HOTP.
- `_send_totp_mail_code()` — Sends the code via email with device/browser/IP context.
- `get_totp_invite_url()` — Returns admin invite URL.
- `action_totp_invite()` — Sends TOTP invite email to selected users.
- `action_open_my_account_settings()` — Opens the security form.

#### `auth_totp.device` (Inherited)

Overrides `unlink()` to send a notification email to users when a trusted device is removed.

#### `res.config.settings` (Inherited)

| Field | Type | Description |
|---|---|---|
| `auth_totp_enforce` | Boolean | Enforce 2FA globally |
| `auth_totp_policy` | Selection | `'employee_required'` or `'all_required'` |

## Login Flow

1. User enters credentials → Server detects 2FA policy applies.
2. Server sends TOTP code to user's email.
3. User receives email with 6-digit code + device/browser/location info.
4. User enters code on the TOTP screen → authenticated.

## Technical Notes

- Code generated using HOTP (counter-based TOTP variant) with 1-hour windows.
- Rate limiting on code check and email send to prevent abuse.
- On new device detection (no trusted cookie), requires TOTP even if 2FA is not globally enforced.
