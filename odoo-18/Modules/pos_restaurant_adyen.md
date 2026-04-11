---
Module: pos_restaurant_adyen
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_restaurant_adyen #restaurant #payment #adyen
---

## Overview

Integrates Adyen payment terminal capture with restaurant tipping flow. Extends `pos_restaurant` tip handling to perform Adyen terminal reauthorization/capture when a tip is added after payment.

**Depends:** `pos_restaurant`, `pos_adyen`

---

## Models

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

| Field | Type | Notes |
|---|---|---|
| `adyen_merchant_account` | Char | POS merchant account code used in Adyen |

**Methods:**
- `_get_adyen_endpoints()` -> extends parent dict with:
  - `'adjust'`: `https://pal-%s.adyen.com/pal/servlet/Payment/v52/adjustAuthorisation`
  - `'capture'`: `https://pal-%s.adyen.com/pal/servlet/Payment/v52/capture`
- `_load_pos_data_fields(config_id)` -> adds `'adyen_merchant_account'` to parent fields

---

### `pos.payment` (Extension)
**Inheritance:** `pos.payment`

**Methods:**
- `_update_payment_line_for_tip(tip_amount)` -> calls parent, then if `use_payment_terminal == 'adyen'` calls `_adyen_capture()`
- `_adyen_capture()` -> sends capture request to Adyen with `originalReference=transaction_id`, `modificationAmount` (amount * 10^decimal_places), `currency`, `merchantAccount`

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Endpoint version:** Uses Adyen API v52 for capture/adjust endpoints (vs base `pos_adyen` which uses v52 for payment request). This module adds the specific capture/adjustment endpoints needed for tip handling.

2. **Tip capture flow:** When `pos.config` has `set_tip_after_payment=True`, after the customer adds a tip, this module triggers an Adyen capture for the tip amount (in addition to the base payment capture already done at order payment). The capture is done server-side via `_adyen_capture`.

3. **Currency precision:** Amount conversion uses `10**self.currency_id.decimal_places` — handles non-standard currencies.