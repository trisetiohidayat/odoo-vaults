---
type: module
module: payment_paypal
tags: [odoo, odoo19, payment, paypal]
created: 2026-04-06
---

# Payment Provider: PayPal

## Overview
| Property | Value |
|----------|-------|
| **Name** | Payment Provider: PayPal |
| **Technical** | `payment_paypal` |
| **Category** | Accounting/Payment Providers |
| **Version** | 2.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
An American payment provider for online payments all over the world. Uses PayPal Checkout API (v2 orders) for payment processing.

## Dependencies
- payment

## Key Models

### payment.transaction (Inherited)
**File:** `models/payment_transaction.py`

#### Fields
| Field | Type | Description |
|-------|------|-------------|
| `paypal_type` | Char | PayPal transaction type (IPN debugging only) |

#### Key Methods
| Method | Description |
|--------|-------------|
| `_get_specific_processing_values()` | Creates PayPal order via `/v2/checkout/orders` API, returns `order_id` |
| `_paypal_prepare_order_payload()` | Builds order payload with purchase_units, payer info, shipping preference |
| `_extract_reference()` | Extracts reference from `reference_id` field |
| `_extract_amount_data()` | Extracts amount and currency from `amount.value` and `amount.currency_code` |
| `_apply_updates()` | Updates tx state based on PayPal payment status |

#### Payment Status Mapping
| PayPal Status | Odoo State |
|---------------|------------|
| Pending statuses | `pending` |
| `COMPLETED` | `done` |
| Cancel statuses | `canceled` |
| Invalid | `error` |

#### Order Payload Structure
```python
{
    'intent': 'CAPTURE',
    'purchase_units': [{
        'reference_id': reference,
        'description': f'{company_name}: {reference}',
        'amount': {'currency_code': currency, 'value': amount},
        'payee': {'email_address': paypal_email_account},
        **shipping_address_vals
    }],
    'payment_source': {
        'paypal': {
            'experience_context': {'shipping_preference': ...},
            'name': {'given_name': first, 'surname': last},
            **invoice_address_vals
        }
    }
}
```

#### Shipping Preference Logic
- If shipping address provided: `'SET_PROVIDED_ADDRESS'`
- Otherwise: `'NO_SHIPPING'`

## Architecture Notes

**API Endpoint:** `POST /v2/checkout/orders` with idempotency key.

**Idempotency Key:** Generated via `payment_utils.generate_idempotency_key()` with scope `payment_request_order`.

**PayPal Email Account:** Used as the payee email in purchase units.

**Webhook/IPN:** PayPal sends IPN notifications; `paypal_type` field stores the transaction type for debugging.

**Error Handling:** Uses PayPal const module for status mapping constants.

## Related
- [Modules/payment](Modules/payment.md)
- [Modules/payment_adyen](Modules/payment_adyen.md)
- [Modules/payment_stripe](Modules/payment_stripe.md)