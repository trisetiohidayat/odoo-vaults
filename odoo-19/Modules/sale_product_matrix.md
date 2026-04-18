---
title: "Sale Product Matrix"
module: sale_product_matrix
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Sale Product Matrix

## Overview

Module `sale_product_matrix` — auto-generated from source code.

**Source:** `addons/sale_product_matrix/`
**Models:** 3
**Fields:** 6
**Methods:** 2

## Models

### product.template (`product.template`)

—

**File:** `product_template.py` | Class: `ProductTemplate`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `product_add_mode` | `Selection` | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `get_single_product_variant` | |


### sale.order (`sale.order`)

Matrix loading and update: fields and methods :

    NOTE: The matrix functionality was done in python, server side, to avoid js
        restriction.  Indeed, the js framework only loads the x first l

**File:** `sale_order.py` | Class: `SaleOrder`

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


### sale.order.line (`sale.order.line`)

—

**File:** `sale_order_line.py` | Class: `SaleOrderLine`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `product_add_mode` | `Selection` | — | — | Y | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [[Modules/Base]]
- [[Modules/Sale]]
