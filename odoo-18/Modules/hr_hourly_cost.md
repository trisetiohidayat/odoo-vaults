---
Module: hr_hourly_cost
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_hourly_cost
---

## Overview
Employee Hourly Wage. Adds a `hourly_cost` (Monetary) field to `hr.employee`. This module is a pure data/field extension — a single field is added to the employee form for use by payroll and timesheet modules. No models directory with custom classes; the Python file is 9 lines.

## Models

### hr.employee (Extension)
Inherits from: `hr.employee`
File: `~/odoo/odoo18/odoo/addons/hr_hourly_cost/models/hr_employee.py`

| Field | Type | Description |
|-------|------|-------------|
| hourly_cost | Monetary | Hourly cost in user's currency; `groups="hr.group_hr_user"` (only HR officers/managers can edit); default=0.0 |

**Inheritance:** Classic `_inherit = 'hr.employee'` — adds the single field. No methods, no overrides.

## Security
- Field is restricted to `hr.group_hr_user` (not visible to regular employees)
- Used by `hr_timesheet_attendance` report to compute `timesheets_cost`, `attendance_cost`, `cost_difference`

## Critical Notes
- **Minimal module** — only 9 lines of Python; the entire value is the field declaration
- **Currency:** Uses `currency_id` from the employee/company context
- **Used by:** `hr_timesheet_attendance.report` (joins on `hr_employee.hourly_cost`)
- **Demo data:** `data/hr_hourly_cost_demo.xml` loads sample values
- **No v17→v18 changes** — same field, same groups restriction
