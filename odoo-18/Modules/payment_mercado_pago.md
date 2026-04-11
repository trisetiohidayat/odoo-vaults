---
Module: payment_mercado_pago
Version: 18.0.0
Type: addon
Tags: #odoo18 #payment_mercado_pago #payment
---

## Overview

`payment_mercado_pago` integrates Odoo with Mercado Pago (Argentina/Latin America), supporting 22+ currencies and 20+ payment methods including credit/debit cards, regional cards (Naranja, OCA, Presto, etc.), and PayPal. Payment is initiated via Mercado Pago's Checkout Preferences API which returns a hosted payment page URL. Webhook notifications are verified by fetching payment status directly from the API.

## Models

### payment.provider (extends base)
**Inheritance:** `payment.provider` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| code | selection | Adds `('mercado_pago', "Mercado Pago")`. `ondelete='set default'` |
| mercado_pago_access_token | Char | Mercado Pago Access Token (required_if_provider='mercado_pago', groups=base.group_system) |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_supported_currencies | self | recordset | Filters to 21 LatAm + common currencies: ARS, BOB, BRL, CLF, CLP, COP, CRC, CUC, CUP, DOP, EUR, GTQ, HNL, MXN, NIO, PAB, PEN, PYG, USD, UYU, VEF, VES |
| _mercado_pago_make_request | self, endpoint, payload=None, method='POST' | dict | POST/GET to `https://api.mercadopago.com`. Sets `Authorization: Bearer {access_token}` and `X-Platform-Id: dev_cdf1cfac242111ef9fdebe8d845d0987`. Handles HTTP errors and empty responses |
| _get_default_payment_method_codes | self | set | Returns `{'card', 'visa', 'mastercard', 'argencard', 'ceconsud', 'cordobesa', 'codensa', 'lider', 'magna', 'naranja', 'nativa', 'oca', 'presto', 'tarjeta_mercadopago', 'shopping', 'elo', 'hipercard'}` |

### payment.transaction (extends base)
**Inheritance:** `payment.transaction` (classic `_inherit`)

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_specific_rendering_values | self, processing_values | dict | Creates Checkout Preference via `/checkout/preferences`. Returns `api_url` (init_point or sandbox_init_point) and decoded `url_params` as form inputs |
| _mercado_pago_prepare_preference_request_payload | self | dict | Builds preference payload: `auto_return=all`, `back_urls` (success/pending/failure all → return_url), `external_reference` (tx reference), `items` (title=reference, qty=1, unit_price=rounded), `notification_url` (webhook with reference appended), `payer` (name, email, phone, address), `payment_methods` (installments=1 to prevent multi-installment proposal). Rounds amount per `CURRENCY_DECIMALS` |
| _get_tx_from_notification_data | self, provider_code, notification_data | recordset | Looks up by `external_reference` |
| _process_notification_data | self, notification_data | None | **Verifies payment** via GET `/v1/payments/{id}`. Sets `provider_reference` from `payment_id`. Maps `payment_type_id` via `PAYMENT_METHODS_MAPPING` (with multi-code split). Falls back to 'unknown' payment method. Maps status via `TRANSACTION_STATUS_MAPPING`: pending/approved/refunded/cancelled/rejected → respective states. Error detail mapped via `_mercado_pago_get_error_msg()` |
| _mercado_pago_get_error_msg | self, status_detail (api.model) | str | Static method returning human-readable error message for Mercado Pago status_detail codes |

## Security / Data

**Security:** `mercado_pago_access_token` restricted to `base.group_system`. No ACL file.

**Data:** None.

## Critical Notes

- **Webhook verification:** All webhook notifications fetch full payment data from API before processing — prevents spoofed notifications.
- **Currency decimals:** `COP`, `HNL`, `NIO` require integer amounts (no decimals). Rounding applied via `float_round(amount, 0, rounding_method='DOWN')`.
- **Installment restriction:** `installments=1` prevents Mercado Pago from offering multi-installment plans for a single-payment checkout.
- **External reference:** Uses Odoo's transaction `reference` as `external_reference` for easy correlation.
- **Payment method mapping:** `PAYMENT_METHODS_MAPPING` values can contain commas (multiple MP codes map to single Odoo code). `_process_notification_data` splits on commas.
- **Fallback payment method:** If `payment_method` lookup fails, falls back to `'unknown'` payment method (if it exists in the system).
- **v17→v18:** No breaking changes. API v1 endpoints unchanged.
