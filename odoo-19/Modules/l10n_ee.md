---
type: module
module: l10n_ee
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Estonia Accounting Localization (`l10n_ee`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This is the base module to manage the accounting chart for Estonia in Odoo. |
| **Technical** | `l10n_ee` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This is the base module to manage the accounting chart for Estonia in Odoo.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |
| `account_edi_ubl_cii` | Dependency |

## Technical Notes
- Country code: `ee` (Estonia)
- Localization type: accounting chart + e-invoicing
- Custom model files: account_tax.py, template_ee.py, res_company.py

## Models

### `account.tax` (Extended)
Estonian-specific tax fields.

### `res.company` (Extended)
Estonian company settings.

## Key Features
- Estonian chart of accounts template
- Standard VAT rates (22%, 9%)
- B2C e-invoice support via UBL

## Related
- [Modules/Account](Modules/account.md) — Core accounting
- [Modules/account_edi_ubl_cii](Modules/account_edi_ubl_cii.md) — UBL e-invoicing