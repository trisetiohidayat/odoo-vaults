# Auth Passkey

**Module:** `auth_passkey`
**Category:** Hidden/Tools
**Depends:** `base_setup`, `web`
**Auto-install:** True
**Version:** 1.1
**License:** LGPL-3

## Overview

Implements passkey authentication for Odoo using the WebAuthn standard. Passkeys are a secure alternative to passwords that allow users to log in using biometrics, hardware keys, or device-based authentication. When logging in with a passkey, MFA is bypassed.

## Models

### `res.users` (inherited)

| Field | Type | Description |
|-------|------|-------------|
| `auth_passkey_key_ids` | One2many | Passkeys registered for the user |

**Key Methods:**
- `_login(credential, user_agent_env)` — Intercepts login with WebAuthn credential, looks up user by credential ID.
- `_check_credentials(credential, env)` — Verifies WebAuthn authentication response, updates sign counter.
- `_get_session_token_fields()` — Includes `auth_passkey_key_ids` in session token.
- `_get_session_token_query_params()` — Joins `auth_passkey_key` in session token query.
- `action_create_passkey()` — Triggers passkey registration wizard.

### `auth.passkey.key`

Stores registered passkeys for users. See `models/auth_passkey_key.py`.

### `auth.passkey.key.create`

Wizard model for passkey registration.

### `auth.passkey.key.create`

Wizard model for identity check during passkey operations.

## Technical Notes

- Uses `simplewebauthn` (bundled) for WebAuthn browser-side operations.
- Bundled `webauthn` Python library (`_vendor/webauthn/`) handles registration and authentication verification.
- Supports multiple passkeys per user.
- Passkey login bypasses MFA (`auth_method: 'passkey'`, `mfa: 'skip'`).
- Sign counter (`sign_count`) tracks authentication usage per credential.
- Controller: `controllers/main.py` handles WebAuthn registration/authentication endpoints.
