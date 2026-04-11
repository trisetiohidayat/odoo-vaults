---
Module: l10n_et
Version: 2.0
Type: l10n/ethiopia
Tags: #odoo18 #l10n #accounting #east_africa
---

# l10n_et

## Overview
Ethiopia accounting localization — chart of accounts, VAT tax structure, withholding tax structure, and regional state data. Authored by Michael Telahun Makonnen. This is a complete redesign from earlier versions (v2.0 vs v1.x in Odoo 17).

## Country
Federal Democratic Republic of Ethiopia — country code `et`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'et'`.

## Data Files
- `data/account_tax_report_data.xml` — Ethiopian tax report (VAT and withholding tax)
- `demo/demo_company.xml` — Ethiopia demo company

## Chart of Accounts
Ethiopian chart of accounts with `et` prefix. Ethiopia's accounting standards follow the Ethiopian Accounting Standards (EAS), largely derived from IFRS, with specific adaptations for the Ethiopian business environment. No mandatory national chart (unlike SYSCOHADA countries).

## Tax Structure
- VAT: 15% standard rate, 0% exports, exempt categories
- Withholding tax: Applied on payments to contractors, dividends, royalties, rent, professional fees, etc. at varying rates (2%–10%+) depending on the nature of payment and recipient type
- Turnover tax: For small businesses below VAT registration threshold
- Income tax: Progressive rates for individuals, flat 30% for companies

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 2.0 in Odoo 18 — complete redesign of Ethiopian localization
- Ethiopia's tax administration is managed by the Ethiopia Revenue Authority (ERA)
- Regional states (Tigray, Amhara, Oromia, SNNP, etc.) listed in `data/res.country.state.csv`
