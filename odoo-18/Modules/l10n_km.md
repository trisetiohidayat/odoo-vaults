---
Module: l10n_km
Version: 18.0
Type: l10n/comoros
Tags: #odoo18 #l10n #accounting #east_africa #syscohada
---

# l10n_km

## Overview
Comoros accounting localization — SYSCOHADA chart of accounts and tax report for Comorian companies.

## Country
Union of the Comoros — country code `km`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'km'`. Provides `_get_km_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — Comoros tax report
- `demo/demo_company.xml` — Comoros demo company

## Chart of Accounts
SYSCOHADA. See [Modules/l10n_bf](l10n_bf.md).

## Tax Structure
TVA at 10% standard rate. IS. Comoros uses OHADA framework.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
