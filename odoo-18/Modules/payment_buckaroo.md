---
Module: payment_buckaroo
Version: 18.0.0
Type: addon
Tags: #odoo18 #payment_buckaroo #payment
---

## Overview

`payment_buckaroo` integrates Odoo with Buckaroo's payment gateway. Supports 25+ payment methods including iDEAL, Bancontact, PayPal, Klarna, SEPA Direct Debit, Sofort, and many regional European methods. Uses SHA-1 digital signatures for request authentication. Buckaroo routes (redirect or direct API) are controlled via `_get_specific_rendering_values`.

## Models

### payment.provider (extends base)
**Inheritance:** `payment.provider` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| code | selection | Adds `('buckaroo', "Buckaroo")`. `ondelete='set default'` |
| buckaroo_website_key | Char | Website Key identifier (required_if_provider='buckaroo') |
| buckaroo_secret_key | Char | Buckaroo Secret Key (required_if_provider='buckaroo', groups=base.group_system) |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_supported_currencies | self | recordset | Filters to `SUPPORTED_CURRENCIES`: EUR, GBP, PLN, DKK, NOK, SEK, CHF, USD |
| _buckaroo_get_api_url | self | str | `https://checkout.buckaroo.nl/html/` (enabled) or test URL |
| _buckaroo_generate_digital_sign | self, values, incoming=True | str | SHA-1 hash of signing string. For incoming: URL-decodes values first, skips `brq_signature`. For both: filters to keys starting with `add_`, `brq_`, `cust_`, sorts lowercase, concatenates `k=v`, appends secret key |
| _get_default_payment_method_codes | self | set | Returns `{'card', 'ideal', 'visa', 'mastercard', 'amex', 'discover'}` |

### payment.transaction (extends base)
**Inheritance:** `payment.transaction` (classic `_inherit`)

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_specific_rendering_values | self, processing_values | dict | Builds Buckaroo form data: `api_url`, `Brq_websitekey`, `Brq_amount`, `Brq_currency`, `Brq_invoicenumber` (reference), all 4 return URLs (same URL for success/cancel/error/reject), optionally `Brq_culture` (partner lang), `Brq_signature`. Signature uses outgoing sign generation |
| _get_tx_from_notification_data | self, provider_code, notification_data | recordset | Looks up by `brq_invoicenumber` (reference). Returns early if super finds match |
| _process_notification_data | self, notification_data | None | Sets `provider_reference` from first key in `brq_transactions` (comma-separated). Updates `payment_method_id` via `PAYMENT_METHODS_MAPPING` lookup. Maps `brq_statuscode` via `STATUS_CODES_MAPPING`: 790-793 → pending, 190 → done, 890-891 → canceled, 690 → refused, 490-492 → error, else unknown |

## Security / Data

**Security:** `buckaroo_secret_key` restricted to `base.group_system`. No ACL file.

**Data:** None.

## Critical Notes

- **Signature filtering:** Only `add_*`, `brq_*`, `cust_*` prefixed parameters participate in signature. This prevents parameter injection.
- **Incoming signature:** Buckaroo POSTs URL-encoded values; Odoo URL-decodes before verifying signature to match Buckaroo's signing process.
- **Currency support:** Only 8 currencies: EUR, GBP, PLN, DKK, NOK, SEK, CHF, USD — Buckaroo's supported set.
- **Reference field:** Uses `brq_invoicenumber` which maps to the Odoo transaction `reference`.
- **v17→v18:** No breaking changes observed.
