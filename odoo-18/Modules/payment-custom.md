---
Module: payment_custom
Version: Odoo 18
Type: Integration
---

# payment_custom — Generic / Manual Payment Provider

`payment_custom` provides a **manual, no-API** payment provider based on displaying payment instructions to the customer. Transactions are immediately set to `pending` status and require manual confirmation by an administrator.

> Previously named `payment_transfer` (pre-16.0). Renamed and refactored in Odoo 16.0 to support duplicate providers via the `custom_mode` field.

---

## Module Facts

| Attribute | Value |
|---|---|
| **Code** | `custom` |
| **Module Key** | `payment_custom` |
| **Depends** | `payment` |
| **License** | LGPL-3 |
| **API** | None — no external gateway |
| **Tokenization** | No |
| **Refund** | No |
| **Manual Capture** | No (transactions are always `pending` until manually confirmed) |
| **Default Payment Method** | `wire_transfer` (code: `wire_transfer`) |

---

## Provider Model: `payment.provider` (extends)

Path: `addons/payment_custom/models/payment_provider.py`

### Fields Added

| Field | Type | Required | Groups | Notes |
|---|---|---|---|---|
| `code` | Selection | — | — | Extended with `('custom', "Custom")` |
| `custom_mode` | Selection | Yes (if code=`custom`) | — | `('wire_transfer', "Wire Transfer")` |
| `qr_code` | Boolean | No | — | Enables QR code display on the payment page |

### SQL Constraint

```python
_sql_constraints = [(
    'custom_providers_setup',
    "CHECK(custom_mode IS NULL OR (code = 'custom' AND custom_mode IS NOT NULL))",
    "Only custom providers should have a custom mode."
)]
```

Enforces that `custom_mode` is only set when `code = 'custom'`. Prevents invalid combinations.

### Key Methods

#### `action_recompute_pending_msg()`
Recomputes the `pending_msg` (bank transfer instructions) from all bank journals of the provider's company.

```python
def action_recompute_pending_msg(self):
    """ Recompute the pending message to include the existing bank accounts. """
    for provider in self.filtered(lambda p: p.custom_mode == 'wire_transfer'):
        company_id = provider.company_id.id
        accounts = self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(company_id),
            ('type', '=', 'bank'),
        ]).bank_account_id
        account_names = "".join(f"<li><pre>{account.display_name}</pre></li>" ...)
        provider.pending_msg = f'<div>...<ul>{account_names}</ul>...</div>'
```

Called by:
1. `create()` hook — immediately nullifies then recomputes `pending_msg` for wire transfer providers
2. The "Recompute Pending Message" wizard button (manual trigger)
3. `_transfer_ensure_pending_msg_is_set()` — called on module `post_init_hook`

#### `create()`
```python
@api.model_create_multi
def create(self, values_list):
    providers = super().create(values_list)
    providers.filtered(lambda p: p.custom_mode == 'wire_transfer').pending_msg = None
    return providers
```
On creation, wire transfer providers have `pending_msg` nullified so the post-init hook can recompute it with the correct company accounts.

#### `_get_removal_domain(provider_code, custom_mode='', **kwargs)`
Extends the base removal domain to also filter by `custom_mode`. This allows each custom sub-mode (e.g., wire transfer) to be independently disabled/removed.

```python
@api.model
def _get_removal_domain(self, provider_code, custom_mode='', **kwargs):
    res = super()._get_removal_domain(provider_code, custom_mode=custom_mode, **kwargs)
    if provider_code == 'custom' and custom_mode:
        return AND([res, [('custom_mode', '=', custom_mode)]])
    return res
```

#### `_get_removal_values()`
```python
@api.model
def _get_removal_values(self):
    res = super()._get_removal_values()
    res['custom_mode'] = None
    return res
```
Nullifies `custom_mode` when the provider is uninstalled/disabled.

#### `_get_default_payment_method_codes()`
Returns `{'wire_transfer'}` for `custom` providers with `custom_mode == 'wire_transfer'`.

#### `_transfer_ensure_pending_msg_is_set()`
Called by the post-init hook. Finds all wire transfer providers missing a `pending_msg` and recomputes it.

---

## Transaction Model: `payment.transaction` (extends)

Path: `addons/payment_custom/models/payment_transaction.py`

### Key Methods

#### `_get_specific_rendering_values(processing_values)`
Returns the form submission URL and reference for the inline/redirect form.

```python
def _get_specific_rendering_values(self, processing_values):
    res = super()._get_specific_rendering_values(processing_values)
    if self.provider_code != 'custom':
        return res
    return {
        'api_url': CustomController._process_url,  # '/payment/custom/process'
        'reference': self.reference,
    }
```

#### `_get_communication()`
Returns the payment reference the customer should use in their transfer. Checks in order: `invoice.payment_reference`, `sale_order.reference`, then `self.reference`.

```python
def _get_communication(self):
    self.ensure_one()
    communication = ""
    if hasattr(self, 'invoice_ids') and self.invoice_ids:
        communication = self.invoice_ids[0].payment_reference
    elif hasattr(self, 'sale_order_ids') and self.sale_order_ids:
        communication = self.sale_order_ids[0].reference
    return communication or self.reference
```

#### `_get_tx_from_notification_data(provider_code, notification_data)`
Finds the transaction by `reference` in the POST data. Falls back to search if the normal ORM lookup fails (which it won't for normal flow).

#### `_process_notification_data(notification_data)`
```python
def _process_notification_data(self, notification_data):
    super()._process_notification_data(notification_data)
    if self.provider_code != 'custom':
        return
    self._set_pending()  # Always set to pending — no auto-confirmation
```

**Critical behavior**: Transactions are ALWAYS set to `pending`, not `done`. The customer is instructed to make a bank transfer; the merchant must manually confirm receipt of funds.

#### `_log_received_message()`
Filters out `custom` providers from the received message log — no external notification to log since there's no API.

#### `_get_sent_message()`
Overrides the "transaction sent" message for custom providers:
```
"The customer has selected {provider_name} to make the payment."
```

---

## Controller: `CustomController`

Path: `addons/payment_custom/controllers/main.py`

### Endpoint

| Route | Method | Auth | CSRF |
|---|---|---|---|
| `/payment/custom/process` | POST | `public` | `False` |

### `custom_process_transaction(**post)`

```python
@route(_process_url, type='http', auth='public', methods=['POST'], csrf=False)
def custom_process_transaction(self, **post):
    _logger.info("Handling custom processing with data:\n%s", pprint.pformat(post))
    request.env['payment.transaction'].sudo()._handle_notification_data('custom', post)
    return request.redirect('/payment/status')
```

1. Receives POST data (contains `reference`)
2. Calls `_handle_notification_data('custom', post)` which invokes `_process_notification_data` → sets tx to `pending`
3. Redirects the customer to the payment status page

---

## Payment Method: `wire_transfer`

Defined in `data/payment_method_data.xml` (noupdate):

```xml
<record id="payment_method_wire_transfer" model="payment.method">
    <field name="name">Wire Transfer</field>
    <field name="code">wire_transfer</field>
    <field name="sequence">1000</field>
    <field name="active">False</field>  <!-- Must be activated per-provider -->
    <field name="image" type="base64" file="payment_custom/static/img/wire_transfer.png"/>
    <field name="support_tokenization">False</field>
    <field name="support_express_checkout">False</field>
    <field name="support_refund">none</field>
</record>
```

Note: `active=False` by default — must be explicitly activated when enabling the provider.

---

## Default Provider: `payment.payment_provider_transfer`

Defined in `data/payment_provider_data.xml` (noupdate):

- `code` = `'custom'`
- `custom_mode` = `'wire_transfer'`
- `pending_msg` cleared via `eval="False"` then recomputed by `_transfer_ensure_pending_msg_is_set()`
- Payment method: `payment_method_wire_transfer`
- Redirect form view used

---

## Hooks

### `post_init_hook` (via `payment.setup_provider`)
1. Calls `setup_provider(env, 'custom')`
2. Calls `_transfer_ensure_pending_msg_is_set()` to populate bank account info into `pending_msg`

### `uninstall_hook` (via `payment.reset_payment_provider`)
Calls `reset_payment_provider(env, 'custom')` which nullifies `custom_mode`.

---

## L4: How It Differs From Other Providers

| Aspect | `payment_custom` (Wire Transfer) | API Providers (Stripe, Authorize, Razorpay) |
|---|---|---|
| **API Calls** | None | Always |
| **Auto Confirmation** | Never — always `pending` | Webhook-driven, automatic |
| **Payment Flow** | Customer reads instructions, initiates transfer externally | Embedded form, real-time payment |
| **State Transitions** | Manual only | `pending` → `authorized` → `done` automatically |
| **Refund** | Manual (no provider support) | Provider API refund flow |
| **Tokenization** | Not supported | Supported |
| **Confirmation Method** | Admin clicks "Confirm" on the transaction | Webhook POST |
| **Testability** | Works identically in test/live mode | Requires test credentials for sandbox |

### When to Use `payment_custom`

- **B2B transactions** where wire transfer is standard practice
- **High-value sales** where credit card fees are undesirable
- **Regions** where online payment gateways are unavailable
- **Multi-company Odoo setups** — each company can have its own bank details auto-populated
- **Offline payments** like checks, cash on delivery (by creating additional `custom_mode` options via customization)

### The `pending_msg` Auto-Generation

The `pending_msg` is dynamically built from all **bank journals** of the provider's company:
- Searches `account.journal` with `type='bank'` for the company
- Renders each bank account's `display_name` as an HTML `<li><pre>` item
- Triggered: on provider creation, on "Recompute" button click, and on module install

This means adding a new bank account journal automatically updates the wire transfer instructions for all active wire transfer providers of that company.

---

## Related Documentation

- [[Core/Payment Framework]] — base payment architecture
- [[Modules/payment]] — core payment module
- [[Modules/payment-authorize]] — Authorize.Net provider
- [[Modules/payment-razorpay]] — Razorpay provider

---

**Tags:** #odoo #odoo18 #payment #integration #manual-payment
