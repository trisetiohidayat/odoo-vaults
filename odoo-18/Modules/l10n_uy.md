---
Module: l10n_uy
Version: 18.0
Type: l10n/uruguay
Tags: #odoo18 #l10n #accounting #uruguay
---

# l10n_uy — Uruguay Accounting

## Overview
Uruguayan accounting localization providing the generic chart of accounts, VAT taxes (IVA), document types, identification types, and currency configuration (UYU, UYI Unidad Indexada). DGI (Direccion General Impositiva) compliant. Co-maintained by Uruguay l10n Team, Guillem Barba, and ADHOC. Requires [Modules/l10n_latam_base](odoo-18/Modules/l10n_latam_base.md) and [Modules/l10n_latam_invoice_document](odoo-18/Modules/l10n_latam_invoice_document.md).

## Country/Region
Uruguay (country code: UY)

## Dependencies
- account
- l10n_latam_invoice_document
- l10n_latam_base

## Key Models

### `l10n_latam.document.type` (Extended via Data)
Document types defined in CSV for Uruguay: Factura, Nota de Credito, Nota de Debito, Remito, etc.

### `res.partner` (Extended)
Inherits: `res.partner`
Pre-configured contacts: DGI (tax authority), Consumidor Final Uruguayo.

### `account.chart.template` (Extended)
Method `_template_uy()`: Loads Uruguayan chart of accounts.

## Chart of Accounts
Generic Uruguayan chart of accounts aligned with DGI requirements and NIIF. 4-digit account codes.

## Tax Structure
- **IVA** (Impuesto al Valor Agregado): 22% (standard), 10% (reduced), 0% (exempt)
- Uruguay uses an invoice/credit-note/debit-note document type system via `l10n_latam_invoice_document`

## Currencies
- **UYU**: Peso Uruguayo
- **UYI**: Unidad Indexada Uruguaya (inflation-adjusted unit used for long-term contracts)

## Fiscal Positions
Fiscal positions for IVA categories: Responsable, Consumidor Final, No Responsable, Exportacion.

## Data Files
- `data/account_tax_report_data.xml`: Tax report structure
- `data/l10n_latam.document.type.csv`: DGI document types
- `data/l10n_latam_identification_type_data.xml`: CI (Cedula de Identidad), RUT, Pasaporte types
- `data/res_partner_data.xml`: DGI, Consumidor Final
- `data/res_currency_data.xml`: UYU and UYI currency configuration
- `views/account_tax_views.xml`: Tax configuration view
- `demo/demo_company.xml`: UY Company
- `demo/res_currency_rate_demo.xml`: Currency rate demo data

## Installation
Install with accounting. Demo company provided with chart, taxes, and document types.

## Historical Notes
Version 0.1 in Odoo 18. Uruguay's DGI has mandated electronic invoicing for most taxpayers. The `l10n_latam_invoice_document` framework provides the document type structure. The Unidad Indexada (UYI) currency is unique to Uruguay — it adjusts for inflation using the ICP (Indice de Precios al Consumo) and is used in accounting for long-term contracts and financial instruments. The `l10n_uy_pos` module adds POS support; `l10n_uy_website_sale` adds eCommerce support.
