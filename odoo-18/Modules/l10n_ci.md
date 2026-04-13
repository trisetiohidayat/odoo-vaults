---
Module: l10n_ci
Version: 18.0
Type: l10n/ivory_coast
Tags: #odoo18 #l10n #accounting #west_africa #syscohada
---

# l10n_ci

## Overview
Ivory Coast (Côte d'Ivoire) accounting localization — SYSCOHADA chart of accounts and tax report for Ivorian companies.

## Country
Republic of Côte d'Ivoire — country code `ci`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'ci'`. Provides `_get_ci_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — Ivory Coast tax report
- `demo/demo_company.xml` — Ivory Coast demo company

## Chart of Accounts
SYSCOHADA. See [Modules/l10n_bf](l10n_bf.md).

## Tax Structure
TVA at 18% standard rate. IS (Impôt sur les Bénéfices). Ivory Coast is one of the largest economies in the WAEMU zone and a hub for OHADA compliance.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
