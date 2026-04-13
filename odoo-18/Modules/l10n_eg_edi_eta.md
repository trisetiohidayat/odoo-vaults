---
Module: l10n_eg_edi_eta
Version: 0.2
Type: l10n/egypt #edi
Tags: #odoo18 #l10n #accounting #egypt #edi #e-invoice
---

# l10n_eg_edi_eta

## Overview
Egyptian Tax Authority (ETA) e-Invoicing integration. This module connects Odoo's accounting to the ETA portal (preproduction and production environments) for mandatory electronic invoice submission, signing, and validation. It is the most complex localization module in the MEA set, with a full EDI pipeline, cryptographic thumb-drive signing, and JSON-based invoice submission.

See also: [Modules/l10n_eg](l10n_eg.md) (base accounting)

## Country
Egypt (Arab Republic of Egypt) — country code `eg`

## Dependencies
- account_edi
- l10n_eg

## Key Models

### `AccountEdiFormat` (`account.edi.format`)
Inherits `account.edi.format`. EDI format code: `eg_eta`.

Core methods:
- `_l10n_eg_get_eta_qr_domain()`, `_l10n_eg_get_eta_api_domain()`, `_l10n_eg_get_eta_token_domain()` — return preproduction or production ETA API URLs
- `_l10n_eg_eta_connect_to_server()` — HTTP client with timeout, error wrapping, and JSON error parsing for ETA API calls
- `_l10n_eg_edi_round(amount, precision_digits=5)` — 5-decimal rounding required for ETA consistency
- `_l10n_eg_eta_get_access_token()` — OAuth2 client credentials flow (Basic auth with client ID/secret)
- `_l10n_eg_edi_post_invoice_web_service()` — POST signed invoice JSON to `/api/v1.0/documentsubmissions`, handle acceptance/rejection
- `_l10n_eg_get_einvoice_status()` — poll ETA API to get document status (Valid, Invalid, Submitted, Cancelled)
- `_cancel_invoice_edi_eta()` — PUT state change to `cancelled` on ETA portal
- `_l10n_eg_get_einvoice_document_summary()` — GET submission details
- `_l10n_eg_get_eta_invoice_pdf()` — GET PDF of government-issued invoice from ETA
- `_l10n_eg_validate_info_address()` — validate partner has all required ETA address fields (country, state, city, street, building number, VAT if above threshold)
- `_l10n_eg_eta_prepare_eta_invoice()` — transform `account.move` into ETA JSON schema 1.0 (issuer, receiver, documentType, invoiceLines, taxTotals, totals)
- `_l10n_eg_eta_prepare_invoice_lines_data()` — build per-line data including EGS/GS1 item codes, unit codes, discounts, taxable items, currency exchange rates
- `_l10n_eg_get_partner_tax_type()` — classify partner as B (B2B), F (B2F/foreign), or P (B2C/person)
- `_l10n_eg_eta_prepare_address_data()` — map partner/company to ETA address object with branch ID for issuer

EDI lifecycle methods:
- `_needs_web_services()` — returns True for `eg_eta` format
- `_get_move_applicability()` — activates on `out_invoice`, `out_refund`, `in_refund` for EG country moves
- `_check_move_configuration()` — validates all prerequisite fields before submission
- `_l10n_eg_edi_post_invoice()` — main post EDI action
- `_l10n_eg_edi_cancel_invoice()` — cancel EDI action
- `_l10n_eg_edi_xml_invoice_content()` — returns JSON-encoded invoice for EDI content

### `AccountMove` (`account.move`)
Inherits `account.move`. Fields:
- `l10n_eg_long_id` — ETA long ID, computed from JSON response attachment
- `l10n_eg_qr_code` — shareable QR code URL linking to ETA invoice portal, computed from UUID and long ID
- `l10n_eg_submission_number` — ETA submission ID from API response, `store=True`
- `l10n_eg_uuid` — ETA document UUID, `store=True`
- `l10n_eg_eta_json_doc_id` — `Many2one` to `ir.attachment` storing the raw JSON request/response
- `l10n_eg_signing_time` — `Datetime` set when signing is initiated
- `l10n_eg_is_signed` — `Boolean` flag set after thumb-drive signing completes

Key methods:
- `_auto_init()` — creates `l10n_eg_uuid` and `l10n_eg_submission_number` columns via `create_column()` if they don't exist (safe migration)
- `button_draft()` — clears `l10n_eg_eta_json_doc_id` and `l10n_eg_is_signed`
- `action_post_sign_invoices()` — orchestrates signing: gets thumb drive, sets signing time, creates JSON attachment, calls thumb drive signing action
- `action_get_eta_invoice_pdf()` — fetches government PDF from ETA and posts it as message attachment
- `_l10n_eg_edi_exchange_currency_rate()` — computes exchange rate from line balance vs amount_currency

### `EtaThumbDrive` (`l10n_eg_edi.thumb.drive`)
Standalone model (no inheritance). Stores ETA USB cryptographic signing credential per user per company.

Fields: `user_id`, `company_id`, `certificate` (binary), `pin` (char), `access_token` (char).

SQL constraint: unique (user_id, company_id).

Key methods:
- `action_sign_invoices()` — launches browser-side signing via `action_post_sign_invoice` client action
- `action_set_certificate_from_usb()` — retrieves certificate from local USB middleware
- `set_certificate()` — called from browser to persist certificate
- `set_signature_data()` — called from browser with signed data; generates CAdES-BES CMS signature and stores on invoice attachment
- `_generate_cades_bes_signature()` — builds PKCS#7/CMS signed data structure using `asn1crypto` library
- `_generate_signed_attrs__()` — builds signed attributes (content-type, message-digest, signing_certificate_v2, signing_time)
- `_serialize_for_signing()` — canonical JSON serialization for deterministic signing

### `EtaActivityType` (`l10n_eg_edi.activity.type`)
Standalone model. Reference data for ETA taxpayer activity codes.

Fields: `name` (Char, translateable), `code` (Char). `_rec_name = 'name'`. Supports name/code search.

### `UomCode` (`l10n_eg_edi.uom.code`)
Standalone model. ETA unit of measure codes for e-invoicing line items.

Fields: `name` (Char, translateable), `code` (Char).

### `UomUom` (`uom.uom`)
Inherits `uom.uom`. Adds `l10n_eg_unit_code_id` — Many2one to `l10n_eg_edi.uom.code`.

### `AccountJournal` (`account.journal`)
Inherits `account.journal`. Fields:
- `l10n_eg_branch_id` — `Many2one` to `res.partner` (company branch/subdivision)
- `l10n_eg_activity_type_id` — `Many2one` to `l10n_eg_edi.activity.type`
- `l10n_eg_branch_identifier` — Char, ETA branch ID from the e-Invoicing portal taxpayer profile

### `ProductTemplate` / `ProductProduct` (`product.template`, `product.product`)
Both inherit their respective models.

- `l10n_eg_eta_code` — Char on both; EGS or GS1 product code required for e-invoicing line items. On `ProductTemplate`, computed from the single variant.

### `ResPartner` (`res.partner`)
Inherits `res.partner`. Adds:
- `l10n_eg_building_no` — Char, building number required in ETA address

Commercial fields and address fields both include `l10n_eg_building_no` so it propagates to contact children.

### `ResCompany` (`res.company`)
Inherits `res.company`. Fields:
- `l10n_eg_client_identifier` — ETA Client ID (API credential)
- `l10n_eg_client_secret` — ETA Secret
- `l10n_eg_production_env` — Boolean to switch between preproduction and production ETA environments
- `l10n_eg_invoicing_threshold` — Float, VAT number requirement threshold (invoice total above this requires customer VAT number)

### `ResConfigSettings` (`res.config.settings`)
Inherits `res.config.settings`. Related fields to `ResCompany` settings above (all `readonly=False`).

### `ResCurrencyRate` (`res.currency.rate`)
Inherits `res.currency.rate`. Overrides `_onchange_rate_warning()` to warn users if EGP exchange rate is not within 5 decimal precision (required for ETA consistency).

## Data Files
- `data/account_edi_data.xml` — EDI format record (`eg_eta`)
- `data/l10n_eg_edi.activity.type.csv` — ETA activity type reference data
- `data/l10n_eg_edi.uom.code.csv` — ETA unit of measure codes
- `data/uom.uom.csv` — maps Odoo UoMs to ETA codes
- `data/res_country_data.xml` — country data for ETA portal
- `security/ir.model.access.csv` — access rights for new models
- `security/eta_thumb_drive_security.xml` — record rules for thumb drive model
- `views/uom_uom_view.xml`, `views/account_move_view.xml`, `views/account_journal_view.xml`, `views/eta_thumb_drive.xml`, `views/product_template_views.xml`, `views/res_config_settings_view.xml`, `views/report_invoice.xml` — UI views

## External Dependencies
Python package: `asn1crypto` — for CMS/PKCS#7 cryptographic signing

## EDI/Fiscal Reporting
Full e-Invoicing pipeline:
1. Invoice created in Odoo with ETA tax codes on lines
2. `action_post_sign_invoices()` — invoice JSON prepared, stored as attachment
3. Thumb-drive signing (browser-side, local middleware) — CAdES-BES signature added
4. Invoice posted via `_l10n_eg_edi_post_invoice()` — submitted to ETA API
5. ETA validates and returns `uuid`, `longId`, `submissionId`
6. QR code generated linking to government portal
7. Cancellation via `_cancel_invoice_edi_eta()`

ETA API domains:
- Preproduction: `https://api.preprod.invoicing.eta.gov.eg`
- Production: `https://api.invoicing.eta.gov.eg`
- Token: `https://id.preprod.eta.gov.eg` / `https://id.eta.gov.eg`

## Historical Notes
- Version 0.2 in Odoo 18
- Requires local middleware/thumb-drive signing tool running at `l10n_eg_eta.sign.host` (default `http://localhost:8069`)
- The thumb-drive mechanism uses a physical USB token with client-side browser signing — this is an Egyptian Tax Authority requirement for digital certificate storage
- External Python dependency `asn1crypto` must be installed separately
