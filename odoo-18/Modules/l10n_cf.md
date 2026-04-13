---
Module: l10n_cf
Version: 18.0
Type: l10n/central_african_republic
Tags: #odoo18 #l10n #accounting #central_africa #syscohada
---

# l10n_cf

## Overview
Central African Republic accounting localization — SYSCOHADA chart of accounts and tax report.

## Country
Central African Republic — country code `cf`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'cf'`. Provides `_get_cf_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — CAR tax report
- `demo/demo_company.xml` — CAR demo company

## Chart of Accounts
SYSCOHADA. See [Modules/l10n_bf](odoo-18/Modules/l10n_bf.md).

## Tax Structure
TVA at rates determined by CEMAC (Communauté Économique et Monétaire de l'Afrique Centrale) framework.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
