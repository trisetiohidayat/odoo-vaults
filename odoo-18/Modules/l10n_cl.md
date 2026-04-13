---
Module: l10n_cl
Version: 18.0
Type: l10n/chile
Tags: #odoo18 #l10n #accounting #chile
---

# l10n_cl — Chile Accounting

## Overview
Chilean localization module providing the Chilean chart of accounts (Plan de Cuentas Chileno), taxes (IVA 19%, 27%), SII (Servicio de Impuestos Internos) document types, taxpayer type classification, and identification types (RUT, RUN). Maintained by Blanco Martin & Asociados. Requires [Modules/l10n_latam_base](odoo-18/Modules/l10n_latam_base.md) and [Modules/l10n_latam_invoice_document](odoo-18/Modules/l10n_latam_invoice_document.md).

## Country/Region
Chile (country code: CL)

## Dependencies
- contacts
- base_vat
- l10n_latam_base
- l10n_latam_invoice_document
- uom
- account

## Key Models

### `res.partner` (Extended)
Inherits: `res.partner`
Added fields:
- `l10n_cl_sii_taxpayer_type` (Selection): 1=VAT Affected (1st Category), 2=Fees Receipt Issuer (2nd category), 3=End Consumer, 4=Foreigner
- `l10n_cl_activity_description` (Char): Economic activity description (giro comercial)

Methods:
- `_format_vat_cl()`: Sanitizes and formats Chilean VAT (RUT) using `stdnum.cl.vat`. Strips dots and CL prefix, returns clean RUT
- `_format_dotted_vat_cl()`: Formats RUT with dotted thousands separators (e.g., `76.123.456-K`)
- `_commercial_fields()`: Returns super() + `l10n_cl_sii_taxpayer_type`
- `create()` / `write()`: Auto-format VAT on partner create/write

### `account.journal` (Extended)
Inherits: `account.journal`
Chilean journals auto-set `l10n_latam_use_documents = True` on sale/purchase journals for SII document types.

### `account.chart.template` (Extended)
Method `_template_cl()`: Loads Chilean chart of accounts.

## Chart of Accounts
Chilean chart based on NIIF (Normas Internacionales de Informacion Financiera). 5-digit account codes following Chilean accounting plan. Includes specific accounts for IVA credito/fisco.

## Tax Structure
- IVA 19% (general rate)
- IVA 27% (additional rate for certain goods/services)
- Taxes for withholding on fees (honorarios)
- SII document types: Factura Electronica, Factura no Afecta/Exenta, Guia de Despacho, Nota de Credito, Nota de Debito, Liquidacion Factura, etc.

## Fiscal Positions
Fiscal positions for SII taxpayer types: afecta, exenta, consumidor final, extranjero.

## Data Files
- `views/account_move_view.xml`: Document type on moves
- `views/account_tax_view.xml`: Chilean tax configuration
- `views/res_bank_view.xml`: Chilean banks
- `views/res_country_view.xml`: Country configuration
- `views/res_company_view.xml`: Company settings
- `views/report_invoice.xml`: Invoice report customization
- `views/res_partner.xml`: Partner form extensions
- `views/res_config_settings_view.xml`: Settings view
- `data/l10n_cl_chart_data.xml`: Chart of accounts
- `data/account_tax_report_data.xml`: Tax report
- `data/account_tax_tags_data.xml`: Tax tags
- `data/l10n_latam_identification_type_data.xml`: Identification types
- `data/l10n_latam.document.type.csv`: SII document types
- `data/product_data.xml`: Chilean products
- `data/uom_data.xml`: Chilean UoM
- `data/res.currency.csv`: CLP/UF currencies
- `data/res.bank.csv`: Chilean banks list
- `data/res.country.csv`: Country configuration
- `data/res_partner.xml`: Demo partners
- `demo/partner_demo.xml`, `demo/demo_company.xml`

## Installation
Install with accounting. SII document types and chart of accounts are loaded automatically.

## Historical Notes
Version 3.1 in Odoo 18. Author: Blanco Martin & Asociados. Chilean localization is one of the most complete LATAM modules. SII has been mandating electronic invoicing progressively. The `l10n_latam_invoice_document` integration provides SII document sequences per journal.
