---
type: module
module: l10n_es_edi_tbai
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Spain Accounting Localization (`l10n_es_edi_tbai`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This module sends invoices and vendor bills to the "Diputaciones |
| **Technical** | `l10n_es_edi_tbai` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This module sends invoices and vendor bills to the "Diputaciones
Forales" of Araba/Álava, Bizkaia and Gipuzkoa.

Invoices and bills get converted to XML and regularly sent to the
Basque government servers which provides them with a unique identifier.
A hash chain ensures the continuous nature of the invoice/bill
sequences. QR codes are added to emitted (sent/printed) invoices,
bills and tickets to allow anyone to check they have been declared.

You need to configure your certificate and the tax agency.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_es` | Dependency |
| `certificate` | Dependency |

## Technical Notes
- Country code: `es`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: l10n_es_edi_tbai_document.py, account_move.py, certificate.py, account_move_send.py, account_move_line.py, l10n_es_edi_tbai_agencies.py, res_company.py, xml_utils.py, res_config_settings.py

## Related
- [Modules/l10n_es](l10n_es.md) - Core accounting