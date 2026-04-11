---
type: module
module: l10n_in_ewaybill
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# India Accounting Localization (`l10n_in_ewaybill`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Indian - E-waybill |
| **Technical** | `l10n_in_ewaybill` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Indian - E-waybill
====================================
To submit E-waybill through API to the government.
We use "Tera Software Limited" as GSP

Step 1: First you need to create an API username and password in the E-waybill portal.
Step 2: Switch to company related to that GST number
Step 3: Set that username and password in Odoo (Goto: Invoicing/Accounting -> Configration -> Settings -> Indian Electronic WayBill or find "E-waybill" in search bar)
Step 4: Repeat steps 1,2,3 for all GSTIN you have in odoo. If you have a multi-company with the same GST number then perform step 1 for the first company only.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_in` | Dependency |

## Technical Notes
- Country code: `in`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_move.py, ir_attachment.py, res_company.py, res_config_settings.py, l10n_in_ewaybill.py, ewaybill_type.py, error_codes.py

## Related
- [[Modules/l10n_in]] - Core accounting