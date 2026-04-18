---
type: module
module: l10n_om
tags: [odoo, odoo19, l10n, localization, oman, gcc]
created: 2026-04-06
---

# Oman Localization (`l10n_om`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Oman - Accounting |
| **Technical** | `l10n_om` |
| **Category** | Accounting/Localizations/Account Charts |
| **Country** | Oman |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Localized accounting for Oman. Activates chart of accounts, taxes, VAT return, fiscal positions, and country states. Depends on `l10n_gcc_invoice` for Arabic bilingual invoice support.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Core accounting module |
| `l10n_gcc_invoice` | GCC Arabic bilingual invoice support |

## Technical Notes
- Country code: `om`
- Localization type: accounting chart, taxes, VAT return, fiscal positions, and states
- Template file: `models/template_om.py` (Omani chart of accounts)
- Data files: `data/res.country.state.csv` (Oman states), `data/tax_report.xml`
- Demo data: `demo/demo_company.xml`

## Related
- [Modules/account](Modules/Account.md)
- [Modules/l10n_gcc_invoice](Modules/l10n_gcc_invoice.md)
- [Modules/l10n_sa](Modules/l10n_sa.md)
- [Modules/l10n_kw](Modules/l10n_kw.md)
- [Modules/l10n_qa](Modules/l10n_qa.md)