---
Module: l10n_in_edi
Version: 18.0
Type: l10n/india
Tags: #odoo18 #l10n #accounting #edi #india #einvoice
---

# l10n_in_edi — Indian E-Invoicing

## Overview
Implements the Indian Government-mandated e-invoice (electronic invoice) system for GST, as per the GST Council's e-invoice framework. Submits invoices to the Invoice Registration Portal (IRP) via a GSP (GST Suvidha Provider) — Odoo uses Tera Software Limited as the GSP. Generates JSON payloads conforming to the IRP 1.03 specification, handles IRN (Invoice Reference Number) generation, cancellation, and QR code with QRIS support.

This module is the core EDI layer for Indian GST. Companies with turnover above Rs. 5 crore are mandated to issue e-invoices.

## Country
India

## Dependencies
- account_edi
- l10n_in

## Key Models

### `AccountEdiFormat` (`account.edi.format`) — account_edi_format.py
- `_inherit = "account.edi.format"`
- EDI format code: `in_einvoice_1_03`

**EDI Format Methods:**

- `_is_enabled_by_default_on_journal(journal)` — returns `False` for e-invoice (only applicable for taxpayers > Rs.5 crore turnover)
- `_is_compatible_with_journal(journal)` — returns `True` only for Indian sale journals
- `_get_l10n_in_gst_tags()` — returns tag IDs for all GST tax base tags (SGST, CGST, IGST, CESS, zero-rated)
- `_get_l10n_in_non_taxable_tags()` — returns tag IDs for exempt, nil-rated, non-GST supplies
- `_get_move_applicability(move)` — returns applicability rules for Indian sale documents with GST:
  - `post`: `_l10n_in_edi_post_invoice`
  - `cancel`: `_l10n_in_edi_cancel_invoice`
  - `edi_content`: `_l10n_in_edi_xml_invoice_content`
- `_needs_web_services()` — returns `True` for `in_einvoice_1_03` (requires online submission)
- `_l10n_in_edi_xml_invoice_content(invoice)` — returns JSON-encoded bytes of the invoice JSON

**Configuration Checks:**
- `_check_move_configuration(move)` — validates:
  - Invoice number <= 16 characters
  - All product lines have HSN codes (4/6/8 digits) and valid GST taxes
  - No negative discounts
  - Partner address fields meet GST portal requirements

**E-Invoice Post Flow (`_l10n_in_edi_post_invoice`):**
1. Generate JSON via `_l10n_in_edi_generate_invoice_json(invoice)`
2. Submit via `_l10n_in_edi_generate(company, json_payload)` (IAP call to GSP)
3. Handle errors: token expiry (1005) → re-authenticate and retry; IRN already generated (2150) → fetch IRN by details; no credit → return buy-credits message
4. On success: create JSON attachment, return success

**E-Invoice Cancel Flow (`_l10n_in_edi_cancel_invoice`):**
1. Read IRN from existing JSON attachment
2. Build cancel JSON: `{Irn, CnlRsn, CnlRem}`
3. Submit cancel via `_l10n_in_edi_cancel(company, cancel_json)`
4. Handle errors (token 1005, already cancelled 9999)
5. Create cancel JSON attachment

**JSON Generation (`_l10n_in_edi_generate_invoice_json`):**
Generates v1.1 format JSON with sections:
- `TranDtls`: TaxSch="GST", SupTyp (B2B/EXPWP/SEZWP/DEXP), RegRev, IgstOnIntra
- `DocDtls`: Typ (INV/CRN/DBN), No, Dt
- `SellerDtls`: from `move.company_id.partner_id`
- `BuyerDtls`: from `move.partner_id`, POS state
- `DispDtls`: dispatch details from `_l10n_in_get_warehouse_address()`
- `ShipDtls`: ship-to details
- `ItemList`: line items with HsnCd, Qty, Unit, UnitPrice, GstRt, IgstAmt, CgstAmt, SgstAmt, CesRt, CesAmt, etc.
- `ValDtls`: AssVal, CgstVal, SgstVal, IgstVal, CesVal, StCesVal, Discount, RndOffAmt, TotInvVal

**Negative Line Handling (`_l10n_in_edi_generate_invoice_json_managing_negative_lines`):**
Converts negative invoice lines to discounts on positive lines with the same HSN code and tax rate.

**Partner Validation (`_l10n_in_validate_partner`):**
- Street/city: 3-100 chars
- Indian ZIP: 6 digits (100000-999999)
- State TIN: exactly 2 digits
- Phone: 10-12 digits
- Email: valid format, 6-100 chars

**IAP Integration:**
- `_l10n_in_edi_get_token(company)` — get/refresh auth token
- `_l10n_in_edi_connect_to_server(company, url_path, params)` — IAP RPC call
- `_l10n_in_edi_authenticate(company)` — POST to `/iap/l10n_in_edi/1/authenticate`; stores `l10n_in_edi_token` and `l10n_in_edi_token_validity` in company record (validity stored in IST, converted to UTC)
- `_l10n_in_edi_generate(company, json_payload)` — POST to `/iap/l10n_in_edi/1/generate`
- `_l10n_in_edi_get_irn_by_details(company, json_payload)` — POST to `/iap/l10n_in_edi/1/getirnbydocdetails`
- `_l10n_in_edi_cancel(company, json_payload)` — POST to `/iap/l10n_in_edi/1/cancel`

### `AccountMove` (`account.move`) — account_move.py
- `_inherit = "account.move"`
- `l10n_in_edi_cancel_reason` — Selection: 1-Duplicate, 2-Data Entry Mistake, 3-Order Cancelled, 4-Others
- `l10n_in_edi_cancel_remarks` — Char
- `l10n_in_edi_show_cancel` — Boolean (compute), True if e-invoice has been sent
- `_compute_l10n_in_edi_show_cancel()` — checks `edi_document_ids` for `in_einvoice_1_03` in sent/to_cancel/cancelled state
- `action_retry_edi_documents_error()` — posts retry message for blocking EDI errors
- `button_cancel_posted_moves()` — OVERRIDE: requires cancel reason+remarks before proceeding (raises `UserError` if not set)
- `_get_l10n_in_edi_response_json()` — reads the JSON attachment from last e-invoice submission
- `_can_force_cancel()` — returns True if any e-invoice document is in `to_cancel` state (allows force-cancel of the move)

### `ResCompany` (`res.company`) — res_company.py
- `_inherit = "res.company"`
- `l10n_in_edi_username` — Char (groups: base.group_system)
- `l10n_in_edi_password` — Char (groups: base.group_system)
- `l10n_in_edi_token` — Char (groups: base.group_system)
- `l10n_in_edi_token_validity` — Datetime (groups: base.group_system)
- `_l10n_in_edi_token_is_valid()` — checks token and validity datetime > now

### `ResConfigSettings` (`res.config.settings`)
- `_inherit = "res.config.settings"`
- Indian e-invoice configuration (username/password, production toggle)

## Data Files
- `data/account_edi_data.xml` — EDI format configuration (in_einvoice_1_03)
- `views/res_config_settings_views.xml` — E-invoice settings form
- `views/edi_pdf_report.xml` — EDI report PDF layout
- `views/account_move_views.xml` — Cancel reason/remarks fields on invoice form
- `demo/demo_company.xml` — Demo Indian company with test GSTIN

## Supply Types (SupTyp in JSON)
- `B2B` — Regular business-to-business
- `EXPWP` — Export with payment of IGST (with payment)
- `EXPWOP` — Export without payment (LUT/bond)
- `SEZWP` — SEZ with payment of IGST
- `SEZWOP` — SEZ without payment
- `DEXP` — Deemed Export

## EDI Flow
1. **Draft** → user creates invoice with GST taxes and HSN codes
2. **Validate** (`_post`) → normal Odoo validation; user sends e-invoice
3. **Submit** → JSON posted to GSP → IRP → IRN returned → JSON saved as attachment
4. **QR Code** → IRP QR code included on printed invoice
5. **Cancel** → user enters reason/remarks → cancel submitted to IRP → IRN invalidated

## Installation
Installable on top of `l10n_in`. Requires GSP credentials (API username/password from e-invoice portal). Demo data includes test GSTIN for sandbox testing.

## Historical Notes
Version 1.03.00 in Odoo 18 (e-invoice IRP version 1.03). e-invoice mandate expanded to companies with turnover > Rs. 5 crore (previously > Rs. 500 crore before gradual rollout). Significant changes in Odoo 18: negative line to discount conversion, export/SEZ supply type differentiation, IgstOnIntra flag for intra-state IGST on B2C, GST portal validation improvements, token refresh logic. Earlier versions (v17) supported e-invoice v1.01.