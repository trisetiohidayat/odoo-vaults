---
Module: l10n_tz_account
Version: 18.0
Type: l10n/tanzania
Tags: #odoo18 #l10n #accounting #east_africa
---

# l10n_tz_account

## Overview
Tanzania accounting localization — chart of accounts and tax report for Tanzanian companies.

## Country
United Republic of Tanzania — country code `tz`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'tz'`.

## Data Files
- `data/l10n_tz_chart_data.xml` — Tanzanian chart of accounts data
- `data/account_tax_report_data.xml` — Tanzania tax report
- `demo/demo_company.xml` — Tanzania demo company

## Chart of Accounts
Tanzanian chart of accounts with `tz` prefix. Tanzania follows Tanzanian Accounting Standards (TAS) aligned with IFRS. Not a SYSCOHADA country.

## Tax Structure
- VAT at 18% standard rate
- Withholding tax on various payments (dividends 10%, interest 15%, royalties 15%, management fees 10%)
- Corporate income tax: 30%
- Tanzania Revenue Authority (TRA) administers taxes

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
Standard installation.

## Historical Notes
- Version 1.0 in Odoo 18
