---
title: POS Loyalty
description: Bridges the loyalty framework with the Point of Sale frontend. Enables coupons, gift cards, loyalty points, and promotions in POS. Client-side evaluation, server-side confirmation, offline-capable.
tags: [odoo19, pos, loyalty, coupon, gift-card, module, ewallet, pos-loyalty]
model_count: 14
models:
  - loyalty.program (pos_config_ids, pos_ok, pos_order_count, pos_report_print_id)
  - loyalty.card (source_pos_order_id, get_gift_card_status, get_loyalty_card_partner_by_code)
  - loyalty.reward (pos load, reward_product_domain, _replace_ilike_with_in)
  - loyalty.rule (valid_product_ids, any_product, promo_barcode)
  - loyalty.mail (pos_report_print_id)
  - barcode.rule (coupon type selection)
  - pos.config (_get_program_ids, _check_before_creating_new_session, use_coupon_code)
  - pos.order (validate_coupon_programs, confirm_coupon_programs, _process_existing_gift_cards)
  - pos.order.line (is_reward_line, reward_id, coupon_id, reward_identifier_code, points_cost)
  - pos.session (_load_pos_data_models)
  - res.partner (loyalty_card_count)
  - product.template (_load_pos_data_search_read, special products)
  - product.product (_load_pos_data_fields, all_product_tag_ids)
dependencies:
  - loyalty
  - point_of_sale
category: Sales/Point of Sale
source: odoo/addons/pos_loyalty/
created: 2026-04-06
updated: 2026-04-11
l4_version_changes: true
l4_security: true
l4_offline_support: true
l4_performance: true
---

# POS Loyalty

## Overview

**Module:** `pos_loyalty`
**Category:** Sales / Point of Sale
**Depends:** `loyalty`, `point_of_sale`
**Auto-install:** Yes (sequence 6 — installs after both dependencies)
**License:** LGPL-3
**Location:** `odoo/addons/pos_loyalty/`

`pos_loyalty` bridges the generic `loyalty` framework with the Point of Sale frontend. It enables coupons, gift cards, loyalty points, and promotional programs at the POS terminal. All loyalty computation — point accrual, reward eligibility, discount application — is evaluated **client-side in the POS JavaScript** for instant feedback during the sale. The Python layer handles three critical server-side responsibilities: **session initialization validation**, **order-persistence confirmation** (the loyalty lifecycle after payment), and **security enforcement** (ACLs, coupon existence checks, gift card one-time-use enforcement).

The module does not define standalone `pos_loyalty.*` models. It extends every model in the `loyalty` module that participates in POS operations (`loyalty.card`, `loyalty.program`, `loyalty.rule`, `loyalty.reward`, `loyalty.mail`), plus key `pos.*` models (`pos.config`, `pos.order`, `pos.order.line`, `pos.session`), and `product.*` models to ensure loyalty-related products are available in the POS product load.

The `pos.load.mixin` pattern is central: every extended model implements `_load_pos_data_domain` and `_load_pos_data_fields` so the POS session preload mechanism pushes only the relevant subset of loyalty records into the browser. This selective loading is critical because a production environment might have thousands of loyalty cards, but only the active programs and on-demand card lookups are needed at the terminal.

---

## Module Dependency Tree

```
pos_loyalty
├── loyalty                          ← loyalty.card, loyalty.program, loyalty.rule,
│   │                                   loyalty.reward, loyalty.mail, loyalty.history
│   ├── product
│   ├── mail
│   └── digest
└── point_of_sale                    ← pos.config, pos.session, pos.order,
                                        pos.order.line, product.product, product.template
    ├── pos_restaurant  (optional)
    ├── pos_self_order  (optional)
    └── account         (payment reconciliation)
```

**Dependency note:** `pos_loyalty` is a **bridge module** — it has no Python code of its own beyond imports. All functionality is mixed into existing models via `_inherit`. It auto-installs because both `loyalty` and `point_of_sale` declare it as a dependency of their own auto-install logic.

---

## Models Detail (L2)

### pos.config — Extended

**File:** `models/pos_config.py`

Two methods added; no new fields. All loyalty program filtering and coupon validation logic is centralized here.

#### `_get_program_ids()`

```python
def _get_program_ids(self) -> res.partner
```

Returns the `loyalty.program` recordset valid for this POS config at the current date. Called by every other model's `_load_pos_data_domain` as the authoritative filter. The result is effectively cached per POS session because `_load_pos_data` is only called once at session startup.

**SQL-level domain filters:**

```
('pos_ok', '=', True)
'|', ('pos_config_ids', '=', self.id), ('pos_config_ids', '=', False)
    # Program with no POS restriction applies everywhere
'|', ('date_from', '=', False), ('date_from', '<=', today)
'|', ('date_to', '=', False), ('date_to', '>=', today)
'|', ('pricelist_ids', '=', False), ('pricelist_ids', 'in', self.available_pricelist_ids.ids)
('currency_id', '=', self.currency_id.id)
```

**Python post-filter** (requires recordset operations, cannot be expressed in SQL domain):

```python
.filtered(lambda p: not p.limit_usage or p.sudo().total_order_count < p.max_usage)
```

If `limit_usage` is True, the program is excluded when `total_order_count >= max_usage`. The `sudo()` call is critical: it bypasses record rules so that usage counting is always accurate regardless of the current user's ACL. This is safe because `total_order_count` is a computed integer with no security implications.

**Returns:** `loyalty.program` recordset, may be empty. An empty result means no loyalty programs are active for this POS.

---

#### `_check_before_creating_new_session()`

```python
def _check_before_creating_new_session(self) -> None
```

Called when a POS manager opens a new session. Inherits from `point_of_sale.pos_config`; calls `super()` only after all checks pass. Fails with `UserError` listing all violations if any check fails.

**Validation 1 — Reward product availability:**

Every `loyalty.reward` with `reward_type == 'product'` must have `available_in_pos = True` on its `reward_product_id`. Also validates `rule_ids.valid_product_ids` for gift card programs (the product being purchased as a gift card must be available in POS).

**Validation 2 — Gift card program structural rules** (enforced per gift card program):

| Check | Required Value | Why |
|---|---|---|
| `len(reward_ids)` | 1 | Gift card balance = points balance; multiple rewards would create ambiguity |
| `len(rule_ids)` | 1 | Same reason |
| `rule.reward_point_amount` | 1 | 1 point per currency unit spent |
| `rule.reward_point_mode` | `'money'` | Points derived from order amount |
| `reward.reward_type` | `'discount'` | Discount-based redemption |
| `reward.discount_mode` | `'per_point'` | 1 currency per point |
| `reward.discount` | 1 | Same |
| `mail_template_id` | set | Email delivery on gift card creation |
| `pos_report_print_id` | set | Physical printout for in-store sale |

These constraints ensure gift cards behave as financial instruments: the card's point balance directly equals its monetary value at a 1:1 conversion rate.

---

#### `use_coupon_code(code, creation_date, partner_id, pricelist_id)`

```python
def use_coupon_code(self, code, creation_date, partner_id, pricelist_id) -> dict
```

Called from POS JavaScript when the cashier enters or scans a coupon/gift card code. This is the **server-side validation endpoint** — the POS JS also computes reward eligibility client-side, but this RPC call serves as the authoritative validation and returns coupon metadata.

**Search order:**

```python
self.env['loyalty.card'].search([
    ('program_id', 'in', self._get_program_ids().ids),
    '|', ('partner_id', 'in', (False, partner_id)), ('program_type', '=', 'gift_card'),
    ('code', '=', code),
], order='partner_id, points desc', limit=1)
```

- `order='partner_id, points desc'` — partner-matched cards rank above anonymous; highest-point card wins among anonymous cards
- Gift card cards (`partner_id = False`) are always searchable regardless of current partner (they are bearer instruments)
- Other program types require either no partner lock (`partner_id = False`) or exact partner match

**Validation sequence** (first failure returns `successful: False`):

1. `coupon.expiration_date < check_date` — card expired
2. `program.date_to < today_date` — program ended
3. `program.limit_usage` and `program.sudo().total_order_count >= program.max_usage` — usage exhausted
4. `program.date_from > today_date` — program not yet started
5. `not program.reward_ids` or all rewards require more points than available — nothing claimable
6. `pricelist_id not in program.pricelist_ids` — pricelist mismatch
7. `program.program_type == 'promo_code'` — promo code program requires the code to be set in POS (already satisfied since we are searching by code, but returns error if logic is reversed)

**Success return payload:**

```python
{
    'successful': True,
    'payload': {
        'program_id': program.id,
        'coupon_id': coupon.id,
        'coupon_partner_id': coupon.partner_id.id,  # may be False for anonymous
        'points': coupon.points,
        'has_source_order': coupon._has_source_order(),
    }
}
```

The `has_source_order` flag tells the POS whether this coupon can be reused (loyalty/ewallet) or is one-time-use (promo code).

---

### loyalty.card — Extended

**File:** `models/loyalty_card.py`
**Inherits:** `['loyalty.card', 'pos.load.mixin']`

#### New Fields

| Field | Type | Description |
|---|---|---|
| `source_pos_order_id` | `Many2one('pos.order')` | PoS order where this coupon was generated. Populated when a coupon is awarded by a POS order (gift card sold at POS, loyalty reward coupon, etc.). |
| `source_pos_order_partner_id` | `Many2one('res.partner')` | Related partner from source order; included in `_mail_get_partner_fields` so coupon email templates render the correct partner name. |

#### `_load_pos_data_domain()` — Returns `False`

```python
def _load_pos_data_domain(self, data, config):
    return False
```

**Effect:** Loyalty cards are **not** preloaded into the POS session. They are fetched **on-demand** per coupon code entry via `use_coupon_code()`. This prevents thousands of cards from bloating the session payload and avoids stale data. Every coupon validation goes to the server.

#### `_load_pos_data_fields(config)`

```python
def _load_pos_data_fields(self, config):
    return ['partner_id', 'code', 'points', 'program_id', 'expiration_date', 'write_date']
```

Only these six fields are transmitted to the POS when a card is queried by code.

#### `_has_source_order()`

```python
def _has_source_order(self):
    return super()._has_source_order() or bool(self.source_pos_order_id)
```

Overrides the base `loyalty.card` to also consider `source_pos_order_id`. Used in `use_coupon_code` response to signal the POS whether the coupon can be reused or reloaded.

#### `get_gift_card_status(gift_code, config_id)`

```python
@api.model
def get_gift_card_status(self, gift_code, config_id) -> dict
```

Returns validity status and card data for a gift card code. This is a separate method from `use_coupon_code` because gift cards have a distinct validation path: they are bearer instruments (no partner lock) and have a one-time-use constraint.

**All conditions for `status = True`:**

```python
card.exists()
(not card.expiration_date or card.expiration_date > today)
card.points > 0
card.program_id.program_type == 'gift_card'
not card.partner_id          # gift card must be anonymous (not yet assigned to a partner)
len([id for id in card.history_ids.mapped('order_id') if id != 0]) == 0
    # No completed POS order in history
```

The `!= 0` filter excludes canceled orders (whose `order_id` evaluates to 0 in the `mapped()` result). A gift card used in a voided order remains valid.

**Returns:** `{'status': bool, 'data': {'loyalty.card': [...]}}`. Returns `status = True` if the card does not exist (so the POS can offer to create a new gift card product sale).

#### `get_loyalty_card_partner_by_code(code)`

```python
@api.model
def get_loyalty_card_partner_by_code(self, code) -> res.partner | False
```

Searches for a loyalty card (not gift card) by code and returns the `partner_id`. Used by the POS to associate a scanned loyalty card with the current customer before computing their point balance.

#### `_compute_use_count()`

```python
def _compute_use_count(self):
    super()._compute_use_count()
    read_group_res = self.env['pos.order.line']._read_group(
        [('coupon_id', 'in', self.ids)], ['coupon_id'], ['__count'])
    count_per_coupon = {coupon.id: count for coupon, count in read_group_res}
    for card in self:
        card.use_count += count_per_coupon.get(card.id, 0)
```

Extends the base `_compute_use_count` to also count usage via `pos.order.line`. The base method counts usage via `sale.order.line` (e-commerce loyalty). POS loyalty redemption adds a separate count via `pos.order.line`. Both are aggregated into `card.use_count`.

---

### loyalty.program — Extended

**File:** `models/loyalty_program.py`
**Inherits:** `['loyalty.program', 'pos.load.mixin']`

#### New Fields

| Field | Type | Description |
|---|---|---|
| `pos_config_ids` | `Many2many('pos.config')` | Restricts which POS configs this program applies to. `store=True, readonly=False` so managers can modify it from the program form. Note: if no POS is specified (`False`), the program applies everywhere. |
| `pos_order_count` | `Integer` (computed SQL) | Count of distinct POS orders that used this program's rewards via LATERAL JOIN. |
| `pos_ok` | `Boolean` (re-declared) | Explicitly re-declared with `default=True` — loyalty programs are POS-enabled by default. |
| `pos_report_print_id` | `Many2one('ir.actions.report')` | Report action for printing gift cards/ewallets from POS. Computed from `communication_plan_ids.pos_report_print_id`; inverse writes back to `communication_plan_ids`. Only valid for `gift_card` and `ewallet` program types. |

#### `_load_pos_data_domain(data, config)`

```python
def _load_pos_data_domain(self, data, config):
    return [('id', 'in', config._get_program_ids().ids)]
```

Returns only programs valid for this POS config, matching date range, currency, and pricelist.

#### `_load_pos_data_fields(config)`

```python
def _load_pos_data_fields(self, config):
    return [
        'name', 'trigger', 'applies_on', 'program_type', 'pricelist_ids', 'date_from',
        'date_to', 'limit_usage', 'max_usage', 'total_order_count', 'is_nominative',
        'portal_visible', 'portal_point_name', 'trigger_product_ids', 'rule_ids', 'reward_ids'
    ]
```

#### `_load_pos_data_read(records, config)`

```python
def _load_pos_data_read(self, records, config):
    return super()._load_pos_data_read(records.sudo(), config)
```

Reads records with `sudo()` because POS users have `perm_read=1` on `loyalty.program` but may not have access to all program fields needed for reward computation. The `sudo()` ensures all data needed for client-side reward computation is available.

#### `_unrelevant_records(config)`

```python
def _unrelevant_records(self, config):
    valid_record = config._get_program_ids()
    return self.filtered(lambda record: record.id not in valid_record.ids).ids
```

Used by `pos.load.mixin` to exclude already-loaded records that are no longer relevant (e.g., after a program's `date_to` has passed during an active session). Returns a list of IDs to remove from the session cache.

#### `_compute_pos_order_count()` — SQL LATERAL JOIN

```sql
SELECT program.id, SUM(orders_count)
FROM loyalty_program program
    JOIN loyalty_reward reward ON reward.program_id = program.id
    JOIN LATERAL (
        SELECT COUNT(DISTINCT orders.id) AS orders_count
        FROM pos_order orders
            JOIN pos_order_line order_lines ON order_lines.order_id = orders.id
        WHERE order_lines.reward_id = reward.id
    ) agg ON TRUE
WHERE program.id = ANY(%s)
GROUP BY program.id
```

The LATERAL JOIN avoids an N+1 correlated subquery per program. Counts distinct `pos.order` records via `pos.order.line` joined to `loyalty.reward`. An order with multiple lines using the same reward counts as 1.

#### `_compute_total_order_count()`

```python
def _compute_total_order_count(self):
    super()._compute_total_order_count()
    for program in self:
        program.total_order_count += program.pos_order_count
```

Aggregates both e-commerce (`sale.order.line`) and POS (`pos.order.line`) usage into the total order count used for `max_usage` enforcement.

---

### loyalty.rule — Extended

**File:** `models/loyalty_rule.py`
**Inherits:** `['loyalty.rule', 'pos.load.mixin']`

#### New Fields

| Field | Type | Description |
|---|---|---|
| `valid_product_ids` | `Many2many('product.product')` (computed) | Resolves `product_ids`, `product_category_id`, `product_tag_id`, and `product_domain` into an actual recordset of products where `available_in_pos = True` and match the rule's domain. Used by POS JS for product-matching loops. |
| `any_product` | `Boolean` (computed) | True if no product filter is set (all products match the rule). Used by POS JS to skip product-matching loops entirely. |
| `promo_barcode` | `Char` (computed, stored, readonly=False) | Auto-generated barcode for the promo code. On every change to `code`, `_generate_code()` produces a new barcode. The POS scans this barcode to apply the promo code. |

#### `_compute_valid_product_ids()`

Groups rules by identical filter criteria to minimize SQL queries:

```python
domain = Domain.AND([
    [('available_in_pos', '=', True)],
    rules[:1]._get_valid_product_domain()
])
rules.valid_product_ids = self.env['product.product'].search(domain, order="id")
rules.any_product = False  # if any filter is set
```

If no product filter is set on the rule, `any_product = True` and `valid_product_ids` is left empty (no product resolution needed).

#### `_load_pos_data_fields(config)` — Excludes `promo_barcode`

```python
def _load_pos_data_fields(self, config):
    return [
        'program_id', 'valid_product_ids', 'any_product', 'currency_id',
        'reward_point_amount', 'reward_point_split', 'reward_point_mode',
        'minimum_qty', 'minimum_amount', 'minimum_amount_tax_mode', 'mode', 'code'
    ]
```

`promo_barcode` is not sent to the POS — the POS JavaScript re-generates it client-side from the `code` field using the same `_generate_code()` algorithm.

---

### loyalty.reward — Extended

**File:** `models/loyalty_reward.py`
**Inherits:** `['loyalty.reward', 'pos.load.mixin']`

#### `_get_discount_product_values()`

Extends the base method to force `taxes_id = False` on auto-created discount line products:

```python
def _get_discount_product_values(self):
    res = super()._get_discount_product_values()
    for vals in res:
        vals.update({'taxes_id': False})
    return res
```

**Why:** Discount line products represent a reward (e.g., 10% off). Tax was already collected on the taxable order lines. Adding a tax entry to the discount line would create a spurious tax credit/debit, corrupting tax reports.

#### `_load_pos_data_domain(data, config)`

Filters rewards to:
- Belong to programs valid for this POS config
- Are NOT `reward_type == 'product'` unless `reward_product_id.active == True`
- Include tagged products where at least one tag variant is active

The `reward_product_tag_id` OR condition handles the case where a tag contains both active and inactive product variants.

#### `_load_pos_data_fields(config)`

```python
def _load_pos_data_fields(self, config):
    return [
        'description', 'program_id', 'reward_type', 'required_points', 'clear_wallet',
        'currency_id', 'discount', 'discount_mode', 'discount_applicability',
        'all_discount_product_ids', 'is_global_discount', 'discount_max_amount',
        'discount_line_product_id', 'reward_product_id', 'multi_product',
        'reward_product_ids', 'reward_product_qty', 'reward_product_uom_id',
        'reward_product_domain'
    ]
```

#### `_replace_ilike_with_in(domain_str)`

Converts server-side `ilike`/`not ilike` operators in `reward_product_domain` to `in`/`not in` with pre-resolved record IDs before sending to the POS:

```python
# Transformation:
# BEFORE: ['categ_id', 'ilike', 'Electronics']
# AFTER:  ['categ_id', 'in', [1, 3, 7]]  (resolved category IDs)
```

**Why:** The POS JavaScript cannot perform text search on many2one fields; IDs must be resolved server-side before transmission. This method parses the JSON domain, resolves each `ilike`/`not ilike` condition on a many2one field by searching for matching display names, and rewrites the operator to `in`/`not in`.

#### `_get_reward_product_domain_fields(config)`

Scans all reward product domains for this config and returns the set of product field names used. These are appended to `product.product._load_pos_data_fields` so the POS has all fields needed to evaluate domain conditions client-side.

#### `unlink()` — Archive Instead of Delete

```python
def unlink(self):
    if len(self) == 1 and self.env['pos.order.line'].sudo().search_count(
        [('reward_id', 'in', self.ids)], limit=1
    ):
        return self.action_archive()
    return super().unlink()
```

**Why:** Once a reward has been used in a POS order line, deleting it would create orphaned references in `pos.order.line`. Archived rewards are excluded from new orders via the `_load_pos_data_domain` filter (`reward_product_id.active` check). The `sudo()` is required because POS users lack read access to `pos.order.line`.

---

### loyalty.mail — Extended

**File:** `models/loyalty_mail.py`

| Field | Type | Description |
|---|---|---|
| `pos_report_print_id` | `Many2one('ir.actions.report')` | Report action triggered when a coupon/gift card is created in POS. Rendered as PDF and attached to the order confirmation email. |

---

### barcode.rule — Extended

**File:** `models/barcode_rule.py`

Inherits `barcode.rule`, adds `('coupon', 'Coupon')` to the `type` Selection with `ondelete='coupon': 'set default'`. Barcode patterns defined in `data/default_barcode_patterns.xml`:

- Pattern: `043|044` — handles both new (043) and legacy (044) gift card barcode formats
- Encoding: `any`
- Sequence: 50 — evaluated after product and standard coupon rules

---

### pos.order — Extended

**File:** `models/pos_order.py`

#### `_get_fields_for_order_line()` — Extended

Adds to base fields list:
```python
fields.extend(['is_reward_line', 'reward_id', 'coupon_id',
               'reward_identifier_code', 'points_cost'])
```

These fields are transmitted from POS JS to Python when creating `pos.order.line` records during order creation.

---

#### `validate_coupon_programs(point_changes, new_codes)`

Called **before** order finalization. `point_changes` maps `coupon_id (int) -> delta_points (float)` where negative = spending points, positive = earning.

**Validation steps:**

1. All coupon IDs must exist and belong to an active program. Missing/bad IDs cause immediate failure with `removed_coupons` list returned.
2. For each coupon: `coupon.points >= -point_changes[coupon.id]`. Uses `float_compare(precision=2)` to avoid floating-point rounding errors.
3. New codes being created must not already exist in the database.

**Failure return** includes `updated_points` dict so the POS can refresh the UI with current balances.

---

#### `confirm_coupon_programs(coupon_data)`

Called **after** `pos.order` is created. `coupon_data` maps `coupon_id (int) -> {points, won, spent, line_codes, program_id, ...}`.

**Execution flow:**

**Step 1 — `_process_existing_gift_cards(coupon_data)`:**

Gift cards in the payload are matched by code or ID, updated in-place, and **removed** from `coupon_data`. For each gift card found:
- **Partner assignment:** If `gift_card.partner_id == False` and `self.partner_id` exists, assigns the partner permanently.
- **Source order assignment:** If no prior source order exists, sets `source_pos_order_id`.
- **Points update:** `gift_card.points += coupon_vals['points']` (spending sends negative value).
- **History created:** `loyalty.history` records the `used`/`issued` amounts.

Gift cards are NOT created here — they are sold as a POS product line (the card creation happens when the gift card product is added to the order).

**Step 2 — `_check_existing_loyalty_cards(coupon_data)`:**

For `loyalty`/`ewallet` program types, if a card for the same partner+program already exists, the incoming `coupon_data` key is redirected to the existing card ID. This prevents duplicate loyalty cards per partner per program.

**Step 3 — `_remove_duplicate_coupon_data(coupon_data)`:**

Checks `loyalty.history` to prevent re-awarding the same coupon reward for the same order on split-payment or retry scenarios.

**Step 4 — Create new coupons:**

All `k < 0` keys in `coupon_data` represent new coupons to create:
```python
coupon_create_vals = {
    'program_id': p['program_id'],
    'partner_id': get_partner_id(p.get('partner_id', self.partner_id.id)),
    'code': p.get('code') or p.get('barcode') or self.env['loyalty.card']._generate_code(),
    'points': 0,  # starts at 0; points credited via history
    'expiration_date': p.get('expiration_date'),
    'source_pos_order_id': self.id,
}
```

Creation is done `sudo()` because POS users lack `create` permission on `loyalty.card`. The `action_no_send_mail=True` context prevents premature email sending during bulk creation.

**Step 5 — Link reward lines:** For each `pos.order.line` with a `reward_identifier_code`, the newly created (or existing) coupon is assigned to `coupon_id`.

**Step 6 — Send creation communication:** Triggers `create` event in `loyalty.mail`, sending emails and/or printing reports.

**Step 7 — Return payload:**
- `coupon_updates`: Nominative card updates (id, points, code, partner_id) for POS cache refresh
- `program_updates`: Usage counts per program for enforcement of `max_usage`
- `new_coupon_info`: Display data for newly created coupons (excludes gift cards/ewallets)
- `coupon_report`: Map of report ID -> coupon IDs to render as PDF attachments

---

#### `_add_mail_attachment(name, ticket, basic_receipt)`

Adds a printed gift card report as a PDF attachment to the order confirmation email:
```python
action_report._render_qweb_pdf(action_report.report_name, filtered_gift_cards.ids)
```

Only gift cards with a configured `pos_report_print_id` are attached.

---

### pos.order.line — Extended

**File:** `models/pos_order_line.py`

#### New Fields

| Field | Type | Index | Description |
|---|---|---|---|
| `is_reward_line` | `Boolean()` | No | True if this line is a loyalty reward (e.g., 10% discount, free product). |
| `reward_id` | `Many2one('loyalty.reward')` | `btree_not_null` | The specific reward claimed. `ondelete='restrict'` prevents accidental reward deletion that would orphan order lines. |
| `coupon_id` | `Many2one('loyalty.card')` | `ondelete='restrict'` | The loyalty card used to claim the reward. |
| `reward_identifier_code` | `Char()` | No | Groups multiple lines that belong to the same reward instance. A multi-product discount generates one identifier shared across all affected lines. |
| `points_cost` | `Float()` | No | Point cost deducted from the coupon for this reward. Multiple lines from the same reward will have the same `points_cost` (deducted once in total, split across lines for display purposes). |

---

### pos.session — Extended

**File:** `models/pos_session.py`

```python
def _load_pos_data_models(self, config):
    data = super()._load_pos_data_models(config)
    data += ['loyalty.program', 'loyalty.rule', 'loyalty.reward', 'loyalty.card']
    return data
```

Registers loyalty models for session preload. Note: `loyalty.card` is registered but returns `False` from `_load_pos_data_domain`, so no cards are preloaded — only the model registration is needed for on-demand queries.

---

### product.product — Extended

**File:** `models/product_product.py`

#### `_load_pos_data_fields(config)` — Extended

Adds `all_product_tag_ids` and any additional fields referenced in `loyalty.reward.reward_product_domain` for this config. This ensures the POS has all product data needed to evaluate rule and reward domains client-side.

```python
missing_fields = self.env['loyalty.reward']._get_reward_product_domain_fields(config) - set(params)
if missing_fields:
    params.extend([field for field in missing_fields if field in self._fields])
```

---

### product.template — Extended

**File:** `models/product_template.py`

#### `_load_pos_data_search_read(data, config)` — Special Product Augmentation

The base POS uses limited loading (`pos_limited_loading`). This override ensures loyalty-specific products are always available in the POS:

**Forces loading of reward and trigger products:**
```python
reward_products = rewards.discount_line_product_id | rewards.reward_product_ids | rewards.reward_product_id
trigger_products = config._get_program_ids().trigger_product_ids
loyalty_product_tmpl_ids = set((reward_products | trigger_products)._filtered_access('read').product_tmpl_id.ids)
```

**Marks special products** (in POS but not yet loaded, to be hidden from product grid):
```python
config_data['_pos_special_products_ids'] += product_ids_to_hide.product_variant_id.ids
```

**Marks display products** (products that should appear in POS grid for gift cards/ewallets):
```python
config_data['_pos_special_display_products_ids'] = special_display_products.product_tmpl_id.ids
```

Includes: `loyalty.gift_card_product_50`, `loyalty.ewallet_product_50`, and all e-wallet trigger products.

---

### res.partner — Extended

**File:** `models/res_partner.py`

| Field | Type | Note |
|---|---|---|
| `loyalty_card_count` | `Integer` | Count of loyalty cards belonging to this partner. Restricted to `base.group_user` and `point_of_sale.group_pos_user`. |

---

## Workflows

### Workflow: Gift Card Sale at POS

```
1. Cashier adds "Gift Card" POS product (price = amount to load)
2. POS JS computes loyalty rules → awards gift_card program points
3. Customer pays face value
4. pos.order._create_orders() creates pos.order + lines
5. pos.order.confirm_coupon_programs():
   a. _process_existing_gift_cards() → finds no existing card (first purchase)
   b. Creates new loyalty.card with code, points = 0, source_pos_order_id = self
   c. loyalty.history created (issued = points_earned)
6. _add_mail_attachment() renders gift card PDF from pos_report_print_id
7. Order email sent with PDF attachment (via loyalty.mail trigger: create)
8. Customer receives physical gift card printout with barcode
```

### Workflow: Gift Card Redemption at POS

```
1. Cashier scans gift card barcode
2. pos.config.use_coupon_code(code, ...) → validates card, returns points balance
3. POS JS computes reward eligibility, creates reward lines (is_reward_line=True)
4. Customer pays (reward lines reduce order total)
5. pos.order.confirm_coupon_programs():
   a. _process_existing_gift_cards():
      - gift_card.points += coupon_vals['points']  (negative = spent)
      - loyalty.history created (used = |points_spent|)
   b. Gift card removed from coupon_data (not re-created)
6. Gift card PDF not re-attached on redemption (only on creation)
```

### Workflow: Loyalty Points Earning at POS

```
1. Customer identified (partner_id set on pos.order)
2. POS JS computes loyalty rules for the order
3. Order paid → pos.order created
4. confirm_coupon_programs():
   a. _check_existing_loyalty_cards():
      - Finds existing card for partner + loyalty program
      - Redirects coupon_data key to existing card ID
   b. coupon.points += points_earned
   c. loyalty.history created (issued = points_earned)
5. Points visible on partner's loyalty card in backend
```

---

## Security (L4)

### ACL Overview

`pos_loyalty` ships a comprehensive `security/ir.model.access.csv` with per-group CRUD permissions:

| Access ID | Model | Group | R | W | C | D |
|---|---|---|---|---|---|---|
| `access_program_pos_user` | `loyalty.program` | `group_pos_user` | 1 | 0 | 0 | 0 |
| `access_program_pos_manager` | `loyalty.program` | `group_pos_manager` | 1 | 1 | 1 | 1 |
| `access_applicability_pos_user` | `loyalty.rule` | `group_pos_user` | 1 | 0 | 0 | 0 |
| `access_applicability_pos_manager` | `loyalty.rule` | `group_pos_manager` | 1 | 1 | 1 | 1 |
| `access_coupon_pos_user` | `loyalty.card` | `group_pos_user` | 1 | 1 | 0 | 0 |
| `access_coupon_pos_manager` | `loyalty.card` | `group_pos_manager` | 1 | 1 | 1 | 0 |
| `access_reward_pos_user` | `loyalty.reward` | `group_pos_user` | 1 | 0 | 0 | 0 |
| `access_reward_pos_manager` | `loyalty.reward` | `group_pos_manager` | 1 | 1 | 1 | 1 |
| `access_communication_pos_user` | `loyalty.mail` | `group_pos_user` | 1 | 0 | 0 | 0 |
| `access_communication_pos_manager` | `loyalty.mail` | `group_pos_manager` | 1 | 1 | 1 | 1 |
| `access_sale_coupon_generate` | `loyalty.generate_wizard` | `group_pos_user` | 1 | 1 | 1 | 0 |
| `access_loyalty_history_pos_user` | `loyalty.history` | `group_pos_user` | 1 | 1 | 1 | 0 |
| `access_loyalty_card_update_balance_pos_user` | `loyalty.card_update_balance` | `group_pos_user` | 1 | 1 | 1 | 0 |

**Key design decisions:**
- POS users can WRITE `loyalty.card` (for point redemption) but cannot CREATE or DELETE — prevents cashiers from fabricating coupons
- POS managers can CREATE coupon records (for the manual coupon generation wizard) but cannot DELETE
- `loyalty.history` is writable by POS users — required for point updates during gift card processing
- `loyalty.card_update_balance` is writable — allows POS to correct point balances

### Coupon Manipulation Attack Surface

The most security-sensitive flow is `use_coupon_code`. The RPC call receives `(code, creation_date, partner_id, pricelist_id)` from the POS JavaScript. Key mitigations:

1. **Code existence check**: The coupon must exist in `loyalty.card` for a program active in this POS config. An attacker cannot guess a coupon code and get a valid response.

2. **Partner lock enforcement**: For non-gift-card programs, the search allows either `partner_id = False` (anonymous card) or exact partner match. A coupon assigned to Partner A cannot be used by Partner B.

3. **Points balance check**: `validate_coupon_programs` checks `coupon.points >= -point_changes[coupon.id]`. Even if the POS JavaScript tries to spend more points than available, the server rejects it.

4. **Program active check**: `program.active` and date range (`date_from`, `date_to`) are enforced server-side. The POS JS may show the reward to the user, but the server will reject it on `confirm_coupon_programs`.

5. **`sudo()` usage**: Three `sudo()` calls exist in the codebase:
   - `_get_program_ids` post-filter for `total_order_count`
   - `_load_pos_data_read` on programs for field access
   - `loyalty.card` creation in `confirm_coupon_programs`
   
   These bypass record rules but NOT field-level `groups` restrictions. POS user `sudo()` cannot access fields hidden by `groups` attribute.

### Gift Card Financial Integrity

Gift cards represent stored monetary value. The key integrity constraints enforced server-side:

- **One-time redemption**: `get_gift_card_status` checks `len([id for id in history_ids.mapped('order_id') if id != 0]) == 0`. This is the last line of defense — even if a malicious actor gets a gift card code and spends it, the history ledger records the transaction permanently.

- **Points = currency**: The `_check_before_creating_new_session` validation enforces the 1:1 conversion rate. A gift card with `discount != 1` or `discount_mode != 'per_point'` cannot be saved, preventing the creation of gift cards with favorable exchange rates.

- **Permanent partner assignment**: Once `_process_existing_gift_cards` assigns `gift_card.partner_id`, it cannot be unassigned from the POS. The gift card becomes locked to that partner. This prevents theft scenarios where a stolen gift card code is assigned to a thief's account.

---

## Offline Loyalty Support (L4)

### Architecture

Odoo's POS supports **offline operation** — the POS JavaScript continues to function when the network connection is lost. Loyalty programs are designed to work offline with the following constraints:

### What Works Offline

**Client-side loyalty computation** (`pos_loyalty/static/src/js/`):

The POS JavaScript evaluates loyalty rules and rewards entirely in the browser using the preloaded program data. When offline:

1. **Program data** is preloaded at session start via `_load_pos_data` — this includes `loyalty.program`, `loyalty.rule`, `loyalty.reward` (filtered by `_load_pos_data_domain`)
2. **Points are computed client-side** based on the order lines and the preloaded rule data
3. **Reward eligibility** is evaluated client-side using the same algorithm as the server
4. **The cashier can apply rewards** and see point calculations without a network connection

**What the offline POS caches:**
- Active loyalty programs (name, rules, rewards)
- Valid product IDs per rule (`valid_product_ids`)
- Reward configuration (discount rates, required points)
- Any already-loaded loyalty cards (via prior `use_coupon_code` calls during the session)

### What Requires Online Connection

**Card validation** requires a server call:

1. `use_coupon_code(code, ...)` — must hit the server to verify the coupon exists, is not expired, and has sufficient points. Offline: the POS cannot validate a newly entered coupon code.

2. `get_gift_card_status(gift_code, config_id)` — must hit the server to check the one-time-use constraint and point balance. Offline: gift card redemption is blocked.

3. `validate_coupon_programs(point_changes, new_codes)` — called before order finalization to verify points balance. Offline: order finalization may fail if loyalty programs are applied.

4. `confirm_coupon_programs(coupon_data)` — called after order creation to persist the loyalty lifecycle (card creation, point updates, history). **This is the most critical offline gap**: if the POS goes offline after payment is collected but before order sync, the loyalty card may not be created and points may not be credited.

### Offline Failure Mode: Split Coupon Scenario

The most dangerous offline scenario:

```
POS goes offline after customer payment is collected

Case A: Loyalty card was supposed to be CREATED
  → Order is stored locally but not synced
  → loyalty.card is never created
  → Customer has no proof of their points
  → On reconnect: _create_orders() + confirm_coupon_programs() runs → card created retroactively
  → Customer may have left the store

Case B: Points were supposed to be CREDITED to existing card
  → Order is stored locally but not synced
  → card.points is NOT updated server-side
  → On reconnect: _create_orders() + confirm_coupon_programs() runs → points credited retroactively
  → Acceptable: points are eventually credited
```

The Odoo POS sync mechanism handles Case B correctly via the standard order synchronization flow. Case A is more problematic — the customer leaves without their loyalty card. This is a known limitation of offline POS: the loyalty lifecycle is only completed when the order syncs.

**Mitigation:** Many implementations require network connectivity for loyalty programs to be active, or they display a warning when offline that loyalty points cannot be awarded until the order syncs.

### Session Cache Invalidation During Active Sessions

Programs are filtered at session start. If a program's `date_to` passes during an active session, it will remain active until the session is closed and reopened. This is a deliberate trade-off: `_unrelevant_records()` exists to support incremental cache refresh, but the POS does not call it per-order.

---

## Version Changes: Odoo 18 to 19 (L4)

### Gift Card Validation — Stricter One-Time Redemption

**Odoo 18:** `get_gift_card_status` checked only that the card existed and had points. The one-time-use constraint relied on the gift card not being in the POS product catalog after first use.

**Odoo 19:** The check was strengthened to explicitly verify no non-cancel order exists in history:
```python
len([id for id in card.history_ids.mapped('order_id') if id != 0]) == 0
```

This closes a gap where a gift card could be used multiple times if the POS went offline between uses.

### Gift Card Partner Assignment — New Logic

**Odoo 18:** Gift cards were anonymous bearer instruments with no partner association.

**Odoo 19:** `_process_existing_gift_cards` now assigns `gift_card.partner_id = self.partner_id` on first use if the card is anonymous:
```python
if not gift_card.partner_id and self.partner_id:
    gift_card.partner_id = self.partner_id
```

This locks the gift card to the customer who first used it, preventing theft.

### New Fields for Coupon Email Templates

**Odoo 18:** Coupon email templates used `partner_id` from the loyalty card record. For coupons generated at POS (gift cards sold, loyalty rewards issued), the `partner_id` might be empty if the customer was not identified.

**Odoo 19:** `source_pos_order_id` and `source_pos_order_partner_id` fields added to `loyalty.card`. The `_mail_get_partner_fields` override includes `source_pos_order_partner_id`, so email templates can now render the correct customer name from the POS order even when the card has no direct partner assignment.

### Reward Domain Translation

**Odoo 18:** `reward_product_domain` was sent to the POS with `ilike` operators on many2one fields. The POS JavaScript could not resolve these text searches.

**Odoo 19:** `_replace_ilike_with_in` added to resolve many2one IDs server-side and rewrite the domain to use `in`/`not in` operators before transmission.

### Reward `unlink()` — Archive Instead of Delete

**Odoo 18:** `loyalty.reward.unlink()` permanently deleted the record, orphaning `pos.order.line` records that referenced it.

**Odoo 19:** `unlink()` now silently archives the reward if it has been used in order lines, preserving referential integrity.

### Program Cache Invalidation

**Odoo 18:** No mechanism existed to remove stale programs from the POS session cache during an active session.

**Odoo 19:** `_unrelevant_records()` added to `loyalty.program` to support the `pos.load.mixin` incremental refresh mechanism, allowing the POS to drop programs that are no longer relevant (e.g., past `date_to`) without restarting the session.

### E-Wallet Display Products

**Odoo 18:** E-wallet trigger products were not explicitly added to `_pos_special_display_products_ids`, potentially causing them to be hidden in the POS product grid.

**Odoo 19:** E-wallet trigger products are now explicitly included in the special display products set.

### `pos_config_ids` — Now Stored

**Odoo 18:** `pos_config_ids` was a pure computed field on `loyalty.program`.

**Odoo 19:** The field is now `store=True, readonly=False`, allowing managers to edit the POS restriction directly from the program form without triggering unnecessary recomputation.

### Points Cost Float Handling

**Odoo 18:** Point comparisons used implicit float comparison.

**Odoo 19:** `float_compare(precision=2)` is explicitly used in `validate_coupon_programs` to prevent floating-point rounding errors when checking if a coupon has enough points for redemption.

### `_get_signature()` Override

**Odoo 19 only:** `loyalty.card._get_signature()` is overridden to use the POS order's `user_id.signature` instead of the default when the card was generated from a POS order:
```python
def _get_signature(self):
    return self.source_pos_order_id.user_id.signature or super()._get_signature()
```

---

## Edge Cases and Failure Modes

### Gift card assigned to partner cannot be unassigned
Once `_process_existing_gift_cards` assigns `gift_card.partner_id = self.partner_id`, it is permanent. The card is then locked to that partner. `use_coupon_code` search favors partner-matched cards, so the assigned card will always be the primary match.

### Gift card one-time redemption enforcement
`get_gift_card_status` returns `status = False` if any non-cancel order exists in `history_ids`. Counted as `len([id for id in history_ids.mapped('order_id') if id != 0]) == 0`. A gift card used in a VOIDED order (where `order_id = 0`) remains valid.

### Points precision
`float_compare` with precision 2 is used throughout to avoid floating-point rounding errors when checking point balances.

### Reward deletion blocked after use
`loyalty.reward.unlink()` silently archives instead of deleting if the reward is referenced by any `pos.order.line`. Archived rewards are excluded from new orders via `_load_pos_data_domain`.

### Split-payment on loyalty reward
`_remove_duplicate_coupon_data` checks `loyalty.history` before awarding points, preventing duplicate point awards if an order is paid in multiple transactions.

### `sudo()` usage
`sudo()` is used in three places: `_get_program_ids` post-filter, `_load_pos_data_read` on programs, and `loyalty.card` creation. These bypass record rules but not field-level `groups` restrictions.

### Gift card sale with existing code collision
`validate_coupon_programs` checks that no new coupon code being created already exists in the database. This prevents accidentally overwriting an existing gift card when selling a new one.

---

## Data Files

### `data/default_barcode_patterns.xml`

Creates a `barcode.rule`:
- `type = 'coupon'`
- `pattern = '043|044'` — handles new (043) and legacy (044) gift card barcode formats
- `encoding = 'any'`
- `sequence = 50`

### `data/gift_card_data.xml` (noupdate)

Post-install configuration:
- Sets `available_in_pos = True` and removes taxes from `loyalty.gift_card_product_50` and `loyalty.ewallet_product_50`
- Links `pos_report_print_id` on the gift card program to `loyalty.report_gift_card`

### `data/pos_loyalty_demo.xml`

Demo data for the main POS:
- Product: `Simple Pen` (`CONS_0002`, price 1.20, `available_in_pos = True`)
- Program: `15% on next order` — `next_order_coupons` type, minimum 100 currency, 15% reward
- Program: `Loyalty Program` — `loyalty` type, `applies_on: both`, 1 point per currency spent, free pen at 50 points
- 10 pre-generated 10% coupon codes for the demo POS

---

## Uninstall Hook

```python
def uninstall_hook(env):
    env['loyalty.history'].search([('order_model', '=', 'pos.order')]).unlink()
```

**Why:** `loyalty.history` records with `order_model = 'pos.order'` carry a reference to `pos.order` records. When `pos_loyalty` is uninstalled, those history records become orphaned references. They are deleted to maintain referential integrity.

---

## Source Files

| File | Purpose |
|---|---|
| `models/__init__.py` | Imports all 14 model extensions |
| `models/pos_config.py` | `_get_program_ids`, `_check_before_creating_new_session`, `use_coupon_code` |
| `models/loyalty_card.py` | `source_pos_order_id`, `get_gift_card_status`, `get_loyalty_card_partner_by_code`, `_compute_use_count` |
| `models/loyalty_program.py` | `pos_config_ids`, `pos_order_count` (SQL LATERAL JOIN), `pos_report_print_id` |
| `models/loyalty_rule.py` | `valid_product_ids`, `any_product`, `promo_barcode` |
| `models/loyalty_reward.py` | Discount product taxes override, domain translation, archive-on-use |
| `models/loyalty_mail.py` | `pos_report_print_id` on communication plan |
| `models/barcode_rule.py` | `coupon` barcode type |
| `models/pos_order.py` | `confirm_coupon_programs`, `validate_coupon_programs`, gift card lifecycle |
| `models/pos_order_line.py` | `is_reward_line`, `reward_id`, `coupon_id`, `points_cost` |
| `models/pos_session.py` | Register loyalty models for session preload |
| `models/product_product.py` | Add loyalty domain fields to POS product load |
| `models/product_template.py` | Force-load reward/trigger products, mark special display products |
| `models/res_partner.py` | `loyalty_card_count` |
| `security/ir.model.access.csv` | Per-group CRUD permissions for all loyalty models |
| `data/default_barcode_patterns.xml` | Gift card barcode pattern `043|044` |
| `data/gift_card_data.xml` | Gift card/ewallet products POS availability + report link |
| `data/pos_loyalty_demo.xml` | Demo loyalty program, reward product, pre-generated coupons |
