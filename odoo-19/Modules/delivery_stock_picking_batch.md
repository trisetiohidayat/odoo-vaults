---
title: "Delivery Stock Picking Batch"
module: delivery_stock_picking_batch
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Delivery Stock Picking Batch

## Overview

Module `delivery_stock_picking_batch` — auto-generated from source code.

**Source:** `addons/delivery_stock_picking_batch/`
**Models:** 3
**Fields:** 3
**Methods:** 0

## Models

### stock.picking.type (`stock.picking.type`)

—

**File:** `stock_picking.py` | Class: `StockPickingType`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `batch_group_by_carrier` | `Boolean` | — | — | — | — | — |
| `batch_max_weight` | `Integer` | — | — | — | — | — |
| `weight_uom_name` | `Char` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### stock.picking (`stock.picking`)

Verifies if a picking can be put in a batch with another picking without violating auto_batch constrains.

**File:** `stock_picking.py` | Class: `StockPicking`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### stock.picking.batch (`stock.picking.batch`)

Verifies if a picking can be safely inserted into the batch without violating auto_batch_constrains.

**File:** `stock_picking_batch.py` | Class: `StockPickingBatch`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/Base](base.md)
