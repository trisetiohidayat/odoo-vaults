---
Module: google_gmail
Version: 18.0.0
Type: addon
Tags: #odoo18 #google #gmail #email #oauth
---

## Overview

Integrates Gmail OAuth2 authentication with Odoo's outgoing SMTP and incoming IMAP mail servers. Supports Gmail as both a sending (SMTP with XOAUTH2 SASL) and receiving (IMAP with XOAUTH2) mail server.

**Depends:** `google_gmail` (own module), `fetchmail` (optional)

**Key Behavior:** OAuth2 flow: user authorizes via browser, Odoo receives authorization code, exchanges for refresh + access token. Access tokens auto-refresh when near expiration. Both SMTP and IMAP use XOAUTH2 authentication.

---

## Models / Mixins

### `google.gmail.mixin` (Abstract)

**Model:** `google.gmail.mixin`
**Type:** Abstract model mixin

| Field | Type | Note |
|-------|------|------|
| `google_gmail_authorization_code` | Char | Initial OAuth code (system group only) |
| `google_gmail_refresh_token` | Char | Long-lived refresh token (system group only) |
| `google_gmail_access_token` | Char | Short-lived access token (system group only) |
| `google_gmail_access_token_expiration` | Integer | Unix timestamp of access token expiry |
| `google_gmail_uri` | Char (compute) | Authorization URL for browser redirect |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_gmail_uri()` | — | Builds Google OAuth2 authorization URL with CSRF state |
| `open_google_gmail_uri()` | Action | Opens authorization URL (system group required) |
| `_fetch_gmail_refresh_token(code)` | tuple | Exchanges auth code for refresh + access token |
| `_fetch_gmail_access_token(refresh_token)` | tuple | Refreshes access token |
| `_fetch_gmail_token(grant_type, **values)` | dict | Generic token endpoint caller |
| `_generate_oauth2_string(user, refresh_token)` | str | XOAUTH2 SASL string; auto-refreshes access token if needed |
| `_get_gmail_csrf_token()` | str | HMAC-based CSRF token for OAuth callback validation |

**Constants:**
- `_SERVICE_SCOPE = 'https://mail.google.com/'`
- `GMAIL_TOKEN_REQUEST_TIMEOUT = 5`
- `GMAIL_TOKEN_VALIDITY_THRESHOLD = 10` (5 + 5 seconds buffer)

### `ir.mail_server` (Inherited)

**Inherited from:** `ir.mail_server` + `google.gmail.mixin`

| Field | Type | Note |
|-------|------|------|
| `smtp_authentication` | Selection | Adds `'gmail'` — Gmail OAuth Authentication |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_smtp_authentication_info()` | — | Sets Gmail-specific info text |
| `_onchange_encryption()` | — | Prevents auto-change of port for Gmail servers |
| `_onchange_smtp_authentication_gmail()` | — | Sets host to `smtp.gmail.com`, encryption to `starttls`, port to 587 |
| `_on_change_smtp_user_gmail()` | — | Sets `from_filter` to `smtp_user` (Gmail servers are per-account) |
| `_check_use_google_gmail_service()` | — | Constrains: no password, `starttls` required, `smtp_user` required |
| `_smtp_login(connection, user, password)` | — | Uses XOAUTH2 if `smtp_authentication == 'gmail'` |

### `fetchmail.server` (Inherited)

**Inherited from:** `fetchmail.server` + `google.gmail.mixin`

| Field | Type | Note |
|-------|------|------|
| `server_type` | Selection | Adds `'gmail'` — Gmail OAuth Authentication |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_server_type_info()` | — | Sets Gmail-specific info text |
| `onchange_server_type()` | — | Sets host to `imap.gmail.com`, SSL to True, port to 993 |
| `_imap_login(connection)` | — | Uses XOAUTH2 SASL if `server_type == 'gmail'` |
| `_get_connection_type()` | — | Returns `'imap'` for Gmail servers |

### `res.config.settings` (Inherited)

**Inherited from:** `res.config.settings`

| Field | Type | Note |
|-------|------|------|
| `google_gmail_client_identifier` | Char | Via `google_gmail_client_id` config parameter |
| `google_gmail_client_secret` | Char | Via `google_gmail_client_secret` config parameter |

---

## Controllers

### `GoogleGmailController`

| Route | Auth | Note |
|-------|------|------|
| `/google_gmail/confirm` | user | OAuth callback; exchanges code for tokens; validates CSRF token; writes tokens to record |

---

## Critical Notes

- **CSRF Protection:** OAuth state includes a HMAC CSRF token validated with `consteq` against `_get_gmail_csrf_token` before storing tokens.
- **Token Auto-Refresh:** `_generate_oauth2_string` checks expiration against `GMAIL_TOKEN_VALIDITY_THRESHOLD` (10s buffer) and auto-refreshes.
- **Per-Account SMTP:** When Gmail SMTP is configured, `from_filter` is locked to the `smtp_user` (user's own email). The `mail.default.from` system parameter can override this for multi-user sending.
- **Password Must Be Empty:** `_check_use_google_gmail_service` explicitly prohibits a password on Gmail mail servers.
- **OAuth Callback:** The `/google_gmail/confirm` endpoint redirects back to `/odoo/<model>/<id>` after successful auth.
