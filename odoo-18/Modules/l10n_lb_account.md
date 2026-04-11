---
Module: l10n_lb_account
Version: 18.0
Type: l10n/lebanon
Tags: #odoo18 #l10n #accounting #lebanon
---

# l10n_lb_account

## Overview
Lebanon accounting localization — chart of accounts, taxes, and fiscal positions for Lebanese companies.

## Country
Lebanese Republic — country code `lb`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'lb'`.

## Data Files
- `data/res.country.state.csv` — Lebanese governorate/district data
- `demo/demo_company.xml` — Lebanon demo company

## Chart of Accounts
Lebanon chart of accounts with `lb` prefix.

## Tax Structure
Lebanon uses a mix of VAT (at 11%), withholding taxes, and municipal taxes. Tax structure defined via the chart template.

## Fiscal Positions
Defined in the module's template data.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
- Lebanon's accounting follows the Lebanese Accounting Chart aligned with French PCMB (Plan Comptable Minimum Bancaire) tradition
