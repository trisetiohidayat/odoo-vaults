---
Module: l10n_es_edi_verifactu_pos
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #spain #pos
---

# l10n_es_edi_verifactu_pos

## Overview
Adds Veri*Factu e-invoice compliance to the Point of Sale. Veri*Factu is Spain's new mandatory real-time invoice reporting system (2024 decree), replacing the old Suministro Inmediato de Información (SII). Each POS order paid without an invoice generates a Veri*Factu submission document.

## EDI Format / Standard
Veri*Factu JSON over REST API to the AEAT. Governed by Spanish Royal Decree 1007/2023 and Order HAC/1278/2023.

## Dependencies
- `l10n_es_edi_verifactu` -- core Veri*Factu module
- `point_of_sale` -- POS session/order models

## Key Models

### `pos.order` (`l10n_es_edi_verifactu_pos.pos_order`)
Inherits: `pos.order`

Fields:
- `l10n_es_edi_verifactu_required` -- Boolean, related to company setting
- `l10n_es_edi_verifactu_document_ids` -- One2many to `l10n_es_edi_verifactu.document`
- `l10n_es_edi_verifactu_state` -- Selection: `rejected | registered_with_errors | accepted | cancelled`
- `l10n_es_edi_verifactu_warning_level` / `_warning` -- HTML warning for errors and pending states
- `l10n_es_edi_verifactu_qr_code` -- Computed QR code URL
- `l10n_es_edi_verifactu_show_cancel_button` -- Computed boolean
- `l10n_es_edi_verifactu_refund_reason` -- Selection: R1–R5

Key methods:
- `_compute_l10n_es_edi_verifactu_state()` -- aggregates state from document chain
- `_l10n_es_edi_verifactu_get_record_values()` -- builds document values; handles refund logic and tax applicability
- `_l10n_es_edi_verifactu_create_documents()` -- creates `l10n_es_edi_verifactu.document` for each order
- `_l10n_es_edi_verifactu_mark_for_next_batch()` -- marks for batch sending
- `_process_saved_order()` -- validates refund reason, partner, and invoice threshold
- `action_pos_order_paid()` -- triggers batch submission on payment
- `_generate_pos_order_invoice()` -- cancels order Veri*Factu record and registers invoice submission

### `pos.session` (`l10n_es_edi_verifactu_pos.pos_session`)
Inherits: `pos.session`

- `_load_pos_data()` -- injects Veri*Factu refund reason options into POS client data

### `l10n_es_edi_verifactu.document` (`l10n_es_edi_verifactu_pos.verifactu_document`)
Inherits: `l10n_es_edi_verifactu.document` (via `_inherit`)

- `pos_order_id` -- Many2one to `pos.order`; links the document back to the POS order

### `res.company` (`l10n_es_edi_verifactu_pos.res_company`)
Inherits: `res.company`

- `_load_pos_data_fields()` -- adds `l10n_es_edi_verifactu_required` to POS field list

### `account.move` (`l10n_es_edi_verifactu_pos.account_move`)
Inherits: `account.move`

- `_l10n_es_edi_verifactu_get_record_values()` -- extends parent; if a refund order exists but the refunded order was not invoiced, retrieves its Veri*Factu submission document

### `pos.config` (`l10n_es_edi_verifactu_pos.pos_config`)
Inherits: `pos.config`

- `l10n_es_edi_verifactu_required` -- Boolean, related to company

## Data Files
No data XML files; relies on parent module.

## How It Works
1. POS order is paid without invoice
2. `action_pos_order_paid()` calls `_l10n_es_edi_verifactu_mark_for_next_batch()`
3. Records are created as `l10n_es_edi_verifactu.document` with type `submission`
4. A cron job (from parent module) batches and sends documents to AEAT
5. If order is later invoiced: the order-level Veri*Factu is cancelled, invoice-level Veri*Factu is created
6. State transitions: `to_send` → `accepted | registered_with_errors | rejected | cancelled`

## Installation
Install after `l10n_es_edi_verifactu` and `point_of_sale`. Auto-installs. Requires company-level `l10n_es_edi_verifactu_required` to be enabled.

## Historical Notes
Veri*Factu replaced SII for simplified invoices starting 2024. The POS extension is new in Odoo 18. The key architectural challenge this module solves is handling refunds where the original order was a POS order (not an invoice): the `_l10n_es_edi_verifactu_get_record_values()` override retrieves the parent Veri*Factu document from the POS order rather than the account move.
