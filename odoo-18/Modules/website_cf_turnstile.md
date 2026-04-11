---
Module: website_cf_turnstile
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_cf_turnstile
---

## Overview

Cloudflare Turnstile anti-bot integration. Replaces Google reCAPTCHA (removed in v18). Provides server-side token verification for forms rendered with the Turnstile widget. Uses Cloudflare's privacy-friendly challenge API.

**Key Dependencies:** `website`

**Python Files:** 3 model files

---

## Models

### ir_http.py — IrHttp

**Inheritance:** `ir.http`

| Method | Description |
|--------|-------------|
| `get_frontend_session_info()` | Adds `turnstile_site_key` from `ir.config_parameter` to session info |
| `_verify_request_recaptcha_token(action)` | Overrides to check both Google recaptcha result and Turnstile token; raises `ValidationError` or `UserError` on failure |
| `_verify_turnstile_token(ip_addr, token, action)` | Verifies token with Cloudflare API; returns string result code |

**Turnstile verification return codes:**
- `is_human`: Token valid, user is human
- `is_bot`: Token invalid, likely bot
- `no_secret`: No private key configured (allow)
- `wrong_action`: Token action mismatch
- `wrong_token`: Invalid or empty token
- `wrong_secret`: Invalid private key
- `timeout`: Request timed out (3.05s)
- `bad_request`: Malformed request

---

### res_config_settings.py — ResConfigSettings

**Inheritance:** `res.config.settings`

| Field | Type | Config Parameter | Groups |
|-------|------|-----------------|--------|
| `turnstile_site_key` | Char | `cf.turnstile_site_key` | base.group_system |
| `turnstile_secret_key` | Char | `cf.turnstile_secret_key` | base.group_system |

---

## Critical Notes

- Google recaptcha check is run first; if it passes, Turnstile is skipped
- Turnstile verification happens server-to-server via `https://challenges.cloudflare.com/turnstile/v0/siteverify`
- The `action` parameter is passed through from the form submission to match the token's expected action
- Timeout is 3.05 seconds to allow for Cloudflare's 3-second limit
- The `ir_http._verify_request_recaptcha_token` method is the central verification hook called by all form controllers
- v17→v18: This module replaced `website_cf_turnstile` (reCAPTCHA) entirely in v18
