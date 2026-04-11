---
type: module
title: "France (l10n_fr) — French Accounting Localization"
description: "French accounting localization with TVA 20%/10%/5.5%, FEC export, DGFIP compliance, and Chorus Pro EDI. Base module; companion modules add COA and reporting."
source_path: ~/odoo/odoo19/odoo/addons/l10n_fr/
tags:
  - odoo
  - odoo19
  - module
  - l10n
  - localization
  - france
related_modules:
  - account
  - l10n_fr_account
  - l10n_fr_pos_cert
created: 2026-04-07
version: "1.0"
---

## Quick Access

### 🔀 Related Flows
- [[Flows/Account/invoice-creation-flow]] — Invoice with French TVA
- [[Flows/Account/payment-flow]] — French payment processing
- [[Flows/Cross-Module/sale-stock-account-flow]] — Sale→Stock→Invoice

### 🔗 Related Modules
- [[Modules/Account]] — Core accounting
- [[Modules/l10n_fr_account]] — FEC export, French financial reports
- [[Modules/l10n_fr_pos_cert]] — Certified French POS (tickets de Caisse)
- [[Modules/l10n_fr]] — FEC (Fichier des Ecritures Comptables) export

---

# l10n_fr - France Accounting

## Overview
- **Name:** France - Localizations
- **Country:** France (FR)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 2.1
- **Author:** Odoo S.A.
- **License:** LGPL-3
- **Dependencies:** `base` only

## Description
Minimal French localization module. Provides basic country data configuration for French companies. Does not include a full chart of accounts or tax templates — those are handled by companion modules:

- **l10n_fr_account** — French accounting reports (FEC, Bilan, Compte de Resultat)
- **l10n_fr_fec** — Fichier des Ecritures Comptables export
- **l10n_fr_facturx_chorus_pro** — Factur-X / Chorus Pro EDI integration
- **l10n_fr_pos_cert** — Certified French POS
- **l10n_fr_hr_holidays**, **l10n_fr_hr_work_entry_holidays** — HR payroll integration

## Data Files
- `data/res_country_data.xml` — French country-specific data
- `views/res_company_views.xml` — Company configuration views
- `views/res_partner_views.xml` — Partner configuration views
- `demo/demo_company.xml` — Demo company

## Key Notes
- No Python models — purely declarative via data files
- Auto-installs with `account` when a French company is created (via `base` country detection)
