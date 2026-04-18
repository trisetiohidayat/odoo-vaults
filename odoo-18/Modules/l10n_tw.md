---
Module: l10n_tw
Version: 18.0
Type: l10n/taiwan
Tags: #odoo18 #l10n #accounting
---

# l10n_tw

## Overview
Taiwan accounting localization providing the Taiwanese chart of accounts, business tax (VAT) structure, and Taiwan-specific address/city data. Depends on `base_address_extended` for city/district address support. Taiwan uses 6-digit account codes, Anglo-Saxon accounting, and `round_globally` tax calculation.

## Country
Taiwan

## Dependencies
- [Core/BaseModel](Core/BaseModel.md) (account)
- `account` — core accounting module
- `base_address_extended` — extended address fields (city/district)

## Key Models

### AccountChartTemplate (`account.chart.template`, classic extension)
- `_get_tw_template_data()` — sets 6-digit account codes: receivable `tw_119100`, payable `tw_217100`, expense `tw_511100`, income `tw_411100`, stock input `tw_124500`, stock output `tw_124600`, stock valuation `tw_123100`
- `_get_tw_res_company()` — enables `anglo_saxon_accounting`, fiscal country `base.tw`, bank prefix `1113`, cash prefix `1111`, transfer prefix `1114`, POS receivable `tw_119150`, sale tax `tw_tax_sale_5`, purchase tax `tw_tax_purchase_5`, early pay discount loss `tw_411400`, gain `tw_512400`, cash diff income `tw_718500`, expense `tw_718600`, `tax_calculation_rounding_method: round_globally`

## Data Files
- `data/res.country.state.csv` — Taiwan states/counties for address handling
- `data/res_currency_data.xml` — currency data
- `data/res_country_data.xml` — country configuration
- `data/res.city.csv` — Taiwan cities/districts for address forms
- `demo/demo_company.xml` — demo company data

## Chart of Accounts
6-digit account codes:
- `111xxxx` — Cash/Bank (cash `1111`, bank `1113`, transfer `1114`)
- `119xxxx` — Receivables (general `119100`, POS `119150`)
- `123xxxx` — Inventory/Stock valuation (`123100`)
- `124xxxx` — Stock input/output (`124500`, `124600`)
- `217xxxx` — Payables (`217100`)
- `411xxxx` — Revenue (`411100`, early pay discount loss `411400`)
- `511xxxx` — Expenses (`511100`, early pay discount gain `512400`)
- `718xxxx` — Other income/expense (currency exchange `718100`/`718200`, cash diff income `718500`/`718600`)

## Tax Structure
Taiwan uses **Business Tax (營業稅)** — a form of VAT:
- `tw_tax_sale_5` — 5% sale Business Tax (default sale tax)
- `tw_tax_purchase_5` — 5% purchase Business Tax (default purchase tax)
- Taiwan's business tax rate is typically 5% for general businesses (with exceptions for financial institutions, small businesses, etc.)
- `tax_calculation_rounding_method: round_globally` — Taiwan tax is calculated with global rounding

## Fiscal Positions
None explicitly defined in the template module.

## EDI/Fiscal Reporting
No dedicated EDI module for Taiwan in Odoo 18. No tax report XML data file in the module itself — the `account` module may provide a generic report for Taiwan.

## Installation
Install via Apps or during company setup by selecting Taiwan as country. Auto-installs with `account`. The `res.city.csv` data provides Taiwan-specific city/district options for partner addresses.

## Historical Notes
- Version 1.0 — initial Odoo 18 release.
- Taiwan's Business Tax (營業稅) was reformed in 2020 with a new electronic invoice system (電子發票) — this module does not yet include e-invoice support.
- Taiwan uses invoice-based tax with a Uniform Invoice Number (統一發票) system for retail transactions.
- 5% is the standard business tax rate; financial institutions use 2%, small-scale businesses use 1%.
- Anglo-Saxon accounting enabled for inventory costing.
