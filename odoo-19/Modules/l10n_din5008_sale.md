---
type: module
module: l10n_din5008_sale
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# DIN5008 Accounting Localization (`l10n_din5008_sale`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | DIN5008 accounting localization |
| **Technical** | `l10n_din5008_sale` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
DIN 5008 document layout for sale orders (quotations and sale orders).

Extends [Modules/l10n_din5008](modules/l10n_din5008.md) with sale-specific QWeb report templates following the DIN 5008 standard for German/Swiss business documents.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_din5008` | DIN 5008 base layout |
| `sale` | Sale orders |

## Technical Notes
- Country code: `de`, `ch` (Germany, Switzerland)
- Localization type: document layout
- Data-only module (no Python models)
- Auto-installs with `l10n_de` and `sale`

## Related
- [Modules/l10n_din5008](modules/l10n_din5008.md) — Base DIN 5008 layout
- [Modules/l10n_din5008_purchase](modules/l10n_din5008_purchase.md) — Purchase order layout
- [Modules/l10n_din5008_repair](modules/l10n_din5008_repair.md) — Repair order layout
- [Modules/l10n_din5008_expense](modules/l10n_din5008_expense.md) — Expense report layout
- [Modules/l10n_din5008_stock](modules/l10n_din5008_stock.md) — Stock delivery order layout