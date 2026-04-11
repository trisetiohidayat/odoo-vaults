---
Module: pos_restaurant_stripe
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_restaurant_stripe #restaurant #payment #stripe
---

## Overview

Integrates Stripe terminal capture with restaurant tipping flow. Extends `pos_restaurant` tip handling to capture the full authorized amount (base + tip) on Stripe when a tip is added after payment.

**Depends:** `pos_restaurant`, `pos_stripe`

---

## Models

### `pos.order` (Extension)
**Inheritance:** `pos.order`

**Methods:**
- `action_pos_order_paid()` -> calls parent, then if `config.set_tip_after_payment=False` (i.e., tip collected at payment time, not after), iterates all payment lines with `use_payment_terminal == 'stripe'` and calls `_stripe_capture_payment()` on each for the full tip-inclusive total.

---

### `pos.payment` (Extension)
**Inheritance:** `pos.payment`

**Methods:**
- `_update_payment_line_for_tip(tip_amount)` -> calls parent (updates `amount += tip_amount`), then if `payment_method_id.use_payment_terminal == 'stripe'` calls `stripe_capture_payment(transaction_id, amount_to_capture=self.amount)` to capture the new total (base + tip).

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Stripe tip capture:** Unlike Adyen (which captures only the tip delta via `modificationAmount`), Stripe's capture is done for the full new amount. The `stripe_capture_payment` method captures by `paymentIntentId` with an explicit `amount_to_capture` parameter set to the new (higher) total.

2. **Two tip flows:** When `set_tip_after_payment=True` (tip added after customer leaves): the `pos.payment._update_payment_line_for_tip` triggers the Stripe capture for the full new amount. When `set_tip_after_payment=False` (tip added at payment time): `pos.order.action_pos_order_paid` iterates Stripe payments and captures the tip-inclusive total.

3. **Interaction with pos_restaurant_adyen:** `pos_restaurant_stripe` handles the Stripe-specific tip capture. `pos_restaurant_adyen` handles the Adyen-specific tip capture. `pos_restaurant` provides the base `_update_payment_line_for_tip` that both extend.
