---
Module: l10n_in_edi_ewaybill
Version: 18.0
Type: l10n/india-edi
Tags: #odoo18 #l10n #edi #einvoice #ewaybill #india
---

# l10n_in_edi_ewaybill — Indian E-waybill (EDI)

## Overview
E-waybill EDI module for India. Generates and submits e-waybill JSON to the GST e-waybill portal via GSP (Tera Software Limited). Can generate e-waybill directly (without IRN) or link to an existing e-invoice IRN from `l10n_in_edi`. Part of the Indian GST EDI stack. Not auto-install because some companies may only need e-invoice without e-waybill.

## Country
India

## Dependencies
- l10n_in_edi (which transitively requires l10n_in)

## Key Models

### `AccountEdiFormat` (`account.edi.format`) — account_edi_format.py
- `_inherit = "account.edi.format"`
- EDI format code: `in_ewaybill_1_03`
- Methods:
  - `_l10n_in_edi_ewaybill_base_irn_or_direct(move)` — determines if using IRN-linked or direct e-waybill
  - `_l10n_in_edi_ewaybill_irn_json_invoice_content(move)` — IRN-based JSON content
  - `_l10n_in_edi_ewaybill_json_invoice_content(move)` — direct (no IRN) JSON content
  - `_l10n_in_edi_ewaybill_cancel_invoice(invoices)` — cancel e-waybill
  - `_l10n_in_edi_ewaybill_handle_zero_distance_alert_if_present()` — handles transport distance alert
  - `_l10n_in_edi_ewaybill_irn_post_invoice_edi(invoices)` — post e-waybill linked to IRN
  - `_l10n_in_edi_irn_ewaybill_generate_json(invoice)` — generates JSON for IRN-linked e-waybill
  - `_l10n_in_edi_ewaybill_post_invoice_edi(invoices)` — post direct e-waybill
  - `_l10n_in_edi_ewaybill_get_error_message(code)` — maps error codes to human messages
  - `_l10n_in_edi_ewaybill_generate_json(invoices)` — direct e-waybill JSON generation
  - `_l10n_in_edi_irn_ewaybill_generate(company, json_payload)` — IAP call: generate e-waybill via IRN
  - `_l10n_in_edi_irn_ewaybill_get(company, irn)` — IAP call: get e-waybill by IRN
  - `_l10n_in_edi_ewaybill_no_config_response()` — returns message if no credentials
  - `_l10n_in_edi_ewaybill_check_authentication(company)` — validates token
  - `_l10n_in_set_missing_error_message(response)` — handles missing field errors
  - `_l10n_in_edi_ewaybill_connect_to_server(company, url_path, params)` — IAP RPC
  - `_l10n_in_edi_ewaybill_authenticate(company)` — auth to e-waybill portal
  - `_l10n_in_edi_ewaybill_generate(company, json_payload)` — direct generate
  - `_l10n_in_edi_ewaybill_cancel(company, json_payload)` — cancel
  - `_l10n_in_edi_ewaybill_get_by_consigner(company, doc_type, doc_number)` — lookup by consigner

### `AccountMove` (`account.move`) — account_move.py
- `_inherit = "account.move"`
- `_compute_l10n_in_edi_ewaybill_show_send_button()` — shows send button
- `_compute_l10n_in_edi_ewaybill_direct()` — shows direct vs IRN-linked mode
- `_compute_l10n_in_edi_show_cancel()` — shows cancel button
- `button_cancel_posted_moves()` — override requiring cancel reason

### `ResCompany` (`res.company`) — res_company.py
- `_inherit = "res.company"`
- E-waybill credentials: `l10n_in_edi_ewaybill_username`, `l10n_in_edi_ewaybill_password`

### `ResConfigSettings` (`res.config.settings`)
- `_inherit = "res.config.settings"`
- E-waybill settings (credentials, production toggle)

### `EWayBillType` (`l10n.in.ewaybill.type`) — ewaybill_type.py
- `_name = "l10n.in.ewaybill.type"`
- Fields: `name`, `code` (INV, BIL, BOE, CHN, CIN, CTR), `sub_type` (Supply, Export, SKD/CKD/Lots, Import, Others), `sub_type_code`, `allowed_supply_type` (both/in/out), `active`
- Display name: `"%s (Sub-Type: %s)" % (name, sub_type)`

## Data Files
- `data/account_edi_data.xml` — EDI format `in_ewaybill_1_03`
- `data/ewaybill_type_data.xml` — E-waybill document types (INV/BIL/BOE/CHN/CIN/CTR × Supply/Export/etc.)
- `security/ir.model.access.csv`
- `views/account_move_views.xml`
- `views/edi_pdf_report.xml`
- `views/res_config_settings_views.xml`

## E-Waybill JSON Structure
Direct e-waybill JSON fields: `supplyType`, `subSupplyType`, `docType`, `docNo`, `docDate`, `fromGstin`, `fromTrdName`, `fromAddr1`, `fromAddr2`, `fromPlace`, `fromPincode`, `fromState`, `actFromState`, `toGstin`, `toTrdName`, `toAddr1`, `toAddr2`, `toPlace`, `toPincode`, `toState`, `actToState`, `itemList`, `totalValue`, `cgstValue`, `sgstValue`, `igstValue`, `cessValue`, `cessNonAdvolValue`, `totInvValue`, `transporterId`, `transporterName`, `transDocNo`, `transDocDate`, `vehicleNo`, `vehicleType` (regular/over-dimensional).

## Installation
Installable. Not auto-install — requires manual activation since some businesses only need e-invoice.

## Historical Notes
Version 1.03.00 in Odoo 18 (matches e-invoice version). E-waybill system was introduced by GST Council for transport of goods > Rs. 50,000. Previously separate from e-invoice but now linked via IRN. Supports both direct generation and IRN-linked generation.