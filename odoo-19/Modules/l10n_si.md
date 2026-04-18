---
type: module
module: l10n_si
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Slovenia Accounting Localization (`l10n_si`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Chart of accounts and taxes for Slovenia. |
| **Technical** | `l10n_si` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Chart of accounts and taxes for Slovenia.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |
| `base_vat` | Dependency |
| `account_edi_ubl_cii` | Dependency |

## Technical Notes
- Country code: `si` (Slovenia)
- Localization type: accounting chart + e-invoicing
- Custom model files: template_si.py, account_move.py, account_journal.py

## Models

### `account.journal` (Extended)
Slovenian journal-specific settings.

### `account.move` (Extended)
Slovenian invoice/e-invoice fields.

## Key Features
- Slovenian chart of accounts (SRS)
- Standard VAT rates (22%, 9.5%)
- UBL e-invoice support

## Related
- [Modules/Account](Modules/Account.md) — Core accounting
- [Modules/account_edi_ubl_cii](Modules/account_edi_ubl_cii.md) — UBL e-invoicing