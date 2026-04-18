---
type: module
module: payment_stripe
tags: [odoo, odoo19, payment, stripe]
uuid: 7b3d1e2f-4c8a-5d9b-6e0f-1a2b3c4d5e6f
created: 2026-04-06
---

# Payment Provider: Stripe

## Overview

| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Stripe |
| **Technical** | `payment_stripe` |
| **Category** | Accounting/Payment Providers |
| **Version** | 2.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Module** | `payment_stripe` |

## Description

An Irish-American payment provider (HQ in Dublin, US-based) covering the US and 135+ other countries. Stripe is the most widely used payment provider in Odoo due to its developer-friendly API, excellent documentation, and comprehensive feature set. In Odoo 19, the Stripe module supports Express Checkout (Apple Pay, Google Pay), manual capture (full capture only), partial refunds, tokenization, and Stripe Connect for marketplace/sub-account flows.

Stripe handles all PCI compliance on their side — card data never touches the Odoo server. Instead, Stripe.js tokenizes card details client-side and returns a PaymentMethod ID that Odoo uses server-side. This architecture eliminates the need for PCI DSS compliance for the merchant.

## Dependencies

```
payment
```

## Module Structure

```
payment_stripe/
├── models/
│   ├── payment_provider.py      # Provider config, Stripe Connect, onboarding
│   └── payment_transaction.py    # Transaction lifecycle, webhook processing
├── controllers/
│   └── main.py                  # StripeController (webhook, return URL)
├── data/
│   └── neutralization.py        # Credential neutralization
├── static/
│   └── src/js/
│       ├── stripe_form.js        # Stripe.js initialization and form handling
│       └── express_checkout.js   # Apple Pay / Google Pay button
└── __manifest__.py
```

## Installation

The module is auto-installed with `payment`. To configure:

1. Go to **Invoicing / Accounting > Configuration > Payment Providers**
2. Select Stripe and enter credentials:
   - **Stripe Publishable Key**: From Stripe Dashboard (visible on frontend)
   - **Stripe Secret Key**: From Stripe Dashboard > Developers > API keys (hidden)
   - **Stripe Webhook Secret**: From Stripe Dashboard > Developers > Webhooks (hidden)
3. Set the state to "Enabled" (Production) or "Test" (Sandbox)
4. Optionally configure **Stripe Connect** for marketplace flows

## Data Flow

### Payment Flow (Stripe.js)

```
Customer Checkout
      │
      ▼
Odoo renders Stripe form
      │
      ▼
Browser loads Stripe.js (https://js.stripe.com/v3/)
      │
      ▼
Customer enters card details (in Stripe's iframe)
      │
      ▼
stripe.createPaymentMethod({
  type: 'card',
  card: { token },
  billing_details: { name, email, address }
})
      │
      ▼
Browser receives PaymentMethod ID (pm_xxx)
      │
      ▼
Odoo sends pm_xxx to server via /payment/stripe/payment
      │
      ▼
server: _stripe_create_payment_intent()
  POST /v1/payment_intents  (with pm_xxx)
      │
      ├──► PaymentIntent status = requires_confirmation
      │
      ▼
  POST /v1/payment_intents/{id}/confirm
      │
      ├──► status = 'succeeded' (card OK):
      │         └── tx.state = 'done'
      │
      ├──► status = 'requires_action' (3DS):
      │         └── tx.state = 'pending'
      │              │
      │              ▼
      │         Browser handles 3DS redirect
      │              │
      │              ▼
      │         POST /payment/stripe/webhook
      │              └── tx.state = 'done'
      │
      └──► status = 'requires_payment_method' (failure):
               └── tx.state = 'error'
```

### Manual Capture Flow

```
PaymentIntent created (capture_method='manual')
      │
      ├──► status = 'requires_capture':
      │         └── tx.state = 'authorized'
      │              │
      │              ▼
      │         User clicks "Capture" in Odoo
      │              │
      │              ▼
      │         _stripe_capture_payment_intent()
      │           POST /v1/payment_intents/{id}/capture
      │              │
      │              ▼
      │         status = 'succeeded':
      │              └── tx.state = 'done'
```

### Refund Flow

```
Done transaction (state='done')
      │
      ▼
User clicks "Refund"
      │
      ▼
stripe.refund({
  payment_intent: pi_xxx,
  amount: 1999  # in smallest currency unit
})
  POST /v1/refunds
      │
      ├──► Refund created (status='succeeded'):
      │         └── tx.operation = 'refund'
      │
      └──► Partial refund: call multiple times
               └── tx.operation updated per refund
```

### Webhook Flow

```
Stripe event (payment_intent.succeeded, charge.refunded, etc.)
      │
      ▼
POST /payment/stripe/webhook (StripeController)
      │
      ▼
_verify_webhook_signature()
  - Reads Stripe-Signature header
  - Verifies using stripe_webhook_secret (whsec_xxx)
  - Parses event object
      │
      ├──► Invalid signature:
      │         HTTP 403 Forbidden
      │
      └──► Valid signature:
               ▼
          _process_webhook()
            - payment_intent.succeeded: _set_done()
            - payment_intent.requires_capture: _set_authorized()
            - charge.refunded: _set_operation('refund')
            - refund.updated: update refund status
               │
               ▼
          HTTP 200 (empty body)
```

## Key Models

### payment.provider (Inherited)

**File:** `models/payment_provider.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `code` | Selection | Adds `stripe` option to provider code |
| `stripe_publishable_key` | Char | Public key for frontend (pk_test_xxx or pk_live_xxx) |
| `stripe_secret_key` | Char | Secret key for API calls (sk_test_xxx or sk_live_xxx) |
| `stripe_webhook_secret` | Char | Webhook signing secret (whsec_xxx) |
| `stripe_is_portal_payment` | Boolean | Enables Stripe Customer Portal for payment |
| `stripe_use_connected_account` | Boolean | Use Stripe Connect for connected accounts |
| `stripe_journal_id` | Many2one | Journal for Stripe Connect payouts |

#### Feature Support

| Feature | Support | Notes |
|---------|---------|-------|
| Manual capture | `full_only` | Full capture only, no partial |
| Refund | `partial` | Partial refunds supported |
| Tokenization | `True` | Payment method tokens for recurring |
| Express Checkout | `True` | Apple Pay and Google Pay |
| Stripe Connect | `True` | Marketplace sub-accounts |
| Partial capture | `False` | Only full capture supported |

#### Key Methods

##### `_compute_feature_support_fields()`

Enables express checkout, manual capture, refund, and tokenization features.

```python
def _compute_feature_support_fields(self):
    super()._compute_feature_support_fields()
    self.feature_support_ids = [
        Command.link(self.env.ref('payment.connection_available').id),
        Command.link(self.env.ref('paymentexpress_checkout').id),
        Command.link(self.env.ref('payment.mandatory_capture_flow').id),
        Command.link(self.env.ref('payment.refund').id),
        Command.link(self.env.ref('payment.tokenization').id),
    ]
```

##### `_stripe_get_inline_form_values()`

Returns the JSON configuration for the Stripe.js frontend form.

```python
def _stripe_get_inline_form_values(self):
    self.ensure_one()
    return {
        'publishable_key': self.stripe_publishable_key,
        'amount': {
            'amount': self._stripe_ format_amount(tx.amount, tx.currency_id),
            'currency': tx.currency_id.name.lower(),
        },
        'billing_details': {
            'name': partner.name,
            'email': partner.email,
            'address': self._stripe_format_address(partner),
        },
        'tokenization_requested': tx.tokenize,
        'express_checkout': {
            'payment_method_types': ['apple_pay', 'google_pay'],
            'amount': ...,
            'currency': ...,
        },
    }
```

##### `_stripe_get_publishable_key()`

Returns the Stripe publishable key for the frontend. The key is scoped to the provider's state (test vs production).

```python
def _stripe_get_publishable_key(self):
    self.ensure_one()
    if self.state == 'disabled':
        return None
    return self.stripe_publishable_key
```

##### `action_start_onboarding()`

Initiates the Stripe Connect onboarding flow. This creates a connected Stripe account for the merchant if they want to use Stripe Connect (marketplace features).

```python
def action_start_onboarding(self):
    self.ensure_one()
    connected_account = self._stripe_fetch_or_create_connected_account()
    account_link = self._stripe_create_account_link(connected_account)
    return {
        'type': 'ir.actions.act_url',
        'url': account_link['url'],
        'target': 'self',
    }
```

##### `_stripe_fetch_or_create_connected_account()`

Gets or creates a Stripe connected account for the provider's company.

```python
def _stripe_fetch_or_create_connected_account(self):
    # Check if company already has a connected account ID stored
    connected_account_id = self.env.company.stripe_connected_account_id
    
    if not connected_account_id:
        # Create a new connected account via Stripe API
        payload = self._stripe_prepare_connect_account_payload()
        response = self._stripe_make_request('/v1/accounts', payload)
        connected_account_id = response['id']
        self.env.company.stripe_connected_account_id = connected_account_id
    
    return connected_account_id
```

##### `_stripe_prepare_connect_account_payload()`

Builds the company data payload for creating a Stripe Connect account.

```python
def _stripe_prepare_connect_account_payload(self):
    company = self.env.company
    country_code = self._stripe_get_country(company.country_id.code)
    return {
        'type': 'standard',  # or 'express' for onboarding flow
        'country': country_code,
        'email': company.email,
        'business_profile': {'name': company.name},
        'capabilities': {
            'card_payments': {'requested': True},
            'transfers': {'requested': True},
        },
    }
```

##### `_stripe_create_account_link()`

Creates a Stripe-hosted onboarding URL for the connected account.

```python
def _stripe_create_account_link(self, account_id):
    base_url = self.get_base_url()
    payload = {
        'account': account_id,
        'refresh_url': f'{base_url}/payment/stripe/connect/refresh',
        'return_url': f'{base_url}/payment/stripe/connect/return',
        'type': 'account_onboarding',
    }
    return self._stripe_make_request('/v1/account_links', payload)
```

##### `_stripe_onboarding_is_ongoing()`

Hook for other modules to check if Stripe Connect onboarding is still in progress.

```python
def _stripe_onboarding_is_ongoing(self):
    self.ensure_one()
    connected_account_id = self.env.company.stripe_connected_account_id
    if not connected_account_id:
        return False
    
    account = self._stripe_make_request(f'/v1/accounts/{connected_account_id}')
    return account.get('details_submitted') is False
```

##### `_build_request_url(endpoint)`

Routes requests to the correct Stripe API URL.

```python
def _build_request_url(self, endpoint):
    # If using proxy: goes through Odoo's proxy
    # Otherwise: direct to Stripe API
    base_url = 'https://api.stripe.com/v1'
    return f'{base_url}/{endpoint}'
```

##### `_build_request_headers(tx=None)`

Adds Stripe authentication headers.

```python
def _build_request_headers(self, tx=None):
    return {
        'Authorization': f'Bearer {self.stripe_secret_key}',
        'Stripe-Version': '2023-10-16',  # API version
        'Content-Type': 'application/x-www-form-urlencoded',
    }
```

Note: Stripe uses `application/x-www-form-urlencoded` for most API calls, not JSON.

### payment.transaction (Inherited)

**File:** `models/payment_transaction.py`

#### Key Methods

##### `_get_specific_processing_values()`

Returns Stripe-specific values for payment processing.

```python
def _get_specific_processing_values(self, processing_values):
    res = super()._get_specific_processing_values(processing_values)
    return {
        **res,
        'stripe_publishable_key': self.provider_id.stripe_publishable_key,
        'stripe_amount': self.provider_id._stripe_format_amount(
            self.amount, self.currency_id
        ),
        'stripe_currency': self.currency_id.name.lower(),
        'stripe_customer_id': self._stripe_get_customer_id(),
    }
```

##### `_create_stripe_payment_intent()`

Creates a Stripe PaymentIntent via the API.

```python
def _create_stripe_payment_intent(self, payment_method_id=None):
    payload = {
        'amount': self.provider_id._stripe_format_amount(
            self.amount, self.currency_id
        ),
        'currency': self.currency_id.name.lower(),
        'payment_method': payment_method_id,
        'confirm': 'true',  # Auto-confirm
        'automatic_payment_methods[enabled]': 'true',
        'automatic_payment_methods[allow_redirects]': 'never',
        'description': f'{self.env.company.name}: {self.reference}',
        'metadata[reference]': self.reference,
        'capture_method': 'manual' if self.provider_id.capture_manually else 'automatic',
        **self._stripe_get_customer_payload(),
    }
    
    response = self.provider_id._stripe_make_request(
        '/v1/payment_intents',
        payload,
    )
    
    self.stripe_payment_intent = response['id']
    return response
```

##### `_stripe_capture_payment_intent()`

Captures an authorized PaymentIntent (manual capture flow).

```python
def _stripe_capture_payment_intent(self):
    payload = {
        'amount_to_capture': self.provider_id._stripe_format_amount(
            self.amount, self.currency_id
        ),
    }
    
    response = self.provider_id._stripe_make_request(
        f'/v1/payment_intents/{self.stripe_payment_intent}/capture',
        payload,
    )
    
    # status = 'succeeded': capture successful
    # status = 'canceled': capture failed
```

Note: Stripe only supports full capture (no partial). The `capture_manually` feature in Odoo uses `capture_method='manual'` which puts the PaymentIntent in `requires_capture` state.

##### `_stripe_refund_payment_intent()`

Issues a refund for a succeeded PaymentIntent.

```python
def _stripe_refund_payment_intent(self, amount_to_refund=None):
    payload = {
        'payment_intent': self.stripe_payment_intent,
    }
    if amount_to_refund:
        payload['amount'] = self.provider_id._stripe_format_amount(
            amount_to_refund, self.currency_id
        )
    
    response = self.provider_id._stripe_make_request(
        '/v1/refunds',
        payload,
    )
    
    self.operation = 'refund'
```

##### `_stripe_cancel_payment_intent()`

Cancels an authorized (but not captured) PaymentIntent.

```python
def _stripe_cancel_payment_intent(self):
    response = self.provider_id._stripe_make_request(
        f'/v1/payment_intents/{self.stripe_payment_intent}/cancel',
        {},
    )
    self._set_canceled()
```

##### `_apply_updates(response_data)`

Updates transaction state based on Stripe event data.

```python
def _apply_updates(self, event_type, event_data):
    if event_type == 'payment_intent.succeeded':
        self._set_done()
    elif event_type == 'payment_intent.requires_action':
        self._set_pending()
    elif event_type == 'payment_intent.canceled':
        self._set_canceled()
    elif event_type == 'payment_intent.payment_failed':
        failure_message = event_data.get('last_payment_error', {}).get('message', '')
        self._set_error(failure_message)
```

#### State Mapping

| Stripe `PaymentIntent.status` | Odoo State | Notes |
|-------------------------------|------------|-------|
| `succeeded` | `done` | Payment completed |
| `requires_capture` | `authorized` | Manual capture mode, pending capture |
| `requires_action` | `pending` | 3DS/SCA redirect in progress |
| `requires_payment_method` | `error` | Card failed |
| `canceled` | `canceled` | Payment canceled |

## Architecture Notes

### Stripe.js and PCI Compliance

Stripe.js is a JavaScript library that tokenizes sensitive card data in the browser. The key security properties:

1. **Card data never touches Odoo's server** — The browser sends card details directly to Stripe.js, which returns a `payment_method_id` (pm_xxx)
2. **No PCI DSS compliance needed for merchant** — Since card data never touches the merchant's server, the merchant's PCI scope is dramatically reduced
3. **Stripe handles 3D Secure** — SCA (Strong Customer Authentication) is handled by Stripe.js and the browser

Odoo's `payment_stripe` module loads Stripe.js and initializes it with the publishable key:

```html
<script src="https://js.stripe.com/v3/"></script>
<script>
  const stripe = Stripe('pk_test_xxx');
</script>
```

### Express Checkout (Apple Pay / Google Pay)

Stripe supports Express Checkout buttons for Apple Pay and Google Pay. This uses the `payment_modes` configuration and requires domain verification:

```javascript
// Frontend: express_checkout.js
const paymentRequest = stripe.paymentRequest({
  country: 'US',
  currency: 'usd',
  total: { label: 'Odoo Order', amount: 1999 },
  requestPayerName: true,
  requestPayerEmail: true,
});

// Apple Pay / Google Pay button rendered automatically
const prButton = elements.create('paymentRequestButton', { paymentRequest });
```

The `action_stripe_verify_apple_pay_domain()` method handles domain verification for Apple Pay. Google Pay domains are verified through the Stripe Dashboard.

### Stripe Connect

For marketplace scenarios (Odoo Shops, multi-vendor), Stripe Connect allows splitting payments between a platform account and connected sub-accounts:

```
Customer pays $100
      │
      ├── Platform fee: $10 (application_fee_amount)
      ├── Connected account: $90
      └── Stripe: processing fees deducted
```

The `_stripe_use_connected_account` flag on the provider controls whether to route payments through connected accounts.

### Webhook Security

Stripe signs all webhook payloads with a webhook secret using HMAC-SHA256:

```
Stripe-Signature: t=1614556800,v1=5257a869e7ecebeda32affa62cdca3fa
```

The signature header contains a timestamp (`t=`) and one or more signatures (`v1=`). The signature is `HMAC-SHA256(timestamp + "." + payload, webhook_secret)`.

Odoo verifies by:
1. Extracting timestamp and signature from header
2. Computing expected signature
3. Comparing with `hmac.compare_digest` (constant-time comparison)

### Proxy Architecture

For certain requests, Odoo routes through a proxy layer (`/payment/stripe/proxy`). This allows:
- IP-based rate limiting
- Request logging
- API key rotation without downtime

```python
def _stripe_make_request(self, endpoint, payload=None):
    if self._stripe_uses_proxy():
        return self._stripe_proxy_request(endpoint, payload)
    return self._stripe_direct_request(endpoint, payload)
```

### Idempotency

All Stripe API requests include an `Idempotency-Key` header:

```python
headers['Idempotency-Key'] = payment_utils.generate_idempotency_key(
    self, scope='payment_request'
)
```

This prevents duplicate charges if a request is retried due to network failure.

### Currency Formatting

Stripe uses the smallest currency unit (e.g., cents for USD, pence for GBP):

```python
def _stripe_format_amount(self, amount, currency):
    # amount=19.99, currency USD (2 decimal places)
    # -> 1999
    return int(amount * (10 ** currency.decimal_places))
```

### Error Handling

Stripe error responses include:

```python
{
    'error': {
        'type': 'card_error',       # card_error, validation_error, api_error
        'code': 'card_declined',    # e.g., 'card_declined', 'expired_card'
        'decline_code': 'insufficient_funds',
        'message': 'Your card has insufficient funds.',
    }
}
```

The `_parse_response_error()` method extracts these fields for display in Odoo.

## Configuration

### Stripe Dashboard Setup

1. **Get API keys**: Stripe Dashboard > Developers > API keys
   - Publishable key: `pk_test_xxx` or `pk_live_xxx`
   - Secret key: `sk_test_xxx` or `sk_live_xxx` (server-side only)
2. **Configure webhook**: Stripe Dashboard > Developers > Webhooks
   - Add endpoint: `https://your-odoo-domain.com/payment/stripe/webhook`
   - Select events: `payment_intent.succeeded`, `payment_intent.requires_action`, `payment_intent.payment_failed`, `charge.refunded`, `refund.updated`
   - Copy the webhook signing secret (`whsec_xxx`)
3. **Verify domain**: For Express Checkout, verify your domain in Stripe Dashboard > Settings > Apple Pay / Google Pay

### Stripe Connect (Optional)

For marketplace features:
1. Enable Stripe Connect in the provider
2. Click "Start Onboarding" to initiate connected account creation
3. Complete the Stripe-hosted onboarding flow
4. Once complete, payments can be split using `_stripe_use_connected_account`

### Supported Currencies

Stripe supports 135+ currencies. The module automatically formats amounts correctly. Note:
- Some currencies use 0 decimal places (e.g., JPY) — Odoo handles this
- Cryptocurrency is not supported directly (requires third-party integration)

## Security Analysis

### Credential Storage

| Field | Storage | Access |
|-------|---------|--------|
| `stripe_secret_key` | Ir.config_parameter (system) | System group only |
| `stripe_webhook_secret` | Ir.config_parameter (system) | System group only |
| `stripe_publishable_key` | Plain in `payment.provider` | Public (frontend uses it) |

### Webhook Signature Verification

```python
def _verify_webhook_signature(self, payload, headers):
    sig = headers.get('Stripe-Signature', '')
    # Parse: t=timestamp,v1=signature
    # Compute: HMAC-SHA256(timestamp + '.' + payload, secret)
    # Compare with hmac.compare_digest (timing-attack safe)
    return computed_sig == received_sig
```

### Card Data Security

- Card numbers are collected by Stripe.js in a secure iframe, never touching Odoo
- Stripe.js is loaded from `https://js.stripe.com` (a Stripe-controlled CDN)
- The publishable key only authorizes frontend operations, not server-side charges
- PCI compliance is the merchant's responsibility only for Odoo's application logic, not card data handling

### Best Practices

1. **Always use webhooks for state updates** — Don't rely solely on the synchronous payment response; the webhook confirms the authoritative state
2. **Handle duplicates** — Stripe may send the same event multiple times; use idempotency keys and check if the state is already set
3. **Use test mode during development** — Stripe test mode uses test card numbers that never charge real money
4. **Monitor webhook failures** — If the webhook endpoint returns non-200 for too long, Stripe may disable it

## Testing

### Test Card Numbers

| Card Number | Scenario | 3DS |
|-------------|----------|-----|
| `4242424242424242` | Successful payment | No |
| `4000000000000002` | Always fails | No |
| `4000002500003155` | Requires SCA | Yes |
| `4000008260003178` | Insufficient funds | No |
| `4000000000009995` | Insufficient test balance | No |

### Test Mode

Set the provider state to "Test" to use Stripe sandbox. The publishable and secret keys will use `pk_test_xxx` and `sk_test_xxx`.

## Related

- [Modules/payment](payment.md) — Base payment engine
- [Modules/payment_adyen](payment_adyen.md) — Adyen provider
- [Modules/payment_paypal](payment_paypal.md) — PayPal provider
- [Modules/payment_mollie](payment_mollie.md) — Mollie provider
