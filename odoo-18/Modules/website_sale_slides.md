---
Module: website_sale_slides
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_sale_slides #ecommerce #elearning
---

## Overview

**Module:** `website_sale_slides`
**Depends:** `website_sale`, `website_slides`
**Location:** `~/odoo/odoo18/odoo/addons/website_sale_slides/`
**Purpose:** Sells eLearning courses as products. On order confirmation, grants course membership. Adds `course` service tracking type and `payment` enrollment mode.

## Models

### `product.template` (website_sale_slides/models/product_template.py)

Inherits: `product.template`

| Field | Type | Description |
|---|---|---|
| `service_tracking` | Selection | Extended: adds `'course'` ("Course Access") — ondelete: `'set default'` |

| Method | Decorator | Description |
|---|---|---|
| `_prepare_service_tracking_tooltip()` | override | Returns tooltip "Grant access to the eLearning course linked to this product" for `course` type |
| `_get_product_types_allow_zero_price()` | override | Adds `'course'` to zero-price allowed product types |
| `_service_tracking_blacklist()` | override | Adds `'course'` to blacklisted types (course products don't create tasks/projects) |

### `product.product` (website_sale_slides/models/product_product.py)

Inherits: `product.product`

| Field | Type | Description |
|---|---|---|
| `channel_ids` | One2many (`slide.channel`) | "Courses" — courses linked to this product (via `product_id` on channel) |

| Method | Decorator | Description |
|---|---|---|
| `_is_add_to_cart_allowed()` | override | Also allows products linked to published `slide.channel` (payment-based courses are always addable) |
| `get_product_multiline_description_sale()` | override | Appends "Access to: [course names]" for products linked to payment channels |

### `sale.order` (website_sale_slides/models/sale_order.py)

Inherits: `sale.order`

| Method | Decorator | Description |
|---|---|---|
| `_action_confirm()` | override | On order confirm: searches order lines for products linked to `payment`-enroll channels; calls `slide.channel._action_add_members(partner_id)` for each matching channel |
| `_verify_updated_quantity()` | override | Returns `1, warning` if user tries to add a course product more than once to the cart |

### `slide.channel` (website_sale_slides/models/slide_channel.py)

Inherits: `slide.channel`

| Field | Type | Description |
|---|---|---|
| `enroll` | Selection | Extended: adds `'payment'` ("On payment") — ondelete: sets `enroll='invite'` |
| `product_id` | Many2one (`product.product`) | Required when `enroll='payment'`; domain: `service_tracking='course'` |
| `product_sale_revenues` | Monetary (compute, group: `sales_team.group_sale_salesman`) | Total revenues from sales reports for this channel's product |
| `currency_id` | Many2one | Related to `product_id.currency_id` |

SQL Constraints:
- `product_id_check`: `CHECK(enroll != 'payment' OR product_id IS NOT NULL)` — product required for payment channels

| Method | Decorator | Description |
|---|---|---|
| `_get_default_product_id()` | `@api.model` | Searches for products with `service_tracking='course'`; returns ID if exactly one found |
| `_compute_product_sale_revenues()` | `@api.depends('product_id')` | Aggregates `price_total` from `sale.report` for the channel's product |
| `create()` | `@api.model_create_multi` | Syncs product publication for `payment` enrollment channels |
| `write()` | override | Syncs product publication when `is_published` changes on `payment` channels |
| `_synchronize_product_publish()` | private | Publishes product when channel is published; unpublishes product when all linked channels are unpublished |
| `action_view_sales()` | action | Opens sale report filtered to channel's product |
| `_filter_add_members()` | override | Adds `payment` channels to filtered result if user has write access (allows public purchase to grant access) |

## Security / Data

No `ir.model.access.csv`. Data files:
- `product_data.xml`, `product_demo.xml` — demo course products
- `sale_order_demo.xml` — demo sales of courses
- `slide_demo.xml` — demo slides/channels

## Critical Notes

- v17→v18: No breaking changes known.
- `enroll='payment'` is the key bridge: a course product links a `product.product` to a `slide.channel` with payment-based enrollment.
- Course can only be added once to cart (`_verify_updated_quantity` blocks qty > 1).
- Product publication is automatically synced with channel publication (bidirectional).
- `_filter_add_members` override: anyone with write access on the channel can add members, not just instructors.