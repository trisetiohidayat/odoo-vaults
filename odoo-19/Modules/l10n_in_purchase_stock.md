# India - Purchase Stock (`l10n_in_purchase_stock`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | India - Purchase Stock |
| **Technical** | `l10n_in_purchase_stock` |
| **Category** | Accounting/Localizations/Warehouse |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_in_stock`, `purchase_stock` |

## Description
Bridge between Indian GST accounting, purchase orders, and warehouse management. Extends purchase-linked stock moves and pickings with GST-specific data: warehouse address resolution for e-invoices, product price derivation from purchase order for dropshipments, and fiscal position selection based on purchase order settings.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_in_stock` | Indian warehouse accounting |
| `purchase_stock` | Purchase order ↔ stock picking link |

## Technical Notes
- Country code: `in` (India)
- Concern: GST compliance for purchase-to-stock flow

## Models

### `stock.move` (Extended)
**`_l10n_in_get_product_price_unit()`** — Gets unit price from the related purchase order line, applying:
- Product UoM conversion (`product_uom_id._compute_price`)
- Currency conversion from PO currency to company currency

Used for Indian GST purchase valuation when warehouse moves are tied to purchase orders.

### `stock.picking` (Extended)
**`_get_l10n_in_dropship_dest_partner()`** — For dropship pickings linked to a purchase order, returns the `dest_address_id` (drop ship recipient) rather than the standard delivery address

**`_l10n_in_get_fiscal_position()`** — Returns the purchase order's fiscal position for the Indian picking, ensuring correct tax mapping (inter-state vs intra-state GST)

### `account.move` (Extended)
**`_l10n_in_get_warehouse_address()`** — EXTENDS `l10n_in`. When invoice lines are linked to a purchase order, the warehouse address is sourced from the `move_ids.warehouse_id.partner_id` of the purchase line (for purchase-linked deliveries), not just from standard inventory routes

## Related
- [[Modules/l10n_in_stock]] — Indian warehouse accounting
- [[Modules/l10n_in_purchase_stock]] — Indian purchase order accounting
- [[Modules/l10n_in]] — Core Indian accounting
- [[Modules/purchase_stock]] — Base purchase-stock bridge
