---
type: module
module: l10n_eg_edi_eta
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Egypt Accounting Localization (`l10n_eg_edi_eta`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Egypt Tax Authority Invoice Integration |
| **Technical** | `l10n_eg_edi_eta` |
| **Category** | account |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Egypt Tax Authority Invoice Integration
==============================================================================
Integrates with the ETA portal to automatically send and sign the Invoices to the Tax Authority.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account_edi` | Dependency |
| `l10n_eg` | Dependency |

## Technical Notes
- Country code: `eg` (Egypt)
- Localization type: e-invoicing (ETA / Egyptian Tax Authority)
- Custom model files: account_move.py, account_edi_format.py, eta_thumb_drive.py, account_journal.py, product_template.py, res_company.py, uom_uom.py, res_currency_rate.py, eta_activity_type.py, res_config_settings.py, res_partner.py

## Models

### `l10n_eg_edi.thumb.drive` (Thumb Drive)
Stores USB cryptographic token (eToken) information for signing Egyptian e-invoices.

**Fields:**
- `name` — Drive identifier
- `serial_number` — eToken serial number
- `pin` — eToken PIN
- `document_count` — Number of documents signed

### `l10n_eg_edi.activity.type` (ETA Activity Type)
Lookup table for Egyptian economic activity type codes from ETA.

**Fields:**
- `name`, `code` — Activity name and ETA code

### `account.edi.format` (Extended)
Egyptian ETA e-invoice format handler:
- Generates ETA-compliant JSON/XML
- Handles thumb drive signing
- Manages submission to ETA portal

### `account.move` (Extended)
Egyptian invoice fields (ETA source, signature, submission status).

### `res.company` (Extended)
ETA credentials, thumb drive config, branch codes.

### `res.partner` (Extended)
Egyptian partner fields (activity type, address validation).

## Related
- [Modules/l10n_eg](odoo-18/Modules/l10n_eg.md) — Core Egyptian accounting
- [Modules/account_edi](odoo-17/Modules/account_edi.md) — EDI framework