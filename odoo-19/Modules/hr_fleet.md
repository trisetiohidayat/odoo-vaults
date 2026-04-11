---
type: module
module: hr_fleet
tags: [odoo, odoo19, hr, fleet, vehicles]
created: 2026-04-06
---

# Fleet for HR

## Overview

| Property | Value |
|----------|-------|
| **Name** | Fleet History |
| **Technical** | `hr_fleet` |
| **Category** | Human Resources |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description

Links HR employees with fleet vehicles. Maintains vehicle assignment history, tracks drivers as employees (not just contacts), and synchronizes car data with employee records.

## Dependencies

- `hr`
- `fleet`

## Key Models

| Model | Description |
|-------|-------------|
| `fleet.vehicle` | Vehicle records (inherited/extended) |
| `fleet.vehicle.assignation.log` | Vehicle assignment history |
| `hr.employee` | Employee records (extended) |

## fleet.vehicle (extends fleet.fleet)

**File:** `models/fleet_vehicle.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `driver_employee_id` | Many2one | Driver as HR employee |
| `driver_employee_name` | Char | Related from driver_employee_id |
| `future_driver_employee_id` | Many2one | Next driver as HR employee |
| `mobility_card` | Char | Employee mobility card (computed) |

### Key Methods

| Method | Description |
|--------|-------------|
| `_update_create_write_vals()` | Sync driver employee <-> driver contact |
| `_compute_driver_employee_id()` | Find employee from driver contact |
| `_compute_future_driver_employee_id()` | Find next employee from future driver contact |
| `_compute_mobility_card()` | Copy from driver employee |
| `action_open_employee()` | Open related employee form |
| `open_assignation_logs()` | Open assignment history (list view) |

---

## hr.employee (extends hr.hr)

**File:** `models/employee.py`

### Additional Fields

| Field | Type | Description |
|-------|------|-------------|
| `employee_cars_count` | Integer | Number of cars assigned (computed) |
| `car_ids` | One2many | Vehicles where employee is driver |
| `license_plate` | Char | License plates from cars (computed) |
| `mobility_card` | Char | Mobility card number |

### Key Methods

| Method | Description |
|--------|-------------|
| `action_open_employee_cars()` | Open car history list |
| `_compute_license_plate()` | Combine fleet plates with private plate |
| `_search_license_plate()` | Search by fleet or private plate |
| `_compute_employee_cars_count()` | Count assignment logs |
| `_check_work_contact_id()` | Prevent removing address if linked to car |

### Constraints

| Constraint | Description |
|-----------|-------------|
| `_check_work_contact_id()` | Cannot remove work_contact_id from employees linked to cars |

---

## Model Relationships

```
hr.employee
  |-- car_ids --> fleet.vehicle
       |-- driver_employee_id --> hr.employee
       |-- future_driver_employee_id --> hr.employee
       |-- driver_id --> res.partner
            (via work_contact_id sync)

fleet.vehicle
  |-- driver_employee_id --> hr.employee
  |-- driver_id --> res.partner
  |-- future_driver_employee_id --> hr.employee
  |-- future_driver_id --> res.partner
```

## Key Behaviors

- Setting `driver_employee_id` on a vehicle automatically updates `driver_id` to the employee's work contact
- Setting `driver_id` to a contact that maps to exactly one employee auto-fills `driver_employee_id`
- Same bidirectional sync applies to future drivers
- Changing an employee's `work_contact_id` updates linked vehicles' driver_id
- `mobility_card` is synced from employee to vehicle

## Related

- [[Modules/hr]]
- [[Modules/fleet]]
