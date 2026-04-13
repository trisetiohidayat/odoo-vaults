# POS Repair

## Overview
- **Name:** POS - Repair
- **Category:** Technical
- **Depends:** `point_of_sale`, `repair`
- **Auto-install:** True
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
Link module between Point of Sale and Repair. Allows repair orders to be created, managed, or referenced from the POS interface.

## Models

### `sale.order.line` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `is_repair_line` | Boolean | Computed: True if linked to a repair via stock moves |

## Assets
- POS frontend assets for repair flow

## Related
- [Modules/point_of_sale](modules/point_of_sale.md) — Base POS module
- [Modules/repair](modules/repair.md) — Repair management module
