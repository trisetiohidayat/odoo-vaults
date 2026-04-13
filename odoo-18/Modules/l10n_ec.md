---
Module: l10n_ec
Version: 18.0
Type: l10n/ecuador
Tags: #odoo18 #l10n #accounting #ecuador
---

# l10n_ec — Ecuadorian Accounting

## Overview
Comprehensive Ecuadorian localization. Adds the Ecuadorian chart of accounts (based on Super Intendencia de Companias recommendations), SRI (Servicio de Rentas Internas) taxes and withholdings, fiscal positions, document types, identification types, and local bank list. Maintained by TRESCLOUD. Requires [Modules/l10n_latam_base](l10n_latam_base.md) and [Modules/l10n_latam_invoice_document](l10n_latam_invoice_document.md).

## Country/Region
Ecuador (country code: EC)

## Dependencies
- base
- base_iban
- account_debit_note
- l10n_latam_invoice_document
- l10n_latam_base
- account

## Key Models

### `l10n_ec.sri.payment`
Inherits: `models.Model`
- `_name`: `l10n_ec.sri.payment`
- Fields: `name` (Char, translate), `code` (Char), `active` (Boolean)
- Models SRI payment forms (e.g., 01=credito en cuenta, 02=cheque, 03=efectivo, etc.)
- Used by invoices for e-invoicing (electronic emission)

### `account.journal` (Extended)
Inherits: `account.journal`
Added fields:
- `l10n_ec_require_emission` (Boolean, computed): True if sale journal with documents in Ecuador
- `l10n_ec_entity` (Char, size=3): SRI emission entity number
- `l10n_ec_emission` (Char, size=3): SRI emission point number
- `l10n_ec_emission_address_id` (Many2one res.partner): Emission address for electronic invoicing

Method `_compute_l10n_ec_require_emission()`: Sets true for sale journals in EC using documents.

### `account.move` (Extended)
Inherits: `account.move`
Extended with Ecuadorian document types and SRI-specific fields.

### `res.partner` (Extended)
Inherits: `res.partner`
VAT validation for Ecuadorian RUC.

## Chart of Accounts
Chart of accounts based on Super Intendencia de Companias recommendations. 4-digit account structure covering the full Ecuadorian accounting plan.

## Tax Structure
- **IVA** 12% (general rate, being phased to 15% in some contexts)
- **IVA 0%**: Exempt goods/services
- **ICE**: Impuesto a los Consumos Especiales
- **Retenciones en la fuente**: Withholding tax (IR) at various rates
- **ISD**: Impuesto a la Salida de Divisas
- SRI payment methods for electronic invoicing

## SRI Document Types
~41 purchase document types managed via `l10n_latam.document.type`. Electronic emission supported for sale documents.

## Fiscal Positions
Fiscal positions auto-map taxes:
- IVA responsable vs. IVA consumidor final
- IVA 0% for exports
- Retenciones for different partner types

## Data Files
- `security/ir.model.access.csv`: Access control
- `data/account_tax_report_data.xml`: Tax report structure
- `data/res.bank.csv`: Ecuadorian banks
- `data/l10n_latam_identification_type_data.xml`: RUC, Cedula, Pasaporte identification types
- `data/res_partner_data.xml`: Consumidor Final, SRI, IESS partners
- `data/l10n_latam.document.type.csv`: SRI document types
- `data/l10n_ec.sri.payment.csv`: SRI payment methods
- `views/root_sri_menu.xml`: SRI menu
- `views/account_tax_view.xml`: Tax configuration
- `views/l10n_latam_document_type_view.xml`: Document types
- `views/l10n_ec_sri_payment.xml`: SRI payment view
- `views/account_journal_view.xml`: Journal view with SRI fields
- `views/res_partner_view.xml`: Partner view
- `demo/demo_company.xml`

## Installation
Install with accounting. Chart of accounts and taxes auto-install based on company country = Ecuador.

## Historical Notes
Version 3.9 in Odoo 18. Ecuador uses the SRI electronic invoicing system (comprobantes electronicos). The `l10n_ec_entity` and `l10n_ec_emission` fields on journals map to the SRI authorization numbers. The `l10n_ec_emission_address_id` allows multi-establishment companies to emit from different addresses. The `l10n_ec_stock` module extends stock operations with SRI compliance.
