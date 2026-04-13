---
type: module
module: l10n_dk_oioubl
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Denmark Accounting Localization (`l10n_dk_oioubl`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | E-invoice implementation for the Denmark |
| **Technical** | `l10n_dk_oioubl` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
E-invoice implementation for the Denmark

## Dependencies
| Module | Purpose |
|--------|---------|
| `account_edi_ubl_cii` | Dependency |
| `l10n_dk` | Dependency |

## Technical Notes
- Country code: `dk` (Denmark)
- Localization type: e-invoicing (OIOUBL 2.01)
- Custom model files: account_move.py, account_edi_xml_oioubl_201.py, res_partner.py

## Models

### `account.edi.xml.oioubl_201` (Abstract)
Danish OIOUBL 2.01 e-invoicing format (legacy, superseded by Nemhandel/OIOUBL 2.1).

**Inherits:** `account.edi.xml.ubl_21`

- `_name = 'account.edi.xml.oioubl_201'`

### `account.move` (Extended)
Danish e-invoice fields.

### `res.partner` (Extended)
Danish partner-specific fields (EAN, CVR).

## Related
- [Modules/l10n_dk](Modules/l10n_dk.md) — Core Danish accounting
- [Modules/l10n_dk_nemhandel](Modules/l10n_dk_nemhandel.md) — Newer OIOUBL 2.1 / Nemhandel format
- [Modules/account_edi_ubl_cii](Modules/account_edi_ubl_cii.md) — UBL framework