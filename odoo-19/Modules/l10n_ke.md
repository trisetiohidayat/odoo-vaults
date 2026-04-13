---
type: module
module: l10n_ke
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Kenya Accounting Localization (`l10n_ke`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This provides a base chart of accounts and taxes template for use in Odoo. |
| **Technical** | `l10n_ke` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This provides a base chart of accounts and taxes template for use in Odoo.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |

## Technical Notes
- Country code: `ke` (Kenya)
- Localization type: accounting chart + e-invoicing
- Custom model files: account_tax.py, account_move.py, template_ke.py, res_company.py, l10n_ke_item_code.py

## Models

### `l10n_ke.item.code` (KRA Item Code)
KRA-defined codes that justify a given tax rate or exemption for Kenyan e-invoicing.

**Fields:**
- `name` — Code description

### `account.tax` (Extended)
Kenyan-specific tax fields for KRA compliance.

### `account.move` (Extended)
Kenyan e-invoicing fields (TIMS integration).

### `res.company` (Extended)
Kenyan company settings and KRA credentials.

## Related
- [Modules/l10n_ke_edi_tremol](odoo-18/Modules/l10n_ke_edi_tremol.md) — Kenyan e-invoicing via Tremol G03
- [Modules/Account](odoo-18/Modules/account.md) — Core accounting