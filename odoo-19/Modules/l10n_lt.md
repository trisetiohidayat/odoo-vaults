---
type: module
module: l10n_lt
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Lithuania Accounting Localization (`l10n_lt`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Chart of Accounts (COA) Template for Lithuania's Accounting. |
| **Technical** | `l10n_lt` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Chart of Accounts (COA) Template for Lithuania's Accounting.

This module also includes:

* List of available banks in Lithuania.
* Tax groups.
* Most common Lithuanian Taxes.
* Fiscal positions.
* Account Tags.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |
| `account_edi_ubl_cii` | Dependency |

## Technical Notes
- Country code: `lt`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_tax.py, account_journal.py, template_lt.py

## Related
- [Modules/l10n_lt](odoo-18/Modules/l10n_lt.md) - Core accounting