---
type: module
module: l10n_sk
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Slovakia Accounting Localization (`l10n_sk`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Slovakia accounting chart and localization: Chart of Accounts 2020, basic VAT rates + |
| **Technical** | `l10n_sk` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Slovakia accounting chart and localization: Chart of Accounts 2020, basic VAT rates +
fiscal positions.

Tento modul definuje:
• Slovenskú účtovú osnovu za rok 2020

• Základné sadzby pre DPH z predaja a nákupu

• Základné fiškálne pozície pre slovenskú legislatívu


Pre viac informácií kontaktujte info@26house.com alebo navštívte https://www.26house.com.

## Dependencies
| Module | Purpose |
|--------|---------|
| `base_iban` | Dependency |
| `base_vat` | Dependency |
| `account` | Dependency |

## Technical Notes
- Country code: `sk`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_move.py, res_company.py, template_sk.py

## Related
- [[Modules/l10n_sk]] - Core accounting