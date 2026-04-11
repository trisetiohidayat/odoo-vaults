# purchase_stock — Purchase Stock

**Tags:** #odoo #odoo18 #purchase #stock #logistics #procurement
**Odoo Version:** 18.0
**Module Category:** Purchase + Stock Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`purchase_stock` is the dual of `sale_stock` for the Purchase side. It manages PO-to-receipt propagation, vendor delivery performance tracking, MTO/buy procurement rules, kit component handling, price difference accounting, and inter-company transit logic. One of the largest integration modules.

**Technical Name:** `purchase_stock`
**Python Path:** `~/odoo/odoo18/odoo/addons/purchase_stock/`
**Inherits From:** `purchase`, `stock`
**Depends:** `purchase`, `stock`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/purchase_order.py` | `purchase.order` | Receipt tracking, incoterm, incoming pickings, effective date, on-time rate |
| `models/purchase_order_line.py` | `purchase.order.line` | Stock move qty received, kit handling, forecasted issues |
| `models/account_invoice.py` | `account.move` | Anglo-Saxon price diff (PDiff) calculation |
| `models/account_move_line.py` | `account.move.line` | PDiff application via SVL layers |
| `models/stock.py` | `stock.picking`, `stock.lot`, `procurement.group`, `stock.warehouse`, `stock.orderpoint` | Receipt links, lot tracking, buy route, replenishment |
| `models/stock_rule.py` | `stock.rule` | Buy procurement execution |

---

## Models Reference

### `purchase.order` (models/purchase_order.py)

#### Additional Fields

| Field | Type | Notes |
|-------|------|-------|
| `incoterm_location` | Char | Incoterm delivery location |
| `incoming_picking_count` | Integer | Count of incoming pickings |
| `picking_ids` | Many2many | Linked stock.pickings |
| `dest_address_id` | Many2one | Drop ship address |
| `picking_type_id` | Many2one | Receipt picking type |
| `default_location_dest_id_usage` | Char | Related from picking type |
| `group_id` | Many2one | Procurement group |
| `is_shipped` | Boolean | All pickings done |
| `effective_date` | Datetime | Date of first done receipt |
| `on_time_rate` | Float | Related from partner |
| `receipt_status` | Selection | 'pending'/'early'/'late'/'done' |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_picking_ids()` | Links pickings via group_id |
| `_compute_incoming_picking_count()` | Counts pickings |
| `_compute_effective_date()` | Sets effective_date from first done picking |
| `_compute_is_shipped()` | True when all pickings done |
| `_compute_receipt_status()` | Computes pending/early/late/done |
| `_compute_dest_address_id()` | Related dest address |
| `write(vals)` | Logs qty decreases |
| `action_add_from_catalog()` | Add product from catalog |
| `button_approve()` | Calls `_create_picking()` |
| `_prepare_grouped_data()` | Adds picking_type_id to grouping |
| `button_cancel()` | Full chain cancellation, MTO→MTS conversion |
| `action_view_picking()` | Returns picking action |
| `_prepare_invoice()` | Adds incoterm to invoice |
| `_log_decrease_ordered_quantity()` | Logs note on PO |
| `_get_destination_location()` | Gets final destination |
| `_get_final_location_record()` | Location lookup |
| `_get_picking_type()` | Determines picking type |
| `_prepare_group_vals()` | Creates group vals |
| `_prepare_picking()` | Creates receipt picking |
| `_create_picking()` | Single picking creation |
| `_add_picking_info()` | Sets carrier, notes |
| `_get_orders_to_reminder()` | Finds POs needing reminder |

---

### `purchase.order.line` (models/purchase_order_line.py)

#### Additional Fields

| Field | Type | Notes |
|-------|------|-------|
| `qty_received_method` | Selection | Adds 'stock_moves' option |
| `move_ids` | One2many | Stock moves linked to POL |
| `orderpoint_id` | Many2one | Linked orderpoint |
| `move_dest_ids` | Many2many | Downstream moves |
| `product_description_variants` | Char | Variant description |
| `propagate_cancel` | Boolean | Propagate cancellation |
| `forecasted_issue` | Boolean | Potential stock issue |
| `is_storable` | Boolean | Related from product |
| `location_final_id` | Many2one | Related from order |
| `group_id` | Many2one | Related from order |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_qty_received_method()` | Returns 'stock_moves' for storable |
| `_compute_qty_received()` | Sums move quantities (handles kits) |
| `_compute_forecasted_issue()` | Detects stock shortages |
| `write(vals)` | Updates move dates, packaging |
| `action_product_forecast_report()` | Opens forecast report |
| `unlink()` | Cancels moves, handles move_dests |
| `_update_move_date_deadline()` | Syncs dates |
| `_create_or_update_picking()` | Creates or updates receipt |
| `_get_stock_move_price_unit()` | Gets move price unit |
| `_prepare_stock_moves()` | Kit component creation |
| `_get_stock_move_vals()` | Builds move vals |
| `_find_candidate()` | Finds existing POL |
| `_get_outgoing_incoming_moves()` | Filters by direction |
| `_prepare_account_move_line()` | Adds balance |
| `_prepare_purchase_order_line_from_procurement()` | From procurement |
| `_create_stock_moves()` | Batch move creation |
| `_merge_po_line()` | Merges duplicate POLs |

---

### `account.move` (models/account_invoice.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_stock_account_prepare_anglo_saxon_in_lines_vals()` | Full PDiff calculation using `account.move.line._apply_price_difference()` |
| `_post()` | Applies PDiff SVLs, updates `standard_price` |

---

### `account.move.line` (models/account_move_line.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_get_valued_in_moves()` | Returns valued in moves for the line |
| `_get_out_and_not_invoiced_qty()` | Qty out but not yet invoiced |
| `_apply_price_difference()` | Full PDiff layer logic: `_generate_price_difference_vals()` → `_replay_history()` → `_prepare_pdiff_vals()` → SVL creation |
| `_generate_price_difference_vals()` | Generates PDiff aml and svl vals |
| `_replay_history()` | Replays history to compute PDiff at time of invoice |
| `_prepare_pdiff_vals()` | Prepares PDiff vals |
| `_prepare_pdiff_aml_vals()` | PDiff account.move.line vals |
| `_prepare_pdiff_svl_vals()` | PDiff stock.valuation.layer vals |
| `_get_price_unit_val_dif_and_relevant_qty()` | Gets price diff components |

#### Critical PDiff Logic

Price difference (PDiff) is the variance between:
- **PO price** (landed cost at receipt time)
- **Invoice price** (what we actually paid)

When `standard` cost method: PDiff is tracked via SVL layers. When `average` cost method: PDiff adjusts `standard_price` directly.

---

### `stock.rule` (models/stock_rule.py)

| Field | Value | Notes |
|-------|-------|-------|
| `action` | `'buy'` added | Buy procurement rule action |

#### Methods

| Method | Behavior |
|--------|----------|
| `_run_buy()` | Full PO generation from procurement: finds/creates PO, adds line, quits on conflict |
| `_get_lead_days()` | Adds vendor lead time, PO security lead, days_to_purchase |
| `_get_procurements_to_merge_groupby()` | Groups by partner, currency, rules |
| `_get_procurements_to_merge()` | Returns list of procurement groups |
| `_merge_procurements()` | Merges same product from multiple procurements |
| `_update_purchase_order_line()` | Updates existing POL qty |
| `_prepare_purchase_order()` | Creates new PO vals |
| `_make_po_get_domain()` | Filters by procurement group requisition |
| `_push_prepare_move_copy_values()` | Passes values to push rules |
| `_get_partner_id()` | Gets supplier from seller_id |

---

## Security File

No standalone security XML file. Relies on `purchase` and `stock` base security.

---

## Data Files

| File | Content |
|------|---------|
| `data/cron.xml` | `_purchase_order_reminder_priority_picking_types_notification` cron (weekly) |
| `data/stock_data.xml` | Buy route: `route_warehouse0_buy` + buy pull rule per warehouse |
| `data/stock_orderpoint_data.xml` | Orderpoint visibility rule |

---

## Critical Behaviors

1. **Buy Route**: The core procurement action (`_run_buy`). When a procurement runs on the buy route, it finds or creates a PO for the product's seller, adds a line, and triggers a PO confirmation.

2. **Kit Component Handling**: `_get_po_line_moves()` detects bom lines (phantom kits), recursively gets component moves, and `_compute_qty_received()` sums component quantities rather than the finished product.

3. **Price Difference (PDiff)**: When `standard` cost method is used and invoice price differs from PO price, `_apply_price_difference()` creates correction SVLs. For `average` cost method, `standard_price` is updated directly.

4. **MTO to MTS Conversion on Cancel**: `button_cancel()` checks if the PO line had MTO routes. If the stock was received (cannot unbuild), converts to MTS by keeping the stock and flagging for `stock.move.to_refund`.

5. **Transit Locations**: `_get_destination_location()` handles inter-company transit: if `dest_address_id` is set (drop-ship), the destination is the partner's location, not the warehouse's internal location.

6. **Receipt Status**: Computed as 'pending' (no done receipts), 'early' (done before expected), 'late' (done after expected), 'done' (all received).

---

## v17→v18 Changes

- `receipt_status` field added for improved receipt tracking
- `_compute_receipt_status()` method added
- `_compute_dest_address_id()` added for better drop-ship handling
- `_compute_is_shipped()` now returns True when all pickings are done, not just when there's a done picking
- `default_location_dest_id_usage` related field added
- Improved `_run_buy()` for better PO generation from multiple procurement sources

---

## Notes

- This is the second-largest integration module after `sale_stock`
- The PDiff logic in `account_move_line.py` is the most complex part of the module
- Buy route rules are warehouse-specific and generated dynamically per warehouse
- The `_purchase_order_reminder_priority_picking_types_notification` cron runs weekly to remind about upcoming receipts
