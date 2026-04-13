---
type: module
module: l10n_cz
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Czech Republic Accounting Localization (`l10n_cz`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Czech accounting chart and localization.  With Chart of Accounts with taxes and basic fiscal positions. |
| **Technical** | `l10n_cz` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Czech accounting chart and localization.  With Chart of Accounts with taxes and basic fiscal positions.

Tento modul definuje:

- Českou účetní osnovu za rok 2020

- Základní sazby pro DPH z prodeje a nákupu

- Základní fiskální pozice pro českou legislativu

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |
| `account_edi_ubl_cii` | Dependency |
| `base_iban` | Dependency |
| `base_vat` | Dependency |

## Technical Notes
- Country code: `cz`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_move.py, template_cz.py, l10n_cz_tax_office.py, res_company.py

## Related
- [Modules/l10n_cz](modules/l10n_cz.md) - Core accounting