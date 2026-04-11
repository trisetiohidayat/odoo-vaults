---
Module: payment_asiapay
Version: 18.0.0
Type: addon
Tags: #odoo18 #payment_asiapay #payment
---

## Overview

`payment_asiapay` integrates Odoo with the AsiaPay (PayDollar/PesoPay/SiamPay/BimoPay) multi-brand payment platform. Supports 40+ payment methods across Asia-Pacific. Requires single-currency configuration and supports signature-based verification using SHA1/SHA256/SHA512.

## Models

### payment.provider (extends base)
**Inheritance:** `payment.provider` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| code | selection | Adds `('asiapay', "AsiaPay")`. `ondelete='set default'` |
| asiapay_brand | Selection | Brand selector: `paydollar` (default), `pesopay`, `siampay`, `bimopay`. Required if_provider='asiapay' |
| asiapay_merchant_id | Char | AsiaPay Merchant ID. Required if_provider='asiapay' |
| asiapay_secure_hash_secret | Char | Secure hash secret (required, groups=base.group_system) |
| asiapay_secure_hash_function | Selection | Hash function: `sha1` (default), `sha256`, `sha512`. Required |

**Constraints:**

| Constraint | Description |
|------------|-------------|
| `_limit_available_currency_ids` | Restricts to one currency when not disabled. Validates all selected currencies against `CURRENCY_MAPPING.keys()` and raises if unsupported |

### payment.provider Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _asiapay_get_api_url | self | str | Returns brand-specific URL from `API_URLS[environment][brand]` (production or test) |
| _asiapay_calculate_signature | self, data, incoming=True | str | Hashes signing string using configured algorithm. `incoming=True` uses incoming signature keys; `incoming=False` uses outgoing keys. String format: `k1\|k2\|...\|secret` joined by `|` |
| _get_default_payment_method_codes | self | set | Returns `{'card', 'visa', 'mastercard', 'amex', 'discover'}` |

### payment.transaction (extends base)
**Inheritance:** `payment.transaction` (classic `_inherit`)

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_reference | self, provider_code, prefix=None, separator='-', **kwargs | str | Enforces max 35-character reference. Uses `singularize_reference_prefix(prefix, max_length=35)` to prevent oversize. Falls back to `_compute_reference_prefix` if no prefix |
| _get_specific_rendering_values | self, processing_values | dict | Builds AsiaPay form data: `merchant_id`, `amount`, `reference`, `currency_code` (via `CURRENCY_MAPPING`), `mps_mode=SCP`, `return_url`, `payment_type=N`, `language` (mapped via `LANGUAGE_CODES_MAPPING` with fallback chain: full tag → country code → 'en'), `payment_method` (mapped or 'ALL'), `secure_hash`, `api_url` |
| _get_tx_from_notification_data | self, provider_code, notification_data | recordset | Looks up by `Ref` field. Returns early if super finds match |
| _process_notification_data | self, notification_data | None | Sets `provider_reference` from `PayRef`, updates `payment_method_id` via `PAYMENT_METHODS_MAPPING` lookup, maps `successcode` via `SUCCESS_CODE_MAPPING`: '0' → `_set_done`, '1' → `_set_error`, else unknown error |

## Security / Data

**Security:** `asiapay_secure_hash_secret` field restricted to `base.group_system`.

**Data:** `asiapay_data.xml` — demo data (payment method configuration).

## Critical Notes

- **Multi-brand architecture:** Single provider can target any of 4 AsiaPay brands (PayDollar, PesoPay, SiamPay, BimoPay), each with separate API URLs.
- **Currency constraint:** Only one currency allowed; must be in AsiaPay's supported set (AED, AUD, BND, CAD, CNY, EUR, GBP, HKD, IDR, INR, JPY, KRW, MOP, MYR, NZD, PHP, SAR, SGD, THB, TWD, USD, VND).
- **Signature:** Uses configurable hash algorithm (SHA1/SHA256/SHA512) with different key ordering for incoming vs outgoing.
- **Language mapping:** Supports 14 language/country variants with intelligent fallback (full tag → country prefix → English).
- **v17→v18:** No specific breaking changes. Currency validation constraint added or more strictly enforced.
