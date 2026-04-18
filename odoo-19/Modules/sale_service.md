---
title: "Sale Service"
module: sale_service
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Sale Service

## Overview

Module `sale_service` — auto-generated from source code.

**Source:** `addons/sale_service/`
**Models:** 1
**Fields:** 1
**Methods:** 1

## Models

### sale.order.line (`sale.order.line`)

Get the default generic services domain for sale.order.line.
        You can filter out domain leafs by passing kwargs of the form 'check_<leaf_field>=False'.
        Only 'is_service' cannot be disab

**File:** `sale_order_line.py` | Class: `SaleOrderLine`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `is_service` | `Boolean` | Y | — | — | Y | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `name_search` | |




## Related

- [Modules/Base](base.md)
- [Modules/Sale](Sale.md)
