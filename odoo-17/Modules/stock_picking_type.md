---
tags: [odoo, odoo17, module, stock_picking_type, warehouse]
research_depth: medium
---

# Stock Picking Type Module — Deep Reference

**Source:** `addons/stock/models/stock_picking.py` — class `PickingType` (line 20)

> In Odoo 17, `stock.picking.type` is defined directly in `stock_picking.py`, not in a separate file.

## Overview

Picking operation types define the nature of stock operations: receipt (incoming), delivery (outgoing), or internal transfer. Each warehouse has multiple picking types automatically created at installation, one per step in the reception/delivery flow.

## Key Model: `stock.picking.type`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Operation type name (e.g., "Receipts", "Delivery Orders") |
| `color` | Integer | Color for kanban view |
| `sequence` | Integer | Order in "All Operations" kanban view |
| `sequence_id` | Many2one | Associated `ir.sequence` for reference numbering |
| `sequence_code` | Char | Short prefix code (e.g., "IN", "OUT", "INT", "PICK", "PACK") |
| `code` | Selection | `incoming` / `outgoing` / `internal` |
| `warehouse_id` | Many2one | Parent warehouse (compute, ondelete cascade) |
| `company_id` | Many2one | Company |
| `default_location_src_id` | Many2one | Default source location for new pickings |
| `default_location_dest_id` | Many2one | Default destination location for new pickings |
| `default_location_return_id` | Many2one | Default returns location (domain: `return_location = True`) |
| `return_picking_type_id` | Many2one | The return picking type counterpart |
| `use_create_lots` | Boolean | Allow creation of new lots/serial numbers |
| `use_existing_lots` | Boolean | Allow use of existing lots/serial numbers |
| `show_entire_packs` | Boolean | Allow moving entire packages |
| `print_label` | Boolean | Print SSCC label on this operation |
| `show_reserved` | Boolean | Pre-fill detailed operations with reserved stock |
| `show_operations` | Boolean | Show detailed operations instead of aggregated moves |
| `reservation_method` | Selection | `at_confirm` / `manual` / `by_date` |
| `reservation_days_before` | Integer | Days before scheduled date to reserve (for `by_date`) |
| `reservation_days_before_priority` | Integer | Days before for priority transfers |
| `auto_show_reception_report` | Boolean | Show reception report at validation |
| `create_backorder` | Selection | `ask` / `always` / `never` — backorder policy |
| `auto_print_delivery_slip` | Boolean | Auto-print delivery slip on validation |
| `auto_print_return_slip` | Boolean | Auto-print return slip on validation |
| `auto_print_product_labels` | Boolean | Auto-print product labels |
| `auto_print_lot_labels` | Boolean | Auto-print lot/SN labels |
| `auto_print_packages` | Boolean | Auto-print package labels |
| `auto_print_package_label` | Boolean | Auto-print package label when "Put in Pack" is used |
| `product_label_format` | Selection | Dymo, 2x7, 4x7, 4x12, ZPL variants |
| `lot_label_format` | Selection | Lot label format (4x12 or ZPL, per-lot or per-unit) |
| `barcode` | Char | Barcode for scanning |
| `active` | Boolean | Active/archived |
| `count_picking_draft` | Integer | Count of draft pickings (computed) |
| `count_picking_ready` | Integer | Count of ready pickings (computed) |
| `count_picking` | Integer | Count of assigned/waiting/confirmed pickings (computed) |
| `count_picking_waiting` | Integer | Count of waiting pickings (computed) |
| `count_picking_late` | Integer | Count of late pickings (computed) |
| `count_picking_backorders` | Integer | Count of pickings with backorders (computed) |
| `picking_properties_definition` | PropertiesDefinition | Properties definition for this type |

### Operation Types (`code` field)

| Code | Name | Default Source | Default Destination |
|------|------|----------------|---------------------|
| `incoming` | Receipt | `stock.location.suppliers` | `warehouse.lot_stock_id` |
| `outgoing` | Delivery | `warehouse.lot_stock_id` | `stock.location.customers` |
| `internal` | Internal Transfer | `warehouse.lot_stock_id` | `warehouse.lot_stock_id` |

### Reservation Methods

| Method | Key | Description |
|--------|-----|-------------|
| `at_confirm` | At Confirmation | Reserve immediately when picking is confirmed |
| `manual` | Manually | Only reserve when user clicks "Check Availability" |
| `by_date` | Before scheduled date | Scheduled job reserves based on `reservation_days_before` |

> Note: `reservation_method` is hidden for `incoming` pickings.

### Auto-Batch Fields (from `stock_picking_batch`)

| Field | Type | Description |
|-------|------|-------------|
| `auto_batch` | Boolean | Enable automatic batching on confirm |
| `batch_group_by_partner` | Boolean | Group by contact |
| `batch_group_by_destination` | Boolean | Group by destination country |
| `batch_group_by_src_loc` | Boolean | Group by source location |
| `batch_group_by_dest_loc` | Boolean | Group by destination location |
| `batch_max_lines` | Integer | Max lines per batch (0 = unlimited) |
| `batch_max_pickings` | Integer | Max pickings per batch (0 = unlimited) |
| `batch_auto_confirm` | Boolean | Auto-confirm new batches |
| `count_picking_batch` | Integer | Batch count (computed) |
| `count_picking_wave` | Integer | Wave count (computed) |

## Picking Types Created per Warehouse

When a `stock.warehouse` is created, five picking types are generated:

| Picking Type | `sequence_code` | `code` | Active When |
|-------------|-----------------|--------|-------------|
| Receipts (`in_type_id`) | `IN` | `incoming` | Always |
| Delivery Orders (`out_type_id`) | `OUT` | `outgoing` | Always |
| Internal Transfers (`int_type_id`) | `INT` | `internal` | Multi-location or non-single-step |
| Pick (`pick_type_id`) | `PICK` | `internal` | Delivery steps > 1 step |
| Pack (`pack_type_id`) | `PACK` | `internal` | Delivery steps = 3 steps |

Sequence prefix format: `WH_CODE/CODE_PREFIX/00001` (e.g., `WH/IN/00001`).

## Return Picking Types

Each incoming/outgoing picking type has a linked return counterpart:

```python
# When Receipts type is created:
return_picking_type_id = out_type_id   # links to Delivery Orders (Returns to supplier)

# When Delivery Orders type is created:
return_picking_type_id = in_type_id    # links to Receipts (Customer returns)
```

Return pickings are created from the "Return" button on a validated picking. The `stock.picking.return_id` field links to the original picking; `return_ids` is the reverse one2many.

## Key Computed Defaults

```python
# Incoming: source = supplier, dest = lot_stock
# Outgoing: source = lot_stock, dest = customer
# print_label: True only for outgoing types
# use_create_lots: True only for incoming types
# use_existing_lots: True only for outgoing types
# show_reserved: False for incoming (receipts always show available qty)
# reservation_method hidden when code = 'incoming'
```

## Action Methods

| Method | Action |
|--------|--------|
| `get_action_picking_tree_late` | Show late pickings for this type |
| `get_action_picking_tree_backorder` | Show pickings with backorders |
| `get_action_picking_tree_waiting` | Show waiting pickings |
| `get_action_picking_tree_ready` | Show ready pickings |
| `get_action_picking_type_operations` | Show all operations |
| `get_action_picking_tree_batch` | Show batch transfers (from `stock_picking_batch`) |
| `get_action_picking_tree_wave` | Show waves (from `stock_picking_batch`) |

## Sequence Auto-Update

When `sequence_code` is changed, the linked `ir.sequence` is updated:
- `prefix` changes to `warehouse_code/sequence_code/`
- Padding stays at 5 digits

## `by_date` Reservation Logic

When `reservation_method = 'by_date'`:

1. All draft/confirmed/waiting/partially_available moves under this type get `reservation_date` recomputed:
   - `reservation_date = scheduled_date - reservation_days_before`
   - For priority moves: `scheduled_date - reservation_days_before_priority`
2. A scheduled action reads moves whose `reservation_date <= today` and calls `action_assign`.

## See Also

- [Modules/stock](stock.md) — `stock.picking`, `stock.location`
- [Modules/stock_warehouse](stock_warehouse.md) — warehouse configuration
- [Modules/stock_picking_batch](stock_picking_batch.md) — batch transfers
- [Modules/stock_rule](Modules/stock_rule.md) — procurement rules
