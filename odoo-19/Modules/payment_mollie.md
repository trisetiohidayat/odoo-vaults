---
type: module
module: payment_mollie
tags: [odoo, odoo19, payment, mollie]
uuid: 5b1c2d3e-4f5a-6b7c-8d9e-0f1a2b3c4d5e
created: 2026-04-06
---

# Payment Provider: Mollie (`payment_mollie`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Mollie |
| **Technical** | `payment_mollie` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A., Applix BV, Droggol Infotech Pvt. Ltd. |
| **Module** | `payment_mollie` |

## Description

A Dutch payment provider covering most European countries. Mollie provides online payments via credit cards, SEPA Direct Debit, iDEAL, Bancontact, SOFORT, and dozens of other local payment methods across the Netherlands, Germany, France, Belgium, Austria, and broader Europe. Mollie's key differentiator is its simplicity — a single API key controls everything, and the live/test mode is auto-detected from the key format.

In Odoo 19, the Mollie module connects directly to the Mollie REST API v2, handles payment creation, webhook notifications, and refund processing. Unlike Stripe and Adyen, Mollie does not support manual capture or tokenization natively — payments are captured immediately upon authorization.

## Dependencies

```
payment
```

## Module Structure

```
payment_mollie/
├── models/
│   ├── payment_provider.py       # Provider config, API setup
│   └── payment_transaction.py     # Payment creation, webhook, refunds
├── controllers/
│   └── main.py                   # MollieController (return URL, webhook)
├── const.py                       # Constants: locales, currencies, method mapping
├── data/
│   └── neutralization.py         # Credential neutralization
└── __manifest__.py
```

## Installation

1. Create a Mollie account at https://www.mollie.com
2. Go to **Developers > API keys** to get your API key:
   - Test key: `test_xxx`
   - Live key: `live_xxx`
3. In Odoo: **Invoicing / Accounting > Configuration > Payment Providers**
4. Select Mollie and paste the API key
5. Mollie auto-detects test vs. production based on the key prefix
6. Configure the webhook URL in Mollie Dashboard:
   - URL: `https://your-odoo-domain.com/payment/mollie/webhook`
   - Or let Odoo configure it automatically via `action_mollie_create_webhook()`

## Data Flow

### Payment Flow

```
Customer Checkout
      │
      ▼
Odoo: payment_transaction._get_specific_processing_values()
      │
      ▼
_mollie_prepare_payment_request_payload()
  - Builds payment payload with amount, description, redirect URL
  - Includes payment method from provider's default methods
      │
      ▼
POST https://api.mollie.com/v2/payments
  Headers: Authorization: Bearer <api_key>
  Body: {
    amount: { currency: "EUR", value: "19.99" },
    description: "MyCompany: S00001-001",
    redirectUrl: "https://.../payment/mollie/return?tx=<ref>",
    webhookUrl: "https://.../payment/mollie/webhook",
    locale: "en_US",
    metadata: { reference: "S00001-001" },
    method: "creditcard"  // or omitted for all methods
  }
      │
      ▼
Mollie returns payment object:
{
  id: "tr_abc123",
  status: "open",          // open, pending, failed, paid, expired, canceled
  _links: {
    checkout: { href: "https://www.mollie.com/checkout/..." },
    webhook: "https://api.mollie.com/v2/payments/tr_abc123"
  }
}
      │
      ▼
Odoo stores mollie_payment_id on transaction
      │
      ▼
Browser redirects to Mollie checkout page
  URL: https://www.mollie.com/checkout/...?theme=...
      │
      ▼
Customer completes payment on Mollie
      │
      ▼
Mollie redirects to /payment/mollie/return
      │
      ▼
MollieController._return_url()
  - Fetches payment status from Mollie API
  - _apply_updates(status) -> state
      │
      ▼
AND/OR Mollie sends webhook POST /payment/mollie/webhook
      │
      ▼
MollieController._webhook_url()
  - Verifies webhook (Mollie-API-Key header check)
  - _verify_and_process(payment_id)
    - Fetches payment from Mollie
    - _apply_updates(status)
```

### Webhook Processing

```
POST /payment/mollie/webhook
  Headers: Mollie-Idempotency-Key, Mollie-API-Key (for verification)
      │
      ▼
_verify_and_process(payment_id)
  - Fetch payment from Mollie: GET /v2/payments/<id>
  - Find Odoo transaction by mollie_payment_id
  - Call _apply_updates(status)
      │
      ├──► status = "paid": tx.state = 'done'
      ├──► status = "pending": tx.state = 'pending'
      ├──► status = "failed": tx.state = 'error'
      ├──► status = "canceled": tx.state = 'canceled'
      └──► status = "expired": tx.state = 'canceled'
      │
      ▼
Returns HTTP 200 (Mollie expects acknowledgment)
```

### Refund Flow

```
Done transaction
      │
      ▼
User clicks "Refund"
      │
      ▼
POST https://api.mollie.com/v2/payments/<id>/refunds
  Body: {
    amount: { currency: "EUR", value: "19.99" },  // or partial
    description: "Refund for S00001-001"
  }
      │
      ├──► 200: Refund created (status: pending)
      │         └── tx.operation = 'refund'
      │
      └──► Mollie sends REFUND webhook when settled
               └── Refund status updated
```

## Key Models

### payment.provider (Inherited)

**File:** `models/payment_provider.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `mollie_api_key` | Char | Mollie Test or Live API key (determines environment) |
| `mollie_profile_id` | Char | Mollie profile ID (optional, for multi-website) |
| `mollie_website_id` | Char | Mollie website ID (optional) |

#### Feature Support

| Feature | Support | Notes |
|---------|---------|-------|
| Manual capture | `False` | Immediate capture only |
| Refund | `partial` | Partial refunds supported |
| Tokenization | `False` | Not natively supported |
| Express Checkout | `False` | Not supported |

#### Key Methods

##### `_get_supported_currencies()`

Filters the currency dropdown to Mollie-supported currencies.

```python
def _get_supported_currencies(self):
    supported = super()._get_supported_currencies()
    return supported.filtered_domain([
        ('name', 'in', const.SUPPORTED_CURRENCIES)
    ])
```

**Supported Currencies (28):**

```
AED, AUD, BGN, BRL, CAD, CHF, CZK, DKK, EUR, GBP,
HKD, HRK, HUF, ILS, JPY, MXN, MYR, NOK, NZD, PHP,
PLN, RON, SEK, SGD, THB, USD, ZAR
```

##### `_get_default_payment_method_codes()`

Returns the default payment methods for the Mollie provider.

```python
def _get_default_payment_method_codes(self):
    return const.DEFAULT_PAYMENT_METHOD_CODES
```

Default methods: `creditcard`, `bancontact`, `belfius`, `kbc`, `klarna`, `paypal`, `sofort`, `ideal`, `banktransfer`, `directdebit`

##### `_build_request_url(endpoint)`

Builds the Mollie API URL.

```python
def _build_request_url(self, endpoint):
    return f"https://api.mollie.com/v2/{endpoint}"
```

All Mollie API endpoints are under `https://api.mollie.com/v2/`.

##### `_build_request_headers(tx=None)`

Builds authentication headers using the API key.

```python
def _build_request_headers(self, tx=None):
    return {
        'Authorization': f'Bearer {self.mollie_api_key}',
        'Content-Type': 'application/json',
    }
```

The API key is directly in the `Authorization` header (Basic Auth format: `Bearer <key>`).

##### `_parse_response_error(response)`

Extracts error information from Mollie error responses.

```python
def _parse_response_error(self, response):
    error_data = response.json()
    return {
        'error_code': error_data.get('status', ''),
        'error_message': error_data.get('message', ''),
        'error_detail': error_data.get('field', ''),
    }
```

Mollie error format:

```python
{
    "status": 422,
    "title": "Unprocessable Entity",
    "detail": "The amount is higher than the maximum for method 'ideal'.",
    "extra": {
        "parameter": "amount",
        "minimum": "0.01",
        "maximum": "100000.00"
    }
}
```

### payment.transaction (Inherited)

**File:** `models/payment_transaction.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `mollie_payment_id` | Char | Mollie's payment ID (tr_xxx) |
| `mollie_profile_id` | Char | Mollie profile that processed the payment |
| `mollie_payment_mode` | Char | Payment method used (creditcard, ideal, etc.) |

#### Key Methods

##### `_mollie_prepare_payment_request_payload()`

Builds the Mollie payment creation payload.

```python
def _mollie_prepare_payment_request_payload(self):
    base_url = self.provider_id.get_base_url()
    return {
        'amount': {
            'currency': self.currency_id.name,
            'value': f'{self.amount:.2f}',  # String format required
        },
        'description': f'{self.env.company.name}: {self.reference}',
        'redirectUrl': f'{base_url}/payment/mollie/return?tx_id={self.id}',
        'webhookUrl': f'{base_url}/payment/mollie/webhook',
        'locale': self._mollie_get_locale(),
        'metadata': {
            'reference': self.reference,
        },
        # Payment method selection
        'method': self._mollie_get_preferred_method(),
    }
```

**Payload Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `amount` | Object | `{currency, value}` — value must be string (e.g., "19.99") |
| `description` | String | Shown on Mollie's payment page |
| `redirectUrl` | URL | Where Mollie redirects after payment |
| `webhookUrl` | URL | Mollie's server-to-server notification |
| `locale` | String | UI language (e.g., `en_US`, `nl_NL`, `de_DE`) |
| `metadata` | Object | Custom data returned in webhook/refund |
| `method` | String | Specific payment method (optional — omit for all) |

##### `_mollie_get_locale()`

Determines the locale for the Mollie checkout page based on the partner's country.

```python
def _mollie_get_locale(self):
    partner = self.partner_id
    
    # Map country to Mollie locale
    if partner.country_id:
        locale = const.SUPPORTED_LOCALES.get(partner.country_id.code)
        if locale:
            return locale
    
    return 'en_US'  # Default fallback
```

**Supported Locales:**

| Code | Language |
|------|----------|
| `nl_NL` | Dutch (Netherlands) |
| `nl_BE` | Dutch (Belgium) |
| `fr_FR` | French |
| `fr_BE` | French (Belgium) |
| `de_DE` | German |
| `de_AT` | German (Austria) |
| `de_CH` | German (Switzerland) |
| `en_US` | English (default) |
| `en_GB` | English (UK) |
| `es_ES` | Spanish |
| `it_IT` | Italian |
| `pl_PL` | Polish |
| `pt_PT` | Portuguese |
| `sv_SE` | Swedish |
| `fi_FI` | Finnish |
| `da_DK` | Danish |
| `nb_NO` | Norwegian |
| `hu_HU` | Hungarian |
| `cs_CZ` | Czech |
| `ro_RO` | Romanian |
| `sk_SK` | Slovak |
| `bg_BG` | Bulgarian |
| `lt_LT` | Lithuanian |
| `sl_SI` | Slovenian |
| `et_EE` | Estonian |

##### `_mollie_get_preferred_method()`

Returns the payment method to pre-select. If the provider allows all methods, this returns `None` and Mollie shows all options.

```python
def _mollie_get_preferred_method(self):
    # Use the first enabled payment method on the provider
    if self.payment_method_id:
        return self.payment_method_id.code
    return None  # Show all methods
```

##### `_apply_updates(status, response_data)`

Maps Mollie payment status to Odoo transaction state.

```python
def _apply_updates(self, status, response_data):
    if status == 'paid':
        self._set_done()
    elif status == 'pending':
        self._set_pending()
    elif status in ('failed', 'canceled', 'expired'):
        self._set_canceled()
    else:
        _logger.warning("Unknown Mollie payment status: %s", status)
```

**Mollie Payment Status Mapping:**

| Mollie Status | Odoo State | Notes |
|---------------|------------|-------|
| `open` | `pending` | Payment created, not yet completed |
| `pending` | `pending` | Redirect in progress or bank transfer pending |
| `paid` | `done` | Payment successful |
| `failed` | `error` | Payment failed |
| `canceled` | `canceled` | Payment canceled by user |
| `expired` | `canceled` | Payment expired (not completed in time) |

##### `_mollie_refund()`

Issues a refund via Mollie's refund API.

```python
def _mollie_refund(self, amount_to_refund=None):
    refund_amount = amount_to_refund or self.amount
    payload = {
        'amount': {
            'currency': self.currency_id.name,
            'value': f'{refund_amount:.2f}',
        },
        'description': f'Refund: {self.reference}',
    }
    
    response = self.provider_id._mollie_make_request(
        f'/v2/payments/{self.mollie_payment_id}/refunds',
        payload,
    )
    
    self.operation = 'refund'
    return response
```

Mollie refunds are asynchronous — the API returns `202 Accepted` immediately, and the refund settles asynchronously. The webhook fires when the refund is settled.

#### MollieController

**File:** `controllers/main.py`

##### `_webhook_url()`

Handles Mollie's webhook notifications. This is the primary payment confirmation mechanism.

```python
@http.route('/payment/mollie/webhook', type='json', auth='public')
def mollie_webhook(self, **data):
    payment_id = data.get('id') or request.jsonrequest.get('id')
    
    # Verify using the API key in the header
    api_key = request.httprequest.headers.get('Mollie-API-Key')
    
    # Verify the payment belongs to this Odoo instance
    tx = request.env['payment.transaction'].sudo()._mollie_verify_payment(
        payment_id, api_key
    )
    
    if not tx:
        return 'not found'
    
    # Process the webhook
    tx._mollie_handle_webhook()
    
    return 'ok'
```

The webhook uses `type='json'` for POST requests. Mollie sends a JSON body with the payment object.

##### `_return_url()`

Handles the customer return from Mollie's checkout page.

```python
@http.route('/payment/mollie/return', type='http', auth='public', website=True)
def mollie_return(self, tx_id, **kwargs):
    tx = request.env['payment.transaction'].browse(int(tx_id))
    
    # Fetch current payment status from Mollie
    payment = tx.provider_id._mollie_make_request(
        f'/v2/payments/{tx.mollie_payment_id}'
    )
    
    # Apply status update
    tx._apply_updates(payment.get('status'), payment)
    
    # Redirect to order confirmation page
    return request.redirect('/payment/validate')
```

The return URL is a simple HTTP redirect — the actual payment state is determined by the webhook, but the return URL provides immediate customer feedback.

##### `_verify_and_process(payment_id)`

Static helper that verifies a payment exists in Mollie's system and returns the payment object.

```python
@staticmethod
def _verify_and_process(payment_id, api_key):
    # Make direct API call to Mollie to verify payment
    response = requests.get(
        f'https://api.mollie.com/v2/payments/{payment_id}',
        headers={'Authorization': f'Bearer {api_key}'},
        timeout=10,
    )
    return response.json()
```

## Payment Methods

Mollie supports dozens of payment methods. The module maps Odoo's internal method codes to Mollie method IDs:

```python
# const.py
PAYMENT_METHODS_MAPPING = {
    'creditcard': 'creditcard',       # Visa, Mastercard, Amex
    'bancontact': 'bancontact',       # Belgian cards
    'belfius': 'belfius',             # Belgian bank
    'kbc': 'kbc',                     # Belgian bank
    'klarna': 'klarna',               # Buy Now Pay Later
    'paypal': 'paypal',               # PayPal
    'sofort': 'sofort',               # German/Swiss bank transfer
    'ideal': 'ideal',                 # Dutch bank transfer
    'banktransfer': 'banktransfer',   # SEPA credit transfer
    'directdebit': 'directdebit',    # SEPA Direct Debit
    'applepay': 'applepay',           # Apple Pay
    'googlepay': 'googlepay',         # Google Pay
    'tikkie': 'tikkie',               # Dutch mobile payment
    'eps': 'eps',                     # Austrian bank transfer
    'giropay': 'giropay',             # German bank transfer
    'klarna_pay_later': 'klarna_pay_later',
    'klarna_slice_it': 'klarna_slice_it',
    'maestro': 'maestro',             # Debit card
    'multibanco': 'multibanco',       # Portuguese
    'p24': 'p24',                     # Polish bank transfer
    'sepa': 'sepa',                   # SEPA credit transfer
    'voucher': 'voucher',            # Mollie vouchers
}

DEFAULT_PAYMENT_METHOD_CODES = [
    'creditcard', 'bancontact', 'ideal', 'paypal', 'sofort',
    'banktransfer', 'directdebit', 'klarna'
]
```

## Architecture Notes

### Test vs Production Detection

Mollie uses a single API key field. The key prefix determines the environment:

```
Test key:  test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Live key:  live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Odoo does not have a separate "test mode" toggle — the environment is determined by the key used. This simplifies configuration but requires careful key management.

### Payment Methods

Unlike Stripe (which uses a single `card` method), Mollie exposes many payment methods as separate options. Each method:
- May have different transaction fees
- May have different settlement timelines
- Requires the method to be activated in the Mollie dashboard

The `_get_supported_payment_method_codes()` method on the provider filters which methods are shown to the customer based on what is configured.

### Webhook Security

Mollie's webhook security is simpler than Stripe/Adyen:
- Mollie sends an `Mollie-API-Key` header in webhook requests
- The webhook handler verifies that the API key matches the provider's configured key
- No HMAC or RSA signature verification is required (the API key acts as the shared secret)

```python
def mollie_webhook(self, **data):
    incoming_key = request.httprequest.headers.get('Mollie-API-Key')
    provider_key = self.provider_id.mollie_api_key
    
    if incoming_key != provider_key:
        return request.not_found()
    
    # Process webhook...
```

This is a shared-secret model. The webhook URL is private (not easily guessable), and the API key proves the sender has valid credentials.

### Webhook Idempotency

Mollie may send the same webhook notification multiple times (network retries). The `_apply_updates()` method should be idempotent — calling `_set_done()` on an already-done transaction is a no-op.

### Payment Expiry

Mollie payments expire after a configurable time (default: 30 minutes for bank transfers, instant for cards). Expired payments cannot be completed and should be canceled.

### Settlement

Mollie settles payments automatically:
- Card payments: typically within 2 business days
- Bank transfers (iDEAL, SEPA): after the transfer is confirmed (1-2 business days)
- Direct debit: after the debit is collected (typically 5 business days)

Odoo does not track settlement status — it only tracks the payment authorization status.

## Configuration

### Mollie Dashboard

1. **API keys**: Dashboard > Developers > API keys
2. **Payment methods**: Dashboard > Websites > [your website] > Payment methods
   - Activate the methods you want to accept
   - Some methods require additional setup (e.g., Klarna requires agreement)
3. **Webhook**: Dashboard > Developers > Webhooks
   - Set URL to `https://your-odoo-domain.com/payment/mollie/webhook`
   - Optionally set the API key here too
4. **Profiles**: For multi-website setups, each website can have its own Mollie profile

### Odoo Configuration

The provider has these settings:

| Setting | Description |
|---------|-------------|
| State | Enabled / Disabled / Test |
| Company | Which company this provider belongs to |
| Payment Method Codes | Which Mollie methods to offer |
| Journal | Journal for recording transactions |

## Security Analysis

### Credential Storage

| Field | Storage | Access |
|-------|---------|--------|
| `mollie_api_key` | Ir.config_parameter (system) | System group only |

The API key is stored as a system parameter and is only accessible to administrators.

### Webhook Verification

The webhook handler verifies the `Mollie-API-Key` header against the provider's stored key. This prevents unauthorized webhook submissions.

### Card Data

Mollie handles all PCI compliance. Card data is collected by Mollie's hosted pages and never touches Odoo's server. Odoo only stores the `mollie_payment_id`.

### Best Practices

1. **Always use the webhook for state updates** — the redirect return URL is for user experience, not authoritative state
2. **Set up webhook monitoring** — Mollie's dashboard shows webhook delivery status
3. **Handle duplicates** — same webhook may be sent multiple times
4. **Use test key during development** — never accidentally use live key in development

## Testing

### Test Mode

Simply use a `test_` API key. Mollie provides test mode automatically — no separate toggle needed.

### Test Payment Methods

Mollie's test mode supports simulated payments:
- Use test card numbers provided by Mollie
- For iDEAL: select a test bank
- For SEPA: simulate a test transfer

### Testing Webhooks Locally

Use Mollie's webhook testing tool (Dashboard > Developers > Webhooks > Test) to send fake webhook events during development.

## Error Handling

Mollie error responses:

```python
{
    "status": 422,
    "title": "Unprocessable Entity",
    "detail": "The given credit card was declined.",
    "_links": {
        "documentation": { "href": "https://docs.mollie.com/..." }
    }
}
```

Common error codes:
- `422 Unprocessable Entity`: Invalid request (wrong amount, currency not supported, method not enabled)
- `401 Unauthorized`: Invalid API key
- `403 Forbidden`: Access denied (e.g., payment method not allowed)
- `404 Not Found`: Payment not found

## Related

- [Modules/payment](payment.md) — Base payment engine
- [Modules/payment_stripe](payment_stripe.md) — Stripe provider
- [Modules/payment_adyen](payment_adyen.md) — Adyen provider
- [Modules/payment_paypal](payment_paypal.md) — PayPal provider
- [Modules/pos_mollie](pos_mollie.md) — Mollie POS terminal integration
