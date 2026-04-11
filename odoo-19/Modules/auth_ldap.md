# Authentication via LDAP (`auth_ldap`)

**Category:** Hidden/Tools
**Depends:** `base`, `base_setup`
**External dependencies:** `python-ldap` (Python library), `python3-ldap` (APT package)
**Author:** Odoo S.A.
**License:** LGPL-3
**Odoo 18→19 changes:** Minor — `no_reset_password=True` context on user creation was added to prevent spurious password-reset emails on first LDAP login (confirmed in Odoo 18 as well, but was emphasized in the context pattern). No structural changes to the model or auth flow in Odoo 19.

---

## Overview

Enables LDAP and Active Directory-based authentication for Odoo. Users log in with their corporate directory credentials; Odoo never stores the LDAP password. Supports multiple LDAP servers per company, per-server sequencing, automatic user creation on first login, and attribute mapping (name, email, phone) from LDAP entries.

**Authentication is always two-phase:** Odoo's local `res_users` table is tried first; only if local auth raises `AccessDenied` does the LDAP chain engage. This design coexists gracefully with local users (e.g., the Administrator account) and mixed environments.

---

## Module Architecture

```
auth_ldap/
├── models/
│   ├── res_company.py        # res.company: adds ldaps O2M
│   ├── res_company_ldap.py   # res.company.ldap: core LDAP model
│   ├── res_users.py          # res.users: auth overrides
│   └── res_config_settings.py # One2many relay to ldaps
├── views/
│   ├── ldap_installer_views.xml      # Standalone LDAP config form/tree/action
│   └── res_config_settings_views.xml # Inherits base_setup settings page
└── security/
    └── ir.model.access.csv   # base.group_system CRUD on res.company.ldap
```

---

## Model: `res.company.ldap`

Core model. One record per LDAP server per company.

### Fields

| Field | Type | Default | Required | Notes |
|---|---|---|---|---|
| `company` | `Many2one(res.company)` | — | Yes | Owning company; `ondelete='cascade'` |
| `sequence` | `Integer` | `10` | No | Lower values tried first; controls iteration order |
| `ldap_server` | `Char` | `'127.0.0.1'` | Yes | IP or hostname |
| `ldap_server_port` | `Integer` | `389` | Yes | Standard LDAP port |
| `ldap_binddn` | `Char` | `False` | No | DN of service account used to query the directory. Empty = anonymous bind |
| `ldap_password` | `Char` | `False` | No | Password for service account; stored in plain text in `res_company_ldap` table |
| `ldap_filter` | `Char` | — | Yes | LDAP search filter; must contain at least one `%s` placeholder substituted with the login name |
| `ldap_base` | `Char` | — | Yes | Base DN of the search scope (subtree) |
| `ldap_tls` | `Boolean` | `False` | No | Requests STARTTLS on the connection; does NOT use `ldaps://` |
| `user` | `Many2one(res.users)` | `False` | No | Template user whose groups and settings are copied to newly created LDAP users |
| `create_user` | `Boolean` | `True` | No | If True, auto-create a local `res.users` record on first successful LDAP auth |

### Field Details

**`ldap_filter`** — The arbitrary LDAP filter string is the most critical configuration. The `%s` placeholder(s) are substituted with the raw login string via `ldap.filter.filter_format()`. Multiple `%s` placeholders are supported (e.g., `(|(mail=%s)(uid=%s))`), so the same placeholder is repeated. Odoo logs a warning if no `%s` is found, but still executes the filter.

The filter must return exactly one LDAP entry; zero results or multiple results both cause authentication to fail silently (returns `False`). This is intentional — ambiguous results are not auto-resolved.

**`ldap_binddn` / `ldap_password`** — These credentials belong to a **service account**, not the logging-in user. They are used only for the initial search query to locate the user's DN. The user's own DN is then used for the bind attempt. Anonymous binding is supported (leave both empty) for LDAP servers that permit it, but this is only for the service query — the user's own password is always required for authentication.

**`ldap_tls`** — Uses STARTTLS (opportunistic TLS on port 389), not LDAPS (SSL on port 636). Requires the LDAP server to have STARTTLS enabled. Certificate validation is delegated to the system CA bundle. This option cannot be used simultaneously with `ldaps://` — the connection always uses `ldap://` and calls `start_tls_s()` conditionally.

**`create_user`** — When `True`, the `_get_or_create_user` method creates a new `res.users` record on first LDAP login. The new user is created with `login=login.lower().strip()` (lowercased and trimmed). If `user` (template user) is set, the template's record is `.copy()`ed; otherwise a bare record is `.create()`d. In both paths, `active=True` is explicitly set and the `no_reset_password=True` context prevents Odoo from sending a welcome password email (LDAP users have no local password to reset to).

**`user` (template user)** — The template user is expected to have appropriate groups pre-assigned (e.g., `base.group_user`, `base.group_portal`, or custom groups). If the template has a non-empty `password` field, that password is copied to new users, creating a **master password vulnerability** — documented explicitly in the README. The recommended pattern: set up a template user with only group memberships and a blank password.

### Security: `ldap_password` Storage

The service account password is stored in plain text in the `res_company_ldap` table. Access to this record is restricted to `base.group_system` (see `ir.model.access.csv`). In production, use a minimally privileged LDAP service account that can only search, not modify entries.

### Config Parameter: `auth_ldap.disable_chase_ref`

Set via `ir.config_parameter` key `auth_ldap.disable_chase_ref` (default `'True'`). Controls the `ldap.OPT_REFERRALS` option. When `True`, referrals are disabled with `connection.set_option(ldap.OPT_REFERRALS, ldap.OPT_OFF)`. When `False`, the LDAP client will chase referrals automatically — this can expose the server to SSRF-like behavior where Odoo makes outbound connections to URLs embedded in LDAP referral responses. Always keep this at the default `'True'` unless referrals are explicitly required.

---

## Methods on `res.company.ldap`

### `_get_ldap_dicts()` — Class/recordset method

```
def _get_ldap_dicts(self) -> list[dict]
```

Retrieves all `res.company.ldap` records from the database and returns them as a list of plain dictionaries. Always executed as `sudo()` to bypass record rules (LDAP configs are privileged). The returned dicts contain only the safe subset of fields needed for authentication: `id`, `company`, `ldap_server`, `ldap_server_port`, `ldap_binddn`, `ldap_password`, `ldap_filter`, `ldap_base`, `user`, `create_user`, `ldap_tls`. Ordered by `sequence` ASC.

This is the single entry point for all LDAP config access throughout the module.

### `_connect(conf) -> LDAPWrapper`

Opens an LDAP connection. Constructs URI as `ldap://%s:%d` (always LDAP, never LDAPS; TLS is handled via STARTTLS). The `LDAPWrapper` class wraps the raw `ldap.initialize()` object and only exposes four methods: `passwd_s`, `search_st`, `simple_bind_s`, `unbind`. This is a deliberate API limitation — it prevents code from accidentally calling other `ldap` module methods.

Key behaviors:
- `ldap.OPT_REFERRALS` set to `OPT_OFF` when `auth_ldap.disable_chase_ref` is `True` (default).
- If `conf['ldap_tls']` is `True`, calls `connection.start_tls_s()` after initialization.
- Returns a `LDAPWrapper` instance (not the raw connection object).

### `_get_entry(conf, login) -> (dn: str|False, entry: dict|False)`

Locates the user's DN in the LDAP directory. Steps:
1. Formats the filter using `ldap.filter.filter_format(filter_tmpl, [login] * placeholders)`.
2. Calls `_query(conf, formatted_filter)` to execute the search.
3. Filters out entries with empty DNs (DN-less results can occur with some LDAP configurations).
4. Returns `(dn, entry)` if exactly one result; `(False, False)` otherwise.

**Edge case:** Zero results means the user does not exist in LDAP. Multiple results (same login resolving to multiple DNs) also returns `(False, False)`. Both cases silently reject the login — no differentiation for security reasons.

### `_authenticate(conf, login, password) -> ldap_entry|False`

Primary authentication method. Implements LDAP simple bind authentication:
1. **Rejects empty passwords** explicitly before any network call (per RFC 4513 §6.3.1 "unauthenticated authentication" prevention).
2. Calls `_get_entry(conf, login)` to locate the user's DN.
3. Opens a new connection as the **user** (not the service account) with `simple_bind_s(dn, password)`.
4. Returns the LDAP entry dict on success; `False` on `INVALID_CREDENTIALS` or any `LDAPError`.

This method is called in two contexts: during `_login()` (new session) and during `_check_credentials()` (password re-verification mid-session).

### `_query(conf, filter, retrieve_attributes=None) -> list[(dn, attrs)]`

Executes an LDAP search as the **service account** (binddn + password, or anonymously). Scope is `SCOPE_SUBTREE`. Timeout is 60 seconds. The service bind supports all three LDAP simple auth modes: authenticated bind, anonymous bind, and unauthenticated authentication (documented in RFC 4513 §5.1). Results are returned as a list of `(dn, {attr: [bytes_values]})` tuples via `search_st()` (the `_st` variant enables the timeout).

### `_map_ldap_attributes(conf, login, ldap_entry) -> dict`

Maps LDAP attributes to Odoo `res.users` field values for new user creation:
- `'name'`: from `ldap_entry[1]['cn'][0]` (bytes decoded via `.decode()` implicitly through list indexing; Odoo stores the raw bytes from LDAP).
- `'login'`: lowercased and stripped login string.
- `'company_id'`: `conf['company'][0]` (the company record's integer ID from the Many2one).
- `'email'`: set to `login` if `login` matches the single email regex (i.e., if the user logs in with their email address).

The `cn` attribute is the only mapped attribute; `mail`, `telephoneNumber`, etc. are not automatically mapped. Custom attribute mapping requires overriding `_map_ldap_attributes` in a custom module.

### `_get_or_create_user(conf, login, ldap_entry) -> int`

Creates or retrieves the Odoo user for a successfully authenticated LDAP user:
1. Lowercases and strips the login: `login.lower().strip()`.
2. Queries `res_users` by `lower(login)`.
3. If the user exists and is **active**, returns their ID immediately.
4. If the user exists but is **inactive**, silently returns their ID — they can still log in (this is unusual; inactive records normally block login).
5. If no user exists and `conf['create_user']` is `True`: creates a new user via `.copy()` (if template set) or `.create()` (if no template), with `active=True`.
6. If no user exists and `conf['create_user']` is `False`: raises `AccessDenied`.

**Concurrency note:** The `SELECT` + `CREATE` pattern is not atomic in Odoo — between the `SELECT` and `CREATE`, another concurrent LDAP login for the same new user could also pass the `SELECT` and attempt to `CREATE`. The database `UNIQUE` constraint on `login` (lowercased) would cause one of the two inserts to fail with a unique violation. The failing process would then raise `AccessDenied` (no exception handling for unique constraint violations in this flow).

### `_change_password(conf, login, old_passwd, new_passwd) -> bool`

Attempts to change the LDAP password via the LDAP `passwd_s()` extended operation:
1. Locates the user's DN via `_get_entry()`.
2. Opens a connection as the user (`simple_bind_s(dn, old_passwd)`).
3. Calls `conn.passwd_s(dn, old_passwd, new_passwd)`.
4. Returns `True` on success; `False` on `INVALID_CREDENTIALS` (wrong old password) or `LDAPError`.

**Limitation:** Not all LDAP directories support `passwd_s()`. Active Directory, for example, uses a different mechanism (LDAP password modify extended operation or direct attribute modification with appropriate permissions). On failure, the method silently returns `False` and the caller's `change_password()` on `res.users` falls back to the standard Odoo password change.

### `test_ldap_connection()` -> action

UI action invoked from the LDAP configuration form. Tests connectivity using the current record's field values (not `_get_ldap_dicts`). Performs a simple bind as the configured service account (using `ldap_binddn`/`ldap_password`). Returns a `display_notification` action with `type: success|danger`, specific messages for `SERVER_DOWN`, `INVALID_CREDENTIALS`, `TIMEOUT`, and generic `LDAPError`. Does not test user authentication.

---

## Model: `res.users` (Extension)

### `_login(credential, user_agent_env) -> {'uid': int, 'auth_method': 'ldap', 'mfa': 'default'}`

Overrides `auth.codern.py`/`models.py`'s `_login`. Auth flow:

```
try:
    # Phase 1: standard Odoo local auth
    return super()._login(...)
except AccessDenied:
    # Phase 2: LDAP chain
    if user already exists in res_users (even with NULL password):
        raise  # re-raise AccessDenied, don't try LDAP

    for conf in Ldap._get_ldap_dicts():
        entry = Ldap._authenticate(conf, login, password)
        if entry:
            return {
                'uid': Ldap._get_or_create_user(conf, login, entry),
                'auth_method': 'ldap',
                'mfa': 'default',
            }
    raise  # no LDAP server succeeded
```

The `SELECT id FROM res_users WHERE lower(login)=%s` check before the LDAP loop is the critical distinction: if the login already maps to a local user record, LDAP is **never attempted**. This means:
- A local user with a non-matching password always fails (even if the same credentials work in LDAP).
- To move a local user to LDAP auth, their `password` field must be `NULL` (blank), which causes local auth to raise `AccessDenied`, triggering the LDAP phase.

The `auth_method: 'ldap'` and `mfa: 'default'` return values are used by Odoo's session management and MFA framework to record how the user authenticated.

### `_check_credentials(credential, env) -> {...}`

Called during session renewal or when Odoo needs to re-verify the user's password mid-session. Same two-phase pattern as `_login`, but:
- Only entered when the primary (Odoo) credential check fails with `AccessDenied`.
- `credential['type'] == 'password'` and `credential.get('password')` must both be true; API key or other credential types immediately re-raise.
- `env['interactive']` controls whether password auth is allowed in non-interactive (e.g., XML-RPC) contexts. When `False`, API key-only mode (`_rpc_api_keys_only()`) is enforced unless `interactive=True`.
- Returns the same dict as `_login` but for the existing user's ID (no creation step).

### `change_password(old_passwd, new_passwd) -> bool`

Iterates all LDAP configs via `_get_ldap_dicts()`. For each config, calls `_change_password()`. If any server successfully changes the password, `_set_empty_password()` is called to clear the local `password` field (which is `NULL` for LDAP users anyway), then returns `True`. Falls back to `super().change_password()` if no LDAP server is configured or all fail.

### `_set_empty_password()`

Direct SQL operation that sets `password=NULL` for the current user. Called after a successful LDAP password change to keep the local password field in sync (always `NULL` for LDAP users). Uses `flush_recordset()`/`invalidate_recordset()` around the `UPDATE` to maintain ORM cache consistency.

---

## Model: `res.company` (Extension)

```python
ldaps = fields.One2many('res.company.ldap', 'company', string='LDAP Parameters',
                        copy=True, groups="base.group_system")
```

`copy=True` means duplicating a company (via `copy()`) will also copy its LDAP server configurations. The `groups` attribute restricts UI visibility to `base.group_system`; programmatic access via ORM is unrestricted unless record rules are added.

---

## Model: `res.config.settings` (Extension)

```python
ldaps = fields.One2many(related='company_id.ldaps', string="LDAP Parameters", readonly=False)
```

A related One2many that mirrors `company_id.ldaps` into the Settings form. Because `readonly=False`, changes made in the Settings form are written back directly to the `res.company.ldap` records. The form is rendered within the context of the current user's active company.

---

## Views and Navigation

### Standalone LDAP Form (`res.company.ldap`)

Accessed via the **Settings → LDAP Server** button (added by `auth_ldap` to the `base_setup.res_config_settings_view_form`). The button triggers `action_ldap_installer` which opens the `res.company.ldap` form/list with full CRUD. The form includes a **Test Connection** button that invokes `test_ldap_connection()`.

Form sections:
- **Server Information**: `ldap_server`, `ldap_server_port`, `ldap_tls`
- **Login Information**: `ldap_binddn`, `ldap_password`
- **Process Parameter**: `ldap_base`, `ldap_filter`, `sequence`
- **User Information**: `create_user`, `user` (template)

### Settings Page Integration

The `res_config_settings_views.xml` inherits from `base_setup.res_config_settings_view_form`:
- Inherits inside `<setting id="module_auth_ldap">` to add a **LDAP Server** button.
- Replaces the `<div id="auth_ldap_warning">` (the "Save this page and come back here" notice) with an empty div — once LDAP is configured, the warning disappears.

---

## Security

### Access Control

`res.company.ldap` requires `base.group_system` for all operations (read, write, create, unlink). Regular users cannot view or edit LDAP server configurations.

### Passwords Never Stored Client-Side

LDAP user passwords are never written to `res_users.password`. The `res_users.password` field is always `NULL` for LDAP-authenticated users. This means:
- Odoo's own password strength policy does not apply to LDAP passwords.
- Password expiry policies come from the LDAP directory, not Odoo.
- `base.default` `res.users` `password` defaults are irrelevant for LDAP users.

### Service Account Password Storage

The LDAP service account password (`ldap_password`) is stored in plain text in `res_company_ldap`. Mitigations:
- Restrict `base.group_system` membership tightly.
- Use a dedicated LDAP service account with minimal read-only permissions.
- Consider `ldap_password` as a sensitive credential equivalent to a database password.

### Anonymous LDAP Binding

Supported (both `ldap_binddn` and `ldap_password` empty). This only affects the **service query bind** (step 2 of auth: locating the user's DN). The user's own authentication always requires their password. Anonymous service binding should only be used when the LDAP directory is configured to allow unauthenticated searches — unusual in production AD environments.

---

## Performance Considerations

### LDAP Query Timeout

`_query()` uses `search_st(..., timeout=60)` — the `_st` variant enforces a 60-second wall-clock timeout on the search operation. If the LDAP server is unresponsive, the connection hangs for up to 60 seconds before raising `ldap.TIMEOUT`. In high-latency or WAN-connected LDAP environments, consider this when diagnosing slow login issues.

### Sequential Server Iteration

`_login()` and `_check_credentials()` iterate through `_get_ldap_dicts()` sequentially, trying each server in `sequence` order until one succeeds. If a server is unreachable, every login attempt waits for its timeout before trying the next. Deployments with multiple LDAP servers should order them by expected load.

### `_get_ldap_dicts()` is Called Twice Per Auth Flow

Once in `_login()` and once in `_check_credentials()`. Each call performs a `sudo().search_read()` against the `res_company_ldap` table. This is a small, indexed table, but in high-concurrency scenarios with no request caching, it adds one SQL query per auth phase.

### Connection Lifecycle

Each LDAP operation (`_get_entry`, `_authenticate`, `_query`, `_change_password`, `test_ldap_connection`) opens its own connection, binds, performs the operation, unbinds, and discards the connection. There is no connection pooling. For high-volume deployments, consider implementing a `LDAPWrapper` connection pool as a customization.

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| Login matches local user record | LDAP is skipped; local auth always runs first |
| LDAP user exists but is inactive in Odoo | `_get_or_create_user` returns the inactive user's ID — they can still log in |
| LDAP filter returns 0 results | `_get_entry` returns `(False, False)`; `_authenticate` returns `False` |
| LDAP filter returns >1 result | `_get_entry` returns `(False, False)`; silently rejected |
| LDAP filter has no `%s` placeholder | Warning logged; filter still executed |
| Empty password passed | `_authenticate` returns `False` immediately (RFC 4513 compliance) |
| LDAP server unreachable | `ldap.SERVER_DOWN` raised; caught and returns `False` |
| STARTTLS fails (server不支持) | `ldap.LDAPError` raised; caught and returns `False` |
| LDAP password change not supported | `_change_password` returns `False`; falls back to Odoo local password change |
| Concurrent first login of same new user | Database unique constraint on `login` raises; one process gets `AccessDenied` |
| Login with uppercase/lowercase difference | Login is lowercased at `_get_or_create_user`; `lower(login)` used for DB lookup |
| Template user has a non-empty password | That password is copied to every new LDAP user — a documented security risk |

---

## Cross-Module Integration

| Module | Integration Point |
|---|---|
| `base` | `res.users` model extension; `res.company` model extension |
| `base_setup` | `module_auth_ldap` boolean field on `res.config.settings`; Settings page inherit |
| `auth_totp` | Compatible; LDAP users can use TOTP as second factor; `mfa: 'default'` signals to use standard MFA |
| `auth_oauth` | Coexists; OAuth and LDAP are independent auth methods tried in separate hooks |
| `auth_signup` | Disabled by default for LDAP users (no `password` field); signup flow requires local password |
| `res.users` (`base`) | Login uniqueness enforced at DB level; `login` is `unique` index, case-insensitive via `lower()` |

---

## Upgrade / Migration Notes (Odoo 18 → 19)

- The `no_reset_password=True` context on user creation was retained. This prevents the `mail` module from sending password reset emails to LDAP users who have no local password.
- The `auth_ldap.disable_chase_ref` config parameter was present in Odoo 18; the default remains `'True'`.
- No changes to the model schema or field definitions between Odoo 18 and 19.
- The `change_password` fallback to `super()` was present in Odoo 18; behavior unchanged.
- Test suite tagged `database_breaking` — LDAP tests are excluded from standard runs because they require a live LDAP server.
