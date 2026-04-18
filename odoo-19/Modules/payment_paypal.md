---
type: module
module: payment_paypal
tags: [odoo, odoo19, payment, paypal]
uuid: 6a2c3d4e-5f6b-7c8d-9e0f-1a2b3c4d5e6f
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
| **Module** | `payment_paypal` |

## Description

An American payment provider for online payments worldwide. PayPal is one of the most recognizable payment brands, offering buyer protection and a familiar checkout experience. In Odoo, this module uses the **PayPal Checkout API v2** (Orders API) to process payments. Unlike Stripe or Adyen which use server-side tokenization, PayPal uses a redirect-based flow where the customer is redirected to PayPal's hosted page to approve the payment, then returned to Odoo.

The PayPal provider supports payment confirmation via webhook/IPN (Instant Payment Notification) and also handles the redirect return URL for confirmation. It does not support manual capture, express checkout, or tokenization natively — those would require additional configuration or modules.

## Dependencies

```
payment
```

## Module Structure

```
payment_paypal/
├── models/
│   ├── payment_provider.py      # Provider config, PayPal API setup
│   └── payment_transaction.py    # Order creation, webhook/IPN processing
├── controllers/
│   └── main.py                  # PayPalController (return URL, webhook)
├── data/
│   └── neutralization.py        # Credential neutralization
└── __manifest__.py
```

## Installation

1. Go to **Invoicing / Accounting > Configuration > Payment Providers**
2. Select PayPal and enter:
   - **PayPal Email Account**: The primary PayPal email for receiving payments
   - **PayPal Merchant ID**: From PayPal Developer Dashboard
   - **PayPal Client ID**: For PayPal JavaScript SDK
   - **PayPal Secret Key**: For server-side API calls (hidden)
3. Configure the webhook endpoint in PayPal Developer Dashboard:
   - URL: `https://your-odoo-domain.com/payment/paypal/webhook`
   - Events: `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.REFUNDED`, `CHECKOUT.ORDER.APPROVED`
4. Set the provider to "Enabled"

## Data Flow

### Payment Flow (Redirect)

```
Customer Checkout (state='draft')
      │
      ▼
Odoo: payment_transaction._get_specific_processing_values()
      │
      ▼
Server creates PayPal Order via POST /v2/checkout/orders
  Headers: Authorization: Bearer <access_token>
  Idempotency-Key: <tx.reference>
  Body: {
    intent: 'CAPTURE',           # or 'AUTHORIZE' for auth-only
    purchase_units: [{
      reference_id: '<tx.reference>',
      description: '<company>: <reference>',
      amount: { currency_code: 'EUR', value: '19.99' },
      payee: { email_address: '<paypal_email_account>' },
      ...shipping_address
    }],
    payment_source: { paypal: { experience_context: {...} }}
  }
      │
      ▼
PayPal returns order ID (e.g., 7X835832KY1234567)
      │
      ▼
Odoo stores paypal_order_id on transaction
      │
      ▼
Browser redirects customer to PayPal approval URL
  URL: https://www.paypal.com/checkoutnow?token=<order_id>
      │
      ▼
Customer logs into PayPal and approves payment
      │
      ▼
Browser redirects back to:
  /payment/paypal/return?PayerID=XYZ&token=<order_id>
      │
      ▼
PayPalController._return_url()
  - Extracts order_id and PayerID
  - _send_capture_request() or _capture_order()
    POST /v2/checkout/orders/<id>/confirm-capture
    Body: { payer_id: PayerID }
      │
      ├──► Capture succeeded (status=COMPLETED):
      │         └── tx.state = 'done'
      │
      └──► Capture failed:
               └── tx.state = 'error'

  OR: Webhook fires PAYMENT.CAPTURE.COMPLETED
          └── tx.state = 'done'
```

### Webhook/IPN Flow

```
PayPal event fires
      │
      ▼
POST /payment/paypal/webhook
  Headers: PAYPAL-TRANSMISSION-ID, PAYPAL-TRANSMISSION-TIME,
           PAYPAL-TRANSMISSION-SIG, PAYPAL-CERT-URL,
           PAYPAL-AUTH-ALGO
      │
      ▼
PayPalController._verify_webhook_signature()
  - Fetches PayPal certificate from PAYPAL-CERT-URL
  - Verifies signature against payload
      │
      ├──► Invalid signature:
      │         HTTP 403 Forbidden
      │
      └──► Valid:
               ▼
          _process_webhook()
            - PAYMENT.CAPTURE.COMPLETED: _apply_updates() -> 'done'
            - PAYMENT.CAPTURE.REFUNDED: _apply_updates() -> 'done' + operation='refund'
            - CHECKOUT.ORDER.APPROVED: ignored (handled by return URL)
            - PAYMENT.CAPTURE.DENIED: _apply_updates() -> 'error'
            - PAYMENT.CAPTURE.DECLINED: _apply_updates() -> 'error'
               │
               ▼
          HTTP 200
```

### Idempotency Pattern

```
Customer clicks "Pay" (creates order)
      │
      ▼
Network error - no response received
      │
      ▼
Customer clicks "Pay" again
      │
      ▼
Same idempotency key sent
      │
      ▼
PayPal returns cached response (no duplicate order created)
      │
      ▼
Odoo proceeds normally
```

## Key Models

### payment.provider (Inherited)

**File:** `models/payment_provider.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `paypal_email_account` | Char | Primary PayPal email for receiving payments |
| `paypal_merchant_id` | Char | PayPal Merchant ID from developer dashboard |
| `paypal_client_id` | Char | Client ID for PayPal JS SDK |
| `paypal_secret_key` | Char | Secret key for API calls (hidden) |
| `paypal_pending_timeout` | Integer | Hours before pending PayPal orders are canceled |

#### Key Methods

##### `_paypal_make_request(endpoint, payload=None, method='POST')`

Makes an authenticated request to PayPal API.

```python
def _paypal_make_request(self, endpoint, payload=None, method='POST'):
    url = f'https://api-m.paypal.com{endpoint}'
    
    # Get access token
    access_token = self._paypal_get_access_token()
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'PayPal-Request-Id': payment_utils.generate_idempotency_key(
            self, scope='payment_request_order'
        ),
    }
    
    if method == 'GET':
        response = requests.get(url, headers=headers, timeout=10)
    else:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
    
    response.raise_for_status()
    return response.json()
```

##### `_paypal_get_access_token()`

Fetches or caches an OAuth2 access token from PayPal.

```python
def _paypal_get_access_token(self):
    # Token is cached in ir.config_parameter
    cached = self.env['ir.config_parameter'].get_param(
        'payment_paypal.access_token'
    )
    expiry = self.env['ir.config_parameter'].get_param(
        'payment_paypal.access_token_expiry'
    )
    
    if cached and expiry and datetime.now() < datetime.fromisoformat(expiry):
        return cached
    
    # Fetch new token
    url = 'https://api-m.paypal.com/v1/oauth2/token'
    response = requests.post(
        url,
        data={'grant_type': 'client_credentials'},
        auth=(self.paypal_client_id, self.paypal_secret_key),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
    )
    
    token_data = response.json()
    access_token = token_data['access_token']
    
    # Cache token with expiry
    self.env['ir.config_parameter'].set_param(
        'payment_paypal.access_token', access_token
    )
    self.env['ir.config_parameter'].set_param(
        'payment_paypal.access_token_expiry',
        (datetime.now() + timedelta(seconds=token_data['expires_in'] - 60)).isoformat()
    )
    
    return access_token
```

### payment.transaction (Inherited)

**File:** `models/payment_transaction.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `paypal_order_id` | Char | PayPal order ID (from v2/checkout/orders) |
| `paypal_payer_id` | Char | PayPal account ID of the payer |
| `paypal_type` | Char | Transaction type for IPN debugging |

#### Key Methods

##### `_get_specific_processing_values(processing_values)`

Returns PayPal-specific values for the checkout form.

```python
def _get_specific_processing_values(self, processing_values):
    res = super()._get_specific_processing_values(processing_values)
    
    # Create PayPal order
    order_payload = self._paypal_prepare_order_payload()
    order_response = self.provider_id._paypal_make_request(
        '/v2/checkout/orders',
        order_payload,
    )
    
    self.paypal_order_id = order_response['id']
    self.paypal_type = 'paypal'
    
    # Get the approval URL
    approve_url = next(
        link['href'] for link in order_response['links']
        if link['rel'] == 'approve'
    )
    
    return {
        **res,
        'paypal_order_id': order_response['id'],
        'paypal_approve_url': approve_url,
    }
```

##### `_paypal_prepare_order_payload()`

Builds the PayPal Checkout v2 order payload.

```python
def _paypal_prepare_order_payload(self):
    company = self.env.company
    partner = self.partner_id
    
    # Shipping address
    shipping_address_vals = {}
    if partner.street and partner.city:
        shipping_address_vals = {
            'shipping_preference': 'SET_PROVIDED_ADDRESS',
            'purchase_units': [{
                'shipping': {
                    'address': {
                        'address_line_1': partner.street,
                        'address_line_2': partner.street2 or '',
                        'admin_area_2': partner.city,
                        'admin_area_1': partner.state_id.code or '',
                        'postal_code': partner.zip or '',
                        'country_code': partner.country_id.code or '',
                    },
                    'name': {'full_name': partner.name},
                },
            }],
        }
    else:
        shipping_address_vals = {'shipping_preference': 'NO_SHIPPING'}
    
    # Invoice address
    invoice_address_vals = {}
    if partner:
        invoice_address_vals = {
            'name': {'given_name': partner.name.split()[0] if partner.name else ''},
            'surname': ' '.join(partner.name.split()[1:]) if partner.name else '',
            'email_address': partner.email or '',
        }
    
    return {
        'intent': 'CAPTURE',  # Funds captured immediately
        'purchase_units': [{
            'reference_id': self.reference,
            'description': f'{company.name}: {self.reference}',
            'amount': {
                'currency_code': self.currency_id.name,
                'value': str(self.amount),  # PayPal accepts string amounts
            },
            'payee': {
                'email_address': self.provider_id.paypal_email_account,
            },
            **shipping_address_vals.get('purchase_units', [{}])[0],
        }],
        'payment_source': {
            'paypal': {
                'experience_context': {
                    'payment_method_preference': 'IMMEDIATE_PAYMENT_REQUIRED',
                    'brand_name': company.name,
                    'landing_page': 'LOGIN',  # or 'BILLING', 'NO_PREFERENCE'
                    'user_action': 'PAY_NOW',  # or 'CONTINUE'
                    'return_url': self.provider_id.get_base_url() + '/payment/paypal/return',
                    'cancel_url': self.provider_id.get_base_url() + '/payment/paypal/cancel',
                    'shipping_preference': shipping_address_vals.get('shipping_preference', 'NO_SHIPPING'),
                },
                **invoice_address_vals,
            }
        },
    }
```

**Payload Structure Diagram:**

```
POST /v2/checkout/orders
{
  intent: "CAPTURE",
  purchase_units: [{
    reference_id: "S00001-001",
    description: "MyCompany: S00001-001",
    amount: {
      currency_code: "EUR",
      value: "19.99"
    },
    payee: {
      email_address: "merchant@paypal.com"
    },
    shipping: { ... }   // if address provided
  }],
  payment_source: {
    paypal: {
      experience_context: {
        shipping_preference: "SET_PROVIDED_ADDRESS",
        return_url: "https://...",
        cancel_url: "https://...",
        ...
      },
      name: { given_name: "John", surname: "Doe" },
      email_address: "customer@paypal.com"
    }
  }
}
```

##### `_send_capture_request()`

Captures the PayPal order after customer approval. Called when the customer returns from PayPal.

```python
def _send_capture_request(self):
    payload = {
        'payer_id': self.paypal_payer_id,
    }
    
    response = self.provider_id._paypal_make_request(
        f'/v2/checkout/orders/{self.paypal_order_id}/capture',
        payload,
    )
    
    # Status can be: COMPLETED, DECLINED, REFUSED, etc.
    status = response.get('status')
    
    self._apply_updates(status, response)
```

The `payer_id` is extracted from the return URL (`?PayerID=XYZ`) — it is the PayPal account ID of the customer who approved the payment.

##### `_apply_updates(status, response_data)`

Maps PayPal payment status to Odoo transaction state.

```python
def _apply_updates(self, status, response_data):
    """Map PayPal status to Odoo state."""
    
    # Extract captures from response
    captures = response_data.get('purchase_units', [{}])[0].get('payments', {}).get('captures', [])
    
    if not captures:
        # No captures yet - check for pending
        if status in ('PENDING', 'CREATED', 'SAVED', 'APPROVED'):
            self._set_pending()
        elif status in ('VOIDED', 'COMPLETED'):
            self._set_error("Payment voided or already completed")
        return
    
    capture = captures[0]
    capture_status = capture.get('status')
    
    if capture_status == 'COMPLETED':
        self._set_done()
    elif capture_status in ('PENDING', 'ON_HOLD'):
        self._set_pending()
    elif capture_status in ('DECLINED', 'REFUNDED', 'CANCELLED'):
        self._set_error(f"Payment {capture_status.lower()}")
    else:
        self._set_error(f"Unknown capture status: {capture_status}")
```

##### `_extract_reference()`

Extracts the Odoo transaction reference from the PayPal order.

```python
def _extract_reference(self, response_data):
    purchase_units = response_data.get('purchase_units', [])
    if purchase_units:
        reference_id = purchase_units[0].get('reference_id', '')
        # reference_id is set to self.reference in payload
        if reference_id and reference_id != 'DEFAULT':
            return reference_id
    return None
```

##### `_extract_amount_data()`

Extracts amount and currency from the PayPal response.

```python
def _extract_amount_data(self, response_data):
    purchase_units = response_data.get('purchase_units', [])
    if purchase_units:
        amount_data = purchase_units[0].get('amount', {})
        return {
            'amount': Decimal(amount_data.get('value', '0')),
            'currency': amount_data.get('currency_code', ''),
        }
    return {'amount': Decimal('0'), 'currency': ''}
```

#### Payment Status Mapping

| PayPal Order Status | Capture Status | Odoo State | Notes |
|--------------------|----------------|-------------|-------|
| `PENDING` | - | `pending` | Buyer hasn't completed payment |
| `APPROVED` | - | `pending` | Approved but not captured |
| `CREATED` | - | `pending` | Order created, not yet approved |
| `COMPLETED` | `COMPLETED` | `done` | Payment captured successfully |
| `COMPLETED` | `PENDING` | `pending` | Capture pending (e.g., fraud review) |
| `DECLINED` | `DECLINED` | `error` | Payment declined |
| `VOIDED` | - | `canceled` | Order voided |

#### Refund Status Mapping

| PayPal Capture Status | Odoo State |
|----------------------|------------|
| `REFUNDED` | `done` (operation=`refund`) |
| `PARTIALLY_REFUNDED` | `done` (operation=`refund`) |
| `PENDING` (refund) | `pending` |

## Architecture Notes

### PayPal Checkout API (v2 Orders)

The module uses PayPal's modern Checkout API (not the legacy Express Checkout API). Key characteristics:

- **Orders vs Payments**: The API works with "orders" first, which are then captured to initiate the actual money movement
- **`intent: 'CAPTURE'`**: The payment is captured immediately after approval (simplest flow)
- **`intent: 'AUTHORIZE'`**: Creates a payment authorization that must be captured separately later (like manual capture in Stripe)
- **Idempotency**: Orders are idempotent when the same `PayPal-Request-Id` header is sent

### Redirect Flow

Unlike Stripe's inline form (Stripe.js) or Adyen's embedded components, PayPal's classic flow redirects the customer to PayPal's hosted page:

```
1. Customer clicks "Pay with PayPal"
2. Odoo creates an order and gets the approval URL
3. Browser redirects to PayPal (new tab or same tab depending on config)
4. Customer logs in and approves on PayPal
5. PayPal redirects back to Odoo's /payment/paypal/return
6. Odoo captures the order and shows the confirmation
```

This is a **redirect-based** flow, which means:
- The customer leaves the Odoo website briefly
- Session state must be maintained across the redirect
- The return URL must be accessible and properly signed

### Webhook vs Return URL

The module uses **both** webhook and return URL for payment confirmation:

1. **Return URL** (`/payment/paypal/return`): The primary path. When PayPal redirects the customer back, Odoo immediately captures the order and updates the transaction state.
2. **Webhook** (`/payment/paypal/webhook`): A fallback and confirmation path. PayPal also sends a webhook event for the same payment. This ensures state consistency if the customer closes the browser after PayPal approval.

Both paths call `_apply_updates()` which is idempotent (re-calling on an already-done transaction is safe).

### Webhook Security

PayPal webhooks use RSA signature verification (not HMAC). The flow:

1. PayPal sends headers: `PAYPAL-TRANSMISSION-ID`, `PAYPAL-TRANSMISSION-TIME`, `PAYPAL-TRANSMISSION-SIG`, `PAYPAL-CERT-URL`, `PAYPAL-AUTH-ALGO`
2. Odoo fetches the certificate from `PAYPAL-CERT-URL` (must be from `api.paypal.com`)
3. Odoo verifies the signature using the certificate's public key
4. This proves the webhook came from PayPal and wasn't tampered with

```python
def _verify_webhook_signature(self, payload, headers):
    # Fetch certificate
    cert_url = headers['PAYPAL-CERT-URL']
    assert cert_url.startswith('https://api.paypal.com/')  # Security check
    
    cert = requests.get(cert_url).content
    
    # Build signed_payload string
    # "timestamp.body" where body is the raw JSON payload
    transmission_time = headers['PAYPAL-TRANSMISSION-TIME']
    signed_payload = f"{transmission_time}.{payload}"
    
    # Verify signature using certificate
    signature = base64.b64decode(headers['PAYPAL-TRANSMISSION-SIG'])
    algo = headers['PAYPAL-AUTH-ALGO']  # e.g., "SHA256withRSA"
    
    # Use crypto.verify with certificate public key
    verified = crypto.verify(cert, signature, signed_payload.encode())
```

### Idempotency Key

The `PayPal-Request-Id` header ensures request idempotency:

```python
'PayPal-Request-Id': payment_utils.generate_idempotency_key(
    self, scope='payment_request_order'
)
```

This is critical because:
- If the network fails after PayPal creates the order but before Odoo receives the response, the user might retry
- Without idempotency, PayPal would create a duplicate order
- With idempotency, PayPal returns the existing order for the same `Request-Id`

### PayPal Email Account

The `paypal_email_account` is the payee email address in the purchase unit. This determines where the payment is received. It must match the email of the PayPal account that owns the Client ID and Secret Key.

### Pending Timeout

PayPal orders can remain in `PENDING` or `APPROVED` state indefinitely if the customer doesn't complete approval. The `paypal_pending_timeout` field specifies how many hours to wait before canceling such orders.

### Error Handling

PayPal error responses follow:

```python
{
    'name': 'RESOURCE_NOT_FOUND',
    'message': 'Order XXXXX not found',
    'debug_id': 'abc123',
    'details': [...]
}
```

Common error types:
- `VALIDATION_ERROR`: Invalid request parameters
- `RESOURCE_NOT_FOUND`: Order/capture not found
- `INSTRUMENT_DECLINED`: Payment method declined
- `PAYER_CANNOT_PAY`: Payer cannot pay (e.g., insufficient balance)
- `CANNOT_CAPTURE`: Authorization expired or already captured

## Configuration

### PayPal Developer Dashboard Setup

1. **Create an app**: PayPal Developer > My Apps & Credentials > Create App
   - Choose "Checkout" as the app type
   - Copy **Client ID** and **Secret** to Odoo
2. **Get Merchant ID**: PayPal Developer > My Apps & Credentials > Dashboard
3. **Set the primary email**: In PayPal account settings, ensure the receiving email is set
4. **Configure webhook**: My Apps & Credentials > Webhooks
   - Add webhook: `https://your-odoo-domain.com/payment/paypal/webhook`
   - Subscribe to: `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.REFUNDED`, `CHECKOUT.ORDER.APPROVED`

### Return URL Configuration

PayPal redirects to these URLs (configured in the order payload):
- **Return URL**: `https://your-odoo-domain.com/payment/paypal/return`
- **Cancel URL**: `https://your-odoo-domain.com/payment/paypal/cancel`

Both must be accessible and return HTTP 200.

## Security Analysis

### Credential Storage

| Field | Storage | Access |
|-------|---------|--------|
| `paypal_client_id` | Plain in `payment.provider` | Admin only |
| `paypal_secret_key` | Ir.config_parameter (system) | System group only |

### Webhook Verification

PayPal uses **RSA signature verification** (asymmetric), unlike Stripe's HMAC (symmetric). This means:
- PayPal signs webhooks with a private key
- Odoo verifies using PayPal's public certificate
- The certificate URL must be validated to prevent DNS rebinding attacks

### Best Practices

1. **Use webhooks as source of truth**: The return URL can be blocked by browser pop-up blockers; webhooks are more reliable
2. **Verify webhook signatures**: Never trust webhook payloads without signature verification
3. **Handle idempotency**: PayPal may retry webhooks; use `PAYPAL-TRANSMISSION-ID` for deduplication
4. **Configure pending timeout**: Cancel abandoned PayPal orders to avoid stale records

## Related Modules Comparison

| Feature | Stripe | Adyen | PayPal | Mollie |
|---------|--------|-------|--------|--------|
| Manual capture | Full only | Partial | Not supported | Not supported |
| Partial refund | Yes | Yes | Yes | Yes |
| Tokenization | Yes | Yes | Limited | Limited |
| Express Checkout | Apple Pay, Google Pay | No | PayPal Button | No |
| Inline form | Stripe.js | Components | Redirect | Redirect |
| Webhook security | HMAC-SHA256 | HMAC-SHA256 | RSA | Simple header |

## Testing

### Sandbox Credentials

Use PayPal Sandbox accounts from PayPal Developer Dashboard:
- Create a Business account (receiver)
- Create Personal accounts (senders)
- Use the Business account's Client ID and Secret in test mode

### Test Card on PayPal

PayPal sandbox allows testing without real money. Use sandbox.paypal.com for the API calls.

### Test Scenarios

| Scenario | PayPal Status | Odoo State |
|----------|--------------|------------|
| Successful payment | COMPLETED | done |
| Payment pending (e.g., eCheck) | PENDING | pending |
| Payment declined by PayPal | DECLINED | error |
| Payment refused by buyer | VOIDED | canceled |
| Buyer closes PayPal window | (no return) | (stays pending, auto-canceled) |

## Related

- [Modules/payment](Modules/payment.md) — Base payment engine
- [Modules/payment_stripe](Modules/payment_stripe.md) — Stripe provider
- [Modules/payment_adyen](Modules/payment_adyen.md) — Adyen provider
- [Modules/payment_mollie](Modules/payment_mollie.md) — Mollie provider
