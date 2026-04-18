---
tags:
  - odoo
  - odoo19
  - hr
  - timesheet
  - attendance
  - reporting
  - modules
  - cross-module
summary: "Provides a read-only SQL reporting view that reconciles timesheet entries against attendance records per employee per day, exposing hours worked and cost differences."
description: |
  `hr_timesheet_attendance` is a reconciliation reporting module that compares timesheet hours logged by employees against the hours recorded by the attendance system. It creates a materialized SQL view — `hr.timesheet.attendance.report` — that joins `account_analytic_line` (timesheet entries) with `hr_attendance` (clock-in/clock-out records) on employee and date, producing a side-by-side comparison of expected vs. actual hours and costs.

  This is critical for organizations where employees log time via timesheets (for project billing or internal cost analysis) but attendance is tracked separately (for payroll or labor law compliance). The report exposes discrepancies that might indicate timesheet fraud, attendance system errors, or legitimate overtime that was not captured in timesheets.
---

# Timesheets/Attendances Reporting (`hr_timesheet_attendance`)

## Overview

| Property | Value |
|----------|-------|
| **Module** | `hr_timesheet_attendance` |
| **Category** | Human Resources / Attendances |
| **Depends** | `hr_timesheet`, `hr_attendance` |
| **Auto-install** | `True` |
| **Version** | `1.1` |
| **License** | LGPL-3 |
| **Odoo** | 19.0 |

`hr_timesheet_attendance` bridges the timesheet and attendance systems by creating a reconciliation report. It does not add business logic to either system — instead, it creates a unified read-only reporting view that joins both datasets, enabling managers to see at a glance whether employees' timesheet entries match their attendance records.

## Architecture

### Dependency Chain

```
base
  └── hr (hr.employee, hr.department)
        └── hr_attendance (hr.attendance, check_in, check_out, worked_hours)
        └── hr_timesheet (account_analytic_line, project_id, unit_amount)
              └── hr_timesheet_attendance  ← this module
```

The module requires both `hr_attendance` and `hr_timesheet` to be installed. If only one is present, the module cannot function meaningfully — there would be nothing to compare against.

### The Reporting View Design

The module creates a single **auto-init SQL view** (`hr.timesheet.attendance.report`) that is materialized at module install/upgrade time. It is not a standard Odoo model with CRUD methods — it is a read-only reporting model (`_auto = False` but `_auto` is handled by the `init()` method with raw SQL).

The view joins two data sources:

```
attendance records (hr_attendance)
    └── employee_id, check_in, check_out, worked_hours
    └── CAST to DATE using employee's timezone
    
UNION ALL
    
timesheet entries (account_analytic_line)
    └── employee_id, date, unit_amount (hours)
    └── filtered to only project-linked lines (project_id IS NOT NULL)
```

After UNION ALL, rows are GROUP BY employee + date, summing attendance hours and timesheet hours separately.

## Model: `hr.timesheet.attendance.report`

### Field Definitions

```python
# Source: odoo/addons/hr_timesheet_attendance/report/hr_timesheet_attendance_report.py
class HrTimesheetAttendanceReport(models.Model):
    _name = 'hr.timesheet.attendance.report'
    _auto = False
    _description = 'Timesheet Attendance Report'

    employee_id = fields.Many2one('hr.employee', readonly=True)
    date = fields.Date(readonly=True)
    total_timesheet = fields.Float("Timesheets Time", readonly=True)
    total_attendance = fields.Float("Attendance Time", readonly=True)
    total_difference = fields.Float("Time Difference", readonly=True)
    timesheets_cost = fields.Float("Timesheet Cost", readonly=True)
    attendance_cost = fields.Float("Attendance Cost", readonly=True)
    cost_difference = fields.Float("Cost Difference", readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
```

#### Field Inventory

| Field | Type | Description | SQL Source |
|-------|------|-------------|-----------|
| `employee_id` | Many2one (hr.employee) | Employee | `hr_attendance.employee_id` / `ts.employee_id` |
| `date` | Date | Day of the record | Cast from `check_in` AT TIME ZONE (per employee's calendar TZ) |
| `total_timesheet` | Float (hours) | Hours logged in timesheets | `SUM(ts.unit_amount)` from `account_analytic_line` |
| `total_attendance` | Float (hours) | Hours worked per attendance | `SUM(hr_attendance.worked_hours)` |
| `total_difference` | Float (hours) | Attendance minus Timesheet | `total_attendance - total_timesheet` |
| `timesheets_cost` | Float (currency) | Cost of timesheet hours | `SUM(unit_amount) * hourly_cost` |
| `attendance_cost` | Float (currency) | Cost of attendance hours | `SUM(worked_hours) * hourly_cost` |
| `cost_difference` | Float (currency) | Cost gap | `(attendance_hours - timesheet_hours) * hourly_cost` |
| `company_id` | Many2one (res.company) | Company | Per company data isolation |

### SQL View Definition

```python
# Source: odoo/addons/hr_timesheet_attendance/report/hr_timesheet_attendance_report.py
def init(self):
    tools.drop_view_if_exists(self.env.cr, self._table)
    self.env.cr.execute("""CREATE OR REPLACE VIEW %s AS (
        SELECT
            max(id) AS id,
            t.employee_id,
            t.date,
            t.company_id,
            coalesce(sum(t.attendance), 0) AS total_attendance,
            coalesce(sum(t.timesheet), 0) AS total_timesheet,
            coalesce(sum(t.attendance), 0) - coalesce(sum(t.timesheet), 0) as total_difference,
            NULLIF(sum(t.timesheet) * t.emp_cost, 0) as timesheets_cost,
            NULLIF(sum(t.attendance) * t.emp_cost, 0) as attendance_cost,
            NULLIF(
                (coalesce(sum(t.attendance), 0) - coalesce(sum(t.timesheet), 0)) * t.emp_cost, 0
            ) as cost_difference
        FROM (
            -- Attendance records: convert check_in to employee's timezone, then cast to DATE
            SELECT
                -hr_attendance.id AS id,
                hr_employee.hourly_cost AS emp_cost,
                hr_attendance.employee_id AS employee_id,
                hr_attendance.worked_hours AS attendance,
                NULL AS timesheet,
                CAST(hr_attendance.check_in AT TIME ZONE 'utc' AT TIME ZONE
                    (SELECT calendar.tz FROM resource_calendar as calendar
                     INNER JOIN hr_employee ON employee.id = hr_attendance.employee_id
                     LEFT JOIN hr_version v ON v.id = employee.current_version_id
                     WHERE calendar.id = v.resource_calendar_id)
                AS DATE) as date,
                hr_employee.company_id as company_id
            FROM hr_attendance
            LEFT JOIN hr_employee ON hr_employee.id = hr_attendance.employee_id
            WHERE check_in::date <= CURRENT_DATE

            UNION ALL

            -- Timesheet records
            SELECT
                ts.id AS id,
                hr_employee.hourly_cost AS emp_cost,
                ts.employee_id AS employee_id,
                NULL AS attendance,
                ts.unit_amount AS timesheet,
                ts.date AS date,
                ts.company_id AS company_id
            FROM account_analytic_line AS ts
            LEFT JOIN hr_employee ON hr_employee.id = ts.employee_id
            WHERE ts.project_id IS NOT NULL
              AND date <= CURRENT_DATE
        ) AS t
        GROUP BY t.employee_id, t.date, t.company_id, t.emp_cost
        ORDER BY t.date
    ) % self._table)
```

#### Key Design Decisions

1. **Negative ID trick**: Attendance rows use `-hr_attendance.id` as the ID to avoid collision with timesheet rows that use positive IDs. This ensures `max(id)` still returns a valid group identifier.

2. **Timezone-aware date casting**: The attendance `check_in` timestamp is first converted from the database UTC storage to the employee's configured timezone (via `resource_calendar.tz`), then cast to DATE. This ensures that for employees in different timezones, the date boundary is correct (e.g., a night-shift employee who clocks in at 23:00 on Monday should not have those hours attributed to Tuesday).

3. **`NULLIF(..., 0)` for cost fields**: Cost calculations use `NULLIF(..., 0)` to return NULL rather than 0 when the multiplication result would be 0. This prevents displaying zero-cost rows when the employee's hourly cost is not set.

4. **Date filter `<= CURRENT_DATE`**: Both attendance and timesheet queries filter to current or past dates, preventing future-dated timesheet entries from appearing in the report.

5. **Only project-linked timesheets**: `WHERE ts.project_id IS NOT NULL` ensures that non-project timesheet entries (e.g., internal administrative time tracked in a non-billable analytic account) are excluded from the comparison.

## Views and Actions

### View Modes

The module registers three views and one action for the report model.

| View | Type | Purpose |
|------|------|---------|
| `view_hr_timesheet_attendance_report_search` | Search | Filtering by employee, date range, and my team/department |
| `view_hr_timesheet_attendance_report_pivot` | Pivot | Cross-tabulation of attendance vs timesheet by employee and date |
| `hr_timesheet_attendance_report_view_graph` | Graph | Time-series visualization of the difference |

### Pivot View Fields

```xml
<pivot string="Timesheet Attendance" disable_linking="1" sample="1">
    <field name="date" interval="month" type="row"/>
    <field name="total_attendance" type="measure" widget="timesheet_uom"/>
    <field name="total_timesheet" type="measure" widget="timesheet_uom"/>
    <field name="total_difference" type="measure" widget="timesheet_uom"/>
    <field name="timesheets_cost"/>
    <field name="attendance_cost"/>
    <field name="cost_difference"/>
</pivot>
```

The `timesheet_uom` widget displays time in the configured timesheet UoM (hours or minutes), ensuring consistency with the user's timesheet settings.

### Menu Item

```
HR / Reporting / Timesheets / Timesheets / Attendance Analysis
```

Located under the timesheet reporting menu, making it accessible to timesheet managers alongside other timesheet reports.

## Security and Access Control

### Record Rules (Three Layers)

The module defines three `ir.rule` records controlling access to the report data:

```xml
<!-- 1. Multi-company rule: always applied (no groups specified) -->
<record id="...rule_company" model="ir.rule">
    <field name="domain_force">[('company_id', 'in', company_ids + [False])]</field>
</record>

<!-- 2. User rule: timesheet users see only their own data -->
<record id="...rule_user" model="ir.rule" groups="hr_timesheet.group_hr_timesheet_user">
    <field name="domain_force">[('employee_id', '=', user.employee_id.id)]</field>
</record>

<!-- 3. Approver rule: approvers see all -->
<record id="...rule_approver" model="ir.rule" groups="hr_timesheet.group_hr_timesheet_approver">
    <field name="domain_force">[(1, '=', 1)]</field>  <!-- See all -->
</record>

<!-- 4. Manager rule: administrators see all -->
<record id="...rule_manager" model="ir.rule" groups="hr_timesheet.group_timesheet_manager">
    <field name="domain_force">[(1, '=', 1)]</field>  <!-- See all -->
</record>
```

| Group | Access Level | Domain Rule |
|-------|-------------|-------------|
| `group_hr_timesheet_user` | Own records only | `[('employee_id', '=', user.employee_id.id)]` |
| `group_hr_timesheet_approver` | All employees in scope | `[(1, '=', 1)]` (all) |
| `group_timesheet_manager` | All records | `[(1, '=', 1)]` (all) |
| No group (base) | Multi-company filtered | `[('company_id', 'in', company_ids)]` |

### Access Control List (ACL)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_hr_timesheet_attendance_report_user,
  hr_timesheet_attendance.report.user,
  model_hr_timesheet_attendance_report,
  hr_timesheet.group_hr_timesheet_user,
  1,0,0,0
```

The ACL grants **read-only** access (`perm_read=1`, all others 0) to timesheet users. This enforces the report's read-only nature at the ORM level.

## Practical Usage Scenarios

### Scenario 1: Catching Unreported Overtime

An employee consistently clocks in 2 hours of overtime per week that is not reflected in their timesheet. In the pivot report:
- `total_attendance` shows 42 hours/week
- `total_timesheet` shows 40 hours/week
- `total_difference` shows +2 hours/week
- `cost_difference` shows the cost impact of the unreported overtime

The manager uses this data to either:
- Approve the overtime and update the timesheet retroactively.
- Remind the employee to log all hours.

### Scenario 2: Timesheet Fraud Detection

The attendance system shows a standard 8-hour day for an employee, but their timesheet shows 6 hours. The `total_difference` would be +2 (attendance > timesheet), indicating possible timesheet fraud or attendance system misuse.

### Scenario 3: Billable Hours Reconciliation

A project manager wants to confirm that all attendance hours for a project's team members are captured in timesheets for billing purposes. The report grouped by project (via timesheet lines) can reveal gaps.

### Scenario 4: Cost Center Analysis

A department head wants to understand the total labor cost per day. The attendance cost (based on actual hours worked) vs. timesheet cost (based on logged project hours) reveals:
- Whether non-project time is being captured.
- Whether overtime costs are being correctly attributed to projects.

## Technical Notes

### `_auto = False` Pattern

The model sets `_auto = False` to prevent Odoo from creating the table automatically via ORM. Instead, the table is created manually by the `init()` method with raw SQL. This is the standard Odoo pattern for materialized SQL views used as reporting models.

### `formatted_read_group` Override

```python
# Source: odoo/addons/hr_timesheet_attendance/report/hr_timesheet_attendance_report.py
@api.model
def formatted_read_group(self, domain, groupby=(), aggregates=(), having=(),
                          offset=0, limit=None, order=None) -> list[dict]:
    if not order and groupby:
        order = ', '.join(
            f"{spec} DESC" if spec.startswith('date:') else spec
            for spec in groupby
        )
    return super().formatted_read_group(
        domain, groupby, aggregates, having=having,
        offset=offset, limit=limit, order=order
    )
```

This override ensures that when no explicit order is provided, the read group defaults to ordering by the groupby fields in descending order. This is important for date-based groupings where users typically want to see the most recent periods first.

### Timezone Handling Complexity

The SQL query uses a subquery to join the employee's `resource_calendar` to get their timezone (`calendar.tz`), then uses that timezone to convert the UTC `check_in` timestamp before casting to DATE. This handles:
- Employees in different timezones within the same company.
- Daylight saving time transitions (handled automatically by PostgreSQL's AT TIME ZONE).
- Employees without a calendar (uses NULL timezone, falls back to UTC).

### No CRUD Operations

Because this is a read-only SQL view, attempting to create, write, or unlink records through the ORM will raise an error. All write operations must be done on the underlying source tables (`hr_attendance` or `account_analytic_line`).

## Related Documentation

- [Modules/hr_timesheet](hr_timesheet.md) — Timesheets (project time tracking via `account_analytic_line`)
- [Modules/hr_attendance](hr_attendance.md) — Attendance tracking (clock-in/clock-out)
- [Modules/hr](hr.md) — Human Resources core module
- [Modules/CRM](CRM.md) — CRM module
- [Patterns/Cross-Module-Integration](Patterns/Cross-Module-Integration.md) — Cross-module reporting patterns
