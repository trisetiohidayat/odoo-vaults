---
Module: website_sale_mrp
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_sale_mrp #ecommerce #mrp #kits
---

## Overview

**Module:** `website_sale_mrp`
**Depends:** `website_sale`, `mrp`
**Location:** `~/odoo/odoo18/odoo/addons/website_sale_mrp/`
**Purpose:** Integrates kit/MoC (manufacture to order) product availability with eCommerce cart — computes unavailable kit quantities caused by other cart lines, so out-of-stock warnings are accurate.

## Models

### `sale.order` (website_sale_mrp/models/sale_order.py)

Inherits: `sale.order`

| Method | Decorator | Description |
|---|---|---|
| `_get_unavailable_quantity_from_kits(product)` | private | Recursively computes how many units of a `is_kits` product become unavailable due to other kit lines in the same cart. Uses BoM explode to track component consumption. Handles nested kits (kits containing kits). Returns `unavailable_qty`. |

**Algorithm detail:**
1. Explode the product's BoM to get component requirements.
2. Track other kit lines in the order that consume the same components.
3. Compute max free kit qty from component availability.
4. `unavailable_qty = free_qty - max_free_kit_qty` for the product.
5. For nested kits: update `unavailable_component_qties` as components are consumed.

## Security / Data

No `ir.model.access.csv`. No data XML files.

## Critical Notes

- v17→v18: No breaking changes.
- This module addresses the "kit availability" problem: if a kit product has 5 available units but your cart already has 3 of another kit that shares a component, the kit's effective availability is less than 5.
- The `_get_unavailable_quantity_from_kits` method is called by `website_sale_stock` availability checks.
- Key fields used: `is_kits` on `product.product` (from `mrp` module), `_bom_find` with `bom_type='phantom'`.