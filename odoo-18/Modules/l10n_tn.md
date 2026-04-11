---
Module: l10n_tn
Version: 18.0
Type: l10n/tunisia
Tags: #odoo18 #l10n #accounting #tunisia
---

# l10n_tn

## Overview
Tunisia accounting localization — chart of accounts and tax report for Tunisian companies. Follows the Tunisian Accounting System (Plan Comptable Tunisien — PCT).

## Country
Republic of Tunisia — country code `tn`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'tn'`.

## Data Files
- `data/tax_report.xml` — Tunisian tax report structure
- `demo/demo_company.xml` — Tunisia demo company

## Chart of Accounts
Tunisia uses the Plan Comptable Tunisien (PCT) — an 8-class national accounting system (classes 0-8), required for companies under the Tunisian Commercial Code. Prefixed with `tn`.

## Tax Structure
TVA (Taxe sur la Valeur Ajoutée) at 6%, 12%, 18%, 19% rates depending on the product/service category. Corporate tax (IS) and professional tax. Tax report defined in `data/tax_report.xml`.

## Fiscal Positions
Defined in template data.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
- Tunisia's PCT is mandatory for companies above certain thresholds under the Tunisian accounting regulations
