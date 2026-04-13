---
Module: l10n_th
Version: 18.0
Type: l10n/thailand
Tags: #odoo18 #l10n #accounting #qr-codes
---

# l10n_th

## Overview
Thailand accounting localization providing the Thai chart of accounts, VAT structure, and PromptPay QR code generation. Authored by Almacom. Thailand uses 7-digit account codes and 7% VAT. Includes withholding tax reports (PND3, PND53) for contractor/service payments and a custom commercial invoice report.

## Country
Thailand

## Dependencies
- [Core/BaseModel](odoo-18/Core/BaseModel.md) (account)
- `account_qr_code_emv` — EMV QR code generation for PromptPay

## Key Models

### AccountChartTemplate (`account.chart.template`, classic extension)
- `_get_th_template_data()` — sets short-code account names: receivable `a_recv`, payable `a_pay`, expense `a_exp_cogs`, income `a_sales`
- `_get_th_res_company()` — fiscal country `base.th`, bank prefix `1110`, cash prefix `1100`, transfer prefix `16`, POS receivable `a_recv_pos`, sale tax `tax_output_vat`, purchase tax `tax_input_vat`

### AccountMove (`account.move`, classic extension)
- `_get_name_invoice_report()` — returns `l10n_th.report_invoice_document` for Thai companies (custom commercial invoice)

### IrActionsReport (`ir.actions.report`, classic extension)
- `_pre_render_qweb_pdf()` — validates that only invoices can be printed via `l10n_th.report_commercial_invoice`; raises `UserError` otherwise

### ResBank (`res.partner.bank`, classic extension)
Extends for **PromptPay QR**:
- `proxy_type` selection adds `ewallet_id`, `merchant_tax_id`, `mobile`
- `_check_th_proxy()` — validates: merchant_tax_id must be 13 digits; mobile must be 10 digits; QR type must be one of the three
- `_compute_display_qr_setting()` — enables QR display always for TH banks
- `_get_merchant_account_info()` — returns GIRO tag 29 with PromptPay GUID `A000000677010111`, proxy type (1=mobile, 2=merchant_tax_id, 3=ewallet_id), and serialized proxy value; mobile numbers are prefixed with country code `66`
- `_get_error_messages_for_qr()` — validates currency is THB only
- `_check_for_qr_code_errors()` — enforces valid proxy type for TH

### ResPartner (`res.partner`, classic extension)
- `l10n_th_branch_name` — computed Char: returns `Branch {company_registry}` for Thai companies, `Headquarter` if no branch code

## Data Files
- `data/account_tax_report_data.xml` — **VAT Report** (PP30 format): Output Tax (1–5) and Input Tax (6–7) + Net VAT (8–12); **PND53** withholding report (withholding on payment to juristic person); **PND3** withholding report (withholding on payment to individual)
- `data/template/account.account-th.csv` — chart of accounts
- `data/template/account.tax-th.csv` — tax definitions including VAT 7%, zero-rated, exempt, and withholding taxes
- `data/template/account.tax.group-th.csv` — tax groups
- `views/report_invoice.xml` — custom commercial invoice report
- `tests/test_l10n_th_emv_qr.py` — QR code test suite
- `migrations/` — migration scripts
- `demo/demo_company.xml` — demo company data

## Chart of Accounts
Short-code (mnemonic) account names:
- `a_recv` / `a_recv_pos` — Receivables
- `a_pay` — Payables
- `a_sales` — Revenue
- `a_exp_cogs` — Cost of Sales/Expenses
- `a_input_vat` / `a_output_vat` — VAT accounts
- `a_income_gain` — Currency exchange gain
- `a_exp_loss` — Currency exchange loss

## Tax Structure
Thailand uses **VAT at 7%** (standard rate):
- `tax_output_vat` — 7% Output VAT (sale)
- `tax_input_vat` — 7% Input VAT (purchase)
- `tax_output_vat_0` — 0% Zero-rated output
- `tax_input_vat_0` — 0% Input VAT
- `tax_output_vat_exempted` — Exempt output
- `tax_input_vat_exempted` — Exempt input

Withholding taxes (negative percentage, purchase side):
- `tax_wht_co_1` — Company WHT 1% (Transportation)
- `tax_wht_co_2` — Company WHT 2% (Advertising)
- ...more WHT categories for PND53/PND3 reporting

## Fiscal Positions
None explicitly defined in this module.

## EDI/Fiscal Reporting
- VAT Report (PP30): Output Tax sections (sales 1–5) + Input Tax (6–7) + Net VAT (8–12)
- **PND53**: Withholding tax report for payments to juristic persons (companies)
- **PND3**: Withholding tax report for payments to individuals (natural persons)
- PromptPay QR codes for domestic payments

## Installation
Install via Apps or during company setup by selecting Thailand as country. Post-init hook preserves tags. Auto-installs with `account`.

## Historical Notes
- Version 2.0: Major update for Odoo 18.
- Thailand VAT was 7% from 2008 to 2023, temporarily reduced to 0% (Oct 2023 – Sep 2024) as an economic stimulus, then reinstated at 7%.
- PromptPay is Thailand's national QR payment standard operated byromptPay Co., Ltd.
- WHT rates in Thailand vary: 1% (transportation), 2% (advertising), 3% (services, commissions), 5% (professional fees), etc.
- Branch name on partner is derived from `company_registry` (BRN — Business Registration Number).
