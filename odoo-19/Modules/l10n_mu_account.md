---
type: module
module: l10n_mu_account
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Mauritius Accounting Localization (`l10n_mu_account`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This is the base module to manage the accounting chart for the Republic of Mauritius in Odoo. |
| **Technical** | `l10n_mu_account` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This is the base module to manage the accounting chart for the Republic of Mauritius in Odoo.
==============================================================================================
    - Chart of accounts
    - Taxes
    - Fiscal positions
    - Default settings

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |

## Technical Notes
- Country code: `mu`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_move.py, base_document_layout.py, template_mu.py

## Related
- [Modules/l10n_fr](l10n_fr.md) - Core accounting