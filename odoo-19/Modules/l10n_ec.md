---
type: module
module: l10n_ec
tags: [odoo, odoo19, l10n, localization]
created: 2026-04-06
---

# Ecuador Accounting Localization (`l10n_ec`)

## Overview
- **Name:** Ecuadorian Accounting
- **Country:** Ecuador (EC)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 3.9
- **Author:** TRESCLOUD
- **License:** LGPL-3
- **Dependencies:** `base`, `base_iban`, `account_debit_note`, `l10n_latam_invoice_document`, `l10n_latam_base`, `account`
- **Auto-installs:** `account`
- **Countries:** `ec`

## Description

This module adds accounting features for Ecuadorian localization, representing the minimum requirements to operate a business in Ecuador in compliance with local regulations from the SRI (Servicio de Rentas Internas) and the Superintendency of Companies (Super Intendencia de Companias).

## Configuration
1. Go to your company and configure your country as Ecuador
2. Install the invoicing or accounting module - everything will be handled automatically

## Features
- Ecuadorian chart of accounts (based on Super Intendencia de Companias recommendation)
- Pre-configured taxes including withholdings (IVA, Retenciones)
- Fiscal positions for automatic tax application
- ~41 purchase document types
- Ecuadorian identification types
- Ecuadorian banks
- Default partners: Consumidor Final, SRI, IESS
- VAT validation for RUC and DNI

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](modules/account.md) | Core accounting module |
| [Modules/l10n_latam_invoice_document](modules/l10n_latam_invoice_document.md) | LATAM document types support |
| [Modules/l10n_latam_base](modules/l10n_latam_base.md) | Latin America base localization |
| `account_debit_note` | Debit note support |
| `base_iban` | IBAN bank account support |

## Key Models

### account.move (Inherit)
Extends `account.move` with SRI document support:

- **l10n_ec_sri_payment_id:** Many2one to `l10n_ec.sri.payment` - SRI payment method for the invoice
- **_get_l10n_ec_documents_allowed():** Returns allowed documents based on partner identification type code
- **_get_l10n_latam_documents_domain():** Filters documents by partner type and country (credit/debit notes, invoices)
- **_get_ec_formatted_sequence():** Format: `{doc_prefix} {entity}-{emission}-{9-digit-sequence}`
- **_get_starting_sequence():** Creates sequence using SRI entity/emission/sequence format
- **_get_last_sequence_domain():** Tracks sequence per document type and internal type (not just journal)
- **_skip_format_document_number():** Allows free-format for vendor credit notes from foreign partners

### res.partner (Inherit)
Extends `res.partner` with Ecuadorian VAT validation:

- **l10n_ec_vat_validation:** Computed field showing VAT validation error messages
- **_run_check_identification():** Validates DNI (10 digits) for Ecuadorian partners
- **_compute_l10n_ec_vat_validation():** Uses stdnum library to validate RUC and CI (Cedula de Identidad) using SRI algorithm
- **_l10n_ec_get_identification_type():** Maps Odoo identification types to Ecuadorian codes (cedula, ruc, passport, foreign)

### l10n_latam.document.type (Inherit)
Extends `l10n_latam.document.type`:

- Adds `purchase_liquidation` and `withhold` to internal_type selection
- **l10n_ec_check_format:** Boolean to enable Ecuadorian document number format validation
- **_format_document_number():** Validates format `001-001-123456789` (3-3-9 digits)

### l10n_ec.sri.payment (Standalone)
Custom model for SRI payment methods:

- **sequence:** Display order
- **name:** Payment method name (translated)
- **code:** SRI payment method code
- **active:** Active state

### account.journal (Inherit)
Extends `account.journal` with SRI emission fields:

- **l10n_ec_entity:** 3-digit emission entity number from SRI
- **l10n_ec_emission:** 3-digit emission point number from SRI
- **l10n_ec_emission_address_id:** Address for electronic invoicing
- **l10n_ec_require_emission:** Computed - true for sale journals with documents enabled

### account.tax (Inherit)
Extends `account.tax` with SRI-specific codes:

- **l10n_ec_code_base:** Tax declaration code for base amount
- **l10n_ec_code_applied:** Tax declaration code for resulting amount
- **l10n_ec_code_ats:** ATS table 5 code for tax credit/cost/expense classification

## SRI Document Type Mapping

Documents are mapped to partner identification codes (ATS Table 2):

| Partner Code | Description | Document Types |
|-------------|-------------|----------------|
| `01` | RUC (in) | 01, 02, 04, 05, 08, 09, 11, 12, 16, 20, 21, 41, 42, 43, 45, 47, 48 |
| `02` | Cedula (in) | 03, 04, 05, 09, 19, 41, 294, 344 |
| `03` | Pasaporte (in) | 03, 04, 05, 09, 15, 19, 41, 45, 294, 344 |
| `04` | RUC (out) | 01, 04, 05, 41, 44, 47, 48, 49, 50, 51, 52, 370-373 |
| `05` | Cedula (out) | 01, 04, 05, 41, 44, 47, 48, 370-373 |
| `06` | Pasaporte (out) | 01, 04, 05, 41, 44, 47, 48, 370-373 |
| `07` | Final Consumer | 01, 04, 05 |
| `08` | Foreign | 01, 04, 05, 15, 16, 41, 47, 48 |
| `09` | Consumption liquidation | Various |
| `20/21` | Special | Various |

## Partner Identification Types (ATS)

| Code | Type | Description |
|------|------|-------------|
| `01` | RUC | Registro Unico de Contribuyentes (in-country) |
| `02` | Cedula | Cedula de Identidad (in-country) |
| `03` | Pasaporte | Passport (in-country, foreigners) |
| `04` | RUC | RUC (foreign) |
| `05` | Cedula | Cedula (foreign) |
| `06` | Pasaporte | Pasaporte (foreign) |
| `07` | Final Consumer | 9999999999999 |
| `08` | Foreign ID | Other foreign identification |

## Ecuadorian Tax Structure

### IVA (Impuesto al Valor Agregado)
- **Standard rates:** 0%, 12%, 15%
- 15% is the highest rate, 12% common, 0% for exempt goods
- SRI requires detailed reporting of VAT amounts by rate

### ICE (Impuesto a los Consumos Especiales)
- Excise tax on specific luxury goods (beverages, tobacco, vehicles, etc.)
- Specific rates by product category

### IR (Impuesto a la Renta)
- Corporate income tax
- Progressive rates for individuals

### Withholdings (Retenciones)
- Renta withholding on payments to suppliers
- IVA withholding for VAT registered taxpayers
- ISD (Impuesto a la Salida de Divisas) - tax on foreign currency payments

## Data Files
- `data/account_tax_report_data.xml` - SRI tax report configuration
- `data/res.bank.csv` - Ecuadorian bank data
- `data/l10n_latam_identification_type_data.xml` - Identification types
- `data/res_partner_data.xml` - Default contacts
- `data/l10n_latam.document.type.csv` - Document types (~20+ types)
- `data/l10n_ec.sri.payment.csv` - SRI payment methods
- Views for tax, document type, partner, journal, SRI payment

## Related Modules
- [Modules/l10n_ec](modules/l10n_ec.md) - Core accounting (this module)
- [Modules/l10n_ec_sale](modules/l10n_ec_sale.md) - Ecuador sale extensions
- [Modules/l10n_ec_stock](modules/l10n_ec_stock.md) - Ecuador stock extensions
- [Modules/account](modules/account.md) - Core accounting
- [Modules/l10n_latam_base](modules/l10n_latam_base.md) - Latin America base localization
- [Modules/l10n_latam_invoice_document](modules/l10n_latam_invoice_document.md) - LATAM document types
