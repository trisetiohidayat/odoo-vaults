---
type: module
module: l10n_pl_edi
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Poland Accounting Localization (`l10n_pl_edi`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Export FA(3) compliant XML invoices and prepare for integration with KSeF. |
| **Technical** | `l10n_pl_edi` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Export FA(3) compliant XML invoices and prepare for integration with KSeF.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_pl` | Dependency |
| `certificate` | Dependency |

## Technical Notes
- Country code: `pl` (Poland)
- Localization type: e-invoicing (FA(3) via KSeF)
- Custom model files: account_move.py, account_move_send.py, res_company.py, res_config_settings.py, res_partner.py

## Models

### `account.move` (Extended)
Polish e-invoice fields for KSeF (Krajowy System e-Faktur):
- FA(3) XML format generation
- KSeF integration preparation
- Invoice series and numbers

### `account.move.send` (Extended)
Handles sending Polish e-invoices.

### `res.company` (Extended)
KSeF credentials and Polish company settings.

### `res.partner` (Extended)
Polish partner-specific fields for e-invoicing.

## Related
- [Modules/l10n_pl](modules/l10n_pl.md) — Core Polish accounting
- [Modules/certificate](modules/certificate.md) — X.509 certificate management