---
Module: l10n_pk
Version: 18.0
Type: l10n/pakistan
Tags: #odoo18 #l10n #accounting #withholding
---

# l10n_pk

## Overview
Pakistan accounting localization providing the Pakistani chart of accounts, GST/WHT structure, and tax reporting for both VAT and withholding tax. Supports province-level sales tax in addition to federal GST.

## Country
Pakistan

## Dependencies
- [Core/BaseModel](Core/BaseModel.md) (account)
- `account` — core accounting module

## Key Models

### AccountChartTemplate (`account.chart.template`, classic extension)
- `_get_pk_template_data()` — sets 7-digit account codes: receivable `l10n_pk_1121001`, payable `l10n_pk_2221001`, income `l10n_pk_3111001`, expense `l10n_pk_4111001`
- `_get_pk_res_company()` — fiscal country `base.pk`, bank/cash/transfer prefix `112600`, suspense `l10n_pk_2226000`, early pay discount loss `l10n_pk_4411003`, gain `l10n_pk_3112004`, sale tax `pk_sales_tax_17`, purchase tax `purchases_tax_17`

## Data Files
- `data/res.country.state.csv` — Pakistan provinces/states for address handling
- `data/account_tax_vat_report.xml` — VAT tax report
- `data/account_tax_wh_report.xml` — Withholding Tax report
- `migrations/1.1/end-migrate_update_taxes.py` — tax update migration
- `demo/res_partner_demo.xml` — demo partner data
- `demo/demo_company.xml` — demo company data

## Chart of Accounts
7-digit account codes:
- `112xxxx` — Assets (bank/cash/transfer grouped here)
- `222xxxx` — Payables (including suspense `2226000`)
- `311xxxx` — Income (including early pay discount gain `3112004`)
- `411xxxx` — Expenses (including early pay discount loss `4411003`)

## Tax Structure
Pakistan uses a dual VAT/ Sales Tax system:
- Federal GST at 17% default: `pk_sales_tax_17`, `purchases_tax_17`
- Provincial sales taxes (SRB, PRA, etc.) — supported through fiscal positions and tax definitions
- Withholding tax reporting via `account_tax_wh_report.xml`
- WHT categories: dividend, interest, royalty, technical services, rent, etc.

## Fiscal Positions
Not explicitly defined in this module.

## EDI/Fiscal Reporting
- VAT Tax Report via `account_tax_vat_report.xml`
- Withholding Tax Report via `account_tax_wh_report.xml`
- No dedicated EDI module for Pakistan in Odoo 18

## Installation
Install via Apps or during company setup by selecting Pakistan as country. Version 1.1 migration updates taxes from previous version.

## Historical Notes
- Version 1.1: Tax updates in Odoo 18.
- Pakistan's tax system: Federal Board of Revenue (FBR) GST + Provincial sales taxes.
- 17% standard GST rate (federal).
- Withholding tax regime covers multiple categories: salary, dividend, interest, royalty, technical services, rent, etc.
- The withholding tax report is designed for FBR compliance.
