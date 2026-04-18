---
uuid: a1b2c3d4-5e6f-7a8b-9c0d-1e2f3a4b5c6d
tags:
  - odoo
  - odoo19
  - modules
  - integration
  - email
  - oauth2
  - gmail
  - google
---

# Google Gmail (`google_gmail`)

## Overview

| Attribute | Value |
|-----------|-------|
| **Module** | `google_gmail` |
| **Category** | Hidden (Mail Infrastructure) |
| **Depends** | `mail` |
| **Auto-install** | True |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **Source** | `odoo/addons/google_gmail/` |

## Description

The `google_gmail` module adds **Google Gmail OAuth2 authentication** support to Odoo's incoming (IMAP) and outgoing (SMTP) mail servers. Instead of using Gmail app passwords or the deprecated "Less Secure Apps" mode, users connect their Gmail accounts through Google's official OAuth2 flow.

This module replaces the need for IMAP/SMTP authentication with plain passwords, providing:
- **Enhanced security**: OAuth2 tokens are scoped and revocable, unlike passwords
- **No app passwords needed**: Users authenticate through Google's OAuth consent screen
- **Multi-account support**: Each mail server can connect a different Gmail account
- **Automatic token refresh**: Access tokens are refreshed automatically when they expire

## Architecture

The module follows a **mixin-based extension pattern**:

```
google_gmail/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── google_gmail_mixin.py     # OAuth2 token management (abstract)
│   ├── fetchmail_server.py       # Gmail IMAP (incoming mail)
│   ├── ir_mail_server.py         # Gmail SMTP (outgoing mail)
│   └── res_config_settings.py     # OAuth2 credentials in Settings
├── controllers/
│   ├── __init__.py
│   └── main.py                    # OAuth2 callback handlers
├── tools.py                       # Shared utility functions
└── static/
    └── src/xml/
        └── templates.xml          # OAuth error/success page templates
```

The core is the `google.gmail.mixin` abstract model, which is mixed into both `fetchmail.server` (for incoming mail) and `ir.mail_server` (for outgoing mail). Each concrete model then overrides its specific authentication methods.

## OAuth2 Flow

The OAuth2 authentication flow involves several steps to obtain and store refresh tokens:

```
┌─────────────┐    1. User clicks "Authorize"     ┌──────────────────┐
│  Odoo Form  │ ─────────────────────────────────→  Google OAuth   │
│ (mail server│    2. Redirect with auth code     │  Consent Screen  │
│   record)   │ ←──────────────────────────────────                 │
└─────────────┘    3. Callback with authorization code  └──────────────────┘
       │
       │ 4. Exchange code for tokens
       ↓
┌─────────────┐
│  Google     │    5. Returns refresh_token + access_token
│  Token API  │ ─────────────────────────────────→ Odoo stores tokens
└─────────────┘
       │
       │ 6. On mail send/receive:
       ↓       Use refresh_token → new access_token
┌─────────────┐
│ Gmail API   │    7. Authenticated IMAP/SMTP connection
│ (IMAP/SMTP) │ ←─────────────────────────────────
└─────────────┘
```

### Step 1: Configuration Check

Before initiating the OAuth flow, `open_google_gmail_uri()` checks whether custom OAuth2 credentials are configured:

```python
def open_google_gmail_uri(self):
    # Checks if google_gmail_client_id and google_gmail_client_secret are set
    # If NOT configured → uses Odoo IAP (Enterprise only)
    # If configured → uses direct OAuth with custom credentials
```

Two paths exist:
- **Custom credentials path**: Uses the admin-configured `google_gmail_client_id` and `google_gmail_client_secret` stored in `ir.config_parameter`
- **IAP path (Enterprise only)**: Uses Odoo's own IAP endpoint (`https://gmail.api.odoo.com`), which acts as a relay to Google's OAuth

### Step 2: Authorization URL Construction

```python
def _compute_gmail_uri(self):
    # Constructs Google OAuth consent URL with:
    # - client_id: from ir.config_parameter
    # - redirect_uri: {base_url}/google_gmail/confirm
    # - scope: https://mail.google.com/ (required for IMAP/SMTP)
    # - access_type: offline (to get refresh token)
    # - prompt: consent (ensures refresh token is always returned)
    # - state: JSON with model, id, and CSRF token
```

The `state` parameter is critical for security — it contains:
- `model`: The model being configured (e.g., `fetchmail.server`)
- `id`: The record ID
- `csrf_token`: HMAC-based token to prevent CSRF attacks

### Step 3: CSRF Protection

```python
def _get_gmail_csrf_token(self):
    # Generates HMAC-SHA256 token using Odoo's HMAC utility
    # Scope: 'google_gmail_oauth'
    # Message: (model_name, record_id)
    # Verified in the callback to prevent cross-site request forgery
```

### Step 4: Token Exchange

```python
def _fetch_gmail_refresh_token(self, authorization_code):
    # POST to https://oauth2.googleapis.com/token with:
    # - code: authorization code
    # - client_id, client_secret
    # - redirect_uri
    # - grant_type: authorization_code
    # Returns: refresh_token, access_token, expires_in
```

### Step 5: Token Refresh

```python
def _generate_oauth2_string(self, user, refresh_token):
    # Checks if current access_token is expired or about to expire
    # If expired → calls _fetch_gmail_access_token to get new one
    # Stores new access_token + expiration in the mail server record
    # Generates XOAUTH2 SASL string: "user={email}\1auth=Bearer {token}\1\1"
```

The token validity threshold (`GMAIL_TOKEN_VALIDITY_THRESHOLD = 10 seconds`) ensures the token is refreshed before it actually expires, accounting for network latency and token validation time.

## Models

### `google.gmail.mixin` (Abstract)

**File:** `models/google_gmail_mixin.py`

The central mixin providing all OAuth2 functionality. It is mixed into both `fetchmail.server` and `ir.mail_server`.

**Fields:**

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `google_gmail_refresh_token` | Char | `base.group_system` | OAuth2 refresh token (never expires) |
| `google_gmail_access_token` | Char | `base.group_system` | Current access token (short-lived) |
| `google_gmail_access_token_expiration` | Integer | `base.group_system` | Unix timestamp when access token expires |
| `google_gmail_uri` | Char (computed) | `base.group_system` | Authorization URL for OAuth consent |
| `active` | Boolean | — | Whether this server is active |

**Key Methods:**

| Method | Description |
|--------|-------------|
| `_compute_gmail_uri()` | Computes the Google OAuth2 authorization URI |
| `open_google_gmail_uri()` | Action that redirects user to Google login |
| `_fetch_gmail_refresh_token(code)` | Exchanges auth code for refresh + access token |
| `_fetch_gmail_access_token(refresh_token)` | Refreshes access token |
| `_fetch_gmail_token(grant_type, **values)` | Low-level token request to Google |
| `_fetch_gmail_access_token_iap(refresh_token)` | Token refresh via Odoo IAP (EE only) |
| `_generate_oauth2_string(user, refresh_token)` | Builds XOAUTH2 SASL auth string |
| `_get_gmail_csrf_token()` | Generates HMAC-based CSRF token |

**Gmail Service Scope:**

```python
_SERVICE_SCOPE = 'https://mail.google.com/ https://www.googleapis.com/auth/userinfo.email'
```

The `https://mail.google.com/` scope is required for both IMAP access (incoming) and SMTP relay (outgoing). The `userinfo.email` scope verifies the authenticated email address.

### `fetchmail.server` (Extension)

**File:** `models/fetchmail_server.py`

Extends the incoming mail server model to support Gmail OAuth2 authentication via IMAP.

```python
class FetchmailServer(models.Model):
    _name = 'fetchmail.server'
    _inherit = ['fetchmail.server', 'google.gmail.mixin']
```

**Server Type Addition:**

```python
server_type = fields.Selection(selection_add=[('gmail', 'Gmail OAuth Authentication')])
```

When `server_type = 'gmail'`, the form view shows Gmail-specific guidance through `_compute_server_type_info()`.

**Onchange Defaults:**

```python
@api.onchange('server_type', 'is_ssl', 'object_id')
def onchange_server_type():
    if self.server_type == 'gmail':
        self.server = 'imap.gmail.com'
        self.is_ssl = True
        self.port = 993
    # Clears Gmail tokens when switching away from Gmail type
```

**IMAP Authentication Override:**

```python
def _imap_login__(self, connection):
    if self.server_type == 'gmail':
        # Generates XOAUTH2 string and authenticates IMAP connection
        auth_string = self._generate_oauth2_string(self.user, self.google_gmail_refresh_token)
        connection.authenticate('XOAUTH2', lambda x: auth_string)
        connection.select('INBOX')
    else:
        super()._imap_login__(connection)
```

**Connection Type:**

```python
def _get_connection_type(self):
    # Gmail always uses IMAP (not POP), even if the base model supports POP
    return 'imap' if self.server_type == 'gmail' else super()._get_connection_type()
```

**Validation Constraint:**

```python
@api.constrains('server_type', 'is_ssl')
def _check_use_google_gmail_service(self):
    # SSL is mandatory for Gmail IMAP
    if self.server_type == 'gmail' and not self.is_ssl:
        raise UserError(_('SSL is required for server "%s".', server.name))
```

### `ir.mail_server` (Extension)

**File:** `models/ir_mail_server.py`

Extends the outgoing mail server model to support Gmail OAuth2 authentication via SMTP.

```python
class IrMail_Server(models.Model):
    _name = 'ir.mail_server'
    _inherit = ['ir.mail_server', 'google.gmail.mixin']
```

**SMTP Authentication Addition:**

```python
smtp_authentication = fields.Selection(
    selection_add=[('gmail', 'Gmail OAuth Authentication')]
)
```

When `smtp_authentication = 'gmail'`, Odoo shows Gmail-specific guidance and sets appropriate defaults.

**Onchange Behavior:**

```python
@api.onchange('smtp_authentication')
def _onchange_smtp_authentication_gmail(self):
    if self.smtp_authentication == 'gmail':
        self.smtp_host = 'smtp.gmail.com'
        self.smtp_encryption = 'starttls'  # Gmail requires STARTTLS
        self.smtp_port = 587
        self.from_filter = self.smtp_user  # Restrict to sender's email
```

**Validation Constraints:**

```python
@api.constrains('smtp_authentication', 'smtp_pass', 'smtp_encryption', 'from_filter', 'smtp_user')
def _check_use_google_gmail_service(self):
    # 1. Password must be empty (OAuth uses tokens, not passwords)
    # 2. Encryption must be 'starttls' (not 'ssl' or 'none')
    # 3. smtp_user must be set (the Gmail account email)
```

**SMTP Authentication Override:**

```python
def _smtp_login__(self, connection, smtp_user, smtp_password):
    if self.smtp_authentication == 'gmail':
        # Generates XOAUTH2 string, base64-encodes it, and sends AUTH XOAUTH2 command
        auth_string = self._generate_oauth2_string(smtp_user, self.google_gmail_refresh_token)
        oauth_param = base64.b64encode(auth_string.encode()).decode()
        connection.ehlo()
        connection.docmd('AUTH', f'XOAUTH2 {oauth_param}')
    else:
        super()._smtp_login__(connection, smtp_user, smtp_password)
```

**Email Verification:**

The controller's `_check_email_and_redirect_to_gmail_record()` method verifies that the Gmail account email matches the email set on the mail server. This prevents authorization for one Gmail account being used to send from another.

### `res.config.settings` (Extension)

**File:** `models/res_config_settings.py`

Stores Gmail OAuth2 client credentials:

| Field | Config Parameter |
|-------|-----------------|
| `google_gmail_client_identifier` | `google_gmail_client_id` |
| `google_gmail_client_secret` | `google_gmail_client_secret` |

**Configuration path:** `Settings > General Settings > Discuss > Google Gmail`

## Controllers

### OAuth2 Callback: `/google_gmail/confirm`

**File:** `controllers/main.py`

```python
@http.route('/google_gmail/confirm', type='http', auth='user')
def google_gmail_callback(self, code=None, state=None, error=None, **kwargs):
```

Handles the redirect from Google's OAuth consent screen:

1. **Error handling**: If Google returns an `error` parameter, renders an error template
2. **State parsing**: Extracts `model`, `id`, and `csrf_token` from the state JSON
3. **CSRF verification**: `_get_gmail_record()` verifies the CSRF token matches
4. **Token exchange**: Calls `_fetch_gmail_refresh_token(code)` to get tokens
5. **Email verification**: For SMTP servers, verifies the Gmail account email matches
6. **Token storage**: Writes tokens to the mail server record
7. **Redirect**: Returns to the mail server form or user preferences

### OAuth2 Callback: `/google_gmail/iap_confirm`

**File:** `controllers/main.py`

```python
@http.route('/google_gmail/iap_confirm', type='http', auth='user')
def google_gmail_iap_callback(self, model, rec_id, csrf_token, access_token, refresh_token, expiration):
```

Used when the Enterprise IAP path is chosen (when `google_gmail_client_id` is not configured). The IAP relay handles the OAuth flow and returns tokens directly to this callback.

**IAP Flow Steps:**
1. User initiates OAuth from Odoo
2. Odoo contacts `gmail.api.odoo.com` which returns a URL
3. User is redirected to Google via the IAP relay
4. After consent, Google redirects back through IAP
5. IAP redirects to this callback with tokens pre-filled

### CSRF Validation: `_get_gmail_record()`

```python
def _get_gmail_record(self, model_name, rec_id, csrf_token):
    # Verifies:
    # 1. The model inherits from google.gmail.mixin
    # 2. The record exists
    # 3. The CSRF token matches (using consteq for timing-safe comparison)
    # Raises Forbidden() if any check fails
```

### Email Verification: `_check_email_and_redirect_to_gmail_record()`

For `ir.mail_server` records, this method makes a `GET /oauth2/v2/userinfo` call to verify the authenticated Gmail account matches the email set on the mail server. This prevents one user from authorizing a Gmail account for another user's mail server.

## Configuration

### Option A: Odoo IAP (Enterprise Edition Only)

No manual configuration required. Odoo uses its own IAP endpoint to handle the OAuth flow. This is the simplest option for Enterprise users.

### Option B: Custom Google OAuth2 App

1. Create a project in the [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the **Gmail API**
3. Create OAuth 2.0 credentials (Web Application type)
4. Add the redirect URI: `https://your-odoo-domain/google_gmail/confirm`
5. In Odoo, go to **Settings > General Settings > Discuss > Google Gmail**
6. Enter the **Client ID** and **Client Secret**

## XOAUTH2 Authentication

Both IMAP and SMTP use the **XOAUTH2** SASL mechanism, which passes a base64-encoded authentication string:

```
Base64("user={email}\1auth=Bearer {access_token}\1\1")
```

This is the standard OAuth2 authentication method for Gmail, documented in [Google's XOAUTH2 protocol](https://developers.google.com/gmail/imap/xoauth2-protocol).

The refresh token is stored permanently and used to generate short-lived access tokens on each mail operation.

## Token Management

| Token | Lifetime | Storage |
|-------|----------|---------|
| Refresh token | Permanent (until revoked) | `google_gmail_refresh_token` |
| Access token | ~1 hour | `google_gmail_access_token` |
| Access expiration | Unix timestamp | `google_gmail_access_token_expiration` |

Tokens are refreshed proactively: when `access_token_expiration - 10 seconds < current_time`, a new access token is obtained before use.

## Security Notes

1. **CSRF protection**: Every OAuth initiation includes a HMAC-based CSRF token verified on callback
2. **Email verification**: SMTP servers verify the authorized email matches the configured sender
3. **Token isolation**: Each mail server stores its own refresh token; one compromised server does not affect others
4. **Group restrictions**: Token fields are only visible to `base.group_system` (administrators)
5. **Timing-safe comparison**: CSRF tokens are compared using `consteq()` to prevent timing attacks

## Related

- [Modules/mail](mail.md) — Core email and messaging framework
- [Modules/fetchmail](fetchmail.md) — Incoming mail server configuration
- [Modules/mail_mail](mail_mail.md) — Outgoing mail server configuration
- [Modules/google_calendar](google_calendar.md) — Google Calendar OAuth2 integration
- [Modules/microsoft_outlook](microsoft_outlook.md) — Outlook OAuth2 for mail
