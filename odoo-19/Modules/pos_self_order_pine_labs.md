# POS Self Order Pine Labs

## Overview

- **Module:** `pos_self_order_pine_labs`
- **Category:** Sales/Point Of Sale
- **Depends:** `pos_pine_labs`, `pos_self_order`
- **Auto-install:** `True`
- **Author:** Odoo IN Pvt Ltd
- **License:** LGPL-3
- **Source path:** `odoo/addons/pos_self_order_pine_labs/`
- **Odoo version:** 19 CE

## Description

Adds Pine Labs POS terminal payment support to the POS Self Order kiosk app. Customers select items in the self-order interface, then pay via a connected Pine Labs card/UPI terminal. Like Razorpay, Pine Labs uses a **polling-based architecture** where the frontend repeatedly calls a status endpoint. Pine Labs is primarily used in the Indian market and only supports INR currency.

**Key distinguishing feature:** Pine Labs processes amounts in **paisa** (1 INR = 100 paisa), so the self-order module multiplies `order.amount_total` by 100 before sending to the Pine Labs API.

## Architecture

### Dependency Chain

```
pos.payment.method (base)
    └── pos_pine_labs
            └── adds pine_labs_* fields + pine_labs_make_payment_request(),
               pine_labs_fetch_payment_status(), pine_labs_cancel_payment_request()
                    ↕
            pos_self_order_pine_labs
                    overrides _payment_request_from_kiosk()
                    overrides _load_pos_self_data_domain()
                    adds Pine Labs polling controller endpoints
                            ↕
            pos_self_order (base controller: PosSelfOrderController)
                    provides _verify_pos_config(), _send_payment_result()
```

### File Structure

```
pos_self_order_pine_labs/
├── __init__.py
├── __manifest__.py               # depends: [pos_pine_labs, pos_self_order]
│                                 # assets: pos_self_order.assets → static/**/*
├── models/
│   ├── __init__.py
│   └── pos_payment_method.py     # _payment_request_from_kiosk(), _load_pos_self_data_domain()
└── controllers/
    ├── __init__.py
    └── orders.py                # Pine Labs polling endpoints (extends PosSelfOrderController)
```

## L1: Configuration Extensions

### Fields Added to `pos.payment.method`

No new fields are added by `pos_self_order_pine_labs` itself. All Pine Labs credential fields are defined in `pos_pine_labs`:

| Field (from `pos_pine_labs`) | Type | Purpose |
|---|---|---|
| `pine_labs_merchant` | `Char` | Merchant ID issued by Pine Labs |
| `pine_labs_store` | `Char` | Store ID issued by Pine Labs |
| `pine_labs_client` | `Char` | Client ID issued by Pine Labs |
| `pine_labs_security_token` | `Char` | Security token issued by Pine Labs |
| `pine_labs_allowed_payment_mode` | `Selection` | `all`, `card`, `upi` |
| `pine_labs_test_mode` | `Boolean` | Toggle test/live environment |

**Constraint (from `pos_pine_labs`):** `use_payment_terminal == 'pine_labs'` is only valid when `company_id.currency_id.name == 'INR'`. Attempting to use Pine Labs with non-INR currency raises `UserError`.

**Selection addition (from `pos_pine_labs`):** `_get_payment_terminal_selection()` adds `('pine_labs', 'Pine Labs')`.

### POS Config Prerequisites

1. `self_ordering_mode == 'kiosk'` — specifically kiosk mode triggers the extended domain filter
2. The Pine Labs payment method must be added to `payment_method_ids`
3. POS session must be open and the self-ordering URL accessible

## L2: Field Types, Defaults, Provider-Specific Configuration

### `_payment_request_from_kiosk(order)` — Method Override

**File:** `models/pos_payment_method.py` (lines 12-25)

```python
def _payment_request_from_kiosk(self, order):
    if self.use_payment_terminal != 'pine_labs':
        return super()._payment_request_from_kiosk(order)
    reference_prefix = order.config_id.name.replace(' ', '')
    # We need to provide the amount in paisa since Pine Labs processes amounts in paisa.
    # The conversion rate between INR and paisa is set as 1 INR = 100 paisa.
    data = {
        'amount': order.amount_total * 100,           # amount in paisa (integer)
        'transactionNumber': f'{reference_prefix}/Order/{order.id}/{uuid.uuid4().hex}',
        'sequenceNumber': '1'
    }
    payment_response = self.pine_labs_make_payment_request(data)
    payment_response['payment_ref_no'] = data['transactionNumber']
    return payment_response
```

**Key points:**
- `amount` is multiplied by 100 to convert INR to paisa — Pine Labs requires integer amounts in paisa
- `transactionNumber` is the unique reference (same format as Razorpay)
- `sequenceNumber: '1'` — always 1 for single-payment transactions
- The response is augmented with `payment_ref_no = data['transactionNumber']` before returning — this `transactionNumber` is used in subsequent status polls
- `super()._payment_request_from_kiosk(order)` chains to other terminal handlers for non-pine_labs types

### `_load_pos_self_data_domain(data, config)` — Domain Extension

**File:** `models/pos_payment_method.py` (lines 27-32)

```python
@api.model
def _load_pos_self_data_domain(self, data, config):
    domain = super()._load_pos_self_data_domain(data, config)
    if data['pos.config'][0]['self_ordering_mode'] == 'kiosk':
        domain = Domain.OR([[
            ('use_payment_terminal', '=', 'pine_labs'),
            ('id', 'in', config.payment_method_ids.ids)
        ], domain])
    return domain
```

**Minor difference from other modules:** Pine Labs reads `self_ordering_mode` from `data['pos.config'][0]` (the raw loaded data dictionary), while Razorpay reads it from `config` (the browsed record). Both evaluate to the same value — this is an implementation nuance.

### `pine_labs_make_payment_request(data)` — From Parent Module

**Defined in:** `pos_pine_labs/models/pos_payment_method.py` (lines 23-46)

Sends the payment request to the Pine Labs cloud API via `call_pine_labs()`:

```python
body = {
    'Amount': data['amount'],           # in paisa
    'TransactionNumber': data['transactionNumber'],
    'SequenceNumber': data['sequenceNumber']
}
response = call_pine_labs(payment_method=self, endpoint='UploadBilledTransaction', payload=body)
# On success:
{'responseCode': 0, 'status': 'APPROVED', 'plutusTransactionReferenceID': '...'}
# On failure:
{'error': '...'}
```

The `plutusTransactionReferenceID` is the handle for subsequent status polls.

### `pine_labs_fetch_payment_status(data)` — From Parent Module

**Defined in:** `pos_pine_labs/models/pos_payment_method.py` (lines 48-69)

Accepts `{'plutusTransactionReferenceID': ...}`, polls the Pine Labs cloud status API:

```python
body = {'PlutusTransactionReferenceID': data['plutusTransactionReferenceID']}
response = call_pine_labs(payment_method=self, endpoint='GetCloudBasedTxnStatus', payload=body)
# On APPROVED (ResponseCode 0):
{
    'responseCode': 0,
    'status': 'APPROVED',
    'plutusTransactionReferenceID': '...',
    'data': { 'Tag': 'Value', ... }  # formatted transaction details
}
# On PENDING (ResponseCode 1001):
{'responseCode': 1001, 'status': 'APPROVED', 'plutusTransactionReferenceID': '...', 'data': {}}
# On failure:
{'error': '...'}
```

### `pine_labs_cancel_payment_request(data)` — From Parent Module

**Defined in:** `pos_pine_labs/models/pos_payment_method.py` (lines 71-93)

Accepts `{'amount': ..., 'plutusTransactionReferenceID': ...}`, calls `CancelTransactionForced` endpoint:

```python
body = {
    'Amount': data['amount'],
    'PlutusTransactionReferenceID': data['plutusTransactionReferenceID'],
    'TakeToHomeScreen': True,
    'ConfirmationRequired': True
}
response = call_pine_labs(payment_method=self, endpoint='CancelTransactionForced', payload=body)
# On success:
{'responseCode': 0, 'notification': '...'}
# On failure:
{'error': '...'}
```

### Controller Endpoints

#### `/pos-self-order/pine-labs-fetch-payment-status/`

**File:** `controllers/orders.py` (lines 9-38)

```python
@http.route('/pos-self-order/pine-labs-fetch-payment-status/', auth='public', type='jsonrpc')
def pine_labs_fetch_payment_status(self, access_token, order_id, payment_data, payment_method_id):
    pos_config = self._verify_pos_config(access_token)
    order = pos_config.env['pos.order'].browse(order_id)
    payment_method = pos_config.env['pos.payment.method'].browse(payment_method_id)

    if not order.exists() or not payment_method.exists() or order.config_id.id != pos_config.id:
        raise NotFound()

    pine_labs_status_response = payment_method.pine_labs_fetch_payment_status(payment_data)
    if pine_labs_status_response.get('status') == "TXN APPROVED":
        data = pine_labs_status_response.get('data')
        order.add_payment({
            'amount': order.amount_total,
            'payment_method_id': payment_method.id,
            'cardholder_name': data.get('Card Holder Name'),
            'transaction_id': data.get('TransactionLogId'),
            'payment_status': 'done',
            'pos_order_id': order.id,
            'payment_method_authcode': data.get('ApprovalCode'),
            'card_brand': data.get('Card Type'),
            'payment_method_issuer_bank': data.get('Acquirer Name'),
            'card_no': data.get('Card Number') and data.get('Card Number')[-4:],
            'payment_method_payment_mode': data.get('PaymentMode'),
            'payment_ref_no': payment_data.get('payment_ref_no'),
            'pine_labs_plutus_transaction_ref': pine_labs_status_response.get('plutusTransactionReferenceID'),
        })
        order.action_pos_order_paid()
        order._send_payment_result('Success')
    return pine_labs_status_response
```

**Key points:**
- Uses `order.exists()` guard before accessing record data — more robust than Razorpay's `search(..., limit=1)` check
- Checks both `order.exists()` and `payment_method.exists()` and `order.config_id.id == pos_config.id`
- `NotFound()` (HTTP 404) is raised if any check fails — vs Razorpay's `Unauthorized()` (HTTP 401)
- `TXN APPROVED` (note: uppercase) is the success status string
- Card data is extracted from `data` dict (formatted transaction data returned by Pine Labs)
- `card_no` stores only the last 4 digits: `data.get('Card Number')[-4:]`
- `payment_ref_no` stores the original `transactionNumber` from the payment request
- `pine_labs_plutus_transaction_ref` stores the Pine Labs-specific Plutus reference ID
- Calls `_send_payment_result('Success')` unconditionally after successful payment

#### `/pos-self-order/pine-labs-cancel-transaction/`

**File:** `controllers/orders.py` (lines 40-49)

```python
@http.route("/pos-self-order/pine-labs-cancel-transaction/", auth="public", type='jsonrpc')
def pine_labs_cancel_transaction(self, access_token, order_id, payment_data, payment_method_id):
    pos_config = self._verify_pos_config(access_token)
    order = pos_config.env['pos.order'].browse(order_id)
    payment_method = pos_config.env['pos.payment.method'].browse(payment_method_id)

    if not order.exists() or not payment_method.exists() or order.config_id.id != pos_config.id:
        raise NotFound()

    return payment_method.pine_labs_cancel_payment_request(payment_data)
```

Unlike Razorpay's cancel endpoint, Pine Labs' cancel does NOT call `_send_payment_result('fail')` — the frontend must handle the cancel result based on the returned response.

## L3: Cross-Module Integration, Override Pattern, Workflow, Failure Modes

### Cross-Module Integration

#### `pos_pine_labs/models/pine_labs_pos_request.py` — API Client

Provides `call_pine_labs(payment_method, endpoint, payload)` — the HTTP client that communicates with the Pine Labs cloud API. Uses the payment method's `pine_labs_*` credentials to authenticate requests.

#### `pos_self_order` — Base Controller

Provides `_verify_pos_config(access_token)`, `_send_payment_result(result)`, and the base controller class.

### Override Pattern

**Pattern: Guard-then-delegate + response augmentation**

```python
def _payment_request_from_kiosk(self, order):
    if self.use_payment_terminal != 'pine_labs':
        return super()._payment_request_from_kiosk(order)
    # ... build data dict with paisa conversion ...
    payment_response = self.pine_labs_make_payment_request(data)
    payment_response['payment_ref_no'] = data['transactionNumber']  # augment response
    return payment_response
```

The response augmentation (`payment_ref_no`) is important — the `transactionNumber` generated in the payment request must be carried forward into the poll request via the controller. The Pine Labs API does not return the `transactionNumber` in its response, so it is injected into the response dict before returning.

### Payment Workflow (Kiosk Mode)

```
1. Customer selects items in Self Order app
       ↓
2. Customer selects "Pay by Card/UPI"
   → triggers _payment_request_from_kiosk()
       ↓
3. pine_labs_make_payment_request() sends {amount paisa, transactionNumber, sequenceNumber}
   to Pine Labs cloud API
   → terminal displays payment prompt
       ↓
4. Customer taps/inserts card or scans UPI QR
       ↓
5. Frontend polls /pos-self-order/pine-labs-fetch-payment-status/ every few seconds
   → sends payment_data from step 3 (including payment_ref_no = transactionNumber)
       ↓
6. pine_labs_fetch_payment_status() → checks status from Pine Labs API
       ↓
7a. If status == 'TXN APPROVED':
    → add_payment() with card metadata (cardholder name, auth code, card type, etc.)
    → action_pos_order_paid()
    → _send_payment_result('Success') → bus notification to frontend
    → order proceeds to kitchen/fulfillment
       ↓
7b. If error or pending:
    → returns {'error': '...'} or pending status
    → frontend continues polling or shows failure
```

### Differences from Razorpay

| Aspect | Pine Labs | Razorpay |
|---|---|---|
| Amount unit | Paisa (INR x 100, integer) | Rupees (decimal) |
| Success status | `'TXN APPROVED'` | `'AUTHORIZED'` + `'P2P_DEVICE_TXN_DONE'` |
| Cancel behavior | Returns response without bus notification | `_send_payment_result('fail')` called explicitly |
| Payment status poll response | Includes formatted `data` dict with card details | Returns individual fields directly |
| Cancel HTTP status on auth failure | 404 `NotFound()` | 401 `Unauthorized()` |
| Response augmentation | Injects `payment_ref_no` into response | Uses `referenceId` from request |

### Failure Modes

| Failure Mode | Trigger | Handling | User Experience |
|---|---|---|---|
| Terminal unreachable | `call_pine_labs` returns error | `pine_labs_make_payment_request` returns `{'error': ...}` | Frontend shows error, no payment initiated |
| Card declined | `pine_labs_fetch_payment_status` returns non-0 ResponseCode | Returns `{'error': '...'}`, frontend continues polling | Customer sees decline, can retry |
| Cancel at terminal | Customer cancels | Cancel response returned, frontend handles | Terminal returns to home, frontend shows cancel |
| Double payment attempt | Same `transactionNumber` replayed | Pine Labs idempotency prevents duplicate | Payment recorded once |
| Order/payment method deleted mid-flow | `.exists()` check fails | Raises `NotFound()` (404) | Frontend handles 404 |
| INR required constraint | Non-INR currency on payment method | `_check_pine_labs_terminal` raises `UserError` | Prevents configuration of invalid currency |

## L4: Version Changes Odoo 18→19, Security Notes

### Version Changes (Odoo 18 → 19)

`pos_self_order_pine_labs` is **new in Odoo 19**. `pos_pine_labs` existed in Odoo 18 for standard POS, but the self-order kiosk extension was added in Odoo 19 alongside the kiosk self-order feature.

### PCI Compliance Notes

Pine Labs acts as the PCI DSS middleware — Odoo never handles raw card data. The terminal reads the card and communicates with Pine Labs' servers. Odoo receives only:

- `TransactionLogId` — Pine Labs' transaction reference
- `Card Holder Name` — cardholder name printed on card (not the full PAN)
- `Card Number` — masked to last 4 digits only: `data.get('Card Number')[-4:]`
- `ApprovalCode` — authorization code from the issuing bank
- `Card Type` — card network (Visa/Mastercard/etc.)
- `Acquirer Name` — issuing bank name
- `PaymentMode` — mode used (card/UPI/etc.)

No full card numbers, CVVs, or PINs enter Odoo.

### Credentials Storage

- `pine_labs_security_token` is stored on `pos.payment.method` without explicit `groups` restriction (unlike `razorpay_api_key` which is restricted to `group_pos_manager`)
- Pine Labs credential fields (`merchant`, `store`, `client`) are stored in plaintext Char fields
- Production deployments should consider database encryption or vault solutions

### INR Currency Constraint

The `_check_pine_labs_terminal` constraint in `pos_pine_labs` enforces INR at the ORM level:

```python
@api.constrains('use_payment_terminal')
def _check_pine_labs_terminal(self):
    if any(record.use_payment_terminal == 'pine_labs' and
           record.company_id.currency_id.name != 'INR' for record in self):
        raise UserError(_('This Payment Terminal is only valid for INR Currency'))
```

### `auth="public"` Endpoint Security

Same as Razorpay: the polling endpoints use `auth="public"` because self-order kiosks operate without Odoo user sessions.

Security enforcement:
1. `access_token` via `_verify_pos_config(access_token)` — validates token, expiry, config state
2. Record existence checks: `order.exists()` and `payment_method.exists()` — prevents access to deleted records
3. Order ownership: `order.config_id.id == pos_config.id` — ensures order belongs to the authenticated POS config

The `NotFound()` (404) vs `Unauthorized()` (401) difference between Pine Labs and Razorpay is an implementation choice — both indicate the request cannot be fulfilled.

### Paisa Conversion Precision

```python
'amount': order.amount_total * 100  # paisa
```

This conversion can introduce floating-point precision issues for very large amounts (e.g., `100.01 * 100 = 10001.00000000001`). Pine Labs requires integer paisa, so the API may round or reject imprecise values. Odoo does not apply explicit rounding before sending.

## Related

- [Modules/pos_self_order](odoo-18/Modules/pos_self_order.md) — Base self-order module
- [Modules/pos_pine_labs](odoo-18/Modules/pos_pine_labs.md) — Pine Labs terminal integration
- [Modules/pos_self_order_razorpay](odoo-18/Modules/pos_self_order_razorpay.md) — Razorpay terminal in self-order (polling, INR decimal)
- [Modules/pos_self_order_adyen](odoo-18/Modules/pos_self_order_adyen.md) — Adyen terminal in self-order (push webhook, multi-currency)
- [Modules/pos_self_order_qfpay](odoo-19/Modules/pos_self_order_qfpay.md) — QFPay terminal in self-order (webhook, HKD)
