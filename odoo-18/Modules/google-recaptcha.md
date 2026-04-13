---
Module: google_recaptcha
Version: Odoo 18
Type: Integration
Tags: #odoo18, #integration, #security, #recaptcha
Related: [Core/API](Core/API.md), [Modules/Mail](Modules/Mail.md), [Modules/Web](Modules/Web.md)
---

# Google reCAPTCHA Integration (`google_recaptcha`)

> **Source:** `odoo/addons/google_recaptcha/`
> **Depends:** `base_setup`
> **Category:** Hidden
> **License:** LGPL-3

## Overview

The `google_recaptcha` module integrates Google reCAPTCHA v3 into Odoo to protect public-facing forms (signup, password reset) from spam and bot abuse. Unlike reCAPTCHA v2 (the checkbox widget), v3 returns a **score** (0.0 to 1.0) based on user behavior, allowing server-side decisions without any user interaction. The badge can be hidden if legal requirements are met.

**Implements:** reCAPTCHA v3 (invisible, score-based)

---

## Architecture

```
google_recaptcha/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── ir_http.py          # ir.http extension — token verification
│   └── res_config_settings.py  # res.config.settings — key storage
├── controllers/            # (none — no controller needed)
├── views/
│   └── res_config_settings_view.xml  # Settings form extension
└── static/
    ├── src/js/
    │   ├── recaptcha.js    # ReCaptcha JS class (frontend)
    │   └── signup.js       # Public widget for signup/reset-password forms
    ├── src/scss/
    │   ├── recaptcha.scss   # Hide module toggle in settings
    │   └── recaptcha_backend.scss  # Hide grecaptcha-badge
    └── src/xml/
        └── recaptcha.xml   # Legal terms QWeb template
```

---

## Configuration Parameters

Stored in `ir.config_parameter` (system parameters):

| Parameter Key | Type | Description |
|---|---|---|
| `recaptcha_public_key` | Char | **Site Key** — safe to expose in frontend JavaScript. Configured via Settings > General > reCAPTCHA. Groups: `base.group_system` |
| `recaptcha_private_key` | Char | **Secret Key** — used only for server-side verification. Never exposed client-side. Groups: `base.group_system` |
| `recaptcha_min_score` | Float | Minimum acceptable score threshold. Default `0.7`. Lower = more permissive, Higher = stricter. Legal values: `0.1`, `0.3`, `0.7`, `0.9` |

### Configuration Flow

1. Admin goes to **Settings > General Settings**
2. Finds the **reCAPTCHA** section
3. Enters Site Key and Secret Key from [Google reCAPTCHA Admin Console](https://www.google.com/recaptcha/admin/create)
4. Sets minimum score (default 0.7)
5. Keys are stored as `ir.config_parameter` records with `sudo()` access

---

## Model: `ir.http` (Extended)

> **File:** `models/ir_http.py`
> **Inheritance:** Extends `ir.http` (abstract model)
> **Purpose:** Injects reCAPTCHA public key into frontend sessions; verifies tokens server-side

### Methods

#### `session_info()` — Extended
Injects `recaptcha_public_key` into the session info returned to the web client.

```python
def session_info(self):
    session_info = super().session_info()
    return self._add_public_key_to_session_info(session_info)
```

#### `get_frontend_session_info()` — Extended
Same for the public (frontend) session info.

```python
@api.model
def get_frontend_session_info(self):
    frontend_session_info = super().get_frontend_session_info()
    return self._add_public_key_to_session_info(frontend_session_info)
```

#### `_add_public_key_to_session_info(session_info)`
Reads `recaptcha_public_key` from `ir.config_parameter` and adds it to the session dict. If no key is configured, the field is absent.

```python
@api.model
def _add_public_key_to_session_info(self, session_info):
    public_key = self.env['ir.config_parameter'].sudo().get_param('recaptcha_public_key')
    if public_key:
        session_info['recaptcha_public_key'] = public_key
    return session_info
```

#### `_verify_request_recaptcha_token(action)`
Entry point called by form controllers to verify the token. Called by forms **before** processing the submission.

```python
@api.model
def _verify_request_recaptcha_token(self, action):
    ip_addr = request.httprequest.remote_addr
    token = request.params.pop('recaptcha_token_response', False)
    recaptcha_result = request.env['ir.http']._verify_recaptcha_token(ip_addr, token, action)
    # Returns True or raises ValidationError/UserError
```

**Possible return values from `_verify_recaptcha_token`:**

| Result | Meaning | HTTP Method Raised |
|---|---|---|
| `is_human` | Token valid, score above threshold | (none — proceed) |
| `no_secret` | No private key configured | (none — skip check) |
| `wrong_secret` | Secret key is invalid | `ValidationError` |
| `wrong_token` | Token missing or malformed | `ValidationError` |
| `timeout` | Token too old / request timed out | `UserError` |
| `bad_request` | Malformed request to Google | `UserError` |
| `is_bot` | Score below minimum threshold | `False` |

#### `_verify_recaptcha_token(ip_addr, token, action=False)`
Core verification method. Makes a `POST` to `https://www.recaptcha.net/recaptcha/api/siteverify`.

```python
@api.model
def _verify_recaptcha_token(self, ip_addr, token, action=False):
    private_key = request.env['ir.config_parameter'].sudo().get_param('recaptcha_private_key')
    if not private_key:
        return 'no_secret'
    min_score = request.env['ir.config_parameter'].sudo().get_param('recaptcha_min_score')
    r = requests.post('https://www.recaptcha.net/recaptcha/api/siteverify', {
        'secret': private_key,
        'response': token,
        'remoteip': ip_addr,
    }, timeout=2)
```

**L4 — How the verification flow works end-to-end:**

1. **Frontend:** `ReCaptcha.loadLibs()` loads `https://www.recaptcha.net/recaptcha/api.js?render=<SITE_KEY>` and waits for `grecaptcha.ready()`
2. **Frontend:** On form submit, `ReCaptcha.getToken(action)` calls `window.grecaptcha.execute(publicKey, {action})` to get a token. The action name (e.g., `"signup"`, `"password_reset"`) is embedded in the token.
3. **Frontend:** The token is appended as a hidden field `recaptcha_token_response` to the form.
4. **HTTP Request:** Form submits to Odoo controller (e.g., `/web/session/authenticate` or `/web/signup`).
5. **Controller:** Calls `_verify_request_recaptcha_token(action)` **before** processing.
6. **Backend:** `_verify_recaptcha_token()` POSTs the token + private key + IP address to Google reCAPTCHA API.
7. **Google response:** Contains `{"success": bool, "score": float, "action": string, "error-codes": [...]}`.
8. **Score check:** If `score < float(min_score)` → `is_bot`.
9. **Action check:** If `action` param was passed and `result['action'] != action` → `wrong_action`.
10. **Error mapping:** Google's `error-codes` are mapped to Odoo's result strings.
11. **Result:** `_verify_request_recaptcha_token` either returns `True` (proceed) or raises `ValidationError`/`UserError`.

---

## Model: `res.config.settings` (Extended)

> **File:** `models/res_config_settings.py`

| Field | Type | Config Parameter | Groups | Notes |
|---|---|---|---|---|
| `recaptcha_public_key` | Char | `recaptcha_public_key` | `base.group_system` | Google Site Key |
| `recaptcha_private_key` | Char | `recaptcha_private_key` | `base.group_system` | Google Secret Key |
| `recaptcha_min_score` | Float | `recaptcha_min_score` | `base.group_system` | Default `0.7` |

**Note:** Uses `config_parameter=` — values are stored directly as `ir.config_parameter` records, not as `res.config.settings` fields. This is the Odoo "parameter pattern" for settings.

---

## Frontend JavaScript (`ReCaptcha` Class)

> **File:** `static/src/js/recaptcha.js`

### `ReCaptcha` Class

```javascript
export class ReCaptcha {
    constructor() {
        this._publicKey = session.recaptcha_public_key;
    }
    loadLibs() { /* loads grecaptcha API */ }
    async getToken(action) { /* returns {token: ...} or {error: ...} or {message: ...} */ }
}
```

- Reads public key from `session.recaptcha_public_key` (injected server-side)
- Loads `https://www.recaptcha.net/recaptcha/api.js?render=<key>` lazily on `willStart`
- Uses `grecaptcha.ready()` promise pattern (no explicit `onload` callback)
- Returns token string wrapped in an object

### `SignupCaptcha` / `ResetPasswordCaptcha` Widgets

> **File:** `static/src/js/signup.js`

Two `publicWidget` instances auto-attach to forms:

| Widget | Selector | Token Name (Action) |
|---|---|---|
| `SignupCaptcha` | `.oe_signup_form` | `"signup"` |
| `ResetPasswordCaptcha` | `.oe_reset_password_form` | `"password_reset"` |

Both intercept the `submit` event, call `getToken(tokenName)`, append the token as `<input type="hidden" name="recaptcha_token_response">`, then re-trigger submission.

---

## Protected Forms

| Form | Route | Action | Module |
|---|---|---|---|
| Signup form | `/web/signup` | `"signup"` | `web` |
| Reset password | `/web/reset_password` | `"password_reset"` | `web` |

Any other form wanting protection can call `ReCaptcha.getToken(actionName)` and pass `recaptcha_token_response` in the request params, then invoke `_verify_request_recaptcha_token(actionName)` server-side before processing.

---

## Google reCAPTCHA v3 Score Interpretation

| Score Range | Interpretation | Odoo Behavior |
|---|---|---|
| 1.0 | Very likely human | `is_human` — allow |
| 0.7–0.9 | Likely human | `is_human` — allow |
| 0.5–0.7 | Suspicious | `is_human` or `is_bot` depending on threshold |
| 0.0–0.5 | Very likely bot | `is_bot` — reject |

The default threshold of `0.7` blocks roughly 30% of bots while allowing most legitimate users through.

---

## View Extension

> **File:** `views/res_config_settings_view.xml`
> **Inherits:** `base_setup.res_config_settings_view_form`

The module extends the general settings form (Settings > General Settings) by finding the existing `<setting id="recaptcha">` placeholder and replacing its content with three input fields (public key, private key, min score) plus a link to the Google reCAPTCHA admin console.

The module is **always installed** (it is a hidden module), so the toggle in the settings UI is hidden via CSS (`pointer-events: none; display: none`).

---

## Legal / Privacy Note

The `grecaptcha-badge` is hidden via CSS (`visibility: hidden`) in the backend bundle. Hiding the badge is only permitted under Google's policy if a proper legal notice is displayed. The module provides a QWeb template (`google_recaptcha.recaptcha_legal_terms`) that renders the required Google privacy/TOS notice. Module integrators should include this template on pages using reCAPTCHA.
