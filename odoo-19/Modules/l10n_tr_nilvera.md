---
type: module
module: l10n_tr_nilvera
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Turkey Accounting Localization (`l10n_tr_nilvera`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Base module containing core functionalities required by other Nilvera modules. |
| **Technical** | `l10n_tr_nilvera` |
| **Category** | Accounting/Accounting |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Base module containing core functionalities required by other Nilvera modules.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_tr` | Dependency |

## Technical Notes
- Country code: `tr` (Turkey)
- Localization type: e-invoicing (Nilvera API)
- Custom model files: account_journal.py, l10n_tr_nilvera_alias.py, res_company.py, uom_uom.py, res_config_settings.py, res_partner.py

## Models

### `l10n_tr.nilvera.alias` (Customer Alias)
Stores Nilvera customer aliases linked to partners for Turkish e-invoicing.

**Fields:**
- `name` — Alias identifier
- `partner_id` — Related partner

### `account.journal` (Extended)
Extends journal with Nilvera-specific alias configuration.

### `res.company` (Extended)
Adds Nilvera API credentials and settings.

## Related
- [Modules/l10n_tr](Modules/l10n_tr.md) — Core Turkish accounting
- [Modules/l10n_tr_nilvera_einvoice](Modules/l10n_tr_nilvera_einvoice.md) — Turkish e-invoice via Nilvera
- [Modules/l10n_tr_nilvera_edispatch](Modules/l10n_tr_nilvera_edispatch.md) — Turkish e-despatch note via Nilvera
- [Modules/l10n_tr_nilvera_einvoice_extended](Modules/l10n_tr_nilvera_einvoice_extended.md) — Extended Turkish e-invoice features