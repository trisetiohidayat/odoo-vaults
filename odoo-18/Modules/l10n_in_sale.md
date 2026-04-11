---
Module: l10n_in_sale
Version: 18.0
Type: l10n/india
Tags: #odoo18 #l10n #accounting #sale #india
---

# l10n_in_sale — Indian Sale Report (GST)

## Overview
India-specific extension of the Sale module, adding GST-specific fields and fiscal position logic to sale orders and customer invoices. Computes GST treatment from partner, determines Place of Supply, applies fiscal positions (intra-state CGST+SGST vs inter-state IGST), and carries these through to the invoice.

## Country
India

## Dependencies
- l10n_in
- sale

## Key Models

### `SaleOrder` (`sale.order`) — sale_order.py
- `_inherit = "sale.order"`
- `l10n_in_reseller_partner_id` — Many2one `res.partner`, domain on partners with VAT
- `l10n_in_gst_treatment` — Selection: regular, composition, unregistered, consumer, overseas, special_economic_zone, deemed_export, uin_holders. Computed, stored, precomputed.
- `_compute_fiscal_position_id()` — EXTENDS sale:
  - Computes Place of Supply (POS) as partner's shipping state
  - If POS state = company state → intra-state (CGST+SGST fiscal position)
  - If POS state != company state → inter-state (IGST fiscal position)
  - SEZ treatment: uses foreign_state (overseas/SEZ → IGST at 0%)
  - Foreign (non-India) → foreign_state
  - Groups by fiscal state then by company to avoid multi-company conflicts
- `_compute_l10n_in_gst_treatment()` — `@api.depends('partner_id')`:
  - overseas if partner country != India
  - regular if partner has VAT (GSTIN)
  - consumer if no GSTIN
- `_prepare_invoice()` — carries `l10n_in_reseller_partner_id` and `l10n_in_gst_treatment` to the invoice

## Data Files
- `views/report_sale_order.xml` — Sale order print with GST fields
- `views/sale_views.xml` — SO form with GST treatment and reseller fields
- `data/product_demo.xml` — Demo products with HSN codes

## GST Treatment and Fiscal Position on Sales
The `_compute_fiscal_position_id` override in `SaleOrder` is the primary mechanism for applying Indian GST fiscal positions on sales documents, before the invoice is created. The invoice inherits the fiscal position from the SO.

**Fiscal Position Logic:**
1. SEZ customer → foreign_state → IGST 0% (via `fiscal_position_in_sez` or `fiscal_position_in_export_sez_in`)
2. Overseas (export) → foreign_state → IGST 0% with LUT (via `fiscal_position_in_lut_sez`)
3. Inter-state (different state from company) → IGST
4. Intra-state (same state as company) → CGST+SGST

## Installation
`auto_install = True`. Auto-installs with `l10n_in` + `sale`.

## Historical Notes
Version 1.0 in Odoo 18. Key change from Odoo 17: fiscal position computation moved from `account.move` into `sale.order` so that the correct tax is shown in the Sale Order quotation itself, not just the final invoice.