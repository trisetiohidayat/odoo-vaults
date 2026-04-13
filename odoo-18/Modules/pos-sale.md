---
Module: pos_sale
Version: Odoo 18
Type: Integration
Dependencies: point_of_sale, sale_management
---

# POS Sale Integration (`pos_sale`)

## Overview

`pos_sale` links the Point of Sale to the Sale Order management system. It enables two primary workflows:

1. **Quotation workflow**: A customer can select an existing sale order quotation at POS and pay a deposit (down payment) against it
2. **Immediate payment**: Products ordered at POS can optionally create or update sale orders linked to a sales team

**Key architectural role:**
- Extends `sale.order` and `sale.order.line` with POS reverse-link fields
- Extends `pos.order` and `pos.order.line` with sale order origin fields
- Extends `pos.config` and `pos.session` with sales team association
- Extends `stock.picking` to handle POS lines linked to sale order lines
- Overrides sale order computation fields (`amount_unpaid`, `qty_delivered`, `amount_invoiced`) to account for POS payments
- Automatically creates down payment sale order lines when a down payment product is sold at POS

---

## Module Structure

```
pos_sale/
├── models/
│   ├── pos_config.py       # crm_team_id, down_payment_product_id
│   ├── pos_order.py        # pos.order/pos.order.line extensions + sync logic
│   ├── sale_order.py       # sale.order/sale.order.line extensions + down payments
│   ├── pos_session.py      # pos.session: crm_team_id + loads sale.order/line
│   ├── crm_team.py        # crm.team: pos_config_ids, open session count
│   ├── stock_picking.py    # stock.picking: unreserve + create moves
│   ├── product_product.py  # product.product: invoice_policy, optional_products
│   └── res_config_settings.py # POS config settings wizard
└── __manifest__.py        # depends: point_of_sale, sale_management; auto_install: True
```

---

## `sale.order` — Extended

### POS-Added Fields

| Field | Type | Notes |
|---|---|---|
| `pos_order_line_ids` | O2M `pos.order.line` | POS lines linked to this sale order (readonly) |
| `pos_order_count` | Integer (computed) | Count of linked POS orders |
| `amount_unpaid` | Monetary (computed/stored) | `amount_total - (invoices_paid + pos_paid)` |

### Key Methods

**`_count_pos_order()`** — `pos_order_count = len(order.pos_order_line_ids.mapped('order_id'))`.

**`action_view_pos_order()`** — Returns an action window listing all linked POS orders.

**`_compute_amount_unpaid()`** — Stored computed field:

```
amount_unpaid = amount_total
             - sum(invoice_lines.price_total WHERE parent_state != 'cancel')
             - sum(pos_order_line_ids.price_subtotal_incl)
```

Prevents double-payment and double-invoicing by tracking what has already been paid at POS.

**`_compute_amount_to_invoice()`** — Subtracts POS order amounts from `amount_to_invoice` (POS payment counts as partial invoicing).

**`_compute_amount_invoiced()`** — For orders not fully invoiced, adds POS down payment amounts (only for lines that are `is_downpayment`) to `amount_invoiced`.

### POS Data Loading

**`_load_pos_data_domain(data)`** — Returns `[('pos_order_line_ids.order_id.state', '=', 'draft')]` — loads only quotations (draft sale orders) that have not yet been fully processed.

**`_load_pos_data_fields(config_id)`** — Loads: `name`, `state`, `user_id`, `order_line`, `partner_id`, `pricelist_id`, `fiscal_position_id`, `amount_total`, `amount_untaxed`, `amount_unpaid`, `picking_ids`, `partner_shipping_id`, `partner_invoice_id`, `date_order`, `write_date`.

---

## `sale.order.line` — Extended

### POS-Added Fields

| Field | Type | Notes |
|---|---|---|
| `pos_order_line_ids` | O2M `pos.order.line` | POS lines linked to this sale order line (readonly) |

### Key Methods

**`_load_pos_data_domain(data)`** — Returns `[('order_id', 'in', [sale_order_ids_from_data])]` — loads only lines belonging to sale orders already loaded for POS.

**`_load_pos_data_fields(config_id)`** — Loads: `discount`, `display_name`, `price_total`, `price_unit`, `product_id`, `product_uom_qty`, `qty_delivered`, `qty_invoiced`, `qty_to_invoice`, `display_type`, `name`, `tax_id`, `is_downpayment`, `write_date`.

**`_compute_qty_delivered()`** — For POS-linked sale lines:
- If all linked POS order pickings are `done`: converts POS line qty using `_convert_qty(sale_line, pos_line.qty, 'p2s')`
- Only affects non-service products

**`_compute_qty_invoiced()`** — Adds converted POS quantities to the invoiced quantity (same `'p2s'` conversion).

**`_get_sale_order_fields()`** — Returns the field list for `read_converted()`.

**`read_converted()`** — Reads sale order line fields and performs UoM conversion if sale line UoM differs from product UoM. Also extracts `lot_names` and `lot_qty_by_name` for tracked products.

**`_convert_qty(sale_line, qty, direction)`** — UoM conversion:
- `'s2p'`: sale line UoM → product UoM (`sale_line_uom._compute_quantity(qty, product_uom, False)`)
- `'p2s'`: product UoM → sale line UoM (`product_uom._compute_quantity(qty, sale_line_uom, False)`)

**`_compute_untaxed_amount_invoiced()`** — Adds `sum(pos_order_line_ids.price_subtotal)` to untaxed invoiced amount.

**`_get_downpayment_line_price_unit(invoices)`** — Adds POS down payment line `price_unit` to the down payment price computation.

**`unlink()`** — Protected: `sale.order.line` records that are `is_downpayment=True` and have `pos_order_line_ids` cannot be deleted from the sale order side.

---

## `pos.order` — Extended

### POS-Added Fields

| Field | Type | Notes |
|---|---|---|
| `currency_rate` | Float (computed/stored) | Conversion rate: `company.currency` → `order.currency` |
| `crm_team_id` | M2O `crm.team` | Sales team for this POS order |
| `sale_order_count` | Integer (computed) | Count of linked sale orders |

### Key Methods

**`_count_sale_order()`** — `sale_order_count = len(order.lines.mapped('sale_order_origin_id'))`.

**`_complete_values_from_session(session, values)`** — Sets `crm_team_id` from session's `config_id.crm_team_id` if not already provided.

**`_compute_currency_rate()`** — Uses `res.currency._get_conversion_rate()` at `date_order`.

**`sync_from_ui(orders)`** — The core sync method called when POS orders are submitted. Handles the full POS-to-Sale-order integration:

1. **Down payment creation**: For each POS line with the `down_payment_product_id` product:
   - Creates a down payment section (using `_prepare_down_payment_section_values`) if none exists
   - Creates a `sale.order.line` record on the linked sale order with `is_downpayment=True`
2. **Sale order confirmation**: If `order.state != 'draft'`, confirms all linked draft/sent sale orders
3. **Stock move demand update**: For each linked sale order line:
   - Flushes `qty_delivered` to DB
   - Computes `expected_qty_to_ship_later` from POS pickings
   - Updates `stock.move.product_uom_qty` for all related moves
   - Cancels pickings with zero `product_uom_qty`
   - Re-assigns pickings with remaining quantities

**`_prepare_invoice_vals()`** — When creating an invoice from a POS order linked to a sale order:
- Sets `team_id` from `crm_team_id`
- Sets `partner_shipping_id` from sale order (if differs from invoice address)
- Sets `invoice_payment_term_id` from sale order (unless early payment discount applies)
- Sets `partner_id` from `partner_invoice_id` if different

**`action_view_sale_order()`** — Returns an action window listing all linked sale orders.

**`_get_fields_for_order_line()`** — Adds `sale_order_origin_id`, `down_payment_details`, `sale_order_line_id` to POS line export.

**`_prepare_order_line(order_line)`** — Formats `sale_order_origin_id` and `sale_order_line_id` as `{id, name}` dicts for POS serialization.

**`_get_invoice_lines_values(line_values, pos_line)`** — If `pos_line.sale_order_origin_id`, copies the sale order line's description and analytic distribution to the invoice line.

**`write(vals)`** — Ensures `crm_team_id` is defaulted from session config if not explicitly set.

---

## `pos.order.line` — Extended

| Field | Type | Notes |
|---|---|---|
| `sale_order_origin_id` | M2O `sale.order` | The sale order this line originates from |
| `sale_order_line_id` | M2O `sale.order.line` | The specific sale order line |
| `down_payment_details` | Text | Stores down payment context for display |
| `qty_delivered` | Float | Computed from picking state; `copy=False` |

### `_compute_qty_delivered()` Logic

For POS lines in `paid`/`done`/`invoiced` orders:
- If `outgoing_pickings.done` exist AND `order.shipping_date` is set: uses POS qty, tracking remaining quantities per product across lines (FIFO-style for split deliveries)
- If `outgoing_pickings.done` exist but no `shipping_date`: fully delivered (entire qty)
- Otherwise: `qty_delivered = 0`

### `_launch_stock_rule_from_pos_order_lines()`

Called during stock move creation. Cancels any upstream stock moves (`_rollup_move_origs()`) for sale order lines before creating new moves from POS — prevents double-reservation of stock.

### `_load_pos_data_fields(config_id)`

Adds `sale_order_origin_id`, `sale_order_line_id`, `down_payment_details` to POS data.

---

## `pos.config` — Extended

| Field | Type | Notes |
|---|---|---|
| `crm_team_id` | M2O `crm.team` | Sales team assigned to this POS; propagates to orders and sessions |
| `down_payment_product_id` | M2O `product.product` | Product used for POS down payments on sale orders |

### Key Methods

**`_get_special_products()`** — Includes all POS down payment products (from all POS configs) in the special products list for POS session loading.

**`_ensure_downpayment_product()`** — Post-init hook that sets the default down payment product on `pos_config_main`.

**`load_onboarding_furniture_scenario()`** — Adds `_ensure_downpayment_product()` call to the onboarding scenario.

---

## `pos.session` — Extended

| Field | Type | Notes |
|---|---|---|
| `crm_team_id` | M2O `crm.team` (related) | Mirrors `config_id.crm_team_id` |

**`_load_pos_data_models(config_id)`** — Adds `sale.order` and `sale.order.line` to the models loaded into the POS session.

---

## `stock.picking` — Extended

### Method Override

**`_create_move_from_pos_order_lines(lines)`** — Customizes which POS order lines generate stock moves:

```python
def _create_move_from_pos_order_lines(self, lines):
    lines_to_unreserve = self.env['pos.order.line']
    for line in lines:
        # Skip lines with a future shipping date (handled separately)
        if line.order_id.shipping_date:
            continue
        # Skip lines where POS warehouse differs from sale line warehouse
        if any(wh != line.order_id.config_id.warehouse_id
               for wh in line.sale_order_line_id.move_ids.location_id.warehouse_id):
            continue
        lines_to_unreserve |= line

    # Unreserve stock for sale order lines that will now be fulfilled by POS
    lines_to_unreserve.sale_order_line_id.move_ids\
        .filtered(lambda ml: ml.state not in ['cancel', 'done'])\
        ._do_unreserve()

    # Only create moves for lines that have valued moves OR no sale order line at all
    return super()._create_move_from_pos_order_lines(
        lines.filtered(
            lambda l: not l.sale_order_line_id
            or (l.sale_order_line_id.has_valued_move_ids()
                or not l.sale_order_line_id.move_ids)
        )
    )
```

**L4 — Why unreserve:**
When a product ordered in a sale order is instead delivered via POS (not the regular warehouse picking), the original stock reservation from the sale order's moves must be freed. Otherwise the system would try to reserve stock twice.

**L4 — `has_valued_move_ids()` check:**
If the sale order line already has valued (stockable, non-zero value) moves, those are used and no new moves are created from the POS line.

---

## `crm.team` — Extended

| Field | Type | Notes |
|---|---|---|
| `pos_config_ids` | O2M `pos.config` | POS configs linked to this sales team |
| `pos_sessions_open_count` | Integer (computed) | Count of open POS sessions across all configs in this team |
| `pos_order_amount_total` | Float (computed) | Sum of `price_total` from open session POS orders |

**`_compute_pos_sessions_open_count()`** — `search_count` for `state='opened'` sessions.

**`_compute_pos_order_amount_total()`** — `_read_group` on `report.pos.order` grouped by `config_id`, summing `price_total`, filtered to open sessions and team's POS configs.

---

## `product.product` — Extended

**`_load_pos_data_fields(config_id)`** — Adds `invoice_policy`, `optional_product_ids`, `type` to POS product data.

**`get_product_info_pos(price, quantity, pos_config_id)`** — Adds `optional_products` to product info response:
- Filters `optional_product_ids` through `_optional_product_pos_domain()`
- Returns list: `[{name, price}]` for each optional product

**`_optional_product_pos_domain()`** — Domain: `sale_ok=True`, `available_in_pos=True`, correct company.

---

## L4: POS Quotation vs. Immediate Payment

| Scenario | Sale Order Behavior | POS Behavior |
|---|---|---|
| Pay quotation deposit | POS loads quotation; creates `sale.order.line` with `is_downpayment=True` | Order linked to SO; partial payment recorded |
| Pay full quotation | Above + order confirmed when POS order state != 'draft' | Full SO amount considered paid in `amount_unpaid` |
| Immediate POS sale (no SO) | No sale order created | Normal POS flow |
| Refund on POS (linked to SO) | Original SO line credited | `refunded_orderline_id.sale_order_origin_id` tracked |

---

## L4: Down Payment Flow at POS

```
Customer: I want to order 10 units of Product X for next month
Salesperson: Creates sale.order (quotation) with 10 units
Customer today: Pays $50 deposit at POS

At POS:
  1. Salesperson searches sale.order (draft quotation)
  2. Loads quotation into POS session
  3. Adds down payment line ($50)
  4. Collects payment via payment terminal
  5. POS order synced → sync_from_ui() called

sync_from_ui() results:
  - sale.order.line created with is_downpayment=True
  - sale.order confirmed (if order.state != 'draft')
  - amount_unpaid recalculated: total - $50 deposit
  - stock.move.product_uom_qty updated (qty_delivered from POS if applicable)

Later: Sale order invoiced
  - Down payment line is credited in invoice
  - amount_invoiced includes the $50 POS deposit
```

---

## `amount_unpaid` Computation

```
sale.order.amount_unpaid =

    amount_total
  - Σ(order_line.invoice_lines.price_total WHERE parent_state != 'cancel')
  - Σ(pos_order_line_ids.price_subtotal_incl)
```

This prevents:
- Double payment: customer cannot pay at POS + invoice again
- Double invoicing: invoice for the full amount when a POS deposit was already paid

---

## Security

- `pos_order_line_ids` and `pos_order_count` on `sale.order` are group-restricted to `point_of_sale.group_pos_user`
- `sale_order_origin_id` on `pos.order.line` is not group-restricted (accessible to sales team)
- `crm_team_id` on `pos.order` and `pos.session` allows sales analytics per team

---

## Related Documentation

- [Modules/Sale](modules/sale.md) — Sale management module
- [Modules/Point of Sale](modules/point-of-sale.md) — POS core
- [Modules/Stock](modules/stock.md) — Stock picking and move management
- [Core/API](core/api.md) — Computed fields, `@api.depends`, `@api.model`
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — Sale order state machine

#odoo #odoo18 #pos_sale #sale-order #down-payment #pos #crm-team
