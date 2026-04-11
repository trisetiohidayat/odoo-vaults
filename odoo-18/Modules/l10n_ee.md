---
Module: l10n_ee
Version: 18.0
Type: l10n/estonia
Tags: #odoo18 #l10n #accounting
---

# l10n_ee

## Overview
Estonian accounting localization providing the Estonian chart of accounts, KM (VAT/Käibemaks) tax templates, and fiscal position mappings. Estonia's highly digitalized tax administration supports real-time VAT reporting.

## Country
Estonia

## Dependencies
- account

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| account_tax.py | `AccountTax` | (extends) |
| template_ee.py | `AccountChartTemplate` | (base) |

## Data Files
- `data/template/account.account-ee.csv` — 211 accounts
- `data/template/account.group-ee.csv` — account groups
- `data/template/account.tax-ee.csv` — Estonian KM (VAT) taxes
- `data/template/account.fiscal.position-ee.csv` — fiscal positions
- `data/template/account.tax.group-ee.csv` — tax groups
- `data/account_tax_report_data.xml` — Estonian tax report structure

## Chart of Accounts
211-account Estonian chart of accounts following the Estonian accounting chart structure.

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (Exempt, EU G/S, Triangulation, Passengers, EX VAT Customs) |
| 5% | Reduced rate (essentials) |
| 9% | Reduced rate (accommodation, cultural) |
| 13% | Intermediate rate (EX KMS §38) |
| 20% | Standard rate (Car, Fixed Assets, KMS §41¹) |
| 22% | Previous standard rate (historical) |
| 24% | Current standard rate (KM — Käibemaks) |

Tax suffixes: `G` = Goods, `S` = Services, `Car` = Motor vehicles (with 50% deduction option), `EX KMS §38` = Export under KMS Article 38, `KMS §41¹` = KMS Article 41(1) special regime, `EU G/S Triangulation` = Triangular intra-EU transactions.

## Fiscal Positions
Estonian fiscal positions covering:
- Domestic B2B and B2C
- EU intra-community (goods and services)
- Triangular transactions (A-B-C chain)
- Export transactions (exemption)
- Passenger transport (0% domestic)

## EDI/Fiscal Reporting
Estonia has one of the most digitally advanced tax systems globally. The Estonian Tax and Customs Board (ETCB) provides real-time VAT reporting through the e-MTA system. No dedicated EDI module in this package; standard `account_edi_ubl_cii` provides Peppol/e-invoice support. Estonian e-invoices follow the European standard EN 16931.

## Installation
Manual install or country selection.

## Historical Notes
- Odoo 17→18: Estonian VAT standard rate changed from 22% to 20% (with 22% still available for historical transactions). Current standard rate is 20%.
- Estonia's digital-by-default approach means all VAT declarations are filed online via e-MTA.
- The 9% reduced rate covers accommodation services.
