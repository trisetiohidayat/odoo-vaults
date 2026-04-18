---
title: "Hr Fleet"
module: hr_fleet
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Hr Fleet

## Overview

Module `hr_fleet` — auto-generated from source code.

**Source:** `addons/hr_fleet/`
**Models:** 9
**Fields:** 15
**Methods:** 9

## Models

### hr.employee (`hr.employee`)

—

**File:** `employee.py` | Class: `HrEmployee`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `employee_cars_count` | `Integer` | Y | — | — | — | — |
| `car_ids` | `One2many` | Y | — | — | — | — |
| `license_plate` | `Char` | Y | — | — | — | — |
| `mobility_card` | `Char` | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `action_open_employee_cars` | |
| `write` | |


### hr.employee.public (`hr.employee.public`)

—

**File:** `employee.py` | Class: `HrEmployeePublic`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `mobility_card` | `Char` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### fleet.vehicle (`fleet.vehicle`)

—

**File:** `fleet_vehicle.py` | Class: `FleetVehicle`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `mobility_card` | `Char` | Y | — | — | Y | — |
| `driver_employee_id` | `Many2one` | Y | — | — | Y | — |
| `driver_employee_name` | `Char` | Y | — | Y | Y | — |
| `future_driver_employee_id` | `Many2one` | Y | — | — | Y | — |


#### Methods (4)

| Method | Description |
|--------|-------------|
| `create` | |
| `write` | |
| `action_open_employee` | |
| `open_assignation_logs` | |


### fleet.vehicle.assignation.log (`fleet.vehicle.assignation.log`)

—

**File:** `fleet_vehicle_assignation_log.py` | Class: `FleetVehicleAssignationLog`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `driver_employee_id` | `Many2one` | Y | — | — | Y | — |
| `attachment_number` | `Integer` | Y | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_get_attachment_view` | |


### fleet.vehicle.log.contract (`fleet.vehicle.log.contract`)

—

**File:** `fleet_vehicle_log_contract.py` | Class: `FleetVehicleLogContract`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `purchaser_employee_id` | `Many2one` | — | — | Y | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_open_employee` | |


### fleet.vehicle.log.services (`fleet.vehicle.log.services`)

—

**File:** `fleet_vehicle_log_services.py` | Class: `FleetVehicleLogServices`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `purchaser_employee_id` | `Many2one` | Y | — | — | Y | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### fleet.vehicle.odometer (`fleet.vehicle.odometer`)

—

**File:** `fleet_vehicle_odometer.py` | Class: `FleetVehicleOdometer`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `driver_employee_id` | `Many2one` | — | — | Y | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### ir.attachment (`ir.attachment`)

—

**File:** `ir_attachment.py` | Class: `IrAttachment`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_preview_attachment` | |


### mail.activity.plan.template (`mail.activity.plan.template`)

Ensure that hr types are used only on employee model

**File:** `mail_activity_plan_template.py` | Class: `MailActivityPlanTemplate`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `responsible_type` | `Selection` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/HR](HR.md)
