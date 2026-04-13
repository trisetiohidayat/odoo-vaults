---
Module: l10n_latam_invoice_document
Version: 18.0
Type: l10n/latam-invoice-document
Tags: #odoo18 #l10n #accounting #latam #documents
---

# l10n_latam_invoice_document — LATAM Document Types

## Overview
Provides the LATAM document type taxonomy for fiscal invoice numbering. Introduces `l10n_latam.document.type` — a model defining country-specific document types (invoice, debit note, credit note) with codes, prefixes, and report names. Integrates with `account.journal` (via `l10n_latam_use_documents` flag), `account.move` (document type and number fields), and `account.chart.template` (auto-enables document usage on journals). The framework is extended by each country module (Argentina, Chile, Peru, Uruguay, Ecuador, Brazil) to populate country-specific document type data. Required by [Modules/l10n_ar](Modules/l10n_ar.md), [Modules/l10n_br](Modules/l10n_br.md), [Modules/l10n_cl](Modules/l10n_cl.md), [Modules/l10n_pe](Modules/l10n_pe.md), [Modules/l10n_ec](Modules/l10n_ec.md), [Modules/l10n_uy](Modules/l10n_uy.md).

## Country/Region
Multi-country (LATAM)

## Dependencies
- account
- account_debit_note

## Key Models

### `l10n_latam.document.type`
Inherits: `models.Model`
- `_name`: `l10n_latam.document.type`
- `_order`: `sequence, id`
- `_rec_names_search`: `['name', 'code']`

Fields:
- `active` (Boolean, default=True)
- `sequence` (Integer, default=10): Display order; most common first
- `country_id` (Many2one res.country, required): Country where this document type is valid
- `name` (Char, required, translate): Human-readable name
- `doc_code_prefix` (Char): Prefix for document numbers, e.g., `FA` → `FA 0001-0000001`
- `code` (Char): Localization-specific code (e.g., `1` for Factura in Argentina, `01` for Factura in Peru)
- `report_name` (Char): Name on printed reports (e.g., `FACTURA`, `NOTA DE CREDITO`)
- `internal_type` (Selection): invoice | debit_note | credit_note | all — analog to account.move.move_type with more options for stock picks and other models

Method `_format_document_number()`: Template method. Subclasses (Argentina, Peru, etc.) override to validate/format document numbers against country-specific patterns. Default: no-op.

Method `_compute_display_name()`: Returns `'(code) name'` if code is set.

### `account.journal` (Extended)
Inherits: `account.journal`
Added fields:
- `l10n_latam_use_documents` (Boolean): Enables legal invoicing on this journal; if False, journal is for non-invoice entries (receipts, tax payments, journal entries)
- `l10n_latam_company_use_documents` (Boolean, computed): Links to company `_localization_use_documents()`

Methods:
- `_onchange_company()`: Auto-sets `l10n_latam_use_documents = True` for sale/purchase journals when company uses documents
- `_compute_has_sequence_holes()`: Disables sequence hole detection for document-use journals
- `check_use_document()`: Constraint prevents changing `l10n_latam_use_documents` if the journal has posted invoices
- `_compute_debit_sequence()` / `_compute_refund_sequence()`: Disables debit/refund sequences for document journals

### `account.move` (Extended)
Inherits: `account.move`

**SQL Constraints**: Two unique indexes for name uniqueness:
1. `account_move_unique_name`: `(name, journal_id)` WHERE `state='posted' AND name!='/' AND (l10n_latam_document_type_id IS NULL OR move_type NOT IN in_invoice/in_refund/in_receipt)`
2. `account_move_unique_name_latam`: `(name, commercial_partner_id, l10n_latam_document_type_id, company_id)` WHERE `state='posted' AND name!='/' AND l10n_latam_document_type_id IS NOT NULL AND move_type IN in_invoice/in_refund/in_receipt`

Added fields:
- `l10n_latam_available_document_type_ids` (Many2many l10n_latam.document.type, computed): Documents available for this move based on journal, partner, move type, company country
- `l10n_latam_document_type_id` (Many2one, computed+stored): Selected document type; auto-set from available on draft
- `l10n_latam_document_number` (Char, computed+inverse): Document number extracted from name (strips prefix) or set manually
- `l10n_latam_use_documents` (Boolean, related): From journal
- `l10n_latam_manual_document_number` (Boolean, computed): True if numbering is manual (purchase journals default)
- `l10n_latam_document_type_id_code` (Char, related): Document type code

Methods:
- `_auto_init()`: Creates column with `create_column` to skip computation on existing records during install (performance optimization). Drops old single-column unique index and creates two partitioned indexes.
- `_compute_name()`: For document-use moves without doc type → name=False; for manual docs → name not computed
- `_compute_name_placeholder()`: Sets name placeholder to False for document moves
- `_compute_l10n_latam_manual_document_number()`: `_is_manual_document_number()` returns `True` for purchase journals by default
- `_is_manual_document_number()`: Hook — returns True for purchase journals; country modules override
- `_compute_l10n_latam_document_number()`: Extracts document number after prefix
- `_inverse_l10n_latam_document_number()`: Formats and writes name from document number + prefix
- `_onchange_l10n_latam_document_type_id()`: Clears name on document type change
- `_compute_highest_name()`: Returns empty for manual document numbers
- `_deduce_sequence_number_reset()`: Returns 'never' for document moves (continuous sequence)
- `_skip_format_document_number()`: Hook for country-specific skip logic
- `_get_starting_sequence()`: Returns `"doc_code_prefix 00000000"` for document journals
- `_get_last_sequence_domain()`: Adds `l10n_latam_document_type_id` to sequence gap check
- `_post()`: Raises error if document-type journal is used for receipts
- `_check_l10n_latam_documents()`: Validates posted invoices have document type and number
- `_check_invoice_type_document_type()`: Validates internal_type vs. move_type consistency
- `_get_l10n_latam_documents_domain()`: Returns domain for available document types based on move_type and company country
- `_compute_l10n_latam_available_document_types()`: Searches `l10n_latam.document.type` filtered by country and internal_type
- `_compute_l10n_latam_document_type()`: Auto-selects first available document type for draft moves
- `_compute_made_sequence_gap()`: Disables gap detection for document journals

### `account.move.line` (Extended)
Inherits: `account.move.line`
Views: Document type and number shown in move line list and printed reports.

### `account.chart.template` (Extended)
Inherits: `account.chart.template`
Method `_get_latam_document_account_journal()`: Sets `l10n_latam_use_documents = True` on sale and purchase journals during chart template loading if company uses documents.

### `res.company` (Extended)
Inherits: `res.company`
Method `_localization_use_documents()`: Hook for country modules to return True. Default in this module: False.

## How It Works
1. Journal optionally enables `l10n_latam_use_documents`
2. If enabled, sale/purchase journals auto-get document sequences on template loading
3. When invoice is created, `_compute_l10n_latam_document_type()` auto-selects from available documents
4. Document number combines `doc_code_prefix` + sequential number (or manual entry)
5. Country modules (AR, CL, PE, etc.) extend `_get_l10n_latam_documents_domain()` and override `_format_document_number()` for validation

## Data Files
- `views/account_journal_view.xml`: Use Documents flag on journal form
- `views/account_move_line_view.xml`: Document columns in move line tree
- `views/account_move_view.xml`: Document type/number on move form
- `views/l10n_latam_document_type_view.xml`: Document type list/form
- `views/report_templates.xml`: Report template modifications
- `report/invoice_report_view.xml`: Document type in printed invoice
- `wizards/account_move_reversal_view.xml`: Credit note reversal with document type
- `security/ir.model.access.csv`: ACL for document type model

## Installation
Install before any LATAM country localization module. Document type data is loaded by country modules. The `_auto_init()` optimization is critical for performance on large databases.

## Historical Notes
Document types are a fundamental LATAM accounting concept. In Argentina, AFIP defines specific document types (Factura A/B/C/E, Nota de Credito A/B/C, Nota de Debito A/B/C, etc.) each with different fiscal treatment. In Chile, SII defines Factura Electronica, Guia de Despacho, etc. The unique index design (`commercial_partner_id, l10n_latam_document_type_id`) is key: multiple invoices of different document types can share the same number for the same partner, which is common in LATAM. The `_auto_init()` performance optimization was added in Odoo 17 when the module was refactored — without it, computing the document type field on all existing moves during install could cause memory errors on large databases.
