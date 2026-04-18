---
tags: [odoo, odoo19, spreadsheet, dashboard, timesheet, hr_timesheet, project]
---

# spreadsheet_dashboard_hr_timesheet

## Overview

| Property | Value |
|----------|-------|
| Technical Name | `spreadsheet_dashboard_hr_timesheet` |
| Category | Productivity/Dashboard |
| Depends | `spreadsheet_dashboard`, `hr_timesheet` |
| Auto-install trigger | `hr_timesheet` |
| License | LGPL-3 |
| Module type | Data-only (no Python models) |

Provides a pre-configured [spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) template for project managers and HR to visualize timesheet data — hours logged per employee, project, and task. Auto-installs whenever `hr_timesheet` is active. Places the "Project" dashboard in the Project dashboard group.

## Module Architecture

This is a pure data module. No Python model code, no views, no controllers.

```
spreadsheet_dashboard_hr_timesheet/
├── __init__.py               # empty
├── __manifest__.py           # depends on hr_timesheet, auto_install
└── data/
    ├── dashboards.xml        # creates spreadsheet.dashboard record
    └── files/
        └── tasks_dashboard.json   # live dashboard spreadsheet (no sample file)
```

**Note:** Unlike most other spreadsheet dashboard modules, this one has only a single JSON file — there is no `tasks_sample_dashboard.json`. The `sample_dashboard_file_path` field is left unset, which means the empty-data fallback will not switch to a sample view; instead, the framework will display the live (but empty) spreadsheet.

## Dashboard Record Definition

Source: `/data/dashboards.xml`

```xml
<record id="spreadsheet_dashboard_tasks" model="spreadsheet.dashboard">
    <field name="name">Project</field>
    <field name="spreadsheet_binary_data" type="base64"
           file="spreadsheet_dashboard_hr_timesheet/data/files/tasks_dashboard.json"/>
    <field name="dashboard_group_id"
           ref="spreadsheet_dashboard.spreadsheet_dashboard_group_project"/>
    <field name="group_ids"
           eval="[Command.link(ref('hr_timesheet.group_hr_timesheet_approver'))]"/>
    <field name="sequence">100</field>
    <field name="is_published">True</field>
</record>
```

### Record Properties

| Field | Value | Significance |
|-------|-------|--------------|
| `name` | "Project" | Shown in dashboard navigation |
| `dashboard_group_id` | `group_project` | Appears under "Project" section |
| `group_ids` | `hr_timesheet.group_hr_timesheet_approver` | Timesheet Approvers only |
| `sequence` | 100 | Position within Project dashboard group |
| `main_data_model_ids` | (not set) | No empty-check; always shows live spreadsheet |
| `sample_dashboard_file_path` | (not set) | No sample fallback available |
| `is_published` | True | Visible immediately |

## Framework Integration

### No Main Data Model Set

This module does not set `main_data_model_ids`, which is unusual compared to the other spreadsheet dashboard modules. The implication is that `_dashboard_is_empty()` returns `False` (because no model is checked), so the live spreadsheet is always shown even when there are no timesheets. The spreadsheet itself will simply show zero/empty values if no data exists.

The `sale_timesheet` dashboard module (which also covers timesheets) takes a different approach by explicitly setting multiple main data models. The difference reflects the scoping: this module focuses on the basic `hr_timesheet` use case (project/task time tracking), while `spreadsheet_dashboard_sale_timesheet` focuses on billable time linked to sales.

### Access: Timesheet Approvers

`hr_timesheet.group_hr_timesheet_approver` is the manager-level group for timesheets. Regular employees who only log time do not see this dashboard — it is reserved for those who oversee and approve timesheets across the team.

### Project Group Placement

`spreadsheet_dashboard_group_project` is the Project dashboard group. Sequence 100 is a mid-range position. The `spreadsheet_dashboard_sale_timesheet` module also adds a "Timesheets" dashboard to the same group at sequence 200, so the "Project" dashboard (this module) appears first.

## Data Sources and KPI Structure

The spreadsheet reads from timesheet analytic lines using ODOO.PIVOT formulas. The core timesheet record in Odoo is `account.analytic.line` with `project_id` set (not null), which is what `hr_timesheet` creates.

### Primary Model: `account.analytic.line`

This model stores the actual time entries. When `project_id` is populated, it is a timesheet line.

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `employee_id` | Many2one | Dimension: employee breakdown |
| `project_id` | Many2one | Dimension: project breakdown |
| `task_id` | Many2one | Dimension: task-level detail |
| `date` | Date | Period filtering (day/week/month) |
| `unit_amount` | Float | Hours logged (the core measure) |
| `name` | Char | Activity description |
| `company_id` | Many2one | Multi-company filtering |

### Secondary Models

| Model | Relationship | Dashboard Use |
|-------|-------------|---------------|
| `hr.employee` | employee_id | Name, department, job position |
| `project.project` | project_id | Project name, stage, customer |
| `project.task` | task_id | Task name, stage, deadline |

### Key KPIs Tracked

**Hours by Employee**
- Total hours logged per employee in a period
- Employee utilization trend (hours per week over time)
- Employees with no logged hours (potential issue)
- Average hours per day per employee

**Hours by Project**
- Total hours per project (all time and by period)
- Project-level timeline: hours per week/month
- Top projects by hours consumed
- Projects approaching or exceeding hour budgets

**Task-Level Breakdown**
- Hours per task within a project
- Task stage vs. hours logged correlation
- Open tasks with zero hours (not started?)
- Completed tasks with time entries (for actuals vs. estimates)

**Time Distribution**
- Hours by day of week (workload patterns)
- Peak time-logging periods
- Hours breakdown by activity type (if `timesheet_activity_type` is used)

**Approval Status**
- Unvalidated/pending timesheet lines
- Lines approved by manager
- Timesheet submission compliance by employee

## hr_timesheet Module Integration

`hr_timesheet` extends `project.task` and `project.project` with timesheet-specific fields. It creates `account.analytic.line` records for each time entry:

```
Employee logs time on task
    → account.analytic.line created
        employee_id: hr.employee
        project_id: project.project
        task_id: project.task
        unit_amount: hours
        account_id: project's analytic account
```

The dashboard aggregates these lines to produce the project/employee time analytics.

## Auto-Install Behavior

```python
'auto_install': ['hr_timesheet'],
```

When `hr_timesheet` is installed (which requires `project` and `analytic`), this dashboard module auto-installs. This means every company using Odoo's project time tracking gets the Project dashboard immediately — no extra setup needed.

## Dependencies Chain

```
spreadsheet_dashboard_hr_timesheet
├── spreadsheet_dashboard   # base framework
└── hr_timesheet            # depends on:
    ├── hr                  # hr.employee
    ├── analytic            # account.analytic.line
    └── project             # project.project, project.task
```

## Comparison with sale_timesheet Dashboard

| Aspect | This Module | spreadsheet_dashboard_sale_timesheet |
|--------|-------------|--------------------------------------|
| Focus | Internal project tracking | Billable time on customer orders |
| Main models | (none set) | analytic.line, project, sale.order |
| Sample file | None | Yes |
| Sequence | 100 | 200 |
| Dashboard name | "Project" | "Timesheets" |

## Customization Notes

Since this dashboard shows all timesheet lines without filtering to billable time, common customizations include:

1. **Billable filter**: Add a filter for `so_line` (sale order line) being set, to see only billable hours
2. **Utilization rate**: Add a KPI formula: actual hours / available hours × 100
3. **Employee profiles**: Link employee records to show capacity (hours per week from `resource.calendar`)
4. **Department filter**: Add a slicer by `employee_id.department_id`

## Related Modules

- [spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — Dashboard framework
- [spreadsheet_dashboard_sale_timesheet](Modules/spreadsheet_dashboard_sale_timesheet.md) — Extends timesheet analytics with sale order billing
- `hr_timesheet` — Creates `account.analytic.line` for project time entries
- `project` — `project.project` and `project.task` models

## Source Files

- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_hr_timesheet/__manifest__.py`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_hr_timesheet/data/dashboards.xml`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_hr_timesheet/data/files/tasks_dashboard.json`
