---
Module: website_sale_comparison
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_sale_comparison #ecommerce
---

## Overview

**Module:** `website_sale_comparison`
**Depends:** `website_sale`
**Location:** `~/odoo/odoo18/odoo/addons/website_sale_comparison/`
**Purpose:** Enables product comparison on the eCommerce site. Adds attribute categories for grouping attributes in comparison view.

## Models

### `product.attribute.category` (website_sale_comparison/models/product_attribute_category.py)

**NEW MODEL** — not inheriting an existing model.

| Field | Type | Description |
|---|---|---|
| `name` | Char | Category name; required; translatable |
| `sequence` | Integer | Sort order; default `10`; indexed |
| `attribute_ids` | One2many (`product.attribute`) | Attributes in this category; domain: `category_id = False` |

SQL Constraints: `_order = 'sequence, id'`

### `product.attribute` (website_sale_comparison/models/product_attribute.py)

Inherits: `product.attribute`

| Field | Type | Description |
|---|---|---|
| `category_id` | Many2one (`product.attribute.category`) | eCommerce category; indexed; helps group attributes in comparison page |

Order: `category_id, sequence, id`

### `product.template.attribute.line` (website_sale_comparison/models/product_template_attribute_line.py)

Inherits: `product.template.attribute.line`

| Method | Decorator | Description |
|---|---|---|
| `_prepare_categories_for_display()` | public | Groups attribute lines by their attribute's `category_id`. Returns `OrderedDict[{category: [ptal...]}]`. Attributes without category go to empty-key bucket. |

### `product.product` (website_sale_comparison/models/product_product.py)

Inherits: `product.product`

| Method | Decorator | Description |
|---|---|---|
| `_prepare_categories_for_display()` | public | For comparison page: groups products' attribute values by category, then attribute. Returns `OrderedDict[{category: OrderedDict[{attribute: OrderedDict[{product: [ptav]}]}]}]`. |

## Security / Data

`ir.model.access.csv` present.

Data files:
- `website_sale_comparison_data.xml` — demo attribute categories and attribute assignments
- `website_sale_comparison_demo.xml` — demo data

## Critical Notes

- v17→v18: No breaking changes.
- `product.attribute.category` is a new Odoo model introduced by this module (not in base).
- The `_prepare_categories_for_display` override on `product.template.attribute.line` and `product.product` is the key presentation method used by the website comparison controller.
- Attribute categories are optional — unclassified attributes fall into a default bucket.