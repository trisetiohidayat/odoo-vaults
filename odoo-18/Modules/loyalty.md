---
Module: loyalty
Version: Odoo 18
Type: Business
---

# Loyalty & Promotional Programs (`loyalty`)

Manages loyalty cards, gift cards, eWallets, promotions, coupons, and discount codes. Integrates with `sale` for order discount application and `product` for gift card/eWallet prepaid products.

**Source path:** `~/odoo/odoo18/odoo/addons/loyalty/`
**Depends:** `base`, `product`, `sale`

---

## Program Types

The `loyalty.program.program_type` field determines the program behavior:

| `program_type` | `applies_on` | `trigger` | Portal Visible | Point Name | Description |
|----------------|-------------|-----------|---------------|------------|-------------|
| `coupons` | `current` | `with_code` | No | `Coupon point(s)` | Single-use discount codes shared with customers |
| `promotion` | `current` | `auto` | No | `Promo point(s)` | Auto-applied discounts on current order |
| `gift_card` | `future` | `auto` | Yes | `€` (currency symbol) | Sell gift cards; points represent prepaid credit |
| `loyalty` | `both` | `auto` | Yes | `Loyalty point(s)` | Accumulate points across orders, redeem for rewards |
| `ewallet` | `future` | `auto` | Yes | `€` (currency symbol) | Store monetary value for future orders |
| `promo_code` | `current` | `with_code` | No | `Discount point(s)` | Single promo code for specific products |
| `buy_x_get_y` | `current` | `auto` | No | `Credit(s)` | Buy N items, get M free (e.g., 2+1) |
| `next_order_coupons` | `future` | `auto` | Yes | `Coupon point(s)` | Generate coupon for next order after current order |
| `fidelity` | `both` | `auto` | No | `Loyalty point(s)` | Buy 10 units of a specific product → 10 currency off (variant of `loyalty`) |

---

## Models

### `loyalty.program` — Program Definition

```python
class LoyaltyProgram(models.Model):
    _name = 'loyalty.program'
```

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Program name (required) |
| `program_type` | Selection | One of 9 program types (see table above) |
| `active` | Boolean | Soft delete; cascades to rules/rewards/comm plans |
| `sequence` | Integer | Display order |
| `company_id` | M2O `res.company` | Multi-company scoping |
| `currency_id` | M2O `res.currency` | Program currency; defaults to company currency |
| `currency_symbol` | Char | Related from currency |
| `pricelist_ids` | M2M `product.pricelist` | Restrict program to specific pricelists only |
| `date_from` / `date_to` | Date | Validity period |
| `limit_usage` | Boolean | Whether to cap total usage |
| `max_usage` | Integer | Max total uses if `limit_usage=True` |
| `applies_on` | Selection: `current`/`future`/`both` | When rewards can be claimed |
| `trigger` | Selection: `auto`/`with_code` | How customers access the program |
| `portal_visible` | Boolean | Show points in portal/eCommerce/PoS |
| `portal_point_name` | Char | Label for points in portal (e.g., "Points", "€") |
| `is_nominative` | Boolean (compute) | `applies_on='both'` or (`ewallet`/`loyalty` + `applies_on='future'`) — card tied to partner |
| `is_payment_program` | Boolean (compute) | `program_type in ('gift_card', 'ewallet')` — can pay with points |
| `rule_ids` | O2M `loyalty.rule` | Conditional rules for earning points |
| `reward_ids` | O2M `loyalty.reward` | Rewards that can be claimed |
| `communication_plan_ids` | O2M `loyalty.mail` | Email/SMS triggers |
| `coupon_ids` | O2M `loyalty.card` | Issued coupons/gift cards |
| `coupon_count` | Integer (compute) | Total coupons in this program |
| `coupon_count_display` | Char (compute) | Human-readable count label |
| `total_order_count` | Integer (compute) | Currently `0` (placeholder for analytics) |
| `payment_program_discount_product_id` | M2O `product.product` | Auto-created discount product for gift_card/ewallet |
| `mail_template_id` | M2O `mail.template` | Simplified field for gift_card/ewallet comm plans |
| `trigger_product_ids` | M2M `product.product` | Alias for `rule_ids.product_ids` (gift_card/ewallet simplified view) |

#### Program Type Default Values

When `program_type` changes, `_compute_from_program_type()` writes the defaults defined in `_program_type_default_values()`:

```python
'gift_card': {
    'applies_on': 'future', 'trigger': 'auto', 'portal_visible': True,
    'portal_point_name': currency_symbol,
    'rule_ids': [(5,0,0), (0,0, {'reward_point_mode': 'money', 'reward_point_split': True,
                                'product_ids': gift_card_product})],
    'reward_ids': [(5,0,0), (0,0, {'reward_type': 'discount', 'discount_mode': 'per_point',
                                   'discount': 1, 'discount_applicability': 'order', 'required_points': 1})],
},
'loyalty': {
    'applies_on': 'both', 'trigger': 'auto', 'portal_visible': True,
    'portal_point_name': 'Loyalty point(s)',
    'rule_ids': [(5,0,0), (0,0, {'reward_point_mode': 'money'})],
    'reward_ids': [(5,0,0), (0,0, {'discount': 5, 'required_points': 200})],
},
'ewallet': {
    'applies_on': 'future', 'trigger': 'auto', 'portal_visible': True,
    'portal_point_name': currency_symbol,
    'rule_ids': [(5,0,0), (0,0, {'reward_point_amount': '1', 'reward_point_mode': 'money'})],
    'reward_ids': [(5,0,0), (0,0, {'discount_mode': 'per_point', 'discount': 1, 'required_points': 1})],
}
```

#### Key Methods

- `_compute_currency_id()` — Defaults to `company_id.currency_id`
- `_compute_is_nominative()` — Nominative if `applies_on='both'` or eWallet/loyalty with `applies_on='future'`
- `_compute_is_payment_program()` — True for gift_card and ewallet
- `_compute_coupon_count()` — Groups `loyalty.card` by `program_id`
- `_get_valid_products(products)` — Returns dict `{rule: matching_products}` — filters products by each rule's domain; for gift_card returns all products if rule has no domain
- `toggle_active()` — Cascade-enables/disables rules, rewards, comm plans, and discount line products
- `get_program_templates()` — Returns menu templates for both `gift_ewallet` and standard menu types
- `create_from_template()` — Creates program from template; returns form action
- `_get_template_values()` — Returns per-type default creation values

#### Constraints

- `check_max_usage`: `limit_usage=False OR max_usage > 0`
- `_check_date_from_date_to`: `date_to >= date_from`
- `_constrains_reward_ids`: At least one reward required (skipped via `loyalty_skip_reward_check` context)
- `_check_pricelist_currency`: All pricelists must use the program's currency

---

### `loyalty.rule` — Earning Rules

```python
class LoyaltyRule(models.Model):
    _name = 'loyalty.rule'
```

| Field | Type | Notes |
|-------|------|-------|
| `program_id` | M2O `loyalty.program` | Parent program (required, cascade delete) |
| `program_type` | Selection | Related from program |
| `active` | Boolean | Soft delete |
| `product_ids` | M2M `product.product` | Match specific products |
| `product_category_id` | M2O `product.category` | Match product category + children |
| `product_tag_id` | M2O `product.tag` | Match products with this tag |
| `product_domain` | Char | Serialized domain for advanced filtering (default `"[]"`) |
| `reward_point_amount` | Float | Points earned per trigger (default `1`) |
| `reward_point_mode` | Selection: `order`/`money`/`unit` | How points are computed |
| `reward_point_split` | Boolean | Split coupons per matched unit (only for `future` programs, non-nominative) |
| `reward_point_name` | Char | Related from program |
| `minimum_qty` | Integer | Minimum quantity of matched products |
| `minimum_amount` | Monetary | Minimum order value |
| `minimum_amount_tax_mode` | Selection: `incl`/`excl` | Tax-inclusive or exclusive minimum |
| `mode` | Selection: `auto`/`with_code` | Computed from `code` |
| `code` | Char | Promo code — triggers `mode='with_code'` |

#### Reward Point Modes

- `order`: Fixed `reward_point_amount` points per order (if minimums met)
- `money`: `reward_point_amount` points per currency unit spent (e.g., 1 point per $1)
- `unit`: `reward_point_amount` points per unit of matched product purchased

#### Key Methods

- `_compute_mode()` — If `code` is set → `with_code`; otherwise `auto`
- `_compute_code()` — Clears code when mode is `auto`
- `_get_valid_product_domain()` — Builds domain from `product_ids`, `product_category_id` (with child_of), `product_tag_id`, and `product_domain` AST literal. Combines with `OR`, then `AND` with domain literal.
- `_get_valid_products()` — Returns `product.product` search from domain
- `_compute_amount(currency_to)` — Converts `minimum_amount` to target currency

#### Constraints

- `reward_point_amount > 0`
- Code uniqueness: promo code must not duplicate other rule codes or loyalty card codes
- `_constraint_trigger_multi`: `reward_point_split` not allowed for `ewallet` or nominative programs

---

### `loyalty.reward` — Reward Definitions

```python
class LoyaltyReward(models.Model):
    _name = 'loyalty.reward'
```

| Field | Type | Notes |
|-------|------|-------|
| `program_id` | M2O `loyalty.program` | Parent (required, cascade) |
| `program_type` | Selection | Related from program |
| `active` | Boolean | Soft delete |
| `description` | Char (compute/store) | Human-readable reward description |
| `reward_type` | Selection: `product`/`discount` | Default `discount` |
| `required_points` | Float | Points needed to claim (must be > 0) |
| `point_name` | Char | Related from program |
| `clear_wallet` | Boolean | Redeem all points at once |
| `user_has_debug` | Boolean (compute) | Shows debug info for `base.group_no_one` |

**Discount rewards (`reward_type='discount'`):**

| Field | Type | Notes |
|-------|------|-------|
| `discount` | Float | Discount value (default `10`) |
| `discount_mode` | Selection: `percent`/`per_order`/`per_point` | How discount is applied |
| `discount_applicability` | Selection: `order`/`cheapest`/`specific` | Target of discount |
| `discount_product_domain` | Char | Domain for specific products |
| `discount_product_ids` | M2M `product.product` | Specific discounted products |
| `discount_product_category_id` | M2O `product.category` | Discounted category |
| `discount_product_tag_id` | M2O `product.tag` | Discounted tag |
| `all_discount_product_ids` | M2M `product.product` (compute) | Resolved product list |
| `discount_max_amount` | Monetary | Cap on discount amount |
| `discount_line_product_id` | M2O `product.product` | Auto-created service product for discount line |
| `is_global_discount` | Boolean (compute) | True if `discount` on `order` with `per_order` or `percent` |
| `tax_ids` | M2M `account.tax` | Taxes for the discount line |

**Product rewards (`reward_type='product'`):**

| Field | Type | Notes |
|-------|------|-------|
| `reward_product_id` | M2O `product.product` | Product to give free |
| `reward_product_tag_id` | M2O `product.tag` | Tag for multiple eligible products |
| `multi_product` | Boolean (compute) | True if multiple products available |
| `reward_product_ids` | M2M `product.product` (compute/search) | Computed list of available products |
| `reward_product_qty` | Integer | Quantity to give (default `1`) |
| `reward_product_uom_id` | M2O `uom.uom` (compute) | UoM from the reward product |

#### Key Methods

- `_compute_description()` — Builds description string based on reward type, discount value, mode, applicability, max cap. For gift card/ewallet uses static string.
- `_get_discount_product_domain()` — Resolves `discount_product_ids`, category (with children), tag, and domain literal into a domain expression
- `_compute_all_discount_product_ids()` — Respects `loyalty.compute_all_discount_product_ids` config param: if `enabled`, searches and stores all matching products; if disabled, returns empty
- `_compute_multi_product()` — Combines `reward_product_id` with tag's products (excludes combo type)
- `_search_reward_product_ids()` — Search across `reward_product_id` or `reward_product_tag_id.product_ids`
- `_create_missing_discount_line_products()` — Auto-creates `product.product` records (type=service, sale_ok=False) for discount lines. Called on `create()` and when `description` changes.
- `_get_discount_product_values()` — Returns vals dict for auto-created discount product: `name=description`, `type='service'`, `sale_ok=False`, `purchase_ok=False`, `lst_price=0`

#### Constraints

- `required_points > 0`
- `reward_product_qty > 0` (only when `reward_type='product'`)
- `discount > 0` (only when `reward_type='discount'`)
- `_check_reward_product_id_no_combo`: reward product cannot be type `combo`

---

### `loyalty.card` — Loyalty Card / Coupon / Gift Card

```python
class LoyaltyCard(models.Model):
    _name = 'loyalty.card'
    _rec_name = 'code'
```

| Field | Type | Notes |
|-------|------|-------|
| `program_id` | M2O `loyalty.program` | Parent program |
| `program_type` | Selection | Related from program |
| `partner_id` | M2O `res.partner` | Card owner (optional — for nominative programs) |
| `points` | Float | Current point balance |
| `point_name` | Char | Related from program |
| `points_display` | Char (compute) | Formatted display: `"500 Points"` or formatted currency |
| `code` | Char | Unique identifier (default: generated UUID barcode-style) |
| `expiration_date` | Date | Card expiry; **not allowed for `loyalty` program type** |
| `active` | Boolean | Soft delete |
| `use_count` | Integer (compute) | Times redeemed (override point for extensions) |
| `history_ids` | O2M `loyalty.history` | Transaction history |

#### Key Methods

- `_generate_code()` — Generates `'044' + uuid4()[7:-18]` (barcode-style, unique prefix)
- `_compute_display_name()` — `"ProgramName: Code"`
- `_compute_points_display()` — Calls `_format_points(points)`: if currency symbol, uses `format_amount`; otherwise formats as `"N point_name"`
- `_format_points(points)` — Handles int/float display; currency-formatted if eWallet/gift_card
- `_restrict_expiration_on_loyalty()` — `onchange` raises `ValidationError` if expiration set on `loyalty` type card
- `_compute_use_count()` — Default returns `0`; overridable
- `_get_default_template()` — Returns first comm plan with `trigger='create'`
- `_get_mail_partner()` — Returns `partner_id` (override for special cases)
- `_get_mail_author()` — Returns internal user, company partner, or current company partner
- `_send_creation_communication()` — Sends all `trigger='create'` comm plans on card creation; skips if `loyalty_no_mail` context
- `_send_points_reach_communication(points_changes)` — Sends highest milestone comm plan crossed; only sends if partner exists and points increased
- `_has_source_order()` — Returns `False`; override for e-commerce integration
- `action_coupon_send()` — Opens email composer with default template
- `action_loyalty_update_balance()` — Opens `loyalty.card.update.balance` wizard

#### Constraints

- `card_code_unique`: `unique(code)`
- `_contrains_code()`: Code must not match any `loyalty.rule` with `mode='with_code'`

#### L4: Points Computation Flow

The `sale.order` line processing in `sale_loyalty` module (not base `loyalty`) calls `_get_valid_products()` on rules to determine which products match the rule, then computes points based on `reward_point_mode`:

- `order`: 1× `reward_point_amount` per order
- `money`: `order_subtotal × reward_point_amount` (per currency unit)
- `unit`: `matched_qty × reward_point_amount`

If `reward_point_split=True` and `applies_on='future'`, one coupon is generated **per matched unit** rather than one per order.

#### L4: Gift Card / eWallet — Prepaid Value Mechanism

Gift cards and eWallets work differently from loyalty points:

1. **Gift card sale**: Customer buys a gift card product (e.g., `gift_card_product_50` = €50). The product is configured in the rule's `product_ids`. When purchased, the `loyalty.card` is created with `points = product_price` (since `reward_point_mode='money'` with `reward_point_amount=1`). The card represents €50 of prepaid credit.

2. **eWallet top-up**: Similar mechanism — a top-up product is purchased, creating a card with monetary balance.

3. **Payment**: When a `sale.order` is placed and a gift card/eWallet card is applied, the `loyalty.reward` with `discount_mode='per_point'` converts points back to currency at a 1:1 rate (1 point = 1 currency unit). The `sale_loyalty` module handles applying this as a payment (not a discount line) by setting the order's `loyalty_card_id` field.

4. **Communication**: Both gift card and eWallet programs have a simplified `mail_template_id` field that controls the creation communication. The template is stored via `loyalty.mail` with `trigger='create'`.

---

### `loyalty.mail` — Communication Plans

| Field | Type | Notes |
|-------|------|-------|
| `active` | Boolean | Soft delete |
| `program_id` | M2O `loyalty.program` | Required (cascade delete) |
| `trigger` | Selection: `create`/`points_reach` | When to send |
| `points` | Float | Milestone threshold for `points_reach` trigger |
| `mail_template_id` | M2O `mail.template` | Template to send (model must be `loyalty.card`) |

---

### `loyalty.history` — Transaction History

| Field | Type | Notes |
|-------|------|-------|
| `card_id` | M2O `loyalty.card` | Parent card (cascade delete) |
| `company_id` | M2O | Related from card |
| `description` | Text | Human-readable transaction description |
| `issued` | Float | Points/currency added |
| `used` | Float | Points/currency consumed |
| `order_model` | Char | Source model (e.g., `sale.order`) for linking |
| `order_id` | Many2oneReference | Source record ID |

#### Key Methods

- `_get_order_portal_url()` — Returns `False` by default; override for portal links
- `_get_order_description()` — Returns display name of the source order

---

### `res.partner` — EXTENDED (loyalty module)

| Field | Type | Notes |
|-------|------|-------|
| `loyalty_card_count` | Integer (compute, sudo) | Active loyalty cards with positive points (non-expired) |

#### Key Methods

- `_compute_count_active_cards()` — Uses `_read_group` with complex domain: filters by company, partner+children, points > 0, program active, non-expired. Counts all child partners under the same umbrella.
- `action_view_loyalty_cards()` — Opens loyalty card action filtered to partner and children

---

### `product.product` — EXTENDED (loyalty module)

#### Key Methods

- `write()`: Prevents archiving products used in active loyalty rewards (`discount_line_product_id` or `discount_product_ids`)
- `_unlink_except_loyalty_products()`: Prevents deleting `gift_card_product_50` and `ewallet_product_50` products (must archive instead)

---

### `product.template` — EXTENDED (loyalty module)

- `_unlink_except_loyalty_products()`: Same protection for gift card / eWallet products at template level

---

### `product.pricelist` — EXTENDED (loyalty module)

- `action_archive()`: Prevents archiving a pricelist that is used by active loyalty programs

---

## L4: How Loyalty Interacts with Sale Orders (sale_loyalty module)

The base `loyalty` module provides the data models; the `sale_loyalty` module handles the order integration:

1. **Applying programs to order**: `sale.order` lines call `loyalty.program._get_valid_products()` to filter which products match rules. Points are computed and stored on `sale.order.line` (see `loyalty.card` extension in `sale_loyalty`).

2. **Creating coupons**: When `applies_on='future'` and minimums are met, a `loyalty.card` is generated and emailed via the comm plan.

3. **Redeeming points**: `sale.order` has a `coupon_point_ids` O2M (from `loyalty_card` extension). When a reward is claimed, the card's `points` is decremented and a `loyalty.history` record is created.

4. **Discount lines**: For discount rewards, `loyalty.reward._create_missing_discount_line_products()` creates a service product used as the discount line. The discount is applied as a negative line on the order.

5. **Portal visibility**: `portal_visible=True` programs show the customer's card balance in the eCommerce checkout and in the customer portal via `loyalty_card_count` on `res.partner`.

---

## L4: eCommerce Integration

When `website_sale_loyalty` is installed:
- Loyalty cards appear on the checkout page for portal-visible programs
- Gift cards can be used as payment methods (eWallet balance)
- Promo codes can be entered at checkout
- Points can be redeemed for discounts in the cart

The `loyalty.card._has_source_order()` method returns `False` in base; override to indicate whether the card was generated from a specific e-commerce order for reporting.

---

## Tags

#loyalty #odoo18 #promotion #gift-card #ewallet #coupon #loyalty-card #sale
