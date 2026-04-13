---
Module: payment_razorpay
Version: Odoo 18
Type: Integration
---

# payment_razorpay — Razorpay Payment Provider

`payment_razorpay` integrates Odoo with **Razorpay**, an Indian payment gateway supporting INR and multiple international currencies. It covers card payments, netbanking, UPI, wallets, paylater, and EMI. Razorpay is the only provider in Odoo 18 that supports **UPI** and **eMandate** (recurring payments via autopay).

---

## Module Facts

| Attribute | Value |
|---|---|
| **Code** | `razorpay` |
| **Module Key** | `payment_razorpay` |
| **Depends** | `payment` |
| **License** | LGPL-3 |
| **API** | Razorpay REST API v1 (`https://api.razorpay.com/v1/`) |
| **Webhook URL** | `/payment/razorpay/webhook` |
| **Tokenization** | Yes (via tokenization for eMandate/recurring) |
| **Manual Capture** | Yes (`capture_manually` supported) |
| **Refund** | Partial (full + partial) |
| **Void** | **Not supported** — raises `UserError` |
| **Default Payment Methods** | `card`, `netbanking`, `upi`, `visa`, `mastercard`, `amex`, `discover` |
| **Supported Currencies** | 93+ currencies (see `const.SUPPORTED_CURRENCIES`); primary: INR |

---

## Provider Model: `payment.provider` (extends)

Path: `addons/payment_razorpay/models/payment_provider.py`

### Fields Added

| Field | Type | Required | Groups | Notes |
|---|---|---|---|---|
| `code` | Selection | — | — | Extended with `('razorpay', "Razorpay")` |
| `razorpay_key_id` | Char | Yes (if provider=`razorpay`) | — | Public key ID |
| `razorpay_key_secret` | Char | Yes (if provider=`razorpay`) | `base.group_system` | Private secret key |
| `razorpay_webhook_secret` | Char | Yes (if provider=`razorpay`) | `base.group_system` | For HMAC-SHA256 webhook signature verification |

### Feature Support

```python
def _compute_feature_support_fields(self):
    super()._compute_feature_support_fields()
    self.filtered(lambda p: p.code == 'razorpay').update({
        'support_manual_capture': 'full_only',  # Capture after auth
        'support_refund': 'partial',             # Partial refunds supported
        'support_tokenization': True,             # Token + eMandate
    })
```

### Key Methods

#### `_get_supported_currencies()`
Filters supported currencies to those in `const.SUPPORTED_CURRENCIES`:

```python
def _get_supported_currencies(self):
    supported_currencies = super()._get_supported_currencies()
    if self.code == 'razorpay':
        supported_currencies = supported_currencies.filtered(
            lambda c: c.name in const.SUPPORTED_CURRENCIES
        )
    return supported_currencies
```

Note: This filters by the provider's configured `available_currency_ids`, not by the raw Razorpay capability. A Razorpay account must be configured for the relevant currencies.

#### `_razorpay_make_request(endpoint, payload=None, method='POST')`
Makes authenticated HTTP requests to the Razorpay API:

```python
def _razorpay_make_request(self, endpoint, payload=None, method='POST'):
    self.ensure_one()
    api_version = self.env.context.get('razorpay_api_version', 'v1')
    url = f'https://api.razorpay.com/{api_version}/{endpoint}'
    auth = (self.razorpay_key_id, self.razorpay_key_secret)
    # Uses Basic Auth via requests' auth parameter
    # GET: requests.get(url, params=payload, auth=auth, timeout=10)
    # POST: requests.post(url, json=payload, auth=auth, timeout=10)
    # On HTTP error: raises ValidationError with Razorpay error description
    # On connection error: raises ValidationError "Could not establish connection"
```

#### `_razorpay_calculate_signature(data)`
Computes HMAC-SHA256 webhook signature for verification:

```python
def _razorpay_calculate_signature(self, data):
    secret = self.razorpay_webhook_secret
    if not secret:
        _logger.warning("Missing webhook secret; aborting signature calculation.")
        return None
    return hmac.new(secret.encode(), msg=data, digestmod=hashlib.sha256).hexdigest()
```

Used by the webhook controller to verify the `X-Razorpay-Signature` header.

#### `_get_validation_amount()`
```python
def _get_validation_amount(self):
    res = super()._get_validation_amount()
    if self.code != 'razorpay':
        return res
    return 1.0  # Flat INR 1 validation amount
```

#### `_get_default_payment_method_codes()`
Returns `{'card', 'netbanking', 'upi', 'visa', 'mastercard', 'amex', 'discover'}`.

---

## Transaction Model: `payment.transaction` (extends)

Path: `addons/payment_razorpay/models/payment_transaction.py`

### Key Methods

#### `_get_specific_processing_values(processing_values)`
Creates a Razorpay customer and order, returns data for the frontend JS:

```python
def _get_specific_processing_values(self, processing_values):
    res = super()._get_specific_processing_values(processing_values)
    if self.provider_code != 'razorpay':
        return res
    if self.operation in ('online_token', 'offline'):
        return {}

    customer_id = self._razorpay_create_customer()['id']
    order_id = self._razorpay_create_order(customer_id)['id']
    return {
        'razorpay_key_id': self.provider_id.razorpay_key_id,
        'razorpay_public_token': self.provider_id._razorpay_get_public_token(),
        'razorpay_customer_id': customer_id,
        'is_tokenize_request': self.tokenize,
        'razorpay_order_id': order_id,
    }
```

**Critical**: For token/offline payments, returns empty dict — no new order/customer needed.

#### `_razorpay_create_customer()`
```python
def _razorpay_create_customer(self):
    payload = {
        'name': self.partner_name,
        'email': self.partner_email or '',
        'contact': self.partner_phone and self._validate_phone_number(self.partner_phone) or '',
        'fail_existing': '0',  # Do not error if customer already exists
    }
    return self.provider_id._razorpay_make_request('customers', payload=payload)
```

- Phone number is validated and formatted via `_validate_phone_number()`
- `fail_existing: '0'` allows idempotent customer creation

#### `_validate_phone_number(phone)`
Validates and formats the customer's phone number:

```python
@api.model
def _validate_phone_number(self, phone):
    if not phone and self.tokenize:
        raise ValidationError("Razorpay: " + _("The phone number is missing."))
    try:
        phone = self._phone_format(
            number=phone, country=self.partner_country_id, raise_exception=self.tokenize
        )
    except Exception:
        raise ValidationError("Razorpay: " + _("The phone number is invalid."))
    return phone
```

#### `_razorpay_prepare_order_payload(customer_id=None)`
Builds the Razorpay Order payload:

```python
def _razorpay_prepare_order_payload(self, customer_id=None):
    converted_amount = payment_utils.to_minor_currency_units(self.amount, self.currency_id)
    pm_code = (self.payment_method_id.primary_payment_method_id or self.payment_method_id).code
    payload = {
        'amount': converted_amount,
        'currency': self.currency_id.name,
        **({'method': pm_code} if pm_code not in const.FALLBACK_PAYMENT_METHOD_CODES else {}),
    }
    if self.operation in ['online_direct', 'validation']:
        payload['customer_id'] = customer_id
        if self.tokenize:
            payload['token'] = {
                'max_amount': payment_utils.to_minor_currency_units(
                    self._razorpay_get_mandate_max_amount(), self.currency_id
                ),
                'expire_at': time.mktime((datetime.today() + relativedelta(years=10)).timetuple()),
                'frequency': 'as_presented',
            }
    else:  # 'online_token', 'offline'
        payload['payment_capture'] = not self.provider_id.capture_manually
    if self.provider_id.capture_manually:
        payload['payment'] = {
            'capture': 'manual',
            'capture_options': {
                'manual_expiry_period': 7200,   # 2 hours to capture
                'refund_speed': 'normal',
            }
        }
    return payload
```

**Key behavior**:
- Amount converted to **paise** (INR minor units) via `to_minor_currency_units()`
- For tokenization: creates a token with `max_amount` and 10-year expiry
- For manual capture: sets `capture: manual` with 2-hour capture window

#### `_razorpay_get_mandate_max_amount()`
Returns the maximum amount allowed on the tokenized eMandate:

```python
def _razorpay_get_mandate_max_amount(self):
    pm_code = (self.payment_method_id.primary_payment_method_id or self.payment_method_id).code
    pm_max_amount_INR = const.MANDATE_MAX_AMOUNT.get(pm_code, 100000)  # Default: 1L INR
    pm_max_amount = self._razorpay_convert_inr_to_currency(pm_max_amount_INR, self.currency_id)
    mandate_values = self._get_mandate_values()
    if 'amount' in mandate_values and 'MRR' in mandate_values:
        max_amount = min(pm_max_amount, max(mandate_values['amount'] * 1.5, mandate_values['MRR'] * 5))
    else:
        max_amount = pm_max_amount
    return max_amount
```

Uses `MANDATE_MAX_AMOUNT` from `const.py`:
```python
MANDATE_MAX_AMOUNT = {
    'card': 1000000,  # INR 10 lakhs
    'upi': 100000,    # INR 1 lakh
}
```

#### `_send_payment_request()`
Sends a recurring/token payment request. Includes a 36-hour cooldown check:

```python
def _send_payment_request(self):
    super()._send_payment_request()
    if self.provider_code != 'razorpay':
        return
    if not self.token_id:
        raise UserError("Razorpay: " + _("The transaction is not linked to a token."))

    # 36-hour anti-duplicate protection
    reference_prefix = re.sub(r'-(?!.*-).*$', '', self.reference) or self.reference
    earlier_pending_tx = self.search([
        ('provider_code', '=', 'razorpay'),
        ('state', '=', 'pending'),
        ('token_id', '=', self.token_id.id),
        ('operation', 'in', ['online_token', 'offline']),
        ('reference', '=like', f'{reference_prefix}%'),
        ('create_date', '>=', fields.Datetime.now() - relativedelta(hours=36)),
        ('id', '!=', self.id),
    ], limit=1)
    if earlier_pending_tx:
        raise UserError("Razorpay: " + _("Your last payment with reference %s will soon be processed. "
            "Please wait up to 24 hours before trying again."))

    order_data = self._razorpay_create_order()
    phone = self._validate_phone_number(self.partner_phone)
    customer_id, token_id = self.token_id.provider_ref.split(',')
    payload = {
        'email': self.partner_email,
        'contact': phone,
        'amount': order_data['amount'],
        'currency': self.currency_id.name,
        'order_id': order_data['id'],
        'customer_id': customer_id,
        'token': token_id,
        'description': self.reference,
        'recurring': '1',
    }
    recurring_payment_data = self.provider_id._razorpay_make_request(
        'payments/create/recurring', payload=payload
    )
    self._handle_notification_data('razorpay', recurring_payment_data)
```

**L4 Note**: The 36-hour window exists because RBI regulations allow Razorpay to take up to 24 hours to process a payment. Prevents double-charging during that window.

#### `_send_capture_request(amount_to_capture=None)`
```python
def _send_capture_request(self, amount_to_capture=None):
    child_capture_tx = super()._send_capture_request(amount_to_capture=amount_to_capture)
    if self.provider_code != 'razorpay':
        return child_capture_tx
    converted_amount = payment_utils.to_minor_currency_units(self.amount, self.currency_id)
    response_content = self.provider_id._razorpay_make_request(
        f'payments/{self.provider_reference}/capture',
        payload={'amount': converted_amount, 'currency': self.currency_id.name}
    )
    self._handle_notification_data('razorpay', response_content)
    return child_capture_tx
```

#### `_send_void_request(amount_to_void=None)`
```python
def _send_void_request(self, amount_to_void=None):
    child_void_tx = super()._send_void_request(amount_to_void=amount_to_void)
    if self.provider_code != 'razorpay':
        return child_void_tx
    raise UserError(_("Transactions processed by Razorpay can't be manually voided from Odoo."))
```

**Critical**: Razorpay does not support voiding. Once authorized, a payment must be captured or left to expire (automatic after the `manual_expiry_period`).

#### `_send_refund_request(amount_to_refund=None)`
```python
def _send_refund_request(self, amount_to_refund=None):
    refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
    if self.provider_code != 'razorpay':
        return refund_tx
    converted_amount = payment_utils.to_minor_currency_units(
        -refund_tx.amount, refund_tx.currency_id  # Negative for refunds
    )
    payload = {
        'amount': converted_amount,
        'notes': {'reference': refund_tx.reference},
    }
    response_content = refund_tx.provider_id._razorpay_make_request(
        f'payments/{self.provider_reference}/refund', payload=payload
    )
    response_content.update(entity_type='refund')
    refund_tx._handle_notification_data('razorpay', response_content)
    return refund_tx
```

#### `_get_tx_from_notification_data(provider_code, notification_data)`
Handles both payment and refund entity types:

```python
def _get_tx_from_notification_data(self, provider_code, notification_data):
    # ...
    entity_type = notification_data.get('entity_type', 'payment')
    if entity_type == 'payment':
        reference = notification_data.get('description')
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'razorpay')])
    else:  # 'refund'
        notes = notification_data.get('notes')
        reference = notes.get('reference') if isinstance(notes, dict) else None
        if reference:  # Odoo-initiated refund
            tx = self.search([('reference', '=', reference), ('provider_code', '=', 'razorpay')])
        else:  # Razorpay-initiated refund (e.g., dispute)
            source_tx = self.search([
                ('provider_reference', '=', notification_data['payment_id']),
                ('provider_code', '=', 'razorpay'),
            ])
            if source_tx:
                tx = self._razorpay_create_refund_tx_from_notification_data(source_tx, notification_data)
```

#### `_process_notification_data(notification_data)`
Maps Razorpay payment statuses to Odoo states:

| Razorpay Status | Odoo State | Notes |
|---|---|---|
| `created`, `pending` | `_set_pending()` | Payment initiated |
| `authorized` | `_set_authorized()` | Only if `capture_manually=True` |
| `captured`, `refunded`, `processed` | `_set_done()` | Captured; `refunded` here means Odoo-initiated refund is done |
| `failed` | `_set_error()` | Payment failed |

Special behavior:
- If `token_id` is missing but `token_id` exists in response + `allow_tokenization=True`: auto-tokenizes via `_razorpay_tokenize_from_notification_data()`
- For refund transactions (`operation == 'refund'`): immediately triggers post-processing cron

#### `_razorpay_tokenize_from_notification_data(notification_data)`
Creates a `payment.token` from the payment entity data:

```python
def _razorpay_tokenize_from_notification_data(self, notification_data):
    # Extract details based on payment method:
    # card: last4 from notification_data['card']['last4']
    # upi: vpa from '@' onwards
    # others: pm_code
    token = self.env['payment.token'].create({
        'provider_id': self.provider_id.id,
        'payment_method_id': self.payment_method_id.id,
        'payment_details': details,
        'partner_id': self.partner_id.id,
        # provider_ref stores both Razorpay customer_id and token_id
        'provider_ref': f'{notification_data["customer_id"]},{notification_data["token_id"]}',
    })
    self.write({'token_id': token, 'tokenize': False})
```

**L4 Note**: The `provider_ref` stores `customer_id,token_id` as a comma-separated string. When charging the token later (`_send_payment_request`), it splits this back: `customer_id, token_id = self.token_id.provider_ref.split(',')`.

---

## Token Model: `payment.token` (extends)

Path: `addons/payment_razorpay/models/payment_token.py`

### Additional Method

#### `_razorpay_get_limit_exceed_warning(amount, currency_id)`
Returns a warning message when the payment amount exceeds the mandate's `max_amount`:

```python
def _razorpay_get_limit_exceed_warning(self, amount, currency_id):
    if not amount or self.provider_code != 'razorpay':
        return ""
    # Try to get max amount from the source transaction
    primary_tx = Transaction.search(
        [('token_id', '=', self.id), ('operation', 'not in', ['offline', 'online_token'])],
        limit=1,
    )
    if primary_tx:
        mandate_max_amount = primary_tx._razorpay_get_mandate_max_amount()
    else:
        pm = self.payment_method_id.primary_payment_method_id or self.payment_method_id
        mandate_max_amount_INR = const.MANDATE_MAX_AMOUNT.get(pm.code, 1000000)
        mandate_max_amount = Transaction._razorpay_convert_inr_to_currency(
            mandate_max_amount_INR, currency_id
        )
    if amount > mandate_max_amount:
        return _("You can not pay amounts greater than %s %s with this payment method",
                 currency_id.symbol, float_round(mandate_max_amount, precision_digits=0))
    return ""
```

---

## Webhook Controller: `RazorpayController`

Path: `addons/payment_razorpay/controllers/main.py`

### Webhook Endpoint

| Route | Method | Auth | Type |
|---|---|---|---|
| `/payment/razorpay/webhook` | POST | `public` | `http` |

### Handled Events

Defined in `const.py`:
```python
HANDLED_WEBHOOK_EVENTS = [
    'payment.authorized',   # Capture triggered from capture request
    'payment.captured',    # Auto-capture completed
    'payment.failed',      # Payment failed
    'refund.failed',       # Refund failed at Razorpay side
    'refund.processed',    # Refund completed
]
```

### `razorpay_webhook()`
```python
@route(_webhook_url, type='http', methods=['POST'], auth='public', csrf=False)
def razorpay_webhook(self):
    data = request.get_json_data()
    event_type = data['event']
    if event_type in HANDLED_WEBHOOK_EVENTS:
        entity_type = 'payment' if 'payment' in event_type else 'refund'
        try:
            entity_data = data['payload'].get(entity_type, {}).get('entity', {})
            entity_data.update(entity_type=entity_type)

            # Verify HMAC signature
            received_signature = request.httprequest.headers.get('X-Razorpay-Signature')
            tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
                'razorpay', entity_data
            )
            self._verify_notification_signature(
                request.httprequest.data, received_signature, tx_sudo
            )

            tx_sudo._handle_notification_data('razorpay', entity_data)
        except ValidationError:  # Acknowledge to avoid spam
            _logger.exception("Unable to handle the notification data; skipping to acknowledge")
    return request.make_json_response('')  # Always acknowledge
```

**L4 Note**: Returns HTTP 200 (empty string) even on errors — Razorpay interprets 4xx/5xx as delivery failures and retries indefinitely. Acknowledging prevents webhook storms.

### `_verify_notification_signature(notification_data, received_signature, tx_sudo)`
HMAC-SHA256 verification:
1. Reads raw `request.httprequest.data` (raw bytes, not parsed JSON)
2. Computes `hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()`
3. Compares with `X-Razorpay-Signature` header via `hmac.compare_digest()` (timing-safe)
4. Raises `Forbidden()` if missing or mismatched

---

## Constants: `const.py`

### Supported Currencies
93 currencies including INR (primary), USD, EUR, GBP, AED, AUD, etc.

### `FALLBACK_PAYMENT_METHOD_CODES`
```python
FALLBACK_PAYMENT_METHOD_CODES = {
    'wallets_india',    # Razorpay wallets (not in orders API)
    'paylater_india',   # PayLater
    'emi_india',        # EMI
}
```
These are **excluded** from the Razorpay Order `method` field because the Orders API doesn't support them directly.

### `PAYMENT_STATUS_MAPPING`
```python
PAYMENT_STATUS_MAPPING = {
    'pending': ('created', 'pending'),
    'authorized': ('authorized',),
    'done': ('captured', 'refunded', 'processed'),  # refunded = refund completed
    'error': ('failed',),
}
```

### `MANDATE_MAX_AMOUNT`
```python
MANDATE_MAX_AMOUNT = {
    'card': 1000000,  # INR 10 lakhs
    'upi': 100000,    # INR 1 lakh
}
```

---

## Payment Flow: Full Lifecycle

### Direct Payment (Card, UPI, Netbanking)

```
1. Customer selects Razorpay at checkout
2. _get_specific_processing_values()
   → _razorpay_create_customer()     → POST /customers
   → _razorpay_create_order()        → POST /orders  (amount in paise)
   → returns { razorpay_key_id, razorpay_customer_id, razorpay_order_id, is_tokenize_request }
3. Frontend JS uses Razorpay.js to render payment form
4. Customer completes payment in browser
5. Razorpay.js calls /payments/{order_id} internally
6. On success: frontend receives razorpay_payment_id
7. Odoo backend receives webhook: payment.authorized / payment.captured
   → _get_tx_from_notification_data() → finds tx by reference in description
   → _process_notification_data()    → maps status to Odoo state
   → If tokenize: _razorpay_tokenize_from_notification_data() → creates payment.token
```

### Manual Capture Flow

```
1. _razorpay_prepare_order_payload(): sets capture='manual' on order
2. Payment authorized (not captured) → tx._set_authorized()
3. Merchant clicks "Capture" → _send_capture_request()
   → POST /payments/{provider_reference}/capture
   → Webhook fires: payment.authorized
   → tx._set_done()
```

### Token/Recurring Payment (eMandate)

```
1. Customer enables autopay at checkout (tokenize=True)
2. Frontend receives token_id after payment success
3. _razorpay_tokenize_from_notification_data() creates payment.token
   → provider_ref = 'customer_id,token_id'
4. On next order: _send_payment_request()
   → POST /payments/create/recurring
   → 36-hour anti-duplicate check
   → customer_id + token_id from provider_ref
5. Webhook: payment.authorized or payment.captured
```

### Refund Flow

```
1. Merchant clicks "Refund" → _send_refund_request()
   → POST /payments/{provider_reference}/refund
   → response has entity_type='refund'
2. _handle_notification_data('razorpay', response_content)
3. tx._set_done()
4. cron_post_process_payment_tx triggered immediately (since no browsing)
```

---

## L4: Key Architecture Decisions

### 1. Webhook-First Architecture
Unlike Authorize.Net (client-polling), Razorpay uses **webhooks** as the primary notification mechanism. The `/payment/razorpay/webhook` endpoint must be:
- Accessible from the public internet
- Acknowledged with HTTP 200 even on processing errors
- HMAC-verified to prevent spoofed notifications

### 2. Orders API + Customer Object
Razorpay requires creating an Order before accepting payment. The integration:
- Creates a `customer` object at Razorpay for every payment
- Creates an `order` object linked to that customer
- The order's `description` field carries the Odoo `reference` for webhook correlation
- For token payments, the order is created fresh each time but charged to the stored token

### 3. Minor Currency Units (Paise)
Razorpay operates in paise (1/100th of INR). The `payment_utils.to_minor_currency_units()` converts Odoo's float amounts:
```python
converted_amount = payment_utils.to_minor_currency_units(self.amount, self.currency_id)
```

### 4. UPI Mandate Limits
UPI mandates have a lower `MANDATE_MAX_AMOUNT` (INR 1 lakh vs. INR 10 lakhs for cards). The `_razorpay_get_mandate_max_amount()` computes the per-transaction ceiling based on:
- Payment method type (card vs. UPI)
- Document mandate values (`amount * 1.5` or `MRR * 5`, whichever is higher, capped at the payment method limit)

### 5. No Void — Automatic Expiry
Razorpay does not support voiding authorized payments. The authorization automatically expires after `manual_expiry_period` (set to 7200 seconds = 2 hours in the order payload). The `_send_void_request()` explicitly raises a `UserError` to prevent merchant confusion.

### 6. `provider_ref` Stores Two IDs
The `payment.token.provider_ref` for Razorpay stores `'{razorpay_customer_id},{razorpay_token_id}'` (comma-separated). This is split during `_send_payment_request()`. This is distinct from Authorize.Net's two-field approach (profile + payment_profile_id).

### 7. Tokenization on Success, Not Upfront
Razorpay tokenization works by:
1. Including a `token` block in the Order payload (with `max_amount`, `expire_at`, `frequency`)
2. On successful payment, Razorpay creates the token and returns `token_id` in the webhook payload
3. Odoo creates the `payment.token` record from the webhook data

This means tokens are only created after a successful first payment.

### 8. RBI Compliance: 36-Hour Anti-Duplicate Window
Per RBI guidelines (notification ID 11668), Razorpay can take up to 24 hours to process a payment. The 36-hour window in `_send_payment_request()` prevents duplicate charges for the same recurring payment.

---

## Hooks

```python
def post_init_hook(env):
    setup_provider(env, 'razorpay')

def uninstall_hook(env):
    reset_payment_provider(env, 'razorpay')
```

---

## Related Documentation

- [Core/Payment Framework](core/payment-framework.md) — base payment architecture
- [Modules/payment](modules/payment.md) — core payment module
- [Modules/payment-custom](modules/payment-custom.md) — manual wire transfer provider
- [Modules/payment-authorize](modules/payment-authorize.md) — Authorize.Net provider (client-driven, no webhooks)

---

**Tags:** #odoo #odoo18 #payment #razorpay #india #upi #mandate #integration
