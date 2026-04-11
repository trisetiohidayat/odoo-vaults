---
tags:
  - "#odoo"
  - "#odoo19"
  - "#orm"
  - "#modules"
  - "#security"
  - "#authentication"
---

# res.users

> **Module:** `base` | **File:** `odoo/addons/base/models/res_users.py` (1,733 lines)
> **Gamification Extension:** `odoo/addons/gamification/models/res_users.py` (371 lines)
> **Inherits from:** `res.partner` via delegation (`_inherits`)
> **Gamification Extension Inherits:** `res.users`

The `res.users` model is the central user account model in Odoo. Unlike earlier versions where `res.users` stored both partner data and user data, Odoo 19 uses **delegation inheritance**: `res.users` inherits from `res.partner`, storing partner-related fields (name, email, phone, avatar) on the `res.partner` record, while keeping user-specific data (login, password, groups, company) on the `res.users` record itself.

---

## Model Definition

```python
class ResUsers(models.Model):
    _name = 'res.users'
    _description = 'User'
    _inherits = {'res.partner': 'partner_id'}      # Delegation inheritance
    _order = 'name, login'
    _allow_sudo_commands = False
```

### Inheritance Model: Delegation (`_inherits`)

```python
_inherits = {'res.partner': 'partner_id'}
```

This means:
- Every `res.users` record has a mandatory `partner_id` Many2one pointing to a `res.partner`.
- The partner's fields (name, email, phone, image_* fields, etc.) are accessible directly on the user via field delegation. For example, `user.name` reads from `user.partner_id.name`.
- Deleting a `res.users` record cascades to its `res.partner` record.
- A separate `res.partner` record is created automatically when a user is created.

### `_allow_sudo_commands = False`

This security flag prevents the `sudo()` method from executing XML-RPC or JSON-RPC commands on behalf of the user unless the user already has `sudo` rights. This is a hardening measure against privilege escalation.

---

## All Fields

### Identity & Authentication

#### `partner_id`
```python
partner_id = fields.Many2one(
    'res.partner',
    required=True,
    ondelete='restrict',
    bypass_search_access=True,
    index=True,
    string='Related Partner',
    help='Partner-related data of the user'
)
```
- **Type:** Many2one to `res.partner`
- **Required:** `True`
- **Ondelete:** `'restrict'` - prevents deleting a partner that has an associated user
- **`bypass_search_access`:** `True` - allows searching users without requiring partner access rights
- **Purpose:** The anchor record storing the user's name, email, phone, and avatar images. All inherited fields are backed by this record.

#### `login`
```python
login = fields.Char(required=True, help="Used to log into the system")
```
- **Type:** Char
- **Required:** `True`
- **Constraint:** `_login_key` - UNIQUE constraint across the entire database
- **Purpose:** The username used during authentication. Must be unique system-wide.
- **Onchange behavior:** If the login matches an email pattern (`tools.single_email_re`), it auto-fills the `email` field.

#### `password`
```python
password = fields.Char(
    compute='_compute_password',
    inverse='_set_password',
    copy=False,
    help="Keep empty if you don't want the user to be able to connect on the system."
)
```
- **Type:** Char (stored hashed in the database)
- **Computed + Inverse:** This is a write-only field. It is never returned in plaintext.
- **`_compute_password`:** Always sets the value to `''` (empty string) when read - the actual hash is stored in the database column but this computed field hides it.
- **`_set_password`:** The inverse writes the hashed value. Uses `_crypt_context()` with `pbkdf2_sha512` to hash the plaintext password before storing.
- **`copy=False`:** Passwords are not copied when duplicating a user record.
- **Empty password:** An empty string password means the user cannot log in via password authentication. They may still authenticate via API key or other methods.

#### `new_password`
```python
new_password = fields.Char(
    string='Set Password',
    compute='_compute_password',
    inverse='_set_new_password',
    help="Specify a value only when creating a user or if you're changing the user's password..."
)
```
- **Type:** Char (write-only, like `password`)
- **Purpose:** Set a new password for another user. An administrator can set this without knowing the old password.
- **`_set_new_password`:** Validates that if `user == self.env.user` (changing own password via form), it raises a `UserError` forcing the user to use the dedicated change password wizard instead. For other users, it delegates to `_set_password`.

#### `api_key_ids`
```python
api_key_ids = fields.One2many(
    'res.users.apikeys',
    'user_id',
    string="API Keys"
)
```
- **Type:** One2many to `res.users.apikeys`
- **Purpose:** Stores API keys for programmatic authentication. See the API Keys section below.

### Status & Activity

#### `active`
```python
active = fields.Boolean(default=True)
```
- **Type:** Boolean
- **Default:** `True`
- **Purpose:** Soft-delete mechanism. Deactivating a user (setting `active=False`) prevents login and hides the user from most searches. The user's data is preserved.
- **Constraint:** Cannot deactivate the superuser (`id = 1`). Cannot deactivate yourself.
- **Write behavior:** When `active=True` is set on a user, `partner_id.action_unarchive()` is called to also unarchive the partner.

#### `active_partner`
```python
active_partner = fields.Boolean(
    related='partner_id.active',
    readonly=True,
    string="Partner is Active"
)
```
- **Type:** Boolean (related, readonly)
- **Purpose:** Reflects the partner's active state. Useful for checking if the partner record is archived independently.

#### `share`
```python
share = fields.Boolean(
    compute='_compute_share',
    compute_sudo=True,
    store=True,
    string='Share User'
)
```
- **Type:** Boolean (computed, stored)
- **`compute_sudo=True`:** Computation runs as superuser to determine share status accurately.
- **`_compute_share`:** Returns `False` if the user has `base.group_user` (internal employee group) in their `all_group_ids` (direct or implied). Returns `True` for portal and public users.
- **Purpose:** Distinguishes internal users (who have full access) from external/share users (portal, public) who have limited access.
- **Implication:** Users cannot simultaneously belong to mutually exclusive groups (portal vs. internal user vs. public). The `_check_disjoint_groups` constraint enforces this.

#### `login_date`
```python
login_date = fields.Datetime(
    related='log_ids.create_date',
    string='Latest Login',
    readonly=False
)
```
- **Type:** Datetime (related to `log_ids.create_date`)
- **Purpose:** Stores the timestamp of the user's most recent login. Retrieved via the `res.users.log` model's creation timestamp.
- **`readonly=False`:** Allows resetting or overriding in certain contexts.

#### `log_ids`
```python
log_ids = fields.One2many(
    'res.users.log',
    'create_uid',
    string='User log entries'
)
```
- **Type:** One2many to `res.users.log`
- **Purpose:** Historical record of login events. Each login creates a new `res.users.log` entry.
- **Garbage collection:** The `_gc_user_logs` autovacuum method deletes duplicate log entries, keeping only the most recent per user.

### Company & Multi-Company

#### `company_id`
```python
company_id = fields.Many2one(
    'res.company',
    string='Company',
    required=True,
    default=lambda self: self.env.company.id,
    context={'user_preference': True}
)
```
- **Type:** Many2one to `res.company`
- **Required:** `True`
- **Default:** The current user's default company (`self.env.company`).
- **`context={'user_preference': True}`:** When this context is set, searches for companies return only the user's allowed companies.
- **Purpose:** The user's currently active company. All business operations use this as the default company context.
- **Constraint:** Must be one of the companies in `company_ids`.

#### `company_ids`
```python
company_ids = fields.Many2many(
    'res.company',
    'res_company_users_rel',
    'user_id', 'cid',
    string='Companies',
    default=lambda self: self.env.company.ids
)
```
- **Type:** Many2many to `res.company`
- **Default:** All companies in the database (when a new user is created, they get access to all current companies).
- **Purpose:** The list of companies the user is allowed to work with. In multi-company environments, this controls which companies appear in the company switcher.
- **Constraint:** `company_id` must always be in `company_ids`. Enforced by `_check_user_company`.

#### `companies_count`
```python
companies_count = fields.Integer(
    compute='_compute_companies_count',
    string="Number of Companies"
)
```
- **Type:** Integer (computed, not stored)
- **`_compute_companies_count`:** Counts all active companies in the database (via sudo).

### Localization

#### `tz`
```python
# Inherited from res.partner via delegation
# tz = fields.Selection(..., related='partner_id.tz', ...)
```
- **Type:** Selection (list of IANA timezone identifiers)
- **Source:** Stored on `partner_id`
- **Purpose:** User's preferred timezone. Used to display datetimes in the user's local time.

#### `tz_offset`
```python
tz_offset = fields.Char(
    compute='_compute_tz_offset',
    string='Timezone offset'
)
```
- **Type:** Char (e.g., `'+0700'`)
- **Computed from:** The `tz` field value.
- **Purpose:** Display-friendly timezone offset string.

#### `lang`
```python
# Inherited from res.partner via delegation
# lang = fields.Selection(..., related='partner_id.lang', ...)
```
- **Type:** Selection (installed language codes)
- **Source:** Stored on `partner_id`
- **Purpose:** User's preferred language for UI display and email templates.

#### `email_domain_placeholder`
```python
email_domain_placeholder = fields.Char(
    compute="_compute_email_domain_placeholder"
)
```
- **Type:** Char (computed)
- **`_compute_email_domain_placeholder`:** Extracts the email domain from the current user's email and displays it as a placeholder hint when creating new users. E.g., if the admin's email is `admin@acme.com`, the placeholder becomes `e.g. email@acme.com`.

### Groups & Security

#### `group_ids`
```python
group_ids = fields.Many2many(
    'res.groups',
    'res_groups_users_rel',
    'uid', 'gid',
    string='Groups',
    default=lambda s: s._default_groups(),
    help="Groups explicitly assigned to the user"
)
```
- **Type:** Many2many to `res.groups`
- **Default:** Returns `base.group_user` (Employee group) plus any groups implied by `base.default_user_group` if it exists.
- **Purpose:** Direct group assignments. Groups can imply other groups (e.g., `group_user` implies `base.module_category_general` groups). See `all_group_ids`.
- **Inverse behavior:** When writing to `group_ids`, the ORM automatically recomputes implied groups.

#### `all_group_ids`
```python
all_group_ids = fields.Many2many(
    'res.groups',
    string="Groups and implied groups",
    compute='_compute_all_group_ids',
    compute_sudo=True,
    search='_search_all_group_ids'
)
```
- **Type:** Many2many (computed)
- **`compute_sudo=True`:** Computed as superuser to see all group memberships.
- **`_compute_all_group_ids`:** `user.group_ids.all_implied_ids` - expands to include all groups implied by direct assignments (via the group's `implied_ids` relation).
- **Searchable:** `_search_all_group_ids` allows searching users by their implied groups.
- **Performance:** `_get_group_ids()` is cached via `@tools.ormcache('self.id')` for fast group checks.

#### `accesses_count`
```python
accesses_count = fields.Integer(
    '# Access Rights',
    compute='_compute_accesses_count',
    compute_sudo=True
)
```
- **Type:** Integer (computed, sudo)
- **`_compute_accesses_count`:** Counts `len(groups.model_access)` across all of the user's groups.

#### `rules_count`
```python
rules_count = fields.Integer(
    '# Record Rules',
    compute='_compute_accesses_count',
    compute_sudo=True
)
```
- **Type:** Integer (computed, sudo)
- **`_compute_accesses_count`:** Counts `len(groups.rule_groups)` across all of the user's groups.

#### `groups_count`
```python
groups_count = fields.Integer(
    '# Groups',
    compute='_compute_accesses_count',
    compute_sudo=True
)
```
- **Type:** Integer (computed, sudo)
- **`_compute_accesses_count`:** Counts `len(groups)` - the total number of groups (direct and implied).

### User Preferences

#### `action_id`
```python
action_id = fields.Many2one(
    'ir.actions.actions',
    string='Home Action',
    help="If specified, this action will be opened at log on for this user..."
)
```
- **Type:** Many2one to `ir.actions.actions`
- **Purpose:** Custom home action that overrides the default menu. Used for dashboard-style interfaces.
- **Constraint:** `_check_action_id` prevents selecting the "App Switcher" action, `ir.actions.client` with tag `reload`, or `ir.actions.act_window` with `active_id` in context (since those require a pre-selected record).

#### `signature`
```python
signature = fields.Html(
    string="Email Signature",
    compute='_compute_signature',
    readonly=False,
    store=True
)
```
- **Type:** Html (stored)
- **`_compute_signature`:** If the signature is empty HTML, auto-generates it as `<div>{user.name}</div>`.
- **`readonly=False`:** Can be edited even though it's computed.

#### `res_users_settings_ids`
```python
res_users_settings_ids = fields.One2many(
    'res.users.settings',
    'user_id'
)
```
- **Type:** One2many to `res.users.settings`
- **Purpose:** User-specific settings (e.g., notification preferences,/discuss configurations).

#### `res_users_settings_id`
```python
res_users_settings_id = fields.Many2one(
    'res.users.settings',
    string="Settings",
    compute='_compute_res_users_settings_id',
    search='_search_res_users_settings_id'
)
```
- **Type:** Many2one (computed, with search support)
- **Purpose:** Convenience field to access the first settings record for the user.

### Inherited Fields from res.partner

These fields are delegated to `partner_id` and are stored on the partner record:

| Field | Type | Source | Purpose |
|-------|------|--------|---------|
| `name` | Char | `partner_id.name` | User's display name |
| `email` | Char | `partner_id.email` | Email address |
| `phone` | Char | `partner_id.phone` | Phone number |

All three have `readonly=False` to allow writing back to the partner record.

### Role Field

#### `role`
```python
role = fields.Selection(
    [('group_user', 'User'), ('group_system', 'Administrator')],
    compute='_compute_role',
    readonly=False,
    string="Role"
)
```
- **Type:** Selection (computed, writable)
- **Purpose:** Convenience field showing whether the user is a regular User or Administrator.
- **`_compute_role`:** Maps `has_group('base.group_system')` to `'group_system'`, `has_group('base.group_user')` to `'group_user'`, otherwise `False`.
- **`_onchange_role`:** When the role is changed, the method replaces the user's groups to either keep only `group_user` or `group_system` (plus other non-admin/non-user groups).

### Technical Fields

#### `view_group_hierarchy`
```python
view_group_hierarchy = fields.Json(
    string='Technical field for user group setting',
    store=False,
    copy=False,
    default=_default_view_group_hierarchy
)
```
- **Type:** Json (not stored)
- **`_default_view_group_hierarchy`:** Returns a hierarchical tree of all groups, used for the "Group Hierarchy" setting in user preferences.
- **Copy:** Disabled - this field should not be duplicated.

---

## Constraints

### `_check_user_company`
```python
@api.constrains('company_id', 'company_ids', 'active')
def _check_user_company(self):
    for user in self.filtered(lambda u: u.active):
        if user.company_id not in user.company_ids:
            raise ValidationError(...)
```
- **Purpose:** Ensures the user's current company (`company_id`) is always in the list of allowed companies (`company_ids`).
- **Scope:** Only enforced on active users.

### `_check_action_id`
```python
@api.constrains('action_id')
def _check_action_id(self):
```
- **Purpose:** Prevents selecting problematic home actions:
  1. The "App Switcher" action (`base.action_open_website`)
  2. Client actions with tag `reload` (would create an infinite loop)
  3. Window actions that require `active_id` in context (would fail without a selected record)

### `_check_disjoint_groups`
```python
@api.constrains('group_ids')
def _check_disjoint_groups(self):
```
- **Purpose:** Prevents users from being simultaneously assigned to mutually exclusive user-type groups (portal, internal, public). These are defined in `res.groups._get_user_type_groups()`.
- **Raises:** `ValidationError` if a user belongs to more than one of these exclusive groups.

### `_check_at_least_one_administrator`
```python
@api.constrains('group_ids')
def _check_at_least_one_administrator(self):
    if not self.env.registry._init_modules:
        return  # skip during base module initialization
    if not self.env.ref('base.group_system').user_ids:
        raise ValidationError(_("You must have at least an administrator user."))
```
- **Purpose:** Database-level safety check ensuring there is always at least one user in `base.group_system`. Skipped during initial module installation to allow the initial setup.

### `_login_key` (SQL Constraint)
```python
_login_key = models.Constraint(
    "UNIQUE (login)",
    'You can not have two users with the same login!'
)
```
- **Purpose:** Database-level constraint ensuring login uniqueness.

---

## CRUD Methods

### `create()`
```python
@api.model_create_multi
def create(self, vals_list):
    users = super().create(vals_list)
    # Create user settings for internal users
    # Sync partner company_id with user company_id
    # Sync partner active state with user active state
    # Auto-generate SVG avatar for internal users without image
    return users
```

**Key behaviors during user creation:**
1. Calls `super().create()` which creates the `res.partner` record (via `_inherits`) and then the `res.users` record.
2. If the user is internal (`_is_internal()`) and has no settings, creates a `res.users.settings` record via `sudo()`.
3. If the partner has a company set and it differs from the user's company, syncs the partner's company to match.
4. Syncs the partner's `active` state with the user's `active` state.
5. For internal users without an image, generates an SVG avatar with the user's initials via `partner_id._avatar_generate_svg()`.

### `write()`
```python
def write(self, vals):
    # Block self-deactivation and superuser activation
    # Self-editing: validate writeable fields only
    # Company switching: sync partner company
    # Company change: reset lazy properties on all envs
    # Group change: clear model access cache
    return super().write(vals)
```

**Key behaviors during user update:**

1. **Cannot activate superuser:** If trying to activate the superuser (id=1), raises `UserError`.
2. **Cannot deactivate self:** If the current user (`self.env.uid`) is in `self._ids` and `active` is being set to `False`, raises `UserError`.
3. **Self-editing validation:** If the user is editing their own record, only fields in `SELF_WRITEABLE_FIELDS` are allowed. If `company_id` is in the list but not in the user's allowed companies, it is silently removed.
4. **Company sync to partner:** If `company_id` changes and the partner has a company set (not global), the partner's company is updated to match.
5. **Lazy property reset:** If company fields change, `reset_cached_properties(env)` is called on all transaction environments to clear cached `company` and `companies` lazy properties.
6. **Access cache clearing:** If `group_ids` change, `ir.model.access.call_cache_clearing_methods()` is invoked.
7. **Registry cache clearing:** If any field in `_get_invalidation_fields()` changes, the registry cache is cleared.

### `unlink()`
```python
@api.ondelete(at_uninstall=True)
def _unlink_except_master_data(self):
    # Prevents deletion of:
    # 1. The superuser (id = SUPERUSER_ID)
    # 2. The admin user (base.user_admin)
    # 3. Portal user template (base.template_portal_user_id)
    # 4. Public user (base.public_user)
```

**Protections:**
- Prevents deleting the superuser (id=1) - needed for internal Odoo operations.
- Prevents deleting the admin user (`base.user_admin`).
- Prevents deleting portal template and public users.
- Clears the registry cache after deletion.
- Uses `@api.ondelete(at_uninstall=True)` to only enforce at module uninstall, not during normal operation.

### `copy_data()`
```python
def copy_data(self, default=None):
    # Appends " (copy)" to name and login to avoid duplicates
```

---

## Authentication & Session Management

### `_check_credentials()`
```python
def _check_credentials(self, credential, env):
    """ Validates the current user's password.

    :returns: auth_info dict with:
        - uid: authenticated user ID
        - auth_method: 'password' or 'apikey'
        - mfa: 'default', 'enforce', or 'skip'
    """
```

This is the core authentication method. Its behavior:

1. **Password verification:** If the credential type is `'password'`:
   - Queries the stored password hash directly from the database (bypasses ORM to get the raw hash).
   - Uses `CryptContext.verify_and_update()` to check the password.
   - If the hash needs rehashing (algorithm updated), it automatically updates the stored password.
   - If rehashing occurs and the request is active, it flushes the environment, clears the registry cache, and computes a new session token so the user is not logged out.
   - Returns `{'uid': ..., 'auth_method': 'password', 'mfa': 'default'}`.

2. **API key fallback (non-interactive):** If the credential type is not `'password'` or password verification failed, and the request is non-interactive (e.g., RPC), it tries `res.users.apikeys._check_credentials()`.

3. **Raises `AccessDenied`:** If all authentication methods fail.

### `authenticate()`
```python
def authenticate(self, credential, user_agent_env):
    """Verifies credentials and returns auth_info dict."""
    auth_info = self._login(credential, user_agent_env)
    # If system user logged in successfully and base_location provided,
    # updates web.base.url configuration parameter
    return auth_info
```

### `_login()`
```python
def _login(self, credential, user_agent_env):
    # Searches user by login
    # Asserts can authenticate (_assert_can_auth - rate limiting)
    # Calls _check_credentials()
    # Sets timezone from browser cookie on first login
    # Updates last login (_update_last_login)
    # Raises AccessDenied on failure (triggers rate limit counter)
```

### `_assert_can_auth()` - Rate Limiting / Login Cooldown
```python
@contextlib.contextmanager
def _assert_can_auth(self, user=None):
```

This is a **context manager** that implements brute-force protection:

1. **Tracks failures per IP:** Uses `registry._login_failures` (a `defaultdict` mapping IP address to `(failure_count, last_failure_timestamp)`).
2. **Cooldown check:** `_on_login_cooldown()` checks if:
   - Failures >= `base.login_cooldown_after` (default: 5)
   - AND time since last failure < `base.login_cooldown_duration` (default: 60 seconds)
   - If both true, the login is rejected with `AccessDenied`.
3. **On success:** Removes the IP from the failures map.
4. **On `AccessDenied`:** Increments the failure counter and updates the timestamp.
5. **Private IP warning:** Logs a warning if a private IP is rate-limited, as it might indicate a misconfigured reverse proxy.

**Configurable via System Parameters:**
- `base.login_cooldown_after`: Number of failures before cooldown (set to 0 to disable).
- `base.login_cooldown_duration`: Cooldown duration in seconds.

### Session Token Management

#### `_get_session_token_fields()`
```python
def _get_session_token_fields(self):
    return {'id', 'login', 'password', 'active'}
```
- **Purpose:** Returns the set of field names used to compute the session token. Changing any of these fields invalidates all active sessions for that user.

#### `_compute_session_token()`
```python
@tools.ormcache('sid')
def _compute_session_token(self, sid):
    """ Compute a session token given a session id and a user id """
    field_values = self._session_token_get_values()
    return self._session_token_hash_compute(sid, field_values)
```
- **Cached:** Per-session ID. The cache is invalidated when any of the session token fields change.
- **`_session_token_get_values`:** Executes a SQL query to fetch the current values of session token fields from the database (with the database secret).
- **`_session_token_hash_compute`:** Uses HMAC-SHA256 to hash the session ID with a key derived from the user's fields. The key tuple is `(field_name, field_value)` for all non-null fields.

**Security model:** The session token is an HMAC of the session ID, where the HMAC key is derived from user-specific, server-side data. This prevents session fixation attacks. Changing the password, login, or active status invalidates all existing sessions.

### Password Change

#### `change_password()`
```python
@api.model
def change_password(self, old_passwd, new_passwd):
    """Change current user password. Old password must be provided."""
    credential = {'login': self.env.user.login, 'password': old_passwd, 'type': 'password'}
    self._check_credentials(credential, {'interactive': True})
    self.env.user._change_password(new_passwd)
    return True
```
- **Requires old password:** The old password must be verified before allowing the change.
- **Interactive context:** Forces interactive authentication flow.

#### `_change_password()`
```python
def _change_password(self, new_passwd):
    new_passwd = new_passwd.strip()
    if not new_passwd:
        raise UserError(_("Setting empty passwords is not allowed..."))
    # Logs: user login, user id, admin login, admin id, IP
    self.password = new_passwd
```
- **Strips whitespace:** Leading/trailing whitespace is removed.
- **Empty check:** Rejects empty passwords.
- **Logging:** Records who changed whose password and from which IP.

### `_update_last_login()`
```python
@api.model
def _update_last_login(self):
    # Creates a new res.users.log record (population via defaults)
    # Old duplicate entries are cleaned up by _gc_user_logs
```
- **Non-destructive:** Uses `create({})` which populates `create_uid` and `create_date` via defaults. This avoids race conditions with concurrent logins.
- **Cleanup:** The autovacuum method `_gc_user_logs` runs periodically to delete duplicate entries.

---

## Password Hashing

### `_crypt_context()`
```python
@tools.ormcache(cache='stable')
def _crypt_context(self):
    return CryptContext(
        ['pbkdf2_sha512', 'plaintext'],
        deprecated=['auto'],
        pbkdf2_sha512__rounds=max(MIN_ROUNDS, int(cfg.get_param('password.hashing.rounds', 0))),
    )
```
- **`MIN_ROUNDS = 600_000`:** The minimum number of PBKDF2 rounds enforced by the Odoo codebase.
- **Default algorithm:** `pbkdf2_sha512` (first in the schemes list).
- **`deprecated='auto'`:** If a hash was made with fewer rounds than currently configured, `verify_and_update()` will return the hash as needing an update and Odoo will rehash it on next successful login.
- **System Parameter:** `password.hashing.rounds` allows configuring the number of rounds (higher = more secure but slower). Must be >= `MIN_ROUNDS`.
- **Plaintext fallback:** The `plaintext` scheme is included for compatibility with legacy unencrypted passwords. These are automatically upgraded on startup via `init()`.

### `init()` - Plaintext Password Upgrade
```python
def init(self):
    cr.execute("""
        SELECT id, password FROM res_users
        WHERE password IS NOT NULL
          AND password !~ '^\$[^$]+\$[^$]+\$.'
    """)
    # For each user with a plaintext password, re-hash it
    ResUsers.browse(uid).password = pw
```
- On module initialization, any password that does not match the pattern of a salted hash (i.e., plaintext passwords) is automatically hashed using the current `CryptContext`.

---

## API Keys (`res.users.apikeys`)

### Model: `ResUsersApikeys`
```python
class ResUsersApikeys(models.Model):
    _name = 'res.users.apikeys'
    _description = 'Users API Keys'
    _auto = False  # Custom table with secret column
    _allow_sudo_commands = False
```

The `_auto = False` is critical: it allows defining a table with a `key` column that stores the hash directly without the ORM interfering.

**Table schema (created in `init()`):**
```sql
CREATE TABLE res_users_apikeys (
    id serial PRIMARY KEY,
    name varchar NOT NULL,
    user_id integer REFERENCES res_users(id) ON DELETE CASCADE,
    scope varchar,
    expiration_date timestamp,
    index varchar(8) NOT NULL CHECK (char_length(index) = 8),
    key varchar NOT NULL,  -- hashed API key
    create_date timestamp DEFAULT (now() at time zone 'utc')
)
```
- **`index`:** First 8 hex characters (4 bytes / 20% of a 20-byte random key). Stored in plaintext for fast lookup.
- **`key`:** The full key hashed with `pbkdf2_sha512` at only 6,000 rounds (fast because the key is already random, not user-derived).

### Key Generation
```python
API_KEY_SIZE = 20  # bytes
INDEX_SIZE = 8     # hex digits = 4 bytes

def _generate(self, scope, name, expiration_date):
    k = binascii.hexlify(os.urandom(API_KEY_SIZE)).decode()
    # Store: key[:INDEX_SIZE] (plaintext index) + hash of full key
```

- Key = 40-character hex string (20 random bytes).
- Only the first 8 hex chars (index) are stored in plaintext. The full key is hashed.
- On authentication, the system finds the record by index, then verifies the full key against the stored hash.

### Key Verification
```python
def _check_credentials(self, *, scope, key):
    index = key[:INDEX_SIZE]
    # SELECT user_id, key FROM res_users_apikeys
    #   WHERE index = index AND user active AND scope matches AND not expired
    # For each match, verify KEY_CRYPT_CONTEXT.verify(key, current_key)
    #   return user_id if valid
```
- **Scope matching:** `NULL` scope means the key works for any scope. Otherwise, the key's scope must exactly match.
- **Expiration:** Keys with `expiration_date < now()` are rejected.

### Expiration Enforcement
```python
def _check_expiration_date(self, date):
    # System users can create persistent (non-expiring) keys
    # Others: max_duration based on their group privileges
    #   e.g., group with api_key_duration = 365 means max 1 year
```

Groups can define `api_key_duration` (in days) to limit how long non-admin users can create keys for.

### `@check_identity` Decorator

Actions that create or revoke API keys are decorated with `@check_identity`, which requires the user to re-enter their password if they have not done so in the last 10 minutes. See `check_identity` in helpers.

---

## Helper Classes

### `check_identity` Decorator
```python
def check_identity(fn):
    """ Wrapped method should be an *action method* (called from a button
    type=object), and requires extra security to be executed. This decorator
    checks if the identity (password) has been checked in the last 10mn, and
    pops up an identity check wizard if not.

    Prevents access outside of interactive contexts (aka with a request)
    """
```

**Used on:**
- `preference_change_password()` - change own password
- `api_key_wizard()` - create new API key
- `action_revoke_all_devices()` - revoke sessions/devices
- `ResUsersIdentitycheck.run_check()` - confirm password

**Behavior:**
1. Checks if `request.session.get('identity-check-last')` is within the last 10 minutes.
2. If yes, executes the method.
3. If no, creates a `res.users.identitycheck` wizard record with the method context and returns an action to open it as a dialog.
4. Raises `UserError` if called outside of an HTTP request context.

### `ResUsersIdentitycheck` Wizard
```python
class ResUsersIdentitycheck(models.TransientModel):
    _name = 'res.users.identitycheck'
    password = fields.Char(store=False)

    def run_check(self):
        self._check_identity()
        request.session['identity-check-last'] = time.time()
        # Deserialize and execute the deferred method
```

### `ChangePasswordOwn` Wizard
```python
class ChangePasswordOwn(models.TransientModel):
    new_password = fields.Char(string="New Password")
    confirm_password = fields.Char(string="New Password (Confirmation)")

    @api.constrains('new_password', 'confirm_password')
    def _check_password_confirmation(self):
        if self.confirm_password != self.new_password:
            raise ValidationError(...)

    @check_identity
    def change_password(self):
        self.env.user._change_password(self.new_password)
        self.unlink()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
```

---

## Group & Permission Methods

### `has_group()`
```python
@api.readonly
def has_group(self, group_ext_id: str) -> bool:
    # Returns whether user belongs to the given group
    # Raises AccessError if called by non-internal user on another user
    # Special: base.group_no_one only effective in debug mode
    result = self._has_group(group_ext_id)
    if group_ext_id == 'base.group_no_one':
        result = result and bool(request and request.session.debug)
    return result
```

### `has_groups()` - Multi-group Check
```python
@api.readonly
def has_groups(self, group_spec: str) -> bool:
    # Comma-separated list of fully-qualified group XML IDs
    # Supports negation with ! prefix
    # Example: "base.group_user,base.group_portal,!base.group_system"
    # Returns True if user is in at least one positive group AND no negative groups
```

### `_has_group()` - Internal Check
```python
def _has_group(self, group_ext_id: str) -> bool:
    group_id = self.env['res.groups']._get_group_definitions().get_id(group_ext_id)
    return group_id in (self._get_group_ids() if self.id else self.all_group_ids._origin._ids)
```
- **`_get_group_ids()`:** Cached via `@tools.ormcache('self.id')`. Returns the tuple of all group IDs (direct + implied) for the user.
- **`all_group_ids` (on new records):** Falls back to `self.all_group_ids._origin._ids`.

### User Type Methods

| Method | Description |
|--------|-------------|
| `_is_internal()` | `has_group('base.group_user')` - internal employee |
| `_is_portal()` | `has_group('base.group_portal')` - external portal user |
| `_is_public()` | `has_group('base.group_public')` - public website visitor |
| `_is_system()` | `has_group('base.group_system')` - administrator |
| `_is_admin()` | `_is_superuser() or has_group('base.group_erp_manager')` |
| `_is_superuser()` | `self.id == SUPERUSER_ID` (id = 1) |

---

## Self-Access Control

### `SELF_READABLE_FIELDS`
```python
@property
def SELF_READABLE_FIELDS(self):
    return [
        'signature', 'company_id', 'login', 'email', 'name', 'image_1920',
        'image_1024', 'image_512', 'image_256', 'image_128', 'lang', 'tz',
        'tz_offset', 'group_ids', 'partner_id', 'write_date', 'action_id',
        'avatar_1920', 'avatar_1024', 'avatar_512', 'avatar_256', 'avatar_128',
        'share', 'device_ids', 'api_key_ids', 'phone', 'display_name',
    ]
```

### `SELF_WRITEABLE_FIELDS`
```python
@property
def SELF_WRITEABLE_FIELDS(self):
    return [
        'signature', 'action_id', 'company_id', 'email', 'name',
        'image_1920', 'lang', 'tz', 'api_key_ids', 'phone'
    ]
```

### `read()` Override
```python
def read(self, fields=None, load='_classic_read'):
    readable, _ = self._self_accessible_fields()
    if fields and self == self.env.user and all(key in readable or key.startswith('context_') for key in fields):
        # safe fields only, so we read as super-user to bypass access rights
        self = self.sudo()
    return super().read(fields=fields, load=load)
```
- Users can read their own record's safe fields via `sudo()` without triggering access errors.
- Non-safe fields require proper ACLs as usual.

### `write()` Self-Edit Validation
When a user writes to their own record, only `SELF_WRITEABLE_FIELDS` are accepted. Other fields are silently dropped (or the entire write is rejected if any non-writeable field is present).

### `onchange()` Self-Edit
```python
def onchange(self, values, field_names, fields_spec):
    # Hack: pre-load self-readable fields into cache before onchange logic
    if self == self.env.user:
        [self.sudo()[field_name] for field_name in self._self_accessible_fields()[0]]
    return super().onchange(values, field_names, fields_spec)
```

---

## Computed Fields Detail

### `_compute_companies_count`
```python
@api.depends('company_id')
def _compute_companies_count(self):
    self.companies_count = self.env['res.company'].sudo().search_count([])
```
- **Dependency:** `company_id` (triggers recompute when current company changes)
- **Note:** Counts all companies in the database, not just the user's allowed companies.

### `_compute_tz_offset`
```python
@api.depends('tz')
def _compute_tz_offset(self):
    for user in self:
        user.tz_offset = datetime.datetime.now(
            pytz.timezone(user.tz or 'GMT')
        ).strftime('%z')
```
- **Format:** `'+0700'`, `'-0530'`, etc.

### `_compute_signature`
```python
@api.depends('name')
def _compute_signature(self):
    for user in self.filtered(lambda u: u.name and is_html_empty(user.signature)):
        user.signature = Markup('<div>%s</div>') % user['name']
```
- Auto-generates a default signature using the user's name if the current signature is empty HTML.

---

## L3: Edge Cases & Override Patterns

### Company Switching Side Effects
When `company_id` changes in `write()`:
1. The partner's company is synced if the partner is not a "global" partner (i.e., has a company set).
2. All transaction `Env` objects are iterated, and if any env's user is in the set of modified users, `reset_cached_properties(env)` is called. This clears the `company` and `companies` lazy properties on those envs, forcing them to be re-read from the database on next access.
3. This is critical for multi-company workflows where changing company mid-session would otherwise use stale cached company data.

### `name_search()` Override
```python
@api.model
def name_search(self, name='', domain=None, operator='ilike', limit=100):
    # First tries to match by exact login
    if name and not operator in NEGATIVE_OPERATORS:
        if user := self.search_fetch(Domain('login', '=', name) & domain, ['display_name']):
            return [(user.id, user.display_name)]
    return super().name_search(name, domain, operator, limit)
```
- **Optimization:** If the search term matches a user's login exactly, it returns only that user immediately, bypassing the slower name-based search.

### `_search_display_name()` Override
```python
@api.model
def _search_display_name(self, operator, value):
    domain = super()._search_display_name(operator, value)
    if operator in ('in', 'ilike') and value:
        # Also search by login for 'in' and 'ilike' operators
        name_domain = [('login', 'in', [value] if isinstance(value, str) else value)]
        if users := self.search(name_domain):
            domain = [('id', 'in', users.ids)]
    return domain
```
- **Purpose:** When searching display names with `in` or `ilike`, also search by login. This avoids a performance issue where searching both name and login (on separate tables) prevents index usage.

### `_default_view_group_hierarchy()`
```python
def _default_view_group_hierarchy(self):
    return self.env['res.groups']._get_view_group_hierarchy()
```
- Returns a Json representation of the group hierarchy tree for the user preferences UI.

### `_rpc_api_keys_only()`
```python
def _rpc_api_keys_only(self):
    """ To be overridden if RPC access needs to be restricted to API keys, e.g. for 2FA """
    return False
```
- Can be overridden to enforce API-key-only authentication for certain users (used by the `auth_totp` module for 2FA enforcement).

---

## L4: Performance, Security & Historical Changes

### Performance Considerations

1. **`@tools.ormcache` is heavily used:**
   - `_self_accessible_fields()` - cached at model level
   - `_crypt_context()` - cached at model level
   - `_get_group_ids(self.id)` - cached per user (keyed by user ID)
   - `_compute_session_token(sid)` - cached per session ID
   - `_get_company_ids(self.id)` - cached per user
   - `context_get()` - cached per UID

2. **`_login_failures` is a process-level defaultdict:**
   - Shared across all workers in the same process.
   - Not shared across different Odoo workers (stateless across workers for rate limiting).
   - Not persistent across worker restarts.

3. **N+1 avoidance in `_compute_accesses_count`:**
   - Groups are computed once and reused for all three count fields (`accesses_count`, `rules_count`, `groups_count`).

4. **Bulk rank recomputation:**
   - `_recompute_rank_bulk()` is used when the number of users exceeds 3x the number of ranks, to avoid N queries per user.

### Security Hardening (Odoo 19)

1. **`_allow_sudo_commands = False`:** Prevents privilege escalation via `sudo()` in XML-RPC calls.
2. **`bypass_search_access=True` on `partner_id`:** Allows searching for users without read access on partners.
3. **`@api.readonly` on `has_group()`:** Prevents these methods from being called as writable methods.
4. **`request` check in `check_identity`:** Prevents calling identity-sensitive methods outside of HTTP contexts.
5. **Rate limiting:** Login cooldown prevents brute-force attacks.
6. **Session token:** HMAC-based session tokens prevent session fixation.
7. **API key:** 20-byte random keys with separate index storage for fast lookup.
8. **`readonly=True, groups=fields.NO_ACCESS` on `ResUsersIdentitycheck.request`:** The serialized context stored for deferred method execution is not readable by non-admin users.

### Password Security

- **Algorithm:** PBKDF2-SHA512 with configurable rounds (minimum 600,000).
- **Automatic upgrade:** Plaintext and weak hashes are automatically upgraded on login.
- **Work factor tuning:** `password.hashing.rounds` system parameter allows increasing rounds as hardware improves.
- **No plaintext storage:** The `password` field is computed to always return `''` on read. The actual hash is in the DB column.
- **Session preservation on rehash:** When a password is rehashed on login, the session token is also updated so the user is not logged out.

### Odoo 18 to 19 Changes

1. **`share` field computation:** Changed to depend on `all_group_ids` rather than just `group_ids`. This correctly accounts for implied groups (e.g., a user with an implied group that implies `base.group_user` should still be considered internal).
2. **`role` field:** Added as a convenience computed-writable field for distinguishing User vs. Administrator roles.
3. **`view_group_hierarchy`:** Added as a Json field for group hierarchy visualization in user preferences.
4. **`_check_disjoint_groups` constraint:** Strengthened to prevent users from being in multiple exclusive user-type groups simultaneously.
5. **`_login_failures` mechanism:** Improved with private IP detection warnings.
6. **`_search_display_name`:** Refactored to avoid performance issues when searching by `in` or `ilike` operators.
7. **Karma tracking removal:** The `failure_counter` and related fields were removed. Login failure tracking is now purely in-memory via `_login_failures`, not stored in the database.

---

## Gamification Extension (`gamification/res_users.py`)

The `gamification` module extends `res.users` with gamification features.

### Gamification Fields

#### `karma`
```python
karma = fields.Integer(
    'Karma',
    compute='_compute_karma',
    store=True,
    readonly=False
)
```
- **Type:** Integer (computed, stored)
- **`store=True`:** Stored in `res.users` table (the value comes from `gamification.karma.tracking`).
- **`readonly=False`:** Can be written directly, which triggers karma tracking.
- **`_compute_karma`:** Queries `gamification_karma_tracking` for the most recent entry per user, ordered by `tracking_date DESC, id DESC`.

#### `karma_tracking_ids`
```python
karma_tracking_ids = fields.One2many(
    'gamification.karma.tracking',
    'user_id',
    string='Karma Changes',
    groups="base.group_system"
)
```
- **Access:** Only visible to system administrators.

#### `badge_ids`
```python
badge_ids = fields.One2many(
    'gamification.badge.user',
    'user_id',
    string='Badges',
    copy=False
)
```

#### `gold_badge`, `silver_badge`, `bronze_badge`
```python
gold_badge = fields.Integer('Gold badges count', compute="_get_user_badge_level")
silver_badge = fields.Integer('Silver badges count', compute="_get_user_badge_level")
bronze_badge = fields.Integer('Bronze badges count', compute="_get_user_badge_level")
```
- Computed from `gamification_badge_user` joined with `gamification_badge` where `level` matches.

#### `rank_id`
```python
rank_id = fields.Many2one(
    'gamification.karma.rank',
    'Rank',
    index='btree_not_null'
)
```
- The user's current rank based on karma.
- **`index='btree_not_null'`:** Creates a B-tree index that excludes NULL values for better query performance.

#### `next_rank_id`
```python
next_rank_id = fields.Many2one('gamification.karma.rank', 'Next Rank')
```
- The rank the user is working toward.

### Karma Methods

#### `_add_karma()`
```python
def _add_karma(self, gain, source=None, reason=None):
    """Add karma to a single user. Creates a tracking record."""
    values = {'gain': gain, 'source': source, 'reason': reason}
    return self._add_karma_batch({self: values})
```

#### `_add_karma_batch()`
```python
def _add_karma_batch(self, values_per_user):
    """Batch karma addition with single database write."""
    create_values = []
    for user, values in values_per_user.items():
        # Computes new_value, old_value, origin_ref, reason
        create_values.append({...})
    self.env['gamification.karma.tracking'].sudo().create(create_values)
    return True
```

#### `_get_tracking_karma_gain_position()`
Returns the user's absolute position in karma gain ranking within a given timeframe.

#### `_get_karma_position()`
Returns the user's absolute position in total karma ranking.

#### `_recompute_rank()`
```python
def _recompute_rank(self):
    # For small datasets: per-user rank computation
    # For large datasets: delegates to _recompute_rank_bulk
    if len(self) > len(ranks) * 3:
        self._recompute_rank_bulk()
        return
    for user in self:
        # Find highest rank where karma >= karma_min
        # Write rank_id and next_rank_id
        # Notify via _rank_changed() if rank changed
```

#### `_recompute_rank_bulk()`
For large datasets, computes ranks by rank (instead of by user) to reduce from O(N) to O(R) database queries where R is the number of ranks.

### Karma Rank Model (`gamification.karma.rank`)

```python
class GamificationKarmaRank(models.Model):
    _name = 'gamification.karma.rank'
    _description = 'Rank based on karma'
    _inherit = ['image.mixin']
    _order = 'karma_min'

    name = fields.Text(string='Rank Name', translate=True, required=True)
    description = fields.Html(string='Description', translate=..., sanitize_attributes=False)
    description_motivational = fields.Html(...)
    karma_min = fields.Integer(string='Required Karma', required=True, default=1)
    user_ids = fields.One2many('res.users', 'rank_id', string='Users')
    rank_users_count = fields.Integer("# Users", compute="_compute_rank_users_count")

    _karma_min_check = models.Constraint(
        'CHECK( karma_min > 0 )',
        'The required karma has to be above 0.',
    )
```

---

## Multi-Company Extension (`base/models/res_users.py` - `UsersMultiCompany`)

```python
class UsersMultiCompany(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        # Auto-add/remove base.group_multi_company based on company count
        return users

    def write(self, vals):
        res = super().write(vals)
        # Sync base.group_multi_company membership on company_ids change
        return res
```

**Auto group management:**
- If a user has access to 1 or fewer companies and has `base.group_multi_company`, the group is automatically removed.
- If a user has access to 2+ companies and does not have `base.group_multi_company`, the group is automatically added.
- This applies to `create()`, `write()`, and `new()`.

---

## Related Models Referenced

| Model | Module | Purpose |
|-------|--------|---------|
| `res.partner` | `base` | Stores name, email, phone, avatar via `_inherits` |
| `res.groups` | `base` | Security groups |
| `res.company` | `base` | Multi-company support |
| `res.users.log` | `base` | Login history tracking |
| `res.users.settings` | `base` | User preferences/settings |
| `res.users.apikeys` | `base` | API key authentication |
| `res.users.identitycheck` | `base` | Password re-check wizard |
| `change.password.wizard` | `base` | Admin password change |
| `change.password.own` | `base` | Self password change |
| `res.device` | `base` | Trusted devices |
| `ir.actions.actions` | `base` | Home action target |
| `ir.config_parameter` | `base` | System parameters |
| `gamification.karma.tracking` | `gamification` | Karma change history |
| `gamification.karma.rank` | `gamification` | Karma-based ranks |
| `gamification.badge.user` | `gamification` | Badge awards |

---

## System Parameters Used

| Key | Default | Purpose |
|-----|---------|---------|
| `password.hashing.rounds` | 0 (uses MIN_ROUNDS=600k) | PBKDF2 work factor |
| `base.login_cooldown_after` | 5 | Failures before cooldown |
| `base.login_cooldown_duration` | 60 | Cooldown duration (seconds) |
| `database.secret` | - | Used in session token HMAC |

---

## Class Diagram Summary

```
res.partner (via _inherits)
  ├── name (delegated)
  ├── email (delegated)
  ├── phone (delegated)
  └── image_* (delegated)

res.users (main model)
  ├── partner_id ──────► res.partner
  ├── login (unique)
  ├── password (write-only, hashed)
  ├── active
  ├── share (computed: internal vs portal)
  ├── company_id ─────► res.company
  ├── company_ids ────► res.company (many2many)
  ├── group_ids ───────► res.groups
  ├── all_group_ids (computed: direct + implied)
  ├── api_key_ids ────► res.users.apikeys
  ├── device_ids ─────► res.device
  ├── log_ids ────────► res.users.log
  ├── action_id ──────► ir.actions.actions
  ├── res_users_settings_ids ──► res.users.settings
  ├── karma (gamification)
  ├── rank_id (gamification) ──► gamification.karma.rank
  ├── badge_ids (gamification)
  └── karma_tracking_ids (gamification)

UsersMultiCompany (mixin)
  └── Auto-manages base.group_multi_company membership

ResUsersApikeys (companion model)
  └── API key storage and verification

ResUsersIdentitycheck (transient wizard)
  └── Password re-verification

ChangePasswordWizard / ChangePasswordOwn (transient wizards)
  └── Password change flows
```

---

## Key Design Decisions

1. **Delegation inheritance (`_inherits`):** Separates partner data from user technical data, allowing users to share partner records in certain scenarios while keeping authentication separate.
2. **Write-only password field:** The `password` field is computed with an inverse, making it impossible to read the hashed password back through the ORM. This is a deliberate security measure.
3. **In-memory rate limiting:** Login failure tracking uses process memory rather than the database, making it fast but not persistent across worker restarts. This is intentional - the feature is for rate limiting, not audit logging (which is handled by `res.users.log`).
4. **Stored karma:** The `karma` field is stored in the `res.users` table despite being computed from `gamification.karma.tracking`. This is for performance - group and rank checks need the karma value without joining to the tracking table.
5. **`_allow_sudo_commands = False`:** Hardens against privilege escalation in multi-tenant environments where untrusted code might use `sudo()`.
6. **`compute_sudo=True` on `share`:** Ensures share status is computed correctly regardless of the calling user's privileges, since share status affects access control decisions throughout the system.
