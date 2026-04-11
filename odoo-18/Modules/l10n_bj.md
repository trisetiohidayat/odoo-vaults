---
Module: l10n_bj
Version: 18.0
Type: l10n/benin
Tags: #odoo18 #l10n #accounting #west_africa #syscohada
---

# l10n_bj

## Overview
Benin accounting localization — SYSCOHADA chart of accounts and tax report for Beninese companies.

## Country
Republic of Benin — country code `bj`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'bj'`. Provides `_get_bj_syscebnl_template_data()` using SYSCOHADA.

## Data Files
- `data/account_tax_report_data.xml` — Benin tax report
- `demo/demo_company.xml` — Benin demo company

## Chart of Accounts
SYSCOHADA (OHADA uniform accounting system). See [[Modules/l10n_bf]] for details.

## Tax Structure
TVA at 18% standard rate, IS/IR for companies/individuals. Benin's tax framework follows OHADA directives.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
