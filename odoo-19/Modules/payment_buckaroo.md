---
type: module
module: payment_buckaroo
tags: [odoo, odoo19, payment, payment-provider, eu, buckaroo]
created: 2026-04-11
---

# Payment Provider: Buckaroo

## Overview

| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Buckaroo |
| **Technical** | `payment_buckaroo` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `payment` |

## Description

Buckaroo is a Dutch payment service provider (PSP) covering multiple European countries. The module integrates with Buckaroo's HTML redirect checkout to support card payments, iDEAL, PayPal, SEPA Direct Debit, Bancontact, Klarna, and many other European payment methods. Buckaroo uses a BPE 3.0 HTML interface where the customer is redirected to a Buckaroo-hosted payment page.

**Key characteristics:**
- Redirect-based (Buckaroo HTML checkout page)
- Extensive European payment method coverage (20+ methods)
- SHA-1 digital signature for request signing
- Separate return URL and webhook (BPE 3.0 spec)
- Currency filtering — only EUR, GBP, PLN, DKK, NOK, SEK, CHF, USD

---

## Architecture

```
Odoo                     Buckaroo                       Buckaroo API
  |                           |                               |
  |-- POST /payment/pay ------>|                               |
  |   (rendering_values:       |                               |
  |    Brq_websitekey,          |                               |
  |    Brq_amount, Brq_signature|                               |
  |                            |-- GET /html/?Brq_... ------->|
  |                            |   (redirect to Buckaroo page)  |
  |  (customer pays on         |                               |
  |   Buckaroo page)          |                               |
  |                            |<-- POST /return (result) ------|
  |                            |   (brq_statuscode,            |
  |                            |    brq_transactions)          |
  |<-- POST /return ---------->|                               |
  |   (signature verified,      |                               |
  |    _process called)         |                               |
  |                            |                               |
  |<-- POST /webhook --------->|                               |
  |   (async BPE notification) |                               |
```

**Controller:** `BuckarooController` at `controllers/main.py`
- `_return_url = '/payment/buckaroo/return'` — handles customer redirect (POST, `save_session=False`)
- `_webhook_url = '/payment/buckaroo/webhook'` — handles BPE asynchronous notification

---

## Dependencies

```
payment_buckaroo
  └── payment (base module)
```

## Module Structure

```
payment_buckaroo/
├── __init__.py
├── __manifest__.py
├── const.py                 # Payment method mapping, status codes, supported currencies
├── controllers/
│   ├── __init__.py
│   └── main.py              # BuckarooController
├── models/
│   ├── __init__.py
│   ├── payment_provider.py  # PaymentProvider extension
│   └── payment_transaction.py # PaymentTransaction extension
├── views/
│   ├── payment_buckaroo_templates.xml
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
        selection_add=[('buckaroo', "Buckaroo")],
        ondelete={'buckaroo': 'set default'}
    )
```

### Methods Overridden

| Method | File | What It Does |
|--------|------|--------------|
| `_get_supported_currencies()` | `payment_provider.py` | Filters to EUR, GBP, PLN, DKK, NOK, SEK, CHF, USD |
| `_get_default_payment_method_codes()` | `payment_provider.py` | Returns card, ideal, visa, mastercard, amex, discover |
| `_buckaroo_get_api_url()` | `payment_provider.py` | Returns production or sandbox HTML endpoint |
| `_buckaroo_generate_digital_sign()` | `payment_provider.py` | SHA-1 of sorted BPE parameters with secret key |
| `_get_specific_rendering_values()` | `payment_transaction.py` | Builds BPE 3.0 payload with all required Brq_ fields |
| `_extract_reference()` | `payment_transaction.py` | Extracts `brq_invoicenumber` from response |
| `_extract_amount_data()` | `payment_transaction.py` | Extracts `brq_amount` and `brq_currency` |
| `_apply_updates()` | `payment_transaction.py` | Maps status code, updates provider_reference and payment method |

---

## L2: Fields, Defaults, Constraints

### `payment.provider` Extended Fields

| Field | Type | Required | Groups | Description |
|-------|------|----------|--------|-------------|
| `code` | `selection` | Yes | — | Added `buckaroo` option |
| `buckaroo_website_key` | `Char` | Yes (if `buckaroo`) | — | Website key for Buckaroo identification |
| `buckaroo_secret_key` | `Char` | Yes (if `buckaroo`) | `base.group_system` | Pre-shared secret for SHA-1 signing |

### `const.py` — Buckaroo Constants

```python
DEFAULT_PAYMENT_METHOD_CODES = {
    'card', 'ideal', 'visa', 'mastercard', 'amex', 'discover'
}

PAYMENT_METHODS_MAPPING = {
    # 20+ mappings: alipay, apple_pay, bancontact, belfius, billink,
    # card, cartes_bancaires, eps, giropay, in3, ideal, kbc,
    # bank_reference, p24, paypal, poste_pay, sepa_direct_debit,
    # sofort, tinka, trustly, wechat_pay, klarna, afterpay_riverty
}

STATUS_CODES_MAPPING = {
    'pending': (790, 791, 792, 793),
    'done':    (190,),
    'cancel':  (890, 891),
    'refused': (690,),
    'error':   (490, 491, 492),
}

SUPPORTED_CURRENCIES = ['EUR', 'GBP', 'PLN', 'DKK', 'NOK', 'SEK', 'CHF', 'USD']
```

### Supported Currencies

Only 8 currencies are supported by Buckaroo. `_get_supported_currencies()` in `PaymentProvider` filters the available currencies for any provider with code `buckaroo`. Transactions in unsupported currencies will be blocked at the provider level.

---

## L3: Cross-Module, Override Patterns, Workflow Triggers, Failure Modes

### Cross-Module Flow

1. **Checkout init:** `PaymentTransaction._get_specific_rendering_values()` builds Buckaroo BPE 3.0 payload
2. **Redirect:** Customer posts to Buckaroo HTML endpoint with signed `Brq_` parameters
3. **Return:** `BuckarooController.buckaroo_return_from_checkout()` receives POST, normalizes keys to lowercase, verifies signature, calls `_process()`
4. **Webhook:** `BuckarooController.buckaroo_webhook()` handles BPE async notification (same pattern)
5. **Post-processing:** `_apply_updates()` maps `brq_statuscode` to Odoo states

### Override Pattern

The same 4-step pipeline used across all bridge modules:

```
1. _get_specific_rendering_values()  → builds Brq_ prefixed form payload
2. _extract_reference()              → brq_invoicenumber
3. _extract_amount_data()           → brq_amount + brq_currency
4. _apply_updates()                 → maps status code, updates provider_reference
```

**Buckaroo-specific signature pattern:** Only parameters with prefixes `add_`, `brq_`, or `cust_` are included in the SHA-1 signing string. Keys are sorted alphabetically (case-insensitive).

### Workflow Triggers

| Trigger | Route | What Happens |
|---------|-------|-------------|
| Customer return redirect | `POST /payment/buckaroo/return` | Key normalization, signature verify, `_process()`, redirect to `/payment/status` |
| BPE async webhook | `POST /payment/buckaroo/webhook` | Same processing, empty string acknowledgement |

**Key normalization:** Buckaroo parameter names are case-insensitive. `_normalize_data_keys()` converts all keys to lowercase so Odoo's lookup is case-insensitive (e.g., `brq_invoicenumber` vs `BRQ_InvoiceNumber`).

### Failure Modes

| Scenario | Behavior |
|----------|----------|
| Missing `brq_signature` | `Forbidden()` — rejected |
| SHA-1 signature mismatch | `Forbidden()` — rejected |
| `brq_transactions` missing | `_set_error("Received data with missing transaction keys")` |
| `brq_statuscode` = 690 | `_set_error("Your payment was refused")` |
| `brq_statuscode` = 490/491/492 | `_set_error("An error occurred during processing")` |
| Unknown status code | `_set_error("Unknown status code: ...")` |

---

## L4: Odoo 18→19 Changes, Security

### Version Changes (Odoo 18→19)

No breaking API changes identified. The module structure, SHA-1 signing logic, and status code mappings are unchanged between Odoo 18 and 19. The BPE 3.0 specification Buckaroo uses has been stable.

### Security: Credential Storage

| Field | Storage | Protection |
|-------|---------|------------|
| `buckaroo_website_key` | Plain Char in `payment.provider` | No group restriction |
| `buckaroo_secret_key` | Plain Char | `base.group_system` — admin-only visibility |

### Security: Signature Verification

**SHA-1 signing (outgoing — Odoo to Buckaroo):**
```python
def _buckaroo_generate_digital_sign(values, incoming=True):
    # For outgoing: use raw values as-is
    items = values.items()
    # Filter to brq_, add_, cust_ prefixes only
    filtered_items = [(k, v) for k, v in items
                      if any(k.lower().startswith(p) for p in ('add_', 'brq_', 'cust_'))]
    # Sort by lowercased key
    sorted_items = sorted(filtered_items, key=lambda p: p[0].lower())
    # Build string k=v pairs
    sign_string = ''.join(f'{k}={v or ""}' for k, v in sorted_items)
    sign_string += self.buckaroo_secret_key  # append secret
    return sha1(sign_string.encode('utf-8')).hexdigest()
```

**Incoming verification (Buckaroo to Odoo):** URL-decodes all values before signing, then compares with received `brq_signature`. Uses `hmac.compare_digest()` for timing-safe comparison.

**Parameter filtering:** Only `add_*`, `brq_*`, `cust_*` parameters participate in the signature — prevents injection via other parameter names.

### Security: Return URL Sharing

Buckaroo's BPE 3.0 specification uses the same URL for all 4 return scenarios (success, cancel, error, reject). All four are mapped to the same Odoo return URL:

```python
'Brq_return': return_url,
'Brq_returncancel': return_url,
'Brq_returnerror': return_url,
'Brq_returnreject': return_url,
```

The actual outcome is determined by `brq_statuscode` in the POST data, not the URL.

---

## Related

- [Modules/payment](payment.md) — Base payment module
- [Modules/payment_aps](payment_aps.md) — Amazon Payment Services (MENA)
- [Modules/payment_iyzico](payment_iyzico.md) — Iyzico (Turkey)
- [Modules/payment_stripe](payment_stripe.md) — Stripe
