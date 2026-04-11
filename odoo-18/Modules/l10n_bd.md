---
Module: l10n_bd
Version: 18.0
Type: l10n/bangladesh
Tags: #odoo18 #l10n #accounting #bangladesh
---

# l10n_bd — Bangladesh Accounting

## Overview
Base accounting module for Bangladesh, providing chart of accounts aligned with Bangladesh Financial Reporting Standards (BFRS) and a VAT tax structure. Activates VAT-compliant tax reporting and account codes.

## Country
Bangladesh

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (AbstractModel)
- `_inherit = 'account.chart.template'`
- Defines property accounts: receivable (`l10n_bd_100201`), payable (`l10n_bd_200101`), expense (`l10n_bd_500200`), income (`l10n_bd_400100`)
- Company defaults: fiscal country `base.bd`, bank/cash prefix `10010`, POS receivable `l10n_bd_100202`, suspense `l10n_bd_100102`, currency exchange gain/loss accounts, cash difference accounts, transfer account `l10n_bd_100101`, early pay discount gain/loss, default sale tax `VAT_S_IN_BD_10`, purchase tax `VAT_P_IN_BD_10`
- Creates a `tax_adjustment` journal with code `TA` (type: general, shown on dashboard)

## Data Files
- `data/account.account.tag.csv` — Account classification tags
- `data/res.country.state.csv` — Bangladesh administrative divisions
- `data/account_tax_report_data.xml` — VAT tax report structure
- `views/menu_items.xml`
- `demo/demo_company.xml` — Demo data for Bangladesh company

## Chart of Accounts
Bangladesh chart following BFRS classification with 6-digit account codes. Accounts organized by type (Asset 1xxxx, Liability 2xxxx, Income 4xxxx, Expense 5xxxx).

## Tax Structure
- **VAT** — Standard VAT rate (currently 15% standard, reduced rates for specific goods/services)
- Tax Adjustments journal for VAT returns and corrections

## Fiscal Positions
Standard fiscal position mapping for Bangladesh inter-state/regional transactions.

## Installation
Auto-installs with `account`. Demo company provided for initial setup.

## Historical Notes
Version 1.0 in Odoo 18 — initial Bangladesh localization. Authored by Odoo community. No prior Odoo 17 version tracked in manifest.