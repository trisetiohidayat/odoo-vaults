---
type: module
module: sale_loyalty
tags: [odoo, odoo19, sale, loyalty, coupon, points, gift_card, discount, reward]
created: 2026-04-06
updated: 2026-04-11
---

# sale_loyalty

## Overview

| Property | Value |
|----------|-------|
| **Name** | Loyalty & Loyalty Program on Sales |
| **Technical** | `sale_loyalty` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Module Path** | `~/odoo/odoo19/odoo/addons/sale_loyalty/` |

## Description

Integrates the **loyalty engine** (loyalty card, program, rule, reward) directly into **Sale Orders**. Without this module, loyalty programs operate standalone; with this module, loyalty rules and rewards apply dynamically to quotation/sales order lines. Supports loyalty points, gift cards, e-wallets, and promotional discounts.

**Dependencies:** `sale`, `loyalty`
**Auto-install:** `True` (installed automatically when both `sale` and `loyalty` are present)
**Uninstall hook:** `uninstall_hook()` in `__init__.py` — deletes all `loyalty.history` records where `order_model = 'sale.order'` on module uninstall. Prevents orphaned history entries after the bridge is removed. Also clears associated point allocations via `sale.order.coupon.points` cascade delete.

## Architecture

```
loyalty (base module)
├── loyalty.card         # Kupon/kartu loyalitas
├── loyalty.program      # Program: loyalty, gift_card, ewallet, promotion
├── loyalty.rule         # Aturan earning points
├── loyalty.reward      # Hadiah: discount, free_product
└── loyalty.history     # Riwayat poin

sale_loyalty (bridge module)
├── sale_order.py              # Extends sale.order — coupon tracking, reward wizard, point ops
├── sale_order_line.py         # Extends sale.order.line — reward lines, points_cost
├── loyalty_card.py            # Extends loyalty.card — order_id, use_count from SOL
├── loyalty_program.py         # Extends loyalty.program — order_count, sale_ok
├── loyalty_reward.py          # Extends loyalty.reward — discount product tax settings
├── sale_order_coupon_points.py # sale.order.coupon.points model
└── loyalty_history.py        # Extends loyalty.history — portal URL for SO
```

---

## Key Models

### sale.order (Extended)

**File:** `models/sale_order.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `applied_coupon_ids` | Many2many `loyalty.card` | Coupons manually applied to this order |
| `code_enabled_rule_ids` | Many2many `loyalty.rule` | Rules triggered via promo code |
| `coupon_point_ids` | One2many `sale.order.coupon.points` | Per-coupon point allocations for this order |
| `reward_amount` | Float (computed) | Total value of all discount rewards on this order |
| `gift_card_count` | Integer (computed) | Number of gift card coupons generated from this order |
| `loyalty_data` | Json (computed) | Serialized loyalty points data for the frontend |

**`_get_no_effect_on_threshold_lines()`** (line 128-131):
Returns an empty `sale.order.line` recordset. In the base module, delivery lines have no effect on minimum purchase thresholds. Override in custom modules to exclude additional line types (e.g., service fees) from rule evaluation.

#### Computed Fields

**`_compute_reward_total()`** (line 39-51):
```python
def _compute_reward_total(self):
    for order in self:
        reward_amount = 0
        for line in order.order_line:
            if not line.reward_id:
                continue
            if line.reward_id.reward_type != 'product':
                reward_amount += line.price_subtotal
            else:
                # Free products subtract their retail value
                reward_amount -= line.product_id.lst_price * line.product_uom_qty
        order.reward_amount = reward_amount
```
For discount rewards: sum of `price_subtotal` (already negative).
For free product rewards: subtract the retail value (`lst_price * qty`) from the total.

**`_compute_loyalty_data()`** (line 53-84):
Populates `loyalty_data` JSON for confirmed orders only. Reads from `loyalty.history` via sudo to get `total_issued` and `total_cost` per order. Used by the loyalty reward wizard UI.

**`_compute_gift_card_count()`** (line 86-98):
Counts `loyalty.card` records linked to this order with `program_type = 'gift_card'`.

---

### sale.order.line (Extended)

**File:** `models/sale_order_line.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `is_reward_line` | Boolean (computed) | True if this line is a loyalty reward |
| `reward_id` | Many2one `loyalty.reward` | The reward that generated this line |
| `coupon_id` | Many2one `loyalty.card` | The loyalty card used for this reward |
| `reward_identifier_code` | Char | Groups multiple lines from the same reward claim together |
| `points_cost` | Float | Points consumed from the card for this reward |

#### Key Method Overrides

**`_compute_name()`** (line 21-24): Skips name computation for reward lines — avoids product description lookup errors.

**`_compute_discount()`** (line 26-28): Skips discount computation for reward lines.

**`_compute_tax_ids()`** (line 35-46): Reward lines compute taxes using the partner's fiscal position independently from the product taxes. Gift card/discount rewards use no-tax products.

**`_get_display_price()`** (line 48-53): Returns `price_unit` directly for non-product rewards (price is set by the promotion, not from product list_price).

**`_can_be_invoiced_alone()`** (line 55-56): Reward lines cannot be invoiced independently of the parent order.

**`_is_discount_line()`** (line 58-59): Lines with `reward_type == 'discount'` are recognized as discount lines by the account module.

**`_reset_loyalty(complete=False)`** (line 61-80): Resets a line to a non-reward state (`points_cost=0`, `price_unit=0`). If `complete=True`, also clears `coupon_id` and `reward_id`. Called during program/reward re-evaluation.

#### create() / write() — Point Synchronization (line 83-105)

```python
# On create: if order already confirmed, deduct points immediately
if line.coupon_id and line.points_cost and line.state == 'sale':
    line.coupon_id.points -= line.points_cost
    line.order_id._update_loyalty_history(line.coupon_id, line.points_cost)

# On write (points_cost changed): reverse old + apply new
previous_vals = {line: (line.points_cost, line.coupon_id) for line in self}
res = super().write(vals)
if cost_in_vals:
    for line, (previous_cost, previous_coupon) in previous_vals.items():
        if line.state != 'sale':
            continue
        if line.points_cost != previous_cost or line.coupon_id != previous_coupon:
            previous_coupon.points += previous_cost
            line.coupon_id.points -= line.points_cost
```

If the SOL's points_cost changes on an already-confirmed order, the points are adjusted immediately.

#### unlink() — Cleanup (line 107-132)

On reward line deletion:
1. Finds and deletes all related reward lines (same `reward_identifier_code`)
2. Removes the coupon from `applied_coupon_ids` if it was the last line using it
3. Deletes auto-generated coupons (nominative, `applies_on == 'current'`) that have no remaining lines
4. **Restores points** to the coupon if the order is confirmed
5. Unlinks orphaned coupon records

**`_sellable_lines_domain()`** (line 134-135): Excludes reward lines from the product availability domain used in the e-commerce/cart.

**`_can_be_edited_on_portal()`** (line 139-140): Reward lines are locked from portal edit.

---

### sale.order.coupon.points

**File:** `models/sale_order_coupon_points.py`

Tracks how a sale order impacts a specific coupon's point balance. This is the **per-order point ledger**.

```python
class SaleOrderCouponPoints(models.Model):
    _name = 'sale.order.coupon.points'
    order_id    # -> sale.order (cascade delete)
    coupon_id   # -> loyalty.card (cascade delete)
    points      # Float — positive = issued, negative = consumed
```

**SQL Constraint:** `UNIQUE(order_id, coupon_id)` — one row per coupon per order.

This model records the **allocation** of points on an order before confirmation. At confirmation time, `_add_loyalty_history_lines()` converts these allocations into `loyalty.history` entries.

---

### loyalty.card (Extended)

**File:** `models/loyalty_card.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | Many2one `sale.order` | The order that generated this card (for gift card/loyalty card generation). Readonly. Used to link generated coupons back to the originating SO. |
| `order_id_partner_id` | Many2one `res.partner` (related) | Partner from the generating order via `order_id.partner_id`. Used as the email recipient override for card communications. |

#### Key Methods

**`_get_default_template()`** (line 19-23): Falls back to `loyalty.mail_template_loyalty_card` if no program-specific template exists.

**`_mail_get_partner_fields()`** (line 25-26): Includes `order_id_partner_id` so the card email goes to the order's customer, not the generating partner (who may be an internal sales rep, not the end customer).

**`_get_mail_author()`** (line 28-33): Returns the **order's salesperson** (or the order's company) as the email author, instead of the system default. Ensures the sales rep sends the loyalty card email. Checks `order_id.sudo().company_id in env.companies` before assuming the order is accessible.

**`_get_signature()`** (line 35-36): Uses the order's salespersons's signature (`order_id.user_id.signature`) instead of the card's own partner signature. Fallback to `super()` if no order or user.

**`_compute_use_count()`** (line 38-44): Adds SOL-based usage to the card's use count via `read_group` on `sale.order.line` filtered by `coupon_id`. Combined with base module's loyalty.history count for total usage.

**`_has_source_order()`** (line 46-47): Returns True if the card was generated from a sale order — used by `_get_allow_nominative_transfer()` (base) to determine if the card can be transferred to another partner. Card is non-transferable if `order_id` is set.

**`action_archive()`** (line 49-54): When archiving a card, also deletes draft-state point entries in `sale.order.coupon.points`. Unlinks via `search()` then `unlink()` (not `unlink()` via O2M cascade) to avoid accidentally deleting confirmed-order point entries.

---

### loyalty.program (Extended)

**File:** `models/loyalty_program.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `order_count` | Integer (computed) | Number of distinct SOs that used a reward from this program |
| `sale_ok` | Boolean | Whether this program can be used in Sales (default `True`) |

**`_compute_order_count()`** (line 12-21):
Uses `read_group` on `sale.order.line` with `reward_id` filter. Counts distinct orders per program, accounting for multiple reward lines from the same order being counted once.

**`_compute_total_order_count()`** (line 23-26): Adds the `order_count` to the base program's total (combines POS + eCommerce + Sales counts).

---

### loyalty.reward (Extended)

**File:** `models/loyalty_reward.py`

**`_get_discount_product_values()`** (line 9-17): Configures the auto-generated discount product for sale orders:
- `taxes_id = False` — discounts are not taxable
- `supplier_taxes_id = False`
- `invoice_policy = 'order'` — invoiced at order time, not delivery

**`unlink()`** (line 19-22): If the reward is in use on any SOL, archives it instead of deleting (prevents orphaned reward references).

---

### loyalty.history (Extended)

**File:** `models/loyalty_history.py`

**`_get_order_portal_url()`** (line 9-12): Returns the portal URL for the associated sale order (enabling the customer to view the order from the loyalty history email).

---

## Reward Computation Flow

### Entry Point: `_update_programs_and_rewards()`

This method (inherited from `loyalty` base module) is called every time the order changes. It runs in 5 stages:

```
STEP 1: Retrieve all applicable programs
  ├── Load nominative cards (loyalty/ewallet) into applied_coupon_ids
  ├── Gather points_programs (already applied, earning points)
  ├── Gather coupon_programs (applied via promo code)
  ├── Find automatic_programs (trigger='auto', not yet applied)
  └── Validate via _program_check_compute_points()

STEP 2: Update applied programs
  ├── Programs with errors → remove reward lines, unlink coupons
  └── Valid programs → update coupon_point_ids

STEP 3: Update reward lines
  ├── Reset all reward lines to reward-less state
  ├── Re-apply rewards based on current points
  └── Gift card/ewallet applied last

STEP 4: Apply new programs
  └── __try_apply_program() for each newly triggered automatic program

STEP 5: Cleanup
  └── Remove orphaned reward lines and coupons
```

### Discount Computation Methods

| Method | Applies To | Description |
|--------|-----------|-------------|
| `_discountable_order()` | Order-level discount | Full order subtotal eligible |
| `_discountable_cheapest()` | Cheapest line | Only the cheapest eligible line |
| `_discountable_specific()` | Specific products | Domain-filtered products, avoids negative totals |
| `_discountable_amount()` | Helper | Total amount ignoring certain rewards |
| `_cheapest_line()` | Helper | Finds cheapest eligible line for `cheapest` and `specific` |
| `_get_specific_discountable_lines()` | Helper | Returns all eligible lines for `specific` discounts |

**`_get_applied_global_discount_lines()`** (line 241-246):
Returns the first applied global discount reward line (or empty recordset). A reward is a global discount if `reward.is_global_discount == True` (order-level `percent` or `per_order` discounts). Used by `_apply_program_reward()` to detect and compare competing global discounts.

**`_get_applied_global_discount()`** (line 248-252):
Returns the `loyalty.reward` record for the currently applied global discount. Convenience wrapper around `_get_applied_global_discount_lines().reward_id`.

**`_discountable_order()`** is the most complex:
- Uses `AccountTax._aggregate_base_lines_tax_details()` for tax grouping
- Gift cards / eWallets apply to the **full order amount**
- Other programs **exclude delivery lines** from the discount base
- **Fixed taxes are never discounted**

**`_get_reward_values_discount()`** produces the `sale.order.line` values for discount rewards:
- Handles three `discount_mode` values: `per_point`, `per_order`, `percent`
- Handles three `discount_applicability` values: `order`, `cheapest`, `specific`
- Discount is **capped** at `discount_max_amount`, `order's total amount`, and the `discountable` amount
- If multiple tax groups exist on the order, the discount is **split per tax group** (one SOL per group)
- For gift card / eWallet (`is_payment_program=True`): `price_unit = -min(max_discount, discountable)`

### Helper Methods for Discount Computation

**`_cheapest_line(reward)`** (line 389-407):
Finds the cheapest order line eligible for a `cheapest` discount. Applies `reward._get_discount_product_domain()` filter and skips reward lines, combo item lines, and zero-qty/zero-price lines. Returns `line._get_lines_with_price()` (a recordset, not a single line). Used by both `_discountable_cheapest()` and `_discountable_specific()`.

**`_get_specific_discountable_lines(reward)`** (line 429-445):
Returns all non-reward, non-combo order lines whose `product_id` matches `reward._get_discount_product_domain()`. Skips `_get_no_effect_on_threshold_lines()` (delivery lines). Used by `_discountable_specific()` and `_discountable_cheapest()` to build the candidate line set.

**`_generate_random_reward_code()`** (module-level function):
Generates an 8-character lowercase hex string (`str(random.getrandbits(32))`) used as `reward_identifier_code` on each new reward line. Groups all lines generated from the same reward claim so they can be deleted together in `unlink()`. Not cryptographically random — only used for intra-order grouping.

**`_get_reward_values_product()`** handles free product rewards:
- Determines how many free units can be claimed (`points // required_points`)
- `clear_wallet` option: claims all points at once
- Sets `reward_product_qty = reward.reward_product_qty * claimable_count`

---

## Order Lifecycle Hooks

### `action_confirm()` Override (line 140-183)

```
1. Validate: ensure no reward has negative points
   └── raises ValidationError if any coupon would go negative

2. _update_programs_and_rewards()
   └── Re-evaluate all programs and rewards

3. _add_loyalty_history_lines()
   └── Creates loyalty.history entries:
       - issued = coupon_point_ids.points (points allocated)
       - used = sum(order_line.points_cost) (points consumed)

4. Remove ghost coupons
   └── Deletes unclaimed 'current' program coupons

5. Commit point changes to cards
   └── coupon.points += change (per _get_point_changes())

6. super().action_confirm()
   └── Standard SO confirmation (create pickings, invoices, etc.)

7. If has claimable rewards (and single order):
   └── Display notification: "There are available rewards not added to this order"

8. _send_reward_coupon_mail()
   └── Emails newly generated loyalty/gift cards to customer
```

### `_action_cancel()` Override (line 185-207)

```
1. Delete loyalty.history entries (sudo)
   └── Undo the loyalty ledger entries

2. Reverse point changes
   └── coupon.points -= changes (per _get_point_changes())

3. Unlink all reward lines from the order

4. Unlink auto-generated nominative coupons with no usage
   └── Filters: order_id in self AND use_count = 0

5. Unlink coupon_point_ids
   └── Point allocation records for this order
```

---

## Gift Card / eWallet Flow

Gift cards and e-wallets are **payment programs** (not loyalty programs). They work differently:

| Aspect | Loyalty Program | Gift Card / eWallet |
|--------|----------------|---------------------|
| Balance | Points | Currency amount |
| Program Type | `loyalty` | `gift_card` / `ewallet` |
| Reward Type | discount, free_product | discount only |
| Earning | Based on rules | Pre-loaded on card |
| Discount Applicability | Varies | Full order total |

**Gift card redemption**:
1. Customer enters gift card code on the SO
2. `_get_reward_values_discount()` creates a reward line with:
   - `price_unit = -min(max_discount, discountable)` (negative = credit)
   - `points_cost` = card balance consumed
3. At confirmation: `coupon_id.points -= points_cost`
4. At cancellation: `coupon_id.points += points_cost` (balance restored)

**Gift card generation**:
1. Order confirmed with a gift card program
2. `order_id` written to `loyalty.card`
3. `_send_reward_coupon_mail()` emails the card to the customer

---

## Point Tracking System

### Core Point Methods

**`_get_point_changes()`** (line 759-772):
Computes the net point delta per coupon for the current order state:
```
point_delta = sum(coupon_point_ids.points) - sum(order_line.points_cost)
```
Returns `defaultdict(int) {coupon: delta}`. Called by:
- `action_confirm()`: adds changes to cards (`coupon.points += delta`)
- `_action_cancel()`: reverses changes (`coupon.points -= delta`)

**`_get_real_points_for_coupon(coupon, post_confirm=False)`** (line 774-789):
Returns the usable point balance for a coupon on this order:
```
For unconfirmed orders:
  usable = coupon.points
            + coupon_point_ids.points (if applies_on != 'future')
            - sum(order_line.points_cost)
            → rounded via coupon.currency_id.round()
For confirmed orders: returns coupon.points directly
```
Used by `_apply_program_reward()` to check if a coupon has enough points to claim a reward.

**`_add_points_for_coupon(coupon_points_dict)`** (line 791-808):
Updates or creates `sale.order.coupon.points` entries for a dict of `{coupon: points}`. For confirmed orders, updates `coupon.points` directly (immediate commit). For draft orders, updates or creates `coupon_point_ids` entries. Uses `tracking_disable=True` context on writes.
┌─────────────────────────────────────────────────────────┐
│              POINTS FLOW PER ORDER                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Order Created                                          │
│      │                                                  │
│      ├── Program automatic trigger →                     │
│      │   coupon_point_ids += (coupon, +N points)         │
│      │   → Coupon: points += N                          │
│      │                                                  │
│      ├── Customer apply code →                          │
│      │   applied_coupon_ids += coupon                    │
│      │   → Check rules → _program_check_compute_points()│
│      │                                                  │
│      └── Claim reward →                                 │
│          reward_line created with points_cost             │
│          → Coupon: points -= points_cost                │
│                                                          │
│  Order Confirmed                                        │
│      │                                                  │
│      ├── loyalty.history created:                       │
│      │   issued = coupon_point_ids.points               │
│      │   used = sum(order_line.points_cost)             │
│      │                                                  │
│      └── Points FINAL: coupon.points +/-= changes        │
│                                                          │
│  Order Cancelled                                        │
│      │                                                  │
│      ├── loyalty.history deleted                        │
│      └── coupon.points -= changes (reverse)             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Program Domain Filtering

**`_get_program_domain()`** (line 656-666):
Base domain for all loyalty program searches on this order:

```python
[('active', '=', True),
 ('sale_ok', '=', True),
 company_domain,              # includes child companies
 '|', ('pricelist_ids', '=', False),
      ('pricelist_ids', 'in', [pricelist_id.id]),
 '|', ('date_from', '=', False),
      ('date_from', '<=', today),
 '|', ('date_to', '=', False),
      ('date_to', '>=', today)]
```

Programs must be:
- Active and `sale_ok = True`
- Compatible with the current company (and parent company for inter-company loyalty)
- Compatible with the order's pricelist (or unrestricted)
- Within validity dates (checked against company timezone via `_get_confirmed_tx_create_date()`)

**Program query helpers** on `sale.order`:

| Method | Returns |
|--------|---------|
| `_get_points_programs()` | Programs with a coupon_point_ids entry (earning points on this order) |
| `_get_reward_programs()` | Programs whose rewards are currently applied on SOLs |
| `_get_applied_programs()` | Union of points + reward programs |
| `_get_reward_coupons()` | Positive-point coupons on `applies_on='future'` programs (to email) |
| `_get_applied_global_discount()` | Currently applied global discount reward (if any) |

**`_apply_program_reward(reward, coupon, **kwargs)`** (line 926-959):
Applies a specific reward to the order using the given coupon. Called by the reward wizard and `__try_apply_program()`. Steps:
1. Detects and rejects if a better global discount is already applied
2. Validates coupon has enough points (`_get_real_points_for_coupon()`)
3. Validates non-nominative future programs cannot be claimed on current order
4. Gets reward line values via `_get_reward_line_values()`
5. Writes to order via `_write_vals_from_reward_vals()`
6. Returns `{'error': ...}` dict on failure, `{}` on success
```python
[('active', '=', True),
 ('sale_ok', '=', True),
 company_domain,
 '|', ('pricelist_ids', '=', False),
      ('pricelist_ids', 'in', [pricelist_id.id]),
 '|', ('date_from', '=', False),
      ('date_from', '<=', today),
 '|', ('date_to', '=', False),
      ('date_to', '>=', today)]
```

Programs must be:
- Active and `sale_ok = True`
- Compatible with the current company
- Compatible with the order's pricelist (or unrestricted)
- Within validity dates

---

## Wizard Integration

**`action_open_reward_wizard()`** (line 209-221):
- If exactly 1 reward claimable and exactly 1 coupon → auto-apply
- If multiple → opens `sale.loyalty.reward.wizard`
- If none → returns True (no action)

**`action_view_gift_cards()`** (line 223-232):
Smart button target: opens `loyalty.card` list filtered to `order_id = self` and `program_type = 'gift_card'`.

**`__try_apply_program(program, coupon, status)`** (line 1351-1383):
Private implementation of `_try_apply_program()`. Handles three coupon-creation scenarios:
1. **Nominative + existing coupon**: adds points to the existing card via `_add_points_for_coupon()`
2. **Nominative + no coupon**: searches for existing card, creates one if points > 0
3. **Non-nominative**: creates new coupon(s) in batch (one per split point entry), using `loyalty_no_mail=True` and `tracking_disable=True` context to suppress mail and tracking

**`_get_discount_amount(reward, discountable)`** (line 908-924):
Computes the monetary discount amount for a reward. Handles `discount_mode='per_order'` (direct currency conversion) and `discount_mode='percent'` (percentage of discountable). Used exclusively by `_best_global_discount_already_applied()` to compare two global discounts.

**`_write_vals_from_reward_vals(reward_vals, old_lines, delete=True)`** (line 833-850):
Atomic write on `order_line` combining `Command.UPDATE`, `Command.CREATE`, and `Command.DELETE` in one `write()` call. Preserves `name` (custom descriptions) when reusing a line with the same product. Called by `_apply_program_reward()` and `_update_programs_and_rewards()`. Returns untouched old lines for cleanup.

**`_get_not_rewarded_order_lines()`** (line 1209-1210):
Returns SOLs with a product and no `reward_id`. The starting set for point computation, avoiding double-counting of reward lines.

**`_get_order_line_price(order_line, price_type)`** (line 1212-1213):
Aggregates `price_unit` or `price_total` via `line._get_lines_with_price()`. Used in `_program_check_compute_points()` for `money`-mode point calculations where the amount paid per rule must be summed.

**`_allow_nominative_programs()`** (line 1015-1020):
Returns `True`. Allows loyalty/ewallet cards with existing points to auto-load into `applied_coupon_ids`. Override in POS to restrict nominative programs on layaway orders.

**`_remove_program_from_points(programs)`** (line 821-822):
Unlinks `sale.order.coupon.points` entries for all coupons belonging to the given programs. Called when a program is no longer applicable so its point allocations are cleaned up.

**`_get_applicable_program_points(domain=None)`** (line 705-718):
Searches automatic programs matching `_get_program_domain()`, runs `_program_check_compute_points()`, returns `{program: points}` for programs with a valid `status['points']`. Used by STEP 4 of `_update_programs_and_rewards()` to find newly triggered automatic programs.

**`_get_trigger_domain()`** (line 668-679):
Base domain for searching `loyalty.rule` records by code in `_try_apply_code()`. Combines `_get_program_domain()` with `rule.active`, `program_id.sale_ok`, and code-mode/pricelist/date restrictions. `mode='with_code'` filter is applied at search time.

**`_get_program_timezone()`** (line 681-687):
Returns company timezone (from `company_id.partner_id.tz`), falling back to `loyalty.timezone` config parameter, then `'UTC'`. All program date validity checks use this timezone instead of UTC.

**`copy(default=None)`** (line 133-138):
Duplicates the SO but removes all reward lines via `unlink()`. Reward lines are not copied because points/coupons/discounts are order-specific — copying them would cause double-claiming.

---

## Extension Points

### Custom Points Calculation
Override `_program_check_compute_points()` to add custom rule evaluation logic.

### Adding New Reward Types
Override `_get_reward_line_values()` to handle custom reward type behavior.

### Custom Discount Scope
Override `_discountable_*()` methods to customize which order lines are eligible for discount.

### Pre/Post Reward Application
Override `__try_apply_program()`, calling `super()` to inject logic before/after reward application.

### Prevent Coupon Generation
Override `_send_reward_coupon_mail()` to add conditions or custom email templates.

---

## Key Takeaways

1. **sale_loyalty is a bridge module** between the loyalty engine and sale orders
2. **Points are real-time** — updated on every order change via `_update_programs_and_rewards()`
3. **Confirmation commits points** — once the SO is confirmed, points are finalized on the cards
4. **Gift cards use currency balance**, not points — they are payment programs
5. **Reward discount lines are tax-free** — `taxes_id = False` on discount products
6. **Cancellation is clean** — all tracked points are reversed, all reward lines removed
7. **Multiple discount tax splits** — one SOL per tax group for accurate tax reporting
8. **Partner email matching** is required for card-to-order linking — prevents wrong partner association

---

## Wizard Models

### `sale.loyalty.coupon.wizard`

**File:** `wizard/sale_loyalty_coupon_wizard.py`

**Purpose:** Apply a coupon code to a sales order via UI.

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | Many2one `sale.order` | Target order. Default from context active_id. `required` |
| `coupon_code` | Char | Code to apply. `required` |

**`action_apply()`** — Code Application Flow:
```python
def action_apply(self):
    # 1. Call _try_apply_code on order
    status = self.order_id._try_apply_code(self.coupon_code)

    # 2. Raise error if code invalid
    if 'error' in status:
        raise ValidationError(status['error'])

    # 3. Collect all claimable rewards from returned dict
    #    (returns {coupon: rewards, ...})
    all_rewards = self.env['loyalty.reward']
    for rewards in status.values():
        all_rewards |= rewards

    # 4. Open reward wizard with pre-selected rewards
    action = self.env['ir.actions.actions']._for_xml_id(
        'sale_loyalty.sale_loyalty_reward_wizard_action'
    )
    action['context'] = {
        'active_id': self.order_id.id,
        'default_reward_ids': all_rewards.ids,
    }
    return action
```

**Error Handling:**
- `'not_found': True` in result means code doesn't match any rule or coupon
- `'error'` contains the localized error message
- Common errors: expired coupon, insufficient points, program not available for order

**Related Action:** `sale_loyalty_coupon_wizard_action` (window action, target=new, context populated with active_id)

**Error Handling:**
- `'not_found': True` in result means code doesn't match any rule or coupon — a user-friendly "invalid code" error is raised.
- `'error'` contains the localized error message: e.g., expired coupon, insufficient points, program not available for order, program already applied, incompatible global discount.
- `'already_applied': True` in the `_try_apply_program` error dict — the program is already on the order; the wizard still opens to let the user modify existing rewards.

---

### `sale.loyalty.reward.wizard`

**File:** `wizard/sale_loyalty_reward_wizard.py`

**Purpose:** Select and claim a reward from the available options.

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | Many2one `sale.order` | Target order. Default from context. `required` |
| `reward_ids` | Many2many `loyalty.reward` | Computed from `_get_claimable_rewards()` |
| `selected_reward_id` | Many2one `loyalty.reward` | User's selection. Domain filtered to `reward_ids` |
| `multi_product_reward` | Boolean (related) | True if reward has multiple product options |
| `reward_product_ids` | Many2many `product.product` | Available products for multi-product rewards |
| `selected_product_id` | Many2one `product.product` | Selected product (computed) |

**`action_apply()`** — Reward Application:
```python
def action_apply(self):
    # 1. Validate reward selected
    if not self.selected_reward_id:
        raise ValidationError(_('No reward selected.'))

    # 2. Find the coupon that offers this reward
    claimable_rewards = self.order_id._get_claimable_rewards()
    selected_coupon = False
    for coupon, rewards in claimable_rewards.items():
        if self.selected_reward_id in rewards:
            selected_coupon = coupon
            break

    if not selected_coupon:
        raise ValidationError(_(
            'Coupon not found while trying to add the following reward: %s',
            self.selected_reward_id.description
        ))

    # 3. Apply the reward to the order
    self.order_id._apply_program_reward(
        self.selected_reward_id,
        coupon,
        product=self.selected_product_id
    )

    # 4. Re-evaluate all programs (recalculate discounts)
    self.order_id._update_programs_and_rewards()

    # 5. Clean up unused coupons
    self._unlink_unused_coupon_ids()

    return True
```

**`_unlink_unused_coupon_ids()`** — Cleanup Logic:
```python
def _unlink_unused_coupon_ids(self):
    # Remove 'current' program coupons that were generated by this order
    # but not used by any reward line
    reward_coupons = self.order_id.order_line.coupon_id
    self.order_id.coupon_point_ids.filtered(
        lambda points: (
            points.coupon_id.program_id.applies_on == 'current' and
            points.coupon_id not in reward_coupons
        )
    ).coupon_id.sudo().unlink()
```

**`_compute_claimable_reward_ids()`** — Lazy Reward Loading:
```python
@api.depends('order_id')
def _compute_claimable_reward_ids(self):
    for wizard in self:
        if not wizard.order_id:
            wizard.reward_ids = False
        else:
            # Get all claimable rewards from all applied coupons
            claimable_reward = wizard.order_id._get_claimable_rewards()
            reward_ids = self.env['loyalty.reward']
            for rewards in claimable_reward.values():
                reward_ids |= rewards
            wizard.reward_ids = reward_ids
```

**`action_cancel()`** (line 58-60):
Closes the wizard without applying a reward. Calls `_unlink_unused_coupon_ids()` before closing to clean up any auto-generated `current`-applies coupons that were never used.

**`_unlink_unused_coupon_ids()`** (line 62-69):
Removes `current`-applies coupons that were generated from this order but have no reward line using them. Filters to `coupon_point_ids` where `program_id.applies_on == 'current'` and the coupon is not in `order_line.coupon_id`. Runs `sudo().unlink()` since salespersons may not have unlink rights on loyalty cards.
```python
@api.depends('reward_product_ids')
def _compute_selected_product_id(self):
    for wizard in self:
        if not wizard.selected_reward_id.reward_type == 'product':
            wizard.selected_product_id = False
        else:
            # Default to first available product
            wizard.selected_product_id = wizard.reward_product_ids[:1]
```

---

## L3: Edge Cases and Special Patterns

### Cross-Model: Gift Card Payment with Zero-Order Total

When a gift card covers the entire order amount, `_validate_order()` triggers automatic invoicing:

```python
def _validate_order(self):
    super()._validate_order()
    if self.amount_total or not self.reward_amount:
        return
    # If order total is 0 (fully covered by reward) AND reward_amount exists
    auto_invoice = self.env['ir.config_parameter'].get_param('sale.automatic_invoice')
    if str2bool(auto_invoice):
        self._force_lines_to_invoice_policy_order()
        invoice = self._create_invoices(final=True)
        invoice.action_post()
```

Edge case: `amount_total = 0` but `reward_amount = 0` (no rewards) — no invoice created.

### Cross-Model: POS + Sales Multi-Channel

The `coupon_point_ids` system is shared between POS and Sales. A coupon can be:
1. Generated in POS (points earned)
2. Redeemed in Sales (points consumed)
3. Or vice versa

The `order_count` on `loyalty.program` aggregates across all channels via `_compute_total_order_count()`.

### Override Pattern: Global Discount Comparison

When a new global discount is applied, `_best_global_discount_already_applied()` determines whether to keep the existing one:

```python
def _best_global_discount_already_applied(self, current_reward, new_reward, discountable=None):
    """
    Compare two global discount rewards.

    Rules:
    - If current_reward == new_reward: keep current
    - If BOTH discounts exceed order total: prefer SMALLER discount
      (customer keeps more valuable voucher)
    - Otherwise: prefer BIGGER discount
    """
```

This prevents the scenario where a $100 discount on a $50 order would consume a customer's 15%-off coupon when a 10%-off coupon would be better (leaving the 15% for future use).

### Override Pattern: Code Activation Tracking

Promo codes are tracked via `code_enabled_rule_ids` rather than on the coupon itself:

```python
# In _try_apply_code():
if rule in self.code_enabled_rule_ids:
    return {'error': _("This promo code is already applied.")}

# When applying program:
if rule:
    self.code_enabled_rule_ids |= rule
```

This allows the same rule (code) to be used across multiple orders (each order tracks its own activation). The rule can only be "enabled" once per order.

### Override Pattern: Payment Programs (Gift Card/eWallet)

Gift card and eWallet are **payment programs** (`is_payment_program = True`). They have special behavior:

1. **No threshold effect**: They don't count toward minimum purchase thresholds
2. **Full order amount**: Applied on total order amount (not discounted amount)
3. **No fixed tax exclusion**: Fixed taxes ARE included in discountable amount
4. **Always applied last**: Processed after other discounts in `_update_programs_and_rewards()`

```python
# In _discountable_order():
if not reward.program_id.is_payment_program:
    # Fixed taxes excluded
    taxes = taxes.filtered(lambda t: t.amount_type != 'fixed')
```

### Override Pattern: Coupon Partner Migration

When a public user (no login) order is confirmed, their coupons are migrated to the partner if they later log in:

```python
# In _update_programs_and_rewards():
if pe.coupon_id.partner_id.is_public and not self.partner_id.is_public:
    pe.coupon_id.partner_id = self.partner_id
```

This handles the flow where a guest adds items to cart, applies a coupon, then logs in before confirming.

### Override Pattern: Public-to-Logged Partner Migration

When a public (guest) user applies a coupon to a draft order and then logs in before confirming, the coupon's `partner_id` is updated to the logged-in customer mid-session:

```python
# In _update_programs_and_rewards() STEP 2:
if pe.coupon_id.partner_id.is_public and not self.partner_id.is_public:
    pe.coupon_id.partner_id = self.partner_id
```

This also zeroes out point entries for coupons that don't belong to the current partner (e.g., mistakenly applied a different customer's card):

```python
if pe.coupon_id.partner_id and pe.coupon_id.partner_id != self.partner_id:
    pe.points = 0  # Neutralize rather than unlink to preserve audit trail
    point_entries_to_unlink |= pe
```

### Failure Mode: Expired Coupons

Coupons are filtered on every `_update_programs_and_rewards()` call:

```python
# Remove expired coupons from applied_coupon_ids
if initial_coupons := self.applied_coupon_ids:
    check_date = self._get_confirmed_tx_create_date()
    self.applied_coupon_ids = initial_coupons.filtered(
        lambda c: not c.expiration_date or c.expiration_date >= check_date,
    )
```

This means a coupon expiring mid-quotation will be silently removed.

### Failure Mode: Insufficient Points After Re-evaluation

If a reward is applied, then the order changes (product removed, quantity reduced) such that the coupon no longer has enough points, the reward is automatically removed in STEP 3 of `_update_programs_and_rewards()`:

```python
if coupon not in all_coupons or points < reward.required_points:
    continue  # Reward lines will be removed at end
```

### Performance: Lazy Evaluation in `_get_claimable_rewards()`

The discountable amount and zero-check are lazy to avoid expensive computation when not needed:

```python
# Only evaluate discountable amount if needed
discountable = lazy(lambda: self._discountable_amount(global_discount_reward))
total_is_zero = lazy(lambda: self.currency_id.is_zero(discountable))
```

---

## L4: Performance, Historical Changes, Security

### Performance Implications

#### 1. `_program_check_compute_points()` Complexity

**O(n*m*k)** where:
- n = number of programs
- m = number of rules per program
- k = number of order lines

```python
# For each program → for each rule → for each order line
for line in self.order_line - self._get_no_effect_on_threshold_lines():
    for program in programs:
        for rule in program.rule_ids:
            if line.product_id in so_products_per_rule.get(rule, []):
                lines_per_rule[rule] |= line._get_lines_with_price()
```

**Mitigation:** Uses `_get_valid_products()` with batch filtering:
```python
# Products are pre-filtered per rule
products_per_rule = programs._get_valid_products(products)
```

**Optimization opportunities:**
- Add `limit=1` checks where possible
- Cache `_discountable_amount()` results during reward wizard session
- Consider `read_group` for line aggregation instead of `mapped()`

#### 2. `_discountable_specific()` Nested Loop

Complex nested iteration for fixed-amount discounts that interact with each other:

```python
for lines in discount_lines.values():  # Per reward
    for line in itertools.chain(non_common_lines, common_lines):
        # Track remaining_amount_per_line and discounted_amounts
```

**Complexity:** O(d*m) where d=number of existing discounts, m=lines

**Mitigation:** Uses `defaultdict` for efficient aggregation and early exit when `discounted_amount == 0`.

#### 3. `_update_programs_and_rewards()` - Delayed Cleanup Pattern

Unlink operations are delayed to end to prevent cache invalidation during iteration:

```python
# STEP 5: Cleanup
order_line_update = [(Command.DELETE, line.id) for line in lines_to_unlink]
if order_line_update:
    self.write({'order_line': order_line_update})  # Single write, not per-line
if coupons_to_unlink:
    coupons_to_unlink.sudo().unlink()
```

#### 4. Batch Coupon Creation

When multiple point entries are created for a program:

```python
new_coupons = self.env['loyalty.card'].with_context(
    loyalty_no_mail=True,
    tracking_disable=True
).create([{
    'program_id': program.id,
    'partner_id': partner_id,
    'points': 0,
    'order_id': self.id,
} for _ in new_coupon_points])
```

The `loyalty_no_mail` context prevents email sending for batch-created coupons.

#### 5. `SELECT FOR UPDATE NOWAIT` Locking

```python
self.env.cr.execute("""
    SELECT id FROM loyalty_program WHERE id=%s FOR UPDATE NOWAIT
""", (program.id,))
```

This prevents concurrent code applications from causing race conditions. The `NOWAIT` option causes an error immediately if the lock is held, triggering a transaction retry rather than waiting.

### Odoo 18 → 19 Changes

#### 1. New `_discountable_order()` Implementation (Odoo 19)

Odoo 18 used a simpler calculation for order-level discounts. Odoo 19 refactored to use the account module's tax computation system:

```python
# Odoo 19: Uses tax account module
AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
AccountTax._round_base_lines_tax_details(base_lines, self.company_id)
base_lines_aggregated_values = AccountTax._aggregate_base_lines_tax_details(...)
```

This provides more accurate tax grouping for discount line splitting.

#### 2. `loyalty_data` JSON Field (Odoo 19)

New computed JSON field for frontend portal display:
```python
loyalty_data = fields.Json(compute='_compute_loyalty_data')
# Returns: {'point_name': 'Points', 'issued': 100.0, 'cost': 50.0}
```

Previously, this data was computed on-the-fly by the JS widget.

#### 3. `_get_confirmed_tx_create_date()` Timezone Handling (Odoo 19)

New method for timezone-aware date checking:
```python
def _get_confirmed_tx_create_date(self):
    order_tz = self._get_program_timezone()
    confirmed_txs_dates = self.sudo().transaction_ids.filtered(
        lambda tx: tx.state in ('done', 'authorized'),
    ).mapped('create_date')
    if confirmed_txs_dates:
        tx_date = min(confirmed_txs_dates)
        return tx_date.astimezone(timezone(order_tz)).date()
    return fields.Date.context_today(self.with_context(tz=order_tz))
```

This ensures that program date validity is checked against the company's timezone, not UTC.

#### 4. `_best_global_discount_already_applied()` Addition (Odoo 18→19)

Added to handle the case where a customer has multiple global discount coupons and the system needs to pick the better one.

#### 5. `sale_loyalty_reward_wizard` Enhanced (Odoo 19)

Reward wizard added multi-product support with `selected_product_id` field and computed visibility. Multi-product rewards require the customer to select a specific product from the reward panel before the reward is applied, triggering a redirect to `pricelist()` with the selected product context.

#### 6. `Domain.AND` and `lazy()` API Additions (Odoo 19)

Two new framework APIs are used in `sale_loyalty` for Odoo 19:

**`Domain.AND()`** (`odoo.fields.Domain`): Used in `_get_program_domain()`, `_get_trigger_domain()`, `_get_applicable_program_points()`, and `_update_programs_and_rewards()` to combine domain expressions programmatically. Replaces the Odoo 18 pattern of `+ [(leaf, =, value)]` list concatenation.

**`lazy()`** (`odoo.tools.lazy`): Wraps expensive callables so they are only evaluated when accessed. In `_get_claimable_rewards()`, `_discountable_amount()` is wrapped in `lazy()` because most coupons in the loop will be filtered out before needing the actual discountable value:

```python
discountable = lazy(lambda: self._discountable_amount(global_discount_reward))
total_is_zero = lazy(lambda: self.currency_id.is_zero(discountable))
```

This avoids running `compute_all()` on all order lines for every coupon iteration.

#### 7. `sale.order.coupon.points` SQL Constraint (Odoo 19)

The model uses a SQL-level `UNIQUE` constraint as a `models.Constraint`:

```python
_order_coupon_unique = models.Constraint(
    'UNIQUE (order_id, coupon_id)',
    "The coupon points entry already exists.",
)
```

This replaces any ORM-level deduplication that may have existed in Odoo 18, providing PostgreSQL-enforced uniqueness at the DB level.

#### 8. `loyalty.reward` unlink() Arcive-on-Use Guard (Odoo 19)

In Odoo 19, `loyalty_reward.unlink()` checks for any `sale.order.line` referencing the reward before deletion. If found, it archives the reward instead of deleting it:

```python
def unlink(self):
    if len(self) == 1 and self.env['sale.order.line'].sudo().search_count(
        [('reward_id', 'in', self.ids)], limit=1
    ):
        return self.action_archive()
    return super().unlink()
```

This prevents orphaned `reward_id` foreign key references in confirmed SOs while still allowing unused rewards to be deleted normally.

### Data File: `sale_loyalty_data.xml`

This file strips taxes from gift card and e-wallet products on module install/update:

```xml
<record id="loyalty.gift_card_product_50" model="product.product">
    <field name="taxes_id" eval="False"/>
</record>
<record id="loyalty.ewallet_product_50" model="product.product">
    <field name="taxes_id" eval="False"/>
</record>
```

**Why:** Gift card and e-wallet programs create reward lines that effectively pay for the order. Tax should apply to the product being purchased (the gift card itself), not the discount mechanism. By clearing `taxes_id` on these product templates, the system avoids double-taxing scenarios where a gift card is used to buy a taxed product.

## Security

### SQL Injection Prevention

All database operations use ORM:
```python
# Safe - ORM
rule = self.env['loyalty.rule'].search(domain)
coupon = self.env['loyalty.card'].search([('code', '=', code)])

# Safe - parameterized query (only raw SQL used for lock)
self.env.cr.execute("""
    SELECT id FROM loyalty_program WHERE id=%s FOR UPDATE NOWAIT
""", (program.id,))
```

No string interpolation with user input in SQL.

### Code Validation

Codes are validated before application:
- Checked against `loyalty.rule` and `loyalty.card` tables
- Expiration dates enforced
- Usage limits checked with row-level locking

### Coupon Ownership

Coupon-point associations are validated:
```python
# Remove point entry if coupon doesn't belong to customer
if pe.coupon_id.partner_id and pe.coupon_id.partner_id != self.partner_id:
    pe.points = 0
    point_entries_to_unlink |= pe
```

Prevents customers from using other customers' coupons.

### Access Rights on Reward Lines

Reward lines are made readonly in views:
```xml
<field name="product_uom_qty" readonly="is_reward_line"/>
<field name="price_unit" readonly="is_reward_line"/>
<field name="tax_ids" readonly="is_reward_line"/>
```

Users cannot manually modify reward line values.

### Portal Edit Restrictions

```python
def _can_be_edited_on_portal(self):
    return super()._can_be_edited_on_portal() and not self.is_reward_line
```

Reward lines cannot be modified via the customer portal.

#### ACL Entries (from `security/ir.model.access.csv`)

| ACL ID | Model | Group | R | W | C | D |
|--------|-------|-------|---|---|---|---|
| `access_program_salesman` | `loyalty.program` | Salesperson | Y | — | — | — |
| `access_program_manager` | `loyalty.program` | Manager | Y | Y | Y | Y |
| `access_applicability_salesman` | `loyalty.rule` | Salesperson | Y | — | — | — |
| `access_applicability_manager` | `loyalty.rule` | Manager | Y | Y | Y | Y |
| `access_coupon_salesman` | `loyalty.card` | Salesperson | Y | Y | — | — |
| `access_coupon_manager` | `loyalty.card` | Manager | Y | Y | Y | — |
| `access_reward_salesman` | `loyalty.reward` | Salesperson | Y | — | — | — |
| `access_reward_manager` | `loyalty.reward` | Manager | Y | Y | Y | Y |
| `access_communication_salesman` | `loyalty.mail` | Salesperson | Y | — | — | — |
| `access_communication_manager` | `loyalty.mail` | Manager | Y | Y | Y | Y |
| `access_sale_coupon_apply_code` | `sale.loyalty.coupon.wizard` | Salesperson | Y | Y | Y | — |
| `access_sale_coupon_apply_code_line` | `sale.loyalty.reward.wizard` | Salesperson | Y | Y | Y | — |
| `access_sale_coupon_generate` | `loyalty.generate.wizard` | Salesperson | Y | Y | Y | — |
| `access_sale_order_coupon_points_manager` | `sale.order.coupon.points` | Manager | Y | Y | Y | Y |
| `access_sale_order_coupon_points_salesman` | `sale.order.coupon.points` | Salesperson | Y | — | — | — |
| `access_loyalty_history_salesman` | `loyalty.history` | Salesperson | Y | Y | Y | — |
| `access_loyalty_card_update_balance_salesman` | `loyalty.card.update.balance` | Salesperson | Y | Y | Y | — |

**Notable:** Salespersons can write on `loyalty.card` (apply/use coupons) and create loyalty history entries, but cannot delete any loyalty record. Managers have full CRUD. The `sale.order.coupon.points` model is hidden from salespersons (read-only) — they interact with it only indirectly through order workflows.

### Program Type Defaults

The `_program_type_default_values()` method in `loyalty.program` defines sensible defaults:

| Type | Points Mode | Default Rule | Default Reward |
|------|-------------|--------------|----------------|
| `coupons` | — (code-based) | None | 10% discount, 1 point |
| `promotion` | `order` | Min $50 | 10% discount, 1 point |
| `gift_card` | `money` (1:1) | Specific product | 1 unit per point, future |
| `loyalty` | `money` | None | 5% at 200 points, both |
| `ewallet` | `money` | None | 1 unit per point, future |
| `promo_code` | — (code-based) | Specific product | 10% on product, current |
| `buy_x_get_y` | `unit` | Min 2 qty | Free product, 2 points |
| `next_order_coupons` | — | Min $100 | 15% on order, future |

### Point Calculation Modes

**`reward_point_mode` on `loyalty.rule`:**

| Mode | Formula | Example |
|------|---------|---------|
| `order` | `points = reward_point_amount` | 10 points per order |
| `money` | `points = reward_point_amount * amount_paid` | 1 point per $1 spent |
| `unit` | `points = reward_point_amount * qty` | 1 point per product unit |

For `money` mode, only products matching the rule's product filter count toward the amount.

**`reward_point_split`:** When enabled on `applies_on='future'` programs, generates separate coupons per matched unit (e.g., buying 3 units of the gift card product creates 3 separate $50 gift cards).

---

## Related Models (Base Loyalty Module)

### `loyalty.program` Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Program name (translated) |
| `program_type` | Selection | coupons, gift_card, loyalty, promotion, ewallet, promo_code, buy_x_get_y, next_order_coupons |
| `applies_on` | Selection | current (immediate), future (next order), both |
| `trigger` | Selection | auto (automatic), with_code (promo code) |
| `rule_ids` | One2many | Earning rules |
| `reward_ids` | One2many | Available rewards |
| `communication_plan_ids` | One2many | Email automation triggers |
| `is_nominative` | Boolean (computed) | True if card is partner-bound (loyalty, ewallet, or applies_on='both') |
| `is_payment_program` | Boolean (computed) | True for gift_card and ewallet |
| `limit_usage` / `max_usage` | Boolean/Integer | Program-wide usage limits |
| `date_from` / `date_to` | Date | Validity period |
| `pricelist_ids` | Many2many | Restrict to specific pricelists |
| `portal_visible` | Boolean | Show points in customer portal |
| `portal_point_name` | Char | Custom label for points (e.g., "$" for gift cards) |

### `loyalty.reward` Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `reward_type` | Selection | `product` (free product), `discount` (price reduction) |
| `required_points` | Float | Points needed to claim this reward |
| `description` | Char | Auto-computed display name (e.g., "10% on your order") |
| `clear_wallet` | Boolean | Claim all points at once instead of partial |
| `point_name` | Char (related) | Display name from program |
| **Discount fields:** | | |
| `discount` | Float | Discount value |
| `discount_mode` | Selection | `percent`, `per_order`, `per_point` |
| `discount_applicability` | Selection | `order`, `cheapest`, `specific` |
| `discount_product_ids` | Many2many | Products for specific applicability |
| `discount_product_category_id` | Many2one | Product category filter |
| `discount_product_tag_id` | Many2one | Product tag filter |
| `discount_product_domain` | Char | Advanced domain filter (JSON string) |
| `discount_max_amount` | Monetary | Maximum discount cap |
| `discount_line_product_id` | Many2one | Product used for discount line |
| `is_global_discount` | Boolean | True if order-level percent/per_order |
| **Product reward fields:** | | |
| `reward_product_id` | Many2one | Free product |
| `reward_product_tag_id` | Many2one | Products available via tag |
| `multi_product` | Boolean | Multiple products selectable |
| `reward_product_ids` | Many2many | All available products |
| `reward_product_qty` | Integer | Quantity to claim |

### `loyalty.rule` Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `product_ids` | Many2many | Specific products |
| `product_category_id` | Many2one | Category filter |
| `product_tag_id` | Many2one | Product tag filter |
| `product_domain` | Char | Advanced domain filter |
| `minimum_qty` | Integer | Minimum product quantity |
| `minimum_amount` | Monetary | Minimum purchase amount |
| `minimum_amount_tax_mode` | Selection | `incl` (tax included), `excl` (tax excluded) |
| `reward_point_amount` | Float | Points to award |
| `reward_point_mode` | Selection | `order`, `money`, `unit` |
| `reward_point_split` | Boolean | Split coupons per unit (future programs) |
| `mode` | Selection | `auto`, `with_code` |
| `code` | Char | Promo code (when mode='with_code') |

### `loyalty.card` Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `program_id` | Many2one | Associated program |
| `partner_id` | Many2one | Card owner (nominative programs) |
| `points` | Float | Current point/currency balance |
| `code` | Char | Unique code (auto-generated UUID-based) |
| `expiration_date` | Date | Card expiration |
| `use_count` | Integer | Number of times used |
| `active` | Boolean | Card active status |
| `order_id` | Many2one (sale_loyalty) | Generating order |

### `loyalty.history` Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `card_id` | Many2one | Associated card |
| `order_id` | Integer | Order ID (polymorphic) |
| `order_model` | Char | Model name for order reference |
| `description` | Char | Description (e.g., "Order SO001") |
| `issued` | Float | Points issued |
| `used` | Float | Points consumed |

---

## Tags

#odoo #odoo19 #modules #sale_loyalty #loyalty #discounts #coupons #rewards #points #sale_order
