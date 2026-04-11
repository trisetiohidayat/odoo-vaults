# l10n_be - Belgium Accounting

## Overview
- **Name:** Belgium - Accounting
- **Country:** Belgium (BE)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 2.0
- **Author:** Noviat, Odoo S.A.
- **License:** LGPL-3
- **Dependencies:** `account`, `account_edi_ubl_cii`, `base_iban`, `base_vat`
- **Auto-installs:** `account`

## Description
Base module for Belgian accounting. Provides chart of account templates, VAT declaration reports, and XML export for Belgian statutory reports (VAT, Intrastat, Annual Listing).

After installation, launches the accounting configuration wizard.

## Models

### account.journal (Inherit)
Extends `account.journal`:
- Adds Belgium-specific `invoice_reference_model` option: `'be'` — formats invoice references as `+++000/2024/00182+++` (Belgian structured communication format)

### res.partner (Inherit)
Extends `res.partner`:
- **_compute_company_registry():** OVERRIDE — for Belgian partners with a valid VAT, the company registry is automatically set to the VAT number (without country code)

### account.chart.template (AbstractModel, partial — `template_be_comp`)
Inherits `account.chart.template`:
- **Template `be_comp`:** Companies sub-template (child of `be`)
  - Code digits: 6
  - Bank prefix: `550`, Cash prefix: `570`, Transfer prefix: `580`
  - Sets fiscal country to Belgium

## Reports (Data-Driven)
The module defines Belgium-specific menu items and sequences for:
- **Partner VAT Intra (XML export)** — Intrastat-style report for intra-EU transactions
- **Periodical VAT Declaration (XML)** — Standard VAT return
- **Annual Listing of VAT-Subjected Customers** — Yearly recapitulative statement

## Data Files
- `data/account_tax_report_data.xml` — Belgian VAT report structure
- `data/l10n_be_sequence_data.xml` — Sequence configurations
- `data/menuitem_data.xml` — Legal reporting menu items
- `demo/demo_company.xml` — Demo company

## Related Modules
- **l10n_be_pos_restaurant** — Belgian restaurant POS
- **l10n_be_pos_sale** — Belgian POS sale extension
