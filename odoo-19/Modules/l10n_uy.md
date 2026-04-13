---
type: module
module: l10n_uy
tags: [odoo, odoo19, l10n, localization]
created: 2026-04-06
---

# Uruguay Localization (`l10n_uy`)

## Overview
- **Name:** Uruguay - Accounting
- **Country:** Uruguay (UY)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 0.1
- **Author:** Uruguay l10n Team, Guillem Barba, ADHOC
- **License:** LGPL-3
- **Dependencies:** `account`, `l10n_latam_invoice_document`, `l10n_latam_base`
- **Auto-installs:** `account`
- **Countries:** `uy`

## Description

General Chart of Accounts for Uruguay.

This module adds accounting functionalities for the Uruguayan localization, representing the minimum required configuration for a company to operate in Uruguay under the regulations and guidelines provided by the DGI (Direccion General Impositiva).

## Features

- Uruguayan Generic Chart of Account
- Pre-configured VAT (IVA) Taxes and Tax Groups
- Legal document types in Uruguay
- Valid contact identification types in Uruguay
- Configuration and activation of Uruguayan Currencies (UYU, UYI - Unidad Indexada Uruguaya)
- Frequently used default contacts: DGI, Consumidor Final Uruguayo

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](Account.md) | Core accounting module |
| [Modules/l10n_latam_invoice_document](l10n_latam_invoice_document.md) | LATAM document types support |
| [Modules/l10n_latam_base](l10n_latam_base.md) | Latin America base localization |

## Key Models

### account.tax (Inherit)
Extends `account.tax`:
- **l10n_uy_tax_category:** Selection field with value `vat` — used to group transactions in Financial Reports required by DGI

### account.move (Inherit)
Extends `account.move` with DGI document support:

- **_get_starting_sequence():** Creates sequence using document type code prefix and journal document number with 8-digit padding (format: `{prefix} A{7-digit}`)
- **_l10n_uy_get_formatted_sequence():** Returns `{doc_code_prefix} A{7-digit-number}` format
- **_get_last_sequence_domain():** Adds `l10n_latam_document_type_id` to sequence tracking for Uruguayan companies using documents
- **_get_l10n_latam_documents_domain():** Restricts document types based on the subtype of the original move (for reversals/debit notes)

### l10n_latam.document.type (Inherit)
Extends `l10n_latam.document.type`:
- **_format_document_number():** Validates and formats Uruguayan document numbers — max 2 letters for the first part, max 7 digits for the second (e.g., `XX0000001`, `A0000001`)

### l10n_latam.identification.type (Inherit)
Extends `l10n_latam.identification.type`:
- **l10n_uy_dgi_code:** Char field storing the DGI code for Uruguayan identification types

### res.company (Inherit)
Extends `res.company` with Uruguayan-specific configuration.

### res.partner (Inherit)
Extends `res.partner` with Uruguayan-specific configuration.

## Uruguayan Document Subtypes

Documents are classified by the module into subtypes for proper credit note/debit note suggestion:

| Subtype | Document Codes | Description |
|---------|---------------|-------------|
| Non-electronic | `0` | Paper-based documents |
| E-Ticket | `101, 102, 103, 201, 202, 203` | Electronic tickets |
| E-Invoice | `111, 112, 113, 211, 212, 213` | Electronic invoices |
| E-Inv-Expo | `121, 122, 123, 221, 222, 223` | Export electronic invoices |
| E-Boleta | `151, 152, 153, 251, 252, 253` | Electronic receipts (not yet implemented) |

When a document is reversed or debited, the system restricts credit/debit notes to the same document subtype.

## Uruguayan Tax Structure

### IVA (Impuesto al Valor Agregado)
- **Minimum rate:** 10%
- **Basic rate:** 22%
- **Maximum rate:** 22% (with some exceptions)
- Uruguay uses a dual IVA rate system

### IMEBA (Impuesto a la Enajenacion de Bienes Agropecuarios)
- Tax on the transfer of agricultural goods

### IRPF (Impuesto a la Renta de las Personas Fisicas)
- Personal income tax applicable to individuals

## Currencies

- **UYU** - Uruguayan Peso
- **UYI** - Unidad Indexada Uruguaya (Indexed Unit) - used for inflation-adjusted transactions

## Data Files
- `data/account_tax_report_data.xml` - Uruguayan tax report configuration
- `data/l10n_latam.document.type.csv` - Document types
- `data/l10n_latam_identification_type_data.xml` - Identification types with DGI codes
- `data/res_partner_data.xml` - Default contacts (DGI, Consumidor Final)
- `data/res_currency_data.xml` - UYU and UYI currency data
- `views/account_tax_views.xml` - Tax view overrides

## Demo Data
- Demo company "UY Company" with pre-installed chart of accounts, taxes, document types, and identification types
- Demo contacts: IEB Internacional, Consumidor Final Anonimo Uruguayo

## Related Modules
- [Modules/l10n_uy](l10n_uy.md) - Core accounting (this module)
- [Modules/l10n_uy_pos](l10n_uy_pos.md) - Uruguayan POS integration
- [Modules/account](Account.md) - Core accounting
- [Modules/l10n_latam_base](l10n_latam_base.md) - Latin America base localization
- [Modules/l10n_latam_invoice_document](l10n_latam_invoice_document.md) - LATAM document types
- [Modules/l10n_latam_check](l10n_latam_check.md) - LATAM check handling
