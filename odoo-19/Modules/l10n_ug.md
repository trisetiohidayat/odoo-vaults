---
type: module
module: l10n_ug
tags: [odoo, odoo19, l10n, localization, uganda, africa]
created: 2026-04-06
---

# Uganda Localization (`l10n_ug`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Uganda - Accounting |
| **Technical** | `l10n_ug` |
| **Category** | Accounting/Localizations/Account Charts |
| **Country** | Uganda |
| **Version** | 1.0.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Localized accounting for Uganda. Activates chart of accounts, taxes, fiscal positions, default settings, and tax report for companies based in Uganda. Auto-installs with `account`.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Core accounting module |

## Technical Notes
- Country code: `ug`
- Localization type: accounting chart, taxes, fiscal positions, default settings, and tax report
- Template file: `models/template_ug.py` (Ugandan chart of accounts)
- Data file: `data/account_tax_report_data.xml` (tax report structure)
- Demo data: `demo/demo_company.xml`

## Related
- [Modules/account](odoo-18/Modules/account.md)
- [Modules/l10n_ke](odoo-18/Modules/l10n_ke.md)