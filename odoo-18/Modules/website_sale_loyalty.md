---
Module: website_sale_loyalty
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_sale_loyalty #ecommerce #loyalty
---

## Overview

**Module:** `website_sale_loyalty`
**Depends:** `loyalty`, `website_sale`
**Location:** `~/odoo/odoo18/odoo/addons/website_sale_loyalty/`
**Purpose:** Bridges loyalty/coupon system with eCommerce — enables eCommerce-specific loyalty programs (`ecommerce_ok`), coupon application from session, auto-apply rewards, abandoned cart coupon cleanup, and visual merging of multi-tax discount lines.

## Models

### `loyalty.program` (website_sale_loyalty/models/loyalty_program.py)

Inherits: `loyalty.program` + `website.multi.mixin`

| Field | Type | Description |
|---|---|---|
| `ecommerce_ok` | Boolean | "Available on Website"; default `True` — marks program as usable in eCommerce cart |

| Method | Decorator | Description |
|---|---|---|
| `action_program_share()` | action | Opens coupon share wizard for the program |

### `loyalty.rule` (website_sale_loyalty/models/loyalty_rule.py)

Inherits: `loyalty.rule`

| Field | Type | Description |
|---|---|---|
| `website_id` | Many2one (`website`) | Related to `program_id.website_id`; `store=True` |

| Method | Decorator | Description |
|---|---|---|
| `_constrains_code()` | `@api.constrains('code', 'website_id')` | Ensures promo codes are unique per accessible website. Allows duplicate codes across websites but not within the same website's scope. Also prevents coupon codes from colliding with loyalty card codes. |

### `loyalty.card` (website_sale_loyalty/models/loyalty_card.py)

Inherits: `loyalty.card`

| Method | Decorator | Description |
|---|---|---|
| `action_coupon_share()` | action | Opens coupon share wizard |

### `sale.order` (website_sale_loyalty/models/sale_order.py)

Inherits: `sale.order`

| Field | Type | Description |
|---|---|---|
| `disabled_auto_rewards` | Many2many (`loyalty.reward`) | Tracks rewards manually disabled so auto-apply won't re-apply them; managed via `sale_order_disabled_auto_rewards_rel` table |

| Method | Decorator | Description |
|---|---|---|
| `_get_program_domain()` | override | Replaces `sale_ok` filter with `ecommerce_ok` when order has website; adds website scope |
| `_get_trigger_domain()` | override | Same logic for trigger programs: `sale_ok` → `ecommerce_ok` + website scope |
| `_get_program_timezone()` | override | Returns website's salesperson timezone (or fallback to parent) |
| `_try_pending_coupon()` | private | Reads `pending_coupon_code` from session, applies it, pops from session; auto-applies single-reward programs |
| `_update_programs_and_rewards()` | override | Calls `_try_pending_coupon()` before parent to handle session-based coupons |
| `_auto_apply_rewards()` | private | Auto-claims rewards for: non-nominative programs, single-reward programs, non-multi-product rewards, not in `disabled_auto_rewards`, not already applied |
| `_compute_website_order_line()` | override | Merges multiple discount lines from the same program (same reward/coupon/identifier) into one line; hides original tax-split lines |
| `_compute_cart_info()` | override | Subtracts reward line quantities from `cart_quantity` to avoid inflating item count |
| `get_promo_code_error(delete=True)` | session | Reads/clears `error_promo_code` from session |
| `get_promo_code_success_message(delete=True)` | session | Reads/clears `successful_code` from session |
| `_set_delivery_method()` | override | Triggers `_update_programs_and_rewards` after delivery change |
| `_remove_delivery_line()` | override | Triggers `_update_programs_and_rewards` after removing delivery |
| `_cart_update()` | override | Handles forced deletion of reward lines; calls `_update_programs_and_rewards` and `_auto_apply_rewards` after cart change |
| `_get_non_delivery_lines()` | override | Excludes delivery reward lines (type='shipping') from non-delivery lines |
| `_get_free_shipping_lines()` | private | Returns order lines where `reward_type == 'shipping'` |
| `_allow_nominative_programs()` | override | Public users cannot use nominative programs |
| `_gc_abandoned_coupons()` | `@api.autovacuum` | Removes coupon links from abandoned draft eCommerce orders older than configurable validity (default 4 days); calls `_update_programs_and_rewards` to re-evaluate |
| `_get_claimable_and_showable_rewards()` | override | Extends claimable rewards with partner's loyalty cards from the same program domain (with_code triggers or auto future programs) |
| `_cart_find_product_line(product_id, line_id=None)` | override | Filters out reward lines from cart line lookup |

### `sale.order.line` (website_sale_loyalty/models/sale_order_line.py)

Inherits: `sale.order.line`

| Method | Decorator | Description |
|---|---|---|
| `_show_in_cart()` | override | Hides discount-type reward lines from website_order_line |
| `unlink()` | override | When `website_sale_loyalty_delete` context set: adds deleted reward to `disabled_auto_rewards` on parent order |

## Security / Data

`ir.model.access.csv` present (from loyalty module).

Data files:
- `product_demo.xml` — demo products for loyalty rewards

## Critical Notes

- v17→v18: `ecommerce_ok` field added to `loyalty.program` to distinguish website vs. sales-order programs.
- `website_id` on `loyalty.rule` enables per-website promo code uniqueness.
- Abandoned cart coupon cleanup (`_gc_abandoned_coupons`) runs as an auto-vacuum job.
- Multi-tax discount lines are merged client-side in the cart for display clarity.
- The `disabled_auto_rewards` mechanism prevents infinite loop when user manually removes an auto-claimable reward.