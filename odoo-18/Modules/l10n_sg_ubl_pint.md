---
Module: l10n_sg_ubl_pint
Version: 18.0
Type: l10n/singapore/edi
Tags: #odoo18 #l10n #edi #peppol
---

# l10n_sg_ubl_pint

## Overview
Singapore Peppol PINT e-invoicing module. Provides the Singapore implementation of the Peppol International (PINT) Billing standard for IRAS e-Invoice compliance. Built on `account_edi_ubl_cii_tax_extension` and BIS Billing 3. Singapore's IRAS mandates e-invoice submission via Peppol.

## Country
Singapore

## Dependencies
- [Core/BaseModel](core/basemodel.md) (account_edi_ubl_cii_tax_extension)
- `account_edi_ubl_cii_tax_extension` — extended UBL/CII with tax category codes

## Key Models

### AccountEdiXmlUBLPINTSG (`account.edi.xml.ubl_bis3`, abstract)
- `_name = 'account.edi.xml.pint_sg'`
- `_export_invoice_filename()` — `filename_pint_sg.xml`
- `_get_partner_party_vals()` — sets all `tax_scheme_vals` to `{'id': 'GST'}` for all tax scheme entries
- `_get_invoice_tax_totals_vals_list()` — adds second TaxTotal section in SGD (accounting currency) when invoice currency differs; see SG PINT spec
- `_get_tax_category_list()` — sets all tax category entries to `tax_scheme_vals: {'id': 'GST'}`
- `_get_additional_document_reference_list()` — when currency ≠ SGD, adds `sgdtotal-excl-gst` and `sgdtotal-incl-gst` document references per [BR-53-GST-SG]
- `_export_invoice_vals()` — sets `customization_id: pint_sg`, `profile_id: urn:peppol:bis:billing`, `uuid` from `_l10n_sg_get_uuid()`
- `_export_invoice_constraints()` — validates SG VAT category codes on all taxes; validates seller street address and post code are set for SR/ZR/SRRC/SROVR categories

### AccountMove (`account.move`, classic extension)
- `_l10n_sg_get_uuid()` — generates deterministic UUID from database UUID + move ID; avoids storing a new field on the move

### AccountTax (`account.tax`, classic extension)
Extends `ubl_cii_tax_category_code` with Singapore-specific codes:
- `SR` — Local supply of goods and services
- `SRCA-S` — Customer accounting supply made by the supplier
- `SRCA-C` — Customer accounting supply made by the customer on supplier's behalf
- `SROVR-RS` — Remote services under Overseas Vendor Registration Regime
- `SROVR-LVG` — Low-value goods accountable by redeliverer/EMP
- `SRRC` — Reverse charge for B2B imported services
- `SRLVG` — Own supply of low-value goods
- `ZR` — Export / international services (zero-rated)
- `ES33` — Regulation 33 exempt supplies
- `ESN33` — Non-Regulation 33 exempt supplies
- `DS` — Deemed supplies (reported under GST legislation)
- `OS` — Out of scope
- `NG` — Not GST-registered company
- `NA` — Taxable but no GST charged

### ResPartner (`res.partner`, classic extension)
- `invoice_edi_format` selection adds `('pint_sg', "Singapore (Peppol PINT SG)")`
- `_get_edi_builder()` — maps `pint_sg` to `account.edi.xml.pint_sg`
- `_get_ubl_cii_formats_info()` — registers `pint_sg` with countries `['SG']`, `on_peppol: True`, `sequence: 90` (higher priority than UBL_SG from `account_edi_ubl_cii`)

## Data Files
None — pure Python models, no XML/CSV data files.

## Tax Structure
Singapore GST at 9% uses SG-specific UBL tax category codes. All tax categories MUST use these SG codes in PINT SG documents. The most common is `SR` (Standard-Rated 9%). Codes requiring seller address validation: `SR`, `SRCA-S`, `SRCA-C`, `ZR`, `SRRC`, `SROVR-RS`, `SROVR-LVG`, `SRLVG`, `NA`.

## EDI/Fiscal Reporting
- Peppol PINT SG specification: https://docs.peppol.eu/poac/sg/2024-Q2/pint-sg/
- On Peppol network (`on_peppol: True`)
- `sequence: 90` gives `pint_sg` priority over the generic `UBL_SG` format
- UUID generation via DB UUID + move ID (no new field needed)
- Dual-currency support with mandatory SGD TaxTotal when invoice in foreign currency

## Installation
Install alongside `l10n_sg`. Does not auto-install. The `pint_sg` format is available for selection on partners and moves, and has higher priority than the base `UBL_SG` format.

## Historical Notes
- New module in Odoo 18.
- Singapore's IRAS mandated Peppol e-invoicing starting 2024 (gradual rollout by company size).
- SG PINT requires explicit address on seller for multiple GST categories.
- The 14 distinct SG tax category codes reflect Singapore's complex GST rules (zero-rating, exemption categories, deemed supplies, overseas vendor regimes).
