---
Module: l10n_tr_nilvera_einvoice
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #turkey #nilvera #einvoice
---

# l10n_tr_nilvera_einvoice

## Overview
Sends and receives Turkish e-invoices via the Nilvera portal API. Produces UBL 1.2/TR XML conforming to Nilvera's requirements and integrates with Odoo's `account.move.send` framework for submission, status tracking, and incoming invoice processing. Depends on `l10n_tr_nilvera` and `account_edi_ubl_cii`.

## EDI Format / Standard
UBL 1.2/TR ("TR1.2") with Turkish e-invoice profile. Two sub-profiles: `TEMELFATURA` (e-invoice capable partner) and `EARSIVFATURA` (e-archive only). Nilvera REST API with JSON responses.

## Dependencies
- `l10n_tr_nilvera` -- API credentials and partner status
- `account_edi_ubl_cii` -- UBL XML generation framework

## Key Models

### `account.edi.xml.ubl.tr` (`l10n_tr_nilvera_einvoice.account_edi_xml_ubl_tr`)
Abstract model inheriting `account.edi.xml.ubl_21`. The core UBL TR XML builder.

Key export overrides:
- `_export_invoice_filename()` -- Returns `{name}_einvoice.xml`
- `_export_invoice_vals()` -- Sets `customization_id = 'TR1.2'`, `profile_id`, `uuid`, `line_count_numeric`, `document_type_code` (`SATIS|IADE`), adds amount-in-words note, exchange rate note
- `_l10n_tr_get_amount_integer_partn_text_note()` -- Converts amount to Turkish words (using `num2words`) for the verbal amount note
- `_get_partner_party_identification_vals_list()` -- Appends VKN/TCKN identification; strips invalid IDs
- `_get_partner_party_tax_scheme_vals_list()` -- Cleans TaxScheme to only Tax Office name
- `_get_partner_party_legal_entity_vals_list()` / `_get_partner_person_vals()` -- Handles individual TCKN structure
- `_get_tax_category_list()` -- Sets `9015` for withholding, `0015` for standard KDV; Turkish tax scheme names
- `_get_invoice_tax_totals_vals_list()` / `_get_invoice_monetary_total_vals()` -- Handles prepaid amounts, allowance rounding
- `_get_delivery_vals_list()` -- Adds picking reference if `stock_picking` link exists
- `_get_invoice_line_price_vals()` / `_get_invoice_line_vals()` -- Adds `base_quantity_attrs` with UoM code

Import:
- `_import_retrieve_partner_vals()` -- Extracts VAT from party identification
- `_import_fill_invoice_form()` -- Imports Nilvera UUID to `l10n_tr_nilvera_uuid`

### `account.move` (`l10n_tr_nilvera_einvoice.account_move`)
Extends: `account.move`

- `l10n_tr_nilvera_uuid` -- Char; stores the Nilvera-assigned UUID on incoming invoices

### `account.move.send` (`l10n_tr_nilvera_einvoice.account_move_send`)
Extends: `account.move.send`

Implements `l10n_tr_nilvera` as an EDI sender. Uses the Nilvera REST API client from `l10n_tr_nilvera.lib.nilvera_client`.

### `account.journal` (`l10n_tr_nilvera_einvoice.account_journal`)
Extends: `account.journal`

- `l10n_tr_nilvera_alias_id` -- Journal-level alias selection for purchase journals

### `res.partner.category` (`l10n_tr_nilvera_einvoice.res_partner_category`)
Extends: `res.partner.category`

- `_get_l10n_tr_official_categories()` -- Returns official sector categories used in e-invoice party identification

## Data Files
- `data/cron.xml` -- Cron for polling incoming invoices
- `data/ubl_tr_templates.xml` -- UBL template overrides
- `data/res_partner_category_data.xml` -- Official sector categories
- `views/account_journal_dashboard_views.xml`, `views/account_move_views.xml` -- UI
- `security/ir.model.access.csv` -- ACL

## How It Works
1. Invoice is posted and sent via `account.move.send`
2. `_export_invoice_vals()` builds the UBL TR XML vals dictionary
3. The Nilvera API is called: partner status determines `TEMELFATURA` vs `EARSIVFATURA` profile
4. Nilvera returns a UUID; stored in `l10n_tr_nilvera_uuid`
5. A cron job polls for incoming invoices (vendor invoices sent to the company via Nilvera)
6. Incoming XML is imported via `_import_fill_invoice_form()` with UUID tracking
7. Status is tracked via `l10n_it_edi_state`-style states

## Installation
Auto-installs with `l10n_tr_nilvera`. Requires Nilvera API key on the company and partner scanning. Configure purchase journal alias for receiving vendor invoices.

## Historical Notes
Nilvera e-invoice for Turkey was introduced in Odoo 18 as a replacement/alternative to the earlier Turkish e-invoice modules. The `UBL TR 1.2` profile is stricter than the generic UBL 2.1: it removes `buyer_reference`, strips unnecessary nodes from tax schemes, and uses specific tax type codes (`9015` for withholding/KDV tevkifatı). The amount-in-words note (`_l10n_tr_get_amount_integer_partn_text_note`) is a legal requirement in Turkey.
