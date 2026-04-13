---
type: module
module: l10n_lu
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Luxembourg Accounting Localization (`l10n_lu`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This is the base module to manage the accounting chart for Luxembourg. |
| **Technical** | `l10n_lu` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This is the base module to manage the accounting chart for Luxembourg.
======================================================================

    * the Luxembourg Official Chart of Accounts (law of June 2009 + 2015 chart and Taxes),
    * the Tax Code Chart for Luxembourg
    * the main taxes used in Luxembourg
    * default fiscal position for local, intracom, extracom

Notes:
    * the 2015 chart of taxes is implemented to a large extent,
      see the first sheet of tax.xls for details of coverage
    * to update the chart of tax template, update tax.xls and run tax2csv.py

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |
| `base_iban` | Dependency |
| `base_vat` | Dependency |
| `account_edi_ubl_cii` | Dependency |

## Technical Notes
- Country code: `lu`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: template_lu.py

## Related
- [Modules/l10n_lu](l10n_lu.md) - Core accounting