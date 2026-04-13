---
Module: l10n_ae
Version: 18.0
Type: l10n/uae
Tags: #odoo18 #l10n #accounting #uae #gcc
---

# l10n_ae

## Overview
United Arab Emirates accounting localization — provides the UAE chart of accounts, state-level VAT tax rates per emirate, tax report broken down by emirate, fiscal positions, bank data, and Arabic/English invoice report layout.

## Country
United Arab Emirates (UAE) — country code `ae`

## Dependencies
- base
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'ae'`.

`_get_ae_template_data()` sets:
- `property_account_receivable_id`: `uae_account_102011`
- `property_account_payable_id`: `uae_account_201002`
- `property_account_expense_categ_id`: `uae_account_400001`
- `property_account_income_categ_id`: `uae_account_500001`
- `code_digits`: `6`

`_get_ae_res_company()` sets default company configuration including fiscal country, bank/cash/transfer code prefixes, POS receivable account, currency exchange accounts, early pay discount accounts, and default sale/purchase tax.

The default sale tax is state-dependent: AZ (Abu Dhabi, default), AJ (Ajman), DU (Dubai), FU (Fujairah), RK (Ras Al Khaima), SH (Sharjah), UQ (Umm Al Quwain).

`_get_ae_account_journal()` adds two extra journals when UAE chart is active: `TA` (Tax Adjustments) and `IFRS`.

### `AccountMoveLine` (`account.move.line`)
Inherits `account.move.line`. Adds `l10n_ae_vat_amount` — `Monetary` field computed via `_compute_vat_amount()` as `price_total - price_subtotal` for display in invoice line views.

## Data Files
- `data/l10n_ae_data.xml` — sets VAT label on `base.ae` country record; sets AED currency symbol; creates `gcc_countries_group` res.country.group for Bahrain, Saudi Arabia, UAE (for VAT implementing states)
- `data/account_tax_report_data.xml` — tax report (`account.report`) with per-emirate breakdown of standard-rated supplies, zero-rated, exempt, out-of-scope, reverse charge, and import bases and taxes
- `data/res.bank.csv` — UAE bank data
- `views/report_invoice_templates.xml` — invoice template customizations
- `views/account_move.xml` — account move view extensions (adds `l10n_ae_vat_amount` to line view)
- `demo/demo_company.xml` — UAE demo company

## Chart of Accounts
6-digit chart with `uae_account_` prefix. Receivable accounts in 102xxx range, payable in 201xxx, income in 500xxx, expense in 400xxx. Designed for UAE Federal Law No. 2 of 2015 (companies law) and UAE VAT requirements.

## Tax Structure
VAT at 5% standard rate (introduced January 2018). Per-emirate tax authority codes differ. State-dependent sale tax default based on company state. Zero-rated and exempt supplies available. Reverse charge mechanism for B2B imports.

## Fiscal Positions
In `data/account_tax_report_data.xml` — fiscal positions for cross-border transactions.

## EDI/Fiscal Reporting
No EDI module — relies on [Modules/l10n_gcc_invoice](modules/l10n_gcc_invoice.md) for bilingual reporting.

## Installation
`auto_install: ['account']` — automatically installed with account module when UAE is selected as country.

## Historical Notes
- Version 1.0 in Odoo 18
- UAE VAT at 5% — unlike most other GCC countries (15%)
- State-level tax accounts allow emirate-level VAT reporting for FATCO (Federal Authority for CT and ZATCA) requirements
