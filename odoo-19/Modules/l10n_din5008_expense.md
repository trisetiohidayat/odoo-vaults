---
type: module
module: l10n_din5008_expense
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# DIN5008 Accounting Localization (`l10n_din5008_expense`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | DIN5008 accounting localization |
| **Technical** | `l10n_din5008_expense` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
DIN 5008 document layout for expense reports.

Extends [Modules/l10n_din5008](odoo-18/Modules/l10n_din5008.md) with expense-specific QWeb report templates following the DIN 5008 standard.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_din5008` | DIN 5008 base layout |
| `hr_expense` | Expense reports |

## Technical Notes
- Country code: `de`, `ch`
- Localization type: document layout
- Data-only module (no Python models)

## Related
- [Modules/l10n_din5008](odoo-18/Modules/l10n_din5008.md) — Base DIN 5008 layout
- [Modules/l10n_din5008_sale](odoo-18/Modules/l10n_din5008_sale.md) — Sale order layout
- [Modules/l10n_din5008_purchase](odoo-18/Modules/l10n_din5008_purchase.md) — Purchase order layout
- [Modules/l10n_din5008_repair](odoo-18/Modules/l10n_din5008_repair.md) — Repair order layout
- [Modules/l10n_din5008_stock](odoo-18/Modules/l10n_din5008_stock.md) — Stock delivery order layout