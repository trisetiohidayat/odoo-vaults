# loyalty — Coupons & Loyalty

**Module:** `loyalty`
**Manifest:** `loyalty/__manifest__.py`
**Category:** Sales
**Depends:** `product`, `portal`, `account`
**License:** LGPL-3
**Author:** Odoo S.A.

Use discounts, gift cards, eWallets and loyalty programs across sales channels. Covers promotional discounts, loyalty points, gift card programs, eWallet top-ups, buy-X-get-Y offers, and next-order coupon generation.

---

## Architecture Overview

The loyalty module defines **6 core transactional models** and **2 wizards**:

```
loyalty.program          # Program definition container
├── loyalty.rule         # Earning rules (how points are earned per order)
├── loyalty.reward       # Redemption rewards (what points can be exchanged for)
├── loyalty.mail         # Automated email triggers (at creation, when reaching X points)
└── loyalty.card         # Issued coupon / loyalty card / gift card instance
    └── loyalty.history  # Point transaction ledger (issued / used per card)

loyalty.generate.wizard           # Bulk coupon generator
loyalty.card.update.balance       # Manual point balance adjustment
```

Cross-module extensions on: `product.product`, `product.template`, `product.pricelist`, `res.partner`.

---

## Program Types

The `program_type` field drives all program behavior. It is a required `Selection` with 8 values:

| `program_type` | Label | `applies_on` default | `trigger` default | `portal_visible` | `portal_point_name` |
|---|---|---|---|---|---|
| `promotion` | Promotional Program | `current` | `auto` | No | "Promo point(s)" |
| `coupons` | Coupons | `current` | `with_code` | No | "Coupon point(s)" |
| `promo_code` | Discount Code | `current` | `with_code` | No | "Discount point(s)" |
| `gift_card` | Gift Card | `future` | `auto` | Yes | currency symbol (e.g. "$") |
| `loyalty` | Loyalty Cards | `both` | `auto` | Yes | "Loyalty point(s)" |
| `ewallet` | eWallet | `future` | `auto` | Yes | currency symbol |
| `buy_x_get_y` | Buy X Get Y | `current` | `auto` | No | "Credit(s)" |
| `next_order_coupons` | Next Order Coupons | `future` | `auto` | Yes | "Coupon point(s)" |

The `applies_on` field determines the **points consumption model**:

- **`current`** — Points earned on the order are immediately usable on that same order. If not redeemed, points are lost.
- **`future`** — Points earned generate a new coupon for use on a future order.
- **`both`** — Points accumulate on the card across orders (nominative loyalty card); can also be redeemed on the current order.

**L4: `applies_on='both'` marks a program as nominative** (`is_nominative = True`). This triggers different UI behavior: cards are bound to a partner, points accumulate, and the card is visible in the customer portal.

---

## `loyalty.program` — Program Definition

**File:** `models/loyalty_program.py`
**Inherits:** `base.model` (no explicit `_inherit`)
**Order:** `sequence`
**Rec name:** `name`

### Fields

| Field | Type | Notes |
|---|---|---|
| `name` | Char (translate) | Program display name |
| `active` | Boolean (default True) | Toggle activates/archives program + cascades to children |
| `sequence` | Integer | Sort order |
| `company_id` | Many2one `res.company` | Defaults to `self.env.company` |
| `currency_id` | Many2one `res.currency` | Computed from `company_id`; stored; required; drives all monetary fields |
| `currency_symbol` | Char (related) | Mirror of `currency_id.symbol` |
| `pricelist_ids` | Many2many `product.pricelist` | Restricts program to specific pricelists; validated to share program's currency |
| `total_order_count` | Integer (compute) | Stub for extensions; Odoo core returns 0; external modules (e.g. `sale_loyalty`) populate this |
| `rule_ids` | One2many `loyalty.rule` | Conditional earning rules; computed from `_compute_from_program_type` on `program_type` change |
| `reward_ids` | One2many `loyalty.reward` | Available rewards; computed from `_compute_from_program_type` |
| `communication_plan_ids` | One2many `loyalty.mail` | Automated email triggers; computed from `_compute_from_program_type` |
| `mail_template_id` | Many2one `mail.template` | Simplified field for gift_card/ewallet; inverse creates/updates `communication_plan_ids` |
| `trigger_product_ids` | Many2many (related, writable) | Convenience alias to `rule_ids.product_ids`; only meaningful for gift_card/ewallet |
| `coupon_ids` | One2many `loyalty.card` | All issued cards for this program |
| `coupon_count` | Integer (compute) | Count of cards via `_read_group` |
| `coupon_count_display` | Char (compute) | Human-readable "X Coupons" / "X Gift Cards" etc. |
| `program_type` | Selection (required, default `promotion`) | Drives all other defaults via `_program_type_default_values()` |
| `date_from` | Date | Start of validity period (inclusive) |
| `date_to` | Date | End of validity period (inclusive) |
| `limit_usage` | Boolean | If True, `max_usage` must be > 0 |
| `max_usage` | Integer | Max total redemptions across all cards in this program |
| `applies_on` | Selection (`current`/`future`/`both`) | When points/rewards apply; computed from `program_type` defaults |
| `trigger` | Selection (`auto`/`with_code`) | Whether automatic or requires a promo code; computed from `program_type` defaults |
| `portal_visible` | Boolean (default False) | Shows card balance in eCommerce/PoS portal |
| `portal_point_name` | Char (translate) | Label for points in portal (e.g. "Points", "$", "Credits") |
| `is_nominative` | Boolean (compute) | True if `applies_on == 'both'` or if loyalty/ewallet with `applies_on == 'future'` |
| `is_payment_program` | Boolean (compute) | True if `program_type in ('gift_card', 'ewallet')` |
| `payment_program_discount_product_id` | Many2one `product.product` (compute) | For payment programs: returns the `discount_line_product_id` of the first reward |

### Constraints

```
CHECK (limit_usage = False OR max_usage > 0)
  → "Max usage must be strictly positive if a limit is used."

@constrains('currency_id', 'pricelist_ids')
  → All pricelists in `pricelist_ids` must share the same currency as the program.

@constrains('date_from', 'date_to')
  → date_from must be <= date_to.

@constrains('reward_ids')
  → Every active program must have at least one reward
     (skipped with context `loyalty_skip_reward_check`).
```

### Key Methods

#### `_program_type_default_values()`

Returns a `dict` keyed by `program_type` string. Each value is a `dict` of field defaults applied by `_compute_from_program_type` whenever `program_type` changes. This includes:
- `applies_on`, `trigger`, `portal_visible`, `portal_point_name`
- `rule_ids` O2M command list (clears existing + creates default rule)
- `reward_ids` O2M command list (clears existing + creates default reward)
- `communication_plan_ids` O2M command list

**Prototype instantiation pattern**: Changing `program_type` on a program record triggers this compute, which wipes and rebuilds all rules, rewards, and communication plans from the template defaults.

Example for `gift_card`:
```python
'gift_card': {
    'applies_on': 'future',
    'trigger': 'auto',
    'portal_visible': True,
    'portal_point_name': self.env.company.currency_id.symbol,
    'rule_ids': [(5, 0, 0), (0, 0, {
        'reward_point_amount': 1,
        'reward_point_mode': 'money',   # 1 point per $ spent
        'reward_point_split': True,     # separate coupon per unit
        'product_ids': ref('loyalty.gift_card_product_50'),
    })],
    'reward_ids': [(5, 0, 0), (0, 0, {
        'reward_type': 'discount',
        'discount_mode': 'per_point',   # $1 off per point
        'discount': 1,
        'discount_applicability': 'order',
        'required_points': 1,
        'description': _("Gift Card"),
    })],
}
```

Example for `buy_x_get_y`:
```python
'buy_x_get_y': {
    'applies_on': 'current',
    'trigger': 'auto',
    'rule_ids': [..., {
        'reward_point_mode': 'unit',   # per unit paid
        'product_ids': first_sale_product,
        'minimum_qty': 2,              # buy 2 to qualify
    }],
    'reward_ids': [..., {
        'reward_type': 'product',      # free product reward
        'reward_product_id': first_sale_product,
        'required_points': 2,          # 2 credits = 1 free item
    }],
}
```

#### `_compute_from_program_type()`

`@api.depends('program_type')`. Called when `program_type` changes. For each distinct `program_type` among the records being written, calls `programs.write(program_type_defaults[program_type])`. This rebuilds `rule_ids`, `reward_ids`, and `communication_plan_ids`.

#### `_get_valid_products(products)`

Returns a `dict` mapping each rule to the subset of `products` that match its domain. Used by the `sale_loyalty` module to evaluate rule applicability at order-line time.

#### `action_open_loyalty_cards()`

Opens the `loyalty.card` action window filtered to this program, with context set to `program_type`, `program_item_name`, `default_program_id`, and `default_mode` (set to `'selected'` for ewallet, `'anonymous'` otherwise).

#### `write()` — active propagation

When `active` changes to `False`, cascades `active=False` to all `rule_ids`, `reward_ids`, `communication_plan_ids`, and their `discount_line_product_id`s. When `active` changes to `True`, reverses the cascade.

**L4: `reward_ids` write race condition** — When changing `program_type`, ORM writes `reward_ids` before the new defaults are available, triggering the `_constrains_reward_ids` constraint (program must have at least one reward). The `write()` method detects this by checking whether the new `reward_ids` cache is falsy, and if not, wraps the write in `loyalty_skip_reward_check=True` context and applies `program_type` to the context so `loyalty.reward`'s `default_get()` can pull the correct defaults.

#### `get_program_templates()` / `create_from_template()`

Returns structured template metadata for the program creation wizard in the UI. Includes a `fidelity` pseudo-template that creates a loyalty program with `buy_x_get_y`-style unit accumulation and a per-order discount reward.

---

## `loyalty.rule` — Earning Rules

**File:** `models/loyalty_rule.py`
**Inherits:** `base.model`
**Description:** Defines conditions under which customers earn points/credits on an order.

### Fields

| Field | Type | Notes |
|---|---|---|
| `active` | Boolean (default True) | |
| `program_id` | Many2one `loyalty.program` (required, ondelete cascade, index) | Parent program |
| `program_type` | Selection (related) | Mirror of `program_id.program_type` |
| `company_id` | Many2one (related stored) | Stored for ir.rule security filtering |
| `currency_id` | Many2one (related) | Mirror of `program_id.currency_id` |
| `user_has_debug` | Boolean (compute) | True if user in `base.group_no_one`; shows dev-only fields |
| `product_domain` | Char (default `"[]"`) | Raw domain string for custom product filter |
| `product_ids` | Many2many `product.product` | Specific products that trigger the rule |
| `product_category_id` | Many2one `product.category` | Include all children of this category |
| `product_tag_id` | Many2one `product.tag` | Include products with this tag |
| `reward_point_amount` | Float (default 1) | Points awarded; must be > 0 (DB constraint) |
| `reward_point_split` | Boolean (default False) | Generate separate coupons per matched unit; only for `applies_on='future'` programs; **not allowed for nominative programs** (`applies_on='both'` or `ewallet`) |
| `reward_point_name` | Char (related) | Mirror of `program_id.portal_point_name` |
| `reward_point_mode` | Selection (required, default `order`) | How points are calculated: `order` (flat per order), `money` (per currency unit spent), `unit` (per unit of product purchased) |
| `minimum_qty` | Integer (default 1) | Minimum quantity of matched products to trigger |
| `minimum_amount` | Monetary (default 0) | Minimum purchase amount to trigger |
| `minimum_amount_tax_mode` | Selection (`incl`/`excl`, default `incl`) | Whether `minimum_amount` is tax-inclusive or tax-exclusive |
| `mode` | Selection (`auto`/`with_code`, compute) | `with_code` if `code` is set; `auto` otherwise |
| `code` | Char (compute w/ inverse) | Promo code; triggers `mode='with_code'`; auto-cleared when mode set to `auto` |

### Constraints

```
CHECK (reward_point_amount > 0)
  → "Rule points reward must be strictly positive."

@constrains('reward_point_split')
  → _constraint_trigger_multi: prevents reward_point_split=True for
     applies_on='both' or program_type='ewallet' programs.

@constrains('code', 'active')
  → _constrains_code:
     1. Promo codes must be unique across all active rules.
     2. No rule code may match any active loyalty.card.code.
```

### Key Methods

#### `_get_valid_product_domain()`

Builds a domain combining `product_ids`, `product_category_id` (with all children via recursive child resolution), `product_tag_id`, and any raw `product_domain` string (parsed via `ast.literal_eval`). Uses `Domain.OR()` for the specific filters, then ANDs with the raw domain. Returns `Domain.TRUE` if no filters.

**L4: Performance** — `product_domain` is a raw Char field storing a JSON-encoded domain. For large catalogs, evaluation is deferred to the caller (`sale_loyalty`'s order processing). `reward_point_split=True` causes one coupon per matched unit, dramatically increasing coupon volume.

#### `_compute_amount(currency_to)`

Converts `minimum_amount` from the rule's currency to `currency_to` using `currency_id._convert()`. Used at order validation time to compare against order lines.

---

## `loyalty.reward` — Redemption Rewards

**File:** `models/loyalty_reward.py`
**Inherits:** `base.model`
**Order:** `required_points asc`
**Rec name:** `description`

### Fields

| Field | Type | Notes |
|---|---|---|
| `active` | Boolean (default True) | |
| `program_id` | Many2one `loyalty.program` (required, ondelete cascade) | Parent program |
| `company_id` | Many2one (related stored) | Stored for ir.rule security |
| `currency_id` | Many2one (related) | |
| `description` | Char (translate, compute+store+precompute) | Auto-generated human-readable description |
| `reward_type` | Selection (`product`/`discount`, required, default `discount`) | |
| `user_has_debug` | Boolean (compute) | Shows debug fields if user in `base.group_no_one` |
| `discount` | Float (default 10) | Discount value; positive (DB constraint if `reward_type='discount'`) |
| `discount_mode` | Selection (`percent`/`per_order`/`per_point`) | How discount is expressed: `%` (percentage), per order (fixed per order), per point (fixed per point spent) |
| `discount_applicability` | Selection (`order`/`cheapest`/`specific`) | Where discount applies: entire order, cheapest product only, specific products |
| `discount_product_domain` | Char (default `"[]"`) | Raw domain for `discount_applicability='specific'` |
| `discount_product_ids` | Many2many `product.product` | Specific products for `discount_applicability='specific'` |
| `discount_product_category_id` | Many2one `product.category` | Category for specific products |
| `discount_product_tag_id` | Many2one `product.tag` | Tag for specific products |
| `all_discount_product_ids` | Many2many `product.product` (compute) | Resolved product set for `specific` applicability |
| `discount_max_amount` | Monetary | Cap on total discount amount; 0 = unlimited |
| `discount_line_product_id` | Many2one `product.product` | Auto-created service product used to represent the discount line on sale orders |
| `is_global_discount` | Boolean (compute) | True if reward_type='discount', applicability='order', mode in ('per_order', 'percent') |
| `reward_product_id` | Many2one `product.product` | Free product (for `reward_type='product'`); must not be type='combo' |
| `reward_product_tag_id` | Many2one `product.tag` | Tag of products that can be claimed |
| `multi_product` | Boolean (compute) | True if `reward_type='product'` and more than 1 available product |
| `reward_product_ids` | Many2many (compute) | Products available for product-type reward |
| `reward_product_qty` | Integer (default 1) | Quantity of free product given |
| `reward_product_uom_id` | Many2one `uom.uom` (compute) | UoM from the reward product template |
| `required_points` | Float (default 1) | Points needed to claim; must be > 0 (DB constraint) |
| `point_name` | Char (related) | Mirror of `program_id.portal_point_name` |
| `clear_wallet` | Boolean (default False) | If True, redeeming this reward zeroes out the card's points |

### Constraints

```
CHECK (required_points > 0)
CHECK (reward_type != 'product' OR reward_product_qty > 0)
CHECK (reward_type != 'discount' OR discount > 0)
```

### Key Methods

#### `_get_discount_product_domain()`

Identical pattern to `loyalty.rule._get_valid_product_domain()` but for discount applicability products. Combines `discount_product_ids`, `discount_product_category_id` (with recursive child resolution), `discount_product_tag_id`, and raw `discount_product_domain`.

#### `_create_missing_discount_line_products()`

Creates a `product.product` (type=service, sale_ok=False, purchase_ok=False, lst_price=0) for each reward that lacks one. Called on `create()` and on `write()` when `description` changes. The product name is kept in sync with `reward.description` on write.

**L4: Discount line products are shared across programs** — Multiple rewards can share the same `discount_line_product_id` if they were created before this method existed. New rewards each get their own product. Archiving/unarchiving a reward propagates to its `discount_line_product_id`.

#### `_compute_description()`

Auto-generates the `description` field based on `program_type` and reward type:

- `gift_card` / `ewallet` → `"Gift Card"` / `"eWallet"`
- `reward_type='product'` → `"Free Product - {product_name}"`
- `reward_type='discount'` → pattern like `"10% on your order"`, `"$5 per point on the cheapest product"`, `"$15 on specific products (Max $50)"`
- Handles currency position (before/after symbol) from `currency_id.position`

#### `discount_max_amount` L4

This field is a hard cap applied to the total discount value per order. The `sale_loyalty` module's discount computation respects this limit by multiplying `discount` by `required_points` and then capping at `discount_max_amount` for `per_point` mode.

---

## `loyalty.card` — Issued Card / Coupon

**File:** `models/loyalty_card.py`
**Inherits:** `mail.thread`
**Rec name:** `code`

### Fields

| Field | Type | Notes |
|---|---|---|
| `program_id` | Many2one `loyalty.program` (ondelete restrict, index btree_not_null) | |
| `program_type` | Selection (related) | |
| `company_id` | Many2one (related stored precompute) | |
| `currency_id` | Many2one (related) | |
| `partner_id` | Many2one `res.partner` (index) | Set for nominative cards (loyalty/ewallet with `applies_on='both'` or `'future'`) |
| `points` | Float (tracking) | Current point balance |
| `point_name` | Char (related) | |
| `points_display` | Char (compute) | Formatted string: e.g. `"150 Points"` or `"$50.00"` |
| `code` | Char (required, unique) | Barcode-identifiable; generated via `_generate_code()` if not provided |
| `expiration_date` | Date | **Not allowed for loyalty cards** (`program_type='loyalty'`) — raises `ValidationError` |
| `use_count` | Integer (compute, stub) | Always 0 in base; extended by `sale_loyalty` |
| `active` | Boolean (default True) | |
| `history_ids` | One2many `loyalty.history` (readonly) | |

### Code Generation

```python
def _generate_code(self):
    return "044" + str(uuid4())[7:-18]
```

Uses a `044` GS1 prefix (GS1-128 application identifier for coupons) followed by a 15-character UUID slice, producing an 18-character alphanumeric code. The `044` prefix ensures barcode scanners recognize it as a coupon code.

### Constraints

```
UNIQUE(code)
  → "A coupon/loyalty card must have a unique code."

@constrains('code')
  → _contrains_code: prevents a card from sharing a code with any 'with_code' rule.
```

### Communication Triggers

#### `_send_creation_communication()`

Called on `create()`. Sends `trigger='create'` emails from the program's `communication_plan_ids`. Respects `loyalty_no_mail` and `action_no_send_mail` contexts to suppress. If the mail template lacks `email_from`, auto-populates it from the company/author. The `_get_mail_author()` method returns `self.env.user` if internal, else `company_id.partner_id`.

#### `_send_points_reach_communication(points_changes)`

Called on `write()` when `points` changes. Sends `trigger='points_reach'` emails for milestone thresholds. If a card crosses multiple milestones in one transaction, only the **highest** milestone email is sent. Skips if:
- `coupon_change['old'] >= coupon_change['new']` (points lost or unchanged)
- No `partner_id` on the card
- `loyalty_no_mail` context is set

**L4: Milestone ambiguity resolution** — The milestones are sorted `reverse=True`, so iteration finds the highest threshold first. The `break` ensures only one email fires per write transaction.

### Wizard Actions

#### `action_loyalty_update_balance()`

Opens `loyalty.card.update.balance` wizard pre-filled with `default_card_id = self.id`.

#### `action_coupon_send()`

Opens `mail.compose.message` in comment mode with the card as `res_id` and the program's `trigger='create'` mail template pre-loaded.

---

## `loyalty.history` — Point Transaction Ledger

**File:** `models/loyalty_history.py`
**Inherits:** `base.model`
**Order:** `id desc`

### Fields

| Field | Type | Notes |
|---|---|---|
| `card_id` | Many2one `loyalty.card` (required, index, ondelete cascade) | |
| `company_id` | Many2one (related) | |
| `description` | Text (required) | Human-readable description of the transaction |
| `issued` | Float | Points/money added to the card |
| `used` | Float | Points/money deducted from the card |
| `order_model` | Char (readonly) | Model name of associated order (e.g. `sale.order`) |
| `order_id` | Many2oneReference (readonly) | ID of associated order record |

### Methods

#### `_get_order_portal_url()`

Stub method returning `False`. Extended by `sale_loyalty` to return the portal-accessible order URL.

#### `_get_order_description()`

Returns `display_name` of the related order by browsing `order_model` with `order_id`. Returns empty string if either is falsy.

**L4: Audit trail** — `loyalty.history` is the authoritative point audit log. Every programmatic point change should create a history entry. The `loyalty.card.update.balance` wizard and `loyalty.generate.wizard` both create history entries on point mutations.

---

## `loyalty.mail` — Communication Plan

**File:** `models/loyalty_mail.py`
**Inherits:** `base.model`

### Fields

| Field | Type | Notes |
|---|---|---|
| `active` | Boolean (default True) | |
| `program_id` | Many2one `loyalty.program` (required, ondelete cascade) | |
| `trigger` | Selection (`create`/`points_reach`) | When to send: at card creation or when points reach threshold |
| `points` | Float | Milestone threshold; only relevant when `trigger='points_reach'` |
| `mail_template_id` | Many2one `mail.template` (required, domain: `model='loyalty.card'`) | Email template to send |

---

## Wizards

### `loyalty.generate.wizard` — Bulk Coupon Generator

**File:** `wizard/loyalty_generate_wizard.py`
**Model:** `loyalty.generate.wizard`

| Field | Type | Notes |
|---|---|---|
| `program_id` | Many2one `loyalty.program` (required) | Defaults from context `active_id` or `default_program_id` |
| `program_type` | Selection (related) | |
| `mode` | Selection (`anonymous`/`selected`, required, default `anonymous`) | |
| `customer_ids` | Many2many `res.partner` | Partners for `mode='selected'` |
| `customer_tag_ids` | Many2many `res.partner.category` | Tags for `mode='selected'` |
| `coupon_qty` | Integer (compute, writable) | Count of coupons to generate; for `selected` mode auto-calculated as partner count |
| `points_granted` | Float (required, default 1) | Initial balance for each generated card |
| `points_name` | Char (related) | |
| `valid_until` | Date | Expiration for all generated cards |
| `will_send_mail` | Boolean (compute) | True if `mode='selected'` and program has a `trigger='create'` communication |
| `confirmation_message` | Char (compute) | Preview message for the generate action |
| `description` | Text | Description stored in each `loyalty.history` entry |

**`generate_coupons()`** creates `coupon_qty` `loyalty.card` records, then creates one `loyalty.history` record per card with `issued=points_granted`. History entries use the wizard's `description` (or default `"Gift For Customer"`). Returns the created coupon recordset.

### `loyalty.card.update.balance` — Manual Balance Adjustment

**File:** `wizard/loyalty_card_update_balance.py`
**Model:** `loyalty.card.update.balance`

| Field | Type | Notes |
|---|---|---|
| `card_id` | Many2one `loyalty.card` (required, readonly) | Pre-filled from context |
| `old_balance` | Float (related to `card_id.points`) | Shows current balance |
| `new_balance` | Float (required) | New balance to set |
| `description` | Char (required) | Reason for adjustment |

**`action_update_card_point()`** validates `new_balance >= 0` and `new_balance != old_balance`, computes the difference, creates a `loyalty.history` entry (with `issued` or `used` accordingly), then sets `card_id.points = new_balance`.

---

## Cross-Module Integrations

### `product.product` Extension

- **`write()` override**: Prevents archiving (`active=False`) of any product used as `discount_line_product_id` or in `discount_product_ids` of an active reward. Raises `ValidationError`.
- **`_unlink_except_loyalty_products()`**: Prevents deleting `loyalty.gift_card_product_50` and `loyalty.ewallet_product_50` product records. Raises `UserError`.

### `product.template` Extension

- **`create()` override**: When `loyalty_is_gift_card_product` context is set, auto-assigns the `gift_card.png` placeholder image to `image_1920`.
- **`_unlink_except_loyalty_products()`**: Same product-deletion guard as `product.product`.

### `product.pricelist` Extension

- **`action_archive()` override**: Prevents archiving a pricelist that is linked to any active `loyalty.program` via `pricelist_ids`. Raises `UserError`.

### `res.partner` Extension

- **`loyalty_card_count`** (Integer, compute with `compute_sudo=True`, groups: `base.group_user`): Counts active loyalty cards for the partner and all their child contacts where:
  - `points > 0`
  - `program_id.active = True`
  - `expiration_date` is either False or >= today
  - Company is in `env.companies` or False
  - Uses `_read_group` with recursive parent-walk aggregation.
- **`action_view_loyalty_cards()`**: Opens `loyalty.card` action filtered to partner and all children.

---

## Security

### Access Control (CSV)

All models have `perm_read=1` for `base.group_user` (all authenticated users). Only portal-accessible data flows through `mail.thread` on `loyalty.card`.

### Record Rules (ir.rule, multi-company)

All 5 core models have multi-company `ir.rule` records defined in `data/loyalty_data.xml`:

```
domain_force: ['|', ('company_id', 'in', company_ids + [False]),
                    ('company_id', 'parent_of', company_ids)]
```

This covers: `loyalty.program`, `loyalty.card`, `loyalty.history`, `loyalty.rule`, `loyalty.reward`.

**L4: `parent_of` operator** — The `parent_of` domain operator handles parent-child company hierarchies. A record at the parent company is visible to all child company users. This is critical for multinational loyalty deployments where a corporate entity manages programs shared across subsidiaries.

### Deletion Guards

- Programs with `active=True` cannot be deleted (`_unlink_except_active`).
- `gift_card_product_50` and `ewallet_product_50` cannot be deleted (only archived).
- Products used in active reward `discount_product_ids` cannot be archived.
- Pricelists linked to active programs cannot be archived.

---

## Gift Card / eWallet Payment Loop

Gift card and eWallet programs use a **self-funding payment pattern**:

```
Customer buys Gift Card product ($50)
    → sale.order line with product=gift_card_product_50
    → Points rule triggers: 1 point per $ spent (reward_point_mode='money')
    → Card created with points=50, code=GIFT_XXX

Customer redeems Gift Card on future order
    → loyalty.reward with discount_mode='per_point', discount=1, required_points=1
    → Each point = $1 off the order
    → discount_line_product_id used as the order line product
```

**Key property**: `payment_program_discount_product_id` on `loyalty.program` points to the reward's `discount_line_product_id`. The `sale_loyalty` module uses this as the sale order line product when applying the discount.

**eWallet vs Gift Card distinction**: Both use the same `per_point` discount mechanism, but eWallet uses `reward_point_split=False` (all points accumulate on a single card) while Gift Card uses `reward_point_split=True` (each purchased unit generates a separate coupon with its own code).

---

## Performance Considerations

1. **`all_discount_product_ids` compute** — Controlled by `loyalty.compute_all_discount_product_ids` ir.config_parameter. Default is `False` (lazy; uses domain only). When set to `'enabled'`, eagerly searches all matching products. For large catalogs, lazy mode is significantly faster at form-render time but defers the search to order application time.

2. **`reward_point_split=True`** — Creates one `loyalty.card` per unit purchased. For orders with high quantities, this can generate hundreds of cards, stressing the `loyalty.card` table and triggering many `_send_creation_communication()` emails.

3. **`loyalty.history` append-only ledger** — History records are never cleaned up. In high-volume deployments, consider adding a retention policy or archival job.

4. **`_send_points_reach_communication`** in a write transaction — Each card write triggers point-change detection. For batch operations (e.g., importing points), suppress with `loyalty_no_mail` context.

---

## Odoo 18 → 19 Changes

- **`product_domain` field on `loyalty.rule`** — Previously not present as a Char field; now exposed for programmatic domain assignment.
- **`_compute_from_program_type` replace pattern** — Uses O2M command lists `[(5, 0, 0)]` to atomically clear and rebuild rules/rewards on program type change. This pattern was present in Odoo 18 but the constraint workaround (`loyalty_skip_reward_check`) was refined.
- **`loyalty.card` display_name change** — Now computed as `"{program_id.name}: {code}"` replacing the prior rec_name behavior.
- **`gift_card_product_50` and `ewallet_product_50` image** — Gift card product now has a default placeholder image assigned via `product.template.create()` override with `loyalty_is_gift_card_product` context.
- **`is_nominative` compute** — Extended to include `ewallet` programs with `applies_on='future'`, not just `loyalty` programs.
- **`clear_wallet` field** — Added to `loyalty.reward` to support redeeming rewards that exhaust the card balance.

---

## Related Models

- [Modules/sale_loyalty](Modules/sale_loyalty.md) — Loyalty integration in Sales Orders
- [Modules/pos_loyalty](Modules/pos_loyalty.md) — Loyalty in Point of Sale
- [Modules/website_sale_loyalty](Modules/website_sale_loyalty.md) — Loyalty on eCommerce
- [Core/Fields](Core/Fields.md) — Field type reference

## Tags

`#odoo` `#odoo19` `#modules` `#loyalty` `#coupons` `#giftcard` `#ewallet` `#promotion`

---

## sale_loyalty Integration — Loyalty in Sales Orders

**Module:** `sale_loyalty`
**Manifest:** `sale_loyalty/__manifest__.py`
**Depends:** `loyalty`, `sale`
**Auto-install:** True (from `loyalty`)

`sale_loyalty` extends `loyalty` with sales order integration. It provides the point computation engine that evaluates rules against order lines, computes applicable rewards, applies discounts, and manages point redemption.

### Models Extended

#### `sale.order` Extension

**File:** `sale_loyalty/models/sale_order.py`

| Field | Type | Notes |
|---|---|---|
| `applied_coupon_ids` | Many2many `loyalty.card` | Manually applied coupons (copied=false) |
| `code_enabled_rule_ids` | Many2many `loyalty.rule` | Manually triggered rules via promo code (copied=false) |
| `coupon_point_ids` | One2many `sale.order.coupon.points` | Pending coupon-point allocations before order confirmation |
| `reward_amount` | Float (compute) | Sum of all reward line amounts (negative = product freebies) |
| `gift_card_count` | Integer (compute) | Count of gift card cards generated from this order |
| `loyalty_data` | Json (compute) | Aggregated issued/used points from `loyalty.history` for confirmed orders |

**Key methods:**

#### `_update_programs_and_rewards()`

Recomputes which programs are active, evaluates all rules against current order lines, determines applicable rewards, and applies or removes discount lines. Called on every order change (line add/remove, coupon apply).

#### `_get_point_changes()`

Returns a `dict` mapping `loyalty.card` to the net point change when the order is confirmed. Differs from the raw rule computation because `applies_on='current'` coupons deduct their reward cost, and `applies_on='future'` / `applies_on='both'` coupons accumulate issued points only.

#### `_get_claimable_rewards(forced_coupons=None)`

Returns a `dict` mapping `loyalty.card` to the `loyalty.reward` recordset the customer can currently claim. Evaluates each card's available points against reward `required_points`. Excludes rewards that have already been applied to the order. **Only one `shipping` reward can be active at a time** (enforced by `sale_loyalty_delivery`).

#### `action_confirm()` — Loyalty flow

```python
def action_confirm(self):
    # 1. Validate: no negative point balances
    if any(_get_real_points_for_coupon(c) < 0 for c in all_coupons):
        raise ValidationError(...)
    # 2. Update programs and rewards
    order._update_programs_and_rewards()
    # 3. Create loyalty.history entries for confirmed order
    order._add_loyalty_history_lines()
    # 4. Delete ghost coupons (current programs, unclaimed)
    coupon_point_ids.filtered(
        lambda pe: pe.coupon_id.program_id.applies_on == 'current'
        and pe.coupon_id not in reward_coupons
    ).coupon_id.sudo().unlink()
    # 5. Add/remove points from coupons
    for coupon, change in order._get_point_changes().items():
        coupon.points += change     # For future/both
    super().action_confirm()         # Calls sale order confirm
    # 6. Send reward coupon emails (for future coupons)
    order._send_reward_coupon_mail()
```

**L4: Ghost coupon cleanup** — `coupon_point_ids` records represent pending point allocations. If an order is confirmed but no reward was claimed from a `applies_on='current'` program, those pending points are orphaned and the coupon is deleted via `sudo().unlink()`. This prevents `loyalty.card` table bloat from abandoned pending allocations.

#### `_action_cancel()` — Loyalty rollback

1. Deletes all `loyalty.history` entries linked to this order (sudo, to bypass record rules).
2. Reverses point changes: `coupon.points -= change` for previously confirmed orders.
3. Unlinks reward lines (`order_line.filtered('is_reward_line').unlink()`).
4. Deletes non-nominative coupons created from this order that have no use count.

#### `_add_loyalty_history_lines()`

Aggregates `coupon_point_ids` (issued) and `order_line` costs (used) per coupon, then creates one `loyalty.history` entry per coupon with both `issued` and `used` amounts. This is the authoritative audit entry for the confirmed order.

---

#### `sale.order.line` Extension

**File:** `sale_loyalty/models/sale_order_line.py`

| Field | Type | Notes |
|---|---|---|
| `is_reward_line` | Boolean (compute) | True if `reward_id` is set |
| `reward_id` | Many2one `loyalty.reward` (readonly) | The reward that created this line |
| `coupon_id` | Many2one `loyalty.card` (readonly) | The card whose points funded this reward |
| `reward_identifier_code` | Char | Groups multiple reward lines from the same reward claim |
| `points_cost` | Float | Points deducted from the coupon for this reward |

**Core behavior on `create()`:**
```python
for line in res:
    if line.coupon_id and line.points_cost and line.state == 'sale':
        line.coupon_id.points -= line.points_cost
        line.order_id._update_loyalty_history(line.coupon_id, line.points_cost)
```
When a reward line is added to a confirmed order, the coupon is immediately debited. For draft orders, debit happens on `action_confirm()`.

**Core behavior on `unlink()`:**
- Collects all related reward lines (same `reward_id`, `coupon_id`, `reward_identifier_code`) and deletes them together.
- Returns points to the coupon if the order was confirmed.
- Unlinks coupons created from this order that are no longer referenced.

**`is_reward_line` propagation** through multiple inheritance layers:

```
loyalty.reward.reward_type == 'discount' → sale.order.line.is_reward_line = True
                                         → _is_discount_line() returns True
                                         → line.price_unit = negative (discount)
```

`reward_type == 'product'` creates a regular-looking line with `price_unit = 0`, listing the free product as a regular product but with no charge.

---

### `loyalty.card` Extension (sale_loyalty)

**File:** `sale_loyalty/models/loyalty_card.py`

| Field | Type | Notes |
|---|---|---|
| `order_id` | Many2one `sale.order` (readonly) | Source order for generated coupons (gift_card, loyalty, next_order_coupons, ewallet) |
| `order_id_partner_id` | Many2one `res.partner` (related) | Convenience: `order_id.partner_id` |

**`_get_mail_author()` override:** Returns the order's salesperson's partner, falling back to the company partner. This means loyalty card emails are sent from the sales rep, not a generic noreply.

**`_compute_use_count()` override:** Extends the base stub by counting `sale.order.line` records referencing this coupon (reward usage). This accumulates across all orders.

**`_has_source_order()` override:** Returns `True` if `order_id` is set, distinguishing generated coupons from manually created ones.

**`action_archive()` override:** Deletes any `sale.order.coupon.points` records linked to draft orders before archiving the card. This prevents orphaned pending allocations from blocking card archival.

---

### `sale.order.coupon.points` — Pending Point Allocation

**File:** `sale_loyalty/models/sale_order_coupon_points.py`

| Field | Type | Notes |
|---|---|---|
| `order_id` | Many2one `sale.order` (required, cascade) | |
| `coupon_id` | Many2one `loyalty.card` (required, cascade) | |
| `points` | Float (required) | Points to be issued on confirmation |

**SQL Constraint:**
```
UNIQUE (order_id, coupon_id)
  → "The coupon points entry already exists."
```

This is the intermediate table that holds pending point issuances before `action_confirm()`. It allows the same coupon to accumulate points from multiple orders (for `applies_on='both'` programs) because the unique constraint prevents duplicate rows but not multiple rows with different `order_id` values.

---

### Point Computation Flow (L4)

```
sale.order line added/removed
    → _update_programs_and_rewards()
        → _get_applicable_programs()
        → _get_applicable_rules()          # per rule, filter matching order lines
        → _compute_rule_points()           # multiply matched qty by reward_point_amount
        → _create_coupon_points()           # creates sale.order.coupon.points for future coupons
        → _get_applicable_rewards()
        → _get_claimable_rewards()          # filter by points >= required_points
        → _apply_program_reward()          # creates sale.order.line with points_cost
```

**Points computation per `reward_point_mode`:**
- `'order'`: flat `reward_point_amount` per matching rule, regardless of qty/amount
- `'money'`: `reward_point_amount` × (line price_subtotal / currency rounding)
- `'unit'`: `reward_point_amount` × total matched product quantity

**Discount computation for `discount_mode='per_point'`:**
```
discount_amount = min(
    discount × required_points,
    discount_max_amount or inf
)
```

`discount_max_amount` is a hard cap on the total discount value, not per-unit.

---

## sale_loyalty_delivery — Free Shipping Reward

**Module:** `sale_loyalty_delivery`
**Manifest:** `sale_loyalty_delivery/__manifest__.py`
**Depends:** `sale_loyalty`, `delivery`
**Auto-install:** True

Adds a `reward_type = 'shipping'` option to `loyalty.reward` and provides the mechanism to apply free shipping as a loyalty reward.

### `loyalty.reward` Extension

**File:** `sale_loyalty_delivery/models/loyalty_reward.py`

Adds `selection_add=[('shipping', 'Free Shipping')]` to `reward_type`. Ondelete defaults to `'set default'` (falls back to `'discount'`).

#### `_compute_description()` override

```python
for reward in shipping_rewards:
    reward.description = _('Free shipping')
    if reward.discount_max_amount:
        reward.description += _(' (Max %s)', formatted_amount)
```
The `discount_max_amount` becomes the maximum shipping cost covered by the reward (e.g., "Free Shipping (Max $20)").

### `sale.order` Extension

**File:** `sale_loyalty_delivery/models/sale_order.py`

#### `_get_reward_values_free_shipping()`

```python
delivery_line = self.order_line.filtered(lambda l: l.is_delivery)[:1]
max_discount = reward.discount_max_amount or float('inf')
return [{
    'name': _('Free Shipping - %s', reward.description),
    'reward_id': reward.id,
    'coupon_id': coupon.id,
    'points_cost': reward.required_points if not reward.clear_wallet
                   else self._get_real_points_for_coupon(coupon),
    'product_id': reward.discount_line_product_id.id,
    'price_unit': -min(max_discount, delivery_line.price_unit or 0),
    ...
}]
```

- Reads the existing delivery line (`is_delivery=True`) from the order.
- Caps the discount at `discount_max_amount` (or the delivery cost, whichever is lower).
- If `clear_wallet=True`, deducts the entire card balance (`_get_real_points_for_coupon`) rather than the reward's `required_points`.
- Creates a negative-price sale order line using `reward.discount_line_product_id` (auto-created like any other reward).

**L4: `clear_wallet` interaction with free shipping** — When `clear_wallet=True` on a shipping reward, the points cost equals the card's entire balance. This zeroes out the card on redemption.

#### `_get_no_effect_on_threshold_lines()` override

Adds delivery lines and shipping reward lines to the set that does not count toward the minimum purchase threshold for other rewards.

#### `_get_not_rewarded_order_lines()` override

Excludes delivery lines (`is_delivery=True`) from the lines that generate reward points. Shipping lines should not fund further rewards.

#### `_get_claimable_rewards()` override

Filters to prevent multiple `shipping` rewards being active simultaneously. If any shipping reward is already on the order, shipping rewards are removed from the claimable set for all coupons.

### `loyalty.program` Extension

**File:** `sale_loyalty_delivery/models/loyalty_program.py`

Modifies `loyalty` program default to include a `shipping` reward:
```python
res['loyalty']['reward_ids'].append((0, 0, {
    'reward_type': 'shipping',
    'required_points': 100,
}))
```

Also overrides the `promotion` template description to mention free shipping instead of the generic "10% off".

---

## L4: Program State Machine — Active Lifecycle

Programs do not have an explicit state field (no `state` Selection). Instead, `active` (Boolean) acts as the state. A program is "active" if `active=True` and the current date is within `date_from` / `date_to` bounds.

**Implied states:**
- **Inactive**: `active = False` → cascades `active=False` to all children (rules, rewards, communication plans) and their products. Cannot be deleted.
- **Valid**: `active = True` and within date range → fully operational.
- **Expired**: `active = True` but `date_to < today` → rule evaluation still runs, but date validation in `_update_programs_and_rewards()` (in `sale_loyalty`) excludes expired programs.
- **Draft**: `active = True` and `date_from > today` → future-dated programs are operational but have no effect until the start date passes.

**L4: Date range vs `active`** — Programs with `active=True` but expired (`date_to` in the past) are not automatically filtered out at the model level. The `sale_loyalty` module's `_get_applicable_programs()` must check the date range explicitly. A cron job or manual deactivation is required to archive expired programs.

---

## L4: Negative Points, Expired Cards, Multiple Programs

### Negative Points

**Mechanism:** A reward's `points_cost` is deducted from the card on order confirmation. If the card's balance is less than the cost, the deduction can drive the balance negative.

**Validation at `action_confirm()`:**
```python
if any(order._get_real_points_for_coupon(coupon) < 0 for coupon in all_coupons):
    raise ValidationError(_("One or more rewards on the sale order is invalid."))
```
This raises a `ValidationError` and blocks order confirmation if any applied coupon would go negative.

**`_get_real_points_for_coupon()`** computes: `coupon.points - sum(pending points_cost for this coupon across all orders)`. This accounts for the fact that a coupon might have points allocated in draft orders that haven't been confirmed yet.

### Expired Cards

**Code enforcement:**
- `loyalty.card.expiration_date` is checked against today when counting cards on `res.partner.loyalty_card_count`.
- In `sale_loyalty._get_applicable_programs()`, expired cards are excluded from the candidates.
- Loyalty cards with `program_type='loyalty'` cannot have an `expiration_date` at all (enforced by `_restrict_expiration_on_loyalty()` onchange).

**Gift cards / eWallet with expiration:** These program types DO allow `expiration_date`. After expiration, the card remains in the system but `_get_claimable_rewards()` returns empty for that card.

### Multiple Active Programs

**Priority resolution in `sale_loyalty._update_programs_and_rewards()`:**
1. All matching programs are collected.
2. Programs are sorted by `sequence` (lower first).
3. Discounts are applied in order; later discounts can reduce the taxable base for earlier ones.
4. For percentage discounts on `order` applicability, the base is the order subtotal after previous discounts.

**Coupon stacking:**
- Manually applied coupons (`applied_coupon_ids`) are always included.
- Code-triggered rules (`code_enabled_rule_ids`) are included when the code matches.
- Automatic programs (`trigger='auto'`) are always evaluated.
- Maximum one `shipping` reward can be applied at a time.

**Program-specific reward filtering:**
```python
# Each reward is linked to its program, so incompatible rewards never mix
res[coupon] = rewards.filtered(lambda r: r.program_id in order._get_applicable_programs())
```

---

## L4: Performance Analysis — Point Computation Complexity

### Complexity Model

**Rule evaluation:** For each rule, `sale_loyalty._get_applicable_rules()` filters `order_line` by the rule's product domain. Domain evaluation is O(n) where n = number of order lines.

**Point computation:** For `reward_point_mode='money'`, each matched line's `price_subtotal` is divided by the currency rounding factor. This is O(matched_lines).

**Reward application:** For each `applies_on='current'` reward, `_get_reward_line_values()` creates a sale order line. The cost is dominated by domain evaluation on the order.

### Key Performance Flags

| Configuration | Impact |
|---|---|
| `loyalty.compute_all_discount_product_ids = 'enabled'` | Eagerly searches all products for `all_discount_product_ids` — slow on large catalogs |
| `reward_point_split=True` | Creates one coupon per matched unit — N coupons for N units purchased |
| `applies_on='both'` on many cards | Each order update recomputes `_get_real_points_for_coupon()` for all coupons |
| `program_type='loyalty'` with many active cards | `_get_claimable_rewards()` iterates all partner cards |
| Gift card bulk generation (wizard) | Creates N `loyalty.card` + N `loyalty.history` records in a single transaction |

### Caching Strategy

`sale_loyalty` uses `lazy` from `odoo.tools` to defer expensive computations. The `loyalty_data` Json field aggregates from `loyalty.history` via `_read_group`, which PostgreSQL handles efficiently.

### N+1 Prevention

- `_read_group` used for card counts (avoids loop per partner).
- `_get_applicable_rules()` processes all rules in batch against order lines.
- `_compute_reward_total()` iterates order lines once to aggregate all reward amounts.

### Scaling Recommendations

1. For catalogs > 10,000 products, set `loyalty.compute_all_discount_product_ids` to `disabled` (lazy domain evaluation).
2. For high-volume gift card programs, consider archiving used gift cards rather than accumulating them.
3. For nominative programs with > 10,000 active cards per partner, the `_get_claimable_rewards()` iteration may need pagination.
4. Consider adding an index on `loyalty.card(partner_id, program_id, points)` for frequent lookups.

---

## L4: Odoo 18 → 19 Migration Notes for Loyalty

### Breaking Changes

| Area | Odoo 18 | Odoo 19 |
|---|---|---|
| `display_name` | `rec_name = 'code'` | Computed `"%s: %s" % (program_id.name, code)` |
| `product_domain` on rule | Char field but undocumented | Now exposed and writable via `_get_valid_product_domain()` |
| `is_nominative` compute | Only `applies_on='both'` on `loyalty` program | Also includes `ewallet` with `applies_on='future'` |
| `clear_wallet` field | Not present | New field on `loyalty.reward` |
| `_compute_from_program_type` | Constraint could fire prematurely | `loyalty_skip_reward_check` context refined |
| `gift_card_product_50` image | None | Auto-assigned `gift_card.png` via `loyalty_is_gift_card_product` context |

### Code Patterns to Update

1. Any custom overrides of `loyalty.card._send_creation_communication()` need to handle the new `_get_mail_author()` behavior (order salesperson fallback).

2. Custom reward types (via `_inherit` on `loyalty.reward` with `selection_add`) need `ondelete={'custom_type': 'set default'}` to prevent constraint failures on uninstall.

3. The `sale_loyalty._get_point_changes()` dict may have different keys in Odoo 19 if you have custom `applies_on` extensions.

4. Gift card products (`gift_card_product_50`, `ewallet_product_50`) can no longer be deleted (only archived) — update any data migration scripts.

### Data Migration Checklist

- [ ] Check for orphaned `loyalty.card` records with `program_id.active=False` — clean up or archive.
- [ ] Verify all `loyalty.reward` records have a `discount_line_product_id` — run `_create_missing_discount_line_products()` if needed.
- [ ] Update any hardcoded `program_type` values if custom types were added.
- [ ] Review `_constrains_code` behavior for any promo code conflicts.
- [ ] Test gift card purchase + redemption flow end-to-end.

---

## L4: Security Model — Coupon Code Attacks and Access Control

### Code Generation Robustness

```python
def _generate_code(self):
    return "044" + str(uuid4())[7:-18]
```

The `044` prefix is the GS1-128 application identifier for "coupon redemption code". The remaining 15 characters are from a UUID v4, giving approximately 3.4×10^38 possible codes. Brute-force attacks are computationally infeasible.

**L4: No code collision check in `_generate_code()`** — The method does not verify uniqueness against existing cards. The DB constraint `UNIQUE(code)` provides eventual enforcement, but a race condition could theoretically cause a duplicate-key error. For bulk generation via `loyalty.generate.wizard`, the ORM batch insert handles this gracefully.

### Code guessing attack mitigation

The `_contrains_code` method also prevents a card from sharing a code with any `'with_code'` rule (promo codes), and vice versa. This prevents an attacker from registering a promo code that collides with an existing gift card.

### Access Control

**Read access:** All authenticated users (`base.group_user`) have `perm_read` on all loyalty models. This is intentional — partners should be able to see their own cards via the portal.

**Write access:** Only users with specific permissions can modify card points, create rewards, or archive programs. The `loyalty.card.update.balance` wizard requires explicit write access.

**Portal access:** Cards with `portal_visible=True` and a `partner_id` are accessible via the customer portal. Anonymous gift card codes (no `partner_id`) are NOT portal-accessible.

**Multi-company isolation:** The `parent_of` operator in ir.rule ensures that a card created at a parent company is visible to all child company users. If this is not desired, add a record rule with a stricter domain.

### Data Privacy

`loyalty.history` records contain `order_id` (Many2oneReference) which links to `sale.order`. This means point transaction history is accessible through the order's audit trail. Consider privacy regulations (GDPR) when retaining loyalty history — no automatic purge mechanism exists in the base module.

---

## L4: Point Caching and Stale Card Handling

### Point Balance Caching

Points are stored directly on `loyalty.card.points` (Float). There is no separate cache. All reads hit the DB record.

**Stale reads:** When a sale order is in draft state, `coupon_point_ids` holds pending point allocations. `_get_real_points_for_coupon()` computes the effective balance as `coupon.points - pending_costs`. A stale `coupon.points` value (e.g., modified by another process between order save and confirm) is detected by the negative-points validation check in `action_confirm()`.

### Stale Card Scenarios

| Scenario | Detection | Resolution |
|---|---|---|
| Card expired but still has points | `expiration_date` check in `_get_claimable_rewards()` | Returns empty rewards; points remain but unusable |
| Card archived mid-order | `active` check in program applicability | Program excluded from order |
| Partner unlinked from card | `partner_id` existence check | Card becomes anonymous; portal access lost |
| Points changed via wizard while order is draft | Negative points validation in `action_confirm()` | Raises `ValidationError`, blocks confirm |
| Concurrent point redemption | Database-level `points` write with SQL constraint | Last write wins; negative balance prevented by ORM check |

### Concurrency Control

The `points` field is updated via ORM `write()` in multiple places:
- `action_confirm()`: `coupon.points += change`
- `action_cancel()`: `coupon.points -= change` (reversal)
- `loyalty.card.update.balance` wizard: direct `points = new_balance`
- `sale.order.line.create()`: `coupon_id.points -= line.points_cost`

For concurrent edits (e.g., POS redemption while admin updates balance), the last write wins. The negative-points validation in `action_confirm()` provides eventual consistency.

**L4: No optimistic locking** — The module does not use `write_date` or version fields to detect concurrent modifications. For high-concurrency deployments (e.g., large PoS with many cashiers), consider adding `ir.sequence` versioning or a PostgreSQL advisory lock.

---

## Related Models

- [Modules/sale_loyalty](Modules/sale_loyalty.md) — Loyalty integration in Sales Orders
- [Modules/sale_loyalty_delivery](Modules/sale_loyalty_delivery.md) — Free shipping reward type
- [Modules/pos_loyalty](Modules/pos_loyalty.md) — Loyalty in Point of Sale
- [Modules/website_sale_loyalty](Modules/website_sale_loyalty.md) — Loyalty on eCommerce
- [Modules/delivery](Modules/delivery.md) — Delivery costs and carrier management
- [Core/Fields](Core/Fields.md) — Field type reference

## Tags

`#odoo` `#odoo19` `#modules` `#loyalty` `#coupons` `#giftcard` `#ewallet` `#promotion` `#sale_loyalty` `#points` `#rewards`
