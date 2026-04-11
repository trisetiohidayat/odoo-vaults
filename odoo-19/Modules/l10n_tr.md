---
type: module
module: l10n_tr
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Turkey Accounting Localization (`l10n_tr`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This is the base module to manage the accounting chart for Türkiye in Odoo |
| **Technical** | `l10n_tr` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This is the base module to manage the accounting chart for Türkiye in Odoo
==========================================================================

Türkiye accounting basic charts and localizations
-------------------------------------------------
Activates:

- Chart of Accounts
- Taxes
- Tax Report

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |

## Technical Notes
- Country code: `tr`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_journal.py, account_move_line.py, product.py, template_tr.py

## Related
- [[Modules/l10n_tr]] - Core accounting