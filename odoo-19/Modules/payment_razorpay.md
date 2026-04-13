---
type: module
module: payment_razorpay
tags: [odoo, odoo19, payment, razorpay]
created: 2026-04-06
---

# Payment Provider: Razorpay

## Overview
| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Razorpay |
| **Technical** | `payment_razorpay` |
| **Category** | Accounting/Payment Providers |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
A payment provider covering India. Supports INR transactions, tokenization for recurring payments (eMandate), manual capture, and refunds.

## Dependencies
- payment

## Key Models

### payment.provider (Inherited)
**File:** `models/payment_provider.py`

#### Fields
| Field | Type | Description |
|-------|------|-------------|
| `code` | Selection | Added `razorpay` option |
| `razorpay_key_id` | Char | Public key for frontend (set by user) |
| `razorpay_public_token` | Char | Public token for frontend (set by user) |

#### Feature Support
| Feature | Support |
|---------|---------|
| Manual capture | Supported (authorized then captured) |
| Refund | `partial` |
| Tokenization | `True` (eMandate recurring) |

### payment.transaction (Inherited)
**File:** `models/payment_transaction.py`

#### Key Methods
| Method | Description |
|--------|-------------|
| `_get_specific_processing_values()` | Creates customer + order, returns key_id, customer_id, order_id, tokenize flag |
| `_razorpay_create_customer()` | Creates Razorpay customer with name, email, phone |
| `_razorpay_create_order()` | Creates Razorpay order for payment |
| `_razorpay_prepare_order_payload()` | Builds order with amount, currency, payment method, mandate token |
| `_razorpay_get_mandate_max_amount()` | Computes max amount for eMandate (INR 1,00,000 default) |
| `_validate_phone_number()` | Formats phone number via `_phone_format` with country |
| `_send_payment_request()` | Sends token-based recurring payment request |
| `_send_refund_request()` | Sends refund with reference in notes |
| `_send_capture_request()` | Captures authorized payment |
| `_send_void_request()` | Raises UserError (Razorpay cannot be voided) |
| `_search_by_reference()` | Searches by description for payments, by notes for refunds, or creates child tx |
| `_extract_token_values()` | Returns customer_id + token_id combined in `provider_ref` |

#### Amount Handling
- Amounts converted to minor currency units (paise) via `payment_utils.to_minor_currency_units()`
- INR converted back to target currency for non-INR transactions via `_razorpay_convert_inr_to_currency()`

#### Tokenization
Provider ref format: `{customer_id},{token_id}` (comma-separated)

Mandate max amount per payment method:
- Card: INR 100,000 (default)
- UPI: varies
- eMandate valid for 10 years with `frequency: as_presented`

#### eMandate Rules
- Prevent duplicate token payments within 36 hours
- Max amount = min(pm_max_amount, max(amount*1.5, MRR*5))

#### State Mapping
| Razorpay Status | Odoo State |
|-----------------|------------|
| `authorized` (if capture_manually) | `authorized` |
| `captured` | `done` |
| `refunded` | `done` (refund child tx) |
| `error` | `error` |

## Architecture Notes

**Customer Creation:** Every new payment creates a Razorpay customer unless a token already exists.

**Webhook:** Supports payment, refund, and capture webhook entities.

**Refund Tracking:** Refund reference stored in `notes.reference` field for lookup.

**Partial Refunds:** Supported via standard refund flow.

**Return URL:** Uses `RazorpayController._return_url` with reference query param for redirect payments.

## Related
- [Modules/payment](modules/payment.md)
- [Modules/payment_adyen](modules/payment_adyen.md)