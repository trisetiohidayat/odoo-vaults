# POS MRP

## Overview
- **Name:** pos_mrp
- **Category:** Sales/Point of Sale
- **Depends:** `point_of_sale`, `mrp`
- **Auto-install:** True
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
Link module between Point of Sale and Manufacturing (MRP). Enables POS to handle products with phantom Bills of Materials (Kits), properly resolving their cost using the Anglo-Saxon accounting method.

## Models

### `pos.order.line` (Extended)
| Method | Description |
|--------|-------------|
| `_get_stock_moves_to_consider()` | Overrides to explode BoM and match correct stock moves for kit products |

### `pos.order` (Extended)
| Method | Description |
|--------|-------------|
| `_get_pos_anglo_saxon_price_unit()` | Overrides to compute correct cost for kit products by exploding the phantom BoM and summing component costs |

## Key Features
- Accurate COGS calculation for kit/phantom BoM products sold at POS
- Explodes kit products into components for stock move matching
- Anglo-Saxon accounting: uses component costs from BoM instead of product cost

## Data Files
- `security/ir.model.access.csv` — Access control

## Related
- [Modules/point_of_sale](Modules/point_of_sale.md) — Base POS module
- [Modules/MRP](Modules/MRP.md) — Manufacturing module
