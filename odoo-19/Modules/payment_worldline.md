# Payment Provider: Worldline

## Overview

- **Name**: Payment Provider: Worldline
- **Code**: `payment_worldline`
- **Category**: Accounting/Payment Providers
- **Module Version**: 1.0
- **License**: LGPL-3
- **Author**: Odoo S.A.
- **Depends**: `payment`

## Description

A French payment provider covering several European countries. Integrates with Worldline's Hosted Checkout API using HMAC-SHA256 signed requests. Supports card payments (hosted checkout and tokenized direct API) as well as redirected alternative payment methods.

## Key Features

- Hosted Checkout Session for redirect-based payments
- Tokenization for card payments (token stored on Worldline)
- Redirect payment methods (bank transfers, wallets)
- Alternative to capture flow (SALE authorization mode)
- Automatic 3DS handling via hosted checkout
- HMAC-SHA256 request signing with RFC1123 timestamps
- Idempotency key support for safe retry

## Provider Configuration

**Fields on `payment.provider`:**
- `code = 'worldline'`
- `worldline_pspid` -- Worldline PSPID (merchant account ID)
- `worldline_api_key` -- API Key for HMAC authentication
- `worldline_api_secret` -- API Secret for HMAC authentication (group: base.group_system)
- `worldline_webhook_key` -- Webhook key (group: base.group_system)
- `worldline_webhook_secret` -- Webhook secret (group: base.group_system)

**Feature Support:**
- `support_tokenization = True`

## Models

### `payment.provider` (inherited)

**Key Methods:**
- `_compute_feature_support_fields()` -- Enables tokenization.
- `_get_default_payment_method_codes()` -- Returns `const.DEFAULT_PAYMENT_METHOD_CODES`.
- `_build_request_url(endpoint)` -- Returns `{api_url}/v2/{pspid}/{endpoint}`.
- `_worldline_get_api_url()` -- Returns `https://payment.direct.worldline-solutions.com` in production, `https://payment.preprod.direct.worldline-solutions.com` in test mode.
- `_build_request_headers(method, endpoint, idempotency_key)` -- Builds HMAC-SHA256 auth header with RFC1123 timestamp, multi-line signing string, and idempotency key support.
- `_worldline_calculate_signature()` -- Implements multi-line HMAC-SHA256 signing string per Worldline docs.
- `_parse_response_error()` -- Collects all error messages from `errors` array in response.

### `payment.transaction` (inherited)

**Key Methods:**
- `_compute_reference()` -- Worldline limits references to 30 characters. If exceeded, re-generates with `singularize_reference_prefix(prefix='WL')`.
- `_get_specific_processing_values()` -- For tokenized payments that fail with `AUTHORIZATION_REQUESTED` (3DS redirect needed): resets to draft, switches to `online_redirect`, returns `{'force_flow': 'redirect'}`.
- `_get_specific_rendering_values()` -- Creates hosted checkout session via `_worldline_create_checkout_session()`. For redirect PMs: uses `redirectPaymentMethodSpecificInput`. For card PMs: uses `cardPaymentMethodSpecificInput` with `authorizationMode='SALE'` and `tokenize` flag.
- `_send_payment_request()` -- For tokenized card payments: sends POST to `/payments` with stored token, `authorizationMode='SALE'`, unscheduled card-on-file fields. Uses idempotency key.
- `_extract_reference()` -- Extracts `merchantReference` from nested `paymentResult.payment.paymentOutput.references`.
- `_extract_amount_data()` -- Extracts `amountOfMoney.amount` and `currencyCode`, converts from minor to major units.
- `_apply_updates()` -- Extracts payment data from `paymentResult`. Maps status: pending: `AUTHORIZATION_REQUESTED` on token ops -> `_set_error()`; `PENDING_CAPTURE`/`CAPTURE_REQUESTED` on validation -> `_set_done()`; else -> `_set_pending()`; done -> `_set_done()`; cancel/declined -> error with code. Unknown -> `_set_error()`.
- `_worldline_extract_payment_method_data()` -- Helper to extract from card-specific or redirect-specific output.
- `_extract_token_values()` -- Extracts card last 4 digits and `token` from payment method data.

## Constants (const.py)

- `PAYMENT_METHODS_MAPPING` -- Maps Odoo payment method codes to Worldline payment product IDs
- `REDIRECT_PAYMENT_METHODS` -- Codes that use redirect flow
- `PAYMENT_STATUS_MAPPING` -- Maps Worldline status strings to Odoo states
- `DEFAULT_PAYMENT_METHOD_CODES` -- Default payment method codes

## Related

- [Modules/payment](odoo-18/Modules/payment.md) -- Base payment module
- [Modules/payment_buckaroo](odoo-18/Modules/payment_buckaroo.md) -- Another European payment provider
- [Modules/payment_mollie](odoo-18/Modules/payment_mollie.md) -- Another Dutch/European provider
