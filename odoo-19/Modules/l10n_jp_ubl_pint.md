---
type: module
module: l10n_jp_ubl_pint
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Japan Accounting Localization (`l10n_jp_ubl_pint`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | The UBL PINT e-invoicing format for Japan is based on the Peppol International (PINT) model for Billing. |
| **Technical** | `l10n_jp_ubl_pint` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
The UBL PINT e-invoicing format for Japan is based on the Peppol International (PINT) model for Billing.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account_edi_ubl_cii` | Dependency |

## Technical Notes
- Country code: `jp` (Japan)
- Localization type: e-invoicing (UBL PINT for Peppol)
- Custom model files: account_edi_xml_pint_jp.py, res_partner.py

## Models

### `account.edi.xml.pint_jp` (Abstract)
UBL PINT format for Japan.

**Inherits:** `account.edi.xml.ubl_bis3`

- `_name = 'account.edi.xml.pint_jp'`
- Extends Peppol BIS3 with Japan-specific rules

### `res.partner` (Extended)
Extends partner with Japanese EDI-specific fields.

## Related
- [Modules/l10n_jp](Modules/l10n_jp.md) — Core Japanese accounting
- [Modules/account_edi_ubl_cii](Modules/account_edi_ubl_cii.md) — UBL BIS3 base for Peppol e-invoicing
- [Modules/l10n_anz_ubl_pint](Modules/l10n_anz_ubl_pint.md) — Australia/New Zealand PINT format
- [Modules/l10n_sg_ubl_pint](Modules/l10n_sg_ubl_pint.md) — Singapore PINT format