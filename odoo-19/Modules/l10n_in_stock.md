# India - Stock Management (`l10n_in_stock`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | India - Stock Management |
| **Technical** | `l10n_in_stock` |
| **Category** | Accounting/Localizations/Warehouse |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_in`, `stock` |

## Description
Indian warehouse accounting localization. Provides base hooks for GST-linked stock operations (e-Waybill, fiscal position, dropship destination) and forces commercial invoice generation on all pickings. Used as a base for other Indian stock modules (`l10n_in_purchase_stock`, `l10n_in_sale_stock`, `l10n_in_ewaybill_stock`).

## Technical Notes
- Country code: `in` (India)
- Core concern: GST compliance for warehouse operations

## Models

### `stock.picking` (Extended)
**`_should_generate_commercial_invoice()`** — OVERRIDES `stock`. Always returns `True` — forces commercial invoice generation for all Indian pickings (required for GST e-Waybill)

**`_get_l10n_in_dropship_dest_partner()`** — Placeholder stub. Override by `l10n_in_purchase_stock` to return dropship destination from purchase order

**`_l10n_in_get_invoice_partner()`** — Placeholder stub. Override by `l10n_in_sale_stock` to return invoice partner from sale order

**`_l10n_in_get_fiscal_position()`** — Placeholder stub. Override by `l10n_in_*_stock` modules to return fiscal position from order

### `stock.move` (Extended)
**`_l10n_in_get_product_price_unit()`** — Returns product's standard price converted to the move's UoM

**`_l10n_in_get_product_tax()`** — Returns tax ids from `product_id.supplier_taxes_id` (for incoming) or `product_id.taxes_id` (for outgoing)

## Related
- [[Modules/l10n_in]] — Core Indian accounting
- [[Modules/l10n_in_purchase_stock]] — Purchase-stock bridge with GST
- [[Modules/l10n_in_sale]] — Sale order GST handling
