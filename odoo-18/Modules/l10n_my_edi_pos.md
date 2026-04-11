---
Module: l10n_my_edi_pos
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #malaysia #pos
---

# l10n_my_edi_pos

## Overview
Integrates the MyInvois e-invoicing system (Malaysia's LHDN mandatory e-invoice platform) with the Point of Sale. POS orders are linked to consolidated invoices which are submitted monthly to the MyInvois API during the allowed timeframe. The module depends on `l10n_my_edi_extended` and `point_of_sale`.

## EDI Format / Standard
UBL 2.1 MyInvois Profile (customised Malaysian extension). API calls to the LHDN MyInvois sandbox/production endpoints via the `account_edi_ubl_cii` framework.

## Dependencies
- `l10n_my_edi_extended` -- core MyInvois module with UBL XML builder
- `point_of_sale` -- POS framework

## Key Models

### `pos.order` (`l10n_my_edi_pos.pos_order`)
Inherits: `pos.order`

Fields:
- `consolidated_invoice_ids` -- Many2many to `myinvois.document` (link to consolidated invoice)

Methods:
- `_process_order()` -- blocks refund orders that would violate MyInvois rules: if refunded order was submitted to MyInvois, refund must be invoiced; if not yet submitted, refund must not be invoiced
- `_order_fields()` -- captures `consolidated_invoice_ids` from POS client data
- `_generate_pos_order_invoice()` -- prevents invoicing of orders already in a consolidated invoice; validates partner identification data; invoices without PDF first, sends to MyInvois, then generates PDF
- `_get_active_consolidated_invoice()` -- returns the currently active (non-cancelled) consolidated invoice for the order
- `action_show_consolidated_invoice()` -- opens the consolidated invoice form/list

### `myinvois.document` (`l10n_my_edi_pos.myinvois_document_pos`)
Inherits: `myinvois.document`

Extends the parent `MyInvoisDocument` model for POS-consolidated invoices.

Fields:
- `pos_order_ids` -- Many2many to `pos.order`
- `pos_config_id` -- Many2one to `pos.config`
- `linked_order_count` -- Computed count of linked orders
- `pos_order_date_range` -- Computed string: first to last order date

Methods:
- `_get_starting_sequence()` -- Returns `CINV/YYYY/00000` for consolidated invoices
- `_compute_linked_order_count()` / `_compute_pos_order_date_range()`
- `_separate_orders_in_lines()` -- Groups orders by PoS config and continuity (sequence gaps break groups); returns `{config: [order_set]}`
- `_myinvois_export_document()` -- Builds consolidated invoice XML from linked POS orders using the UBL MyInvois builder
- `_myinvois_export_document_constraints()` -- Validates supplier details (phone E.164 format, TIN, address fields, industrial classification) and enforces `EI00000000010` customer VAT for consolidated invoices
- `action_view_linked_orders()` -- Returns action to open linked orders
- `action_open_consolidate_invoice_wizard()` -- Opens wizard to create consolidated invoice from date range

### `account.edi.xml.ubl_myinvois_my` (`l10n_my_edi_pos.account_edi_xml_ubl_my`)
Inherits: `account.edi.xml.ubl_myinvois_my`

- `_get_consolidated_invoice_node()` -- Renders consolidated invoice XML (invoked from `_myinvois_export_document()`)

### `account.tax` (`l10n_my_edi_pos.account_tax`)
Inherits: `account.tax`

- `_load_pos_data_fields()` -- Injects tax-related fields needed by the POS client for MyInvois submission (extends parent, exact extensions minimal)

## Data Files
- `data/ir_cron.xml` -- Cron job for MyInvois polling/status updates
- `data/res_partner.xml` -- Default partner configurations
- `security/myinvois_security.xml`, `ir.model.access.csv` -- Access control
- `views/myinvois_document_pos_views.xml`, `views/pos_order_views.xml`, `wizard/*.xml` -- UI views

## How It Works
1. POS orders are created and saved (not invoiced individually)
2. A consolidated invoice wizard groups orders by date range
3. `_separate_orders_in_lines()` groups orders by PoS config and sequence continuity
4. The XML is generated via `_myinvois_export_document()` using UBL MyInvois templates
5. Constraints are validated (supplier phone, TIN, addresses; customer VAT = `EI00000000010`)
6. Document is submitted to MyInvois API; state moves `in_progress` → `valid | rejected`
7. Orders already submitted cannot be refunded without being invoiced (enforced in `_process_order()`)

## Installation
Install after `l10n_my_edi_extended` and `point_of_sale`. Auto-installs. Requires Malaysian company settings (industrial classification, TIN) and LHDN API credentials configured in the parent module.

## Historical Notes
The consolidated invoice feature is new in Odoo 18. Malaysia's MyInvois mandate allows grouping many small POS transactions into a single e-invoice submission to reduce API call volume. The `EI00000000010` "General Public" TIN is a special MyInvois identifier for B2C consolidated invoices.
