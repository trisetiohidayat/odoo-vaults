# auth_oauth

OAuth2 Authentication module for Odoo 19.

> **Module:** `auth_oauth` | **Category:** Hidden/Tools | **License:** LGPL-3
> **Technical area:** Authentication & Identity | **Depends:** `base`, `web`, `base_setup`, `auth_signup`

---

## Module Overview

The `auth_oauth` module enables OAuth2-based Single Sign-On (SSO) in Odoo, allowing users to authenticate via external identity providers such as Google, Facebook, or any standards-compliant OAuth2 server. It integrates directly with Odoo's session management, user provisioning, and the `auth_signup` flow.

### What This Module Does

- Defines a configurable registry of OAuth2 providers (`auth.oauth.provider`)
- Handles the full OAuth2 authorization code flow from the login page
- Validates access tokens against the provider's `validation_endpoint`
- Creates new Odoo users automatically on first OAuth login (via `auth_signup`)
- Stores per-user OAuth identifiers and optionally short-lived access tokens
- Bridges `auth_signup` and `web` to render OAuth provider buttons on the login page
- Includes an `/auth_oauth/oea` endpoint for Odoo.com Account SSO (Odoo Enterprise to Odoo.sh/existing DB)

### What This Module Does NOT Do

- It does **not** act as an OAuth2 identity provider itself (no userinfo/authorization server)
- It does **not** handle refresh tokens; the access token stored is short-lived and not automatically renewed
- It does **not** provide SAML support (see `auth_jwt` for JWT-based auth in Odoo 19+)
- It does **not** automatically provision users unless `auth_signup` is installed and enabled

### Dependency Chain

```
auth_oauth
  └── base         (ir.config_parameter, res.users, ir.model.access)
  └── web          (http.Controller routing, session)
  └── base_setup   (ResConfigSettings form)
  └── auth_signup  (SignupError, .signup(), do_signup(), user creation)
```

---

## auth.oauth.provider

**Model:** `auth.oauth.provider` | **Inherited by:** `mail.message` no inheritance

Registry of configured OAuth2 identity providers. Each record corresponds to one OAuth2 provider (e.g., Google, Odoo.com). The module ships three pre-configured providers: **Odoo.com Accounts**, **Facebook Graph**, and **Google OAuth2**. The Odoo.com provider is auto-enabled; Facebook and Google are present but disabled.

### Fields

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | Char | Yes | — | Display name of the provider, e.g., "Google OAuth2" |
| `client_id` | Char | No | — | Odoo's OAuth client identifier registered with the provider. For `provider_openerp`, auto-set to `database.uuid` on module init |
| `auth_endpoint` | Char | Yes | — | Provider's authorization endpoint URL. E.g., `https://accounts.google.com/o/oauth2/auth` |
| `scope` | Char | No | `openid profile email` | Space-separated OAuth2 scope string. Controls what user attributes the access token grants access to |
| `validation_endpoint` | Char | Yes | — | URL called to validate the access token and retrieve the user identity (`userinfo` endpoint). Required |
| `data_endpoint` | Char | No | — | Optional second endpoint called after `validation_endpoint` to fetch additional user data (e.g., Facebook's `me?fields=id,name,email` merges name/email separately from the `validation_endpoint` result) |
| `enabled` | Boolean | No | `False` | Controls whether this provider appears on the login page. Only enabled providers are listed by `list_providers()` |
| `css_class` | Char | No | `fa fa-fw fa-sign-in text-primary` | CSS classes applied to the provider's login button icon in the UI. Group-restricted to `base.group_no_one` (developer mode) |
| `body` | Char | Yes | — | Button label text shown on the login dialog. Supports translation (`translate=True`) |
| `sequence` | Integer | No | `10` | Controls display order in the provider list view |

### SQL Constraint

```python
_uniq_users_oauth_provider_oauth_uid = models.Constraint(
    'unique(oauth_provider_id, oauth_uid)',
    'OAuth UID must be unique per provider',
)
```

This is enforced at the `res.users` level (see below), not directly on `auth.oauth.provider`. It ensures that a given OAuth user ID is never duplicated under the same provider within the users table.

### Pre-configured Providers (data/auth_oauth_data.xml)

| ID | Name | `auth_endpoint` | `validation_endpoint` | Enabled |
|---|---|---|---|---|
| `provider_openerp` | Odoo.com Accounts | `https://accounts.odoo.com/oauth2/auth` | `https://accounts.odoo.com/oauth2/tokeninfo` | Yes (auto) |
| `provider_facebook` | Facebook Graph | `https://www.facebook.com/dialog/oauth` | `https://graph.facebook.com/me` + `data_endpoint` | No |
| `provider_google` | Google OAuth2 | `https://accounts.google.com/o/oauth2/auth` | `https://www.googleapis.com/oauth2/v3/userinfo` | No |

The `client_id` for `provider_openerp` is set dynamically at module init via `IrConfigParameter.init()`: it reads `database.uuid` from `ir.config_parameter` and writes it as `client_id`. This links the Odoo instance to its Odoo.com developer app.

### Access Control

`ir.model.access.csv` grants full `base.group_system` access to `model_auth_oauth_provider`. Only system administrators can create, edit, or delete providers. Normal users cannot access this model.

### UI Access Path

`Settings → Users → OAuth Providers` (menu item ID: `menu_oauth_providers`). This menu item is itself restricted to `base.group_no_one` (developer mode), so it is hidden from ordinary users.

---

## res.users Extensions

**Model:** `res.users` | **Inheritance:** `_inherit = 'res.users'`

Standard Odoo user model extended with OAuth identity fields. All fields are stored on `res.users` itself (not a separate relation table).

### Fields

| Field | Type | Groups | Notes |
|---|---|---|---|
| `oauth_provider_id` | Many2one → `auth.oauth.provider` | — | Links the user record to their identity provider |
| `oauth_uid` | Char | — | The provider-assigned unique user ID (e.g., Google's "sub" claim). Set at registration time. `copy=False` — not copied when duplicating the user |
| `oauth_access_token` | Char (readonly) | `NO_ACCESS` (hidden from all) | Stores the current OAuth access token for session re-authentication. `prefetch=False` to avoid loading tokens in bulk. Never exposed via API or UI |
| `has_oauth_access_token` | Boolean (computed, readonly) | `base.group_erp_manager` | True if `oauth_access_token` is non-empty. The only OAuth token field readable by admin users |

### SQL Constraint

```python
_uniq_users_oauth_provider_oauth_uid = models.Constraint(
    'unique(oauth_provider_id, oauth_uid)',
    'OAuth UID must be unique per provider',
)
```

Enforced at the PostgreSQL level. Concurrent registrations for the same OAuth user will result in a unique violation error rather than a silent duplicate.

### Why `oauth_access_token` Is Hidden from All Users

The token field uses `groups=fields.NO_ACCESS`, which removes it from all access contexts including superuser. It is only ever accessed via `.sudo()` in internal methods. Storing the token enables `_check_credentials()` to re-authenticate an existing session without requiring the user to re-authorize in the browser — the token is sent as a Bearer credential to Odoo's own endpoint and matched server-side.

### `SELF_READABLE_FIELDS` Extension

```python
@property
def SELF_READABLE_FIELDS(self):
    return super().SELF_READABLE_FIELDS + ['has_oauth_access_token']
```

`has_oauth_access_token` is added to the self-readable fields list so users can see whether their account has an active OAuth token (for account security pages). The token value itself remains hidden.

### Computed Field: `_compute_has_oauth_access_token`

```python
@api.depends('oauth_access_token')
def _compute_has_oauth_access_token(self):
    for user in self:
        user.has_oauth_access_token = bool(user.sudo().oauth_access_token)
```

Uses `sudo()` internally because `oauth_access_token` is `NO_ACCESS`. The compute fires on write to `oauth_access_token` via `_auth_oauth_signin()`.

---

## Core Authentication Methods

### `auth_oauth(provider, params)`

**Signature:** `@api.model def auth_oauth(self, provider, params)`

**Entry point** for the entire OAuth2 flow, called from the `/auth_oauth/signin` controller. Accepts:
- `provider`: integer provider ID
- `params`: dict containing at minimum `access_token` (from the OAuth provider callback) and `state` (JSON-encoded state object)

**Workflow:**

1. Extracts `access_token` from `params`
2. Calls `_auth_oauth_validate(provider, access_token)` to get validation dict
3. Calls `_auth_oauth_signin(provider, validation, params)` to get user login string
4. Returns a 3-tuple: `(dbname, login, access_token)` — the controller uses this to establish the session

If `_auth_oauth_signin` returns `None` (which only happens via `no_user_creation` context), raises `AccessDenied`.

### `_auth_oauth_validate(provider, access_token)`

**Signature:** `@api.model def _auth_oauth_validate(self, provider, access_token)`

Validates the access token against the provider and extracts the user identity.

**Step 1 — Token validation RPC:**
Calls `_auth_oauth_rpc(oauth_provider.validation_endpoint, access_token)` which sends a GET request to the provider's userinfo endpoint. Uses either:
- Bearer Authorization header: `Authorization: Bearer <token>` — if `auth_oauth.authorization_header` ir.config_parameter is set
- Query parameter: `?access_token=<token>` — default

Response is parsed as JSON. If the response has a 401-style `WWW-Authenticate` header with an error, that error dict is returned instead.

**Step 2 — Additional data endpoint (optional):**
If `data_endpoint` is configured on the provider, a second RPC is made and results are merged into the validation dict. This pattern is used by Facebook to fetch email and name separately.

**Step 3 — Subject resolution:**
The "subject" (unique user identifier from the provider) is extracted from one of several possible keys, checked in priority order:

| Priority | Key | Provider |
|---|---|---|
| 1 | `sub` | Standard OIDC / OpenID Connect |
| 2 | `id` | Google v1 userinfo, Facebook OpenGraph |
| 3 | `user_id` | Google tokeninfo, Odoo tokeninfo |

The code iterates through these keys, pops non-null values, and returns the first match. If no subject is found, raises `AccessDenied(_('Missing subject identity'))`.

The resolved subject is stored back in `validation['user_id']` and used as `oauth_uid`.

**Performance note:** Each OAuth login triggers 1–2 HTTP requests to the identity provider (`validation_endpoint` and optionally `data_endpoint`). These are synchronous and blocking. Default timeout is 10 seconds per request. A slow or unreachable provider will cause a login timeout. Consider setting up connection monitoring for the configured endpoints.

### `_auth_oauth_signin(provider, validation, params)`

**Signature:** `@api.model def _auth_oauth_signin(self, provider, validation, params)`

Locates an existing user or creates a new one, then returns the user login.

**Existing user lookup:**
```python
oauth_user = self.search([
    ("oauth_uid", "=", oauth_uid),
    ('oauth_provider_id', '=', provider)
])
```

If found (and unique), writes the new `access_token` to the user record and returns `login`. If not found or if `no_user_creation` context is set, raises `AccessDenied`, which triggers the signup path.

**New user creation (signup path):**
When `AccessDenied` is caught and `no_user_creation` context is absent:
1. `state` is parsed from `params` to extract the signup `token` (if any)
2. `_generate_signup_values(provider, validation, params)` is called to build user values
3. `self.signup(values, token)` is called — delegates to `auth_signup` which handles password generation and invitation emails
4. Returns the new user's login

If `SignupError` or `UserError` is raised during signup (e.g., signup disabled, invitation expired), the original `AccessDenied` is re-raised, which redirects the user to the error page.

### `_generate_signup_values(provider, validation, params)`

```python
{
    'name': validation.get('name', email),
    'login': email,
    'email': email,
    'oauth_provider_id': provider,
    'oauth_uid': validation['user_id'],
    'oauth_access_token': params['access_token'],
    'active': True,
}
```

The email address is used as the login. If the provider does not return an email, a synthetic login is generated: `provider_<id>_user_<oauth_uid>@` — note the `@` is included but no domain, which can cause issues with some Odoo features that expect valid email format. The `name` falls back to the email if not present.

### `_auth_oauth_rpc(endpoint, access_token)`

```python
def _auth_oauth_rpc(self, endpoint, access_token):
    if self.env['ir.config_parameter'].sudo().get_param('auth_oauth.authorization_header'):
        response = requests.get(endpoint, headers={'Authorization': 'Bearer %s' % access_token}, timeout=10)
    else:
        response = requests.get(endpoint, params={'access_token': access_token}, timeout=10)
    if response.ok:
        return response.json()
    auth_challenge = parse_auth(response.headers.get("WWW-Authenticate"))
    if auth_challenge and auth_challenge.type == 'bearer' and 'error' in auth_challenge:
        return dict(auth_challenge)
    return {'error': 'invalid_request'}
```

Uses the `requests` library (not Odoo's internal HTTP client). The 10-second timeout guards against provider slow responses. The `WWW-Authenticate` header parsing handles OAuth2 error responses encoded in the HTTP 401 challenge — this is the standard way providers communicate errors. Compatible with both `datastructures.WWWAuthenticate.from_header` (Python 3.10+) and the legacy `http.parse_www_authenticate_header` (older versions).

### `_check_credentials(credential, env)`

**Override** on `res.users`. Enables OAuth token re-authentication within an existing Odoo session.

```python
def _check_credentials(self, credential, env):
    try:
        return super()._check_credentials(credential, env)
    except AccessDenied:
        if not (credential['type'] == 'oauth_token' and credential['token']):
            raise
        passwd_allowed = env['interactive'] or not self.env.user._rpc_api_keys_only()
        if passwd_allowed and self.env.user.active:
            res = self.sudo().search([
                ('id', '=', self.env.uid),
                ('oauth_access_token', '=', credential['token'])
            ])
            if res:
                return {
                    'uid': self.env.user.id,
                    'auth_method': 'oauth',
                    'mfa': 'default',
                }
        raise
```

This method is called during session authentication (see `authenticate()`). When a standard password/credential check fails:
1. Checks if the credential is an `oauth_token` type
2. Checks if password authentication is allowed (`interactive` sessions or non-API-key-only users)
3. Looks up the user by `id == uid` and matches the stored token
4. Returns auth info dict marking `auth_method='oauth'` and `mfa='default'`

**Security note:** The search is scoped to `id == self.env.uid`, so the token can only be used to re-authenticate the user who owns the token. An attacker cannot use a stolen token to hijack a different user's session.

### `_get_session_token_fields()`

```python
def _get_session_token_fields(self):
    return super()._get_session_token_fields() | {'oauth_access_token'}
```

Adds `oauth_access_token` to the set of fields that contribute to the session security hash. This ensures that if the stored token changes (e.g., user logs out and back in), existing sessions are invalidated.

### `remove_oauth_access_token()`

```python
def remove_oauth_access_token(self):
    user = self.env.user
    if not (user.has_group('base.group_erp_manager') or self == user):
        raise AccessError(...)
    self.sudo().oauth_access_token = False
```

Allows a user to revoke their own OAuth token, or allows an ERP manager to revoke any user's token. After revocation, `_compute_has_oauth_access_token` updates and the session will require re-authentication.

---

## OAuth2 Login Flow (Full Sequence)

```
User browser                         Odoo server                          Provider
    │                                     │                                     │
    │── GET /web/login ──────────────────▶│                                     │
    │◀─ Login page (OAuth buttons) ──────│                                     │
    │── Click "Sign in with Google" ─────▶│                                     │
    │── Redirect to Google auth_endpoint ▶│                                     │
    │◀─ User authenticates at Google ───│                                     │
    │── Authorization code to /auth_oauth/signin ◀─────────────────────────────│
    │                                     │── GET validation_endpoint?access_token ──▶│
    │                                     │◀─ {sub: "...", email: "...", name: "..."} ──│
    │                                     │                                     │
    │                                     │── Search res.users by oauth_uid     │
    │                                     │── (found) Write new oauth_access_token│
    │                                     │── commit()                           │
    │                                     │── session.authenticate()             │
    │◀─ Redirect to /web (or redirect) ──│                                     │
```

**Key steps in detail:**

1. **Login page** (`OAuthLogin.web_login`): Calls `list_providers()` which searches `auth.oauth.provider` for `enabled=True`. For each provider, it constructs the authorization URL with `response_type=token`, `client_id`, `redirect_uri` set to `{url_root}auth_oauth/signin`, and `scope`. The `state` parameter is a JSON object containing `d` (dbname), `p` (provider_id), and `r` (redirect URL). Optionally includes `t` (signup token).

2. **Authorization redirect** from the provider lands at `/auth_oauth/signin` with the access token in the URL fragment (handled by the `fragment_to_query_string` decorator which uses a JavaScript redirect to move the fragment to query params).

3. **Signin controller** (`OAuthController.signin`):
   - Parses `state` JSON to get `dbname`, `provider_id`
   - Calls `res.users.with_user(SUPERUSER_ID).auth_oauth(provider, kw)` which validates and locates/creates the user
   - Commits the transaction **before** calling `session.authenticate()` — this ensures the new user record is visible within the same database transaction
   - Computes the final redirect URL: explicit redirect param > action ID > menu ID > `/odoo` default
   - Redirects with `303 See Other`, disabling the location header auto-correction to prevent redirect loops

4. **Session establishment**: `request.session.authenticate()` is called with `credential = {'login': login, 'token': access_token, 'type': 'oauth_token'}`. This calls `_check_credentials()` which matches the token and establishes the session.

---

## Controllers

### OAuthLogin (extends AuthSignupHome)

Inherits from `web.auth_signup.AuthSignupHome` (which in turn extends `web.Home`). Intercepts `web_login` to inject OAuth providers into the QWeb context.

#### `list_providers()`

```python
def list_providers(self):
    try:
        providers = request.env['auth.oauth.provider'].sudo().search_read([('enabled', '=', True)])
    except Exception:
        providers = []
    for provider in providers:
        return_url = request.httprequest.url_root + 'auth_oauth/signin'
        state = self.get_state(provider)
        params = dict(
            response_type='token',       # implicit flow (token in URL fragment)
            client_id=provider['client_id'],
            redirect_uri=return_url,
            scope=provider['scope'],
            state=json.dumps(state),
        )
        provider['auth_link'] = "%s?%s" % (provider['auth_endpoint'], werkzeug.urls.url_encode(params))
    return providers
```

**Performance:** Uses `search_read` (direct SQL) rather than a normal `search()` + `read()` for efficiency. Runs as `sudo(SUPERUSER_ID)` because normal users cannot read the provider model.

**`response_type='token'` note:** Uses the OAuth2 implicit flow (`token` returned in URL fragment). This is less secure than the authorization code flow but avoids the need for a server-side code exchange step. For production deployments with Google or other major providers, the authorization code flow is recommended — this module could be extended to support `code` as `response_type`.

#### `get_state(provider)`

```python
def get_state(self, provider):
    redirect = request.params.get('redirect') or 'web'
    if not redirect.startswith(('//', 'http://', 'https://')):
        redirect = '%s%s' % (request.httprequest.url_root, redirect[1:] if redirect[0] == '/' else redirect)
    state = dict(
        d=request.session.db,
        p=provider['id'],
        r=werkzeug.urls.url_quote_plus(redirect),
    )
    token = request.params.get('token')
    if token:
        state['t'] = token
    return state
```

Builds the state object for the OAuth2 authorization request. Normalizes the `redirect` parameter to prevent open redirect vulnerabilities — external URLs starting with `http://` or `https://` are rejected.

#### `web_login()`

Extends `AuthSignupHome.web_login()`. After the parent response is rendered (QWeb check), injects `providers` into `response.qcontext`. If `oauth_error` is present in the query string, maps it to a human-readable message:
- `oauth_error=1`: "Sign up is not allowed on this database."
- `oauth_error=2`: "Access Denied" (generic exception)
- `oauth_error=3`: "You do not have access to this database or your invitation has expired."

#### `get_auth_signup_qcontext()`

Extends `AuthSignupHome.get_auth_signup_qcontext()` to add `providers` to the signup/reset-password QWeb context, so OAuth buttons also appear on those pages.

### OAuthController

#### `signin(**kw)`

Decorators: `@http.route('/auth_oauth/signin', type='http', auth='none', readonly=False)`

- `auth='none'`: No session required — the user has not been authenticated yet
- `readonly=False`: Database changes allowed (user creation)
- `@fragment_to_query_string`: Moves URL fragment (`#access_token=...`) to query parameters via JavaScript before processing

#### `oea(**kw)`

Decorator: `@http.route('/auth_oauth/oea', type='http', auth='none', readonly=False)`

Handles Odoo Enterprise Account (OEA) authentication — a special flow where Odoo.com authenticates users for Odoo.sh or existing Odoo Enterprise deployments. Sets `no_user_creation` context to prevent auto-provisioning of users not pre-invited.

---

## res.config.settings

**Model:** `res.config.settings` (TransientModel)

Provides a UI panel in **Settings → General Settings** to enable Google OAuth and enter the Google Client ID. The panel is only visible when `module_auth_oauth` is installed.

### Fields

| Field | Type | Notes |
|---|---|---|
| `auth_oauth_google_enabled` | Boolean | Mirrors `auth.oauth.provider` enabled state for the Google provider |
| `auth_oauth_google_client_id` | Char | Mirrors `client_id` on the Google provider |
| `server_uri_google` | Char (computed) | Displays the callback URI: `{web.base.url}/auth_oauth/signin` — user must register this as an authorized redirect URI in the Google Cloud Console |

### `get_values()` / `set_values()`

Reads from / writes to `auth.oauth.provider` records via `env.ref()`:
```python
google_provider = self.env.ref('auth_oauth.provider_google', False)
```

If the Google provider record is missing (e.g., data file not loaded), these methods gracefully no-op. The Google provider is created by `data/auth_oauth_data.xml` with `noupdate="1"`, so it persists across upgrades.

---

## ir.config_parameter Integration

### `IrConfigParameter.init(force=False)`

Overrides `ir.config_parameter.init()` to initialize the Odoo.com provider's `client_id` to the database UUID on every module upgrade (when `force=True`):

```python
oauth_oe = self.env.ref('auth_oauth.provider_openerp', raise_if_not_found=False)
if not oauth_oe:
    return
dbuuid = self.sudo().get_param('database.uuid')
oauth_oe.write({'client_id': dbuuid})
```

This ensures that `provider_openerp.client_id` always matches the current database's UUID. It runs during module install/update when `force=True`.

---

## Security Considerations

### Token Storage

The OAuth access token is stored in plaintext in `res.users.oauth_access_token`. This token grants access to the user's data at the OAuth provider. Implications:
- **Database-level exposure**: Anyone with direct DB access can read the token
- **Session hijacking**: If the token is compromised, an attacker with DB access could establish a valid Odoo session
- **Mitigation**: `oauth_access_token` has `NO_ACCESS` (not readable via ORM), and `_check_credentials` scopes lookups to the session owner (`id == self.env.uid`)

### CSRF / State Parameter

The `state` parameter is JSON-encoded and includes the database name, provider ID, and intended redirect URL. The controller verifies `dbname` matches `request.session.db`. The redirect URL is normalized to reject absolute external URLs.

### User Provisioning

Users can self-register via OAuth if `auth_signup` is enabled. If `auth_signup` is disabled and `no_user_creation` context is not set, the signup attempt raises `SignupError`, which redirects to the error page.

### SQL Constraint Uniqueness

The constraint `unique(oauth_provider_id, oauth_uid)` at the database level prevents duplicate OAuth users per provider. This is enforced by PostgreSQL, not Odoo's ORM — concurrent registrations for the same provider would fail with a unique violation.

---

## Odoo 18 → 19 Changes

### New in Odoo 19

- **`has_oauth_access_token`** computed field and corresponding `SELF_READABLE_FIELDS` addition — lets users see if their account has an active OAuth token
- **`remove_oauth_access_token()`** method — allows self-service token revocation
- **`_get_session_token_fields()`** override — includes `oauth_access_token` in session security hash, invalidating sessions on token change
- **`data_endpoint`** field on `auth.oauth.provider` — enables a separate data-fetch step (used by Facebook to augment the validation response with email/name)
- **`body`** field (translated button label) — supports i18n of the login button text
- **`css_class`** field — enables custom styling of provider icons

### Removed / Deprecated

- No direct removal of prior auth_oauth features in Odoo 19. The module is largely stable. The main architectural change is the addition of per-user token management and the data_endpoint pattern.

---

## Edge Cases

### Provider Does Not Return Email

If the OAuth provider does not return an `email` field, `_generate_signup_values` generates a synthetic email: `provider_<id>_user_<oauth_uid>@`. This is technically invalid (no `@domain`) and may cause issues with:
- Email sending (Odoo requires valid email format for `mail.template` rendering)
- `login` field uniqueness if the same user re-registers from different providers

### Multiple Providers with Same Email

If the same email address is returned by two different OAuth providers (e.g., Google and Facebook both return `user@example.com`), two separate user records are created — one per provider. This is because `login` (set to email) is only unique-per-provider for the `oauth_uid` constraint, not across providers. Users would need to manually merge accounts.

### Token Expiry

The stored `oauth_access_token` is not refreshed automatically. When the token expires at the provider, subsequent `_check_credentials` calls will fail (the provider's RPC returns an error), and the user must re-authenticate via the OAuth flow. There is no refresh token management.

### Database UUID Collision (provider_openerp)

If a database UUID is changed manually in `ir.config_parameter`, the `provider_openerp.client_id` does not automatically update. Running `IrConfigParameter.init(force=True)` via module upgrade resyncs it.

### Odoo.com Provider Disabled

If `provider_openerp` is manually disabled, the `/auth_oauth/oea` endpoint will fail the `env.ref()` lookup and redirect to `/web?db=<name>` with a 303. This is a graceful degradation — the user is redirected to standard login.

### Concurrent Registration

Two simultaneous OAuth logins from the same provider for a first-time user could theoretically result in a unique constraint violation if `_generate_signup_values` generates identical values and `signup()` is called concurrently. PostgreSQL's unique constraint catches this, but the second user would see an error rather than being merged with the first.

---

## Related Models and Integration Points

| Related Model | Integration | Direction |
|---|---|---|
| `res.users` | `_inherit`, stores OAuth fields | Extended |
| `auth.oauth.provider` | Defines providers, used by controllers | Core |
| `res.config.settings` | Google OAuth config panel | UI settings |
| `ir.config_parameter` | `auth_oauth.authorization_header` flag; `database.uuid` for openerp client_id | Config |
| `auth_signup` | User creation via `.signup()`; `SignupError` handling; `AuthSignupHome` inheritance | Cooperative |
| `web` | Session via `request.session.authenticate()`; `web.Home` base controller | Session |
| `base` | `base.group_no_one`, `base.group_system`, `base.group_erp_manager` | Permissions |

### Configuration Parameter: `auth_oauth.authorization_header`

If set to `'True'`, the module uses the `Authorization: Bearer <token>` header instead of the `?access_token=` query parameter for provider RPC calls. Some OAuth providers require one or the other. Google prefers the Authorization header; some older providers only support query params.

---

## File Inventory

```
auth_oauth/
├── __init__.py                        # Imports controllers + models
├── __manifest__.py                     # name, category, depends, data, assets
├── controllers/
│   ├── __init__.py                    # Imports main
│   └── main.py                        # OAuthLogin, OAuthController
├── models/
│   ├── __init__.py                    # Imports auth_oauth, res_config_settings,
│   │                                   # ir_config_parameter, res_users
│   ├── auth_oauth.py                  # AuthOauthProvider (provider config)
│   ├── ir_config_parameter.py         # Odoo.com client_id auto-init
│   ├── res_config_settings.py         # Google OAuth settings panel
│   └── res_users.py                   # res.users OAuth fields + auth methods
├── data/
│   └── auth_oauth_data.xml           # Pre-configured providers (Odoo, Facebook, Google)
├── views/
│   ├── auth_oauth_views.xml          # Form, list, action, menu for providers
│   ├── auth_oauth_templates.xml      # QWeb template extension (adds providers to auth_btns)
│   └── res_config_settings_views.xml # Google OAuth settings in General Settings
├── security/
│   └── ir.model.access.csv           # base.group_system full access to provider model
└── static/
    └── src/scss/auth_oauth.scss      # CSS styles for provider icons
```

---

## Tags

#odoo #odoo19 #modules #auth_oauth #oauth2 #sso #authentication
