---
Module: l10n_fr_account
Version: 18.0
Type: l10n/france-accounting
Tags: #odoo18 #l10n #accounting
---

# l10n_fr_account

## Overview
French accounting localization providing the French **PCG** (Plan Comptable Général) chart of accounts, TVA (Taxe sur la Valeur Ajoutée) tax templates, and fiscal position mappings. Also includes support for **Monaco** (PRG — Plan de Compte de Monaco). Supports Factur-X (French/CII hybrid e-invoice format) through the base `account_edi_ubl_cii` module.

## Country
France (Metropolitan), Monaco

## Dependencies
- base_iban
- base_vat
- account
- l10n_fr

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| account_move.py | `AccountMove` | (extends) |
| res_company.py | `ResCompany` | (extends) |
| template_fr.py | `AccountChartTemplate` | (PCG French) |
| template_mc.py | `AccountChartTemplate` | (Monaco PRG) |

## Data Files
- `data/template/account.account-fr.csv` — 649 accounts (PCG — Plan Comptable Général)
- `data/template/account.group-fr.csv` — account groups
- `data/template/account.tax-fr.csv` — French TVA taxes
- `data/template/account.fiscal.position-fr.csv` — 52 fiscal positions
- `data/template/account.tax.group-fr.csv` — French tax groups
- `data/account_chart_template_data.xml` — chart template configuration
- `data/account_data.xml` — French-specific account data
- `data/tax_report_data.xml` — French tax report structure
- `data/l10n_fr_account_demo.xml` — demo data
- `data/res.bank.csv` — French bank list (Banque de France)

## Chart of Accounts
**PCG (Plan Comptable Général)** — 649 accounts based on the French general accounting plan. Mandatory for all French companies (metropolitan). Aligned with the official French accounting classification (classes 1–7 plus classe 8).

Monaco uses the **PRG** (Plan de Compte de Monaco) — provided via `template_mc.py`.

## Tax Structure

| Rate | Description |
|------|-------------|
| 0% | Exempt (EX), EU G/S, Exempt G/S |
| 2.1% | Super-reduced rate (newspapers, medicines) |
| 5.5% | Reduced rate (food, cultural, housing) |
| 8.5% | Intermediate rate (assurance, housing improvements) |
| 10% | Reduced rate (restaurants, transport, renovation) |
| 20% | Standard rate (TVA — taxe sur la valeur ajoutée) |

Tax suffixes: `G` = Goods, `S` = Services, `EU` = Intra-community, `EX` = Export, `INC` = Incluse (included), `R E` = Remise (discount).

## Fiscal Positions
52 fiscal positions covering:
- Domestic France (B2B and B2C)
- EU intra-community B2B (reverse charge — Autoliquidation)
- EU intra-community B2C
- Export outside EU
- Monaco transactions

## EDI/Fiscal Reporting

### Factur-X
France mandates electronic invoices for B2G (Chorus Pro) and increasingly for B2B under the 2024 e-invoicing mandate. **Factur-X** is the French standard — a hybrid PDF+XML format combining a human-readable PDF with embedded CII/ZUGFeRD XML data. Supported via `account_edi_ubl_cii` (UBL/CII PDF attachment generation).

### B2B E-invoicing
France is implementing a national e-invoicing portal (Chorus Facturation) for all B2G invoices, with a phased rollout for B2B invoicing via the PDP (Plateforme de Dématérialisation) system.

## Installation
Install after `[[Modules/l10n_fr]]`. Auto-configured for French mainland companies. Monaco companies use the PRG chart template.

## Historical Notes
- Odoo 17→18: Factur-X attachment to PDFs improved for Chorus Pro compatibility.
- French TVA rates unchanged from Odoo 17.
- The 2.1% super-reduced rate applies to physical newspapers (digital editions may differ).
- France's e-invoicing mandate (2024+) is handled through Peppol network access and Chorus Pro integration.
