---
type: module
module: l10n_gcc_invoice_stock_account
tags: [odoo, odoo19, l10n, localization, gcc, stock, accounting, arabic]
created: 2026-04-06
---

# Gulf Cooperation Council WMS Accounting (`l10n_gcc_invoice_stock_account`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Gulf Cooperation Council WMS Accounting |
| **Technical** | `l10n_gcc_invoice_stock_account` |
| **Category** | Accounting/Localizations |
| **Countries** | KW, OM, QA, AE, SA |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Adds Arabic as a secondary language for lots and serial numbers (stock tracking). Combines `l10n_gcc_invoice` features with `stock_account` for Arabic-language inventory valuation and lot reporting in GCC countries.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_gcc_invoice` | GCC invoice bilingual support |
| `stock_account` | Stock valuation and accounting |

## Technical Notes
- Auto-installs: True (installed automatically with `l10n_gcc_invoice` when `stock_account` is present)
- Report templates: `views/report_invoice.xml` (extends GCC invoice with lot/serial Arabic text)
- No model files - relies on inherited report rendering from parent modules

## Related
- [Modules/l10n_gcc_invoice](l10n_gcc_invoice.md)
- [Modules/stock_account](stock_account.md)
- [Modules/stock](Stock.md)
- [Modules/l10n_sa](l10n_sa.md)
- [Modules/l10n_ae](l10n_ae.md)
- [Modules/l10n_kw](l10n_kw.md)