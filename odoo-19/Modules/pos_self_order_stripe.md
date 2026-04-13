# POS Self Order Stripe

## Overview

- **Name:** POS Self Order Stripe
- **Category:** Sales/Point Of Sale
- **Depends:** `pos_stripe`, `pos_self_order`
- **Auto-install:** True
- **Author:** Odoo S.A.
- **License:** LGPL-3

## L1 — How Stripe Payment Works in Self-Order POS

`pos_self_order_stripe` is a thin glue module that enables **Stripe Terminal** as a payment method inside the **POS Self-Order** kiosk/mobile interface. It extends the standard Stripe terminal integration (from `pos_stripe`) to work within the self-order flow.

**Core capability:** When a customer completes a self-order at a kiosk terminal, the POS can request a payment from Stripe Terminal directly — no cashier involvement required. The module bridges `pos_stripe`'s terminal API with `pos_self_order`'s kiosk data loading pipeline.

**Two self-order modes supported:**

| Mode | Description | Payment Flow |
|------|-------------|--------------|
| **Kiosk** | Customer-facing terminal; customer walks up, orders, pays | Stripe Terminal via `_payment_request_from_kiosk` |
| **Mobile** | Customer uses own phone via QR code; pays online | N/A for this module (handled by `pos_online_payment_self_order`) |

---

## L2 — Field Types, Defaults, Constraints

### Models Extended

#### `pos.payment.method` (via `_inherit = 'pos.payment.method'`)

No new fields are defined on the model. The module extends two methods:

| Method | Signature | Purpose |
|--------|-----------|---------|
| `_payment_request_from_kiosk` | `(order) → dict` | Delegates payment request to Stripe when in kiosk mode |
| `_load_pos_self_data_domain` | `(data, config) → Domain` | Filters which payment methods are available in self-order data |

### Method Extension Details

#### `_payment_request_from_kiosk(self, order)`

```python
def _payment_request_from_kiosk(self, order):
    if self.use_payment_terminal != 'stripe':
        return super()._payment_request_from_kiosk(order)
    else:
        return self.stripe_payment_intent(order.amount_total)
```

| Condition | Behavior |
|-----------|----------|
| Payment terminal is **not** Stripe | Delegates to `pos_payment` base class (likely raises error or returns not-supported) |
| Payment terminal **is** Stripe | Calls `stripe_payment_intent()` on the payment method recordset to create/initiate a Stripe payment intent for the order total |

The `stripe_payment_intent()` method is defined in `pos_stripe` on `pos.payment.method`. It handles the full Stripe Terminal flow including generating a client secret and returning the payment intent details to the frontend.

#### `_load_pos_self_data_domain(self, data, config)`

```python
@api.model
def _load_pos_self_data_domain(self, data, config):
    domain = super()._load_pos_self_data_domain(data, config)
    if config.self_ordering_mode == 'kiosk':
        domain = Domain.OR([
            [('use_payment_terminal', '=', 'stripe'), ('id', 'in', config.payment_method_ids.ids)],
            domain
        ])
    return domain
```

| Context | Behavior |
|---------|----------|
| `self_ordering_mode == 'kiosk'` | Adds Stripe terminal payment methods (that are assigned to this POS config) to the self-order data domain. This makes them available in the kiosk's data payload. |
| Other modes (mobile, etc.) | Returns `super()` domain — Stripe terminal is not relevant for mobile web ordering |

**Why this matters:** In `pos_self_order`, the `_load_pos_self_data_domain` method on `pos.payment.method` filters which payment methods are sent to the POS frontend. By adding the Stripe terminal filter in kiosk mode, the module ensures that Stripe payment methods appear in the self-order UI and are selectable by the customer.

### Defaults

No new defaults are defined. Stripe-specific configuration (API keys, terminal settings) comes from the `pos_stripe` provider configuration.

### Constraints

No new constraints are defined. All validation is handled by `pos_stripe` (provider credentials) and `pos_self_order` (mode configuration).

---

## L3 — Cross-Model, Override Pattern, Workflow Trigger

### Cross-Model Architecture

```
pos_self_order_stripe
  └─ extends pos.payment.method
       ├── _payment_request_from_kiosk()   → calls stripe_payment_intent()
       └── _load_pos_self_data_domain()    → adds stripe terminal filter in kiosk mode

pos_stripe
  └─ defines stripe_payment_intent() on pos.payment.method
       └── Initiates Stripe Terminal payment intent via Stripe API

pos_self_order
  └─ defines base _load_pos_self_data_domain() on pos.payment.method
       └── Base filter for self-order payment methods

payment_authorize
  └─ separate provider; not involved here
```

### Payment Flow (Kiosk Mode)

```
1. Customer selects products on kiosk screen
2. Customer taps "Pay" button
3. POS frontend calls _payment_request_from_kiosk() on pos.payment.method
4. pos_self_order_stripe checks: use_payment_terminal == 'stripe'
5. Calls self.stripe_payment_intent(order.amount_total)  [from pos_stripe]
6. Stripe Terminal SDK on hardware device prompts card tap/insert
7. Payment result returned to POS
8. Order marked as paid
```

### Override Pattern

**Pattern:** Early-return guard + super() delegation.

```python
def _payment_request_from_kiosk(self, order):
    if self.use_payment_terminal != 'stripe':
        return super()._payment_request_from_kiosk(order)  # Not our concern
    else:
        return self.stripe_payment_intent(order.amount_total)  # Handle Stripe
```

This pattern:
- Avoids conflicts with other payment terminal providers (Adyen, etc.)
- Uses Odoo's standard `super()` chain for non-Stripe terminals
- Limits scope of the override to exactly what is needed

### Workflow Trigger

| Trigger | Source | Action |
|---------|--------|--------|
| POS session loads self-order data | `pos_self_order` calls `_load_pos_self_data_domain` | Stripe terminal methods included in domain for kiosk mode |
| Customer initiates payment in kiosk | POS frontend calls `_payment_request_from_kiosk` | `stripe_payment_intent()` invoked for Stripe |

---

## L4 — Version Changes: Odoo 18 to Odoo 19

`pos_self_order_stripe` is a thin module. In both Odoo 18 and Odoo 19, the implementation is nearly identical.

### What Changed in the Odoo 18 to Odoo 19 Transition

**Odoo 18:** The module used `or` operator for domain composition in `_load_pos_self_data_domain`:

```python
# Odoo 18 (approximate)
domain = [('use_payment_terminal', '=', 'stripe'), ('id', 'in', config.payment_method_ids.ids)] + domain
```

**Odoo 19:** The module uses `Domain.OR()` for cleaner domain composition:

```python
# Odoo 19
domain = Domain.OR([
    [('use_payment_terminal', '=', 'stripe'), ('id', 'in', config.payment_method_ids.ids)],
    domain
])
```

`Domain` is a new Odoo 19 class (`from odoo.fields import Domain`) that provides a cleaner way to compose domain expressions. `Domain.OR([a, b])` is functionally equivalent to `['|'] + a + b` but more readable.

### Other Relevant Changes

| Area | Odoo 18 | Odoo 19 | Impact |
|------|---------|---------|--------|
| `pos_stripe.stripe_payment_intent()` | Present | Present | Unchanged |
| `pos_self_order._load_pos_self_data_domain` | Present | Present | Base method still there; module still hooks correctly |
| `Domain` utility class | Not available | New in 19 | Used for cleaner domain composition |

### Conclusion

`pos_self_order_stripe` requires **minimal migration effort** from Odoo 18 to 19. The main change is the `Domain.OR()` API usage (which is backward-compatible via manual list composition if needed). The functional behavior is identical.

---

## Data Files

- `views/assets_stripe.xml` — Asset references for Stripe JS in the self-order frontend

## Assets

- `pos_self_order.assets`: All Stripe self-order frontend assets (loaded into self-order POS)
- `pos_self_order.assets_tests`: Test tours for Stripe self-order kiosk flow

## Related

- [Modules/pos_stripe](modules/pos_stripe.md) — Stripe Terminal integration (defines `stripe_payment_intent()`)
- [Modules/pos_self_order](modules/pos_self_order.md) — Base self-order module
- [Modules/pos_online_payment_self_order](modules/pos_online_payment_self_order.md) — Online payment in self-order (mobile mode)
