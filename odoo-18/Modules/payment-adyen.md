---
Module: payment_adyen
Version: Odoo 18
Type: Integration
Tags: #payment, #adyen, #provider, #integration, #orm, #webhook, #3ds2
---

# Payment Provider: Adyen (`payment_adyen`)

> **Source:** `~/odoo/odoo18/odoo/addons/payment_adyen/`
> **Manifest:** `version: 2.0`, `category: Accounting/Payment Providers`, `depends: payment`
> **License:** LGPL-3

A Dutch payment provider covering Europe and the US. Integrates via Adyen's Checkout API (v71) and Recurring API (v68). Supports card payments, wallets (Apple Pay, Google Pay, PayPal), bank transfers, and regional methods. Full tokenization (stored credentials), manual capture, partial refunds, and 3DS2/SCA are all supported.

---

## Module Structure

```
payment_adyen/
├── models/
│   ├── __init__.py
│   ├── payment_provider.py     # payment.provider extension
│   ├── payment_transaction.py  # payment.transaction extension
│   └── payment_token.py        # payment.token extension
├── controllers/
│   └── main.py                 # AdyenController (webhook + payment routes)
├── wizards/
│   ├── __init__.py
│   ├── payment_capture_wizard.py   # Capture wizard extension
│   └── payment_capture_wizard_views.xml
├── const.py                    # API versions, currency decimals, result code mapping
├── utils.py                    # format_partner_name, include_partner_addresses, format_partner_address
├── data/
│   └── payment_provider_data.xml
└── static/src/js/
    └── payment_form.js
```

---

## Models

### `payment.provider` (Extended)

Inherits `payment.provider` and registers `code = 'adyen'`. All Adyen-specific credentials are stored here.

#### Fields

| Field | Type | Required | Groups | Description |
|-------|------|----------|--------|-------------|
| `code` | `Selection` | Yes | — | Extends selection with `('adyen', "Adyen")` |
| `adyen_merchant_account` | `Char` | Yes | `base.group_system` | Adyen merchant account identifier |
| `adyen_api_key` | `Char` | Yes | `base.group_system` | Adyen Webservice API key (server-side only) |
| `adyen_client_key` | `Char` | Yes | — | Adyen Client Key (used in frontend SDK) |
| `adyen_hmac_key` | `Char` | Yes | `base.group_system` | HMAC key for webhook signature verification |
| `adyen_api_url_prefix` | `Char` | Yes | — | Adyen API URL prefix from the Adyen merchant portal (e.g. `1234567`) |

#### Feature Support Flags

| Feature | Support Level |
|---------|--------------|
| `support_manual_capture` | `partial` — Adyen supports delayed capture; Odoo can trigger capture/void |
| `support_refund` | `partial` — Full and partial refunds |
| `support_tokenization` | `True` — Recurring/stored card payments |
| `support_express_checkout` | — (not set) |

#### Lifecycle Methods

**`create(values_list)`** — Overrides create to extract and normalize the `adyen_api_url_prefix` from a pasted URL via regex `r'(?:https://)?(\w+-\w+).*'` → group 1. Strips trailing slashes.

**`write(values)`** — Same prefix normalization on write.

#### Business Methods — Payment Flow

**`_adyen_make_request(endpoint, endpoint_param=None, payload=None, method='POST', idempotency_key=None)`**

Core HTTP client for all Adyen API calls. Builds URL dynamically:

```
https://{prefix}.adyen.com/checkout/V{version}/{endpoint}       # live
https://{prefix}.adyen.com/checkout/V{version}/{endpoint}       # test
```

The test mode URL uses `.adyen.com`; live uses `-{prefix}-checkout-live.adyenpayments.com`.

- `X-API-Key` header set from `adyen_api_key`
- `idempotency-key` header supported (PayPal-style `Idempotency-Key`)
- HTTP 4xx with JSON error body raises `ValidationError`
- HTTP connection error raises `ValidationError`
- Timeout: 60 seconds

**`_adyen_compute_shopper_reference(partner_id)`** → `f'ODOO_PARTNER_{partner_id}'`

Used as `shopperReference` in all Adyen requests. Unique per partner — stored on `payment.token.adyen_shopper_reference`.

**`_adyen_get_inline_form_values(pm_code, amount=None, currency=None)`** → JSON string

Returns values needed by the frontend JS to render the Adyen Web Drop-in:
```python
{
    'client_key': <self.adyen_client_key>,
    'adyen_pm_code': const.PAYMENT_METHODS_MAPPING.get(pm_code, pm_code),
    'formatted_amount': {'value': <minor_units>, 'currency': <code>}
}
```

**`_adyen_get_formatted_amount(amount, currency)`** → `{'value': minor_units, 'currency': code}`

Converts amount to Adyen minor units using `const.CURRENCY_DECIMALS` override map.

**`_get_default_payment_method_codes()`** → `{'card', 'visa', 'mastercard', 'amex', 'discover'}`

---

### `payment.transaction` (Extended)

Inherits `payment.transaction`. Handles Adyen payment flows, webhook processing, and side-effects (capture, void, refund, tokenization).

#### Processing Values

**`_get_specific_processing_values(processing_values)`**

Returns:
```python
{
    'converted_amount': <minor_units int>,
    'access_token': <hmac-signed token tying amount+ref+partner to this request>
}
```

The `access_token` is verified in the controller before calling `/payments` to prevent tampering.

#### Flow: Online Payment (Direct)

**Controller: `AdyenController.adyen_payments()`** — called via `/payment/adyen/payments`

1. Verifies `access_token` via `payment_utils.check_access_token()`
2. Builds Adyen payment payload:
   - `merchantAccount`, `amount`, `countryCode`, `reference`
   - `paymentMethod` from frontend
   - `shopperReference` = `ODOO_PARTNER_{partner_id}`
   - `recurringProcessingModel`: `'CardOnFile'` (most likely to trigger 3DS)
   - `storePaymentMethod`: `tx_sudo.tokenize` (bool)
   - `authenticationData.threeDSRequestData.nativeThreeDS`: `'preferred'` — enables 3DS2
   - `channel`: `'web'`, `origin`: base URL (required for 3DS)
   - `browserInfo`: passed from frontend
   - `lineItems`: single line item with amount+tax
   - If `capture_manually=False`: `captureDelayHours: 0` (override to immediate capture)
3. Calls `_adyen_make_request('/payments', payload=data)`
4. Calls `_handle_notification_data('adyen', response_content + merchantReference)`
5. Returns response to frontend (may contain `resultCode` like `RedirectShopper` or `Authorised`)

#### Flow: 3DS2 / SCA Handling

- Adyen's Checkout API handles 3DS2 natively via `threeDSRequestData.nativeThreeDS: 'preferred'`
- `origin` (base URL) and `browserInfo` are required and passed to Adyen
- 3DS1 redirects handled by **`adyen_return_from_3ds_auth()`** at `/payment/adyen/return`
  - Reads `redirectResult` param, calls `/payments/details` with `redirectResult`
  - Overrides `tx.operation = 'online_redirect'` before processing
- Frontend calls **`adyen_payment_details()`** at `/payment/adyen/payments/details` for additional action results

#### Flow: Tokenization / S2S Recurring

**`_send_payment_request()`** — for tokenized (S2S / off-session) payments:

```python
{
    'merchantAccount': <from provider>,
    'amount': {'value': <minor_units>, 'currency': <code>},
    'countryCode': <partner country or NL>,
    'reference': <tx.reference>,
    'paymentMethod': {'storedPaymentMethodId': <token.provider_ref>},
    'shopperReference': <token.adyen_shopper_reference>,
    'recurringProcessingModel': 'Subscription',
    'shopperInteraction': 'ContAuth',    # Continuous authority
    'shopperIP': <customer IP>,
    'shopperEmail': <partner email>,
    'shopperName': {'firstName': ..., 'lastName': ...},
    'telephoneNumber': <partner phone>,
    'lineItems': [{'amountIncludingTax': ..., 'quantity': '1', 'description': ...}],
    'captureDelayHours': 0  # if not manual capture
}
```

If `operation == 'offline'` and error occurs: logs to chatter and returns (no rollback).

#### Flow: Capture

**`_send_capture_request(amount_to_capture=None)`**

Calls `POST /payments/{provider_reference}/captures` with:
```python
{
    'merchantAccount': <provider.adyen_merchant_account>,
    'amount': {'value': <minor_units>, 'currency': <currency>},
    'reference': <tx.reference>
}
```

Response with `status == 'received'` logs to chatter. Child transaction PSP reference updated from response.

#### Flow: Void / Cancel

**`_send_void_request(amount_to_void=None)`**

Calls `POST /payments/{provider_reference}/cancels`. Child void PSP reference updated.

#### Flow: Refund

**`_send_refund_request(amount_to_refund=None)`**

Creates a child `refund_tx` first (via super), then calls:
```
POST /payments/{provider_reference}/refunds
```
with:
```python
{
    'merchantAccount': ...,
    'amount': {'value': <negative_minor_units>, 'currency': ...},
    'reference': <refund_tx.reference>
}
```

Adyen returns `pspReference` (different from original payment) + `status: 'received'`. That PSP ref is written to `refund_tx.provider_reference`.

#### Webhook Processing

**Controller: `AdyenController.adyen_webhook()`** at `POST /payment/adyen/notification`

1. Parses JSON body — `data['notificationItems']`
2. For each `NotificationRequestItem`:
   - Looks up transaction by `merchantReference` (for `AUTHORISATION`) or `pspReference` (for capture/void/refund)
   - Calls `_verify_notification_signature()` — HMAC-SHA256 over flattened payload
   - Remaps `eventCode` + `success` booleans into `resultCode` strings:
     - `AUTHORISATION` + `success=true` → `resultCode: 'Authorised'`
     - `CANCELLATION` + `success=true` → `resultCode: 'Cancelled'`
     - `REFUND/CAPTURE` + `success=true` → `resultCode: 'Authorised'`
     - `CAPTURE_FAILED` + `success=true` → `resultCode: 'Error'`
   - Skips unsupported event codes silently (acks them)
3. Calls `tx._handle_notification_data('adyen', notification_data)`
4. Returns `'[accepted]'` (plain text response required by Adyen)

**Signature Verification (`_verify_notification_signature`)**

- Reads `additionalData.hmacSignature` from payload
- Computes HMAC-SHA256 over keys: `pspReference, originalReference, merchantAccountCode, merchantReference, amount.value, amount.currency, eventCode, success`
- Uses `binascii.a2b_hex(hmac_key)` (HMAC key is hex-encoded)
- Compares with `hmac.compare_digest` (timing-safe)

#### `_process_notification_data` State Mapping

| Adyen `resultCode` | Odoo State |
|-------------------|-----------|
| `ChallengeShopper`, `IdentifyShopper`, `Pending`, `PresentToShopper`, `Received`, `RedirectShopper` | `_set_pending()` |
| `Authorised` + manual capture ON + `AUTHORISATION` event | `_set_authorized()` |
| `Authorised` + manual capture ON + `CAPTURE` event | `_set_done()` |
| `Authorised` + manual capture OFF | `_set_done()` |
| `Cancelled` | `_set_canceled()` |
| `Error` | `_set_error()` |
| `Refused` | `_set_error("Your payment was refused. Please try again.")` |
| Unknown | `_set_error("Received data with invalid payment state: ...")` |

#### Child Transaction Creation

**`_adyen_create_child_tx_from_notification_data(source_tx, notification_data, is_refund=False)`**

Used for Adyen-initiated capture/void/refund (not initiated from Odoo). Adyen can use the same `pspReference` pattern across child operations. Creates child transaction via `source_tx._create_child_transaction(converted_amount, is_refund=..., provider_reference=...)`.

#### Tokenization

**`_adyen_tokenize_from_notification_data(notification_data)`**

When `tokenize=True` and `resultCode == 'Authorised'`:
1. Reads `additionalData.recurring.recurringDetailReference` and `additionalData.recurring.shopperReference`
2. Creates `payment.token` with:
   - `provider_ref`: `recurring.recurringDetailReference` (Adyen stored credential ID)
   - `adyen_shopper_reference`: `recurring.shopperReference` (ODOO_PARTNER_{id})
3. Links token to transaction and clears `tokenize` flag

---

### `payment.token` (Extended)

| Field | Type | Description |
|-------|------|-------------|
| `adyen_shopper_reference` | `Char` (readonly) | The `shopperReference` used for this partner's Adyen recurring agreements. Format: `ODOO_PARTNER_{partner_id}`. Used to look up stored payment methods. |

---

### Wizard: `payment.capture.wizard` (Extended)

**`payment_capture_wizard.py`** — Adyen adds one boolean field:

| Field | Type | Description |
|-------|------|-------------|
| `has_adyen_tx` | `Boolean` (compute) | True if any selected transaction has `provider_code == 'adyen'`. Used to conditionally show Adyen-specific UI in the capture wizard. |

```python
@api.depends('transaction_ids')
def _compute_has_adyen_tx(self):
    for wizard in self:
        wizard.has_adyen_tx = any(tx.provider_code == 'adyen' for tx in wizard.transaction_ids)
```

---

## Constants (`const.py`)

### API Endpoint Versions

```python
API_ENDPOINT_VERSIONS = {
    '/paymentMethods': 71,        # Checkout API
    '/payments': 71,               # Checkout API
    '/payments/details': 71,      # Checkout API
    '/payments/{}/cancels': 71,    # Checkout API
    '/payments/{}/captures': 71,   # Checkout API
    '/payments/{}/refunds': 71,    # Checkout API
}
```

### Currency Decimals (Non-Standard)

```python
CURRENCY_DECIMALS = {'CLP': 2, 'CVE': 0, 'IDR': 0, 'ISK': 2}
```

### Payment Method Code Mapping

Adyen internal codes (excerpt): `scheme`→card, `mc`→mastercard, `visa`→visa, `amex`→amex, `sepadirectdebit`→sepa_direct_debit, `afterpaytouch`→afterpay, `klarna_account`→klarna_pay_over_time, `directEbanking`→sofort, `cup`→unionpay, `wechatpayQR`→wechat_pay, `cashapp`→cash_app_pay, etc.

### Result Code Mapping

```python
RESULT_CODES_MAPPING = {
    'pending':    ('ChallengeShopper', 'IdentifyShopper', 'Pending',
                   'PresentToShopper', 'Received', 'RedirectShopper'),
    'done':       ('Authorised',),
    'cancel':     ('Cancelled',),
    'error':      ('Error',),
    'refused':    ('Refused',),
}
```

---

## L4: Deep-Dive Notes

### How Adyen API Integration Works

1. **Frontend** loads Adyen's Web Drop-in via the JS asset
2. Frontend calls `/payment/adyen/payment_methods` with amount + country → Adyen returns available methods
3. Customer submits payment → frontend calls `/payment/adyen/payments` with encrypted card data
4. Controller verifies `access_token`, then calls Adyen `/payments` (Checkout API v71)
5. Adyen returns `resultCode` — could be `Authorised`, `Refused`, `Pending`, `RedirectShopper`, etc.
6. If `RedirectShopper` (3DS1 or redirect-based method): browser redirected to Adyen → returns with `redirectResult` → `/payment/adyen/payments/details` called
7. `_handle_notification_data` updates transaction state
8. If `tokenize=True`: Adyen returns `additionalData.recurring.*` → token created

### 3DS2 / SCA Handling

- Odoo prefers native 3DS2 (`nativeThreeDS: 'preferred'`) but gracefully falls back to 3DS1 redirect
- `origin` (Odoo's base URL) and `browserInfo` are mandatory for 3DS to work
- The `returnUrl` parameter on the `/payments` request points to `/payment/adyen/return`
- `recurringProcessingModel: 'CardOnFile'` increases chance of triggering SCA even for stored cards

### Webhook Signature Verification

Uses Adyen's **HMAC-SHA256** signature. The signing string is built by concatenating 8 fixed fields with `:` separator, after flattening the nested notification dict. The HMAC key is stored in hex format (`binascii.a2b_hex`). Adyen expects base64-encoded output. Comparison is timing-safe (`hmac.compare_digest`).

### Adyen-Initiated Operations

Adyen can send notifications for operations done in the Adyen merchant portal (not via Odoo):
- `CAPTURE`: Adyen auto-captures after configured delay
- `CANCELLATION`: Adyen voided an authorization
- `REFUND`: Refund issued from Adyen dashboard

All three result in `source_tx` being updated OR a child transaction being created in Odoo. Partial captures/voids create child transactions; full ones update the source transaction directly.

### How Refund Works

1. User triggers refund from Odoo → `_send_refund_request` called
2. Child `refund_tx` record created with negative amount
3. `POST /payments/{pspReference}/refunds` sent to Adyen
4. Adyen returns `pspReference` for the refund (different from original)
5. State tracked via webhook: `charge.refund` event processed in Stripe webhook; Adyen uses `REFUND` event code

### Capture Delay Override Pattern

When `capture_manually=False` on the provider, Odoo **forces** `captureDelayHours: 0` on the payment request. This is critical: without it, if the merchant account has a default capture delay (e.g., 24 hours), the `AUTHORISATION` webhook event would arrive but the payment would not actually be captured. Odoo would show "Authorized" but the money would not be settled. By forcing immediate capture, Odoo ensures the payment completes in one step.

### `adyen_api_url_prefix` Normalization

The prefix is extracted from the full API URL pasted in the merchant portal (e.g., `https://checkout-test.adyen.com/v71/...` → `checkout-test`). Both `create` and `write` trigger normalization via `_adyen_extract_prefix_from_api_url`, which uses `re.sub(r'(?:https://)?(\w+-\w+).*', r'\1', prefix)`.

---

## Routes Summary

| Route | Type | Auth | Purpose |
|-------|------|------|---------|
| `/payment/adyen/payment_methods` | JSON | public | Query available Adyen payment methods |
| `/payment/adyen/payments` | JSON | public | Initiate payment; calls Adyen `/payments` |
| `/payment/adyen/payments/details` | JSON | public | Submit 3DS/redirect details; calls Adyen `/payments/details` |
| `/payment/adyen/return` | HTTP | public | 3DS1 return URL (no CSRF, no session save) |
| `/payment/adyen/notification` | HTTP | public | Adyen webhook receiver |

---

## Hooks

```python
# post_init_hook
setup_provider(env, 'adyen')   # Creates payment.provider record for 'adyen'

# uninstall_hook
reset_payment_provider(env, 'adyen')  # Removes/demotes the provider record
```

---

## Relations

- `payment.transaction` → `payment.provider` via `provider_id` (Many2one)
- `payment.transaction` → `payment.token` via `token_id` (Many2one, optional)
- `payment.token` → `payment.provider` via `provider_id` (Many2one)
- `payment.token` → `res.partner` via `partner_id` (Many2one)

---

## See Also

- [[Modules/payment]] — Base payment module (`payment.provider`, `payment.transaction`, `payment.token`)
- [[Core/API]] — `@api.depends`, `@api.onchange`, access token pattern
- [[Patterns/Security Patterns]] — ir.rule, field groups, `base.group_system`
