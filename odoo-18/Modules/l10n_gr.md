---
Module: l10n_gr
Version: 18.0
Type: l10n/gr
Tags: #odoo18 #l10n #accounting
---

# l10n_gr

## Overview
Greek accounting localization providing the Greek chart of accounts (Γενικό Λογιστικό Σχέδιο), ΦΠΑ (VAT/Φόρος Προστιθέμενης Αξίας) tax templates, and fiscal position mappings. Greece uses a multi-rate VAT system with several reduced rates for tourism and essential goods.

## Country
Greece (Ελλάδα)

## Dependencies
- account
- base_iban
- base_vat

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| template_gr.py | `AccountChartTemplate` | (base) |

## Data Files
- `data/template/account.account-gr.csv` — 454 accounts
- `data/template/account.group-gr.csv` — account groups
- `data/template/account.tax-gr.csv` — Greek ΦΠΑ taxes
- `data/template/account.fiscal.position-gr.csv` — fiscal positions
- `data/template/account.tax.group-gr.csv` — tax groups
- `data/account_tax_report_data.xml` — Greek tax report structure

## Chart of Accounts
454-account Greek chart of accounts based on the Greek General Accounting Plan (Γενικό Λογιστικό Σχέδιο).

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (Exempt, Export, EU G/S, IG) |
| 4% | Super-reduced rate (essential goods, books, medicines) |
| 6% | Reduced rate (food, beverages, cultural) |
| 9% | Reduced rate (transport, hotels, restaurants) |
| 13% | Intermediate rate (certain goods/services) |
| 17% | Special rate (electricity, natural gas) |
| 24% | Standard rate (ΦΠΑ) |

Tax suffixes: `G` = Goods, `S` = Services, `EU G/S` = Intra-community, `IG` = Intra-General (triangular), `Import` = Import transactions.

## Fiscal Positions
Fiscal positions covering:
- Domestic B2B/B2C
- EU intra-community B2B (reverse charge)
- EU intra-community B2C
- Export (outside EU)
- Triangular transactions (IG)
- Tourist trade (special regime)

## EDI/Fiscal Reporting
Greece follows EU VAT reporting requirements. The myDATA platform (ΑΑΔΕ) is the Greek digital tax platform for electronic invoice transmission and VAT reporting. No dedicated EDI module in this package.

## Installation
Manual install or country selection. `auto_install: ['account']`.

## Historical Notes
- Odoo 17→18: Greek VAT rates unchanged from Odoo 17.
- Greece's 13% intermediate rate applies to certain goods categories.
- The 17% rate was introduced for energy products and may be subject to legislative changes.
