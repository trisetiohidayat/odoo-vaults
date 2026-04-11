---
Module: payment_razorpay_oauth
Version: 18.0.0
Type: addon
Tags: #odoo18 #payment_razorpay_oauth #payment
---

## Overview

`payment_razorpay_oauth` extends `payment_razorpay` with an OAuth-based onboarding flow for Razorpay. Instead of requiring merchants to manually enter API keys, the OAuth flow allows merchants to connect their Razorpay account directly from Odoo via a browser redirect. Handles token refresh and webhook setup automatically after OAuth authorization.

## Models

### payment.provider (extends base)
**Inheritance:** Extends `payment.provider` — adds OAuth fields, reuses all `payment_razorpay` payment processing

**Fields (all from `payment_razorpay` base):**

| Field | Type | Description |
|-------|------|-------------|
| razorpay_key_id | Char | OAuth-provided key ID (not required when OAuth is configured) |
| razorpay_key_secret | Char | OAuth-provided key secret (not required) |
| razorpay_webhook_secret | Char | Webhook secret |
| razorpay_account_id | Char | Razorpay Account ID (groups=base.group_system) |
| razorpay_refresh_token | Char | OAuth refresh token (groups=base.group_system) |
| razorpay_public_token | Char | OAuth public token (groups=base.group_system) |
| razorpay_access_token | Char | OAuth access token (groups=base.group_system) |
| razorpay_access_token_expiry | Datetime | Access token expiry (groups=base.group_system) |

**Action Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| action_razorpay_redirect_to_oauth_url | self | dict (URL action) | Builds OAuth authorization URL via Razorpay proxy. Checks company currency is in `SUPPORTED_CURRENCIES`. Redirects to OAuth URL with CSRF token and return URL |
| action_razorpay_reset_oauth_account | self | bool | Clears all OAuth tokens, account ID, sets state to 'disabled', `is_published=False`. Used to disconnect account |
| action_razorpay_create_webhook | self | dict (client notification) | Creates webhook via Razorpay API with random UUID secret, registers it for `HANDLED_WEBHOOK_EVENTS`. Sets `razorpay_webhook_secret`. Shows success notification |

**Constraints:**

| Constraint | Description |
|------------|-------------|
| `_check_razorpay_credentials_are_set_before_enabling` | If `state != 'disabled'` and `code == 'razorpay'`, requires either OAuth account (`razorpay_account_id`) OR both manual credentials (`razorpay_key_id` + `razorpay_key_secret`) |

**OAuth Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _razorpay_make_proxy_request | self, endpoint, payload=None | dict | Makes JSON-RPC 2.0 request to Odoo's Razorpay proxy (`OAUTH_URL`). Proxy handles actual Razorpay API calls for OAuth tokens. Raises `ValidationError` on connection error or proxy-side exceptions |
| _razorpay_get_public_token | self | str | Returns `razorpay_public_token` |
| _razorpay_get_access_token | self | str | Returns access token, auto-refreshing if expired. Triggers `_razorpay_refresh_access_token()` when `expiry < now` |
| _razorpay_refresh_access_token | self | None | Calls proxy to exchange `razorpay_refresh_token` for new tokens. Updates all token fields with new values and computed expiry |

## Security / Data

**Security:** All OAuth token fields (`razorpay_*_token`, `razorpay_account_id`, `razorpay_access_token_expiry`) restricted to `base.group_system`.

**Data:** `const.py` defines `OAUTH_URL = 'https://razorpay.api.odoo.com/api/razorpay/1'`

## Critical Notes

- **OAuth vs Manual:** Two authentication modes: (1) OAuth via `payment_razorpay_oauth` with account connection flow, (2) Manual key/secret via `payment_razorpay`.
- **Proxy architecture:** All Razorpay API calls for OAuth go through `razorpay.api.odoo.com` proxy (Odoo's hosted service) rather than direct to Razorpay.
- **Token auto-refresh:** `_razorpay_get_access_token()` checks expiry and auto-refreshes tokens that are about to expire.
- **Webhook auto-setup:** `action_razorpay_create_webhook()` programmatically creates the webhook on Razorpay, storing the generated secret.
- **Currency check:** Onboarding action checks company currency against Razorpay's supported currencies and shows a `RedirectWarning` if unsupported.
- **v17→v18:** This is a new module in Odoo 18 — `payment_razorpay` existed in v17 but OAuth flow is new in v18.
