---
title: "Mrp Landed Costs"
module: mrp_landed_costs
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Mrp Landed Costs

## Overview

Module `mrp_landed_costs` — auto-generated from source code.

**Source:** `addons/mrp_landed_costs/`
**Models:** 1
**Fields:** 2
**Methods:** 0

## Models

### stock.landed.cost (`stock.landed.cost`)

—

**File:** `stock_landed_cost.py` | Class: `StockLandedCost`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `target_model` | `Selection` | — | — | — | — | — |
| `mrp_production_ids` | `Many2many` | — | Y | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/MRP](MRP.md)
