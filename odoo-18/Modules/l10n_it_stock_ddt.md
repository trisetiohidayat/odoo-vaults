---
Module: l10n_it_stock_ddt
Version: 18.0
Type: l10n/it
Tags: #odoo18 #l10n #accounting #stock
---

# l10n_it_stock_ddt

## Overview
Italian localization extension that adds the *Documento di Trasporto* (DDT) — Transport Document. Italy requires a DDT whenever goods are physically transferred between parties. The DDT legitimizes transport (e.g., police checks) and must accompany shipments. This module generates a separate DDT number sequence per warehouse/outgoing picking type, attaches transport metadata, links DDTs to invoices for FatturaPA XML export, and provides a printable DDT report.

## Country
[Italy](account.md) 🇮🇹

## Dependencies
- l10n_it_edi
- stock_delivery
- stock_account

## Key Models

### StockPicking
`models/stock_picking.py` — extends `stock.picking`
- `l10n_it_transport_reason` (Selection) — reason for transport: `sale`, `outsourcing`, `evaluation`, `gift`, `transfer`, `substitution` (returned goods), `attemped_sale`, `loaned_use`, `repair`
- `l10n_it_transport_method` (Selection) — transport method: `sender`, `recipient`, `courier`
- `l10n_it_transport_method_details` (Char) — free-text transport notes
- `l10n_it_parcels` (Integer, default=1) — number of parcels
- `l10n_it_ddt_number` (Char, readonly) — DDT sequence number assigned on `_action_done`
- `l10n_it_show_print_ddt_button` (Boolean, computed) — visible only for done Italian outgoing shipments or dropshipments
- `_compute_l10n_it_show_print_ddt_button()` — `@api.depends`: shows print button when IT, done, locked, and (outgoing or dropshipment)
- `_action_done()` — override: assigns DDT number from picking type sequence on completion

### StockPickingType
`models/stock_picking_type.py` — extends `stock.picking.type`
- `l10n_it_ddt_sequence_id` (Many2one `ir.sequence`) — no-gap sequence for DDT numbering per warehouse
- `_get_dtt_ir_seq_vals()` — helper: builds sequence name and prefix based on warehouse
- `create()` — override: auto-creates `no_gap` DDT sequence for IT outgoing picking types
- `write()` — override: updates DDT sequence name/prefix if sequence_code changes

### AccountMove
`models/account_invoice.py` — extends `account.move`
- `l10n_it_ddt_ids` (Many2many `stock.picking`, computed) — linked delivery orders for this invoice
- `l10n_it_ddt_count` (Integer, computed) — number of linked DDTs
- `_l10n_it_edi_document_type_mapping()` — override: adds `TD24` (deferred invoice) document type; marks all except TD07 as non-direct
- `_l10n_it_edi_invoice_is_direct()` — an invoice is direct only if all linked DDTs were done on the same date as the invoice
- `_l10n_it_edi_features_for_document_type_selection()` — adds `direct_invoice` feature flag
- `_get_ddt_values()` — FIFO matching of invoice lines to DDTs via sale order lines; handles multi-order invoices and returns
- `_compute_ddt_ids()` — `@api.depends` on invoice lines and sale lines; computes linked pickings
- `get_linked_ddts()` — action returning list/form of linked DDTs
- `_l10n_it_edi_get_values()` — extends FatturaPA XML values with DDT dictionary for `DatiDDT` node rendering

## Data Files
- `data/l10n_it_ddt_template.xml` — QWeb template extending FatturaPA export: injects `DatiDDT` nodes with DDT number, date, and line references for each linked picking
- `report/l10n_it_ddt_report.xml` — DDT printable report (PDF): company/customer address, transport details, order reference, parcels, product table with value

## Chart of Accounts
Inherits from `l10n_it` (Italian base chart).

## Tax Structure
Inherits from `l10n_it_edi` (FatturaPA standard).

## Fiscal Positions
DDT determines invoice type (TD01 direct vs TD24 deferred) in FatturaPA:
- Direct invoice: DDT done same day as invoice
- Deferred invoice (TD24): DDT done on different day (requires separate transport document)

## EDI/Fiscal Reporting
**FatturaPA XML:**
- `DatiDDT` node added to FatturaPA for each linked picking
- Contains: NumeroDDT (DDT number, max 20 chars), DataDDT (DDT date), RiferimentoNumeroLinea (invoice line numbers)
- TD24 document type used for deferred invoices (DDT ≠ invoice date)

## Installation
`auto_install: True` — auto-installed with `l10n_it_edi` when dependencies present.

Post-init hook: `_create_picking_seq` — creates DDT sequences for all existing outgoing picking types.

## Historical Notes

**Odoo 17 → 18 changes:**
- TD24 document type for deferred invoices was introduced more recently (pre-Odoo 18)
- DDT sequence management (`no_gap` implementation) is a mature feature
- FIFO matching between invoice lines and DDTs via sale order lines is the established pattern
- DDT report has been stable; physical transport document requirements are consistent

**Performance Notes:**
- DDT sequence creation on init is O(picking_types) — fast
- FIFO matching on large invoices with many DDTs: O(n) where n = invoice lines × DDTs
- DDT computation is cached; only recomputes on line changes