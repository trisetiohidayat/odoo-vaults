---
Module: l10n_ga
Version: 18.0
Type: l10n/gabon
Tags: #odoo18 #l10n #accounting #central_africa #syscohada
---

# l10n_ga

## Overview
Gabon accounting localization — SYSCOHADA chart of accounts and tax report for Gabonese companies.

## Country
Gabonese Republic — country code `ga`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'ga'`. Provides `_get_ga_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — Gabon tax report
- `demo/demo_company.xml` — Gabon demo company

## Chart of Accounts
SYSCOHADA. See [Modules/l10n_bf](l10n_bf.md).

## Tax Structure
TVA at 18% standard rate (CEMAC zone). IS. Gabon follows OHADA/CEMAC tax directives.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
