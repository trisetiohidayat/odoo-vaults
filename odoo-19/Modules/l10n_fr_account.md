---
type: module
module: l10n_fr_account
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# France Accounting Localization (`l10n_fr_account`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This is the module to manage the accounting chart for France in Odoo. |
| **Technical** | `l10n_fr_account` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This is the module to manage the accounting chart for France in Odoo.
========================================================================

This module applies to companies based in France mainland. It doesn't apply to
companies based in the DOM-TOMs (Guadeloupe, Martinique, Guyane, Réunion, Mayotte).

This localisation module creates the VAT taxes of type 'tax included' for purchases
(it is notably required when you use the module 'hr_expense'). Beware that these
'tax included' VAT taxes are not managed by the fiscal positions provided by this
module (because it is complex to manage both 'tax excluded' and 'tax included'
scenarios in fiscal positions).

This localisation module doesn't properly handle the scenario when a France-mainland
company sells services to a company based in the DOMs. We could manage it in the
fiscal positions, but it would require to differentiate between 'product' VAT taxes
and 'service' VAT taxes. We consider that it is too 'heavy' to have this by default
in l10n_fr_account; companies that sell services to DOM-based companies should update the
configuration of their taxes and fiscal positions manually.

**Credits:** Sistheo, Zeekom, CrysaLEAD, Akretion and Camptocamp.

## Dependencies
| Module | Purpose |
|--------|---------|
| `base_iban` | Dependency |
| `base_vat` | Dependency |
| `account` | Dependency |
| `account_edi_ubl_cii` | Dependency |
| `l10n_fr` | Dependency |

## Technical Notes
- Country code: `fr`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_move.py, base_document_layout.py, template_mc.py, res_company.py, template_fr.py, res_partner.py

## Related
- [[Modules/l10n_fr]] - Core accounting