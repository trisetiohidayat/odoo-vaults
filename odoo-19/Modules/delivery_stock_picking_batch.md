---
type: module
module: delivery_stock_picking_batch
tags: [odoo, odoo19, delivery, stock, batch, picking, shipping]
created: 2026-04-06
---

# Delivery Stock Picking Batch

## Overview
| Property | Value |
|----------|-------|
| **Name** | Delivery Stock Picking Batch |
| **Technical** | `delivery_stock_picking_batch` |
| **Category** | Supply Chain/Inventory |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Links batch pickings with delivery carriers. Adds carrier-based grouping and maximum weight constraints to the batch picking system. Auto-installs with `stock_delivery` and `stock_picking_batch`.

## Dependencies
- `stock_delivery`
- `stock_picking_batch`

## Key Models
| Model | Type | Description |
|-------|------|-------------|
| `stock.picking.type` | Extension | Batch group-by carrier, max weight per operation type |
| `stock.picking` | Extension | Carrier-based domain filtering for auto-batching |
| `stock.picking.batch` | Extension | Weight constraint enforcement on batch creation |
| `res.config.settings` | Extension | Inherits to expose any delivery-related settings |

## `stock.picking.type` (Extension)
### Fields
| Field | Type | Description |
|-------|------|-------------|
| `batch_group_by_carrier` | Boolean | Auto-group batches by carrier during auto-batch |
| `batch_max_weight` | Integer | Maximum weight (in product UoM); transfers exceeding this are excluded |
| `weight_uom_name` | Char | Weight unit label (computed from product UoM config) |

### Methods
| Method | Purpose |
|--------|---------|
| `_get_batch_group_by_keys` | Adds `batch_group_by_carrier` to auto-batch grouping keys |

## `stock.picking` (Extension)
### Methods
| Method | Purpose |
|--------|---------|
| `_get_possible_pickings_domain` | Filters by `carrier_id` when `batch_group_by_carrier` is set |
| `_get_possible_batches_domain` | Filters by carrier when `batch_group_by_carrier` is set |
| `_get_auto_batch_description` | Appends carrier name to auto-batch description |
| `_is_auto_batchable` | Checks weight constraint: `self.weight + picking.weight <= batch_max_weight` |

## `stock.picking.batch` (Extension)
### Methods
| Method | Purpose |
|--------|---------|
| `_is_picking_auto_mergeable` | Checks weight constraint against current batch weight |
| `_is_line_auto_mergeable` | Checks weight constraint against wave (batch) weight |

## Batch Weight Constraints
```
A transfer is excluded from a batch if:
  batch.picking_type_id.batch_max_weight > 0 AND
  (existing_batch_weight + transfer.weight) > batch_max_weight
```

## Related
- [Modules/stock_picking_batch](Modules/stock_picking_batch.md)
- [Modules/stock_delivery](Modules/stock_delivery.md)
- [Modules/delivery](Modules/delivery.md)
