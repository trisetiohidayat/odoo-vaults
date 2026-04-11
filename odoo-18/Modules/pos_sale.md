# POS Sale Module (pos_sale)

## Overview

The `pos_sale` module links Point of Sale orders with Sale Orders, enabling unified sales tracking across both channels. It allows POS orders to be linked to existing sale orders, handles down payments from POS, and synchronizes delivery picking quantities.

## Key Models

### sale.order (pos_sale Extension)

Extends `sale.order` with POS order line tracking and POS-specific computation.

**Additional Fields:**
- `pos_order_line_ids`: One2many - POS order lines that originate from this sale order (via `sale_order_origin_id`)
- `pos_order_count`: Integer - Number of linked POS orders (computed)
- `amount_unpaid`: Monetary - Amount left to pay in POS (total minus invoice and POS payments)

**Key Methods:**

- `_count_pos_order()`: Counts distinct POS orders linked via `pos_order_line_ids.mapped('order_id')`.
- `action_view_pos_order()`: Opens a list/form view of all POS orders linked to this sale order.
- `_compute_amount_unpaid()`: Computes `amount_unpaid = amount_total - (total_invoice_paid + total_pos_paid)`.
  - `total_invoice_paid`: sum of invoiced line totals (non-cancelled invoice lines)
  - `total_pos_paid`: sum of POS line `price_subtotal_incl` from linked POS order lines
- `_compute_amount_to_invoice()`: Subtracts POS order line amounts from `amount_to_invoice` to avoid double-counting.
- `_compute_amount_invoiced()`: Adds POS down payment line amounts to `amount_invoiced` for down payments marked as paid in POS.
- `_load_pos_data_domain(data)`: Filters to sale orders that have draft POS orders (draft POS orders indicate the sale is still being processed at POS).
- `_load_pos_data_fields(config_id)`: Returns full order data including `name`, `state`, `user_id`, `order_line`, `partner_id`, `pricelist_id`, `fiscal_position_id`, `amount_total`, `amount_untaxed`, `amount_unpaid`, `picking_ids`, `partner_shipping_id`, `partner_invoice_id`, `date_order`, `write_date`.

### sale.order.line (pos_sale Extension)

Extends `sale.order.line` with POS order line tracking.

**Additional Fields:**
- `pos_order_line_ids`: One2many - POS order lines linked to this sale order line

**Key Methods:**

- `_load_pos_data_domain(data)`: Filters sale order lines to those belonging to sale orders already loaded (via `sale.order` data).
- `_load_pos_data_fields(config_id)`: Returns line fields for POS: `discount`, `display_name`, `price_total`, `price_unit`, `product_id`, `product_uom_qty`, `qty_delivered`, `qty_invoiced`, `qty_to_invoice`, `display_type`, `name`, `tax_id`, `is_downpayment`, `write_date`.
- `_compute_qty_delivered()`: Adds to the base computation the quantity delivered from POS orders. Considers only POS orders in `paid`/`done`/`invoiced` state, and only when all pickings are `done`.
- `_compute_qty_invoiced()`: Adds to the base computation the quantity invoiced from POS orders (in `paid`/`done`/`invoiced` state).
- `_compute_untaxed_amount_invoiced()`: Adds `price_subtotal` from POS order lines.
- `read_converted()`: Reads sale line data with UoM conversion. Handles `lot_names` and `lot_qty_by_name` for tracked products, merges line notes from display lines.
- `_convert_qty(sale_line, qty, direction)`: Converts quantity between sale line UoM and product UoM.
  - `s2p`: sale line UoM to product UoM
  - `p2s`: product UoM to sale line UoM
- `_get_sale_order_fields()`: Returns the list of fields included in `read_converted()`.
- `_get_downpayment_line_price_unit(invoices)`: Adds POS down payment amounts to the down payment line price unit computation.
- `unlink()`: Preserves downpayment lines that have POS order line references (prevents deleting deposit lines from POS).

### pos.order (pos_sale Extension)

Extends `pos.order` with sale order linkage, currency rate, and CRM team assignment.

**Additional Fields:**
- `crm_team_id`: Many2one - Sales team assigned from the POS config
- `sale_order_count`: Integer - Number of linked sale orders (computed)
- `currency_rate`: Float - Stored currency conversion rate (computed at order creation)

**Key Methods:**

- `_count_sale_order()`: Counts distinct sale orders via `lines.mapped('sale_order_origin_id')`.
- `_complete_values_from_session(session, values)`: Sets `crm_team_id` from the session's POS config.
- `_compute_currency_rate()`: Recomputes the currency rate from the order's date using `res.currency._get_conversion_rate()`.
- `_prepare_invoice_vals()`: Merges sale order details into the POS invoice:
  - Sets `team_id` from `crm_team_id`
  - Sets `partner_shipping_id` from the sale order's shipping address (if different from invoice address)
  - Sets `invoice_payment_term_id` from the sale order's payment terms (unless early payment discount applies)
  - Overrides `partner_id` with the sale order's invoice address if different
- `sync_from_ui(orders)`: Called when POS orders are synced from the frontend. Handles complex sale order synchronization:
  - For down payment lines linked to a sale order: creates a down payment section and a `sale.order.line` with `is_downpayment=True`
  - Confirms draft sale orders linked to paid POS order lines
  - Updates stock move quantities: recalculates `product_uom_qty` on stock moves for waiting/confirmed/assigned pickings based on POS quantities
  - Cancels or reassigns pickings where all move quantities are zero
  - Flushes recordsets to ensure computed quantities are persisted before updating stock moves
- `action_view_sale_order()`: Opens a list/form view of all sale orders linked to this POS order.
- `_get_fields_for_order_line()`: Adds `sale_order_origin_id`, `down_payment_details`, `sale_order_line_id` to order line fields.
- `_prepare_order_line(order_line)`: Normalizes `sale_order_origin_id` and `sale_order_line_id` from x2many command format to id dicts.
- `_get_invoice_lines_values(line_values, pos_line)`: Uses the sale order line's name and analytic distribution for invoiced lines from a sale order origin.
- `write(vals)`: Ensures `crm_team_id` is set from the session config if not provided.
- `_launch_stock_rule_from_pos_order_lines()`: Cancels upstream stock moves when POS order lines linked to sale orders are cancelled/deleted.

### pos.order.line (pos_sale Extension)

Extends `pos.order.line` with sale order line linkage.

**Additional Fields:**
- `sale_order_origin_id`: Many2one - The sale order from which this line originates
- `sale_order_line_id`: Many2one - The specific sale order line
- `down_payment_details`: Text - Details about down payment for display
- `qty_delivered`: Float - Computed delivery quantity

**Key Methods:**

- `_compute_qty_delivered()`: Computes the quantity delivered from POS order lines:
  - If a `shipping_date` is set: distributes quantity across outgoing pickings based on product matching
  - If no shipping date but pickings exist in `done` state: full quantity is delivered
  - Otherwise: zero
- `_load_pos_data_fields(config_id)`: Adds `sale_order_origin_id`, `sale_order_line_id`, `down_payment_details` to the loaded fields.

## Cross-Module Relationships

- **sale**: Sale order and order line models form the origin of POS-downpayment flows
- **point_of_sale**: Core POS order and order line models
- **crm**: CRM sales team assigned from POS config to orders and invoices
- **stock**: Stock pickings are updated based on POS quantities for linked sale order lines

## Edge Cases

1. **Down Payment Creation**: When a POS order contains a product linked to a sale order (e.g., a deposit), `sync_from_ui` creates a down payment section and a `sale.order.line` with `is_downpayment=True` on the origin sale order. This is done even for partial refunds (qty < 0).
2. **Currency Rate Storage**: The `currency_rate` is stored on the POS order at creation time using `_get_conversion_rate()`. This ensures consistent reporting even if exchange rates change later.
3. **Sale Order Confirmation**: Sale orders are auto-confirmed when a POS order is finalized (state != draft), even if the sale order was in draft/sent state.
4. **Stock Move Quantity Updates**: For sale orders with assigned pickings, POS quantities are propagated back to stock moves. This handles partial deliveries and multi-step delivery scenarios.
5. **Waiting Picking Cancellation**: If POS order lines deplete a sale order's demand completely, the waiting/confirmed pickings are cancelled. Otherwise, `action_assign()` is called to re-reserve.
6. **Shipping Date Distribution**: When a POS order has a `shipping_date`, the quantity delivered is distributed across pickings based on product matching and running totals (`product_qty_left_to_assign`).
7. **Invoice Partner Override**: The POS order's invoice is created with the sale order's invoice partner (not the POS partner), ensuring the correct accounting entry.
8. **Multiple Sale Orders**: A single POS order can reference multiple sale orders via different lines. All are handled together in `sync_from_ui`.
