---
Module: l10n_be
Version: 18.0
Type: l10n/belgium
Tags: #odoo18 #l10n #accounting
---

# l10n_be

## Overview
Belgium's base accounting localization. Provides the official Belgian chart of accounts (PCMN — Plan Comptable Minimum Normalisé), VAT tax templates for all Belgian VAT rates, and fiscal position mappings for intra-EU and third-country trade. Launches the accounting configuration wizard on install.

## Country
Belgium

## Dependencies
- account
- base_iban
- base_vat

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| account_journal.py | `AccountJournal` | (base) |
| account_move.py | `AccountMove` | (base) |
| account_tax.py | `AccountTax` | (base) |
| res_partner.py | `ResPartner` | (base) |
| template_be.py | `AccountChartTemplate` | (base) |
| template_be_asso.py | `AccountChartTemplate` | (base) |
| template_be_comp.py | `AccountChartTemplate` | (base) |

### AccountChartTemplate variants
- `template_be.py` — Standard Belgian PCMN chart (307 accounts)
- `template_be_asso.py` — Association/non-profit variant (43 additional accounts)
- `template_be_comp.py` — Compromise structure for specific entity types (68 accounts)

## Data Files
- `data/template/account.account-be.csv` — 307 accounts (PCMN)
- `data/template/account.account-be_asso.csv` — 43 association accounts
- `data/template/account.account-be_comp.csv` — 68 compromise accounts
- `data/template/account.group-be.csv` — account groups
- `data/template/account.tax-be.csv` — Belgian VAT taxes
- `data/template/account.fiscal.position-be.csv` — 72 fiscal positions
- `data/template/account.tax.group-be.csv` — tax groups
- `data/account_tax_report_data.xml` — Belgian tax report structure
- `data/l10n_be_sequence_data.xml` — invoice number sequences
- `data/menuitem_data.xml` — menu configuration

## Chart of Accounts
Based on the **PCMN (Plan Comptable Minimum Normalisé)** — the mandatory Belgian minimum chart of accounts. Three variants:
- **Full PCMN**: 307 accounts for general use
- **Asso variant**: +43 accounts for non-profit associations (ASBL/VZW)
- **Comp variant**: +68 accounts for companies requiring extended classification

Account numbering uses the standard Belgian 7-digit structure (0-7 classes).

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (EX), Intra-EU (EU G/M/S/T), reverse charge |
| 6% | Reduced rate (books, cultural, medical) |
| 12% | Medium rate (restaurants, hotels, housing renovation) |
| 21% | Standard rate (TVA/BTW) |
| 21% | Various domestic (D35, D50, D85) breakdown variants |

Tax suffixes: `G` = Goods, `S` = Services, `M` = Mixed, `IG` = Intra-Genéral, with `Cocont` for co-contractor scenarios.

## Fiscal Positions
72 fiscal positions including:
- Belgium B2B (with VAT number validation)
- EU B2C private persons
- Intra-Community supply (reverse charge)
- Export to non-EU (exemption)
- Triangular transactions

## EDI/Fiscal Reporting
Belgium participates in EU ViDA/PEPPOL e-invoicing. No dedicated Belgian EDI module in this package; relies on `account_edi_ubl_cii` for UBL/CII formats. Belgian e-invoicing mandates (Chorus Pro for government invoices) require additional configuration.

## Installation
Install manually or auto-triggered by country selection.

## Historical Notes
- Odoo 17→18: Belgian tax report XML export format updated for EU VAT reporting changes.
- Three chart template variants consolidated from prior versions.
- VAT division codes (D35/D50/D85) support the Belgium-specific Belgian VAT reporting breakdown requirements.
