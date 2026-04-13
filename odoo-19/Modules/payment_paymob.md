# Payment Paymob (`payment_paymob`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Paymob |
| **Technical** | `payment_paymob` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `payment` |

## Description
Multi-country payment provider for the Middle East and Africa. Paymob is a regional payment gateway covering Egypt, UAE, Saudi Arabia, Jordan, Oman, and Kenya. Supports card payments, mobile wallets (e.g., Vodafone Cash, Fawry), bank transfers, and installments. Uses Paymob's Unified Checkout API with server-side tokenization.

## Coverage
Egypt, UAE (Etisalat), Saudi Arabia, Jordan, Oman, Kenya

## Technical Notes
- API: Paymob REST API (v1/intention/)
- Country-specific API prefixes (e.g., `accept` for Egypt, `mars` for UAE)
- Access token expires hourly — auto-refreshed
- Supports installments via `installments_eg` payment method code

## Provider Configuration Fields

| Field | Type | Description |
|-------|------|-------------|
| `paymob_account_country_id` | Many2one | Paymob account country (determines API endpoint and currency) |
| `paymob_public_key` | Char | Paymob public key (frontend tokenization) |
| `paymob_secret_key` | Char | Paymob secret key (backend auth for client requests) |
| `paymob_hmac_key` | Char | HMAC key for webhook signature verification |
| `paymob_api_key` | Char | API key for access token generation |

## Models

### `payment.provider` (Extended)
**Fields:** Adds Paymob-specific credential fields.

**Key methods:**
- `_get_default_payment_method_codes()` — Returns Paymob default codes
- `_inverse_paymob_account_country_id()` — When country is set, auto-assigns the corresponding currency based on `const.CURRENCY_MAPPING` (only one currency per Paymob account)
- `action_sync_paymob_payment_methods()` — Syncs payment methods with Paymob portal; updates integration names so the gateway identifier matches Odoo's payment method codes
- `_match_paymob_payment_methods()` — Filters Paymob gateways: excludes Apple Pay, Google Pay, saved cards, Moto/Auth card methods; matches by `gateway_type` to Odoo codes; prefers most recent gateway per type
- `_update_payment_method_integration_names()` — PATCHes Paymob gateway `integration_name` to `{code}{environment}` format
- `_paymob_get_api_url()` — Returns `https://{country_prefix}.paymob.com` based on account country
- `_paymob_fetch_access_token()` — POSTs API key to `/api/auth/tokens`; token valid 1 hour
- `_build_request_headers()` — Builds Bearer auth header (secret key for client-side, access token for server-side)
- `_parse_response_error()` — Parses Paymob error messages (handles billing_data field validation errors)

### `payment.transaction` (Extended)
**Key methods:**
- `_compute_reference()` — Singularizes Paymob references for uniqueness
- `_get_specific_rendering_values()` — Creates Paymob "intention" (order) via `POST /v1/intention/`, returns `api_url` and `url_params` for Unified Checkout JS SDK
- `_paymob_prepare_payment_request_payload()` — Builds intention payload with amount in minor units, currency, payment methods (suffixes with `{code}{environment}`), billing data, webhook/return URLs
- `_extract_reference()` — Reads `merchant_order_id` from payment data
- `_extract_amount_data()` — Reads `amount_cents` and `currency` from Paymob response
- `_apply_updates()` — Maps `pending`/`success` flags to Odoo transaction states

**Special handling:**
- Oman Net: includes both `omannet` and `card` integration codes in the intention payload

## Constraints
- `_check_available_country_currency_ids()` — Only one currency per Paymob account; must be a Paymob-supported currency

## Related
- [Modules/payment](payment.md) — Base payment engine
- [Modules/payment_adyen](payment_adyen.md) — Adyen provider (similar terminal flow)
- [Modules/payment_razorpay](payment_razorpay.md) — Razorpay provider
