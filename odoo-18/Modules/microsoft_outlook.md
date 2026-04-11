---
Module: microsoft_outlook
Version: 18.0
Type: addon
Tags: #microsoft_outlook, #mail, #oauth, #integration
---

# microsoft_outlook — Microsoft Outlook Integration

> Outlook OAuth2 support for incoming (IMAP) and outgoing (SMTP) mail servers. Enables full OAuth2 authentication without passwords for both fetchmail and ir.mail.server.

## Module Overview

| Property | Value |
|---|---|
| Category | Hidden |
| Version | 1.1 |
| Depends | `mail` |
| License | LGPL-3 |

## What It Extends

- `ir.mail_server` — adds Outlook OAuth as SMTP authentication method
- `fetchmail.server` — adds Outlook OAuth as IMAP server type
- `microsoft.outlook.mixin` — reusable OAuth2 mixin (scope, token management, SASL string)
- `res.config.settings` — exposes `microsoft_outlook_client_id` and `microsoft_outlook_client_secret` as system parameters

## Architecture

The module defines an abstract `microsoft.outlook.mixin` that both `ir.mail_server` and `fetchmail.server` inherit. It handles the full OAuth2 authorization code + refresh token flow with Microsoft's identity platform.

```
Microsoft Identity v2.0 Endpoint:
https://login.microsoftonline.com/common/oauth2/v2.0/
```

## `microsoft.outlook.mixin` — Abstract Mixin

```python
class MicrosoftOutlookMixin(models.AbstractModel):
    _name = 'microsoft.outlook.mixin'
    _description = 'Microsoft Outlook Mixin'
    _OUTLOOK_SCOPE = None  # set on concrete models
```

**Fields (on the mixin model):**

| Field | Type | Description |
|---|---|---|
| `is_microsoft_outlook_configured` | Boolean (compute) | True if `microsoft_outlook_client_id` + `microsoft_outlook_client_secret` are set |
| `microsoft_outlook_refresh_token` | Char | Refresh token (group: `base.group_system`) |
| `microsoft_outlook_access_token` | Char | Current access token (group: `base.group_system`) |
| `microsoft_outlook_access_token_expiration` | Integer | Unix timestamp when access token expires |
| `microsoft_outlook_uri` | Char (compute) | Full OAuth2 authorization URL |

**Key Methods:**

- `_compute_is_microsoft_outlook_configured()` → reads `microsoft_outlook_client_id` and `microsoft_outlook_client_secret` from `ir.config_parameter`
- `_compute_outlook_uri()` → builds authorization URL with CSRF state: `{endpoint}?client_id=...&redirect_uri={base_url}/microsoft_outlook/confirm&response_type=code&scope=offline_access%20{_OUTLOOK_SCOPE}`
- `open_microsoft_outlook_uri()` → returns `ir.actions.act_url` to open the authorization page (requires `base.group_system`)
- `_fetch_outlook_refresh_token(authorization_code)` → exchanges auth code for tokens (returns `refresh_token`, `access_token`, `expiration`)
- `_fetch_outlook_access_token(refresh_token)` → uses refresh token to get new access token (also returns new refresh_token — Microsoft rotates them)
- `_fetch_outlook_token(grant_type, **values)` → generic token endpoint caller; raises `UserError` on failure
- `_generate_outlook_oauth2_string(login)` → builds the XOAUTH2 SASL string: `user={email}\1auth=Bearer {access_token}\1\1`; auto-refreshes token if expired
- `_get_outlook_csrf_token()` → generates HMAC scope token for CSRF protection of the OAuth callback
- `_get_microsoft_endpoint()` → returns `microsoft_outlook.endpoint` config param or default `https://login.microsoftonline.com/common/oauth2/v2.0/`

---

## `ir.mail_server` Extension — Outgoing (SMTP)

```python
class IrMailServer(models.Model):
    _name = 'ir.mail_server'
    _inherit = ['ir.mail_server', 'microsoft.outlook.mixin']
    _OUTLOOK_SCOPE = 'https://outlook.office.com/SMTP.Send'
```

**New Selection Value:**

- `smtp_authentication = 'outlook'` — Outlook OAuth Authentication

**Computed/Onchange Behavior:**

- `_compute_is_microsoft_outlook_configured()` → only True for records with `smtp_authentication == 'outlook'`
- `_compute_smtp_authentication_info()` → sets info string explaining OAuth process
- `_onchange_smtp_authentication_outlook()` → auto-sets `smtp_host='smtp.outlook.com'`, `smtp_encryption='starttls'`, `smtp_port=587`, and clears stored tokens
- `_on_change_smtp_user_outlook()` → sets `from_filter = smtp_user` (Outlook servers are personal only)

**Constraints (`_check_use_microsoft_outlook_service`):**

- `smtp_pass` must be empty (OAuth has no password)
- `smtp_encryption` must be `starttls`
- `smtp_user` must be set (email address)

**SMTP Login:**

- `_smtp_login(connection, smtp_user, smtp_password)` → if `smtp_authentication == 'outlook'`, builds XOAUTH2 base64 string and sends `AUTH XOAUTH2 {b64}` instead of plain login

---

## `fetchmail.server` Extension — Incoming (IMAP)

```python
class FetchmailServer(models.Model):
    _name = 'fetchmail.server'
    _inherit = ['fetchmail.server', 'microsoft.outlook.mixin']
    _OUTLOOK_SCOPE = 'https://outlook.office.com/IMAP.AccessAsUser.All'
```

**New Selection Value:**

- `server_type = 'outlook'` — Outlook OAuth Authentication

**Key Methods:**

- `_compute_is_microsoft_outlook_configured()` → only True for `server_type == 'outlook'`
- `_compute_server_type_info()` → sets descriptive info string for the UI
- `onchange_server_type()` → auto-sets `server='imap.outlook.com'`, `is_ssl=True`, `port=993`, clears stored tokens
- `_imap_login(connection)` → if `server_type == 'outlook'`, authenticates via XOAUTH2 and selects INBOX
- `_get_connection_type()` → returns `'imap'` for Outlook type (overrides the default that checks `is_ssl`)

**Constraint:** SSL (`is_ssl=True`) is required for Outlook servers.

---

## `res.config.settings` Extension

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
```

| Field | Type | Description |
|---|---|---|
| `microsoft_outlook_client_identifier` | Char | Config param: `microsoft_outlook_client_id` |
| `microsoft_outlook_client_secret` | Char | Config param: `microsoft_outlook_client_secret` |

These map to the Azure Active Directory app registration credentials in `ir.config_parameter`.

---

## OAuth2 Flow Summary

1. Admin registers an app at [Azure Portal](https://portal.azure.com) with `SMTP.Send` (outgoing) and/or `IMAP.AccessAsUser.All` (incoming) scopes.
2. In Odoo Settings, admin fills in Client ID and Client Secret.
3. On the mail server form, selecting `outlook` authentication opens the OAuth authorization URL (via `open_microsoft_outlook_uri` action).
4. User logs in to Microsoft, grants permissions, and is redirected to `/microsoft_outlook/confirm` with an auth code.
5. Odoo exchanges the auth code for `refresh_token` + `access_token` and stores them on the mail server record.
6. On each send/fetch, `_generate_outlook_oauth2_string()` auto-refreshes the access token if expired and generates the XOAUTH2 SASL string.

## See Also

- [[Modules/Mail]] — Base mail module
- [[Modules/Microsoft Account]] — `microsoft_account` for Azure credential management pattern
- [[Patterns/Security Patterns]] — OAuth2 token storage and group-based field visibility
- [[Modules/Auth OAuth]] — Alternative OAuth approach for user authentication
