---
Module: payment_aps
Version: 18.0
Type: addon
Tags: #payment #payment_aps
---

# Payment Provider: Amazon Payment Services (`payment_aps`)

## Overview

**Code:** `payment_aps` | **Version:** 1.0 | **Category:** Accounting/Payment Providers | **Depends:** `payment` | **License:** LGPL-3

Amazon Payment Services (APS, formerly PayFort) is a MENA-region payment provider. The module extends the Odoo payment framework with APS-specific transaction handling, SHA-256 HMAC signature computation, and webhook/redirect notification processing.

---

## Provider Configuration Fields

`payment.provider` — `code = fields.Selection(selection_add=[('aps', "Amazon Payment Services")], ondelete={'aps': 'set default'})`

| Field | Type | Required | Groups | Description |
|---|---|---|---|---|
| `aps_merchant_identifier` | Char | Yes (provider) | — | APS Merchant Identifier |
| `aps_access_code` | Char | Yes (provider) | `base.group_system` | APS Access Code |
| `aps_sha_request` | Char | Yes (provider) | `base.group_system` | SHA phrase for outgoing requests |
| `aps_sha_response` | Char | Yes (provider) | `base.group_system` | SHA phrase for incoming notifications |

**Default payment methods:** `card`, `visa`, `mastercard`, `amex`, `discover`

---

## API URLs

`_aps_get_api_url()` — `models/payment_provider.py:44`
- `enabled` state: `https://checkout.payfort.com/FortAPI/paymentPage`
- `test` state: `https://sbcheckout.payfort.com/FortAPI/paymentPage`

---

## Signature Computation

`_aps_calculate_signature(data, incoming=True)` — `models/payment_provider.py:50`

```
sign_data = ''.join(f'k=v' for k,v sorted(data.items()) if k != 'signature')
signing_string = key + sign_data + key   # key = aps_sha_response if incoming else aps_sha_request
return sha256(signing_string.encode()).hexdigest()
```

---

## Controller Routes

`APSController` — `controllers/main.py`

| Route | Auth | Methods | CSRF | Session | Description |
|---|---|---|---|---|---|
| `/payment/aps/return` | public | POST | No | No | Checkout redirect return |
| `/payment/aps/webhook` | public | POST | No | — | Webhook notification |

`_verify_notification_signature()` (line 74): Compares received `signature` vs. computed HMAC-SHA256 with `incoming=True`. Acknowledges with `''` on error (not 'SUCCESS') to avoid provider retries.

---

## Transaction Processing (`payment.transaction`)

### Reference Computation
`_compute_reference()` — `models/payment_transaction.py:22`: Uses `payment_utils.singularize_reference_prefix()` to enforce APS's alphanumeric-only (plus `-` and `_`) reference constraint.

### Rendering Values
`_get_specific_rendering_values()` — `models/payment_transaction.py:43`:
```python
{
    'command': 'PURCHASE',
    'access_code', 'merchant_identifier', 'merchant_reference',
    'amount': str(converted_to_minor_units),
    'currency', 'language': partner_lang[:2],
    'customer_email', 'return_url',
    ['payment_option' if not 'card'],
    'signature': _aps_calculate_signature(values, incoming=False),
    'api_url': _aps_get_api_url(),
}
```

### Transaction Matching
`_get_tx_from_notification_data()` — `models/payment_transaction.py:80`: Uses `merchant_reference` field from notification data.

### Notification Processing
`_process_notification_data()` — `models/payment_transaction.py:108`:
- `provider_reference` = `fort_id`
- `payment_method` = `payment_option` (lowercased) via `_get_from_code()`
- Status codes: `'14'` → done, `'19'` → pending, else → error

### Status Mapping (`const.py:5`)
```python
PAYMENT_STATUS_MAPPING = {
    'pending': ('19',),
    'done': ('14',),
}
```

---

## Utilities

`utils.py` — `get_payment_option(payment_method_code)`:
- Returns `payment_method_code.upper()` if not `'card'`
- Returns `''` for `'card'` so the user picks the brand on APS's hosted page

---

## Hooks

- `post_init_hook`: `setup_provider(env, 'aps')`
- `uninstall_hook`: `reset_payment_provider(env, 'aps')`

---

## Key Integration Notes

- **Signature:** Double-sided HMAC-SHA256 — `key + sorted_data + key`
- **Reference constraint:** Alphanumeric + `-` + `_` only; `singularize_reference_prefix()` prevents document-based names containing `/`
- **No tokenization:** APS module does not implement saved-token payments
- **Webhook ack:** Returns empty string `''` (not 'SUCCESS') to suppress retries on `ValidationError`
- **MENA coverage:** Saudi Arabia (mada), UAE, Egypt, Jordan, Qatar, Kuwait, etc.

---

## File Structure

```
payment_aps/
├── __manifest__.py
├── __init__.py             # post_init_hook + uninstall_hook
├── const.py                # PAYMENT_STATUS_MAPPING, DEFAULT_PAYMENT_METHOD_CODES
├── utils.py                # get_payment_option()
├── models/
│   ├── __init__.py
│   ├── payment_provider.py # _aps_get_api_url, _aps_calculate_signature
│   └── payment_transaction.py
└── controllers/
    ├── __init__.py
    └── main.py             # APSController
```
