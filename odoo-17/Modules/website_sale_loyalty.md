---
tags: [odoo, odoo17, module, website_sale_loyalty, loyalty, coupons]
research_depth: medium
---

# Website Sale Loyalty Module — Deep Reference

**Source:** `addons/website_sale_loyalty/models/`

## Overview

`website_sale_loyalty` integrates Odoo's loyalty/coupon engine (`sale_loyalty`) with the e-commerce storefront. It enables promotional codes, automatic rewards, loyalty cards, and coupon sharing — all surfaced within the website cart and checkout flow.

Key responsibilities:
- Replace `sale_ok` with `ecommerce_ok` in loyalty program domains for website orders
- Auto-apply single-reward programs after cart updates
- Handle pending coupon codes stored in session between page loads
- Visually merge multi-tax discount lines into a single cart line
- Expose loyalty cards and programs to the website with share links

## Key Models

### `sale.order` (Extended by website_sale_loyalty)

**File:** `sale_order.py`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `disabled_auto_rewards` | Many2many `loyalty.reward` | Rewards the user manually removed; excluded from auto-apply |

#### Program Domain Override (`_get_program_domain`)

Replaces the `sale_ok=True` leaf with `ecommerce_ok=True` when the order has a `website_id`, so only programs with `ecommerce_ok=True` are shown to online customers:

```python
def _get_program_domain(self):
    res = super()._get_program_domain()
    if self.website_id:
        for idx, leaf in enumerate(res):
            if leaf[0] != 'sale_ok':
                continue
            res[idx] = ('ecommerce_ok', '=', True)
            return expression.AND([res, [('website_id', 'in', (self.website_id.id, False))]])
    return res
```

#### Pending Coupon Handling (`_try_pending_coupon`)

If a coupon code was entered but the cart was not yet ready, it is stored in `request.session['pending_coupon_code']`. On every cart update, `_try_pending_coupon()` is called to retry applying it:

```python
def _try_pending_coupon(self):
    pending_coupon_code = request.session.get('pending_coupon_code')
    if pending_coupon_code:
        status = self._try_apply_code(pending_coupon_code)
        if 'error' not in status:
            request.session.pop('pending_coupon_code')
            if len(status) == 1:
                coupon, rewards = next(iter(status.items()))
                if len(rewards) == 1 and not rewards.multi_product:
                    self._apply_program_reward(rewards, coupon)
        return status
    return True
```

#### Auto-apply Rewards (`_auto_apply_rewards`)

After every cart update, attempts to automatically claim rewards. A reward is auto-applied only if:
- The program has exactly 1 reward
- The program is not nominative
- The reward is not a multi-product reward
- The reward is not in `disabled_auto_rewards`
- The reward is not already applied

```python
def _auto_apply_rewards(self):
    claimed_reward_count = 0
    claimable_rewards = self._get_claimable_rewards()
    for coupon, rewards in claimable_rewards.items():
        if (
            len(coupon.program_id.reward_ids) != 1
            or coupon.program_id.is_nominative
            or (rewards.reward_type == 'product' and rewards.multi_product)
            or rewards in self.disabled_auto_rewards
            or rewards in self.order_line.reward_id
        ):
            continue
        try:
            res = self._apply_program_reward(rewards, coupon)
            if 'error' not in res:
                claimed_reward_count += 1
        except UserError:
            pass
    return bool(claimed_reward_count)
```

#### Cart Line Merging (`_compute_website_order_line`)

When a discount program applies to products with different tax rates, `sale_loyalty` generates one discount line per tax. `website_sale_loyalty` merges these visually into a single line for the cart display (since the website cart does not show per-line taxes):

```
Line 1: 10% off Product A (tax A) - $15
Line 2: 10% off Product B (tax B) - $11.50
Line 3: 10% off Product C (tax C) - $10
→ Merged in cart to: 10% discount - $36.50 (no tax)
```

The merged line is a `new()` transient record — it exists only for rendering; it does not persist to the database.

#### `_update_programs_and_rewards` Override

Calls `_try_pending_coupon()` before the parent method, ensuring promo codes entered earlier are retried after every cart change.

#### `_cart_update` Override

Handles the case where a discount reward line is being removed (set to qty 0). Uses `line_id` forcing unlink instead of quantity update:

```python
def _cart_update(self, product_id, line_id=None, ...):
    line = self.order_line.filtered(lambda sol: sol.product_id.id == product_id)[:1]
    reward_id = line.reward_id
    if set_qty == 0 and line.coupon_id and reward_id and reward_id.reward_type == 'discount':
        line_id = line.id  # Force unlink of the reward line
    res = super()._cart_update(...)
    self._update_programs_and_rewards()
    self._auto_apply_rewards()
    return res
```

#### Abandoned Coupon Cleanup (`_gc_abandoned_coupons`)

Garbage-collects coupons applied to abandoned carts older than `website_sale_coupon.abandoned_coupon_validity` (default: 4 days). Resets `applied_coupon_ids` and recomputes rewards.

#### `_get_claimable_and_showable_rewards`

Returns rewards the customer can see and claim on the website, including:
- Rewards from loyalty cards linked to the partner
- Future-program rewards (automatic programs where the partner has a card)
- Only rewards with sufficient points, non-expired coupons, and excluding already-applied rewards

### `sale.order.line` (Extended by website_sale_loyalty)

**File:** `sale_order_line.py`

#### `_show_in_cart()` Override

Discount reward lines are excluded from `website_order_line` because they are handled by the merged rendering in `sale_order._compute_website_order_line`:

```python
def _show_in_cart(self):
    return self.reward_id.reward_type != 'discount' and super()._show_in_cart()
```

#### `unlink()` Override

When a reward line is deleted from the cart UI, the reward is added to `order.disabled_auto_rewards` to prevent auto-reapplying it:

```python
def unlink(self):
    if self.env.context.get('website_sale_loyalty_delete', False):
        for line in self:
            if line.reward_id:
                order.disabled_auto_rewards += line.reward_id
    return super().unlink()
```

### `loyalty.program` (Extended by website_sale_loyalty)

**File:** `loyalty_program.py`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `ecommerce_ok` | Boolean | If True, program is available on the e-commerce website |

Inherits from `website.multi.mixin`, so `website_id` on the program restricts it to a specific website.

#### `action_program_share`

Creates a coupon share link via `coupon.share`, allowing the promotion to be shared externally.

### `loyalty.rule` (Extended by website_sale_loyalty)

**File:** `loyalty_rule.py`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `website_id` | Many2one (related to `program_id.website_id`) | Restricts rule to a website |

#### Unique Code Constraint (`_constrains_code`)

Prevents duplicate promo codes across programs that are both accessible from the same website:

```python
@api.constrains('code', 'website_id')
def _constrains_code(self):
    with_code = self.filtered(lambda r: r.mode == 'with_code')
    # Search existing rules with same code, same website
    # Raise ValidationError if duplicate found
    # Also prevent loyalty.card codes from sharing a promo code
```

### `loyalty.card` (Extended by website_sale_loyalty)

**File:** `loyalty_card.py`

#### `action_coupon_share`

Creates a `coupon.share` record and returns the share action, allowing customers to share their loyalty card/coupon code.

## Coupon Flow on the Website

```
1. Customer enters promo code at checkout
   → WebsiteSale.pricelist() controller
   → sale_order._cart_update_pricelist(pricelist_id=...)
   → If code is not yet recognized (no coupon record): stored in session as 'pending_coupon_code'

2. Every cart update triggers:
   → _cart_update() → _update_programs_and_rewards()
   → _try_pending_coupon() → attempts to apply the code
   → If success: removes from session, optionally auto-applies reward
   → If failure: keeps in session, error shown to user

3. Coupon applied:
   → sale_loyalty creates coupon record (if needed) and discount line
   → website_sale_loyalty merges multi-tax discount lines in cart display
```

## See Also

- [Modules/sale_loyalty](Modules/sale_loyalty.md) — base loyalty and coupon engine
- [Modules/website_sale](Modules/website_sale.md) — e-commerce cart and checkout
- [Modules/loyalty](Modules/loyalty.md) — loyalty program and reward definitions
