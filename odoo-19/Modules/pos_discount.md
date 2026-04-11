# POS Discount

## Overview
- **Name:** Point of Sale Discounts
- **Category:** Sales/Point of Sale
- **Depends:** `point_of_sale`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
Allows the cashier to quickly give percentage-based discounts on the whole order. Adds a "Discount" button to the POS interface with a configurable default percentage.

## Models

### `pos.config` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `iface_discount` | Boolean | Enable order discounts |
| `discount_pc` | Float | Default discount percentage (default: 10.0) |
| `discount_product_id` | Many2one | Product used to apply the discount |

## Key Features
- Global order-level discount button in POS UI
- Configurable default discount percentage per POS config
- Uses a dedicated discount product recorded on the order line
- Discount validation: checks for discount product before opening session

## Hooks
- `open_ui` — Validates that a discount product is set before opening POS
- `_get_special_products()` — Includes discount products in POS special products

## Data Files
- `data/pos_discount_data.xml` — Default discount product
- `views/res_config_settings_views.xml` — Settings view
- `views/pos_config_views.xml` — POS config form extension

## Related
- [[Modules/point_of_sale]] — Base POS module
