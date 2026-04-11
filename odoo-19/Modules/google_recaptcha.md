# Google reCAPTCHA (`google_recaptcha`)

**Category:** Hidden
**Depends:** `base_setup`
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

Integrates Google reCAPTCHA v3 into Odoo to prevent bot spam on public pages. reCAPTCHA v3 returns a score (0.0 to 1.0) based on user behavior, rather than presenting interactive challenges. Server-side verification is performed via an HTTP request to Google's API.

## Models

### `ir.http` (Extension)
Extends `ir.http` to inject reCAPTCHA verification into public requests.

**Key Methods:**
- `session_info()` / `get_frontend_session_info()` — Extends session info to include whether reCAPTCHA is enabled for the current website.
- `_add_public_key_to_session_info(session_info)` — Adds reCAPTCHA site key to session for frontend use.
- `_verify_request_recaptcha_token(action)` — Verifies the reCAPTCHA token for a given action (e.g., `'submit'`, `'login'`). Returns True if score >= threshold.
- `_verify_recaptcha_token(ip_addr, token, action=False)` — Sends token to Google reCAPTCHA API for verification. Returns True if successful and score >= threshold. Raises validation error if verification fails.

### `res.config.settings` (Extension)
Adds reCAPTCHA configuration to Odoo Settings.

**Methods:**
- `get_values()` — Reads reCAPTCHA settings from `ir.config_parameter`.
- `set_values()` — Persists reCAPTCHA settings to `ir.config_parameter`.

**Config Parameters:**
- `google_recaptcha_public_key` — Site key (public)
- `google_recaptcha_private_key` — Secret key (private, server-side only)
- `google_recaptcha.minimum_score` — Minimum acceptable score (default ~0.5)
- `website.recaptcha_frontend_threshold` — Per-website score threshold

## Frontend Assets

- `static/src/js/recaptcha.js` — Client-side reCAPTCHA v3 integration
- `static/src/interactions/**/*` — Form interaction components
- `static/src/xml/recaptcha.xml` — Backend reCAPTCHA widget XML
- `static/src/scss/recaptcha.scss` — reCAPTCHA styling
