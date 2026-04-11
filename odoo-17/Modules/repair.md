---
tags: [odoo, odoo17, module, repair]
research_depth: medium
---

# Repair Module — Deep Reference

**Source:** `addons/repair/models/`

## Overview

After-sales product repair management — creates repair orders (RO) to track products returned by customers, consume spare parts, invoice repair fees, and manage product traceability through the repair process. Integrates with `stock`, `sale`, and `mail`.

## File Map

| File | Purpose |
|------|---------|
| `repair.py` | `repair.order` model + `repair.tags` |
| `stock_move.py` | `repair_id` / `repair_line_type` on moves |
| `stock_move_line.py` | Lot visibility on repair moves |
| `stock_picking.py` | Return picking integration |
| `stock_lot.py` | Lot/serial traceability |
| `product.py` | Repair product type |
| `stock_warehouse.py` | `repair_type_id` on warehouse |

## Key Model: repair.order

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Auto-generated reference (e.g. `RO/00001`) |
| `company_id` | Many2one | Owning company |
| `state` | Selection | `draft` → `confirmed` → `under_repair` → `done` / `cancel` |
| `priority` | Selection | `0` Normal / `1` Urgent |
| `partner_id` | Many2one | Customer (for invoicing/delivery) |
| `user_id` | Many2one | Responsible technician |
| `product_id` | Many2one | Product to repair |
| `product_qty` | Float | Quantity (default 1.0) |
| `product_uom` | Many2one | Unit of measure |
| `lot_id` | Many2one | Lot/serial number |
| `tracking` | Selection | Auto-filled from product tracking |
| `picking_type_id` | Many2one | `stock.picking.type` code=`repair_operation` |
| `location_id` | Many2one | Current product location (before repair) |
| `location_dest_id` | Many2one | Repair shop location (after parts added) |
| `parts_location_id` | Many2one | Removed parts destination |
| `recycle_location_id` | Many2one | Recycled parts destination |
| `move_ids` | One2many | Spare part stock moves (add/remove/recycle) |
| `move_id` | Many2one | Stock move for the product-to-repair itself |
| `parts_availability` | Char | Computed: Available / Exp date / Not Available |
| `parts_availability_state` | Selection | `available` / `expected` / `late` |
| `is_parts_available` | Boolean | All parts in stock |
| `is_parts_late` | Boolean | Any part late vs `schedule_date` |
| `sale_order_id` | Many2one | Linked sale order (from which return originated) |
| `sale_order_line_id` | Many2one | Linked SOL |
| `picking_id` | Many2one | Return order that delivered the product |
| `is_returned` | Boolean | `True` if `picking_id.state == 'done'` |
| `under_warranty` | Boolean | Warranty flag — sets all prices to 0 |
| `schedule_date` | Datetime | Planned repair start |
| `tag_ids` | Many2many | Repair tags |
| `internal_notes` | Html | Internal notes |

### State Machine

```
draft ──[action_validate()]──> confirmed ──[action_repair_start()]──> under_repair
                                                                 │
                                                     [action_repair_end() calls
                                                      action_repair_done() if complete]
                                                                 │
                                                          [wizard if incomplete]
                                                                 │
                                                         repairs_done ──> done
                                                         under_repair ──> done (if parts done)
                                                                │
                                                         [action_repair_cancel()]──> cancel
```

**Note:** In Odoo 17, the intermediate `ready` and `invoice_existing` states were removed. The states are now simply: `draft`, `confirmed`, `under_repair`, `done`, `cancel`.

### Repair Line Types (on stock.move)

| `repair_line_type` | Description | Source Location | Destination Location |
|--------------------|-------------|-----------------|----------------------|
| `add` | Spare part to add | `repair.location_id` | `repair.location_dest_id` |
| `remove` | Part removed | `repair.location_dest_id` | `repair.parts_location_id` |
| `recycle` | Part removed and recycled | `repair.location_dest_id` | `repair.recycle_location_id` |

### Location Mapping

Locations are resolved from the `picking_type_id` (repair operation type):

```python
MAP_REPAIR_TO_PICKING_LOCATIONS = {
    'location_id':         'default_location_src_id',
    'location_dest_id':    'default_location_dest_id',
    'parts_location_id':   'default_remove_location_dest_id',
    'recycle_location_id': 'default_recycle_location_dest_id',
}
```

## Key Methods

### action_validate()
Validates the RO before confirming. Checks:
- No negative quantities on `move_ids`
- If `product_id` is storable, checks quants at `location_id` (with/without owner)
- If insufficient stock → shows `stock.warn.insufficient.qty.repair` wizard
- If consumable or no product → directly calls `_action_repair_confirm()`

### _action_repair_confirm()
Internal confirm logic:
- Sets `state = 'confirmed'`
- Calls `move_ids._action_confirm()`, `move_ids._trigger_scheduler()`
- Reserves parts via `move_ids._action_assign()`

### action_repair_start()
Transitions `confirmed` → `under_repair`. Calls `_action_repair_confirm()` if still in `draft`.

### action_repair_end()
Pre-completion check:
- If any move is partial or not all picked → shows `repair.warn.uncomplete.move` wizard (asks for confirmation)
- If all complete → calls `action_repair_done()`

### action_repair_done()
Core completion logic:
1. Cancel any moves with zero quantity
2. Auto-pick moves where nothing was picked
3. For service products from SO with `ordered_prepaid` policy → set `qty_delivered = qtyOrdered`
4. Validate tracking (require lot if product is tracked)
5. Create `stock.move` for the product-to-repair (with `repair_id` set, `location_id == location_dest_id`) — stores as `repair.move_id`
6. Calls `move_id._action_done(cancel_backorder=True)` for all moves (product move + parts moves)
7. Updates SO line price units to match delivered qty/price
8. Sets `state = 'done'`

### action_repair_cancel()
- Prevents cancelling `done` ROs
- Sets linked SOL qty to 0
- Cancels all `move_ids`
- Sets `state = 'cancel'`

### action_repair_cancel_draft()
- Cancels the RO first
- Unlinks zero-qty SOLs
- Resets moves and RO to `draft`

### action_create_sale_order()
Creates a sale order linked to the RO (for invoicing parts and labor):
- One SO per RO
- Adds SOLs for every `add`-type move line
- Opens the SO with `action_view_sale_order()`

### _update_sale_order_line_price()
When `under_warranty` toggles: sets `price_unit = 0` for `add`-type moves; otherwise re-computes price.

## Repair → Stock Move Integration (`stock_move.py`)

Every repair line is a `stock.move` with:

```python
repair_id = fields.Many2one('repair.order')
repair_line_type = fields.Selection([('add', 'Add'), ('remove', 'Remove'), ('recycle', 'Recycle')])
```

Key behaviors:
- Moves auto-name themselves from the RO
- `_is_consuming()` returns `True` for `add` type moves (included in delivery report)
- `_should_be_assigned()` returns `False` (no reservation loop for repair moves)
- `_split()` returns `[]` (partial moves are NOT split when RO is done)
- `_create_repair_sale_order_line()` creates SOLs for `add` moves when RO is confirmed

## Repair → Return Flow

If product is returned from a sale order:
1. Return picking (`stock.picking`, `return_id != False`) is created
2. RO is created with `picking_id` pointing to the return
3. `is_returned` is `True` when return is `done`
4. `repair_request` displays the SOL description

## See Also

- [[Modules/stock]] — stock.move, stock.move.line, picking types
- [[Modules/sale]] — return flow, SOL integration
- [[Modules/mrp_repair]] — BOM integration in repair (if installed)
- [[Modules/mail]] — mail.thread / mail.activity.mixin on repair.order
