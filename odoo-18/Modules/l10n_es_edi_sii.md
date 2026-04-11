---
Module: l10n_es_edi_sii
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #spain #sii
---

# l10n_es_edi_sii

## Overview
Sends **SII (Suministro de Libros IVA)** tax reports to the Spanish Tax Agency (AEAT) via the SDI (Sedes electrónicas). Mandatory for companies with turnover exceeding EUR 6M, optional for others. Reports VAT on customer invoices and vendor bills automatically after posting.

## EDI Format / Standard
**SII XML** — AES encryption, SOAP/WSDL web service submission. Format defined by AEAT's Procedimiento G417. Tax classification uses Spanish `l10n_es_type` on `account.tax` (sujeto, exento, no_sujeto, retencion, dua, ignore).

## Dependencies
- `certificate` — SOAP signing
- `l10n_es` — Spanish chart with tax agency configuration
- `account_edi` — EDI document framework
- `pyOpenSSL` — Python external dependency for HTTPS client certificates

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountEdiFormat` | `account.edi.format` | `account.edi.format` | Registers `es_sii` EDI format; implements `_export_invoice` |
| `AccountMove` | `account.move` | `account.move` | Adds `l10n_es_edi_is_required`, `l10n_es_edi_csv`, `l10n_es_registration_date` fields; overrides draft-reset checks for SII |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | EDI send wizard; batch submission support |
| `Certificate` | `certificate.certificate` | `certificate.certificate` | Certificate for SOAP TLS |
| `ResCompany` | `res.company` | `res.company` | SII configuration: agency, certificate, tax agency URL |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | SII settings form |

## Data Files
- `data/account_edi_data.xml` — EDI format registration and SII tax type mapping

## How It Works

### Activation
- Set tax agency on company: "Agencia Estatal de la Administración Tributaria (AEAT)" or others (Bizkaia, Gipuzkoa, Navarra,绍兴)
- Configure certificate
- `l10n_es_edi_is_required` computed on moves: ES country, has tax with `l10n_es_type != 'ignore'`, company has agency configured

### Submission Flow
1. Invoice posted → EDI document created with `es_sii` format
2. `_post_to_web_service` via SOAP — registers invoice with AEAT
3. Response returns **CSV** (Código Seguro de Verificación) — stored on move
4. Automatic cancellation: if original invoice is cancelled → SII cancellation request sent
5. DUA invoices (importDeclaration): handled as a special tax type `dua`

### State Management
SII document state machine:
- `to_send` → submitted → `sent` or `error`
- `to_cancel` → cancellation submitted → `cancelled`

Reset to draft is blocked for SII invoices that have been successfully submitted (unless cancelled first via AEAT).

## Installation
Install after `l10n_es`. Post-init hook sets up EDI format configuration. Demo data: `demo/demo_certificate.xml`, `demo/demo_company.xml`.

## Historical Notes
- **Odoo 17 → 18**: SII format largely stable; SOAP client modernized; error handling improved for timeout/retry scenarios; batch submission support added for vendor bills
- Version bumped from 1.0 to 1.1 in 18.0