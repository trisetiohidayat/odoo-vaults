---
type: module
module: payment_stripe
tags: [odoo, odoo19, payment, stripe]
created: 2026-04-06
---

# Payment Provider: Stripe

## Overview
| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Stripe |
| **Technical** | `payment_stripe` |
| **Category** | Accounting/Payment Providers |
| **Version** | 2.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
An Irish-American payment provider covering the US and many other countries. Supports Express Checkout (Apple Pay, Google Pay), manual capture, partial refunds, tokenization, and Stripe Connect onboarding.

## Dependencies
- payment

## Key Models

### payment.provider (Inherited)
**File:** `models/payment_provider.py`

#### Fields
| Field | Type | Description |
|-------|------|-------------|
| `code` | Selection | Added `stripe` option to provider code |
| `stripe_publishable_key` | Char | Public key for frontend identification |
| `stripe_secret_key` | Char | Secret key for API calls (system group) |
| `stripe_webhook_secret` | Char | Webhook signing secret (system group) |

#### Feature Support
| Feature | Support |
|---------|---------|
| Express Checkout (Apple Pay, Google Pay) | `True` |
| Manual capture | `full_only` (full capture only, no partial) |
| Refund | `partial` |
| Tokenization | `True` |

#### Key Methods
| Method | Description |
|--------|-------------|
| `_compute_feature_support_fields()` | Enables express checkout, capture, refund, tokenization |
| `_stripe_get_inline_form_values()` | Returns JSON with publishable key, amount, billing details, tokenization flag |
| `_stripe_get_publishable_key()` | Returns Stripe publishable key |
| `action_start_onboarding()` | Starts Stripe Connect onboarding, creates connected account |
| `action_stripe_create_webhook()` | Creates webhook endpoint and sets secret |
| `action_stripe_verify_apple_pay_domain()` | Verifies domain for Apple Pay |
| `_stripe_onboarding_is_ongoing()` | Hook for modules to check onboarding state |

### payment.transaction (Inherited)
**File:** `models/payment_transaction.py` (in base payment module, Stripe adds specific logic)

#### Stripe Connect Methods
| Method | Description |
|--------|-------------|
| `_stripe_fetch_or_create_connected_account()` | Gets or creates Stripe connected account |
| `_stripe_prepare_connect_account_payload()` | Builds company data payload for Stripe |
| `_stripe_create_account_link()` | Creates onboarding URL (one-time use) |
| `_stripe_get_country()` | Maps company country to Stripe country code |

#### Request Building
| Method | Description |
|--------|-------------|
| `_build_request_url()` | Routes through proxy or direct to Stripe API |
| `_build_request_headers()` | Adds Bearer token and Stripe-Version header |
| `_parse_response_error()` | Extracts error message from Stripe response |

## Architecture Notes

**Webhook URL:** `StripeController._webhook_url` (joined with base URL)

**Stripe Connect Onboarding:** Full flow for connected accounts with state validation constraint (`_check_state_of_connected_account_is_never_test` and `_check_onboarding_of_enabled_provider_is_completed`).

**Proxy Architecture:** Uses proxy for some requests with `_prepare_json_rpc_payload` to pass both payload and proxy_data.

**Express Checkout:** Supports Apple Pay and Google Pay via `support_express_checkout`.

**Supported Countries:** Defined in `const.SUPPORTED_COUNTRIES`.

## Related
- [[Modules/payment]]
- [[Modules/payment_adyen]]
- [[Modules/payment_paypal]]