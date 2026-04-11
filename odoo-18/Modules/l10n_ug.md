---
Module: l10n_ug
Version: 1.0.0
Type: l10n/uganda
Tags: #odoo18 #l10n #accounting #east_africa
---

# l10n_ug

## Overview
Uganda accounting localization — chart of accounts, taxes, tax report, and fiscal positions for Ugandan companies.

## Country
Republic of Uganda — country code `ug`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'ug'`.

## Data Files
- `data/account_tax_report_data.xml` — Uganda tax report
- `demo/demo_company.xml` — Uganda demo company

## Chart of Accounts
Ugandan chart of accounts with `ug` prefix. Uganda follows Ugandan Accounting Standards (UAS), largely IFRS-aligned. Not a SYSCOHADA country.

## Tax Structure
- VAT at 18% standard rate (Uganda Revenue Authority — URA)
- Withholding tax on various payments (dividends 15%, interest 10%/15%/20% depending on recipient, royalties 15%, management fees 6%, rent 12%)
- Corporate income tax: 30% for companies
- PAYE (Pay As You Earn) for employees

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0.0 in Odoo 18
