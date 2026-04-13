---
Module: delivery_stock_picking_batch
Version: 18.0
Type: addon
Tags: #delivery #stock #batch #carrier
---

# delivery_stock_picking_batch

Links stock picking batches to delivery carriers. Adds carrier-based grouping and maximum weight constraints for auto-batching of delivery pickings.

## Module Overview

**Category:** Hidden
**Depends:** `stock_delivery`, `stock_picking_batch`
**Auto-Install:** True
**License:** LGPL-3

## What It Does

Extends `stock.picking.type` with carrier grouping and weight limits, and extends `stock.picking.batch` with weight-aware auto-batch merge logic.

## Extends

### `stock.picking.type` (Extended)

| Field | Type | Description |
|-------|------|-------------|
| `batch_group_by_carrier` | Boolean | Auto-group batches by carrier when auto-batching |
| `batch_max_weight` | Integer | Maximum total weight for auto-batching (0 = unlimited) |
| `weight_uom_name` | Char | Derived weight unit of measure label (computed) |

`_get_batch_group_by_keys()` appends `batch_group_by_carrier` to the picking type's group-by keys list (inherited from `stock_picking_batch`).

### `stock.picking.batch` (Extended)

`_is_picking_auto_mergeable()` - checks that adding a picking to a batch does not exceed `batch_max_weight`. Also called for line-level weight via `_is_line_auto_mergeable()`.

### `stock.picking` (Extended)

| Method | Description |
|--------|-------------|
| `_get_possible_pickings_domain()` | Adds `carrier_id` filter when `batch_group_by_carrier` is set |
| `_get_possible_batches_domain()` | Same carrier constraint for batch search |
| `_get_auto_batch_description()` | Appends carrier name to batch description when grouping by carrier |
| `_is_auto_batchable()` | Weight check before adding picking to batch |

## Data

| File | Purpose |
|------|---------|
| `views/stock_picking_type_views.xml` | Inherits `stock_picking_batch` form view to add `batch_group_by_carrier` toggle, `batch_max_weight` input, and `weight_uom_name` label (only visible when `auto_batch` is true) |

## Key Details

- Weight tracking requires `stock_delivery` (which adds `weight` to `stock.picking`)
- When `batch_group_by_carrier = True`, pickings are only auto-batched with other pickings sharing the same `carrier_id`
- Weight limits apply per-batch; exceeding `batch_max_weight` blocks the picking from auto-batching

---

*See also: [Modules/stock_picking_batch](modules/stock_picking_batch.md), [Modules/delivery](modules/delivery.md), [Modules/stock](modules/stock.md)*
