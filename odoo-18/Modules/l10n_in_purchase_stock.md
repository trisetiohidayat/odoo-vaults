---
Module: l10n_in_purchase_stock
Version: 18.0
Type: l10n/india
Tags: #odoo18 #l10n #accounting #purchase #stock #india
---

# l10n_in_purchase_stock — Indian Purchase and Warehouse Management

## Overview
Extension bridging [Modules/l10n_in_purchase](l10n_in_purchase.md) + [Modules/l10n_in_stock](l10n_in_stock.md) + `purchase_stock`. Adds the warehouse address to vendor bills created from Purchase Orders — a legal requirement in Indian GST for determining the place of supply and validating the originating warehouse.

## Country
India

## Dependencies
- l10n_in_purchase
- l10n_in_stock
- purchase_stock

## Key Models

### `AccountMove` (`account.move`) — account_move.py
- `_inherit = "account.move"`
- Inherits GST treatment logic from `l10n_in_purchase`

### `StockMove` (`stock.move`) — stock_move.py
- `_inherit = "stock.move"`
- `_l10n_in_get_product_price_unit()` — returns product's standard price in stock move's product UOM (calls `product_id.uom_id._compute_price()`)
- `_l10n_in_get_product_tax()` — returns taxes from product supplier taxes (incoming) or sale taxes (outgoing), flagged with `is_from_order: False`

### `StockPicking` (`stock.picking`) — stock_picking.py
- `_inherit = 'stock.picking'`
- Overrides `_l10n_in_get_invoice_partner()` — returns partner from purchase order (used by EDI/e-waybill for invoice partner identification)
- Overrides `_l10n_in_get_fiscal_position()` — returns fiscal position from purchase order

## Data Files
None (pure code module).

## Warehouse Address Flow
1. Purchase Order created with vendor → warehouse assigned
2. Vendor bill created from PO → `_onchange_purchase_auto_complete()` from `l10n_in_purchase` copies GST treatment
3. `l10n_in_purchase_stock` overrides `_l10n_in_get_warehouse_address()` (via `l10n_in_stock` base) to read warehouse address from PO and inject into the invoice (used in e-invoice JSON generation in [Modules/l10n_in_edi](l10n_in_edi.md))

## Installation
`auto_install = True`. Auto-installs as part of the Indian purchase-stock accounting stack.

## Historical Notes
Version 1.0 in Odoo 18. New module pattern in Odoo 18: split purchase-stock integration into its own module rather than embedding in `l10n_in_purchase`. Enables cleaner dependency chains.