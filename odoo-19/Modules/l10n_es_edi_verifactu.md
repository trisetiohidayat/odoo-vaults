---
type: module
module: l10n_es_edi_verifactu
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Spain Accounting Localization (`l10n_es_edi_verifactu`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Module for sending Spanish Veri*Factu XML to the AEAT |
| **Technical** | `l10n_es_edi_verifactu` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Module for sending Spanish Veri*Factu XML to the AEAT

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_es` | Dependency |

## Technical Notes
- Country code: `es` (Spain)
- Localization type: e-invoicing (Veri*Factu for AEAT)
- Custom model files: account_tax.py, account_move.py, certificate.py, verifactu_document.py, account_move_send.py, res_company.py, account_chart_template.py, res_config_settings.py, res_partner.py

## Models

### `l10n_es_edi_verifactu.document` (Veri*Factu Document)
Stores Veri*Factu billing records for the Spanish Tax Agency (AEAT).

**Fields:**
- `name`, `date`, `company_id`, `xml_attachment_id`
- `state` — `to_send`, `pending`, `accepted`, `rejected`
- `chain_index` — Position in the signature chain
- `response_message` — Response from AEAT
- `is_cancel` — Whether this is a cancellation record

**Key Methods:**
- `_create_for_record()` — Creates Veri*Factu submission or cancellation document for a given record
- `trigger_next_batch()` — Sends all waiting documents via SOAP (AEAT API)
- `_generate_verifactu_document()` — Builds the Veri*Factu XML document
- `_l10n_es_edi_verifactu_get_endpoints()` — Gets WSDL endpoints from company settings
- `_post_to_aeat()` — Sends SOAP request to AEAT with X.509 certificate auth
- `_process_response()` — Handles AEAT response

**Technical Notes:**
- Uses SOAP/WSDL via zeep for AEAT communication
- Certificate-based authentication via `certificate` module
- Chain integrity: each document references the preceding document's signature (SHA256)
- Minimum 60-second delay between submissions (or batch of 1000)
- Veri*Factu version: 1.0
- Uses `zeep` for WSDL operations with certificate binding

### `account.move` (Extended)
- `_l10n_es_edi_verifactu_get_name()` — Generates Veri*Factu document number

### `account.move.send` (Extended)
- `._l10n_es_edi_verifactu_get_extra_attachments()` — Includes Veri*Factu XML in email

### `account.chart.template` (Extended)
- Adds Veri*Factu chart template data

### `res.company` (Extended)
- `_l10n_es_edi_verifactu_get_certificate()` — Gets TLS certificate for AEAT auth
- `_l10n_es_edi_verifactu_get_endpoints()` — Returns WSDL URLs

## Related
- [Modules/l10n_es](l10n_es.md) — Core Spanish accounting chart
- [Modules/l10n_es_edi_sii](l10n_es_edi_sii.md) — SII (Immediate Supply of Information) module
- [Modules/l10n_es_edi_tbai](l10n_es_edi_tbai.md) — TicketBAI (Basque country) module
- [Modules/certificate](certificate.md) — X.509 certificate management