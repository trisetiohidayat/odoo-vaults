---
tags: [odoo, odoo17, module, auth, oauth, sso, identity]
research_depth: medium
---

# Auth OAuth Module — Deep Reference

**Source:** `addons/auth_oauth/models/`

## Overview

OAuth2 single-sign-on integration. Allows users to log in with external identity providers (Google, GitHub, Azure AD, etc.) using the OAuth 2.0 authorization code flow. The module stores provider configuration and maps OAuth identity to Odoo user records.

## Key Models

### auth.oauth.provider — Provider Configuration

**File:** `auth_oauth.py`

Stores the configuration for each OAuth2 identity provider.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required) | Display name: "Google", "GitHub", "Azure AD" |
| `client_id` | Char | Our OAuth client ID (application identifier) |
| `auth_endpoint` | Char (required) | Authorization URL (`/authorize` endpoint) |
| `scope` | Char | OAuth scopes, default: `openid profile email` |
| `validation_endpoint` | Char (required) | UserInfo / token introspection URL |
| `data_endpoint` | Char | Optional endpoint for extended user data |
| `enabled` | Boolean | Whether this provider is active |
| `css_class` | Char | CSS class for the login button icon |
| `body` | Char (required) | Button label text (translatable) |
| `sequence` | Integer | Display order on login page |

**Note on `auth_endpoint` vs `validation_endpoint`:**
- `auth_endpoint` — used by the Odoo web flow to redirect the browser to the provider
- `validation_endpoint` — called server-to-server to validate the access token and retrieve user info

### res.users — OAuth Extension

**File:** `res_users.py`

Extends `res.users` with three fields:

| Field | Type | Description |
|-------|------|-------------|
| `oauth_provider_id` | Many2one → `auth.oauth.provider` | The identity provider |
| `oauth_uid` | Char | User ID from the provider (unique per provider) |
| `oauth_access_token` | Char (readonly, copy=False) | Current access token |

**SQL Constraint:** `unique(oauth_provider_id, oauth_uid)` — a user cannot have two records for the same OAuth provider.

## OAuth Login Flow

### 1. User clicks OAuth button

The controller (`auth_oauth.controllers.main.AuthOAuthController`) redirects the browser to `auth_endpoint` with parameters:
```
client_id, redirect_uri, state, scope, response_type=code
```

The `state` parameter includes a cryptographically random token (`t`) to prevent CSRF.

### 2. Provider redirects back with authorization code

The provider redirects to Odoo's callback URL:
```
/auth_oauth/signin?code=xxx&state=...
```

### 3. Server-side token exchange

`ResUsers.auth_oauth(provider, params)` is called:
1. Extract `access_token` from `params`
2. Call `_auth_oauth_validate(provider, access_token)`:
   - `GET validation_endpoint?access_token=...` (or `Authorization: Bearer ...` header if configured)
   - Returns user info JSON
   - If `data_endpoint` is configured, fetch additional data
   - Extract `subject` key — tries `sub` (standard), `id` (Google v1, Facebook), `user_id` (Google tokeninfo), in that order
   - Raises `AccessDenied` if no subject found
3. Call `_auth_oauth_signin(provider, validation, params)`:
   - Search for existing user: `oauth_uid = validation['user_id']` AND `oauth_provider_id = provider`
   - If found: update `oauth_access_token` and return `login`
   - If not found and `no_user_creation` context: return `None`
   - Otherwise: create new user via `_generate_signup_values()` → `self.signup(values, token)`

### 4. `_generate_signup_values`

Creates a new `res.users` record from OAuth data:
```python
{
    'name': validation.get('name', email),
    'login': email,
    'email': email,
    'oauth_provider_id': provider,
    'oauth_uid': oauth_uid,
    'oauth_access_token': params['access_token'],
    'active': True,
}
```

Falls back to `'provider_{id}_user_{uid}@oauth.odoo'` if no email in token.

### 5. Password fallback

`_check_credentials()` in `res_users.py` falls back to OAuth when password auth fails:
```python
# If password fails, check OAuth access token
if self.env.user.active:
    res = self.sudo().search([
        ('id', '=', self.env.uid),
        ('oauth_access_token', '=', password)
    ])
    if res:
        return  # auth succeeds
```

This allows using the OAuth access token as a session password for API access.

## Authorization Header Mode

A config parameter `auth_oauth.authorization_header` (set via System → Parameters) changes the token transport from query string to header:
```python
# Default (query param):
response = requests.get(endpoint, params={'access_token': access_token})

# With header mode:
response = requests.get(endpoint, headers={'Authorization': 'Bearer %s' % access_token})
```

Some OAuth providers (e.g., Azure AD) require the header approach.

## Private Fields

`oauth_access_token` is added to `USER_PRIVATE_FIELDS` (in `base.addons.auth_signup.models.res_users`) so it is excluded from `_read` and `_convert_to_write` publicly — prevents leaking tokens via API.

## Password-less Authentication

Since the user's password may be unknown (they registered via OAuth), the `_check_credentials` override allows the OAuth access token to act as the password for XML-RPC / JSON-RPC calls.

## See Also

- [Modules/auth_totp](odoo-18/Modules/auth_totp.md) — two-factor authentication
- [Modules/auth_signup](odoo-18/Modules/auth_signup.md) — user registration and signup
- [Modules/base](odoo-18/Modules/base.md) — user model foundation