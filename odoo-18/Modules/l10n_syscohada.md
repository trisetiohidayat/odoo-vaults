---
Module: l10n_syscohada
Version: 18.0
Type: l10n/ohada
Tags: #odoo18 #l10n #accounting #ohada #syscohada
---

# l10n_syscohada

## Overview
OHADA/SYSCOHADA accounting framework module — the shared chart of accounts base for 17 West and Central African countries. This is the foundational module that all country-specific OHADA localizations depend on. It provides the SYSCOHADA Revised plan: a standardized 8-class accounting structure mandated by the OHADA Treaty (Organisation pour l'Harmonisation en Afrique du Droit des Affaires).

## Region
OHADA zone — 17 African nations

## Countries
Benin, Burkina Faso, Cameroon, Central African Republic, Comoros, Congo (Republic of), Ivory Coast, Gabon, Guinea, Guinea-Bissau, Equatorial Guinea, Mali, Niger, Democratic Republic of the Congo, Senegal, Chad, Togo

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'syscohada'`.

`_get_syscohada_template_data()` sets:
- `property_account_receivable_id`: `pcg_4111` (Clients — effets à recevoir)
- `property_account_payable_id`: `pcg_4011` (Fournisseurs — effets à payer)
- `property_account_expense_categ_id`: `pcg_6011` (Achats de marchandises)
- `property_account_income_categ_id`: `pcg_7011` (Ventes de marchandises)
- `name`: `'SYSCOHADA - Revised'`
- `code_digits`: `6`

`_get_syscohada_res_company()` sets defaults:
- `bank_account_code_prefix`: `521`
- `cash_account_code_prefix`: `571`
- `transfer_account_code_prefix`: `585`
- `account_default_pos_receivable_account_id`: `pcg_4113`
- `income_currency_exchange_account_id`: `pcg_776`
- `expense_currency_exchange_account_id`: `pcg_676`
- `account_journal_early_pay_discount_loss_account_id`: `pcg_6019`
- `account_journal_early_pay_discount_gain_account_id`: `pcg_7019`

## Data Files
- `data/menuitem_data.xml` — menu structure for accounting reports
- `data/template/` — chart of accounts data (account.account records)

## Chart of Accounts: SYSCOHADA Revised Plan
The SYSCOHADA (Système Comptable OHADA) is an 8-class plan:

| Class | Description | Example accounts |
|-------|-------------|-----------------|
| **Classe 1** | Capitaux permanents (Permanent capital) | 101 Capital, 105 Primes liées au capital, 11 Réserves, 12 Résultat net de l'exercice, 14 Provisions réglementées, 16 Dettes financières |
| **Classe 2** | Immobilisations (Fixed assets) | 21 Immobilisations incorporelles, 22 Immobilisations corporelles, 23 Immobilisations en cours, 24 Participations et créances financières |
| **Classe 3** | Stocks et en-cours (Inventories) | 31 Marchandises, 32 Matières premières, 33 Autres approvisionnements, 35 Stocks de produits |
| **Classe 4** | Tiers (Third parties) | 401 Fournisseurs, 411 Clients, 43 Sécurité sociale, 44 État et collectivités publiques, 45 Groupe et associés |
| **Classe 5** | Banques, établissements financiers et assimilés | 521 Banque locale, 531 Chèques postaux, 571 Caisse |
| **Classe 6** | Charges (Expenses) | 601 Achats de marchandises, 611 Achats de matières premières, 62 Services extérieurs, 63 Charges de personnel, 64 Impôts et taxes, 65 Autres charges d'exploitation, 66 Charges financières, 67 Charges exceptionnelles |
| **Classe 7** | Produits (Revenue) | 701 Ventes de marchandises, 706 Prestations de services, 708 Produits annexes, 71 Production stockée, 72 Production immobilisée, 74 Subventions d'exploitation, 75 Autres produits d'exploitation, 76 Produits financiers, 77 Produits exceptionnels |
| **Classe 8** | Comptes de liaison et hors bilan (Link accounts and off-balance sheet) | 81 Valeurs in limbo, 85 Stocksходящие, 88 Engagements reçus, 89 Engagements donnés |

The plan uses 6-digit codes prefixed with `pcg_` in Odoo (Plan Comptable Général).

## Tax Structure
No taxes defined in this module — taxes are country-specific and defined in each country module (e.g., `l10n_bf` for Burkina Faso, `l10n_cm` for Cameroon, etc.). Each country module adds TVA (TVA at country-specific rates) and IS/IR corporate income tax reporting structures.

Typical OHADA country VAT rates:
| Country group | Standard TVA rate |
|---------------|-------------------|
| WAEMU (UEMOA) | 18% (Benin, Burkina Faso, Côte d'Ivoire, Guinea-Bissau, Mali, Niger, Senegal, Togo) |
| CEMAC | 18% (Cameroon, Central African Republic, Chad, Congo, Gabon) |
| Other OHADA | Variable (DRC 16%, Equatorial Guinea 15%, Comoros 10%) |

## Fiscal Positions
No fiscal positions in this base module — defined in country-specific modules.

## Installation
Standard installation. This module is a dependency for the 16 country-specific OHADA modules and is typically installed automatically via `l10n_*` module dependencies.

## Historical Notes
- Odoo 18 SYSCOHADA is the "Revised" version aligned with the 2017 OHADA accounting regulations (Le Système Comptable OHADA Révisé, SCOHADA-R)
- The SYSCOHADA norm is mandatory for all companies registered in OHADA member states that meet the size thresholds (medium and large enterprises)
- Small enterprises may use a simplified plan (SYSCOHADA PME)
- Reference: `http://biblio.ohada.org/pmb/opac_css/doc_num.php?explnum_id=2063`
