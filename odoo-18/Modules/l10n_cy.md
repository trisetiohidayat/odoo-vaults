---
Module: l10n_cy
Version: 18.0
Type: l10n/cyprus
Tags: #odoo18 #l10n #accounting
---

# l10n_cy

## Overview
Cyprus localization module providing the Cypriot chart of accounts, VAT (ΦΠΑ) tax templates, and tax report structures. Compliant with Cyprus VAT legislation.

## Country
Cyprus

## Dependencies
- account
- base_vat

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| template_cy.py | `AccountChartTemplate` | (base) |

## Data Files
- `data/template/account.account-cy.csv` — 169 accounts
- `data/template/account.tax-cy.csv` — Cypriot VAT taxes
- `data/template/account.fiscal.position-cy.csv` — fiscal positions
- `data/template/account.tax.group-cy.csv` — tax groups
- `data/account_tax_report_data.xml` — Cypriot tax report structure
- `data/menuitem_data.xml` — menu configuration

## Chart of Accounts
169-account Cypriot chart of accounts based on the Cyprus Companies Law accounting classification.

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (E), Zero-rated (EU, OEU) |
| 3% | Reduced rate (food, books, medical) |
| 5% | Reduced rate (tourism, transport) |
| 9% | Reduced rate (certain goods/services) |
| 19% | Standard rate (ΦΠΑ — VAT) |

Tax suffixes: `EU` = Intra-community, `S` = Services, `RC` = Reverse Charge, `OEU` = Outside EU.

## Fiscal Positions
Fiscal position mappings for:
- Domestic transactions
- Intra-EU B2B (with VAT number validation)
- Intra-EU B2C
- Export outside EU (exemption)

## EDI/Fiscal Reporting
No dedicated EDI module. Cyprus follows EU VAT reporting requirements. The `account_edi_ubl_cii` module provides standard e-invoicing support.

## Installation
Manual install or country selection auto-install.

## Historical Notes
- Odoo 18 retains the same VAT rate structure as Odoo 17.
- Cyprus uses the standard EU reverse charge mechanism for B2B intra-EU transactions.
