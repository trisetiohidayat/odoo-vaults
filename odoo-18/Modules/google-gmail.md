---
Module: google_gmail
Version: Odoo 18
Type: Integration
Tags: #odoo18, #integration, #email, #gmail, #oauth2
Related: [Modules/Mail](mail.md), [Modules/google-account](google-account.md), [Core/API](API.md)
---

# Gmail Integration (`google_gmail`)

> **Source:** `odoo/addons/google_gmail/`
> **Depends:** `mail`
> **Category:** Hidden
> **Auto-install:** `True`
> **License:** LGPL-3

## Overview

The `google_gmail` module provides two Gmail integrations in Odoo:

1. **Incoming mail server (fetchmail):** Fetch emails from a Gmail inbox via IMAP using OAuth2 (replaces the old IMAP/POP password-based auth)
2. **Outgoing mail server (SMTP):** Send emails through Gmail's SMTP server using OAuth2 (replaces password-based SMTP auth)

Both integrations replace the traditional username/password authentication with **Google OAuth2**, eliminating the need for Gmail's less-secure "App Passwords."

**Google Scope Used:** `https://mail.google.com/` (full read/write access to Gmail)

---

## Architecture

```
google_gmail/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── google_gmail_mixin.py     # Abstract mixin — OAuth2 token management
│   ├── fetchmail_server.py       # Extends fetchmail.server (incoming)
│   ├── ir_mail_server.py         # Extends ir.mail_server (outgoing)
│   └── res_config_settings.py    # Global OAuth2 credentials
├── controllers/
│   ├── __init__.py
│   └── main.py                   # OAuth2 callback: /google_gmail/confirm
├── views/
│   ├── fetchmail_server_views.xml   # fetchmail.server form extension
│   ├── ir_mail_server_views.xml     # ir.mail_server form extension
│   └── res_config_settings_views.xml  # Settings form
└── static/
    └── src/scss/
        └── google_gmail.scss    # Style: authorization_code field width
```

---

## Global Configuration

> **File:** `models/res_config_settings.py`

Stored in `ir.config_parameter` (accessible from Settings > Email > Email Servers):

| Config Parameter | Field | Description |
|---|---|---|
| `google_gmail_client_id` | `google_gmail_client_identifier` | OAuth2 Client ID from Google Cloud Console |
| `google_gmail_client_secret` | `google_gmail_client_secret` | OAuth2 Client Secret from Google Cloud Console |

These are the **global** OAuth2 app credentials shared by all Gmail mail servers in the Odoo instance. Each individual mail server then gets its own **refresh token** after the admin authorizes it.

---

## Model: `google.gmail.mixin` (Abstract)

> **File:** `models/google_gmail_mixin.py`
> **Inheritance:** `models.AbstractModel`
> **Mixin for:** `fetchmail.server`, `ir.mail_server`

### Fields

| Field | Type | Groups | Description |
|---|---|---|---|
| `google_gmail_authorization_code` | Char | `base.group_system` | Temporary code returned by Google during OAuth flow. Not used after token exchange. `copy=False` |
| `google_gmail_refresh_token` | Char | `base.group_system` | **Long-lived token** used to obtain new access tokens. Persisted. `copy=False` |
| `google_gmail_access_token` | Char | `base.group_system` | Short-lived (1 hour) access token. Refreshed automatically. `copy=False` |
| `google_gmail_access_token_expiration` | Integer | `base.group_system` | Unix timestamp when the access token expires. `copy=False` |
| `google_gmail_uri` | Char (compute) | `base.group_system` | Computed OAuth2 authorization URL for this specific record |

### `_SERVICE_SCOPE`

```python
_SERVICE_SCOPE = 'https://mail.google.com/'
```

This single scope grants full Gmail access. It is passed to Google during the authorization request.

### Computed: `_compute_gmail_uri()`

Builds the Google OAuth2 authorization URL. Called whenever `google_gmail_authorization_code` changes.

```python
@api.depends('google_gmail_authorization_code')
def _compute_gmail_uri(self):
    Config = self.env['ir.config_parameter'].sudo()
    google_gmail_client_id = Config.get_param('google_gmail_client_id')
    google_gmail_client_secret = Config.get_param('google_gmail_client_secret')
    base_url = self.get_base_url()

    redirect_uri = url_join(base_url, '/google_gmail/confirm')

    for record in self:
        google_gmail_uri = 'https://accounts.google.com/o/oauth2/v2/auth?%s' % url_encode({
            'client_id': google_gmail_client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': self._SERVICE_SCOPE,
            'access_type': 'offline',      # Required for refresh token!
            'prompt': 'consent',            # Force consent screen (ensures refresh token)
            'state': json.dumps({
                'model': record._name,
                'id': record.id or False,
                'csrf_token': record._get_gmail_csrf_token() if record.id else False,
            })
        })
        record.google_gmail_uri = google_gmail_uri
```

**Key parameters:**
- `access_type: 'offline'` — tells Google to return a **refresh token** (not just an access token). Without this, the access token expires and cannot be renewed without re-authorization.
- `prompt: 'consent'` — forces the consent screen, ensuring a new refresh token is issued even if the user previously authorized.
- `state` — JSON containing `model`, `id`, and `csrf_token`. The `csrf_token` prevents CSRF attacks during the OAuth callback.

### `open_google_gmail_uri()`

Action method invoked by a button on the mail server form. Opens the Google OAuth consent page in a new tab. Requires `base.group_system`.

```python
def open_google_gmail_uri(self):
    self.ensure_one()
    if not self.env.user.has_group('base.group_system'):
        raise AccessError(_('Only the administrator can link a Gmail mail server.'))
    if not self.google_gmail_uri:
        raise UserError(_('Please configure your Gmail credentials.'))
    return {
        'type': 'ir.actions.act_url',
        'url': self.google_gmail_uri,
    }
```

### Token Exchange Methods

#### `_fetch_gmail_refresh_token(authorization_code)`

Exchanges the one-time authorization code for a refresh token + initial access token.

```python
def _fetch_gmail_refresh_token(self, authorization_code):
    response = self._fetch_gmail_token('authorization_code', code=authorization_code)
    return (
        response['refresh_token'],
        response['access_token'],
        int(time.time()) + response['expires_in'],
    )
```

#### `_fetch_gmail_access_token(refresh_token)`

Uses the refresh token to obtain a new short-lived access token.

```python
def _fetch_gmail_access_token(self, refresh_token):
    response = self._fetch_gmail_token('refresh_token', refresh_token=refresh_token)
    return (
        response['access_token'],
        int(time.time()) + response['expires_in'],
    )
```

#### `_fetch_gmail_token(grant_type, **values)`

Generic token endpoint caller. Posts to `https://oauth2.googleapis.com/token`.

```python
def _fetch_gmail_token(self, grant_type, **values):
    Config = self.env['ir.config_parameter'].sudo()
    google_gmail_client_id = Config.get_param('google_gmail_client_id')
    google_gmail_client_secret = Config.get_param('google_gmail_client_secret')
    base_url = self.get_base_url()
    redirect_uri = url_join(base_url, '/google_gmail/confirm')

    response = requests.post(
        'https://oauth2.googleapis.com/token',
        data={
            'client_id': google_gmail_client_id,
            'client_secret': google_gmail_client_secret,
            'grant_type': grant_type,
            'redirect_uri': redirect_uri,
            **values,
        },
        timeout=GMAIL_TOKEN_REQUEST_TIMEOUT,  # 5 seconds
    )
```

#### `_generate_oauth2_string(user, refresh_token)`

Generates the XOAUTH2 SASL authentication string used in SMTP/IMAP connections. Automatically refreshes the access token if expired.

```python
def _generate_oauth2_string(self, user, refresh_token):
    self.ensure_one()
    now_timestamp = int(time.time())
    if not self.google_gmail_access_token \
       or not self.google_gmail_access_token_expiration \
       or self.google_gmail_access_token_expiration - GMAIL_TOKEN_VALIDITY_THRESHOLD < now_timestamp:
        # Token expired or missing — refresh it
        access_token, expiration = self._fetch_gmail_access_token(
            self.google_gmail_refresh_token)
        self.write({
            'google_gmail_access_token': access_token,
            'google_gmail_access_token_expiration': expiration,
        })
    return 'user=%s\1auth=Bearer %s\1\1' % (user, self.google_gmail_access_token)
```

**Token validity threshold:** `GMAIL_TOKEN_VALIDITY_THRESHOLD = GMAIL_TOKEN_REQUEST_TIMEOUT + 5 = 10 seconds`. The access token is refreshed 10 seconds before its actual expiry to account for network latency.

### CSRF Protection

#### `_get_gmail_csrf_token()`

Generates a HMAC-based CSRF token using `tools.misc.hmac()` scoped to `(model_name, record_id)`.

```python
def _get_gmail_csrf_token(self):
    self.ensure_one()
    return tools.misc.hmac(
        env=self.env(su=True),
        scope='google_gmail_oauth',
        message=(self._name, self.id),
    )
```

This token is embedded in the `state` parameter during authorization, then verified in the callback to prevent cross-site request forgery.

---

## Model: `fetchmail.server` (Extended)

> **File:** `models/fetchmail_server.py`
> **Inheritance:** `fetchmail.server` + `google.gmail.mixin`

### Field Extension

| Field | Change | Description |
|---|---|---|
| `server_type` | `selection_add` | Added `'gmail'` option to server type selection |

The `'gmail'` option uses IMAP over SSL (port 993) with OAuth2 authentication.

### Server Type Info

```python
def _compute_server_type_info(self):
    gmail_servers = self.filtered(lambda server: server.server_type == 'gmail')
    gmail_servers.server_type_info = _(
        'Connect your Gmail account with the OAuth Authentication process. \n'
        'You will be redirected to the Gmail login page where you will '
        'need to accept the permission.')
    super(FetchmailServer, self - gmail_servers)._compute_server_type_info()
```

### Onchange: Auto-configure for Gmail

```python
@api.onchange('server_type', 'is_ssl', 'object_id')
def onchange_server_type(self):
    if self.server_type == 'gmail':
        self.server = 'imap.gmail.com'
        self.is_ssl = True
        self.port = 993
    else:
        self.google_gmail_authorization_code = False
        self.google_gmail_refresh_token = False
        self.google_gmail_access_token = False
        self.google_gmail_access_token_expiration = False
        super(FetchmailServer, self).onchange_server_type()
```

When the admin selects "Gmail OAuth Authentication" as the server type, Odoo automatically:
- Sets server to `imap.gmail.com`
- Enables SSL (`is_ssl = True`)
- Sets port to `993` (Gmail IMAP over SSL)

### IMAP Login via OAuth2

```python
def _imap_login(self, connection):
    self.ensure_one()
    if self.server_type == 'gmail':
        auth_string = self._generate_oauth2_string(self.user, self.google_gmail_refresh_token)
        connection.authenticate('XOAUTH2', lambda x: auth_string)
        connection.select('INBOX')
    else:
        super(FetchmailServer, self)._imap_login(connection)
```

Uses the IMAP `AUTHENTICATE` command with the `XOAUTH2` mechanism. The connection object (an `IMAP4_SSL` wrapper) receives the OAuth2 string and uses it to authenticate with Gmail.

### Connection Type

```python
def _get_connection_type(self):
    self.ensure_one()
    return 'imap' if self.server_type == 'gmail' else super()._get_connection_type()
```

Gmail fetchmail servers always use IMAP (not POP). The parent implementation would choose `imap` or `pop` based on the server type.

---

## Model: `ir.mail_server` (Extended)

> **File:** `models/ir_mail_server.py`
> **Inheritance:** `ir.mail_server` + `google.gmail.mixin`

### Field Extension

| Field | Change | Description |
|---|---|---|
| `smtp_authentication` | `selection_add` | Added `'gmail'` option |

```python
smtp_authentication = fields.Selection(
    selection_add=[('gmail', 'Gmail OAuth Authentication')],
    ondelete={'gmail': 'set default'})
```

When a Gmail server is deleted, the authentication method falls back to the default (`'login'`).

### SMTP Authentication Info

```python
def _compute_smtp_authentication_info(self):
    gmail_servers = self.filtered(lambda server: server.smtp_authentication == 'gmail')
    gmail_servers.smtp_authentication_info = _(
        'Connect your Gmail account with the OAuth Authentication process.  \n'
        'By default, only a user with a matching email address will be able to use this server. '
        'To extend its use, you should set a "mail.default.from" system parameter.')
    super(IrMailServer, self - gmail_servers)._compute_smtp_authentication_info()
```

### Onchange: Auto-configure for Gmail SMTP

```python
@api.onchange('smtp_authentication')
def _onchange_smtp_authentication_gmail(self):
    if self.smtp_authentication == 'gmail':
        self.smtp_host = 'smtp.gmail.com'
        self.smtp_encryption = 'starttls'
        self.smtp_port = 587
    else:
        self.google_gmail_authorization_code = False
        self.google_gmail_refresh_token = False
        self.google_gmail_access_token = False
        self.google_gmail_access_token_expiration = False
```

Auto-configures Gmail SMTP with TLS (STARTTLS) on port 587. Note: Gmail also supports SMTPS on port 465, but Odoo uses STARTTLS (port 587) as the default.

### Onchange: Set `from_filter` to Gmail Address

```python
@api.onchange('smtp_user', 'smtp_authentication')
def _on_change_smtp_user_gmail(self):
    if self.smtp_authentication == 'gmail':
        self.from_filter = self.smtp_user  # e.g., "user@gmail.com"
```

The `from_filter` restricts this mail server to sending only from the authenticated Gmail address. This prevents the server from being used to send from other addresses.

### Constraints

```python
@api.constrains('smtp_authentication', 'smtp_pass', 'smtp_encryption', 'from_filter', 'smtp_user')
def _check_use_google_gmail_service(self):
    gmail_servers = self.filtered(lambda server: server.smtp_authentication == 'gmail')
    for server in gmail_servers:
        if server.smtp_pass:
            raise UserError(_('Please leave the password field empty for Gmail mail server...'))
        if server.smtp_encryption != 'starttls':
            raise UserError(_('Incorrect Connection Security for Gmail... Please set it to "TLS (STARTTLS)".'))
        if not server.smtp_user:
            raise UserError(_('Please fill the "Username" field with your Gmail username...'))
```

Three constraints enforced at record write time:
1. `smtp_pass` must be **empty** (OAuth2 uses tokens, not passwords)
2. `smtp_encryption` must be **`starttls`** (not `none` or `ssl`)
3. `smtp_user` must be **set** (the Gmail address used for authorization)

### SMTP Login via OAuth2

```python
def _smtp_login(self, connection, smtp_user, smtp_password):
    if len(self) == 1 and self.smtp_authentication == 'gmail':
        auth_string = self._generate_oauth2_string(smtp_user, self.google_gmail_refresh_token)
        oauth_param = base64.b64encode(auth_string.encode()).decode()
        connection.ehlo()
        connection.docmd('AUTH', f'XOAUTH2 {oauth_param}')
    else:
        super(IrMailServer, self)._smtp_login(connection, smtp_user, smtp_password)
```

Overrides the parent SMTP login. Instead of calling `connection.login(smtp_user, smtp_password)`, it:
1. Generates the XOAUTH2 string via `_generate_oauth2_string()` (which auto-refreshes the token if needed)
2. Base64-encodes it
3. Issues `AUTH XOAUTH2 <base64>` via `docmd`

---

## Controller: `GoogleGmailController`

> **File:** `controllers/main.py`
> **Route:** `/google_gmail/confirm`

### OAuth2 Callback Flow

```
1. Admin clicks "Connect your Gmail account" button
   → open_google_gmail_uri() returns act_url to:
     https://accounts.google.com/o/oauth2/v2/auth?client_id=...&scope=...&state=json(model,id,csrf)

2. User logs into Google and grants permission
   → Google redirects to: /google_gmail/confirm?code=AUTH_CODE&state=json(...)

3. Controller receives the callback:
   - Validates user is in base.group_system
   - Parses and validates the state JSON
   - Verifies CSRF token against stored HMAC
   - Calls _fetch_gmail_refresh_token(code) → gets refresh + access token
   - Writes tokens to the mail server record
   - Redirects back to the mail server form
```

### Callback Code

```python
@http.route('/google_gmail/confirm', type='http', auth='user')
def google_gmail_callback(self, code=None, state=None, error=None, **kwargs):
    if not request.env.user.has_group('base.group_system'):
        raise Forbidden()

    if error:
        return _('An error occur during the authentication process.')

    state = json.loads(state)
    model_name = state['model']
    rec_id = state['id']
    csrf_token = state['csrf_token']

    model = request.env[model_name]
    record = model.browse(rec_id).exists()

    # Verify CSRF
    if not csrf_token or not consteq(csrf_token, record._get_gmail_csrf_token()):
        raise Forbidden()

    # Exchange code for tokens
    refresh_token, access_token, expiration = record._fetch_gmail_refresh_token(code)

    record.write({
        'google_gmail_access_token': access_token,
        'google_gmail_access_token_expiration': expiration,
        'google_gmail_authorization_code': code,
        'google_gmail_refresh_token': refresh_token,
    })

    return request.redirect(f'/odoo/{model_name}/{rec_id}')
```

**Security checks:**
1. `auth='user'` — requires authenticated Odoo user
2. `base.group_system` — requires system administrator group
3. CSRF token verification via `consteq()` (timing-safe comparison)
4. Record existence check (`browse().exists()`)
5. Model must inherit `google.gmail.mixin`

---

## OAuth2 Token Lifecycle

```
User clicks "Connect"
        │
        ▼
[Generate Authorization URL]
  - client_id, scope=https://mail.google.com/
  - access_type=offline, prompt=consent
  - state={model, id, csrf_token}
        │
        ▼
[User grants permission in browser]
        │
        ▼
[Google → /google_gmail/confirm?code=XXX]
        │
        ▼
[_fetch_gmail_refresh_token(code)]
  POST https://oauth2.googleapis.com/token
  Returns: refresh_token, access_token, expires_in
        │
        ▼
[Tokens stored on mail server record]
  - refresh_token: persistent, never expires (unless revoked)
  - access_token: expires in ~1 hour
        │
        ▼
[Every email send/fetch]
        │
        ▼
[_generate_oauth2_string()]
  Check: is access_token valid (expiry - 10s > now)?
    ├─ YES → use cached access_token
    └─ NO  → _fetch_gmail_access_token(refresh_token)
                → new access_token + new expiry
                → write to record
                → use new access_token
        │
        ▼
[SMTP: AUTH XOAUTH2 <base64>]
[IMAP: AUTHENTICATE XOAUTH2 <lambda>]
        │
        ▼
[Gmail API: send/fetch email]
```

---

## View Extensions

### `fetchmail.server` Form (`views/fetchmail_server_views.xml`)

Inherits `mail.view_email_server_form`. After the `user` field, inserts a Gmail-specific panel:

- If no refresh token: shows "Connect your Gmail account" button
- If refresh token present: shows green "Gmail Token Valid" badge
- If no OAuth credentials configured: shows warning alert linking to Settings

### `ir.mail_server` Form (`views/ir_mail_server_views.xml`)

Inherits `base.ir_mail_server_form`. Same pattern as fetchmail — after `smtp_user`:
- "Connect your Gmail account" button (no token)
- "Gmail Token Valid" badge (token valid)
- Configuration alert (no client credentials)

### Settings Form (`views/res_config_settings_views.xml`)

Inherits `mail.res_config_settings_view_form`. Replaces the Gmail module toggle placeholder with:
- `google_gmail_client_identifier` (ID) field
- `google_gmail_client_secret` (Secret) field
