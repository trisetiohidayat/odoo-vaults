# l10n_cl - Chile Accounting

## Overview
- **Name:** Chile - Accounting
- **Country:** Chile (CL)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 3.1
- **Author:** Blanco Martin & Asociados
- **License:** LGPL-3
- **Dependencies:** `contacts`, `base_vat`, `l10n_latam_base`, `l10n_latam_invoice_document`, `uom`, `account`
- **Auto-installs:** `account`

## Description
Chilean accounting chart and tax localization based on Chilean accounting standards. Supports SII (Servicio de Impuestos Internos) electronic documents (DTE — Documento Tributario Electronico).

## Models

### res.partner (Inherit)
Extends `res.partner`:
- **l10n_cl_sii_taxpayer_type:** Selection — `1` VAT Affected (1st Category), `2` Fees Receipt Issuer (2nd), `3` End Consumer, `4` Foreigner
- **l10n_cl_activity_description:** Economic activity description field
- **_commercial_fields():** Includes taxpayer type
- **_run_check_identification():** Formats and validates Chilean RUN (Rol Unico Nacional) using `format_vat_cl`
- **_format_dotted_vat_cl():** Formats RUT as `7.608.642-8` notation

### account.move (Inherit)
Extends `account.move` with SII DTE support:
- **partner_id_vat:** Related partner VAT
- **l10n_latam_internal_type:** Related document internal type
- **_check_l10n_latam_document_number_is_numeric():** DTE folio must contain only digits
- **_get_l10n_latam_documents_domain():** Filters documents by taxpayer type and country — restricts certain document codes per partner type (e.g., type 1 cannot use boletas; foreigner uses code 46)
- **_check_document_types_post():** Validates taxpayer type + VAT + document code compatibility on posting
- **_l10n_cl_onchange_journal():** Clears document type on journal change
- **_get_l10n_latam_documents_domain():** Full domain logic for sale/purchase journals based on SII rules
- **_get_starting_sequence():** Format: `DOC_PREFIX 6-digit-sequence`
- **_get_last_sequence_domain():** Sequence tracking per document type + company + move type (not just journal)
- **_get_name_invoice_report():** Returns `l10n_cl.report_invoice_document` for Chilean sale/credit-note or foreign-purchase documents
- **_l10n_cl_include_sii():** True for documentos 39, 41, 110, 111, 112, 34
- **_l10n_cl_get_invoice_totals_for_report():** Adjusts tax totals for boletas/exports (excludes VAT detail)
- **_l10n_cl_get_amounts():** Computes VAT amount, taxable/subtotal, exempt, global discounts, second-currency amounts for DTE
- **_l10n_cl_get_withholdings():** Computes withholding taxes (ILA, retenciones) for electronic documents — codes 15, 17, 18, 19, 24-27, 271
- **_compute_tax_totals():** OVERRIDE — disables company-currency recap in tax totals grid for Chilean reports

## Data Files
- `data/l10n_cl_chart_data.xml` — Chilean chart of accounts
- `data/account_tax_report_data.xml` — Chilean tax report
- `data/account_tax_tags_data.xml` — Tax tag data
- `data/l10n_latam.document.type.csv` — Document types (factura electronica, boleta, nota credito, guia, etc.)
- `data/l10n_latam_identification_type_data.xml` — RUT/RUN identification types
- `data/uom_data.xml` — Chilean UoMs
- `data/res.currency.csv` / `data/res_currency_data.xml` — CLP and foreign currencies
- `data/res.bank.csv` / `data/res.country.csv` — Banks and countries
- Views: move, tax, bank, country, company, invoice report

## SII Document Types
- Codes 33/34 — Factura electronica / Factura no afecta (exenta)
- Code 39 — Boleta electronica
- Code 41 — Boleta no afectada
- Code 46 — Factura de compra (foreign)
- Code 56 — Nota de credito
- Code 61 — Nota de debito
- Codes 110/111/112 — Export documents
- Code 71 — Boleta de honorarios electronica
