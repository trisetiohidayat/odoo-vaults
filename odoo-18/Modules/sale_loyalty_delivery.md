# sale_loyalty_delivery — Sale Loyalty Delivery

**Tags:** #odoo #odoo18 #sale #loyalty #delivery #reward #free-shipping
**Odoo Version:** 18.0
**Module Category:** Sale + Loyalty / Delivery Rewards
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_loyalty_delivery` extends the loyalty program to support free shipping as a reward type. It adds a shipping-specific reward mode, modifies the program template and order total calculation to exclude delivery lines from threshold calculations, and creates free shipping reward lines when a loyalty reward is claimed.

**Technical Name:** `sale_loyalty_delivery`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_loyalty_delivery/`
**Depends:** `sale_loyalty`, `delivery`
**Inherits From:** `loyalty.reward`, `loyalty.program`, `sale.order`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/loyalty_reward.py` | `loyalty.reward` | Shipping reward type |
| `models/loyalty_program.py` | `loyalty.program` | Program template and values for shipping rewards |
| `models/sale_order.py` | `sale.order` | Threshold exclusion, free shipping reward computation |

---

## Models Reference

### `loyalty.reward` (models/loyalty_reward.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `reward_type` | Selection | Adds `'shipping'` option alongside `'product'` and `'discount'` |

#### Field Notes

The `ondelete` for `'shipping'` is `'set default'` — shipping rewards are converted to the default selection if the field type is removed.

---

### `loyalty.program` (models/loyalty_program.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_program_type_default_values()` | Adds shipping reward type to default values |
| `get_program_templates()` | Changes promotion description for shipping reward programs |
| `_get_template_values()` | Sets reward_type='shipping' for free shipping programs |

---

### `sale.order` (models/sale_order.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_amount_total_without_delivery()` | Sums amounts excluding `is_delivery=True` lines and ewallet/gift_card |
| `_get_no_effect_on_threshold_lines()` | Adds delivery lines to set of lines excluded from threshold |
| `_get_not_rewarded_order_lines()` | Adds delivery lines to non-rewarded lines |
| `_get_reward_values_free_shipping()` | Computes free shipping reward line values |
| `_get_reward_line_values()` | Calls `_get_reward_values_free_shipping()` for shipping rewards |
| `_get_claimable_rewards()` | Filters shipping rewards by checking if line already has a shipping reward |

#### Free Shipping Reward Logic

`_get_reward_values_free_shipping()` determines the free shipping reward:
1. Finds the matching delivery carrier from the SO's `carrier_id`
2. Uses the carrier's `base_on_rule` price as the reward value (full free shipping)
3. Creates a discount reward line with `is_delivery=True` and `is_reward_line=True`

#### Threshold Exclusion Logic

`_get_no_effect_on_threshold_lines()` adds `is_delivery=True` lines to the threshold-excluded set, so delivery charges don't prevent customers from reaching reward thresholds.

---

## Security File

No security file.

---

## Data Files

No data file.

---

## Critical Behaviors

1. **Free Shipping Reward**: When a shipping loyalty reward is claimed, `_get_reward_values_free_shipping()` creates a negative discount line covering the full shipping cost (the SOL `is_delivery=True` flag causes it to appear as a delivery discount).

2. **Threshold Exclusion**: Delivery lines (`is_delivery=True`) are excluded from both the threshold computation (`_get_no_effect_on_threshold_lines()`) and the "not rewarded" lines (`_get_not_rewarded_order_lines()`), so shipping cost doesn't block or inflate threshold calculations.

3. **Single Shipping Reward Per Order**: `_get_claimable_rewards()` filters out shipping rewards if the order already has a shipping reward line. This prevents duplicate free shipping awards.

4. **eWallet/Gift Card Exclusion**: `_compute_amount_total_without_delivery()` also excludes ewallet and gift card lines from the total, consistent with the pattern of excluding non-product-value items from threshold calculations.

---

## v17→v18 Changes

No significant changes from v17 to v18 identified. Module structure and logic remain consistent with the loyalty delivery rewards feature.

---

## Notes

- This module requires both `sale_loyalty` (loyalty program base) and `delivery` (delivery carrier base) dependencies
- The free shipping reward value is tied to the delivery carrier's rate, not a fixed amount
- `_get_claimable_rewards()` prevents stacking multiple shipping rewards on the same order
- The `is_delivery=True` flag on the reward SOL makes it appear in the delivery section of the SO, providing good UX
