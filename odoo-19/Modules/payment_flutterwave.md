---
uuid: d4e8c1a2-3b5f-6a7c-8d9e-0f1a2b3c4d5e
tags:
  - odoo
  - odoo19
  - modules
  - payment
  - flutterwave
  - payment-provider
  - africa
---

# Payment Flutterwave (`payment_flutterwave`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Flutterwave |
| **Technical** | `payment_flutterwave` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `payment` |
| **Version** | 1.0 |

## Description

Flutterwave is an African payment gateway provider that enables businesses across Africa to accept payments online. The module integrates with Flutterwave's unified payment API, supporting card payments, mobile money, bank transfers, and numerous local payment methods across Nigeria, Kenya, Ghana, South Africa, and other African nations.

Flutterwave positions itself as the "Stripe of Africa" - providing a modern REST API that simplifies payment acceptance across multiple African countries, each with different banking infrastructure and regulatory requirements. The Odoo integration allows merchants to collect payments from customers using their preferred local payment methods without requiring separate integrations for each country or provider.

This module is particularly valuable for businesses operating in or expanding to African markets where local payment methods dominate. Unlike global payment processors that may not support African payment methods, Flutterwave specializes in the continent's diverse payment ecosystem.

## Geographic Coverage

Flutterwave supports payments from customers across numerous African countries and accepts payments in multiple currencies:

### Supported Countries
- Nigeria (NGN)
- Kenya (KES)
- Ghana (GHS)
- South Africa (ZAR)
- Tanzania (TZS)
- Uganda (UGX)
- Rwanda (RWF)
- Zambia (ZMW)
- Malawi (MWK)
- Sierra Leone (SLL)
- Guinea (GNF)
- Morocco (MAD)
- Cameroon (XAF)
- And additional countries

### Supported Currencies

| Currency | Code | Region |
|----------|------|--------|
| Nigerian Naira | NGN | Nigeria |
| Kenyan Shilling | KES | Kenya |
| Ghanaian Cedi | GHS | Ghana |
| South African Rand | ZAR | South Africa |
| US Dollar | USD | International |
| Euro | EUR | International |
| British Pound | GBP | International |
| Tanzanian Shilling | TZS | Tanzania |
| Ugandan Shilling | UGX | Uganda |
| Moroccan Dirham | MAD | Morocco |
| CFA Franc | XAF / XOF | West Africa |

This broad currency support makes Flutterwave ideal for pan-African businesses that need to accept payments in local currencies while settling in preferred currencies.

## Payment Methods

Flutterwave supports a wide variety of payment methods through a unified API:

### Card Payments
- Visa
- Mastercard
- American Express
- Discover

### Mobile Money
- M-Pesa (Kenya, Tanzania, Uganda)
- MTN Mobile Money
- Airtel Money
- Tigo Pesa
- Vodafone Cash

### Bank Transfers
- Nigerian bank transfers
- South African bank transfers
- Kenya bank transfers
- Other local bank transfers

### Other Methods
- USSD payments
- Voucher payments
- QR code payments

## Technical Architecture

### Module Structure

```
payment_flutterwave/
├── __init__.py
├── __manifest__.py
├── const.py                    # Constants: currencies, payment methods, status mapping
├── controllers/
│   ├── __init__.py
│   └── main.py               # FlutterwaveController - webhook & return handling
└── models/
    ├── __init__.py
    ├── payment_provider.py    # PaymentProvider extension
    └── payment_transaction.py # PaymentTransaction extension
```

### Data Flow

```
Customer Checkout
    │
    ▼
Odoo Payment Form
    │
    ▼
Flutterwave API (/payments endpoint)
    │
    ├── Payment Link Generated
    │
    ▼
Customer Redirected to Flutterwave Checkout
    │
    ├── Customer enters payment details
    ├── Customer authenticates (3DS if required)
    └── Payment processed by Flutterwave
    │
    ├── On Success: Webhook notification sent to Odoo
    ├── On Pending: Webhook notification sent to Odoo
    └── On Failure: Return to Odoo status page
    │
    ▼
Odoo Processes Transaction
    │
    ├── Transaction state updated (done/pending/error)
    ├── Order/Sale Order invoice state updated
    └── Customer notified
```

### API Integration

The module communicates with Flutterwave using their REST API at `https://api.flutterwave.com/v3/`. All requests require:

- **Authentication**: Bearer token using the `flutterwave_secret_key`
- **Content-Type**: `application/json`

The module handles:
1. **Payment Initiation**: Creating a payment session and obtaining a payment link
2. **Payment Verification**: Verifying payment status after customer returns
3. **Webhook Processing**: Handling asynchronous payment notifications
4. **Tokenization**: Storing card details securely for recurring payments

## Provider Configuration Fields

### Core Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | Selection | Yes | Fixed value: `flutterwave` |
| `flutterwave_public_key` | Char | Yes | Public key for client-side tokenization |
| `flutterwave_secret_key` | Char | Yes | Secret key for server-side API calls (hidden) |
| `flutterwave_webhook_secret` | Char | Yes | Secret for verifying webhook signatures (hidden) |

### Field Security

Both `flutterwave_secret_key` and `flutterwave_webhook_secret` are restricted to the `base.group_system` group, preventing regular users from viewing sensitive credentials. This follows security best practices for payment integration.

### Configuration Steps

1. **Create Flutterwave Account**: Register at [flutterwave.com](https://flutterwave.com)
2. **Obtain API Keys**: Get public and secret keys from Flutterwave dashboard
3. **Configure Webhook**: Set webhook URL to `https://your-odoo.com/payment/flutterwave/webhook`
4. **Copy Webhook Secret**: Get the webhook signing secret from Flutterwave dashboard
5. **Enter Credentials**: Input all three keys in the Odoo provider configuration

## Models Extended

### `payment.provider` (Extended)

The module extends the base `payment.provider` model to add Flutterwave-specific functionality:

#### Field Extension

```python
code = fields.Selection(
    selection_add=[('flutterwave', "Flutterwave")],
    ondelete={'flutterwave': 'set default'}
)
flutterwave_public_key = fields.Char(...)
flutterwave_secret_key = fields.Char(...)
flutterwave_webhook_secret = fields.Char(...)
```

#### Key Methods

**`_compute_feature_support_fields()`**

Enables tokenization support for Flutterwave:

```python
def _compute_feature_support_fields(self):
    super()._compute_feature_support_fields()
    self.filtered(lambda p: p.code == 'flutterwave').update({
        'support_tokenization': True,
    })
```

This allows customers to save their card details for future purchases (requires additional frontend integration).

**`_get_supported_currencies()`**

Filters currencies to Flutterwave-supported set:

```python
def _get_supported_currencies(self):
    supported_currencies = super()._get_supported_currencies()
    if self.code == 'flutterwave':
        supported_currencies = supported_currencies.filtered(
            lambda c: c.name in const.SUPPORTED_CURRENCIES
        )
    return supported_currencies
```

**`_get_compatible_providers()`**

Excludes Flutterwave from validation operations since it doesn't support payment method validation:

```python
def _get_compatible_providers(self, *args, is_validation=False, report=None, **kwargs):
    providers = super()._get_compatible_providers(...)
    if is_validation:
        providers = providers.filtered(lambda p: p.code != 'flutterwave')
    return providers
```

**`_build_request_url()`**

Constructs Flutterwave API URLs:

```python
def _build_request_url(self, endpoint, **kwargs):
    if self.code != 'flutterwave':
        return super()._build_request_url(endpoint, **kwargs)
    return url_join('https://api.flutterwave.com/v3/', endpoint)
```

**`_build_request_headers()`**

Adds Bearer token authentication:

```python
def _build_request_headers(self, *args, **kwargs):
    if self.code != 'flutterwave':
        return super()._build_request_headers(*args, **kwargs)
    return {'Authorization': f'Bearer {self.flutterwave_secret_key}'}
```

### `payment.transaction` (Extended)

The transaction model handles Flutterwave-specific payment processing:

#### Reference Generation

Flutterwave requires unique transaction references. The module ensures uniqueness using `singularize_reference_prefix`:

```python
def _compute_reference(self, provider_code, prefix=None, separator='-', **kwargs):
    if provider_code == 'flutterwave':
        prefix = payment_utils.singularize_reference_prefix(prefix=prefix, separator=separator)
    return super()._compute_reference(provider_code, prefix=prefix, separator=separator, **kwargs)
```

#### Rendering Values

Builds the payment payload sent to Flutterwave:

```python
def _get_specific_rendering_values(self, processing_values):
    payload = {
        'tx_ref': self.reference,
        'amount': self.amount,
        'currency': self.currency_id.name,
        'redirect_url': urls.urljoin(base_url, FlutterwaveController._return_url),
        'customer': {
            'email': self.partner_email,
            'name': self.partner_name,
            'phonenumber': self.partner_phone,
        },
        'customizations': {
            'title': self.company_id.name,
            'logo': urls.urljoin(base_url, f'web/image/res.company/{self.company_id.id}/logo'),
        },
        'payment_options': const.PAYMENT_METHODS_MAPPING.get(
            self.payment_method_code, self.payment_method_code
        ),
    }
```

#### Payment Status Processing

Maps Flutterwave statuses to Odoo transaction states:

| Flutterwave Status | Odoo State |
|-------------------|------------|
| `successful` | `done` |
| `pending`, `pending auth` | `pending` |
| `cancelled` | `cancel` |
| `failed` | `error` |

#### Token Management

For tokenized payments (saved cards), the module handles:

- **Token Creation**: Extracts card token and customer email from payment response
- **Payment Request**: Sends token-based payment requests to Flutterwave
- **3DS Handling**: Manages 3D Secure authentication redirects

#### Authorization Pending Detection

Identifies transactions awaiting external authorization:

```python
def _flutterwave_is_authorization_pending(self):
    return self.filtered_domain([
        ('provider_code', '=', 'flutterwave'),
        ('operation', '=', 'online_token'),
        ('state', '=', 'pending'),
        ('provider_reference', 'ilike', 'https'),
    ])
```

## Controller Endpoints

### `FlutterwaveController`

Located in `controllers/main.py`, handles three main endpoints:

#### 1. Return from Checkout

**Route**: `/payment/flutterwave/return`
**Method**: GET
**Auth**: Public

Processes the customer return after payment. Verifies the payment with Flutterwave API and updates the transaction state.

#### 2. Return from Authorization

**Route**: `/payment/flutterwave/auth_return`
**Method**: GET
**Auth**: Public

Handles the return after 3D Secure authentication. Parses the JSON response and delegates to the checkout return handler.

#### 3. Webhook Handler

**Route**: `/payment/flutterwave/webhook`
**Method**: POST
**Auth**: Public
**CSRF**: Disabled (required for webhook calls)

Receives asynchronous payment notifications. Only processes `charge.completed` events:

```python
def flutterwave_webhook(self):
    data = request.get_json_data()
    if data['event'] == 'charge.completed':
        payment_data = data['data']
        tx_sudo._process('flutterwave', payment_data)
    return request.make_json_response('')
```

### Webhook Security

Webhook authenticity is verified using the `verif-hash` header:

```python
@staticmethod
def _verify_signature(received_signature, tx_sudo):
    expected_signature = tx_sudo.provider_id.flutterwave_webhook_secret
    if not hmac.compare_digest(received_signature, expected_signature):
        raise Forbidden()
```

Using `hmac.compare_digest` prevents timing attacks on the signature comparison.

## Constants (`const.py`)

### Supported Currencies

```python
SUPPORTED_CURRENCIES = [
    'GBP', 'CAD', 'XAF', 'CLP', 'COP', 'EGP', 'EUR', 'GHS', 'GNF',
    'KES', 'MWK', 'MAD', 'NGN', 'RWF', 'SLL', 'STD', 'ZAR', 'TZS',
    'UGX', 'USD', 'XOF', 'ZMW',
]
```

### Payment Status Mapping

```python
PAYMENT_STATUS_MAPPING = {
    'pending': ['pending', 'pending auth'],
    'done': ['successful'],
    'cancel': ['cancelled'],
    'error': ['failed'],
}
```

### Default Payment Method Codes

```python
DEFAULT_PAYMENT_METHOD_CODES = {
    'card', 'mpesa', 'visa', 'mastercard', 'amex', 'discover',
}
```

### Payment Methods Mapping

```python
PAYMENT_METHODS_MAPPING = {
    'bank_transfer': 'banktransfer',
}
```

## Feature Support

| Feature | Support Level | Notes |
|---------|--------------|-------|
| Express Checkout | No | Not implemented in current version |
| Tokenization | Yes | Card tokenization enabled |
| Manual Capture | No | Full capture only |
| Partial Capture | No | Not supported |
| Refund | Yes | Via standard Odoo refund flow |
| Partial Refund | Yes | Supported |
| Validation | No | Excluded from validation operations |

## Payment Flow: Redirect Model

### Step 1: Customer Initiates Payment

1. Customer selects Flutterwave as payment method on Odoo checkout
2. Odoo creates a `payment.transaction` record with state `draft`
3. Odoo calls Flutterwave `/payments` API to create a payment session
4. Flutterwave returns a payment link (`redirect_url`)

### Step 2: Customer Pays on Flutterwave

1. Customer is redirected to Flutterwave checkout page
2. Customer enters payment details or selects local payment method
3. For cards: Customer may complete 3D Secure authentication
4. Flutterwave processes the payment

### Step 3: Return and Verification

1. Flutterwave redirects customer back to Odoo return URL
2. Odoo's `flutterwave_return_from_checkout` receives the redirect
3. Odoo calls Flutterwave `/transactions/verify_by_reference` API
4. Transaction state is updated based on verification result

### Step 4: Webhook Confirmation

1. Flutterwave sends webhook notification to Odoo webhook endpoint
2. Odoo verifies webhook signature using `verif-hash` header
3. Transaction state is confirmed/updated
4. Order/Invoice state is updated accordingly

## Security Considerations

### Sensitive Data Handling

- Secret keys are stored with `groups='base.group_system'` restriction
- Webhook secrets are never exposed to client-side code
- HMAC comparison prevents timing attacks on signature verification

### HTTPS Requirement

Flutterwave requires all webhook callbacks and redirect URLs to use HTTPS in production. Configure your Odoo instance behind an SSL-terminating reverse proxy or use Odoo's native SSL configuration.

### Webhook Configuration

In your Flutterwave dashboard:
1. Navigate to Settings > Webhooks
2. Add your webhook URL: `https://your-domain.com/payment/flutterwave/webhook`
3. Enable all event types (especially `charge.completed`)
4. Copy the webhook signing secret to Odoo configuration

## Troubleshooting

### Common Issues

**Payment not updating after customer returns**
- Check that webhook is properly configured in Flutterwave dashboard
- Verify webhook secret matches between Flutterwave and Odoo
- Check Odoo logs for webhook processing errors

**Signature verification failed**
- Ensure webhook secret is correctly copied (no extra spaces)
- Check that the server's clock is synchronized
- Verify the `verif-hash` header is being sent

**Currency not supported**
- Verify the currency is in the `SUPPORTED_CURRENCIES` list
- Ensure the currency is active in Odoo
- Check if Flutterwave supports that currency for your region

**3D Secure not working**
- Ensure your Flutterwave account has 3DS enabled
- Check that return URLs are properly configured
- Verify the auth return URL is accessible

## Related

- [Modules/payment](payment.md) — Base payment engine and transaction processing
- [Modules/payment_xendit](payment_xendit.md) — Southeast Asian payment provider
- [Modules/payment_nuvei](payment_nuvei.md) — Latin American payment provider
- [Modules/payment_demo](payment_demo.md) — Demo payment provider for testing
- [Modules/payment_custom](payment_custom.md) — Custom/wire transfer payment method
