---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #pos
  - #restaurant
  - #payment
  - #adyen
---

# pos_restaurant_adyen — Adyen Tip Capture for Restaurant POS

> Adds American-style tip adjustment to the restaurant POS payment flow via the Adyen payment terminal. When `set_tip_after_payment = True` is enabled on the POS config, this module prevents immediate payment capture on Adyen so that a tip can be added after the customer leaves, then triggers a re-authorization (adjustment) for the tip amount. In Odoo 19, this uses a hybrid architecture: a client-side JavaScript override to force pre-authorization, and a server-side Python model to handle tip capture via Adyen's `adjustAuthorisation` endpoint.

**Module:** `pos_restaurant_adyen` | **Location:** `odoo/addons/pos_restaurant_adyen/` | **Version:** 1.0
**Depends:** `pos_adyen`, `pos_restaurant`, `payment_adyen` | **Category:** Point of Sale | **License:** LGPL-3
**Auto-install:** `True` (installs automatically when all three dependencies are present)

---

## Module Architecture

`pos_restaurant_adyen` is a **hybrid bridge module** — it has both client-side JavaScript (to force pre-authorization) and server-side Python ORM (to capture tips). This differs from `pos_restaurant_stripe` which is purely client-side.

```
pos_restaurant_adyen
    ├── models/
    │   ├── __init__.py
    │   ├── pos_order.py          (server: action_pos_order_paid override)
    │   ├── pos_payment.py        (server: _update_payment_line_for_tip, _adyen_capture)
    │   └── pos_payment_method.py  (server: adyen_merchant_account, endpoint override)
    ├── static/src/overrides/models/
    │   └── payment_adyen.js      (client: _adyenPayData, sendPaymentAdjust, canBeAdjusted)
    └── __manifest__.py
```

| Layer | File | Model Extended | Purpose |
|---|---|---|---|
| Client pre-auth | `static/src/overrides/models/payment_adyen.js` | `PaymentAdyen` (JS class) | Force pre-authorization; adjust on tip; card-type gate |
| Order trigger | `models/pos_order.py` | `pos.order` | Capture on order paid when not in tip-after-payment mode |
| Tip capture | `models/pos_payment.py` | `pos.payment` | Capture on tip confirmation; `_adyen_capture()` method |
| Config | `models/pos_payment_method.py` | `pos.payment.method` | Adds `adyen_merchant_account`; adds `adjust` endpoint |

---

## L1: How Adyen Tipping Works with Restaurant POS

### The Problem with Pre-Authorization

In a restaurant, the payment authorization must account for a tip that will be determined after the card is presented. If the terminal captures the payment immediately (standard e-commerce flow), the tip cannot be added. A pre-authorization followed by an adjustment (re-authorization) at the tip amount solves this.

### Odoo's Architecture for Post-Payment Tips

The restaurant POS has two tipping modes:

1. **Tip product** (`iface_tipproduct`): Customer sees tip buttons on the payment screen before payment. The tip is added as a regular order line. Payment is captured for the total (order + tip) in a single transaction. No special Adyen handling needed.

2. **Tip after payment** (`set_tip_after_payment`): Customer pays for the order without a tip. The payment is pre-authorized (not captured). After the customer leaves, the server/manager adjusts the payment to the new total including the tip, triggering a re-authorization for the difference. **This is where `pos_restaurant_adyen` is required.**

### Two Adyen Capture Paths

`pos_restaurant_adyen` implements **two separate capture triggers**, depending on the tipping mode:

**Path 1 — Immediate capture (no tip-after-payment):** When `set_tip_after_payment = False` (default), the payment is captured immediately after the card is presented. This is triggered from `action_pos_order_paid` on `pos.order`.

**Path 2 — Deferred capture (tip-after-payment):** When `set_tip_after_payment = True`, the payment is pre-authorized (not captured) during the initial payment. After the customer leaves, the waiter enters a tip and confirms. The frontend calls `sendPaymentAdjust()` on the `PaymentAdyen` JS class, which triggers `adjustAuthorisation` via `_callAdyen`.

### The Flow with `pos_restaurant_adyen`

```
Customer pays at Adyen terminal
    │
    ▼
pos_restaurant_adyen (client): _adyenPayData() adds "authorisationType=PreAuth"
    │
    ▼
Adyen terminal: Pre-authorizes base amount (no capture yet)
    │
    ▼
Order marked as paid: action_pos_order_paid()
    │
    ├── set_tip_after_payment = True?
    │       └── No: pos_restaurant_adyen server._adyen_capture() called immediately
    │
    ▼
TipScreen activates (manager/waiter enters tip)
    │
    ▼
pos.payment server: _update_payment_line_for_tip(tip_amount)
    │
    ├── super() writes amount += tip_amount
    │
    ▼
pos_restaurant_adyen (client): sendPaymentAdjust(uuid)
    │
    ├── canBeAdjusted(uuid) → card_type in ["mc","visa","amex","discover"]?
    │
    ▼
_callAdyen(data, "adjust")
    │
    ├── Builds { originalReference, modificationAmount, merchantAccount,
    │            additionalData: { industryUsage: "DelayedCharge" } }
    │
    ▼
POST https://pal-{merchant}.adyen.com/pal/servlet/Payment/v52/adjustAuthorisation
    │
    ▼
Adyen: Adjusts pre-authorization to base + tip amount
```

### Comparison: Client vs Server Capture

| Aspect | Client-side (`payment_adyen.js`) | Server-side (`pos_payment.py`) |
|---|---|---|
| Endpoint | `adjustAuthorisation` | `capture` |
| Method | `_callAdyen(data, "adjust")` | `proxy_adyen_request(data, "capture")` |
| Trigger | `TipScreen.validateTip()` → `sendPaymentAdjust()` | `action_pos_order_paid()` for non-tip-after-payment |
| Pre-auth required | Yes (via `_adyenPayData`) | No — immediate capture |
| Card-type gate | `canBeAdjusted()` restricts to MC/Visa/Amex/Discover | No gate — captures all Adyen lines |

### Comparison with `pos_restaurant_stripe`

| Aspect | `pos_restaurant_adyen` | `pos_restaurant_stripe` |
|---|---|---|
| Capture trigger | Server-side Python (`_adyen_capture`) + client-side JS (`sendPaymentAdjust`) | JavaScript client-only (`capturePaymentStripe`) |
| Capture endpoint | Adyen `adjustAuthorisation` (re-auth) | Stripe `capturePaymentStripe` (capture) |
| Pre-auth mechanism | Client JS appends `authorisationType=PreAuth` to Adyen data | Stripe SDK handles pre-auth natively |
| Merchant account | Read from `adyen_merchant_account` on `pos.payment.method` | Read from Stripe config |
| Card-type gate | `canBeAdjusted()` restricts to major cards only | `canBeAdjusted()` excludes interac/eftpos only |
| Server vs client capture | Two paths: immediate (server) and deferred (client) | Two paths: immediate (stripe base) and deferred (stripe bridge JS) |

---

## L2: Server-Side Components

### Manifest

```python
{
    'name': 'POS Restaurant Adyen',
    'version': '1.0',
    'category': 'Point of Sale',
    'sequence': 6,
    'summary': 'Adds American style tipping to Adyen',
    'depends': ['pos_adyen', 'pos_restaurant', 'payment_adyen'],
    'auto_install': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_restaurant_adyen/static/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

**Dependency chain:** `payment_adyen` → `pos_adyen` → `pos_restaurant` → `pos_restaurant_adyen`

**Auto-install behavior:** Automatically installed when all three dependencies are present.

**No XML view files:** Payment method configuration is inherited from `pos_adyen` and `payment_adyen`.

---

## L3: Client-Side Override

### File: `static/src/overrides/models/payment_adyen.js`

This is a JavaScript patch on `PaymentAdyen` (the base Adyen OWL component from `pos_adyen`).

```javascript
import { PaymentAdyen } from "@pos_adyen/app/utils/payment/payment_adyen";
import { patch } from "@web/core/utils/patch";

patch(PaymentAdyen.prototype, {
    _adyenPayData() {
        var data = super._adyenPayData(...arguments);

        if (data.SaleToPOIRequest.PaymentRequest.SaleData.SaleToAcquirerData) {
            data.SaleToPOIRequest.PaymentRequest.SaleData.SaleToAcquirerData +=
                "&authorisationType=PreAuth";
        } else {
            data.SaleToPOIRequest.PaymentRequest.SaleData.SaleToAcquirerData =
                "authorisationType=PreAuth";
        }

        return data;
    },

    sendPaymentAdjust(uuid) {
        var order = this.pos.getOrder();
        var line = order.getPaymentlineByUuid(uuid);
        var data = {
            originalReference: line.transaction_id,
            modificationAmount: {
                value: parseInt(line.amount * Math.pow(10, this.pos.currency.decimal_places)),
                currency: this.pos.currency.name,
            },
            merchantAccount: this.payment_method_id.adyen_merchant_account,
            additionalData: {
                industryUsage: "DelayedCharge",
            },
        };

        return this._callAdyen(data, "adjust");
    },

    canBeAdjusted(uuid) {
        var order = this.pos.getOrder();
        var line = order.getPaymentlineByUuid(uuid);
        return ["mc", "visa", "amex", "discover"].includes(line.card_type);
    },
});
```

#### Override 1: `_adyenPayData`

**Parent behavior (from `pos_adyen`):** The base Adyen component sends a payment request with the standard authorization type. Without this override, Adyen would capture the payment immediately on pre-authorization.

**Restaurant override:** Appends `&authorisationType=PreAuth` to the `SaleToAcquirerData` field in the Adyen payment request. This tells the Adyen terminal to pre-authorize the amount rather than capture it immediately. The pre-authorization remains open on the card, allowing a tip to be added later.

**Why modify `SaleToAcquirerData`:** This field is the raw data blob sent to the Adyen terminal alongside the payment request. Adding the `authorisationType=PreAuth` parameter is the Adyen-specific way to request pre-authorization mode. The same approach is used by the base `pos_adyen` for other pre-auth scenarios (e.g., hotel/invoice pre-auths).

**When `_adyenPayData` is called:** During the payment flow, when the POS sends the payment request to the Adyen terminal via the IoT proxy. This happens before `action_pos_order_paid` — the order is not yet marked paid.

#### Override 2: `sendPaymentAdjust`

**Parent behavior:** The base `PaymentAdyen` class does not implement `sendPaymentAdjust` — this is a new method added by `pos_restaurant_adyen`. This is the tip adjustment entry point.

**Restaurant override:** Retrieves the payment line by UUID, builds an Adyen `adjustAuthorisation` request, and calls `_callAdyen(data, "adjust")`.

**`originalReference`:** The Adyen `pspReference` from the original pre-authorization. Links the adjustment to the specific authorization.

**`modificationAmount`:** An Adyen `Amount` object. `value` is an integer in minor currency units (e.g., cents for USD). `parseInt(line.amount * Math.pow(10, decimal_places))` handles precision for all supported currencies.

**`merchantAccount`:** Read from `this.payment_method_id.adyen_merchant_account` — synced from the server model field.

**`additionalData.industryUsage: "DelayedCharge"`:** This Adyen metadata tells Adyen that this is a delayed charge (hotel/car rental style) rather than a incremental authorization (top-up). For restaurant tips, `DelayedCharge` is semantically appropriate — the customer is settling a bill that has now been finalized with a tip.

**`line.amount` at this point:** The tip has been added to `line.amount` by the server-side `_update_payment_line_for_tip` (which called `super().write({"amount": self.amount + tip_amount})`). The frontend reads `line.amount` which has already been updated server-side. So this captures the full tip-inclusive amount.

#### Override 3: `canBeAdjusted`

**Four conditions must all be `True` for a payment to be eligible for tip adjustment:**

| Condition | Source | Rationale |
|---|---|---|
| `set_tip_after_payment = True` | Implicit via `TipScreen` activation | Only shown when enabled |
| `payment_method_id.use_payment_terminal === "adyen"` | `PaymentAdyen` class itself | Only applies to Adyen terminals |
| `line.card_type` is in `["mc", "visa", "amex", "discover"]` | From Adyen terminal response | **Only major cards support incremental adjustment.** Debit cards (Interac), Australian Eftpos, and other regional cards do not support `adjustAuthorisation`. |

**L4 — Card-type detection:** The `card_type` field is set by the Adyen terminal when the card is read, returned in the payment response. The POS frontend reads this from the payment line data. If the card type is not in the whitelist, `canBeAdjusted()` returns `False`, and the `TipScreen` will not offer tip adjustment for that payment.

**Comparison with Stripe:** Stripe's bridge uses `card_type !== "interac" && !line.card_type.includes("eftpos")` as a negative exclusion (block interac/eftpos). Adyen's bridge uses a positive whitelist (allow only mc/visa/amex/discover). The difference reflects which card types each payment processor supports for incremental capture.

---

## L3: Server-Side Model Extensions

### `pos.order` (Extended)

**File:** `models/pos_order.py`

**Inherits:** `pos.order` | **Purpose:** Trigger immediate capture for non-tip-after-payment orders

#### `action_pos_order_paid`

```python
def action_pos_order_paid(self):
    res = super(PosOrder, self).action_pos_order_paid()
    if not self.config_id.set_tip_after_payment:
        payment_lines = self.payment_ids.filtered(
            lambda line: line.payment_method_id.use_payment_terminal == 'adyen'
        )
        for payment_line in payment_lines:
            payment_line._adyen_capture()
    return res
```

**Logic:**
- Calls parent first (standard `pos.order` paid logic)
- If `set_tip_after_payment = False` (default): captures immediately for all Adyen payment lines
- If `set_tip_after_payment = True`: **does not capture here** — capture is deferred to the client-side `sendPaymentAdjust()` after tip is entered

**Override pattern:** The parent `pos.order.action_pos_order_paid()` handles the state transition and related bookkeeping. The bridge adds Adyen capture as a post-processing step.

**L4 Note — Exception handling:** If `_adyen_capture()` throws after `super()` has already completed, the order is already marked paid. The payment line amount is recorded but Adyen has not captured. The exception propagates; the frontend handles this via its error handling in the TipScreen path.

---

### `pos.payment` (Extended)

**File:** `models/pos_payment.py`

**Inherits:** `pos.payment` | **Purpose:** Capture Adyen payment when tip is confirmed

#### `_update_payment_line_for_tip`

```python
def _update_payment_line_for_tip(self, tip_amount):
    res = super()._update_payment_line_for_tip(tip_amount)
    if self.payment_method_id.use_payment_terminal == 'adyen':
        self._adyen_capture()
    return res
```

**Override pattern:** Calls parent first (writes the new amount to `pos.payment.amount`), then checks if this is an Adyen terminal. If yes, triggers capture. The parent's write updates `amount = base_amount + tip_amount`, so `_adyen_capture` captures at the tip-inclusive total.

**Workflow trigger:** Called by the frontend `TipScreen.validateTip()` when the waiter confirms a tip.

**L4 Note — Dual capture path:** For Adyen, there are actually two capture mechanisms: client-side (`sendPaymentAdjust` via `_callAdyen`) and server-side (`_adyen_capture` via `proxy_adyen_request`). The client-side uses `adjustAuthorisation`; the server-side uses `capture`. The client-side path is triggered from the `TipScreen` (post-payment tip). The server-side path is triggered from `action_pos_order_paid` (immediate capture, no tip).

#### `_adyen_capture`

```python
def _adyen_capture(self):
    data = {
        'originalReference': self.transaction_id,
        'modificationAmount': {
            'value': int(self.amount * 10**self.currency_id.decimal_places),
            'currency': self.currency_id.name,
        },
        'merchantAccount': self.payment_method_id.adyen_merchant_account,
    }
    return self.payment_method_id.proxy_adyen_request(data, 'capture')
```

**Purpose:** Immediate capture of the authorized amount. Used when `set_tip_after_payment = False` — the payment is captured right after the order is marked paid.

**`proxy_adyen_request`:** Defined in `pos_adyen`'s `PosPaymentMethod` model. Sends the request to the Adyen PAL endpoint. The server-side uses `capture` while the client-side uses `adjust` — both are valid capture mechanisms, with `capture` being the simpler immediate capture.

**L4 Note — Two capture mechanisms:** The server-side `_adyen_capture` uses `capture` (immediate, simpler). The client-side `sendPaymentAdjust` uses `adjust` (re-authorization, allows incremental adjustment). For the deferred tip case, `adjust` is more semantically correct — the pre-auth was for the base amount, and `adjust` adds the tip as an additional authorization. For the immediate capture case, `capture` is simpler since no pre-auth was done.

---

### `pos.payment.method` (Extended)

**File:** `models/pos_payment_method.py`

**Inherits:** `pos.payment.method` | **Purpose:** Add Adyen merchant account field and adjust endpoint

#### `adyen_merchant_account`

```python
adyen_merchant_account = fields.Char(
    help='The POS merchant account code used in Adyen'
)
```

**Type:** Char. The value is the Adyen merchant account string, e.g., `"OdooIncEurope"`.

**No uniqueness constraint:** The same merchant account can be used across multiple payment methods (for different POS configs).

#### `_get_adyen_endpoints`

```python
def _get_adyen_endpoints(self):
    return {
        **super()._get_adyen_endpoints(),
        'adjust': 'https://pal-%s.adyen.com/pal/servlet/Payment/v52/adjustAuthorisation',
        'capture': 'https://pal-%s.adyen.com/pal/servlet/Payment/v52/capture',
    }
```

**Override pattern:** Extends the parent's endpoint dictionary with `adjust` and `capture` endpoints. API version `v52` is hardcoded.

**L4 — `adjust` vs `capture`:** The `adjust` endpoint is used by the client-side `sendPaymentAdjust` for deferred tip capture (incremental re-authorization). The `capture` endpoint is used by the server-side `_adyen_capture` for immediate capture. Both are Adyen Payment API v52 endpoints.

#### `_load_pos_data_fields`

```python
@api.model
def _load_pos_data_fields(self, config):
    params = super()._load_pos_data_fields(config)
    params += ['adyen_merchant_account']
    return params
```

Ensures `adyen_merchant_account` is synced to the POS frontend — `sendPaymentAdjust` reads `this.payment_method_id.adyen_merchant_account` in the client.

---

## L3: Failure Modes

| Failure Mode | Trigger | Behavior |
|---|---|---|
| Adyen adjust fails after tip entry | Network error, terminal offline, wrong merchant account | `sendPaymentAdjust()` throws; `TipScreen` shows error. Order has `is_tipped=True` but pre-auth not adjusted. Manual resolution required. |
| Card not in whitelist (e.g., Visa Electron, Interac) | Customer uses unsupported card | `canBeAdjusted()` returns `False`; tip adjustment not available for this payment. Use tip product approach instead. |
| `set_tip_after_payment` disabled after pre-auth | Admin toggles flag while order is pending tip | The `TipScreen` checks `set_tip_after_payment` on entry, not continuously. Pre-authorized amount remains open. |
| Zero tip entered | Waiter confirms 0 tip | `sendPaymentAdjust()` is called with `modificationAmount.value` = full order total. Adyen adjusts the pre-auth to the base amount (no change). |
| Pre-auth expiry | Adyen pre-auth expires (typically 7 days) | Adyen releases the hold without adjusting. Order remains marked as paid in Odoo with no funds captured. |
| Merchant account not configured | `adyen_merchant_account` is empty | `sendPaymentAdjust()` includes empty `merchantAccount`; Adyen returns `800`. Adjustment fails. |
| Server-side capture fails (immediate mode) | Network error | `action_pos_order_paid()` throws; order is NOT marked paid. Exception propagates to the session closing logic. |

---

## L4: Version Changes (Odoo 18 → 19)

`pos_restaurant_adyen` version 1.0 was introduced in Odoo 19 as a new bridge module. There is no Odoo 18 equivalent of this specific module.

### Odoo 18: Pre-existing Implementation

In Odoo 18, the restaurant Adyen tip adjustment logic was embedded directly in the `pos_adyen` module. The pre-authorization forcing, the adjustment call, and the card-type gating were all part of `pos_adyen`'s `PaymentAdyen` JavaScript class.

### Odoo 19: Module Extraction

In Odoo 19, this logic was **extracted** into `pos_restaurant_adyen` as a standalone auto-install module. This mirrors the same architectural change made for `pos_restaurant_stripe` — Odoo 19 systematically extracted restaurant-specific payment terminal logic into dedicated bridge modules.

The extraction separates concerns: `pos_adyen` no longer needs to know about restaurant-specific logic. The restaurant Adyen tipping can be updated independently of `pos_adyen`.

### Known Limitations

| Limitation | Description | Workaround |
|---|---|---|
| No offline support | Tip adjustment requires Adyen terminal connectivity | Cash tips can be added as tip products |
| Card whitelist strictness | Only MC/Visa/Amex/Discover supported; all other cards (including Visa Electron, Mastercard Debit, regional cards) excluded | Use tip product approach instead |
| Pre-auth expiry | Adyen pre-authorizations expire | Process tips before expiry; captured amounts are settled |
| `adjustAuthorisation` (re-auth) vs `capture` | Both mechanisms exist; the client uses `adjust`, server uses `capture` | Both work; `adjust` is more semantically correct for pre-auth scenarios |
| Hardcoded API version `v52` | No mechanism to upgrade API version from Odoo settings | Upgrade requires module code change |

---

## L4: Security Analysis

### Access Control

No new ACL entries are defined. The module extends existing models that already have ACLs from their parent modules (`pos_adyen`, `pos_restaurant`, `payment_adyen`). The `adyen_merchant_account` field has no `groups` restriction — payment terminal configuration is a manager-level operation.

### Data in Motion

The client-side `sendPaymentAdjust` sends `originalReference`, `modificationAmount`, `merchantAccount`, and `industryUsage` over HTTPS to Adyen. The server-side `_adyen_capture` uses the same data via `proxy_adyen_request`. No Odoo session data or customer PII is transmitted. The Adyen API key is stored in `payment.provider` settings (from `payment_adyen`).

### Card-type Information

The `line.card_type` is set by the Adyen terminal during the card read process. This is read-only on the Odoo side — Odoo does not influence which card type is detected. The whitelist in `canBeAdjusted()` is a business rule enforced client-side. A technically sophisticated actor could potentially bypass this check in the JS, but the consequence is only that an unsupported card receives a tip adjustment request (which Adyen would reject anyway).

### No Server-Side Validation of Card Type

There is no server-side check in `pos_restaurant_adyen` that validates `card_type` before the capture/adjust call. The gate is entirely in the client-side `canBeAdjusted()`. If the client-side check is bypassed (via JS manipulation), the Adyen API call would be sent, and Adyen would reject unsupported card types with an appropriate error.

---

## Cross-Module Integration

| Partner Module | Relationship | Integration Point |
|---|---|---|
| `pos_adyen` | Hard dependency | `PaymentAdyen` JS class (parent being patched); `_callAdyen()` method; `proxy_adyen_request()` server method |
| `pos_restaurant` | Hard dependency | `set_tip_after_payment` flag on `pos.config`; `TipScreen` component; `pos.payment._update_payment_line_for_tip` (trigger) |
| `payment_adyen` | Hard dependency | Adyen API authentication; capture endpoint routing |
| `point_of_sale` | Inherited via deps | `pos.order`, `pos.payment` base |
| `pos_restaurant_stripe` | No dependency | Coexists independently |
| `pos_restaurant_loyalty` | No dependency | Coexists independently |

---

## Related Documentation

- [Modules/pos_restaurant](modules/pos_restaurant.md) — Restaurant POS base module
- [Modules/pos_adyen](modules/pos_adyen.md) — Adyen terminal POS integration
- [Modules/payment_adyen](modules/payment_adyen.md) — Adyen payment provider
- [Modules/pos_restaurant_stripe](modules/pos_restaurant_stripe.md) — Stripe tipping bridge (for comparison)
