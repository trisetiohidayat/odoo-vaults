---
type: module
module: l10n_fr_facturx_chorus_pro
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# France Accounting Localization (`l10n_fr_facturx_chorus_pro`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Add support to fill three fields used when using Chorus Pro, especially when invoicing public services. |
| **Technical** | `l10n_fr_facturx_chorus_pro` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Add support to fill three fields used when using Chorus Pro, especially when invoicing public services.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |
| `account_edi_ubl_cii` | Dependency |
| `l10n_fr_account` | Dependency |

## Technical Notes
- Country code: `fr` (France)
- Localization type: e-invoicing (Factur-X via Chorus Pro)
- Custom model files: account_move.py, account_edi_xml_ubl_bis3.py

## Models

### `account.edi.xml.ubl_bis3` (Extended)
Extends UBL BIS3 with French Chorus Pro-specific fields:
- Three extra mandatory fields for Chorus Pro invoicing of public services
- Factur-X / ZUGFeRD hybrid format support

### `account.move` (Extended)
Chorus Pro-specific invoice fields (service type, contract reference, etc.).

## Related
- [Modules/l10n_fr_account](l10n_fr_account.md) — French accounting chart
- [Modules/account_edi_ubl_cii](account_edi_ubl_cii.md) — UBL BIS3 framework