---
Module: l10n_fi
Version: 18.0
Type: l10n/finland
Tags: #odoo18 #l10n #accounting
---

# l10n_fi

## Overview
Finnish accounting localization providing the Finnish chart of accounts (Tilinpäätös), ALV (arvonlisävero/VAT) tax templates, fiscal positions, and Finnish standard invoice payment reference (viitenumero) support.

## Country
Finland (Suomi)

## Dependencies
- base_iban
- base_vat
- account

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| account_journal.py | `AccountJournal` | (extends) |
| account_move.py | `AccountInvoiceFinnish` | (extends) |
| template_fi.py | `AccountChartTemplate` | (base) |

### AccountInvoiceFinnish
Extends `AccountMove` with Finnish invoice numbering and payment reference validation. Supports the Finnish standard reference (viitenumero) format for invoice payment references.

## Data Files
- `data/template/account.account-fi.csv` — 971 accounts
- `data/template/account.tax-fi.csv` — Finnish ALV taxes
- `data/template/account.fiscal.position-fi.csv` — Finnish fiscal positions
- `data/template/account.tax.group-fi.csv` — tax groups
- `data/account_account_tag_data.xml` — account tags
- `data/account_tax_report_line.xml` — Finnish tax report line structure

## Chart of Accounts
971-account Finnish chart of accounts based on the statutory Finnish accounting chart (Tilinpäätöskaava). One of the most comprehensive in EU localizations, reflecting Finland's detailed account classification requirements.

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (EX, TRI), Zero-rated (EU G/S, Åland), No deduction (C) |
| 10% | Reduced rate (food, accommodation) |
| 14% | Medium rate (transport, cultural) |
| 24% | Standard rate (ALV) |
| 25.5% | Previous standard rate (historical) |

Tax suffixes: `G` = Goods, `S` = Services, `EU` = Intra-community, `EX D` = Export with documents, `FI C` = Finnish construction reverse charge, `C` = Cash accounting eligible.

## Fiscal Positions
Finnish-specific fiscal positions covering:
- Domestic B2B/B2C
- EU intra-community (goods and services)
- Export transactions
- Triangular transactions (TRI)
- Åland Islands (special economic zone — 0% under specific conditions)

## EDI/Fiscal Reporting
Finnish e-invoicing is highly developed. Standard format is Finvoice (ISO 20022 based). Peppol/PEPPOL BIS Billing 3.0 is supported via `account_edi_ubl_cii`. Finnish Tax Administration (Verohallinto) receives VAT reports via MyTax (OmaVero).

## Installation
Manual install or country selection.

## Historical Notes
- Odoo 17→18: Finnish ALV standard rate reduced from 25.5% to 24% (effective 2024/2025 reform reflected in Odoo 18 data).
- Finnish invoice payment reference (viitenumero) validation is built into the account move model.
- Åland Islands have a special VAT regime — goods shipped to Åland from mainland Finland are zero-rated if certain conditions are met.
