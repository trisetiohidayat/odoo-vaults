---
Module: website_event_sale
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_sale
---

## Overview

Integrates event ticket sales with the e-commerce website cart. Tickets are sold as products with seat availability checking, automatic registration creation, and abandoned cart reminders (excluding sold-out events).

**Key Dependencies:** `event_sale`, `website_event`, `sale`

**Python Files:** 4 model files

---

## Models

### product_template.py — ProductTemplate (extension)

**Inheritance:** `product.template`

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_get_product_types_allow_zero_price()` | `@api.model` | Adds `"event"` to product types allowed at zero price |

---

### product_product.py — ProductProduct

**Inheritance:** `product.product` (standalone definition for access rules)

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `event_ticket_ids` | One2many | Yes | `event.event.ticket` records using this product |

**Methods:**

| Method | Description |
|--------|-------------|
| `_is_add_to_cart_allowed()` | Returns True if any ticket's event is `website_published` |

---

### sale_order.py — SaleOrder

**Inheritance:** `sale.order`

| Method | Description |
|--------|-------------|
| `_cart_find_product_line(product_id, line_id, event_ticket_id, **kwargs)` | Finds existing line matching the same event ticket |
| `_verify_updated_quantity(order_line, product_id, new_qty, event_ticket_id, **kwargs)` | Validates seat availability; warns on sold-out or insufficient seats; forbids qty increase beyond available |
| `_prepare_order_line_values(product_id, quantity, event_ticket_id, **kwargs)` | Adds `event_id` and `event_ticket_id` to line values |
| `_update_cart_line_values(order_line, update_values)` | On qty decrease: cancels excess `event.registration` records |
| `_filter_can_send_abandoned_cart_mail()` | Excludes carts where any ticket is sold out or expired |

---

### product_pricelist.py — PricelistItem

**Inheritance:** `product.pricelist.item`

| Method | Description |
|--------|-------------|
| `_onchange_event_sale_warning()` | Onchange on `applied_on`, `product_id`, `product_tmpl_id`, `min_quantity` — warns that min_quantity > 0 won't apply to event tickets |

---

## Security / Data

**Security File:** `security/website_event_sale_security.xml`

- `event_product_template_public`: Public/portal can read product templates linked to published event tickets

**Data Files:**
- `data/event_data.xml`: Demo event ticket products

---

## Critical Notes

- `_verify_updated_quantity` uses `seats_available` (real-time remaining seats) not `seats_reserved`
- On qty decrease: registrations are cancelled in FIFO order (`offset=new_qty, limit=old_qty-new_qty`)
- Abandoned cart check: `sale_available` on ticket must be True for all lines
- `event_ticket_id` on sale order line links the cart item to a specific ticket type
- `website_published` check ensures unpublished events can't sell via website even if product exists
- v17→v18: `sale_available` field on tickets replaced older availability logic; abandoned cart filter improved
