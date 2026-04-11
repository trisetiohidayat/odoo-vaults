---
Module: hr_maintenance
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_maintenance
---

## Overview
Bridge module between HR and Maintenance. Links equipment and maintenance requests to employees and departments. Adds HR-aware fields to `maintenance.equipment` (employee assignment, department assignment, owner user) and `maintenance.request` (employee link). Also extends `res.users` and the `hr.departure.wizard` to handle equipment unassignment on employee departure.

## Models

### maintenance.equipment (Extension)
Inherits from: `maintenance.equipment`
File: `~/odoo/odoo18/odoo/addons/hr_maintenance/models/equipment.py`

| Field | Type | Description |
|-------|------|-------------|
| employee_id | Many2one(hr.employee) | Assigned employee; `compute='_compute_equipment_assign'`, `store=True`, `readonly=False` |
| department_id | Many2one(hr.department) | Assigned department; `compute='_compute_equipment_assign'`, `store=True`, `readonly=False` |
| equipment_assign_to | Selection | `department | employee | other`; required, default='employee' |
| owner_user_id | Many2one(res.users) | `compute='_compute_owner'`, `store=True` |
| assign_date | Date | Assignment date; `compute='_compute_equipment_assign'`, `store=True`, `copy=True` |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_owner | self | None | Sets `owner_user_id`: employee→`employee.user_id`, department→`department.manager_id.user_id`, other→`env.user` |
| _compute_equipment_assign | self | None | Clears the non-selected target (employee OR department) based on `equipment_assign_to`; sets `assign_date` to today |
| create | vals_list | records | Auto-subscribes employee user and department manager to equipment messages |
| write | vals | bool | Auto-subscribes new employee/department manager when assignment changes |
| _track_subtype | init_values | record | Returns `maintenance.mt_mat_assign` subtype when `employee_id` or `department_id` changes |

### maintenance.request (Extension)
Inherits from: `maintenance.request`
File: `~/odoo/odoo18/odoo/addons/hr_maintenance/models/equipment.py`

| Field | Type | Description |
|-------|------|-------------|
| employee_id | Many2one(hr.employee) | Requesting employee; default=current user's employee |
| owner_user_id | Many2one(res.users) | `compute='_compute_owner'`, `store=True` |
| equipment_id | Many2one | Domain: only equipment assigned to `employee_id` or unassigned |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| create | vals_list | records | Subscribes `employee_id.user_id.partner_id` to the request thread |
| write | vals | bool | Subscribes new employee on reassignment |
| message_new | msg, custom_values | record | Email gateway handler: looks up user by sender email and auto-assigns `employee_id` |

### res.users (Extension)
Inherits from: `res.users`
File: `~/odoo/odoo18/odoo/addons/hr_maintenance/models/res_users.py`

| Field | Type | Description |
|-------|------|-------------|
| equipment_ids | One2many(maintenance.equipment) | Equipment owned by user (`owner_user_id`) |
| equipment_count | Integer | Related from `employee_id.equipment_count`; `SELF_READABLE_FIELDS` includes this |

### hr.employee (Extension)
Inherits from: `hr.employee`
File: `~/odoo/odoo18/odoo/addons/hr_maintenance/models/res_users.py`

| Field | Type | Description |
|-------|------|-------------|
| equipment_ids | One2many(maintenance.equipment) | Equipment assigned to employee; `groups="hr.group_hr_user"` |
| equipment_count | Integer | Count of assigned equipment; `compute='_compute_equipment_count'`, `groups="hr.group_hr_user"` |

### hr.departure.wizard (Extension)
Inherits from: `hr.departure.wizard`
File: `~/odoo/odoo18/odoo/addons/hr_maintenance/wizard/hr_departure_wizard.py`

| Field | Type | Description |
|-------|------|-------------|
| unassign_equipment | Boolean | "Free Equipments"; default=True. If True, unlinks all equipment assignments from the departing employee |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| action_register_departure | self | bool | Calls `super()`, then if `unassign_equipment`: unlinks all `equipment_ids` from the employee |

## Security
- `security/equipment.xml`: Implies `maintenance.group_equipment_manager` into `hr.group_hr_user` — HR officers automatically get equipment manager rights
- `equipment_ids` on `hr.employee` and `equipment_count` are restricted to `hr.group_hr_user`

## Critical Notes
- **Key pattern:** `equipment_assign_to` Selection (3-way: employee/department/other) drives which fields are populated; `_compute_equipment_assign` clears the non-selected target
- **Email gateway:** `message_new` on `maintenance.request` auto-links the request to the employee of the sender
- **Departure flow:** When an employee is marked as departed, all their equipment can be auto-unassigned via the wizard
- **v17→v18:** No breaking changes; same model structure
