---
type: module
module: l10n_es_edi_sii
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Spain Accounting Localization (`l10n_es_edi_sii`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This module sends the taxes information (mostly VAT) of the |
| **Technical** | `l10n_es_edi_sii` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This module sends the taxes information (mostly VAT) of the
vendor bills and customer invoices to the SII.  It is called
Procedimiento G417 - IVA. Llevanza de libros registro.  It is
required for every company with a turnover of +6M€ and others can
already make use of it.  The invoices are automatically
sent after validation.

How the information is sent to the SII depends on the
configuration that is put in the taxes.  The taxes
that were in the chart template (l10n_es) are automatically
configured to have the right type.  It is possible however
that extra taxes need to be created for certain exempt/no sujeta reasons.

You need to configure your certificate and the tax agency.

## Dependencies
| Module | Purpose |
|--------|---------|
| `certificate` | Dependency |
| `l10n_es` | Dependency |
| `account_edi` | Dependency |

## Technical Notes
- Country code: `es`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_move.py, account_edi_format.py, certificate.py, account_move_send.py, res_company.py, res_config_settings.py

## Related
- [[Modules/l10n_es]] - Core accounting