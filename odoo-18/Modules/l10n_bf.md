---
Module: l10n_bf
Version: 18.0
Type: l10n/burkina_faso
Tags: #odoo18 #l10n #accounting #west_africa #syscohada
---

# l10n_bf

## Overview
Burkina Faso accounting localization — provides the SYSCOHADA-compliant chart of accounts and tax report for Burkinabe companies. All West and Central African OHADA-zone countries share the same chart of accounts (SYSCOHADA), with only the tax rates and tax report line items differing per country.

See also: [Modules/l10n_syscohada](Modules/l10n_syscohada.md) for the shared SYSCOHADA framework chart.

## Country
Burkina Faso — country code `bf`

## Dependencies
- l10n_syscohada
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'bf'`. Provides `_get_bf_syscebnl_template_data()` using the SYSCOHADA framework from the base `l10n_syscohada` module.

## Data Files
- `data/account_tax_report_data.xml` — Burkina Faso tax report (TVA at 18%, other taxes)
- `demo/demo_company.xml` — Burkina Faso demo company

## Chart of Accounts
SYSCOHADA Revised Plan (Plan Comptable OHADA Révisé) — the uniform 8-class accounting system mandated by OHADA for 17 African nations. Burkina Faso joined OHADA in 1995. The chart uses 6-digit codes with `pcg_` prefix inherited from the base `l10n_syscohada` module:

- Classe 1: Capitaux permanents — capital, reserves, results, financial debts
- Classe 2: Immobilisations — intangible, tangible, financial assets
- Classe 3: Stocks et en-cours — merchandise, raw materials, finished goods
- Classe 4: Tiers — clients, fournisseurs, state, social
- Classe 5: Banques et trésorerie — banks and cash
- Classe 6: Charges — purchases, services, personnel, taxes
- Classe 7: Produits — sales, services, other revenue
- Classe 8: Comptes de liaison / hors bilan

## Tax Structure
- **TVA (Taxe sur la Valeur Ajoutée)**: 18% standard rate (WAEMU harmonized rate)
- **IS (Impôt sur les Sociétés)**: 27.5% standard rate for companies
- **IR (Impôt sur les Revenus)**: for individuals and sole proprietors
- Withholding taxes on payments for services
- Burkina Faso uses the WAEMU (West African Economic and Monetary Union) common tax framework

## Fiscal Positions
Defined in `data/account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed when account module is installed.

## Historical Notes
- Version 1.0 in Odoo 18
- Burkina Faso joined OHADA in 1995; SYSCOHADA is the mandatory accounting standard for medium and large enterprises
- Taxes administered by the Direction Générale des Impôts (DGI) of Burkina Faso
