# Turkiye - Nilvera E-Invoice (`l10n_tr_nilvera_einvoice`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Turkiye - Nilvera E-Invoice |
| **Technical** | `l10n_tr_nilvera_einvoice` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Auto-install** | `l10n_tr_nilvera` |

## Description
Sends and receives electronic invoices to/from the Nilvera portal using the Turkish UBL-TR 1.2 format. Supports both e-invoice (e-fatura) for registered businesses and e-archive (e-arşiv) for non-registered recipients. Handles the full lifecycle: submission, status tracking, PDF retrieval, and incoming document import.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_tr_nilvera` | Core Turkish localization |
| `account_edi_ubl_cii` | UBL/CII EDI framework |

## Technical Notes
- Country code: `tr`
- Format: UBL-TR 1.2 (UBL 2.1 Turkish profile)
- API: Nilvera REST API
- Customization ID: `TR1.2`
- Profiles: `TEMELFATURA` (e-invoice) and `EARSIVFATURA` (e-archive)
- Module has Python model files with full EDI submission logic

## Models

### `account.edi.xml.ubl.tr` (Abstract, inherits `account.edi.xml.ubl_21`)
UBL-TR 1.2 document builder. Customizes the standard UBL 2.1 export for Turkish Nilvera requirements.

**Key XML customizations:**
- Removes `<BuyerReference>` tag (Nilvera rejects it)
- Strips `<InvoiceLine/Item/ClassifiedTaxCategory>` nodes (not allowed in Turkey)
- Removes invoice line period nodes (start/end dates not allowed)
- Forces 2 decimal places (`currency_dp = 2`) on all monetary amounts
- Withholding tax category code: `9015`; standard: `0015`

**Key methods:**
- `_export_invoice_filename()` — Returns `'{name}_einvoice.xml'`
- `_add_invoice_header_nodes()` — Sets `CustomizationID=TR1.2`, `ProfileID=TEMELFATURA|EARSIVFATURA`, Turkish invoice number format `ABC2009123456789`
- `_l10n_tr_get_amount_integer_partn_text_note()` — Converts amount to Turkish text ("YALNIZ : ... TL") using `num2words`
- `_get_party_node()` — VKN/TCKN identification for companies/individuals, zero-width space for missing family name
- `_get_party_identification_node_list()` — Uses `VKN` scheme for companies, `TCKN` for individuals
- `_get_tax_category_node()` — KDV Tevkifatı for withholding, Gercek Usulde KDV otherwise
- `_add_invoice_monetary_total_nodes()` — Forces `AllowanceTotalAmount` even when zero; removes `<PrepaidAmount>`
- `_import_fill_invoice_form()` — Reads Nilvera UUID on import

### `account.move` (Extended)
Fields for Nilvera tracking:

| Field | Type | Description |
|-------|------|-------------|
| `l10n_tr_nilvera_uuid` | Char | Universally unique identifier from Nilvera |
| `l10n_tr_nilvera_send_status` | Selection | `not_sent`, `sent`, `succeed`, `waiting`, `error`, `unknown` |

**Key methods:**
- `_post()` — Generates UUID on first post for Turkish moves without one
- `button_draft()` — Blocks reset to draft for sent Nilvera documents (error state shows message only)
- `_l10n_tr_nilvera_submit_einvoice(xml_file, customer_alias)` — Submit to `/einvoice/Send/Xml`
- `_l10n_tr_nilvera_submit_earchive(xml_file)` — Submit to `/earchive/Send/Xml`
- `_l10n_tr_nilvera_submit_document()` — Core POST via Nilvera client; handles 401/403 auth errors, 4xx client errors, 500 server errors; auto-posts missing series/sequence
- `_l10n_tr_nilvera_get_submitted_document_status()` — Poll Nilvera for status of sent invoices
- `_l10n_tr_nilvera_get_documents()` — Paginated fetch of incoming documents from Nilvera (cron-triggered)
- `_l10n_tr_nilvera_get_invoice_from_uuid()` — Download and parse incoming XML, create `account.move`
- `_l10n_tr_nilvera_add_pdf_to_invoice()` — Attach Nilvera-generated PDF as main attachment
- `l10n_tr_nilvera_get_pdf()` — Fetch Nilvera PDF for successful sales
- `_l10n_tr_nilvera_einvoice_check_negative_lines()` — Returns True if any line has negative qty or price (Nilvera rejects these)
- `_l10n_tr_nilvera_einvoice_check_invalid_subscription_dates()` — Validates deferred date consistency

**Cron jobs:**
- `_cron_nilvera_get_new_einvoice_purchase_documents()` — Fetch incoming purchase e-invoices
- `_cron_nilvera_get_new_einvoice_sale_documents()` — Fetch incoming sale e-invoices
- `_cron_nilvera_get_new_earchive_sale_documents()` — Fetch incoming e-archive sales
- `_cron_nilvera_get_invoice_status()` — Poll status for sent/waiting invoices
- `_cron_nilvera_get_sale_pdf()` — Batch-fetch Nilvera PDFs for successful sales

### `account.journal` (Extended)
Buttons and computed visibility for Nilvera:

- `_compute_show_fetch_in_einvoices_button()` — Shows button when `is_nilvera_journal` + API key + purchase type
- `_compute_show_refresh_out_einvoices_status_button()` — Shows button when API key + sale type
- `button_fetch_in_einvoices()` — Trigger purchase e-invoice fetch
- `button_refresh_out_einvoices_status()` — Trigger status refresh for sale invoices

## Data Files
- `data/cron.xml` — Scheduled actions for Nilvera sync
- `data/res_partner_category_data.xml` — Official Turkish tax category tags
- `views/account_move_views.xml` — Nilvera status field and buttons

## Related
- [Modules/l10n_tr_nilvera](modules/l10n_tr_nilvera.md) — Core Turkish localization
- [Modules/l10n_tr_nilvera_edispatch](modules/l10n_tr_nilvera_edispatch.md) — e-Despatch (e-İrsaliye) via Nilvera
