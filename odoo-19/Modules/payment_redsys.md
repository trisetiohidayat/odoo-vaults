---
type: module
module: payment_redsys
tags: [odoo, odoo19, payment, payment-provider, spain, redsys]
created: 2026-04-11
---

# Payment Provider: Redsys

## Overview

| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Redsys |
| **Technical** | `payment_redsys` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `payment` |

## Description

Redsys (formerly Sermepa/Redsys) is a Spanish payment gateway covering the Spanish market. It is the dominant payment provider in Spain, supporting card payments (Visa, Mastercard, Amex, Diners, JCB) and Bizum. Redsys uses a server-to-server signature scheme where merchant parameters are Base64-encoded and signed with a 3DES-derived HMAC-SHA256 key. The payment is performed through an HTTP redirect to Redsys's SIS (Sistema Integral de Gestión de Pago) platform.

**Key characteristics:**
- Redirect-based (customer redirected to Redsys SIS)
- 3DES-HMAC-SHA256 signature scheme with derived key
- Base64-encoded merchant parameters in the redirect form
- Supports card brands and Bizum
- 3D Secure (EMV3DS) data included in merchant parameters

---

## Architecture

```
Odoo                         Redsys SIS
  |                              |
  |-- POST /payment/pay -------->|
  |   (merchant_parameters:      |
  |    Base64(JSON{DS_MERCHANT_*})|
  |    signature: HMAC-SHA256)   |
  |                              |
  | (customer redirected to SIS) |
  |                              |
  |                              |<-- fills card on SIS
  |                              |
  |<-- Ds_MerchantParameters     |
  |    (Base64, contains result) |
  |    Ds_Signature: HMAC-SHA256 |
  |                              |
  | (redirect to /payment/status) |
```

**Controller:** `RedsysController` at `controllers/main.py`
- `_return_url = '/payment/redsys/return'` — handles customer return (GET, signature verified)
- `_webhook_url = '/payment/redsys/webhook'` — handles async notification (POST)

---

## Dependencies

```
payment_redsys
  └── payment (base module)
```

## Module Structure

```
payment_redsys/
├── __init__.py
├── __manifest__.py
├── const.py                    # Payment method codes, status mappings
├── controllers/
│   ├── __init__.py
│   └── main.py                # RedsysController
├── models/
│   ├── __init__.py
│   ├── payment_provider.py    # PaymentProvider extension
│   └── payment_transaction.py # PaymentTransaction extension
├── views/
│   ├── payment_redsys_templates.xml
│   └── payment_provider_views.xml
└── data/
    └── payment_provider_data.xml
```

---

## L1: Integration with Base `payment` Module

### Provider Registration

```python
class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('redsys', "Redsys")],
        ondelete={'redsys': 'set default'}
    )
```

### Methods Overridden

| Method | File | What It Does |
|--------|------|--------------|
| `_get_default_payment_method_codes()` | `payment_provider.py` | Returns card, bizum, visa, mastercard, amex, diners, jcb |
| `_redsys_get_api_url()` | `payment_provider.py` | Returns production or sandbox SIS URL |
| `_redsys_calculate_signature()` | `payment_provider.py` | 3DES-encrypts order, then HMAC-SHA256 |
| `create()` | `payment_transaction.py` | Sets `provider_reference = reference` for Redsys txs |
| `_compute_reference()` | `payment_transaction.py` | Uses timestamp-based prefix, `S` separator (no `-`) — Redsys rejects `-` |
| `_get_specific_rendering_values()` | `payment_transaction.py` | Builds merchant params, encodes to Base64, computes signature |
| `_redsys_prepare_merchant_parameters()` | `payment_transaction.py` | Builds DS_MERCHANT_* dict including EMV3DS data |
| `_extract_reference()` | `payment_transaction.py` | Extracts `Ds_Order` from payment data |
| `_extract_amount_data()` | `payment_transaction.py` | Converts Ds_Amount to major units, looks up currency by iso_numeric |
| `_apply_updates()` | `payment_transaction.py` | Maps Ds_Response, updates payment method and state |

---

## L2: Fields, Defaults, Constraints

### `payment.provider` Extended Fields

| Field | Type | Required | Groups | Description |
|-------|------|----------|--------|-------------|
| `code` | `selection` | Yes | — | Added `redsys` option |
| `redsys_merchant_code` | `Char` | Yes (if `redsys`) | — | Redsys merchant/FUC code |
| `redsys_merchant_terminal` | `Char` | Yes (if `redsys`) | — | Terminal number (usually `001`) |
| `redsys_secret_key` | `Char` | Yes (if `redsys`) | `base.group_system` | Base64-encoded SHA-256 key for 3DES derivation |

### `const.py` — Redsys Constants

```python
DEFAULT_PAYMENT_METHOD_CODES = {
    'card', 'bizum',
    'visa', 'mastercard', 'amex', 'diners', 'jcb'
}

PAYMENT_METHODS_MAPPING = {
    'bizum':      'Z',
    'card':       'C',
    'visa':       '1',
    'mastercard': '2',
    'amex':       '8',
    'diners':     '6',
    'jcb':        '9',
}

PAYMENT_STATUS_MAPPING = {
    'done':   tuple(f'{i:04}' for i in range(100)) + ('400', '900'),
    'cancel': ('9915',),
    'error':  ('101', '102', '106', '125', '129', '172', '173', '174',
                '180', '184', '190', '191', '195', '202', '904', '909',
                '913', '944', '950', '9912', '912', '9064', '9078', '9093',
                '9094', '9104', '9218', '9253', '9256', '9257', '9261',
                '9997', '9998', '9999'),
}
```

### Reference Format

Redsys imposes strict reference requirements:
- Alphanumeric characters only (`A-Za-z0-9`)
- Minimum 9 characters, maximum 12 characters
- No hyphens (uses `S` as separator instead)

```python
# Reference generation for Redsys
prefix = str(int(fields.Datetime.now().timestamp()))[-10:]  # 10-char timestamp
return super()._compute_reference(provider_code, prefix=prefix, separator='S', **kwargs)
```

---

## L3: Cross-Module, Override Patterns, Workflow Triggers, Failure Modes

### Cross-Module Flow

1. **Transaction creation:** `create()` on `payment.transaction` sets `provider_reference = reference` for Redsys transactions
2. **Redirect form:** `_get_specific_rendering_values()` builds Base64-encoded merchant parameters, computes 3DES-HMAC-SHA256 signature
3. **Return:** `RedsysController` decodes `Ds_MerchantParameters`, verifies signature, calls `_process()`
4. **Webhook:** Same signature verification and processing pattern

### Signature Derivation (Redsys Specific)

Redsys uses a multi-step signature derivation:

```python
# Step 1: Decode the Base64 SHA-256 key
decoded_key = base64.b64decode(secret_key)
# Step 2: 3DES-encrypt the order number (Ds_Merchant_Order) with zero IV
cipher = Cipher(algorithms.TripleDES(decoded_key), modes.CBC(b'\x00' * 8))
derived_key = cipher.encryptor().update(reference_bytes.ljust(16)) + finalize()
# Step 3: HMAC-SHA256 of the merchant parameters using the derived key
hmac_obj = hmac.new(derived_key, merchant_parameters.encode(), hashlib.sha256)
# Step 4: Base64-urlsafe encode the HMAC result
signature = base64.urlsafe_b64encode(hmac_obj.digest()).decode()
```

This is specific to Redsys and requires the `cryptography` library (via `cryptography.hazmat`).

### Override Pattern

The signature derivation method `_redsys_calculate_signature()` is called by both the transaction (for outgoing signature) and the controller (for incoming verification), reusing the same 3DES-HMAC-SHA256 logic.

### EMV3DS Data

The merchant parameters include full 3D Secure data for liability shift:

```python
'DS_MERCHANT_EMV3DS': {
    'billAddrCity': self.partner_city,
    'billAddrCountry': COUNTRY_NUMERIC_CODES.get(self.partner_country_id.code, ''),
    'billAddrLine1': self.partner_address,
    'billAddrPostCode': self.partner_zip,
    'billAddrState': self.partner_state_id.code,
    'cardholderName': self.partner_name,
    'email': self.partner_email,
}
```

This is automatically passed to Redsys SIS for 3D Secure authentication.

### Workflow Triggers

| Trigger | Route | What Happens |
|---------|-------|-------------|
| Customer return | `GET /payment/redsys/return` | Decodes Base64 merchant params, verifies signature, `_process()` |
| Async notification | `POST /payment/redsys/webhook` | Same processing, returns empty `''` acknowledgement |

### Failure Modes

| Scenario | Behavior |
|----------|----------|
| Missing `Ds_Signature` | `Forbidden()` — rejected |
| HMAC signature mismatch | `Forbidden()` — rejected |
| `Ds_Response` in 0000-0099, 400, 900 | `_set_done()` |
| `Ds_Response` = 9915 | `_set_canceled()` |
| `Ds_Response` in error codes | `_set_error()` with `Ds_ErrorCode` |
| Unknown `Ds_Response` | `_set_error("Unknown status code: ...")` |

---

## L4: Odoo 18→19 Changes, Security

### Version Changes (Odoo 18→19)

No breaking API changes. The 3DES-HMAC-SHA256 signature scheme and Base64 merchant parameter encoding are unchanged. The `cryptography` library (via `cryptography.hazmat`) is used for the TripleDES cipher — this is a non-standard dependency for Odoo but already present in the Odoo Python environment.

### Security: Credential Storage

| Field | Storage | Protection |
|-------|---------|------------|
| `redsys_merchant_code` | Plain Char in `payment.provider` | No group restriction |
| `redsys_merchant_terminal` | Plain Char | No group restriction |
| `redsys_secret_key` | Plain Char (Base64-encoded) | `base.group_system` |

### Security: Signature Verification

The Redsys signature uses `hmac.compare_digest()` for timing-safe comparison. The controller verifies incoming signatures from both the return URL and the webhook:

```python
received_signature = payment_data.get('Ds_Signature')
expected_signature = tx_sudo.provider_id._redsys_calculate_signature(
    payment_data.get('Ds_MerchantParameters'),
    tx_sudo.reference,
    tx_sudo.provider_id.redsys_secret_key,
)
if not hmac.compare_digest(received_signature, expected_signature):
    raise Forbidden()
```

### Security: 3DES Key Handling

- The secret key stored in `redsys_secret_key` is the Base64 encoding of a SHA-256 hash (as provided by Redsys to the merchant)
- The 3DES cipher is derived from the key using the **order reference** (not the full merchant parameters) — this is Redsys's specific anti-tampering mechanism
- The derived key is never stored; it is recomputed on every request

### Security: Return URL vs Webhook

Both routes verify the same HMAC signature. The return is a GET request (customer redirects from Redsys SIS), while the webhook is a POST. The controller decodes the Base64 payload from `Ds_MerchantParameters` field in both cases.

---

## Related

- [Modules/payment](modules/payment.md) — Base payment module
- [Modules/payment_buckaroo](modules/payment_buckaroo.md) — Buckaroo (EU)
- [Modules/payment_aps](modules/payment_aps.md) — Amazon Payment Services (MENA)
- [Modules/payment_stripe](modules/payment_stripe.md) — Stripe
