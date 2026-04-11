# Payment Nuvei (`payment_nuvei`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Nuvei |
| **Technical** | `payment_nuvei` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `payment` |

## Description
Global payment provider covering Latin America and international markets via Nuvei's unified payment platform. Supports credit cards, local payment methods, and alternative payment options. Uses merchant/site credentials with secret key HMAC signature.

## Coverage
Latin America (Brazil, Mexico, Argentina, Chile, Colombia, etc.), international markets

## Technical Notes
- API: Nuvei REST API
- Signature: HMAC-based merchant authentication
- Currencies: filtered to Nuvei-supported set

## Provider Configuration Fields

| Field | Type | Description |
|-------|------|-------------|
| `nuvei_merchant_identifier` | Char | Merchant account identifier |
| `nuvei_site_identifier` | Char | Site identifier code for the merchant account |
| `nuvei_secret_key` | Char | Secret key for HMAC signature generation |

## Models

### `payment.provider` (Extended)
**`_get_supported_currencies()`** — Filters to Nuvei-supported currencies from `const.SUPPORTED_CURRENCIES`

**`_get_default_payment_method_codes()`** — Returns Nuvei default payment method codes

### `payment.transaction` (Extended)
Nuvei-specific transaction handling (payment creation, HMAC-signed requests, webhook processing).

## Related
- [[Modules/payment]] — Base payment engine
