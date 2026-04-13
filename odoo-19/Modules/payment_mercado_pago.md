---
type: module
module: payment_mercado_pago
tags: [odoo, odoo19, payment, mercadopago, latam]
created: 2026-04-06
---

# Payment Provider: Mercado Pago

## Overview
| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Mercado Pago |
| **Technical** | `payment_mercado_pago` |
| **Category** | Accounting/Payment Providers |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
A payment provider covering several countries in Latin America (Brazil, Argentina, Mexico, etc.). Supports redirect-based checkout, token-based S2S payments, and customer card management.

## Dependencies
- payment

## Key Models

### payment.transaction (Inherited)
**File:** `models/payment_transaction.py`

#### Key Methods
| Method | Description |
|--------|-------------|
| `_get_specific_rendering_values()` | Creates checkout preference, returns `api_url` and `url_params` for redirect form |
| `_mercado_pago_prepare_preference_request_payload()` | Builds preference with back_urls, items, payer info for redirect flow |
| `_mercado_pago_prepare_payment_request_payload()` | Builds payload for direct/token payment |
| `_mercado_pago_prepare_base_request_payload()` | Base payload with external_reference and webhook notification_url |
| `_send_payment_request()` | Sends card token payment via `/v1/payments` endpoint |
| `_mercado_pago_convert_amount()` | Rounds amount for special currencies (COP, HNL, NIO as integers) |
| `_extract_reference()` | Extracts from `external_reference` |
| `_extract_amount_data()` | Extracts from `additional_info.items` or `transaction_amount` |
| `_apply_updates()` | Updates tx state, payment method, provider reference |
| `_extract_token_values()` | Fetches/creates MP customer, fetches card via `/v1/customers/{id}/cards`, returns `provider_ref` as card_id |

#### Payment Return Flow
- Uses `init_point` (live) or `sandbox_init_point` (test) from preference response
- Redirect form embeds URL params as hidden inputs to preserve them

#### State Mapping
| Mercado Pago Status | Odoo State |
|---------------------|------------|
| `pending` statuses | `pending` |
| `approved` | `done` |
| `cancelled` | `canceled` |
| `error` | `error` |

#### Tokenization Flow
1. Search existing MP customer by email (`GET /v1/customers/search`)
2. If not found, create new customer (`POST /v1/customers`)
3. Create card token (`POST /v1/customers/{id}/cards`)
4. Store `provider_ref` = card_id, `payment_details` = last_four_digits, `mercado_pago_customer_id` = customer_id

#### Currency Decimal Handling
Special rounding for COP, HNL, NIO: `decimal_places=None` means integer amount.

## Architecture Notes

**Webhook Route:** `const.WEBHOOK_ROUTE/{sanitized_reference}` - reference in URL path for lookup.

**Error Message Mapping:** `const.ERROR_MESSAGE_MAPPING` maps `status_detail` codes to user-friendly messages.

**Payment Method Mapping:** Maps MP `payment_type_id` and `payment_method_id` to Odoo payment methods via `const.PAYMENT_METHODS_MAPPING`.

**Fallback Payment Method:** Falls back to `unknown` payment method if not found.

## Related
- [Modules/payment](Modules/payment.md)
- [Modules/payment_razorpay](Modules/payment_razorpay.md)