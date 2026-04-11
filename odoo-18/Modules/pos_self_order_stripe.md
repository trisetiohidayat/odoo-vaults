---
Module: pos_self_order_stripe
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_self_order_stripe #self_order #payment #stripe
---

## Overview

Enables Stripe terminal payment intents in kiosk self-order mode. Overrides `_payment_request_from_kiosk` to create and return Stripe payment intents for the order total, and handles capture via a dedicated controller endpoint.

**Depends:** `pos_self_order`, `pos_stripe`

---

## Models

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

**Methods:**
- `_payment_request_from_kiosk(order)` -> if `use_payment_terminal != 'stripe'`, delegates to super. Otherwise calls `stripe_payment_intent(order.amount_total)` which:
  - Uses `capture_method: manual` (required for terminal)
  - Uses `payment_method_types: ['card_present']`
  - Converts amount via `_stripe_calculate_amount` (divides by currency rounding)
  - For AUD/AU: adds `payment_method_options[card_present][capture_method]=manual_preferred`
  - For CAD/CA: adds `payment_method_types[]=interac_present`
  - Returns the Stripe API response (contains `id` for later capture)

---

## Controllers

### `pos_self_order_stripe.controllers.orders.PosSelfOrderControllerStripe`
**Inheritance:** `pos_self_order.controllers.orders.PosSelfOrderController`

**Methods:**
- `get_stripe_creditentials(access_token, payment_method_id)` -> `/pos-self-order/stripe-connection-token/` (typo in route name): returns Stripe connection token from the payment method's `stripe_connection_token()` call
- `stripe_capture_payment(access_token, order_access_token, payment_intent_id, payment_method_id)` -> `/pos-self-order/stripe-capture-payment/`: validates capture amount matches order total, adds payment record, calls `action_pos_order_paid()`, broadcasts `PAYMENT_STATUS` notification (Success/fail) in kiosk mode

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Manual capture:** All Stripe terminal payments use `capture_method: manual` — payments are authorized but not captured until the order is completed. This supports tip addition after payment.

2. **Regional variants:** AUD (Australia) and CAD (Canada) have special capture method handling due to regional card network requirements.

3. **`_stripe_calculate_amount`:** Amount is divided by currency rounding (e.g., $10.00 with 2 decimal places becomes 1000 cents) — different from Razorpay/PayTM which keep the amount as decimal.

4. **Two-step flow:** `_payment_request_from_kiosk` creates the payment intent (authorization), and `stripe_capture_payment` captures it after card interaction. The amount is verified server-side before capture to prevent tampering.
