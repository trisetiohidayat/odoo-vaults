---
title: website_sale_loyalty
tags:
  - "#odoo19"
  - "#modules"
  - "#loyalty"
  - "#ecommerce"
  - "#website"
description: Coupons, Promotions, Gift Cards and Loyalty Programs for eCommerce — bridges sale_loyalty core loyalty engine with the website_sale checkout flow.
updated: 2026-04-11
---

# website_sale_loyalty

**Module Key:** `website_sale_loyalty`
**Depends:** `website_sale`, `website_links`, `sale_loyalty`
**Category:** Website/Website
**Auto-install:** `website_sale`, `sale_loyalty`
**License:** LGPL-3
**Author:** Odoo S.A.

Bridges the [Modules/loyalty](Modules/loyalty.md) core engine with the eCommerce storefront. Handles coupon/promo code entry on the cart page, automatic reward application, loyalty points display, e-wallet top-up, gift card redemption, and the "Share" coupon link wizard for marketing.

---

## Architecture Overview

```
sale_loyalty (core engine)
    ├── loyalty.program    — program definitions
    ├── loyalty.rule       — rule conditions (coupon code, min amount, etc.)
    ├── loyalty.reward     — reward definitions (discount, free product, free shipping)
    ├── loyalty.card       — individual coupon/gift card/loyalty card records
    └── sale.order         — applies programs to SO lines

website_sale_loyalty (frontend bridge)
    ├── sale.order         — ecommerce-specific overrides (_get_program_domain, auto-apply)
    ├── sale.order.line    — reward line display filtering
    ├── loyalty.program    — adds ecommerce_ok flag + website multi-mixin
    ├── loyalty.rule       — website-scoped code uniqueness constraint
    ├── loyalty.card       — share action button
    ├── product.product    — unpublished reward image access for public users
    └── coupon.share       — wizard for generating shareable coupon links
```

---

## Dependency Chain

```
website_sale_loyalty
├── website_sale          (website checkout, cart controller, cart page rendering)
├── website_links         (link tracker for short URLs in coupon share)
└── sale_loyalty
    ├── loyalty            (core models: program, rule, reward, card, history)
    └── sale              (sale.order, sale.order.line)
```

---

## Models

### `sale.order` — Extended

**Inherited from:** `sale.order` (via `sale_loyalty` extension)
**File:** `models/sale_order.py`

#### Fields Added by `website_sale_loyalty`

| Field | Type | Description |
|---|---|---|
| `disabled_auto_rewards` | `Many2many(loyalty.reward)` | Reward records the auto-claim logic should skip for this order. Populated when a customer manually removes a discount reward line from the cart. |

#### `_get_program_domain()` — Program Eligibility Filter

```python
def _get_program_domain(self):
    res = super()._get_program_domain()
    if self.website_id:
        for idx, leaf in enumerate(res):
            if leaf[0] != 'sale_ok':
                continue
            res[idx] = ('ecommerce_ok', '=', True)
            return Domain.AND([res, [('website_id', 'in', (self.website_id.id, False))]])
    return res
```

**L3 — Cross-model logic:**
Replaces the `sale_ok` leaf (which controls [Modules/Sale](Modules/sale.md) app eligibility) with `ecommerce_ok` when the order has a `website_id`. Also gates on `website_id` being either the current website or unset (False), meaning programs not assigned to any specific website are available on all.

**L3 — Domain leaf transformation:**
- `sale_ok=True` (B2B/backend) becomes `ecommerce_ok=True` (B2C/website)
- Adds `website_id in (current_id, False)` to scope programs to the current website

#### `_get_trigger_domain()` — Trigger Program Filter

```python
def _get_trigger_domain(self):
    res = super()._get_trigger_domain()
    if self.website_id:
        for idx, leaf in enumerate(res):
            if leaf[0] != 'program_id.sale_ok':
                continue
            res[idx] = ('program_id.ecommerce_ok', '=', True)
            return Domain.AND([res, [('program_id.website_id', 'in', (self.website_id.id, False))]])
    return res
```

Same transformation as `_get_program_domain()` but for the trigger domain used when evaluating which programs' rules match the order.

#### `_get_program_timezone()` — Per-Website Timezone

```python
def _get_program_timezone(self):
    return self.website_id.salesperson_id.tz or super()._get_program_timezone()
```

Returns the website's assigned salesperson's timezone for program date validity checks, falling back to the base method.

#### `_try_pending_coupon()` — Session-Stored Coupon

```python
def _try_pending_coupon(self):
    if not request:
        return False
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

**L3 — Flow:**
1. Reads `pending_coupon_code` from the HTTP session (set by `/coupon/<code>` route)
2. Calls `_try_apply_code()` to validate and get the matching rewards
3. If exactly one reward and it is not a multi-product selector, auto-applies it immediately
4. Returns the status dict; upstream callers check for `'error'` key

**L4 — Performance:** Session read is O(1); `_try_apply_code` hits the DB but is necessary. Called on every cart page render.

#### `_update_programs_and_rewards()` — Hook for Pending Coupon

```python
def _update_programs_and_rewards(self):
    for order in self:
        order._try_pending_coupon()
    return super()._update_programs_and_rewards()
```

**L3 — Why it exists:** Ensures that a coupon code stored in session (via the `/coupon/<code>` shareable link) is processed before the base `_update_programs_and_rewards` recalculates all program rewards. This makes sharing a coupon link work: clicking a link sets the session, then navigating to the cart picks it up.

#### `_auto_apply_rewards()` — Automatic Single-Reward Claim

```python
def _auto_apply_rewards(self):
    self.ensure_one()
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

**L3 — Conditions for auto-apply (all must be true):**
1. Program has exactly **one reward** defined
2. Program is **not nominative** (not a per-customer loyalty card)
3. Reward is **not a multi-product selector**
4. Reward is **not in `disabled_auto_rewards`** (customer previously removed it)
5. Reward is **not already on the order**

**L3 — Failure handling:** Wrapped in `try/except UserError` — silently skips if the reward cannot be applied (e.g., points become insufficient after recalculation).

**L4 — Edge case:** The `disabled_auto_rewards` mechanism prevents a reward from being auto-applied immediately after the customer manually deleted it. This is set in `sale_order_line.unlink()` when deletion is triggered by the loyalty module context flag.

#### `_compute_website_order_line()` — Visual Discount Merging

```python
def _compute_website_order_line(self):
    super()._compute_website_order_line()
    for order in self:
        grouped_order_lines = defaultdict(lambda: self.env['sale.order.line'])
        for line in order.order_line:
            if line.reward_id and line.coupon_id:
                grouped_order_lines[(line.reward_id, line.coupon_id, line.reward_identifier_code)] |= line
        new_lines = self.env['sale.order.line'].new({...})
        if new_lines:
            order.website_order_line += new_lines
```

**L3 — Problem solved:** When a discount reward applies to multiple products with different taxes, Odoo creates one discount `sale.order.line` per tax group. On the website, customers should only see a single merged discount line. This method groups those multiple lines into a single phantom `new()` record and appends it to `website_order_line` for display.

**L4 — Tax edge case:** Lines are merged **only for display**. The actual tax calculation lines remain untouched. The merged line uses `tax_ids=False` and sums the `price_subtotal` of all grouped lines. This is safe only because the website cart does not display taxes per line.

**Fields on merged line:** `product_id`, `tax_ids=False`, `price_unit`=sum, `price_subtotal`=sum, `price_total`=sum, `discount=0`, `product_uom_qty=1`, `is_reward_line=True`, `coupon_id`, `reward_id`.

#### `_compute_cart_info()` — Cart Quantity Correction

```python
def _compute_cart_info(self):
    super(SaleOrder, self)._compute_cart_info()
    for order in self:
        reward_lines = order.website_order_line.filtered(lambda line: line.is_reward_line)
        order.cart_quantity -= int(sum(reward_lines.mapped('product_uom_qty')))
```

Subtracts reward line quantities from `cart_quantity`. Without this, free-product reward lines (e.g., "get a free mug") would inflate the cart item count shown in the header.

#### `_verify_cart_after_update()` — Cart Recompute Trigger

```python
def _verify_cart_after_update(self):
    super()._verify_cart_after_update()
    self._update_programs_and_rewards()
    self._auto_apply_rewards()
    if request:
        request.session['website_sale_cart_quantity'] = self.cart_quantity
```

Called after any cart update (add, remove, change quantity). Re-runs program evaluation and auto-claim, then syncs the cart quantity to the session for the header badge.

#### `_get_claimable_and_showable_rewards()` — Rewards Panel Data

```python
def _get_claimable_and_showable_rewards(self):
    self.ensure_one()
    res = self._get_claimable_rewards()
    loyalty_cards = self.env['loyalty.card'].search([
        ('partner_id', '=', self.partner_id.id),
        ('program_id', 'any', self._get_program_domain()),
        '|',
            ('program_id.trigger', '=', 'with_code'),
            '&', ('program_id.trigger', '=', 'auto'), ('program_id.applies_on', '=', 'future'),
    ])
    total_is_zero = self.currency_id.is_zero(self.amount_total)
    global_discount_reward = self._get_applied_global_discount()
    for coupon in loyalty_cards:
        points = self._get_real_points_for_coupon(coupon)
        for reward in coupon.program_id.reward_ids - self.order_line.reward_id:
            # Skip if global discount already applied, zero total, expired, insufficient points
            ...
            if points >= reward.required_points:
                if coupon in res:
                    res[coupon] |= reward
                else:
                    res[coupon] = reward
    return res
```

**L3 — What it returns:** A dict `{loyalty_card: loyalty_reward}` of rewards the current partner can **see and claim** on the "My Rewards" panel of the cart page.

**L3 — Search filters:**
- `partner_id` matches the current customer
- `program_id` matches the eCommerce program domain
- Program is either `with_code` trigger OR `auto` with `applies_on='future'`

**L3 — Per-reward exclusion conditions:**
- Global discount already applied and this reward is not better
- `amount_total` is zero (no discount rewards on free orders)
- Card is expired (`expiration_date < today`)
- Insufficient points for the reward

**L4 — `is_global_discount` comparison:** Uses `_best_global_discount_already_applied()` to prevent showing a loyalty discount reward when a better promo-code discount is already active.

#### `_allow_nominative_programs()` — Loyalty Card Eligibility

```python
def _allow_nominative_programs(self):
    if not request or not hasattr(request, 'website'):
        return super()._allow_nominative_programs()
    return not request.website.is_public_user() and super()._allow_nominative_programs()
```

Nominative (per-customer) loyalty programs are only accessible to **logged-in customers**. Public/guest users cannot use loyalty card points on the website.

#### `_gc_abandoned_coupons()` — Abandoned Coupon Cleanup

```python
@api.autovacuum
def _gc_abandoned_coupons(self, *args, **kwargs):
    ICP = self.env['ir.config_parameter']
    validity = ICP.get_param('website_sale_coupon.abandonned_coupon_validity', 4)
    validity = fields.Datetime.to_string(fields.Datetime.now() - timedelta(days=int(validity)))
    so_to_reset = self.env['sale.order'].search([
        ('state', '=', 'draft'),
        ('write_date', '<', validity),
        ('website_id', '!=', False),
        ('applied_coupon_ids', '!=', False),
    ])
    so_to_reset.applied_coupon_ids = False
    for so in so_to_reset:
        so._update_programs_and_rewards()
```

**L3 — Cleanup trigger:** Runs via `autovacuum` (Odoo's scheduled cleanup hook). Finds draft website orders older than the configured validity (default: 4 days) that have `applied_coupon_ids`. Resets those coupons and re-evaluates the order.

**L4 — Performance:** Only targets `state='draft'` orders. Does not affect confirmed/sent orders. The `write_date` check means in-progress orders are not affected.

#### `_recompute_cart()` — Full Cart Recompute

```python
def _recompute_cart(self):
    self._update_programs_and_rewards()
    self._auto_apply_rewards()
    super()._recompute_cart()
```

Calls loyalty recalculation **before** the base cart recompute. Used by the `cart()` controller to refresh the full cart state including applied rewards.

#### `_cart_find_product_line()` — Exclude Reward Lines from Cart Add

```python
def _cart_find_product_line(self, *args, **kwargs):
    return super()._cart_find_product_line(*args, **kwargs).filtered(
        lambda sol: not sol.is_reward_line
    )
```

Prevents the standard cart add logic from matching reward discount lines when a customer tries to add a product that is also on a reward line. Reward lines are managed exclusively by `_update_programs_and_rewards`.

#### `_get_non_delivery_lines()` — Exclude Free Shipping Reward Lines

```python
def _get_non_delivery_lines(self):
    return super()._get_non_delivery_lines() - self._get_free_shipping_lines()
```

Removes free-shipping reward lines from the "non-delivery lines" set, ensuring shipping discounts are not double-counted in delivery-related calculations.

---

### `sale.order.line` — Extended

**Inherited from:** `sale.order.line`
**File:** `models/sale_order_line.py`

#### `_get_line_header()` — Reward Line Display Name

```python
def _get_line_header(self):
    if self.is_reward_line:
        return self.name
    return super()._get_line_header()
```

Returns `self.name` for reward lines (which already contains the formatted reward description like "10% Discount") rather than the standard product-based name construction.

#### `_show_in_cart()` — Hide Discount Lines from Website Cart

```python
def _show_in_cart(self):
    return self.reward_id.reward_type != 'discount' and super()._show_in_cart()
```

Discount-type reward lines are excluded from `website_order_line` because they are rendered via the separate "Loyalty, coupon, gift card" panel in the cart total section. Product and shipping rewards still show.

**L4 — Why this matters:** If discount lines appeared in the cart product list, customers would see duplicate entries: one for the merged display line and one for the actual `sale.order.line` records.

#### `_is_reorder_allowed()` — Block Reorder of Reward Lines

```python
def _is_reorder_allowed(self):
    return not self.reward_id and super()._is_reorder_allowed()
```

Any line with a `reward_id` (free product, discount, free shipping) cannot be reordered via the "Reorder" button in the customer portal.

#### `unlink()` — Track Disabled Auto-Rewards on Deletion

```python
def unlink(self):
    if self.env.context.get('website_sale_loyalty_delete', False):
        disabled_rewards_per_order = defaultdict(lambda: self.env['loyalty.reward'])
        for line in self:
            if line.reward_id:
                disabled_rewards_per_order[line.order_id] |= line.reward_id
        for order, rewards in disabled_rewards_per_order.items():
            order.disabled_auto_rewards += rewards
    return super().unlink()
```

When a reward line is deleted via the website cart UI (signaled by the `website_sale_loyalty_delete` context flag), the deleted `reward_id` is added to `sale_order.disabled_auto_rewards` on the parent order. This prevents `_auto_apply_rewards()` from immediately re-adding the same reward.

#### `_should_show_strikethrough_price()` — No Strikethrough for Rewards

```python
def _should_show_strikethrough_price(self):
    return super()._should_show_strikethrough_price() and not self.is_reward_line
```

Reward lines always suppress the "was: X now: Y" strikethrough price display since they have a zero or negative effective price.

#### `_is_sellable()` — Reward Lines Except Free Products

```python
def _is_sellable(self):
    return super()._is_sellable() and (
        not self.is_reward_line or self.reward_id.reward_type == 'product'
    )
```

Discount and shipping reward lines are not independently sellable. Free product reward lines are sellable (the free product itself can be re-added to cart).

---

### `loyalty.program` — Extended

**Inherited from:** `loyalty.program` + `website.multi.mixin`
**File:** `models/loyalty_program.py`

#### Fields Added

| Field | Type | Description |
|---|---|---|
| `ecommerce_ok` | `Boolean` (default `True`) | Gate for "Available on Website" — replaces `sale_ok` for eCommerce program eligibility. Controls whether the program appears in the website rewards panel. |
| `show_non_published_product_warning` | `Boolean` (computed) | Shows a warning if an eWallet program's trigger products are not published on the website. |

#### `_compute_show_non_published_product_warning`

```python
@api.depends('program_type', 'trigger_product_ids.website_published')
def _compute_show_non_published_product_warning(self):
    for program in self:
        program.show_non_published_product_warning = (
            program.program_type == 'ewallet'
            and any(not product.website_published for product in program.trigger_product_ids)
        )
```

Only triggers for `ewallet` program type. eWallet top-up requires customers to add a trigger product to cart, so those products must be website-published.

#### `action_program_share()` — Open Coupon Share Wizard

```python
def action_program_share(self):
    self.ensure_one()
    return self.env['coupon.share'].create_share_action(program=self)
```

Opens the `coupon.share` wizard pre-filled with this program. Triggered from the "Share" button on the loyalty program tree/form views.

#### `website_id` — Inherited from `website.multi.mixin`

| Field | Type | Description |
|---|---|---|
| `website_id` | `Many2one(website)` | Restricts program visibility to a specific website. False = all websites. |

**L3 — Interaction with `ecommerce_ok`:** Both must allow the website for the program to appear. `website_id` controls multi-website scope; `ecommerce_ok` controls the channel (Sale app vs. eCommerce).

---

### `loyalty.rule` — Extended

**Inherited from:** `loyalty.rule`
**File:** `models/loyalty_rule.py`

#### Fields Added

| Field | Type | Description |
|---|---|---|
| `website_id` | `Many2one(website)` | Related from `program_id.website_id`, stored. Enables per-website code uniqueness constraints. |

#### `_constrains_code()` — Website-Scoped Code Uniqueness

```python
@api.constrains('code', 'website_id', 'active')
def _constrains_code(self):
    with_code = self.filtered(lambda r: r.mode == 'with_code' and r.active)
    mapped_codes = with_code.mapped('code')
    read_result = self.env['loyalty.rule'].search_read(
        [('website_id', 'in', [False] + [w.id for w in self.website_id]),
        ('mode', '=', 'with_code'),
        ('code', 'in', mapped_codes),
        ('id', 'not in', with_code.ids),
        ('active', '=', True)],
        fields=['code', 'website_id']
    ) + [{'code': p.code, 'website_id': p.website_id} for p in with_code]
    existing_codes = set()
    for res in read_result:
        website_checks = (res['website_id'], False) if res['website_id'] else (False,)
        for website in website_checks:
            val = (res['code'], website)
            if val in existing_codes:
                raise ValidationError(_('The promo code must be unique.'))
            existing_codes.add(val)
    if self.env['loyalty.card'].search_count([
        ('code', 'in', mapped_codes), ('active', '=', True)
    ]):
        raise ValidationError(_('A coupon with the same code was found.'))
```

**L3 — Why `website_id` is checked twice:** A rule assigned to `website_id=A` conflicts with another rule on `website_id=A`, but does **not** conflict with a rule on `website_id=B` or `website_id=False` (all websites). The `website_checks` loop adds both the specific website and `False` to the conflict set, ensuring that a code assigned to website A does not conflict with "all websites" but does conflict with A itself.

**L3 — Coupon card conflict:** Also raises if any active `loyalty.card` (individual coupon) has the same code, preventing the same code from being a program rule and a personal coupon simultaneously.

**L4 — Performance:** `search_read` with a limited `fields` list avoids fetching all columns. The constraint runs on `write` and `create` via Odoo's `@api.constrains` mechanism.

---

### `loyalty.card` — Extended

**Inherited from:** `loyalty.card`
**File:** `models/loyalty_card.py`

#### `action_coupon_share()` — Open Share Wizard for a Card

```python
def action_coupon_share(self):
    self.ensure_one()
    return self.env['coupon.share'].create_share_action(coupon=self)
```

Opens the `coupon.share` wizard pre-filled with this specific card (vs. the program-level share). Available as a "Share" button in the loyalty card tree view.

---

### `product.product` — Extended

**Inherited from:** `product.product`
**File:** `models/product_product.py`

#### `_can_return_content()` — Unpublished Reward Product Images for Public

```python
def _can_return_content(self, field_name=None, access_token=None):
    if (
        field_name in ["image_%s" % size for size in [1920, 1024, 512, 256, 128]]
        and self.env['loyalty.reward'].sudo().search_count([
            ('discount_line_product_id', '=', self.id),
        ], limit=1)
    ):
        return True
    return super()._can_return_content(field_name, access_token)
```

Public (unauthenticated) users can access images of products that are linked as `discount_line_product_id` on a `loyalty.reward`, even if those products are unpublished. This allows reward products to display images on the website without being fully published in the catalog.

**L4 — Security:** Uses `sudo()` to bypass record rules for the `loyalty.reward` search. This is safe because the check only grants image access to already-unpublished products (not sensitive data), and only for standard image size fields.

#### `_get_product_placeholder_filename()` — Reward-Specific Placeholder

```python
def _get_product_placeholder_filename(self):
    if self.env['loyalty.reward'].sudo().search_count([
        ('discount_line_product_id', '=', self.id),
    ], limit=1):
        if self.env['loyalty.reward'].sudo().search_count([
            ('program_type', '=', 'gift_card'),
            ('discount_line_product_id', '=', self.id),
        ], limit=1):
            return 'loyalty/static/img/gift_card.png'
        return 'loyalty/static/img/discount_placeholder_thumbnail.png'
    return super()._get_product_placeholder_filename()
```

Returns a loyalty-specific placeholder image for reward products that have no actual product image:
- Gift card programs: `gift_card.png`
- Other programs (coupons, promotions): `discount_placeholder_thumbnail.png`
- Default: falls back to the standard product placeholder

---

## Wizard: `coupon.share`

**File:** `wizard/coupon_share.py`
**Model:** `coupon.share` (TransientModel)

### Purpose

Generates a shareable URL for a coupon or promotion program. The URL follows the pattern `/coupon/<code>?r=<redirect>` and automatically applies the coupon when the recipient visits the website with an active cart.

### Fields

| Field | Type | Description |
|---|---|---|
| `website_id` | `Many2one(website)` | Target website for the share link. Required. |
| `coupon_id` | `Many2one(loyalty.card)` | Specific coupon card to share. Required for `program_type='coupons'`. |
| `program_id` | `Many2one(loyalty.program)` | Program to share. Required. |
| `program_website_id` | `Many2one(website)` | Related from `program_id.website_id` (readonly). |
| `promo_code` | `Char` (computed) | The actual code: `coupon_id.code` or `program_id.rule_ids.code`. |
| `share_link` | `Char` (computed) | Full URL: `{base}/coupon/{code}?r={redirect}`. |
| `redirect` | `Char` (default `/shop`) | Page to redirect to after coupon is applied. |

### Constraints

- `_check_program`: A `coupon_id` is required when `program_type == 'coupons'`.
- `_check_website`: The `website_id` must match `program_website_id` if the program has a website assigned.

### `_compute_share_link()` — Short URL Support

```python
def _compute_share_link(self):
    for record in self:
        target_url = '{base}/coupon/{code}?{query}'.format(...)
        if record.env.context.get('use_short_link'):
            tracker = self.env['link.tracker'].search([('url', '=', target_url)], limit=1)
            if not tracker:
                tracker = self.env['link.tracker'].create({'url': target_url})
            record.share_link = tracker.short_url
        else:
            record.share_link = target_url
```

When `use_short_link=True` (set by `action_generate_short_link`), the wizard creates or reuses a `link.tracker` record from `website_links` to generate a UTM-tracked short URL.

### `create_share_action()` — Entry Point from Model Button

```python
@api.model
def create_share_action(self, coupon=None, program=None):
    if bool(program) == bool(coupon):
        raise UserError(_("Provide either a coupon or a program."))
    return {
        'name': _('Share %s', ...),
        'type': 'ir.actions.act_window',
        'view_mode': 'form',
        'res_model': 'coupon.share',
        'target': 'new',
        'context': {
            'default_program_id': program and program.id or coupon.program_id.id,
            'default_coupon_id': coupon and coupon.id or None,
        }
    }
```

Called from `loyalty.card.action_coupon_share()` or `loyalty.program.action_program_share()`.

---

## Controllers

### `main.py` — `WebsiteSale` (extends `website_sale.main.WebsiteSale`)

#### `pricelist()` — POST Coupon Code Submission

**Route:** `/shop/pricelist` (inherited from `website_sale`)
**Method:** `route()` (default GET+POST)

```python
def pricelist(self, promo, reward_id=None, **post):
    coupon_status = order_sudo._try_apply_code(promo)
    if coupon_status.get('not_found'):
        return super().pricelist(promo, **post)
    elif coupon_status.get('error'):
        request.session['error_promo_code'] = coupon_status['error']
    elif 'error' not in coupon_status:
        reward_successfully_applied = True
        if len(coupon_status) == 1:
            coupon, rewards = next(iter(coupon_status.items()))
            if len(rewards) == 1:
                reward = rewards
            else:
                reward = reward_id in rewards.ids and rewards.browse(reward_id)
            if reward and (not reward.multi_product or request.env.context.get('product_id')):
                reward_successfully_applied = self._apply_reward(order_sudo, reward, coupon)
        if reward_successfully_applied:
            request.session['successful_code'] = promo
    return request.redirect(post.get('r', '/shop/cart'))
```

**L3 — Flow:**
1. Tries to apply the code via `_try_apply_code()`
2. Falls back to `website_sale.main.WebsiteSale.pricelist()` if `not_found` (not a loyalty code — lets `website_sale` handle price list/pricelist logic)
3. On error, stores in session for display on cart page
4. If multiple rewards, requires `reward_id` parameter to disambiguate
5. If exactly one reward and not multi-product, auto-applies immediately

**L4 — Multi-product edge case:** If a reward has multiple `reward_product_ids` (user must choose a free product), the auto-apply is skipped. The customer must select via the reward panel instead.

#### `activate_coupon()` — GET Coupon Share URL Handler

**Route:** `/coupon/<string:code>` (type=http, auth=public, website=True)

```python
def activate_coupon(self, code, r='/shop', **kw):
    code = code.strip()
    request.session['pending_coupon_code'] = code
    if order_sudo := request.cart:
        result = order_sudo._try_pending_coupon()
        if isinstance(result, dict) and 'error' in result:
            url_query['coupon_error'] = result['error']
        else:
            url_query['notify_coupon'] = code
    else:
        url_query['coupon_error'] = _("The coupon will be automatically applied when you add something in your cart.")
        url_query['coupon_error_type'] = 'warning'
    redirect = url_parts.replace(query=url_encode(url_query))
    return request.redirect(redirect.to_url())
```

**L3 — Public accessibility:** `auth='public'` means unauthenticated users can visit this link. The coupon is stored in their session and applied on next cart load.

**L3 — Empty cart handling:** If no cart exists yet, stores a warning message that the coupon will apply when the cart is created. The user is redirected to the cart page (empty) where the coupon will be picked up by `_try_pending_coupon()` on the next request.

#### `claim_reward()` — POST Reward Claim from Cart Panel

**Route:** `/shop/claimreward` (type=http, auth=public, website=True)

```python
def claim_reward(self, reward_id, code=None, **post):
    reward_sudo = request.env['loyalty.reward'].sudo().browse(reward_id).exists()
    claimable_rewards = order_sudo._get_claimable_and_showable_rewards()
    for coupon_, rewards in claimable_rewards.items():
        if reward_sudo in rewards:
            coupon = coupon_
            if code == coupon.code and (...conditions...):
                return self.pricelist(code, reward_id=reward_id)
    if coupon:
        self._apply_reward(order_sudo, reward_sudo, coupon)
    return request.redirect(redirect)
```

**L3 — Flow:**
1. Loads the reward record (sudo, for public access)
2. Looks up the corresponding coupon from `claimable_rewards`
3. If `code` is present and matches conditions (code-based or auto/future programs), redirects to `pricelist()` for standard processing
4. Otherwise applies directly via `_apply_reward()`

#### `_apply_reward()` — Apply Reward with Delivery Recalculation

```python
def _apply_reward(self, order, reward, coupon):
    product_id = request.env.context.get('product_id')
    product = product_id and request.env['product.product'].sudo().browse(product_id)
    try:
        reward_status = order._apply_program_reward(reward, coupon, product=product)
    except UserError as e:
        request.session['error_promo_code'] = str(e)
        return False
    if 'error' in reward_status:
        request.session['error_promo_code'] = reward_status['error']
        return False
    order._update_programs_and_rewards()
    if order.carrier_id.free_over and not reward.program_id.is_payment_program:
        res = order.carrier_id.rate_shipment(order)
        if res.get('success'):
            order.set_delivery_line(order.carrier_id, res['price'])
        else:
            order._remove_delivery_line()
    return True
```

**L3 — Delivery recalculation trigger:** After applying a reward, if the carrier has `free_over=True` and the reward is NOT a payment program (eWallet/gift card), the shipping rate is re-evaluated. This allows free shipping rewards to adjust the delivery line amount dynamically.

**L4 — `is_payment_program` exclusion:** eWallet and gift card rewards are excluded from this recalculation because they represent payment instruments, not shipping discounts. Re-evaluating shipping against them could cause infinite loops or incorrect pricing.

---

### `cart.py` — `Cart` (extends `website_sale.controllers.cart.Cart`)

#### `cart()` — Cart Page with Loyalty Recalculation

```python
def cart(self, **post):
    if order_sudo := request.cart:
        order_sudo._update_programs_and_rewards()
        order_sudo._auto_apply_rewards()
    return super().cart(**post)
```

Runs loyalty program evaluation before rendering the cart page. This ensures pending coupons are applied and auto-claimable rewards are granted on every cart page load.

#### `wallet_top_up()` — eWallet Self-Service Reload

**Route:** `/wallet/top_up` (type=http, auth=user, website=True)

```python
def wallet_top_up(self, **kwargs):
    product = self.env['product.product'].browse(int(kwargs['trigger_product_id']))
    self.add_to_cart(product.product_tmpl_id.id, product.id, 1)
    return request.redirect('/shop/cart')
```

Adds the selected eWallet trigger product (e.g., a "Top Up $50" product) to the cart. The eWallet payment method then consumes the cart balance and adds it to the loyalty card. Requires authentication.

---

### `payment.py` — `PaymentPortal` (extends `website_sale.controllers.payment.PaymentPortal`)

#### `_validate_transaction_for_order()` — Final Reward Lock-In

```python
def _validate_transaction_for_order(self, transaction, sale_order):
    super()._validate_transaction_for_order(transaction, sale_order)
    if sale_order.exists():
        initial_amount = sale_order.amount_total
        sale_order._update_programs_and_rewards()
        if sale_order.currency_id.compare_amounts(sale_order.amount_total, initial_amount):
            raise ValidationError(
                _("Cannot process payment: applied reward was changed or has expired.\n"
                  "Please refresh the page and try again.")
            )
```

**L3 — Purpose:** Prevents a race condition where a reward's validity changes between the customer viewing the checkout page and completing payment (e.g., another coupon was applied, or a program expired).

**L4 — `compare_amounts` behavior:** Returns 0 if equal, -1 if first is lower, 1 if first is higher. The `if` condition triggers on any non-zero difference, including rounding discrepancies. This is intentionally strict to protect both merchant and customer from incorrect charges.

**L4 — Performance:** Called at the **last step** before payment processing. The `_update_programs_and_rewards()` call is a DB write operation but only touches coupon point records, not the transaction itself.

---

## View Templates (QWeb)

### `website_sale_templates.xml` — Key Template Overrides

#### `sale_coupon_result` (inherits `website_sale.coupon_form`)

Changes the coupon input placeholder from "Coupon code..." to "Gift card or discount code...".

#### `modify_code_form` (inherits `website_sale.total`)

Renders the full loyalty rewards panel on the cart page:

- **Error messages**: Reads `error_promo_code` from session and order's `get_promo_code_error()`
- **Success messages**: Reads `successful_code` from session
- **Loyalty card balance**: Shows for `program_type == 'loyalty'` programs with the current point balance
- **Claimable rewards**: Iterates `_get_claimable_and_showable_rewards()` and renders a claim/use form per reward
- **Code masking**: Shows only last 4 characters of non-nominative coupon codes: `coupon.code[-4:].rjust(14, '&#8902;')`
- **Multi-product selector**: Renders a `<select>` when `reward.multi_product == True`
- **Expiration date**: Displays `coupon.expiration_date` if set

#### `layout` (inherits `website.layout`)

Injects hidden toast notification elements into every page for coupon feedback messages:
- `.coupon-error-message` — red/danger notification
- `.coupon-warning-message` — yellow/warning notification
- `.coupon-info-message` — green/success notification

These are picked up by the `CouponToaster` public interaction on page load.

#### `cart_discount` (inherits `website_sale.total`)

Inactive by default (`active="False"`). When enabled via the Website Builder "Coupon Snippet Options" panel, shows the `reward_amount` (total discount value) as a separate row in the cart totals, above the untaxed total.

#### `cart_lines_quantity` (inherits `website_sale.cart_lines_quantity`)

Disables the quantity `+`/`-` selector for `reward_type == 'product'` reward lines. Free product reward lines should not have their quantity manually changed on the cart page — the reward rules control the quantity.

#### `cart_line_product_no_link` / `cart_summary_inherit_website_gift_card_sale`

Injects the `sale_loyalty.used_gift_card` template to display gift card code/value info on reward lines in both the cart page and the cart summary/checkout.

#### `website_sale_purchased_gift_card` (inherits `website_sale.confirmation`)

On the order confirmation page, renders the `sale_loyalty.sale_purchased_gift_card` template, which shows gift card codes for any gift card products purchased in the order. This allows customers to copy the code to give to recipients.

---

## Static Assets

### Interactions (Public-facing, `web.public.interactions`)

| File | Class | Selector | Purpose |
|---|---|---|---|
| `coupon_toaster.js` | `CouponToaster` | `.coupon-message` | Converts server-side flash messages (injected into layout) into Odoo notification toasts on page load. Handles info, error, and warning message types. |
| `gift_card_copy.js` | `GiftCardCopy` | `.o_purchased_gift_card .copy-to-clipboard` | Copies gift card code to clipboard on click using `browser.navigator.clipboard.writeText()`. |
| `checkout.js` | (patch on `Checkout`) | — | Patches the `_updateCartSummary` method to dynamically update shipping discount amounts and per-item discount amounts in the checkout summary without a full page reload. |

### Website Builder Plugin

| File | Purpose |
|---|---|
| `coupon_option_plugin.js` | Registers `CouponOption` as a builder option on the coupon/promotion snippet. Extends `Checkout` plugin. |
| `coupon_option.xml` | `BuilderCheckbox` template enabling the "Show Discount in Subtotal" toggle in the Website Builder panel for the coupon snippet. |

### Portal Template Extension

| File | Purpose |
|---|---|
| `portal_loyalty_card.xml` | Extends `loyalty.portal_loyalty_card_dialog` to add a "Claim" button for loyalty rewards and a top-up form for eWallet programs in the customer portal's loyalty card dialog. |

---

## Menu Structure

```
Website > eCommerce (website_sale.menu_ecommerce)
└── Loyalty (menu_loyalty, groups=sales_team.group_sale_manager, sequence=4)
    ├── Loyalty & Discount Programs     → loyalty.loyalty_program_discount_loyalty_action
    └── Gift Card & eWallet Programs    → loyalty.loyalty_program_gift_ewallet_action
```

---

## Configuration Settings

**Settings > Website > eCommerce**: The "Loyalty Programs" shortcut button (`res_config_settings_views.xml`) links directly to the loyalty program action. It is only visible when the `loyalty` module is installed.

---

## Cross-Module Integration Summary

| Integration Point | Module | Detail |
|---|---|---|
| Program eligibility | `sale_loyalty` | `_get_program_domain()` replaces `sale_ok` with `ecommerce_ok` |
| Coupon apply | `sale_loyalty` | `_try_apply_code()`, `_apply_program_reward()` |
| Auto-claim | `sale_loyalty` | `_get_claimable_rewards()`, `_auto_apply_rewards()` |
| Gift card payment | `sale_loyalty` | `is_payment_program` flag on loyalty.program |
| Points display | `sale_loyalty` | `_get_real_points_for_coupon()`, `point_name` on loyalty.card |
| Global discount | `sale_loyalty` | `_get_applied_global_discount()`, `_best_global_discount_already_applied()` |
| Delivery recalc | `website_sale` | `set_delivery_line()`, `carrier_id.rate_shipment()` |
| Short URLs | `website_links` | `link.tracker` model for UTM-tracked coupon share links |
| Session storage | `website_sale` | `request.session` for `pending_coupon_code`, `error_promo_code`, `successful_code` |
| Cart quantity | `website_sale` | `request.session['website_sale_cart_quantity']` sync |
| Portal loyalty card | `loyalty` | `loyalty.portal_loyalty_card_dialog` QWeb template extended |
| eWallet trigger products | `loyalty` | `trigger_product_ids` on loyalty.program for top-up products |

---

## Odoo 18 to 19 Changes

- **`ecommerce_ok` field added** to `loyalty.program` in this module, replacing the Odoo 18 pattern where `sale_ok=True` controlled both backend and website eligibility. The split means programs can now be configured independently for B2B (Sale) and B2C (eCommerce) channels.
- **`_get_claimable_and_showable_rewards()`** is a new method in Odoo 19 that consolidates what was previously spread between `_get_claimable_rewards()` (backend) and website template logic. It now handles the full "show in the rewards panel" computation including expiration checks, global discount comparison, and zero-total exclusion.
- **`_compute_website_order_line()` visual merge** replaces a simpler approach where discount lines were suppressed directly. The new `new()` record technique allows proper monetary aggregation across tax groups for correct display.
- **`disabled_auto_rewards`** Many2many field added to track manually dismissed reward lines, preventing auto-apply loops after customer deletion.
- **`CouponToaster` interaction** replaced older JS notification approaches with the Odoo 19 public interaction registry system.
- **Payment validation hardening**: `_validate_transaction_for_order()` now explicitly compares amounts after re-evaluating rewards, where Odoo 18 relied on implicit order state checks.
- **Short URL generation** for coupon sharing now uses the `website_links` `link.tracker` model for UTM-tracked short links.
- **`Domain.AND` API** (Odoo 19 new API): Both `_get_program_domain()` and `_get_trigger_domain()` use `Domain.AND()` to combine domain leaves programmatically, replacing the Odoo 18 pattern of nested list concatenation. This API is used throughout the loyalty module for composing eligibility, trigger, and program validity domains.
- **`lazy()` function** (Odoo 19): `_get_claimable_rewards()` uses `lazy()` from `odoo.tools.lazy` to defer expensive `_discountable_amount()` computation until actually needed, avoiding unnecessary tax aggregation when the result short-circuits evaluation.
- **eWallet product warning**: `_compute_show_non_published_product_warning` is a new Odoo 19 compute that flags eWallet programs where trigger products are unpublished on the website, preventing the top-up flow from silently failing.

---

## Security

### Access Control

All ACL entries are inherited from `sale_loyalty` via module dependency. No additional ACL rows are defined in this module's `ir.model.access.csv` — the `coupon.share` wizard is a `TransientModel` and does not require explicit ACL entries.

**Key authorization points:**

| Route | Auth | Protection |
|-------|------|-----------|
| `pricelist()` (POST) | public | Coupon code validated server-side; `sale_loyalty._try_apply_code()` enforces all rules |
| `/coupon/<code>` | public | Coupon stored in session only; applied on next cart load |
| `/shop/claimreward` | public | Reward verified against `_get_claimable_and_showable_rewards()` |
| `/wallet/top_up` | user | `auth='user'` enforced by `@route` decorator |
| Payment validation | auth | `_validate_transaction_for_order()` aborts if amount changed |

### CSRF Protection

All state-mutating POST routes (`pricelist()`, `claim_reward()`, `wallet_top_up()`) use Odoo's `@route()` decorator which enforces CSRF tokens by default. The `coupon_share` wizard uses the standard `ir.actions.act_window` form mechanism, which includes CSRF protection via the form submission mechanism.

### SQL Injection Prevention

Code uniqueness constraint in `loyalty_rule.py` uses `search_read()` with explicit `fields` parameter and ORM `search_count()` for coupon card conflict checks. No raw SQL with user string interpolation.

### Session-Based Coupon Storage

`pending_coupon_code` is stored in `request.session` (server-side session). An attacker cannot inject a coupon code for another user via URL manipulation — the code is applied only to the session owner's cart.

### Public Image Access (`product.product._can_return_content`)

The `sudo()` call on `loyalty.reward` search is intentional and safe because it only checks whether a product ID is linked to a `discount_line_product_id`. This grants image access for reward products that may be unpublished on the website. The `sudo()` is bounded to a count-only operation with no field write access.

### Coupon Race Conditions

The `sale_loyalty._try_apply_code()` uses `SELECT ... FOR UPDATE NOWAIT` on the `loyalty_program` row before applying a code. In `website_sale_loyalty`, the `_validate_transaction_for_order()` re-evaluates rewards before payment finalization and aborts if the amount changes, preventing a class of TOCTOU (time-of-check-time-of-use) attacks where a coupon expires between cart display and payment.

### XSS Prevention

Coupon codes and reward names rendered in QWeb templates are automatically escaped by Odoo's template engine. The `coupon_toaster.js` receives messages via server-side session storage (`request.session`) and renders them via Odoo's notification system, which escapes HTML content.

### Nominative Program Access

`_allow_nominative_programs()` returns `False` for public/guest users, preventing unauthenticated users from accessing loyalty/ewallet card points. This blocks the ability to enumerate or use other customers' loyalty cards via the website panel.

### ACL Summary (from `security/ir.model.access.csv`)

`website_sale_loyalty` reuses all ACL entries from `sale_loyalty`. Additional ACLs specific to this module:

| ACL ID | Model | Group | R | W | C | D |
|--------|-------|-------|---|---|---|---|
| `coupon_share_wizard` | `coupon.share` | (inherited via TransientModel) | — | — | — | — |

TransientModel records are automatically deleted by the Odoo garbage collector and do not store sensitive data. No explicit ACL needed.
