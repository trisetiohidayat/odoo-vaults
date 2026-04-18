---
Module: l10n_ar
Version: 18.0
Type: l10n/argentina
Tags: #odoo18 #l10n #accounting #argentina
---

# l10n_ar — Argentina Accounting

## Overview
The primary Argentine localization module. Adds the complete AFIP (Administracion Federal de Ingresos Publicos) accounting configuration: chart of accounts per AFIP responsibility type, VAT tax groups with AFIP codes, AFIP responsibility types, document types (facturas, notas de credito/debito), identification types (CUIT, CUIL, DNI), fiscal positions, and AFIP concept selection for electronic invoicing. Requires [Modules/l10n_latam_base](Modules/l10n_latam_base.md) and [Modules/l10n_latam_invoice_document](Modules/l10n_latam_invoice_document.md).

## Country/Region
Argentina (country code: AR)

## Dependencies
- account
- l10n_latam_invoice_document
- l10n_latam_base

## Key Models

### `l10n_ar.afip.responsibility.type`
Inherits: `models.Model`
- `_name`: `l10n_ar.afip.responsibility.type`
- Fields: `name` (Char), `sequence` (Integer), `code` (Char), `active` (Boolean)
- Unique constraints on `name` and `code`
- Stores AFIP responsibility classifications: Responsable Inscripto, Exento, Monotributo, Cons. Final, Exterior, etc.
- Used by `res.partner.l10n_ar_afip_responsibility_type_id` and `account.move.l10n_ar_afip_responsibility_type_id`

### `res.partner` (Extended)
Inherits: `res.partner`
Added fields:
- `l10n_ar_vat` (Char, computed): Returns the CUIT/VAT from identification number if the type's AFIP code is 80
- `l10n_ar_formatted_vat` (Char, computed): Formats CUIT as `XX-XXXXXXXX-X`
- `l10n_ar_gross_income_number` (Char): IIBB (Gross Income) number
- `l10n_ar_gross_income_type` (Selection): multilateral, local, exempt
- `l10n_ar_afip_responsibility_type_id` (Many2one): Links to AFIP responsibility type

Methods:
- `ensure_vat()`: Raises `UserError` if no CUIT configured
- `l10n_ar_identification_validation()`: Validates CUIT/CUIL/DNI using `stdnum.ar`
- `_get_id_number_sanitize()`: Strips separators from VAT number, returns integer

### `account.move` (Extended)
Inherits: `account.move`
Added fields:
- `l10n_ar_afip_responsibility_type_id` (Many2one): Frozen at posting time
- `l10n_ar_afip_concept` (Selection): 1=Products, 2=Services, 3=Products+Services, 4=Export
- `l10n_ar_afip_service_start` (Date): Service period start
- `l10n_ar_afip_service_end` (Date): Service period end

Key methods:
- `_get_concept()`: Determines AFIP concept from product types on invoice lines (products vs. services vs. mixed; expo invoice special case for Zona Franca)
- `_l10n_ar_get_amounts()`: Aggregates amounts for electronic invoice and digital VAT books — returns vat_amount, vat_taxable_amount, vat_exempt_base_amount, vat_untaxed_base_amount, not_vat_taxes_amount, iibb_perc_amount, mun_perc_amount, intern_tax_amount, other_taxes_amount, profits_perc_amount, vat_perc_amount
- `_get_vat()`: Returns VAT lines for WSFE web service
- `_get_l10n_latam_documents_domain()`: Filters document types by journal letter (A/B/C/E) and AFIP codes
- `_check_argentinean_invoice_taxes()`: Validates exactly one VAT tax per line; enforces zero/non-zero VAT based on document type purchase aliquots
- `_set_afip_responsibility()`: Called on `_post()` to snapshot partner's AFIP responsibility at invoice time
- `_set_afip_service_dates()`: Auto-sets service period dates on service invoices
- `_onchange_afip_responsibility()`: Warning if partner has no AFIP responsibility configured
- `_onchange_partner_journal()`: Auto-switches between domestic and export (FEERCEL/FEEWS) journals based on partner type
- `_check_invoice_type_document_type()`: Allows internal-type documents (code 99) to be used as refunds
- `_check_moves_use_documents()`: Prevents non-invoice entries in journals using documents

### Chart of Account Templates
Three separate templates loaded based on company's AFIP responsibility type:
- `template_ar_ri`: Responsable Inscripto (full VAT regime)
- `template_ar_ex`: Exento (exempt from VAT)
- `template_ar_base`: Monotributo (simplified regime)

No journals are auto-generated; user configures sale journals manually.

### `l10n_latam.document.type` (Extended via Data)
Documents defined in CSV/XML: Factura A/B/C/E (export), Nota de Debito A/B/C, Nota de Credito A/B/C, Recibo, Liquidacion A/B, etc. Each linked to AFIP letter (A/B/C/E) and purchase_aliquots flag.

## Data Files
- `data/l10n_latam_identification_type_data.xml`: DNI, CUIT, CUIL, passport, foreign ID
- `data/l10n_ar_afip_responsibility_type_data.xml`: All AFIP responsibility types with codes
- `data/account_chart_template_data2.xml`: Three chart templates (RI, Exento, Monotributo)
- `data/uom_uom_data.xml`: AFIP-specific UoM codes
- `data/l10n_latam.document.type.csv`: Document types
- `data/res_partner_data.xml`: consumidor_final, AFIP partners
- `data/res.currency.csv`: ARS currency

## Chart of Accounts
Three separate chart templates, each tied to an AFIP responsibility type. Accounts cover the full PCGE (Plan de Cuentas General Electronico) structure with 8-digit codes: 1-Assets, 2-Liabilities, 3-Equity, 4-Revenue, 5-Costs, 6-Expenses.

## Tax Structure
VAT aliquots: 0%, 2.5%, 5%, 10.5%, 21%, 27%. Tax groups include:
- IVA Responsable Inscripto
- IVA Sujeto Exento
- IVA No Responsable
- IVA Zero
- Percepcion IIBB (gross income)
- percepciones Municipalidad
- Impuestos Internos
- Otras Tasas

Each tax group carries `l10n_ar_vat_afip_code` (for VAT) or `l10n_ar_tribute_afip_code` (for other taxes).

## Fiscal Positions
Fiscal positions map taxes for different AFIP responsibility types — e.g., responsible inscripto selling to final consumer (exempt), export operations (no VAT), and intercompany transfers.

## EDI/Fiscal Reporting
No EDI module in core (l10n_ar_edi is community). Supports:
- AFIP concept codes for WSFE/WSFEX web services
- Digital VAT books (txt format)
- Invoice letter system (A for IVA responsable, B for consumer, C for exempt, E for export)
- ARCA (formerly AFIP) VAT reporting per RG 5614/2024

## Installation
Install with accounting module. On first run, configure the company's AFIP Responsibility Type. The chart of accounts must be manually installed based on that responsibility. Sale journals must be manually configured with AFIP POS system.

## Historical Notes
Version 3.7 in Odoo 18. Key Odoo 17→18 changes: document type codes updated to current AFIP requirements; new ARCA VAT reporting support (RG 5614/2024); consumer-type C invoice handling improved; CBU account type added with validation; service date period auto-calculation added for concept 2/3/4 invoices. The POS module (`l10n_ar_pos`) was separated from core.
