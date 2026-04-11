---
type: module
module: l10n_no
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Norway Accounting Localization (`l10n_no`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This is the module to manage the accounting chart for Norway in Odoo. |
| **Technical** | `l10n_no` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This is the module to manage the accounting chart for Norway in Odoo.

Updated for Odoo 9 by Bringsvor Consulting AS <www.bringsvor.com>

## Dependencies
| Module | Purpose |
|--------|---------|
| `base_iban` | Dependency |
| `base_vat` | Dependency |
| `account` | Dependency |
| `account_edi_ubl_cii` | Dependency |

## Technical Notes
- Country code: `no`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: template_no.py, account_tax.py, account_move.py, account_journal.py, res_company.py, res_partner.py

## Related
- [[Modules/l10n_no]] - Core accounting