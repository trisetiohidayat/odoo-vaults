---
Module: l10n_ie
Version: 18.0
Type: l10n/ie
Tags: #odoo18 #l10n #accounting
---

# l10n_ie

## Overview
Irish accounting localization providing the Irish chart of accounts, VAT (Value Added Tax) tax templates following Irish Revenue rules, and fiscal position mappings for EU and third-country trade.

## Country
Ireland

## Dependencies
- account
- base_iban
- base_vat

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| template_ie.py | `AccountChartTemplate` | (base) |

## Data Files
- `data/template/account.account-ie.csv` — 145 accounts
- `data/template/account.tax-ie.csv` — Irish VAT taxes
- `data/template/account.fiscal.position-ie.csv` — fiscal positions
- `data/template/account.tax.group-ie.csv` — tax groups
- `data/tax_report-ie.xml` — Irish tax report structure

## Chart of Accounts
145-account Irish chart of accounts based on Irish accounting standards. Ireland uses a simplified chart compared to continental European systems.

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (EX G/S), Zero-rated (EU G/S, G/S EXEMPT) |
| 4.8% | Livestock / agricultural reduced rate (LS) |
| 9% | Reduced rate (tourism, cultural, sporting) |
| 13.5% | Standard reduced rate (services, professional) |
| 23% | Standard rate (VAT) |

Tax suffixes: `EU G/S` = Intra-community, `EX G/S` = Export, `G/S EXEMPT` = Exempt, `LS` = Livestock scheme.

Notable: Ireland has a special **4.8% rate for livestock and agricultural goods** — a historically significant rate for the farming sector.

## Fiscal Positions
Irish fiscal positions covering:
- Domestic (Ireland)
- EU intra-community B2B (with VAT number validation)
- EU intra-community B2C
- Export outside EU
- Reverse charge for specific services

## EDI/Fiscal Reporting
Irish Revenue (Revenue Commissioners) requires electronic filing of VAT returns for most businesses. No dedicated EDI module in this package.

## Installation
Manual install or country selection.

## Historical Notes
- Odoo 17→18: Irish VAT rates unchanged from Odoo 17.
- Ireland's 4.8% agricultural rate is unique in the EU and reflects the importance of the farming sector.
- The 9% rate (tourism rate) was temporarily reduced during COVID-19 and may be subject to legislative adjustment.
- Irish VAT rules differ between goods and services with specific reverse charge rules for construction and sub-contracting.
