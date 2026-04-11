---
type: module
module: l10n_se
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Sweden Accounting Localization (`l10n_se`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Swedish Accounting |
| **Technical** | `l10n_se` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Swedish Accounting
------------------

This is the base module to manage the accounting chart for Sweden in Odoo.
It also includes the invoice OCR payment reference handling.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |
| `base_vat` | Dependency |
| `account_edi_ubl_cii` | Dependency |

## Technical Notes
- Country code: `se`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_move.py, account_journal.py, template_se_K3.py, template_se.py, res_company.py, template_se_K2.py, res_partner.py

## Related
- [[Modules/l10n_se]] - Core accounting