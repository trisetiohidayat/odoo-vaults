# POS Self Order QFPay

## Overview

- **Module:** `pos_self_order_qfpay`
- **Category:** Sales/Point Of Sale
- **Depends:** `pos_qfpay`, `pos_self_order`
- **Auto-install:** `True`
- **Author:** Odoo S.A.
- **License:** LGPL-3
- **Source path:** `odoo/addons/pos_self_order_qfpay/`
- **Odoo version:** 19 CE

## Description

Adds QFPay terminal support to the POS Self Order kiosk app for the Hong Kong market. Customers select items in the self-order interface, then pay via a connected QFPay terminal. QFPay is architecturally distinct from Razorpay and Pine Labs — it uses a **webhook-based push architecture** similar to Adyen, rather than frontend polling. QFPay only supports HKD currency.

QFPay also uniquely includes a **test file** (`tests/test_basic.py`) and **extends `pos.config`** to register itself as a supported kiosk payment terminal.

## Architecture

### Dependency Chain

```
pos.config (base)
    └── pos_self_order_qfpay
            └── overrides _supported_kiosk_payment_terminal() to add 'qfpay'
                    ↕
pos.payment.method (base)
    └── pos_qfpay
            └── adds qfpay_* fields + qfpay_sign_request(), _qfpay_handle_webhook()
                    ↕
            pos_self_order_qfpay
                    overrides _load_pos_self_data_domain()
                    overrides _qfpay_handle_webhook()  ← handles kiosk payment in webhook
                            ↕
            pos_qfpay/controllers/main.py  (QFPayNotificationController)
                    webhook: /qfpay/notify
                            ↕
            pos_self_order (base controller: PosSelfOrderController)
                    provides _send_payment_result()
```

### File Structure

```
pos_self_order_qfpay/
├── __init__.py
├── __manifest__.py               # depends: [pos_qfpay, pos_self_order]
│                                 # assets: includes qfpay.js + self_order static/src/**/*
│                                 # assets_tests: includes qfpay.js tour tests
├── models/
│   ├── __init__.py
│   ├── pos_payment_method.py    # _load_pos_self_data_domain(), _qfpay_handle_webhook()
│   └── pos_config.py            # _supported_kiosk_payment_terminal()
└── tests/
    ├── __init__.py
    └── test_basic.py            # TestPointOfSaleHttpCommon tests for kiosk QFPay
```

## L1: Configuration Extensions

### Fields Added to `pos.payment.method`

No new fields are added by `pos_self_order_qfpay` itself. All QFPay fields are defined in `pos_qfpay`:

| Field (from `pos_qfpay`) | Type | Purpose |
|---|---|---|
| `qfpay_terminal_ip_address` | `Char` | QFPay terminal IP address |
| `qfpay_pos_key` | `Char` | QFPay POS Key (group: `group_pos_manager`) |
| `qfpay_notification_key` | `Char` | QFPay Notification Key (group: `group_pos_manager`) |
| `qfpay_latest_response` | `Char` | Latest response from QFPay (group: `group_pos_manager`) |
| `qfpay_payment_type` | `Selection` | Payment type: `card_payment`, `wx`, `alipay`, `payme`, `union`, `fps`, `octopus`, `unionpay_card`, `amex_card` |

**Constraint (from `pos_qfpay`):** `use_payment_terminal == 'qfpay'` is only valid when `company_id.currency_id.name == 'HKD'`.

**Selection addition (from `pos_qfpay`):** `_get_payment_terminal_selection()` adds `('qfpay', 'QFPay')`.

### `pos.config` Extension

**File:** `models/pos_config.py`

```python
class PosConfig(models.Model):
    _inherit = "pos.config"

    def _supported_kiosk_payment_terminal(self):
        res = super()._supported_kiosk_payment_terminal()
        res.append('qfpay')
        return res
```

**Purpose:** Registers QFPay as a supported kiosk payment terminal in `pos.config`. This is used by the POS kitchen display system (KDS) — orders paid via QFPay are sent to the KDS only after payment succeeds. This is the only self-order provider module that extends `pos.config`.

### POS Config Prerequisites

1. `self_ordering_mode == 'kiosk'`
2. The QFPay payment method must be added to `payment_method_ids`
3. The QFPay notification webhook (`/qfpay/notify`) must be configured in QFPay's merchant portal
4. POS session must be open

## L2: Field Types, Defaults, Provider-Specific Configuration

### `_load_pos_self_data_domain(data, config)` — Domain Extension

**File:** `models/pos_payment_method.py` (lines 9-14)

```python
@api.model
def _load_pos_self_data_domain(self, data, config):
    domain = super()._load_pos_self_data_domain(data, config)
    if config.self_ordering_mode == 'kiosk':
        domain = Domain.OR([[
            ('use_payment_terminal', '=', 'qfpay'),
            ('id', 'in', config.payment_method_ids.ids)
        ], domain])
    return domain
```

Standard OR-domain pattern: in kiosk mode, QFPay terminals linked to this POS config are included in the payment method list.

### `_qfpay_handle_webhook(config, data, uuid)` — Method Override

**File:** `models/pos_payment_method.py` (lines 16-39)

This is the core webhook handler override — it intercepts the QFPay notification processing for kiosk orders:

```python
@api.model
def _qfpay_handle_webhook(self, config, data, uuid):
    if config.self_ordering_mode != 'kiosk':
        return super()._qfpay_handle_webhook(config, data, uuid)

    if data.get('notify_type') != 'payment':
        return

    if data['status'] == "1":  # payment success
        order = self.env['pos.order'].search([('uuid', '=', uuid)], limit=1)
        if order:
            order.add_payment({
                'amount': order.amount_total,
                'payment_date': fields.Datetime.now(),
                'payment_method_id': self.id,
                'payment_ref_no': data['chnlsn'],
                'transaction_id': data['syssn'],
                'pos_order_id': order.id,
            })
            order.action_pos_order_paid()
            order._send_payment_result("Success")
    else:
        order._send_payment_result("fail")
```

**Key points:**
- Only handles `notify_type == 'payment'` — other notification types (e.g., refunds) are ignored
- `status == "1"` indicates payment success (QFPay convention)
- Order lookup uses `uuid` (not `id`) — the `uuid` is the payment order identifier embedded in the QFPay `out_trade_no`
- `self.id` refers to the `pos.payment.method` record — the webhook knows which payment method was used because it is extracted from the `out_trade_no` in `QFPayNotificationController`
- If the payment succeeds, `_send_payment_result("Success")` is called
- If the payment fails, `_send_payment_result("fail")` is called (even if the order lookup fails — `_send_payment_result` is called on a potentially non-existent order?)

**Parent implementation (`pos_qfpay`):**
```python
@api.model
def _qfpay_handle_webhook(self, config, data, uuid):
    config._notify("QFPAY_LATEST_RESPONSE", {
        'response': data,
        'line_uuid': uuid,
    })
```
The parent broadcasts the QFPay response via Odoo's notification system to the POS frontend (for regular POS). The self-order override short-circuits this for kiosk mode and directly processes the payment.

### `_supported_kiosk_payment_terminal()` — PosConfig Extension

**File:** `models/pos_config.py`

```python
def _supported_kiosk_payment_terminal(self):
    res = super()._supported_kiosk_payment_terminal()
    res.append('qfpay')
    return res
```

Appends `'qfpay'` to the list of kiosk payment terminals. This list is used by the POS kitchen display system to determine which orders should be held from the KDS queue until payment is confirmed. Orders paid via QFPay (or any terminal in this list) wait for payment confirmation before appearing on the KDS.

### QFPay Signature (from Parent Module)

**File:** `pos_qfpay/models/pos_payment_method.py` (lines 48-79)

QFPay uses an AES/MD5 signature scheme for webhook verification:

```python
def qfpay_sign_request(self, payload):
    key = self.sudo().qfpay_pos_key
    aes_iv = 'qfpay202306_hjsh'  # constant IV per QFPay docs

    # Sort and format payload
    payload_items = sorted((k, '' if v is None else v) for k, v in payload.items())
    formated_payload = ','.join(f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}" for k, v in payload_items)
    formated_payload = '{' + formated_payload + '}'

    # Generate MD5 digest
    md5 = hashlib.md5()
    md5.update((formated_payload + key).encode('utf-8'))
    digest = md5.hexdigest().upper()

    # Encrypt with AES-CBC
    cipher = Cipher(algorithms.AES(key.encode('utf-8')), modes.CBC(aes_iv.encode('utf-8')))
    ...
```

### QFPay Webhook Controller (from Parent Module)

**File:** `pos_qfpay/controllers/main.py`

The base `QFPayNotificationController` handles incoming QFPay webhook notifications:

```python
@route('/qfpay/notify', type='http', auth='public', methods=['POST'], csrf=False)
def qfpay_notify(self, **kwargs):
    data = json.loads(request.httprequest.get_data())
    # Extract [payment_uuid, session_id, pm_id] from out_trade_no
    [payment_uuid, session_id, pm_id] = trade_no.split('--')
    qfpay_pm_sudo = request.env['pos.payment.method'].sudo().browse(int(pm_id))

    # Verify signature using X-QF-SIGN header
    sign_str = raw_body + qfpay_pm_sudo.qfpay_notification_key.encode()
    computed_sign = hashlib.md5(sign_str).hexdigest().upper()
    if not consteq(computed_sign, request.httprequest.headers.get('X-QF-SIGN')):
        return  # silently ignore invalid signature

    # Call _qfpay_handle_webhook (overridden by pos_self_order_qfpay for kiosk mode)
    qfpay_pm_sudo._qfpay_handle_webhook(pos_session_sudo.config_id, data, payment_uuid)
    return Response('SUCCESS', status=200)
```

**`out_trade_no` format:** `{payment_uuid}--{session_id}--{payment_method_id}`

The `out_trade_no` embeds three pieces of information that allow the webhook to route to the correct payment method and session.

## L3: Cross-Module Integration, Override Pattern, Workflow, Failure Modes

### Cross-Module Integration

#### `pos_qfpay/controllers/main.py` — Webhook Receiver

Provides `/qfpay/notify` endpoint (`auth='public'`, `type='http'`, `csrf=False`). This endpoint:
1. Receives the QFPay HTTP POST notification
2. Parses `out_trade_no` to extract `payment_uuid`, `session_id`, `pm_id`
3. Verifies the `X-QF-SIGN` header using MD5 of (raw_body + notification_key)
4. Calls `_qfpay_handle_webhook()` — which is overridden by `pos_self_order_qfpay` for kiosk mode

#### `pos_self_order` — Base Controller

Provides `_send_payment_result(result)` — called by the webhook handler after processing.

#### `pos.config` — KDS Integration

The `_supported_kiosk_payment_terminal()` override registers QFPay with the KDS so orders are held until payment confirmation.

### Override Pattern

**Pattern: Conditional short-circuit of parent behavior**

```python
def _qfpay_handle_webhook(self, config, data, uuid):
    if config.self_ordering_mode != 'kiosk':
        return super()._qfpay_handle_webhook(config, data, uuid)
    # handle kiosk self-order payment directly
    ...
```

This pattern differs from the other modules: instead of extending with `super()` + additions, QFPay short-circuits the parent behavior entirely when in kiosk mode. For non-kiosk (standard POS) mode, it delegates to the parent, which broadcasts via `_notify()`.

### Payment Workflow (Kiosk Mode — Webhook Push)

```
1. Customer selects items in Self Order app
       ↓
2. Customer selects QFPay payment method
   → QFPay.js initiates payment via QFPay's client SDK
   → Frontend polls or waits for webhook push from QFPay servers
       ↓
3. QFPay processes payment on their servers
   → QFPay server sends HTTP POST to /qfpay/notify (webhook)
       ↓
4. QFPayNotificationController receives webhook
   → Extracts [payment_uuid, session_id, pm_id] from out_trade_no
   → Verifies X-QF-SIGN using MD5(notification_key)
   → Calls _qfpay_handle_webhook() → OVERRIDDEN by pos_self_order_qfpay
       ↓
5. pos_self_order_qfpay._qfpay_handle_webhook() processes:
   - Checks notify_type == 'payment'
   - Checks status == "1" (success)
   - Looks up order by uuid
   - add_payment() + action_pos_order_paid()
   - _send_payment_result("Success") → bus notification to frontend
       ↓
6. Frontend receives bus notification, shows success screen
   → order proceeds to kitchen/fulfillment
```

**Key difference from Adyen:** QFPay uses a **push webhook** similar to Adyen, but the webhook is routed through `_qfpay_handle_webhook()` override rather than a separate controller class override. There is no polling endpoint (unlike Razorpay/Pine Labs).

### Failure Modes

| Failure Mode | Trigger | Handling | User Experience |
|---|---|---|---|
| QFPay server unreachable | Webhook never arrives | Frontend times out waiting for `_send_payment_result` | Customer sees timeout, can retry |
| Invalid QFPay signature | `X-QF-SIGN` header mismatch | Logs warning, silently returns | QFPay retries; order may be stuck |
| Non-payment notification | `notify_type != 'payment'` | Ignored (returns immediately) | No action taken |
| Order not found | `order.search([('uuid', '=', uuid)])` returns empty | Payment recorded but `_send_payment_result` called on empty recordset | Potential issue — `_send_payment_result` called on empty set |
| Order already paid | `action_pos_order_paid()` called on paid order | ORM prevents duplicate payment | No double-payment possible |
| Webhook fires before frontend ready | Race condition | `order.search()` finds order; payment recorded | Payment goes through |
| `self_ordering_mode != 'kiosk'` | Regular POS QFPay payment | Delegates to parent `_qfpay_handle_webhook` | Standard POS QFPay flow |

**Potential issue:** In the failure branch (`else: order._send_payment_result("fail")`), if the order search returns no records, `_send_payment_result("fail")` is called on an empty recordset. This is likely a no-op but represents incomplete error handling.

### Test Coverage

QFPay is the **only** self-order provider module with a dedicated test file (`tests/test_basic.py`):

```python
class TestSelfOrderKioskQFPay(TestPointOfSaleHttpCommon, AccountTestInvoicingCommon):
    def test_kiosk_qfpay(self):
        res = self.pos_config.load_self_data()
        pm = res.get('pos.payment.method', [])
        self.assertEqual(len(pm), 1)
        self.assertEqual(pm[0]['name'], 'Qfpay')

        after_pay_kds = self.env['pos.config']._supported_kiosk_payment_terminal()
        self.assertTrue('qfpay' in after_pay_kds)

    def test_tour_kiosk_qfpay_order(self):
        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()
        with patch('odoo.addons.pos_qfpay.controllers.main.consteq', lambda a, b: True):
            self.start_tour(self_route, "kiosk_qfpay_order")
```

The tour test mocks `consteq` to bypass HMAC verification during testing.

## L4: Version Changes Odoo 18→19, Security Notes

### Version Changes (Odoo 18 → 19)

`pos_self_order_qfpay` is **new in Odoo 19**. `pos_qfpay` existed in Odoo 18 for standard POS, but the self-order kiosk extension was added in Odoo 19.

### PCI Compliance Notes

QFPay acts as the PCI DSS middleware for card transactions. For alternative payment methods (Alipay, WeChat Pay, etc.), compliance depends on the respective payment method provider. Odoo receives only:

- `syssn` — QFPay's system serial number (transaction reference)
- `chnlsn` — channel serial number
- `pos_order_id` (embedded in `out_trade_no`)

QFPay does not return card details in the webhook — card data is managed entirely within the QFPay SDK and their servers.

### Credentials Storage

- `qfpay_pos_key` and `qfpay_notification_key` are stored on `pos.payment.method` with `groups='point_of_sale.group_pos_manager'`
- Both are sensitive and should be protected at rest in production

### Signature Verification

QFPay uses MD5-based signature verification:

```python
sign_str = raw_body + qfpay_notification_key.encode()
computed_sign = hashlib.md5(sign_str).hexdigest().upper()
if not consteq(computed_sign, request.httprequest.headers.get('X-QF-SIGN')):
    _logger.warning("QFPay notification signature mismatch")
    return  # silently ignore
```

- Uses `consteq()` for constant-time comparison (prevents timing attacks)
- MD5 is used because QFPay's API requires it (not Odoo's choice)
- **Note:** MD5 is cryptographically broken for collision resistance, but for HMAC-style verification (where only one party knows the secret key), MD5 remains secure against forgery as long as the key is strong

### `auth="public"` Webhook Security

The `/qfpay/notify` endpoint uses `auth='public'` because QFPay's servers call it without Odoo session cookies. Security is enforced through:
1. **Signature verification** — `X-QF-SIGN` header validated with `qfpay_notification_key`
2. **`consteq()` comparison** — constant-time comparison prevents timing attacks
3. **`out_trade_no` parsing** — the webhook extracts `payment_method_id` from the trade number and looks it up in the database

### HKD Currency Constraint

```python
@api.constrains('use_payment_terminal')
def _check_qfpay_terminal(self):
    if any(record.use_payment_terminal == 'qfpay' and
           record.company_id.currency_id.name != 'HKD' for record in self):
        raise UserError(_('QFPay is only valid for HKD Currency'))
```

This enforces HKD at the ORM level, matching QFPay's market focus (Hong Kong).

### HKD vs INR: Module Audience

| Module | Currency | Primary Market |
|---|---|---|
| Razorpay | INR | India |
| Pine Labs | INR | India |
| Adyen | Multi-currency | Global |
| QFPay | HKD | Hong Kong |

QFPay and Adyen support more payment methods beyond card (Alipay, WeChat Pay, PayMe, etc.) as reflected in the `qfpay_payment_type` selection field.

## Related

- [Modules/pos_self_order](Modules/pos_self_order.md) — Base self-order module
- [Modules/pos_qfpay](Modules/pos_qfpay.md) — QFPay terminal integration
- [Modules/pos_self_order_razorpay](Modules/pos_self_order_razorpay.md) — Razorpay terminal in self-order (polling, INR)
- [Modules/pos_self_order_pine_labs](Modules/pos_self_order_pine_labs.md) — Pine Labs terminal in self-order (polling, paisa, INR)
- [Modules/pos_self_order_adyen](Modules/pos_self_order_adyen.md) — Adyen terminal in self-order (push webhook, multi-currency)
