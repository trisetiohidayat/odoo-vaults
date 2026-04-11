---
Module: payment_flutterwave
Version: 18.0.0
Type: addon
Tags: #odoo18 #payment_flutterwave #payment
---

## Overview

`payment_flutterwave` integrates Odoo with Flutterwave, an African-focused payment gateway supporting 30+ currencies and payment methods (card, M-Pesa, bank transfer). Uses tokenized payment flows with 3-D Secure redirect support. The provider creates a payment link via Flutterwave's v3 API and redirects the user there; payment status is verified via webhook callback.

## Models

### payment.provider (extends base)
**Inheritance:** `payment.provider` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| code | selection | Adds `('flutterwave', "Flutterwave")`. `ondelete='set default'` |
| flutterwave_public_key | Char | Public key identifier (required_if_provider='flutterwave') |
| flutterwave_secret_key | Char | Secret key (required_if_provider='flutterwave', groups=base.group_system) |
| flutterwave_webhook_secret | Char | Webhook HMAC secret (required_if_provider='flutterwave', groups=base.group_system) |

**Feature Support Fields:** `support_tokenization=True`

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_compatible_providers | *args, is_validation=False, report=None, **kwargs | recordset | **Excludes Flutterwave for validation operations** (adds to report with reason 'validation_not_supported'). Validates tokens via Flutterwave's tokenized flow which is incompatible with validation |
| _get_supported_currencies | self | recordset | Filters to 21 African + international currencies: GBP, CAD, XAF, CLP, COP, EGP, EUR, GHS, GNF, KES, MWK, MAD, NGN, RWF, SLL, STD, ZAR, TZS, UGX, USD, XOF, ZMW |
| _flutterwave_make_request | self, endpoint, payload=None, method='POST' | dict | POST/GET to `https://api.flutterwave.com/v3/`. Sets `Authorization: Bearer {secret_key}`. Handles HTTP errors and connection errors |
| _get_default_payment_method_codes | self | set | Returns `{'card', 'mpesa', 'visa', 'mastercard', 'amex', 'discover'}` |

### payment.transaction (extends base)
**Inheritance:** `payment.transaction` (classic `_inherit`)

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_specific_processing_values | self, processing_values | dict | For `online_token` operations with pending state + URL-like provider_reference, renders redirect form to the authorization URL (3DS redirect) |
| _get_specific_rendering_values | self, processing_values | dict | Creates Flutterwave payment via `/payments` endpoint. Sends `tx_ref=reference`, `amount`, `currency`, `redirect_url`, `customer` (email, name, phonenumber), `customizations` (company name + logo), `payment_options`. Returns `{'api_url': payment_link_data['data']['link']}` |
| _send_payment_request | self | None | Token-based payment via `/tokenized-charges`. Reads `token.provider_ref` as token, `token.flutterwave_customer_email`, sends amount, currency, country, `tx_ref`, name, IP, `redirect_url`. Handles response |
| _get_tx_from_notification_data | self, provider_code, notification_data | recordset | Looks up by `tx_ref` or `txRef` |
| _process_notification_data | self, notification_data | None | **Always verifies payment** via GET `/transactions/verify_by_reference`. Sets `provider_reference` from `verified_data['id']`. Maps `status`: pending → `_set_pending` (with auth URL capture), successful → `_set_done` + tokenize if `tokenize=True` and card token in response, cancelled → `_set_canceled`, failed → error |
| _flutterwave_tokenize_from_notification_data | self, notification_data | None | Creates token with `flutterwave_customer_email` from `notification_data['customer']['email']`, `provider_ref` = card token, `payment_details` = last 4 digits |
| _flutterwave_is_authorization_pending | self | recordset | Detects 3DS redirect scenario: `provider_code='flutterwave'`, `operation='online_token'`, `state='pending'`, `provider_reference` looks like a URL (contains 'https') |

### payment.token (extends base)
**Inheritance:** `payment.token` (classic `_inherit`)

| Field | Type | Description |
|-------|------|-------------|
| flutterwave_customer_email | Char | Customer email at token creation time (readonly) |

## Security / Data

**Security:** `flutterwave_secret_key`, `flutterwave_webhook_secret` restricted to `base.group_system`.

**Data:** None.

## Critical Notes

- **Validation not supported:** Flutterwave does not support $0.00 validation transactions — `_get_compatible_providers` filters it out for `is_validation=True` operations.
- **Payment verification:** Every webhook notification triggers a `/transactions/verify_by_reference` API call before updating transaction state — prevents forged notifications.
- **3DS redirect flow:** When token payment requires 3DS authentication, `_flutterwave_is_authorization_pending()` detects this and `_get_specific_processing_values()` renders a redirect form to the auth URL.
- **Tokenization:** Tokenize requests (`tokenize=True`) result in a card token stored on `payment.token` with `flutterwave_customer_email` preserved for subsequent token payments.
- **v17→v18:** No breaking changes observed. API v3 unchanged.
- **Webhook acknowledgment:** Always acknowledges to prevent Flutterwave from retrying (even on validation errors).
