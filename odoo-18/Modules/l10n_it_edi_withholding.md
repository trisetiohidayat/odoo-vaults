---
Module: l10n_it_edi_withholding
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #italy #withholding #pension-fund
---

# l10n_it_edi_withholding

## Overview
Extends the Italian e-invoicing module with withholding tax (ritenuta) and pension fund (CASSA Previdenza) handling for FatturaPA XML. Withholding taxes and pension fund contributions are computed like other taxes, but are reported in dedicated XML sections (DatiRitenuta, DatiCassaPrevidenziale) in the FatturaPA. Enasarco and AssoSoftware-specific formats are also supported.

## EDI Format / Standard
FatturaPA XML with extended DatiGeneraliDocumento sections:
- `DatiRitenuta`: tipo_ritenuta, aliquota_ritenuta, importo_ritenuta, causale_pagamento
- `DatiCassaPrevidenziale`: tipo_cassa, aliquota_cassa, imponibile_cassa, importo_contributo_cassa, ritenuta, natura

## Dependencies
- `l10n_it_edi` -- core Italian e-invoicing

## Key Models

### `account.move` (`l10n_it_edi_withholding.account_move`)
Extends: `account.move`

Fields (computed from tax lines):
- `l10n_it_amount_vat_signed` -- VAT amount
- `l10n_it_amount_withholding_signed` -- Withholding amount
- `l10n_it_amount_pension_fund_signed` -- Pension fund amount
- `l10n_it_amount_before_withholding_signed` -- Total before withholding (untaxed + VAT + pension fund)

Methods:
- `_compute_amount_extended()` -- Aggregates tax lines by type (VAT / withholding / pension_fund)
- `_l10n_it_edi_grouping_function_base_lines()` / `_grouping_function_tax_lines()` / `_grouping_function_total()` -- Skips withholding and pension fund taxes from standard VAT grouping
- `_l10n_it_edi_get_values()` -- EXTENDS parent; builds withholding_values and pension_fund_values for XML template
- `_l10n_it_edi_export_taxes_check()` -- Validates withholding and pension fund are configured correctly
- Import: `_l10n_it_edi_get_extra_info()` -- Parses DatiRitenuta and DatiCassaPrevidenziale from incoming XML; `_l10n_it_edi_search_tax_for_import()` -- matches taxes by withholding_type + withholding_reason or pension_fund_type
- `_get_pension_fund_tax_for_line()` -- Applies pension fund to lines matching AssoSoftware tags if present
- `_l10n_it_edi_import_line()` -- Applies withholding and pension fund taxes to imported invoice lines; handles Enasarco (TC07)
- `_l10n_it_edi_import_invoice()` -- Handles global Enasarco line (price=0, single pension fund element)

### `account.tax` / `account.chart.template`
Minimal extensions for withholding and pension fund tax configuration and initial data.

## Data Files
- `data/account_withholding_report_data.xml` -- Withholding summary report
- `data/invoice_it_template.xml` -- FatturaPA template with DatiRitenuta/DatiCassa sections
- `views/l10n_it_view.xml` -- UI for withholding fields
- `security/ir.model.access.csv` -- ACL

## How It Works
1. Invoice posted with withholding and/or pension fund taxes on lines
2. `_compute_amount_extended()` computes breakdown (VAT / withholding / pension fund)
3. `_l10n_it_edi_get_values()` builds separate XML structures for withholding and pension fund sections
4. Withholding: aggregated by tipo_ritenuta + causale_pagamento; Pension fund: by tipo_cassa + AliquotaIVA
5. Export: both sections are rendered in the FatturaPA XML per AssoSoftware or standard format
6. Import: XML sections are parsed and matched to configured taxes by type + percentage; applied to invoice lines
7. Enasarco (TC07): special handling for global pension fund line where price_unit=0

## Installation
Post-init hook `_l10n_it_edi_withholding_post_init` configures Italian accounting data. Install after `l10n_it_edi`.

## Historical Notes
The Italian withholding system is complex because of the interaction between multiple tax types: standard VAT, withholding taxes (RITENUTA, which reduce the taxable base), pension fund contributions (CASSA, which are a separate percentage applied after VAT), and Enasarco (a specific TC07 pension fund for the construction industry). The ordering of taxes in the tax configuration matters because pension funds that follow withholding taxes use `sequence > withholding.sequence` to determine applicability. The AssoSoftware XML specification adds `AltriDatiGestionali/AswCassPre` tags to explicitly mark lines with pension funds -- Odoo 18 supports both the standard and AssoSoftware formats.
