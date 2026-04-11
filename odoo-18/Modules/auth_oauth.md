# auth_oauth — OAuth2 Provider Authentication

**Module:** `auth_oauth`
**Odoo Version:** 18
**Source:** `~/odoo/odoo18/odoo/addons/auth_oauth/`

---

## Overview

The `auth_oauth` module integrates OAuth2 authentication providers (Google, Facebook, custom OIDC providers) into Odoo's authentication system. It manages provider configuration, handles the OAuth2 authorization flow, validates tokens with providers, maps provider user IDs to Odoo users, and creates new users from OAuth data.

---

## Architecture

### Model Structure

```
auth.oauth.provider         # OAuth2 provider configuration
res.users                   # Extended with OAuth2 identity fields
```

### File Map

| File | Purpose |
|------|---------|
| `models/auth_oauth.py` | `auth.oauth.provider` model |
| `models/res_users.py` | User OAuth identity and authentication |
| `controllers/main.py` | OAuth2 web authentication controller |

---

## Core Models

### auth.oauth.provider

**`auth.oauth.provider`** stores the configuration for each OAuth2 identity provider.

**Inheritance:** `models.Model`
** `_name`: `auth.oauth.provider`
** `_description`: `"OAuth2 provider"`
** `_order`: `sequence, name`

#### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `name` | `Char` | Provider display name (e.g., "Google") |
| `client_id` | `Char` | OAuth2 Client ID (application identifier from the provider) |
| `auth_endpoint` | `Char` | Authorization endpoint URL. E.g., `https://accounts.google.com/o/oauth2/v2/auth` |
| `scope` | `Char` | OAuth2 scope. Default: `'openid profile email'` |
| `validation_endpoint` | `Char` | UserInfo/Token validation endpoint URL. E.g., `https://oauth2.googleapis.com/tokeninfo` |
| `data_endpoint` | `Char` | Optional additional data endpoint for fetching extended user attributes |
| `enabled` | `Boolean` | Whether this provider is active for login |
| `css_class` | `Char` | CSS class for the login button icon (default `fa fa-fw fa-sign-in text-primary`) |
| `body` | `Char` | Login button label text (required, translatable) |
| `sequence` | `Integer` | Display order (default `10`) |

#### Standard Provider Fields

The model itself stores generic OAuth2 fields. Provider-specific configuration (client secrets, etc.) would be stored in `ir.config_parameter` or a provider-specific module.

---

### res.users — OAuth Extension

**Model:** `res.users`
**Inheritance:** Extends `res.users`

#### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `oauth_provider_id` | `Many2one(auth.oauth.provider)` | OAuth provider this user is linked to |
| `oauth_uid` | `Char` | User ID from the OAuth provider (`sub` claim or equivalent) |
| `oauth_access_token` | `Char` | OAuth2 access token for this user (readonly, copy=False, prefetch=False) |

#### SQL Constraints

```python
('uniq_users_oauth_provider_oauth_uid', 'unique(oauth_provider_id, oauth_uid)',
 'OAuth UID must be unique per provider')
```

This constraint ensures each `(provider, uid)` pair maps to exactly one user.

---

## OAuth2 Authentication Flow

### Step 1 — Authorization Request

The web controller redirects the user to the provider's `auth_endpoint` with parameters:
- `client_id`
- `redirect_uri` (Odoo's callback URL)
- `scope`
- `state` (JSON containing `d`, `p` [provider id], `t` [token for csrf])

### Step 2 — Token Exchange & Validation

When the provider redirects back to Odoo's callback:

**`_auth_oauth_validate(provider, access_token)`**

Makes an HTTP request to the provider's `validation_endpoint`:

```python
def _auth_oauth_validate(self, provider, access_token):
    validation = self._auth_oauth_rpc(oauth_provider.validation_endpoint, access_token)
    # Optionally fetch additional data from data_endpoint
    if oauth_provider.data_endpoint:
        data = self._auth_oauth_rpc(oauth_provider.data_endpoint, access_token)
        validation.update(data)

    # Extract subject (user ID) — try multiple possible keys
    subject = next(filter(None, [
        validation.pop('sub'),      # standard OIDC
        validation.pop('id'),        # Google v1, Facebook
        validation.pop('user_id'),  # Google tokeninfo
    ]), None)

    if not subject:
        raise AccessDenied('Missing subject identity')

    validation['user_id'] = subject
    return validation
```

**`_auth_oauth_rpc(endpoint, access_token)`**

Makes the HTTP call to the provider:
```python
def _auth_oauth_rpc(self, endpoint, access_token):
    if config_param('auth_oauth.authorization_header'):
        # Use Bearer token in Authorization header
        response = requests.get(endpoint, headers={'Authorization': f'Bearer {access_token}'}, timeout=10)
    else:
        # Use query parameter
        response = requests.get(endpoint, params={'access_token': access_token}, timeout=10)

    if response.ok:
        return response.json()

    # Handle WWW-Authenticate challenge (e.g., token expired)
    auth_challenge = parse_auth(response.headers.get("WWW-Authenticate"))
    if auth_challenge and auth_challenge.type == 'bearer' and 'error' in auth_challenge:
        return dict(auth_challenge)

    return {'error': 'invalid_request'}
```

### Step 3 — User Signin/Signup

**`_auth_oauth_signin(provider, validation, params)`**

Attempts to authenticate and sign in:

```python
def _auth_oauth_signin(self, provider, validation, params):
    oauth_uid = validation['user_id']
    oauth_user = self.search([
        ("oauth_uid", "=", oauth_uid),
        ('oauth_provider_id', '=', provider)
    ])

    if not oauth_user:
        raise AccessDenied()  # No existing user → try signup

    oauth_user.write({'oauth_access_token': params['access_token']})
    return oauth_user.login
```

If `AccessDenied` is raised (no existing user) AND `no_user_creation` context is not set:
1. Parses the `state` parameter to extract the signup token
2. Calls `_generate_signup_values(provider, validation, params)` to build user vals
3. Calls `self.signup(values, token)` → creates the user (via `auth_signup`)
4. Returns the new user's login

**`_generate_signup_values(provider, validation, params)`**

Maps OAuth provider data to user fields:

```python
def _generate_signup_values(self, provider, validation, params):
    oauth_uid = validation['user_id']
    email = validation.get('email', 'provider_%s_user_%s' % (provider, oauth_uid))
    return {
        'name': validation.get('name', email),
        'login': email,
        'email': email,
        'oauth_provider_id': provider,
        'oauth_uid': oauth_uid,
        'oauth_access_token': params['access_token'],
        'active': True,
    }
```

### Step 4 — Entry Point

**`auth_oauth(provider, params)`**

The main auth method called by `ir_auth`: validates the token and returns user credentials:
```python
def auth_oauth(self, provider, params):
    validation = self._auth_oauth_validate(provider, access_token)
    login = self._auth_oauth_signin(provider, validation, params)
    return (dbname, login, access_token)
```

---

## OAuth Access Token in Sessions

**`_check_credentials(credential, env)`**

Overrides the standard credential check to also accept OAuth tokens:

```python
def _check_credentials(self, credential, env):
    try:
        return super()._check_credentials(credential, env)
    except AccessDenied:
        if not (credential['type'] == 'oauth_token' and credential['token']):
            raise  # Not an OAuth token → re-raise

        if env['interactive'] or user.active:
            # Check if the OAuth token matches this user
            res = self.sudo().search([
                ('id', '=', self.env.uid),
                ('oauth_access_token', '=', credential['token'])
            ])
            if res:
                return {'uid': self.env.user.id, 'auth_method': 'oauth', 'mfa': 'default'}
        raise
```

**`_get_session_token_fields()`**

Adds `oauth_access_token` to session token fields so the OAuth token can be used to maintain sessions.

---

## Private Fields

`oauth_access_token` is added to `USER_PRIVATE_FIELDS` in the base model:
```python
base.models.res_users.USER_PRIVATE_FIELDS.append('oauth_access_token')
```

This prevents the access token from being exposed in API responses.

---

## Key Design Decisions

1. **Multiple subject key support:** Providers use different keys for the user ID (`sub` in OIDC standard, `id` for Google v1/Facebook, `user_id` for Google's tokeninfo). The `next(filter(...))` pattern tries each in order, providing broad compatibility.

2. **`no_user_creation` context:** If the OAuth flow is being used purely for authentication (not registration), the caller can set `no_user_creation=True` to prevent user auto-creation and get `None` instead of raising `AccessDenied`.

3. **Token storage:** `oauth_access_token` is stored on the user record and updated on each login. This allows Odoo to recognize returning OAuth users and maintain session validity.

4. **Authorization header vs. query param:** The `_auth_oauth_rpc()` method supports both Bearer header and query parameter authentication modes, configurable via `auth_oauth.authorization_header` config parameter.

5. **Fail-open for data endpoint:** If the optional `data_endpoint` call fails, only the additional data is omitted — the core validation result is still used. This prevents a provider's extended data service outage from blocking all logins.

6. **Signup delegation to `auth_signup`:** When a new OAuth user is detected, the flow delegates to `self.signup()` which uses the `auth_signup` module's user creation logic. This means OAuth registration respects the B2B/B2C invitation scope configured in `auth_signup`.

---

## Notes

- The OAuth2 authorization flow is managed by the web controller (`controllers/main.py`), which constructs the authorization URL and handles the callback. The controller builds a `state` parameter containing `{d: db, p: provider_id, t: csrf_token}` for CSRF protection and routing.
- `parse_auth` is imported with a compatibility shim for older werkzeug versions that used `http.parse_www_authenticate_header` instead of the newer `datastructures.WWWAuthenticate.from_header`.
- The `oauth_access_token` is stored with `prefetch=False` to avoid loading it unnecessarily for all users — it is only fetched when specifically needed for session validation.
- Provider credentials (client_secret) are not stored in `auth.oauth.provider` — they are managed through `ir.config_parameter` or external configuration to avoid exposure in the database.
