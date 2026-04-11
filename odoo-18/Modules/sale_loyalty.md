# sale_loyalty - Sale Loyalty

**Module:** `sale_loyalty`
**Depends:** `sale`, `loyalty`
**Auto-install:** True
**Category:** Sales/Sales

---

## Purpose

Integrates the base `loyalty` program system with sale orders. Enables discount and loyalty programs (coupons, loyalty cards, promotions) to be applied on sales orders. Adds SO-specific fields and wizards for applying coupon codes and selecting rewards. The core loyalty models (`loyalty.card`, `loyalty.program`, `loyalty.rule`, `loyalty.reward`) are defined in the `loyalty` base module.

---

## Models

### sale.order Extension

**File:** `models/sale_order.py`

Extends `sale.order` to track applied coupons and loyalty state:

| Field | Type | Description |
|---|---|---|
| `applied_coupon_ids` | `Many2many` | Manually applied coupon cards |
| `code_enabled_rule_ids` | `Many2many` | Manually triggered promotion rules |
| `coupon_point_ids` | `One2many` | Tracks coupon point changes per order (`sale.order.coupon.points`) |
| `reward_amount` | `Float` | Computed total discount from reward lines |
| `loyalty_data` | `Json` | Computed loyalty state for UI |

**Key Computed Fields:**

- `_compute_reward_total()` - Sums `price_subtotal` of reward lines (non-product rewards)
- `_compute_loyalty_data()` - Json blob with program states, claimable rewards, coupon points

**Key Methods:**

- `_get_claimable_rewards()` - Returns `{coupon: reward_set}` dict of claimable rewards per coupon
- `_apply_program_reward(reward, coupon, product)` - Applies a reward from a coupon
- `_update_programs_and_rewards()` - Recomputes reward lines
- `_try_apply_code(code)` - Attempts to apply a coupon/promo code to the order
- `_reset_loyalty()` - Clears all loyalty data
- `_update_loyalty_history(coupon, points)` - Records point history

**Wizard Actions:**

- `action_apply_loyalty()` - Opens the reward selection wizard

---

### sale.order.line Extension

**File:** `models/sale_order_line.py`

| Field | Type | Description |
|---|---|---|
| `is_reward_line` | `Boolean` | Computed, True if line has a `reward_id` |
| `reward_id` | `Many2one` | The loyalty reward that generated this line |
| `coupon_id` | `Many2many` | The coupon used for this reward |
| `reward_identifier_code` | `Char` | Groups multiple reward lines from the same reward together |
| `points_cost` | `Float` | Loyalty points consumed on this line |

**Key Methods:**

- `_compute_is_reward_line()` - Returns `bool(line.reward_id)`
- `_compute_tax_id()` - Handles tax computation for discount and free product lines
- `_get_display_price()` - For discount rewards, returns `price_unit` directly (no list_price lookup)
- `_can_be_invoiced_alone()` - Returns False for reward lines
- `_is_not_sellable_line()` - Reward lines excluded from sellable products
- `_is_discount_line()` - Returns True if `reward_id.reward_type == 'discount'`
- `_reset_loyalty(complete)` - Resets points_cost and optionally coupon/reward
- `_sellable_lines_domain()` - Adds `reward_id = False` to exclude reward lines

**CRUD Overrides:**

- `create()` - Deducts points from coupon when order is confirmed (`state == 'sale'`)
- `write()` - Adjusts coupon points if points_cost changes on a confirmed order
- `unlink()` - Also removes related reward lines, unlinks auto-created coupons, returns points to coupon

---

### loyalty.card Extension

**File:** `models/loyalty_card.py`

| Field | Type | Description |
|---|---|---|
| `order_id` | `Many2one` | The sale order that generated this coupon |

**Overrides:**

- `_get_default_template()` - Returns `loyalty.mail_template_loyalty_card` if no template set
- `_get_mail_partner()` - Prefers `order_id.partner_id` over card partner
- `_get_mail_author()` - Uses order's salesperson or company as author
- `_get_signature()` - Uses order's user signature
- `_compute_use_count()` - Includes sale order line usage count
- `_has_source_order()` - Returns True if the card was generated from a sale order

---

### loyalty.program Extension

**File:** `models/loyalty_program.py`

| Field | Type | Description |
|---|---|---|
| `order_count` | `Integer` | Number of unique orders with rewards from this program |
| `sale_ok` | `Boolean` | Default True - program available in sales |

**Overrides:**

- `_compute_order_count()` - Counts unique orders (1 per program per order)
- `_compute_total_order_count()` - Includes order_count in total_order_count

---

### sale.order.coupon.points

**File:** `models/sale_order_coupon_points.py`

| Field | Type | Description |
|---|---|---|
| `order_id` | `Many2one` | Sale order |
| `coupon_id` | `Many2one` | Loyalty card |
| `points` | `Float` | Points impact from this order |

SQL constraint: unique(order_id, coupon_id)

---

### loyalty.history Extension

**File:** `models/loyalty_history.py`

- `_get_order_portal_url()` - Returns portal URL for sale order source

---

### loyalty.reward Extension

**File:** `models/loyalty_reward.py`

Overrides `_get_discount_product_values()` to set tax-free, order-based invoicing for discount products.
Overrides `unlink()` - Archives instead of deletes if reward has been used in an SO line.

---

## Wizards

### sale.loyalty.coupon.wizard

**File:** `wizard/sale_loyalty_coupon_wizard.py`

| Field | Type | Description |
|---|---|---|
| `order_id` | `Many2one` | Target SO |
| `coupon_code` | `Char` | Code to apply |

**Action:** `action_apply()` - Calls `_try_apply_code(coupon_code)`, then opens the reward selection wizard

---

### sale.loyalty.reward.wizard

**File:** `wizard/sale_loyalty_reward_wizard.py`

| Field | Type | Description |
|---|---|---|
| `order_id` | `Many2one` | Target SO |
| `reward_ids` | `Many2many` | Computed claimable rewards |
| `selected_reward_id` | `Many2one` | User's selected reward |
| `multi_product_reward` | `Boolean` | Related to selected reward |
| `reward_product_ids` | `Many2many` | Products in multi-product rewards |
| `selected_product_id` | `Many2one` | Selected product (for multi-product rewards) |

**Compute:** `_compute_claimable_reward_ids()` - Gets claimable rewards from `_get_claimable_rewards()`

**Action:** `action_apply()` - Applies the selected reward via `_apply_program_reward()`, then updates programs

---

## Loyalty Program Types (from base loyalty module)

| Program Type | Description |
|---|---|
| `coupon` | One-time code-based promotions |
| `loyalty` | Accumulated points programs |
| `gift_card` | Prepaid card programs |

### trigger_on Options

| Value | Description |
|---|---|
| `pos` | Trigger at Point of Sale |
| `order` | Trigger at Sale Order |

### rule Types (from loyalty)

| rule_type | Description |
|---|---|
| `product` | Based on specific products |
| `product_category` | Based on product categories |
| `minimum_amount` | Minimum order amount |
| `order` | Any order |

### reward Types (from loyalty)

| reward_type | Description |
|---|---|
| `product` | Free product reward |
| `discount` | Discount (percentage or fixed) |
| `evoucher` | Electronic voucher |

### discount Types

| discount_type | Description |
|---|---|
| `percentage` | % discount |
| `fixed_amount` | Fixed amount discount |

### discount_apply_on

| Value | Description |
|---|---|
| `order` | Entire order |
| `specific_products` | Specific products only |
| `categories` | Product categories |

---

## Loyalty Flow in Sale Order

1. **User enters code** via `sale.loyalty.coupon.wizard`
2. **`_try_apply_code()`** validates code and creates/uses coupon
3. **`_get_claimable_rewards()`** determines which rewards can be claimed
4. **Reward wizard** lets user select which reward to apply
5. **`_apply_program_reward()`** creates reward order lines
6. **On SO confirmation** - points are deducted from coupons and history recorded
7. **On SO cancellation** - points are returned

---

## Key Integration Points

### With `loyalty` module

- `loyalty.card` - Stores coupon/loyalty card state
- `loyalty.program` - Defines program rules and rewards
- `loyalty.rule` - Defines earning conditions
- `loyalty.reward` - Defines what the customer gets
- `loyalty.mail` - Automatic email for loyalty programs
- `loyalty.level` - Tiered loyalty (silver/gold/platinum)
- `coupon.generate` - Wizard to generate coupon codes

### With `sale`

- `sale.order` gets loyalty fields and methods
- `sale.order.line` tracks reward lines

### With `pos_sale_loyalty` (optional)

- POS integration for loyalty at point of sale

### With `sale_loyalty_delivery` (optional)

- Free shipping rewards

---

## Key Constants (from loyalty base module)

The `loyalty` module defines the core program infrastructure. `sale_loyalty` only extends sale-specific behavior. Loyalty levels (tiered programs) and coupon generation are handled in the base module, not here.

---

## Related Modules

| Module | Purpose |
|---|---|
| `loyalty` | Base loyalty infrastructure |
| `loyalty_gift_card` | Gift card specific features |
| `sale_loyalty_delivery` | Free delivery reward |
| `pos_sale_loyalty` | POS + loyalty integration |
| `sale_loyalty_check` | Loyalty check/verification |