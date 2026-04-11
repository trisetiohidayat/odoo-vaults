---
Module: l10n_in_pos
Version: 18.0
Type: l10n/india
Tags: #odoo18 #l10n #accounting #pos #india
---

# l10n_in_pos — Indian Point of Sale

## Overview
India-specific extension of the Point of Sale module. Adds GST treatment computation, HSN/SAC code tracking at POS order line level, and India-specific tax type handling so that POS orders generate fully GST-compliant invoices when converted to journal entries.

## Country
India

## Dependencies
- l10n_in
- point_of_sale

## Key Models

### `PosOrder` (`pos.order`) — pos_order.py
- `_inherit = 'pos.order'`
- `_prepare_invoice_vals()` — EXTENDS point_of_sale:
  - Computes `l10n_in_gst_treatment` from partner (same logic as sale orders: overseas if foreign, regular if Indian with VAT, consumer if no GSTIN)
  - Injects `l10n_in_gst_treatment` into invoice vals
- `_prepare_product_aml_dict()` — EXTENDS:
  - Adds `l10n_in_hsn_code` from product to the account move line dict (so journal items carry HSN code for GST reporting)

### `PosOrderLine` (`pos.order.line`) — pos_order_line.py
- `_inherit = "pos.order.line"`
- `l10n_in_hsn_code` — Char, computed from `product_id.l10n_in_hsn_code` (stored, copy=False)
- `_compute_l10n_in_hsn_code()` — `@api.depends('product_id')` — copies HSN from product to POS line
- `_load_pos_data_fields(config_id)` — `@api.model` — extends POS data load to include `l10n_in_hsn_code` for Indian configurations

### `ProductProduct` (`product.product`) — product_product.py
- `_inherit = "product.product"`
- `_load_pos_data_fields(config_id)` — `@api.model` — extends POS data load to include `l10n_in_hsn_code` for Indian configurations (ensures product HSN is synced to POS frontend)

### `AccountMove` (`account.move`) — account_move.py
- `_inherit = 'account.move'`
- India-specific invoice overrides from `l10n_in` (HSN warning, GST treatment display, invoice sequence validation)

### `AccountTax` (`account.tax`) — account_tax.py
- `_inherit = 'account.tax'`
- `_load_pos_data_fields(config_id)` — `@api.model` — extends POS tax data load to include `l10n_in_tax_type` field (needed for POS frontend to display CGST/SGST/IGST breakdown)

## Data Files
- `views/pos_order_line_views.xml` — POS order line form with HSN code display
- `views/res_config_settings_views.xml` — Indian POS configuration settings
- `data/pos_bill_data.xml` — Indian currency denominations/bills (for cash handling)
- `data/product_demo.xml` — Demo products for POS with HSN codes
- JS assets: `l10n_in/static/src/helpers/hsn_summary.js` — HSN summary computation for POS receipts

## POS Invoice GST Flow
1. POS order created → lines inherit HSN from products
2. Order closed → `_prepare_invoice_vals()` computes GST treatment and creates journal entry
3. Invoice journal entry carries HSN codes on lines (from `_prepare_product_aml_dict`)
4. Tax computation uses IGST/CGST/SGST split based on fiscal position from l10n_in

## Installation
`auto_install = True`. Auto-installs with `l10n_in` + `point_of_sale`. JS assets loaded via `point_of_sale._assets_pos`.

## Historical Notes
Version 1.0 in Odoo 18. HSN code tracking at POS line level is new in Odoo 18 — earlier versions didn't propagate HSN to POS invoices. The `l10n_in_tax_type` field loading in POS data ensures tax type information is available on the POS frontend for GST-compliant receipts.