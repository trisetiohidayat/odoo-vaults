---
type: module
module: payment_aps
tags: [odoo, odoo19, payment, payment-provider, mena, amazon]
created: 2026-04-11
---

# Payment Provider: Amazon Payment Services

## Overview

| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Amazon Payment Services |
| **Technical** | `payment_aps` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `payment` |

## Description

Amazon Payment Services (APS) is a redirect-based payment provider covering the MENA (Middle East and North Africa) region, including UAE, Saudi Arabia, Egypt, Qatar, and surrounding markets. The module integrates with the PayFort/Fort API (now branded under Amazon Payment Services) to handle card payments and alternative payment methods.

**Key characteristics:**
- Redirect-based (customer redirected to APS-hosted checkout page)
- Supports card payments and brand-specific options (Visa, Mastercard, Amex, Discover)
- HMAC-SHA256 signature for both incoming and outgoing communications
- Webhook and redirect return URL for payment status confirmation

---

## Architecture

```
Odoo                    APS Provider               PayFort/Fort API
  |                           |                           |
  |-- GET /shop/payment/pay -->|                           |
  |   (tx created, reference)  |                           |
  |<- 200 (redirect form) ----|-- POST to api_url -------->|
  |                           |   (merchant_reference,     |
  |                           |    amount, currency,       |
  |                           |    signature)              |
  |                           |                           |
  | (customer fills card on    |                           |
  |  APS-hosted page)          |                           |
  |                           |<- POST /return (result) ---|
  |                           |   (fort_id, status,       |
  |                           |    signature)              |
  |<-- POST /return --------->|                           |
  |   (tx._process called)    |                           |
  |                           |                           |
  | (optional webhook)        |                           |
  |<-- POST /webhook ---------|                           |
  |   (same data)             |                           |
```

**Controller:** `APSController` at `controllers/main.py`
- `_return_url = '/payment/aps/return'` — handles redirect from APS
- `_webhook_url = '/payment/aps/webhook'` — receives asynchronous webhook notification

---

## Dependencies

```
payment_aps
  └── payment (base module)
```

## Module Structure

```
payment_aps/
├── __init__.py
├── __manifest__.py
├── const.py                    # Status mapping, default payment method codes
├── utils.py                    # get_payment_option() helper
├── controllers/
│   ├── __init__.py
│   └── main.py                 # APSController
├── models/
│   ├── __init__.py
│   ├── payment_provider.py    # PaymentProvider extension
│   └── payment_transaction.py # PaymentTransaction extension
├── views/
│   ├── payment_aps_templates.xml
│   └── payment_provider_views.xml
└── data/
    └── payment_provider_data.xml
```

---

## L1: Integration with Base `payment` Module

### Provider Registration

`PaymentProvider` extends `payment.provider` by adding the `aps` code to the selection:

```python
class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('aps', "Amazon Payment Services")],
        ondelete={'aps': 'set default'}
    )
```

The `ondelete='set default'` ensures that if the APS module is uninstalled, the provider falls back to `none`.

### Methods Overridden

| Method | File | What It Does |
|--------|------|--------------|
| `_get_default_payment_method_codes()` | `payment_provider.py` | Returns `{'card', 'visa', 'mastercard', 'amex', 'discover'}` |
| `_aps_get_api_url()` | `payment_provider.py` | Returns production or sandbox checkout URL |
| `_aps_calculate_signature()` | `payment_provider.py` | HMAC-SHA256 of sorted `k=v` pairs with passphrase |
| `_compute_reference()` | `payment_transaction.py` | Overrides to use `singularize_reference_prefix()` — APS rejects non-alphanumeric references |
| `_get_specific_rendering_values()` | `payment_transaction.py` | Builds Fort API payload with all required fields |
| `_extract_reference()` | `payment_transaction.py` | Extracts `merchant_reference` from payment data |
| `_extract_amount_data()` | `payment_transaction.py` | Converts minor units back to major, extracts currency |
| `_apply_updates()` | `payment_transaction.py` | Maps status code to transaction state, updates provider reference |

---

## L2: Fields, Defaults, Constraints

### `payment.provider` Extended Fields

| Field | Type | Required | Groups | Description |
|-------|------|----------|--------|-------------|
| `code` | `selection` | Yes | — | Added `aps` option |
| `aps_merchant_identifier` | `Char` | Yes (if `aps`) | — | APS merchant account code |
| `aps_access_code` | `Char` | Yes (if `aps`) | `base.group_system` | Access code for the merchant account |
| `aps_sha_request` | `Char` | Yes (if `aps`) | `base.group_system` | SHA phrase for outgoing requests |
| `aps_sha_response` | `Char` | Yes (if `aps`) | `base.group_system` | SHA phrase for incoming responses |

**Credential field notes:**
- `aps_access_code`, `aps_sha_request`, `aps_sha_response` are in `base.group_system` — only administrators can view/edit them after creation
- `copy=False` on all credential fields prevents credentials from being duplicated with the provider record

### `const.py` Constants

```python
PAYMENT_STATUS_MAPPING = {
    'pending': ('19',),   # Status 19: pending/awaiting
    'done':    ('14',),   # Status 14: authorized/captured
}

DEFAULT_PAYMENT_METHOD_CODES = {
    'card', 'visa', 'mastercard', 'amex', 'discover'
}
```

### `utils.py` — Payment Option Mapping

```python
def get_payment_option(payment_method_code):
    # Returns UPPERCASE code if not 'card', else '' (lets user pick brand on APS page)
    return payment_method_code.upper() if payment_method_code != 'card' else ''
```

---

## L3: Cross-Module, Override Patterns, Workflow Triggers, Failure Modes

### Cross-Module Flow

1. **Checkout init (`sale`):** `payment_transaction` record created with `reference`, `amount`, `currency`, `partner`
2. **Redirect form (`website_sale`):** QWeb form posts to APS checkout URL with signed payload
3. **Return/WEBHOOK (`APSController`):**
   - `_verify_signature()` validates HMAC-SHA256 using `aps_sha_response`
   - `_process()` on the transaction calls the overridden `_extract_*` and `_apply_updates` methods
4. **Post-processing:** `_set_done()`, `_set_pending()`, or `_set_error()` updates the transaction state
5. **sale order:** `sale_order` listens to `transaction.was-success` event via `message_post` notification

### Override Pattern

Each provider follows the same 4-step pipeline in `PaymentTransaction`:

```
1. _get_specific_rendering_values()   → builds form/post payload
2. _extract_reference()               → parses reference from response
3. _extract_amount_data()             → parses amount+currency from response
4. _apply_updates()                  → updates tx state, provider_reference, payment_method
```

### Workflow Trigger

| Trigger | Route | What Happens |
|---------|-------|-------------|
| Customer return redirect | `POST /payment/aps/return` | Signature verified, `_process()` called, redirect to `/payment/status` |
| APS async webhook | `POST /payment/aps/webhook` | Same processing, returns empty `''` acknowledgement |

### Failure Modes

| Scenario | Behavior |
|----------|----------|
| Missing `signature` in response | `Forbidden()` raised — request rejected |
| Signature mismatch | `Forbidden()` raised — potential replay/ tampering |
| Unknown `status` code (not 14 or 19) | `_set_error()` with `response_message` |
| No transaction found for reference | Silently ignored (logged warning) |
| APS API unreachable | Normal HTTP error propagation |

---

## L4: Odoo 18→19 Changes, Security

### Version Changes (Odoo 18→19)

No breaking API changes were identified for `payment_aps` between Odoo 18 and 19. The module structure, constant values, and method signatures are consistent. The Odoo 19 `payment` base module does introduce some internal refactoring (e.g., `_search_by_reference` is now called with a dict instead of positional args in some paths), but `payment_aps` remains fully compatible.

### Security: Credential Storage

| Field | Storage | Protection |
|-------|---------|------------|
| `aps_merchant_identifier` | Plain Char in `payment.provider` table | No group restriction |
| `aps_access_code` | Plain Char | `base.group_system` — visible only to admin |
| `aps_sha_request` | Plain Char | `base.group_system` |
| `aps_sha_response` | Plain Char | `base.group_system` |

**Risk:** Credentials are stored unencrypted in the database. They should be protected at the DB level (DB encryption at rest, restricted DB user) and network level (HTTPS everywhere).

**`copy=False` rationale:** Prevents accidental duplication of the provider with credentials attached.

### Security: Signature Verification

Signature verification uses `hmac.compare_digest()` (timing-safe comparison) to prevent timing attacks:

```python
expected_signature = tx_sudo.provider_id._aps_calculate_signature(payment_data, incoming=True)
if not hmac.compare_digest(received_signature, expected_signature):
    _logger.warning("Received payment data with invalid signature.")
    raise Forbidden()
```

**Incoming vs outgoing signature:**
- `incoming=True`: Uses `aps_sha_response` phrase (for verifying what APS sends)
- `incoming=False`: Uses `aps_sha_request` phrase (for signing what Odoo sends)

The signing string is built from sorted `k=v` pairs concatenated with the phrase on both sides: `phrase + k1=v1k2=v2 + phrase`.

### Security: Session Handling

The return route uses `save_session=False` because the `SameSite` cookie behavior can cause session loss during redirect:

```python
@http.route(_return_url, type='http', auth='public', methods=['POST'], csrf=False, save_session=False)
def aps_return_from_checkout(self, **data):
    # save_session=False prevents Odoo from creating a new session
    # The session is instead recovered when the user lands on /payment/status
```

---

## Related

- [Modules/payment](odoo-18/Modules/payment.md) — Base payment module
- [Modules/payment_stripe](odoo-17/Modules/payment_stripe.md) — Stripe (direct/PCI-compliant)
- [Modules/payment_buckaroo](odoo-18/Modules/payment_buckaroo.md) — Buckaroo (EU)
- [Modules/payment_adyen](odoo-17/Modules/payment_adyen.md) — Adyen
