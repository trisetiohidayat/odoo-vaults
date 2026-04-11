# website_sale_gelato

Odoo 19 Website/e-Commerce Module

## Overview

`website_sale_gelato` is a **bridge module** between `sale_gelato` (Gelato print-on-demand integration) and `website_sale` (e-Commerce). Ensures Gelato products are properly displayed and purchasable on the Odoo website.

## Module Details

- **Category**: Website/Website
- **Depends**: `sale_gelato`, `website_sale`
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Auto-install**: Yes

## Key Components

### Models

#### `product.document` (Inherited)

| Field | Type | Description |
|---|---|---|
| `is_gelato` | Boolean (readonly) | Marks a document as a Gelato print image |

**Constraints:**
- `_check_product_is_unpublished_before_removing_print_images()` — Products must be unpublished before Gelato print images can be removed.

#### `product.template` (Inherited)

- `_check_print_images_are_set_before_publishing()` — Cannot publish without print images.
- `action_create_product_variants_from_gelato_template()` — Unpublishes products when new print images are created.
- `_create_attributes_from_gelato_info()` — Also sets `description_ecommerce` from Gelato.

## Relationship to Other Modules

| Module | Role |
|---|---|
| `sale_gelato` | Core Gelato integration |
| `website_sale` | Website e-Commerce |
| `website_sale_gelato` | Website-specific Gelato bridge |

See also: `sale_gelato`, `sale_gelato_stock`
