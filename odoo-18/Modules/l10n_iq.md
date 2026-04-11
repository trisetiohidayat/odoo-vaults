---
Module: l10n_iq
Version: 18.0
Type: l10n/iraq
Tags: #odoo18 #l10n #accounting #iraq
---

# l10n_iq

## Overview
Iraq accounting localization — chart of accounts, tax data, and regional state/province listings for Iraqi companies.

## Country
Republic of Iraq — country code `iq`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'iq'`.

## Data Files
- `data/res.country.state.csv` — Iraqi governorate/province data
- `demo/demo_company.xml` — Iraq demo company

## Chart of Accounts
Iraq chart of accounts with `iq` prefix.

## Tax Structure
No detailed tax data file in this module — basic chart and states only. Tax structure defined via the template.

## Fiscal Positions
Not explicitly defined in this module.

## Installation
Standard installation.

## Historical Notes
- Version 1.0 in Odoo 18
- Iraq does not currently have a formal VAT system; income tax and customs are the primary direct taxes
