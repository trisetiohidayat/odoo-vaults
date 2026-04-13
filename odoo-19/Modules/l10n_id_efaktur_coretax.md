---
type: module
module: l10n_id_efaktur_coretax
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Indonesia Accounting Localization (`l10n_id_efaktur_coretax`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | E-invoicing feature provided by DJP (Indonesian Tax Office). As of January 1st 2025, |
| **Technical** | `l10n_id_efaktur_coretax` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
E-invoicing feature provided by DJP (Indonesian Tax Office). As of January 1st 2025,
        Indonesia is using CoreTax system, which changes the file format and content of E-Faktur.
        We're changing from CSV files into XML.
        At the same time, due to tax regulation changes back and forth, for general E-Faktur now,
        TaxBase (DPP) has to be mulitplied by factor of 11/12 while multiplied to tax of 12% which
        is resulting to 11%.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_id` | Dependency |

## Technical Notes
- Country code: `id`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_move.py, account_move_line.py, product_template.py, uom_code.py, uom_uom.py, efaktur_document.py, product_code.py, res_partner.py

## Related
- [Modules/l10n_id](Modules/l10n_id.md) - Core accounting