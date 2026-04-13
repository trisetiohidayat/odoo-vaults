---
type: module
module: l10n_lv
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Latvia Accounting Localization (`l10n_lv`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Chart of Accounts (COA) Template for Latvia's Accounting. |
| **Technical** | `l10n_lv` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Chart of Accounts (COA) Template for Latvia's Accounting.
This module also includes:
* Tax groups,
* Most common Latvian Taxes,
* Fiscal positions,
* Latvian bank list.

author is Allegro IT (visit for more information https://www.allegro.lv)
co-author is Chick.Farm (visit for more information https://www.myacc.cloud)

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |
| `base_vat` | Dependency |
| `account_edi_ubl_cii` | Dependency |

## Technical Notes
- Country code: `lv`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: template_lv.py

## Related
- [Modules/l10n_lv](modules/l10n_lv.md) - Core accounting