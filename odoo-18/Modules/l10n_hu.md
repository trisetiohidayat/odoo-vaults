---
Module: l10n_hu
Version: 18.0
Type: l10n/hu
Tags: #odoo18 #l10n #accounting
---

# l10n_hu

## Overview
Hungarian accounting localization providing the Hungarian chart of accounts (Számviteli törvény / Hungarian Accounting Law), ÁFA (általános forgalmi adó / VAT) tax templates, and fiscal position mappings. Hungary has one of the highest standard VAT rates in the EU.

## Country
Hungary (Magyarország)

## Dependencies
- account
- base_vat

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| account_move.py | `AccountMove` | (extends) |
| res_partner.py | `ResPartner` | (extends) |
| template_hu.py | `AccountChartTemplate` | (base) |

## Data Files
- `data/template/account.account-hu.csv` — 389 accounts
- `data/template/account.group-hu.csv` — account groups
- `data/template/account.tax-hu.csv` — Hungarian ÁFA taxes
- `data/template/account.fiscal.position-hu.csv` — fiscal positions
- `data/template/account.tax.group-hu.csv` — tax groups
- `data/account_tax_report_data.xml` — Hungarian tax report structure
- `data/res.bank.csv` — Hungarian bank list

## Chart of Accounts
389-account Hungarian chart of accounts structured per the Hungarian Accounting Law (Számviteli törvény).

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (AAM, EU G/S, EX, G/S EX, G/S EXEMPT, ICA, R, TAM) |
| 5% | Reduced rate (essentials, medicines, newspapers) |
| 7% | Reduced rate (cultural, sporting, catering) |
| 12% | Reduced rate (construction, housing renovation) |
| 18% | Intermediate rate |
| 27% | Standard rate (ÁFA — highest in EU) |

Tax suffixes: `AAM` = Reverse charge agricultural, `EU G/S` = Intra-community, `EX/S EXEMPT` = Export exemption, `ICA` = Intra-Community Acquisition, `TAM` = Tax agent reverse charge, `PPE` = Particular performance rule, `CS` = Cash accounting scheme.

Hungary's 27% standard VAT rate is the highest in the EU.

## Fiscal Positions
Hungarian fiscal positions covering:
- Domestic B2B/B2C
- EU intra-community goods and services (reverse charge)
- Export transactions
- Reverse charge for specific sectors (construction, agricultural, electronic communications)

## EDI/Fiscal Reporting
Hungary uses the **Online Számla** (Online Invoice) system — mandatory real-time invoice reporting to NAV (Nemzeti Adó- és Vámhivatal). E-invoicing is required for B2G transactions. EDI handled by `l10n_hu_edi` (separate module). See `[Modules/l10n_hu_edi](Modules/l10n_hu_edi.md)`.

## Installation
Manual install or country selection.

## Historical Notes
- Odoo 17→18: Hungarian ÁFA rates unchanged from Odoo 17.
- Hungary's NAV Online Számla system is one of the most comprehensive real-time reporting systems in the EU.
- Cash accounting scheme (ÁFA készpénzforgalmi nyilvántartás) available for small businesses.
- The 12% rate applies specifically to construction and housing renovation services.
