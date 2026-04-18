---
uuid: a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d
tags:
  - odoo
  - odoo19
  - modules
  - payment
  - payment-provider
  - xendit
  - southeast-asia
  - indonesia
  - philippines
---

# Payment Xendit (`payment_xendit`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Xendit |
| **Technical** | `payment_xendit` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `payment` |
| **Version** | 1.0 |

## Description

Xendit is a Southeast Asian payment gateway that provides a unified API for accepting payments across Indonesia, Philippines, Vietnam, Thailand, and Malaysia. The module integrates with Xendit's comprehensive payment platform, supporting credit/debit cards, e-wallets, bank transfers, and various local payment methods.

Xendit has become a dominant payment processor in Southeast Asia, particularly in Indonesia where it supports the most popular local payment methods including OVO, DANA, LinkAja, GoPay, and QRIS. The Odoo integration allows merchants to:

- Accept payments from customers using their preferred local methods
- Process card payments with tokenization support
- Handle refunds and disputes through Odoo
- Access comprehensive transaction reporting

The module supports a wide range of payment methods that would otherwise require separate integrations, making it ideal for businesses operating in or expanding to Southeast Asian markets.

## Geographic Coverage

### Supported Countries and Currencies

| Country | Currency | Code | Primary Payment Methods |
|---------|----------|------|------------------------|
| Indonesia | Indonesian Rupiah | IDR | OVO, DANA, LinkAja, GoPay, QRIS, Card |
| Philippines | Philippine Peso | PHP | GCash, Maya (PayMaya), Card |
| Vietnam | Vietnamese Dong | VND | Appota, ZaloPay, VNPT Wallet |
| Thailand | Thai Baht | THB | LINE Pay, ShopeePay, PromptPay, SCB |
| Malaysia | Malaysian Ringgit | MYR | FPX, Touch 'n Go, Card |

### Currency Decimal Handling

Xendit requires specific decimal handling for certain currencies. The module implements custom rounding:

```python
CURRENCY_DECIMALS = {
    'IDR': 0,  # No decimals
    'MYR': 0,  # No decimals
    'PHP': 0,  # No decimals
    'THB': 0,  # No decimals
    'VND': 0,  # No decimals
}
```

These currencies do not use decimal places - amounts must be whole numbers. The `_get_rounded_amount()` method ensures correct formatting.

## Payment Methods

### Indonesia (IDR)

- **Card**: Visa, Mastercard, JCB
- **E-Wallet**: OVO, DANA, LinkAja, GoPay
- **QR Code**: QRIS (national QR standard)
- **Bank Transfer**: BCA, Permata, BRI, BNI, Mandiri

### Philippines (PHP)

- **Card**: Visa, Mastercard
- **E-Wallet**: GCash, Maya (PayMaya)

### Vietnam (VND)

- **E-Wallet**: Appota, ZaloPay, VNPT Wallet

### Thailand (THB)

- **E-Wallet**: LINE Pay, ShopeePay
- **QR Code**: PromptPay
- **Bank**: SCB, Krungthai, Bangkok Bank

### Malaysia (MYR)

- **Bank Transfer**: FPX (supporting 20+ banks)
- **E-Wallet**: Touch 'n Go
- **Card**: Visa, Mastercard

### FPX Bank List

Xendit supports FPX with 20+ Malaysian banks through a unified integration. The module handles mapping for:

```python
FPX_METHODS = [
    "DD_UOB_FPX", "DD_PUBLIC_FPX", "DD_AFFIN_FPX", "DD_AGRO_FPX",
    "DD_ALLIANCE_FPX", "DD_AMBANK_FPX", "DD_ISLAM_FPX", "DD_MUAMALAT_FPX",
    "DD_BOC_FPX", "DD_RAKYAT_FPX", "DD_BSN_FPX", "DD_CIMB_FPX",
    "DD_HLB_FPX", "DD_HSBC_FPX", "DD_KFH_FPX", "DD_MAYB2U_FPX",
    "DD_OCBC_FPX", "DD_RHB_FPX", "DD_SCH_FPX",
    "AFFIN_FPX_BUSINESS", "AGRO_FPX_BUSINESS", "ALLIANCE_FPX_BUSINESS",
    # ... more business accounts
]
```

## Technical Architecture

### Module Structure

```
payment_xendit/
├── __init__.py
├── __manifest__.py
├── const.py                    # Constants: currencies, methods, mappings
├── controllers/
│   ├── __init__.py
│   └── main.py               # XenditController - webhook & payment handling
└── models/
    ├── __init__.py
    ├── payment_provider.py    # PaymentProvider extension
    └── payment_transaction.py # PaymentTransaction extension
```

### Data Flow

```
Customer Checkout (Southeast Asia)
    │
    ▼
Odoo Payment Form
    │
    ├── For Cards: Tokenization flow
    │   ├── Token generated on frontend
    │   └── Charged via API
    │
    ├── For E-Wallets/QR: Invoice flow
    │   ├── Invoice created via API
    │   ├── Customer redirected to pay
    │   └── Webhook confirms payment
    │
    ▼
Xendit API Processing
    │
    ▼
Webhook Notification to Odoo
    │
    ├── Payment verified
    ├── Transaction state updated
    └── Order processing triggered
```

### API Integration

Xendit API Base URL: `https://api.xendit.co/`

**Authentication**: Basic Auth using secret key
```python
def _build_request_auth(self, **kwargs):
    if self.code != 'xendit':
        return super()._build_request_auth(**kwargs)
    return self.xendit_secret_key, ''  # Basic auth: secret_key:''
```

## Provider Configuration Fields

### Core Fields

| Field | Type | Required | Groups | Description |
|-------|------|----------|--------|-------------|
| `code` | Selection | Yes | - | Fixed value: `xendit` |
| `xendit_public_key` | Char | Yes | base.group_system | For frontend tokenization |
| `xendit_secret_key` | Char | Yes | base.group_system | For server-side API calls |
| `xendit_webhook_token` | Char | Yes | base.group_system | For webhook verification |

### Field Details

**`xendit_public_key`**

Used by the frontend JavaScript to tokenize card details. This key is safe to expose in the browser.

**`xendit_secret_key`**

Used server-side for all API calls. This key must be kept secret and is restricted to the `base.group_system` group.

**`xendit_webhook_token`**

Used to verify that webhook requests originate from Xendit. This is sent as a header in webhook callbacks.

### Configuration Steps

1. **Create Xendit Account**: Register at [xendit.co](https://xendit.co)
2. **Obtain API Keys**: Get public and secret keys from Xendit dashboard
3. **Configure Webhook**:
   - URL: `https://your-odoo.com/payment/xendit/webhook`
   - Events: Payment successful, Payment failed, etc.
4. **Copy Webhook Token**: Get the callback token from Xendit dashboard
5. **Enter Credentials**: Input all keys in Odoo provider configuration

## Models Extended

### `payment.provider` (Extended)

#### Field Extension

```python
code = fields.Selection(
    selection_add=[('xendit', "Xendit")],
    ondelete={'xendit': 'set default'}
)
xendit_public_key = fields.Char(...)
xendit_secret_key = fields.Char(...)
xendit_webhook_token = fields.Char(...)
```

#### Key Methods

**`_compute_feature_support_fields()`**

Enables tokenization for Xendit (required for card payments):

```python
def _compute_feature_support_fields(self):
    super()._compute_feature_support_fields()
    self.filtered(lambda p: p.code == 'xendit').support_tokenization = True
```

**`_get_supported_currencies()`**

Filters currencies to Xendit-supported set:

```python
def _get_supported_currencies(self):
    supported_currencies = super()._get_supported_currencies()
    if self.code == 'xendit':
        supported_currencies = supported_currencies.filtered(
            lambda c: c.name in const.SUPPORTED_CURRENCIES
        )
    return supported_currencies
```

**`_get_redirect_form_view()`**

Returns `None` for validation operations to prevent rendering issues:

```python
def _get_redirect_form_view(self, is_validation=False):
    if self.code == 'xendit' and is_validation:
        return None
    return super()._get_redirect_form_view(is_validation)
```

**`_build_request_url()`**

Constructs Xendit API URLs:

```python
def _build_request_url(self, endpoint, **kwargs):
    if self.code != 'xendit':
        return super()._build_request_url(endpoint, **kwargs)
    return f'https://api.xendit.co/{endpoint}'
```

**`_build_request_auth()`**

Configures Basic Auth for Xendit:

```python
def _build_request_auth(self, **kwargs):
    if self.code != 'xendit':
        return super()._build_request_auth(**kwargs)
    return self.xendit_secret_key, ''
```

### `payment.transaction` (Extended)

#### Amount Rounding

Xendit requires special decimal handling for Southeast Asian currencies:

```python
def _get_rounded_amount(self):
    decimal_places = const.CURRENCY_DECIMALS.get(
        self.currency_id.name, self.currency_id.decimal_places
    )
    return float_round(self.amount, decimal_places, rounding_method='DOWN')
```

#### Rendering Values for Non-Card Methods

For e-wallets and bank transfers, the module creates an invoice:

```python
def _get_specific_rendering_values(self, processing_values):
    if self.provider_code != 'xendit' or self.payment_method_code == 'card':
        return res
    
    payload = self._xendit_prepare_invoice_request_payload()
    invoice_data = self._send_api_request('POST', 'v2/invoices', json=payload)
    return {'api_url': invoice_data.get('invoice_url')}
```

#### Invoice Request Payload

```python
def _xendit_prepare_invoice_request_payload(self):
    payload = {
        'external_id': self.reference,
        'amount': self._get_rounded_amount(),
        'description': self.reference,
        'customer': {
            'given_names': self.partner_name,
        },
        'success_redirect_url': f'{redirect_url}?{success_url_params}',
        'failure_redirect_url': redirect_url,
        'payment_methods': [const.PAYMENT_METHODS_MAPPING.get(
            self.payment_method_code, self.payment_method_code.upper())
        ],
        'currency': self.currency_id.name,
    }
```

#### Card Token Charges

For card payments with tokenization:

```python
def _xendit_create_charge(self, token_ref, auth_id=None):
    payload = {
        'token_id': token_ref,
        'external_id': self.reference,
        'amount': self._get_rounded_amount(),
        'currency': self.currency_id.name,
    }
    if auth_id:
        payload['authentication_id'] = auth_id
    if self.token_id or self.tokenize:
        payload['is_recurring'] = True
```

#### Payment Status Processing

Maps Xendit statuses to Odoo transaction states:

```python
PAYMENT_STATUS_MAPPING = {
    'draft': (),
    'pending': ('PENDING',),
    'done': ('SUCCEEDED', 'PAID', 'CAPTURED'),
    'cancel': ('CANCELLED', 'EXPIRED'),
    'error': ('FAILED',)
}
```

## Controller Endpoints

### `XenditController`

Located in `controllers/main.py`:

#### 1. Payment Endpoint (JSON-RPC)

**Route**: `/payment/xendit/payment`
**Type**: JSON-RPC
**Auth**: Public

Handles token-based payments from the frontend:

```python
@http.route('/payment/xendit/payment', type='jsonrpc', auth='public')
def xendit_payment(self, reference, token_ref, auth_id=None):
    tx_sudo = request.env['payment.transaction'].sudo().search([
        ('reference', '=', reference)
    ])
    tx_sudo._xendit_create_charge(token_ref, auth_id=auth_id)
```

#### 2. Webhook Handler

**Route**: `/payment/xendit/webhook`
**Method**: POST
**Auth**: Public
**CSRF**: Disabled

Receives payment notifications from Xendit:

```python
@http.route(_webhook_url, type='http', methods=['POST'], auth='public', csrf=False)
def xendit_webhook(self):
    data = request.get_json_data()
    received_token = request.httprequest.headers.get('x-callback-token')
    tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference('xendit', data)
    if tx_sudo:
        self._verify_notification_token(received_token, tx_sudo)
        tx_sudo._process('xendit', data)
    return request.make_json_response(['accepted'], status=200)
```

#### 3. Return Handler

**Route**: `/payment/xendit/return`
**Method**: GET
**Auth**: Public

Handles customer return after payment:

```python
@http.route(_return_url, type='http', methods=['GET'], auth='public')
def xendit_return(self, tx_ref=None, success=False, access_token=None, **data):
    if access_token and str2bool(success, default=False):
        tx_sudo = request.env['payment.transaction'].sudo().search([...])
        if tx_sudo and payment_utils.check_access_token(access_token, tx_ref, tx_sudo.amount):
            tx_sudo._set_pending()
    return request.redirect('/payment/status')
```

### Webhook Security

Webhook authenticity is verified using the `x-callback-token` header:

```python
def _verify_notification_token(self, received_token, tx_sudo):
    if not consteq(tx_sudo.provider_id.xendit_webhook_token, received_token):
        raise Forbidden()
```

## Payment Flows

### Flow 1: E-Wallet Payment (Redirect)

```
1. Customer selects e-wallet (OVO, DANA, GCash, etc.)
   │
   ▼
2. Odoo creates Xendit invoice via API
   │
   ▼
3. Customer redirected to Xendit/institution checkout
   │
   ▼
4. Customer completes payment in e-wallet app
   │
   ▼
5. Webhook notification sent to Odoo
   │
   ▼
6. Transaction state: done
```

### Flow 2: Card Tokenization

```
1. Customer enters card details on frontend
   │
   ▼
2. Frontend tokenizes via Xendit.js
   │
   ▼
3. Token sent to Odoo
   │
   ▼
4. Odoo charges token via Xendit API
   │
   ▼
5. Webhook confirms charge
   │
   ▼
6. Transaction state: done
```

### Flow 3: QRIS (Indonesia)

```
1. Customer selects QRIS payment
   │
   ▼
2. Odoo creates invoice
   │
   ▼
3. QR code generated by Xendit
   │
   ▼
4. Customer scans with any bank/e-wallet app
   │
   ▼
5. Payment confirmed via webhook
   │
   ▼
6. Transaction state: done
```

## Constants (`const.py`)

### Supported Currencies

```python
SUPPORTED_CURRENCIES = ['IDR', 'MYR', 'PHP', 'THB', 'VND']
```

### Currency Decimal Places

```python
CURRENCY_DECIMALS = {
    'IDR': 0,
    'MYR': 0,
    'PHP': 0,
    'THB': 0,
    'VND': 0,
}
```

### Default Payment Methods

```python
DEFAULT_PAYMENT_METHOD_CODES = {
    'card', 'dana', 'ovo', 'qris',  # ID
    'fpx', 'touch_n_go',            # MY
    'promptpay', 'linepay', 'shopeepay',  # TH
    'appota', 'zalopay', 'vnptwallet',   # VN
    'visa', 'mastercard',  # Brands
}
```

### Payment Method Mappings

```python
PAYMENT_METHODS_MAPPING = {
    'bank_bca': 'BCA',
    'bank_permata': 'PERMATA',
    'bpi': 'DD_BPI',
    'card': 'CREDIT_CARD',
    'maya': 'PAYMAYA',
    'wechat_pay': 'WECHATPAY',
    'scb': 'DD_SCB_MB',
    'krungthai_bank': 'DD_KTB_MB',
    'bangkok_bank': 'DD_BBL_MB',
    'touch_n_go': 'TOUCHNGO',
    **{method: 'fpx' for method in FPX_METHODS}  # All FPX banks map to 'fpx'
}
```

### Payment Status Mapping

```python
PAYMENT_STATUS_MAPPING = {
    'draft': (),
    'pending': ('PENDING',),
    'done': ('SUCCEEDED', 'PAID', 'CAPTURED'),
    'cancel': ('CANCELLED', 'EXPIRED'),
    'error': ('FAILED',)
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
| Validation | No | Returns None for validation views |

## Indonesia: QRIS Support

QRIS (Quick Response Code Indonesian Standard) is a national QR code standard that allows customers to pay using any participating bank's app or e-wallet. Xendit supports QRIS as a unified payment method.

### How QRIS Works

1. Customer selects QRIS at checkout
2. Odoo creates an invoice with QRIS payment method
3. Xendit returns a QR code
4. Customer scans the QR code with any bank/e-wallet app
5. Payment is processed and confirmed via webhook

This is particularly popular in Indonesia as it:
- Works with all major banks and e-wallets
- No need for separate integrations
- Low transaction fees
- Instant settlement

## Related

- [Modules/payment](Modules/payment.md) — Base payment engine and transaction processing
- [Modules/payment_flutterwave](Modules/payment_flutterwave.md) — African payment provider
- [Modules/payment_nuvei](Modules/payment_nuvei.md) — Latin American payment provider
- [Modules/payment_demo](Modules/payment_demo.md) — Demo payment provider for testing
- [Modules/payment_custom](Modules/payment_custom.md) — Custom/wire transfer payment method
