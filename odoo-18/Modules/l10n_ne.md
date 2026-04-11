---
Module: l10n_ne
Version: 18.0
Type: l10n/niger
Tags: #odoo18 #l10n #accounting #west_africa #syscohada
---

# l10n_ne

## Overview
Niger accounting localization — SYSCOHADA chart of accounts and tax report for Nigerien companies.

## Country
Republic of Niger — country code `ne`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'ne'`. Provides `_get_ne_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — Niger tax report
- `demo/demo_company.xml` — Niger demo company

## Chart of Accounts
SYSCOHADA. See [[Modules/l10n_bf]].

## Tax Structure
TVA at 19% standard rate (WAEMU zone). Niger uses OHADA/SYSCOHADA accounting framework.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
