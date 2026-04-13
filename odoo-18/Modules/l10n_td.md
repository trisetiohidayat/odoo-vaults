---
Module: l10n_td
Version: 18.0
Type: l10n/chad
Tags: #odoo18 #l10n #accounting #central_africa #syscohada
---

# l10n_td

## Overview
Chad accounting localization — SYSCOHADA chart of accounts and tax report for Chadian companies.

## Country
Republic of Chad — country code `td`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'td'`. Provides `_get_td_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — Chad tax report
- `demo/demo_company.xml` — Chad demo company

## Chart of Accounts
SYSCOHADA. See [Modules/l10n_bf](Modules/l10n_bf.md).

## Tax Structure
TVA at 18% standard rate (CEMAC zone). IS. Chad follows OHADA/CEMAC tax framework.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
