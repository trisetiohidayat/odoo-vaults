---
Module: l10n_es_edi_verifactu
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #spain #verifactu
---

# l10n_es_edi_verifactu

## Overview
Spanish Veri*Factu EDI module for real-time invoice reporting to the AEAT (Agencia Tributaria). Veri*Factu is the new mandatory system for all Spanish businesses from 2025/2026, replacing the older VeriFactu fiscal serialisation devices. This module submits signed invoice XML documents directly to the AEAT's Veri*Factu platform via SOAP web services.

## EDI Format / Standard
**Veri*Factu XML** — Spanish AEAT real-time invoice reporting format. Version 1.0. Uses SOAP/WSDL with Zeep client, certificate-based TLS, and XML digital signatures. Batch submission supported (up to 1000 invoices per call).

## Dependencies
- `l10n_es` — Spanish chart
- `account_edi` — EDI framework (not strictly required but provides structure)
- `certificate` — for SOAP TLS and XML signing

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `L10nEsEdiVerifactuDocument` | `l10n_es_edi_verifactu.document` | `base` | Tracks submitted documents: state, UUID, external UUID, send attempts |
| `AccountChartTemplate` | `account.chart.template` | `account.chart.template` | Tax template loading for Veri*Factu tax types |
| `AccountMove` | `account.move` | `account.move` | Links to VerifactuDocument; EDI export; cancellation |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Batch send wizard |
| `AccountTax` | `account.tax` | `account.tax` | Tax-level Veri*Factu configuration |
| `Certificate` | `certificate.certificate` | `certificate.certificate` | SOAP + XML signing certificate |
| `ResCompany` | `res.company` | `res.company` | Veri*Factu credentials: username, password, WSDL endpoint |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings form |
| `ResPartner` | `res.partner` | `res.partner` | Partner-level EDI fields |

## Data Files
- `data/ir_cron.xml` — Scheduled job for batch sending and status polling
- View files for document, move, tax, company, config

## How It Works

### Document Lifecycle
1. Invoice posted → `l10n_es_edi_verifactu.document` created in `to_send` state
2. Cron job `_cron_l10n_es_edi_verifactu_send` processes pending documents
3. Batch of up to 1000 documents submitted via SOAP `registration` operation
4. Response parsed: UUID assigned, state updated to `sent` or `error`
5. Cancellation via `cancel` operation with reason code

### Batch Submission
`BATCH_LIMIT = 1000`. Documents with same company processed together. SHA256 hash of each invoice included for deduplication.

### Signature
Uses `_sha256()` helper and Zeep SOAP client. Certificate attached to session for TLS. SOAP response includes registration result per document.

### Error Handling
- `L10nHuEdiConnectionError` exception class used for connection failures
- Retry mechanism with exponential backoff
- Error state stored on document record

## Installation
Post-init hook `_l10n_es_edi_verifactu_post_init_hook` sets up default configuration. Demo data available.

## Historical Notes
- **Odoo 18**: New module. Veri*Factu is Spain's replacement for the older VeriFactu device-based fiscal memory systems. All businesses subject to invoicing obligations must report in real-time to the AEAT.
- Uses Zeep SOAP library (added to external dependencies)
- Signature: SHA256 hash of each invoice XML for integrity, not XAdES (Veri*Factu uses different signature model)