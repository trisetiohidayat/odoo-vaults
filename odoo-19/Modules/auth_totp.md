---
type: module
module: auth_totp
tags: [odoo, odoo19, security, 2fa, totp, authentication, mfa]
created: 2026-04-11
updated: 2026-04-11
depth: L4
---

# Two-Factor Authentication (auth_totp)

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `auth_totp` |
| **Category** | Extra Tools |
| **License** | LGPL-3 |
| **Auto Install** | Yes |
| **Author** | Odoo S.A. |
| **Odoo Version** | 19.0+ |
| **Depends** | `web` |

## Description

Time-based One-Time Password (TOTP) authentication module provides an additional security layer for Odoo user accounts. After enabling 2FA, users must enter a 6-digit code from their authenticator app alongside their password when logging in.

This module implements the [RFC 6238 TOTP algorithm](https://datatracker.ietf.org/doc/html/rfc6238), which is the industry-standard protocol used by Google Authenticator, Microsoft Authenticator, Authy, and other authenticator applications.

---

## L1: Module Structure and Fields

### Module Files

```
auth_totp/
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── totp.py              # Pure Python TOTP algorithm (RFC 6238)
│   ├── auth_totp.py         # auth_totp.device model
│   ├── auth_totp_rate_limit_log.py  # Rate limit tracking
│   └── res_users.py        # res.users extensions
├── controllers/
│   ├── __init__.py
│   └── home.py             # web_totp route
├── wizard/
│   ├── __init__.py
│   ├── auth_totp_wizard.py
│   └── auth_totp_wizard_views.xml
├── views/
│   ├── res_users_views.xml  # User form/search extensions
│   └── templates.xml        # QWeb login form
├── security/
│   ├── security.xml         # ir.rule for auth_totp.device + wizard
│   └── ir.model.access.csv
├── tests/
│   ├── test_totp.py
│   └── test_apikeys.py
└── data/
    └── ir_action_data.xml   # ir.actions.server for admin disable
```

### TOTP Algorithm Implementation

**File:** `models/totp.py`

```python
# 160 bits, as recommended by HOTP RFC 4226, section 4, R6.
# Google Auth uses 80 bits by default but supports 160.
TOTP_SECRET_SIZE = 160
ALGORITHM = 'sha1'
DIGITS = 6
TIMESTEP = 30

class TOTP:
    def __init__(self, key):
        self._key = key

    def match(self, code, t=None, window=TIMESTEP, timestep=TIMESTEP):
        """Check if code matches within the fuzz window."""
        if t is None:
            t = time.time()
        low = int((t - window) / timestep)
        high = int((t + window) / timestep) + 1
        return next((
            counter for counter in range(low, high)
            if hotp(self._key, counter) == code
        ), None)

def hotp(secret, counter):
    C = struct.pack(">Q", counter)  # 64b big-endian counter
    mac = hmac.new(secret, msg=C, digestmod=ALGORITHM).digest()
    offset = mac[-1] & 0xF          # dynamic offset per RFC 4226 §5.4
    code = struct.unpack_from('>I', mac, offset)[0] & 0x7FFFFFFF  # 31b mask
    r = code % (10 ** DIGITS)
    return r
```

### TOTP/HOTP Specification

| Parameter | Value | Description |
|-----------|-------|-------------|
| Algorithm | SHA1 | HMAC-SHA1 per RFC 4226 |
| Key Size | 160 bits | Per HOTP RFC 4226 §4/R6 |
| Digits | 6 | Standard TOTP format (9 max due to 31-bit mask) |
| Time Step | 30 seconds | Code refresh interval |
| Fuzz Window | 30 seconds | Accepts codes from T-30s to T+30s |
| HOTP Truncation | 31-bit mask | `& 0x7FFFFFFF` limits digits to 9 (10th would be ~1.1 bits) |

### TOTP Secret Compression

The `compress` utility strips whitespace from secrets before Base32 operations:

```python
compress = functools.partial(re.sub, r'\s', '')
# Applied in: wizard URL generation, wizard enable, res_users._totp_try_setting
# Allows secrets to be stored with spaces ("ABCD EFGH IJKL") but processed as "ABCDEFGHIJKL"
```

---

## L2: Models and State Machine

### res.users Extensions

**File:** `models/res_users.py`

#### Schema Migration

```python
def init(self):
    super().init()
    if not sql.column_exists(self.env.cr, self._table, "totp_secret"):
        self.env.cr.execute("ALTER TABLE res_users ADD COLUMN totp_secret varchar")
```

`totp_secret` and `totp_last_counter` columns are created by direct SQL if they do not exist. This is a migration-safe pattern that handles upgrades from pre-TOTP Odoo installs.

#### Fields Added to res.users

| Field | Type | Access | Storage | Description |
|-------|------|--------|---------|-------------|
| `totp_secret` | Char | NO_ACCESS | DB column | Base32-encoded TOTP secret (plain text) |
| `totp_last_counter` | Integer | NO_ACCESS | DB column | Last used HOTP counter (replay prevention) |
| `totp_enabled` | Boolean | READ (self) | Computed | True when `totp_secret` is non-null |
| `totp_trusted_device_ids` | One2many | READ (self) | `auth_totp_device` table | Trusted browser device records |

```python
class ResUsers(models.Model):
    _inherit = 'res.users'

    totp_secret = fields.Char(
        copy=False, groups=fields.NO_ACCESS,
        compute='_compute_totp_secret', inverse='_inverse_token'
    )
    totp_last_counter = fields.Integer(copy=False, groups=fields.NO_ACCESS)
    totp_enabled = fields.Boolean(
        string="Two-factor authentication",
        compute='_compute_totp_enabled',
        search='_totp_enable_search'
    )
    totp_trusted_device_ids = fields.One2many(
        'auth_totp.device', 'user_id',
        string="Trusted Devices"
    )
```

#### Self-Readable Fields

```python
@property
def SELF_READABLE_FIELDS(self):
    return super().SELF_READABLE_FIELDS + ['totp_enabled', 'totp_trusted_device_ids']
```

Users can always read their own `totp_enabled` and `totp_trusted_device_ids` state — even if they do not have `base.group_user` write access.

#### Secret Storage Pattern

```python
def _compute_totp_secret(self):
    for user in self:
        if not user.id:
            user.totp_secret = user._origin.totp_secret  # bypass SQL on new record
            continue
        self.env.cr.execute(
            'SELECT totp_secret FROM res_users WHERE id=%s', (user.id,)
        )
        user.totp_secret = self.env.cr.fetchone()[0]

def _inverse_token(self):
    self.sudo().totp_last_counter = False  # reset replay counter on secret change
    for user in self:
        secret = user.totp_secret if user.totp_secret else None
        self.env.cr.execute(
            'UPDATE res_users SET totp_secret = %s WHERE id=%s',
            (secret, user.id)
        )
```

**Security note:** Direct SQL is used to bypass ORM access groups. The `groups=fields.NO_ACCESS` flag blocks non-admin RPC reads of `totp_secret`, but the compute and inverse bypass this for internal authentication flows.

**L4 Performance note:** `_compute_totp_secret` issues one SQL query per user record. In batch contexts (e.g., `search().read(['totp_secret'])`), each record triggers `self.env.cr.execute`. The `_origin` guard prevents errors when evaluating defaults on new (unsaved) user records.

#### State: TOTP Enabled/Disabled

```python
@api.depends('totp_secret')
def _compute_totp_enabled(self):
    for r, v in zip(self, self.sudo()):
        r.totp_enabled = bool(v.totp_secret)

def _totp_enable_search(self, operator, value):
    value = not value if operator == '!=' else value
    if value:
        self.env.cr.execute("SELECT id FROM res_users WHERE totp_secret IS NOT NULL")
    else:
        self.env.cr.execute(
            "SELECT id FROM res_users WHERE totp_secret IS NULL OR totp_secret='false'"
        )
    result = self.env.cr.fetchall()
    return [('id', 'in', [x[0] for x in result])]
```

The search method uses direct SQL to bypass the `NO_ACCESS` restriction on `totp_secret`, enabling the UI filter buttons ("2FA Enabled" / "2FA Disabled") in the Users list view.

### auth_totp.device Model

**File:** `models/auth_totp.py`

```python
class Auth_TotpDevice(models.Model):
    _name = 'auth_totp.device'
    _inherit = ["res.users.apikeys"]
    _description = "Authentication Device"
    _auto = False  # table created by res.users.apikeys init()
```

**L4 Architecture:** `_auto = False` causes the model to reuse the table created by `res.users.apikeys` during its `init()` hook. The parent model's `init()` creates a table named after the child model (`auth_totp_device`) with columns: `id`, `user_id`, `name`, `key` (hashed), `scope`, and `expires`. Because `_auto = False`, no separate table is created by `auth_totp.device`.

| Method | Purpose |
|--------|---------|
| `_check_credentials_for_uid(scope, key, uid)` | Validates a device key for a specific user; returns `True` if key matches uid |
| `_get_trusted_device_age()` | Reads `auth_totp.trusted_device_age` ir.config_parameter; returns seconds; falls back to 90 days |
| `_remove()` | Inherited from `res.users.apikeys`: deletes the device record |
| `_generate(scope, name, expires)` | Inherited: generates key, stores hash, returns raw key (sent to browser as cookie) |

```python
def _check_credentials_for_uid(self, *, scope, key, uid):
    """Return True if device key matches given `scope` for user ID `uid`"""
    assert uid, "uid is required"
    return self._check_credentials(scope=scope, key=key) == uid

def _get_trusted_device_age(self):
    ICP = self.env['ir.config_parameter'].sudo()
    try:
        nbr_days = int(ICP.get_param('auth_totp.trusted_device_age', TRUSTED_DEVICE_AGE_DAYS))
        if nbr_days <= 0:
            nbr_days = None
    except ValueError:
        nbr_days = None
    if nbr_days is None:
        _logger.warning("Invalid value for 'auth_totp.trusted_device_age', using default value.")
        nbr_days = TRUSTED_DEVICE_AGE_DAYS
    return nbr_days * 86400  # seconds
```

**Config parameter:** `auth_totp.trusted_device_age` (integer, days). Setting to `0` or negative disables trusted device feature (cookie will have `max_age=None` → session cookie).

### auth_totp.wizard Model

**File:** `wizard/auth_totp_wizard.py`

```python
class Auth_TotpWizard(models.TransientModel):
    _name = 'auth_totp.wizard'
    _description = "2-Factor Setup Wizard"

    user_id = fields.Many2one('res.users', required=True, readonly=True)
    secret = fields.Char(required=True, readonly=True)  # human-readable, with spaces
    url = fields.Char(store=True, readonly=True, compute='_compute_qrcode')
    qrcode = fields.Binary(attachment=False, store=True, readonly=True, compute='_compute_qrcode')
    code = fields.Char(string="Verification Code", size=7, store=False)
    # NOTE: size=7 allows for 6 digits + potential null terminator edge case
```

#### QR Code Generation

```python
@api.depends('user_id.login', 'user_id.company_id.display_name', 'secret')
def _compute_qrcode(self):
    global_issuer = request and request.httprequest.host.split(':', 1)[0]
    for w in self:
        issuer = global_issuer or w.user_id.company_id.display_name
        w.url = url = werkzeug.urls.url_unparse((
            'otpauth', 'totp',
            werkzeug.urls.url_quote(f'{issuer}:{w.user_id.login}', safe=':'),
            werkzeug.urls.url_encode({
                'secret': compress(w.secret),
                'issuer': issuer,
                'algorithm': ALGORITHM.upper(),  # 'SHA1'
                'digits': DIGITS,               # 6
                'period': TIMESTEP,             # 30
            }), ''
        ))
        data = io.BytesIO()
        qrcode.Make(url.encode(), box_size=4).save(data, optimise=True, format='PNG')
        w.qrcode = base64.b64encode(data.getvalue()).decode()
```

**L4 Performance note:** `attachment=False` ensures the binary image is stored as a column value, not as an ir.attachment record. This avoids the filesystem overhead for a transient, single-use record.

**L4 QR code security:** The URL is encoded at `box_size=4` (small modules) to produce a dense but scannable QR code. The `compress()` function strips spaces from the human-readable secret before embedding.

#### Wizard `enable` Method

```python
@check_identity
def enable(self):
    try:
        c = int(compress(self.env.context.get('code', '')))  # reads from button context, not field
    except ValueError:
        raise UserError(_("The verification code should only contain numbers"))
    if self.user_id._totp_try_setting(self.secret, c):
        self.secret = ''  # empty it immediately — no need to keep it in memory until GC
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("2-Factor authentication is now enabled."),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
    raise UserError(_('Verification failed, please double-check the 6-digit code'))
```

The code is passed via the button's `context="{'code': code}"` rather than read directly from the field — this prevents the code from being stored in the wizard record (which would be accessible via `ir.model.data` or audit logs).

### auth_totp.rate_limit_log Model

**File:** `models/auth_totp_rate_limit_log.py`

```python
class AuthTotpRateLimitLog(models.Model):
    _name = 'auth.totp.rate.limit.log'
    _description = 'TOTP rate limit logs'  # plural

    _user_id_limit_type_create_date_idx = models.Index("(user_id, limit_type, create_date)")

    user_id = fields.Many2one('res.users', required=True, readonly=True)
    ip = fields.Char(readonly=True)
    limit_type = fields.Selection([
        ('send_email', 'Send Email'),      # used by auth_totp_mail
        ('code_check', 'Code Checking'),  # used by auth_totp
    ], readonly=True)
```

**L4 Architecture note:** Despite being a TransientModel by naming convention (`.` prefix on `_name`), this model is registered with `_auto = True` (default). No explicit TransientModel inheritance exists, meaning records persist until explicitly deleted. The `_totp_rate_limit_purge` method removes them after a successful TOTP verification.

The composite index on `(user_id, limit_type, create_date)` covers the rate limit query domain exactly.

### Enrollment State Machine

```
┌─────────────────────────────────────────────────────────────┐
│                    ENROLLMENT STATE MACHINE                     │
└─────────────────────────────────────────────────────────────┘

User clicks "Enable 2FA"
         │
         ├─ @check_identity (re-authenticate with password)
         │
         ▼
Generate 160-bit secret via os.urandom()
Base32-encode → "ABCD EFGH IJKL MNPQ" (groups of 4, with spaces)
         │
         ▼
Create auth_totp.wizard record (TransientModel)
         │
         ▼
Display QR code (otpauth:// URI) + manual secret entry
         │
         ▼
User scans QR or enters secret into authenticator app
Authenticator generates 6-digit code (refreshes every 30s)
         │
         ▼
User enters code in wizard
Button calls enable() with context={'code': '123456'}
         │
         ├─ @check_identity (re-authenticate again)
         │
         ▼
_compress(code) → parse int
_totp_try_setting(secret, code):
  ├─ compress(secret), base32decode, call TOTP(key).match(code)
  ├─ match returns counter (HOTP step) or None
  ├─ None → return False → UserError
  └─ counter → write totp_secret, totp_last_counter=counter
       → refresh session token → return True
         │
         ▼
Wiz.sudo().secret = ''  # memory cleared
display_notification: "2FA is now enabled"
```

---

## L3: Authentication Flow, Rate Limiting, and Controller

### L3.1 Full Authentication Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                     LOGIN FLOW WITH TOTP                                 │
└──────────────────────────────────────────────────────────────────────┘

  User                          Odoo Server
    │                                    │
    │  1. POST /web/login (password)    │
    │───────────────────────────────────>│
    │                                    │ AuthToken: check password
    │                                    │ _mfa_type() → 'totp'
    │                                    │ Set pre_uid in session
    │  2. Redirect /web/login/totp       │
    │<───────────────────────────────────│
    │                                    │
    │  3. GET /web/login/totp           │
    │   (Check trusted device cookie)   │
    │───────────────────────────────────>│
    │   │ Cookie td_id present?          │
    │   ├─ YES: _check_credentials_for_uid(uid=user.id)
    │   │      → Session finalized → /web
    │   │                                 │
    │   └─ NO: Show TOTP entry form       │
    │<───────────────────────────────────│
    │                                    │
    │  4. POST /web/login/totp          │
    │     (totp_token=123456, remember?) │
    │───────────────────────────────────>│
    │                                    │ _totp_rate_limit('code_check')
    │                                    │ _assert_can_auth(user.id)
    │                                    │ Decode secret from DB
    │                                    │ TOTP(key).match(token)
    │                                    │ Replay check (counter >= last)
    │  5. Redirect /web (authenticated)  │
    │<───────────────────────────────────│
    │   │ (If remember=True:             │
    │   │   Generate device key          │
    │   │   Set td_id cookie 90d         │
    │   │   request.session.touch())    │
```

### L3.2 MFA Type Discovery Methods

These two methods form the integration point with the Odoo web auth stack:

```python
def _mfa_type(self):
    r = super()._mfa_type()
    if r is not None:
        return r  # delegate to auth_totp_mail or other MFA extensions
    if self.totp_enabled:
        return 'totp'  # auth_totp owns the 'totp' type

def _mfa_url(self):
    r = super()._mfa_url()
    if r is not None:
        return r
    if self._mfa_type() == 'totp':
        return '/web/login/totp'
```

Extensions like `auth_totp_mail` override these methods to return `'totp_mail'` and their own URL. The parent-chain call allows stacking multiple MFA modules.

### L3.3 The web_totp Controller

**File:** `controllers/home.py`

```python
TRUSTED_DEVICE_COOKIE = 'td_id'
TRUSTED_DEVICE_AGE_DAYS = 90

class Home(web_home.Home):
    @http.route(
        '/web/login/totp',
        type='http', auth='public', methods=['GET', 'POST'],
        sitemap=False, website=True,
        multilang=False  # website=True layout but skip i18n to avoid redirects
    )
    def web_totp(self, redirect=None, **kwargs):
        ...
```

**Route attributes:**
- `auth='public'` — accessible without login (session has `pre_uid` from phase 1)
- `website=True` — enables `web.login_layout` rendering
- `multilang=False` — prevents language redirect on the TOTP page (would lose POST data)
- `sitemap=False` — excluded from sitemap crawlers

#### GET Handler

```python
if request.session.uid:
    return request.redirect(self._login_redirect(...))  # already logged in

if not request.session.get('pre_uid'):
    return request.redirect('/web/login')  # no pending auth

user = request.env['res.users'].browse(request.session['pre_uid'])
if request.httprequest.method == 'GET':
    cookies = request.cookies
    key = cookies.get(TRUSTED_DEVICE_COOKIE)
    if key:
        user_match = request.env['auth_totp.device']._check_credentials_for_uid(
            scope="browser", key=key, uid=user.id)
        if user_match:
            request.session.finalize(request.env)
            request.update_env(user=request.session.uid)
            request.update_context(**request.session.context)
            return request.redirect(self._login_redirect(...))
```

#### POST Handler

```python
elif request.httprequest.method == 'POST' and kwargs.get('totp_token'):
    try:
        with user._assert_can_auth(user=user.id):
            credentials = {
                'type': user._mfa_type(),  # returns 'totp'
                'token': int(re.sub(r'\s', '', kwargs['totp_token'])),
            }
            user._check_credentials(credentials, {'interactive': True})
    except AccessDenied as e:
        error = str(e)
    except ValueError:
        error = _("Invalid authentication code format.")
    else:
        request.session.finalize(request.env)
        request.update_env(user=request.session.uid)
        request.update_context(**request.session.context)
        response = request.redirect(self._login_redirect(...))

        if kwargs.get('remember'):
            name = _("%(browser)s on %(platform)s",
                browser=request.httprequest.user_agent.browser.capitalize(),
                platform=request.httprequest.user_agent.platform.capitalize(),
            )
            if request.geoip.city.name:
                name += f" ({request.geoip.city.name}, {request.geoip.country_name})"

            trusted_device_age = request.env['auth_totp.device']._get_trusted_device_age()
            key = request.env['auth_totp.device'].sudo()._generate(
                "browser", name,
                datetime.now() + timedelta(seconds=trusted_device_age)
            )
            response.set_cookie(
                key=TRUSTED_DEVICE_COOKIE, value=key,
                max_age=trusted_device_age,
                httponly=True, samesite='Lax'
            )

        # Crapy workaround for unupdatable Odoo Mobile App iOS
        request.session.touch()
        return response

request.session.touch()
return request.render('auth_totp.auth_totp_form', {...})
```

**L4 Mobile iOS workaround:** `request.session.touch()` updates the session's modification time. The iOS Odoo app cannot parse the redirect response properly after a successful TOTP login (due to cookie restrictions). By touching the session first, the logout-on-session-expiry is prevented for mobile app users.

### L3.4 Credential Verification with Rate Limiting

```python
def _check_credentials(self, credentials, env):
    if credentials['type'] == 'totp':
        self._totp_rate_limit('code_check')  # raises AccessDenied if exceeded
        sudo = self.sudo()
        key = base64.b32decode(sudo.totp_secret)
        match = TOTP(key).match(credentials['token'])
        if match is None:
            _logger.info("2FA check: FAIL for %s %r", self, sudo.login)
            raise AccessDenied(_("Verification failed, please double-check the 6-digit code"))

        # Replay attack prevention
        if sudo.totp_last_counter and match <= sudo.totp_last_counter:
            _logger.warning("2FA check: REUSE for %s %r", self, sudo.login)
            raise AccessDenied(_("Verification failed, please use the latest 6-digit code"))

        sudo.totp_last_counter = match
        _logger.info("2FA check: SUCCESS for %s %r", self, sudo.login)
        self._totp_rate_limit_purge('code_check')  # clean up log entries
        return {
            'uid': self.env.user.id,
            'auth_method': 'totp',
            'mfa': 'default',
        }
    return super()._check_credentials(credentials, env)
```

### L3.5 Rate Limiting Implementation

```python
TOTP_RATE_LIMITS = {
    'send_email': (5, 3600),  # auth_totp_mail: 5 codes per hour
    'code_check': (5, 3600),  # auth_totp: 5 verifications per hour
}

def _totp_rate_limit(self, limit_type):
    self.ensure_one()
    assert request, "A request is required to be able to rate limit TOTP related actions"
    limit, interval = TOTP_RATE_LIMITS[limit_type]
    RateLimitLog = self.env['auth.totp.rate.limit.log'].sudo()
    ip = request.httprequest.environ['REMOTE_ADDR']
    domain = [
        ('user_id', '=', self.id),
        ('create_date', '>=', datetime.now() - timedelta(seconds=interval)),
        ('limit_type', '=', limit_type),
    ]
    count = RateLimitLog.search_count(domain)
    if count >= limit:
        descriptions = {
            'send_email': _('You reached the limit of authentication mails sent for your account, please try again later.'),
            'code_check': _('You reached the limit of code verifications for your account, please try again later.'),
        }
        raise AccessDenied(descriptions[limit_type])
    RateLimitLog.create({
        'user_id': self.id, 'ip': ip, 'limit_type': limit_type,
    })

def _totp_rate_limit_purge(self, limit_type):
    self.ensure_one()
    assert request, "A request is required to be able to rate limit TOTP related actions"
    RateLimitLog = self.env['auth.totp.rate.limit.log'].sudo()
    RateLimitLog.search([
        ('user_id', '=', self.id),
        ('limit_type', '=', limit_type),
    ]).unlink()  # purge ALL entries for user/limit_type (not just within window)
```

**L4 Rate limit purge design:** On success, `_totp_rate_limit_purge` removes **all** log entries for that user+type — not just those within the time window. This is correct because a successful login proves the user has the device, so any prior failed attempts are no longer relevant.

---

## L4: Security Deep-Dive, Secret Storage, and Odoo 18→19 Changes

### L4.1 Secret Storage Security

The TOTP secret is stored as a **plain Base32-encoded string** in the `res_users.totp_secret` column:

| Aspect | Implementation | Security Implication |
|--------|---------------|----------------------|
| Storage format | Plain Base32 (`"JBSWY3DP EHPK3PXP"`) | Anyone with DB read access can decode |
| Access control | `groups=fields.NO_ACCESS` | ORM RPC returns `False` for non-admin |
| Retrieval method | Direct SQL `SELECT` in `_compute_totp_secret` | Bypasses NO_ACCESS for authentication |
| `totp_secret` in session token | `_get_session_token_fields()` includes it | Changing secret invalidates all sessions |
| Replay prevention | `totp_last_counter` (HOTP counter) | Codes cannot be replayed within window |
| Secret clearing | `_inverse_token` resets `totp_last_counter` | Changing secret invalidates old codes |

**L4 Attack surface:** The plain-text storage is the primary risk. An attacker with DB read access (e.g., through SQL injection or a compromised DB host) can extract and decode the TOTP secret. Mitigations:
- Database-level encryption at rest (LVM dm-crypt, TDE)
- Row-level security or restricted DB user
- Odoo Enterprise Credential Vault (stores secrets in an encrypted keystore)
- The secret is never logged, exposed in API responses, or stored in `ir.model.data`

### L4.2 Brute Force Protection (4 Layers)

| Layer | Mechanism | Protection |
|-------|-----------|------------|
| 1. Code space | 6 digits = 1,000,000 possible codes | 1 in 500,000 chance per attempt (fuzz window) |
| 2. Time decay | Codes expire every 30s; only 1-2 valid at any moment | Attacker must try within exact 30s window |
| 3. Rate limiting | 5 attempts/hour per user (stored per-user, not per-IP) | Mitigates distributed brute force |
| 4. Replay prevention | `totp_last_counter >= match` rejects codes | Eliminates intercepted-code attacks |

The rate limit is keyed to `user_id`, not IP address. This means:
- **Benefit:** An attacker cannot bypass rate limits by using many IPs
- **Downside:** A malicious admin could intentionally rate-limit a victim by making failed attempts in their name (requires admin access)

### L4.3 Session Token Binding

When TOTP is enabled or disabled, the session token is refreshed to prevent session fixation attacks:

```python
def _totp_try_setting(self, secret, code):
    ...
    self.sudo().totp_secret = secret
    self.sudo().totp_last_counter = match
    if request:
        self.env.flush_all()
        new_token = self.env.user._compute_session_token(request.session.sid)
        request.session.session_token = new_token

def action_totp_disable(self):
    ...
    self.sudo().write({'totp_secret': False})
    if request and self == self.env.user:
        self.env.flush_all()
        new_token = self.env.user._compute_session_token(request.session.sid)
        request.session.session_token = new_token
```

The `_get_session_token_fields()` override ensures changes to `totp_secret` trigger recomputation:

```python
def _get_session_token_fields(self):
    return super()._get_session_token_fields() | {'totp_secret'}
```

**L4 Session fixation:** If an attacker somehow plants a session cookie on a victim (e.g., via `pre_uid` manipulation), the session token binding prevents the attacker from using their pre-authenticated session after the victim completes TOTP.

### L4.4 Identity Verification for Administrative Actions

Both enabling and disabling TOTP require recent identity verification via `@check_identity` (re-entering password, valid for 5 minutes by default):

```python
@check_identity
def action_totp_disable(self):
    if not (self == self.env.user or self.env.user._is_admin() or self.env.su):
        _logger.info("2FA disable: REJECT for %s (%s) by uid #%s", ...)
        return False
    self.revoke_all_devices()
    self.sudo().write({'totp_secret': False})
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'type': 'warning',
            'message': _("Two-factor authentication disabled for: %s", ...),
            'next': {'type': 'ir.actions.act_window_close'},
        }
    }

@check_identity
def action_totp_enable_wizard(self):
    if self.env.user != self:
        raise UserError(_("Two-factor authentication can only be enabled for yourself"))
    if self.totp_enabled:
        raise UserError(_("Two-factor authentication already enabled"))
    ...
```

**Admin disable workflow:** An ERP manager (group_erp_manager) can disable TOTP for any user via the contextual action `action_totp_disable` (bound from `data/ir_action_data.xml`). This is the recovery path when a user loses their authenticator device:
1. ERP manager clicks "Disable 2FA" on the affected user's form
2. ERP manager must re-authenticate with their own password (`@check_identity` on the ERP manager's session)
3. All trusted devices are revoked
4. User can now log in with password only and re-enroll

**L4 Privilege escalation risk:** If an admin's own password is compromised while TOTP is not enabled on the admin account, the attacker can enable TOTP on behalf of the admin (via `action_totp_enable_wizard` which only requires `@check_identity` with the compromised password). Recommendation: always enable TOTP on admin accounts first.

### L4.5 Password Change Revokes Trusted Devices

```python
@api.model
def change_password(self, old_passwd, new_passwd):
    self.env.user._revoke_all_devices()
    return super().change_password(old_passwd, new_passwd)

def _revoke_all_devices(self):
    self.totp_trusted_device_ids._remove()
```

A password change invalidates all trusted devices because password compromise implies the possibility of device compromise.

### L4.6 RPC/API Access Impact

```python
def _rpc_api_keys_only(self):
    self.ensure_one()
    return self.totp_enabled or super()._rpc_api_keys_only()
```

When TOTP is enabled, password-based RPC is blocked. The `_assert_can_auth` context manager enforces this during the browser TOTP flow:

```python
with user._assert_can_auth(user=user.id):
    ...
```

This context manager raises `AccessDenied` if the user has TOTP enabled but is attempting non-API-key authentication.

| Access Method | TOTP Disabled | TOTP Enabled |
|---------------|--------------|--------------|
| Password XML-RPC | Allowed | BLOCKED |
| Password JSON-RPC | Allowed | BLOCKED |
| `authenticate` with `interactive=True` + faked type | Allowed | BLOCKED (tested) |
| API Keys | Allowed | Allowed |
| Browser session (password + TOTP) | Password only | Password + TOTP |
| Browser session (trusted device cookie) | Password only | TOTP bypassed |

The tests verify this blocking explicitly:

```python
# After enabling 2FA:
self.assertFalse(
    self.xmlrpc_common.authenticate(db, 'test_user', 'test_user', {}),
    "Should not have returned a uid"
)
# Attempting to fake the auth type is also blocked:
self.assertFalse(
    self.xmlrpc_common.authenticate(db, 'test_user', 'test_user', {'interactive': True}),
    'Trying to fake the auth type should not work'
)
```

### L4.7 Odoo 18→19 Changes

| Aspect | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| Rate limiting | Not present | Added: 5 attempts/hour per user |
| Rate limit log model | Not present | `auth.totp.rate.limit.log` added |
| Rate limit purge on success | Not present | `_totp_rate_limit_purge` added |
| `auth_totp.device` | `_auto = False` | Same |
| Session token binding | Present | Same |
| Trusted device cookie | `httponly=True` | `httponly=True, samesite='Lax'` |
| Replay prevention | `totp_last_counter` | Same |
| `_rpc_api_keys_only` override | Present | Same |
| Wizard context | Basic | Added `dialog_size='medium'` |
| Wizard button context | Field-based | `context="{'code': code}"` |
| Trusted device name | Browser + platform | + GeoIP city/country |
| `action_totp_disable` return | Not `display_notification` | Returns `display_notification` |
| `request.session.touch()` | Not present | Added (mobile iOS workaround) |
| `totp_secret` column creation | `ALTER TABLE` on init | Same |

### L4.8 Trusted Device Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   TRUSTED DEVICE LIFECYCLE                      │
└──────────────────────────────────────────────────────────────┘

Generation (on successful TOTP + "remember" checkbox):
  1. _generate("browser", name, expiry) → returns RAW key (not stored)
  2. key stored as HMAC-SHA256 hash in auth_totp_device.key
  3. Raw key sent as td_id cookie (max_age = trusted_device_age seconds)
  4. Browser auto-sends cookie on every request

Validation (on GET /web/login/totp):
  1. Read td_id from cookie
  2. _check_credentials(scope="browser", key=td_id) → looks up hash
  3. Checks expiry, scope, user_id match
  4. If valid: session finalized, TOTP step bypassed

Expiration:
  - Cookie max_age expires → browser deletes cookie automatically
  - Device record stays in DB until manual revocation or password change

Revocation triggers:
  - User changes password    → _revoke_all_devices() via change_password hook
  - User disables TOTP       → revoke_all_devices() → _remove() each device
  - Admin disables TOTP     → revoke_all_devices() (via action_totp_disable)
  - User deletes device UI   → unlink via ORM (res.users.apikeys._remove)
```

### L4.9 Security Record Rules

**`auth_totp.device` (from `security/security.xml`):**

```xml
<!-- Public users: no access at all (always-false domain) -->
<record id="api_key_public" model="ir.rule">
    <field name="domain_force">[(0, '=', 1)]</field>
    <field name="groups" eval="[Command.link(ref('base.group_public'))]"/>
</record>

<!-- Logged-in users: own devices only -->
<record id="api_key_user" model="ir.rule">
    <field name="domain_force">[('user_id', '=', user.id)]</field>
    <field name="groups" eval="[Command.link(ref('base.group_portal')),
                                Command.link(ref('base.group_user'))]"/>
</record>

<!-- Admin: all devices (to revoke them) -->
<record id="api_key_admin" model="ir.rule">
    <field name="domain_force">[(1, '=', 1)]</field>
    <field name="groups" eval="[Command.link(ref('base.group_system'))]"/>
</record>
```

**`auth_totp.wizard` (from `security/security.xml`):**

```xml
<!-- Users can only access their own wizard record -->
<record model="ir.rule" id="rule_auth_totp_wizard">
    <field name="domain_force">[('user_id', '=', user.id)]</field>
</record>
```

**Access control (`ir.model.access.csv`):**

| Model | Group | read | write | create | unlink |
|-------|-------|------|-------|--------|--------|
| `auth_totp.device` | base.group_user | 1 | 0 | 0 | 0 |
| `auth_totp.device` | base.group_portal | 1 | 0 | 0 | 0 |
| `auth_totp.rate.limit.log` | base.group_user | 0 | 0 | 0 | 0 |
| `auth_totp.wizard` | base.group_user | 1 | 1 | 1 | 1 |

The rate limit log has zero all permissions because it is only written/read internally via `sudo()` calls from within `_totp_rate_limit` and `_totp_rate_limit_purge` — the ORM security model never applies to internal code paths using `sudo()`.

### L4.10 QR Code URI Format

The enrollment wizard generates an `otpauth://` URI following the Google Authenticator spec:

```
otpauth://totp/Odoo:admin@company.com?secret=JBSWY3DPEHPK3PXP&issuer=Odoo&algorithm=SHA1&digits=6&period=30
```

| Component | Value | Notes |
|-----------|-------|-------|
| Protocol | `otpauth://totp` | Key URI format v1.0 |
| Label | `Odoo:admin@company.com` | `{issuer}:{login}` URL-quoted |
| `secret` | Base32 (no spaces) | Compressed from stored secret |
| `issuer` | HTTP host or company name | Falls back to `company_id.display_name` |
| `algorithm` | `SHA1` | Uppercase (Google Auth requires this) |
| `digits` | `6` | |
| `period` | `30` | |

The `issuer` field in the URI is critical: changing the server's host name after enrollment will cause authenticator apps to show "Invalid token" because the issuer mismatch is treated as a security issue by strict apps (e.g., Google Authenticator ignores it, but Microsoft Authenticator validates it).

---

## L3/L4: Wizard Views and User Preferences

### User Preferences Form (`view_totp_field`)

Inherits `base.view_users_form_simple_modif` (the "Preferences" / My Profile form):

```xml
<!-- "Enable 2FA" button shown to self (uid == user.id), only when disabled -->
<button invisible="totp_enabled" name="action_totp_enable_wizard"
    type="object" class="btn btn-secondary h-100 my-auto" string="Enable 2FA"/>

<!-- Status + "Disable" button shown when enabled -->
<div invisible="not totp_enabled" class="h-100 d-flex...">
    <i class="fa fa-check text-success"/>
    <span class="fw-bold ms-1 me-2">Enabled</span>
    <button name="action_totp_disable" type="object" class="btn btn-secondary h-100">
        Disable
    </button>
</div>
```

**L4 UI behavior:** Users cannot enable TOTP for other users from their own preferences form (enforced in `action_totp_enable_wizard`). However, admins can see the "Enable 2FA" button for other users (invisible when `totp_enabled or id != uid` — the `id != uid` part hides it for self too, but the button is still present for admins to disable).

### Admin User Form (`view_totp_form`)

Inherits `base.view_users_form` (full user form with "Enable" for other users visible):

```xml
<!-- Admin can see "Disabled" text for other users (not button) -->
<div invisible="totp_enabled or id == uid" class="h-100 d-flex...">
    <i class="fa fa-remove text-danger"/>
    <span class="fw-bold ms-1">Disabled</span>
</div>
```

### Users List Search Filters

```xml
<filter name="totp_enabled" string="Two-factor authentication Enabled"
    domain="[('totp_enabled','!=',False)]"/>
<filter name="totp_disabled" string="Two-factor authentication Disabled"
    domain="[('totp_enabled','=',False)]"/>
```

These filters use the computed `totp_enabled` field (which in turn uses `_totp_enable_search` with direct SQL).

### Admin Contextual Action

**File:** `data/ir_action_data.xml`

```xml
<record model="ir.actions.server" id="action_disable_totp">
    <field name="name">Disable two-factor authentication</field>
    <field name="model_id" ref="base.model_res_users"/>
    <field name="binding_model_id" ref="base.model_res_users"/>
    <field name="state">code</field>
    <field name="code">action = records.action_totp_disable()</field>
    <field name="group_ids" eval="[(4, ref('base.group_erp_manager'))]"/>
</record>
```

This creates a contextual action available from the Users list view and form for users in `base.group_erp_manager`.

---

## Extension Modules

### auth_totp_mail

Extends `auth_totp` to support email-based 2FA when authenticator apps are unavailable.

| Aspect | auth_totp | auth_totp_mail |
|--------|-----------|----------------|
| MFA type | `totp` | `totp_mail` |
| Code generation | TOTP (RFC 6238) | HMAC using user_id + login timestamp + secret |
| Rate limit type | `code_check` | `send_email` |
| Delivery | Authenticator app | Email link/code |
| Secret storage | Same | Same |

The `_totp_rate_limit` with `limit_type='send_email'` limits email codes to 5 per hour.

### auth_totp_portal

Provides TOTP support for portal (B2B/B2C) users. Portal users access Odoo via the website and can enable 2FA on their portal account using the same flow as internal users.

---

## RPC/API Access with TOTP

### Impact on External Access

| Access Method | TOTP Disabled | TOTP Enabled |
|--------------|---------------|--------------|
| Password-based XML-RPC/JSON-RPC | Allowed | BLOCKED |
| `authenticate` with faked `interactive` | Allowed | BLOCKED (verified in tests) |
| API Keys (ir.attachment-stored) | Allowed | Allowed |
| OAuth tokens | Allowed | Allowed |
| Browser session: password only | Allowed | Password + TOTP step |
| Browser session: trusted device | Allowed | TOTP bypassed |

---

## Configuration

| Parameter | Key | Type | Default | Description |
|-----------|-----|------|---------|-------------|
| Trusted device lifetime | `auth_totp.trusted_device_age` | Integer (days) | 90 | Set to `<=0` to disable trusted devices |
| TOTP issuer (auto) | HTTP host | String | Server hostname | Used in QR code `otpauth://` label |
| TOTP issuer (fallback) | `res.company.display_name` | String | Company name | Used if HTTP host unavailable |

---

## Limitations

| Aspect | Authenticator App | SMS (not supported) |
|--------|------------------|---------------------|
| Security | High (offline, no SIM swap) | Lower (SIM swap risk) |
| Offline | Yes | No |
| Cost | Free | Carrier fees |
| Backup | Via QR code transfer | Carrier dependent |

### Known Limitations

1. **No SMS Support**: Odoo only supports authenticator apps (by design — SMS 2FA is considered less secure)
2. **No Backup Codes**: Users must regenerate codes if they lose their device; recovery requires admin to disable TOTP
3. **Clock Dependency**: Requires synchronized clocks (mitigated by 30s fuzz window in both directions)
4. **Per-User, Not Per-Session**: 2FA is account-level, not session-level; once authenticated, all sessions are 2FA-authenticated
5. **No Biometric Fallback**: Only TOTP codes are supported natively
6. **Plain-text Secret Storage**: The Base32 secret is stored without encryption at rest in the database
7. **No IP-based Rate Limiting**: Rate limits are per-user only; a distributed attack using many IPs bypasses the 5/hour limit

---

## Security Best Practices

1. **Enable for All Admin/Manager Users**: Always protect accounts with broad access first
2. **Use Company Email**: Avoid personal email for 2FA recovery; if personal email is compromised, 2FA cannot be recovered
3. **Store the Secret Safely**: When enabling TOTP, some apps allow exporting the secret — store it in a password manager
4. **Keep Trusted Devices Minimal**: Regularly review and remove old trusted devices from the user form
5. **Monitor Logs**: Check the `auth.totp.rate.limit.log` records for unusual patterns (many `code_check` failures for one user)
6. **Use API Keys for Automation**: Any automated script hitting a TOTP-enabled user account must use API keys; set these up before enabling TOTP
7. **Avoid Changing Server Hostnames**: Changing the Odoo server's hostname after TOTP enrollment may cause authenticator app failures due to issuer mismatch

---

## Tests

**File:** `tests/test_totp.py`

The test suite uses a `TestTOTPMixin` to install a TOTP hook that bypasses the time window constraint (since test runs are non-real-time):

```python
class TestTOTPMixin:
    def install_totphook(self):
        # Adds /totphook JSON endpoint that generates codes for current time
        # Patches auth_TOTP.match to accept codes relative to baseline_time
        ...
```

Test cases:

| Test | What it verifies |
|------|-----------------|
| `test_totp` | Full flow: enable 2FA, RPC blocked, reuse rejected, trusted device works, disable works, RPC restored |
| `test_totp_administration` | Admin can disable 2FA for another user via contextual action |
| `test_totp_authenticate` | Session info is not leaked for half-logged-in users (returns `uid: None`) |

---

## Related Documentation

- [[Modules/web]] — Web controller base (`web_home.Home` parent)
- [[Modules/auth_oauth]] — OAuth authentication (also extends `_mfa_type`)
- [[Modules/auth_signup]] — User registration
- [[Modules/auth_password_policy]] — Password strength requirements
- [[Core/API]] — `@check_identity` decorator, identity verification flow
- [[Patterns/Security Patterns]] — ir.rule, ir.model.access.csv, field groups

---

## Appendix: Code Examples

### Checking if User Has TOTP Enabled

```python
user = env['res.users'].browse(user_id)
if user.totp_enabled:
    print("TOTP is active for this user")
    print(f"Trusted devices: {len(user.totp_trusted_device_ids)}")
```

### Enabling TOTP Programmatically

```python
user = env['res.users'].browse(user_id)

# Launch the enrollment wizard (requires identity check)
action = user.action_totp_enable_wizard()
wizard = env['auth_totp.wizard'].browse(action['res_id'])

# QR code for scanning
qr_code_base64 = wizard.qrcode

# Manual secret (with spaces for readability)
secret = wizard.secret  # "JBSW Y3DP EHPK 3PXP"

# In the wizard view, the user enters the code manually.
# Programmatically, you would need to:
import time
from odoo.addons.auth_totp.models.totp import TOTP
import base64

secret_clean = re.sub(r'\s', '', secret)
key = base64.b32decode(secret_clean)
totp = TOTP(key)
code = totp.match(time.time())  # get current code

# Validate and enable
result = wizard.with_context(code=str(code)).enable()
```

### Disabling TOTP for a Locked-Out User (Admin)

```python
user = env['res.users'].browse(locked_out_user_id)
# Requires admin identity check via @check_identity
action = user.action_totp_disable()
# Returns display_notification; wizard/form closes
```

### Revoking All Trusted Devices

```python
user = env['res.users'].browse(user_id)
user._revoke_all_devices()  # calls _remove() on each auth_totp.device
```

### Using API Keys with TOTP

```python
import xmlrpc.client

url = 'http://localhost:8069'
db = 'mydb'

common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, 'admin', 'API_KEY_STRING_HERE', {})

# uid is returned if API key is valid (TOTP is bypassed for API keys)
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
result = models.execute_kw(
    db, uid, 'API_KEY_STRING_HERE',
    'res.partner', 'read', [1], {'fields': ['name', 'email']}
)
```

### Generating a TOTP Secret (Python)

```python
import os
import base64
from odoo.addons.auth_totp.models.totp import TOTP, TOTP_SECRET_SIZE

secret_bytes = os.urandom(TOTP_SECRET_SIZE // 8)  # 20 bytes = 160 bits
secret_b32 = base64.b32encode(secret_bytes).decode()
print(f"Secret: {secret_b32}")  # e.g. "JBSWY3DPEHPK3PXP"

# Generate current TOTP code
key = base64.b32decode(secret_b32)
totp = TOTP(key)
code = totp.match()  # uses time.time()
print(f"Current code: {code:06d}")  # e.g. "123456"
```
