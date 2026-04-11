---
Module: pos_online_payment_self_order
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_online_payment_self_order #self_order #online_payment
---

## Overview

Integrates online payment with self-order (mobile QR-code ordering). Allows customers to pay for self-order orders online via the same payment providers as `pos_online_payment`, but via the self-order interface rather than cashier POS.

**Depends:** `pos_online_payment`, `pos_self_order`

---

## Models

### `pos.config` (Extension)
**Inheritance:** `pos.config`

| Field | Type | Notes |
|---|---|---|
| `self_order_online_payment_method_id` | Many2one `pos.payment.method` | Domain: `is_online_payment=True`. Only for mobile mode with pay-after-each. |

**Methods:**
- `_check_self_order_online_payment_method_id()` -> `@api.constrains`: only enforces if `self_ordering_mode='mobile'` AND `self_ordering_service_mode='each'` AND method has valid provider
- `_get_self_ordering_data()` -> extends parent to include `self_order_online_payment_method` in payment methods data

---

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

**Methods:**
- `_load_pos_self_data_domain(data)` -> if kiosk mode: adds `('is_online_payment', '=', True)` to existing domain (OR with existing Adyen/Stripe terminals). If mobile: returns `[('is_online_payment', '=', True)]` (all online payment methods)

---

### `pos.order` (Extension)
**Inheritance:** `pos.order`

| Field | Type | Notes |
|---|---|---|
| `use_self_order_online_payment` | Boolean (compute+store) | Whether order uses self-order online payment |

**Computed:** `_compute_use_self_order_online_payment` -> `bool(config.self_order_online_payment_method_id)`

**Methods:**
- `create(vals_list)` -> auto-sets `use_self_order_online_payment=True` when `self_order_online_payment_method_id` is configured
- `write(vals)` -> allows writing `use_self_order_online_payment` only for draft orders matching config's self-order online payment setting
- `_compute_online_payment_method_id()` -> if `use_self_order_online_payment=True`: uses `config.self_order_online_payment_method_id`; otherwise delegates to parent
- `get_and_set_online_payments_data(next_online_payment_amount=False)` -> extends parent: when next amount is 0 and self_order_online_payment_method_id exists, switches order to use self-order online payment

---

### `res.config.settings` (Extension)
**Inheritance:** `res.config.settings`

| Field | Type | Notes |
|---|---|---|
| `pos_self_order_online_payment_method_id` | Many2one related to `pos_config_id.self_order_online_payment_method_id` | readonly=False |

---

## Controllers

### `pos_online_payment_self_order.controllers.payment_portal.PaymentPortalSelfOrder`
**Inheritance:** `pos_online_payment.controllers.payment_portal.PaymentPortal`

**Methods:**
- `pos_order_pay(pos_order_id, access_token=None, exit_route=None)` -> overrides parent: sends `progress` notification via `_send_notification_payment_status` before delegating to parent
- `pos_order_pay_confirmation(pos_order_id, tx_id=None, access_token=None, exit_route=None, **kwargs)` -> overrides parent: after processing, sends `success` or `fail` notification based on transaction state
- `_send_notification_payment_status(pos_order_id, status)` -> broadcasts `ONLINE_PAYMENT_STATUS` notification with status (`progress`/`success`/`fail`) and order data

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Mobile vs kiosk online payment:** In mobile (QR menu) mode, online payments use `self_order_online_payment_method_id`. In kiosk mode, the regular `pos.payment.method` with `is_online_payment=True` from the config's payment methods is used.

2. **`use_self_order_online_payment` toggle:** This field allows switching between regular online payment and self-order online payment on the same order. It's computed-stored and only changeable for draft orders with matching config settings.

3. **Payment method domain filter:** In mobile mode, the `_load_pos_self_data_domain` on `pos.payment.method` returns ALL online payment methods (not just those in payment_method_ids) — allowing the self-order to access online payment methods that may not be configured in the POS config.

4. **Three-step notification flow:** The controller sends `progress` when payment starts, then `success` or `fail` after the transaction completes. The self-order frontend uses these notifications to update the UI (e.g., "Payment in progress...", "Payment successful!", "Payment failed").
