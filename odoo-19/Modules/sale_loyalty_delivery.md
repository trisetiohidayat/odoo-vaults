---
title: Sale Loyalty Delivery
description: Bridge module adding free shipping rewards to the sale loyalty program. Allows loyalty programs to reward customers with free delivery or free delivery up to a maximum cost.
tags: [odoo19, sales, loyalty, delivery, module, reward]
model_count: 1
models:
  - sale.order
dependencies:
  - sale_loyalty
  - delivery
category: Sales/Sales
source: odoo/addons/sale_loyalty_delivery/
created: 2026-04-14
uuid: d4e5f6a7-b8c9-0123-def0-234567890123
---

# Sale Loyalty Delivery

## Overview

**Module:** `sale_loyalty_delivery`
**Category:** Sales/Sales
**Depends:** `sale_loyalty`, `delivery`
**Auto-install:** True
**License:** LGPL-3
**Author:** Odoo S.A.
**Module directory:** `odoo/addons/sale_loyalty_delivery/`

`sale_loyalty_delivery` is a loyalty reward extension that adds "Free Shipping" as a new reward type within Odoo's loyalty program framework (`sale_loyalty`). Loyalty programs can now reward customers with free delivery -- either completely free shipping or free shipping capped at a maximum discount amount.

This module bridges two independent systems: the loyalty program engine (`sale_loyalty`) and the delivery carrier pricing system (`delivery`). Without this module, loyalty programs could reward customers with discounts on products, e-wallets, and gift cards, but not with delivery cost reductions.

## Module Structure

```
sale_loyalty_delivery/
├── __init__.py
├── __manifest__.py
├── models/
│   └── sale_order.py     # Extends sale.order with shipping reward logic
└── views/
    └── loyalty_reward_views.xml  # Injects shipping-specific fields into reward form
```

The module has no independent models -- it only extends `sale.order` with overrides and adds view modifications to the loyalty reward form.

## Dependency Chain

```
sale_loyalty_delivery
├── sale_loyalty          # Loyalty program engine
│   ├── sale              # Sales order management
│   │   ├── product       # Product pricing
│   │   └── account       # Account move (invoicing)
│   └── loyalty           # Loyalty program definition (loyalty.program, loyalty.reward, loyalty.card)
└── delivery              # Delivery carriers and pricing
    ├── sale              # (shared dependency)
    └── stock             # Stock moves (for delivery orders)
```

**Why both `sale_loyalty` and `delivery`?**

| System | Responsibility |
|--------|---------------|
| `sale_loyalty` | Manages loyalty programs, rewards, coupons, and points. Defines the `loyalty.reward` model with its `reward_type` field. |
| `delivery` | Manages delivery carriers, shipping methods, and pricing rules. Creates `delivery.carrier` records and `sale.order.line` delivery lines. |

This module connects them: it teaches `sale.order` how to create a loyalty reward line that cancels out the delivery line cost.

## The Loyalty Reward System (from sale_loyalty)

To understand this module, it helps to know how `sale_loyalty` structures rewards.

### The `loyalty.reward` Model

Loyalty rewards are defined in `loyalty.reward`. Each reward has a `reward_type`:

| reward_type | Effect |
|-------------|--------|
| `discount` | Applies a percentage or fixed discount to order lines or the total |
| `product` | Gives a free or discounted product |
| `shipping` | Waives delivery costs (new in this module) |
| `loyalty` | Converts points into a coupon (e-wallet) |
| `gift_card` | Creates a gift card code |

The `sale_loyalty_delivery` module adds `shipping` to this enumeration by extending `sale.order` methods.

### How Loyalty Rewards Are Applied

The `sale_loyalty` module applies rewards via `_get_reward_line_values()` on `sale.order`:

```
1. User claims a reward (via loyalty.card points)
      ↓
2. sale_loyalty calls _get_reward_line_values(reward, coupon)
      ↓
3. reward.reward_type determines which sub-method is called
      → discount: _get_reward_values_discount()
      → product: _get_reward_values_product()
      → shipping: _get_reward_values_free_shipping()  ← New from sale_loyalty_delivery
      → loyalty: _get_reward_values_loyalty()
      → gift_card: _get_reward_values_gift_card()
      ↓
4. A sale.order.line is created as an "is_reward_line" with negative price_unit
      ↓
5. Order total is recalculated
```

## Models

### `sale.order` (extends `sale.order`)

**File:** `models/sale_order.py`

The `sale.order` model is the central piece. This module overrides five methods to integrate shipping rewards with the loyalty system.

#### `_compute_amount_total_without_delivery()`

```python
def _compute_amount_total_without_delivery(self):
    res = super()._compute_amount_total_without_delivery()
    return res - sum(
        self.order_line.filtered(
            lambda l: l.coupon_id and l.coupon_id.program_type in ['ewallet', 'gift_card']
        ).mapped('price_unit')
    )
```

**Purpose:** Adjusts the order total used for threshold calculations (e.g., "spend $100 to get free shipping").

**Context:** The `sale_loyalty` module computes a "total without delivery" to determine whether a customer has reached a spending threshold for earning or claiming rewards. The base implementation excludes delivery lines from this total. This override further excludes e-wallet and gift card line amounts, because those are virtual payment instruments, not actual spending.

**Why exclude e-wallets and gift cards?**
If a customer pays with a $50 e-wallet balance, that $50 should not count toward "spend $X to get free shipping" because the merchant is not receiving $50 in revenue -- it is redeeming loyalty points. Without this exclusion, customers could game the threshold by loading e-wallets.

#### `_get_no_effect_on_threshold_lines()`

```python
def _get_no_effect_on_threshold_lines(self):
    res = super()._get_no_effect_on_threshold_lines()
    return res + self.order_line.filtered(
        lambda line: line.is_delivery or line.reward_id.reward_type == 'shipping')
```

**Purpose:** Excludes shipping reward lines from spending threshold calculations.

**Context:** In loyalty programs with tiered rewards ("spend $50 for 5% off, spend $100 for free shipping"), the system needs to know which lines count toward the threshold. The base `sale_loyalty` excludes delivery lines and discount lines. This override additionally excludes lines where `reward_id.reward_type == 'shipping'`, because a free shipping reward should not contribute to the threshold that triggered it (preventing circular logic).

#### `_get_not_rewarded_order_lines()`

```python
def _get_not_rewarded_order_lines(self):
    """Exclude delivery lines from consideration for reward points."""
    order_line = super()._get_not_rewarded_order_lines()
    return order_line.filtered(lambda line: not line.is_delivery)
```

**Purpose:** Excludes delivery lines when calculating loyalty points earned.

**Context:** When a loyalty program awards points based on order value ("1 point per $1 spent"), delivery costs should not generate additional loyalty points. This method filters out any line marked `is_delivery=True`, ensuring customers only earn points on the product value, not the shipping markup.

**Note:** This is slightly different from the `_get_no_effect_on_threshold_lines` override -- that one excludes from threshold checks, while this excludes from point accrual. A line could affect thresholds but not earn points, depending on program configuration.

#### `_get_reward_values_free_shipping()`

```python
def _get_reward_values_free_shipping(self, reward, coupon, **kwargs):
    delivery_line = self.order_line.filtered(lambda l: l.is_delivery)[:1]
    taxes = delivery_line.product_id.taxes_id._filter_taxes_by_company(self.company_id)
    taxes = self.fiscal_position_id.map_tax(taxes)
    max_discount = reward.discount_max_amount or float('inf')
    return [{
        'name': _('Free Shipping - %s', reward.description),
        'reward_id': reward.id,
        'coupon_id': coupon.id,
        'points_cost': reward.required_points if not reward.clear_wallet else self._get_real_points_for_coupon(coupon),
        'product_id': reward.discount_line_product_id.id,
        'price_unit': -min(max_discount, delivery_line.price_unit or 0),
        'product_uom_qty': 1,
        'order_id': self.id,
        'is_reward_line': True,
        'sequence': max(self.order_line.filtered(lambda x: not x.is_reward_line).mapped('sequence'), default=0) + 1,
        'tax_ids': [Command.clear()] + [Command.link(tax.id) for tax in taxes],
    }]
```

**Purpose:** Creates the actual reward order line when a free shipping reward is claimed.

**Step-by-step breakdown:**

1. **Find the delivery line:** `self.order_line.filtered(lambda l: l.is_delivery)[:1]` finds the delivery line on the order (created by the `delivery` module when a shipping method is selected). If no delivery line exists, `delivery_line` is an empty recordset and `delivery_line.price_unit` is 0.

2. **Compute taxes:** The taxes on the delivery product are computed and mapped through the fiscal position (for B2B/B2G scenarios).

3. **Determine the discount amount:** `max_discount = reward.discount_max_amount or float('inf')` -- if the reward has a `discount_max_amount` (the "up to X" cap), use that; otherwise, the reward covers the full delivery cost.

4. **Create the reward line values:**
   - `name`: "Free Shipping - {reward.description}" -- e.g., "Free Shipping - Loyalty Reward"
   - `price_unit`: Negative of the delivery cost, capped at `max_discount`. A negative price reduces the order total.
   - `is_reward_line`: `True` -- marks this as a loyalty reward line.
   - `sequence`: After the last non-reward line.
   - `tax_ids`: Inherits the same taxes as the delivery line it is negating (except where fiscal position changes them).

#### `_get_reward_line_values()`

```python
def _get_reward_line_values(self, reward, coupon, **kwargs):
    self.ensure_one()
    if reward.reward_type == 'shipping':
        self = self.with_context(lang=self._get_lang())
        reward = reward.with_context(lang=self._get_lang())
        return self._get_reward_values_free_shipping(reward, coupon, **kwargs)
    return super()._get_reward_line_values(reward, coupon, **kwargs)
```

**Purpose:** Routes to the correct sub-method based on `reward_type`. This is the main entry point for reward application.

**The language context:** `self.with_context(lang=self._get_lang())` ensures the reward description is rendered in the customer's language when the order line is created.

#### `_get_claimable_rewards()`

```python
def _get_claimable_rewards(self, forced_coupons=None):
    res = super()._get_claimable_rewards(forced_coupons)
    if any(reward.reward_type == 'shipping' for reward in self.order_line.reward_id):
        # Allow only one reward of type shipping at the same time
        filtered_res = {}
        for coupon, rewards in res.items():
            filtered_rewards = rewards.filtered(lambda r: r.reward_type != 'shipping')
            if filtered_rewards:
                filtered_res[coupon] = filtered_rewards
        res = filtered_res
    return res
```

**Purpose:** Prevents claiming multiple shipping rewards simultaneously.

**Business logic:** Only one free shipping reward can apply to an order. If the customer has already claimed a shipping reward (checked via `self.order_line.reward_id`), the system removes all shipping rewards from the list of claimable rewards. This prevents a customer from stacking two "free shipping" rewards to get double the discount.

**Important:** This filtering happens in `res` (the result from super), meaning it only filters rewards the customer is **eligible to claim**, not rewards already on the order. The already-applied shipping reward line remains; it just cannot be claimed again.

## Views

**File:** `views/loyalty_reward_views.xml`

This file adds UI elements to the loyalty reward form and kanban views.

### Reward Form View Modification

```xml
<record id="loyalty_reward_view_form_inherit_loyalty_delivery" model="ir.ui.view">
    <field name="inherit_id" ref="loyalty.loyalty_reward_view_form"/>
    <field name="arch" type="xml">
        <group name="reward_type_group" position="after">
            <group id="shipping" string="Free shipping" invisible="reward_type != 'shipping'">
                <field name="discount_max_amount"/>
            </group>
        </group>
    </field>
</record>
```

**What it does:** Adds a new field group below the reward type group. The group is only visible when `reward_type == 'shipping'`.

| Field | Description |
|-------|-------------|
| `discount_max_amount` | Maximum discount amount for free shipping. If set, shipping is free only up to this amount. If delivery costs more, the customer pays the difference. |

**Example:** If `discount_max_amount = 20` and delivery costs $35, the customer pays $15 and gets $20 off.

### Reward Kanban View Modification

```xml
<record id="loyalty_reward_view_kanban_inherit_loyalty_delivery" model="ir.ui.view">
    <field name="inherit_id" ref="loyalty.loyalty_reward_view_kanban"/>
    <field name="arch" type="xml">
        <div name="reward_info" position="inside">
            <t t-elif="record.reward_type.raw_value === 'shipping'">
                Free shipping <t t-if="record.discount_max_amount.raw_value > 0">( Max <field name="discount_max_amount"/> )</t>
            </t>
        </div>
    </field>
</record>
```

**What it does:** In the kanban view of loyalty rewards, displays "Free shipping" for shipping-type rewards, with the maximum amount shown in parentheses if set.

## How the Complete Flow Works

```
1. Customer shops on e-commerce website
      ↓
2. Adds products to cart (sale.order created)
      ↓
3. Selects delivery method (delivery.carrier selected)
      → delivery module creates sale.order.line with is_delivery=True
      → Delivery cost added to order total
      ↓
4. Loyalty points accumulated (per sale_loyalty rules)
      ↓
5. Customer has enough points to claim "Free Shipping" reward
      → Customer clicks "Claim" on the reward
      ↓
6. _get_reward_line_values() called with reward_type='shipping'
      → Routes to _get_reward_values_free_shipping()
      → Creates negative price_unit order line:
         price_unit = -min(discount_max_amount, delivery_line.price_unit)
      ↓
7. Order total recalculated:
      → Products: +$100
      → Delivery: +$25
      → Shipping Reward: -$25 (or -$20 if max $20)
      → Final Total: $100 (or $105 if capped)
      ↓
8. Customer completes checkout
      → Payment processed for adjusted total
      → Delivery confirmed with carrier
```

## The `discount_max_amount` Feature

The `discount_max_amount` field enables a powerful business scenario: "free shipping up to a limit."

| Scenario | discount_max_amount | Delivery Cost | Customer Pays Delivery |
|----------|--------------------:|---------------:|------------------------:|
| Full free shipping | Not set (null) | $25 | $0 |
| Capped at $20 | 20 | $25 | $15 |
| Capped at $50 | 50 | $35 | $0 |
| Capped at $10 | 10 | $25 | $15 |

This is useful when:
- The merchant wants to subsidize standard shipping but not express delivery.
- Carrier rates vary by zone and the merchant wants to cover urban areas fully but not remote zones.
- The merchant sets a cap to manage the cost of the loyalty program.

## Extension Points

| Extension | How |
|-----------|-----|
| Add minimum order value for shipping rewards | Add a check in `_get_reward_values_free_shipping()` |
| Exclude specific carriers from free shipping rewards | Filter delivery_line by carrier in `_get_reward_values_free_shipping()` |
| Stack multiple shipping discounts | Override `_get_claimable_rewards()` to allow multiple `shipping` rewards |
| Add shipping reward to welcome emails | Extend the loyalty program template in `sale_loyalty` |
| Track shipping reward cost as a marketing expense | Add analytics fields to the reward line in `_get_reward_values_free_shipping()` |

## Relationship to sale_loyalty Methods

Here is how the method overrides fit into the full `sale_loyalty` method call chain:

```
sale_loyalty workflow methods on sale.order:

_get_no_effect_on_threshold_lines()
  ├─ sale_loyalty base implementation
  └─ sale_loyalty_delivery extension: adds is_delivery and shipping reward lines

_get_not_rewarded_order_lines()
  ├─ sale_loyalty base implementation
  └─ sale_loyalty_delivery extension: excludes is_delivery lines

_compute_amount_total_without_delivery()
  ├─ sale_loyalty base implementation
  └─ sale_loyalty_delivery extension: subtracts e-wallet/gift-card lines

_get_reward_line_values(reward, coupon)
  ├─ sale_loyalty base: routes to discount/product/loyalty/gift_card handlers
  └─ sale_loyalty_delivery extension: routes to _get_reward_values_free_shipping()

_get_reward_values_free_shipping(reward, coupon)  ← New method
  └─ sale_loyalty_delivery: creates the negative delivery line

_get_claimable_rewards(forced_coupons)
  ├─ sale_loyalty base: returns all eligible rewards
  └─ sale_loyalty_delivery extension: removes shipping rewards if one is already claimed
```

## Related

- [Modules/sale_loyalty](sale_loyalty.md) -- Loyalty programs: rewards, coupons, points, e-wallets, gift cards
- [Modules/delivery](delivery.md) -- Delivery carriers: shipping methods, pricing, rules
- [Modules/loyalty](loyalty.md) -- Loyalty program definition: programs, rewards, cards, rules
- [Modules/sale](sale.md) -- Sales order management
- [Modules/website_sale_loyalty](website_sale_loyalty.md) -- E-commerce loyalty: loyalty points display on shop
