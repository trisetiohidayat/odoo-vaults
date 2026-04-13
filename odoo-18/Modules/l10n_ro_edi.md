---
Module: l10n_ro_edi
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #romania #einvoice #anaf
---

# l10n_ro_edi

## Overview
Romanian e-invoicing module integrating with **ANAF** (National Agency for Fiscal Administration) via the e-Factura system. Romania mandated B2B e-invoice reporting starting January 2024 for large companies, expanding to all businesses. This module generates, submits, and manages e-invoices in the Romanian UBL 2.1 CIUS-RO format.

## EDI Format / Standard
**UBL 2.1 CIUS-RO** — Romanian extension of UBL 2.1 (Core Invoice Usage Specification). Specific elements for Romanian fiscal requirements: VAT split payment indicator, series/number formatting, Romanian tax codes. Submits via ANAF API using `account_edi_proxy_client`.

## Dependencies
- `account_edi_ubl_cii` — Base UBL/CII framework
- `l10n_ro` — Romanian chart of accounts

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountEdiXmlUBLRO` | `account.edi.xml.ubl.ro` | `account.edi.xml.ubl_21` | CIUS-RO format generator: Romanian invoice type codes, series, VAT registration validation |
| `AccountEdiXmlUBLCIUSRO` | `account.edi.xml.ubl.ciusro` | `account.edi.xml.ubl_21` | Common CIUS-RO format (also used by [Modules/l10n_rs_edi](Modules/l10n_rs_edi.md)) |
| `AccountMove` | `account.move` | `account.move` | Romanian EDI state tracking |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Send wizard integration |
| `L10nRoEdiDocument` | `l10n_ro_edi.document` | `base` | Document tracking: state, message, external ID, send date |
| `ResCompany` | `res.company` | `res.company` | ANAF credentials, proxy user |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings form |
| `ResPartner` | `res.partner` | `res.partner` | Romanian company ID (J/Ro number) |
| `CIUSRODocument` | `ciusro.document` | `base` | Base document for CIUS-RO format tracking |
| `AccountEdiFormat` | `account.edi.format` | `account.edi.format` | EDI format registration |

## Data Files
- `data/ir_cron.xml` — Cron for batch sending and status sync
- `security/ir.model.access.csv` — Access control

## How It Works

### CIUS-RO Format
CIUS-RO (Core Invoice Usage Specification for Romania) is a Romanian profile of EN 16931. Extends UBL 2.1 with:
- Invoice type: "380" (commercial invoice), "381" (credit note), "383" (debit note)
- Series: alphanumeric, up to 10 chars
- VAT split payment indicator when applicable
- Romanian-specific tax codes

### ANAF API
- Uses `account_edi_proxy_client` to communicate with ANAF
- Registration of invoice with ANAF
- Status polling
- Cancellation requests

### Document Tracking
`L10nRoEdiDocument` tracks submission state independently of `account.edi.document`:
- State: `pending`, `sent`, `accepted`, `rejected`, `cancelled`
- Stores ANAF-assigned ID and send timestamp

## Installation
Auto-installs with `l10n_ro`. Standard module installation.

## Historical Notes
- **Odoo 17**: Romanian e-invoicing was not available in standard Odoo
- **Odoo 18**: First complete ANAF e-Factura integration. Romania mandated e-invoicing for B2B transactions. Phased rollout by company size.