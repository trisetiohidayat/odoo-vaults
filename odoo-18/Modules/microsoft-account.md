# microsoft_account — Microsoft Cloud Integration Base

## Overview

The `microsoft_account` module is the **foundation module** for all Microsoft Cloud integrations in Odoo. It provides OAuth2 authentication services for the Microsoft identity platform (Azure AD / MS Graph API), token management, and HTTP request utilities used by downstream modules such as `microsoft_calendar`.

**Depends:** `base_setup`
**Category:** Hidden/Tools
**License:** LGPL-3

---

## Architecture

```
microsoft_account/
├── models/
│   ├── microsoft_service.py  # AbstractModel — OAuth2 + MS Graph API base
│   └── res_users.py          # res.users extension with microsoft_* token fields
├── controllers/
│   └── main.py               # MicrosoftAuth controller — OAuth2 callback route
├── data/
│   └── microsoft_account_data.xml  # Default microsoft_redirect_uri
└── __manifest__.py
```

---

## Model: `microsoft.service` (AbstractModel)

**File:** `addons/microsoft_account/models/microsoft_service.py`

### Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `TIMEOUT` | `20` | Default HTTP request timeout (seconds) |
| `DEFAULT_MICROSOFT_AUTH_ENDPOINT` | `https://login.microsoftonline.com/common/oauth2/v2.0/authorize` | Authorization URL |
| `DEFAULT_MICROSOFT_TOKEN_ENDPOINT` | `https://login.microsoftonline.com/common/oauth2/v2.0/token` | Token exchange URL |
| `DEFAULT_MICROSOFT_GRAPH_ENDPOINT` | `https://graph.microsoft.com` | MS Graph API base URL |
| `RESOURCE_NOT_FOUND_STATUSES` | `(204, 404)` | HTTP codes treated as empty responses |

### Key Methods

#### `_get_microsoft_client_id(service)`

Reads `microsoft_{service}_client_id` from `ir.config_parameter`. Client ID is not treated as a secret — it is safe to include in authorization URLs in clear text.

#### `_get_calendar_scope()`

```python
def _get_calendar_scope(self):
    return 'offline_access openid Calendars.ReadWrite'
```

Returns the OAuth2 scope string for Microsoft Calendar access. This is the **default scope** used by all Microsoft Calendar integrations:
- `offline_access` — requests a refresh token (required for background sync)
- `openid` — OpenID Connect identity layer
- `Calendars.ReadWrite` — read/write access to user calendars

#### `_get_auth_endpoint()` / `_get_token_endpoint()`

```python
@api.model
def _get_auth_endpoint(self):
    return self.env["ir.config_parameter"].sudo().get_param(
        'microsoft_account.auth_endpoint', DEFAULT_MICROSOFT_AUTH_ENDPOINT)

@api.model
def _get_token_endpoint(self):
    return self.env["ir.config_parameter"].sudo().get_param(
        'microsoft_account.token_endpoint', DEFAULT_MICROSOFT_TOKEN_ENDPOINT)
```

Both endpoints are **configurable via ICP**, defaulting to the shared multi-tenant Azure AD endpoints (`/common/`). This allows enterprise customers with their own Azure AD app registrations to override the endpoints.

#### `_get_authorize_uri(from_url, service, scope, redirect_uri)`

Constructs the Microsoft OAuth2 authorization URL.

```python
@api.model
def _get_authorize_uri(self, from_url, service, scope, redirect_uri):
    state = {
        'd': self.env.cr.dbname,
        's': service,
        'f': from_url,
        'u': self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
    }
    encoded_params = urls.url_encode({
        'response_type': 'code',
        'client_id': self._get_microsoft_client_id(service),
        'state': json.dumps(state),
        'scope': scope,
        'redirect_uri': redirect_uri,
        'access_type': 'offline'
    })
    return "%s?%s" % (self._get_auth_endpoint(), encoded_params)
```

**State object:**
```json
{
    "d": "database_name",
    "s": "service_name",
    "f": "return_url",
    "u": "database_uuid"
}
```

The state encodes the database name, service, return URL, and database UUID for security validation on callback.

#### `_get_microsoft_tokens(authorize_code, service, redirect_uri)`

Exchanges an authorization code for access + refresh tokens.

```python
@api.model
def _get_microsoft_tokens(self, authorize_code, service, redirect_uri):
    ICP_sudo = self.env['ir.config_parameter'].sudo()
    scope = self._get_calendar_scope()
    headers = {"content-type": "application/x-www-form-urlencoded"}
    data = {
        'code': authorize_code,
        'client_id': self._get_microsoft_client_id(service),
        'client_secret': _get_microsoft_client_secret(ICP_sudo, service),
        'grant_type': 'authorization_code',
        'scope': scope,
        'redirect_uri': redirect_uri
    }
    dummy, response, dummy = self._do_request(
        self._get_token_endpoint(), params=data, headers=headers, method='POST', preuri=''
    )
    return response.get('access_token'), response.get('refresh_token'), response.get('expires_in')
```

**Returns:** `(access_token, refresh_token, expires_in)` tuple.

**Note:** Unlike Google's token endpoint, Microsoft's token endpoint is included in `preuri=''` so the request goes directly to `login.microsoftonline.com`. The `_do_request` method's default `preuri` is `DEFAULT_MICROSOFT_GRAPH_ENDPOINT`, which is used for actual MS Graph API calls.

#### `_refresh_microsoft_token(service, rtoken)`

```python
@api.model
def _refresh_microsoft_token(self, service, rtoken):
    ICP_sudo = self.env['ir.config_parameter'].sudo()
    headers = {"content-type": "application/x-www-form-urlencoded"}
    data = {
        'client_id': self._get_microsoft_client_id(service),
        'client_secret': _get_microsoft_client_secret(ICP_sudo, service),
        'grant_type': 'refresh_token',
        'refresh_token': rtoken,
    }
    dummy, response, dummy = self._do_request(
        DEFAULT_MICROSOFT_TOKEN_ENDPOINT,
        params=data, headers=headers, method='POST', preuri=''
    )
    return response.get('access_token'), response.get('expires_in')
```

**Returns:** `(new_access_token, expires_in)`.

#### `generate_refresh_token(service, authorization_code)`

```python
@api.model
def generate_refresh_token(self, service, authorization_code):
    ICP_sudo = self.env['ir.config_parameter'].sudo()
    scope = self._get_calendar_scope()
    headers = {"content-type": "application/x-www-form-urlencoded"}
    data = {
        'client_id': self._get_microsoft_client_id(service),
        'redirect_uri': ICP_sudo.get_param('microsoft_redirect_uri'),
        'client_secret': _get_microsoft_client_secret(ICP_sudo, service),
        'scope': scope,
        'grant_type': "refresh_token"
    }
    req = requests.post(self._get_token_endpoint(), data=data, headers=headers, timeout=TIMEOUT)
    req.raise_for_status()
    return req.json().get('refresh_token')
```

Note: This method uses `requests.post` directly (bypassing `_do_request`) and returns only the refresh token. This is a separate code path for regenerating refresh tokens.

#### `_do_request(uri, params=None, headers=None, method='POST', preuri=DEFAULT_MICROSOFT_GRAPH_ENDPOINT, timeout=TIMEOUT)`

Core HTTP executor for MS Graph API calls.

**Security:** Asserts target host is either `DEFAULT_MICROSOFT_TOKEN_ENDPOINT` or `DEFAULT_MICROSOFT_GRAPH_ENDPOINT`.

**Returns:** `(status_code, response_dict, ask_time)` tuple.

**Status code handling:**
- `204` / `404`: Returns `{}` as response (empty body, not raised)
- Other errors: logged and re-raised

**Default `preuri`:** `https://graph.microsoft.com` — all MS Graph API calls use this base URL.

---

## `_get_microsoft_client_secret(ICP, service)` — Module-Level Hook

```python
def _get_microsoft_client_secret(ICP_sudo, service):
    return ICP_sudo.get_param('microsoft_%s_client_secret' % service)
```

Mirrors the pattern from `google_account`. Allows downstream modules to override the function to inject custom credentials. Must only be called in request contexts, never returned in clear text.

---

## Model: `res.users` (Microsoft Extension)

**File:** `addons/microsoft_account/models/res_users.py`

### Fields Added

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `microsoft_calendar_rtoken` | `Char` | `base.group_system` | OAuth2 refresh token |
| `microsoft_calendar_token` | `Char` | `base.group_system` | OAuth2 access token |
| `microsoft_calendar_token_validity` | `Datetime` | `base.group_system` | When the access token expires |

> **Note:** Unlike `google_calendar` (which stores tokens in `res.users.settings`), `microsoft_account` stores Microsoft tokens **directly on `res.users`**. This is a design difference between the two integration base modules.

### `_set_microsoft_auth_tokens(access_token, refresh_token, ttl)`

```python
def _set_microsoft_auth_tokens(self, access_token, refresh_token, ttl):
    self.write({
        'microsoft_calendar_rtoken': refresh_token,
        'microsoft_calendar_token': access_token,
        'microsoft_calendar_token_validity': fields.Datetime.now() + timedelta(seconds=ttl) if ttl else False,
    })
```

Writes all three token fields in a single `write()` call.

---

## HTTP Controller: `MicrosoftAuth`

**File:** `addons/microsoft_account/controllers/main.py`

### Route: `/microsoft_account/authentication`

**Auth:** `public`

**Purpose:** OAuth2 callback for Microsoft identity platform. Mirrors the `GoogleAuth` controller pattern.

**Flow:**
1. Decode `state` JSON — extract `service` (`s`), return URL (`f`)
2. If `code` received: exchange for tokens via `_get_microsoft_tokens()` → write to `res.users` via `_set_microsoft_auth_tokens()` → redirect to return URL
3. If `error`: redirect to `return_url?error={error}`
4. Otherwise: redirect to `return_url?error=Unknown_error`

---

## Default Configuration Data

**File:** `addons/microsoft_account/data/microsoft_account_data.xml`

```xml
<record id="config_microsoft_redirect_uri" model="ir.config_parameter">
    <field name="key">microsoft_redirect_uri</field>
    <field name="value">urn:ietf:wg:oauth:2.0:oob</field>
</record>
```

The default `microsoft_redirect_uri` is `urn:ietf:wg:oauth:2.0:oob` (Out-Of-Band), a placeholder used in older OAuth2 flows. Enterprise deployments with custom Azure app registrations should override this in their configuration.

---

## ICP Configuration Parameters

| Key | Default | Purpose |
|-----|---------|---------|
| `microsoft_{service}_client_id` | — | Azure AD app registration client ID |
| `microsoft_{service}_client_secret` | — | Azure AD app registration client secret |
| `microsoft_redirect_uri` | `urn:ietf:wg:oauth:2.0:oob` | OAuth2 redirect URI (configurable) |
| `microsoft_account.auth_endpoint` | `https://login.microsoftonline.com/common/oauth2/v2.0/authorize` | Auth URL (rarely changed) |
| `microsoft_account.token_endpoint` | `https://login.microsoftonline.com/common/oauth2/v2.0/token` | Token URL (rarely changed) |

---

## L4: Google vs Microsoft OAuth2 Comparison

### Similarities

Both providers follow OAuth2 2.0 best practices:
- Authorization code flow (not implicit)
- Refresh token for background/offline access
- Access tokens are short-lived (typically 1 hour)
- State parameter for CSRF protection
- Redirect URI must match registered app configuration

### Key Differences

| Aspect | Google | Microsoft |
|--------|--------|-----------|
| Authorization URL | `accounts.google.com/o/oauth2/auth` | `login.microsoftonline.com/common/oauth2/v2.0/authorize` |
| Token endpoint | `accounts.google.com/o/oauth2/token` | `login.microsoftonline.com/common/oauth2/v2.0/token` |
| API base URL | `www.googleapis.com` | `graph.microsoft.com` |
| Token storage | `res.users.settings` (google_calendar) | `res.users` directly (microsoft_account) |
| Scope format | URL-based (`https://www.googleapis.com/auth/calendar`) | Space-separated string (`offline_access openid Calendars.ReadWrite`) |
| Endpoint config | Hardcoded | Configurable via ICP |
| Redirect URI default | Odoo callback URL | `urn:ietf:wg:oauth:2.0:oob` (OOB placeholder) |

### Scope Format Difference

Google scopes are full URLs: `https://www.googleapis.com/auth/calendar`

Microsoft scopes are short identifiers: `Calendars.ReadWrite`

The `offline_access` scope in Microsoft is equivalent to Google's `access_type=offline` parameter — both request a refresh token.

### Multi-Tenant Support

Microsoft's `/common/` endpoint in the default configuration supports both personal Microsoft accounts (Outlook.com, Hotmail) and Azure AD work/school accounts. Enterprise customers can configure their own tenant-specific endpoints via the `microsoft_account.auth_endpoint` and `microsoft_account.token_endpoint` ICP parameters.

---

## Related Models

| Model | Module | Role |
|-------|--------|------|
| `res.users` | `base` | Extended with microsoft_* token fields |
| `ir.config_parameter` | `base` | Stores client_id, client_secret, endpoints |
| `microsoft.service` | `microsoft_account` | OAuth2 + MS Graph API utilities |
| `microsoft.calendar.sync` | `microsoft_calendar` | Uses `microsoft.service` for Calendar API calls |
