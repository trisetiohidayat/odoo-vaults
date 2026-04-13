---
type: module
module: l10n_es_edi_facturae
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Spain Accounting Localization (`l10n_es_edi_facturae`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This module create the Facturae file required to send the invoices information to the General State Administrations. |
| **Technical** | `l10n_es_edi_facturae` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This module create the Facturae file required to send the invoices information to the General State Administrations.
It allows the export and signature of the signing of Facturae files.
The current version of Facturae supported is the 3.2.2

for more informations, see https://www.facturae.gob.es/face/Paginas/FACE.aspx

## Dependencies
| Module | Purpose |
|--------|---------|
| `certificate` | Dependency |
| `l10n_es` | Dependency |

## Technical Notes
- Country code: `es`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_tax.py, account_move.py, certificate.py, account_move_send.py, res_company.py, uom_uom.py, account_chart_template.py, res_partner.py

## Related
- [Modules/l10n_es](Modules/l10n_es.md) - Core accounting