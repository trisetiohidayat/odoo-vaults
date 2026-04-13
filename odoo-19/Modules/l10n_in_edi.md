---
type: module
module: l10n_in_edi
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# India Accounting Localization (`l10n_in_edi`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Indian - E-invoicing |
| **Technical** | `l10n_in_edi` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Indian - E-invoicing
====================
To submit invoicing through API to the government.
We use "Tera Software Limited" as GSP
Step 1: First you need to create an API username and password in the E-invoice portal.
Step 2: Switch to company related to that GST number
Step 3: Set that username and password in Odoo (Goto: Invoicing/Accounting -> Configuration -> Settings -> Customer Invoices or find "E-invoice" in search bar)
Step 4: Repeat steps 1,2,3 for all GSTIN you have in odoo. If you have a multi-company with the same GST number then perform step 1 for the first company only.
For the creation of API username and password please ref this document: <https://service.odoo.co.in/einvoice_create_api_user>

## Dependencies
| Module | Purpose |
|--------|---------|
| `account_edi` | Dependency |
| `l10n_in` | Dependency |

## Technical Notes
- Country code: `in` (India)
- Localization type: e-invoicing (GST e-invoice via IRN)
- GSP: Tera Software Limited
- Custom model files: account_move.py, ir_attachment.py, account_move_send.py, account_move_line.py, res_company.py, res_config_settings.py, res_partner.py

## Models

### `account.move` (Extended)
Indian e-invoice fields:
- IRN (Invoice Registration Number) from GST portal
- QR code generation for e-invoice
- Ack number and date
- E-invoice status tracking

### `res.company` (Extended)
E-invoice API credentials (username/password) per company.

### `res.partner` (Extended)
Indian GSTIN validation and partner fields.

## Related
- [Modules/l10n_in](Modules/l10n_in.md) — Core Indian accounting
- [Modules/l10n_in_edi](Modules/l10n_in_edi.md) — Indian e-invoice base
- [Modules/l10n_in_ewaybill](Modules/l10n_in_ewaybill.md) — Indian e-waybill
- [Modules/account_edi](Modules/account_edi.md) — EDI framework