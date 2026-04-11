---
Module: payment_authorize
Version: Odoo 18
Type: Integration
---

# payment_authorize — Authorize.Net Payment Provider

`payment_authorize` integrates Odoo with **Authorize.Net** (a US-based payment gateway covering the US, Australia, and Canada). It supports card payments (Visa, Mastercard, Amex, Discover), ACH direct debit, tokenization, manual capture, and full refunds.

---

## Module Facts

| Attribute | Value |
|---|---|
| **Code** | `authorize` |
| **Module Key** | `payment_authorize` |
| **Depends** | `payment` |
| **License** | LGPL-3 |
| **API** | Authorize.Net XML API v1 |
| **API Endpoint** | `https://api.authorize.net/xml/v1/request.api` (live) / `https://apitest.authorize.net/xml/v1/request.api` (test) |
| **Tokenization** | Yes (Customer Profiles + Payment Profiles) |
| **Manual Capture** | Yes (`capture_manually` supported) |
| **Refund** | Full + partial |
| **Void** | Yes (before settlement) |
| **Default Payment Methods** | `ach_direct_debit`, `card`, `visa`, `mastercard`, `amex`, `discover` |
| **Currency** | **One currency per provider account** — constraint enforced |

---

## Provider Model: `payment.provider` (extends)

Path: `addons/payment_authorize/models/payment_provider.py`

### Fields Added

| Field | Type | Required | Groups | Notes |
|---|---|---|---|---|
| `code` | Selection | — | — | Extended with `('authorize', 'Authorize.Net')` |
| `authorize_login` | Char | Yes (if provider=`authorize`) | — | API Login ID from Authorize.Net |
| `authorize_transaction_key` | Char | Yes (if provider=`authorize`) | `base.group_system` | API Transaction Key |
| `authorize_signature_key` | Char | Yes (if provider=`authorize`) | `base.group_system` | API Signature Key (for webhooks) |
| `authorize_client_key` | Char | No | — | Public client key for inline form; fetched via `action_update_merchant_details()` |

### Constraint: Currency Limitation

```python
@api.constrains('available_currency_ids', 'state')
def _limit_available_currency_ids(self):
    for provider in self.filtered(lambda p: p.code == 'authorize'):
        if len(provider.available_currency_ids) > 1 and provider.state != 'disabled':
            raise ValidationError(
                _("Only one currency can be selected by Authorize.Net account.")
            )
```

**L4 Note**: Authorize.Net uses one merchant account per currency. Odoo enforces this by preventing multi-currency configuration on an active Authorize.Net provider. The merchant must configure a separate provider for each currency they accept.

### Feature Support

```python
def _compute_feature_support_fields(self):
    super()._compute_feature_support_fields()
    self.filtered(lambda p: p.code == 'authorize').update({
        'support_manual_capture': 'full_only',
        'support_refund': 'full_only',
        'support_tokenization': True,
    })
```

- `support_manual_capture = 'full_only'`: Partial capture is supported
- `support_refund = 'full_only'`: Both full and partial refunds supported
- `support_tokenization = True`: Recurring/tokenized payments supported

### Key Methods

#### `action_update_merchant_details()`
Fetches Authorize.Net merchant details to auto-populate `available_currency_ids` and `authorize_client_key`.

```python
def action_update_merchant_details(self):
    self.ensure_one()
    if self.state == 'disabled':
        raise UserError(_("This action cannot be performed while the provider is disabled."))

    authorize_API = AuthorizeAPI(self)

    # 1. Validate credentials
    res_content = authorize_API.test_authenticate()
    if res_content.get('err_msg'):
        raise UserError(_("Failed to authenticate.\n%s", res_content['err_msg']))

    # 2. Fetch merchant details
    res_content = authorize_API.merchant_details()
    if res_content.get('err_msg'):
        raise UserError(_("Could not fetch merchant details:\n%s", res_content['err_msg']))

    # 3. Update provider
    currency = self.env['res.currency'].search([('name', 'in', res_content.get('currencies'))])
    self.available_currency_ids = [Command.set(currency.ids)]
    self.authorize_client_key = res_content.get('publicClientKey')
```

Requires `base.group_system` to execute.

#### `_get_validation_amount()`
```python
def _get_validation_amount(self):
    res = super()._get_validation_amount()
    if self.code != 'authorize':
        return res
    return 0.01  # Authorize.Net uses $0.01 for validation, not $1.00
```

#### `_authorize_get_inline_form_values()`
Returns a JSON blob of inline form values needed by the frontend JS:
```python
def _authorize_get_inline_form_values(self):
    self.ensure_one()
    return json.dumps({
        'state': self.state,
        'login_id': self.authorize_login,
        'client_key': self.authorize_client_key,
    })
```

#### `_get_default_payment_method_codes()`
Returns `{'ach_direct_debit', 'card', 'visa', 'mastercard', 'amex', 'discover'}`.

---

## Transaction Model: `payment.transaction` (extends)

Path: `addons/payment_authorize/models/payment_transaction.py`

### Key Methods

#### `_get_specific_processing_values(processing_values)`
Returns an access token for the inline payment form:

```python
def _get_specific_processing_values(self, processing_values):
    res = super()._get_specific_processing_values(processing_values)
    if self.provider_code != 'authorize':
        return res
    return {
        'access_token': payment_utils.generate_access_token(
            processing_values['reference'], processing_values['partner_id']
        )
    }
```

#### `_authorize_create_transaction_request(opaque_data)`
Routes to `authorize()` or `auth_and_capture()` depending on `capture_manually`:

```python
def _authorize_create_transaction_request(self, opaque_data):
    self.ensure_one()
    authorize_API = AuthorizeAPI(self.provider_id)
    if self.provider_id.capture_manually or self.operation == 'validation':
        return authorize_API.authorize(self, opaque_data=opaque_data)
    else:
        return authorize_API.auth_and_capture(self, opaque_data=opaque_data)
```

#### `_send_payment_request()`
Sends a payment request using a stored token. Routes to `authorize()` or `auth_and_capture()` based on `capture_manually`. Raises `UserError` if the token has no `authorize_profile`.

```python
def _send_payment_request(self):
    super()._send_payment_request()
    if self.provider_code != 'authorize':
        return
    if not self.token_id.authorize_profile:
        raise UserError("Authorize.Net: " + _("The transaction is not linked to a token."))
    authorize_API = AuthorizeAPI(self.provider_id)
    if self.provider_id.capture_manually:
        res_content = authorize_API.authorize(self, token=self.token_id)
    else:
        res_content = authorize_API.auth_and_capture(self, token=self.token_id)
    self._handle_notification_data('authorize', {'response': res_content})
```

#### `_send_capture_request(amount_to_capture=None)`
```python
def _send_capture_request(self, amount_to_capture=None):
    child_capture_tx = super()._send_capture_request(amount_to_capture=amount_to_capture)
    if self.provider_code != 'authorize':
        return child_capture_tx
    authorize_API = AuthorizeAPI(self.provider_id)
    rounded_amount = round(self.amount, self.currency_id.decimal_places)
    res_content = authorize_API.capture(self.provider_reference, rounded_amount)
    self._handle_notification_data('authorize', {'response': res_content})
    return child_capture_tx
```

#### `_send_void_request(amount_to_void=None)`
```python
def _send_void_request(self, amount_to_void=None):
    child_void_tx = super()._send_void_request(amount_to_void=amount_to_void)
    if self.provider_code != 'authorize':
        return child_void_tx
    authorize_API = AuthorizeAPI(self.provider_id)
    res_content = authorize_API.void(self.provider_reference)
    self._handle_notification_data('authorize', {'response': res_content})
    return child_void_tx
```

#### `_send_refund_request(amount_to_refund=None)`
Complex flow that handles multiple Authorize.Net states:

```python
def _send_refund_request(self, amount_to_refund=None):
    # 1. Fetch transaction details from Authorize.Net
    tx_details = authorize_api.get_transaction_details(self.provider_reference)

    # 2. tx_status 'voided' -> set canceled
    if tx_status in TRANSACTION_STATUS_MAPPING['voided']:
        self._set_canceled(extra_allowed_states=('done',))

    # 3. tx_status 'refunded' -> create done refund tx immediately
    elif tx_status in TRANSACTION_STATUS_MAPPING['refunded']:
        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
        refund_tx._set_done()
        self.env.ref('payment.cron_post_process_payment_tx')._trigger()

    # 4. tx_status 'authorized' -> void instead (funds haven't moved)
    elif tx_status in TRANSACTION_STATUS_MAPPING['authorized']:
        res_content = authorize_api.void(self.provider_reference)
        tx_to_process = self

    # 5. tx_status 'captured' -> issue refund via API
    elif tx_status in TRANSACTION_STATUS_MAPPING['captured']:
        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
        res_content = authorize_api.refund(self.provider_reference, rounded_amount, tx_details)
        tx_to_process = refund_tx
```

Uses `TRANSACTION_STATUS_MAPPING` from `const.py`:
```python
TRANSACTION_STATUS_MAPPING = {
    'authorized': ['authorizedPendingCapture', 'capturedPendingSettlement'],
    'captured': ['settledSuccessfully'],
    'voided': ['voided'],
    'refunded': ['refundPendingSettlement', 'refundSettledSuccessfully'],
}
```

#### `_process_notification_data(notification_data)`
Maps Authorize.Net response codes to Odoo transaction states:

| `x_response_code` | Meaning | Odoo Action |
|---|---|---|
| `'1'` (Approved) + `auth_capture`/`prior_auth_capture` | Captured | `_set_done()` + tokenize if needed |
| `'1'` + `auth_only` | Authorized only | `_set_authorized()` + tokenize if needed |
| `'1'` + `void` | Voided | `_set_canceled()` (or `_set_done()` for validation txs) |
| `'1'` + `refund` | Refund processed | `_set_done()` |
| `'2'` | Declined | `_set_canceled()` |
| `'4'` | Held for Review | `_set_pending()` |
| Other | Error | `_set_error()` |

For `auth_only` with `operation == 'validation'`, the method also sends a void request after processing (to close the $0.01 auth hold):
```python
if self.operation == 'validation':
    self._send_void_request()
```

#### `_authorize_tokenize()`
Creates a `payment.token` record from the transaction using `createCustomerProfileFromTransactionRequest` API:

```python
def _authorize_tokenize(self):
    authorize_API = AuthorizeAPI(self.provider_id)
    cust_profile = authorize_API.create_customer_profile(
        self.partner_id, self.provider_reference
    )
    if cust_profile:
        token = self.env['payment.token'].create({
            'provider_id': self.provider_id.id,
            'payment_method_id': self.payment_method_id.id,
            'payment_details': cust_profile.get('payment_details'),  # Last 4 card digits
            'partner_id': self.partner_id.id,
            'provider_ref': cust_profile.get('payment_profile_id'),
            'authorize_profile': cust_profile.get('profile_id'),  # Customer profile ID
        })
        self.write({'token_id': token.id, 'tokenize': False})
```

---

## Token Model: `payment.token` (extends)

Path: `addons/payment_authorize/models/payment_token.py`

### Fields Added

| Field | Type | Notes |
|---|---|---|
| `authorize_profile` | Char | Authorize.Net Customer Profile ID (unique per partner) |

### Field Notes

- `provider_ref` on `payment.token` (inherited) stores the **Payment Profile ID** (unique per partner+card combo)
- `authorize_profile` stores the **Customer Profile ID** (one per partner in Authorize.Net)
- Together they identify the exact card on file for token-based payments

---

## API Class: `AuthorizeAPI`

Path: `addons/payment_authorize/models/authorize_request.py`

This is a **plain Python class** (not an Odoo model) that wraps all Authorize.Net XML API calls.

### Constructor

```python
def __init__(self, provider):
    if provider.state == 'enabled':
        self.url = 'https://api.authorize.net/xml/v1/request.api'
    else:
        self.url = 'https://apitest.authorize.net/xml/v1/request.api'
    self.name = provider.authorize_login
    self.transaction_key = provider.authorize_transaction_key
```

### API Methods

| Method | Authorize.Net Operation | Description |
|---|---|---|
| `test_authenticate()` | `authenticateTestRequest` | Validates API credentials |
| `merchant_details()` | `getMerchantDetailsRequest` | Returns currencies + public client key |
| `create_customer_profile()` | `createCustomerProfileFromTransactionRequest` | Creates a customer profile from a past transaction |
| `delete_customer_profile()` | `deleteCustomerProfileRequest` | Removes a customer profile |
| `authorize()` | `createTransactionRequest` (authOnlyTransaction) | Authorizes payment (no capture) |
| `auth_and_capture()` | `createTransactionRequest` (authCaptureTransaction) | Authorizes + captures in one call |
| `capture()` | `createTransactionRequest` (priorAuthCaptureTransaction) | Captures a previously authorized payment |
| `void()` | `createTransactionRequest` (voidTransaction) | Voids an authorized (uncaptured) payment |
| `refund()` | `createTransactionRequest` (refundTransaction) | Refunds a captured payment |
| `get_transaction_details()` | `getTransactionDetailsRequest` | Fetches full transaction info (needed for refund) |

### `_make_request(operation, data=None)`
Core HTTP POST method. Sends JSON-wrapped XML API request, logs everything, handles errors.

```python
def _make_request(self, operation, data=None):
    request = {
        operation: {
            'merchantAuthentication': {
                'name': self.name,
                'transactionKey': self.transaction_key,
            },
            **(data or {})
        }
    }
    response = requests.post(self.url, json.dumps(request), timeout=60)
    # ... error handling ...
    return response
```

### `_format_response(response, operation)`
Normalizes Authorize.Net responses into a consistent dictionary format:

```python
{
    'x_response_code': '1',          # 1=Approved, 2=Declined, 3=Error, 4=Held
    'x_trans_id': '1234567890',      # Authorize.Net transaction ID
    'x_type': 'auth_capture',        # Operation type
    'payment_method_code': 'Visa',   # Card type
    'x_response_reason_text': '...'  # Error message if any
}
```

### `_prepare_authorization_transaction_request(transaction_type, tx_data, tx)`
Builds the transaction request payload. Includes:
- `transactionType` (authOnlyTransaction / authCaptureTransaction)
- `amount`
- `order` (invoiceNumber + description from `tx.reference`)
- `customer` (email)
- `billTo` (partner details — skipped for token payments)
- `customerIP`

### `_prepare_tx_data(token=None, opaque_data=False)`
Exactly one of `token` or `opaque_data` must be provided:
- **With token**: Uses `profile.customerProfileId` + `profile.paymentProfileId`
- **Without token**: Uses `opaqueData` (card details obfuscated by Authorize.Net's client-side JS)

---

## Controller: `AuthorizeController`

Path: `addons/payment_authorize/controllers/main.py`

### JSON Endpoint

| Route | Method | Auth | Type |
|---|---|---|---|
| `/payment/authorize/payment` | POST | `public` (access token validated) | `json` |

### `authorize_payment(reference, partner_id, access_token, opaque_data)`

```python
@http.route('/payment/authorize/payment', type='json', auth='public')
def authorize_payment(self, reference, partner_id, access_token, opaque_data):
    # 1. Verify the access token hasn't been tampered with
    if not payment_utils.check_access_token(access_token, reference, partner_id):
        raise ValidationError("Authorize.Net: " + _("Received tampered payment request data."))

    # 2. Find the transaction
    tx_sudo = request.env['payment.transaction'].sudo().search([('reference', '=', reference)])

    # 3. Make the payment request
    response_content = tx_sudo._authorize_create_transaction_request(opaque_data)

    # 4. Process the response
    tx_sudo._handle_notification_data('authorize', {'response': response_content})
```

**Note**: The access token is a HMAC-based token generated in `_get_specific_processing_values()` using the reference + partner_id. It prevents tampering with the payment form data.

---

## Default Provider Data

Defined in `data/payment_provider_data.xml` (noupdate):

```xml
<record id="payment.payment_provider_authorize" model="payment.provider">
    <field name="code">authorize</field>
    <field name="inline_form_view_id" ref="inline_form"/>
    <field name="allow_tokenization">True</field>
</record>
```

The inline form view (`inline_form`) is defined in `views/payment_provider_views.xml`.

---

## Payment Flow: Full Lifecycle

### Direct Payment (Card Entry on Website)

```
Customer enters card → JS encrypts via Authorize.Net SDK → opaque_data
                                                    ↓
POST /payment/authorize/payment (JSON)
    → AuthorizeController.authorize_payment()
        → tx._authorize_create_transaction_request(opaque_data)
            → AuthorizeAPI.auth_and_capture() or authorize()
                → POST https://api.authorize.net/xml/v1/request.api
                    ← { x_response_code: '1', x_trans_id: '...', x_type: 'auth_capture' }
        → tx._handle_notification_data('authorize', {'response': ...})
            → tx._process_notification_data()
                → tx._set_done() [or _set_authorized() if capture_manually]
                → tx._authorize_tokenize() [if tokenize=True]
```

### Token/Recurring Payment

```
Customer on file → _send_payment_request()
    → AuthorizeAPI.auth_and_capture(tx, token=self.token_id)
        → Uses token.authorize_profile + token.provider_ref (payment_profile_id)
    → _handle_notification_data()
```

### Manual Capture Flow

```
1. Payment authorized → tx._set_authorized()
2. Merchant clicks "Capture" → _send_capture_request()
    → AuthorizeAPI.capture(provider_reference, amount)
        → priorAuthCaptureTransaction
3. _handle_notification_data → tx._set_done()
```

### Void Flow

```
Merchant clicks "Cancel" → _send_void_request()
    → AuthorizeAPI.void(provider_reference)
        → voidTransaction (only works on authorized, uncaptured txs)
    → _handle_notification_data → tx._set_canceled()
```

### Refund Flow

```
Merchant clicks "Refund" → _send_refund_request()
    → get_transaction_details() to determine status
    → If captured: AuthorizeAPI.refund(provider_reference, amount, tx_details)
        → refundTransaction
    → If authorized only: AuthorizeAPI.void(provider_reference)
        → voidTransaction (funds never moved)
    → _handle_notification_data
```

---

## L4: Key Architecture Decisions

### 1. No Webhooks — All Client-Initiated
Unlike Razorpay/Stripe, Authorize.Net integration does **not** use webhooks. All state changes are driven by responses returned directly from the API calls made by the Odoo server after the customer's browser submits payment data via the JSON controller.

### 2. Two-Profile Model
Authorize.Net uses a two-level profile hierarchy:
- **Customer Profile** (`authorize_profile` on token): One per partner. Created via `createCustomerProfileFromTransactionRequest`.
- **Payment Profile** (`provider_ref` on token): One per card per partner. Stored alongside the customer profile.

When charging a token, both IDs must be provided.

### 3. ACH Direct Debit Bill-To Requirement
The `_prepare_authorization_transaction_request()` method conditionally adds `billTo` data for ACH transactions:
- **With token**: No `billTo` allowed by Authorize.Net
- **Without token (new ACH)**: `billTo` is required with full billing address

### 4. Void vs. Refund State Machine
The refund flow in `_send_refund_request()` checks the actual Authorize.Net settlement state (not just Odoo's `state`) because:
- A payment can be `authorized` in Odoo but already `settledSuccessfully` in Authorize.Net
- Refunding a settled payment requires the refund API call
- Voiding an authorized-only payment cancels before settlement

### 5. `$0.01` Validation Amount
Unlike other providers that use `$1.00` for card validation, Authorize.Net's hosted form validation uses `$0.01`. The void is sent immediately after to release the authorization hold.

### 6. Client Key for Inline Form
The `authorize_client_key` is used by Odoo's frontend JS to communicate with Authorize.Net's server-side encryption library. It is fetched automatically via `action_update_merchant_details()` which calls `getMerchantDetailsRequest`.

---

## Hooks

```python
def post_init_hook(env):
    setup_provider(env, 'authorize')

def uninstall_hook(env):
    reset_payment_provider(env, 'authorize')
```

---

## Related Documentation

- [[Core/Payment Framework]] — base payment architecture
- [[Modules/payment]] — core payment module
- [[Modules/payment-custom]] — manual wire transfer provider
- [[Modules/payment-razorpay]] — Razorpay provider (webhook-based)

---

**Tags:** #odoo #odoo18 #payment #authorize-net #gateway #integration
