---
type: module
module: payment_adyen
tags: [odoo, odoo19, payment, adyen]
created: 2026-04-06
---

# Payment Provider: Adyen

## Overview
| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Adyen |
| **Technical** | `payment_adyen` |
| **Category** | Accounting/Payment Providers |
| **Version** | 2.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
A Dutch payment provider covering Europe and the US. Supports card payments, manual capture, partial refunds, and tokenization for recurring payments.

## Dependencies
- payment

## Key Models

### payment.provider (Inherited)
**File:** `models/payment_provider.py`

#### Fields
| Field | Type | Description |
|-------|------|-------------|
| `code` | Selection | Added `adyen` option to provider code |
| `adyen_merchant_account` | Char | Merchant account code for Adyen |
| `adyen_api_key` | Char | Adyen API key (system group) |
| `adyen_client_key` | Char | Client key for frontend |
| `adyen_hmac_key` | Char | Webhook HMAC key (system group) |
| `adyen_api_url_prefix` | Char | Base URL prefix for Adyen API |

#### Feature Support
| Feature | Support |
|---------|---------|
| Manual capture | `partial` (can capture partially) |
| Refund | `partial` (partial refunds supported) |
| Tokenization | `True` |

#### Key Methods
| Method | Description |
|--------|-------------|
| `_adyen_get_inline_form_values()` | Returns JSON for rendering the inline payment form |
| `_adyen_get_formatted_amount()` | Formats amount in Adyen's required format |
| `_adyen_compute_shopper_reference()` | Computes unique partner reference for Adyen |
| `_build_request_url()` | Builds API URL with versioned endpoints |
| `_build_request_headers()` | Adds X-API-Key and idempotency headers |

### payment.transaction (Inherited)
**File:** `models/payment_transaction.py`

#### Key Methods
| Method | Description |
|--------|-------------|
| `_get_specific_processing_values()` | Returns converted amount and access token |
| `_send_payment_request()` | Sends token-based payment request to Adyen |
| `_send_capture_request()` | Captures an authorized payment |
| `_send_void_request()` | Sends void/cancel request |
| `_send_refund_request()` | Sends partial/full refund request |
| `_search_by_reference()` | Finds tx by reference, handles capture/void/refund events |
| `_apply_updates()` | Updates tx state based on Adyen eventCode and resultCode |

#### Webhook Events Handled
- `AUTHORISATION` - Payment authorization
- `CAPTURE` / `CAPTURE_FAILED` - Capture (manual or automatic)
- `CANCELLATION` - Void/cancel
- `REFUND` - Refund notification

#### State Mapping
| Adyen resultCode | Odoo State |
|------------------|------------|
| Pending modifiers | `pending` |
| Done (no manual capture) | `done` |
| Done (manual capture + AUTHORISATION event) | `authorized` |
| Done (manual capture + CAPTURE event) | `done` |
| Cancel modifiers | `canceled` |
| Error/refused modifiers | `error` |

## Architecture Notes

**API URL Pattern:** `https://{prefix}.adyen.com/checkout/V{version}/{endpoint}`
- Test mode uses `-test.adyen` suffix
- Live mode uses `-checkout-live.adyenpayments` suffix

**Request Headers:** `X-API-Key` with optional `idempotency-key` for POST requests.

**Webhook Security:** HMAC key is used to verify webhook authenticity.

## Related
- [Modules/payment](modules/payment.md)
- [Modules/payment_stripe](modules/payment_stripe.md)
- [Modules/payment_paypal](modules/payment_paypal.md)