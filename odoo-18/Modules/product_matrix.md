---
Module: product_matrix
Version: 18.0.0
Type: addon
Tags: #odoo18 #product #matrix #website #sale
---

## Overview

Adds product matrix grid support to the e-commerce product configurator. Generates a grid data structure from `product.template.attribute.value` combinations for the website product page matrix widget.

**Depends:** `website_sale`, `sale_product_matrix`

**Key Behavior:** The matrix is rendered as a dynamic table on the product configurator page. Each cell represents a valid attribute value combination and its variant.

---

## Models

### `product.template` (Inherited)

**Inherited from:** `product.template`

| Method | Returns | Note |
|--------|---------|------|
| `_get_template_matrix(...)` | dict | Builds grid structure: header rows (attribute values), body rows (variant info + price) |

### `product.template.attribute.value` (Inherited)

**Inherited from:** `product.template.attribute.value`

| Method | Returns | Note |
|--------|---------|------|
| `_grid_header_cell(value, position)` | dict | Formats header cell: value name, price extra, currency-converted price |
