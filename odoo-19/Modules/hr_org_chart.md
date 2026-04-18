---
title: "Hr Org Chart"
module: hr_org_chart
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Hr Org Chart

## Overview

Module `hr_org_chart` — auto-generated from source code.

**Source:** `addons/hr_org_chart/`
**Models:** 4
**Fields:** 10
**Methods:** 0

## Models

### hr.employee (`hr.employee`)

—

**File:** `hr_employee.py` | Class: `HrEmployee`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `subordinate_ids` | `One2many` | Y | — | — | — | — |
| `is_subordinate` | `Boolean` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### hr.employee.public (`hr.employee.public`)

—

**File:** `hr_employee.py` | Class: `HrEmployeePublic`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `subordinate_ids` | `One2many` | Y | — | Y | — | — |
| `is_subordinate` | `Boolean` | — | — | Y | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### hr.employee (`hr.employee`)

Helper function to compute subordinates_ids.
        Get all subordinates (direct and indirect) of an employee.
        An employee can be a manager of his own manager (recursive hierarchy; e.g. the C

**File:** `hr_org_chart_mixin.py` | Class: `HrEmployee`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `child_all_count` | `Integer` | Y | — | Y | Y | — |
| `department_color` | `Integer` | Y | — | Y | — | — |
| `child_count` | `Integer` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### hr.employee.public (`hr.employee.public`)

—

**File:** `hr_org_chart_mixin.py` | Class: `HrEmployeePublic`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `child_all_count` | `Integer` | Y | — | — | — | — |
| `department_color` | `Integer` | Y | — | — | — | — |
| `child_count` | `Integer` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/HR](HR.md)
