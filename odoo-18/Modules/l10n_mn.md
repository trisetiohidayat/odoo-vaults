---
Module: l10n_mn
Version: 18.0
Type: l10n/mongolia
Tags: #odoo18 #l10n #accounting
---

# l10n_mn

## Overview
Mongolia accounting localization providing the Mongolian official chart of accounts, tax code structure, and VAT reporting. Contributed by BumanIT LLC. The module uses 8-digit account codes following the Mongolia Official Chart of Accounts.

## Country
Mongolia

## Dependencies
- [Core/BaseModel](BaseModel.md) (account)
- `account` — core accounting module

## Key Models

### AccountChartTemplate (`account.chart.template`, classic extension)
- `_get_mn_template_data()` — sets 8-digit account codes: receivable `account_template_1201_0201`, payable `account_template_3101_0201`, expense `account_template_6101_0101`, income `account_template_5101_0101`, stock input `account_template_1407_0101`, stock output `account_template_1408_0101`, stock valuation `account_template_1401_0101`
- `_get_mn_res_company()` — enables `anglo_saxon_accounting`, fiscal country `base.mn`, bank prefix `11`, cash prefix `10`, transfer prefix `1109`, sale tax `account_tax_sale_vat1`, purchase tax `account_tax_purchase_vat1`

## Data Files
- `data/account.account.tag.csv` — account tags for Mongolian accounting classification
- `data/vat_report.xml` — VAT report structure
- `demo/demo_company.xml` — demo company data

## Chart of Accounts
8-digit account codes based on the Mongolia Official Chart of Accounts:
- `12xx_xxxx` — Receivables (pattern `1201_0201`)
- `31xx_xxxx` — Payables (pattern `3101_0201`)
- `51xx_xxxx` — Revenue (pattern `5101_0101`)
- `61xx_xxxx` — Expenses (pattern `6101_0101`)
- `14xx_xxxx` — Inventory/Stock accounts (valuation `1401`, input `1407`, output `1408`)
- Currency exchange gain: `account_template_5301_0201`, loss: `account_template_5302_0201`
- Early pay discount gain: `account_template_5701_0101`, loss: `account_template_5701_0201`

## Tax Structure
- `account_tax_sale_vat1` — default sale VAT (likely 10%)
- `account_tax_purchase_vat1` — default purchase VAT
- VAT report based on Mongolian Tax Code requirements

## Fiscal Positions
None explicitly defined in the template module.

## EDI/Fiscal Reporting
VAT report via `vat_report.xml`. No dedicated EDI module for Mongolia in Odoo 18.

## Installation
Install via Apps or during company setup by selecting Mongolia as country. Auto-installs with `account`.

## Historical Notes
- Version 1.1 — updated for Odoo 18.
- Developed with financial contribution from Baskhuu Lodoikhuu, BumanIT LLC.
- Mongolia uses a 10% standard VAT rate (check actual tax data in installed instance).
- Anglo-Saxon accounting enabled for proper inventory costing.
