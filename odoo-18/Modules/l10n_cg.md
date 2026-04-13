---
Module: l10n_cg
Version: 18.0
Type: l10n/congo
Tags: #odoo18 #l10n #accounting #central_africa #syscohada
---

# l10n_cg

## Overview
Republic of the Congo (Congo-Brazzaville) accounting localization — SYSCOHADA chart of accounts and tax report.

## Country
Republic of the Congo — country code `cg`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'cg'`. Provides `_get_cg_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — Congo tax report
- `demo/demo_company.xml` — Congo demo company

## Chart of Accounts
SYSCOHADA. See [Modules/l10n_bf](l10n_bf.md).

## Tax Structure
TVA at 18% standard rate. IS/IR. Congo uses the OHADA/SYSCOHADA framework.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
