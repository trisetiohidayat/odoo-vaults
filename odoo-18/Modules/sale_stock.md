# sale_stock — Sale Stock

**Tags:** #odoo #odoo18 #sale #stock #logistics
**Odoo Version:** 18.0
**Module Category:** Sale + Stock Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_stock` bridges the Sale Order and Stock modules in Odoo 18. It handles SO-to-picking propagation, delivery commitments, MTO (Make to Order) procurement, Anglo-Saxon accounting integration, and stock-driven delivery status tracking.

**Technical Name:** `sale_stock`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_stock/`
**Inherits From:** `sale`, `stock`
**Depends:** `sale`, `stock`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/sale_order.py` | `sale.order` | Delivery commitments, effective dates, warehouse, incoterm |
| `models/sale_order_line.py` | `sale.order.line` | Stock-based qty delivered, MTO route, qty widgets |
| `models/account_move.py` | `account.move` | COGS journal entries, downpayment handling, lot tracking |
| `models/account_move_line.py` | `account.move.line` | Anglo-Saxon price unit, reinvoice checks |
| `models/stock.py` | `stock.move`, `stock.picking`, `stock.lot`, `stock.route`, `procurement.group`, `stock.rule` | Sale-picking links, auto-create SOLs, lot-sale tracking |
| `models/stock_valuation_layer.py` | `stock.valuation.layer` | Related product preference |
| `models/stock_warehouse.py` | `stock.warehouse` | Cross-dock route sale_selectable |
| `models/res_config_settings.py` | `res.config.settings` | Security lead, picking policy |
| `models/res_users.py` | `res.users` | Property warehouse |
| `models/res_company.py` | `res.company` | Security lead |
| `models/product_template.py` | `product.template` | Expense policy, service type overrides |

---

## Models Reference

### `sale.order` (models/sale_order.py)

#### Additional Fields

| Field | Type | Compute/Store | Decorators | Notes |
|-------|------|---------------|------------|-------|
| `incoterm` | Many2one | Yes | — | Incoterms (sale.incoterms) |
| `incoterm_location` | Char | Yes | — | Incoterm delivery location |
| `picking_policy` | Selection | Yes | — | 'direct' or 'one' |
| `warehouse_id` | Many2one | Yes (store) | — | Default warehouse |
| `picking_ids` | One2many | Yes | — | `stock.picking` linked to SO |
| `delivery_count` | Integer | Yes | — | Count of pickings |
| `delivery_status` | Selection | Yes (store) | — | 'new', 'partial', 'done', 'cancel' |
| `procurement_group_id` | Many2one | Yes | — | Procurement group |
| `effective_date` | Datetime | Yes | — | When first delivery was done |
| `expected_date` | Datetime | Yes | — | Customer promised date |
| `json_popover` | Json | Yes | — | Delivery popover data |
| `show_json_popover` | Boolean | Yes | — | Show popover flag |

#### Methods

| Method | Decorators | Behavior |
|--------|-----------|----------|
| `_init_column('warehouse_id')` | `@api.model` | Sets default warehouse_id from user property |
| `_compute_effective_date()` | `@api.depends` | Sets effective_date to date of first done picking |
| `_compute_delivery_status()` | `@api.depends` | Computes 'new'/'partial'/'done'/'cancel' based on picking states |
| `_compute_expected_date()` | `@api.depends` | Sets expected_date = max commitment_date of SOLs |
| `_select_expected_date()` | `@api.depends` | Helper for expected_date |
| `_check_warehouse()` | `@api.constrains` | Validates warehouse consistency |
| `write(vals)` | — | Propagates commitment_date to stock moves, logs delivery changes |
| `_compute_json_popover()` | `@api.depends` | Builds popover with qty status |
| `_action_confirm()` | — | Calls `_action_confirm` on lines (launches stock rules) |
| `_compute_picking_ids()` | `@api.depends` | Links pickings via procurement group |
| `_compute_warehouse_id()` | `@api.depends` | Determines warehouse from company/partner |
| `_onchange_partner_shipping_id()` | `@api.onchange` | Syncs warehouse from partner |
| `action_view_delivery()` | — | Returns action for delivery picking tree |
| `_action_cancel()` | — | Cascades cancel to pickings |
| `_get_action_view_picking()` | — | Returns action for picking list |
| `_prepare_invoice()` | — | Adds incoterm + effective_date to invoice vals |
| `_log_decrease_ordered_quantity()` | — | Logs note on SO when qty decreases |

---

### `sale.order.line` (models/sale_order_line.py)

#### Additional Fields

| Field | Type | Compute/Store | Decorators | Notes |
|-------|------|---------------|------------|-------|
| `qty_delivered_method` | Selection | Yes | `@api.depends` | Adds 'stock_move' option |
| `route_id` | Many2one | — | — | MTO/custom route |
| `move_ids` | One2many | — | — | Stock moves linked to SOL |
| `virtual_available_at_date` | Float | Yes | `@api.depends` | Forecast stock |
| `scheduled_date` | Datetime | Yes | `@api.depends` | Move scheduled date |
| `forecast_expected_date` | Datetime | Yes | `@api.depends` | Forecast arrival |
| `free_qty_today` | Float | Yes | `@api.depends` | Immediately available qty |
| `qty_available_today` | Float | Yes | `@api.depends` | Qty at end of today |
| `warehouse_id` | Many2one | Yes | `@api.depends` | Line warehouse |
| `qty_to_deliver` | Float | Yes | `@api.depends` | Total qty to deliver |
| `is_mto` | Boolean | Yes (store) | `@api.depends` | MTO route flag |
| `display_qty_widget` | Boolean | Yes | `@api.depends` | Show qty widget |
| `is_storable` | Boolean | Yes (related) | — | From product |
| `customer_lead` | Float | — | — | Lead time days |

#### Methods

| Method | Decorators | Behavior |
|--------|-----------|----------|
| `_compute_qty_delivered_method()` | `@api.depends` | Returns 'stock_move' for storable products |
| `_compute_qty_delivered()` | `@api.depends` | Sums move quantities for stock_move deliveries |
| `_action_launch_stock_rule()` | — | Creates procurements for stock moves |
| `_prepare_procurement_values()` | — | Builds vals dict: route, warehouse, partner, packaging, deadline |
| `_get_location_final()` | — | Gets final destination location |
| `_get_outgoing_incoming_moves()` | — | Filters moves by direction |
| `_get_procurement_group()` | — | Gets or creates procurement group |
| `_prepare_procurement_group_vals()` | — | Creates group with sale_id |
| `_create_procurements()` | — | Runs stock.rule `_procurement_configure` |
| `_update_line_quantity()` | — | Updates procurement qty |
| `_get_action_add_from_catalog_extra_context()` | — | Extra context for catalog add |
| `_get_product_catalog_lines_data()` | — | Returns catalog data dict |

---

### `stock.move` (models/stock.py — StockMove class)

| Field | Type | Notes |
|-------|------|-------|
| `sale_line_id` | Many2one (`sale.order.line`) | Link to sale line, index btree_not_null |

#### Methods

| Method | Behavior |
|--------|----------|
| `_prepare_merge_moves_distinct_fields()` | Adds `sale_line_id` to merge fields |
| `_get_related_invoices()` | Returns posted invoices from sale order |
| `_get_source_document()` | Prefers sale order over generic source |
| `_assign_picking_post_process()` | Posts message linking picking to sale order |
| `_get_all_related_sm(product)` | Includes moves with matching sale_line_id product |

---

### `stock.picking` (models/stock.py — StockPicking class)

| Field | Type | Notes |
|-------|------|-------|
| `sale_id` | Many2one (`sale.order`) | Computed from `group_id.sale_id`, inverse supported, index btree_not_null |

| Method | Behavior |
|--------|----------|
| `_compute_sale_id()` | Reads `group_id.sale_id` |
| `_set_sale_id()` | Writes to group or creates new procurement group |
| `_auto_init()` | Creates `sale_id` column if missing |
| `_action_done()` | Auto-creates SOLs for delivered products not on SO |
| `_log_less_quantities_than_expected()` | Logs note on SO for qty variances |
| `_can_return()` | Allows return if linked to SO |

---

### `stock.lot` (models/stock.py — StockLot class)

| Field | Type | Notes |
|-------|------|-------|
| `sale_order_ids` | Many2many (`sale.order`) | Computed from move lines |
| `sale_order_count` | Integer | Count of related sale orders |

| Method | Behavior |
|--------|----------|
| `_compute_sale_order_ids()` | Searches done move lines with lot, filters by customer/transit dest |

---

## Security File: `security/sale_stock_security.xml`

**Groups:** `sale_stock.group_sale_stock_rules`
- ACL `sale.order`: read, write, create, unlink (if `sale.group_sale_order_manager`)
- ACL `stock.picking`: read, write, create, unlink (if `stock.group_stock_manager`)
- ACL `stock.move`: read, write (if `stock.group_stock_manager`)
- ACL `procurement.group`: read, write

---

## Data Files

| File | Content |
|------|---------|
| `data/sale_stock_data.xml` | Default `property_warehouse_for_sale_order` on `res.users` |
| `data/stock_data.xml` | Route: `route_warehouse0_mto_pull` (MTO pull rule) |
| `data/ir_rule.xml` | Record rules for procurement groups by company |

---

## Critical Behaviors

1. **MTO Procurement**: Lines with `route_id` pointing to MTO route create procurements that generate stock moves linked back to the SOL via `sale_line_id`.

2. **Auto-SOL Creation on Delivery** (`_action_done`): When a picking linked to a sale order is validated, if a stock move has no `sale_line_id` and is going to customer/transit (not returned), a new SOL is auto-created for that product with `qty_delivered` set.

3. **Downpayment Handling**: `account_move.py` overrides `_stock_account_get_last_step_stock_moves()` to include SO moves for downpayment/out_refund, ensuring correct COGS computation.

4. **Delivery Status**: Computed on SO based on picking states: 'new' (no pickings), 'partial' (some pickings done), 'done' (all pickings done), 'cancel'.

5. **Commitment Date Propagation**: `write()` on sale.order propagates `commitment_date` changes to stock move `date_deadline` fields.

6. **Lot Tracking on Invoice**: `account_move.py` `_get_invoiced_lot_values()` returns lots delivered for the invoice line.

---

## v17→v18 Changes

- `delivery_status` field added to `sale.order` for improved delivery tracking UI
- `json_popover` / `show_json_popover` fields for enriched popover data
- `_compute_json_popover()` method added
- `_get_action_add_from_catalog_extra_context()` added for product catalog integration
- Improved `_log_decrease_ordered_quantity()` with more detailed notes

---

## Notes

- `sale_stock` is the heaviest integration module combining SO + Stock + Account
- Its `account_move.py` is the canonical override point for COGS on sales
- The `stock.py` file adds `sale_line_id` index as `btree_not_null` for performance
- MTO route requires `stock.route_warehouse0_mto_pull` to be active on the warehouse
