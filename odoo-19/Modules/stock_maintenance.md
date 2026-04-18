---
title: "Stock Maintenance"
module: stock_maintenance
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Stock Maintenance

## Overview

Module `stock_maintenance` — auto-generated from source code.

**Source:** `addons/stock_maintenance/`
**Models:** 2
**Fields:** 3
**Methods:** 2

## Models

### maintenance.equipment (`maintenance.equipment`)

—

**File:** `maintenance.py` | Class: `MaintenanceEquipment`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `location_id` | `Many2one` | Y | — | — | — | — |
| `match_serial` | `Boolean` | Y | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_open_matched_serial` | |


### stock.location (`stock.location`)

—

**File:** `stock_location.py` | Class: `StockLocation`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `equipment_count` | `Integer` | Y | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_view_equipments_records` | |




## Related

- [[Modules/Base]]
- [[Modules/Stock]]
