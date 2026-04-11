---
Module: l10n_zm_account
Version: 1.0.0
Type: l10n/zambia
Tags: #odoo18 #l10n #accounting #southern_africa
---

# l10n_zm_account

## Overview
Zambia accounting localization — chart of accounts, taxes, fiscal positions, and custom invoice report for Zambian companies.

## Country
Republic of Zambia — country code `zm`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'zm'`.

### `AccountMove` (`account.move`)
Inherits `account.move`. Overrides `_get_name_invoice_report()` — returns `l10n_zm_account.report_invoice_document` custom Zambia invoice layout when company is Zambian.

## Data Files
- `data/account_tax_report_data.xml` — Zambia tax report
- `views/report_invoice.xml` — Zambia-specific invoice report
- `demo/demo_company.xml` — Zambia demo company

## Chart of Accounts
Zambian chart of accounts with `zm` prefix. Zambia follows Zambian Accounting Standards (ZAS), IFRS-aligned. Not a SYSCOHADA country.

## Tax Structure
- VAT at 16% standard rate (Zambia Revenue Authority — ZRA)
- Withholding tax on dividends (0% for residents, 15% for non-residents), interest, royalties, management fees
- Corporate income tax: 30%
- Mineral royalty tax (for mining companies)
- ZRA administers all federal taxes

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
Standard installation (no `auto_install` specified).

## Historical Notes
- Version 1.0.0 in Odoo 18
