---
Module: l10n_lu
Version: 18.0
Type: l10n/lu
Tags: #odoo18 #l10n #accounting
---

# l10n_lu

## Overview
Luxembourg accounting localization providing the Luxembourg Official Chart of Accounts (law of June 2009 + 2015 chart), comprehensive tax templates covering Luxembourg's complex tax system including **TVA** (Taxe sur la Valeur Ajoutée), intra-community (EC), and reverse charge (IC) schemes, and fiscal position mappings.

## Country
Luxembourg

## Dependencies
- account
- base_iban
- base_vat

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| template_lu.py | `AccountChartTemplate` | (base) |

## Data Files
- `data/template/account.account-lu.csv` — 746 accounts
- `data/template/account.group-lu.csv` — account groups
- `data/template/account.tax-lu.csv` — Luxembourg TVA taxes
- `data/template/account.fiscal.position-lu.csv` — fiscal positions
- `data/template/account.tax.group-lu.csv` — tax groups
- `data/l10n_lu_chart_data.xml` — Luxembourg chart of accounts data
- `data/tax_report/section_1.xml` — tax report section 1
- `data/tax_report/section_2.xml` — tax report section 2
- `data/tax_report/sections_34.xml` — tax report sections 3-4
- `data/tax_report/tax_report.xml` — full tax report structure

## Chart of Accounts
746-account Luxembourg Official Chart of Accounts based on the law of June 2009 with 2015 updates. One of the most comprehensive EU charts reflecting Luxembourg's role as an international financial center.

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (EC E/G/S, IC E/G/S, ICT, EX EC, EX IC, ST G, S S) |
| 3% | Reduced rate (certain goods) |
| 7% | Reduced rate (restaurant, accommodation) |
| 8% | Reduced rate (fuel, transport) |
| 13% | Intermediate rate |
| 14% | Intermediate rate |
| 16% | Intermediate rate |
| 17% | Higher rate (ATN — benefit in kind) |

Luxembourg's tax system includes complex distinctions:
- **EC** = Intra-community transactions
- **IC** = Reverse charge / Intra-community acquisition
- **EC(P)** = Particular reverse charge scenarios
- **E** = Expenditure/expense treatment
- **G** = Goods, **S** = Services, **IG/IS** = Intra-group
- ATN (Avantage en Nature) = Benefits in kind for employee taxation

## Fiscal Positions
Comprehensive fiscal position mappings covering:
- Domestic B2B/B2C
- EC intra-community (supplies with VAT, exempt)
- IC reverse charge (acquisitions)
- EC(P) particular reverse charge scenarios
- ICT (Intra-group transactions)
- Export transactions
- Special regimes for financial and investment services

## EDI/Fiscal Reporting
Luxembourg participates in EU ViDA/PEPPOL e-invoicing mandates. No dedicated EDI module in this package.

## Installation
Post-init hook `_post_init_hook` applies custom account tags. `auto_install: ['account']`.

## Historical Notes
- Odoo 17→18: Luxembourg VAT rates unchanged from Odoo 17.
- Luxembourg's complex tax system with EC/IC/EC(P) distinctions reflects its role as an international financial and holding center.
- The ATN (Avantage en Nature) tax codes support employee benefit calculations required by Luxembourg labor law.
- Luxembourg's 746-account chart is notably more detailed than neighboring countries, supporting complex financial instrument accounting.
