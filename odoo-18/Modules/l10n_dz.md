---
Module: l10n_dz
Version: 18.0
Type: l10n/algeria
Tags: #odoo18 #l10n #accounting #algeria
---

# l10n_dz

## Overview
Algeria accounting localization — chart of accounts and tax report for Algerian companies. Algerian accounting follows the Plan Comptable National (PCN).

## Country
People's Democratic Republic of Algeria — country code `dz`

## Dependencies
- base_vat
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'dz'`. Author: Osis (Algerian ERP partner).

## Data Files
- `data/tax_report.xml` — tax report structure for Algerian VAT reporting
- `demo/demo_company.xml` — Algeria demo company

## Chart of Accounts
Algeria uses the Plan Comptable National (PCN) — a French-influenced 7-class national chart of accounts. Prefixed with `dz`.

## Tax Structure
Algeria has a complex tax system: VAT (TVA) at 9%, 14%, and 19% rates depending on sector; corporate income tax (IBS); professional tax; property tax. Tax report defined in `data/tax_report.xml`.

## Fiscal Positions
Defined in template data.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
- Algeria's PCN is mandatory for companies operating under the Algerian commercial code
