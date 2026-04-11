---
type: module
module: l10n_jo_edi
tags: [odoo, odoo19, l10n, localization, jordan, edi, einvoice, ubl, jofotara]
created: 2026-04-06
---

# Jordan E-Invoicing (`l10n_jo_edi`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Jordan E-Invoicing |
| **Technical** | `l10n_jo_edi` |
| **Category** | Accounting/Localizations/EDI |
| **Country** | Jordan |
| **Summary** | Electronic Invoicing for Jordan UBL 2.1 |
| **Author** | Odoo S.A., Smart Way Business Solutions |
| **License** | LGPL-3 |

## Description
Electronic Invoicing for Jordan via JoFotara integration. Generates and sends UBL 2.1 compliant invoices to the Jordanian tax authority through the JoFotara platform.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account_edi_ubl_cii` | UBL 2.1 EDI infrastructure |
| `l10n_jo` | Jordan base accounting localization |

## Key Models

### `account.edi.xml.ubl_21.jo` (Abstract)
Inherits `account.edi.xml.ubl_21` to implement Jordan-specific UBL 2.1 export:

| Feature | Description |
|---------|-------------|
| Document type | Forces `invoice` for both invoices and credit/debit notes |
| Fixed taxes | Reported as taxes (not AllowanceCharges) |
| Currency rounding | 9 decimal places (JO currency namespace) |
| Invoice lines | Per-line rounding with 9 decimals |

### `account.move` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `l10n_jo_edi_status` | Selection | EDI submission status |
| `l10n_jo_edi_message` | Text | EDI response message |

### `account.move.send` (Extended)
Handles sending invoices to JoFotara via the EDI framework.

### `ir.attachment` (Extended)
Stores and manages EDI attachments for Jordanian invoices.

### `res.company` (Extended)
Company-level JoFotara API configuration fields.

### `res.config.settings` (Extended)
Settings view for JoFotara API credentials and configuration.

## Technical Notes
- Auto-installs with: `l10n_jo`
- Post-init hook: `_post_init_hook`
- Views: invoice views, report templates, res config settings
- UBL format: ISO UBL 2.1 adapted for Jordan

## Related
- [[Modules/account]]
- [[Modules/account_edi_ubl_cii]]
- [[Modules/l10n_jo]]