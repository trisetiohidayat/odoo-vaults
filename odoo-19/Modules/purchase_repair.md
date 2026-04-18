---
title: "Purchase Repair"
module: purchase_repair
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Purchase Repair

## Overview

Module `purchase_repair` — auto-generated from source code.

**Source:** `addons/purchase_repair/`
**Models:** 2
**Fields:** 2
**Methods:** 2

## Models

### purchase.order (`purchase.order`)

—

**File:** `purchase_order.py` | Class: `PurchaseOrder`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `repair_count` | `Integer` | Y | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_view_repair_orders` | |


### repair.order (`repair.order`)

—

**File:** `repair_order.py` | Class: `RepairOrder`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `purchase_count` | `Integer` | Y | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_view_purchase_orders` | |




## Related

- [Modules/Base](base.md)
- [Modules/Purchase](Purchase.md)
