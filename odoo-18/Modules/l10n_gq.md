---
Module: l10n_gq
Version: 18.0
Type: l10n/equatorial_guinea
Tags: #odoo18 #l10n #accounting #central_africa #syscohada
---

# l10n_gq

## Overview
Equatorial Guinea accounting localization — SYSCOHADA chart of accounts and tax report.

## Country
Republic of Equatorial Guinea — country code `gq`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'gq'`. Provides `_get_gq_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — Equatorial Guinea tax report
- `demo/demo_company.xml` — Equatorial Guinea demo company

## Chart of Accounts
SYSCOHADA. See [Modules/l10n_bf](Modules/l10n_bf.md).

## Tax Structure
TVA at 15% standard rate. IS. Equatorial Guinea uses the OHADA/CEMAC framework.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
