---
type: module
module: l10n_sg_ubl_pint
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Singapore Accounting Localization (`l10n_sg_ubl_pint`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | The UBL PINT e-invoicing format for Singapore is based on the Peppol International (PINT) model for Billing. |
| **Technical** | `l10n_sg_ubl_pint` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
The UBL PINT e-invoicing format for Singapore is based on the Peppol International (PINT) model for Billing.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account_edi_ubl_cii` | Dependency |

## Technical Notes
- Country code: `sg` (Singapore)
- Localization type: e-invoicing (UBL PINT for Peppol)
- Custom model files: account_edi_xml_pint_sg.py, account_tax.py, account_move.py, res_partner.py

## Models

### `account.edi.xml.pint_sg` (Abstract)
UBL PINT format for Singapore.

**Inherits:** `account.edi.xml.ubl_bis3`

- `_name = 'account.edi.xml.pint_sg'`
- Extends Peppol BIS3 with Singapore-specific rules

### `account.tax` (Extended)
Singapore-specific tax configuration for Peppol compliance.

### `account.move` (Extended)
Singapore-specific fields for e-invoicing.

### `res.partner` (Extended)
Singapore-specific partner fields.

## Related
- [[Modules/l10n_sg]] — Core Singapore accounting
- [[Modules/account_edi_ubl_cii]] — UBL BIS3 base for Peppol e-invoicing
- [[Modules/l10n_anz_ubl_pint]] — Australia/New Zealand PINT format
- [[Modules/l10n_jp_ubl_pint]] — Japan PINT format