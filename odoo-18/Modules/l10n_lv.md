---
Module: l10n_lv
Version: 18.0
Type: l10n/lv
Tags: #odoo18 #l10n #accounting
---

# l10n_lv

## Overview
Latvian accounting localization providing the Latvian chart of accounts, PVN (pievienotās vērtības nodoklis / VAT) tax templates, fiscal positions, and Latvian bank data.

## Country
Latvia (Latvija)

## Dependencies
- account
- base_vat

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| template_lv.py | `AccountChartTemplate` | (base) |

## Data Files
- `data/template/account.account-lv.csv` — 242 accounts
- `data/template/account.group-lv.csv` — account groups
- `data/template/account.tax-lv.csv` — Latvian PVN taxes
- `data/template/account.fiscal.position-lv.csv` — fiscal positions
- `data/template/account.tax.group-lv.csv` — tax groups
- `data/account_tax_report_data.xml` — Latvian tax report structure

## Chart of Accounts
242-account Latvian chart of accounts based on Latvian accounting standards.

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (EU G/S Tri, EX G/S, RC, S) |
| 5% | Reduced rate (medicine, books, cultural) |
| 12% | Reduced rate (accommodation, transport, cultural) |
| 21% | Standard rate (PVN) |

Tax suffixes: `EU G/S` = Intra-community goods/services, `EU G Tri` = Triangular transaction, `EX G/S` = Export exemption, `RC` = Reverse charge, `S` = Standard.

## Fiscal Positions
Latvian fiscal positions covering:
- Domestic B2B/B2C
- EU intra-community goods and services
- Triangular intra-EU transactions (EU G Tri)
- Export transactions
- Reverse charge for construction and specific goods

## EDI/Fiscal Reporting
Latvia uses the **e-Adrese** (e-Address) system for government communications and the **VID** (Valsts Ieņēmumu Diena / SRS) tax portal for VAT reporting. No dedicated EDI module in this package.

## Installation
Manual install or country selection.

## Historical Notes
- Odoo 17→18: Latvian VAT rates unchanged from Odoo 17.
- Latvia uses a three-rate VAT system (5%, 12%, 21%) with the 12% rate covering accommodation, transport, and cultural events.
- The triangular transaction support (EU G Tri) reflects Latvia's role in intra-Baltic trade chains.
