---
tags: [odoo, odoo17, module, sale_loyalty, coupon, loyalty]
research_depth: medium
source: addons/sale_loyalty/models/ + addons/loyalty/models/
---

# Sale Loyalty Module — Deep Reference

**Source:** `addons/sale_loyalty/models/` + `addons/loyalty/models/`

## Overview

Loyalty programs, coupons, discount codes, and rewards for sales orders. Extends `sale.order` and `sale.order.line` to apply and track promotions. The base `loyalty` module (`addons/loyalty`) defines the core models (`loyalty.program`, `loyalty.card`, `loyalty.rule`, `loyalty.reward`) which `sale_loyalty` integrates with `sale.order`.

---

## Architecture

Two layers:

1. **`loyalty` module** (base) — Defines program structure independently of any application. Used by both e-commerce and sales.
2. **`sale_loyalty` module** (add-on) — Integrates loyalty into `sale.order`:
   - Adds `applied_coupon_ids`, `code_enabled_rule_ids`, `coupon_point_ids` to `sale.order`
   - Adds `reward_id`, `coupon_id`, `points_cost`, `is_reward_line` to `sale.order.line`
   - Handles reward application, point calculation, and order confirmation hooks
   - `sale.order.line` extension for reward lines, point management, and lifecycle hooks

---

## Key Models

### loyalty.program (`loyalty/models/loyalty_program.py`)

Core program definition. `sale_loyalty` extends this with `sale_ok` and `order_count`.

**Program Types (`program_type` Selection):**

| Type | Code | Description |
|------|------|-------------|
| Coupon | `coupons` | Single/multi-use codes |
| Gift Card | `gift_card` | Prepaid cards, balance-based |
| Loyalty Card | `loyalty` | Points accumulation |
| Promotion | `promotion` | Auto-applied discounts |
| eWallet | `ewallet` | Stored monetary balance |
| Promo Code | `promo_code` | One-time discount code |
| Buy X Get Y | `buy_x_get_y` | Quantity-based free products |
| Next Order Coupon | `next_order_coupons` | Generates coupon for next order |

**`applies_on` — When points/rewards are usable:**

| Value | Meaning |
|-------|---------|
| `current` | Points/rewards usable on the same order that earned them |
| `future` | Points earned now, usable on a later order (generates a coupon) |
| `both` | Points accumulate and are also usable on current order |

**`trigger` — How a program activates:**

| Value | Meaning |
|-------|---------|
| `auto` | Automatically applied when conditions are met |
| `with_code` | Requires entering a code |

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Program name (required, translate) |
| `program_type` | Selection | Program category (required, default `promotion`) |
| `applies_on` | Selection | `current / future / both` (default `current`) |
| `trigger` | Selection | `auto / with_code` |
| `active` | Boolean | Program active state |
| `company_id` | Many2one | Company scope |
| `currency_id` | Many2one | Point currency (default: company currency) |
| `pricelist_ids` | Many2many | Pricelists where program applies |
| `rule_ids` | One2many | `loyalty.rule` children |
| `reward_ids` | One2many | `loyalty.reward` children |
| `communication_plan_ids` | One2many | Email notification triggers |
| `coupon_ids` | One2many | All generated `loyalty.card` records |
| `coupon_count` | Integer | Number of coupons (computed) |
| `total_order_count` | Integer | Orders using this program's rewards |
| `portal_visible` | Boolean | Show points in portal/POS ticket |
| `portal_point_name` | Char | Display name for points (e.g., "Stars") |
| `date_from` / `date_to` | Date | Validity period |
| `limit_usage` | Boolean | Cap total uses |
| `max_usage` | Integer | Max total redemptions |
| `is_nominative` | Boolean | Per-customer card tracking (computed) |
| `is_payment_program` | Boolean | Gift card / eWallet (computed) |
| `payment_program_discount_product_id` | Many2one | Product used for payment program discounts |

**Key Methods:**

- `_program_type_default_values()` — Returns defaults for each `program_type`. For example, `promotion` sets `trigger=auto`, `applies_on=current`, one rule (min amount 50), one reward (10% discount). `gift_card` sets `applies_on=future`, `portal_visible=True`, per-money rule.
- `_compute_from_program_type()` — When `program_type` changes, resets `rule_ids`, `reward_ids`, `trigger`, `applies_on` to the defaults from `_program_type_default_values()`. Uses `defaultdict` to batch writes per program_type.
- `_compute_is_nominative()` — True when `applies_on == 'both'` or (`ewallet` + `applies_on == 'future'`).
- `_compute_is_payment_program()` — True for `gift_card` and `ewallet`.
- `_get_valid_products(products)` — Returns dict mapping rules to matching products based on rule domain.
- `action_open_loyalty_cards()` — Opens the `loyalty.card` list view filtered to this program.

**Constraints:**
- `_constrains_reward_ids()` — Requires at least one reward.
- `limit_usage` requires `max_usage > 0`.

---

### loyalty.card (`loyalty/models/loyalty_card.py`)

A single coupon or loyalty card. Represents a customer's loyalty account in a program. `sale_loyalty` extends with `order_id` (the source sale order) and email-related overrides.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `program_id` | Many2one | Parent program |
| `program_type` | Selection | Related to program |
| `company_id` | Many2one | Related to program (stored) |
| `currency_id` | Many2one | Related to program |
| `partner_id` | Many2one | Card owner (optional, for nominative programs) |
| `points` | Float | Current point balance (tracking=True, triggers emails on change) |
| `point_name` | Char | Related to `program.portal_point_name` |
| `points_display` | Char | Formatted display string (computed) |
| `code` | Char | Unique barcode-scannable code (default: generated via `_generate_code()` using UUID) |
| `expiration_date` | Date | Expiry date (not allowed on loyalty cards) |
| `use_count` | Integer | Times used (computed from `sale.order.line`) |
| `order_id` | Many2one | Source sale order (added by `sale_loyalty`) |

**Key Methods:**

- `_generate_code()` — Returns `'044' + uuid4[7:-18]` (barcode-compatible).
- `_format_points(points)` — Formats with currency symbol if eWallet/gift card, else integer or float with point name.
- `_compute_use_count()` — Counts from `sale.order.line.coupon_id`. `sale_loyalty` extends this with `sale.order.line` read_group.
- `_restrict_expiration_on_loyalty()` — Onchange raises error if loyalty card has expiration date.
- `_send_creation_communication()` — Sends email via communication plan trigger `create` (skipped if `loyalty_no_mail` context).
- `_send_points_reach_communication(points_changes)` — Sends email when card crosses milestone thresholds (only sends highest milestone crossed).
- `_get_default_template()` — Returns first communication plan with `trigger == 'create'`. `sale_loyalty` falls back to `loyalty.mail_template_loyalty_card` if none defined.
- `_get_mail_partner()` — Returns `partner_id` or `order_id.partner_id` (sale_loyalty override).
- `_get_mail_author()` — Returns `order_id.user_id.partner_id` or `order_id.company_id.partner_id` (sale_loyalty override).
- `_get_signature()` — Returns `order_id.user_id.signature` or super (sale_loyalty override).
- `_has_source_order()` — Returns True if `order_id` exists (sale_loyalty override).

**Constraint:** `code` must be unique. Also validated against loyalty.rule codes — cannot have a card code that matches a rule code.

---

### loyalty.rule (`loyalty/models/loyalty_rule.py`)

Defines conditions for earning points in a program.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `program_id` | Many2one | Parent program (cascade delete) |
| `company_id` | Many2one | Related to program (stored) |
| `currency_id` | Many2one | Related to program |
| `active` | Boolean | Rule active state |
| `mode` | Selection | `auto / with_code` |
| `code` | Char | Promo code (mutually exclusive with card codes) |
| `reward_point_amount` | Float | Points earned (must be > 0) |
| `reward_point_mode` | Selection | `order / money / unit` — how points are calculated |
| `reward_point_split` | Boolean | Generate one coupon per unit (only for `future` programs with money/unit mode) |
| `minimum_qty` | Integer | Minimum product quantity |
| `minimum_amount` | Monetary | Minimum order amount |
| `minimum_amount_tax_mode` | Selection | `incl / excl` (tax inclusive or exclusive) |
| `product_ids` | Many2many | Applicable products |
| `product_category_id` | Many2one | Applicable category |
| `product_tag_id` | Many2one | Applicable product tag |
| `product_domain` | Char | Custom domain (stored as stringified domain list) |

**`reward_point_mode` Options:**

| Value | Meaning |
|-------|---------|
| `order` | Fixed points per qualifying order |
| `money` | Points per currency unit spent |
| `unit` | Points per unit purchased |

**Key Methods:**

- `_get_valid_product_domain()` — Builds domain from `product_ids`, `product_category_id` (including child categories via `_find_all_category_children`), `product_tag_id`, and `product_domain` (parsed with `ast.literal_eval`). Combined with OR logic.
- `_get_valid_products()` — Searches products matching the domain.
- `_compute_amount(currency_to)` — Converts `minimum_amount` to target currency using `_convert`.

**Constraints:**
- `reward_point_amount > 0`
- `reward_point_split` not allowed for `applies_on == 'both'` or `ewallet` programs
- Code uniqueness: no two rules in the same program can share a code; card codes cannot match rule codes

---

### loyalty.reward (`loyalty/models/loyalty_reward.py`)

Defines what customers can claim. `sale_loyalty` overrides `_get_discount_product_values()` to disable taxes on discount products and set invoice policy to `order`.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `program_id` | Many2one | Parent program (cascade delete) |
| `company_id` | Many2one | Related to program (stored) |
| `currency_id` | Many2one | Related to program |
| `active` | Boolean | Reward active state |
| `description` | Char | Display description (auto-generated, translatable) |
| `reward_type` | Selection | `product / discount` (default `discount`) |
| `required_points` | Float | Points needed to claim (must be > 0) |
| `clear_wallet` | Boolean | Claim entire point balance at once |
| `point_name` | Char | Related to program portal name |

**Discount fields:**

| Field | Type | Description |
|-------|------|-------------|
| `discount` | Float | Discount value (must be > 0) |
| `discount_mode` | Selection | `percent / per_point / per_order` |
| `discount_applicability` | Selection | `order / cheapest / specific` |
| `discount_max_amount` | Monetary | Cap on total discount |
| `discount_product_ids` | Many2many | Applicable products for specific discount |
| `discount_product_category_id` | Many2one | Applicable category |
| `discount_product_tag_id` | Many2one | Applicable tag |
| `discount_product_domain` | Char | Custom domain string |
| `all_discount_product_ids` | Many2many | Computed resolved product set |
| `discount_line_product_id` | Many2one | Product used on `sale.order.line` to represent discount |
| `is_global_discount` | Boolean | True if `discount + order + percent` (computed) |

**Product reward fields:**

| Field | Type | Description |
|-------|------|-------------|
| `reward_product_id` | Many2one | Free product |
| `reward_product_tag_id` | Many2one | Tag for multi-product reward |
| `multi_product` | Boolean | Multiple products selectable (computed) |
| `reward_product_ids` | Many2many | Computed products from tag + direct |
| `reward_product_qty` | Integer | Quantity to give (default 1) |
| `reward_product_uom_id` | Many2one | Unit of measure |

**`discount_mode` Options:**

| Value | Meaning |
|-------|---------|
| `percent` | % off the applicable amount |
| `per_point` | Fixed amount per point redeemed |
| `per_order` | Fixed amount per order |

**Key Methods:**

- `_get_discount_product_domain()` — Same logic as `loyalty.rule._get_valid_product_domain()`. Used for `specific` applicability.
- `_compute_description()` — Auto-generates description: e.g., `"10% on your order"`, `"$5 per point on cheapest product"`, `"Free Product - Acme Widget"`. Reads `discount_mode`, `discount_applicability`, currency symbol.
- `_create_missing_discount_line_products()` — On create/write, ensures every reward has its own discount product. Creates service-type products with `sale_ok=False`, `purchase_ok=False`, `lst_price=0`. Sets `discount_line_product_id`.
- `_get_discount_product_values()` — Returns `[{'name': ..., 'type': 'service', ...}]` for product creation. `sale_loyalty` override sets `taxes_id=False`, `supplier_taxes_id=False`, `invoice_policy='order'`.
- `unlink()` — If the reward has been applied to any `sale.order.line`, archives it instead of deleting (via `action_archive()`).

**Computed fields:**
- `_compute_all_discount_product_ids()` — Respects `loyalty.compute_all_discount_product_ids` config param; if `enabled`, searches and stores; otherwise leaves empty.
- `_compute_multi_product()` — True when reward_type is `product` and `reward_product_id + tag.products` has more than one product.

---

### sale.order (`sale_loyalty/models/sale_order.py`)

Extends `sale.order` with loyalty tracking and reward computation.

**New Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `applied_coupon_ids` | Many2many | Manually entered coupon codes |
| `code_enabled_rule_ids` | Many2many | Rules triggered by entered codes |
| `coupon_point_ids` | One2many | `sale.order.coupon.points` — tracks coupon/points impact on this order |
| `reward_amount` | Float | Total discount value from rewards (computed) |

**Key Methods:**

- `_compute_reward_total()` — Sums `price_subtotal` for non-product rewards; for product rewards, subtracts `lst_price * qty`.
- `_get_no_effect_on_threshold_lines()` — Returns lines excluded from minimum amount thresholds (e.g., some rewards). Default returns empty recordset.
- `action_confirm()` — Validates all coupons have non-negative real points, calls `_update_programs_and_rewards()`, removes unused `current` program coupons, applies point changes to coupon balances, calls `super()`, sends reward coupon emails.
- `_action_cancel()` — Reverts point changes on confirmed orders, removes reward lines, deletes non-nominative coupons with no use count, clears `coupon_point_ids`.
- `action_open_reward_wizard()` — Opens the reward claim wizard if multiple options exist; if only one non-multi-product reward, auto-applies immediately.
- `_get_applied_global_discount_lines()` / `_get_applied_global_discount()` — Returns the first global discount reward line.
- `_get_reward_values_product(reward, coupon, product=None)` — Returns line vals dict for a free product reward. Computes claimable count from points, calculates `points_cost`, generates random reward code.
- `_get_reward_values_discount(reward, coupon)` — Complex discount calculation:
  - Calls `_discountable_order()` / `_discountable_cheapest()` / `_discountable_specific()` based on applicability
  - Applies `discount_max_amount` cap, then `discount_mode` calculation
  - Handles `per_point` (uses coupon balance), `per_order` (fixed), `percent` (percentage)
  - Returns line dicts per tax for non-payment programs; single negative line for payment programs
- `_discountable_order(reward)` — Computes total discountable amount and per-tax breakdown for `order` applicability. Excludes `is_payment_program` lines from threshold lines.
- `_discountable_cheapest(reward)` — Returns cheapest non-reward line's price and tax breakdown.
- `_discountable_specific(reward)` — Complex: prevents discount from making order go below zero. Tracks remaining amounts per line, applies existing discounts first, then computes new discountable.
- `_send_reward_coupon_mail()` — Sends creation emails for any coupons generated from this order.
- `copy()` — Overridden to delete reward lines when copying an order.

---

### sale.order.line (`sale_loyalty/models/sale_order_line.py`)

Extends `sale.order.line` to represent reward lines and track coupon point costs.

**New Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `is_reward_line` | Boolean | Computed: True if `reward_id` exists |
| `reward_id` | Many2one | Which `loyalty.reward` created this line |
| `coupon_id` | Many2one | Which `loyalty.card` was used |
| `reward_identifier_code` | Char | Groups multiple lines from the same reward |
| `points_cost` | Float | Points deducted from coupon for this line |

**Key Methods:**

- `_compute_is_reward_line()` — Sets based on `bool(reward_id)`.
- `_compute_name()` — Skips name computation for reward lines (avoids expensive product name lookup).
- `_compute_tax_id()` — For reward lines, applies fiscal position to taxes. Discount lines are split per tax via the line product; free product lines use the line tax.
- `_get_display_price()` — Reward lines (non-product) use `price_unit` directly without going through pricelist.
- `_can_be_invoiced_alone()` — Reward lines cannot be invoiced by themselves.
- `_is_not_sellable_line()` — Reward lines are not sellable.
- `_is_discount_line()` — True for discount-type rewards.
- `_reset_loyalty(complete=False)` — Zeroes `points_cost` and `price_unit`; if `complete`, also clears `coupon_id` and `reward_id`.
- `create(vals_list)` — On create, if order is confirmed (`state == 'sale'`), deducts `points_cost` from `coupon_id.points`.
- `write(vals)` — If `points_cost` changes, adjusts `coupon_id.points` (adds back old, subtracts new).
- `unlink()` — Removes related reward lines from the same order, returns points to coupons if confirmed, deletes orphaned auto-generated coupons.
- `_sellable_lines_domain()` — Excludes `reward_id` lines from sellable domain.

---

### sale.order.coupon.points (`sale_loyalty/models/sale_order_coupon_points.py`)

Tracks how a specific coupon's points are affected by an order. Each `(order, coupon)` pair has at most one record (SQL unique constraint).

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | Many2one | Sale order (cascade delete) |
| `coupon_id` | Many2one | Loyalty card (cascade delete) |
| `points` | Float | Points impact (+ earned or - redeemed) |

---

## How Coupons Work

### Program Types and Flow

**Automatic Programs (`trigger = auto`):**
1. Order is created/updated
2. `_update_programs_and_rewards()` checks rules
3. Matching rules accumulate points
4. If `applies_on == 'current'` and points cover a reward, reward line added
5. If `applies_on == 'future'`, a `loyalty.card` is generated (coupon sent by email)

**Code-Based Programs (`trigger = with_code`):**
1. User enters code in the frontend
2. `applied_coupon_ids` or `code_enabled_rule_ids` populated
3. Same rule/reward matching occurs

### Point Earning Flow (on `action_confirm`)

1. `_get_point_changes()` computes per-coupon net point delta
2. `coupon.points += delta` for each coupon
3. If `applies_on == 'future'`, new `loyalty.card` created with the points
4. Email sent via `_send_reward_coupon_mail()`

### Point Redemption Flow

1. Customer claims reward via `action_open_reward_wizard()`
2. `_apply_program_reward()` called
3. `_get_reward_values_discount()` or `_get_reward_values_product()` computes line values
4. `sale.order.line` created with `reward_id`, `coupon_id`, `points_cost`
5. On `sale` state, `coupon_id.points -= points_cost`

---

## Sale Order Line Reward Lifecycle

| Event | Action |
|-------|--------|
| Line created (order confirmed) | `coupon_id.points -= points_cost` |
| Points cost changed | `coupon_id.points += old_cost; coupon_id.points -= new_cost` |
| Line deleted | `coupon_id.points += points_cost`; remove from `applied_coupon_ids` |
| Order cancelled | `coupon_id.points += points_cost` for all reward lines |

---

## See Also

- [Modules/sale](sale.md) — `sale.order` base
- [Modules/loyalty](loyalty.md) — Base loyalty framework (program, rule, reward, card)
- [Modules/website_sale_loyalty](website_sale_loyalty.md) — eCommerce-specific loyalty integration