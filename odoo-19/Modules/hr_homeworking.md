---
title: "Hr Homeworking"
module: hr_homeworking
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Hr Homeworking

## Overview

Module `hr_homeworking` — auto-generated from source code.

**Source:** `addons/hr_homeworking/`
**Models:** 6
**Fields:** 32
**Methods:** 3

## Models

### hr.employee (`hr.employee`)

—

**File:** `hr_employee.py` | Class: `HrEmployee`

#### Fields (10)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `monday_location_id` | `Many2one` | — | — | — | — | — |
| `tuesday_location_id` | `Many2one` | — | — | — | — | — |
| `wednesday_location_id` | `Many2one` | — | — | — | — | — |
| `thursday_location_id` | `Many2one` | — | — | — | — | — |
| `friday_location_id` | `Many2one` | — | — | — | — | — |
| `saturday_location_id` | `Many2one` | Y | — | — | — | — |
| `sunday_location_id` | `Many2one` | Y | — | — | — | — |
| `exceptional_location_id` | `Many2one` | Y | — | — | — | — |
| `hr_icon_display` | `Selection` | — | — | — | — | — |
| `today_location_name` | `Char` | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `get_views` | |


### hr.employee.public (`hr.employee.public`)

—

**File:** `hr_employee_public.py` | Class: `HrEmployeePublic`

#### Fields (8)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `monday_location_id` | `Many2one` | — | — | — | — | — |
| `tuesday_location_id` | `Many2one` | — | — | — | — | — |
| `wednesday_location_id` | `Many2one` | — | — | — | — | — |
| `thursday_location_id` | `Many2one` | — | — | — | — | — |
| `friday_location_id` | `Many2one` | — | — | — | — | — |
| `saturday_location_id` | `Many2one` | — | — | — | — | — |
| `sunday_location_id` | `Many2one` | — | — | — | — | — |
| `today_location_name` | `Char` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### hr.employee.location (`hr.employee.location`)

—

**File:** `hr_homeworking.py` | Class: `HrEmployeeLocation`

#### Fields (7)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `work_location_id` | `Many2one` | — | — | Y | — | Y |
| `work_location_name` | `Char` | — | — | Y | — | Y |
| `work_location_type` | `Selection` | — | — | Y | — | Y |
| `employee_id` | `Many2one` | Y | — | Y | — | Y |
| `employee_name` | `Char` | Y | — | Y | — | — |
| `date` | `Date` | Y | — | — | — | — |
| `day_week_string` | `Char` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### hr.work.location (`hr.work.location`)

—

**File:** `hr_work_location.py` | Class: `HrWorkLocation`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### res.partner (`res.partner`)

—

**File:** `res_partner.py` | Class: `ResPartner`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### res.users (`res.users`)

—

**File:** `res_users.py` | Class: `ResUsers`

#### Fields (7)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `monday_location_id` | `Many2one` | — | — | Y | — | — |
| `tuesday_location_id` | `Many2one` | — | — | Y | — | — |
| `wednesday_location_id` | `Many2one` | — | — | Y | — | — |
| `thursday_location_id` | `Many2one` | — | — | Y | — | — |
| `friday_location_id` | `Many2one` | — | — | Y | — | — |
| `saturday_location_id` | `Many2one` | — | — | Y | — | — |
| `sunday_location_id` | `Many2one` | — | — | Y | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `SELF_READABLE_FIELDS` | |
| `SELF_WRITEABLE_FIELDS` | |




## Related

- [Modules/Base](base.md)
- [Modules/HR](HR.md)
