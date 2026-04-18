---
title: "Account Fleet"
module: account_fleet
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Account Fleet

## Overview

Module `account_fleet` — auto-generated from source code.

**Source:** `addons/account_fleet/`
**Models:** 4
**Fields:** 9
**Methods:** 4

## Models

### account.move (`account.move`)

—

**File:** `account_move.py` | Class: `AccountMove`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### fleet.vehicle.log.services (`fleet.vehicle.log.services`)

—

**File:** `account_move.py` | Class: `AccountMoveLine`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `vehicle_id` | `Many2one` | Y | — | — | — | — |
| `need_vehicle` | `Boolean` | Y | — | — | — | — |
| `vehicle_log_service_ids` | `One2many` | Y | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `write` | |
| `unlink` | |


### fleet.vehicle (`fleet.vehicle`)

—

**File:** `fleet_vehicle.py` | Class: `FleetVehicle`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `bill_count` | `Integer` | Y | — | — | — | — |
| `account_move_ids` | `One2many` | Y | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_view_bills` | |


### account.move.line (`account.move.line`)

—

**File:** `fleet_vehicle_log_services.py` | Class: `FleetVehicleLogServices`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `account_move_line_id` | `Many2one` | Y | — | Y | — | — |
| `account_move_state` | `Selection` | Y | — | Y | Y | — |
| `amount` | `Monetary` | Y | — | — | Y | — |
| `vehicle_id` | `Many2one` | Y | — | — | Y | Y |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_open_account_move` | |




## Related

- [Modules/Base](base.md)
- [Modules/Account](Account.md)
