---
type: module
module: l10n_ke_edi_tremol
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Kenya Accounting Localization (`l10n_ke_edi_tremol`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This module integrates with the Kenyan G03 Tremol control unit device to the KRA through TIMS. |
| **Technical** | `l10n_ke_edi_tremol` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This module integrates with the Kenyan G03 Tremol control unit device to the KRA through TIMS.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_ke` | Dependency |

## Technical Notes
- Country code: `ke` (Kenya)
- Localization type: e-invoicing (Tremol G03 control unit via KRA TIMS)
- Custom model files: account_move.py, account_move_send.py, res_company.py, res_config_settings.py, res_partner.py

## Models

### `account.move` (Extended)
Extends invoice/journal entry with Kenya-specific e-invoicing fields:
- KRA TIMS integration fields
- Tremol G03 control unit data
- Invoice serial numbers for fiscal device

### `account.move.send` (Extended)
Handles sending Kenya e-invoices via Tremol device integration.

### `res.company` (Extended)
Tremol device configuration and KRA credentials.

### `res.partner` (Extended)
Kenyan partner-specific fields for e-invoicing.

## Related
- [[Modules/l10n_ke]] — Core Kenyan accounting
- [[Modules/account_edi_proxy_client]] — EDI proxy framework