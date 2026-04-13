---
Module: l10n_jp_ubl_pint
Version: 18.0
Type: l10n/japan/edi
Tags: #odoo18 #l10n #edi #peppol
---

# l10n_jp_ubl_pint

## Overview
Peppol PINT JP e-invoicing module for Japan. Provides the Japanese implementation of the Peppol International (PINT) Billing standard. Built on the BIS Billing 3 base format (`account.edi.xml.ubl_bis3`) and extends it with Japan-specific rules.

## Country
Japan

## Dependencies
- [Core/BaseModel](Core/BaseModel.md) (account_edi_ubl_cii)
- `account_edi_ubl_cii` — UBL/CII EDI framework

## Key Models

### AccountEdiXmlUBLPINTJP (`account.edi.xml.ubl_bis3`, abstract)
- `_name = 'account.edi.xml.pint_jp'`
- `_export_invoice_filename()` — `filename_pint_jp.xml`
- `_get_partner_address_vals()` — removes `country_subentity_code` (Japan does not use Japanese prefectures in EDI)
- `_get_partner_party_legal_entity_vals_list()` — removes `company_id` (optional in JP PINT; scheme_id would be taken from ISO/IEC 6523 list if present)
- `_get_invoice_period_vals_list()` — adds invoice date as a required invoice period `[aligned-ibrp-052]`
- `_get_invoice_tax_totals_vals_list()` — handles JPY no-decimal rounding; adds second TaxTotal section in accounting currency when invoice currency differs from company currency
- `_export_invoice_vals()` — sets `customization_id: pint_jp`, `profile_id: urn:peppol:bis:billing`; for invoices after 2023-10-01, uses new Registration Number for Qualified Invoice (removes `JP` prefix from VAT/tax ID)

### ResPartner (`res.partner`, classic extension)
- `invoice_edi_format` selection adds `('pint_jp', "Japan (Peppol PINT JP)")`
- `_get_edi_builder()` — maps `pint_jp` format to `account.edi.xml.pint_jp`
- `_get_ubl_cii_formats_info()` — registers `pint_jp` with countries `['JP']` and `on_peppol: True`

## Data Files
None — pure Python model, no XML/CSV data files.

## Tax Structure
PINT JP constrains tax categories: Japan uses the standard UN/ECE tax codes. For invoices dated after 2023-10-01, the new "Registration Number for Qualified Invoice" (適格請求書発行事業者登録番号) must be used — this is a 13-digit TIN without the `JP` country prefix.

## EDI/Fiscal Reporting
- Peppol PINT JP specification: https://docs.peppol.eu/poac/jp/pint-jp
- Works on the Peppol network (`on_peppol: True`)
- Dual-currency support: when invoice currency differs from company currency (JPY), a second TaxTotal section is appended in accounting currency per JP PINT rules
- Decimal handling: JPY has 0 decimal places — `_get_invoice_tax_totals_vals_list` sets `currency_dp` accordingly

## Installation
Install alongside or after `l10n_jp`. The `pint_jp` format becomes available in partner and move EDI format selection.

## Historical Notes
- New in Odoo 18 as a dedicated PINT country module. In Odoo 17, Japan EDI support was more limited.
- The 2023-10-01 date marks the start of Japan's Qualified Invoice System (適格請求書等保存方式), replacing the old input-tax deduction method.
- `l10n_jp_ubl_pint` does not auto-install; it is a user-selectable EDI format.
