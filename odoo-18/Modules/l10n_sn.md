---
Module: l10n_sn
Version: 18.0
Type: l10n/senegal
Tags: #odoo18 #l10n #accounting #west_africa #syscohada
---

# l10n_sn

## Overview
Senegal accounting localization — SYSCOHADA chart of accounts and tax report for Senegalese companies. Senegal is one of the founding members of OHADA and a WAEMU hub.

## Country
Republic of Senegal — country code `sn`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'sn'`. Provides `_get_sn_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — Senegal tax report
- `demo/demo_company.xml` — Senegal demo company

## Chart of Accounts
SYSCOHADA. See [Modules/l10n_bf](odoo-18/Modules/l10n_bf.md).

## Tax Structure
TVA at 18% standard rate (WAEMU harmonized). IS (Impôt sur les Sociétés) at 30% standard rate. Senegal uses OHADA/SYSCOHADA accounting and WAEMU common tax directives.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
