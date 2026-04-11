---
Module: l10n_tr_nilvera_einvoice_extended
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #turkey #nilvera #einvoice
---

# l10n_tr_nilvera_einvoice_extended

## Overview
Extends `l10n_tr_nilvera_einvoice` with additional invoice scenarios (Basic, Export, Public Sector), invoice types (Sales, Withholding, Tax Exempt, Registered for Export), and tax office configuration. Adds Turkish Tax Office master data, withholding reason codes, exemption reason codes, and extended UBL TR templates covering all Nilvera invoice profiles.

## EDI Format / Standard
Same UBL TR 1.2 as parent. Adds profile scenarios and extended templates.

## Dependencies
- `l10n_tr_nilvera_einvoice` -- core Nilvera e-invoice
- `contacts` -- contact model extensions

## Key Models

### `l10n_tr_nilvera_einvoice_extended.tax.office` (`l10n_tr_nilvera_einvoice_extended.l10n_tr_nilvera_einvoice_extended_tax_office`)
Stands alone: no `_inherit`.

- `name` -- Char (translateable)
- `code` -- Integer (tax office code)
- `state_id` -- Many2one to `res.country.state`
- `state_code` -- Related to `state_id.code`

Master data for Turkish Revenue Administration (GİB) tax offices.

### `l10n_tr_nilvera_einvoice_extended.account.tax.code` (`l10n_tr_nilvera_einvoice_extended.l10n_tr_nilvera_einvoice_extended_account_tax_code`)
Stands alone: no `_inherit`.

- `name` / `code` -- Char fields
- `code_type` -- Selection: `withholding | exemption | other`

Defines withholding reason codes (`l10n_tr_tax_withholding_code_id` on `account.tax`) and exemption reason codes.

### `account.tax` (`l10n_tr_nilvera_einvoice_extended.account_tax`)
Extends: `account.tax`

- `l10n_tr_tax_withholding_code_id` -- Many2one to `l10n_tr_nilvera_einvoice_extended.account.tax.code` (domain: `code_type = 'withholding'`)

Links tax to a Nilvera withholding reason code.

### `account.edi.xml.ubl.tr` (`l10n_tr_nilvera_einvoice_extended.account_edi_xml_ubl_tr`)
Extends: `account.edi.xml.ubl.tr` (from parent)

Adds scenario/type-based profile selection and extended template rendering.

### `account.move` / `account.move.send` / `account.move.line` / `res.company` / `res.partner` / `product.product` / `product.template` / `res.config.settings`
Various extensions to wire tax office, withholding codes, exemption reasons, and company settings through to the UBL export.

## Data Files
- `data/l10n_tr_nilvera_einvoice_extended.tax.office.csv` -- Tax office master data (400+ entries)
- `data/account_incoterms_data.xml` -- Incoterms for export invoices
- `data/ubl_tr_templates.xml` -- Extended UBL templates
- `security/ir.model.access.csv` -- ACL
- `views/account_tax_views.xml`, `views/res_company_views.xml`, `views/l10n_tr_nilvera_einvoice_extended_tax_office_views.xml` -- UI

## How It Works
1. User configures tax withholding codes and exemption reason codes on account taxes
2. Tax office master data is available on company/partner forms
3. When invoice is exported, `_export_invoice_vals()` uses the extended templates to render scenario-specific UBL
4. Withholding reason codes (`TD.SPECIAL.code`) are embedded in tax lines per Nilvera requirements

## Installation
Auto-installs with `l10n_tr_nilvera_einvoice`. The `post_init_hook` `_l10n_tr_nilvera_einvoice_extended_post_init` loads tax office data.

## Historical Notes
The "extended" module separates invoice scenarios into distinct modules in Odoo 18. In Odoo 17, the Turkish e-invoice templates did not differentiate scenarios as granularly. The separate `account.tax.code` model for withholding and exemption reasons mirrors the Revenue Administration's official code lists.
