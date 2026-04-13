---
Module: pos_loyalty
Version: Odoo 18
Type: Integration
Dependencies: loyalty, point_of_sale
---

# Point of Sale - Coupons & Loyalty (`pos_loyalty`)

## Overview

`pos_loyalty` bridges the [Modules/Loyalty](modules/loyalty.md) module with the Point of Sale. It enables loyalty programs, gift cards, promotions, and coupon-based discounts to be applied and redeemed at the POS terminal. It is an **auto-install** module that depends on both `loyalty` and `point_of_sale`.

**Key architectural role:**
- Extends `pos.config` with loyalty program resolution logic
- Extends `pos.order` with coupon validation, confirmation, and history recording
- Extends `pos.order.line` with reward line tracking fields
- Extends base `loyalty.program`, `loyalty.rule`, `loyalty.reward`, and `loyalty.card` with `pos.load.mixin` so they are pushed into the POS frontend session
- Extends `res.partner` with loyalty card count
- Extends `product.product` to include loyalty reward product fields in POS data
- Adds `coupon` barcode rule type for scanning loyalty cards/coupons at POS

---

## Module Structure

```
pos_loyalty/
├── models/
│   ├── loyalty_program.py    # Extends loyalty.program (pos.load.mixin)
│   ├── loyalty_rule.py       # Extends loyalty.rule (pos.load.mixin)
│   ├── loyalty_reward.py     # Extends loyalty.reward (pos.load.mixin)
│   ├── loyalty_card.py       # Extends loyalty.card (pos.load.mixin)
│   ├── loyalty_mail.py       # Extends loyalty.mail (pos_report_print_id)
│   ├── barcode_rule.py       # Adds 'coupon' barcode rule type
│   ├── pos_config.py         # Extends pos.config (loyalty program methods)
│   ├── pos_order.py          # Extends pos.order (validate/confirm coupons)
│   ├── pos_order_line.py     # Extends pos.order.line (reward line fields)
│   ├── pos_session.py        # Extends pos.session (loyalty model list)
│   ├── product_product.py   # Extends product.product (POS loyalty fields)
│   └── res_partner.py        # Extends res.partner (loyalty_card_count)
└── __manifest__.py           # depends: loyalty, point_of_sale; auto_install: True
```

---

## How Loyalty Programs Work at POS

When a POS session opens, `_check_before_creating_new_session()` on `pos.config` validates all loyalty programs assigned to that POS before the session can start. It enforces:

1. **Reward products must be `available_in_pos = True`** — if any product reward or gift card rule product is not available in POS, the session is blocked.
2. **Gift card program structural rules** — if the POS has gift card programs:
   - Must have exactly **one rule** and **one reward**
   - Rule must use **1 point per currency spent** (`reward_point_amount=1`, `reward_point_mode='money'`)
   - Reward must be a **1 currency per point discount** (`discount_mode='per_point'`, `discount=1`)
   - Must have a **mail template** if print reports are enabled
   - Must have a **print report** if print is enabled

`pos.config._get_program_ids()` returns all active loyalty programs valid for the current POS, filtering by:
- `pos_ok = True`
- POS config assignment (`pos_config_ids` or unassigned = all POS)
- Date range (`date_from`, `date_to`)
- Usage limits (`limit_usage`, `max_usage`)

---

## `loyalty.program` — Extended (from `loyalty` module)

> Parent model: `loyalty.loyalty_program` in `addons/loyalty/models/loyalty_program.py`

### POS-Added Fields

| Field | Type | Notes |
|---|---|---|
| `pos_config_ids` | M2M `pos.config` | POS restriction; empty = applies to all POS |
| `pos_order_count` | Integer (computed) | Count of POS orders using this program's rewards |
| `pos_ok` | Boolean | Defaults `True`; gates POS availability |
| `pos_report_print_id` | M2O `ir.actions.report` | Report for printing gift cards from POS |

### Key Methods

**`_load_pos_data(data)`** — sudo search_read of programs for this POS config's `_get_program_ids()`. Loaded fields: `name`, `trigger`, `applies_on`, `program_type`, `pricelist_ids`, `date_from`, `date_to`, `limit_usage`, `max_usage`, `total_order_count`, `is_nominative`, `portal_visible`, `portal_point_name`, `trigger_product_ids`, `rule_ids`, `reward_ids`.

**`_compute_pos_order_count()`** — SQL LATERAL JOIN query counting distinct POS orders using this program's reward lines.

**`_inverse_pos_report_print_id()`** — Automatically creates or updates a `loyalty.mail` communication plan entry when `pos_report_print_id` is set on gift card / ewallet programs. Requires `mail_template_id` to already exist.

**`_compute_total_order_count()`** — Aggregates `pos_order_count` into the base `total_order_count` (called by parent).

### L4: `applies_on` at POS

- `current`: Points/rewards applied immediately during the same order (e.g., promotions, buy-X-get-Y)
- `future`: A new `loyalty.card` coupon is generated for a future order (e.g., gift cards, next-order coupons)
- `both`: Points accumulate on a nominative card; rewards also claimable on current order (e.g., loyalty cards)

---

## `loyalty.rule` — Extended (from `loyalty` module)

> Parent model: `loyalty.loyalty_rule` in `addons/loyalty/models/loyalty_rule.py`

### POS-Added Fields

| Field | Type | Notes |
|---|---|---|
| `valid_product_ids` | M2M `product.product` (computed) | Products matching this rule's domain, filtered to `available_in_pos=True` |
| `any_product` | Boolean (computed) | `True` if rule applies to all products |
| `promo_barcode` | Char (computed) | Auto-generated barcode matching the promo code; used for scanning |

### Key Methods

**`_load_pos_data_domain(data)`** — Returns `[('program_id', 'in', config_id._get_program_ids().ids)]` — only rules belonging to this POS's programs are loaded.

**`_load_pos_data_fields(config_id)`** — Returns: `program_id`, `valid_product_ids`, `any_product`, `currency_id`, `reward_point_amount`, `reward_point_split`, `reward_point_mode`, `minimum_qty`, `minimum_amount`, `minimum_amount_tax_mode`, `mode`, `code`.

**`_compute_valid_product_ids()`** — Groups rules by product criteria and resolves the domain against `product.product`, filtering to `available_in_pos=True`. If no product filter exists, `any_product = True`.

**`_compute_promo_barcode()`** — Auto-generates a barcode from `_generate_code()` whenever `code` changes.

---

## `loyalty.reward` — Extended (from `loyalty` module)

> Parent model: `loyalty.loyalty_reward` in `addons/loyalty/models/loyalty_reward.py`

### POS-Added Behavior

**`_get_discount_product_values()`** — Sets `taxes_id: False` on discount line products created for POS rewards (no taxes on loyalty discounts).

**`_load_pos_data_domain(data)`** — Returns `[('program_id', 'in', config_id._get_program_ids().ids)]`.

**`_load_pos_data_fields(config_id)`** — Returns: `description`, `program_id`, `reward_type`, `required_points`, `clear_wallet`, `currency_id`, `discount`, `discount_mode`, `discount_applicability`, `all_discount_product_ids`, `is_global_discount`, `discount_max_amount`, `discount_line_product_id`, `reward_product_id`, `multi_product`, `reward_product_ids`, `reward_product_qty`, `reward_product_uom_id`, `reward_product_domain`.

**`_load_pos_data(data)`** — Search-read with domain, then calls `_replace_ilike_with_in()` on `reward_product_domain` — converts `ilike`/`not ilike` operators on many2one fields to `in`/`not in` with resolved IDs (required because POS JS cannot do name searches).

**`_get_reward_product_domain_fields(config_id)`** — Scans all reward `reward_product_domain` values and returns the set of product fields needed in the POS product data load.

**`unlink()`** — Instead of deleting, **archives** a reward if it has associated POS order lines.

---

## `loyalty.card` — Extended (from `loyalty` module)

> Parent model: `loyalty.loyalty_card` in `addons/loyalty/models/loyalty_card.py`

### POS-Added Fields

| Field | Type | Notes |
|---|---|---|
| `source_pos_order_id` | M2O `pos.order` | The POS order where this card/coupon was generated |

### Key Methods

**`_load_pos_data_domain(data)`** — Returns `[('program_id', 'in', [program["id"] for program in data["loyalty.program"]['data']])]` — loads only cards belonging to programs loaded for this POS.

**`_load_pos_data_fields(config_id)`** — Returns: `partner_id`, `code`, `points`, `program_id`, `expiration_date`, `write_date`.

**`_has_source_order()`** — Returns `True` if `source_pos_order_id` is set (used to determine if a card was generated at POS vs. imported).

**`_get_default_template()`** — Returns `pos_loyalty.mail_coupon_template` if `source_pos_order_id` is set; otherwise delegates to parent.

**`_get_mail_partner()`** — Falls back to `source_pos_order_id.partner_id` if no `partner_id` on the card.

**`_get_signature()`** — Falls back to `source_pos_order_id.user_id.signature`.

**`_compute_use_count()`** — Also counts POS order line usage via `_read_group` on `pos.order.line`.

---

## `pos.order` — Extended

### Key Methods

**`validate_coupon_programs(point_changes, new_codes) -> dict`** — Called when order is validated at POS (pre-commit check):

1. Verifies all coupon IDs still exist and are active
2. Checks `coupon.points >= -point_changes[coupon.id]` (sufficient points for redemption)
3. Checks no new_codes already exist in DB (prevents duplicate coupon codes)
4. Returns `{'successful': False, 'payload': {...}}` with `removed_coupons` or `updated_points` on failure

**`confirm_coupon_programs(coupon_data) -> dict`** — Called after order is created:

1. Calls `_check_existing_loyalty_cards()` — merges duplicate loyalty/ewallet cards for same partner+program
2. Calls `_remove_duplicate_coupon_data()` — skips if `loyalty.history` already exists for this order+program
3. Creates new `loyalty.card` records for coupons awarded by the order (negative IDs in coupon_data map to new cards)
4. Updates existing gift cards with new points balance
5. Links `pos.order.line` records to their `coupon_id` via `reward_identifier_code`
6. Sends creation emails via `_send_creation_communication()`
7. Adds `loyalty.history` lines for points won/spent
8. Returns coupon updates, program usage counts, new coupon info, and coupon reports to print

**`_check_existing_loyalty_cards(coupon_data)`** — For `loyalty` and `ewallet` programs, if the partner already has a card for the program, redirects the new coupon data to the existing card ID instead of creating a duplicate.

**`_remove_duplicate_coupon_data(coupon_data)`** — Prevents double-recording by checking if a `loyalty.history` line already exists for the same `(order_model, order_id, program_id)`.

**`_add_mail_attachment(name, ticket, basic_receipt)`** — Appends gift card PDF report attachments to order confirmation emails if the order generated gift cards with `pos_report_print_id`.

**`_get_fields_for_order_line()`** — Adds `is_reward_line`, `reward_id`, `coupon_id`, `reward_identifier_code`, `points_cost` to the fields exported to POS frontend.

---

## `pos.order.line` — Extended

| Field | Type | Description |
|---|---|---|
| `is_reward_line` | Boolean | `True` if this line is a reward line |
| `reward_id` | M2O `loyalty.reward` | The reward that generated this line |
| `coupon_id` | M2O `loyalty.card` | The coupon used to claim the reward |
| `reward_identifier_code` | Char | Groups multiple reward lines from the same reward action |
| `points_cost` | Float | How many points this reward cost on the coupon |

**`_is_not_sellable_line()`** — Returns `True` for reward lines, preventing them from being resold.

**`_load_pos_data_fields(config_id)`** — Adds loyalty fields to POS data.

---

## `pos.config` — Extended

### Key Methods

**`_get_program_ids() -> loyalty.program recordset`** — Returns all active loyalty programs for this POS:
- `pos_ok = True`
- POS config in `pos_config_ids` OR no POS assigned
- Within date range
- Within usage limits

**`_check_before_creating_new_session()`** — Validates gift card program structure and reward product availability before session opens. Raises `UserError` if invalid.

**`use_coupon_code(code, creation_date, partner_id, pricelist_id) -> dict`** — Validates a scanned/entered coupon code:
- Looks up `loyalty.card` by code within POS programs
- Checks expiration date, program date range, usage limits
- Checks `pricelist_ids` match
- For `promo_code` programs, verifies the code was applied (not just scanned)
- Returns program/coupon info or error message

---

## `pos.session` — Extended

**`_load_pos_data_models(config_id)`** — Adds to the base list: `loyalty.program`, `loyalty.rule`, `loyalty.reward`, `loyalty.card`. These models' data is pushed into the POS frontend session.

---

## `res.partner` — Extended

| Field | Type | Notes |
|---|---|---|
| `loyalty_card_count` | Integer | Count of loyalty cards for the partner (restricted to `base.group_user` and `point_of_sale.group_pos_user`) |

---

## `product.product` — Extended

**`_load_pos_data_fields(config_id)`** — Adds `all_product_tag_ids` and any product fields required by `loyalty.reward.reward_product_domain` that aren't already in the base product data.

**`_load_pos_data(data)`** — Additionally fetches and merges loyalty program reward products, trigger products (for gift card/ewallet programs), and discount line products into the POS product dataset, so they are available at POS even if not normally `available_in_pos`.

---

## `loyalty.mail` — Extended

| Field | Type | Notes |
|---|---|---|
| `pos_report_print_id` | M2O `ir.actions.report` | Print action for gift cards/coupons generated at POS |

---

## Barcode Integration

`barcode.rule` is extended with a new `type = 'coupon'` selection value. This allows coupon/gift card barcodes to be scanned at POS and routed to the loyalty system.

---

## Gift Card Validation at POS

Gift cards in Odoo 18 POS use a specific point-based currency model enforced by `pos.config._check_before_creating_new_session()`:

```
Rule:    1 point per 1 currency unit spent  → reward_point_amount=1, reward_point_mode='money'
Reward:  1 currency unit per 1 point         → discount_mode='per_point', discount=1
```

This means the gift card **behaves as a prepaid wallet**: each unit of currency spent loads 1 point; each point redeemed deducts 1 currency unit from the card balance.

Gift cards can be:
1. **Sold at POS** (generates a new `loyalty.card` with code, linked to `pos.order`)
2. **Redeemed at POS** (discount line applied, points deducted from card)
3. **Recharged** (if `gift_card_settings = 'scan_use'`): additional points added to an existing card

Gift card programs require both a mail template (for email delivery) and a print report (for in-store printing) if those channels are enabled.

---

## POS Loyalty vs. Standalone `loyalty` Module

| Aspect | `loyalty` (standalone) | `pos_loyalty` |
|---|---|---|
| Channel | eCommerce, sale orders | Point of Sale |
| Coupon entry | Manual / website | Scanned or entered at terminal |
| Point computation | Server-side on order confirmation | Real-time in POS JavaScript |
| Gift card printing | Not included | Print report attached to order email |
| Program data delivery | Not needed (server render) | Pushed to POS session via `pos.load.mixin` |
| `loyalty.history` | Records loyalty/ewallet usage | Also records POS order origin via `source_pos_order_id` |
| `res.partner` fields | No loyalty card count at POS | `loyalty_card_count` field with group-based access |

---

## L4: POS Loyalty Program Flow (End-to-End)

```
1. POS Session Opens
   └─ pos.config._check_before_creating_new_session() validates programs
   └─ pos.session._load_pos_data_models() adds loyalty models
   └─ pos_loyalty.models loaded into POS frontend: programs, rules, rewards, cards

2. Customer at POS
   └─ Loyalty card scanned → use_coupon_code() validates + returns card info
   └─ Points computed in JS against program rules
   └─ Reward lines added to order as pos.order.line (is_reward_line=True)

3. Order Payment / Validation
   └─ validate_coupon_programs() checks point balances + no duplicate codes
   └─ pos.order created (server-side)

4. Order Confirmation (after payment)
   └─ confirm_coupon_programs() executes:
       - Creates new loyalty.card for future-order programs (gift cards, coupons)
       - Updates gift card points (recharge scenario)
       - Links reward lines to coupon_id via reward_identifier_code
       - Creates loyalty.history entries
       - Sends email communications
       - Attaches gift card print reports to confirmation email
```

---

## Security Notes

- Gift card creation uses `sudo()` because POS users lack `loyalty.card` create permission
- `source_pos_order_id` on `loyalty.card` links the card to the originating POS order for audit trail
- `loyalty_card_count` on `res.partner` is group-restricted to `base.group_user` and `point_of_sale.group_pos_user`
- Adyen-specific HMAC validation in `pos_adyen` (not in `pos_loyalty`) ensures notification authenticity

---

## Related Documentation

- [Modules/Loyalty](modules/loyalty.md) — Base loyalty module
- [Modules/Point of Sale](modules/point-of-sale.md) — POS core module
- [Core/API](core/api.md) — @api.model, @api.depends decorators
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — State machine patterns

#odoo #odoo18 #pos_loyalty #loyalty #gift-cards #pos #coupons
