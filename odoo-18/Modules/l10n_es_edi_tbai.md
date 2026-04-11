---
Module: l10n_es_edi_tbai
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #spain #ticketbai #basque
---

# l10n_es_edi_tbai

## Overview
Sends invoices and vendor bills to the **TicketBAI** system of the three Basque Country provinces: Araba, Bizkaia, and Gipuzkoa. Generates XML documents with XAdES signature, assigns a chain-based sequence number, and produces QR codes for verification. This is the mandatory e-invoicing system for the Basque Country.

## EDI Format / Standard
**TicketBAI XML v1.2** — Basque government format with XAdES-BES signature. Separate endpoints for each tax agency. For Bizkaia, invoices are wrapped in **LROE** (Libro Registro de Operaciones Empresariales) format and gzip-compressed. Chain integrity guaranteed via hash linking.

## Dependencies
- `l10n_es` — Spanish chart
- `certificate` — for digital signature
- No account_edi dependency — uses custom document model `l10n_es_edi_tbai.document`

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `L10nEsEdiTbaiDocument` | `l10n_es_edi_tbai.document` | `base` | Core document tracking: chain index, state (to_send/accepted/rejected), XML attachment, response |
| `AccountMove` | `account.move` | `account.move` | Links to TBaiDocument; serializes invoice to XML; manages send/cancel |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Send wizard integration |
| `AccountMoveLine` | `account.move.line` | `account.move.line` | Adds TBai-required fields |
| `AccountTax` | `account.tax` | `account.tax` | Tax classification: type (sujeto/exento/recargo/no_sujeto/retencion), exempt reason, bien_inversion flag |
| `Certificate` | `certificate.certificate` | `certificate.certificate` | Certificate for signature and SOAP TLS |
| `ResCompany` | `res.company` | `res.company` | Tax agency selection, certificate link, license dict |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings form |
| `L10nEsEdiTbaiAgencies` | `l10n_es_edi_tbai.agencies` | `base` | Tax agency endpoint registry (URLs, signature policies, QR URLs) |

## Data Files
- `data/template_invoice.xml` — QWeb invoice XML template
- `data/template_LROE_bizkaia.xml` — LROE wrapper for Bizkaia vendor bills
- `data/ir_config_parameter.xml` — Configuration parameters

## How It Works

### Chain Integrity
TicketBAI uses a hash chain: each document's signature is included in the next document's hash. The chain head must be accepted by the government before the next can be submitted. Chain index assigned from a dedicated sequence per company.

### Document Generation
1. On invoice post: `l10n_es_edi_tbai.document` record created
2. `_generate_xml(values)` renders QWeb template with:
   - Sender/recipient data
   - Tax breakdown (sujeta/no-exenta, exenta, no-sujeto, ISP)
   - Regime codes, refund references
3. `_sign_sale_document()` applies XAdES-BES signature using company certificate
4. For Bizkaia sale invoices: XML wrapped in LROE format and gzip-compressed

### Web Service Submission
- **Araba/Gipuzkoa**: Direct POST with XML, response parsed for status code
- **Bizkaia**: gzip-compressed LROE wrapper with JSON headers (`eus-bizkaia-n3-*`), response checked via `EstadoRegistro`

### Response Processing
- Accepted: `state='accepted'`, chain_index set, XML attached
- Rejected: `state='rejected'`, chain_index reset to 0
- Duplicate accepted (codes 005/019): treated as success

### QR Code
QR URL format: `https://tbai-app.{agency}/?id={TBAID}&s={sequence}&nf={number}&i={amount}&cr={crc8}` — CRC8 computed from the URL without the CRC suffix.

## Installation
Install after `l10n_es`. Post-init hook loads certificate and agency defaults. Demo data includes demo certificate, partner, and company.

## Historical Notes
- **Odoo 17**: TicketBAI was a new module; LROE support was partial
- **Odoo 18**: Version 1.1; freelancer mode (epigrafe) for Bizkaia; improved foreign customer validation; better XML signing cleanup; full vendor bill (purchase) support via Bizkaia LROE; refund reason validation (R5 for simplified only)
- Signature uses SHA1 for compatibility with government systems; XAdES-BES profile