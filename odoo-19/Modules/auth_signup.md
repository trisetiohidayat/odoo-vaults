# auth_signup

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `auth_signup` |
| **Category** | `Hidden/Tools` |
| **License** | LGPL-3 |
| **Auto Install** | `True` |
| **Author** | Odoo S.A. |
| **Version** | `1.0` |

## Description

Enables self-service user registration and password reset. Allows unauthenticated visitors to create an account (B2C mode) or administrators to invite users by email (B2B mode). Provides the token-based invitation flow and all related email templates.

This module is **`bootstrap: True`** — it is loaded during the initial database creation — and auto-installs with `base_setup`, `mail`, and `web`.

---

## Dependencies

| Module | Reason |
|--------|--------|
| `base_setup` | Provides template user config (`base.template_portal_user_id`) and settings UI |
| `mail` | Sends invitation/reset emails via `mail.mail` |
| `web` | Provides the web login controller and session management |

---

## Configuration Parameters (`ir.config_parameter`)

| Key | Default | Description |
|-----|---------|-------------|
| `auth_signup.invitation_scope` | `b2c` | Controls registration mode: `b2c` = free signup, `b2b` = invitation only |
| `auth_signup.reset_password` | `True` | Enables the "Reset Password" link on the login page |
| `auth_signup.signup.validity.hours` | `144` (6 days) | Token expiry for new signup invitations |
| `auth_signup.reset_password.validity.hours` | `4` | Token expiry for password reset flows |
| `base.template_portal_user_id` | `False` | ID of the template `res.users` record used as the base for all new signups |

All parameters are set via the Settings UI (`res.config.settings`) or directly in `ir.config_parameter`.

---

## Models

### `res.partner` — Extended

**File:** `models/res_partner.py`

Inherits from `res.partner`. Adds signup token lifecycle management. The module does **not** store a plaintext signup token — instead it generates a cryptographically signed payload via HMAC-SHA256 (`tools.hash_sign`).

#### Fields

| Field | Type | Access | Description |
|-------|------|--------|-------------|
| `signup_type` | `Char` | `groups="base.group_erp_manager"` | Token type: `'signup'` (new user invitation), `'reset'` (password reset), or `False` (no pending token). Cleared immediately on token use. The `groups` restriction means only ERP managers can read it via ORM, but the value is still visible in the database. |

Note: Unlike older Odoo versions, `signup_token` (plaintext token) and `signup_expiration` (Date) fields no longer exist on this model. Token validity is now encoded directly into the signed payload and verified cryptographically at use time.

#### Methods

##### `signup_prepare(signup_type="signup")`

```python
def signup_prepare(self, signup_type="signup"):
    self.write({'signup_type': signup_type})
    return True
```

Sets `signup_type` on the partner to trigger a pending token. Called by:
- `action_reset_password()` on `res.users` — sets `signup_type = 'reset'`
- Admin portal invitation — sets `signup_type = 'signup'`
- Internal user creation via `create()` — sets `signup_type = 'signup'`

Does **not** generate the token immediately. The token is generated lazily in `_generate_signup_token()` when the URL is requested, so the expiration clock starts at URL-generation time, not invitation time. This is a key Odoo 18→19 change that replaced the old `signup_expiration` Date field.

##### `signup_cancel()`

```python
def signup_cancel(self):
    return self.write({'signup_type': None})
```

Cancels any pending signup by clearing `signup_type`. Called by:
- `res.users.write()` when archiving a user (`active=False`)
- `res.users._ondelete_signup_cancel()` on user deletion
- Failed `MailDeliveryException` during user creation

##### `action_signup_prepare()`

Wrapper action method. Returns the result of `signup_prepare()`.

##### `_generate_signup_token(expiration=None)`

```python
def _generate_signup_token(self, expiration=None):
    self.ensure_one()
    if not expiration:
        if self.signup_type == 'reset':
            expiration = int(self.env['ir.config_parameter'].get_param(
                "auth_signup.reset_password.validity.hours", 4))
        else:
            expiration = int(self.env['ir.config_parameter'].get_param(
                "auth_signup.signup.validity.hours", 144))
    plist = [self.id, self.user_ids.ids, self._get_login_date(), self.signup_type]
    payload = tools.hash_sign(self.sudo().env, 'signup', plist, expiration_hours=expiration)
    return payload
```

Generates the HMAC-signed token (similar to JWT but using HMAC-SHA256). The payload is the list: `[partner_id, user_ids, login_date, signup_type]`. Key behavior:

- **Token invalidation on login**: `login_date` is part of the signed payload. As soon as the user logs in and their `login_date` is updated, the token becomes invalid because `verify_hash_signed` will compare the token's `login_date` against the live `_get_login_date()` — they will no longer match.
- **Token invalidation on user count change**: If `user_ids.ids` changes (new user added or existing user deleted), the token is immediately invalidated. This prevents the same invitation token from being used to create multiple accounts.
- **`signup_type` in payload**: If the token type changes (e.g., from `'signup'` to `'reset'`), the original token is invalidated.
- **Expiration**: Encoded as an absolute Unix timestamp in the token. `hash_sign` uses `expiration_hours` to compute the timestamp internally.

Called by `_get_signup_url_for_action()` to embed in the URL.

##### `_get_login_date()`

```python
def _get_login_date(self):
    self.ensure_one()
    users_login_dates = self.user_ids.mapped('login_date')
    users_login_dates = list(filter(None, users_login_dates))  # remove falsy values
    if any(users_login_dates):
        return int(max(map(datetime.timestamp, users_login_dates)))
    return None
```

Returns the **latest** login timestamp (as Unix integer) across all users linked to this partner, or `None` if no user has ever logged in. Used as part of the token payload for invalidation.

##### `_get_partner_from_token(token)`

```python
@api.model
def _get_partner_from_token(self, token):
    if payload := tools.verify_hash_signed(self.sudo().env, 'signup', token):
        partner_id, user_ids, login_date, signup_type = payload
        partner = self.browse(partner_id)
        if login_date == partner._get_login_date() and \
           partner.user_ids.ids == user_ids and \
           signup_type == partner.browse(partner_id).signup_type:
            return partner
    return None
```

Verifies and decodes a signed token. The verification chain:

1. `tools.verify_hash_signed()` — cryptographically verifies HMAC signature and checks timestamp expiry
2. Re-validates `login_date` matches current `_get_login_date()` — invalidates token after first login
3. Re-validates `user_ids` match current `partner.user_ids.ids` — invalidates if user list changes
4. Re-validates `signup_type` matches current `partner.signup_type` — invalidates if type changed or cleared

This multi-layer check replaces the old `signup_expiration` date-based expiry. It is more secure because tampering or timing changes are detected.

##### `_signup_retrieve_partner(token, check_validity=False, raise_exception=False)`

```python
@api.model
def _signup_retrieve_partner(self, token, check_validity=False, raise_exception=False):
    partner = self._get_partner_from_token(token)
    if not partner:
        raise exceptions.UserError(_("Signup token '%s' is not valid or expired", token))
    return partner
```

Wrapper. If `check_validity=True` it calls `_get_partner_from_token()` (which does the full validity check). Called by `res.users.signup()` when a token is provided.

##### `_signup_retrieve_info(token)`

```python
@api.model
def _signup_retrieve_info(self, token):
    partner = self._get_partner_from_token(token)
    if not partner:
        return None
    res = {'db': self.env.cr.dbname}
    res['token'] = token
    res['name'] = partner.name
    if partner.user_ids:
        res['login'] = partner.user_ids[0].login
    else:
        res['email'] = res['login'] = partner.email or ''
    return res
```

Returns partner info for rendering the signup/reset password form. Used by `get_auth_signup_qcontext()` in the controller. Returns `None` for an invalid token (controller then shows "Invalid signup token" error).

##### `_get_signup_url()` / `_get_signup_url_for_action(url=None, action=None, ...)`

```python
def _get_signup_url(self):
    self.ensure_one()
    result = self.sudo()._get_signup_url_for_action()
    # access control checks...
    return result.get(self.id, False)

def _get_signup_url_for_action(self, url=None, action=None, view_type=None,
                               menu_id=None, res_id=None, model=None):
```

Generates the full invitation/reset URL. Context-driven behavior:
- `create_user` context → adds `signup_email` query param
- `signup_valid` context + no existing user → calls `signup_prepare()` first
- `signup_force_type_in_url` context → forces the route (e.g., `'reset'` → `/web/reset_password`)

Route determination: if `signup_type == 'reset'` → `/web/reset_password`, any other truthy type → that type (e.g., `'signup'` → `/web/signup`), default → `/web/login`.

The URL always includes `db`, `token`, and optionally `redirect` and `signup_email` query params.

##### `signup_get_auth_param()`

```python
def signup_get_auth_param(self):
    if not self.env.user._is_internal() and not self.env.is_admin():
        raise exceptions.AccessDenied()
    res = defaultdict(dict)
    allow_signup = self.env['res.users']._get_signup_invitation_scope() == 'b2c'
    for partner in self:
        partner = partner.sudo()
        if allow_signup and not partner.user_ids:
            partner.signup_prepare()
            res[partner.id]['auth_signup_token'] = partner._generate_signup_token()
        elif partner.user_ids:
            res[partner.id]['auth_login'] = partner.user_ids[0].login
    return res
```

Used by portal/mail controllers to generate shareable auth links. Returns a token only if `invitation_scope == 'b2c'` and the partner has no existing user. Requires internal user or admin. Used by `portal.portal_share()` and similar.

---

### `res.users` — Extended

**File:** `models/res_users.py`

Inherits from `res.users`. Drives user creation from templates, password reset, and invitation emails.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `state` | `Selection` (computed, searchable) | `'new'` if `login_date` is falsy, `'active'` if the user has logged in at least once. Used in UI to show "Invited" vs "Confirmed" status. |

The `state` field is **not stored**. It uses a custom `search='_search_state'` that works on the negated domain `log_ids` relation — a user without a `login_date` has no `log_ids` entry matching `'log_ids' != False`.

#### Methods

##### `signup(values, token=None)`

```python
@api.model
def signup(self, values, token=None):
    """ signup a user, to either:
        - create a new user (no token), or
        - create a user for a partner (with token, but no user for partner), or
        - change the password of a user (with token, and existing user).
        :param values: a dictionary with field values that are written on user
        :param token: signup token (optional)
        :return: (dbname, login, password) for the signed up user
    """
```

Three-branch logic:

**With token:**
1. Retrieves the partner via `_signup_retrieve_partner(token, check_validity=True)` — raises `UserError` if invalid/expired
2. Clears `partner.signup_type` immediately (token is consumed)
3. If partner already has a user → writes new values (password change via reset link)
4. If partner has no user → creates a new user via `_signup_create_user()`
5. If user was previously invited but never logged in → calls `_notify_inviter()` to notify the inviter in real time via bus

**Without token (B2C free signup):**
- Requires `invitation_scope == 'b2c'` — checked in `_signup_create_user()`
- Creates user directly

Returns `(login, password)` tuple.

##### `_get_signup_invitation_scope()`

```python
@api.model
def _get_signup_invitation_scope(self):
    return self.env['ir.config_parameter'].sudo().get_param(
        'auth_signup.invitation_scope', 'b2b')
```

Reads `auth_signup.invitation_scope` config. Defaults to `'b2b'` (invitation only).

##### `_signup_create_user(values)`

```python
@api.model
def _signup_create_user(self, values):
    # check that uninvited users may sign up
    if 'partner_id' not in values:
        if self._get_signup_invitation_scope() != 'b2c':
            raise SignupError(_('Signup is not allowed for uninvited users'))
    return self._create_user_from_template(values)
```

Bouncer for free signup: raises `SignupError` if `partner_id` is not in `values` and scope is not `b2c`. Delegates to `_create_user_from_template()`.

##### `_create_user_from_template(values)`

```python
def _create_user_from_template(self, values):
    template_user_id = literal_eval(
        self.env['ir.config_parameter'].sudo().get_param(
            'base.template_portal_user_id', 'False'))
    template_user = self.browse(template_user_id)
    if not template_user.exists():
        raise ValueError(_("Signup: invalid template user"))
    ...
    values['active'] = True
    try:
        with self.env.cr.savepoint():
            return template_user.with_context(no_reset_password=True).copy(values)
    except Exception as e:
        raise SignupError(str(e))
```

Core user creation: reads `base.template_portal_user_id` from config (default `False`), validates it exists, then copies it with `no_reset_password=True` context to suppress the email trigger on copy. The `copy()` operation inherits all groups/rights from the template user — this is the mechanism by which new portal users get their default access rights. Raises `SignupError` if login is already taken (copy fails due to unique constraint on `login`).

##### `reset_password(login)`

```python
def reset_password(self, login):
    users = self.search(self._get_login_domain(login))
    if not users:
        users = self.search(self._get_email_domain(login))
    if not users:
        raise Exception(_("No account found for this login"))
    if len(users) > 1:
        raise Exception(_("Multiple accounts found for this login"))
    return users.action_reset_password()
```

Public-facing entry point. Looks up user by login first, then by email. Raises if zero or multiple matches. Delegates to `action_reset_password()`. Note: raises plain `Exception`, not `UserError` — the controller catches it.

##### `action_reset_password()`

```python
def action_reset_password(self):
    try:
        if self.env.context.get('create_user') == 1:
            return self._action_reset_password(signup_type="signup")
        else:
            return self._action_reset_password(signup_type="reset")
    except MailDeliveryException as mde:
        if len(mde.args) == 2 and isinstance(mde.args[1], ConnectionRefusedError):
            raise UserError(_("Could not contact the mail server..."))
        else:
            raise UserError(_("There was an error when trying to deliver your Email..."))
```

Context-driven dispatcher. `create_user=1` context flag means "new invitation" (sets `signup_type='signup'`). Otherwise "password reset" (`signup_type='reset'`). Also handles SMTP delivery failures with user-friendly messages.

##### `_action_reset_password(signup_type="reset")`

```python
def _action_reset_password(self, signup_type="reset"):
    if self.env.context.get('install_mode') or self.env.context.get('import_file'):
        return
    if self.filtered(lambda user: not user.active):
        raise UserError(_("You cannot perform this action on an archived user."))
    create_mode = bool(self.env.context.get('create_user'))
    self.mapped('partner_id').signup_prepare(signup_type=signup_type)
    # send email...
```

The heavy lifter. Steps:

1. **Skip in install/import mode** — no emails sent during data import or setup
2. **Guard archived users** — cannot reset password for inactive users
3. **Prepare partner token** — calls `signup_prepare(signup_type)` on all related partners
4. **Select email template**: uses `set_password_email` for internal users, `portal_set_password_email` for portal users, or falls back to inline template rendering
5. **Send per-user emails** inside individual savepoints (one failure does not block others)
6. **Return** `display_notification` action to show success message on client

Template selection logic (lines 167-178):
- If `create_mode=True` (new user): send `set_password_email` to internal users, `portal_set_password_email` to portal users
- If `create_mode=False` (reset): falls through to the inline template render path (no `set_password_email` or `portal_set_password_email`)

##### `_notify_inviter()`

```python
def _notify_inviter(self):
    for user in self:
        user.create_uid._bus_send(
            "res.users/connection",
            {"username": user.name, "partnerId": user.partner_id.id}
        )
```

Sends a real-time bus notification to the inviting user when a new user confirms their account. The inviting user sees a toast/banner in the Odoo interface indicating the new user has connected. Only sent if the invited user has never logged in before (checked in `signup()` before calling this).

##### `send_unregistered_user_reminder(after_days=5, batch_size=100)`

```python
def send_unregistered_user_reminder(self, *, after_days=5, batch_size=100):
    ...
    datetime_min = fields.Datetime.today() - relativedelta(days=after_days)
    datetime_max = datetime_min + relativedelta(days=1)
    invited_by_users = self.search_fetch([
        ('share', '=', False),
        ('create_uid.email', '!=', False),
        ('create_date', '>=', datetime_min),
        ('create_date', '<', datetime_max),
        ('log_ids', '=', False),  # no login yet
    ], ['name', 'login', 'create_uid']).grouped('create_uid')
    for user, invited_users in invited_by_users.items():
        ...
        template.send_mail(user.id, ...)
```

Daily CRON job target. Finds internal users created in the last day window with no `log_ids` (never logged in), groups by inviter, and sends the inviter a reminder with the list of pending invitations. Uses `search_fetch` with `grouped()` for efficiency.

Batch size of 100 controls the number of email operations per CRON tick.

##### `web_create_users(emails)` `@api.model`

```python
@api.model
def web_create_users(self, emails):
    inactive_users = self.search([
        ('state', '=', 'new'), '|', ('login', 'in', emails), ('email', 'in', emails)
    ])
    new_emails = set(emails) - set(inactive_users.mapped('email'))
    res = super().web_create_users(list(new_emails))
    if inactive_users:
        inactive_users.with_context(create_user=True).action_reset_password()
    return res
```

Overrides `base`/`web` method to handle duplicate invitation attempts. If a user was previously invited (state=`'new'`) and is reinvited with the same email, it resends the invitation instead of creating a duplicate. New emails go through normal `web_create_users()`.

##### `create(vals_list)` `@api.model_create_multi`

```python
@api.model_create_multi
def create(self, vals_list):
    users = super().create(vals_list)
    if not self.env.context.get('no_reset_password'):
        users_with_email = users.filtered('email')
        if users_with_email:
            try:
                users_with_email.with_context(create_user=True)._action_reset_password(
                    signup_type='signup')
            except MailDeliveryException:
                users_with_email.partner_id.with_context(create_user=True).signup_cancel()
    return users
```

**Automatic invitation on user creation.** When a user record is created programmatically (e.g., via admin UI or `res.users.create()`), if the context does not contain `no_reset_password`, the system automatically sends an invitation email via `_action_reset_password(signup_type='signup')`. If email delivery fails, the signup token is cancelled via `signup_cancel()`.

The `no_reset_password=True` context suppresses this behavior. It is used in `_create_user_from_template()` to prevent infinite recursion when copying the template user.

##### `write(vals)`

```python
def write(self, vals):
    if 'active' in vals and not vals['active']:
        self.partner_id.sudo().signup_cancel()
    return super().write(vals)
```

Cancels pending signup tokens when archiving a user. Uses `sudo()` because the partner access may be restricted.

##### `_ondelete_signup_cancel()` `@api.ondelete(at_uninstall=False)`

```python
@api.ondelete(at_uninstall=False)
def _ondelete_signup_cancel(self):
    for user in self:
        if user.partner_id:
            user.partner_id.signup_cancel()
```

Cleans up signup tokens when a user record is deleted. Uses `at_uninstall=False` so it does not block module uninstall.

##### `copy(default=None)`

```python
def copy(self, default=None):
    if not default or not default.get('email'):
        self = self.with_context(no_reset_password=True)
    return super().copy(default=default)
```

Suppresses invitation email when duplicating a user without specifying an email. If email is provided, the normal `create()` hook fires and sends an invitation to the copy's email.

---

### `res.config.settings` — Extended

**File:** `models/res_config_settings.py`

| Field | Type | Config Parameter | Description |
|-------|------|-----------------|-------------|
| `auth_signup_reset_password` | `Boolean` | `auth_signup.reset_password` | Toggles the "Reset Password" link on the login page |
| `auth_signup_uninvited` | `Selection` | `auth_signup.invitation_scope` | `b2b` (On invitation) or `b2c` (Free sign up) |
| `auth_signup_template_user_id` | `Many2one(res.users)` | `base.template_portal_user_id` | Template user whose groups/rights are copied to new signups |

The `auth_signup_uninvited` selection controls the `invitation_scope` parameter. In the Settings UI, the Template User link (`action_open_template_user`) is only shown when `auth_signup_uninvited == 'b2c'`.

---

## Controllers

**File:** `controllers/main.py`

### `AuthSignupHome` (extends `Home`)

#### `web_login()` — Overrides `Home`

Calls `super().web_login()`, then injects auth_signup config into the response's template context (`qcontext`). Adds `account_created=True` query param to the redirect when a new user has just registered.

#### `web_auth_signup()`

```
route: /web/signup
auth: public
website: True
sitemap: False
captcha: signup
```

1. Validates that signup is enabled (B2C scope or valid token present) — raises 404 otherwise
2. On `POST`: validates passwords match, calls `do_signup()`, sends `mail_template_user_signup_account_created`, then redirects to login
3. On `GET` with `signup_email` in params: checks if an existing active user has that email and redirects to login with prefilled credentials
4. Detects duplicate email registration and shows friendly error message

Special handling: if MFA is enabled (`request.session.uid is None` after `do_signup`), switches session to `base.public_user` instead of logging in automatically.

#### `web_auth_reset_password()`

```
route: /web/reset_password
auth: public
website: True
sitemap: False
captcha: password_reset
```

1. Validates that reset is enabled or a valid token is present — raises 404 otherwise
2. On `POST` with token: calls `do_signup()` with `do_login=False` (just updates password), shows success message
3. On `POST` without token: calls `reset_password(login)` to initiate email flow
4. On `GET` with `signup_email`: same redirect-to-login logic as signup

#### `get_auth_signup_config()`

Returns the three config booleans injected into all login-family templates:
- `disable_database_manager`: `not tools.config['list_db']`
- `signup_enabled`: `invitation_scope == 'b2c'`
- `reset_password_enabled`: `auth_signup.reset_password == 'True'`

#### `get_auth_signup_qcontext()`

Builds the rendering context for both signup and reset password pages. Merges:
- `SIGN_UP_REQUEST_PARAMS` from `web` module (login, name, password, confirm_password, token, signup_email, ...)
- Config from `get_auth_signup_config()`
- Token info from `_signup_retrieve_info()` (populated into context as `token`, `name`, `login`, `email`)

#### `_prepare_signup_values(qcontext)`

Extracts `login`, `name`, `password` from the form submission. Validates passwords match. Adds the user's preferred language if the browser lang is in the supported languages list.

#### `do_signup(qcontext, do_login=True)`

Orchestrates signup: prepares values, calls `_signup_with_values()`, commits the transaction, then optionally authenticates the session.

#### `_signup_with_values(token, values, do_login)`

Calls `sudo().signup()` on `res.users`, then either calls `request.session.authenticate()` or leaves the session as public user (for MFA flows).

### `AuthBaseSetup` (extends `BaseSetup`)

#### `base_setup_data()`

Adds `resend_invitation: True` to the base setup data response. Used by the frontend to enable "Resend Invitation" buttons.

---

## Token Security Architecture (L4)

### The `tools.hash_sign` / `tools.verify_hash_signed` System

The token system uses HMAC-SHA256-signed, URL-safe encoded payloads. This replaced the old Odoo 17 approach of storing plaintext tokens and expiry dates directly on the partner record.

**Token structure (binary, then base64-encoded):**
```
[version: 1 byte = \x01]
[expiration_timestamp: 8 bytes little-endian Unix timestamp]
[HMAC-SHA256 signature: 32 bytes]
[JSON-encoded message_values: variable]
```

**Message values for signup:**
```python
[partner_id, user_ids, login_date, signup_type]
```

**HMAC key**: derived from `ir.config_parameter` `database.secret` (set at database creation) + scope `'signup'`.

**Security properties:**
- Token is cryptographically signed — cannot be forged without the database secret
- Token expiry is baked into the signature — cannot be extended by modifying the timestamp
- `login_date` in payload invalidates token on first login
- `user_ids` in payload invalidates token if the invited user list changes
- `signup_type` in payload invalidates token if the token type changes (e.g., reset→used→clear)

### `_get_partner_from_token` Validity Chain

```
tools.verify_hash_signed()     ← HMAC + timestamp expiry
         ↓ (decodes payload)
[partner_id, user_ids, login_date, signup_type]
         ↓
self.browse(partner_id)        ← partner still exists?
         ↓
login_date == self._get_login_date()     ← user hasn't logged in yet?
         ↓
self.user_ids.ids == user_ids            ← user list unchanged?
         ↓
self.signup_type == signup_type           ← token type not cleared/changed?
         ↓
return partner
```

### Token Lifecycle

```
Admin creates user
  → res.users.create()
    → _action_reset_password(signup_type='signup')
      → partner.signup_prepare(signup_type='signup')
      → Email sent with _generate_signup_token()

User clicks link
  → _get_partner_from_token(token)
    → verify_hash_signed()      [valid: HMAC OK, not expired]
    → checks login_date, user_ids, signup_type  [valid: all match]
    → returns partner

User submits password
  → signup(values, token)
    → _signup_retrieve_partner(token)  [partner found]
    → partner.write({signup_type: False})  [token consumed]
    → user exists? → write new password
    → user doesn't exist? → _signup_create_user()
```

### Token Storage vs Signed Payload (L4)

The critical architectural shift from Odoo 17→18→19:

| Aspect | Odoo 17 (Stored Token) | Odoo 18/19 (Signed Payload) |
|--------|------------------------|----------------------------|
| Token location | `res.partner.signup_token` (DB column) | URL parameter only |
| Expiry check | SQL: `signup_expiration >= TODAY` | HMAC timestamp verification |
| Invalidation | Manual clear or expiry date | Automatic on login/user changes |
| Tampering | Token string could be modified in DB | Signature invalidation on any change |
| `login_date` support | Not in token payload | Part of signed payload — instant invalidate on login |
| Multiple invitations | Same token reused | Each invitation generates a new token |

The signed payload approach means the token itself carries all necessary validity state. Even if an attacker reads the token from an email log or browser history, they cannot extend its expiry or change its payload without invalidating the HMAC signature.

---

## Email Templates

| Template ID | Purpose | Triggered When |
|-------------|---------|---------------|
| `set_password_email` | New internal user invitation | Admin creates internal user via UI (`create_user=True`) |
| `portal_set_password_email` | New portal user invitation | Admin creates portal user via UI (`create_user=True`) |
| `reset_password_email` | Password reset (inline render) | User clicks "Reset Password" without token |
| `mail_template_data_unregistered_users` | Unregistered user reminder | Daily CRON `send_unregistered_user_reminder` |
| `mail_template_user_signup_account_created` | Self-registration confirmation | B2C user completes free signup |

All templates have `auto_delete: True` to prevent mailbox clutter.

---

## Cron Jobs

| Cron | Model | Frequency | Description |
|------|-------|-----------|-------------|
| `ir_cron_auth_signup_send_pending_user_reminder` | `res.users` | Daily (`interval_type: days`) | Sends reminders to admins who invited users that haven't registered within 5 days. Priority 6 (low). |

The cron calls `send_unregistered_user_reminder(after_days=5, batch_size=100)` using `base.user_root` as the executing user.

---

## Views

| View | Inherits | Purpose |
|------|---------|---------|
| `res_users_view_form` | `base.view_users_form` | Adds "Send an Invitation Email" button (state='new') and "Send Password Reset" button (state='active') to the user form header |
| `view_users_state_tree` | `base.view_users_tree` | Adds `state` column as a badge (info='new', success='active') in the user list |
| `action_send_password_reset_instructions` | — | Server action bound to `res.users` for bulk password reset |
| `res_config_settings_view_form.inherit.auth.signup` | `base_setup.res_config_settings_view_form` | Injects auth_signup settings panel before access rights section |

---

## Edge Cases and Failure Modes

| Scenario | Behavior |
|----------|----------|
| Token expired | `verify_hash_signed()` returns `None` → `_get_partner_from_token()` returns `None` → `_signup_retrieve_partner()` raises `UserError("Signup token ... is not valid or expired")` |
| User already logged in | `login_date` in token no longer matches live `_get_login_date()` → token invalidated → must request new reset link |
| Email delivery failure on user creation | `MailDeliveryException` caught in `create()` → `signup_cancel()` called on partner → user record exists but has no valid token |
| Duplicate signup attempt (same email) | `copy()` on template fails due to unique constraint on `login` → `SignupError` raised → controller catches and shows "Another user is already registered using this email address" |
| Multiple users with same email | `reset_password()` raises `Exception("Multiple accounts found for this login")` → caught as generic `Exception` → shows "Could not reset your password" |
| B2B mode trying to free signup | `_signup_create_user()` raises `SignupError('Signup is not allowed for uninvited users')` → caught by controller → shows "Could not create a new account" |
| User deleted before clicking invitation link | Token verifies cryptographically but `_get_partner_from_token()` returns `None` (partner browse returns empty recordset) |
| Token used twice | First use clears `signup_type` → second use finds `signup_type` mismatch → token invalidated |
| SMTP server down | `MailDeliveryException` raised → `action_reset_password()` catches it and raises `UserError` with mail server configuration guidance |
| Copying user without email | `no_reset_password=True` context suppresses email sending in `create()` |
| Archiving user | `write({'active': False})` calls `signup_cancel()` on partner → any pending invitation is cancelled |
| Deleting user | `_ondelete_signup_cancel()` cancels signup on partner → no partner-level cleanup needed |
| MFA-enabled user completes signup | Session kept as `base.public_user` instead of logging in automatically; user must complete MFA step separately |
| Same partner invited twice as different user types | Two separate `signup_type` values overwrite each other — second invitation invalidates the first token (same partner, different type = payload mismatch) |

---

## Performance Considerations (L4)

### Token Generation Performance

```python
# _generate_signup_token() — no database queries
payload = tools.hash_sign(self.sudo().env, 'signup', plist, expiration_hours=expiration)
```

`hash_sign()` uses HMAC-SHA256 and base64 encoding. The only inputs are the partner ID, user IDs (already in memory via `self.user_ids.ids`), the login date, and the `signup_type`. No SQL queries are executed. This operation is sub-millisecond.

### Token Verification Performance

```python
# _get_partner_from_token() — 1 DB query only after HMAC passes
payload = tools.verify_hash_signed(self.sudo().env, 'signup', token)
partner = self.browse(partner_id)  # The only DB query in the happy path
```

The `verify_hash_signed()` call is pure Python cryptography — no database access. Only after the HMAC is validated does Odoo perform a `browse(partner_id)`. If the token is invalid (wrong HMAC or expired), no database query is made at all. This is significantly more efficient than the Odoo 17 approach which required reading the stored `signup_token` and `signup_expiration` columns first.

### User Creation Performance

```python
# _create_user_from_template() — one savepoint + one copy() operation
with self.env.cr.savepoint():
    return template_user.with_context(no_reset_password=True).copy(values)
```

The `copy()` operation on a `res.users` record is O(n) in the number of fields on the user model. For the default Odoo installation this is fast. The `no_reset_password=True` context prevents the `create()` hook from firing, avoiding an additional email operation.

### Batch Invitation Performance

The `send_unregistered_user_reminder` CRON uses `search_fetch()` with `grouped()`:

```python
self.search_fetch([...], ['name', 'login', 'create_uid']).grouped('create_uid')
```

This is a single SQL query that fetches all needed columns in one pass, then groups the results in Python (no N+1 queries). The CRON processes up to 100 invitations per tick, sending emails via `template.send_mail()` in a loop. Each `send_mail` is an individual SMTP transaction, but failures are isolated by the loop structure.

### Scalability Characteristics

| Operation | Scaling Behavior | Notes |
|-----------|-----------------|-------|
| Token generation | O(1) | No DB, pure HMAC |
| Token verification | O(1) | HMAC + 1 browse |
| User creation | O(k) where k = number of user fields | `copy()` inherits k fields |
| Invitation email send | O(n) emails = n SMTP calls | Batched by CRON ticks (100 per tick) |
| Pending invitation cleanup | O(1) | `signup_cancel()` is a single write |

---

## Odoo 18 → 19 Changes (L4)

### Security Architecture Changes

| Before (Odoo 17/18) | After (Odoo 19) | Why It Changed |
|---------------------|-----------------|---------------|
| `signup_token` (Char) stored on `res.partner` | No stored token — signed payload via `hash_sign` | Eliminates token tampering and expiry manipulation risk |
| `signup_expiration` (Date) stored on `res.partner` | Expiry baked into HMAC-signed token; no DB column | Prevents manual expiry extension via SQL |
| Token validated by checking `signup_token` equality + expiry date | Token validated by `verify_hash_signed` HMAC + inline checks | Multi-layer invalidation (login, user count, type) |
| `signup_valid` field on partner | Replaced by `signup_type` Char field | Cleaner state machine: `False` = no pending token, `signup`/`reset` = active |

### Functional Changes

| Change | Detail |
|--------|--------|
| Token generation timing | Odoo 17: token generated in `signup_prepare()` and stored. Odoo 19: token generated lazily in `_generate_signup_token()` at URL-generation time. Expiry clock now starts at URL-generation, not invitation time. |
| Default `invitation_scope` | Changed from `b2b` to `b2c` (free signup by default) |
| `_notify_inviter()` | Added in Odoo 19. Real-time bus notification to inviting user when new user activates account |
| `send_unregistered_user_reminder` CRON | Added in Odoo 19. Daily reminder to admins for pending invitations |
| `state` field on `res.users` | Added in Odoo 19. Computed `'new'`/`'active'` with custom search for UI status tracking |
| `account_created_email` template | Added in Odoo 19. Confirmation email for B2C self-registration |
| `SignupError` exception | Added in Odoo 19. Module-level exception class defined in `res_partner.py` |
| `web_create_users` override | Added in Odoo 19. Handles re-invitation of existing `'new'` state users |
| `copy()` suppression | Added in Odoo 19. `no_reset_password=True` context on email-less user copies |
| MFA flow handling | Added in Odoo 19. When MFA is enabled, session kept as `base.public_user` after signup instead of auto-login |

### Database Schema Changes

| Odoo 17 Column | Odoo 19 Status |
|----------------|---------------|
| `res.partner.signup_token` | **Removed** |
| `res.partner.signup_expiration` | **Removed** |
| `res.partner.signup_valid` | **Removed** |
| `res.partner.signup_type` | **Added** (Char, groups-restricted) |
| `res.users.state` | **Added** (computed, searchable) |

### API Compatibility

- `res.partner.signup_prepare()` signature unchanged
- `res.users.signup()` signature unchanged
- `res.users.reset_password()` signature unchanged
- `res.users.action_reset_password()` signature unchanged — behavior extended via `create_user` context flag
- No migration script needed: removed columns are dropped, added columns are created with NULL defaults

---

## Related Modules

- [Modules/auth_oauth](auth_oauth.md) — OAuth-based authentication (separate auth provider)
- [Modules/auth_totp](auth_totp.md) — Two-factor authentication
- [Modules/mail](mail.md) — Email delivery for invitations
- [Modules/base_setup](base_setup.md) — Settings UI and template user configuration
- [Modules/portal](portal.md) — Portal access management and sharing
- [Modules/web](web.md) — Web login controller and session management
