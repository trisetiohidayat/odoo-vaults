# sale_gelato_stock

Odoo 19 Sales/Stock Module

## Overview

`sale_gelato_stock` is a **bridge module** between `sale_gelato` (Gelato print-on-demand) and `sale_stock` (Stock from Sales). It prevents Gelato products from triggering standard Odoo stock pickings, since Gelato handles its own fulfillment.

## Module Details

- **Category**: Sales/Sales
- **Depends**: `sale_gelato`, `sale_stock`
- **Author**: Odoo S.A.
- **License**: LGPL-3

## Key Components

### Models

#### `sale.order.line` (Inherited)

`_action_launch_stock_rule()` — Override that **prevents stock procurement** for Gelato product lines. Gelato lines are filtered out before calling `super()`, ensuring no delivery order or stock picking is created for Gelato items.

**Key Methods:**
- `_action_launch_stock_rule(**kwargs)` — Skips Gelato lines; calls parent only for non-Gelato lines.

This is the counterpart to `sale_gelato` which creates orders on Gelato for fulfillment. Without `sale_gelato_stock`, Odoo would attempt to create stock pickings for Gelato products (which is incorrect since Gelato ships directly).

## Relationship to Other Modules

| Module | Role |
|---|---|
| `sale_gelato` | Creates orders on Gelato for fulfillment |
| `sale_stock` | Creates stock pickings from sales |
| `sale_gelato_stock` | Prevents stock pickings for Gelato products |
