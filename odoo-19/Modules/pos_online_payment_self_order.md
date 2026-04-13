# POS Online Payment Self Order

## Overview

- **Name:** POS Self-Order / Online Payment
- **Category:** Sales/Point of Sale
- **Version:** 1.0
- **Depends:** `pos_online_payment`, `pos_self_order`
- **Auto-install:** True
- **Author:** Odoo S.A.
- **License:** LGPL-3

## L1 — How Online Payment Works in Self-Order POS

`pos_online_payment_self_order` bridges **POS self-order** with **online payment providers** (Stripe, Authorize.Net, etc.), enabling customers at a self-order kiosk or mobile device to pay using an online payment method — typically via a QR code that redirects to a payment page.

**Two self-order modes are supported:**

| Mode | Payment Mechanism | Module Role |
|------|------------------|-------------|
| **Kiosk** | Payment terminal (card reader) + online payment fallback | `PosPaymentMethod._load_pos_self_data_domain` adds online payment methods |
| **Mobile** (with `self_ordering_service_mode='each') | QR code → online payment page | `PosPaymentMethod._load_pos_self_data_domain` filters to the configured online payment method |

**Core capability:** Allows the POS Self-Order app to accept payments through online payment providers (not just physical payment terminals). This is essential for mobile self-order where there is no terminal hardware.

---

## L2 — Fields, Methods, Constraints

### Models Extended (4 models)

#### 1. `pos.config` — via `_inherit = 'pos.config'`

**New field:**

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `self_order_online_payment_method_id` | `Many2one(pos.payment.method)` | `False` | The online payment method to use when a customer pays a self-order online. Only methods with `is_online_payment=True` are selectable. |

**Domain:** `domain=[('is_online_payment', '=', True)]` — only published online payment providers appear.

**Methods on `pos.config`:**

| Method | Purpose |
|--------|---------|
| `_check_self_order_online_payment_method_id()` | `@api.constrains` — validates that the selected online payment method has at least one published provider supporting the POS config's currency |
| `_get_self_ordering_data()` | Extends parent to include the online payment method data in the POS session's self-order payload |
| `has_valid_self_payment_method()` | Returns `True` if the config has a valid payment method for self-order (mobile: uses `self_order_online_payment_method_id`; kiosk: uses any online payment in `payment_method_ids`) |

#### 2. `pos.order` — via `_inherit = 'pos.order'`

**New computed/stored field:**

| Field | Type | Compute | Purpose |
|-------|------|---------|---------|
| `use_self_order_online_payment` | `Boolean` (readonly) | `_compute_use_self_order_online_payment` | Whether this order uses online payment (derived from config's `self_order_online_payment_method_id`) |

**Key methods on `pos.order`:**

| Method | Purpose |
|--------|---------|
| `_compute_use_self_order_online_payment()` | `True` if `config_id.self_order_online_payment_method_id` is set |
| `_compute_online_payment_method_id()` | Overrides base to set `online_payment_method_id` from config when `use_self_order_online_payment=True` |
| `get_order_to_print()` | Locks the order row (`SELECT ... FOR UPDATE NOWAIT`) to prevent concurrent printing; raises `ValueError` if already printed |
| `get_and_set_online_payments_data()` | Extends parent to update `use_self_order_online_payment` based on payment amount being zero |
| `_send_notification_online_payment_status()` | Sends WebSocket notification (`ONLINE_PAYMENT_STATUS`) to the POS frontend with current order and payment data |
| `_load_pos_self_data_fields()` | Adds `online_payment_method_id` and `next_online_payment_amount` to self-order data payload |

**Write behavior:** The `write()` method is overridden to handle the `use_self_order_online_payment` field specially — it cannot be manually changed on non-draft orders, preventing accidental corruption of the online payment state.

#### 3. `pos.payment.method` — via `_inherit = 'pos.payment.method'`

**Methods:**

| Method | Purpose |
|--------|---------|
| `_load_pos_self_data_domain(data, config)` | Returns the domain of payment methods to include in self-order data. In **kiosk mode**: includes all online payment methods assigned to the POS. In **mobile mode**: only the specific `self_order_online_payment_method_id` from the config. |

**Domain logic:**

```python
# Kiosk mode
Domain.OR([
    [('is_online_payment', '=', True), ('id', 'in', config.payment_method_ids.ids)],
    domain  # parent domain
])

# Mobile mode
[('is_online_payment', '=', True), ('id', '=', config.self_order_online_payment_method_id.id)]
```

#### 4. `payment.transaction` — via `_inherit = 'payment.transaction'`

**Methods:**

| Method | Purpose |
|--------|---------|
| `_process_pos_online_payment()` | Extends parent. After processing, if the transaction is `authorized` or `done` and linked to a self-order, sends a `'success'` status notification to the POS frontend via `_send_notification_online_payment_status`. |
| `_process(provider_code, payment_data)` | After processing, if the transaction is a confirmed self-order payment, triggers the `payment.cron_post_process_payment_tx` cron for post-processing. |
| `_is_self_order_payment_confirmed()` | Returns `True` if: `pos_order_id` exists AND state is `authorized`/`done` AND `pos_order_id.source` is `mobile` or `kiosk`. |

#### 5. `res.config.settings` — via `_inherit = 'res.config.settings'`

**Related field (not new):**

```python
pos_self_order_online_payment_method_id = fields.Many2one(
    related='pos_config_id.self_order_online_payment_method_id',
    readonly=False
)
```

This exposes the `pos.config` online payment method in the POS settings form.

### Constraints

#### `@api.constrains` on `pos.config`

```python
@api.constrains('self_order_online_payment_method_id')
def _check_self_order_online_payment_method_id(self):
    for config in self:
        if (config.self_ordering_mode == 'mobile'
            and config.self_ordering_service_mode == 'each'
            and config.self_order_online_payment_method_id
            and not config.self_order_online_payment_method_id._get_online_payment_providers(
                config.id, error_if_invalid=True
            )):
            raise ValidationError(_("The online payment method used for self-order "
                "in a POS config must have at least one published payment provider "
                "supporting the currency of that POS config."))
```

| Condition That Triggers | Why |
|------------------------|-----|
| Mode = 'mobile', service_mode = 'each', online_payment_method set, but no published provider for POS currency | Prevents configuration where self-order payments would always fail |

---

## L3 — Cross-Model, Override Pattern, Workflow Trigger

### Cross-Model Architecture

```
pos_online_payment_self_order
  ├─ pos.config:           self_order_online_payment_method_id field
  │   └─ _check_self_order_online_payment_method_id()
  │   └─ _get_self_ordering_data()
  │   └─ has_valid_self_payment_method()
  ├─ pos.order:            use_self_order_online_payment field
  │   └─ _compute_use_self_order_online_payment()
  │   └─ _compute_online_payment_method_id()
  │   └─ get_order_to_print()
  │   └─ get_and_set_online_payments_data()
  │   └─ _send_notification_online_payment_status()
  │   └─ _load_pos_self_data_fields()
  ├─ pos.payment.method:   _load_pos_self_data_domain()
  └─ payment.transaction:  _process_pos_online_payment()
                            _process()
                            _is_self_order_payment_confirmed()

pos_online_payment  (base module — handles online payment flow)
pos_self_order      (base module — handles self-order flow)
```

### Payment Flow (Mobile Self-Order with Online Payment)

```
1. Customer orders via mobile self-order QR code
2. Customer taps "Pay Online"
3. POS frontend calls get_and_set_online_payments_data()
   └─ pos_online_payment_self_order sets use_self_order_online_payment=True
4. Customer scanned/redirected to payment provider's hosted page
5. Customer enters card details on provider page
6. Provider webhooks Odoo with payment result
7. payment.transaction._process() called
   └─ _is_self_order_payment_confirmed() == True
   └─ cron payment.cron_post_process_payment_tx triggered
8. payment.transaction._process_pos_online_payment() called
   └─ _send_notification_online_payment_status('success') sent via WebSocket
9. POS frontend receives success notification
10. Order automatically validated/completed in POS
```

### Workflow Trigger Summary

| Trigger | Model | Method | Side Effect |
|---------|-------|--------|-------------|
| POS session opens | `pos.order` (create) | `create()` | `use_self_order_online_payment` auto-set from config |
| Payment completed on provider side | `payment.transaction` | `_process_pos_online_payment()` | WebSocket notification sent to POS |
| Self-order confirmed as paid | `payment.transaction` | `_process()` | Post-processing cron triggered |
| Customer taps "Pay Online" | `pos.order` | `get_and_set_online_payments_data()` | `use_self_order_online_payment` updated if amount is zero |
| Order print requested | `pos.order` | `get_order_to_print()` | Row locked with `FOR UPDATE NOWAIT`; duplicate print prevented |

---

## L4 — Version Changes: Odoo 18 to Odoo 19

### What Changed in the Odoo 18 to Odoo 19 Transition

The module was **significantly redesigned** between Odoo 18 and Odoo 19. The core functionality is the same, but many methods have been refactored or renamed.

### Key Changes

#### 1. `get_order_to_print()` — New in Odoo 19

The `get_order_to_print()` method with `FOR UPDATE NOWAIT` row locking was **added in Odoo 19** as a concurrency safety measure. In Odoo 18, this method likely did not exist or had simpler behavior.

```python
# Odoo 19 — prevents concurrent print attempts
def get_order_to_print(self):
    self.ensure_one()
    self.env.cr.execute(
        "SELECT id FROM pos_order WHERE id = %s FOR UPDATE NOWAIT",
        (self.id,)
    )
    if self.nb_print > 0:
        raise ValueError("This order has already been printed automatically.")
    self.nb_print += 1
    return self.read_pos_data([], self.config_id.id)
```

#### 2. `Domain` class usage (Odoo 19)

In `_load_pos_self_data_domain` on `pos.payment.method`, Odoo 19 uses the new `Domain` utility class:

```python
# Odoo 18: Manual list concatenation
domain = [('is_online_payment', '=', True), ('id', '=', ...)] + domain

# Odoo 19: Domain.OR() utility
domain = Domain.OR([
    [('is_online_payment', '=', True), ('id', 'in', config.payment_method_ids.ids)],
    domain
])
```

#### 3. `has_valid_self_payment_method()` behavior change

| Aspect | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| Mobile mode check | Used `payment_method_ids` | Uses `self_order_online_payment_method_id` |
| Kiosk mode check | Different logic | Uses any `is_online_payment` in `payment_method_ids` |

#### 4. `write()` override on `pos.order`

The protective write override for `use_self_order_online_payment` (preventing manual changes on non-draft orders) was **added in Odoo 19**. In Odoo 18, this field was likely not write-protected.

#### 5. `_send_notification_online_payment_status()` — New payload

The `pos.order` notification method in Odoo 19 sends a richer payload including `pos.order` and `pos.payment` data read via `_load_pos_self_data_fields`, which was added in Odoo 19.

### Migration Notes

| Item | Action Required |
|------|----------------|
| `get_order_to_print()` row locking | New behavior; no migration needed — Odoo 19 code is the reference |
| `Domain.OR()` usage | If backporting to Odoo 18, replace with manual list concatenation |
| `has_valid_self_payment_method()` | Logic differs; if overriding, compare both versions |
| `use_self_order_online_payment` write protection | Odoo 18 code may allow manual writes; verify expected behavior |

### Conclusion

`pos_online_payment_self_order` received **moderate changes** in the Odoo 18 to 19 transition. The module is architecturally the same but has better concurrency safety (`FOR UPDATE NOWAIT`), improved domain composition (`Domain.OR`), and write-protection for the online payment flag.

---

## Assets

- `pos_self_order.assets`: Frontend app code (QR code generation, payment flow)
- `point_of_sale._assets_pos`: Overrides for POS backend
- `web.assets_tests`: Test tours for multi-table orders
- `pos_self_order.assets_tests`: Test tours for mobile online payment
- `web.assets_unit_tests`: Unit tests for payment flow

## Related

- [Modules/pos_self_order](Modules/pos_self_order.md) — Base self-order module
- [Modules/pos_online_payment](Modules/pos_online_payment.md) — Base online payment handling
- [Modules/payment_authorize](Modules/payment_authorize.md) — Authorize.Net payment provider
