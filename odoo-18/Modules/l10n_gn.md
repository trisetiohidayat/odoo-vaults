---
Module: l10n_gn
Version: 18.0
Type: l10n/guinea
Tags: #odoo18 #l10n #accounting #west_africa #syscohada
---

# l10n_gn

## Overview
Guinea accounting localization — SYSCOHADA chart of accounts and tax report for Guinean companies.

## Country
Republic of Guinea — country code `gn`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'gn'`. Provides `_get_gn_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — Guinea tax report
- `demo/demo_company.xml` — Guinea demo company

## Chart of Accounts
SYSCOHADA. See [Modules/l10n_bf](modules/l10n_bf.md).

## Tax Structure
TVA at 18% standard rate. IS/IR. Guinea uses OHADA framework but with national adaptations.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
