---
Module: l10n_cm
Version: 18.0
Type: l10n/cameroon
Tags: #odoo18 #l10n #accounting #central_africa #syscohada
---

# l10n_cm

## Overview
Cameroon accounting localization — SYSCOHADA chart of accounts and tax report for Cameroonian companies.

## Country
Republic of Cameroon — country code `cm`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'cm'`. Provides `_get_cm_syscebnl_template_data()`.

## Data Files
- `data/account_tax_report_data.xml` — Cameroon tax report
- `demo/demo_company.xml` — Cameroon demo company

## Chart of Accounts
SYSCOHADA. Cameroon uses the SYSCOHADA plan, the national accounting standard required for companies in the CEMAC zone.

## Tax Structure
TVA at 19.25% standard rate (CEMAC framework). IS (Impôt sur les Bénéfices des Sociétés Industrielles, Commerciales et Professionnelles). Cameroon is part of the CEMAC (Communauté Économique et Monétaire de l'Afrique Centrale) zone which sets common external tariffs and tax guidelines.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
