# POS Loyalty Module (pos_loyalty)

## Overview

The `pos_loyalty` module integrates loyalty programs, gift cards, and e-wallets into the Point of Sale. It extends the base loyalty module with POS-specific data loading, coupon validation, and order-level reward application.

## Key Models

### loyalty.program (pos_loyalty Extension)

Extends `loyalty.program` with POS-specific fields and data loading.

**Additional Fields:**
- `pos_config_ids`: Many2many - POS configurations where this program is available
- `pos_order_count`: Integer - Number of POS orders using this program (computed via raw SQL)
- `pos_ok`: Boolean - Whether this program is available in POS (default: True)
- `pos_report_print_id`: Many2one - Report action for printing gift cards from POS

**Key Methods:**

- `_load_pos_data_domain(data)`: Filters programs to only those linked to the current POS config via `_get_program_ids()`.
- `_load_pos_data(data)`: Returns all programs for the POS via sudo, including `rule_ids` and `reward_ids` for full client-side evaluation.
- `_compute_pos_config_ids()`: Auto-clears `pos_config_ids` when `pos_ok` is disabled.
- `_compute_pos_order_count()`: Uses a raw SQL LATERAL JOIN query to count distinct POS orders per program by joining through `loyalty_reward` and `pos_order_line`.
- `_compute_total_order_count()`: Combines eCommerce and POS order counts into `total_order_count`.
- `_inverse_pos_report_print_id()`: When setting a POS report print action for gift_card/ewallet programs, requires `mail_template_id` to be set first. Creates or updates a `loyalty.mail` communication plan entry with trigger `create`.

### loyalty.rule (pos_loyalty Extension)

Extends `loyalty.rule` with POS data loading and valid product computation.

**Additional Fields:**
- `valid_product_ids`: Many2many - Computed products valid for this rule (only those available in POS)
- `any_product`: Boolean - Whether all products match (technical field)
- `promo_barcode`: Char - Auto-generated barcode alternative to the promo code

**Key Methods:**

- `_load_pos_data_domain(data)`: Filters rules to programs available in the current POS.
- `_load_pos_data_fields(config_id)`: Returns fields needed by the POS client: `program_id`, `valid_product_ids`, `any_product`, `currency_id`, point modes, minimum quantities/amounts, mode, and `code`.
- `_compute_valid_product_ids()`: Computes the set of valid products based on `product_ids`, `product_category_id`, `product_tag_id`, and `product_domain`. Adds `available_in_pos = True` domain filter and excludes archived products. Uses grouping to optimize multi-rule computation.
- `_compute_promo_barcode()`: Auto-generates a barcode using `loyalty.card._generate_code()` whenever the rule's `code` field changes.

### loyalty.reward (pos_loyalty Extension)

Extends `loyalty.reward` with POS data loading, domain parsing, and discount product handling.

**Key Methods:**

- `_load_pos_data_domain(data)`: Filters rewards to programs available in the current POS.
- `_load_pos_data(data)`: Returns rewards with their fields including `reward_product_domain` (with `ilike` operators replaced by `in` for client-side performance).
- `_load_pos_data_fields(config_id)`: Returns all reward fields including `description`, `reward_type`, `required_points`, discount details, `reward_product_ids`, and `reward_product_domain`.
- `_get_reward_product_domain_fields(config_id)`: Inspects `reward_product_domain` across all rewards to determine which product fields need to be loaded into the POS (extracts field names from the JSON domain).
- `_replace_ilike_with_in(domain_str)`: Converts `ilike`/`not ilike` operators in product domains to `in`/`not in` with pre-resolved IDs. This is critical for client-side performance since the POS JS cannot run `ilike` searches.
- `_get_discount_product_values()`: Overrides the base method to set `taxes_id: False` on discount products used in POS (to avoid tax complications at the POS level).
- `unlink()`: Instead of deleting rewards that have been used in POS order lines, archives them (`action_archive()`) to preserve history.

### loyalty.card (pos_loyalty Extension)

Extends `loyalty.card` with POS source tracking and POS-specific data loading.

**Additional Fields:**
- `source_pos_order_id`: Many2one - POS order that generated this card (for cards awarded at POS)

**Key Methods:**

- `_load_pos_data_domain(data)`: Filters cards to those belonging to programs loaded in the current POS.
- `_load_pos_data_fields(config_id)`: Returns `partner_id`, `code`, `points`, `program_id`, `expiration_date`, `write_date`.
- `_has_source_order()`: Returns True if the card has either a base loyalty source OR a `source_pos_order_id` (POS-sourced card).
- `_get_default_template()`: For POS-sourced cards, uses the `pos_loyalty.mail_coupon_template` email template instead of the standard coupon template.
- `_get_mail_partner()`: Returns the partner from `source_pos_order_id.partner_id` if available, otherwise falls back to the standard method.
- `_get_signature()`: Uses the POS order's cashier signature if available.
- `_compute_use_count()`: Adds POS order line usage count to the base use count (via `pos.order.line` grouped by `coupon_id`).

### pos.order (pos_loyalty Extension)

Extends `pos.order` with loyalty coupon validation, award, and history tracking.

**Key Methods:**

- `validate_coupon_programs(point_changes, new_codes)`: Called at order validation time.
  - Validates that all coupon IDs in `point_changes` exist and belong to active programs
  - Checks that each coupon has sufficient points for the rewards being claimed
  - Checks that no new coupon codes conflict with existing codes in the database
  - Returns `{'successful': False, 'payload': {...}}` with error details, or `{'successful': True}` on success

- `add_loyalty_history_lines(coupon_data, coupon_updates)`: Creates `loyalty.history` records for points issued and spent during this order.

- `confirm_coupon_programs(coupon_data)`: Called after order creation to finalize loyalty operations.
  - `_check_existing_loyalty_cards()`: For loyalty/ewallet programs, merges duplicate coupons (same partner + program)
  - Creates new `loyalty.card` records for coupons awarded by the order (gift cards, loyalty rewards)
  - Updates gift card points for `scan_use` gift cards
  - Links newly created coupons to their order lines via `reward_identifier_code`
  - Sends creation emails for new coupons
  - Triggers POS report printing for gift card programs
  - Adds loyalty history lines
  - Returns coupon updates, program usage counts, and new coupon info for the receipt

- `_check_existing_loyalty_cards(coupon_data)`: Prevents duplicate loyalty/ewallet cards by finding and merging existing cards for the same partner and program.

- `_remove_duplicate_coupon_data(coupon_data)`: Removes coupon data entries for which a `loyalty.history` line already exists (prevents double-processing on order update).

- `_get_fields_for_order_line()`: Adds loyalty-specific fields: `is_reward_line`, `reward_id`, `coupon_id`, `reward_identifier_code`, `points_cost`.

- `_add_mail_attachment(name, ticket, basic_receipt)`: Attaches gift card PDF reports to order confirmation emails when the program has a POS report print action configured.

## Cross-Module Relationships

- **point_of_sale**: Core POS order, order line, and session models
- **loyalty**: Base loyalty card, reward, rule, and program models
- **loyalty_mail**: Communication plan entries linking mail templates and POS print reports to loyalty programs

## Edge Cases

1. **POS-Sourced Loyalty Cards**: Cards generated at the POS (e.g., gift cards sold) are tracked via `source_pos_order_id`. This is used for email routing, signature sourcing, and source tracking.
2. **Duplicate Loyalty Card Merging**: For loyalty and ewallet programs, if a partner already has a card for a program and uses it again, the existing card is used/updated instead of creating a new one.
3. **Archive Instead of Delete**: Loyalty rewards used in POS orders cannot be deleted; they are archived to preserve data integrity.
4. **ilike to in Conversion**: The POS client cannot execute `ilike` domain operators on product names. `_replace_ilike_with_in()` pre-resolves matching product IDs server-side for client-side product domain evaluation.
5. **Gift Card Program Types**: Programs with `program_type == 'gift_card'` or `'ewallet'` get special handling: they don't print coupon codes on receipts, and gift card programs can have a POS report print action for printing physical gift cards.
6. **Negative Coupon IDs**: In `confirm_coupon_programs`, negative coupon IDs in `coupon_data` indicate newly created coupons (created in the same order). The method maps negative IDs to newly created record IDs.
7. **Loyalty Points Tracking**: Points are tracked via `loyalty.history` entries created per order, recording both `issued` (positive) and `used` (negative) amounts.
8. **Discount Product Tax Handling**: POS discount products are created with no taxes (`taxes_id: False`) to avoid double-tax computation since discounts are applied before tax calculation in POS.
