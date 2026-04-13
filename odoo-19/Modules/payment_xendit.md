# Payment Xendit (`payment_xendit`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Xendit |
| **Technical** | `payment_xendit` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `payment` |

## Description
Southeast Asian payment provider covering Indonesia (OVO, Dana, LinkAja, GoPay, etc.), Philippines (GCash, Maya), Vietnam, Thailand, and Malaysia. Supports tokenization, recurring payments, and multiple local payment methods via Xendit's unified API.

## Coverage
Indonesia, Philippines, Vietnam, Thailand, Malaysia

## Technical Notes
- API: Xendit API
- Supports: tokenization (`support_tokenization = True`)
- Currencies: filtered to Xendit-supported set

## Provider Configuration Fields

| Field | Type | Description |
|-------|------|-------------|
| `xendit_public_key` | Char | Xendit public key (for frontend tokenization) |
| `xendit_secret_key` | Char | Xendit secret key (for server-side API calls) |
| `xendit_webhook_token` | Char | Webhook signature verification token |

## Models

### `payment.provider` (Extended)
**`_compute_feature_support_fields()`** — Enables `support_tokenization = True` for Xendit

**`_get_supported_currencies()`** — Filters to Xendit-supported currencies from `const.SUPPORTED_CURRENCIES`

**`_get_default_payment_method_codes()`** — Returns Xendit default payment method codes

## Related
- [Modules/payment](payment.md) — Base payment engine
