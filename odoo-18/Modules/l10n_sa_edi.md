---
Module: l10n_sa_edi
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #saudi #zatca #ubl
---

# l10n_sa_edi

## Overview
Saudi Arabian e-invoicing module for **ZATCA** (Zakat, Tax and Customs Authority) compliance. Saudi Arabia mandated e-invoicing (Fatoora) in two phases: large companies (December 2021) and all taxpayers (January 2023). This module generates UBL 2.1 invoices in the ZATCA-specific format with SHA256 hashing, digital signatures, and OTP-based submission.

## EDI Format / Standard
**UBL 2.1 ZATCA** — Saudi extension of UBL 2.1. Key features:
- SHA256 hash of previous invoice for chain integrity
- XAdES-BES XML digital signature
- Invoice type codes: 01 (tax invoice), 02 (simplified tax invoice)
- Transaction codes: NNPNESB format
- Down payment support (BR-KSA-80)
- Withholding tax exclusion from totals
- Pre-hash transformation via XSL template

## Dependencies
- `account_edi` — EDI document framework
- `account_edi_ubl_cii` — Base UBL/CII
- `account_debit_note` — Debit note support
- `l10n_sa` — Saudi chart of accounts
- `base_vat` — VAT validation
- `certificate` — For XML signing

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountEdiDocument` | `account.edi.document` | `account.edi.document` | Overrides `_prepare_jobs()` to prioritize ZATCA chain invoices |
| `AccountEdiFormat` | `account.edi.format` | `account.edi.format` | Registers `sa_zatca` format; implements `_export_invoice` |
| `AccountEdiXmlUBL21Zatca` | `account.edi.xml.ubl_21.zatca` | `account.edi.xml.ubl_21` | ZATCA UBL 2.1 format: SHA256 hashing, XAdES signature, transaction codes, payment means, tax exemption codes |
| `AccountJournal` | `account.journal` | `account.journal` | `l10n_sa_latest_submission_hash` for chain linking |
| `AccountMove` | `account.move` | `account.move` | ZATCA state, chain index, confirmation datetime, OTP wizard |
| `AccountMoveLine` | `account.move.line` | `account.move.line` | Withholding tax exclusion |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Send wizard |
| `AccountTax` | `account.tax` | `account.tax` | ZATCA exemption codes, withholding flag |
| `Certificate` | `certificate.certificate` | `certificate.certificate` | Signing certificate |
| `IrAttachment` | `ir.attachment` | `ir.attachment` | Attachment UUID generation |
| `ResCompany` | `res.company` | `res.company` | ZATCA API mode (sandbox/production), CSID credentials |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings form |
| `ResPartner` | `res.partner` | `res.partner` | TIN, additional identification scheme/number, building number, plot ID |

## Data Files
- `data/account_edi_format.xml` — EDI format registration
- `data/ubl_21_zatca.xml` — ZATCA UBL template overrides
- `data/res_country_data.xml` — Saudi-specific country data
- `data/pre-hash_invoice.xsl` — XSLT for SHA256 pre-hash transformation

## How It Works

### Chain Hashing
Each invoice includes the SHA256 hash of the previous invoice in the chain. For sandbox or first invoice, uses predefined hash of "0" character. Hash stored per journal.

### Pre-Hash Transformation
Before signing, XML is transformed via `pre-hash_invoice.xsl` to remove signature elements, canonicalized with c14n, then hashed with SHA256.

### Invoice Types
- Type 1 (tax invoice): standard B2B
- Type 2 (simplified): B2C, no buyer party details required
- Transaction code: NNPNESB (01/02, exports flag, 0, B flag)

### Down Payments
BR-KSA-80: Prepaid amounts deducted from payable amount. Tax amounts recalculated to exclude withholding.

### Tax Exemption Codes
- **S**: Standard rate
- **E**: Exempt (code VATEX-SA-29, 29-7, 30)
- **Z**: Zero-rate (codes VATEX-SA-32 through VATEX-SA-36, EDU, HEA)
- **O**: Out of scope

### OTP Flow
1. User triggers send
2. OTP requested from ZATCA via SMS
3. OTP entered in wizard
4. Invoice submitted with OTP
5. ZATCA returns confirmation

### Sandbox Mode
When `l10n_sa_api_mode == 'sandbox'`, all invoices link to predefined zero hash. Used for development and testing.

## Installation
Standard module install. Demo data available. Depends on `l10n_sa`, `account_edi_ubl_cii`, `certificate`.

## Historical Notes
- **Odoo 17**: Saudi ZATCA e-invoicing was new in Odoo 17.0
- **Odoo 18**: Version 0.2 (indicating this is still maturing). Improved chain handling, simplified invoice support, better tax exemption codes. Withholding tax support added.