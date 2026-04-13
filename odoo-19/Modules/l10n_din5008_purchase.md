---
type: module
module: l10n_din5008_purchase
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# DIN5008 Accounting Localization (`l10n_din5008_purchase`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | DIN5008 accounting localization |
| **Technical** | `l10n_din5008_purchase` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
DIN 5008 document layout for purchase orders (requests for quotation and purchase orders).

Extends [Modules/l10n_din5008](odoo-18/Modules/l10n_din5008.md) with purchase-specific QWeb report templates following the DIN 5008 standard.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_din5008` | DIN 5008 base layout |
| `purchase` | Purchase orders |

## Technical Notes
- Country code: `de`, `ch`
- Localization type: document layout
- Data-only module (no Python models)

## Related
- [Modules/l10n_din5008](odoo-18/Modules/l10n_din5008.md) — Base DIN 5008 layout
- [Modules/l10n_din5008_sale](odoo-18/Modules/l10n_din5008_sale.md) — Sale order layout
- [Modules/l10n_din5008_repair](odoo-18/Modules/l10n_din5008_repair.md) — Repair order layout
- [Modules/l10n_din5008_expense](odoo-19/Modules/l10n_din5008_expense.md) — Expense report layout
- [Modules/l10n_din5008_stock](odoo-18/Modules/l10n_din5008_stock.md) — Stock delivery order layout