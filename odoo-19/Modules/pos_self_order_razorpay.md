# POS Self Order Razorpay

## Overview

- **Module:** `pos_self_order_razorpay`
- **Category:** Sales/Point Of Sale
- **Depends:** `pos_razorpay`, `pos_self_order`
- **Auto-install:** `True`
- **Author:** Odoo S.A.
- **License:** LGPL-3
- **Source path:** `odoo/addons/pos_self_order_razorpay/`
- **Odoo version:** 19 CE

## Description

Adds Razorpay POS terminal payment support to the POS Self Order kiosk/mobile app. Customers select items in the self-order interface, then pay via a connected Razorpay card/UPI terminal. Razorpay is primarily used in the Indian market and only supports INR currency.

## Architecture

### Dependency Chain

```
pos.payment.method (base)
    └── pos_razorpay
            └── adds razorpay_* fields + razorpay_make_payment_request(),
               razorpay_fetch_payment_status(), razorpay_cancel_payment_request()
                    └── pos_self_order_razorpay
                            overrides _payment_request_from_kiosk()
                            adds Razorpay polling controller endpoints
                                    ↕
                    pos_self_order (base controller: PosSelfOrderController)
                            provides _verify_pos_config(), _send_payment_result()
```

The module does **not** add new models. It extends `pos.payment.method` and `PosSelfOrderController`.

### File Structure

```
pos_self_order_razorpay/
├── __init__.py
├── __manifest__.py               # depends: [pos_razorpay, pos_self_order]
│                                 # assets: pos_self_order.assets → static/**/*
├── models/
│   ├── __init__.py
│   └── pos_payment_method.py     # _payment_request_from_kiosk(), _load_pos_self_data_domain()
└── controllers/
    ├── __init__.py
    └── orders.py                 # Razorpay polling endpoints (extends PosSelfOrderController)
```

## L1: Configuration Extensions

### Fields Added to `pos.payment.method`

No new fields are added by `pos_self_order_razorpay` itself. All Razorpay credential fields are defined in the parent module `pos_razorpay`:

| Field (from `pos_razorpay`) | Type | Purpose |
|---|---|---|
| `razorpay_tid` | `Char` | Device Serial No (e.g., `7000012300`) |
| `razorpay_allowed_payment_modes` | `Selection` | `all`, `card`, `upi`, `bharatqr` |
| `razorpay_username` | `Char` | Device Login username |
| `razorpay_api_key` | `Char` | API key (group: `group_pos_manager`) |
| `razorpay_test_mode` | `Boolean` | Toggle test/live environment |

**Constraint (from `pos_razorpay`):** `use_payment_terminal == 'razorpay'` is only valid when `company_id.currency_id.name == 'INR'`. Non-INR currency raises `UserError`.

**Selection addition (from `pos_razorpay`):** `_get_payment_terminal_selection()` adds `('razorpay', 'Razorpay')` to the terminal dropdown on the payment method form.

### POS Config Prerequisites

In `pos.config`, the following must be set:

1. `self_ordering_mode == 'kiosk'` or `'mobile'` — kiosk mode specifically triggers the extended domain filter
2. The Razorpay payment method must be added to `payment_method_ids`
3. POS session must be open and the self-ordering URL accessible

## L2: Field Types, Defaults, Provider-Specific Configuration

### `_payment_request_from_kiosk(order)` — Method Override

**File:** `models/pos_payment_method.py` (lines 9-17)

```python
def _payment_request_from_kiosk(self, order):
    if self.use_payment_terminal != 'razorpay':
        return super()._payment_request_from_kiosk(order)  # guard-then-delegate
    reference_prefix = order.config_id.name.replace(' ', '')
    data = {
        'amount': order.amount_total,              # in INR (decimal rupees)
        'referenceId': f'{reference_prefix}/Order/{order.id}/{uuid.uuid4().hex}',
    }
    return self.razorpay_make_payment_request(data)
```

**Key points:**
- `super()._payment_request_from_kiosk(order)` is called first for non-Razorpay terminals, chaining to other terminal handlers
- `amount` is passed as `order.amount_total` directly in rupees — Razorpay POS accepts decimal amounts
- `referenceId` is constructed as `{pos_config_name}/Order/{order_id}/{uuid}` and passed to `razorpay_make_payment_request()` from the parent module
- `uuid.uuid4().hex` generates a unique request ID to prevent duplicate charges

### `_load_pos_self_data_domain(data, config)` — Domain Extension

**File:** `models/pos_payment_method.py` (lines 19-27)

```python
@api.model
def _load_pos_self_data_domain(self, data, config):
    domain = super()._load_pos_self_data_domain(data, config)
    if config.self_ordering_mode == 'kiosk':
        domain = Domain.OR([
            [('use_payment_terminal', '=', 'razorpay'), ('id', 'in', config.payment_method_ids.ids)],
            domain
        ])
    return domain
```

**Purpose:** Filters which payment methods appear in the POS Self Order frontend on load. In kiosk mode, Razorpay terminals linked to this POS config are OR'd into the domain so they are available alongside default self-order payment methods.

**Trigger:** `config.self_ordering_mode == 'kiosk'` — this filter is **not** applied in `'mobile'` mode (Razorpay is primarily a kiosk feature).

### `razorpay_make_payment_request(data)` — From Parent Module

**Defined in:** `pos_razorpay/models/pos_payment_method.py`

Builds the Razorpay P2P payment request body using `RazorpayPosRequest`, calls the `pay` endpoint:

```python
# On success:
{'success': True, 'p2pRequestId': '<request_id>'}
# On failure:
{'error': '<error_message>'}
```

The `p2pRequestId` is the polling handle — the frontend uses it to call `razorpay_fetch_payment_status()`.

### `razorpay_fetch_payment_status(data)` — From Parent Module

**Defined in:** `pos_razorpay/models/pos_payment_method.py`

Accepts `{'p2pRequestId': ...}`, polls the Razorpay status endpoint:

```python
# On AUTHORIZED:
{'status': 'AUTHORIZED', 'authCode': '...', 'cardLastFourDigit': '...',
 'txnId': '...', 'paymentMode': '...', 'paymentCardType': '...', ...}
# On pending:
{'status': 'PENDING_CODE'}   # P2P_DEVICE_RECEIVED, P2P_DEVICE_SENT, P2P_STATUS_QUEUED
# On FAILED:
{'error': '...'}
```

### `razorpay_cancel_payment_request(data)` — From Parent Module

**Defined in:** `pos_razorpay/models/pos_payment_method.py`

Accepts `{'p2pRequestId': ...}`, calls the Razorpay `cancel` endpoint. Returns `{'error': '...'} ` on any non-success response.

## L3: Cross-Module Integration, Override Pattern, Workflow, Failure Modes

### Cross-Module Integration

#### `pos_self_order` — Base Controller

Provides the base HTTP endpoints the frontend calls. `pos_self_order_razorpay` extends it with two routes:

| Route | Auth | Type | Purpose |
|---|---|---|---|
| `/pos-self-order/razorpay-fetch-payment-status/` | `public` | `jsonrpc` | Poll Razorpay payment status |
| `/pos-self-order/razorpay-cancel-transaction/` | `public` | `jsonrpc` | Cancel pending Razorpay transaction |

Both require a valid `access_token` (verified via `_verify_pos_config(access_token)`) and an `order_id` belonging to the authenticated POS config.

#### `pos_razorpay` — Terminal SDK

Provides the actual Razorpay API communication:

- `RazorpayPosRequest` class — builds signed request bodies, calls the Razorpay P2P API
- `razorpay_make_payment_request(data)` — initiates payment on the terminal
- `razorpay_fetch_payment_status(data)` — polls for payment result
- `razorpay_cancel_payment_request(data)` — voids a pending payment

#### `pos.payment.method` — Field Host

All Razorpay-specific fields (`razorpay_tid`, `razorpay_api_key`, etc.) live on `pos.payment.method`. The self-order module extends this model to add kiosk-specific behavior.

### Override Pattern

The module uses **three** override patterns:

**Pattern 1: Guard-then-delegate (terminal type routing)**

```python
def _payment_request_from_kiosk(self, order):
    if self.use_payment_terminal != 'razorpay':
        return super()._payment_request_from_kiosk(order)  # chain to next handler
    # Razorpay-specific logic
    return self.razorpay_make_payment_request(data)
```

Multiple terminal extensions coexist — each handles its own type and `super()` chains to the next.

**Pattern 2: OR-domain extension (data filtering)**

```python
def _load_pos_self_data_domain(self, data, config):
    domain = super()._load_pos_self_data_domain(data, config)
    if config.self_ordering_mode == 'kiosk':
        domain = Domain.OR([
            [('use_payment_terminal', '=', 'razorpay'), ('id', 'in', config.payment_method_ids.ids)],
            domain
        ])
    return domain
```

Pure domain manipulation — no business logic, only narrowing/expanding the payment method list returned to the frontend.

**Pattern 3: Controller extension (HTTP route augmentation)**

```python
class PosSelfOrderControllerRazorpay(PosSelfOrderController):
    @http.route("/pos-self-order/razorpay-fetch-payment-status/", ...)
    def razorpay_payment_status(self, access_token, order_id, payment_data, payment_method_id):
        ...
```

Extends the base controller with provider-specific polling/cancel endpoints. The base class handles `access_token` verification; the child handles Razorpay-specific response processing.

### Payment Workflow (Kiosk Mode)

```
1. Customer selects items in Self Order app
       ↓
2. Customer selects "Pay by Card/UPI"
   → triggers _payment_request_from_kiosk()
       ↓
3. razorpay_make_payment_request() sends {amount, referenceId} to Razorpay P2P API
   → terminal displays payment prompt
       ↓
4. Customer taps/inserts card or scans UPI QR
       ↓
5. Frontend polls /pos-self-order/razorpay-fetch-payment-status/ every few seconds
       ↓
6. razorpay_fetch_payment_status() → checks AUTHORIZED / FAILED / pending
       ↓
7a. If AUTHORIZED:
    → add_payment() with full card/transaction metadata
    → action_pos_order_paid()
    → _send_payment_result('Success') → bus notification to frontend
    → order proceeds to kitchen/fulfillment
       ↓
7b. If FAILED or no status:
    → _send_payment_result('fail') → bus notification to frontend
    → customer shown failure screen, can retry
```

### Failure Modes

| Failure Mode | Trigger | Handling | User Experience |
|---|---|---|---|
| Terminal unreachable | Razorpay API returns error from `razorpay_make_payment_request` | `{'error': ...}` returned | Frontend shows error, no payment initiated |
| Card declined | `razorpay_fetch_payment_status` returns `FAILED` | `_send_payment_result('fail')` via bus | Customer sees decline, can retry |
| Network timeout on poll | `razorpay_fetch_payment_status` returns `{'status': 'QUEUED'}` | Returns status as-is | Frontend continues polling |
| Cancel before completion | Customer cancels at terminal | Frontend calls `/razorpay-cancel-transaction/` | Terminal returns to home screen |
| Double payment attempt | Customer refreshes and tries to pay again | `action_pos_order_paid()` already called | Order state already `paid` prevents double payment |
| Invalid order ownership | `order_id` does not belong to authenticated POS config | `Unauthorized` raised (line 15) | 401 returned, frontend shows error |

**Security note on `auth="public"`:** The polling endpoints use `auth="public"` because self-order kiosks operate without Odoo user sessions. Authentication is enforced through:
1. `access_token` via `_verify_pos_config(access_token)` (checks token validity, expiry, and config state)
2. Order ownership check: `('id', '=', order_id), ('config_id', '=', pos_config.id)`

## L4: Version Changes Odoo 18→19, Security Notes

### Version Changes (Odoo 18 → 19)

`pos_self_order_razorpay` is **new in Odoo 19**. There is no Odoo 18 counterpart — `pos_razorpay` existed in Odoo 18, but the self-order kiosk extension (`pos_self_order_razorpay`) was introduced alongside the kiosk self-order feature in Odoo 19.

### PCI Compliance Notes

Razorpay acts as the PCI DSS middleware — Odoo never handles raw card data directly. The terminal reads the card and communicates with Razorpay's servers. Odoo receives only:

- `txnId` — Razorpay's transaction reference
- `cardLastFourDigit` — last 4 digits only (no full card number)
- `authCode` — authorization code from the issuing bank
- `paymentCardBrand` — Visa/Mastercard/UPI/etc.
- `paymentMode` — mode used (card/UPI/QR)

No full card numbers, CVVs, or PINs are ever stored by Odoo. This is the primary PCI compliance benefit of using a hosted payment terminal rather than integrating a payment gateway directly.

### Credentials Storage

- `razorpay_api_key` is stored on `pos.payment.method` and is `groups='point_of_sale.group_pos_manager'` — only POS managers can view/edit it in the UI
- API keys are used to sign requests via `RazorpayPosRequest._razorpay_get_request_parameters()`
- API keys should be stored in a secure credential manager in production; Odoo's database stores Char fields without encryption at rest

### `auth="public"` Endpoint Security

The polling endpoints use `auth="public"` because self-order kiosks operate without Odoo user sessions. Security layers:

1. `access_token` verification via `_verify_pos_config(access_token)` — checks token validity, expiry, config state
2. Order ownership check: `('id', '=', order_id), ('config_id', '=', pos_config.id)` — order must belong to the same POS config as the access token
3. No sensitive data is exposed in responses — only payment status codes and card metadata (last 4 digits only)

### INR Currency Constraint

The `_check_razorpay_terminal` constraint in `pos_razorpay` enforces INR at the ORM level:

```python
@api.constrains('use_payment_terminal')
def _check_razorpay_terminal(self):
    if any(record.use_payment_terminal == 'razorpay' and
           record.company_id.currency_id.name != 'INR' for record in self):
        raise UserError(_('This Payment Terminal is only valid for INR Currency'))
```

This prevents accidental configuration of Razorpay in non-INR deployments.

## Related

- [Modules/pos_self_order](odoo-18/Modules/pos_self_order.md) — Base self-order module (provides `PosSelfOrderController`, `_send_payment_result`, `_verify_pos_config`)
- [Modules/pos_razorpay](odoo-18/Modules/pos_razorpay.md) — Razorpay terminal integration (provides `RazorpayPosRequest`, API methods)
- [Modules/pos_self_order_adyen](odoo-18/Modules/pos_self_order_adyen.md) — Adyen terminal in self-order (push-based webhook pattern)
- [Modules/pos_self_order_pine_labs](odoo-19/Modules/pos_self_order_pine_labs.md) — Pine Labs terminal in self-order (polls paisa-based amounts)
- [Modules/pos_self_order_qfpay](odoo-19/Modules/pos_self_order_qfpay.md) — QFPay terminal in self-order (webhook with HKD currency)
