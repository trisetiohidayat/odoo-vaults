---
type: module
module: l10n_fi
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Finland Accounting Localization (`l10n_fi`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This is the Odoo module to manage the accounting in Finland. |
| **Technical** | `l10n_fi` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This is the Odoo module to manage the accounting in Finland.
============================================================

After installing this module, you'll have access to:
    * Finnish chart of account
    * Fiscal positions
    * Invoice Payment Reference Types (Finnish Standard Reference & Finnish Creditor Reference (RF))
    * Finnish Reference format for Sale Orders

Set the payment reference type from the Sales Journal.

## Dependencies
| Module | Purpose |
|--------|---------|
| `base_iban` | Dependency |
| `base_vat` | Dependency |
| `account` | Dependency |
| `account_edi_ubl_cii` | Dependency |

## Technical Notes
- Country code: `fi`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: template_fi.py, account_move.py, account_journal.py, res_partner.py

## Related
- [Modules/l10n_fi](Modules/l10n_fi.md) - Core accounting