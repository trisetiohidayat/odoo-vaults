---
Module: payment_mollie
Version: 18.0.0
Type: addon
Tags: #odoo18 #payment_mollie #payment
---

## Overview

`payment_mollie` integrates Odoo with Mollie, a European payment provider supporting 40+ currencies and payment methods (iDEAL, credit card, SEPA Direct Debit, Klarna, KBC, Przelewy24, Apple Pay). Payment creation is API-driven with Mollie managing the checkout flow; Odoo receives webhook notifications. Uses Mollie API v2 with a custom User-Agent string identifying the Odoo/Mollie integration.

## Models

### payment.provider (extends base)
**Inheritance:** `payment.provider` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| code | selection | Adds `('mollie', 'Mollie')`. `ondelete='set default'` |
| mollie_api_key | Char | Mollie API Key (required_if_provider='mollie', groups=base.group_system) |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_supported_currencies | self | recordset | Filters to Mollie's 30 supported currencies |
| _mollie_make_request | self, endpoint, data=None, method='POST' | dict | POST/GET to `https://api.mollie.com/v2/{endpoint}`. Sets custom `User-Agent: Odoo/{version} MollieNativeOdoo/{module_version}`. Uses Bearer token from API key |
| _get_default_payment_method_codes | self | set | Returns `{'card', 'ideal', 'visa', 'mastercard', 'amex', 'discover'}` |

### payment.transaction (extends base)
**Inheritance:** `payment.transaction` (classic `_inherit`)

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_specific_rendering_values | self, processing_values | dict | Creates Mollie payment via `/payments`. Sets `provider_reference` immediately from `payment_data['id']`. Returns `api_url` (checkout URL from `_links.checkout.href`) and decoded `url_params` |
| _mollie_prepare_payment_request_payload | self | dict | Builds payload: `description` (reference), `amount` (currency + value string with proper decimal places), `locale`, `method` (single-item list), `redirectUrl` (with `?ref={reference}` appended), `webhookUrl` (with `?ref={reference}` appended). Decimal places from `CURRENCY_MINOR_UNITS` or currency's default. Locale filtered to `SUPPORTED_LOCALES` |
| _get_tx_from_notification_data | self, provider_code, notification_data | recordset | Looks up by `ref` query param (passed via webhook URL) |
| _process_notification_data | self, notification_data | None | Fetches current payment status via GET `/payments/{provider_reference}`. Maps `status`: 'pending'/'open' → pending, 'authorized' → authorized, 'paid' → done, 'expired'/'canceled'/'failed' → canceled with message, else error |

## Security / Data

**Security:** `mollie_api_key` restricted to `base.group_system`. No ACL file.

**Data:** None.

## Critical Notes

- **Provider reference set early:** `_get_specific_rendering_values` sets `provider_reference` immediately so the webhook can match transactions even before the redirect back to Odoo.
- **Webhook matching:** Transaction is matched by `ref` query parameter in the webhook URL, not by any ID in the POST body (which only contains `uuid`).
- **Decimal precision:** Uses `CURRENCY_MINOR_UNITS` (from `payment.const`) to determine how many decimals to format the amount string with. E.g., JPY → 0 decimals, USD → 2.
- **Locale fallback:** If user's lang not in `SUPPORTED_LOCALES`, falls back to 'en_US'.
- **Webhook acknowledgment:** Returns to prevent retries on processing errors.
- **v17→v18:** No specific breaking changes. API v2 endpoints stable.
