---
Module: l10n_in_stock
Version: 18.0
Type: l10n/india
Tags: #odoo18 #l10n #accounting #stock #india
---

# l10n_in_stock — Indian Stock Report (GST)

## Overview
India-specific extension of the Stock module. Overrides stock picking behavior to enforce commercial invoice generation for all Indian pickings and defines overridable hooks for warehouse address, invoice partner, and fiscal position — enabling downstream EDI modules (e-invoice, e-waybill) to resolve these values from the stock operation.

## Country
India

## Dependencies
- l10n_in
- stock

## Key Models

### `StockPicking` (`stock.picking`) — stock_picking.py
- `_inherit = 'stock.picking'`
- `_should_generate_commercial_invoice()` — OVERRIDE: returns `True` unconditionally. Ensures every Indian stock picking generates a commercial invoice (required for GST compliance and e-waybill).
- `_get_l10n_in_dropship_dest_partner()` — stub method (returns `pass`). Overridable hook for `l10n_in_purchase_stock` to return destination partner from purchase order.
- `_l10n_in_get_invoice_partner()` — stub method. Overridable hook for downstream modules (l10n_in_purchase_stock, l10n_in_sale_stock) to return invoice partner from linked order.
- `_l10n_in_get_fiscal_position()` — stub method. Overridable hook for downstream modules to return fiscal position from linked order.

### `StockMove` (`stock.move`) — stock_move.py
- `_inherit = "stock.move"`
- `_l10n_in_get_product_price_unit()` — returns product's standard price converted to the move's UOM (calls `product_id.uom_id._compute_price(standard_price, product_uom)`)
- `_l10n_in_get_product_tax()` — returns taxes for the move:
  - Incoming (incoming transfer / receipt): uses `product_id.supplier_taxes_id`
  - Outgoing: uses `product_id.taxes_id` (sale taxes)
  - Returns dict with `is_from_order: False` flag (vs order-based tax fetching)

## Data Files
- `views/report_stockpicking_operations.xml` — Picking operation report with Indian GST fields
- `data/product_demo.xml` — Demo products with Indian-specific data
- Note: `l10n_in_purchase_stock` and `l10n_in_sale_stock` override the stub hooks in `StockPicking`

## Commercial Invoice Requirement
Indian GST requires a commercial invoice for all goods movements. By overriding `_should_generate_commercial_invoice()` to always return `True`, this module ensures stock transfers trigger invoice generation even for internal moves.

## Hook Pattern (Stub Methods)
The three stub methods (`_get_l10n_in_dropship_dest_partner`, `_l10n_in_get_invoice_partner`, `_l10n_in_get_fiscal_position`) define a hook interface that:
- `l10n_in_purchase_stock` overrides for purchase-side pickings (PO → receipt)
- `l10n_in_sale_stock` overrides for sale-side pickings (SO → delivery)
- `l10n_in_ewaybill` (if installed) uses these hooks for e-waybill JSON generation

This pattern avoids circular dependencies and keeps each module focused.

## Installation
`auto_install = True`. Auto-installs with `l10n_in` + `stock`.

## Historical Notes
Version 1.0 in Odoo 18. The stub method pattern was introduced in Odoo 18 to replace the direct Many2one linking approach in earlier versions. Cleaner separation of concerns.