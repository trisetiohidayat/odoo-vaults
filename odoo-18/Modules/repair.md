# repair — Repair Order Management

**Module:** `repair`
**Odoo Version:** 18
**Source:** `~/odoo/odoo18/odoo/addons/repair/`

---

## Overview

The `repair` module manages repair workflows for products, covering the complete lifecycle from initial diagnosis through final repair completion. It handles disassembly (removing parts), repair operations (replacing/swapping components), parts consumption tracking, and optional sale order / invoice integration.

---

## Architecture

### Model Structure

```
repair.order              # Main repair order
repair.tags               # Tagging for repair orders
stock.move                # Extended with repair.line integration
stock.picking             # Extended with return picking linkage
stock.lot                 # Extended with repair traceability
product.product           # Extended with repair domain
sale.order                # Extended with repair binding
mail.compose.message      # Extended for repair messaging
stock.warehouse           # Extended with repair picking type
stock.traceability        # Extended for repair/rework traceability
```

### File Map

| File | Purpose |
|------|---------|
| `models/repair.py` | Core `repair.order`, `repair.tags` models |
| `models/stock.py` | Stock extensions for repair integration |
| `models/sale_order.py` | Sale order binding to repair orders |
| `models/product.py` | Product domain for repair |
| `models/stock_lot.py` | Lot traceability for repairs |
| `models/stock_move.py` | Stock move extensions |
| `models/stock_move_line.py` | Move line extensions |
| `models/stock_picking.py` | Return picking linkage |
| `models/stock_warehouse.py` | Warehouse repair type configuration |
| `models/stock_traceability.py` | Repair/rework traceability |
| `models/mail_compose_message.py` | Messaging on repair orders |

---

## Core Models

### repair.order

**`repair.order`** is the central model representing a repair operation.

**Inheritance:** `models.Model` + `mail.thread` + `mail.activity.mixin` + `product.catalog.mixin`
** `_name`: `repair.order`
** `_description`: `"Repair Order"`
** `_order`: `priority desc, create_date desc`
** `_check_company_auto`: `True`

#### State Machine

```
draft (New)
   |
   v
confirmed (Confirmed)  ← action_validate() if stock available
   |                      OR user skips availability check
   v
under_repair (Under Repair)  ← action_repair_start()
   |
   +--- action_repair_end() → action_repair_done()
   |
   v
done (Repaired)
   OR
cancel (Cancelled)  ← action_repair_cancel() from any non-done state
```

#### Field Reference

**Identification & State**

| Field | Type | Description |
|-------|------|-------------|
| `name` | `Char` | Auto-generated repair reference (from picking type sequence). Default `'New'`. `readonly=True`, `required=True`, `index='trigram'` |
| `company_id` | `Many2one(res.company)` | Company scope (default `env.company`) |
| `state` | `Selection` | Workflow state: `'draft'`, `'confirmed'`, `'under_repair'`, `'done'`, `'cancel'` |
| `priority` | `Selection` | `'0'` (Normal) or `'1'` (Urgent) |

**Parties**

| Field | Type | Description |
|-------|------|-------------|
| `partner_id` | `Many2one(res.partner)` | Customer. Computed from `picking_id.partner_id` if linked to a return |
| `user_id` | `Many2one(res.users)` | Responsible technician (default `env.user`) |

**Product to Repair**

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | `Many2one(product.product)` | Product being repaired. Domain restricts to consumable/storable products |
| `product_qty` | `Float` | Quantity to repair. Computed from return picking if linked, default `1.0` |
| `product_uom` | `Many2one(uom.uom)` | Unit of measure for the product |
| `lot_id` | `Many2one(stock.lot)` | Lot/serial number of product being repaired. Constrained to lots present in the return picking |
| `tracking` | `Selection` | Related from `product_id.tracking` (`'none'`, `'lot'`, `'serial'`) |
| `under_warranty` | `Boolean` | If `True`, all parts added have sales price set to `0.0` |
| `schedule_date` | `Datetime` | Scheduled repair date (default `Datetime.now`) |

**Location / Picking**

| Field | Type | Description |
|-------|------|-------------|
| `picking_type_id` | `Many2one(stock.picking.type)` | Operation type (`code = 'repair_operation'`). Default from warehouse config |
| `picking_id` | `Many2one(stock.picking)` | Return order from which the product came. Sets partner, product, lot, and qty automatically |
| `location_id` | `Many2one(stock.location)` | Component source location (where parts are picked from) |
| `product_location_src_id` | `Many2one(stock.location)` | Product-to-repair source location |
| `product_location_dest_id` | `Many2one(stock.location)` | Destination for repaired product |
| `location_dest_id` | `Many2one(stock.location)` | Added parts destination. Related from picking type |
| `parts_location_id` | `Many2one(stock.location)` | Removed parts destination. Related from picking type |
| `recycle_location_id` | `Many2one(stock.location)` | Recycled parts destination |

**Parts / Operations**

| Field | Type | Description |
|-------|------|-------------|
| `move_ids` | `One2many(stock.move)` | Parts consumed or added. Inverse: `repair_id`. Domain: `repair_line_type != False` |
| `parts_availability` | `Char` | Computed availability status: `'Available'`, `'Exp <date>'`, `'Not Available'` |
| `parts_availability_state` | `Selection` | `'available'`, `'expected'`, `'late'` |
| `is_parts_available` | `Boolean` | All parts available (green indicator) |
| `is_parts_late` | `Boolean` | Any part is late (red indicator) |
| `has_uncomplete_moves` | `Boolean` | Some moves have incomplete quantities |

**Sale Order Binding**

| Field | Type | Description |
|-------|------|-------------|
| `sale_order_id` | `Many2one(sale.order)` | Source sale order |
| `sale_order_line_id` | `Many2one(sale.order.line)` | Source sale order line |
| `repair_request` | `Text` | Related to `sale_order_line_id.name` |

**Return Binding**

| Field | Type | Description |
|-------|------|-------------|
| `is_returned` | `Boolean` | `True` if linked to a done return picking |
| `picking_product_ids` | `One2many(product.product)` | Computed from `picking_id.move_ids.product_id` |
| `picking_product_id` | `Many2one(product.product)` | Related from `picking_id.product_id` |
| `allowed_lot_ids` | `One2many(stock.lot)` | Lots available for selection based on return picking |

**Procurement**

| Field | Type | Description |
|-------|------|-------------|
| `procurement_group_id` | `Many2one(procurement.group)` | Links to procurement group for parts procurement |

**UI Helpers**

| Field | Type | Description |
|-------|------|-------------|
| `unreserve_visible` | `Boolean` | Technical: show unreserve button |
| `reserve_visible` | `Boolean` | Technical: show reserve button |
| `repair_properties` | `Properties` | Custom properties from picking type definition |

---

#### Key Methods

**`action_validate()`**

Entry-point validation before confirming a repair:
1. If `product_id` is not storable, directly calls `_action_repair_confirm()`
2. Checks stock availability at `product_location_src_id` (considers owner `partner_id`)
3. If sufficient stock → calls `_action_repair_confirm()`
4. If insufficient → returns `stock.warn.insufficient.qty.repair` wizard

**`action_repair_start()`**

Transitions state from `confirmed` → `under_repair`. If called on `draft` state, calls `_action_repair_confirm()` first.

**`action_repair_end()`**

Checks all moves have been picked (`move.picked == True`), then calls `action_repair_done()`.

**`action_repair_done()`**

Completes the repair order:
1. Cancels moves with zero quantity
2. Sets all unpicked moves to `picked = True`
3. For each repair with `product_id`: creates a `stock.move` for the repaired product (from `product_location_src_id` → `product_location_dest_id`), linked via `repair_id`
4. Creates `move_line_ids` for the product move (with lot, quantity, owner, consume line references)
5. Calls `_action_done(cancel_backorder=True)` on all moves
6. Updates `sale_order_line_id.qty_delivered` for service products
7. Sets state → `'done'`

**`action_repair_cancel()`**

- Cancels unreceived sale order line quantity (for linked sale orders)
- Cancels all associated stock moves
- Sets state → `'cancel'`

**`action_repair_cancel_draft()`**

Resets to draft after cancellation: restores sale line quantities, resets move states.

**`_action_repair_confirm()`**

Internal confirmation (called by `action_validate` and `action_repair_start`):
1. Calls `_check_company()` on repair and its moves
2. Calls `_adjust_procure_method()` with `picking_type_code='repair_operation'`
3. Calls `_action_confirm()` on all moves
4. Calls `_trigger_scheduler()` for parts procurement
5. Sets state → `'confirmed'`

**`action_create_sale_order()`**

Creates a sale order quotation from the repair order:
- One SO per repair order
- Sets `repair_order_ids` on the SO
- Calls `_create_repair_sale_order_line()` on moves with `repair_line_type == 'add'`

---

### Parts / Move Integration

Repair parts are modeled as `stock.move` records with a `repair_id` link:

| `stock.move` field | Value |
|--------------------|-------|
| `repair_id` | Current `repair.order` |
| `repair_line_type` | `'remove'` (dismantle), `'add'` (install new), `'repair'` (repair existing) |
| `location_id` | `repair.location_id` (component source) |
| `location_dest_id` | `repair.location_dest_id` (destination for added parts) |

The `repair_line_type` is set when moves are created from the repair order UI.

---

### Warranty Behavior

When `under_warranty == True`:
- Parts with `repair_line_type == 'add'` that have linked `sale_line_id` get `price_unit = 0.0` and `technical_price_unit = 0.0`
- Controlled via `_update_sale_order_line_price()`

---

### Lot/Serial Tracking

- `lot_id` is constrained to lots present in the linked return picking (`picking_id.move_ids.lot_ids`)
- When `product_id.tracking == 'serial'` and `product_id` changes, `product_qty` is auto-set to `1.0`
- On `action_repair_done()`, the product move's `move_line_ids` records the lot consumed

---

### Sale Order Integration

Repair orders can be created from:
1. **Manual creation** in the Repair app
2. **Return picking linkage** — when a return picking (`stock.picking` with `is_return==True`) is created, it can spawn a repair order via `picking_id.create_repair()` (in stock)
3. **Sale order line** — RO linked to SOL via `sale_order_id` / `sale_order_line_id`

When a RO is confirmed, it can create moves that generate procurement for parts (via standard stock procurement). Those parts can then be linked to sale order lines via `_create_repair_sale_order_line()`.

---

### Picking Type Configuration

Each warehouse can have a `repair_type_id` (`stock.picking.type` with `code='repair_operation'`) that defines:
- Default source/destination locations
- Default sequence for repair reference numbering
- Repair properties definition

The repair order picks its `picking_type_id` based on `(company, user)` pair from the user's default warehouse.

---

## Key Design Decisions

1. **Parts as stock.moves:** Rather than a dedicated `repair.line` model, repair operations use `stock.move` with a `repair_id` foreign key. This leverages the full power of stock procurement, reservation, and traceability without duplicating logic.

2. **Availability wizard:** Instead of blocking confirmation, `action_validate()` returns a wizard when stock is insufficient, allowing the user to proceed (at their own risk) or resolve the shortage.

3. **Return picking linkage:** When a customer return triggers a repair, the RO automatically inherits the partner, product, lot, and quantity from the return picking. This avoids re-entering known information.

4. **Warranty via price override:** Warranty pricing is handled by zeroing `sale_line_id.price_unit` rather than a separate pricing engine, keeping the flow simple.

5. **Recurring repairs:** The model does not natively support recurring repair schedules (unlike `maintenance.request` which has `recurring_maintenance`). Recurring repairs would require a separate cron job.

---

## Notes

- The `product.catalog.mixin` enables adding parts from the product catalog picker in the repair order form.
- `search_date_category` is a virtual field enabling date-based search filters (Today, Tomorrow, etc.) without storing the category.
- Parts availability computation uses `forecast_availability` and `forecast_expected_date` from stock moves — the same mechanism used in manufacturing orders.
