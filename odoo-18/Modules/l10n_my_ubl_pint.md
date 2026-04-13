---
Module: l10n_my_ubl_pint
Version: 18.0
Type: l10n/malaysia/edi
Tags: #odoo18 #l10n #edi #peppol
---

# l10n_my_ubl_pint

## Overview
Malaysia Peppol PINT e-invoicing module. Provides the Malaysian implementation of the Peppol International (PINT) Billing standard, based on BIS Billing 3. Malaysia's e-Invoice mandate requires electronic invoice submission to LHDN (Lembaga Hasil Dalam Negeri) via Peppol.

## Country
Malaysia

## Dependencies
- [Core/BaseModel](BaseModel.md) (account_edi_ubl_cii)
- `account_edi_ubl_cii` — UBL/CII EDI framework

## Key Models

### AccountEdiXmlUBLPINTMY (`account.edi.xml.ubl_bis3`, abstract)
- `_name = 'account.edi.xml.pint_my'`
- `_export_invoice_filename()` — `filename_pint_my.xml`
- `_export_invoice_vals()` — sets `customization_id: pint_my`, `profile_id: urn:peppol:bis:billing`; when invoice currency differs from company currency, sets `tax_currency_code` to accounting currency
- `_get_invoice_tax_totals_vals_list()` — adds second TaxTotal section in accounting currency when currencies differ
- `_get_partner_party_tax_scheme_vals_list()` — Malaysian invoice tax categories MUST use Malaysian codes; sets `company_id` to SST registration (`sst_registration_number` or `NA`); for supplier role, also appends GST tax scheme with TIN
- `_get_tax_unece_codes()` — OVERRIDE: Malaysia allows only codes T (taxable), E (exempt), O (outside scope of tax); if supplier has no SST registration, returns `O` (Outside scope)
- `_export_invoice_constraints()` — validates that tax category `O` has 0% amount; removes `tax_on_line` and `cen_en16931_tax_line` constraints (Malaysia does not require tax on each line)

### ResCompany (`res.company`, classic extension)
- `sst_registration_number` — related field to `partner_id.sst_registration_number`
- `ttx_registration_number` — related field to `partner_id.ttx_registration_number` (Tourism Tax)

### BaseDocumentLayout (`base.document.layout`, classic extension)
- Adds `sst_registration_number` and `ttx_registration_number` to document layout (display on printed invoices)

### ResPartner (`res.partner`, classic extension)
- `invoice_edi_format` selection adds `('pint_my', "Malaysia (Peppol PINT MY)")`
- `sst_registration_number` — Malaysian Sales and Service Tax registration number
- `ttx_registration_number` — Malaysian Tourism Tax registration number
- `_get_edi_builder()` — maps `pint_my` to `account.edi.xml.pint_my`
- `_get_ubl_cii_formats_info()` — registers `pint_my` with countries `['MY']`, `on_peppol: True`
- `_commercial_fields()` — adds `sst_registration_number` and `ttx_registration_number` to commercial fields

## Data Files
- `views/res_partner_view.xml` — partner form/view extensions for SST/TTx fields
- `views/res_company_view.xml` — company form extensions
- `views/report_invoice.xml` — invoice report layout with SST/TTx fields
- `tests/test_my_ubl_pint.py` — test suite

## Tax Structure
Malaysia e-Invoice uses SST (Sales and Service Tax) codes:
- **T** — Taxable (SST-registered supplier charging SST)
- **E** — Exempt
- **O** — Outside scope of tax (not SST-registered; cannot charge SST/TTx)
- For Peppol, tax category codes are drawn from UN/ECE code list but Malaysia-specific restrictions apply
- If supplier lacks SST registration, all taxes must be category `O` (0%)

## EDI/Fiscal Reporting
- Peppol PINT MY specification: https://docs.peppol.eu/poac/my/pint-my
- On Peppol network (`on_peppol: True`)
- Dual-currency: adds second TaxTotal in MYR accounting currency when invoice in foreign currency
- Malaysia's e-Invoice system (MyInvois) is integrated via Peppol BIS Billing 3

## Installation
Install alongside `l10n_my`. Does not auto-install. User selects `pint_my` as EDI format on partners and moves.

## Historical Notes
- New module in Odoo 18.
- Malaysia's e-Invoice mandate (MyInvois) was progressively rolled out starting 2024.
- The dual-tax-regime (SST + TTx) is reflected in the partner/company fields for both registration numbers.
- Tax category code `O` is critical — only suppliers NOT registered for SST can use it, and they cannot charge any tax.
