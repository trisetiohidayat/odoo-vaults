---
date: 2026-04-11
tags:
  - #modules
  - #website
  - #captcha
  - #security
  - #cloudflare
  - #turnstile
  - #bot-protection
---

# website_cf_turnstile — Cloudflare Turnstile

## Overview

| Attribute         | Value                                             |
|-------------------|---------------------------------------------------|
| **Module**        | `website_cf_turnstile`                           |
| **Category**      | `Website/Website`                                |
| **Depends**       | `website`                                        |
| **Version**       | `1.0`                                             |
| **License**       | `LGPL-3`                                         |
| **Author**        | Odoo S.A.                                        |
| **`installable`** | `True`                                           |

Prevents bot spam on website forms using [[[Cloudflare Turnstile](https://blog.cloudflare.com/turnstile-private-captcha-alternative/)]] — a privacy-first, invisible CAPTCHA alternative to Google reCAPTCHA. The module ships **zero Python model files**; all ORM work lives in two files that extend `ir.http` and `res.config.settings`.

---

## Module Architecture

```
website_cf_turnstile/
├── __manifest__.py                  # Manifest + asset bundling
├── __init__.py                      # Imports ir_http, res_config_settings
├── models/
│   ├── __init__.py
│   ├── ir_http.py                   # ir.http extensions (turnstile verification)
│   └── res_config_settings.py       # turnstile_site_key / turnstile_secret_key fields
├── views/
│   └── res_config_settings_view.xml # Inherits base_setup.res_config_settings_view_form
├── data/
│   └── neutralize.sql               # Clears keys on odoo-instance-neutralize
└── static/src/interactions/
    ├── turnstile.js                 # TurnStile JS class (client-side widget logic)
    ├── turnstile.xml                # QWeb templates: turnstile_container, turnstile_remote_script
    ├── turnstile_captcha.js         # TurnstileCaptcha Interaction (data-captcha forms)
    ├── form.js                      # Patch on Form.prototype (s_website_form snippet)
    └── error_handler.js             # ErrorDialog handler for Turnstile errors
```

---

## Manifest

```python
{
    'name': 'Cloudflare Turnstile',
    'category': 'Website/Website',
    'version': '1.0',
    'depends': ['website'],
    'data': [
        'views/res_config_settings_view.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_cf_turnstile/static/src/interactions/**/*.js',
            'website_cf_turnstile/static/src/interactions/**/*.xml',
        ],
        'web.assets_unit_tests': [
            'website_cf_turnstile/static/tests/**/*',
        ],
        'web.assets_unit_tests_setup': [
            'website_cf_turnstile/static/src/interactions/**/*.js',
            'website_cf_turnstile/static/src/interactions/**/*.xml',
        ],
    },
}
```

**Key observations:**
- No `security/` directory — no ACL CSV files; permissions are inherited from `website`.
- `web.assets_unit_tests_setup` re-injects the frontend assets into test harness so interactions are loadable in the unit-test DOM environment.
- `neutralize.sql` is **not** listed in `data` — it is loaded separately by the `neutralize` mechanism (`--neutralize` CLI flag), not on normal install/upgrade.

---

## Python Models

### `ir.http` — Extended

**File:** `models/ir_http.py`
**Inheritance:** `_inherit = 'ir.http'` (classic extension)
**Abstract model:** `base.ir_http` (from `odoo/addons/base/models/ir_http.py`)

The base `ir.http` provides `_verify_request_recaptcha_token(self, action: str)` which is a no-op stub returning `None`. Both `google_recaptcha` and `website_cf_turnstile` extend it. Callers (website controllers) invoke `_verify_request_recaptcha_token(action)` before processing a form submission.

#### `get_frontend_session_info()`

```python
@api.model
def get_frontend_session_info(self):
    session = super().get_frontend_session_info()
    site_key = self.env['ir.config_parameter'].sudo().get_param('cf.turnstile_site_key')
    if site_key:
        session['turnstile_site_key'] = site_key
    return session
```

- **What it does:** Injects the **public** site key into the frontend session object (`session` in JS).
- **Called by:** Odoo's `web.webclient` on every page load via `/web/session/get_session_info`.
- **L3 — Why `sudo()`:** `ir.config_parameter` records are system-wide; a public user must read them. This is safe — the site key is public by design.
- **L3 — No secret key exposed:** The secret key is never sent to the frontend. Only the public `turnstile_site_key` travels over the wire.
- **L4 — Performance:** Called on every page load; however, it reads a single `ir.config_parameter` row by key (indexed), so the overhead is negligible.

#### `_verify_request_recaptcha_token(action)`

```python
@api.model
def _verify_request_recaptcha_token(self, action):
    super()._verify_request_recaptcha_token(action)   # calls base no-op
    ip_addr = request.httprequest.remote_addr
    token = request.params.pop('turnstile_captcha', False)   # extracted from POST body
    turnstile_result = request.env['ir.http']._verify_turnstile_token(ip_addr, token, action)
    if turnstile_result in ['is_human', 'no_secret']:
        return   # verification passed or disabled
    if turnstile_result == 'wrong_secret':
        raise ValidationError(_("The Cloudflare turnstile private key is invalid."))
    elif turnstile_result == 'wrong_token':
        raise ValidationError(_("The CloudFlare human validation failed."))
    elif turnstile_result == 'timeout':
        raise UserError(_("Your request has timed out, please retry."))
    elif turnstile_result == 'bad_request':
        raise UserError(_("The request is invalid or malformed."))
    else:   # wrong_action, is_bot, etc.
        raise UserError(_("Suspicious activity detected by Turnstile CAPTCHA."))
```

- **What it does:** Orchestrates the full server-side verification flow. Pops `turnstile_captcha` from `request.params` (a `MultiDict`) so it is not re-processed by downstream controllers.
- **Why `pop`:** Prevents the token from being treated as a normal form field — it must only be consumed once by the CAPTCHA verification logic.
- **`request.params.pop` vs `request.httprequest.form.get`:** `request.params` in Odoo is a merged view of query strings and POST body. Both `pop` approaches work; using `params` covers both GET-with-query-params and POST form-encoded bodies.
- **`request.env['ir.http']` dispatch:** Forces routing through the record proxy so the correct `_verify_turnstile_token` implementation is called (even if other modules also extend `ir.http`).
- **L3 — Error distinction:**
  - `ValidationError` → used when the problem is with credentials (`wrong_secret`) — signals a configuration bug.
  - `UserError` → used when the problem is with the user's token or network — signals a transient/user-facing issue.
- **L4 — Security:** The method is `@api.model` (runs as superuser context), which is intentional: CAPTCHA verification must never be bypassed based on user permissions. Bot protection runs before ACL checks.

#### `_verify_turnstile_token(ip_addr, token, action=False)`

```python
@api.model
def _verify_turnstile_token(self, ip_addr, token, action=False):
    private_key = request.env['ir.config_parameter'].sudo().get_param('cf.turnstile_secret_key')
    if not private_key:
        return 'no_secret'
    try:
        r = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
            'secret': private_key,
            'response': token,
            'remoteip': ip_addr,
        }, timeout=3.05)
        result = r.json()
        res_success = result['success']
        res_action = res_success and action and result['action']
    except requests.exceptions.Timeout:
        logger.error("Turnstile verification timeout for ip address %s", ip_addr)
        return 'timeout'
    except Exception:
        logger.error("Turnstile verification bad request response")
        return 'bad_request'

    if res_success:
        if res_action and res_action != action:
            logger.warning("Turnstile verification for ip address %s failed with action %f, expected: %s.", ...)
            return 'wrong_action'
        logger.info("Turnstile verification for ip address %s succeeded", ip_addr)
        return 'is_human'
    errors = result.get('error-codes', [])
    logger.warning("Turnstile verification for ip address %s failed error codes %r. token was: [%s]", ip_addr, errors, token)
    for error in errors:
        if error in ['missing-input-secret', 'invalid-input-secret']:
            return 'wrong_secret'
        if error in ['missing-input-response', 'invalid-input-response']:
            return 'wrong_token'
        if error in ('timeout-or-duplicate', 'internal-error'):
            return 'timeout'
        if error == 'bad-request':
            return 'bad_request'
    return 'is_bot'
```

**Return values and their semantics:**

| Return           | Meaning                                                                 |
|------------------|-------------------------------------------------------------------------|
| `'is_human'`      | Token valid, user verified as human                                    |
| `'no_secret'`     | No private key configured — CAPTCHA is effectively disabled            |
| `'wrong_secret'`  | Secret key is missing or invalid                                       |
| `'wrong_token'`   | Token missing, expired, or invalid                                      |
| `'timeout'`       | Token too old or replayed (`timeout-or-duplicate`) / Cloudflare error   |
| `'bad_request'`   | Cloudflare API rejected the request format                              |
| `'wrong_action'`  | Action name mismatch (token obtained for a different form action)      |
| `'is_bot'`        | Cloudflare classified the request as bot                                |

**L4 — Performance considerations:**
- `timeout=3.05` on the HTTP POST — deliberately set above the 3-second mark so Cloudflare's own timeout (3s) is hit before Python's, ensuring the API response or timeout error is surfaced cleanly.
- Each form submission triggers a **synchronous** outbound HTTP call to Cloudflare before the controller can return a response. In high-traffic deployments, this adds ~100–300ms per verified form submission. Consider caching strategies if form volume is extreme.
- The `requests` library is used (not Odoo's `request.session` or `httpx`) — this is an intentional low-level call that bypasses Odoo's HTTP session middleware for speed.

**L4 — Edge cases:**
- `action` mismatch: The Cloudflare response includes an `action` field that must match the expected action string. This prevents a token captured from one form being replayed on another (e.g., a token obtained from a low-security form being used on a signup form).
- `remoteip` passed to Cloudflare: Odoo reads `request.httprequest.remote_addr`. In deployment behind a reverse proxy (nginx), this must be forwarded via `X-Forwarded-For` and trusted in Odoo's `proxy_mode` config, otherwise all IPs appear as `127.0.0.1` or the proxy IP.
- `'internal-error'` maps to `'timeout'` in Odoo — this means Cloudflare infrastructure errors are surfaced to users as "request timed out", which is a safe degraded mode.
- A `token` that is an empty string returns `'wrong_token'` (caught by `missing-input-response`).

**L4 — Token single-use security:**
- Cloudflare Turnstile tokens are designed to be used **once**. After successful verification, Cloudflare marks the token as consumed; a replay of the same token returns `success: false` with `error-codes: ["timeout-or-duplicate"]`.
- The `pop()` on `request.params` prevents the token from being included in any logged or reflected response — it is consumed and discarded before any downstream code executes.
- The `wrong_action` check adds a second layer: even if a token were replayed within its validity window, a mismatch in action context causes rejection. This is critical for forms where different actions have different risk profiles (e.g., contact form vs. account registration).
- No server-side token cache is needed — Cloudflare handles single-use enforcement on their side.

---

### `res.config.settings` — Extended

**File:** `models/res_config_settings.py`
**Inheritance:** `_inherit = 'res.config.settings'`

```python
class ResConfigSettings(models.TransientModel):
    turnstile_site_key = fields.Char(
        "CF Site Key",
        config_parameter='cf.turnstile_site_key',
        groups='base.group_system',
    )
    turnstile_secret_key = fields.Char(
        "CF Secret Key",
        config_parameter='cf.turnstile_secret_key',
        groups='base.group_system',
    )
```

**Field analysis:**

| Field                 | Type  | Storage key                         | Access group                       | Purpose                                       |
|-----------------------|-------|-------------------------------------|-------------------------------------|-----------------------------------------------|
| `turnstile_site_key`  | Char  | `ir.config_parameter/cf.turnstile_site_key`    | `base.group_system` (Technical/Browse) | Public site key injected into frontend session |
| `turnstile_secret_key`| Char  | `ir.config_parameter/cf.turnstile_secret_key`  | `base.group_system` (Technical/Browse) | Private server-side key for API verification  |

- **`config_parameter` pattern:** Odoo's `config_parameter` field descriptor auto-persists the value to `ir.config_parameter` on write and reads it on demand, without needing a dedicated database column or model. The key prefix `cf.` is the namespace (CloudFlare).
- **`groups='base.group_system'`:** Only members of the System group (typically admin) can view or edit these fields. This is critical: the secret key must not be visible to regular portal users.
- **`@api.model` context:** Since `res.config.settings` is a `TransientModel`, these fields always operate in a superuser-like context via the wizard mechanism — no ACL issues writing to `ir.config_parameter`.

---

## Views

### `res_config_settings_view.xml`

Inherits `base_setup.res_config_settings_view_form` and replaces the `<div id="turnstile_warning">` placeholder (originally injected by the base module's website captcha warning banner) with a proper configuration panel:

```xml
<div id="cfturnstile_configuration_settings">
    <field name="turnstile_site_key"/>
    <field name="turnstile_secret_key"/>
    <a href="https://blog.cloudflare.com/turnstile-private-captcha-alternative/">
        More info
    </a>
</div>
```

**L3 — Why replace `turnstile_warning`:** The base website module injects a warning div when it detects that no CAPTCHA is configured. The Turnstile module replaces that same div with its own settings panel, so the admin experience is unified in one place rather than split across the base module's warning and a separate Turnstile form.

---

## Static Assets — Frontend

### `turnstile.js` — `TurnStile` Class

**Class:** `TurnStile`
**No inheritance — standalone utility class**

```javascript
export class TurnStile {
    static turnstileURL = "https://challenges.cloudflare.com/turnstile/v0/api.js";

    constructor(action) {
        // action: string — the "action name" passed to Cloudflare for verification
        // Modes: cf=?show → always visible; default → interaction-only (invisible)
    }
}
```

**Key methods:**

| Method                  | Signature                                      | Purpose                                             |
|-------------------------|------------------------------------------------|-----------------------------------------------------|
| `clean(el)`             | `static clean(el: HTMLElement)`                | Removes all Turnstile DOM artifacts from a form     |
| `disableSubmit(btn)`    | `static disableSubmit(submitBtn: HTMLElement)` | Adds `disabled` + `cf_form_disabled` class to button |
| `insertScripts(formEl)` | `insertScripts(formEl: HTMLElement)`           | Injects validation hidden input + remote script tag |
| `render()`              | `render()`                                     | Calls `window.turnstile.render()` if not yet up    |

**Widget lifecycle:**

1. **`willStart` / `start`:** `TurnStile.clean()` is called first to remove any stale widget from a previous interaction cycle (e.g., when navigating between pages without full reload).
2. **Widget injection:** The `<div class="s_turnstile">` container is inserted before the submit button; a hidden `<input class="turnstile_captcha_valid">` is appended to the form.
3. **Submit button disabled:** `disableSubmit()` adds `disabled` + `cf_form_disabled` to the submit button, preventing form submission until the CAPTCHA is solved.
4. **Script loading:** The `api.js` script is loaded lazily. If `window.turnstile.render` already exists (i.e., `api.js` was already loaded by another widget on the page), the script is skipped to avoid duplicate loading.
5. **On success (`turnstileSuccess`):** The hidden `turnstile_captcha_valid` input's value is set to `"done"`, and all `cf_form_disabled` buttons are re-enabled. The token is now ready to be submitted with the form.
6. **On error (`throwTurnstileErrorCode`):** The error is thrown and caught by `error_handler.js`.

**L4 — Invisible mode:** By default, Turnstile runs in `interaction-only` mode — it is invisible to users unless Cloudflare's risk score is uncertain and needs explicit challenge. Adding `?cf=show` to the URL forces `always` (always-visible) mode for debugging.

**L4 — `render=explicit` handling:** The API script loads all `data-sitekey` divs on the page automatically unless `?render=explicit` is in the script URL. The module does **not** use `render=explicit` — instead, it checks `window.turnstile?.render` to determine whether to call `render()` manually or let the auto-render kick in. This handles the mixed scenario where some widgets are on the page before the script loads and others are added dynamically after.

**L4 — Password manager compatibility:** `TurnStile` inserts `inputValidation` (`<input style="display:none" class="turnstile_captcha_valid" required>`) to prevent browser password managers from auto-filling and triggering a submit before the CAPTCHA is ready.

---

### `turnstile_captcha.js` — `TurnstileCaptcha` Interaction

**Class:** `TurnstileCaptcha`
**Extends:** `Interaction`
**Registered as:** `website_cf_turnstile.turnstile_captcha`

```javascript
export class TurnstileCaptcha extends Interaction {
    static selector = "form[data-captcha]";   // targets any <form data-captcha="...">
    // ...
}
registry.category("public.interactions")
    .add("website_cf_turnstile.turnstile_captcha", TurnstileCaptcha);
```

- **`static selector`:** Any `<form data-captcha="action_name">` on the page is automatically decorated with Turnstile. The `data-captcha` value is the action string passed to the Turnstile widget and verified server-side.
- **L3 — Interaction pattern:** This uses Odoo's new [Core/API](Core/API.md) (`web.public.interactions` registry). Unlike the old `@website.form` snippet system, Interactions are activated per-DOM-element without requiring a specific snippet to be dragged onto the page. A theme or custom HTML can add `data-captcha="my_form"` to any `<form>` to opt in.
- **L3 — `data-captcha` attribute:** This is a convention that both the backend (`_verify_turnstile_token` action param) and the frontend (`TurnStile` constructor) agree on. Any string is allowed; the backend does not pre-register action names.

---

### `form.js` — Patch on `Form` (Website Form Snippet)

**Patches:** `Form.prototype` from `@website/snippets/s_website_form/form`

```javascript
patch(Form.prototype, {
    start() {
        super.start();
        TurnStile.clean(this.el);
        if (!this.el.classList.contains("s_website_form_no_recaptcha") &&
            !this.el.querySelector(".s_turnstile") &&
            session.turnstile_site_key) {
            // inject Turnstile widget before .s_website_form_send / .o_website_form_send
        }
    },
    destroy() { /* clean + super.destroy() */ },
});
```

- **`s_website_form_no_recaptcha`:** A CSS class that can be added to a form snippet to opt out of CAPTCHA. Set programmatically or via the form snippet's customization panel.
- **L3 — Dual registration:** The website form snippet gets Turnstile via this `Form.patch()` — **not** via the `TurnstileCaptcha` Interaction. This is because `s_website_form` has its own `Form` class that manages submission differently (via the Odoo form snippet controller). The `TurnstileCaptcha` Interaction only handles raw `<form data-captcha>` elements.
- **Action name:** Hardcoded as `"website_form"` — this is the action string passed to Cloudflare and verified server-side. Controllers that submit to the form endpoint must pass the matching action to `_verify_request_recaptcha_token('website_form')`.

---

### `error_handler.js` — Global Error Handler

```javascript
function turnstileErrorHandler(env, error) {
    if (error.message.includes("Turnstile Error")) {
        env.services.dialog.add(ErrorDialog, {
            name: _t("Cloudflare Turnstile Error"),
            traceback: _t("...info... %s ...", error.event.error.code),
        });
        return true;   // error handled, do not propagate
    }
}
registry.category("error_handlers").add("turnstile_error_handler", turnstileErrorHandler);
```

- **Purpose:** Catches JavaScript errors thrown by `TurnStile` (via `globalThis.throwTurnstileErrorCode`) and displays them as a user-friendly modal instead of an unhandled JS crash.
- **`return true`:** Signals that the error was consumed; Odoo's error middleware will not re-throw it.
- **`error.event.error.code`:** Cloudflare's error code (e.g., `timeout`, `error-sitekey-invalid`). See [Cloudflare Turnstile errors reference](https://developers.cloudflare.com/turnstile/reference/errors).

---

### `turnstile.xml` — QWeb Templates

```xml
<t t-name="website_cf_turnstile.turnstile_container">
    <div class="s_turnstile s_turnstile_container cf-turnstile ..."
         t-att-data-action="action"
         t-att-data-appearance="appeareance || 'interaction-only'"
         t-att-data-before-interactive-callback="beforeInteractiveGlobalCallback || '() => {}'"
         t-att-data-callback="executeGlobalCallback || '() => {}'"
         t-att-data-error-callback="errorGlobalCallback || '() => {}'"
         data-response-field-name="turnstile_captcha"
         t-att-data-sitekey="sitekey"
         t-att-style="style">
    </div>
</t>
```

```xml
<t t-name="website_cf_turnstile.turnstile_remote_script">
    <script id="s_turnstile_remote_script" class="s_turnstile" t-att-src="remoteScriptUrl"/>
</t>
```

**Data attributes and their role:**

| Data attribute                     | Set by                       | Consumed by                                      |
|------------------------------------|------------------------------|-------------------------------------------------|
| `data-action`                      | `TurnStile` constructor     | Cloudflare widget; returned in API response    |
| `data-appearance`                  | `TurnStile` (`interaction-only` or `always`) | Cloudflare widget (widget mode) |
| `data-before-interactive-callback` | Global name `"turnstileBecomeVisible"` | Turnstile JS API          |
| `data-callback`                    | Global name `"turnstileSuccess"`   | Turnstile JS API (on success)        |
| `data-error-callback`              | Global name `"throwTurnstileErrorCode"` | Turnstile JS API (on error)       |
| `data-response-field-name`         | `"turnstile_captcha"`       | Not used by Turnstile; may be used by Odoo's form snippet JS |
| `data-sitekey`                     | `session.turnstile_site_key` | Cloudflare widget initialization                  |

---

## Data File

### `neutralize.sql`

```sql
UPDATE ir_config_parameter
SET value = ''
WHERE key IN ('cf.turnstile_site_key', 'cf.turnstile_secret_key');
```

- **Purpose:** GDPR/data minimization compliance. When running `odoo-bin --neutralize`, all Turnstile credentials are wiped so the instance no longer holds live third-party API keys at rest.
- **Not loaded on normal install/upgrade:** The `neutralize` flag triggers a separate code path in Odoo's `neutralize` command that loads all `neutralize.sql` files from installed modules.

---

## End-to-End Flow

```
1. Page Load (any website page)
   └── ir_http.get_frontend_session_info()
       └── Injects session.turnstile_site_key into frontend session

2. Form Render (s_website_form snippet OR <form data-captcha="...">)
   └── Form.start()  OR  TurnstileCaptcha.start()
       └── new TurnStile(action)
           ├── renderToElement("turnstile_container", { sitekey, action, mode })
           ├── insertBefore(submitButton, turnstileEl)
           ├── insertScripts() → hidden input + api.js script
           └── render() → window.turnstile.render(container)

3. User solves CAPTCHA
   └── Cloudflare JS sets input.turnstile_captcha_valid.value = "done"
       └── All .cf_form_disabled buttons re-enabled

4. Form Submit (POST /website/form/ or similar)
   └── Controller calls ir_http._verify_request_recaptcha_token(action)
       ├── request.params.pop('turnstile_captcha')  ← extracts token
       └── ir_http._verify_turnstile_token(ip, token, action)
           ├── requests.post(Cloudflare siteverify endpoint, timeout=3.05)
           └── Maps response → 'is_human' | 'wrong_token' | 'wrong_secret' | ...

5. Token valid → controller proceeds normally
   Token invalid → ValidationError / UserError raised → user sees error dialog
```

---

## Cross-Module Integration

| Module                  | Integration point                           | Mechanism                                             |
|-------------------------|---------------------------------------------|-------------------------------------------------------|
| `website`               | Base dependency                            | Provides form rendering, session, controllers         |
| `base`                  | `ir_http`, `ir_config_parameter`           | Base abstract model, system parameter storage          |
| `base_setup`            | `res_config_settings_view_form`            | Settings view inherited by `res_config_settings_view.xml` |
| `auth_signup`           | `_verify_request_recaptcha_token` call site | Signup can be protected by patching this method       |
| `test_http`             | `test_captcha.py`                          | Test helper patches `_verify_request_recaptcha_token`  |

The `website` module's form controller calls `_verify_request_recaptcha_token(action)` before processing a submission. Because both `google_recaptcha` and `website_cf_turnstile` extend `ir.http` with the same method name, **only one can be installed at a time** — attempting to install both will result in one overriding the other (method resolution order depends on load order). If both are needed, a custom module must implement a dispatcher.

---

## Security Considerations

| Concern                      | Mitigation                                                                 |
|------------------------------|-----------------------------------------------------------------------------|
| Secret key exposure          | Stored in `ir.config_parameter`, only accessible to `base.group_system`    |
| Token replay                 | Cloudflare marks `timeout-or-duplicate` tokens; mapped to `timeout` failure |
| Token stolen from DOM        | Token is a short-lived JWT; Cloudflare validates expiry server-side         |
| Action mismatch attack       | `_verify_turnstile_token` checks `result['action']` against expected action |
| IP spoofing                  | `remoteip` passed to Cloudflare; proxy must set `X-Forwarded-For` correctly |
| CSRF on CAPTCHA verify       | `request.params.pop` prevents token from being reflected/used twice        |
| JS injection in action name  | Action string passed as data attribute and used in Cloudflare API call; Cloudflare treats it as an opaque string |
| Bot protection bypass        | `@api.model` superuser context ensures CAPTCHA runs before ACL checks      |

---

## Performance Considerations

| Area                        | Impact                                                             |
|-----------------------------|--------------------------------------------------------------------|
| Page load                   | `get_frontend_session_info` adds one `get_param` call (~1ms)        |
| API call per submission     | 3.05s timeout; blocks controller thread during verification       |
| `requests.post`             | Synchronous; consider async worker for very high form volume       |
| `api.js` script             | Loaded once per page, cached by browser; ~5–15KB gzipped          |
| `TurnStile.clean()`         | O(n) DOM traversal per form destroy; n = number of widgets cleaned |

---

## Odoo 18 → 19 Changes

The `website_cf_turnstile` module is **new in Odoo 19**. It replaces the `google_recaptcha` module as the recommended CAPTCHA provider for Odoo website forms.

**Module rename:** `web_editor` → `html_editor` (separate module, not related to Turnstile).

| Aspect               | `google_recaptcha` (Odoo 18)              | `website_cf_turnstile` (Odoo 19)                        |
|----------------------|--------------------------------------------|--------------------------------------------------------|
| Provider             | Google reCAPTCHA v2/v3                    | Cloudflare Turnstile                                   |
| Interaction system   | Old snippet patch only                    | New `Interaction` registry + snippet patch             |
| Invisible mode       | reCAPTCHA v3 (always-on risk score)       | Turnstile `interaction-only` (default invisible)       |
| Frontend API         | `grecaptcha` global                       | `window.turnstile` global                              |
| Template             | Inline in controller                      | QWeb `turnstile.xml`                                   |
| Error handling       | Ad hoc                                    | Global `error_handlers` registry entry                  |
| Test isolation       | `patch_captcha_signup` helper             | `patchTurnStile()` helper (nullifies script URL)       |
| Token single-use     | Server-side replay cache (v3)             | Cloudflare-enforced single-use with `timeout-or-duplicate` |
| GDPR neutralize      | Not implemented                           | `neutralize.sql` clears both keys                       |

**L4 — Why a new module and not just a replacement:** The `google_recaptcha` module is retained in Odoo 19 for backward compatibility. New Odoo 19 installations get `website_cf_turnstile` by default via module dependency resolution in the website installer.

**L4 — Bot prevention depth:** Turnstile's bot detection operates at multiple layers:
1. **Client-side:** The Turnstile widget executes JavaScript-based challenge puzzles invisible to the user.
2. **Token issuance:** Cloudflare issues a signed token only after risk evaluation passes.
3. **Server-side verification:** Odoo POSTs the token to Cloudflare's `siteverify` endpoint; Cloudflare validates the token signature, expiry, and action context.
4. **Single-use enforcement:** Tokens cannot be replayed — Cloudflare marks them consumed after first verification.

This four-layer approach means a bot cannot bypass CAPTCHA by simply replaying a captured token, even if it intercepts the token via DOM inspection. The token's cryptographic validity window (~300 seconds) further limits the attack window.
