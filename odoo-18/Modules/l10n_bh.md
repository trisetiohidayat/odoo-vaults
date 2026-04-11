---
Module: l10n_bh
Version: 18.0
Type: l10n/bahrain
Tags: #odoo18 #l10n #accounting #bahrain #gcc
---

# l10n_bh

## Overview
Bahrain accounting localization — chart of accounts, VAT taxes, tax reports (full and simplified), fiscal positions, and state/region data for Bahrain.

## Country
Kingdom of Bahrain — country code `bh`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'bh'`. Provides `_get_bh_template_data()` and `_get_bh_res_company()`.

## Data Files
- `data/tax_report_full.xml` — full VAT tax report for Bahrain
- `data/tax_report_simplified.xml` — simplified VAT tax report
- `data/res.country.state.csv` — Bahrain governorate/state data
- `data/res_country_data.xml` — country-level data
- `demo/demo_company.xml` — Bahrain demo company

## Chart of Accounts
Bahrain chart of accounts (prefix `bh`). No specific template file shown, but uses standard `account.chart.template` pattern.

## Tax Structure
VAT at 10% standard rate (effective December 2019). Full and simplified VAT return reports.

## Fiscal Positions
Defined in data files.

## Installation
Standard installation — no auto_install specified.

## Historical Notes
- Version 1.0 in Odoo 18
- Bahrain's National Bureau for Revenue (NBR) VAT framework
