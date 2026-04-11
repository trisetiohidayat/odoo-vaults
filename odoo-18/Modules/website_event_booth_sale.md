---
Module: website_event_booth_sale
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_booth_sale
---

## Overview

Integrates event booth bookings with the e-commerce (sale) workflow. Allows booths to be sold as products through the website shop cart. Extends `sale.order` and `sale.order.line` to handle booth-specific cart operations.

**Key Dependencies:** `website_event_booth`, `sale`, `product`

**Python Files:** 4 model files

---

## Models

### product_template.py — ProductTemplate

**Inheritance:** `product.template`

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_get_product_types_allow_zero_price()` | `@api.model` | Returns product types that can be added at zero price — adds `"event_booth"` to the list |

---

### product_product.py — ProductProduct

**Inheritance:** `product.product`

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_is_add_to_cart_allowed()` | — | Allows adding to cart if the product is a booth category (even if product rules would normally block it) |

---

### sale_order.py — SaleOrder

**Inheritance:** `sale.order`

| Method | Parameters | Description |
|--------|------------|-------------|
| `_cart_find_product_line()` | `product_id, line_id, event_booth_pending_ids, **kwargs` | Overrides parent to find existing SO lines by `event_booth_pending_ids` matching — avoids duplicate booth reservations |
| `_verify_updated_quantity()` | `order_line, product_id, new_qty, **kwargs` | Forbids qty > 1 on event booth lines (booths are 1-per-line) |
| `_prepare_order_line_values()` | `product_id, quantity, event_booth_pending_ids, registration_values, **kwargs` | Adds `event_id` and `event_booth_registration_ids` (Command.create) to the line values |
| `_prepare_order_line_update_values()` | `order_line, quantity, event_booth_pending_ids, registration_values, **kwargs` | Deletes existing booth registrations and creates new ones on update (supports booth replacement) |

---

## Security / Data

No dedicated security XML or data files in this module.

---

## Critical Notes

- Booth products use `service_tracking = 'event_booth'` on their product variant
- `_cart_find_product_line` filters by booth IDs to avoid double-booking: `any(booth.id in event_booth_pending_ids for booth in line.event_booth_pending_ids)`
- `_verify_updated_quantity` enforces max qty=1 per booth product line
- `event_booth_registration_ids` on the sale order line links the SO to individual booth registrations
- Registration values (sponsor name, email, etc.) from `website_event_booth_sale_exhibitor` are passed through `registration_values` parameter
- v17→v18: Sale order line integration for booths was refactored to use `Command` for registration management
