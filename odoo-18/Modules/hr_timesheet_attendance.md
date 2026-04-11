---
Module: hr_timesheet_attendance
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_timesheet_attendance
---

## Overview
Timesheets/attendances reporting. Links the attendance module to the timesheet module by providing a report that compares timesheet hours vs. attendance hours per employee per day, including cost calculations using `hourly_cost`. Produces a `hr.timesheet.attendance.report` auto-generated SQL view that unions data from `hr_attendance` and `account_analytic_line`.

## Models

### hr.timesheet.attendance.report (AUTO — SQL VIEW)
Inherits from: `base.model`
File: `~/odoo/odoo18/odoo/addons/hr_timesheet_attendance/report/hr_timesheet_attendance_report.py`
`_name = 'hr.timesheet.attendance.report'` — `_auto = False`

| Field | Type | Description |
|-------|------|-------------|
| employee_id | Many2one(hr.employee) | Readonly |
| date | Date | Readonly |
| total_timesheet | Float | Sum of `account_analytic_line.unit_amount` where `project_id IS NOT NULL` |
| total_attendance | Float | Sum of `hr_attendance.worked_hours` |
| total_difference | Float | `total_attendance - total_timesheet` |
| timesheets_cost | Float | `total_timesheet * employee.hourly_cost` |
| attendance_cost | Float | `total_attendance * employee.hourly_cost` |
| cost_difference | Float | `total_difference * employee.hourly_cost` |
| company_id | Many2one(res.company) | Readonly |

**SQL View Definition (`init`):**
```sql
CREATE OR REPLACE VIEW hr_timesheet_attendance_report AS (
  SELECT max(id), employee_id, date, company_id,
    coalesce(sum(attendance), 0) AS total_attendance,
    coalesce(sum(timesheet), 0) AS total_timesheet,
    coalesce(sum(attendance), 0) - coalesce(sum(timesheet), 0) AS total_difference,
    NULLIF(sum(timesheet) * emp_cost, 0) AS timesheets_cost,
    NULLIF(sum(attendance) * emp_cost, 0) AS attendance_cost,
    NULLIF((sum(attendance) - sum(timesheet)) * emp_cost, 0) AS cost_difference
  FROM (
    SELECT -hr_attendance.id, hr_employee.hourly_cost AS emp_cost,
           hr_attendance.employee_id, hr_attendance.worked_hours AS attendance, NULL AS timesheet,
           CAST(hr_attendance.check_in AT TIME ZONE 'utc' AT TIME ZONE calendar.tz AS DATE),
           hr_employee.company_id
    FROM hr_attendance LEFT JOIN hr_employee ON hr_employee.id = hr_attendance.employee_id
    UNION ALL
    SELECT ts.id, hr_employee.hourly_cost, ts.employee_id, NULL, ts.unit_amount, ts.date, ts.company_id
    FROM account_analytic_line ts LEFT JOIN hr_employee ON hr_employee.id = ts.employee_id
    WHERE ts.project_id IS NOT NULL
  ) AS t
  GROUP BY t.employee_id, t.date, t.company_id, t.emp_cost
)
```

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| read_group | domain, fields, groupby, ... | list | Custom order: if `date` is in groupby, sorts descending; other fields ascending |

### ir.ui.menu (Extension)
Inherits from: `ir.ui.menu`
File: `~/odoo/odoo18/odoo/addons/hr_timesheet_attendance/models/ir_ui_menu.py`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _load_menus_blacklist | self | list | Adds `menu_hr_timesheet_attendance_report` to blacklist for users without `group_hr_timesheet_user` |

## Security
File: `security/hr_timesheet_attendance_report_security.xml`

| Rule | Scope | Group |
|------|-------|-------|
| Multi-company rule | `company_id IN company_ids` | all authenticated |
| User rule | `employee_id = user.employee_id` | `hr_timesheet.group_hr_timesheet_user` (own records only) |
| Approver rule | `(1, '=', 1)` | `hr_timesheet.group_hr_timesheet_approver` (all) |
| Manager rule | `(1, '=', 1)` | `hr_timesheet.group_timesheet_manager` (all) |

## Critical Notes
- **`NULLIF(..., 0)` for cost fields:** Prevents showing `0` when there is no hourly cost — makes it clear cost is unknown
- **`hourly_cost` join:** The SQL view joins `hr_employee` by `employee_id` to get `hourly_cost` — requires `hr_hourly_cost` module or the field to exist
- **Timezone handling:** Attendance `check_in` is converted to the employee's calendar timezone before casting to DATE — ensures correct day attribution
- **Negative IDs in UNION:** Attendance records use `-id` to avoid collision with timesheet IDs in `max(id)`
- **`project_id IS NOT NULL`:** Only timesheet lines linked to a project are counted — not all analytic lines
- **Menu hiding:** The report menu is hidden from non-timesheet users via `_load_menus_blacklist` (not via ACL)
- **v17→v18:** `total_difference` column was added as a computed expression (previously only available in the ORM layer)
