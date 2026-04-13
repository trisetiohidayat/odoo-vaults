---
Module: l10n_ml
Version: 18.0
Type: l10n/mali
Tags: #odoo18 #l10n #accounting #west_africa #syscohada
---

# l10n_ml

## Overview
Mali accounting localization — SYSCOHADA chart of accounts and tax report for Malian companies.

## Country
Republic of Mali — country code `ml`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'ml'`. Provides `_get_ml_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — Mali tax report
- `demo/demo_company.xml` — Mali demo company

## Chart of Accounts
SYSCOHADA. See [Modules/l10n_bf](modules/l10n_bf.md).

## Tax Structure
TVA at 18% standard rate (WAEMU harmonized rate). Mali uses OHADA/SYSCOHADA accounting and WAEMU common tax framework.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
