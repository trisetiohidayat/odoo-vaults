---
Module: l10n_es_edi_tbai_pos
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #spain #pos
---

# l10n_es_edi_tbai_pos

## Overview
Adds TicketBAI e-invoice chain compliance to the Point of Sale. Each POS order that is not invoiced generates a TicketBAI XML document submitted to the Spanish tax agency (AEAT) in real-time via the `l10n_es_edi_tbai` chain mechanism. This module extends `point_of_sale` and `l10n_es_edi_tbai`.

## EDI Format / Standard
TicketBAI XML (TBAI) -- Spanish Basque country mandatory e-invoice chain format. Governed by TicketBAI decree (BOE-A-1992-28740). Uses a chain signature model where each document references the previous one.

## Dependencies
- `l10n_es_edi_tbai` -- core TicketBAI module
- `point_of_sale` -- POS session/order models

## Key Models

### `pos.order` (`l10n_es_edi_tbai_pos.pos_order`)
Inherits: `pos.order`

Fields:
- `l10n_es_tbai_state` -- Selection: `to_send | sent`
- `l10n_es_tbai_chain_index` -- Integer: position in the TBAI chain
- `l10n_es_tbai_post_document_id` -- Many2one to `l10n_es_edi_tbai.document`
- `l10n_es_tbai_post_file` / `_name` -- Binary + Char for the XML attachment
- `l10n_es_tbai_is_required` -- Boolean, related to `company_id.l10n_es_tbai_is_enabled`
- `l10n_es_tbai_refund_reason` -- Selection of TBAI refund reason codes

Key methods:
- `_process_saved_order()` -- validates order (simplified invoice limit, refund linkage rules) before saving
- `action_pos_order_paid()` -- triggers `_l10n_es_tbai_post()` after payment if not invoiced
- `_l10n_es_tbai_post()` -- creates EDI document and calls `_post_to_web_service()`
- `_l10n_es_tbai_create_edi_document()` -- creates `l10n_es_edi_tbai.document` record
- `_l10n_es_tbai_get_values()` -- builds tax base lines for XML generation
- `get_l10n_es_pos_tbai_qrurl()` -- returns the TBAI QR code for the receipt

### `pos.session` (`l10n_es_edi_tbai_pos.pos_session`)
Inherits: `pos.session`

- `_load_pos_data()` -- injects TBAI refund reasons into POS client-side data

### `res.company` (`l10n_es_edi_tbai_pos.res_company`)
Inherits: `res.company`

- `_load_pos_data_fields()` -- adds `l10n_es_tbai_is_enabled` to POS field list

## Data Files
No data XML files; uses parent module data.

## How It Works
1. POS order is confirmed and paid (no invoice)
2. `action_pos_order_paid()` calls `_l10n_es_tbai_post()`
3. A `l10n_es_edi_tbai.document` record is created via `_l10n_es_tbai_create_edi_document()`
4. Document XML values are built from order lines + taxes via `_l10n_es_tbai_get_values()`
5. Document is submitted to the TicketBAI web service; state moves to `accepted` or `rejected`
6. If order is later invoiced, a cancellation record is created and the invoice replaces the simplified record
7. The QR code URL is retrieved via `get_l10n_es_pos_tbai_qrurl()` for receipt display

## Installation
Install as part of Spanish localization after `l10n_es` and `l10n_es_edi_tbai`. The module auto-installs with `l10n_es_edi_tbai`. Requires company to have TicketBAI certificates configured.

## Historical Notes
TicketBAI for POS is new in Odoo 18. In Odoo 17, the Spanish TBAI integration only covered `account.move` invoices. The POS extension creates a separate document model chain (mirroring the account move flow) to handle simplified tickets that do not become full invoices.
