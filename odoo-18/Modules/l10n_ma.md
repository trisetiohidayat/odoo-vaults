---
Module: l10n_ma
Version: 18.0
Type: l10n/morocco
Tags: #odoo18 #l10n #accounting #morocco
---

# l10n_ma

## Overview
Morocco accounting localization — chart of accounts, tax report, and partner/company view customizations. Built with assistance from Caudigef. Follows the Moroccan Accounting Framework (Plan Comptable General — PCN).

## Country
Kingdom of Morocco — country code `ma`

## Dependencies
- base
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'ma'`.

### `ResPartner` (`res.partner`)
Inherits `res.partner`. Adds a `_check_company_registry_ma()` `api.constrains` on `company_registry`:
- For partners with `country_code == 'MA'`, validates that `company_registry` is exactly 15 digits (ICE — Identifiant Commun de l'Entreprise, the Moroccan business identifier)
- Raises `ValidationError` if not 15 digits or contains non-digits
- `_get_company_registry_labels()` adds `'MA': 'ICE'` — labels the field as ICE for Moroccan partners

### `BaseDocumentLayout` (`base.document.layout`)
Inherits `base.document.layout`. Used for company document layout configuration (invoice headers, logos, etc.).

## Data Files
- `data/account_tax_report_data.xml` — Moroccan tax report (TVA — Taxe sur la Valeur Ajoutée)
- `views/res_partner_views.xml` — partner view with ICE field label
- `views/res_company_views.xml` — company view customizations
- `views/report_invoice.xml` — invoice report customizations
- `demo/demo_company.xml` — Morocco demo company

## Chart of Accounts
Morocco uses the Plan Comptable General (PCN) with 7 classes — mandatory for companies under Moroccan Commercial Code. Prefixed with `ma`. Includes the full class structure (classe 1: capitaux permanents, classe 2: immobilisations, classe 3: stocks, classe 4: tiers, classe 5: disponibilités, classe 6: charges, classe 7: produits).

## Tax Structure
VAT (TVA) at 0%, 7%, 10%, 14%, 20% rates depending on product/service category. IS (Impôt sur les Sociétés) corporate tax. Tax report in `account_tax_report_data.xml`.

## Fiscal Positions
Defined in template data.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
- Built with help from Caudigef (Moroccan Odoo partner)
- ICE (Identifiant Commun de l'Entreprise) is a 15-digit business identifier introduced by the Moroccan tax authority (DGI)
