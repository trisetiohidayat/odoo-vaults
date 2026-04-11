---
Module: website_sale_comparison_wishlist
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_sale_comparison_wishlist #ecommerce
---

## Overview

**Module:** `website_sale_comparison_wishlist`
**Depends:** `website_sale_comparison`, `website_sale_wishlist`
**Location:** `~/odoo/odoo18/odoo/addons/website_sale_comparison_wishlist/`
**Purpose:** No Python models. This is a pure XML/JS module that adds a "Add to Wishlist" button on the product comparison page. Acts as a bridge between `website_sale_comparison` and `website_sale_wishlist`.

## Models

None.

## Security / Data

No Python models, no `ir.model.access.csv`, no data files.

## Critical Notes

- This is a frontend-only bridge module with no server-side Python code.
- It inherits XML templates from `website_sale_comparison` and `website_sale_wishlist`.
- To understand its behavior, inspect the `views/templates.xml` and `static/` files in the module directory.