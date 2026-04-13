---
Module: l10n_kr
Version: 18.0
Type: l10n/south-korea
Tags: #odoo18 #l10n #accounting
---

# l10n_kr

## Overview
Republic of Korea (South Korea) accounting localization providing the Korean chart of accounts, corporate tax structure, and tax reports. Sets `account_price_include: 'tax_included'` globally, meaning Korean taxes are configured as tax-included by default.

## Country
Republic of Korea (South Korea)

## Dependencies
- [Core/BaseModel](Core/BaseModel.md) (account)
- `account` — core accounting module

## Key Models

### AccountChartTemplate (`account.chart.template`, classic extension)
- `_get_kr_template_data()` — sets 6-digit account codes: receivable `l10n_kr_111301`, payable `l10n_kr_212001`, expense `l10n_kr_510001`, income `l10n_kr_410001`, stock valuation `l10n_kr_112101`, stock input `l10n_kr_112702`, stock output `l10n_kr_112703`, production WIP `l10n_kr_112704`
- `_get_kr_res_company()` — sets `account_price_include: 'tax_included'`, fiscal country `base.kr`, transfer prefix `1116`, bank prefix `1111`, sale tax `l10n_kr_sale_10`, purchase tax `l10n_kr_purchase_10`, deferred expense `l10n_kr_111401`, deferred revenue `l10n_kr_216005`

## Data Files
- `data/res_country_data.xml` — country-specific configuration
- `data/general_tax_report.xml` — general corporate tax report
- `data/simplified_tax_report.xml` — simplified tax report
- `demo/demo_company.xml` — demo company data

## Chart of Accounts
6-digit account codes structured with Korean accounting standards:
- `111xxx` — Assets (receivable `111301`, bank `1111xx`, transfer `1116xx`, stock/Inventory `1121xx`, WIP `1124xx`, prepaid `1114xx`)
- `212xxx` — Payables (`212001`)
- `41xxx` — Income (`410001`, early pay discount gain `410003`)
- `51xxx` — Expenses (`510001`, early pay discount loss `410008`)
- `42xxx` — Non-operating income (currency exchange gain `420007`, cash diff income `420013`)
- `62xxx` — Non-operating expenses (currency exchange loss `620007`, cash diff expense `620014`)

## Tax Structure
Default 10% VAT (Value-Added Tax):
- `l10n_kr_sale_10` — 10% sale tax
- `l10n_kr_purchase_10` — 10% purchase tax
- Korean taxes are **tax-included** by default (`account_price_include: 'tax_included'` set on company)
- Two tax reports: General Tax Report and Simplified Tax Report

## Fiscal Positions
None defined in this module.

## EDI/Fiscal Reporting
- General Tax Report and Simplified Tax Report for corporate tax filing
- Tax-included pricing means tax amounts are embedded in line prices; Odoo extracts tax on posting

## Installation
Install via Apps or during company setup by selecting South Korea as country. Auto-installs with `account`.

## Historical Notes
- Version 1.0 — initial Odoo 18 release.
- Tax-included pricing (`account_price_include: 'tax_included'`) is the Korean convention — prices quoted typically include VAT.
- The `l10n_kr_production_wip_account_id` and `l10n_kr_production_wip_overhead_account_id` fields on res.company support Korean manufacturing accounting.
