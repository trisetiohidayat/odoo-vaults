---
Module: l10n_gw
Version: 18.0
Type: l10n/guinea_bissau
Tags: #odoo18 #l10n #accounting #west_africa #syscohada
---

# l10n_gw

## Overview
Guinea-Bissau accounting localization — SYSCOHADA chart of accounts and tax report.

## Country
Republic of Guinea-Bissau — country code `gw`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'gw'`. Provides `_get_gw_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — Guinea-Bissau tax report
- `demo/demo_company.xml` — Guinea-Bissau demo company

## Chart of Accounts
SYSCOHADA. See [[Modules/l10n_bf]].

## Tax Structure
TVA at 15% standard rate. IS. Guinea-Bissau is a WAEMU (West African Economic and Monetary Union) member, which sets common tax frameworks.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
