---
uuid: b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e
tags:
  - odoo
  - odoo19
  - modules
  - integration
  - security
  - captcha
  - google
  - website
  - forms
---

# Google reCAPTCHA (`google_recaptcha`)

## Overview

| Attribute | Value |
|-----------|-------|
| **Module** | `google_recaptcha` |
| **Category** | Hidden (Security Infrastructure) |
| **Depends** | `base_setup` |
| **Auto-install** | False |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **Source** | `odoo/addons/google_recaptcha/` |

## Description

The `google_recaptcha` module integrates **Google reCAPTCHA v3** into Odoo to protect public-facing forms from spam and bot abuse. Unlike reCAPTCHA v2 (which shows interactive checkboxes or image challenges), reCAPTCHA v3 is **invisible** — it analyzes user behavior and returns a **score** between 0.0 and 1.0, where higher scores indicate more human-like behavior.

The module:
- **Verifies** reCAPTCHA tokens server-side via an HTTP request to Google's API
- **Applies a configurable score threshold** to determine whether to accept or reject a submission
- **Works across multiple websites** in a multi-website Odoo installation, with per-website threshold overrides
- **Supports multiple action names** for fine-grained scoring (e.g., separate thresholds for login vs. contact forms)

## How reCAPTCHA v3 Works

reCAPTCHA v3 is a **risk analysis** system, not a challenge-response system:

```
┌──────────────┐    1. User loads page     ┌──────────────────────┐
│   Odoo       │ ────────────────────────→ │  Google reCAPTCHA v3  │
│   Frontend   │                           │  (invisible)         │
└──────────────┘                           └──────────────────────┘
       │                                         │
       │ 2. Google returns token (based on       │
       │    mouse movements, typing patterns,     │
       │    IP reputation, etc.)                 │
       ↓                                         │
┌──────────────┐                                 │
│ Form Submit  │ 3. Token + IP sent to server   │
│ (token in   │ ──────────────────────────────────→
│  params)    │                                    │
└──────────────┘    4. Server verifies token      │
       │              with Google API              │
       ↓              and checks score             ↓
┌──────────────────────────────────────────────────┐
│   Odoo Backend (ir.http._verify_request_recaptcha_token)
│   - Calls https://www.recaptcha.net/recaptcha/api/siteverify
│   - Gets score (0.0 - 1.0)
│   - Compares against minimum_score threshold
│   - Allows or blocks the request
└──────────────────────────────────────────────────┘
```

## Architecture

```
google_recaptcha/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── ir_http.py           # reCAPTCHA verification in HTTP pipeline
│   └── res_config_settings.py  # reCAPTCHA key configuration
└── static/
    └── src/
        ├── js/
        │   └── recaptcha.js         # Client-side reCAPTCHA v3 loader
        ├── interactions/            # Form interaction components
        ├── xml/
        │   └── recaptcha.xml        # reCAPTCHA widget XML
        └── scss/
            └── recaptcha.scss       # reCAPTCHA styling
```

## reCAPTCHA v3 vs v2

| Aspect | reCAPTCHA v2 | reCAPTCHA v3 |
|--------|-------------|--------------|
| **User interaction** | Checkbox / image selection | Invisible (no interaction) |
| **Challenge** | Interactive | None |
| **Return value** | Boolean (pass/fail) | Score (0.0 to 1.0) |
| **Thresholds** | Fixed | Configurable |
| **Per-action scoring** | No | Yes |
| **User experience** | Can interrupt workflow | Seamless |

Odoo uses **reCAPTCHA v3** exclusively, enabling bot protection without degrading the user experience.

## Models

### `ir.http` (Extension)

**File:** `models/ir_http.py`

The `ir.http` abstract model is extended to integrate reCAPTCHA verification into Odoo's HTTP request pipeline. This ensures reCAPTCHA protection is checked for all public requests that include a reCAPTCHA token.

```python
class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'
```

#### Session Info Extension

```python
def session_info(self):
    # Extends the web client's session info to include the reCAPTCHA public key
    session_info = super().session_info()
    return self._add_public_key_to_session_info(session_info)

@api.model
def get_frontend_session_info(self):
    # Same for the website frontend session info
    frontend_session_info = super().get_frontend_session_info()
    return self._add_public_key_to_session_info(frontend_session_info)

@api.model
def _add_public_key_to_session_info(self, session_info):
    # Adds recaptcha_public_key to session if:
    # 1. reCAPTCHA is enabled in config (enable_recaptcha = True)
    # 2. A public key is configured (recaptcha_public_key is set)
    if public_key and recaptcha_enabled:
        session_info['recaptcha_public_key'] = public_key
```

The frontend JavaScript reads `session_info.recaptcha_public_key` to know which site key to use when calling the reCAPTCHA API.

#### Token Verification Entry Point

```python
@api.model
def _verify_request_recaptcha_token(self, action):
    # Called by controllers when a public form is submitted
    # Checks if:
    # 1. reCAPTCHA is enabled
    # 2. Token is provided in request params
    # Raises ValidationError or UserError on failure
    ip_addr = request.httprequest.remote_addr
    token = request.params.pop('recaptcha_token_response', False)
    recaptcha_result = request.env['ir.http']._verify_recaptcha_token(ip_addr, token, action)
    # Returns (allows request) or raises (blocks request)
```

The `action` parameter corresponds to reCAPTCHA action names registered on the Google developer console. Google tracks accuracy per action.

#### Core Verification

```python
@api.model
def _verify_recaptcha_token(self, ip_addr, token, action=False):
    # Makes POST to https://www.recaptcha.net/recaptcha/api/siteverify
    # Returns string codes:
    #
    # 'is_human'  - Token valid, score >= threshold, action matches
    # 'is_bot'     - Token valid but score < threshold
    # 'no_secret'  - No private key configured (skips verification)
    # 'wrong_secret' - Private key is invalid
    # 'wrong_token'  - Token is invalid, expired, or malformed
    # 'wrong_action' - Action name doesn't match
    # 'timeout'      - Google's API timed out
    # 'bad_request'  - Malformed request to Google API
```

The method returns a **string code** rather than boolean, enabling callers to distinguish between different failure modes.

**Verification flow:**
1. Retrieve private key from `ir.config_parameter` (`recaptcha_private_key`)
2. If no key configured, return `'no_secret'` (allow request — backwards compatible)
3. Make HTTP POST to `https://www.recaptcha.net/recaptcha/api/siteverify` with:
   - `secret`: The private key
   - `response`: The token from the frontend
   - `remoteip`: The user's IP address
4. Parse the JSON response
5. Check `success` flag and `score` value against minimum threshold
6. Log results and return appropriate code

**Score thresholds:**
```python
min_score = request.env['ir.config_parameter'].sudo().get_param('recaptcha_min_score')
# Default: 0.7 (configured in res.config.settings)

if score < float(min_score):
    return 'is_bot'
```

A score below the threshold is treated as a bot attempt. The default threshold of 0.7 is reasonably strict but allows most legitimate users through.

### `res.config.settings` (Extension)

**File:** `models/res_config_settings.py`

Configures reCAPTCHA keys and the minimum acceptable score:

| Field | Config Parameter | Type | Default | Description |
|-------|-----------------|------|---------|-------------|
| `enable_recaptcha` | `enable_recaptcha` | Boolean | `True` | Master switch |
| `recaptcha_public_key` | `recaptcha_public_key` | Char | — | Site key (frontend) |
| `recaptcha_private_key` | `recaptcha_private_key` | Char | — | Secret key (backend) |
| `recaptcha_min_score` | `recaptcha_min_score` | Float | `0.7` | Minimum score threshold |

**Field definitions:**
```python
enable_recaptcha = fields.Boolean(
    "Enable reCAPTCHA",
    config_parameter='enable_recaptcha',
    groups='base.group_system',
    default=True,
)

recaptcha_public_key = fields.Char(
    "Site Key",
    config_parameter='recaptcha_public_key',
    groups='base.group_system',
)

recaptcha_private_key = fields.Char(
    "Secret Key",
    config_parameter='recaptcha_private_key',
    groups='base.group_system',
)

recaptcha_min_score = fields.Float(
    "Minimum score",
    config_parameter='recaptcha_min_score',
    groups='base.group_system',
    default="0.7",
    help="By default, should be one of 0.1, 0.3, 0.7, 0.9.\n"
         "1.0 is very likely a good interaction, 0.0 is very likely a bot",
)
```

**Configuration path:** `Settings > General Settings > Website > Google reCAPTCHA`

Note: `enable_recaptcha` defaults to `True` even though the field is a config_parameter. The `get_values()` method explicitly sets this:

```python
def get_values(self):
    res = super().get_values()
    icp = self.env['ir.config_parameter'].sudo()
    res['enable_recaptcha'] = str2bool(icp.get_param('enable_recaptcha', default=True))
    return res
```

## Verification Response Codes

The verification method returns these codes, each handled differently:

| Code | Meaning | Action | Log Level |
|------|---------|--------|-----------|
| `is_human` | Valid token, score OK, action OK | Allow | INFO |
| `no_secret` | No private key configured | Allow (skip) | — |
| `wrong_secret` | Private key is invalid | Block + UserError | WARNING |
| `wrong_token` | Token invalid/expired | Block + ValidationError | WARNING |
| `wrong_action` | Action name mismatch | Block + UserError | WARNING |
| `timeout` | Google's API timed out | Block + UserError | ERROR |
| `bad_request` | Malformed request to Google | Block + UserError | ERROR |
| `is_bot` | Score below threshold | Block + UserError | WARNING |

The frontend interprets `no_secret` as "reCAPTCHA not configured, proceed normally" to avoid blocking requests when the admin hasn't set up keys.

## Google API Integration

### Endpoint

```
POST https://www.recaptcha.net/recaptcha/api/siteverify
```

Using `recaptcha.net` (rather than `google.com`) is important in regions where Google domains are blocked — reCAPTCHA automatically resolves to the nearest available infrastructure.

### Request Parameters

| Parameter | Description |
|-----------|-------------|
| `secret` | The private key from Settings |
| `response` | The token generated by the frontend reCAPTCHA API |
| `remoteip` | The end user's IP address |

### Response Format

```json
{
  "success": true,
  "score": 0.9,
  "action": "submit",
  "challenge_ts": "2024-01-01T00:00:00Z",
  "hostname": "example.com",
  "error-codes": []
}
```

Key fields:
- **`success`**: Whether the token is valid (but does NOT indicate if it's a human — check `score`)
- **`score`**: A number between 0.0 and 1.0 — lower scores indicate bot-like behavior
- **`action`**: The action name that was registered when the token was generated
- **`error-codes`**: Present when `success` is false (e.g., `missing-input-secret`, `invalid-input-response`)

## Frontend Integration

The frontend JavaScript (`recaptcha.js`) loads the reCAPTCHA v3 API:

```html
<script src="https://www.google.com/recaptcha/api.js?render={public_key}"></script>
```

When a protected form is submitted:
1. The JS calls ` grecaptcha.execute(publicKey, {action: 'submit'})`
2. Google returns a token based on behavioral analysis
3. The token is added to the form as a hidden field (`recaptcha_token_response`)
4. Form submits normally to the server
5. Server calls `_verify_recaptcha_token()` to validate

The `action` parameter in the frontend call should match the `action` parameter passed to `_verify_request_recaptcha_token()` in the backend. Google tracks accuracy per action.

## Multi-Website Support

Odoo's multi-website architecture allows different websites to have different reCAPTCHA thresholds. This is configured via:

- **Global threshold**: `recaptcha_min_score` in Settings
- **Per-website threshold**: `website.recaptcha_frontend_threshold` on the website record (if the website module is installed)

The frontend JavaScript reads the appropriate threshold from the website configuration and only shows reCAPTCHA when the configured threshold is above zero.

## Obtaining reCAPTCHA Keys

1. Go to the [Google reCAPTCHA Admin Console](https://www.google.com/recaptcha/admin)
2. Register a new site with **reCAPTCHA v3** type
3. Add your domain(s) to the allowed domains list
4. You will receive:
   - **Site Key** (starts with the prefix, used in frontend JavaScript)
   - **Secret Key** (used for server-side verification)

For multi-website Odoo, register each website domain.

## Threshold Recommendations

| Threshold | Use Case | Blocking Rate |
|-----------|----------|---------------|
| 0.9 | Very high security (some legitimate users may be blocked) | ~5-10% |
| 0.7 | Balanced (default, recommended for most forms) | ~1-3% |
| 0.5 | Lenient (more users through, some bots may pass) | ~0.5% |
| 0.1 | Minimal protection | ~0% |

Google provides aggregate accuracy data per action in the reCAPTCHA admin console, which can guide threshold tuning.

## Limitations

1. **Score is per-token, not per-IP**: reCAPTCHA v3 analyzes individual browser sessions, not IP addresses. A sophisticated bot could potentially generate valid tokens.
2. **Relies on Google's infrastructure**: If Google's API is unreachable, the `timeout` code is returned and requests are blocked (configurable behavior).
3. **No CAPTCHA challenge fallback**: Unlike v2, there is no fallback to an interactive challenge for borderline scores.
4. **Privacy considerations**: reCAPTCHA v3 sends user behavior data to Google. Privacy-sensitive deployments may need to disclose this.

## Related

- [Modules/website](Modules/website.md) — Website builder with form protection
- [Modules/web](Modules/web.md) — Web framework and HTTP pipeline
- [Modules/auth_signup](Modules/auth_signup.md) — User registration (often protected by reCAPTCHA)
- [Modules/website_crm](Modules/website_crm.md) — Website lead capture forms
