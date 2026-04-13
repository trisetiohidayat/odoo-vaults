---
type: module
module: l10n_in_sale_stock
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# India Accounting Localization (`l10n_in_sale_stock`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Get the warehouse address if the invoice is created from the Sale Order |
| **Technical** | `l10n_in_sale_stock` |
| **Category** | Accounting/Localizations/Sale |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Get the warehouse address if the invoice is created from the Sale Order
In Indian EDI we send shipping address details if available

So this module is to get the warehouse address if the invoice is created from Sale Order

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_in_sale` | Dependency |
| `l10n_in_stock` | Dependency |
| `sale_stock` | Dependency |

## Technical Notes
- Country code: `in`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_move.py, stock_move.py, stock_picking.py

## Related
- [Modules/l10n_in](modules/l10n_in.md) - Core accounting