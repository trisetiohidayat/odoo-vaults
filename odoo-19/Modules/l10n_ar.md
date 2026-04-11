# l10n_ar - Argentina Accounting

## Overview
- **Name:** Argentina - Accounting
- **Country:** Argentina (AR)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 3.7
- **Author:** ADHOC SA
- **License:** LGPL-3
- **Dependencies:** `l10n_latam_invoice_document`, `l10n_latam_base`, `account`
- **Auto-installs:** `account`

## Description
Full Argentine localization for ARCA (Administracion Federal de Ingresos Publicos) compliance. Supports three company responsibility types:
- **Responsable Inscripto (RI)** — Full VAT taxpayer
- **Exento** — VAT exempt
- **Monotributo** — Simplified regime

## Models

### l10n_ar.afip.responsibility.type (Standalone)
New standalone model:
- **name:** Responsibility type name (indexed)
- **sequence:** Display order
- **code:** Internal code (1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16)
- **active:** Boolean

### account.chart.template (AbstractModel)
Inherits `account.chart.template`:
- **Responsibility-to-template matching:** `ar_base` -> Monotributo, `ar_ex` -> Exento, `ar_ri` -> Responsable Inscripto
- **_load():** On CoA install: sets ARCA responsibility, country, `round_globally` tax rounding; sets CUIT identification type on company partner
- **try_loading():** Auto-selects template based on company's pre-configured ARCA responsibility

### account.fiscal.position (Inherit)
Extends `account.fiscal.position`:
- **l10n_ar_afip_responsibility_type_ids:** Many2many to responsibility types — auto-detects FP based on partner's ARCA responsibility
- **_get_fpos_validation_functions():** Adds ARCA responsibility matching to fiscal position detection

### account.journal (Inherit)
Extends `account.journal`:
- **l10n_ar_afip_pos_system:** ARCA POS system type — `II_IM` (Pre-printed), `RLI_RLM` (Online), `BFERCEL` (Electronic Fiscal Bond), `FEERCEL/FEERCELP` (Export), `CPERCEL` (Product Coding), `CF` (External Fiscal Controller)
- **l10n_ar_afip_pos_number:** 5-digit POS number assigned by ARCA
- **l10n_ar_afip_pos_partner_id:** Address used in invoice reports for this POS
- **l10n_ar_is_pos:** Computed — True if sale journal with documents in AR company
- **_get_journal_letter():** Returns allowed document letters (A, B, C, E, M, I) per ARCA rules
- **_get_journal_codes_domain():** Returns domain for allowed document codes per POS system
- **_get_codes_per_journal_type():** Maps POS system to document code lists
- **_onchange_set_short_name():** Auto-sets journal code from POS number
- **_check_afip_pos_system/pos_number():** Constraints on POS configuration
- **write():** Protects key fields from changes after validated invoices exist

### l10n_latam.document.type (Inherit)
Extends `l10n_latam.document.type`:
- **l10n_ar_letter:** Document letter (A, B, C, E, M, T, R, X, I)
- **purchase_aliquots:** 'not_zero' or 'zero' — enforces VAT presence on vendor bills
- **_get_l10n_ar_letters():** Returns available letter selection
- **_format_document_number():** Validates invoice numbers (`POS-number`) and Import Dispatch Numbers (16-digit)

### account.move (Inherit)
Extends `account.move` with extensive ARCA support:
- **l10n_ar_afip_responsibility_type_id:** ARCA responsibility of the counterparty (captured at posting)
- **l10n_ar_afip_concept:** Invoice concept type — `1` Products, `2` Services, `3` Products+Services, `4` Other (export)
- **l10n_ar_afip_service_start / _end:** Service period dates for concept 2/3
- **_compute_l10n_ar_afip_concept():** Auto-suggests based on product types
- **_get_concept():** Determines concept from invoice lines
- **_check_argentinean_invoice_taxes():** Enforces single VAT per line, correct aliquots
- **_set_afip_service_dates():** Auto-fills service period on posting
- **_set_afip_responsibility():** Captures partner responsibility at posting time
- **_onchange_partner_journal():** Switches between domestic and export journals
- **_get_l10n_latam_documents_domain():** Filters document types by journal letter and POS codes
- **_get_l10n_ar_get_document_number_parts():** Parses `POS-number` format
- **_get_formatted_sequence():** Format: `DOC_CODE_PREFIX POS-NUMBER-SEQUENCE`
- **_get_l10n_ar_get_amounts():** Computes VAT amounts, taxable amounts, IIBB, mun perc, internal taxes, profits tax for EDI/reports
- **_get_vat():** Returns VAT breakdown by AFIP code for wsfe web service
- **_l10n_ar_include_vat():** True for letters B, C, X, R
- **_l10n_ar_get_invoice_totals_for_report():** Adjusts tax totals for letter-C invoices (no VAT detail)
- **_get_name_invoice_report():** Returns `l10n_ar.report_invoice_document` for AR companies
- **_check_moves_use_documents():** Prevents non-invoice entries in document journals
- **_post():** Runs validations, sets responsibility and service dates

### res.partner (Inherit)
Extends `res.partner`:
- **l10n_ar_vat:** Computed — extracts CUIT from VAT field
- **l10n_ar_formatted_vat:** Computed — formats CUIT as `XX-XXXXXXXX-X`
- **l10n_ar_gross_income_number / _type:** IIBB (Ingresos Brutos) number and type (multilateral, local, exempt)
- **l10n_ar_afip_responsibility_type_id:** ARCA responsibility type
- **_compute_l10n_ar_formatted_vat():** Uses stdnum.ar.cuit.format
- **_l10n_ar_identification_validation():** Validates CUIT/CUIL/DNI using stdnum.ar
- **_run_check_identification():** Overridden to handle CUIT/CUIL/DNI
- **_get_id_number_sanitize():** Returns sanitized RUT/RUC digits
- **ensure_vat():** Helper — returns VAT or raises error

### account.move.line (Inherit)
Adds ARCA-specific fields to move lines (no custom model file, defined in data).

## Data Files
Extensive data including:
- `data/l10n_latam_identification_type_data.xml` — Identification types (CUIT, CUIL, DNI, etc.)
- `data/l10n_ar_afip_responsibility_type_data.xml` — ARCA responsibility types
- `data/l10n_latam.document.type.csv/.xml` — Document types (facturas, notas de credito/debito, etc.)
- `data/res_partner_data.xml` — Default partners (Consumidor Final, ARCA)
- `data/res.currency.csv` — ARS and reference currencies
- `data/res.country.csv` — AR-specific country codes
- Multiple demo companies and demo invoices per responsibility type

## Related Modules
- **l10n_ar_pos** — Argentine POS
- **l10n_ar_stock** — Argentine stock/WMS
- **l10n_ar_website_sale** — Argentine e-commerce
- **l10n_ar_withholding** — Argentine withholding taxes
