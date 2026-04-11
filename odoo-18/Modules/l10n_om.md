---
Module: l10n_om
Version: 18.0
Type: l10n/oman
Tags: #odoo18 #l10n #accounting #oman #gcc
---

# l10n_om

## Overview
Oman accounting localization — chart of accounts, VAT at 5%, tax report (VAT return), and regional state data.

## Country
Sultanate of Oman — country code `om`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'om'`.

## Data Files
- `data/res.country.state.csv` — Oman governorate/wilayat data
- `data/tax_report.xml` — VAT return report with sections for supplies at 5%, zero-rated, exempt, and imports
- `demo/demo_company.xml` — Oman demo company

## Chart of Accounts
Oman chart of accounts with `om` prefix.

## Tax Structure
VAT at 5% (Oman VAT effective April 2021). Tax report includes:
- 1(a): Supplies of goods/services taxed at 5%
- Standard rated, zero-rated, exempt, and import categories

## Fiscal Positions
Defined in `tax_report.xml`.

## Installation
`auto_install: True` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
- Oman VAT at 5% (same rate as UAE, lower than Saudi 15%)
