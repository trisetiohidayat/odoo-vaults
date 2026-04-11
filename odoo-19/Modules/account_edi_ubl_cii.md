---
title: Account EDI UBL CII
description: Import/export electronic invoices in UBL Bis 3, EHF3, NLCIUS, Factur-X (CII), and XRechnung formats. Peppol endpoint management for res.partner.
tags: [odoo19, accounting, edi, ubl, peppol, einvoicing, module]
model_count: 3
models:
  - account.tax (UBL/CII tax category and exemption codes)
  - res.partner (invoice_edi_format, peppol_endpoint, peppol_eas)
dependencies:
  - account
category: Accounting/Accounting
source: odoo/addons/account_edi_ubl_cii/
created: 2026-04-06
---

# Account EDI UBL CII

## Overview

**Module:** `account_edi_ubl_cii`
**Category:** Accounting/Accounting
**Depends:** `account`
**Auto-install:** Yes
**License:** LGPL-3

Electronic invoicing module supporting import and export of:
- **UBL Bis 3.0** — EU-wide Peppol standard
- **EHF 3.0** — Norwegian standard (fully implemented by UBL Bis 3)
- **NLCIUS** — Dutch standard
- **Factur-X / CII** — French/Chorus Pro standard (PDF/A-3 embedded XML)
- **XRechnung (UBL)** — German standard
- **UBL Bis 3 A-NZ** — Australian/New Zealand
- **UBL Bis 3 SG** — Singapore

Country restrictions: E-FFF (NL), NLCIUS (NL), XRechnung (DE). UBL Bis 3 is available for all countries in the Peppol EAS list.

## Key Features

- Export invoices as XML in multiple EDI formats
- PDF embedding: UBL formats embed the PDF inside the XML for single-file retrieval
- Peppol endpoint management on `res.partner` (EAS codes, endpoint validation)
- Tax category and exemption reason codes for EDI compliance
- Country-specific format suggestions based on partner country
- Factur-X PDF/A-3 option for Chorus Pro auto-detection
- Format selection per journal (Journal > Advanced Settings)
- Automatic Peppol EAS mapping by country

## Models

### res.partner (inherited)

Extends partner with Peppol EDI fields.

| Field | Type | Description |
|-------|------|-------------|
| `invoice_edi_format` | Selection | Preferred EDI format: `facturx`, `ubl_bis3`, `xrechnung`, `nlcius`, `ubl_a_nz`, `ubl_sg` |
| `is_ubl_format` | Boolean (computed) | True if format is a UBL/CII format |
| `is_peppol_edi_format` | Boolean (computed) | True if format is on Peppol network |
| `peppol_endpoint` | Char | Peppol unique identifier / endpoint ID |
| `peppol_eas` | Selection | Peppol E-Address (EAS) code — ~60 country-specific codes |
| `available_peppol_eas` | Json (computed) | EAS codes available for the partner's country |

**Peppol EAS Codes Supported:** Albania VAT, Andorra VAT, Australia ABN, Austria UID/VOKZ, Belgium Company Registry/VAT, Bosnia VAT, Bulgaria VAT, Croatia VAT, Cyprus VAT, Czech VAT, Denmark P/CVR/SE, Estonia Company/VAT, Finland LY-tunnus/OVT/VAT, France SIRENE/SIRET/VAT/FRCTC/Register, Germany Leitweg-ID/VAT, Greece VAT, Hungary VAT, Iceland Kennitala, Ireland VAT, Italy Partita IVA/FTI, Japan SST/IIN, Latvia RegNo/VAT, Liechtenstein VAT, Lithuania JAK/VAT, Luxembourg VAT, Macedonia VAT, Malaysia, Malta VAT, Monaco VAT, Montenegro VAT, Netherlands KvK/OIN/VAT, Norway Org.nr., Poland VAT, Portugal VAT, Romania VAT, Serbia VAT, Singapore UEN, Slovenia VAT, Slovakia VAT, Spain VAT, Sweden Org.nr./VAT, Swiss VAT/UIDB, Turkey VAT, UAE TIN, UK VAT, USA EIN, plus GLN, EAN, DUNS, LEI, S.W.I.F.T, and more.

**Key Methods:**
- `_check_peppol_fields()` — validates endpoint format against EAS rules (Belgian 10-digit, SIRET, Swedish 10-digit, general 1-50 alphanumeric)
- `_get_ubl_cii_formats()` / `_get_ubl_cii_formats_info()` — returns available formats with country lists and `on_peppol` flag
- `_get_ubl_cii_formats_by_country()` — maps country codes to available formats
- `_get_suggested_ubl_cii_edi_format()` — suggests format based on partner country (lowest sequence wins)
- `_get_suggested_peppol_edi_format()` — returns suggested or falls back to `ubl_bis3`
- `_get_peppol_edi_format()` — returns `invoice_edi_format` or suggested format
- `_get_peppol_formats()` — returns formats where `on_peppol=True`
- `_compute_is_ubl_format()` / `_compute_is_peppol_edi_format()` — computed based on `invoice_edi_format`
- `_compute_peppol_endpoint()` — auto-sets endpoint from country/EAS field mapping (e.g., company_registry for BE VAT)
- `_compute_peppol_eas()` — auto-selects EAS based on country if current EAS not valid
- `_compute_available_peppol_eas()` — returns list of EAS options for the country (overridable by localization modules)
- `_build_error_peppol_endpoint()` — validates endpoint format per EAS rules
- `_get_edi_builder()` — returns the appropriate `account.edi.xml.*` model for the format

### account.tax (inherited)

Extends tax with EDI-specific metadata.

| Field | Type | Description |
|-------|------|-------------|
| `ubl_cii_tax_category_code` | Selection | VAT category code for EDI: `AE`, `E`, `S`, `Z`, `G`, `O`, `K`, `L`, `M`, `B` |
| `ubl_cii_tax_exemption_reason_code` | Selection | EU VAT exemption reason code (100+ codes from VATEX-*, VATEX-FR-*) |
| `ubl_cii_requires_exemption_reason` | Boolean (computed) | True if category is `AE`, `E`, `G`, `O`, or `K` |

**Key Methods:**
- `_compute_ubl_cii_requires_exemption_reason()` — auto-computes if exemption reason is required
- `_onchange_ubl_cii_tax_category_code()` — clears exemption reason when no longer required

## Format Details

| Format | Country | Peppol | Embed PDF | Tax Exempt Codes |
|--------|---------|--------|-----------|-----------------|
| `facturx` | FR | No | Yes (PDF/A-3) | Yes |
| `ubl_bis3` | EU-wide | Yes | Yes | Yes |
| `xrechnung` | DE | Yes | Yes | Yes |
| `nlcius` | NL | Yes | No | Yes |
| `ubl_a_nz` | AU/NZ | No | No | No |
| `ubl_sg` | SG | No | No | No |

## Source Files

- `models/account_edi_common.py` — UBL/CII format registry, Peppol EAS mapping, format builder lookup
- `models/res_partner.py` — partner EDI format, Peppol endpoint/EAS fields
- `models/account_tax.py` — tax category and exemption reason codes

## Related Modules

Format implementations live in separate modules:
- `account_edi_ubl_20` / `account_edi_ubl_21` — UBL 2.0/2.1 base implementations
- `account_edi_xml_ubl_bis3` — Peppol Bis 3.0
- `account_edi_xml_cii_facturx` — Factur-X / CII
- `account_edi_xml_ubl_xrechnung` — German XRechnung (UBL DE)
- `account_edi_xml_ubl_nlcius` — Dutch NLCIUS
- `account_edi_xml_ubl_efff` — E-FFF (NL)
- `account_edi_xml_ubl_a_nz` — Australian/New Zealand
- `account_edi_xml_ubl_sg` — Singapore
