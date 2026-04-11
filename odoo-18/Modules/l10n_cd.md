---
Module: l10n_cd
Version: 18.0
Type: l10n/dr_congo
Tags: #odoo18 #l10n #accounting #central_africa #syscohada
---

# l10n_cd

## Overview
Democratic Republic of the Congo accounting localization — SYSCOHADA chart of accounts and tax report for DRC companies.

## Country
Democratic Republic of the Congo — country code `cd`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'cd'`. Provides `_get_cd_syscebnl_template_data()` using SYSCOHADA.

## Data Files
- `data/account_tax_report_data.xml` — DRC tax report
- `demo/demo_company.xml` — DRC demo company

## Chart of Accounts
SYSCOHADA. The DRC uses the SYSCOHADA plan, mandatory for companies registered in the DRC's commercial registry.

## Tax Structure
TVA at 16% standard rate. IRI (Impôt sur les Revenus des Personnes Physiques), IBS (Impôt sur les Bénéfices des Sociétés). DRC uses the OHADA framework but with its own tax rates.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
