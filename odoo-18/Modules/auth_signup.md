# auth_signup — Self-Service User Registration and Password Reset

**Module:** `auth_signup`
**Odoo Version:** 18
**Source:** `~/odoo/odoo18/odoo/addons/auth_signup/`

---

## Overview

The `auth_signup` module provides self-service user registration and password reset functionality for Odoo. It generates cryptographically secure signup tokens, manages invitation flows, and integrates with `res.partner` to handle the complete user creation lifecycle from email invitation to first login.

---

## Architecture

### Model Structure

```
res.partner              # Extended: signup token fields and methods
res.users                # Extended: signup, reset, create from template
auth.signup.vals         # (transient, optional — not present in core)
```

### File Map

| File | Purpose |
|------|---------|
| `models/res_partner.py` | Partner signup token fields and URL generation |
| `models/res_users.py` | User signup/reset flows and template creation |

---

## Token Security Architecture

### random_token()

Generates a 20-character cryptographically secure random token using `random.SystemRandom()`:

```python
chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
# 6 bits/char × 20 chars = 120 bits of entropy
return ''.join(random.SystemRandom().choice(chars) for _ in range(20))
```

### Signed Token System

Starting in recent Odoo versions, tokens are **signed payloads** rather than simple random strings. The system uses `tools.hash_sign()` and `tools.verify_hash_signed()`.

#### `_generate_signup_token(expiration=None)`

Creates a signed token payload containing:
```python
plist = [partner_id, user_ids, login_date, signup_type]
payload = hash_sign('signup', plist, expiration_hours=expiration)
return payload
```

- **Expiration for `reset` type:** Read from `auth_signup.reset_password.validity.hours` config (default 4 hours)
- **Expiration for `signup` type:** Read from `auth_signup.signup.validity.hours` config (default 144 hours / 6 days)

#### `_get_partner_from_token(token)`

Verifies and decodes a signed token:
1. Calls `verify_hash_signed('signup', token)` to decode the payload
2. Validates `partner_id` still matches
3. Validates `user_ids` still matches (no new users added to partner)
4. Validates `login_date` unchanged (token invalidated on login)
5. Validates `signup_type` matches current partner state

If any check fails → returns `None` (expired or tampered token).

---

## res.partner — Signup Extension

**Model:** `res.partner`
**Inheritance:** Extends `res.partner`

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `signup_type` | `Char` | Current token type: `'signup'`, `'reset'`, or `False`. Copy=False, guarded with `groups="base.group_erp_manager"` |

### Key Methods

**`signup_prepare(signup_type="signup")`**

Writes `signup_type` to the partner record. Called before token generation:
```python
def signup_prepare(self, signup_type="signup"):
    self.write({'signup_type': signup_type})
    return True
```

**`signup_cancel()`**

Clears the signup type:
```python
def signup_cancel(self):
    return self.write({'signup_type': None})
```

**`_get_signup_url_for_action(url, action, view_type, menu_id, res_id, model)`**

Generates a signup URL for the partner. Key logic:
1. If `context['signup_valid']` and partner has no user → calls `signup_prepare()`
2. If `context['create_user']` → embeds partner's email as `signup_email` query param
3. Determines route: `'login'`, `'reset_password'`, or the `signup_type` value itself
4. Generates signed token via `_generate_signup_token()`
5. Encodes redirect URL and token into `/web/{route}?db=...&token=...&redirect=...`

**`_signup_retrieve_partner(token, check_validity, raise_exception)`**

Looks up the partner for a given token:
```python
def _signup_retrieve_partner(self, token, ...):
    partner = self._get_partner_from_token(token)
    if not partner:
        raise exceptions.UserError(_("Signup token ... is not valid or expired"))
    return partner
```

**`_signup_retrieve_info(token)`**

Returns a dict with token validity info:
```python
{
    'db': dbname,
    'token': token,          # Only if valid
    'name': partner.name,
    'login': user.login,     # If user already exists
    'email': partner.email,  # If no user yet
}
```

Returns `None` if token is invalid.

**`signup_get_auth_param()`**

Used by the web client to get auth parameters for a partner:
- If B2C mode and no user exists → creates signup token, returns `auth_signup_token`
- If user exists → returns `auth_login` (the existing login)

**`_get_login_date()`**

Returns the most recent `login_date` of all users linked to this partner, as a Unix timestamp integer. This is included in the signed token — if the user logs in, the token is invalidated.

---

## res.users — Signup Extension

**Model:** `res.users`
**Inheritance:** Extends `res.users`

### Additional Field

| Field | Type | Description |
|-------|------|-------------|
| `state` | `Selection` | Computed: `'new'` (never connected) or `'active'` (has logged in). Uses `_search_state()` for filtering |

### Key Methods

**`signup(values, token=None)`**

Main signup entry point. Handles three scenarios:

1. **Token + existing user:** Reset password (invalidate token, write new password)
2. **Token + no user:** Create user from partner (create user linked to partner)
3. **No token:** Direct signup (B2C only — requires `auth_signup.invitation_scope == 'b2c'`)

```python
if token:
    partner = self._signup_retrieve_partner(token, check_validity=True, ...)
    partner.write({'signup_type': False})  # Invalidate token

    if partner_user:  # User already exists
        partner_user.write(values)  # Update (e.g., set password)
    else:              # Create user
        values.update({'name': partner.name, 'partner_id': partner.id})
        partner_user = self._signup_create_user(values)
else:
    # Direct signup (B2C only)
    self._signup_create_user(values)
```

**`_signup_create_user(values)`**

Validates signup is allowed for uninvited users (B2B vs B2C scope), then delegates to `_create_user_from_template()`.

**`_create_user_from_template(values)`**

Creates a new user by copying a template user (`base.template_portal_user_id`):
1. Reads template user ID from `ir.config_parameter`
2. Validates required fields: `login`, `partner_id` or `name`
3. Copies template user with `no_reset_password=True` context
4. Returns the new user record

```python
template_user_id = literal_eval(get_param('base.template_portal_user_id', 'False'))
template_user = self.browse(template_user_id)
return template_user.with_context(no_reset_password=True).copy(values)
```

**`reset_password(login)`**

Entry point for password reset:
1. Searches user by login or email
2. Raises if no user found or multiple users found
3. Calls `action_reset_password()`

**`action_reset_password()`**

Delegates to `_action_reset_password(signup_type)`:
- If `context['create_user'] == 1` → `signup_type="signup"` (new user invitation)
- Otherwise → `signup_type="reset"` (password reset)

**`_action_reset_password(signup_type)`**

The full email sending flow:
1. Prepares signup tokens for all target users via `partner_id.signup_prepare()`
2. Sends email via `set_password_email` template (create mode) or `reset_password_email` template (reset mode)
3. Returns a client notification action

```python
for user in self:
    email_values['email_to'] = user.email
    if account_created_template:
        account_created_template.send_mail(user.id, ...)
    else:
        # Render reset password email inline
        body = self.env['mail.render.mixin']._render_template(...)
        mail = self.env['mail.mail'].sudo().create({...})
        mail.send()
```

**`create(vals_list)`**

Auto-invites newly created users:
```python
def create(self, vals_list):
    users = super().create(vals_list)
    if not self.env.context.get('no_reset_password'):
        users_with_email.filter('email').with_context(
            create_user=True
        )._action_reset_password(signup_type='signup')
    return users
```

---

## Invitation Scope

**`auth_signup.invitation_scope`** (`ir.config_parameter`):
- `'b2b'` (default): Only invited users can sign up. `create_user_from_template` raises `SignupError` for uninvited users.
- `'b2c'`: Anyone with a valid token can sign up. Direct signup (no token) is also allowed.

---

## New Device Alert

**`_alert_new_device()`**

Sends a security notification email when a user logs in from a new device/browser:

- Captures from HTTP request: IP address, city/region/country (via `geoip`), browser, OS
- Renders the `auth_signup.alert_login_new_device` template
- Sends via `mail.mail`

**`_should_alert_new_device()`**

Called by `authenticate()` to determine if an alert should be sent. Must be overridden in custom security modules.

**`authenticate(db, credential, user_agent_env)`**

Extends the base authenticate method to trigger new device alerts after successful authentication:
```python
def authenticate(cls, db, credential, user_agent_env):
    auth_info = super().authenticate(db, credential, user_agent_env)
    try:
        env = api.Environment(cr, auth_info['uid'], {})
        if env.user._should_alert_new_device():
            env.user._alert_new_device()
    except MailDeliveryException:
        pass  # Don't fail auth if email fails
    return auth_info
```

---

## Unregistered User Reminder

**`send_unregistered_user_reminder(after_days, batch_size)`**

Cron job to remind administrators about invited users who haven't activated their accounts:
1. Finds users created > `after_days` days ago, never logged in (`log_ids == False`)
2. Groups them by inviter (`create_uid`)
3. Sends one email per inviter with all their unactivated invitees

---

## Signup URL Generation Flow

```
Administrator triggers invitation
         |
         v
res.users.action_reset_password()
(signup_type='signup' or 'reset')
         |
         v
Mapped partner_ids.signup_prepare(signup_type)
         |
         v
_generate_signup_token()  ← signed payload with expiration
         |
         v
/odoo/reset_password?db=...&token=...&redirect=...
         |
         v
User clicks link → /web/reset_password
         |
         v
signup(values, token)
  - verify token
  - invalidate token
  - create user OR update password
         |
         v
Login → _get_login_date() updates → token permanently invalidated
```

---

## Key Design Decisions

1. **Signed tokens over stored tokens:** Tokens are HMAC-signed rather than stored in the database. This avoids race conditions, database storage overhead, and the need for a cleanup cron. Token revocation happens automatically on use or expiration.

2. **Login invalidates token:** Including `login_date` in the signed payload means logging in with the associated user immediately invalidates any outstanding signup tokens for that partner. This is a security feature preventing token reuse after account activation.

3. **Template user pattern:** New users are created by copying a template user (`base.template_portal_user_id`). This ensures all portal users get identical default groups, settings, and company assignments without hardcoding defaults in the signup flow.

4. **Separate user creation from token invalidation:** In the token flow, `signup_type` is cleared BEFORE the user is modified. This means a failed user creation leaves the token intact for retry.

5. **B2B vs B2C scopes:** The `invitation_scope` config separates enterprise/closed-world (B2B, invitation-only) from public/self-service (B2C) registration models.

6. **MailDeliveryException handling:** Email sending failures during authentication and invitation are caught and suppressed — they should not block the core operation.

---

## Notes

- The `state` field (`'new'` vs `'active'`) uses a custom `_search_state()` method that searches against `log_ids` (the `res.users.log` model that records login events). This is why the `_get_login_date()` method returns `login_date` from `res.users.log`, not from `res.users` directly.
- The `copy()` method on `res.users` suppresses invitation emails when duplicating users by passing `no_reset_password=True` in the context.
- `web_create_users(emails)` handles bulk user creation from the web client: existing inactive users are re-sent invitation emails, while new emails create new users.
