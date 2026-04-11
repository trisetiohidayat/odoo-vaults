---
Module: website_sale_stock_wishlist
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_sale_stock_wishlist #ecommerce #wishlist
---

## Overview

**Module:** `website_sale_stock_wishlist`
**Depends:** `website_sale_wishlist`, `website_sale_stock`
**Location:** `~/odoo/odoo18/odoo/addons/website_sale_stock_wishlist/`
**Purpose:** Adds stock-aware wishlist — shows whether a product is in the user's wishlist alongside stock info in the combination info.

## Models

### `product.wishlist` (website_sale_stock_wishlist/models/product_wishlist.py)

Inherits: `product.wishlist`

| Field | Type | Description |
|---|---|---|
| `stock_notification` | Boolean | Computed `_compute_stock_notification`; default `False`; `required=True`; inverse `_inverse_stock_notification` |

| Method | Decorator | Description |
|---|---|---|
| `_compute_stock_notification()` | `@api.depends('product_id', 'partner_id')` | Sets `True` if `product_id._has_stock_notification(partner_id)` returns True |
| `_inverse_stock_notification()` | inverse | On `True`: adds `partner_id` to `product_id.stock_notification_partner_ids` |

### `product.template` (website_sale_stock_wishlist/models/product_template.py)

Inherits: `product.template`

| Method | Decorator | Description |
|---|---|---|
| `_get_additionnal_combination_info()` | override | When `website_sale_stock_wishlist_get_wish` context is set: adds `is_in_wishlist` boolean to combination info using `product_or_template._is_in_wishlist()` |

## Security / Data

No `ir.model.access.csv`. No data XML files.

## Critical Notes

- v17→v18: No breaking changes.
- The `stock_notification` field bridges wishlist entries and product stock notification subscriptions.
- `website_sale_stock_wishlist_get_wish` context flag controls whether wishlist check is performed (to avoid N+1 queries).