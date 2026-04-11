---
Module: l10n_cz
Version: 18.0
Type: l10n/czech-republic
Tags: #odoo18 #l10n #accounting
---

# l10n_cz

## Overview
Czech accounting localization providing the Czech chart of accounts (Účtová osnova) for 2020, DPH (VAT) tax templates, and fiscal position mappings for domestic, EU, and third-country transactions.

## Country
Czech Republic (Česko)

## Dependencies
- account
- base_iban
- base_vat

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| account_move.py | `AccountMove` | (extends) |
| account_move_line.py | `AccountMoveLine` | (extends) |
| res_company.py | `ResCompany` + `BaseDocumentLayout` | (extends) |
| template_cz.py | `AccountChartTemplate` | (base) |

## Data Files
- `data/template/account.account-cz.csv` — 271 accounts
- `data/template/account.group-cz.csv` — account groups
- `data/template/account.tax-cz.csv` — Czech DPH taxes
- `data/template/account.fiscal.position-cz.csv` — fiscal positions
- `data/template/account.tax.group-cz.csv` — tax groups
- `data/tax_report.xml` — Czech tax report structure
- `data/demo_company.xml` — demo company data

## Chart of Accounts
**Český účetní osnova 2020** — 271 accounts organized per Czech accounting class structure (0–9 digit classes). Covers all mandatory account groups required by Czech law.

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (Exempt, EU G/S, Gold, NA), Reverse charge (RC) |
| 12% | Reduced rate (books, medical, cultural) |
| 21% | Standard rate (DPH) |

Tax suffixes: `EU G` = Intra-community goods, `EU S` = Intra-community services, `EX G/S` = Export, `RC` = Reverse charge, `ND` = Non-deductible, `Vehicle` = Motor vehicle specific rate application.

## Fiscal Positions
Czech-specific fiscal positions covering:
- Domestic B2B
- Intra-community goods (DPH reverse charge)
- Intra-community services
- Export transactions
- Gold transactions (special regime)
- Motor vehicle purchases

## EDI/Fiscal Reporting
Czech e-invoicing is governed by the EET (Elektronická evidence tržeb) system for retail and the ISDOC/ISDEF formats for B2B invoices. No dedicated EDI module in this package; standard `account_edi_ubl_cii` applies. EET compliance requires additional configuration.

## Installation
Manual install or country selection.

## Historical Notes
- Odoo 17→18: Chart of accounts updated to 2020 version (Účtová osnova 2020).
- Czech reverse charge (RČ = Reverzní charge) mechanism applied to specific goods categories (mobile phones, computers, electronics).
- DPH (Daň z přidané hodnoty) rates unchanged from Odoo 17.
