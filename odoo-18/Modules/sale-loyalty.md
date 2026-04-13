---
Module: sale_loyalty
Version: Odoo 18
Type: Extension
Tags: #odoo #odoo18 #sale #loyalty #coupon #reward #promotion
Related Modules: [sale_management](sale_management.md), [sale](sale.md), [loyalty](loyalty.md)
---

# sale_loyalty — Loyalty Programs in Sales Orders

> Integrates loyalty programs (loyalty cards, coupons, gift cards, eWallets) into the sale order workflow. Handles point accumulation, reward application, and gift card redemption.

**Module:** `sale_loyalty`
**Depends:** `sale_management`, `loyalty`
**Models Extended:** `sale.order`, `sale.order.line`, `loyalty.card`, `loyalty.reward`, `loyalty.program`, `loyalty.history`
**Models Created:** `sale.order.coupon.points`
**Source Path:** `~/odoo/odoo18/odoo/addons/sale_loyalty/`

---

## Overview

`sale_loyalty` connects loyalty infrastructure (`loyalty.program`, `loyalty.card`, `loyalty.reward`) to sale orders. It handles:
1. **Point accumulation**: Computing loyalty points earned from order lines
2. **Coupon application**: Applying coupons/promocodes to orders
3. **Reward application**: Discount lines or free products from redeemed points
4. **Gift card redemption**: Using gift card balance as payment
5. **eWallet**: Using accumulated loyalty points as store credit

---

## Models

### `sale.order` — EXTENDED

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `applied_coupon_ids` | `Many2many(loyalty.card)` | Coupons manually applied by the user to the order. |
| `code_enabled_rule_ids` | `Many2many(loyalty.rule)` | Promo code rules that have been activated. |
| `coupon_point_ids` | `One2many(sale.order.coupon.points)` | Tracks how many points each coupon earns on this order. |
| `reward_amount` | `Float` | Total discount value from all reward lines. Computed. |
| `loyalty_data` | `Json` | Computed JSON with `point_name`, `issued`, `cost` from loyalty history. |

#### `_compute_reward_total()`

```python
def _compute_reward_total(self):
    for order in self:
        reward_amount = 0
        for line in order.order_line:
            if not line.reward_id:
                continue
            if line.reward_id.reward_type != 'product':
                reward_amount += line.price_subtotal  # discount lines have negative price_unit
            else:
                # Free products: subtract the list_price from reward_amount (it's a "saving")
                reward_amount -= line.product_id.lst_price * line.product_uom_qty
        order.reward_amount = reward_amount
```

`reward_amount` is negative (total value of discounts) for discount rewards. For free product rewards, it's negative because it represents the retail value of free items the customer would have paid for.

#### `_compute_loyalty_data()`

Populates a JSON field for the sales order's loyalty summary. Only runs on confirmed orders with existing loyalty history. Returns:
```json
{
  "point_name": "Points",
  "issued": 150.0,
  "cost": 50.0
}
```

Where `issued` = points earned from the order, `cost` = points consumed by rewards.

---

### `sale.order.line` — EXTENDED

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `is_reward_line` | `Boolean` | `True` if `reward_id` is set. Computed. |
| `reward_id` | `Many2one(loyalty.reward)` | The reward that generated this line. `ondelete='restrict'`. |
| `coupon_id` | `Many2one(loyalty.card)` | The coupon used to claim this reward. `ondelete='restrict'`. |
| `reward_identifier_code` | `Char` | Groups multiple reward lines from the same reward instance. |
| `points_cost` | `Float` | How many points were spent to claim this reward. |

#### `_compute_is_reward_line()`

```python
@api.depends('reward_id')
def _compute_is_reward_line(self):
    for line in self:
        line.is_reward_line = bool(line.reward_id)
```

Used throughout to identify reward lines and exclude them from:
- Pricelist price computation
- Loyalty point accumulation
- Line count for minimum order thresholds

#### `_can_be_invoiced_alone()`

```python
def _can_be_invoiced_alone(self):
    return super()._can_be_invoiced_alone() and not self.is_reward_line
```

Reward lines cannot be invoiced independently. They are included in the invoice only as part of the overall order structure.

#### `_is_not_sellable_line()`

```python
def _is_not_sellable_line(self):
    return self.is_reward_line or super()._is_not_sellable_line()
```

Reward lines have no sellable value in isolation.

#### `_is_discount_line()`

```python
def _is_discount_line(self):
    return super()._is_discount_line() or self.reward_id.reward_type == 'discount'
```

Reward discount lines are treated as discount lines for tax and invoice grouping purposes.

#### `_reset_loyalty()`

```python
def _reset_loyalty(self, complete=False):
    """Reset line to non-reward state. If complete=True, also remove coupon/reward."""
    vals = {'points_cost': 0, 'price_unit': 0}
    if complete:
        vals.update({'coupon_id': False, 'reward_id': False})
    self.write(vals)
    return self
```

Called when a reward is no longer applicable (e.g., points no longer sufficient, program expired). Keeps the line but clears the reward link and zeroes the price. The line can then be deleted or reused.

#### `create()` / `write()` — Loyalty Point Sync

```python
def create(self, vals_list):
    res = super().create(vals_list)
    for line in res:
        if line.coupon_id and line.points_cost and line.state == 'sale':
            line.coupon_id.points -= line.points_cost
            line.order_id._update_loyalty_history(line.coupon_id, line.points_cost)
    return res

def write(self, vals):
    cost_in_vals = 'points_cost' in vals
    if cost_in_vals:
        previous_vals = {line: (line.points_cost, line.coupon_id) for line in self}
    res = super().write(vals)
    if cost_in_vals:
        for line, (previous_cost, previous_coupon) in previous_vals.items():
            if line.state != 'sale':
                continue
            if line.points_cost != previous_cost or line.coupon_id != previous_coupon:
                previous_coupon.points += previous_cost
                line.coupon_id.points -= line.points_cost
    return res
```

**On create:** If the order is already confirmed (`state == 'sale'`), deducts `points_cost` from the coupon immediately.
**On write:** If `points_cost` changes on a confirmed order, restores points to the previous coupon and deducts from the new coupon.

This ensures point balance is always accurate when the order is confirmed.

#### `unlink()` — Cascade Cleanup

```python
def unlink(self):
    reward_coupon_set = {(l.reward_id, l.coupon_id, l.reward_identifier_code) for l in self if l.reward_id}
    related_lines = self.order_id.order_line.filtered(
        lambda l: (l.reward_id, l.coupon_id, l.reward_identifier_code) in reward_coupon_set
    )
    # Remove applied coupons from order
    for line in self:
        if line.coupon_id:
            if line.coupon_id in line.order_id.applied_coupon_ids:
                line.order_id.applied_coupon_ids -= line.coupon_id
            elif line.coupon_id.order_id == line.order_id and ...:
                coupons_to_unlink |= line.coupon_id
    # Restore points to coupon if order confirmed
    for line in related_lines:
        if line.state == 'sale':
            line.coupon_id.points += line.points_cost
    res = super(...).unlink()
    coupons_to_unlink.sudo().unlink()
    return res
```

When a reward line is deleted:
1. Related reward lines (same `reward_identifier_code`) are also deleted.
2. The coupon is removed from `applied_coupon_ids`.
3. If the coupon was generated by this order (for `current` programs), it is deleted.
4. If the order was confirmed, points are restored to the coupon.
5. Code-enabled rules for the program are removed from the order.

#### `_sellable_lines_domain()`

```python
def _sellable_lines_domain(self):
    return super()._sellable_lines_domain() + [('reward_id', '=', False)]
```

Reward lines are excluded from the domain of sellable lines (used for SOL→AAL mapping in timesheet billing).

---

### `sale.order.coupon.points` — NEW MODEL

Tracks how many points each coupon earns on each sale order.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | `Many2one(sale.order)` | Required, `ondelete='cascade'`. |
| `coupon_id` | `Many2one(loyalty.card)` | Required, `ondelete='cascade'`. |
| `points` | `Float` | Points awarded to the coupon by this order. |

**SQL Constraint:** `(order_id, coupon_id)` is unique.

**L4 — How Points Are Tracked:**

```
Order confirmed
    → _add_loyalty_history_lines() creates loyalty.history records
    → coupon_point_ids records are created by _add_points_for_coupon()
    → Coupon's .points field is updated with the change from _get_point_changes()
```

The `sale.order.coupon.points` model is a join table between orders and coupons for the many-to-many relationship, storing the points each coupon earns on each order.

---

### `loyalty.card` — EXTENDED

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | `Many2one(sale.order)` | The order that generated this coupon. `readonly=True`. |

#### Methods

| Method | Description |
|--------|-------------|
| `_get_default_template()` | Falls back to `loyalty.mail_template_loyalty_card` if the base default is not set. |
| `_get_mail_partner()` | Returns `order_id.partner_id` as the recipient if no partner from parent. |
| `_get_mail_author()` | Uses `order_id.user_id.partner_id` or `order_id.company_id.partner_id` as email author. |
| `_get_signature()` | Uses `order_id.user_id.signature` if available. |
| `_compute_use_count()` | Adds `sale.order.line` use count to the base count. |
| `_has_source_order()` | Returns `True` if `order_id` is set (coupon was generated from an order). |

---

### `loyalty.reward` — EXTENDED

#### `_get_discount_product_values()`

Sets discount reward products to have no tax and `invoice_policy = 'order'`:
```python
def _get_discount_product_values(self):
    res = super()._get_discount_product_values()
    for vals in res:
        vals.update({
            'taxes_id': False,
            'supplier_taxes_id': False,
            'invoice_policy': 'order',
        })
    return res
```

Discount products in `sale_loyalty` are tax-exempt and invoiced at order time (not delivery).

#### `unlink()`

```python
def unlink(self):
    if len(self) == 1 and self.env['sale.order.line'].sudo().search_count([('reward_id', 'in', self.ids)], limit=1):
        return self.action_archive()
    return super().unlink()
```

If a reward is used in any SO line, archiving instead of deleting prevents orphaned reward references.

---

### `loyalty.program` — EXTENDED

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `order_count` | `Integer` | Number of unique orders with a reward from this program. |
| `sale_ok` | `Boolean` | `default=True`. Marks the program as usable in sales. |

#### `_compute_order_count()`

```python
def _compute_order_count(self):
    read_group_res = self.env['sale.order.line']._read_group(
        [('reward_id', 'in', self.reward_ids.ids)], ['order_id'], ['reward_id:array_agg'])
    for program in self:
        program_reward_ids = program.reward_ids.ids
        program.order_count = sum(
            any(id_ in reward_ids for id_ in program_reward_ids)
            for __, reward_ids in read_group_res
        )
```

Counts orders where any of the program's rewards appears. An order using two rewards from the same program counts once.

---

### `loyalty.history` — EXTENDED

#### `_get_order_portal_url()`

```python
def _get_order_portal_url(self):
    if self.order_id and self.order_model == 'sale.order':
        return self.env['sale.order'].browse(self.order_id).get_portal_url()
    return super()._get_order_portal_url()
```

Provides portal URL for loyalty history entries tied to sale orders.

---

## Loyalty Point Computation

### `_program_check_compute_points()`

This is the core method that evaluates which loyalty programs apply to the order and computes the points earned.

#### Step 1: Gather Order Data
```python
order_lines = self._get_not_rewarded_order_lines()  # excludes reward lines and combo lines
products = order_lines.product_id
products_qties = {product: total_qty}  # aggregated across lines
```

#### Step 2: Check Each Rule
For each rule in each program:
```python
rule_amount = rule._compute_amount(self.currency_id)
untaxed_amount = sum(lines_per_rule[rule].mapped('price_subtotal'))
tax_amount = sum(lines_per_rule[rule].mapped('price_tax'))

# Check minimum_amount
if rule_amount > (tax_included and untaxed + tax_amount or untaxed):
    continue  # rule not met

# Check minimum_qty
if ordered_rule_products_qty < rule.minimum_qty:
    continue  # rule not met
```

#### Step 3: Compute Points
```python
if rule.reward_point_mode == 'order':
    points += rule.reward_point_amount  # fixed points per order

elif rule.reward_point_mode == 'money':
    # points per monetary unit spent
    points += rule.reward_point_amount * amount_paid

elif rule.reward_point_mode == 'unit':
    points += rule.reward_point_amount * ordered_rule_products_qty
```

### `_get_real_points_for_coupon()`

```python
def _get_real_points_for_coupon(self, coupon, post_confirm=False):
    points = coupon.points  # current balance on coupon
    if self.state not in ('sale', 'done'):
        if coupon.program_id.applies_on != 'future':
            points += self.coupon_point_ids.filtered(lambda p: p.coupon_id == coupon).points  # points this order will give
        points -= sum(self.order_line.filtered(lambda l: l.coupon_id == coupon).mapped('points_cost'))  # points consumed by rewards
    return points
```

**L4 — Point calculation before confirmation:**
- `coupon.points` = existing balance on the coupon
- `coupon_point_ids.points` = points this order will award upon confirmation
- `order_line.points_cost` = points consumed by rewards already applied

**After confirmation:**
- All point changes are committed to `coupon.points` via `_get_point_changes()`.
- `_add_loyalty_history_lines()` records the transaction.

### `_get_point_changes()`

Returns a dict `{coupon: net_point_change}`:
```python
points_per_coupon = defaultdict(lambda: 0)
for coupon_point in self.coupon_point_ids:
    points_per_coupon[coupon_point.coupon_id] += coupon_point.points  # earned
for line in self.order_line:
    if line.reward_id and line.coupon_id:
        points_per_coupon[line.coupon_id] -= line.points_cost  # consumed
return points_per_coupon
```

Used in `action_confirm()` (to apply changes) and `_action_cancel()` (to reverse them).

---

## Reward Application

### `_get_reward_values_discount()`

Computes discount reward line values.

**Three applicability modes:**

| Mode | Method | Description |
|------|--------|-------------|
| `order` | `_discountable_order()` | Discount on the entire order subtotal |
| `cheapest` | `_discountable_cheapest()` | Discount on the cheapest eligible line |
| `specific` | `_discountable_specific()` | Discount on lines matching specific products |

**Three discount modes:**

| Mode | Description | Example |
|------|-------------|---------|
| `percent` | Percentage of discountable amount | `10% off` |
| `per_order` | Fixed amount off | `$5 off` |
| `per_point` | Discount = `points × discount` | `1 point = $0.01 credit` |

**Max discount cap:** The reward's `discount_max_amount` converted to order currency, AND capped at the `discountable` amount.

**Gift card / eWallet special handling:** For `is_payment_program`, the reward line has a negative `price_unit` (deducts from order total). It can also carry taxes (gift card product taxes are preserved).

### `_get_reward_values_product()`

For free product rewards:
```python
claimable_count = floor(points / reward.required_points)  # DOWN rounding
cost = points if reward.clear_wallet else claimable_count * reward.required_points
return [{
    'name': reward.description,
    'product_id': product.id,
    'discount': 100,  # 100% discount
    'product_uom_qty': reward.reward_product_qty * claimable_count,
    'points_cost': cost,
    ...
}]
```

The line is created with `discount = 100%`, so the customer pays 0. `points_cost` is deducted from the coupon.

---

## Applying Programs and Coupons

### `_try_apply_code()`

The entry point when a customer enters a promo code:

```
1. Search loyalty.rule with code == entered_code
2. If found: activate rule in code_enabled_rule_ids, apply program
3. If not found: search loyalty.card with code == entered_code
   - Check expiration, points, program validity
   - Add coupon to applied_coupon_ids
4. If neither found: return error
5. Call _update_programs_and_rewards()
6. Return claimable rewards
```

### `_update_programs_and_rewards()`

The full recalculation cycle. Called whenever the order changes (in an `onchange`).

#### Step 1: Load Nominative Programs
Automatically loads eWallet and loyalty coupons with positive points for the order's partner into `applied_coupon_ids`.

#### Step 2: Update Applied Programs
For each program already applied:
- Recomputes points given
- Updates `coupon_point_ids` entries
- Removes programs no longer applicable
- Creates new coupons for future orders if needed

#### Step 3: Update Reward Lines
- Resets all reward lines to a neutral state (`_reset_loyalty()`)
- Re-evaluates which rewards are still claimable
- Rewrites reward line values

#### Step 4: Apply New Automatic Programs
Applies any automatic (no-code) promotions that now match.

#### Step 5: Cleanup
- Deletes reward lines that are no longer applicable
- Deletes expired/invalid coupons

### `_get_claimable_rewards()`

Returns `{coupon: set_of_claimable_rewards}` for all coupons on the order.

```python
for coupon in all_coupons:
    points = self._get_real_points_for_coupon(coupon)
    for reward in coupon.program_id.reward_ids:
        if points >= reward.required_points:
            result[coupon] |= reward
```

Excludes:
- Rewards already applied (unless from a payment program — gift cards can be topped up)
- Rewards the customer doesn't have enough points for
- Programs whose rules no longer match
- Global discounts where a better one is already applied

---

## Order Confirmation: `action_confirm()`

```python
def action_confirm(self):
    for order in self:
        all_coupons = order.applied_coupon_ids | order.coupon_point_ids.coupon_id | order.order_line.coupon_id
        if any(order._get_real_points_for_coupon(coupon) < 0 for coupon in all_coupons):
            raise ValidationError(_('One or more rewards on the sale order is invalid.'))
        order._update_programs_and_rewards()
        order._add_loyalty_history_lines()

    # Remove unclaimed current-program coupons
    reward_coupons = self.order_line.coupon_id
    self.coupon_point_ids.filtered(
        lambda pe: pe.coupon_id.program_id.applies_on == 'current'
        and pe.coupon_id not in reward_coupons
    ).coupon_id.sudo().unlink()

    # Apply point changes to coupons
    for coupon, change in self.filtered(lambda s: s.state != 'sale')._get_point_changes().items():
        coupon.points += change

    res = super().action_confirm()
    self._send_reward_coupon_mail()
    return res
```

**Validation:** All coupons must have `points >= 0` after accounting for reward costs. Prevents negative point balances at confirmation.

**Point application:** Points are only applied to `coupon.points` for orders that are not yet in `'sale'` state (avoid double-application on `sale.confirm` called twice).

**Coupons generated:** For `applies_on == 'future'` programs, new coupons are created on confirmation and sent via email.

---

## Order Cancellation: `_action_cancel()`

```python
def _action_cancel(self):
    previously_confirmed = self.filtered(lambda s: s.state == 'sale')
    res = super()._action_cancel()

    # Remove loyalty history
    order_history_lines.sudo().unlink()

    # Reverse point changes
    for coupon, changes in previously_confirmed._get_point_changes().items():
        coupon.points -= changes  # reverse: subtract the previously-added points

    # Remove reward lines and unlink temporary coupons
    self.order_line.filtered(lambda l: l.is_reward_line).unlink()
    self.coupon_point_ids.coupon_id.sudo().filtered(
        lambda c: not c.program_id.is_nominative and c.order_id in self and not c.use_count
    ).unlink()
    self.coupon_point_ids.unlink()
    return res
```

---

## L4: Gift Card Redemption in Sale Orders

Gift cards are a `loyalty.program` with `program_type = 'gift_card'` (an `is_payment_program`). Their behavior differs from loyalty discounts:

### Buying a Gift Card
When a gift card product is added to an order:
1. A `loyalty.card` is created for the program
2. The card's `points` field represents the monetary balance (in reward currency)
3. On order confirmation, `coupon.points` is updated with the purchased amount

### Redeeming a Gift Card
When a gift card is applied as a payment method:
1. User enters the gift card code via `_try_apply_code()`
2. The card is added to `applied_coupon_ids`
3. A reward line is created with `price_unit = -amount` (up to the order total)
4. The line's `points_cost` equals the amount redeemed (in points/currency)
5. On confirmation, `coupon.points -= points_cost` (balance reduced)

### Gift Card Tax Handling
Gift card discount lines preserve the gift card product's taxes:
```python
if reward_program.program_type == 'gift_card':
    taxes_to_apply = reward_product.taxes_id._filter_taxes_by_company(self.company_id)
    # ... map taxes, compute tax-inclusive price ...
    reward_line_values.update({
        'price_unit': new_price,  # tax-inclusive
        'tax_id': [Command.set(mapped_taxes.ids)],
    })
```

This means the gift card payment reduces the order total including tax.

---

## L4: Global Discount Reward

A reward can be marked `is_global_discount = True`. The order can only have one global discount applied at a time.

### `_best_global_discount_already_applied()`

When trying to apply a new global discount, compares the discount amounts:
- If both discounts exceed the order total, the smaller discount wins (customer keeps the larger voucher).
- Otherwise, the larger discount wins.

This prevents a customer from applying a $10-off coupon after a 20%-off coupon when the 20% coupon is more valuable.

---

## L4: Points Accumulation from SO Lines

Points are calculated by `_program_check_compute_points()`:

```
Rule mode: 'money'
  points = reward_point_amount × amount_paid_for_eligible_products

Rule mode: 'unit'
  points = reward_point_amount × total_quantity_of_eligible_products

Rule mode: 'order'
  points = reward_point_amount  (fixed per order)
```

**What counts as "eligible" for point computation:**
- Only non-reward, non-discount lines (`_get_not_rewarded_order_lines()`)
- Only lines matching the rule's product domain
- For `money` mode: uses `price_total` (tax-included), so taxes count toward point accumulation
- Reward discount lines from other programs are excluded
- Delivery lines are excluded unless the program specifically includes them
