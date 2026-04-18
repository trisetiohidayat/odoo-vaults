---
type: module
module: payment_adyen
tags: [odoo, odoo19, payment, adyen]
uuid: 8c4a2f1e-3d6b-4a9c-8e5f-2d1a3b4c5e6f
created: 2026-04-06
---

# Payment Provider: Adyen

## Overview

| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Adyen |
| **Technical** | `payment_adyen` |
| **Category** | Accounting/Payment Providers |
| **Version** | 2.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Module** | `payment_adyen` |

## Description

A Dutch payment provider covering Europe and the US. Adyen is a enterprise-grade payment platform known for its global reach (supports 150+ payment methods and currencies) and its powerful API. In Odoo, this module connects the Adyen API with the payment transaction model, supporting card payments, manual capture flows, partial refunds, tokenization for recurring payments, and webhook-driven state synchronization.

Adyen differs from simpler providers like PayPal in that it requires more configuration (merchant account, API key, client key, HMAC key, URL prefix) and supports a richer event model. Odoo's Adyen integration uses Adyen's Checkout API v70 for payment creation and webhooks for asynchronous state updates.

## Dependencies

```
payment
```

The module extends `payment.provider` and `payment.transaction` from the base `payment` module. No additional dependencies.

## Module Structure

```
payment_adyen/
├── models/
│   ├── payment_provider.py      # Provider configuration, Adyen API setup
│   └── payment_transaction.py    # Transaction lifecycle, webhook processing
├── controllers/
│   └── main.py                  # AdyenController (webhook endpoint)
├── data/
│   └── neutralization.py        # Credential neutralization
├── static/
│   └── src/xml/
│       └── payment_form.xml      # Adyen inline form JS component
└── __manifest__.py
```

## Installation

The module is auto-installed as part of `payment` or can be installed independently. After installation:

1. Go to **Invoicing / Accounting > Configuration > Payment Providers**
2. Select Adyen and enter credentials:
   - **Adyen Merchant Account**: Your Adyen merchant account name
   - **Adyen API Key**: From Adyen Customer Area (system parameter)
   - **Adyen Client Key**: For frontend origin verification
   - **Adyen HMAC Key**: For webhook signature verification
   - **Adyen API URL Prefix**: From Adyen API Credentials page (e.g., `abcdef1234`)
3. Set the provider to "Enabled" and choose "Test" or "Production" environment
4. Save and verify the webhook is accessible at `/payment/adyen/webhook`

## Data Flow

### Payment Flow (Redirect or Inline)

```
Customer Checkout
      │
      ▼
Odoo (create transaction)
      │
      ▼
POST /v70/checkout (Adyen Checkout API)
      │
      ├──► Adyen returns payment data (encrypted, via frontend SDK)
      │         │
      │         ▼
      │    Adyen.js processes card / wallet
      │         │
      │         ▼
      │    POST /payments/details with decrypted payload
      │         │
      │         ▼
      │    Adyen returns resultCode (Authorised, Refused, Pending, etc.)
      │
      ▼
Odoo receives resultCode
      │
      ├──► resultCode = "Authorised" (no manual capture):
      │         └── tx.state = 'done'
      │
      ├──► resultCode = "Authorised" (manual capture enabled):
      │         └── tx.state = 'authorized'
      │              │
      │              ▼
      │         Manual Capture Button triggers _send_capture_request()
      │              │
      │              ▼
      │         tx.state = 'done'
      │
      └──► resultCode in error/refused states:
               └── tx.state = 'error'
```

### Manual Capture Flow

```
Authorized (state='authorized')
      │
      ▼
User clicks "Capture" button on tx
      │
      ▼
_send_capture_request()
  POST /payments/{pspReference}/captures
  Body: {"merchantAccount": ..., "amount": ..., "reference": ...}
      │
      ├──► HTTP 200: capture successful
      │         └── tx.state = 'done'
      │
      └──► Adyen sends CAPTURE webhook event
               └── _apply_updates() sets state = 'done'
```

### Refund Flow

```
Done transaction (state='done')
      │
      ▼
User clicks "Refund" button
      │
      ▼
_send_refund_request()
  POST /payments/{pspReference}/refunds
  Body: {"merchantAccount": ..., "amount": ..., "reference": ...}
      │
      ├──► HTTP 200: refund accepted
      │         └── tx.operation = 'refund', state unchanged
      │
      └──► Adyen sends REFUND webhook
               └── tx.state updated (refund confirmed)
```

### Webhook Flow

```
Adyen platform event
      │
      ▼
POST /payment/adyen/webhook (AdyenController)
      │
      ▼
_verify_webhook_signature()
  - Extracts "hmacSignature" from notification
  - Decodes HMAC key (base64)
  - Computes HMAC-SHA256(notificationItem, hmac_key)
  - Compares with provided signature
      │
      ├──► Signature invalid:
      │         HTTP 403 Forbidden
      │
      └──► Signature valid:
               ▼
          _verify_and_process_notification()
            - For AUTHORISATION: _apply_updates() -> state mapping
            - For CAPTURE/CAPTURE_FAILED: updates capture state
            - For CANCELLATION: sets state to 'canceled'
            - For REFUND: updates refund status
            - For REPORT_AVAILABLE: ignored (logging only)
               │
               ▼
          Returns "[accepted]" to Adyen (required for webhook stability)
```

## Key Models

### payment.provider (Inherited)

**File:** `models/payment_provider.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `code` | Selection | Adds `adyen` option to provider code selection |
| `adyen_merchant_account` | Char | Your Adyen merchant account name |
| `adyen_api_key` | Char | Adyen API key from Customer Area (hidden, system group) |
| `adyen_client_key` | Char | Client key for Adyen.js origin verification |
| `adyen_hmac_key` | Char | Webhook HMAC key for signature verification (hidden) |
| `adyen_api_url_prefix` | Char | API URL prefix from Adyen API Credentials page |

#### Feature Support

| Feature | Support | Notes |
|---------|---------|-------|
| Manual capture | `partial` | Can capture full or partial amount |
| Refund | `partial` | Supports partial refunds |
| Tokenization | `True` | Supports saving tokens for recurring |
| Express Checkout | `False` | Not supported via Adyen module |
| Refund | `partial` | Partial refunds supported |

#### Key Methods

##### `_adyen_get_inline_form_values()`

Returns the JSON configuration needed to render the Adyen inline payment form on the checkout page.

```python
def _adyen_get_inline_form_values(self):
    self.ensure_one()
    return {
        'displayed_handlers': ['card'],  # card is the primary handler
        'partner_id': self.env.user.partner_id.id,
        'access_token': self._get_access_token(),
        'amount': {
            'amount': ...,
            'currency': ...,
        },
        'client_key': self.adyen_client_key,
        'environment': self.state,  # 'test' or 'enabled' (production)
        'merchant_account': self.adyen_merchant_account,
        'payment_methods': self._adyen_get_payment_methods_list(),  # fetches from Adyen
    }
```

Called by the frontend JS component to initialize the Adyen Web Components SDK.

##### `_adyen_get_formatted_amount()`

Formats the amount in Adyen's required integer format (minor units, e.g., EUR 19.99 becomes `1999`).

```python
def _adyen_get_formatted_amount(self, amount, currency):
    # Adyen uses minor units (cents), no decimal places
    return {
        'value': int(amount * (10 ** currency.decimal_places)),
        'currency': currency.name,
    }
```

##### `_adyen_compute_shopper_reference()`

Computes a unique shopper reference for Adyen. This is the partner (customer) ID in Odoo, used for recurring/tokenization.

```python
def _adyen_compute_shopper_reference(self, partner):
    return f"ODOO_{partner.id}"
```

##### `_build_request_url(endpoint)`

Builds the full Adyen API URL for a given endpoint.

```python
def _build_request_url(self, endpoint):
    return f"https://{self.adyen_api_url_prefix}-checkout-live.adyenpayments.com/checkout/v{ADYEN_API_VERSION}/{endpoint}"
    # Test mode: https://{prefix}-checkout-test.adyenpayments.com/checkout/v{version}/{endpoint}
```

The `adyen_api_url_prefix` contains the unique prefix assigned to your Adyen account. Test mode uses `-test.adyen` suffix; production uses `-checkout-live.adyenpayments.com`.

##### `_build_request_headers(tx=None)`

Builds HTTP headers for Adyen API requests.

```python
def _build_request_headers(self, tx=None):
    headers = {
        'X-API-Key': self.adyen_api_key,
        'Content-Type': 'application/json',
    }
    if tx:
        headers['Idempotency-Key'] = tx._get_idempotency_key()
    return headers
```

`X-API-Key` is the primary authentication mechanism. The idempotency key prevents duplicate charges on retry.

### payment.transaction (Inherited)

**File:** `models/payment_transaction.py`

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `tokenize` | Boolean | Whether to create a payment token during this transaction |
| `adyen_psp_reference` | Char | Adyen's primary key for the payment (PSP reference) |
| `adyen_merchant_reference` | Char | Your order reference passed to Adyen |
| `source_transaction_id` | Many2one | For refunds: the original transaction |

#### Key Methods

##### `_get_specific_processing_values()`

Called before payment processing starts. Returns Adyen-specific values:

```python
def _get_specific_processing_values(self, processing_values):
    res = super()._get_specific_processing_values(processing_values)
    converted_amount = self.provider_id._adyen_get_formatted_amount(
        self.amount, self.currency_id
    )
    access_token = self._get_access_token()
    return {
        **res,
        'converted_amount': converted_amount,
        'access_token': access_token,
        'adyen_merchant_reference': self.reference,
    }
```

This method adds the formatted amount (in Adyen's minor units format) and an access token for the frontend SDK.

##### `_send_payment_request()`

Sends the initial payment request to Adyen. Called when the customer submits the payment form.

```python
def _send_payment_request(self):
    # Build the Adyen payment payload
    payload = self._adyen_prepare_payment_request_payload()
    
    # Send to Adyen Checkout API
    response = self.provider_id._adyen_make_request(
        url_subdir='/payments',
        payload=payload,
        method='POST',
    )
    
    # Parse the response
    result_code = response.get('resultCode')
    psp_reference = response.get('pspReference')
    
    self.adyen_psp_reference = psp_reference
    
    # Update state based on resultCode
    self._apply_updates(result_code, response)
```

**Payment Payload Structure:**

```python
{
    'amount': {'value': 1999, 'currency': 'EUR'},  # Minor units
    'reference': 'S00001-001',
    'merchantAccount': 'YourMerchantAccount',
    'shopperEmail': 'customer@example.com',
    'shopperReference': 'ODOO_5',
    'returnUrl': 'https://your-odoo.com/payment/adyen/return',
    'countryCode': 'NL',
    'channel': 'Web',
    # For tokenization:
    'storePaymentMethod': True,
    'recurringProcessingModel': 'CardOnFile',
}
```

##### `_send_capture_request()`

Captures an authorized payment (for manual capture mode). Adyen supports partial capture.

```python
def _send_capture_request(self, amount_to_capture=None):
    amount = amount_to_capture or self.amount
    formatted_amount = self.provider_id._adyen_get_formatted_amount(
        amount, self.currency_id
    )
    payload = {
        'amount': formatted_amount,
        'merchantAccount': self.provider_id.adyen_merchant_account,
        'reference': self.reference,
    }
    
    response = self.provider_id._adyen_make_request(
        url_subdir=f'/payments/{self.adyen_psp_reference}/captures',
        payload=payload,
        method='POST',
    )
    
    # response['response'] = '[capture-received]'
    # Adyen sends CAPTURE webhook for final state
```

**Key difference from Stripe:** Adyen captures are asynchronous — the API returns `[capture-received]` immediately, and the final state comes through the webhook.

##### `_send_void_request()`

Voids/cancels an authorized payment before capture.

```python
def _send_void_request(self):
    payload = {
        'merchantAccount': self.provider_id.adyen_merchant_account,
        'reference': self.reference,
    }
    
    response = self.provider_id._adyen_make_request(
        url_subdir=f'/payments/{self.adyen_psp_reference}/cancels',
        payload=payload,
        method='POST',
    )
```

##### `_send_refund_request()`

Issues a full or partial refund.

```python
def _send_refund_request(self, amount_to_refund=None):
    amount = amount_to_refund or self.amount
    formatted_amount = self.provider_id._adyen_get_formatted_amount(
        amount, self.currency_id
    )
    payload = {
        'amount': formatted_amount,
        'merchantAccount': self.provider_id.adyen_merchant_account,
        'reference': f"REFUND-{self.reference}",
    }
    
    response = self.provider_id._adyen_make_request(
        url_subdir=f'/payments/{self.adyen_psp_reference}/refunds',
        payload=payload,
        method='POST',
    )
```

Adyen supports partial refunds — call multiple times with partial amounts until fully refunded. Each refund is tracked independently by Adyen's `refundReference`.

##### `_search_by_reference()`

Finds transactions by reference, used during webhook processing to route events to the correct transaction.

```python
def _search_by_reference(self, reference):
    return self.search([
        '|',
            ('reference', '=', reference),
            ('adyen_merchant_reference', '=', reference),
        ('provider_code', '=', 'adyen'),
    ])
```

##### `_apply_updates(response_values)`

Maps Adyen event data to Odoo transaction state.

```python
def _apply_updates(self, event_code, response_values):
    # event_code: AUTHORISATION, CAPTURE, CANCELLATION, REFUND
    # response_values: full webhook notification item
    
    result_code = response_values.get('resultCode')  # Authorised, Refused, Pending, etc.
    
    if result_code in self._get_result_code_state('pending'):
        self._set_pending()
    elif result_code == 'Authorised' and not self.provider_id.capture_manually:
        self._set_done()
    elif result_code == 'Authorised' and self.provider_id.capture_manually:
        self._set_authorized()
    elif result_code in self._get_result_code_state('cancel'):
        self._set_canceled()
    elif result_code in self._get_result_code_state('error'):
        self._set_error()
```

#### State Mapping

| Adyen `resultCode` | Adyen `success` | Odoo State | Notes |
|-------------------|-----------------|------------|-------|
| `Pending` | `"false"` | `pending` | |
| `PresentToShopper` | `"false"` | `pending` | Invoice presentment |
| `Received` | `"false"` | `pending` | |
| `Authorised` | `"true"` | `done` or `authorized` | Depends on capture_manually |
| `Authorised` + CAPTURE event | `"true"` | `done` | Manual capture complete |
| `Refused` | `"false"` | `error` | |
| `Error` | `"false"` | `error` | |
| Cancelled | `"false"` | `canceled` | |
| `RedirectShopper` | `"false"` | `pending` | 3DS or redirect flow |

#### Webhook Events Handled

| Adyen Event | Handler | Action |
|-------------|---------|--------|
| `AUTHORISATION` | `_apply_updates` | Sets state based on resultCode + success |
| `CAPTURE` | `_apply_updates` | Sets state to `done` (manual capture complete) |
| `CAPTURE_FAILED` | `_apply_updates` | Sets state to `error` |
| `CANCELLATION` | `_apply_updates` | Sets state to `canceled` |
| `REFUND` | `_apply_updates` | Confirms refund (operation='refund') |
| `REFUND_FAILED` | `_apply_updates` | Reverts refund state |
| `REPORT_AVAILABLE` | (ignored) | Logged only, no state change |

## Architecture Notes

### API Versioning

The module uses **Adyen Checkout API v70**. The version number appears in the URL path (`/checkout/v70/`). When Adyen releases a new API version, the module needs to be updated accordingly.

### Test vs Production URL

Adyen uses different base URLs for test and production:

```
Test:     https://{prefix}-checkout-test.adyenpayments.com/checkout/v{version}/
Production: https://{prefix}-checkout-live.adyenpayments.com/checkout/v{version}/
```

The `adyen_api_url_prefix` is a unique string assigned to each Adyen merchant account and determines which endpoints are accessible.

### Webhook Security

Adyen webhooks carry sensitive payment data and must be verified:

1. **Signature verification**: Adyen sends `additionalData.hmacSignature` in each notification item. This is a base64-encoded HMAC-SHA256 signature computed over the notification item's fields.
2. **HMAC key storage**: The `adyen_hmac_key` is stored as a masked field (system parameter). It should be configured by an administrator with access to the system parameter group.
3. **Response requirement**: Adyen requires a `[accepted]` response to each notification. If the webhook returns anything else, Adyen retries for up to 5 days.
4. **Idempotency**: The webhook should handle duplicate events gracefully. The `_apply_updates` method checks if the state is already set to avoid duplicate processing.

### PCI Compliance

Unlike Stripe where the frontend SDK tokenizes card data client-side, Adyen's approach involves:
- **Client-side**: Adyen Web Components (hosted JS SDK) collects and encrypts card data
- **Server-side**: Odoo receives the encrypted payload and forwards it to Adyen via the Checkout API
- **No card data stored in Odoo**: All card data flows directly between the browser and Adyen; Odoo only stores the PSP reference and token

### Manual Capture Flow

Adyen's default is "immediate capture" (payment is captured at authorization). When `capture_manually = True` is set on the provider:

1. Payment is **authorized** but not captured (funds are held on the card)
2. The transaction enters `authorized` state in Odoo
3. The user manually clicks "Capture" in Odoo
4. Odoo sends a capture request to Adyen
5. Adyen sends a `CAPTURE` webhook confirming the capture
6. Transaction moves to `done`

This is the recommended flow for high-value orders where fraud review is needed before capturing funds.

### Tokenization / Recurring Payments

When `tokenize=True` in the transaction:

```python
# In _send_payment_request:
payload['storePaymentMethod'] = True
payload['recurringProcessingModel'] = 'CardOnFile'  # or 'Subscription'
```

Adyen returns a `recurringDetailReference` (stored token) which can be used for subsequent charges without the card being present. In Odoo, this creates a `payment.token` record linked to the partner.

### Error Handling

Adyen error responses follow this structure:

```python
{
    "status": 422,
    "errorCode": "175",
    "message": "Invalid card number",
    "errorType": "configuration"
}
```

The `_adyen_parse_response_error` method extracts `errorCode` and `message` for user display. Common error codes:

| Error Code | Meaning | Odoo State |
|-----------|---------|------------|
| `010` | Invalid card number | error |
| `175` | Invalid card expiry date | error |
| `176` | Expired card | error |
| `Not allowed` | Card type not enabled | error |
| `Refused` | Generic refusal | error |

### Idempotency

All POST requests to Adyen include an `Idempotency-Key` header:

```python
headers['Idempotency-Key'] = payment_utils.generate_idempotency_key(
    self, scope='payment_request'
)
```

This ensures that if a request is accidentally retried (e.g., network timeout), Adyen does not duplicate the charge. The key is transaction-scoped.

## Configuration

### Adyen Customer Area Setup

1. **Create an API credential set** (Customer Area > Developers > API credentials)
2. **Create a web service user** for server-side API access
3. **Set the API key** for `payment_adyen` (copy to Odoo)
4. **Create a Client Key** for the frontend (copy to Odoo)
5. **Set up the HMAC key** for webhook verification (copy to Odoo)
6. **Copy the API URL Prefix** from the credentials page

### Webhook Configuration in Adyen

1. Go to **Customer Area > Developers > Webhooks**
2. Create a **Standard Notification** webhook
3. Set the URL to: `https://your-odoo-domain.com/payment/adyen/webhook`
4. Enable **HMAC** as the security method
5. Copy the HMAC key to Odoo's `adyen_hmac_key` field
6. Set the **Additional Data** settings to include `hmacSignature`

### Currency Support

Adyen Checkout API supports many currencies. Not all currencies are enabled by default. Check Adyen's documentation for your merchant account's supported currencies and ensure the relevant ones are enabled in Adyen's Customer Area.

## Security Analysis

### Credential Storage

| Field | Storage | Access |
|-------|---------|--------|
| `adyen_api_key` | Ir.config_parameter (system) | System parameter group only |
| `adyen_hmac_key` | Ir.config_parameter (system) | System parameter group only |
| `adyen_client_key` | Plain in `payment.provider` | Admin only |
| `adyen_merchant_account` | Plain in `payment.provider` | Admin only |
| `adyen_api_url_prefix` | Plain in `payment.provider` | Admin only |

The API key and HMAC key are stored as system parameters with `group: base.group_system`, meaning only administrators can view or modify them.

### Webhook Signature Verification

```python
# Simplified signature check
signature_data = "|".join([
    notification.get('pspReference', ''),
    notification.get('originalReference', ''),
    notification.get('merchantAccountCode', ''),
    notification.get('merchantReference', ''),
    notification.get('amount_value', ''),
    notification.get('amount_currency', ''),
    notification.get('eventCode', ''),
    notification.get('success', ''),
])

computed_sig = hmac.new(
    hmac_key_bytes,
    signature_data.encode(),
    hashlib.sha256
).digest()

if not hmac.compare_digest(base64.b64decode(received_sig), computed_sig):
    return False  # Reject webhook
```

### Best Practices

1. **Never log full API responses** — payment data can contain sensitive card details
2. **Use HTTPS everywhere** — the webhook endpoint must be HTTPS for Adyen to accept it
3. **Handle duplicates gracefully** — same webhook may be delivered multiple times
4. **Set webhook retry budget** — Adyen retries failed webhooks for up to 5 days

## Testing

### Test Card Numbers

Use Adyen's public test card numbers:

| Card Type | Number | Expiry | CVV | Result |
|-----------|--------|--------|-----|--------|
| Visa | `4111111111111111` | Any future | `737` | Authorised |
| Mastercard | `5500000000000004` | Any future | `737` | Authorised |
| Visa (refuse) | `4000000000000002` | Any future | `737` | Refused |
| Visa (3DS) | `4000000000000002` | Any future | `737` | 3DS redirect |

### Test Webhooks

Use Adyen's webhook testing tool (Customer Area > Developers > Webhooks > Test) to simulate events. Send test notifications to your `/payment/adyen/webhook` endpoint to verify signature verification and state updates.

## Related

- [Modules/payment](Modules/payment.md) — Base payment engine
- [Modules/payment_stripe](Modules/payment_stripe.md) — Stripe provider comparison
- [Modules/payment_paypal](Modules/payment_paypal.md) — PayPal provider comparison
- [Modules/payment_mollie](Modules/payment_mollie.md) — Mollie provider comparison
