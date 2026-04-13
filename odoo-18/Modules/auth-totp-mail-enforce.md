---
Module: auth_totp_mail_enforce
Version: Odoo 18
Type: Extension
Tags: [#odoo, #odoo18, #security, #auth, #totp, #2fa, #mail, #enforcement]
Related: [Modules/auth_totp](Modules/auth_totp.md) (base TOTP), [Modules/auth_totp_mail](Modules/auth_totp_mail.md) (notifications), [Modules/auth_totp_portal](Modules/auth_totp_portal.md) (portal 2FA), [Core/API](Core/API.md)
---

# auth_totp_mail_enforce — TOTP Email Enforcement

> **Purpose:** Enforce TOTP-based 2FA on users who have not configured an authenticator-app TOTP. When those users log in without a TOTP secret, Odoo sends a 6-digit code by email instead. This module also allows administrators to globally enforce 2FA for all employees or all users via a system-wide config policy.

**Module:** `auth_totp_mail_enforce`
**Depends:** `auth_totp`, `mail`
**Category:** Extra Tools
**License:** LGPL-3
**Source path:** `~/odoo/odoo18/odoo/addons/auth_totp_mail_enforce/`

---

## Architecture Overview

`auth_totp_mail_enforce` serves two distinct roles:

### Role 1: Email TOTP Fallback for Unenrolled Users

The base `auth_totp` module requires a user to have a `totp_secret` to use 2FA. If a user has no `totp_secret`, the base module simply logs them in without any second factor. `auth_totp_mail_enforce` fills this gap:

- If `auth_totp.policy` is set (`employee_required` or `all_required`) and a user has **no** `totp_secret`, the module intercepts the login flow.
- Instead of bypassing 2FA, it uses an HMAC-based TOTP code delivered by email.
- The key is derived from `(user.id, user.login, user.login_date)` — an HMAC, not the user's password or any secret stored in the DB.
- The code has a **3600-second (1-hour) timestep** — deliberately slow, acting as a "one-time password per hour" rather than the typical 30-second TOTP.
- Rate limiting is enforced: max 10 emails per hour, max 10 code checks per hour per IP.

### Role 2: Global TOTP Enforcement Policy

Administrators set `auth_totp.policy = 'employee_required'` or `'all_required'` via the system settings UI. This makes 2FA mandatory for all matching users, even those who have never configured an authenticator app.

**No new persistent fields on `res.users`.** Enforcement is controlled entirely via the `ir.config_parameter` system (`auth_totp.policy`).

---

## Extensions to `res.users`

**Model:** `res.users` (extends `auth_totp` extension)

### Key Method: `_mfa_type()` (override)

```python
def _mfa_type(self):
    r = super()._mfa_type()
    if r is not None:
        return r
    ICP = self.env['ir.config_parameter'].sudo()
    otp_required = False
    if ICP.get_param('auth_totp.policy') == 'all_required':
        otp_required = True
    elif ICP.get_param('auth_totp.policy') == 'employee_required' and self._is_internal():
        otp_required = True
    if otp_required:
        return 'totp_mail'
```

**L4 — How it works:**
- First calls the parent's `_mfa_type()`. If it returns a non-None value (e.g., `'totp'` from `auth_totp` if the user has a `totp_secret`), that takes precedence.
- If the parent returns `None` (user has no authenticator-app TOTP configured), this override checks the system-wide `auth_totp.policy` ICP.
- `'all_required'`: All users (including portal) who lack a `totp_secret` must use mail-based TOTP.
- `'employee_required'`: Only internal users (`self._is_internal() == True`) who lack a `totp_secret` must use mail-based TOTP.
- External/portal users without a `totp_secret` are skipped if policy is `employee_required`.
- Returns `'totp_mail'` as the MFA type string — this triggers the `totp_mail` branch in `_mfa_url()` and `_totp_check()`.

**MRO note:** Because this override calls `super()._mfa_type()` first, a user who has both an authenticator-app TOTP (`totp_secret` set) and a policy-enforced status will always use the app-based `totp` flow, not the mail-based `totp_mail` flow. The mail flow is strictly a **fallback for unenrolled users**.

### Key Method: `_mfa_url()` (override)

```python
def _mfa_url(self):
    r = super()._mfa_url()
    if r is not None:
        return r
    if self._mfa_type() == 'totp_mail':
        return '/web/login/totp'
```

**L4 — How it works:**
- If `_mfa_type()` returns `'totp_mail'`, this returns `/web/login/totp` — the standard TOTP login form (shared with `auth_totp`'s authenticator-app flow).
- The TOTP form template is then extended by `auth_totp_mail_enforce/views/templates.xml` to show the email-code variant instead of the QR code / app-based variant.

### Key Method: `_totp_check()` (override)

```python
def _totp_check(self, code):
    self._totp_rate_limit('code_check')
    user = self.sudo()
    if user._mfa_type() != 'totp_mail':
        return super()._totp_check(code)

    key = user._get_totp_mail_key()
    match = TOTP(key).match(code, window=3600, timestep=3600)
    if match is None:
        _logger.info("2FA check (mail): FAIL for %s %r", user, user.login)
        raise AccessDenied(_("Verification failed, please double-check the 6-digit code"))
    _logger.info("2FA check(mail): SUCCESS for %s %r", user, user.login)
    self._totp_rate_limit_purge('code_check')
    self._totp_rate_limit_purge('send_email')
    return True
```

**L4 — How it works:**
- First applies the code-check rate limit (10 checks per hour per IP).
- Calls `super()._totp_check()` only if `_mfa_type() != 'totp_mail'` — i.e., if the user has an authenticator-app TOTP, delegate to `auth_totp` entirely.
- For `totp_mail` users, uses HMAC-based TOTP with a 1-hour timestep.
- `window=3600` allows ±1 hour clock skew (one full timestep tolerance).
- On success: purges rate limit logs for both `send_email` and `code_check` (so the rate limit window resets after successful auth).
- On failure: raises `AccessDenied`. The rate limit log entry is NOT purged on failure — retries are tracked.

### Key Method: `_get_totp_mail_key()` (private)

```python
def _get_totp_mail_key(self):
    self.ensure_one()
    return hmac(self.env(su=True), 'auth_totp_mail-code', (self.id, self.login, self.login_date)).encode()
```

**L4 — How it works:**
- Derives a unique TOTP key per user per login date using HMAC-SHA256.
- Uses `self.login_date` (the last login timestamp) so the key changes on each login — this makes codes usable only for the current session.
- The HMAC key material is generated server-side; the secret is never sent to or stored by the user.
- `(self.id, self.login, self.login_date)` is a 3-tuple encoded as the HMAC message. Different logins produce different keys even for the same user.

### Key Method: `_get_totp_mail_code()` (private)

```python
def _get_totp_mail_code(self):
    self.ensure_one()
    key = self._get_totp_mail_key()
    now = datetime.now()
    counter = int(datetime.timestamp(now) / 3600)
    code = hotp(key, counter)
    expiration = timedelta(seconds=3600)
    lang = babel_locale_parse(self.env.context.get('lang') or self.lang)
    expiration = babel.dates.format_timedelta(expiration, locale=lang)
    return str(code).zfill(6), expiration
```

**L4 — How it works:**
- Uses HOTP (counter-based OTP) with a 3600-second counter (epoch-seconds / 3600).
- Counter increments once per hour. A code generated at the start of an hour is valid for the entire hour.
- `code` is zero-padded to 6 digits.
- `expiration` is formatted as a human-readable timedelta string using Babel locale (e.g., "an hour" in the user's language).
- Both the code and its expiration string are embedded in the email template via `mail_template_totp_mail_code`.

### Key Method: `_send_totp_mail_code()` (private)

```python
def _send_totp_mail_code(self):
    self.ensure_one()
    self._totp_rate_limit('send_email')

    if not self.email:
        raise UserError(_("Cannot send email: user %s has no email address.", self.name))

    template = self.env.ref('auth_totp_mail_enforce.mail_template_totp_mail_code').sudo()
    context = {}
    if request:
        device = request.httprequest.user_agent.platform
        browser = request.httprequest.user_agent.browser
        context.update({
            'location': None,
            'device': device and device.capitalize() or None,
            'browser': browser and browser.capitalize() or None,
            'ip': request.httprequest.environ['REMOTE_ADDR'],
        })
        if request.geoip.city.name:
            context['location'] = f"{request.geoip.city.name}, {request.geoip.country_name}"

    email_values = {
        'email_to': self.email,
        'email_cc': False,
        'auto_delete': True,
        'recipient_ids': [],
        'partner_ids': [],
        'scheduled_date': False,
    }
    with self.env.cr.savepoint():
        template.with_context(**context).send_mail(
            self.id, force_send=True, raise_exception=True, email_values=email_values,
            email_layout_xmlid='mail.mail_notification_light'
        )
```

**L4 — How it works:**
- Enforces send-email rate limit before sending.
- Gathers browser/device/IP metadata from the HTTP request context for the email.
- Uses `geoip` to include city and country name in the email for transparency.
- All context fields are passed to the mail template renderer.
- Wrapped in a savepoint to avoid partial commits if the email fails.
- `auto_delete=True` ensures the email record is deleted after delivery.

### Key Method: `_totp_rate_limit()` (private)

```python
def _totp_rate_limit(self, limit_type):
    self.ensure_one()
    assert request, "A request is required to be able to rate limit TOTP related actions"
    limit, interval = TOTP_RATE_LIMITS.get(limit_type)
    RateLimitLog = self.env['auth.totp.rate.limit.log'].sudo()
    ip = request.httprequest.environ['REMOTE_ADDR']
    domain = [
        ('user_id', '=', self.id),
        ('create_date', '>=', datetime.now() - timedelta(seconds=interval)),
        ('limit_type', '=', limit_type),
        ('ip', '=', ip),
    ]
    count = RateLimitLog.search_count(domain)
    if count >= limit:
        descriptions = {
            'send_email': _('You reached the limit of authentication mails sent for your account'),
            'code_check': _('You reached the limit of code verifications for your account'),
        }
        description = descriptions.get(limit_type)
        raise AccessDenied(description)
    RateLimitLog.create({...})  # log the attempt
```

**L4 — How it works:**
- Rate limits are IP + user + type scoped (the same IP on the same user account).
- `send_email` limit: 10 emails per hour per IP per user.
- `code_check` limit: 10 failed verifications per hour per IP per user.
- Uses a `TransientModel` (`auth.totp.rate.limit.log`) — records are periodically cleaned by the ORM's transient model garbage collection.
- `assert request` ensures rate limiting only applies to web login flows (not API/RPC calls without HTTP context).
- After a successful verification, rate limit logs are purged via `_totp_rate_limit_purge()`.

### Key Method: `_totp_rate_limit_purge()` (private)

```python
def _totp_rate_limit_purge(self, limit_type):
    self.ensure_one()
    assert request, "A request is required to be able to rate limit TOTP related actions"
    ip = request.httprequest.environ['REMOTE_ADDR']
    RateLimitLog = self.env['auth.totp.rate.limit.log'].sudo()
    RateLimitLog.search([
        ('user_id', '=', self.id),
        ('limit_type', '=', limit_type),
        ('ip', '=', ip),
    ]).unlink()
```

**L4 — How it works:**
- Called after successful TOTP verification to reset the rate limit counters.
- Deletes all matching rate limit log entries for this user + IP + type.
- Next login attempt starts a fresh rate limit window.

---

## New Model: `auth.totp.rate.limit.log`

**Type:** ` TransientModel`
**Purpose:** Track rate limit hits for mail-based TOTP. Transient — automatically garbage-collected by Odoo's transient model cleanup.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `many2one(res.users)` | The user being rate-limited. Required, readonly. |
| `scope` | `char` | HTTP scope (optional, unused in code but stored). |
| `ip` | `char` | IP address of the request. Readonly. |
| `limit_type` | `selection` | Either `'send_email'` or `'code_check'`. Readonly. |

### `init()` — Database Index

```python
def init(self):
    self.env.cr.execute("""
        CREATE INDEX IF NOT EXISTS auth_totp_rate_limit_log_user_id_limit_type_create_date_idx
        ON auth_totp_rate_limit_log(user_id, limit_type, create_date);
    """)
```

A composite index on `(user_id, limit_type, create_date)` ensures rate limit queries are fast even with many log entries.

### Rate Limit Constants

```python
TOTP_RATE_LIMITS = {
    'send_email': (10, 3600),
    'code_check': (10, 3600),
}
```

- **10 emails per hour** per user per IP for resending codes.
- **10 code checks per hour** per user per IP for failed verification attempts.

---

## Extension to `res.config.settings`

**Model:** `res.config.settings` (extends `base_setup` extension)

### Fields

| Field | Type | Config Parameter | Description |
|-------|------|-----------------|-------------|
| `auth_totp_enforce` | `boolean` | (none — computed via `auth_totp.policy`) | Toggle for "Enforce two-factor authentication." Mirrors whether the policy is set. |
| `auth_totp_policy` | `selection` | `auth_totp.policy` | `'employee_required'` or `'all_required'`. |

### `get_values()` — Reading the Config

```python
def get_values(self):
    res = super(ResConfigSettings, self).get_values()
    res['auth_totp_enforce'] = bool(self.env['ir.config_parameter'].sudo().get_param('auth_totp.policy'))
    return res
```

**L4 — How it works:**
- `auth_totp_enforce` is derived from the presence of `auth_totp.policy` ICP — it is `True` if any policy is set (either `'employee_required'` or `'all_required'`).
- This means the toggle in the UI shows as checked if a policy exists, unchecked otherwise.

### `_onchange_auth_totp_enforce()` — Toggle Logic

```python
@api.onchange('auth_totp_enforce')
def _onchange_auth_totp_enforce(self):
    if self.auth_totp_enforce:
        self.auth_totp_policy = self.auth_totp_policy or 'employee_required'
    else:
        self.auth_totp_policy = False
```

**L4 — How it works:**
- Checking the "Enforce two-factor authentication" toggle automatically sets the policy to `'employee_required'` if no policy was selected.
- Unchecking the toggle clears the policy entirely (`False`) — removing the ICP and disabling enforcement.

---

## Data Files

### `data/mail_template_data.xml`

**Template:** `mail_template_totp_mail_code`
**Subject:** "Your two-factor authentication code"
**Model:** `res.users`
**Auto-delete:** True

The template renders:
1. A "new login detected" alert: location, device, browser, IP address.
2. The 6-digit TOTP code (from `_get_totp_mail_code()`).
3. Code expiration time in human-readable format.
4. A warning: "If you did NOT initiate this log-in, change your password."
5. A CTA button: "Activate my two-factor authentication" linking to `object.get_totp_invite_url()`.

The code is rendered in a styled box with the company purple theme color (`#875A7B`).

### `views/templates.xml`

Extends `auth_totp.auth_totp_form` to transform the standard QR-code TOTP form into the email-code variant:

```xml
<div t-if="user._mfa_type() == 'totp_mail'" class="mb-2 mt-2 text-muted">
    <i class="fa fa-envelope-o"/>
    To login, enter below the six-digit authentication code just sent via email to <t t-out="user.email"/>.
</div>
```

Also injects a re-send button (POST to the same form with `send_email=1`) and a "Learn More" link recommending authenticator apps (as a better alternative to mail-based TOTP).

### `views/res_config_settings_views.xml`

Injects into `base_setup.res_config_settings_view_form` under the `allow_import` section:

```xml
<setting id="auth_totp_policy" help="Enforce the two-factor authentication by email...">
    <field name="auth_totp_enforce" />
    <div class="mt16" invisible="not auth_totp_enforce">
        <field name="auth_totp_policy" class="o_light_label" widget="radio"/>
    </div>
</setting>
```

The policy radio buttons (`Employees only` / `All users`) are only visible when enforcement is toggled on.

---

## Login Flow with auth_totp_mail_enforce (L4)

```
User visits /web
  └─ Database + credentials checked
      └─ auth_totp.res.users._lookup() passes
          └─ _mfa_type() evaluated:
              ├─ totp_secret exists → 'totp' (auth_totp app-based flow)
              └─ totp_secret absent + policy active → 'totp_mail' (mail-based flow)
                  └─ User redirected to /web/login/totp
                      └─ Form shown: "Enter 6-digit code sent via email"
                          └─ User submits email address → _send_totp_mail_code()
                              ├─ Rate limit check (send_email): 10/hour
                              └─ Email sent with code + location/browser/IP
                          └─ User submits code → _totp_check()
                              ├─ Rate limit check (code_check): 10/hour
                              ├─ HMAC key derived from (id, login, login_date)
                              ├─ HOTP code matched (window=3600, timestep=3600)
                              └─ Success → session created, rate limits purged
```

---

## TOTP Code Mechanics (L4 — Deep Dive)

Unlike the standard `auth_totp` module which uses TOTP with a 30-second timestep and a user-specific secret stored in `res_users.totp_secret`, `auth_totp_mail_enforce` uses a different approach:

| Parameter | Standard `auth_totp` | `auth_totp_mail_enforce` |
|-----------|---------------------|---------------------------|
| Algorithm | TOTP (SHA1, 30s) | HOTP (SHA256, 3600s timestep) |
| Key source | `res_users.totp_secret` | HMAC of `(id, login, login_date)` |
| Key stored | Yes (per user) | No (derived on demand) |
| Timestep | 30 seconds | 3600 seconds (1 hour) |
| Window | Default | ±3600s (±1 hour) |
| Scope | Per user | Per user per login session |

The 1-hour timestep means a single code is valid for up to 2 hours (current hour ± 1). This is intentional: the email may be read with some delay, and the user should not be locked out due to clock skew or reading delay.

The HMAC key uses `login_date` so each login session has a different key. The code for the previous session's key is invalidated when the user next logs in (which updates `login_date`).

---

## Security Notes

- **HMAC key is not stored.** The code is regenerated server-side each time `_get_totp_mail_code()` is called. No secret is persisted beyond the current session.
- **Rate limiting prevents brute force.** 10 attempts per hour per IP per user makes brute-forcing the 6-digit code infeasible (1 million possible codes, max 10 guesses).
- **`login_date` changes on each login.** A code from a previous login session cannot be replayed.
- **`_rpc_api_keys_only()` override** ensures that if `auth_totp_mail_enforce` is enforcing TOTP, the user cannot use password-based RPC (only API keys bypass 2FA).
