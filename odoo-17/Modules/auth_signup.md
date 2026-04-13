---
tags: [odoo, odoo17, module, auth]
---

# Auth Signup Module

**Source:** `addons/auth_signup/models/`

Extends `res.users` and `res.partner` with self-service registration and password management.

## Key Models

| Model | File | Description |
|-------|------|-------------|
| `res.partner` | `res_partner.py` | Extended with signup token fields |
| `res.users` | `res_users.py` | Extended with signup/reset methods |

## res.partner Extensions

Adds signup token fields to the partner model.

### Fields
- `signup_token` — Token used for signup/password reset (write-only, `groups=base.group_erp_manager`)
- `signup_type` — Type of token: `signup` | `reset`
- `signup_expiration` — Datetime when token expires
- `signup_valid` — Computed: token exists and not expired
- `signup_url` — Computed: full URL for the signup/reset action

### Key Methods

`signup_prepare(signup_type="signup", expiration=False)`
: Generates a random 20-character token and writes it to the partner. If `expiration` is provided, the token expires at that datetime.

`_signup_retrieve_partner(token, check_validity=False, raise_exception=False)`
: Looks up a partner by token. Optionally validates that the token has not expired.

`signup_retrieve_info(token)`
: Returns `{'db', 'token', 'name', 'login', 'email'}` for the partner identified by the token.

`signup_cancel()`
: Clears `signup_token`, `signup_type`, and `signup_expiration`.

`_get_signup_url_for_action(...)`
: Builds the full signup URL, optionally with a redirect parameter back to a specific Odoo action/view/model/res_id.

`signup_get_auth_param()`
: Returns auth parameters for a partner — either a `signup_token` (if no user exists and `b2c` scope) or the existing user's `login`.

## res.users Extensions

### Fields
- `state` — Computed: `new` (never connected) | `active` (confirmed). Searchable via `_search_state()`.

### Invitation Scope
`auth_signup.invitation_scope` config parameter controls self-registration:
- `b2c` — Anyone can sign up (public registration)
- `b2b` — Only invited users can register (default)

### Key Methods

`signup(values, token=None)`
: Main signup entry point. Handles three cases:
  1. **With token, user exists**: Reset password for existing user
  2. **With token, no user**: Create user linked to the invited partner
  3. **No token**: Public signup (only allowed if `invitation_scope=b2c`)

`_signup_create_user(values)`
: Validates that public signup is allowed, then delegates to `_create_user_from_template()`.

`_create_user_from_template(values)`
: Copies a template user (configured via `base.template_portal_user_id`) with the provided values. This ensures new users get the correct groups and defaults.

`reset_password(login)`
: Looks up user by login or email and calls `action_reset_password()`.

`_action_reset_password()`
: Generates a signup token (type=`reset`, 1-day expiration) and sends the signup URL by email. Uses `mail.mail` directly or a `mail.template` for initial invitations.

`action_reset_password()`
: Wrapper that handles `MailDeliveryException` and reports SMTP errors as `UserError`.

`create(vals_list)` (overridden)
: Automatically calls `_action_reset_password()` after creating a user, inviting them to set their password.

`write(vals)` (overridden)
: If `active` is set to `False`, cancels the partner's signup token.

`send_unregistered_user_reminder(after_days=5)`
: Scheduled action that emails creators of newly invited users who have not yet connected.

`_alert_new_device()` / `_prepare_new_device_notice_values()`
: Sends a "new connection" notification email when a user logs in from an unrecognized device. Reads IP address, city/region/country from `request.geoip`.

`web_create_users(emails)`
: RPC method that creates users for a list of emails. Existing `new` users with matching email/login are reset instead.

## Signup Flow

### Public Signup (b2c)
1. User visits `/web/signup`
2. Fills name, login, password
3. `res.users.signup(values)` called — creates user from template
4. `_action_reset_password()` sends email
5. User clicks link in email → password set / account activated

### Invited Signup (b2b)
1. Admin or existing user triggers "Invite" from Contacts or Users
2. `signup_prepare(signup_type="signup")` called on partner
3. Email sent with signup URL containing token
4. User clicks link → `signup(values, token)` creates user
5. User sets password → account activated

### Password Reset
1. User visits `/web/reset_password`
2. Enters email/login
3. `res.users.reset_password(login)` → `action_reset_password()`
4. Token generated (type=`reset`, expires in 1 day)
5. Email with reset link sent
6. User clicks link → `signup(values, token)` updates password

## Auth Adapter Modules

| Module | Description |
|--------|-------------|
| `auth_signup` | Standard email/password registration |
| `auth_oauth` | OAuth providers (Google, custom OAuth2) |
| `auth_ldap` | LDAP directory authentication |
| `auth_totp` | Time-based OTP / TOTP (2FA) |
| `auth_totp_mail_enforce` | Enforce 2FA via email for all users |
| `auth_password_policy` | Enforce password complexity rules |

Each auth module implements `authenticate()` or registers an authentication method with Odoo's auth system.

## Security Notes

- Signup tokens have 120 bits of entropy (20 random alphanumeric characters)
- Tokens are write-only via `_inverse_token()` — stored directly in SQL to avoid access rights restrictions
- New device alerts use `request.geoip` for geolocation when HTTP request context is available
- Archived users have their partner signup tokens canceled

## See Also
- [Modules/mail](mail.md) — Email notifications sent during signup
- `auth_oauth` — OAuth2 sign-in
- `auth_totp` — Two-factor authentication
- `portal` — Public portal user creation
