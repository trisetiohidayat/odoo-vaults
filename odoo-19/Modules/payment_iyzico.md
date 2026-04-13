---
type: module
module: payment_iyzico
tags: [odoo, odoo19, payment, payment-provider, turkey, iyzico]
created: 2026-04-11
---

# Payment Provider: Iyzico

## Overview

| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Iyzico |
| **Technical** | `payment_iyzico` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `payment` |

## Description

Iyzico is a Turkish payment service provider covering the Turkey market. It provides a checkout form (hosted payment page) integration. Unlike most other bridge modules, Iyzico uses a **token verification pattern**: after the customer completes payment on the Iyzico-hosted page, Odoo must make a follow-up API call to verify the token and retrieve the final transaction result.

**Key characteristics:**
- Redirect-based (Iyzico hosted checkout form)
- Token verification: return only provides a token; Odoo must call API to confirm the result
- Supports TRY, EUR, USD, GBP, CHF, NOK, IRR, RUB currencies
- HMAC-SHA256 authentication with random string nonce
- Supports card payments (Visa, Mastercard, Amex, Troy)

---

## Architecture

```
Odoo                      Iyzico API                        Iyzico Checkout
  |                            |                                  |
  |-- POST /payment/iyzipos/   |                                  |
  |   checkoutform/initialize  |                                  |
  |   (HMAC-SHA256 auth,       |                                  |
  |    basket, buyer data)     |                                  |
  |                            |                                  |
  |<-- 200 {paymentPageUrl,    |                                  |
  |    token}                  |                                  |
  |                            |                                  |
  | (redirect customer to      |                                  |
  |  paymentPageUrl)           |                                  |
  |                            |                                  |
  |                            |<-- customer fills card, pays ----|
  |                            |                                  |
  |                            |-- POST /return?tx_ref=...&       |
  |<-- POST /return?tx_ref=...&  token=XXX                        |
  |   (token only)             |                                  |
  |                            |                                  |
  |-- POST /payment/iyzipos/   |                                  |
  |   checkoutform/auth/ecom/  |                                  |
  |   detail  {token}          |                                  |
  |                            |-- verify token with Iyzico ------|
  |                            |<-- final transaction result -----|
  |   (_process with verified   |                                  |
  |    payment data)           |                                  |
```

**Controller:** `IyzicoController` at `controllers/main.py`
- `PAYMENT_RETURN_ROUTE = '/payment/iyzico/return'` — handles customer return (POST, `save_session=False`)
- `WEBHOOK_ROUTE = '/payment/iyzico/webhook'` — handles async webhook (JSON POST)

---

## Dependencies

```
payment_iyzico
  └── payment (base module)
```

## Module Structure

```
payment_iyzico/
├── __init__.py
├── __manifest__.py
├── const.py                    # Status mapping, supported currencies, method codes
├── controllers/
│   ├── __init__.py
│   └── main.py                # IyzicoController
├── models/
│   ├── __init__.py
│   ├── payment_provider.py    # PaymentProvider extension
│   └── payment_transaction.py # PaymentTransaction extension
├── views/
│   ├── payment_iyzico_templates.xml
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
        selection_add=[('iyzico', "Iyzico")],
        ondelete={'iyzico': 'set default'}
    )
```

### Methods Overridden

| Method | File | What It Does |
|--------|------|--------------|
| `_get_supported_currencies()` | `payment_provider.py` | Filters to TRY, EUR, USD, GBP, CHF, NOK, IRR, RUB |
| `_get_default_payment_method_codes()` | `payment_provider.py` | Returns card, mastercard, visa, amex, troy |
| `_build_request_url()` | `payment_provider.py` | Routes to api.iyzipay.com or sandbox-api.iyzipay.com |
| `_build_request_headers()` | `payment_provider.py` | Builds HMAC-SHA256 auth header with random nonce |
| `_iyzico_calculate_signature()` | `payment_provider.py` | HMAC-SHA256 over `{random}/{endpoint}/{payload}` |
| `_parse_response_error()` | `payment_provider.py` | Extracts `errorMessage` from Iyzico error response |
| `_parse_response_content()` | `payment_provider.py` | Checks `status == 'success'`, raises `ValidationError` otherwise |
| `_get_specific_rendering_values()` | `payment_transaction.py` | Calls initialize endpoint, returns redirect URL and params |
| `_iyzico_prepare_cf_initialize_payload()` | `payment_transaction.py` | Builds basket, buyer, billing address payload |
| `_extract_amount_data()` | `payment_transaction.py` | Returns `price` and `currency` from verified payment data |
| `_apply_updates()` | `payment_transaction.py` | Maps `paymentStatus`, updates provider_reference and payment method |

---

## L2: Fields, Defaults, Constraints

### `payment.provider` Extended Fields

| Field | Type | Required | Groups | Description |
|-------|------|----------|--------|-------------|
| `code` | `selection` | Yes | — | Added `iyzico` option |
| `iyzico_key_id` | `Char` | Yes (if `iyzico`) | — | Iyzico API Key |
| `iyzico_key_secret` | `Char` | Yes (if `iyzico`) | `base.group_system` | Iyzico Secret Key for HMAC signing |

### `const.py` — Iyzico Constants

```python
SUPPORTED_CURRENCIES = ['CHF', 'EUR', 'GBP', 'IRR', 'NOK', 'RUB', 'TRY', 'USD']

DEFAULT_PAYMENT_METHOD_CODES = {'card', 'mastercard', 'visa', 'amex', 'troy'}

PAYMENT_METHODS_MAPPING = {
    'amex':       'american_express',
    'mastercard': 'master_card',
}

PAYMENT_STATUS_MAPPING = {
    'pending': ('INIT_THREEDS', 'CALLBACK_THREEDS',
                 'INIT_BANK_TRANSFER', 'INIT_CREDIT', 'PENDING_CREDIT'),
    'done':    ('SUCCESS',),
    'error':   ('FAILURE',),
}
```

### Supported Currencies

Iyzico supports 8 currencies, with TRY (Turkish Lira) being the primary market currency. The `_get_supported_currencies()` filter prevents processing in unsupported currencies.

---

## L3: Cross-Module, Override Patterns, Workflow Triggers, Failure Modes

### Cross-Module Flow (Token Verification Pattern)

The token verification pattern is the defining architectural difference of Iyzico:

1. **Initialize (`_get_specific_rendering_values`):**
   - Calls `POST /payment/iyzipos/checkoutform/initialize/auth/ecom` with basket, buyer, billing address
   - Returns `paymentPageUrl` and parsed URL params for the redirect form
   - If API call fails, `_set_error()` is called and an empty dict is returned (no redirect shown)

2. **Return (`IyzicoController.iyzico_return_from_payment`):**
   - Receives `tx_ref` (Odoo transaction reference) and `token` (Iyzico checkout token)
   - Calls `_verify_and_process()`

3. **Token Verification (`_verify_and_process`):**
   - Makes a **second API call** to `POST /payment/iyzipos/checkoutform/auth/ecom/detail` with the token
   - Iyzico confirms whether the payment succeeded or failed
   - Calls `_process()` with the verified payment data
   - If verification fails, logs error and silently returns (no `_set_error()` on return — this is a design choice)

4. **Webhook (`IyzicoController.iyzico_webhook`):**
   - Receives JSON webhook with `token` and `paymentConversationId`
   - Uses `paymentConversationId` as reference for `_search_by_reference()`
   - Same token verification flow as return route

### Override Pattern

The token verification adds a **pre-confirmation step** that other bridge modules lack:

```
1. _get_specific_rendering_values()    → initialize checkout, get paymentPageUrl
2. (redirect → Iyzico page → return)
3. _verify_and_process() [controller]   → call detail API to verify token
4. _process() → _extract_amount_data() → from verified response
5. _process() → _apply_updates()        → map paymentStatus
```

This means `_extract_reference()` is NOT overridden in `PaymentTransaction` — the base module's `_search_by_reference()` uses the `reference` field (which is the `conversationId` passed to Iyzico) for lookup.

### Workflow Triggers

| Trigger | Route | What Happens |
|---------|-------|-------------|
| Customer return | `POST /payment/iyzico/return` | Extracts `token` + `tx_ref`, verifies token via API, `_process()` |
| Async webhook | `POST /payment/iyzico/webhook` | Reads JSON, extracts `token` + `paymentConversationId`, verifies and processes |

### Failure Modes

| Scenario | Behavior |
|----------|----------|
| Missing `token` in return | Logs warning, redirects to status page without processing |
| Missing `token` in webhook | Logs warning, returns JSON acknowledgement (no error thrown) |
| `_send_api_request` fails in rendering | `_set_error()` on tx, returns `{}`, no redirect form shown |
| `status != 'success'` in verify response | `ValidationError` raised from `_parse_response_content()` — caught as `_set_error()` |
| Unknown `paymentStatus` | `_set_error("Unknown status code: ...")` |

---

## L4: Odoo 18→19 Changes, Security

### Version Changes (Odoo 18→19)

No breaking API changes identified. Iyzico's checkout form API has been stable. The Odoo 19 base `payment` module's `_send_api_request` is the same as Odoo 18, so the request building and response parsing overrides remain compatible.

### Security: Credential Storage

| Field | Storage | Protection |
|-------|---------|------------|
| `iyzico_key_id` | Plain Char in `payment.provider` | No group restriction |
| `iyzico_key_secret` | Plain Char | `base.group_system` |

### Security: HMAC-SHA256 Authentication

Iyzico uses HMAC-SHA256 with a random nonce (similar to AWS Signature Version 4):

```python
def _build_request_headers(self, method, endpoint, payload, **kwargs):
    random_string = ''.join(
        random.SystemRandom().choice(string.ascii_letters + string.digits)
        for _i in range(8)
    )
    signature = self._iyzico_calculate_signature(endpoint, payload, random_string)
    authorization_params = [
        f'apiKey:{self.iyzico_key_id}',
        f'randomKey:{random_string}',
        f'signature:{signature}'
    ]
    hash_base64 = base64.b64encode('&'.join(authorization_params).encode()).decode()
    return {
        'Authorization': f'IYZWSv2 {hash_base64}',
        'x-iyzi-rnd': random_string,
    }

def _iyzico_calculate_signature(self, endpoint, payload, random_string):
    payload_string = json.dumps(payload)
    data_string = f'{random_string}/{endpoint}{payload_string}'
    return hmac.new(
        self.iyzico_key_secret.encode(),
        msg=data_string.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()
```

**Key points:**
- Each request uses a unique random nonce (8 chars, alphanumeric) — prevents replay attacks
- The signature covers `{random}/{endpoint}/{json_payload}` — covers the full request
- Authorization header is `IYZWSv2 base64(randomKey:apiKey:signature)` — Odoo's `IYZWSv2` prefix identifies it as an Odoo integration

### Security: Token Verification as Anti-Fraud

The mandatory token verification step (step 3 above) is a security feature: the `token` received at the return URL is only a reference to an in-progress checkout. The actual payment result can only be confirmed by calling Iyzico's detail API. This prevents attackers from fabricating successful return callbacks without completing payment.

### Security: Webhook Handling

The webhook route handles JSON (`type='http'` but body read via `request.get_json_data()`). Unlike other providers that verify a signature, Iyzico uses token verification as the trust mechanism: the `paymentConversationId` (which is the Odoo transaction reference) ties the webhook to a specific transaction, and the token verification confirms the payment result.

---

## Related

- [Modules/payment](modules/payment.md) — Base payment module
- [Modules/payment_aps](modules/payment_aps.md) — Amazon Payment Services (MENA)
- [Modules/payment_buckaroo](modules/payment_buckaroo.md) — Buckaroo (EU)
- [Modules/payment_stripe](modules/payment_stripe.md) — Stripe
