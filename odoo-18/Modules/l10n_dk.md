---
Module: l10n_dk
Version: 18.0
Type: l10n/denmark
Tags: #odoo18 #l10n #accounting
---

# l10n_dk

## Overview
Danish accounting localization covering both sole proprietors (enkeltmandsvirksomhed) and all company forms (I/S, IVS, ApS, A/S). Provides the Danish chart of accounts, moms (VAT) tax templates (25% standard rate plus special rates), and fiscal position mappings for EU and export transactions.

## Country
Denmark

## Dependencies
- base_iban
- base_vat
- account

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| account_account.py | `AccountAccount` | (extends) |
| account_journal.py | `AccountJournal` | (extends) |
| res_partner.py | `ResPartner` | (extends) |
| template_dk.py | `AccountChartTemplate` | (base) |

## Data Files
- `data/template/account.account-dk.csv` — 303 accounts
- `data/template/account.group-dk.csv` — account groups
- `data/template/account.tax-dk.csv` — Danish VAT (moms) taxes
- `data/template/account.fiscal.position-dk.csv` — 14 fiscal positions
- `data/template/account.tax.group-dk.csv` — tax groups
- `data/account.account.tag.csv` — account tags
- `data/account_tax_report_data.xml` — Danish VAT report structure

## Chart of Accounts
303-account Danish chart of accounts structured per Danish accounting law. Covers all standard account classes (0–9) required for Danish financial reporting.

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (EU-Momsfritaget), Zero-rated (DK-MF, EU-MF), Margin schemes |
| 5% | Cultural exemption (kunstnere) |
| 25% | Standard rate (moms) |
| 25% | Various EU cross-border variants (ArealFradrag, DelvisFradrag, SkønsmæssigFradrag) |

Tax prefixes: `K-` = Kundens (customer) VAT application, `S-` = Sælgers (seller) VAT application. The Danish VAT system distinguishes between full deduction, partial deduction, and no deduction categories.

Special schemes: **Brugtmoms** (used goods margin scheme), **Marginmoms** (margin scheme), **Leasebiler** (leasing vehicles).

## Fiscal Positions
14 fiscal positions including:
- Denmark domestic (Company/B2B)
- EU countries (Company/B2B with VAT)
- EU countries (Private/B2C)
- Non-EU export
- Reverse charge scenarios for specific goods

## EDI/Fiscal Reporting
Danish e-invoicing is mandatory for B2G (government) through the OIOUBL 2.0/2.1 standard via the Nemhandel network. EDI modules:
- `[Modules/l10n_dk_nemhandel](l10n_dk_nemhandel.md)` — OIOUBL 2.1 Nemhandel protocol
- `[Modules/l10n_dk_oioubl](l10n_dk_oioubl.md)` — OIOUBL 2.01 format

Both are available separately and extend `account_edi_ubl_cii`.

## Installation
Manual install or country selection. EDI modules are installed separately as needed.

## Historical Notes
- Odoo 17→18: Danish VAT structure unchanged (25% standard rate).
- OIOUBL 2.1 (l10n_dk_nemhandel) updated from OIOUBL 2.0.
- Danish VAT has no reduced rates — only 0%, 5%, and 25% (the latter being the highest in the EU).
- Rental income and real estate have specific VAT deduction rules (ArealFradrag).
