---
Module: website_sale_gelato
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_sale_gelato #ecommerce #gelato
---

## Overview

**Module:** `website_sale_gelato`
**Depends:** `sale_gelato`, `website_sale`
**Location:** `~/odoo/odoo18/odoo/addons/website_sale_gelato/`
**Purpose:** Integrates Gelato (print-on-demand service) with the eCommerce cart. Prevents mixing Gelato and non-Gelato physical products in the same order, syncs print images, sets eCommerce descriptions.

## Models

### `product.template` (website_sale_gelato/models/product_template.py)

Inherits: `product.template`

| Method | Decorator | Description |
|---|---|---|
| `_check_print_images_are_set_before_publishing()` | `@api.constrains('is_published')` | Raises `ValidationError` if a Gelato-linked product (`gelato_template_ref` set) is published without print images (`gelato_missing_images`) |
| `action_create_product_variants_from_gelato_template()` | action | Extends parent; unpublishes products if Gelato sync created new print images |
| `_create_attributes_from_gelato_info(template_info)` | business | Sets `description_ecommerce` from Gelato template info before calling super |

### `product.document` (website_sale_gelato/models/product_document.py)

Inherits: `product.document`

| Method | Decorator | Description |
|---|---|---|
| `_check_product_is_unpublished_before_removing_print_images()` | `@api.constrains('datas')` | Prevents removing print image data from a published Gelato product |

### `sale.order` (website_sale_gelato/models/sale_order.py)

Inherits: `sale.order`

| Method | Decorator | Description |
|---|---|---|
| `_verify_updated_quantity()` | override | Returns `0, warning` if adding a Gelato product to a cart with non-Gelato physical products (or vice versa) |

## Security / Data

No `ir.model.access.csv`. Data files:
- `delivery_carrier_data.xml` — demo Gelato-compatible delivery carrier

## Critical Notes

- v17→v18: No breaking changes known.
- Gelato is a print-on-demand service — physical products that are printed after order.
- The key business rule: Gelato physical products CANNOT be mixed with non-Gelato physical products in one cart (separate shipping required).
- Service-type products are excluded from this mixing check.
- Print images are synchronized from Gelato and must be set before publishing.
- Product documents flagged as `is_gelato` have additional unpublish-before-deletion protection.