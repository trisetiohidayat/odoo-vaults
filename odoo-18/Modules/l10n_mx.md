---
Module: l10n_mx
Version: 18.0
Type: l10n/mexico
Tags: #odoo18 #l10n #accounting #mexico
---

# l10n_mx — Mexico Accounting

## Overview
Mexico accounting localization providing the minimal SAT-compliant chart of accounts and taxes for CFDI (Comprobante Fiscal Digital por Internet) compliance. Maintained by Vauxoo. Adds `l10n_mx_factor_type` and `l10n_mx_tax_type` to taxes, SAT account tags for debit/credit classification, DIOT report data, Mexican bank ABM codes, CLABE bank account numbers, and UoM codes. CFDI 4.0 compatible.

## Country/Region
Mexico (country code: MX)

## Dependencies
- account

## Key Models

### `account.tax` (Extended)
Inherits: `account.tax`
Added fields:
- `l10n_mx_factor_type` (Selection): Tasa | Cuota | Exento — CFDI 4.0 TipoFactor. Indicates whether the tax base is a rate (Tasa), fixed amount (Cuota), or exempt.
- `l10n_mx_tax_type` (Selection, computed): isr | iva | ieps | local — SAT tax classification. Auto-set to `iva` for MX company taxes.

Method `_compute_l10n_mx_tax_type()`: Sets `iva` for any tax where `country_id.code == 'MX'`.

### `account.account` (Extended)
Inherits: `account.account`
Method `create()`: Auto-tags Mexican accounts with SAT debit/credit balance tags. DEBIT_CODES = ['1', '5', '6', '7'] (codes starting with these → debit balance account); others → credit balance account.

### `res.bank` (Extended)
Inherits: `res.bank`
Added field:
- `l10n_mx_edi_code` (Char): ABM 3-digit bank identification code from Asociacion de Bancos de Mexico.

### `res.partner.bank` (Extended)
Inherits: `res.partner.bank`
Added field:
- `l10n_mx_edi_clabe` (Char): CLABE (Clave Bancaria Estandarizada) — 18-digit standardized Mexican bank account number for SPEI interbank transfers.

### `account.chart.template` (Extended)
Method `_template_mx()`: Loads Mexican chart of accounts.

## Chart of Accounts
SAT-compliant chart with account tags for financial reports. Accounts auto-tagged with debit/credit balance SAT tags on creation. The Mexican chart follows SAT grouping requirements for financial statement filing.

## Tax Structure
- **IVA**: 16% (Impuesto al Valor Agregado), general rate
- **ISR**: Impuesto Sobre la Renta (Income Tax)
- **IEPS**: Impuesto Especial sobre Produccion y Servicios (Special tax on specific goods/services — beverages, tobacco, fuels)
- **Factor Types** (CFDI 4.0 TipoFactor): Tasa (rate-based), Cuota (fixed amount), Exento (exempt)
- **Retenciones**: Withholdings on honorarios, dividends

## DIOT Report
`data/account_report_diot.xml`: DIOT (Informacion sobre Operaciones con Terceros) report required by SAT for documenting VAT credits from suppliers.

## Data Files
- `data/account.account.tag.csv`: SAT debit/credit balance classification tags
- `data/account_report_diot.xml`: DIOT report structure
- `data/res_bank_data.xml`: Mexican banks with ABM codes (BBVA Bancomer, Banamex, Santander, HSBC, etc.)
- `views/partner_view.xml`: RFC field on partner
- `views/res_bank_view.xml`: Bank configuration
- `views/account_views.xml`: Account view with SAT tags
- `views/account_tax_view.xml`: Tax view with CFDI fields
- `data/l10n_mx_uom.xml`: Mexican UoM codes
- `demo/demo_company.xml`

## Installation
Install with accounting. Post-init hook `_enable_group_uom_post_init` activates UoM grouping. SAT debit/credit tags auto-applied to new accounts.

## Historical Notes
Version 2.3 in Odoo 18. Key Odoo 17→18 change: CFDI 4.0 compatibility added via `l10n_mx_factor_type` (TipoFactor) field. The Mexican localization is primarily a data/configuration module — the actual CFDI electronic invoicing (PAC-based signature and validation) is handled by community modules (e.g., `l10n_mx_edi`). Mexico mandated CFDI for all invoices since 2014. The DIOT report is mandatory for VAT-registered companies. CLABE numbers are required for SPEI transfers (Mexico's interbank electronic transfer system).
