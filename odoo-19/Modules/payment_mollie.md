# Payment Mollie (`payment_mollie`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Mollie |
| **Technical** | `payment_mollie` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A., Applix BV, Droggol Infotech Pvt. Ltd. |
| **Website** | https://www.mollie.com |
| **Depends** | `payment` |

## Description
Dutch payment provider covering most European countries. Enables online payments via Mollie's API — credit cards, SEPA Direct Debit, iDEAL, Bancontact, SOFORT, and more. Simple API key configuration with live/test mode auto-detection.

## Coverage
Netherlands, Germany, France, Belgium, Austria, and most European markets

## Technical Notes
- API: Mollie REST API v2 (`https://api.mollie.com/v2/`)
- API key: single key — live/test mode detected from key format
- Currencies: filtered to Mollie-supported set

## Provider Configuration Fields

| Field | Type | Description |
|-------|------|-------------|
| `mollie_api_key` | Char | Mollie Test or Live API key (determines environment) |

## Models

### `payment.provider` (Extended)
**`_get_supported_currencies()`** — Filters to Mollie-supported currencies from `const.SUPPORTED_CURRENCIES`

**`_get_default_payment_method_codes()`** — Returns Mollie default method codes

**`_build_request_url()`** — Returns `https://api.mollie.com/v2/{endpoint}`

**`_build_request_headers()`** — Builds auth headers with Mollie API key

### `payment.transaction` (Extended)
Mollie-specific transaction handling (create payment, webhook processing).

## Related
- [[Modules/payment]] — Base payment engine
- [[Modules/pos_mollie]] — Mollie POS terminal integration
