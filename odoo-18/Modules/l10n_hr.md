---
Module: l10n_hr
Version: 18.0
Type: l10n/hr
Tags: #odoo18 #l10n #accounting
---

# l10n_hr

## Overview
Croatian accounting localization based on the **RRIF 2021** (Računovodstveni i revizijski standardi / Croatian Accounting and Auditing Standards) chart of accounts. Provides PDV (porez na dodanu vrijednost / VAT) tax templates and fiscal position mappings. Croatia uses the euro as its currency since 2023.

## Country
Croatia (Hrvatska)

## Dependencies
- account
- base_vat

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| template_hr.py | `AccountChartTemplate` | (base) |

## Data Files
- `data/template/account.account-hr.csv` — 552 accounts
- `data/template/account.group-hr.csv` — account groups
- `data/template/account.tax-hr.csv` — Croatian PDV taxes
- `data/template/account.fiscal.position-hr.csv` — fiscal positions
- `data/template/account.tax.group-hr.csv` — tax groups
- `data/account_tax_report_data.xml` — Croatian tax report structure
- `data/l10n_hr_chart_data.xml` — RRIF 2021 chart data

## Chart of Accounts
552-account Croatian chart of accounts based on **RRIF 2021** (Računovodstveni i revizijski standardi). Croatia adopted euro (EUR) on 1 January 2023; all amounts in Odoo 18 should be in EUR.

Sources:
- RRIF Bilanka 2016
- RRIF-RP2021 (Croatian Accounting Standards)

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (EX, EXEMPT, EU G/M/S, EU Trans, R C) |
| 5% | Reduced rate (basic necessities, medical, cultural) |
| 13% | Intermediate rate (accommodation, transport) |
| 25% | Standard rate (PDV) |

Tax suffixes: `EU G` = Intra-community goods, `EU S` = Intra-community services, `EU M` = Intra-community mixed, `EU Trans` = Triangular transactions, `EX M` = Import exemption, `R C` = Reverse charge.

## Fiscal Positions
Croatian fiscal positions covering:
- Domestic B2B/B2C
- EU intra-community (goods, services, mixed)
- Triangular intra-EU transactions
- Import transactions
- Reverse charge domestic (for construction and specific goods)

## EDI/Fiscal Reporting
Croatia uses the **e-Porezak** (e-Tax) system for electronic VAT reporting. No dedicated EDI module in this package.

## Installation
Manual install or country selection.

## Historical Notes
- Odoo 17→18: Chart of accounts updated to RRIF 2021 standard.
- Croatia switched from HRK to EUR on 1 January 2023 — Odoo 18 uses EUR natively.
- 13% PDV rate (intermediate rate) applies primarily to tourist accommodation and certain transport services.
