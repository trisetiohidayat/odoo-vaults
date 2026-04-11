---
Module: l10n_lt
Version: 18.0
Type: l10n/lt
Tags: #odoo18 #l10n #accounting
---

# l10n_lt

## Overview
Lithuanian accounting localization providing the Lithuanian chart of accounts (Buhalterinės apskaitos principai), PVM (pridėtinės vertės mokestis / VAT) tax templates, fiscal positions, and Lithuanian bank data.

## Country
Lithuania (Lietuva)

## Dependencies
- account

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| account_journal.py | `AccountJournal` | (extends) |
| template_lt.py | `AccountChartTemplate` | (base) |

## Data Files
- `data/template/account.account-lt.csv` — 186 accounts
- `data/template/account.tax-lt.csv` — Lithuanian PVM taxes
- `data/template/account.fiscal.position-lt.csv` — fiscal positions
- `data/template/account.tax.group-lt.csv` — tax groups
- `data/account_account_tag_data.xml` — account tags
- `data/res_bank_data.xml` — Lithuanian bank list (SWIFT/BIC codes)

## Chart of Accounts
186-account Lithuanian chart of accounts based on Lithuanian accounting standards (Buhalterinės apskaitos įstatymas).

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (EX, EX S, EXEMPT), Special VAT deductions (VAT100, VAT15, VAT42) |
| 5% | Reduced rate (medicine, books, cultural) |
| 9% | Reduced rate (accommodation, heating) |
| 21% | Standard rate (PVM) |

Tax suffixes: `A` = Acquisition, `EU A` = Intra-community acquisition, `G S` = Goods and services, `ND` = Non-deductible, `R` = Reverse charge.

Special codes: `VAT42` = 1/6 partial deduction (old regime), `VAT15` = 15% flat rate for small businesses, `VAT100` = 100% deduction.

## Fiscal Positions
Lithuanian fiscal positions covering:
- Domestic B2B/B2C
- EU intra-community (acquisitions and supplies)
- Export transactions
- Special flat-rate scheme (VAT15) for small businesses
- Reverse charge for construction and specific goods

## EDI/Fiscal Reporting
Lithuania follows EU VAT reporting requirements. The i.MAS system (E. pristatymo sistema) is the Lithuanian e-invoicing system. No dedicated EDI module in this package.

## Installation
Manual install or country selection.

## Historical Notes
- Odoo 17→18: Lithuanian VAT rates unchanged.
- Lithuania's special VAT deduction codes (VAT15, VAT42) support small business flat-rate schemes.
- The 5% reduced rate applies to essential goods and services including books and medicines.
