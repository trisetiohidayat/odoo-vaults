---
type: module
title: "United States (l10n_us) — US Accounting Localization"
description: "US accounting localization with state sales tax integration, fiscal positions by state, 1099 vendor reporting, and no mandatory COA."
source_path: ~/odoo/odoo19/odoo/addons/l10n_us/
tags:
  - odoo
  - odoo19
  - module
  - l10n
  - localization
  - usa
related_modules:
  - account
  - account_tax_python
created: 2026-04-07
version: "1.0"
---

## Quick Access

### 🔀 Related Flows
- [[Flows/Account/invoice-creation-flow]] — US customer invoice
- [[Flows/Account/payment-flow]] — 1099 payment processing
- [[Flows/Cross-Module/purchase-stock-account-flow]] — PO→Receipt→Vendor Bill

### 🔗 Related Modules
- [[Modules/Account]] — Core accounting
- [[Modules/account_tax_python]] — Python-based sales tax computation
- [[Modules/l10n_us_account]] — US-specific chart of accounts

---

# l10n_us - United States Localizations

## Overview
- **Name:** United States - Localizations
- **Country:** United States (US)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 1.1
- **Author:** Odoo S.A.
- **License:** LGPL-3
- **Dependencies:** `base` only

## Description
Minimal US localization module. Provides basic country-specific data for US companies. The US does not have a mandatory statutory chart of accounts, so this module focuses on:
- US country data
- Company data for demo
- Bank account view configurations (e.g., routing/account number fields)

## Data Files
- `data/res_company_data.xml` — US company data
- `views/res_partner_bank_views.xml` — Bank account views (routing number, account number fields)
- `demo/demo_company.xml` — Demo US company

## Key Notes
- No chart of accounts template — US GAAP accounting is handled by the base `account` module
- No tax templates — US sales tax is handled by `account_tax_python` or third-party apps (Avalara, TaxJar)
- State-level sales tax nexus management requires additional modules
