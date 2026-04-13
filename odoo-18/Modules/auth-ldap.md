---
Module: auth_ldap
Version: Odoo 18
Type: Core
Tags: #auth #security #ldap #directory-service
---

# auth_ldap — LDAP Authentication

> Integrates Odoo with an external LDAP directory (Active Directory, OpenLDAP, 389ds, etc.). Enables corporate single sign-on (SSO) by authenticating users against the company LDAP server. Can automatically create local Odoo user accounts from LDAP entries.

**Source:** `~/odoo/odoo18/odoo/addons/auth_ldap/`
**Manifest:** `__manifest__.py`
**Depends:** `base`, `base_setup`
**External dependency:** `python-ldap`
**License:** LGPL-3

---

## Models

### `res.company.ldap` — LDAP Configuration Per Company

The central model. Stores LDAP connection parameters and user mapping rules. Each record represents one LDAP server configuration for one company.

**`_name = 'res.company.ldap'`**
**`_description = 'Company LDAP configuration'`**
**`_order = 'sequence'`** (evaluated in order; first matching server wins)
**`_rec_name = 'ldap_server'`**

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `sequence` | `Integer` | Yes | `10` | Evaluation order. Lower numbers are tried first. |
| `company` | `Many2one(res.company)` | Yes | — | Which company this LDAP config belongs to. |
| `ldap_server` | `Char` | Yes | `'127.0.0.1'` | IP or hostname of the LDAP server. |
| `ldap_server_port` | `Integer` | Yes | `389` | LDAP port. `389` = standard LDAP, `636` = LDAPS. |
| `ldap_binddn` | `Char` | No | `False` | Bind DN for the service account used to query LDAP. Leave empty for anonymous bind. |
| `ldap_password` | `Char` | No | `False` | Password for the service account (stored in plain text in DB — see security note below). |
| `ldap_filter` | `Char` | Yes | — | LDAP search filter. Must contain `%s` placeholder replaced by the login. |
| `ldap_base` | `Char` | Yes | — | Base DN — the root of the LDAP tree to search. |
| `user` | `Many2one(res.users)` | No | `False` | Template user whose groups and settings are copied when creating new LDAP users. |
| `create_user` | `Boolean` | Yes | `True` | If `True`, auto-creates Odoo `res.users` record for new LDAP logins. |
| `ldap_tls` | `Boolean` | Yes | `False` | If `True`, calls `start_tls_s()` after connecting for encrypted channel. Requires STARTTLS on the LDAP server. |

#### L4: Field Details

**`ldap_filter`** — the filter template:
```
(&(objectCategory=person)(objectClass=user)(sAMAccountName=%s))
(uid=%s)
(|(mail=%s)(uid=%s))
```
The `%s` is replaced by the login name the user typed. The filter MUST return exactly one result or authentication fails.

**`ldap_base`** — example:
```
dc=mycompany,dc=com
ou=users,dc=mycompany,dc=com
```

**`ldap_binddn` / `ldap_password`** — service account:
- Used to bind to LDAP and run the user search query.
- If empty, anonymous bind is attempted.
- The password is stored **in clear text** in the database. This is a security consideration — the database should be protected accordingly.
- To mitigate: use a read-only LDAP service account with minimal privileges.

**`ldap_tls`** — STARTTLS vs LDAPS:
- `ldap_tls=False` + port `389` = plain-text LDAP
- `ldap_tls=True` + port `389` = LDAP with STARTTLS upgrade (in-flight encryption)
- port `636` = implicit LDAPS (SSL, no STARTTLS needed)
- Odoo only calls `start_tls_s()` — it does not support implicit SSL on port `636` natively (LDAPWrapper only wraps `simple_bind_s`, `passwd_s`, `search_st`, `unbind`).

#### SQL Constraints

None defined in this model.

---

### `res.company` — LDAP Configuration Link

Extended to add a One2many to `res.company.ldap`.

**Inheritance:** `_inherit = 'res.company'`

#### Fields

| Field | Type | Relation | Description |
|-------|------|----------|-------------|
| `ldaps` | `One2many` | `res.company.ldap` → `company` | All LDAP configurations for this company. One company can have multiple LDAP configs (e.g., different servers for different LDAP trees). |

#### L4: Multi-Company LDAP

Each company can have its own LDAP server. The `_get_ldap_dicts()` method reads all LDAP configs and evaluates them in `sequence` order. In a multi-company/multi-tenant Odoo setup, the LDAP config for the user's company is used.

---

### `res.users` — Authentication Integration

Extended from `base.models.res_users`. Intercepts the login and credential-checking flows to add LDAP authentication as a fallback.

**Inheritance:** `_inherit = 'res.users'`

#### `_login(db, credential, user_agent_env)` — `@classmethod`

Overridden classmethod. Called by `odoo.http.Root` during the `/web/login` HTTP POST.

```python
@classmethod
def _login(cls, db, credential, user_agent_env):
    try:
        return super()._login(db, credential, user_agent_env=user_agent_env)
    except AccessDenied as e:
        # ... LDAP fallback logic ...
```

**Flow:**
1. First, tries normal Odoo database authentication (`super()._login()`).
2. If `AccessDenied` is raised AND the login does NOT exist in `res_users`, proceeds to LDAP.
3. Iterates all LDAP configs in sequence order.
4. Calls `Ldap._authenticate(conf, login, password)` on each.
5. If an LDAP entry is returned, calls `Ldap._get_or_create_user()` to get or make the Odoo user.
6. Returns `{'uid': <user_id>, 'auth_method': 'ldap', 'mfa': 'default'}`.

**L4: Why the pre-check on `res_users`?**
If the login already exists in Odoo but the password is wrong, LDAP should NOT be tried — that would allow bypassing the Odoo password. This is an important security design point.

---

#### `_check_credentials(credential, env)` — Runtime credential check

Overridden for already-logged-in users. When a session is active and the user re-enters credentials (e.g., for sensitive operations), LDAP is tried as a fallback.

```python
def _check_credentials(self, credential, env):
    try:
        return super()._check_credentials(credential, env)
    except AccessDenied:
        # Falls back to LDAP if the user is LDAP-managed
```

**Difference from `_login`:** `_check_credentials` is for in-session credential re-verification (e.g., unlinking a OAuth account, changing password). `_login` is for the initial login handshake.

---

#### `change_password(old_passwd, new_passwd)` — LDAP password write-back

```python
def change_password(self, old_passwd, new_passwd):
    if new_passwd:
        Ldap = self.env['res.company.ldap']
        for conf in Ldap._get_ldap_dicts():
            changed = Ldap._change_password(conf, self.env.user.login, old_passwd, new_passwd)
            if changed:
                self.env.user._set_empty_password()
                return True
    return super(Users, self).change_password(old_passwd, new_passwd)
```

**L4: What this does:**
1. If `new_passwd` is provided, tries to change the password in LDAP using the LDAP `passwd_s()` API.
2. If LDAP change succeeds, sets the Odoo local password to NULL (`_set_empty_password()`).
3. If LDAP change fails on all configs, falls back to `super().change_password()` — normal Odoo password change.
4. The result: LDAP users can change their corporate password from inside Odoo, and the change propagates to LDAP directly.

**`_set_empty_password()`** — Sets `res_users.password = NULL` in the DB. This ensures the local Odoo password is not usable independently of LDAP.

---

## `res.company.ldap` — Key Methods

### `_get_ldap_dicts()` — Config retrieval

Reads all LDAP configs from the DB (sudo) and returns them as a list of dictionaries.

```python
def _get_ldap_dicts(self):
    res = self.sudo().search_read(
        [('ldap_server', '!=', False)],
        ['id', 'company', 'ldap_server', 'ldap_server_port',
         'ldap_binddn', 'ldap_password', 'ldap_filter', 'ldap_base',
         'user', 'create_user', 'ldap_tls'],
        order='sequence'
    )
    return res
```

Returns plain dicts — not recordsets. Used by `res.users` to iterate LDAP configs outside of any ORM context.

---

### `_connect(conf)` — LDAP connection factory

```python
def _connect(self, conf):
    uri = 'ldap://%s:%d' % (conf['ldap_server'], conf['ldap_server_port'])
    connection = ldap.initialize(uri)

    # Optional: disable referral chasing
    ldap_chase_ref_disabled = self.env['ir.config_parameter'].sudo().get_param(
        'auth_ldap.disable_chase_ref')
    if str2bool(ldap_chase_ref_disabled):
        connection.set_option(ldap.OPT_REFERRALS, ldap.OPT_OFF)

    if conf['ldap_tls']:
        connection.start_tls_s()

    return LDAPWrapper(connection)
```

**`LDAPWrapper`** — Thin wrapper around `ldap.initialize()` result. Only exposes: `passwd_s`, `search_st`, `simple_bind_s`, `unbind`. Prevents accidental use of dangerous LDAP operations.

---

### `_authenticate(conf, login, password)` — The core auth method

```python
def _authenticate(self, conf, login, password):
    if not password:
        return False

    dn, entry = self._get_entry(conf, login)
    if not dn:
        return False

    try:
        conn = self._connect(conf)
        conn.simple_bind_s(dn, password)
        conn.unbind()
    except ldap.INVALID_CREDENTIALS:
        return False
    except ldap.LDAPError as e:
        _logger.error('An LDAP exception occurred: %s', e)
        return False

    return entry
```

**L4: The two-bind pattern:**
1. First bind: uses the service account (binddn/password from config) to search for the user DN.
2. Second bind: uses the found DN with the user's own password to verify credentials.

This prevents anonymous users from searching the directory. The filter is applied via `_get_entry()`.

---

### `_get_entry(conf, login)` — LDAP user lookup

```python
def _get_entry(self, conf, login):
    filter_tmpl = conf['ldap_filter']
    placeholders = filter_tmpl.count('%s')
    formatted_filter = filter_format(filter_tmpl, [login] * placeholders)
    results = self._query(conf, formatted_filter)

    results = [entry for entry in results if entry[0]]  # drop entries without DN
    if len(results) == 1:
        dn, entry = results[0]
        return dn, entry
    return False, False
```

**Security:** Only accepts exactly 1 result. Zero or multiple results → authentication fails. This prevents ambiguity attacks.

---

### `_map_ldap_attributes(conf, login, ldap_entry)` — User attribute mapping

```python
def _map_ldap_attributes(self, conf, login, ldap_entry):
    data = {
        'name': ldap_entry[1]['cn'][0],      # 'cn' attribute is required
        'login': login,
        'company_id': conf['company'][0]
    }
    if tools.single_email_re.match(login):
        data['email'] = login
    return data
```

**L4: What fields are populated:**

| Odoo Field | Source | Notes |
|------------|--------|-------|
| `name` | LDAP `cn` attribute | Required. If `cn` is missing, this will crash on `['cn'][0]`. |
| `login` | The login string typed by the user | Lowercased and stripped in `_get_or_create_user`. |
| `company_id` | From the LDAP config's `company` | If only one company, set automatically. |
| `email` | Set to `login` if `login` looks like an email | Uses `tools.single_email_re` regex. |
| `groups` | NOT mapped here | See note below. |
| `active` | Set to `True` if template user is configured | See `_get_or_create_user`. |

**Important gap:** There is NO built-in group mapping. The `groups` field from LDAP is not read from the LDAP entry and not mapped to Odoo groups. This must be implemented via custom `_get_or_create_user` override or by adding a `groups` field to `res.company.ldap`.

---

### `_get_or_create_user(conf, login, ldap_entry)` — User provisioning

```python
def _get_or_create_user(self, conf, login, ldap_entry):
    login = login.lower().strip()
    self.env.cr.execute("SELECT id, active FROM res_users WHERE lower(login)=%s", (login,))
    res = self.env.cr.fetchone()

    if res:
        if res[1]:  # active
            return res[0]
        # inactive existing user: do not reactivate via LDAP
    elif conf['create_user']:
        _logger.debug("Creating new Odoo user \"%s\" from LDAP" % login)
        values = self._map_ldap_attributes(conf, login, ldap_entry)
        SudoUser = self.env['res.users'].sudo().with_context(no_reset_password=True)
        if conf['user']:
            # Copy template user, override name/login/company
            values['active'] = True
            return SudoUser.browse(conf['user'][0]).copy(default=values).id
        else:
            # Minimal create: only name, login, company
            return SudoUser.create(values).id

    raise AccessDenied(_("No local user found for LDAP login and not configured to create one"))
```

**L4: Key behaviors:**
- Login is **lowercased and stripped** before lookup — LDAP `john.doe` and `John.Doe` are the same user.
- Inactive local users are NOT reactivated by LDAP login — if `res_users.active = False`, LDAP login is rejected even with valid credentials.
- Template user: if set in `user` field, the new user inherits all groups and settings from the template. This is the primary mechanism for assigning LDAP users to Odoo groups.
- `no_reset_password=True` context prevents the password reset email from being triggered during user creation.

---

### `_change_password(conf, login, old_passwd, new_passwd)` — LDAP password change

```python
def _change_password(self, conf, login, old_passwd, new_passwd):
    changed = False
    dn, entry = self._get_entry(conf, login)
    if not dn:
        return False
    try:
        conn = self._connect(conf)
        conn.simple_bind_s(dn, old_passwd)
        conn.passwd_s(dn, old_passwd, new_passwd)
        changed = True
        conn.unbind()
    except ldap.INVALID_CREDENTIALS:
        pass
    except ldap.LDAPError as e:
        _logger.error('An LDAP exception occurred: %s', e)
    return changed
```

**Requirements:** The LDAP server must allow the user to modify their own password via the LDAP `passwd_s` extended operation. This typically requires the server to allow simple binds with the user's own DN.

---

## `res.config.settings` — LDAP in Settings UI

Extended to surface the LDAP One2many in the general settings view.

**Inheritance:** `_inherit = 'res.config.settings'`

```python
ldaps = fields.One2many(related='company_id.ldaps', string="LDAP Parameters", readonly=False)
```

This makes the LDAP configurations editable from `Settings > General Settings > LDAP Parameters`.

---

## L4: Authentication Flow Diagrams

### Fresh user login (never logged in before)

```
User submits login + password at /web/login
    → res.users._login()
        → super()._login() raises AccessDenied
        → Check: user exists in res_users? NO
        → For each LDAP config (in sequence order):
            → Ldap._get_entry(conf, login)    # search for user DN
            → Ldap._authenticate(conf, login, password)  # bind with user DN
            → If entry found:
                → Ldap._get_or_create_user(conf, login, entry)
                    → Ldap._map_ldap_attributes()  # get name/email
                    → Create res.users record (active=True if template user set)
                → Return {'uid': <new_user_id>, 'auth_method': 'ldap', 'mfa': 'default'}
```

### Existing LDAP user re-authenticates

```
User submits login + password
    → res.users._login()
        → super()._login() raises AccessDenied
        → Check: user exists in res_users? YES (but password wrong)
        → super()._login() raises AccessDenied again → re-raised
        → LDAP fallback is NOT tried (because user exists locally)
```

### In-session credential re-check (e.g., sensitive operation)

```
User attempts sensitive action
    → _check_credentials(password)
        → super()._check_credentials() raises AccessDenied
        → If user.active and LDAP config exists:
            → Ldap._authenticate(user.login, password)
            → If LDAP auth succeeds: return success
        → Else: re-raise AccessDenied
```

---

## L4: Group Mapping (Custom Implementation Required)

Odoo `auth_ldap` does NOT include built-in LDAP-to-Odoo group mapping. To implement it:

```python
class CompanyLDAP(models.Model):
    _inherit = 'res.company.ldap'

    ldap_mapping_ids = fields.One2many('res.company.ldap.mapping', 'ldap_id')

    def _get_or_create_user(self, conf, login, ldap_entry):
        user_id = super()._get_or_create_user(conf, login, ldap_entry)

        # Custom: map LDAP groups to Odoo groups
        SudoUser = self.env['res.users'].sudo()
        user = SudoUser.browse(user_id)

        for mapping in self.browse(conf['id']).ldap_mapping_ids:
            if mapping._ldap_group_matches_user(ldap_entry):
                user.write({'groups_id': [(4, mapping.odoo_group_id.id)]})

        return user_id
```

---

## Security Considerations

1. **LDAP password stored in clear text** in `res.company.ldap`. Use a dedicated read-only service account.
2. **No LDAP group mapping** — must be custom-coded to map LDAP `memberOf` to Odoo `res.groups`.
3. **Anonymous bind** is possible (leave `ldap_binddn` empty) but should only be used when the directory allows unauthenticated search.
4. **`auth_ldap.disable_chase_ref`** — disable referral chasing to prevent directory traversal attacks.
5. **`ldap_tls`** — always enable STARTTLS in production to prevent credential interception.
6. **`python-ldap`** must be installed: `pip install python-ldap`. This is a C-extension library with system-level dependencies.

---

## See Also

- [Patterns/Security Patterns](Patterns/Security-Patterns.md) — ACL and ir.rule
- [Core/API](Core/API.md) — `@api.model` context and sudo usage
- [Modules/base_setup](Modules/base_setup.md) — `res.config.settings` pattern
