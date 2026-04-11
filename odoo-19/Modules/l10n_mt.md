---
type: module
module: l10n_mt
tags: [odoo, odoo19, l10n, localization, malta]
created: 2026-04-06
---

# Malta Localization (`l10n_mt`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Malta - Accounting |
| **Technical** | `l10n_mt` |
| **Category** | Accounting/Localizations/Account Charts |
| **Country** | Malta |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Malta basic package containing chart of accounts, taxes, and tax reports. Supports Maltese accounting standards with VAT reporting and fiscal positions. Includes UBL 2.1 EDI support via `account_edi_ubl_cii`.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Core accounting module |
| `base_vat` | Maltese VAT number validation |
| `account_edi_ubl_cii` | UBL 2.1 EDI infrastructure |

## Technical Notes
- Country code: `mt`
- Localization type: accounting chart, taxes, and tax reports
- Template file: `models/template_mt.py` (Maltese chart of accounts)
- Data files: `data/menuitem_data.xml`, `data/account_tax_report_data.xml`
- Demo data: `demo/demo_company.xml`

## Related
- [[Modules/account]]
- [[Modules/account_edi_ubl_cii]]
- [[Modules/base_vat]]
- [[Modules/l10n_mt_pos]]