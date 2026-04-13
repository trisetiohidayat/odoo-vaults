---
Module: google_account
Version: Odoo 18
Type: Integration
Tags: #odoo18, #integration, #oauth2, #google
Related: [Modules/google-gmail](odoo-18/Modules/google-gmail.md), [Modules/google-calendar](odoo-18/Modules/google-calendar.md), [Core/API](odoo-18/Core/API.md)
---

# Google Cloud Base (`google_account`)

> **Source:** `odoo/addons/google_account/`
> **Depends:** `base_setup`
> **Category:** Hidden/Tools
> **License:** LGPL-3

## Overview

`google_account` is the foundational module for all Google integrations in Odoo. It provides:

1. **`google.service`** — An abstract model containing shared OAuth2 infrastructure (token exchange, token refresh, HTTP requests) used by every Google integration (Gmail, Calendar, Drive, etc.)
2. **`GoogleAuth` controller** — The shared OAuth2 callback endpoint (`/google_account/authentication`) used by Calendar, Drive, and other per-user Google integrations
3. **`_get_client_secret` hook** — A module-level function that downstream modules can override to provide their own OAuth2 credentials

**Key distinction from `google_gmail`:**
- `google_account` provides `google.service._do_request()` for Google **Calendar API / Drive API** calls
- `google_gmail` has its **own completely independent token flow** for IMAP/SMTP (XOAUTH2) — it stores tokens directly on mail server records and does **not** use `google.service` for token management
- `google_gmail` uses `google_gmail_client_id` / `google_gmail_client_secret` stored directly in `ir.config_parameter`, bypassing the `google_<service>_client_id` pattern

---

## Architecture

```
google_account/
├── __manifest__.py
├── __init__.py
│   └── exports TIMEOUT for use by other modules
├── models/
│   ├── __init__.py
│   └── google_service.py   # google.service abstract model
└── controllers/
    ├── __init__.py
    └── main.py             # GoogleAuth controller — OAuth2 callback
```

---

## Model: `google.service`

> **File:** `models/google_service.py`
> **Inheritance:** `models.AbstractModel`
> **Purpose:** Shared OAuth2 and HTTP infrastructure for Google API calls

### Constants

```python
TIMEOUT = 20  # seconds (exported via __init__.py as google_account.TIMEOUT)

GOOGLE_AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/auth'
GOOGLE_TOKEN_ENDPOINT = 'https://accounts.google.com/o/oauth2/token'
GOOGLE_API_BASE_URL = 'https://www.googleapis.com'
```

### Module-Level Function: `_get_client_secret(ICP_sudo, service)`

Defined at **module level** (not as a model method) to serve as a **patchable extension hook**:

```python
def _get_client_secret(ICP_sudo, service):
    return ICP_sudo.get_param('google_%s_client_secret' % service)
```

Downstream modules can monkey-patch this function to inject their own credentials. This is critical for multi-tenant SaaS deployments where each Odoo instance uses its own Google Cloud project. The function should never return the secret in clear text to logs.

### `_get_client_id(service)`

Returns the OAuth2 client ID for a given service. Client IDs are not secrets (they appear in authorization URLs), so this is safe without sudo:

```python
def _get_client_id(self, service):
    ICP = self.env['ir.config_parameter'].sudo()
    return ICP.get_param('google_%s_client_id' % service)
```

### `_get_authorize_uri(service, scope, redirect_uri, state=None, approval_prompt=None, access_type=None)`

Builds the Google OAuth2 authorization URL. Called by integrating modules to generate the redirect URL:

```python
@api.model
def _get_authorize_uri(self, service, scope, redirect_uri, state=None,
                       approval_prompt=None, access_type=None):
    params = {
        'response_type': 'code',
        'client_id': self._get_client_id(service),
        'scope': scope,
        'redirect_uri': redirect_uri,
    }
    if state:
        params['state'] = state
    if approval_prompt:
        params['approval_prompt'] = approval_prompt
    if access_type:
        params['access_type'] = access_type

    encoded_params = urls.url_encode(params)
    return "%s?%s" % (GOOGLE_AUTH_ENDPOINT, encoded_params)
```

### `_get_google_tokens(authorize_code, service, redirect_uri)`

Exchanges an authorization code for access + refresh tokens. Called by the OAuth2 callback controller after Google redirects back with the code:

```python
@api.model
def _get_google_tokens(self, authorize_code, service, redirect_uri):
    ICP = self.env['ir.config_parameter'].sudo()

    headers = {"content-type": "application/x-www-form-urlencoded"}
    data = {
        'code': authorize_code,
        'client_id': self._get_client_id(service),
        'client_secret': _get_client_secret(ICP, service),
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri
    }
    dummy, response, dummy = self._do_request(
        GOOGLE_TOKEN_ENDPOINT, params=data, headers=headers, method='POST', preuri='')
    return (
        response.get('access_token'),
        response.get('refresh_token'),
        response.get('expires_in')
    )
```

**Returns:** `(access_token, refresh_token, expires_in)` — on `requests.HTTPError`, raises a config warning.

### `_refresh_google_token(service, rtoken)`

Uses a refresh token to obtain a new access token without user interaction:

```python
def _refresh_google_token(self, service, rtoken):
    ICP = self.env['ir.config_parameter'].sudo()

    headers = {"content-type": "application/x-www-form-urlencoded"}
    data = {
        'refresh_token': rtoken,
        'client_id': self._get_client_id(service),
        'client_secret': _get_client_secret(ICP, service),
        'grant_type': 'refresh_token',
    }
    dummy, response, dummy = self._do_request(
        GOOGLE_TOKEN_ENDPOINT, params=data, headers=headers, method='POST', preuri='')
    return (
        response.get('access_token'),
        response.get('expires_in')
    )
```

**Returns:** `(new_access_token, expires_in)`

### `_do_request(uri, params=None, headers=None, method='POST', preuri=GOOGLE_API_BASE_URL, timeout=TIMEOUT)`

Core HTTP request executor — all Google API calls go through this method:

```python
@api.model
def _do_request(self, uri, params=None, headers=None, method='POST',
                preuri=GOOGLE_API_BASE_URL, timeout=TIMEOUT):
    # URL allowlisting — prevents token leakage to arbitrary servers
    assert urls.url_parse(preuri + uri).host in [
        urls.url_parse(url).host for url in (GOOGLE_TOKEN_ENDPOINT, GOOGLE_API_BASE_URL)
    ]

    # Mask client_secret in logs (first 4 chars visible for debugging)
    _log_params = (params or {}).copy()
    if _log_params.get('client_secret'):
        _log_params['client_secret'] = str(_log_params['client_secret'])[:4] + 'x' * 12

    _logger.debug("Uri: %s - Type : %s - Headers: %s - Params : %s!",
                  uri, method, headers, _log_params)

    if method.upper() in ('GET', 'DELETE'):
        res = requests.request(method.lower(), preuri + uri, params=params, timeout=timeout)
    elif method.upper() in ('POST', 'PATCH', 'PUT'):
        res = requests.request(method.lower(), preuri + uri, data=params, headers=headers, timeout=timeout)
    else:
        raise Exception(_('Method not supported...'))

    res.raise_for_status()
    status = res.status_code

    if int(status) == 204:  # Google returns 204 No Content on DELETE
        response = False
    else:
        response = res.json()

    return (status, response, ask_time)
```

**Security features:**
- **URL allowlisting:** Only `GOOGLE_TOKEN_ENDPOINT` or `GOOGLE_API_BASE_URL` are permitted — prevents access token leakage if Odoo is compromised
- **Secrets masking:** `client_secret` is masked in debug logs (first 4 chars visible for debugging)
- **HTTP error propagation:** `raise_for_status()` ensures failures are not silently ignored

**Returns:** `(status_code, response_json_or_False, ask_time)` — the third element is the parsed `Date` header for server-time tracking.

---

## HTTP Controller: `GoogleAuth`

> **File:** `controllers/main.py`
> **Route:** `/google_account/authentication`
> **Auth:** `public` (accessible without Odoo login — handles the Google redirect before the user is authenticated)

### OAuth2 Callback

```python
class GoogleAuth(http.Controller):

    @http.route('/google_account/authentication', type='http', auth="public")
    def oauth2callback(self, **kw):
        state = json.loads(kw.get('state', '{}'))
        service = state.get('s')      # e.g., 'calendar'
        url_return = state.get('f')   # forward URL after auth

        if (not service or (kw.get('code') and not url_return)):
            raise BadRequest()

        if kw.get('code'):
            base_url = request.httprequest.url_root.strip('/') \
                or request.env.user.get_base_url()
            access_token, refresh_token, ttl = request.env['google.service']._get_google_tokens(
                kw['code'], service,
                redirect_uri=f'{base_url}/google_account/authentication')
            service_field = 'res_users_settings_id'
            if service_field in request.env.user:
                request.env.user[service_field]._set_google_auth_tokens(
                    access_token, refresh_token, ttl)
            else:
                raise Warning('No callback field for service <%s>' % service)
            return request.redirect(url_return)

        elif kw.get('error'):
            return request.redirect("%s%s%s" % (url_return, "?error=", kw['error']))
        else:
            return request.redirect("%s%s" % (url_return, "?error=Unknown_error"))
```

**L4 — Full callback flow:**

```
1. User clicks "Sync with Google Calendar" in Odoo
   → google_calendar calls _get_authorize_uri('calendar', scope, redirect_uri, state)
   → Browser redirected to Google consent screen with state={s:'calendar', f:'/odoo/...'}

2. User grants permission in Google
   → Google redirects to /google_account/authentication?code=AUTH_CODE&state={...}

3. Controller receives callback:
   a. auth="public" means no Odoo login required (must work for users who aren't logged in yet)
   b. Parse state JSON → extract service='calendar', url_return='/odoo/...'
   c. Validate: if code present but no url_return → BadRequest
   d. Call google.service._get_google_tokens() → exchanges code for tokens

4. Token storage via res.users.settings:
   a. Check: does request.env.user have 'res_users_settings_id' field?
      - If yes: call user.res_users_settings_id._set_google_auth_tokens(access, refresh, ttl)
      - If no: raise Warning (e.g., public user trying to link calendar)

5. Redirect back to url_return (e.g., the calendar settings page)

6. If user denied permission:
   → Google redirects with error=access_denied (or similar)
   → Controller redirects to url_return?error=access_denied
```

---

## Two Token Storage Patterns in Odoo 18

Odoo uses **two fundamentally different token storage patterns**, depending on the integration type:

### Pattern A: Mail Server Tokens — Stored on Mail Server Records (`google_gmail`)

Tokens stored as fields on the mail server model itself (self-contained, no `google.service` dependency):

```
fetchmail.server / ir.mail_server
  ├── google_gmail_refresh_token              (Char, copy=False, groups=base.group_system)
  ├── google_gmail_access_token              (Char, copy=False, groups=base.group_system)
  └── google_gmail_access_token_expiration   (Integer, copy=False, groups=base.group_system)

OAuth2 flow: google_gmail_mixin._generate_oauth2_string()
  → auto-refreshes via _fetch_gmail_access_token(refresh_token)
  → uses XOAUTH2 SASL mechanism for IMAP/SMTP
```

### Pattern B: User Settings Tokens — Stored on `res.users.settings` (`google_calendar`, etc.)

Tokens stored in the user's personal settings record:

```
res.users
  └── res_users_settings_id (Many2one → res.users.settings)
        ├── google_calendar_rtoken         (Char)
        ├── google_calendar_token           (Char)
        ├── google_calendar_token_validity (Datetime)
        └── google_calendar_sync_token     (Char)

OAuth2 flow: google_account controller → _set_google_auth_tokens()
  → refresh via google.service._refresh_google_token()
  → used in Google Calendar API HTTP calls via google.service._do_request()
```

**The `res_users_settings_id` field on `res.users`** is a lazy-created per-user settings record (`res.users.settings` model). Google Calendar extends `res.users` with `related` fields pointing into this settings record:

```python
# google_calendar/models/res_users.py
class User(models.Model):
    _inherit = 'res.users'

    google_calendar_rtoken = fields.Char(
        related='res_users_settings_id.google_calendar_rtoken',
        groups="base.group_system")
```

---

## How `google.service` Is Used by `google_calendar`

The `google_calendar` module demonstrates the complete `google_account` integration pattern:

1. **`google_calendar/res_users.py`** — Extends `res.users` with `related` fields to `res_users_settings_id` (Google tokens)
2. **`google_calendar/models/google_sync.py`** — Defines `google_calendar_token` context manager:
   ```python
   with google_calendar_token(self) as token:
       events, next_sync_token, default_reminders = calendar_service.get_events(
           sync_token=token, token=token)
   ```
   Inside the context manager, `_refresh_google_token()` is called automatically if the access token is expired
3. **`google_calendar/models/calendar.py`** — Calls `google.service._do_request()` to interact with Google Calendar API v3
4. **`google_calendar/wizard/reset_account.py`** — Calls `google.service._get_google_tokens()` to handle re-authorization
5. **Import pattern:**
   ```python
   from odoo.addons.google_account.models import google_service
   # or: from odoo.addons.google_account.models.google_service import TIMEOUT
   ```

---

## ICP Configuration Parameters

Stored in `ir.config_parameter` (system parameters), keyed by service name:

| Parameter | Per-Service Example | Used By |
|---|---|---|
| `google_{service}_client_id` | `google_calendar_client_id` | `_get_client_id()`, `_get_authorize_uri()`, `_get_google_tokens()` |
| `google_{service}_client_secret` | `google_calendar_client_secret` | `_get_client_secret()` hook |

**Note:** `google_gmail` stores its credentials as `google_gmail_client_id` / `google_gmail_client_secret` **directly in `ir.config_parameter`** (via `res_config_settings.py`) and does **not** use the `google_<service>_client_id` pattern from `google_account`.

---

## Security Notes

1. **URL allowlisting in `_do_request`:** Only `GOOGLE_TOKEN_ENDPOINT` and `GOOGLE_API_BASE_URL` are permitted — prevents access token leakage if the Odoo server is compromised
2. **Client secret masking in logs:** `_log_params` masks `client_secret` to first 4 characters
3. **`auth="public"` callback:** The `/google_account/authentication` route is intentionally public — it handles the OAuth redirect before the user authenticates with Odoo. Security is provided by the `state` HMAC token embedded in the redirect
4. **`_get_client_secret` hook:** Defined at module level so downstream modules (e.g., `google_gmail` in Odoo 17) can override it to provide their own credentials without sharing a single Google Cloud project across all integrations
5. **Refresh token single-use:** Google invalidates the old refresh token each time a new one is issued. Odoo's `_refresh_google_token()` always uses the most recently stored refresh token
