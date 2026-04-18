---
uuid: b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e
tags:
  - odoo
  - odoo19
  - modules
  - payment
  - payment-provider
  - nuvei
  - latin-america
  - pci-dss
---

# Payment Nuvei (`payment_nuvei`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Nuvei |
| **Technical** | `payment_nuvei` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `payment` |
| **Sequence** | 350 |

## Description

Nuvei (formerly SafeCharge) is a global payment technology company that provides a unified payment platform covering Latin America, Europe, and international markets. The module integrates with Nuvei's REST API, supporting credit cards, local payment methods (Alternative Payment Methods/APMs), and regional payment solutions.

Nuvei differentiates itself through:

- **Comprehensive APM Coverage**: Supports dozens of local payment methods across Latin America
- **PCI-DSS Compliance**: Full PCI compliance without additional certification requirements
- **Smart Routing**: Intelligent payment routing to optimize success rates
- **Currency Optimization**: Multi-currency support with competitive FX rates
- **Regional Specialization**: Strong presence in Brazil, Mexico, Argentina, and other LATAM markets

The module enables merchants to accept payments from Latin American customers using their preferred local methods, making it ideal for businesses expanding to or operating in that region.

## Geographic Coverage

### Latin America

| Country | Currency | Code | Primary Payment Methods |
|---------|----------|------|------------------------|
| Brazil | Brazilian Real | BRL | Pix, Boleto, Credit Card |
| Mexico | Mexican Peso | MXN | SPEI, OXXO, Credit Card |
| Argentina | Argentine Peso | ARS | Credit Card, Debit |
| Colombia | Colombian Peso | COP | PSE, Credit Card |
| Chile | Chilean Peso | CLP | WebPay, Credit Card |
| Peru | Peruvian Sol | PEN | Credit Card |
| Uruguay | Uruguayan Peso | UYU | Credit Card |
| Canada | Canadian Dollar | CAD | Credit Card |
| USA | US Dollar | USD | Credit Card |

### Supported Currencies

```python
SUPPORTED_CURRENCIES = [
    'ARS',  # Argentine Peso
    'BRL',  # Brazilian Real
    'CAD',  # Canadian Dollar
    'CLP',  # Chilean Peso
    'COP',  # Colombian Peso
    'MXN',  # Mexican Peso
    'PEN',  # Peruvian Sol
    'USD',  # US Dollar
    'UYU',  # Uruguayan Peso
]
```

## Payment Methods

### Credit/Debit Cards

- Visa
- Mastercard
- American Express
- Discover
- Local card brands (Naranja, MercadoPago, etc.)

### Bank Transfers

- **SPEI** (Mexico): Direct bank transfers via the Mexican interbank system
- **PSE** (Colombia): Online payments through Colombian banks
- **SPEI Business** (Mexico): Business bank transfers

### Cash Vouchers

- **Boleto** (Brazil): Bank payment slips - widely used in Brazil
- **OXXO** (Mexico): Convenience store payments

### Digital Payments

- **Pix** (Brazil): Brazil's instant payment system
- **WebPay** (Chile): Chilean bank-based payments

### Regional Methods

```python
PAYMENT_METHODS_MAPPING = {
    'astropay': 'apmgw_Astropay_TEF',
    'boleto': 'apmgw_BOLETO',
    'card': 'cc_card',
    'nuvei_local': 'apmgw_Local_Payments',
    'oxxopay': 'apmgw_OXXO_PAY',
    'pix': 'apmgw_PIX',
    'pse': 'apmgw_PSE',
    'spei': 'apmgw_SPEI',
    'webpay': 'apmgw_Webpay',
}
```

### Special Handling Methods

**Integer-Only Methods**: Some payment methods require whole amounts:

```python
INTEGER_METHODS = ['webpay']
```

**Full Name Required**: Some methods require customer first and last names:

```python
FULL_NAME_METHODS = ['boleto']
```

## Technical Architecture

### Module Structure

```
payment_nuvei/
├── __init__.py
├── __manifest__.py
├── const.py                    # Constants: currencies, methods, signatures
├── controllers/
│   ├── __init__.py
│   └── main.py               # NuveiController - webhook & return handling
└── models/
    ├── __init__.py
    ├── payment_provider.py    # PaymentProvider extension
    └── payment_transaction.py # PaymentTransaction extension
```

### Data Flow

```
Customer Checkout (Latin America)
    │
    ▼
Odoo Payment Form
    │
    ├── Customer selects payment method
    ├── Method-specific data validation
    │   └── (e.g., full name for Boleto)
    │
    ▼
Nuvei API (purchase.do)
    │
    ├── HMAC-SHA256 signature generated
    ├── All required parameters sent
    │
    ▼
Customer Redirected to Nuvei
    │
    ├── Completes payment at Nuvei/institution
    │
    ▼
Return URL Processing
    │
    ├── Signature verification
    ├── Transaction state update
    │
    ▼
Webhook Confirmation (optional)
    │
    ├── Additional verification
    └── Final state confirmation
```

### Security: HMAC-SHA256 Signature

Nuvei uses HMAC-SHA256 signatures to authenticate all requests and webhook callbacks:

**Outgoing Request Signature**:

```python
def _nuvei_calculate_signature(self, data, incoming=True):
    signature_keys = const.SIGNATURE_KEYS if incoming else data.keys()
    sign_data = ''.join([str(data.get(k, '')) for k in signature_keys])
    key = self.nuvei_secret_key
    signing_string = f'{key}{sign_data}'
    return hashlib.sha256(signing_string.encode()).hexdigest()
```

**Incoming Webhook Verification**:

Webhook signatures are verified using specific keys:

```python
SIGNATURE_KEYS = [
    'totalAmount',
    'currency',
    'responseTimeStamp',
    'PPP_TransactionID',
    'Status',
    'productId',
]
```

## Provider Configuration Fields

### Core Fields

| Field | Type | Required | Groups | Description |
|-------|------|----------|--------|-------------|
| `code` | Selection | Yes | - | Fixed value: `nuvei` |
| `nuvei_merchant_identifier` | Char | Yes | - | Merchant account identifier |
| `nuvei_site_identifier` | Char | Yes | base.group_system | Site identifier code |
| `nuvei_secret_key` | Char | Yes | base.group_system | Secret key for HMAC signing |

### Field Details

**`nuvei_merchant_identifier`**

The merchant identifier is your Nuvei account identifier. It's visible in your Nuvei merchant dashboard and is required for all API calls.

**`nuvei_site_identifier`**

The site identifier represents a specific website/application in your Nuvei account. Different sites can have different configurations.

**`nuvei_secret_key`**

Used to calculate HMAC-SHA256 signatures for request authentication and webhook verification. This is the primary security mechanism.

### Configuration Steps

1. **Create Nuvei Account**: Contact Nuvei or visit [nuvei.com](https://www.nuvei.com)
2. **Obtain Credentials**:
   - Merchant Identifier
   - Site Identifier
   - Secret Key
3. **Configure Return URLs**:
   - Success URL: `/payment/nuvei/return`
   - Error URL: `/payment/nuvei/return`
   - Back URL: `/payment/nuvei/return`
   - Notify URL: `/payment/nuvei/webhook`
4. **Enter Credentials**: Input all credentials in Odoo provider configuration

## Models Extended

### `payment.provider` (Extended)

#### Field Extension

```python
code = fields.Selection(
    selection_add=[('nuvei', "Nuvei")],
    ondelete={'nuvei': 'set default'}
)
nuvei_merchant_identifier = fields.Char(...)
nuvei_site_identifier = fields.Char(...)
nuvei_secret_key = fields.Char(...)
```

#### Key Methods

**`_get_supported_currencies()`**

Filters currencies to Nuvei-supported set:

```python
def _get_supported_currencies(self):
    supported_currencies = super()._get_supported_currencies()
    if self.code == 'nuvei':
        supported_currencies = supported_currencies.filtered(
            lambda c: c.name in const.SUPPORTED_CURRENCIES
        )
    return supported_currencies
```

**`_nuvei_get_api_url()`**

Returns the appropriate API endpoint based on state:

```python
def _nuvei_get_api_url(self):
    if self.state == 'enabled':
        return 'https://secure.safecharge.com/ppp/purchase.do'
    else:  # 'test'
        return 'https://ppp-test.safecharge.com/ppp/purchase.do'
```

**`_nuvei_calculate_signature()`**

Computes HMAC-SHA256 signature for authentication:

```python
def _nuvei_calculate_signature(self, data, incoming=True):
    self.ensure_one()
    signature_keys = const.SIGNATURE_KEYS if incoming else data.keys()
    sign_data = ''.join([str(data.get(k, '')) for k in signature_keys])
    key = self.nuvei_secret_key
    signing_string = f'{key}{sign_data}'
    return hashlib.sha256(signing_string.encode()).hexdigest()
```

### `payment.transaction` (Extended)

#### Rendering Values

Builds the payment form parameters:

```python
def _get_specific_rendering_values(self, processing_values):
    if self.provider_code != 'nuvei':
        return super()._get_specific_rendering_values(processing_values)
    
    # Validate full name for certain payment methods
    if self.payment_method_code in const.FULL_NAME_METHODS:
        if not (first_name and last_name):
            raise UserError("Payment method requires first and last name")
    
    # Round amount for integer-only methods
    is_mandatory_integer_pm = self.payment_method_code in const.INTEGER_METHODS
    rounding = 0 if is_mandatory_integer_pm else self.currency_id.decimal_places
    rounded_amount = float_round(self.amount, rounding, rounding_method='DOWN')
    
    # Build URL parameters
    url_params = {
        'merchant_id': self.provider_id.nuvei_merchant_identifier,
        'merchant_site_id': self.provider_id.nuvei_site_identifier,
        'total_amount': rounded_amount,
        'currency': self.currency_id.name,
        'invoice_id': self.reference,
        # ... more parameters
    }
    
    # Calculate checksum
    checksum = self.provider_id._nuvei_calculate_signature(url_params, incoming=False)
    
    return {
        'api_url': self.provider_id._nuvei_get_api_url(),
        'checksum': checksum,
        'url_params': url_params,
    }
```

#### Amount Data Extraction

```python
def _extract_amount_data(self, payment_data):
    if self.provider_code != 'nuvei':
        return super()._extract_amount_data(payment_data)
    
    # Handle early return case
    if not payment_data:
        return
    
    rounding = 0 if self.payment_method_code in const.INTEGER_METHODS else \
               self.currency_id.decimal_places
    
    return {
        'amount': float(payment_data.get('totalAmount')),
        'currency_code': payment_data.get('currency'),
        'precision_digits': rounding,
    }
```

#### Payment Status Processing

Maps Nuvei statuses to Odoo transaction states:

```python
PAYMENT_STATUS_MAPPING = {
    'pending': ('pending',),
    'done': ('approved', 'ok'),
    'error': ('declined', 'error', 'fail'),
}
```

#### Updates Application

Updates transaction with payment details:

```python
def _apply_updates(self, payment_data):
    if self.provider_code != 'nuvei':
        return super()._apply_updates(payment_data)
    
    # Handle empty data (customer left page)
    if not payment_data:
        self._set_canceled(state_message=_("The customer left the payment page."))
        return
    
    # Update provider reference
    self.provider_reference = payment_data.get('TransactionID')
    
    # Update payment method
    payment_option = payment_data.get('payment_method', '')
    payment_method = self.env['payment.method']._get_from_code(
        payment_option, mapping=const.PAYMENT_METHODS_MAPPING
    )
    self.payment_method_id = payment_method or self.payment_method_id
    
    # Update state based on status
    status = payment_data.get('Status') or payment_data.get('ppp_status')
    # ... status mapping logic
```

## Controller Endpoints

### `NuveiController`

Located in `controllers/main.py`:

#### 1. Return Handler

**Route**: `/payment/nuvei/return`
**Method**: GET
**Auth**: Public

Processes customer return from Nuvei:

```python
@http.route(_return_url, type='http', auth='public', methods=['GET'])
def nuvei_return_from_checkout(self, tx_ref=None, error_access_token=None, **data):
    if tx_ref and error_access_token:
        _logger.warning("Nuvei errored on transaction: %s.", tx_ref)
    
    tx_data = data or {'invoice_id': tx_ref}
    tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference('nuvei', tx_data)
    if tx_sudo:
        self._verify_signature(tx_sudo, data, error_access_token=error_access_token)
        tx_sudo._process('nuvei', data)
    return request.redirect('/payment/status')
```

#### 2. Webhook Handler

**Route**: `/payment/nuvei/webhook`
**Method**: POST
**Auth**: Public
**CSRF**: Disabled

Receives payment notifications:

```python
@http.route(_webhook_url, type='http', auth='public', methods=['POST'], csrf=False)
def nuvei_webhook(self, **data):
    tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference('nuvei', data)
    if tx_sudo:
        self._verify_signature(tx_sudo, data)
        tx_sudo._process('nuvei', data)
    return 'OK'
```

### Signature Verification

Handles two scenarios:

1. **Payment went through**: Verify `advanceResponseChecksum`
2. **Error/Cancel**: Verify `error_access_token`

```python
@staticmethod
def _verify_signature(tx_sudo, payment_data, error_access_token=None):
    if error_access_token:  # Error case
        if not payment_utils.check_access_token(error_access_token, ref):
            raise Forbidden()
    else:  # Success case
        received_signature = payment_data.get('advanceResponseChecksum')
        expected_signature = tx_sudo.provider_id._nuvei_calculate_signature(
            payment_data, incoming=True,
        )
        if not consteq(received_signature, expected_signature):
            raise Forbidden()
```

## Payment Flows

### Flow 1: Credit Card Payment

```
1. Customer selects credit card
   │
   ▼
2. Nuvei.js tokenizes card on frontend
   │
   ▼
3. Odoo receives token
   │
   ▼
4. Odoo creates transaction with token
   │
   ▼
5. Customer redirected to Nuvei (if 3DS required)
   │
   ▼
6. Payment processed
   │
   ▼
7. Return URL or webhook confirms
   │
   ▼
8. Transaction state: done/pending/error
```

### Flow 2: Boleto (Brazil)

```
1. Customer selects Boleto
   │
   ▼
2. Odoo validates full name requirement
   │
   ▼
3. Boleto is generated by Nuvei
   │
   ▼
4. Customer downloads/prints Boleto
   │
   ▼
5. Customer pays at bank/online banking
   │
   ▼
6. Payment confirmed (may take 1-3 days)
   │
   ▼
7. Webhook confirms payment
   │
   ▼
8. Transaction state: done
```

### Flow 3: SPEI (Mexico)

```
1. Customer selects SPEI
   │
   ▼
2. Odoo creates transaction
   │
   ▼
3. SPEI reference generated
   │
   ▼
4. Customer makes transfer using reference
   │
   ▼
5. Bank confirms transfer
   │
   ▼
6. Webhook confirms payment
   │
   ▼
7. Transaction state: done
```

## Constants (`const.py`)

### Supported Currencies

```python
SUPPORTED_CURRENCIES = [
    'ARS', 'BRL', 'CAD', 'CLP', 'COP', 'MXN', 'PEN', 'USD', 'UYU',
]
```

### Default Payment Methods

```python
DEFAULT_PAYMENT_METHOD_CODES = {
    'card',
    'visa', 'mastercard', 'amex', 'discover',
    'tarjeta_mercadopago', 'naranja',
}
```

### Integer Methods

```python
INTEGER_METHODS = ['webpay']
```

### Full Name Methods

```python
FULL_NAME_METHODS = ['boleto']
```

### Payment Methods Mapping

```python
PAYMENT_METHODS_MAPPING = {
    'astropay': 'apmgw_Astropay_TEF',
    'boleto': 'apmgw_BOLETO',
    'card': 'cc_card',
    'nuvei_local': 'apmgw_Local_Payments',
    'oxxopay': 'apmgw_OXXO_PAY',
    'pix': 'apmgw_PIX',
    'pse': 'apmgw_PSE',
    'spei': 'apmgw_SPEI',
    'webpay': 'apmgw_Webpay',
}
```

### Signature Keys

```python
SIGNATURE_KEYS = [
    'totalAmount',
    'currency',
    'responseTimeStamp',
    'PPP_TransactionID',
    'Status',
    'productId',
]
```

### Payment Status Mapping

```python
PAYMENT_STATUS_MAPPING = {
    'pending': ('pending',),
    'done': ('approved', 'ok'),
    'error': ('declined', 'error', 'fail'),
}
```

## Feature Support

| Feature | Support Level | Notes |
|---------|--------------|-------|
| Express Checkout | No | Not implemented |
| Tokenization | No | Card tokenization not in current version |
| Manual Capture | No | Full capture only |
| Partial Capture | No | Not supported |
| Refund | Yes | Via standard Odoo refund flow |
| Partial Refund | Yes | Supported |
| Validation | Yes | Can validate payment details |

## Brazil: Boleto Payment

Boleto Bancario is Brazil's most popular cash payment method. Here's how it works:

### Customer Experience

1. Customer selects Boleto at checkout
2. Customer enters CPF (tax ID) and full name
3. Boleto is generated with a unique bar code
4. Customer pays via:
   - Online banking
   - ATM
   - Bank branch
   - Convenience store
5. Payment is processed (1-3 business days)
6. Merchant receives confirmation

### Technical Requirements

Boleto requires:
- Customer full name (first + last)
- Valid CPF or CNPJ for Brazilian customers
- Amount rounded to whole numbers

The module validates these requirements before generating the payment form.

## Mexico: SPEI and OXXO

### SPEI

SPEI (Sistema de Pagos Interbancarios) is Mexico's interbank electronic transfer system:

- Instant transfers between Mexican banks
- Unique CLABE reference for each transaction
- Available 24/7
- Low transaction fees

### OXXO

OXXO is Mexico's largest convenience store chain, offering cash payments:

- Customer prints payment voucher
- Pays cash at any OXXO store
- Payment confirmed within 24-48 hours
- Ideal for customers without bank accounts

## Security Considerations

### HMAC-SHA256 Signatures

All communication with Nuvei is authenticated using HMAC-SHA256 signatures:

1. **Request Signing**: Outgoing requests include a checksum
2. **Webhook Verification**: Incoming notifications are verified
3. **Replay Prevention**: Timestamps prevent replay attacks

### Sensitive Field Handling

The secret key is restricted to `base.group_system` to prevent unauthorized access.

### PCI-DSS Compliance

By using Nuvei:
- Card data never touches merchant servers
- PCI compliance is handled by Nuvei
- No need for SAQ-D certification

## Related

- [Modules/payment](payment.md) — Base payment engine and transaction processing
- [Modules/payment_flutterwave](payment_flutterwave.md) — African payment provider
- [Modules/payment_xendit](payment_xendit.md) — Southeast Asian payment provider
- [Modules/payment_demo](payment_demo.md) — Demo payment provider for testing
- [Modules/payment_custom](payment_custom.md) — Custom/wire transfer payment method
