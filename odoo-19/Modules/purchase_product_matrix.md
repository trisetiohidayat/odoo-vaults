---
title: "Purchase Product Matrix"
module: purchase_product_matrix
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Purchase Product Matrix

## Overview

Module `purchase_product_matrix` — auto-generated from source code.

**Source:** `addons/purchase_product_matrix/`
**Models:** 2
**Fields:** 8
**Methods:** 1

## Models

### purchase.order (`purchase.order`)

Matrix loading and update: fields and methods :

    NOTE: The matrix functionality was done in python, server side, to avoid js
        restriction.  Indeed, the js framework only loads the x first l

**File:** `purchase.py` | Class: `PurchaseOrder`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `report_grids` | `Boolean` | — | — | — | — | — |
| `grid_product_tmpl_id` | `Many2one` | — | — | — | Y | — |
| `grid_update` | `Boolean` | — | — | — | Y | — |
| `grid` | `Char` | — | Y | — | Y | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `get_report_matrixes` | |


### purchase.order.line (`purchase.order.line`)

—

**File:** `purchase.py` | Class: `PurchaseOrderLine`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `product_template_id` | `Many2one` | — | — | Y | — | — |
| `is_configurable_product` | `Boolean` | — | — | Y | — | — |
| `product_template_attribute_value_ids` | `Many2many` | — | — | Y | — | — |
| `product_no_variant_attribute_value_ids` | `Many2many` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/Purchase](Purchase.md)
