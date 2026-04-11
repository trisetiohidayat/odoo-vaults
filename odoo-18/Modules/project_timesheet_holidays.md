---
Module: project_timesheet_holidays
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_timesheet_holidays #project #timesheet #holidays
---

## Overview

**Module:** `project_timesheet_holidays`
**Depends:** `hr_timesheet`, `hr_holidays` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_timesheet_holidays/`
**License:** LGPL-3
**Post-init hook:** `post_init` — auto-sets leave type project/task from company's internal project.
**Purpose:** Generates timesheet entries for time off requests and public holidays. Links analytic lines to leave records. Marks tasks used by leave types as time-off tasks.

---

## Models

### `hr.leave.type` (models/hr_holidays.py, 10–53)

Inherits: `hr.leave.type`

| Field | Type | Line | Description |
|---|---|---|---|
| `timesheet_generate` | Boolean (compute/store) | 13 | `True` if `time_type != 'other'` and (no company or both `timesheet_task_id` and `timesheet_project_id` set). |
| `timesheet_project_id` | Many2one (`project.project`) (compute/store) | 16 | Defaults to company's `internal_project_id`. |
| `timesheet_task_id` | Many2one (`project.task`) (compute/store) | 18 | Defaults to company's `leave_timesheet_task_id` if it belongs to the same project. |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_compute_timesheet_generate()` | `@api.depends` | 26 | Auto-sets `timesheet_generate` based on time_type and project/task completeness. |
| `_compute_timesheet_project_id()` | `@api.depends` | 30 | Copies `company_id.internal_project_id` to new leave types. |
| `_compute_timesheet_task_id()` | `@api.depends` | 35 | Defaults to company's `leave_timesheet_task_id` if it belongs to the same `timesheet_project_id`. |
| `_check_timesheet_generate()` | `@api.constrains` | 45 | Raises `ValidationError` if `timesheet_generate=True` and company is set but project or task is missing. |

### `hr.leave` (models/hr_holidays.py, 55–188)

Inherits: `hr.leave`

| Field | Type | Line | Description |
|---|---|---|---|
| `timesheet_ids` | One2many (`account.analytic.line`, `holiday_id`) | 58 | Analytic lines created from this leave. |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_validate_leave_request()` | override | 60 | Calls `_generate_timesheets()` before parent validation. |
| `_generate_timesheets(ignored_resource_calendar_leaves=None)` | private | 64 | Generates timesheet lines per working day. Uses leave type's project/task if company is set on leave type, else uses company's `internal_project_id` and `leave_timesheet_task_id`. Handles flexible hours (request_unit_hours/half). Unlinks old timesheets before creating new ones. |
| `_timesheet_prepare_line_values(index, work_hours_data, day_date, work_hours_count, project, task)` | private | 123 | Returns dict: `name="Time Off (N/M)"`, `project_id`, `task_id`, `account_id`, `unit_amount`, `user_id`, `date`, `holiday_id`, `employee_id`, `company_id`. |
| `_check_missing_global_leave_timesheets()` | private | 138 | Finds public holidays overlapping with validated leaves; triggers `_generate_timesheets` for any affected leaves. |
| `action_refuse()` | override | 154 | Unlinks timesheets linked to refused leaves; calls `_check_missing_global_leave_timesheets`. |
| `_action_user_cancel()` | override | 163 | Same: unlinks timesheets on user cancel. |
| `_force_cancel()` | override | 171 | Same: unlinks timesheets on force cancel. |
| `write(vals)` | override | 178 | Removes empty timesheets (0-day leaves) by unlinking them. |

#### `_generate_timesheets` Logic
1. Groups `resource.calendar.leaves` by `holiday_id`
2. For each leave with `timesheet_generate=True`: resolves project/task from leave type or company
3. For flexible-hour leaves (unit hours, half days, single-day): uses calendar `hours_per_day`
4. For regular leaves: calls `_list_work_time_per_day` with calendar exclusions
5. Unlinks existing timesheets for these leaves before creating new ones
6. Creates `account.analytic.line` records with `holiday_id` set

### `account.analytic.line` (models/account_analytic.py, 1–56)

Inherits: `account.analytic.line`

| Field | Type | Line | Description |
|---|---|---|---|
| `holiday_id` | Many2one (`hr.leave`) | 12 | "Time Off Request"; `index='btree_not_null'`; `copy=False` |
| `global_leave_id` | Many2one (`resource.calendar.leaves`) | 13 | "Global Time Off"; `index='btree_not_null'`; `ondelete='cascade'` |
| `task_id` | Many2one (domain restricted) | 14 | Domain: `allow_timesheets=True`, `is_timeoff_task=False`; `project_id` optional via `=?` |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_get_redirect_action()` | private | 16 | Returns action to open the linked leave form. |
| `_unlink_except_linked_leave()` | `@api.ondelete(at_uninstall=False)` | 30 | Prevents deletion of timesheets linked to global time off (always blocked) or leaves (blocked unless `hr_holidays_user` group or owner). Raises `RedirectWarning` with redirect to leave. |
| `_check_can_write(values)` | override | 41 | Prevents writing on timesheets linked to leaves (unless `su`). |
| `_check_can_create()` | override | 46 | Prevents creating timesheets on tasks where `is_timeoff_task=True`. |
| `_get_favorite_project_id_domain(employee_id=False)` | override | 51 | Adds `holiday_id=False, global_leave_id=False` to filter out leave-linked projects from favorite project suggestions. |

### `project.task` (models/project_task.py, 1–41)

Inherits: `project.task`

| Field | Type | Line | Description |
|---|---|---|---|
| `leave_types_count` | Integer (computed) | 9 | Count of leave types linked to this task via `timesheet_task_id`. |
| `is_timeoff_task` | Boolean (computed/search) | 10 | `True` if `leave_types_count > 0` OR task matches company's `leave_timesheet_task_id`. |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_compute_leave_types_count()` | `_read_group` | 12 | Groups `hr.leave.type` by `timesheet_task_id`; maps counts. |
| `_compute_is_timeoff_task()` | compute | 22 | Sets `True` for tasks in `leave_types_count` or matching company leave task. |
| `_search_is_timeoff_task(operator, value)` | search | 27 | Supports `=` and `!=`; inverts result set for `!=` operator. |

### `resource.calendar.leaves` (models/resource_calendar_leaves.py, 1–287)

Inherits: `resource.calendar.leaves`

| Field | Type | Line | Description |
|---|---|---|---|
| `timesheet_ids` | One2many (`account.analytic.line`, `global_leave_id`) | 13 | "Analytic Lines" — timesheets generated from this public holiday. |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_get_resource_calendars()` | private | 15 | Returns calendars of leaves with `calendar_id` plus company-wide calendars for leaves without. |
| `_work_time_per_day(resource_calendars=False)` | override | 25 | Computes work hours per day per calendar accounting for overlapping leaves and resource-specific calendars. Returns nested dict: `{calendar_id: {leave_id: [(date, hours), ...]}}`. |
| `_timesheet_create_lines()` | private | 116 | Bulk-creates timesheets for all employees using the same calendar. Skips days where employee has a validated leave. Returns created lines. |
| `_timesheet_prepare_line_values(index, employee_id, work_hours_data, day_date, work_hours_count)` | private | 184 | Returns dict for global leave timesheet: `name`, `project_id=company.internal_project_id`, `task_id=company.leave_timesheet_task_id`, `account_id`, `unit_amount`, `user_id`, `date`, `global_leave_id`, `employee_id`, `company_id`. |
| `_generate_timesheeets()` | private | 199 | Filters `self` to global leaves (no `resource_id`) with company internal project and task; calls `_timesheet_create_lines()`. |
| `_generate_public_time_off_timesheets(employees)` | private | 204 | Generates timesheets for a specific employee set on a global leave; avoids duplicates by checking existing `global_leave_id` records. |
| `_get_overlapping_hr_leaves(domain=None)` | private | 238 | Finds validated leaves overlapping this global leave with `timesheet_generate=True`. Used when GTO changes or is deleted. |
| `create(vals_list)` | `@api.model_create_multi` | 252 | Calls `_generate_timesheeets()` after creation. |
| `write(vals)` | override | 258 | On date/time/calendar change: unlinks old timesheets, regenerates, and triggers regeneration for overlapping HR leaves. |
| `_regenerate_hr_leave_timesheets_on_gto_unlinked()` | `@api.ondelete(at_uninstall=False)` | 278 | On GTO delete: finds overlapping leaves and regenerates their timesheets (ignoring deleted GTO via `ignored_resource_calendar_leaves`). |

### `hr.employee` (models/hr_employee.py, 1–74)

Inherits: `hr.employee`

| Method | Decorator | Line | Description |
|---|---|---|---|
| `create(vals_list)` | `@api.model_create_multi` | 11 | After creation: calls `_create_future_public_holidays_timesheets` for all future global leaves (unless `salary_simulation` context). |
| `write(vals)` | override | 23 | On activation: creates future timesheets. On deactivation: deletes future timesheets. On calendar change: regenerates future timesheets. |
| `_delete_future_public_holidays_timesheets()` | private | 42 | Unlinks future timesheets (date >= today) linked to `global_leave_id` for inactive employees. |
| `_create_future_public_holidays_timesheets(employees)` | private | 47 | Creates timesheet lines for all future global leaves affecting employees. Groups by calendar, computes work hours per day, creates lines. |

### `res.company` (models/res_company.py, 1–30)

Inherits: `res.company`

| Field | Type | Line | Description |
|---|---|---|---|
| `leave_timesheet_task_id` | Many2one (`project.task`) | 10 | "Time Off Task"; domain: task in `internal_project_id`. |

`_create_internal_project_task()` (override) (line 14)
: Additionally creates a "Time Off" task in the internal project and sets it as `leave_timesheet_task_id`.

### `res.config.settings` (models/res_config_settings.py, 1–30)

Inherits: `res.config.settings`

| Field | Type | Line | Description |
|---|---|---|---|
| `internal_project_id` | Many2one (related) | 10 | Related to company; required; sets default project for time off timesheets. |
| `leave_timesheet_task_id` | Many2one (related) | 15 | Related to company; domain restricts to project's tasks. |

`_onchange_timesheet_project_id()` (line 21)
: Clears `leave_timesheet_task_id` when project changes.

`_onchange_timesheet_task_id()` (line 26)
: Sets `internal_project_id` to the selected task's project.

---

## Post-init Hook (`__init__.py`, line 7)

`post_init(env)`:
- Creates "Internal" project with timesheets enabled for companies missing one
- Creates "Time Off" task in that project for companies missing one
- Updates all existing leave types with `timesheet_generate=True` but no project/task to have defaults

---

## Security

`security/ir.model.access.csv` present.

Data: `data/holiday_timesheets_demo.xml` — demo leave types with timesheet generation settings.

---

## Critical Notes

- Timesheets are only generated when `timesheet_generate=True` on the leave type.
- Public holiday (global leave) timesheets are created for **all employees** using the calendar — not per-employee.
- `_check_missing_global_leave_timesheets` handles the case where a public holiday is created after employees already have validated leaves.
- Timesheet write/delete protection: linked timesheets cannot be modified except via the Time Off application (`hr_holidays`).
- `is_timeoff_task` search allows filtering tasks in the UI.
- `holiday_id` and `global_leave_id` use `btree_not_null` index for efficient joins.
- Company creation automatically creates a "Time Off" task in the internal project via `_create_internal_project_task` override.
- v17→v18: No breaking changes.