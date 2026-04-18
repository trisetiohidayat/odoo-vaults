---
tags:
  - odoo
  - odoo19
  - modules
  - mail
  - outlook
  - oauth2
  - smtp
  - imap
  - authentication
created: 2026-04-11
updated: 2026-04-14
description: Adds Microsoft Outlook OAuth2 authentication for incoming (IMAP) and outgoing (SMTP) mail servers. Uses the microsoft.outlook.mixin pattern for token lifecycle management.
---

# Microsoft Outlook (`microsoft_outlook`)

> Enables Microsoft Outlook OAuth2 authentication for incoming and outgoing mail servers in Odoo. Users connect their personal Outlook accounts without exposing passwords, using the standard OAuth 2.0 authorization code flow. Supports IMAP (incoming mail via `fetchmail.server`) and SMTP (outgoing mail via `ir.mail_server`).

**Module:** `microsoft_outlook` | **Path:** `odoo/addons/microsoft_outlook/` | **Version:** 1.1
**Category:** Hidden | **Depends:** `mail` | **License:** LGPL-3
**Auto-install:** `True` | **Author:** Odoo S.A.

---

## Overview

`microsoft_outlook` is the Microsoft counterpart to `google_gmail`. Where Google Gmail replaces passwords with OAuth2 tokens for both IMAP and SMTP, `microsoft_outlook` does the same for Microsoft's Outlook/Office 365 accounts.

**Two supported protocols:**

| Protocol | Direction | Odoo Model | OAuth2 Scope |
|---|---|---|---|
| IMAP | Incoming (receive) | `fetchmail.server` | `https://outlook.office.com/IMAP.AccessAsUser.All` |
| SMTP | Outgoing (send) | `ir.mail_server` | `https://outlook.office.com/SMTP.Send` |

**Key architectural pattern:** A single abstract mixin (`MicrosoftOutlookMixin`) is inherited by both `fetchmail.server` and `ir.mail_server`. This mixin encapsulates all OAuth2 token lifecycle logic: authorization, token exchange, token refresh, and SASL string generation.

---

## Module File Structure

```
microsoft_outlook/
├── __init__.py
├── __manifest__.py               # depends: mail, auto_install: True
├── models/
│   ├── __init__.py
│   ├── microsoft_outlook_mixin.py  # Abstract mixin: token lifecycle
│   ├── fetchmail_server.py          # IMAP server extension
│   ├── ir_mail_server.py            # SMTP server extension
│   ├── res_config_settings.py       # Settings form: client_id/secret
│   └── res_users.py                 # Possibly user-level settings
├── controllers/
│   ├── __init__.py
│   └── main.py                      # OAuth callback routes
├── views/
│   ├── fetchmail_server_views.xml   # Outlook server type form
│   ├── ir_mail_server_views.xml     # Outlook SMTP auth form
│   ├── res_config_settings_views.xml # Admin settings
│   └── templates.xml                # OAuth consent / error QWeb pages
└── tests/
    ├── __init__.py
    └── test_fetchmail_outlook.py    # IMAP OAuth2 test + constraint test
```

---

## L1: Architecture — How the Mixin Connects Two Mail Server Types

### Inheritance Hierarchy

```
models/microsoft_outlook_mixin.py
    ┌──────────────────────────────────────────┐
    │ MicrosoftOutlookMixin (AbstractModel)    │
    │  _name = 'microsoft.outlook.mixin'       │
    │                                          │
    │  Token fields (all groups=base.group_system):   │
    │    microsoft_outlook_refresh_token       │
    │    microsoft_outlook_access_token        │
    │    microsoft_outlook_access_token_expiration │
    │    microsoft_outlook_uri (computed)     │
    │                                          │
    │  Key methods:                            │
    │    _compute_outlook_uri()                │
    │    open_microsoft_outlook_uri()          │
    │    _fetch_outlook_refresh_token()         │
    │    _fetch_outlook_access_token()          │
    │    _fetch_outlook_token()                 │
    │    _fetch_outlook_access_token_iap()     │
    │    _generate_outlook_oauth2_string()     │
    │    _get_outlook_csrf_token()             │
    │    _get_microsoft_endpoint()              │
    └───────────────┬──────────────────────────┘
                    │ _inherit
        ┌───────────┴───────────┐
        ▼                       ▼
models/fetchmail_server.py    models/ir_mail_server.py
    ┌────────────────────────┐     ┌─────────────────────────┐
    │ FetchmailServer        │     │ IrMail_Server           │
    │ _inherit = ['fetchmail │     │ _inherit = ['ir.mail_   │
    │  .server',             │     │  server',              │
    │  'microsoft.outlook.   │     │  'microsoft.outlook.   │
    │   mixin']              │     │   mixin']              │
    │                        │     │                         │
    │ _OUTLOOK_SCOPE =       │     │ _OUTLOOK_SCOPE =       │
    │  '...IMAP.Access...'   │     │  '...SMTP.Send'        │
    └────────────────────────┘     └─────────────────────────┘
```

### Why a Mixin?

The OAuth2 token lifecycle is **identical** for IMAP and SMTP: both need refresh token storage, access token refresh on expiry, and OAuth2 SASL string generation. The mixin avoids duplicating ~250 lines of token management code across two models. Each inheriting model only needs to define its own `_OUTLOOK_SCOPE` constant and implement protocol-specific login methods.

---

## L2: The `microsoft.outlook.mixin` — Token Lifecycle

### Fields

```python
# models/microsoft_outlook_mixin.py
class MicrosoftOutlookMixin(models.AbstractModel):
    _name = 'microsoft.outlook.mixin'

    microsoft_outlook_refresh_token = fields.Char(
        groups='base.group_system', copy=False)
    microsoft_outlook_access_token = fields.Char(
        groups='base.group_system', copy=False)
    microsoft_outlook_access_token_expiration = fields.Integer(
        groups='base.group_system', copy=False)
    microsoft_outlook_uri = fields.Char(
        compute='_compute_outlook_uri',
        groups='base.group_system',
        string='Authentication URI')
```

All token fields are `groups='base.group_system'` — only administrators can view or modify them. `copy=False` prevents tokens from being duplicated when a mail server record is duplicated.

### Computing the Authorization URI

```python
def _compute_outlook_uri(self):
    Config = self.env['ir.config_parameter'].sudo()
    microsoft_outlook_client_id = Config.get_param('microsoft_outlook_client_id')
    microsoft_outlook_client_secret = Config.get_param('microsoft_outlook_client_secret')
    is_configured = microsoft_outlook_client_id and microsoft_outlook_client_secret

    for record in self:
        if not is_configured:
            record.microsoft_outlook_uri = False
            continue

        record.microsoft_outlook_uri = url_join(self._get_microsoft_endpoint(), 'authorize?%s' % url_encode({
            'client_id': microsoft_outlook_client_id,
            'response_type': 'code',
            'redirect_uri': url_join(base_url, '/microsoft_outlook/confirm'),
            'response_mode': 'query',
            'scope': f'openid email offline_access https://outlook.office.com/User.read {self._OUTLOOK_SCOPE}',
            'state': json.dumps({
                'model': record._name,
                'id': record.id,
                'csrf_token': record._get_outlook_csrf_token(),
            }),
        }))
```

The state parameter carries:
- `model`: Which model is being authorized (`fetchmail.server` or `ir.mail_server`)
- `id`: The record ID — needed because the record must exist before the callback writes tokens
- `csrf_token`: HMAC-signed token to prevent cross-site request forgery on the callback

**CSRF protection:**

```python
def _get_outlook_csrf_token(self):
    self.ensure_one()
    return hmac(
        env=self.env(su=True),
        scope='microsoft_outlook_oauth',
        message=(self._name, self.id),
    )
```

Uses Odoo's `hmac` utility with `su=True` (system-wide, not per-database) scope. The HMAC is verified in the callback controller. If an attacker tricks an admin into visiting a crafted URL, the CSRF check blocks the token write.

### Authorization Flow — Two Paths

#### Path A: Direct OAuth (custom credentials)

```
Admin fills in Settings > Integrations > Microsoft OAuth:
  microsoft_outlook_client_id     ← from Azure App Registration
  microsoft_outlook_client_secret ← from Azure App Registration

User opens mail server form
  → clicks "Connect to Outlook"
  → open_microsoft_outlook_uri() returns ir.actions.act_url
  → Browser redirected to Microsoft login

User logs in and grants permissions
  → Microsoft redirects to /microsoft_outlook/confirm?code=XXX&state={...}
  → Controller verifies CSRF
  → record._fetch_outlook_refresh_token(code)
  → Tokens written to record
  → Redirect back to mail server form
```

#### Path B: IAP Proxy (Enterprise only, no credentials needed)

```
Admin does NOT fill in OAuth credentials

User opens mail server form
  → open_microsoft_outlook_uri() detects credentials missing
  → (EE only) calls IAP endpoint for outlook URL
  → User redirected to IAP proxy
  → IAP redirects to Microsoft login
  → Microsoft redirects to IAP callback
  → IAP redirects to /microsoft_outlook/iap_confirm?tokens...

Controller receives tokens directly from IAP
  → Writes tokens to record
  → Redirect back to mail server form
```

The IAP path requires no Azure app registration and no client secret. It only works on Odoo Enterprise (`release.version_info[-1] == 'e'`). The IAP endpoint (`https://outlook.api.odoo.com`) is Odoo's own OAuth proxy.

### Token Refresh

```python
def _generate_outlook_oauth2_string(self, login):
    self.ensure_one()
    now_timestamp = int(time.time())
    if not self.microsoft_outlook_access_token \
       or not self.microsoft_outlook_access_token_expiration \
       or self.microsoft_outlook_access_token_expiration - OUTLOOK_TOKEN_VALIDITY_THRESHOLD < now_timestamp:

        if not self.microsoft_outlook_refresh_token:
            raise UserError(_('Please connect with your Outlook account before using it.'))

        # Refresh the access token
        (self.microsoft_outlook_refresh_token,
         self.microsoft_outlook_access_token,
         _id_token,
         self.microsoft_outlook_access_token_expiration,
        ) = self._fetch_outlook_access_token(self.microsoft_outlook_refresh_token)

    return 'user=%s\1auth=Bearer %s\1\1' % (login, self.microsoft_outlook_access_token)
```

**Token validity threshold:** `OUTLOOK_TOKEN_VALIDITY_THRESHOLD = 10` seconds. The access token must have at least 10 seconds of remaining life before it's considered valid. This prevents race conditions where a token expires between the validity check and the actual use.

**The SASL XOAUTH2 string format:**
```
user=user@example.com\1auth=Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...\1\1
```
- `\1` is the ASCII SOH character (0x01), used as a separator per RFC 7628
- The string is base64-encoded before being sent via `AUTH XOAUTH2`

---

## L3: `fetchmail.server` — IMAP Integration

**File:** `models/fetchmail_server.py`

```python
class FetchmailServer(models.Model):
    _name = 'fetchmail.server'
    _inherit = ['fetchmail.server', 'microsoft.outlook.mixin']

    _OUTLOOK_SCOPE = 'https://outlook.office.com/IMAP.AccessAsUser.All'

    server_type = fields.Selection(
        selection_add=[('outlook', 'Outlook OAuth Authentication')],
        ondelete={'outlook': 'set default'})
```

**`server_type` selection addition:** Adding `('outlook', 'Outlook OAuth Authentication')` to the selection makes "Outlook OAuth Authentication" appear as a selectable option in the incoming mail server type dropdown.

**Onchange auto-configuration:**

```python
@api.onchange('server_type')
def onchange_server_type(self):
    if self.server_type == 'outlook':
        self.server = 'imap.outlook.com'
        self.is_ssl = True
        self.port = 993
    else:
        self.microsoft_outlook_refresh_token = False
        self.microsoft_outlook_access_token = False
        self.microsoft_outlook_access_token_expiration = False
        super().onchange_server_type()
```

When the user selects "Outlook OAuth Authentication", the form automatically fills:
- `server = 'imap.outlook.com'`
- `is_ssl = True` (SSL/TLS required for IMAP)
- `port = 993` (IMAPS standard port)

When the user switches away from Outlook, tokens are cleared.

**SSL constraint:**

```python
@api.constrains('server_type', 'is_ssl')
def _check_use_microsoft_outlook_service(self):
    for server in self:
        if server.server_type == 'outlook' and not server.is_ssl:
            raise UserError(_('SSL is required for server "%s".', server.name))
```

SSL is mandatory for Outlook IMAP. This is enforced at the constraint level — not an onchange — so it fires on both UI saves and direct Python writes.

**IMAP login override:**

```python
def _imap_login__(self, connection):
    self.ensure_one()
    if self.server_type == 'outlook':
        auth_string = self._generate_outlook_oauth2_string(self.user)
        connection.authenticate('XOAUTH2', lambda x: auth_string)
        connection.select('INBOX')
    else:
        super()._imap_login__(connection)
```

The `XOAUTH2` mechanism authenticates using the OAuth2 bearer token instead of a password. The `lambda x: auth_string` is the callback that `odoo.addons.mail.models.fetchmail.OdooIMAP4_SSL` uses to retrieve the SASL argument — it ignores the `x` parameter.

**Test coverage (verified from source):**

```python
@patch('odoo.addons.mail.models.fetchmail.OdooIMAP4_SSL')
def test_connect(self, mock_imap):
    mock_connection = Mock()
    mock_imap.return_value = mock_connection

    mail_server = self.env['fetchmail.server'].create({
        'name': 'Test server',
        'server_type': 'outlook',
        'user': 'test@example.com',
        'microsoft_outlook_access_token': 'test_access_token',
        'microsoft_outlook_access_token_expiration': time.time() + 1000000,
        'password': '',
        'is_ssl': True,
    })

    mail_server._connect__()

    mock_connection.authenticate.assert_called_once_with('XOAUTH2', ANY)
    args = mock_connection.authenticate.call_args[0]
    self.assertEqual(
        args[1](None),
        'user=test@example.com\1auth=Bearer test_access_token\1\1',
        msg='Should use the right access token'
    )
    mock_connection.select.assert_called_once_with('INBOX')

def test_constraints(self):
    with self.assertRaises(UserError, msg='Should ensure password is empty'):
        self.env['fetchmail.server'].create({
            'name': 'Test server',
            'server_type': 'outlook',
            'password': 'test',
        })
```

---

## L4: `ir.mail_server` — SMTP Integration

**File:** `models/ir_mail_server.py`

```python
class IrMail_Server(models.Model):
    _name = 'ir.mail_server'
    _inherit = ['ir.mail_server', 'microsoft.outlook.mixin']

    _OUTLOOK_SCOPE = 'https://outlook.office.com/SMTP.Send'

    smtp_authentication = fields.Selection(
        selection_add=[('outlook', 'Outlook OAuth Authentication')],
        ondelete={'outlook': 'set default'})
```

**Onchange auto-configuration:**

```python
@api.onchange('smtp_authentication')
def _onchange_smtp_authentication_outlook(self):
    if self.smtp_authentication == 'outlook':
        self.smtp_host = 'smtp.outlook.com'
        self.smtp_encryption = 'starttls'
        self.smtp_port = 587
    else:
        self.microsoft_outlook_refresh_token = False
        self.microsoft_outlook_access_token = False
        self.microsoft_outlook_access_token_expiration = False
```

SMTP uses STARTTLS on port 587 (submission), not IMAPS on port 993. The host is `smtp.outlook.com`. This matches Microsoft's official SMTP configuration.

**Encryption constraint:**

```python
@api.constrains('smtp_authentication', 'smtp_pass', 'smtp_encryption', 'smtp_user')
def _check_use_microsoft_outlook_service(self):
    outlook_servers = self.filtered(lambda server: server.smtp_authentication == 'outlook')
    for server in outlook_servers:
        if server.smtp_pass:
            raise UserError(_('Please leave the password field empty for Outlook mail server...'))
        if server.smtp_encryption != 'starttls':
            raise UserError(_('Incorrect Connection Security for Outlook... Please set it to "TLS (STARTTLS)".'))
        if not server.smtp_user:
            raise UserError(_('Please fill the "Username" field with your Outlook/Office365 username...'))
```

Three constraints enforce the Outlook-specific requirements: no password, STARTTLS required, username required.

**SMTP login override:**

```python
def _smtp_login__(self, connection, smtp_user, smtp_password):
    if len(self) == 1 and self.smtp_authentication == 'outlook':
        auth_string = self._generate_outlook_oauth2_string(smtp_user)
        oauth_param = base64.b64encode(auth_string.encode()).decode()
        connection.ehlo()
        connection.docmd('AUTH', f'XOAUTH2 {oauth_param}')
    else:
        super()._smtp_login__(connection, smtp_user, smtp_password)
```

The `AUTH XOAUTH2` command carries the base64-encoded SASL string. The `smtp_password` parameter is ignored (password-based auth is not used for Outlook).

**Rate limiting:**

```python
def _get_personal_mail_servers_limit(self):
    if self.smtp_authentication == 'outlook':
        return int(self.env['ir.config_parameter'].sudo()
            .get_param('mail.server.personal.limit.minutes_outlook')) or 10
    return super()._get_personal_mail_servers_limit()
```

Outlook servers are rate-limited to 10 emails per minute by default (vs 30 for standard SMTP). This reflects Microsoft's stricter sending limits to prevent spam classification.

**Email ownership verification:**

After OAuth callback receives tokens, the controller verifies the token belongs to the same email address configured on the server:

```python
# In controller: _check_email_and_redirect_to_outlook_record()
refresh_token, access_token, id_token, expiration = record._fetch_outlook_access_token(refresh_token)
id_token_data = id_token.split(".")[1]
id_token_data += '=' * (-len(id_token_data) % 4)
email = json.loads(base64.b64decode(id_token_data)).get('email')
if email_normalize(email) != email_normalize(record[record._email_field]):
    return error_page("...addresses don't match...")
```

This prevents an attacker who obtains an Outlook token for one account from binding it to a different mail server in Odoo.

---

## L5: OAuth Controller Routes

**File:** `controllers/main.py`

### Route 1: `/microsoft_outlook/confirm`

Standard OAuth 2.0 callback. Receives `code` (authorization code) and `state` (JSON with model, id, csrf_token).

```
GET /microsoft_outlook/confirm?code=XXXXX&state={"model":"fetchmail.server","id":7,"csrf_token":"..."}
```

Flow:
1. Parse `state` JSON
2. Verify CSRF token
3. Call `record._fetch_outlook_refresh_token(code)` to exchange code for tokens
4. Call `_check_email_and_redirect_to_outlook_record()` to verify email ownership (for `ir.mail_server`)
5. Write tokens to record
6. Redirect to record form or user preferences

### Route 2: `/microsoft_outlook/iap_confirm`

IAP proxy callback. Receives tokens directly (already exchanged by IAP):

```
GET /microsoft_outlook/iap_confirm?model=...&rec_id=...&csrf_token=...&access_token=...&refresh_token=...&expiration=...
```

### Redirect URL Logic

```python
def _get_redirect_url(self, record):
    if (
        (record._name != 'ir.mail_server'
         or record != request.env.user.outgoing_mail_server_id)
        and request.env.user.has_group('base.group_system')
    ):
        return f'/odoo/{record._name}/{record.id}'  # Admin → mail server form
    return f'/odoo/my-preferences/{request.env.user.id}'  # User → preferences
```

- Admin configuring a general mail server → redirected to the mail server form
- User configuring their personal outgoing mail server → redirected to their user preferences

---

## L6: Version Changes Odoo 18 to 19

| Aspect | Odoo 18 | Odoo 19 | Impact |
|---|---|---|---|
| Mixin architecture | Same | Unchanged | Stable |
| `_OUTLOOK_SCOPE` per model | Same | Unchanged | IMAP + SMTP scopes unchanged |
| IAP fallback | Present | Present | EE-only fallback still works |
| `hmac` scope name | `microsoft_outlook_oauth` | Unchanged | CSRF tokens valid across upgrade |
| `release.version_info` check | `!= 'e'` | Unchanged | CE still blocks IAP path |
| `_fetch_outlook_token` error handling | JSON error parse | Unchanged | Behavior stable |
| `OUTLOOK_TOKEN_VALIDITY_THRESHOLD` | `10` seconds | Unchanged | Prevents token expiry races |
| Rate limit for Outlook SMTP | `mail.server.personal.limit.minutes_outlook` | Default 10/min | Stable |

**No breaking changes** between Odoo 18 and 19 for `microsoft_outlook`. The module was introduced as a new feature in Odoo 15/16 and has remained architecturally stable.

---

## Security Analysis

| Concern | Risk | Assessment |
|---|---|---|
| CSRF on OAuth callback | HIGH without mitigation | `_get_outlook_csrf_token()` uses HMAC; verified in every callback |
| Token stored in DB | MEDIUM | Token fields are `groups='base.group_system'`; not exposed to non-admin users |
| Email ownership spoofing | HIGH without mitigation | Controller decodes `id_token` JWT and compares `email` claim to server's email |
| Token stealing via record duplication | LOW | `copy=False` on all token fields prevents duplication |
| IMAP/SMTP without encryption | BLOCKED | Constraint enforces `is_ssl=True` (IMAP) and `starttls` (SMTP) |
| Password still set on Outlook server | BLOCKED | Constraint raises `UserError` if `smtp_pass` or `password` is non-empty |
| OAuth token stored in transit | SAFE | All token exchange happens server-to-server via HTTPS |
| IAP proxy MITM | SAFE | IAP endpoint is Odoo's own domain; HTTPS enforced |
| CSRF token reuse | SAFE | Each CSRF token is scoped to `(model_name, record_id)` — replayable only for the same record |

### Why `hmac` with `su=True`?

The CSRF token uses `env=self.env(su=True)` to generate a system-wide HMAC key. This is correct because:
1. The key must survive database updates/restores (not tied to a specific user session)
2. The token is validated in the controller, not in an ORM method — there is no user context
3. The `(model_name, record_id)` tuple in the HMAC message ensures the token is bound to a specific record

---

## Failure Mode Diagnostics

| Symptom | Root Cause | Resolution |
|---|---|---|
| "Please connect with your Outlook account" error when sending | No refresh token stored | Click "Connect to Outlook" on the mail server form |
| "An error occurred when fetching the access token" | Invalid/expired refresh token | Click "Connect to Outlook" to re-authorize and get a new refresh token |
| Outlook server won't save | `smtp_pass` or `password` is non-empty | Clear the password field; Outlook uses OAuth tokens |
| Mail fetch fails silently | IMAP server type not set to 'outlook' | Select "Outlook OAuth Authentication" in the server type dropdown |
| "SSL is required" error | `is_ssl = False` on Outlook IMAP server | Set `is_ssl = True` (auto-set by onchange) |
| Wrong emails fetched | Token belongs to wrong Outlook account | Click "Connect to Outlook" with the correct account; controller validates email match |
| "Incorrect Connection Security" | Encryption not STARTTLS | Set encryption to "TLS (STARTTLS)" on port 587 |

---

## See Also

- [Modules/mail](Modules/mail.md) — `fetchmail.server`, `ir.mail_server`, mail threading
- [Modules/google_gmail](Modules/google_gmail.md) — Google's OAuth2 mail integration (mirror of this module)
- [Modules/mail_plugin](Modules/mail_plugin.md) — Outlook contacts enrichment via IAP
- [Core/Fields](Core/Fields.md) — Many2one, Char, Boolean field types
- [Core/API](Core/API.md) — `@api.constrains`, `@api.onchange`, `@api.model` decorator patterns
- [Patterns/Security Patterns](Patterns/Security Patterns.md) — CSRF protection, HMAC tokens, OAuth2 flows
