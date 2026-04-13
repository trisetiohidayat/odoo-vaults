---
type: module
module: l10n_fr_pos_cert
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# France Accounting Localization (`l10n_fr_pos_cert`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This add-on brings the technical requirements of the French regulation CGI art. 286, I. 3° bis that stipulates certain criteria concerning the inalterability, security, storage and archiving of data r |
| **Technical** | `l10n_fr_pos_cert` |
| **Category** | Accounting/Localizations/Point of Sale |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This add-on brings the technical requirements of the French regulation CGI art. 286, I. 3° bis that stipulates certain criteria concerning the inalterability, security, storage and archiving of data related to sales to private individuals (B2C).
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

Install it if you use the Point of Sale app to sell to individuals.

The module adds following features:

    Inalterability: deactivation of all the ways to cancel or modify key data of POS orders, invoices and journal entries

    Security: chaining algorithm to verify the inalterability

    Storage: automatic sales closings with computation of both period and cumulative totals (daily, monthly, annually)

    Access to download the mandatory Certificate of Conformity delivered by Odoo SA (only for Odoo Enterprise users)

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_fr_account` | Dependency |
| `point_of_sale` | Dependency |

## Technical Notes
- Country code: `fr`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: pos.py, account_closing.py, res_company.py, account_fiscal_position.py

## Related
- [Modules/l10n_fr](odoo-18/Modules/l10n_fr.md) - Core accounting