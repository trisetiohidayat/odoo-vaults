---
type: module
module: l10n_in_ewaybill_stock
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# India Accounting Localization (`l10n_in_ewaybill_stock`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Indian E-waybill for Stock |
| **Technical** | `l10n_in_ewaybill_stock` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Indian E-waybill for Stock
==========================

This module enables users to create E-waybill from Inventory App without generating an invoice

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_in_stock` | Dependency |
| `l10n_in_ewaybill` | Dependency |

## Technical Notes
- Country code: `in` (India)
- Localization type: e-waybill for stock/delivery orders
- Custom model files: stock_move.py, stock_picking.py, l10n_in_ewaybill.py

## Models

### `stock.picking` (Extended)
Creates Indian e-waybill from delivery orders (without requiring a sale invoice).

### `stock.move` (Extended)
E-waybill quantity and item handling.

## Related
- [Modules/l10n_in](l10n_in.md) — Core Indian accounting
- [Modules/l10n_in_ewaybill](l10n_in_ewaybill.md) — E-waybill base
- [Modules/l10n_in_stock](l10n_in_stock.md) — Indian stock management