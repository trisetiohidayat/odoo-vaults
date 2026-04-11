---
Module: l10n_rw
Version: 18.0
Type: l10n/rwanda
Tags: #odoo18 #l10n #accounting #east_africa
---

# l10n_rw

## Overview
Rwanda accounting localization — chart of accounts and tax report for Rwandan companies.

## Country
Republic of Rwanda — country code `rw`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'rw'`.

## Data Files
- `data/l10n_rw_chart_data.xml` — Rwandan chart of accounts data
- `data/account_tax_report_data.xml` — Rwanda tax report
- `demo/demo_company.xml` — Rwanda demo company

## Chart of Accounts
Rwandan chart of accounts with `rw` prefix. Rwanda follows Rwandan Accounting Standards (RAS), largely aligned with IFRS. Not a SYSCOHADA country.

## Tax Structure
- VAT at 18% standard rate
- Withholding tax at 15% on specified payments
- Corporate income tax: 30%
- Rwanda uses RRA (Rwanda Revenue Authority) for tax administration

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
