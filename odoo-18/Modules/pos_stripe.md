---
Module: pos_stripe
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_stripe #payment #terminal #stripe
---

## Overview

Integrates Stripe Terminal (Stripe POS hardware) with POS. Supports payment intent creation with manual capture (for tip handling), connection token fetching, and payment capture. Also used as a dependency by `pos_self_order_stripe` for kiosk terminal payments.

**Depends:** `point_of_sale`

---

## Models

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

| Field | Type | Notes |
|---|---|---|
| `stripe_serial_number` | Char | Terminal serial number (e.g., 'WSC513105011295'), copy=False |

**Methods:**
- `_get_payment_terminal_selection()` -> adds `('stripe', 'Stripe')`
- `_load_pos_data_fields(config_id)` -> adds `'stripe_serial_number'`
- `_check_stripe_serial_number()` -> `@api.constrains`: prevents duplicate serial numbers across payment methods
- `_get_stripe_payment_provider()` -> searches `payment.provider` with code='stripe' and current company. Raises UserError if missing.
- `_get_stripe_secret_key()` -> **DEPRECATED** (TODO: remove in master) — returns stripe_secret_key from provider
- `stripe_connection_token()` -> checks `group_pos_user`, calls `provider._stripe_make_request('terminal/connection_tokens')`
- `_stripe_calculate_amount(amount)` -> `round(amount / currency.rounding)` — converts to smallest currency unit (cents)
- `stripe_payment_intent(amount)` -> checks `group_pos_user`, builds params with `capture_method='manual'`, `payment_method_types=['card_present']`. Handles AUD/AU and CAD/CA regional overrides. Returns API response (contains `id` for capture).
- `stripe_capture_payment(paymentIntentId, amount=None)` -> checks `group_pos_user`, calls POST `/payment_intents/{id}/capture` with optional `amount_to_capture` for tip support. Amount uses `_stripe_calculate_amount`.
- `action_stripe_key()` -> returns form action for Stripe payment provider record

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Manual capture required:** Stripe Terminal payments MUST use `capture_method: manual` — the payment is authorized but not captured. This enables tip-after-payment flows where the final amount (base + tip) is captured in a separate `_stripe_calculate_amount(amount)` call.

2. **Currency-specific overrides:**
   - **AUD + AU:** Uses `payment_method_options[card_present][capture_method]=manual_preferred` instead of `manual`
   - **CAD + CA:** Adds `payment_method_types[]=interac_present` for Canadian Interac cards

3. **Duplicate serial prevention:** `_check_stripe_serial_number` ensures each Stripe terminal serial number is unique across all payment methods — a terminal can only be associated with one payment method.

4 **`_stripe_calculate_amount`:** For a $50.00 order with 2 decimal places: `round(50.00 / 0.01) = 5000` cents. For JPY (0 decimal places): `round(50 / 1) = 50`.

5. **`group_pos_user` guard:** All Stripe terminal RPC methods (`stripe_connection_token`, `stripe_payment_intent`, `stripe_capture_payment`) require `group_pos_user` access — prevents non-POS users from creating/capturing payments.