---
Module: payment_nuvei
Version: 18.0.0
Type: addon
Tags: #odoo18 #payment_nuvei #payment
---

## Overview

`payment_nuvei` integrates Odoo with Nuvei (formerly SafeCharge), a global payment provider supporting credit/debit cards, regional methods (WebPay, Boleto, OXXO, PIX, SPEI, PSE), and alternative payment methods across LatAm, Europe, and Asia. Uses SHA-256 HMAC signature verification. Key requirement: some payment methods require integer amounts or full name splitting.

## Models

### payment.provider (extends base)
**Inheritance:** `payment.provider` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| code | selection | Adds `('nuvei', "Nuvei")`. `ondelete='set default'` |
| nuvei_merchant_identifier | Char | Merchant Identifier (required_if_provider='nuvei') |
| nuvei_site_identifier | Char | Site Identifier (required_if_provider='nuvei', groups=base.group_system) |
| nuvei_secret_key | Char | Secret Key (required_if_provider='nuvei', groups=base.group_system) |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _nuvei_get_api_url | self | str | Returns production/test purchase URL |
| _nuvei_calculate_signature | self, data, incoming=True | str | SHA-256 HMAC: `key + concat(values for sig_keys)`. For incoming: uses predefined `SIGNATURE_KEYS`. For outgoing: uses all data keys |
| _get_supported_currencies | self | recordset | Filters to 9 currencies: ARS, BRL, CAD, CLP, COP, MXN, PEN, USD, UYU |
| _get_default_payment_method_codes | self | set | Returns `{'card', 'visa', 'mastercard', 'amex', 'discover', 'tarjeta_mercadopago', 'naranja'}` |

### payment.transaction (extends base)
**Inheritance:** `payment.transaction` (classic `_inherit`)

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_specific_rendering_values | self, processing_values | dict | Builds Nuvei redirect form data with 30+ parameters: address, city, country, currency, email, first/last name, item details, merchant IDs, phone (formatted via `_phone_format()`), timestamps, total, URLs, checksum. Generates access token for error/cancel URL |
| _get_tx_from_notification_data | self, provider_code, notification_data | recordset | Looks up by `invoice_id` (Nuvei's order reference = Odoo's tx reference). If notification is empty (customer left page), cancels the transaction |
| _process_notification_data | self, notification_data | None | Sets `provider_reference` from `TransactionID`. Maps `Status` or `ppp_status` (lowercased) via `PAYMENT_STATUS_MAPPING`: 'pending' → pending, 'approved'/'ok' → done, 'declined'/'error'/'fail' → error with reason message |

## Security / Data

**Security:** `nuvei_secret_key`, `nuvei_site_identifier` restricted to `base.group_system`. No ACL file.

**Data:** None.

## Critical Notes

- **Integer amounts for WebPay:** `INTEGER_METHODS=['webpay']` — amounts are rounded to 0 decimals for these methods.
- **Full name required for Boleto:** `FULL_NAME_METHODS=['boleto']` — requires both first and last name or raises `UserError`.
- **Phone formatting:** `_phone_format()` standardizes phone numbers before inclusion in the request.
- **Empty notification = cancellation:** If Nuvei returns with no data (customer closed browser), `_process_notification_data` sets state to 'canceled' with message "The customer left the payment page."
- **Checksum:** Signature includes `user_token_id` (random UUID) and `time_stamp` — the request is tied to a specific session.
- **v17→v18:** No breaking changes observed.
