---
title: "Product Margin"
module: product_margin
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Product Margin

## Overview

Module `product_margin` — auto-generated from source code.

**Source:** `addons/product_margin/`
**Models:** 1
**Fields:** 17
**Methods:** 0

## Models

### product.product (`product.product`)

Inherit _read_group to calculate the sum of the non-stored fields, as it is not automatically done anymore through the XML.

**File:** `product_product.py` | Class: `ProductProduct`

#### Fields (17)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `date_from` | `Date` | Y | — | — | — | — |
| `date_to` | `Date` | Y | — | — | — | — |
| `invoice_state` | `Selection` | Y | — | — | — | — |
| `sale_avg_price` | `Float` | Y | — | — | — | — |
| `purchase_avg_price` | `Float` | Y | — | — | — | — |
| `sale_num_invoiced` | `Float` | Y | — | — | — | — |
| `purchase_num_invoiced` | `Float` | Y | — | — | — | — |
| `sales_gap` | `Float` | Y | — | — | — | — |
| `purchase_gap` | `Float` | Y | — | — | — | — |
| `turnover` | `Float` | Y | — | — | — | — |
| `total_cost` | `Float` | Y | — | — | — | — |
| `sale_expected` | `Float` | Y | — | — | — | — |
| `normal_cost` | `Float` | Y | — | — | — | — |
| `total_margin` | `Float` | Y | — | — | — | — |
| `expected_margin` | `Float` | Y | — | — | — | — |
| `total_margin_rate` | `Float` | Y | — | — | — | — |
| `expected_margin_rate` | `Float` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/Base](base.md)
