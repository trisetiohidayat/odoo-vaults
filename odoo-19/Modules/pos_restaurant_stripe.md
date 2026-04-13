---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #pos
  - #restaurant
  - #stripe
  - #payment
---

# pos_restaurant_stripe — Stripe Tipping for Restaurant POS

> Adds American-style tip adjustment to the restaurant POS payment flow via the Stripe payment terminal. When `set_tip_after_payment = True` is enabled on the POS config, this module prevents immediate payment capture on Stripe so that a tip can be added after the customer leaves or at the end of the day, then triggers a re-authorization/capture for the tip amount.

**Module:** `pos_restaurant_stripe` | **Location:** `odoo/addons/pos_restaurant_stripe/` | **Version:** 1.0
**Depends:** `pos_stripe`, `pos_restaurant`, `payment_stripe` | **Category:** Point of Sale | **License:** LGPL-3
**Auto-install:** `True` (installs automatically when all three dependencies are present)

---

## Module Architecture

`pos_restaurant_stripe` is an **ultra-thin bridge module**. It contains zero Python models, zero XML data files, and zero server-side business logic. Its entire purpose is to patch the `PaymentStripe` JavaScript class to defer Stripe payment capture when the restaurant tip-after-payment flow is active.

```
pos_restaurant_stripe
    └── static/src/overrides/models/payment_stripe.js    (client-side only)
```

| Layer | File | Role |
|---|---|---|
| Manifest | `__manifest__.py` | Declares dependencies and loads JS assets |
| Client-side | `static/src/overrides/models/payment_stripe.js` | Patches PaymentStripe capture logic |

---

## L1: How Stripe Tipping Works with Restaurant POS

### The Problem with Pre-Authorization

In a restaurant, the payment authorization must account for a tip that will be determined after the card is presented. If the terminal captures the payment immediately (standard e-commerce flow), the tip cannot be added. A pre-authorization followed by a capture at the tip amount solves this.

### Odoo's Architecture for Post-Payment Tips

The restaurant POS has two tipping modes:

1. **Tip product** (`iface_tipproduct`): Customer sees tip buttons on the payment screen before payment. The tip is added as a regular order line. Payment is captured for the total (order + tip) in a single transaction. No special Stripe handling needed.

2. **Tip after payment** (`set_tip_after_payment`): Customer pays for the order without a tip. The payment is pre-authorized (not captured). After the customer leaves, the server/manager adjusts the payment to the new total including the tip, triggering a re-authorization and capture for the difference. **This is where `pos_restaurant_stripe` is required.**

### The Flow with `pos_restaurant_stripe`

```
Customer pays at terminal
    │
    ▼
Stripe pre-authorizes base amount (no capture)
    │
    ▼
pos_restaurant: TipScreen activates after payment
    │
    ├── Manager/waiter enters tip amount
    │
    ▼
pos_restaurant_stripe: PaymentStripe.captureAfterPayment()
    │
    ├── Checks canBeAdjusted(uuid)
    │       └── set_tip_after_payment = True
    │       └── payment_method is Stripe
    │       └── card_type is NOT interac
    │       └── card_type does NOT include "eftpos"
    │
    ▼
sendPaymentAdjust(uuid)
    │
    ▼
Stripe: Capture additional (tip_amount)
```

### Integration with `pos_restaurant`

The module works in conjunction with `pos_restaurant`'s `set_tip_after_payment` flag on `pos.config`. When a restaurant POS session is active and the flag is `True`:

- The payment screen shows "Keep Open" instead of "Close Tab"
- After payment, `TipScreen` activates in the frontend
- When the tip is confirmed, the `PaymentStripe` JavaScript patch intercepts the normal capture flow

### Integration with `payment_stripe`

The module patches the parent `PaymentStripe` class from `pos_stripe`. It does not extend the server-side `payment.transaction` model — all capture logic remains in the Stripe terminal SDK on the client.

---

## L2: Server-Side Components

### Manifest

```python
{
    'name': 'POS Restaurant Stripe',
    'version': '1.0',
    'category': 'Point of Sale',
    'sequence': 6,
    'summary': 'Adds American style tipping to Stripe',
    'depends': ['pos_stripe', 'pos_restaurant', 'payment_stripe'],
    'auto_install': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_restaurant_stripe/static/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

**Dependency chain:** `payment_stripe` (Stripe payment provider) → `pos_stripe` (Stripe POS integration) → `pos_restaurant` (Restaurant POS) → `pos_restaurant_stripe` (Bridge)

**Auto-install behavior:** Because `auto_install = True`, this module is automatically installed when all three dependencies are present in the system. An admin does not need to manually select it.

**No Python models:** There are no `models/` directory, no `__init__.py` in the models directory, and no ORM-level fields or constraints defined in this module. The entire logic lives in the frontend.

---

## L3: Client-Side Override Pattern

### File: `static/src/overrides/models/payment_stripe.js`

```javascript
import { PaymentStripe } from "@pos_stripe/app/payment_stripe";
import { patch } from "@web/core/utils/patch";

patch(PaymentStripe.prototype, {
    async captureAfterPayment(processPayment, line) {
        // Don't capture if the customer can tip, in that case we
        // will capture later.
        if (!this.canBeAdjusted(line.uuid)) {
            return super.captureAfterPayment(...arguments);
        }
    },

    async sendPaymentAdjust(uuid) {
        var order = this.pos.getOrder();
        var line = order.getPaymentlineByUuid(uuid);
        this.capturePaymentStripe(line.transaction_id, line.amount, {
            stripe_currency_rounding: line.currency_id.rounding,
        });
    },

    canBeAdjusted(uuid) {
        var order = this.pos.getOrder();
        var line = order.getPaymentlineByUuid(uuid);
        return (
            this.pos.config.set_tip_after_payment &&
            line.payment_method_id.use_payment_terminal === "stripe" &&
            line.card_type !== "interac" &&
            (!line.card_type || !line.card_type.includes("eftpos"))
        );
    },
});
```

### Override 1: `captureAfterPayment`

**Parent behavior (from `pos_stripe`):** Immediately captures the authorized amount via `payment_stripe`'s capture API after the customer completes payment.

**Restaurant override:** When `canBeAdjusted()` returns `True`, the method exits early — `super.captureAfterPayment()` is **not called** — preventing capture. The pre-authorization remains open on the Stripe terminal until `sendPaymentAdjust()` is called.

**When `canBeAdjusted()` is False:** Delegates to the parent. Normal capture proceeds. This ensures non-restaurant POS terminals, cash payments, or unsupported card types behave as standard.

### Override 2: `sendPaymentAdjust`

**Parent behavior (from `pos_stripe`):** The base class does not implement `sendPaymentAdjust` — this is the bridge module's primary contribution.

**Restaurant override:** Retrieves the payment line by UUID, then calls `capturePaymentStripe(transaction_id, newAmount, options)`. The `newAmount` is the tip-adjusted total (base + tip), which triggers Stripe to capture the full amount including the tip. The `stripe_currency_rounding` option ensures the capture amount matches the currency's decimal precision.

### Override 3: `canBeAdjusted`

Four conditions must all be `True` for a Stripe payment line to be eligible for tip adjustment:

| Condition | Source | Rationale |
|---|---|---|
| `set_tip_after_payment` | `pos.config` | Restaurant must have tip-after-payment enabled |
| `payment_method_id.use_payment_terminal === "stripe"` | Payment line | Only Stripe terminals support re-auth |
| `card_type !== "interac"` | Payment line | Interac (Canadian debit) does not support incremental capture |
| Card type does not include `"eftpos"` | Payment line | Eftpos (Australian debit) does not support incremental capture |

This four-condition gate is the **fail-safe** that prevents inappropriate capture attempts. If any condition is false, the normal capture flow proceeds.

### Failure Modes

| Failure Mode | Trigger | Behavior |
|---|---|---|
| Stripe capture fails after tip entry | Network error or terminal error | The `capturePaymentStripe()` call throws. The frontend shows an error. The order is left in a state where the base amount was pre-authorized but not captured, and the tip was not applied. Manual resolution required. |
| `set_tip_after_payment` disabled after payment | Admin toggles the flag mid-session | The tip screen does not activate (flag checked on screen entry). The pre-authorized amount remains uncaptured. `sendPaymentAdjust()` is never called. |
| Card type changes after authorization | Unsupported scenario | Once pre-authorized, the card type is fixed. `canBeAdjusted()` gates remain valid for the session. |
| Zero tip entered | Waiter enters 0 tip | `capturePaymentStripe()` is called with the base amount (no change). Stripe captures the pre-authorized amount. This is equivalent to normal capture. |

---

## L4: Version Changes (Odoo 18 → 19)

`pos_restaurant_stripe` version 1.0 was introduced in Odoo 19 as a new thin bridge module. There is no Odoo 18 equivalent of this specific module. However, the restaurant tip-after-payment functionality existed in Odoo 18 as part of the broader `pos_restaurant` + `pos_stripe` integration.

### Odoo 18: Pre-existing Implementation

In Odoo 18, the restaurant Stripe tip adjustment logic was embedded directly in the `pos_stripe` module's `PaymentStripe` JavaScript class. The `canBeAdjusted()` logic was part of `pos_stripe`, not a separate bridge.

### Odoo 19: Module Extraction

In Odoo 19, this logic was **extracted** into `pos_restaurant_stripe` as a standalone auto-install module. This architectural change:

1. **Separates concerns**: `pos_stripe` no longer needs to know about restaurant-specific logic
2. **Enables independent release cycles**: Restaurant Stripe tipping can be updated without modifying `pos_stripe`
3. **Reduces `pos_stripe` complexity**: The base Stripe module is cleaner
4. **Auto-install contract**: When `pos_restaurant` + `pos_stripe` + `payment_stripe` are all installed, the bridge activates automatically

### API Stability

Since this module is new in Odoo 19, there is no migration path from an older version. Any Odoo 18 system upgrading to Odoo 19 will have this module installed automatically when dependencies are met.

### Known Limitations

| Limitation | Description | Workaround |
|---|---|---|
| No offline support | Tip adjustment requires Stripe terminal connectivity | Cash tips can be added as tip products |
| Interac/Eftpos exclusion | Canadian and Australian debit cards cannot be tip-adjusted | Use tip product approach instead |
| Single tip per payment | Only one Stripe payment line per order can be adjusted | Multiple payment methods (split payment) bypass adjustment |
| Pre-auth expiry | Stripe pre-authorizations expire (typically 7 days) | Process tips before expiry; captured amounts are settled |

---

## Cross-Module Integration

| Partner Module | Relationship | Integration Point |
|---|---|---|
| `payment_stripe` | Hard dependency | `payment.transaction` server model; Stripe API |
| `pos_stripe` | Hard dependency | `PaymentStripe` JS class (parent being patched) |
| `pos_restaurant` | Hard dependency | `set_tip_after_payment` flag on `pos.config`; `TipScreen` component |
| `pos_restaurant_loyalty` | No dependency | Coexists independently |

The module has **no security concerns**: it runs exclusively on the client, has no server-side code, and only patches the Stripe capture method when all conditions are met.

---

## Related Documentation

- [Modules/pos_restaurant](odoo-18/Modules/pos_restaurant.md) — Restaurant POS base module
- [Modules/pos_stripe](odoo-18/Modules/pos_stripe.md) — Stripe POS integration
- [Modules/payment_stripe](odoo-17/Modules/payment_stripe.md) — Stripe payment provider

---

## L4: Client-Side Source File (Verified from Source)

The JavaScript override file is at `pos_restaurant_stripe/static/src/overrides/models/payment_stripe.js`:

```javascript
import { PaymentStripe } from "@pos_stripe/app/payment_stripe";
import { patch } from "@web/core/utils/patch";

patch(PaymentStripe.prototype, {
    async captureAfterPayment(processPayment, line) {
        // Don't capture if the customer can tip, in that case we
        // will capture later.
        if (!this.canBeAdjusted(line.uuid)) {
            return super.captureAfterPayment(...arguments);
        }
    },

    async sendPaymentAdjust(uuid) {
        var order = this.pos.getOrder();
        var line = order.getPaymentlineByUuid(uuid);
        this.capturePaymentStripe(line.transaction_id, line.amount, {
            stripe_currency_rounding: line.currency_id.rounding,
        });
    },

    canBeAdjusted(uuid) {
        var order = this.pos.getOrder();
        var line = order.getPaymentlineByUuid(uuid);
        return (
            this.pos.config.set_tip_after_payment &&
            line.payment_method_id.use_payment_terminal === "stripe" &&
            line.card_type !== "interac" &&
            (!line.card_type || !line.card_type.includes("eftpos"))
        );
    },
});
```

**Verified from source (Odoo 19.0):**
- `captureAfterPayment` is `async` (not shown in existing doc's simplified pseudo-code)
- `sendPaymentAdjust` is `async` and calls `capturePaymentStripe(transaction_id, amount, options)` — the `stripe_currency_rounding` option is passed to ensure the capture amount respects the currency's decimal precision
- `canBeAdjusted` uses a negative exclusion (block interac/eftpos) rather than a positive whitelist — Stripe supports interac but not incremental capture, while Adyen only supports certain card types

### Stripe vs Adyen Card-Type Gates

| Module | Logic | Blocked | Allowed |
|---|---|---|---|
| `pos_restaurant_stripe` | Negative exclusion (`!== "interac" && !includes("eftpos")`) | Interac, Eftpos | All other card types |
| `pos_restaurant_adyen` | Positive whitelist (`["mc","visa","amex","discover"]`) | All cards not in list | MC, Visa, Amex, Discover |

This difference reflects each payment processor's incremental capture capabilities. Stripe blocks only Canadian (Interac) and Australian (Eftpos) debit cards. Adyen blocks everything except the four major international card networks.
