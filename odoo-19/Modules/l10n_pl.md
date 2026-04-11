# l10n_pl - Poland Accounting

## Overview
- **Name:** Poland - Accounting
- **Country:** Poland (PL)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 2.0
- **Author:** Odoo S.A., Grzegorz Grzelak (OpenGLOBE)
- **License:** LGPL-3
- **Dependencies:** `base_iban`, `base_vat`, `account`, `account_edi_ubl_cii`
- **Auto-installs:** `account`

## Description
Polish accounting localization providing a standard chart of accounts (Plan Kont), taxes, tax areas, and tax registers. Uses Storno accounting (credit-note accounting).

## Models

### account.chart.template (AbstractModel)
Inherits `account.chart.template`:
- **Template `pl`:**
  - Receivable: `chart20000100`, Payable: `chart21000100`
  - Code digits: 8
  - Uses Storno accounting: `use_storno_accounting: True`
  - Bank prefix: `11.000.00`, Cash prefix: `12.000.00`, Transfer: `11.090.00`
  - Inventory valuation accounts configured

### account.move (Inherit)
Extends `account.move` with Polish VAT invoice flags:
- **l10n_pl_vat_b_spv:** Single-purpose voucher (SPV) transfer by taxable person
- **l10n_pl_vat_b_spv_dostawa:** SPV supply to a taxpayer
- **l10n_pl_vat_b_mpv_prowizja:** Agency services for SPV transfer
- **_compute_show_taxable_supply_date():** Always shows taxable supply date for PL invoices
- **_get_accounting_date_source():** Uses `taxable_supply_date` instead of invoice date for PL
- **_get_invoice_currency_rate_date():** Uses `taxable_supply_date` for currency rate date

### res.company (Inherit)
Extends `res.company`:
- **l10n_pl_reports_tax_office_id:** Many2one to `l10n_pl.l10n_pl_tax_office` — specifies the tax office for Polish tax filings

## Data Files
- `security/ir.model.access.csv` — Access rights
- `data/l10n_pl.l10n_pl_tax_office.csv` — Tax office master data
- `data/account.account.tag.csv` — Polish account tags
- `data/account_tax_report_data.xml` — Polish VAT/JPK report structure
- `views/account_move_views.xml`, `views/product_views.xml`, `views/res_partner_views.xml`, `views/res_config_settings_views.xml`

## Post-Init Hook
`_preserve_tag_on_taxes` — preserves account tags on taxes after installation.
