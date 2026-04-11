---
Module: l10n_bg
Version: 18.0
Type: l10n/bulgaria
Tags: #odoo18 #l10n #accounting
---

# l10n_bg

## Overview
Bulgarian accounting localization providing the Bulgarian chart of accounts and VAT (ДДС) tax templates for Bulgaria's three-rate VAT system.

## Country
Bulgaria

## Dependencies
- account
- base_vat

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| template_bg.py | `AccountChartTemplate` | (base) |

## Data Files
- `data/template/account.account-bg.csv` — 332 accounts
- `data/template/account.group-bg.csv` — account groups
- `data/template/account.tax-bg.csv` — Bulgarian VAT taxes
- `data/template/account.fiscal.position-bg.csv` — fiscal positions
- `data/template/account.tax.group-bg.csv` — tax groups
- `data/tax_report.xml` — Bulgarian tax report structure

## Chart of Accounts
332-account Bulgarian chart of accounts aligned with local accounting regulations. Bulgarian account codes use the national classification system.

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (EX), Triangulation (Tri), EU OTC/PTC |
| 9% | Reduced rate (Essentials — food, medicine) |
| 20% | Standard rate (FTC/PTC — Forward/Pay customs) |

Tax codes include: `FTC` = Forward Tax Credit, `PTC` = Pay Tax Credit, with optional EU and triangulation suffixes.

## Fiscal Positions
Fiscal position mappings for:
- Domestic (вътрешни)
- Intra-EU triangular transactions (EU OTC/PTC)
- Export transactions (EXEMPT)

## EDI/Fiscal Reporting
No dedicated EDI module in the base package. Bulgarian VAT reporting is done through the NRA (National Revenue Agency) portal. The companion module `l10n_bg_ledger` provides report ledger functionality.

## Installation
Manual install or country auto-install.

## Historical Notes
- Odoo 17→18: Bulgarian VAT rates unchanged (0%, 9%, 20%).
- Bulgarian specific OTC (One-Triangulation Card) and PTC (Pay-Triangulation Card) fiscal positions support triangular intra-EU transactions.
