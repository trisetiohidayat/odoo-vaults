---
type: module
module: payment_dpo
tags: [odoo, odoo19, payment, payment-provider, africa, dpo]
created: 2026-04-11
---

# Payment Provider: DPO

## Overview

| Property | Value |
|----------|-------|
| **Name** | Payment Provider: DPO |
| **Technical** | `payment_dpo` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `payment` |

## Description

DPO (Direct Pay Online) is an African payment service provider covering Kenya, South Africa, Uganda, Tanzania, Rwanda, Ghana, Nigeria, Zambia, and other African markets. DPO is distinctive among Odoo's payment bridges in that it uses a **token creation pattern** with an **XML-based API** (instead of JSON). The module first creates a transaction token via XML POST to the DPO API, then redirects the customer to DPO's hosted payment page. After payment, DPO redirects back to Odoo, which verifies the payment via a second XML API call (verifyToken).

**Key characteristics:**
- XML-based API over HTTPS (not JSON)
- Two-step flow: `createToken` (get redirect URL) → redirect → `verifyToken` (confirm result)
- Single generic `dpo` payment method code (DPO manages the available payment methods on their hosted page)
- Covers 10+ African countries

---

## Architecture

```
Odoo                        DPO API                       DPO Hosted Page
  |                              |                               |
  |-- POST https://.../API/v6/   |                               |
  |   (XML: createToken,         |                               |
  |    CompanyToken, Transaction, |                               |
  |    Services)                |                               |
  |                              |-- HTTP POST ---------------   |
  |                              |                               |
  |<-- XML: <TransToken>XXX</    |                               |
  |   (token created)           |                               |
  |                              |                               |
  |-- redirect to payv2.php?    |                               |
  |   ID=XXX                    |                               |
  |                              |                               |
  |  (customer pays on DPO page) |                               |
  |                              |                               |
  |                              |<-- payment completed ----------|
  |                              |                               |
  |<-- GET /payment/dpo/return  |                               |
  |   (TransID only)            |                               |
  |                              |                               |
  |-- POST https://.../API/v6/   |                               |
  |   (XML: verifyToken,        |                               |
  |    TransactionToken)        |                               |
  |                              |-- verify with DPO ----------->|
  |                              |<-- XML: TransID, Result, -----|
  |                              |    ResultExplanation --------|
  |  (_process with verified     |                               |
  |   payment data)             |                               |
```

**Controller:** `DPOController` at `controllers/main.py`
- `_return_url = '/payment/dpo/return'` — handles customer return (GET, triggers verifyToken)

---

## Dependencies

```
payment_dpo
  └── payment (base module)
```

## Module Structure

```
payment_dpo/
├── __init__.py
├── __manifest__.py
├── const.py                    # Status mapping, default payment method codes
├── controllers/
│   ├── __init__.py
│   └── main.py                # DPOController
├── models/
│   ├── __init__.py
│   ├── payment_provider.py    # PaymentProvider extension
│   └── payment_transaction.py # PaymentTransaction extension
├── views/
│   ├── payment_dpo_templates.xml
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
        selection_add=[('dpo', "DPO")],
        ondelete={'dpo': 'set default'}
    )
```

### Methods Overridden

| Method | File | What It Does |
|--------|------|--------------|
| `_get_default_payment_method_codes()` | `payment_provider.py` | Returns `{'dpo'}` — single generic method |
| `_build_request_url()` | `payment_provider.py` | Returns DPO API endpoint: `https://secure.3gdirectpay.com/API/v6/` |
| `_build_request_headers()` | `payment_provider.py` | Returns `Content-Type: application/xml; charset=utf-8` |
| `_parse_response_content()` | `payment_provider.py` | Parses XML response into flat dict `{tag: text}` |
| `_get_specific_rendering_values()` | `payment_transaction.py` | Calls `_dpo_create_token()`, returns redirect URL |
| `_dpo_create_token()` | `payment_transaction.py` | Builds XML createToken request, calls `_send_api_request()` |
| `_extract_reference()` | `payment_transaction.py` | Extracts `CompanyRef` from payment data |
| `_extract_amount_data()` | `payment_transaction.py` | Extracts `TransactionAmount` and `TransactionCurrency` |
| `_apply_updates()` | `payment_transaction.py` | Maps `Result` code to state, updates provider_reference |

---

## L2: Fields, Defaults, Constraints

### `payment.provider` Extended Fields

| Field | Type | Required | Groups | Description |
|-------|------|----------|--------|-------------|
| `code` | `selection` | Yes | — | Added `dpo` option |
| `dpo_service_ref` | `Char` | Yes (if `dpo`) | — | DPO Service Type ID for this merchant account |
| `dpo_company_token` | `Char` | Yes (if `dpo`) | `base.group_system` | DPO Company Token for authentication |

### `const.py` — DPO Constants

```python
PAYMENT_STATUS_MAPPING = {
    'pending':    ('003', '007'),           # Awaiting approval
    'authorized':  ('001', '005'),           # Authorized
    'done':        ('000', '002'),           # Captured/paid
    'cancel':      ('900', '901', '902',    # Cancelled
                    '903', '904', '950'),
    'error':       ('801', '802',           # Error
                    '803', '804'),
}

DEFAULT_PAYMENT_METHOD_CODES = {'dpo'}
```

### Payment Method Model Note

DPO uses a single generic `dpo` payment method. Unlike other providers that map individual card brands, DPO presents available payment methods (cards, mobile money, bank transfers) on their hosted page based on the customer's country. The `payment.method` record with code `dpo` is created by the module's data file.

### State Mapping

DPO introduces an additional `authorized` state (`'001'`, `'005'`) that is merged with `done` by Odoo:

```python
elif status_code in (
    const.PAYMENT_STATUS_MAPPING['authorized'] + const.PAYMENT_STATUS_MAPPING['done']
):
    self._set_done()
```

This means DPO's pre-authorization states are treated as successful completions.

---

## L3: Cross-Module, Override Patterns, Workflow Triggers, Failure Modes

### Cross-Module Flow (XML Token Pattern)

The DPO flow follows a unique XML-based two-step pattern:

1. **Token creation (`_dpo_create_token`):**
   ```xml
   <?xml version="1.0" encoding="utf-8"?>
   <API3G>
     <CompanyToken>...</CompanyToken>
     <Request>createToken</Request>
     <Transaction>
       <PaymentAmount>100.00</PaymentAmount>
       <PaymentCurrency>USD</PaymentCurrency>
       <CompanyRef>TX-123456S</CompanyRef>
       <RedirectURL>https://.../payment/dpo/return</RedirectURL>
       <BackURL>https://.../payment/dpo/return</BackURL>
       <customerEmail>customer@example.com</customerEmail>
       <customerFirstName>John</customerFirstName>
       <customerLastName>Doe</customerLastName>
       <customerCity>Nairobi</customerCity>
       <customerCountry>KE</customerCountry>
       <customerZip>00100</customerZip>
     </Transaction>
     <Services>
       <Service>
         <ServiceType>1234</ServiceType>   <!-- dpo_service_ref -->
         <ServiceDescription>TX-123456S</ServiceDescription>
         <ServiceDate>2026/04/11 10:00</ServiceDate>
       </Service>
     </Services>
   </API3G>
   ```
   The response is XML: `<TransToken>TOKEN_VALUE</TransToken>`

2. **Redirect:** Customer goes to `https://secure.3gdirectpay.com/payv2.php?ID=TOKEN_VALUE`

3. **Return (`DPOController._verify_and_process`):**
   ```xml
   <?xml version="1.0" encoding="utf-8"?>
   <API3G>
     <CompanyToken>...</CompanyToken>
     <Request>verifyToken</Request>
     <TransactionToken>TransID</TransactionToken>
   </API3G>
   ```
   The verified response includes `<TransID>`, `<Result>`, `<ResultExplanation>`.

4. **`_process`:** `_extract_amount_data()` and `_apply_updates()` handle the verified data.

### Override Pattern

DPO's XML parsing is handled by `_parse_response_content()` on `PaymentProvider`:

```python
def _parse_response_content(self, response, **kwargs):
    root = ET.fromstring(response.content.decode('utf-8'))
    transaction_data = {element.tag: element.text for element in root}
    return transaction_data
```

This flattens the entire XML response into a single-level dict (e.g., `{'TransToken': 'ABC', ...}`). The transaction and controller then treat this dict identically to how other providers treat JSON responses.

### Workflow Triggers

| Trigger | Route | What Happens |
|---------|-------|-------------|
| Customer return | `GET /payment/dpo/return` | Extracts `TransID`, calls `_verify_and_process()`, redirects to `/payment/status` |

**Note:** DPO does not have a webhook endpoint in this module. Payment confirmation relies entirely on the customer return redirect. For high-value transactions, this is a limitation.

### Failure Modes

| Scenario | Behavior |
|----------|----------|
| `createToken` API call fails | `ValidationError` from `_send_api_request`, caught in `_dpo_create_token` as `_set_error()`, returns `None` |
| No `TransToken` in create response | `_dpo_create_token()` returns `None`, `_get_specific_rendering_values()` returns `{}` (no redirect) |
| `verifyToken` fails | `ValidationError` caught, `_verify_and_process()` silently returns (no `_set_error()`) |
| `Result` = cancel codes | `_set_canceled()` |
| `Result` = error codes | `_set_error()` with `ResultExplanation` |
| Unknown `Result` code | `_set_error("Unknown status code: ...")` |

### No Webhook

DPO's module does not implement a webhook endpoint. The return redirect is the only confirmation mechanism. This differs from all other bridge modules which implement both a return route and a webhook.

---

## L4: Odoo 18→19 Changes, Security

### Version Changes (Odoo 18→19)

No breaking API changes. DPO's API has been stable. The XML-based approach remains the same.

### Security: Credential Storage

| Field | Storage | Protection |
|-------|---------|------------|
| `dpo_service_ref` | Plain Char in `payment.provider` | No group restriction |
| `dpo_company_token` | Plain Char | `base.group_system` |

### Security: No Signature Verification on Return

Unlike all other bridge modules (APS, Buckaroo, Iyzico, Redsys), DPO's return route **does not verify a cryptographic signature**. Instead, it relies on:
1. A second API call (`verifyToken`) to DPO to confirm the transaction result
2. The `TransID` as the only identifier from the return URL

This is acceptable because DPO's `verifyToken` response is authoritative — it comes directly from DPO's database via their API, not from the customer's browser.

### Security: XML Parsing Considerations

The XML parsing is straightforward:

```python
root = ET.fromstring(response.content.decode('utf-8'))
transaction_data = {element.tag: element.text for element in root}
```

This assumes the DPO API always returns a flat XML structure with direct child elements. Nested elements (e.g., `<Transaction><Amount>...</Amount></Transaction>`) would not be captured. This works because DPO's API responses are flat.

### Security: No CSRF

DPOController routes use `csrf=False` implicitly (no CSRF flag set, but the route is `auth='public'`). The return route accepts a GET request (not POST), so CSRF is not applicable.

### Security: Network

All DPO API calls are made over HTTPS to `secure.3gdirectpay.com`. Odoo's `_send_api_request()` uses the `requests` library with no special certificate handling — standard Python SSL verification applies.

---

## Shared Bridge Module Architecture Pattern

All five payment bridge modules follow the same architectural pattern:

```
Base: payment module
  Defines: payment.provider, payment.transaction, PaymentController
  Provides: _process(), _send_api_request(), _search_by_reference()
            _set_done(), _set_pending(), _set_error(), _set_canceled()

Each bridge: payment_{code} module
  Provider extension:
    - Add 'code' to selection
    - Add credential fields
    - Override _get_default_payment_method_codes()
    - Implement _get_*_api_url()
    - Implement _calculate_signature()

  Transaction extension:
    - Override _compute_reference() if provider has reference format requirements
    - Override _get_specific_rendering_values() — builds provider-specific payload
    - Override _extract_reference() — parses provider's reference field
    - Override _extract_amount_data() — parses amount + currency
    - Override _apply_updates() — maps status codes, updates provider_reference

  Controller:
    - _return_url — handles customer redirect
    - _webhook_url — handles async notification (optional)
    - _verify_signature() — HMAC verification
    - _verify_and_process() — fetch verified result + _process()
```

| Provider | Signature | API Format | Special Feature |
|----------|-----------|------------|-----------------|
| APS | HMAC-SHA256 | Form POST | — |
| Buckaroo | SHA-1 | Form POST + webhook | Key normalization |
| Iyzico | HMAC-SHA256 | JSON REST + token verify | Token verification |
| Redsys | 3DES-HMAC-SHA256 | Base64 form POST | EMV3DS data |
| DPO | None (verifyToken) | XML REST | XML parsing |

---

## Related

- [Modules/payment](odoo-18/Modules/payment.md) — Base payment module
- [Modules/payment_aps](odoo-18/Modules/payment_aps.md) — Amazon Payment Services (MENA)
- [Modules/payment_buckaroo](odoo-18/Modules/payment_buckaroo.md) — Buckaroo (EU)
- [Modules/payment_stripe](odoo-17/Modules/payment_stripe.md) — Stripe
