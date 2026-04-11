---
Module: l10n_tg
Version: 18.0
Type: l10n/togo
Tags: #odoo18 #l10n #accounting #west_africa #syscohada
---

# l10n_tg

## Overview
Togo accounting localization — SYSCOHADA chart of accounts and tax report for Togolese companies.

## Country
Togolese Republic — country code `tg`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'tg'`. Provides `_get_tg_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — Togo tax report
- `demo/demo_company.xml` — Togo demo company

## Chart of Accounts
SYSCOHADA. See [[Modules/l10n_bf]].

## Tax Structure
TVA at 18% standard rate (WAEMU harmonized). IS at 27%. Togo uses OHADA/SYSCOHADA accounting framework.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
