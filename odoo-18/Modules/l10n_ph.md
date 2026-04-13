---
Module: l10n_ph
Version: 18.0
Type: l10n/philippines
Tags: #odoo18 #l10n #accounting #withholding #edi
---

# l10n_ph

## Overview
Philippines accounting localization providing the Philippine chart of accounts, VAT structure, withholding tax support, BIR compliance reporting, and BIR Form 2307 (Certificate of Final Tax Withheld) wizard for vendor bill payments. The Philippines uses a complex tax system with VAT, withholding taxes, and annual BIR filings.

## Country
Philippines

## Dependencies
- [Core/BaseModel](Core/BaseModel.md) (account)
- `account` — core accounting module
- `base_vat` — TIN/VAT number validation

## Key Models

### AccountChartTemplate (`account.chart.template`, classic extension)
- `_get_ph_template_data()` — sets 6-digit account codes: receivable `l10n_ph_110000`, payable `l10n_ph_200000`, income `l10n_ph_430400`, expense `l10n_ph_620000`, stock valuation `l10n_ph_110300`, stock input `l10n_ph_110302`, stock output `l10n_ph_110303`
- `_get_ph_res_company()` — enables `anglo_saxon_accounting`, fiscal country `base.ph`, bank prefix `1000`, cash prefix `1001`, transfer prefix `1002`, sale tax `l10n_ph_tax_sale_vat_12`, purchase tax `l10n_ph_tax_purchase_vat_12`

### AccountMove (`account.move`, classic extension)
- `action_open_l10n_ph_2307_wizard()` — opens the BIR 2307 wizard for vendor bills; raises `UserError` if not an `in_invoice`

### AccountPayment (`account.payment`, classic extension)
- `action_open_l10n_ph_2307_wizard()` — opens the BIR 2307 wizard from an outbound payment (supplier payment)

### AccountTax (`account.tax`, classic extension)
- `l10n_ph_atc` — Char field for Philippines **Alphanumeric Tax Code (ATC)**; maps tax to specific BIR revenue regulation category

### ResPartner (`res.partner`, classic extension)
- `branch_code` — extracted from VAT/TIN (3-digit BIR branch code, default `000` for head office)
- `first_name`, `middle_name`, `last_name` — for BIR reporting with proper name formatting
- `_compute_branch_code()` — parses VAT string using `__check_vat_ph_re` regex to extract branch code

### Generate2307Wizard (`l10n_ph_2307.wizard`, transient)
- `moves_to_export` — Many2many of `account.move` to include in export
- `action_generate()` — generates XLS file using `utils._export_bir_2307()`; outputs Form 2307 data for BIR Excel uploader

## Data Files
- `data/account_account_tag_data.xml` — account tags for BIR tax mapping
- `data/account_tax_report_data.xml` — tax report data
- `wizard/generate_2307_wizard_views.xml` — form view and action for 2307 wizard
- `views/account_move_views.xml` — invoice form with BIR action button
- `views/account_payment_views.xml` — payment form with 2307 action
- `views/account_tax_views.xml` — tax form with ATC field
- `views/res_partner_views.xml` — partner form with branch code, name fields
- `security/ir.model.access.csv` — ACL for wizard model
- `tests/test_bir_2307_generation.py` — test suite
- `migrations/1.1/end-migrate_update_taxes.py` — tax update migration
- `demo/demo_company.xml` — demo company data

## Chart of Accounts
6-digit account codes:
- `110xxx` — Assets (receivable `110000`, stock valuation `110300`, POS receivable `110003`)
- `200xxx` — Liabilities (payable `200000`)
- `430xxx` — Revenue (`430400`)
- `620xxx` — Expenses (`620000`)
- `710xxx` — Other income/expense (currency exchange `710100`, cash diff income `710102`, cash diff expense `710103`)

## Tax Structure
Philippines uses 12% VAT (standard rate):
- `l10n_ph_tax_sale_vat_12` — 12% sale VAT (default sale tax)
- `l10n_ph_tax_purchase_vat_12` — 12% purchase VAT (default purchase tax)
- ATC codes on taxes map to BIR revenue regulations
- Withholding taxes supported via `l10n_account_withholding_tax`

## Fiscal Positions
None explicitly defined in the template module.

## EDI/Fiscal Reporting
- **BIR Form 2307** — Certificate of Final Tax Withheld at Source (for vendor payments). The wizard exports XLS for BIR Excel uploader at https://bir-excel-uploader.com/excel-file-to-bir-dat-format/#bir-form-2307-settings
- Action `action_open_l10n_ph_2307_wizard()` on both `account.move` (vendor bills) and `account.payment` (outbound payments)
- Tax report via `account_tax_report_data.xml`

## Installation
Install via Apps or during company setup by selecting Philippines as country. Version 1.1 migration updates taxes.

## Historical Notes
- Version 1.1: Tax updates in Odoo 18.
- Philippines TIN (Tax Identification Number) is 12 digits: 9-digit RRN + 3-digit branch code.
- BIR 2307 is required for payments to local suppliers subject to expanded withholding tax.
- The Philippines has multiple VAT rates: 12% standard, 0% zero-rated, exempt.
- `l10n_ph_atc` field on taxes links to BIR's Alphanumeric Tax Code table.
