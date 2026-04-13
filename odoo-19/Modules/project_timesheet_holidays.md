---
type: module
module: project_timesheet_holidays
tags: [odoo, odoo19, project, hr_holidays, hr_timesheet, timesheet, leave]
created: 2026-04-06
updated: 2026-04-11
---

# Project Timesheet Holidays

## Overview

| Property | Value |
|----------|-------|
| **Name** | Timesheet when on Time Off |
| **Technical** | `project_timesheet_holidays` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Category** | Human Resources |
| **Module Key** | `project_timesheet_holidays` |
| **Version** | 1.0 |
| **Auto-install** | True — auto-resolved when both `hr_timesheet` and `hr_holidays` are installed |

## Description

Bridge module that automatically generates timesheet analytic lines when employees take approved leave (individual time-off requests) or when public/company-wide holidays occur. All auto-generated timesheets are logged on a configurable internal project and task per company, making time-off visible in the timesheet reporting pipeline.

## Dependencies

```python
'depends': ['hr_timesheet', 'hr_holidays']
```

- **`hr_timesheet`**: Provides the `account.analytic.line` model, internal project creation (`_create_internal_project_task`), and the settings form layout.
- **`hr_holidays`**: Provides `hr.leave`, `hr.employee`, leave states, and validation workflow.

### Load Order Constraint

`models/__init__.py` imports `res_company` **before** `hr_leave`. This is intentional — `hr_leave` (via `hr_holidays`) writes to `res.company` fields at class-definition time for the settings form. The `res.company` column must exist before `hr.leave` fields that reference it are evaluated.

## Architecture

The module plugs into three separate write paths:

1. **Leave approval** (`hr.leave` → `_validate_leave_request`) — generates per-day analytic lines for an approved leave request.
2. **Global time-off creation** (`resource.calendar.leaves` → `create`) — generates per-employee analytic lines for public holidays.
3. **Employee lifecycle** (`hr.employee` → `create`/`write`) — backfills future global time-off timesheets for newly created employees and handles calendar changes.

The internal project and "Time Off" task are shared across both paths. Both leave types share the same analytic-line structure, differentiated by `holiday_id` vs `global_leave_id`.

## Models

---

### `res.company` — Internal Project and Task Setup

**Defined in:** `hr_timesheet` base (`res_company.py`), extended by `project_timesheet_holidays/res_company.py`

**Fields added by this module:**

```python
leave_timesheet_task_id = fields.Many2one(
    'project.task',
    string="Time Off Task",
    domain="[('project_id', '=', internal_project_id)]"
)
```

| Field | Type | Notes |
|-------|------|-------|
| `internal_project_id` | Many2one `project.project` | Defined in `hr_timesheet` base. Project must belong to the same company. Created automatically by `hr_timesheet` via `_create_internal_project_task`. |
| `leave_timesheet_task_id` | Many2one `project.task` | Must belong to `internal_project_id`. Created by this module's override of `_create_internal_project_task`. |

**`internal_project_id` creation (in `hr_timesheet`):**
The base `hr_timesheet` module already overrides `_create_internal_project_task()` to create the project. This module further extends that method to create the "Time Off" task.

**`_create_internal_project_task()` — Override chain:**

```python
# project_timesheet_holidays/res_company.py
def _create_internal_project_task(self):
    projects = super()._create_internal_project_task()  # hr_timesheet creates internal project
    for project in projects:
        company = project.company_id
        company = company.with_company(company)
        if not company.leave_timesheet_task_id:
            task = company.env['project.task'].sudo().create({
                'name': _('Time Off'),
                'project_id': company.internal_project_id.id,
                'active': True,
                'company_id': company.id,
            })
            company.write({'leave_timesheet_task_id': task.id})
    return projects
```

**Post-init hook (`__init__.py`):**
The `post_init` hook runs on install/upgrade for existing companies that lack either `internal_project_id` or `leave_timesheet_task_id`. It searches for existing "Internal" projects in each company, creates them if missing, then creates the "Time Off" task. This ensures all pre-existing companies are bootstrapped without requiring manual re-installation.

**Constraint (from `hr_timesheet`):**
`@api.constrains('internal_project_id')` — `_check_internal_project_id_company` ensures the internal project belongs to the same company. If a project from another company is assigned, an `AccessError` is raised.

---

### `hr.leave` — Leave Timesheet Generation

**Defined in:** `hr_holidays` base extended by `project_timesheet_holidays/models/hr_leave.py`

**Field added by this module:**

```python
timesheet_ids = fields.One2many(
    'account.analytic.line', 'holiday_id', string="Analytic Lines"
)
```

Links analytic lines back to the originating leave. Used for display, cascade deletion, and the One2many inverse.

**Skipped leave types:**
Leaves where `holiday_status_id.time_type == 'other'` are skipped — no timesheet is generated. This excludes custom "other" leave types from automatic timesheet creation.

---

**`_validate_leave_request()` — Trigger point:**

```python
def _validate_leave_request(self):
    self._generate_timesheets()
    return super()._validate_leave_request()
```

Called by `hr_holidays` when a leave transitions to `validate` state. Timesheets are generated **before** the parent's `write({'state': 'validate'})` completes. If `_generate_timesheets()` raises an exception, leave validation is aborted.

---

**`_generate_timesheets(ignored_resource_calendar_leaves=None)` — Core logic:**

```
1. Read group resource.calendar.leaves by holiday_id to build a map.
2. For each leave in self:
   a. Resolve project/task from employee.company_id.
   b. Skip if time_type == 'other', or project/task is missing.
   c. Determine work hours per day:
      - Flexible hours + (request_unit_hours OR request_unit_half OR single-day):
        → use explicit hours: request_hour_to - request_hour_from, or half-day calc, or full day hours_per_day.
      - Otherwise:
        → call employee_id._list_work_time_per_day(date_from, date_to) with optional domain to exclude
          overlapping global time-off records (passed in via ignored_resource_calendar_leaves).
3. Build vals_list for account.analytic.line.
4. Delete any pre-existing timesheets linked to this leave (holiday_id unlink and re-create).
5. sudo().create(vals_list).
```

**Flexible hours branch:**
Only enters this branch when `calendar.flexible_hours` is True **and** one of: `request_unit_hours` (hourly leave), `request_unit_half` (half-day), or single-day leave (date_from and date_to are the same calendar day). In this branch it bypasses `_list_work_time_per_day` and directly calculates hours based on request parameters or `hours_per_day / 2`.

**Date/timezone handling:**
All date_from/date_to are naive UTC datetimes stored in Odoo. They are converted to the employee's calendar timezone via `pytz.timezone((calendar or employee).tz)` before extracting `.date()` for the analytic line's `date` field.

**Performance note:**
The `_read_group` call on `resource.calendar.leaves` groups by `holiday_id` to build a mapping of which calendar global leaves correspond to which HR leaves. This allows the function to pass `ignored_resource_calendar_leaves` to `_list_work_time_per_day` so that public holiday hours are excluded from leave timesheet calculation (prevents double-counting when an employee has both a personal leave and a public holiday on the same day).

**Old timesheet cleanup:**
Before creating new lines, any existing analytic lines with `holiday_id == leave.id` AND `project_id != False` are unlinked. This handles regeneration scenarios (e.g., when a global time-off update triggers re-generation of overlapping HR leave timesheets).

---

**`_timesheet_prepare_line_values(index, work_hours_data, day_date, work_hours_count, project, task)`:**

```python
{
    'name': _("Time Off (%(index)s/%(total)s)", index=index + 1, total=len(work_hours_data)),
    'project_id': project.id,
    'task_id': task.id,
    'account_id': project.sudo().account_id.id,
    'unit_amount': work_hours_count,   # hours as float (e.g., 8.0)
    'user_id': self.employee_id.user_id.id,
    'date': day_date,                  # date object, not datetime
    'holiday_id': self.id,
    'employee_id': self.employee_id.id,
    'company_id': task.sudo().company_id.id or project.sudo().company_id.id,
}
```

- `account_id` is pulled from `project.sudo().account_id` — requires sudo because the analytic account may have ACL restrictions.
- `user_id` links the timesheet to the employee's Odoo user for approval visibility.
- `company_id` is taken from the task first, then the project — supports the case where task and project belong to different companies in multi-company setups (though in practice they should match).

---

**`_check_missing_global_leave_timesheets()` — Public holiday gap-filling:**

```python
def _check_missing_global_leave_timesheets(self):
    # Searches for global time-off records within the leave's date range
    # Calls global_leaves._generate_public_time_off_timesheets(employee_ids)
```

Called after leave refusal/cancellation. Fills in any public holiday timesheets that were suppressed because the employee's personal leave overlapped the public holiday. This ensures employees don't lose public holiday timesheet entries just because they were on personal leave during those days.

---

**`action_refuse()` — Refusal cascade:**

```python
def action_refuse(self):
    result = super().action_refuse()
    timesheets = self.sudo().mapped('timesheet_ids')
    timesheets.write({'holiday_id': False})
    timesheets.unlink()
    self._check_missing_global_leave_timesheets()
    return result
```

- The `sudo()` call bypasses ACL on analytic lines (the employee may not have write permission on the analytic line).
- `holiday_id` is cleared before unlink so that `_unlink_except_linked_leave` does not trigger its own access check (it checks for `holiday_id` presence).
- `_check_missing_global_leave_timesheets()` runs after unlink so any days previously skipped due to overlapping personal leave now receive public holiday timesheets.

---

**`_action_user_cancel()` — User cancellation:**

Same pattern as `action_refuse()` but for user-initiated cancellation (via portal or employee self-service). Also calls `_check_missing_global_leave_timesheets()`.

---

**`_force_cancel(*args, **kwargs)` — HR manager force-cancel:**

```python
def _force_cancel(self, *args, **kwargs):
    super()._force_cancel(*args, **kwargs)
    timesheets = self.sudo().timesheet_ids
    timesheets.holiday_id = False
    timesheets.unlink()
```

Overrides the `hr_holidays` force-cancel method to also clean up timesheets.

---

**`write(vals)` — Date-change cleanup:**

```python
def write(self, vals):
    res = super().write(vals)
    for leave in self:
        if leave.number_of_days == 0 and leave.sudo().timesheet_ids:
            leave.sudo().timesheet_ids.holiday_id = False
            timesheet_ids_to_remove.extend(leave.timesheet_ids)
    self.env['account.analytic.line'].browse(set(timesheet_ids_to_remove)).sudo().unlink()
    return res
```

When a leave's dates are changed and the leave becomes zero-days (e.g., date_from and date_to collapsed to the same day then immediately split), any generated timesheet entries are cleaned up. Uses `set()` to deduplicate IDs since multiple leaves in the same write batch may share timesheets.

---

### `resource.calendar.leaves` — Public Holiday Timesheet Generation

**Defined in:** `project_timesheet_holidays/models/resource_calendar_leaves.py`

**Field added by this module:**

```python
timesheet_ids = fields.One2many(
    'account.analytic.line', 'global_leave_id', string="Analytic Lines"
)
```

---

**`_generate_timesheeets()` — Entry point, called on create:**

```python
def _generate_timesheeets(self):
    results_with_leave_timesheet = self.filtered(
        lambda r: not r.resource_id          # must be a global leave (not resource-specific)
        and r.company_id.internal_project_id  # company must have an internal project
        and r.company_id.leave_timesheet_task_id  # company must have a time-off task
    )
    if results_with_leave_timesheet:
        results_with_leave_timesheet._timesheet_create_lines()
```

Only global leaves (where `resource_id` is False) generate timesheets. Resource-specific leaves (individual calendar exceptions) are skipped.

---

**`_get_resource_calendars()` — Calendar resolution:**

```python
def _get_resource_calendars(self):
    leaves_with_calendar = self.filtered('calendar_id')  # calendar-specific global leave
    calendars = leaves_with_calendar.calendar_id           # specific calendar
    leaves_wo_calendar = self - leaves_with_calendar       # company-wide global leave
    if leaves_wo_calendar:
        calendars += self.env['resource.calendar'].search([
            ('company_id', 'in', leaves_wo_calendar.company_id.ids + [False]),
        ])
    return calendars
```

For company-wide global leaves (no `calendar_id`), it returns **all** calendars in the company plus any calendar with no company. This ensures that when a public holiday is created without a specific calendar, all employees in the company are covered.

---

**`_work_time_per_day(resource_calendars=None)` — Complex attendance interval calculation:**

This method computes work hours per day for each global leave, respecting the calendar's attendance schedule and excluding any overlapping resource-specific leave periods.

```
For each calendar in resource_calendars:
  1. Read group: get all global leaves (calendar-specific and company-wide) within self.
  2. For each leave, identify:
     - date_from_min, date_to_max (span of all leaves for this calendar)
     - resources (employees on this calendar)
     - leaves (all leave records)
  3. Call calendar._attendance_intervals_batch(date_from, date_to, resources, tz)
     → returns {resource_id: [(datetime, datetime, vals), ...]}
  4. For each work interval that overlaps the leave's date range:
     tmp_start = max(interval_start, leave.date_from)
     tmp_end   = min(interval_end,   leave.date_to)
     results[calendar_id][leave.id][tmp_start.date()] += (tmp_end - tmp_start).seconds / 3600
  5. Sort results by date.
```

**Important edge case:** This method handles the interaction between calendar-specific global leaves and company-wide global leaves. For company-wide global leaves (no `calendar_id`), it groups by `company_id` and applies those leaves to every calendar belonging to that company. This means a single global leave without a calendar generates timesheets for **all** employees in the company.

---

**`_timesheet_create_lines()` — Per-employee timesheet creation:**

```
1. Get all relevant calendars via _get_resource_calendars().
2. Get work_hours_data via _work_time_per_day().
3. Read group hr.employee by resource_calendar_id to get employees per calendar.
4. Read group hr.leave for all affected employees in the date range (state=validate).
   Build a map: {employee_id: [(date_from, date_to), ...]}
5. For each global leave in self:
   For each employee using that leave's calendar:
     For each (day_date, work_hours_count) in work_hours_data:
       Skip if employee has a validated leave covering day_date (prevent double-generation).
       Append _timesheet_prepare_line_values(...).
6. sudo().create(vals_list).
```

**Key filtering:** An employee on approved leave during a public holiday does **not** get a public holiday timesheet generated. The public holiday timesheet is suppressed in favor of the personal leave timesheet. This prevents double-counting hours.

**Performance note:** The `holidays_by_employee` read group fetches all validated leaves for all affected employees in the date range in a single query, avoiding N+1 within the inner loop.

---

**`_timesheet_prepare_line_values(index, employee_id, work_hours_data, day_date, work_hours_count)`:**

```python
{
    'name': _("Time Off (%(index)s/%(total)s)", ...),
    'project_id': employee_id.company_id.internal_project_id.id,
    'task_id': employee_id.company_id.leave_timesheet_task_id.id,
    'account_id': employee_id.company_id.internal_project_id.account_id.id,
    'unit_amount': work_hours_count,
    'user_id': employee_id.user_id.id,
    'date': day_date,
    'global_leave_id': self.id,
    'employee_id': employee_id.id,
    'company_id': employee_id.company_id.id,
}
```

Similar to `hr.leave._timesheet_prepare_line_values()` but uses `global_leave_id` instead of `holiday_id` and resolves project/task from `employee_id.company_id`.

---

**`_generate_public_time_off_timesheets(employees)` — Called from `hr.leave._check_missing_global_leave_timesheets`:**

Used when a personal leave is refused/cancelled. The personal leave may have suppressed public holiday timesheets (the employee was on leave during a public holiday). This method fills in those gaps by generating public holiday timesheets for the given employees where they are missing.

```
1. Get all public holiday global leaves in the date range (same as _check_missing_global_leave_timesheets).
2. For each global leave:
   For each employee:
     - Skip if calendar mismatch (if global leave has a calendar_id, it must match employee's calendar).
     - Get work hours for the leave from _work_time_per_day.
     - Check which dates already have global_leave_id timesheets for this employee.
     - Generate missing timesheet lines.
```

---

**`write(vals)` — Global time-off update triggers HR leave re-generation:**

```python
def write(vals):
    # If date_from, date_to, or calendar_id changed:
    #   1. Delete existing timesheets for the changed global leaves.
    #   2. Find overlapping hr.leave records (by company + date range + calendar).
    #   3. super().write(vals) — persist the change.
    #   4. Re-generate timesheets for the global leaves.
    #   5. Re-generate timesheets for overlapping HR leaves (passing ignored global leave IDs).
```

When a global time-off is modified, any existing timesheets are deleted first. Overlapping HR leaves are identified via `_get_overlapping_hr_leaves()`, which returns leaves whose date range overlaps and whose employee uses a compatible calendar. Those HR leaves have their timesheets re-generated with the global leave's ID explicitly excluded from `_list_work_time_per_day` (so hours on the public holiday are not double-counted).

---

**`@api.ondelete(at_uninstall=False) _regenerate_hr_leave_timesheets_on_gto_unlinked()`:**

```python
def _regenerate_hr_leave_timesheets_on_gto_unlinked(self):
    global_leaves = self.filtered(lambda l: not l.resource_id)
    for global_leave in global_leaves:
        overlapping_leaves += global_leave._get_overlapping_hr_leaves()
    if overlapping_leaves:
        overlapping_leaves.sudo()._generate_timesheets(ignored_resource_calendar_leaves=global_leaves.ids)
```

On delete of a global time-off, overlapping HR leaves may have had hours suppressed on the global leave's dates. This method re-generates those HR leave timesheets while ignoring the deleted global leave (so hours on that day are properly attributed to the personal leave, not the now-deleted public holiday). `at_uninstall=False` prevents the cascade from running during module uninstall.

---

### `account.analytic.line` — Security and Linkage

**Defined in:** `project_timesheet_holidays/models/account_analytic.py`

**Fields added by this module:**

```python
holiday_id = fields.Many2one(
    "hr.leave", string='Time Off Request', copy=False,
    index='btree_not_null'
)
global_leave_id = fields.Many2one(
    "resource.calendar.leaves", string="Global Time Off",
    index='btree_not_null', ondelete='cascade'
)
task_id = fields.Many2one(domain="[('allow_timesheets', '=', True),
                                     ('project_id', '=?', project_id),
                                     ('has_template_ancestor', '=', False),
                                     ('is_timeoff_task', '=', False)]")
```

**Indexes:**

```python
_timeoff_timesheet_idx = models.Index(
    '(task_id) WHERE (global_leave_id IS NOT NULL OR holiday_id IS NOT NULL) AND project_id IS NOT NULL'
)
```

Partial index for fast lookups of time-off timesheets by task when the time-off link is present. Reduces index size compared to a full index on `task_id`.

**`task_id` domain — key constraints:**
- `is_timeoff_task = False`: Explicitly prevents manual timesheet entry on a time-off task. This is enforced at the ORM level via `_check_can_create()`.
- `has_template_ancestor = False`: Prevents creating timesheets on template-derived tasks (subtasks from templates).
- `('project_id', '=?', project_id)`: Optional match — if `project_id` is set, the task must belong to that project; if `project_id` is False/null, this clause evaluates to True (no restriction).

---

**`_unlink_except_linked_leave()` — Delete protection:**

```python
def _unlink_except_linked_leave(self):
    if any(line.global_leave_id for line in self):
        raise UserError(_('You cannot delete timesheets linked to global time off.'))
    elif any(line.holiday_id for line in self):
        if not self.env.user.has_group('hr_holidays.group_hr_holidays_user') \
           and self.env.user not in self.holiday_id.sudo().user_id:
            raise UserError(error_message)
        action = self._get_redirect_action()
        raise RedirectWarning(error_message, action, _('View Time Off'))
```

- **Global leave timesheets**: Cannot be deleted by anyone. This enforces that public holiday timesheets are immutably tied to the company holiday record.
- **HR leave timesheets**: Deleted only if the current user is an HR holidays manager OR the leave owner. Otherwise a `RedirectWarning` is raised that redirects to the leave form with the message "Please cancel your time off request from the Time Off application instead."

**Note:** The `global_leave_id` field has `ondelete='cascade'` on the field definition, but this ORM-level check runs before any DB cascade. The combination means that deleting a `resource.calendar.leaves` record will cascade-delete its analytic lines at the DB level, bypassing this check — but direct unlink calls from Python code will hit it.

---

**`_check_can_write()` — Write protection:**

```python
def _check_can_write(self, values):
    if not self.env.su and self.holiday_id:
        raise UserError(_('You cannot modify timesheets linked to time off requests.'))
    return super()._check_can_write(values)
```

Only `superuser` (used in migrations, cron jobs, automated processes) can modify leave-linked timesheets. Regular users cannot write to these lines — they must cancel the leave instead, which triggers `action_refuse()` to delete and recreate lines as needed.

---

**`_check_can_create()` — Create protection:**

```python
def _check_can_create(self):
    if not self.env.su and any(task.is_timeoff_task for task in self.task_id):
        raise UserError(_('You cannot create timesheets for a task linked to a time off type.'))
    return super()._check_can_create()
```

Prevents manual timesheet entry on time-off tasks. Even HR managers cannot manually create entries on these tasks — they must go through the leave request flow. This ensures all leave timesheets are generated by the `_generate_timesheets()` logic and carry accurate hour allocations.

---

**`_get_favorite_project_id_domain(employee_id=False)` — Favorites exclusion:**

```python
def _get_favorite_project_id_domain(self, employee_id=False):
    return Domain.AND([
        super()._get_favorite_project_id_domain(employee_id),
        Domain('holiday_id', '=', False),
        Domain('global_leave_id', '=', False),
    ])
```

Time-off tasks are excluded from the timesheet "favorite projects" suggestions in the timesheet entry UI. Prevents employees from accidentally booking time to the internal project via the regular timesheet entry form.

---

### `project.task` — Time-Off Task Identification

**Defined in:** `project_timesheet_holidays/models/project_task.py`

**Fields added by this module:**

```python
leave_types_count = fields.Integer(
    compute='_compute_leave_types_count', string="Time Off Types Count"
)
is_timeoff_task = fields.Boolean(
    "Is Time off Task",
    compute="_compute_is_timeoff_task",
    search="_search_is_timeoff_task",
    export_string_translation=False,
    groups="hr_timesheet.group_hr_timesheet_user"
)
```

**`leave_types_count` — computed via `_compute_leave_types_count`:**

```python
def _compute_leave_types_count(self):
    timesheet_read_group = self.env['account.analytic.line']._read_group(
        [('task_id', 'in', self.ids),
         '|', ('holiday_id', '!=', False), ('global_leave_id', '!=', False)],
        ['task_id'],
        ['__count'],
    )
    # Count = number of distinct leave types (holiday_id + global_leave_id) per task
```

Counts how many distinct leave sources (individual + global) have generated timesheets on this task. Used as part of the `is_timeoff_task` determination.

**`is_timeoff_task` — computed via `_compute_is_timeoff_task`:**

```python
def _compute_is_timeoff_task(self):
    timeoff_tasks = self.filtered(
        lambda task: task.leave_types_count
                     or task.company_id.leave_timesheet_task_id == task
    )
    timeoff_tasks.is_timeoff_task = True
    (self - timeoff_tasks).is_timeoff_task = False
```

A task is marked as a time-off task if either:
1. It has at least one timesheet line with a `holiday_id` or `global_leave_id` (i.e., it's been used as a leave timesheet target), OR
2. It is the current company's configured `leave_timesheet_task_id`.

Condition 2 is dynamic — if the company's time-off task is reassigned, the new task becomes the `is_timeoff_task` even without any timesheet history.

**`is_timeoff_task` — searchable via `_search_is_timeoff_task`:**

```python
def _search_is_timeoff_task(self, operator, value):
    if operator != 'in':
        return NotImplemented
    # Query DISTINCT task_id from account_analytic_line
    #   WHERE task_id IS NOT NULL
    #   AND (holiday_id IS NOT NULL OR global_leave_id IS NOT NULL)
    # Add current company's leave_timesheet_task_id to the set
    return Domain('id', 'in', tuple(timeoff_tasks_ids))
```

Enables domain filters on `is_timeoff_task` (e.g., `[('is_timeoff_task', '=', True)]`) in the UI, such as the `task_id` domain in `account.analytic.line`.

**Security note:** `is_timeoff_task` has `groups="hr_timesheet.group_hr_timesheet_user"` — non-timesheet users cannot see this field. However, the field's logic still functions for access control checks (the `_check_can_create` method uses `task.is_timeoff_task` directly without a groups check).

---

### `res.config.settings` — Company-Level Configuration

**Defined in:** `project_timesheet_holidays/models/res_config_settings.py`

Inherits the form defined by `hr_timesheet` (which inherits from `hr`).

**Fields:**

```python
internal_project_id = fields.Many2one(
    related='company_id.internal_project_id',
    required=True,          # enforced at company field level, not here
    string="Internal Project",
    domain="[('company_id', '=', company_id), ('is_template', '=', False)]",
    readonly=False,
    help="The default project used when automatically generating timesheets via time off requests."
)
leave_timesheet_task_id = fields.Many2one(
    related='company_id.leave_timesheet_task_id',
    string="Time Off Task",
    readonly=False,
    domain="[('company_id', '=', company_id),
             ('project_id', '=?', internal_project_id),
             ('has_template_ancestor', '=', False)]",
    help="The default task used when automatically generating timesheets via time off requests."
)
```

**Onchange: `_onchange_timesheet_project_id()`:**

```python
def _onchange_timesheet_project_id(self):
    if self.internal_project_id != self.leave_timesheet_task_id.project_id:
        self.leave_timesheet_task_id = False
```

Clears the task when the project is changed to a different one, since the task domain restricts to the selected project. Prevents a stale task from being saved that belongs to a different project.

**Onchange: `_onchange_timesheet_task_id()`:**

```python
def _onchange_timesheet_task_id(self):
    if self.leave_timesheet_task_id:
        self.internal_project_id = self.leave_timesheet_task_id.project_id
```

When a task is selected, the project field is automatically populated from the task's project. This keeps the two fields in sync and ensures the task always belongs to the shown project.

**XML placement:** Fields are inserted inside the existing `timesheet_off_validation_setting` group in the HR Timesheet settings form, below the timesheet validation toggle.

---

### `hr.employee` — Employee Lifecycle Timesheet Management

**Defined in:** `project_timesheet_holidays/models/hr_employee.py`

No additional fields. All logic is in method overrides.

**`create(vals_list)` — New employee backfill:**

```python
def create(self, vals_list):
    employees = super().create(vals_list)
    if self.env.context.get('salary_simulation'):
        return employees
    self.with_context(allowed_company_ids=employees.company_id.ids) \
        ._create_future_public_holidays_timesheets(employees)
    return employees
```

- Skips timesheet generation during salary simulation (in `hr_contract` module).
- Uses `allowed_company_ids` context to ensure only the relevant company's global leaves are considered.
- Only generates timesheets for public holidays **after** the employee creation date (prevents backfilling past holidays).

**`write(vals)` — Calendar changes and active state:**

```
Trigger 'active' change:
  - active=True (reactivate): _create_future_public_holidays_timesheets()
  - active=False (deactivate): _delete_future_public_holidays_timesheets()

Trigger 'resource_calendar_id' change:
  - _delete_future_public_holidays_timesheets()
  - _create_future_public_holidays_timesheets() with new calendar
```

Calendar changes cause a full regenerate: old future global leave timesheets are deleted and new ones created based on the new schedule. This correctly handles the case where an employee's working days change (e.g., switching from 5-day to 3-day schedule).

**`_delete_future_public_holidays_timesheets()`:**

```python
def _delete_future_public_holidays_timesheets(self):
    future_timesheets = self.env['account.analytic.line'].sudo().search([
        ('global_leave_id', '!=', False),
        ('date', '>=', fields.Date.today()),
        ('employee_id', 'in', self.ids)
    ])
    future_timesheets.write({'global_leave_id': False})
    future_timesheets.unlink()
```

Only future timesheets (date >= today) are deleted. Past global leave timesheets are preserved for historical reporting accuracy. The `global_leave_id` is cleared before unlink to prevent `_unlink_except_linked_leave` from blocking the deletion.

**`_create_future_public_holidays_timesheets(employees)`:**

```
1. Get all company-wide global leaves (calendar_id=False, resource_id=False) from today onward.
2. Group them by company.
3. For each employee:
   a. Get employee's calendar global_leave_ids from today onward.
   b. Combine with company-wide global leaves.
   c. Call global_leave._work_time_per_day() for the employee's calendar.
   d. For each day/hours pair, append _timesheet_prepare_line_values(...).
4. sudo().create(all vals).
```

Note: `_work_time_per_day` is called per-employee to get calendar-specific attendance intervals, ensuring correct hours on different calendar schedules.

---

## Security

**`security/ir.model.access.csv`:**

```
access_account_analytic_account_leaves_manager,
account.analytic.account,
analytic.model_account_analytic_account,
hr_holidays.group_hr_holidays_manager,1,0,0,0
```

Gives `hr_holidays.group_hr_holidays_manager` read-only access to `account.analytic.account` (analytic account). This is a minimal ACL — the primary security for time-off timesheets is enforced in ORM method overrides, not record rules.

**ACL-enforced protections:**

| Action | Who can do it |
|--------|---------------|
| Unlink analytic line linked to global leave | No one — always blocked |
| Unlink analytic line linked to HR leave | HR Holidays Manager, or leave owner |
| Write to leave-linked analytic line | superuser only |
| Create analytic line on time-off task | superuser only |
| Delete time-off task | HR Holidays Manager (project.task ACL) |

**Record rules:** None defined in this module. Access to leave-linked timesheets is controlled by the method overrides above.

---

## Data Files

**`data/holiday_timesheets_demo.xml` — Demo data initialization:**

```xml
<function model="hr.leave" name="_remove_resource_leave">
    <value eval="[...]"/><!-- SL, CL, SL QDP leave type external IDs -->
</function>
<function model="hr.leave" name="_create_resource_leave">
    <value eval="[...]"/>
</function>
```

Demo data ensures that after the module demo data loads, the `resource.calendar.leaves` (resource leaves) and `hr.leave` records are synchronized. The `_remove_resource_leave` call removes any stale resource leaves, then `_validate_leave_request` is called to re-generate timesheets, then `_create_resource_leave` is called to create resource leaves for the validated leaves. This demo data is part of the overall `hr_holidays` demo scenario.

---

## Views

**`views/res_config_settings_views.xml`:**

Inherits the HR Timesheet settings form. Places `internal_project_id` and `leave_timesheet_task_id` inside the `timesheet_off_validation_setting` group as a labeled row. Only visible when `module_project_timesheet_holidays` is True.

**`views/project_task_views.xml`:**

Inherits `hr_timesheet.view_task_form2_inherited`. Adds `is_timeoff_task` as an invisible field, then sets the `timesheet_ids` tree view to `readonly` when `is_timeoff_task` is True. This makes the timesheet entries on the Time Off task read-only in the task form view — they must be modified by cancelling the leave, not by editing the lines directly.

---

## Post-Init Hook

```python
def post_init(env):
    type_ids_ref = env.ref('hr_timesheet.internal_project_default_stage', ...)
    companies = env['res.company'].search([
        '|', ('internal_project_id', '=', False),
             ('leave_timesheet_task_id', '=', False)
    ])
    for company in companies:
        # Create internal project if missing
        # Create Time Off task if missing
        # Link both to company
```

Ensures all existing companies without the internal project and task get them provisioned on module installation.

---

## Performance Considerations

| Operation | Performance Note |
|-----------|-----------------|
| Leave approval `_generate_timesheets` | Single `sudo().search([('holiday_id', 'in', leave_ids)])` for old-timesheet cleanup. `_list_work_time_per_day` uses efficient attendance interval batch computation. |
| Global leave creation `_timesheet_create_lines` | Single `_read_group` for all employees in all affected calendars. `holidays_by_employee` is a single read-group for all employees. O(1) queries regardless of leave count. |
| Global leave `write` | Regenerates both the global leave timesheets and overlapping HR leave timesheets. Worst case: O(n) where n = number of overlapping leaves. |
| Employee `write` (calendar change) | Full regenerate: delete all future + create all future. Two queries plus N creates. Acceptable for single-employee changes. |
| `is_timeoff_task` search | Uses `execute_query` with direct SQL for the DISTINCT subquery — bypasses ORM for performance when searching large task sets. |

---

## Edge Cases and Failure Modes

1. **No internal project/task configured**: Leaves are silently skipped in `_generate_timesheets`. No error is raised — the leave is approved without timesheet generation. A post-init hook and settings form guide users to configure these.

2. **Employee with no calendar**: Falls back to employee's `tz` directly in flexible hours calculation. In non-flexible path, `_list_work_time_per_day` is called with the employee directly — the method handles None calendar gracefully.

3. **Overlapping global leave and HR leave on same day**: Public holiday timesheet is suppressed (employee already has a personal leave timesheet for that day). The day is not double-counted.

4. **Global leave date range change**: Old timesheets are deleted and re-created. If overlapping HR leaves exist, their timesheets are also regenerated. If the global leave is deleted, overlapping HR leaves have their timesheets regenerated with the now-deleted global leave excluded.

5. **Leave dates changed after approval**: `write()` cleans up zero-day timesheets. `_generate_timesheets()` is not re-called automatically — employees must re-validate the leave to regenerate timesheets, or HR manager must manually trigger re-generation.

6. **Salary simulation context**: `_create_future_public_holidays_timesheets` is skipped during contract salary simulation, preventing unwanted timesheet generation during what-if planning.

7. **`resource_id` on global leave**: Resource-specific leaves (where `resource_id` is set) are filtered out in `_generate_timesheeets()` and do not generate timesheets. These are individual calendar exceptions, not public holidays.

8. **Multi-company**: Each company has its own internal project and time-off task. Global leaves are scoped to a company, so employees in different companies see only their company's public holidays. HR leaves respect `company_id` on the leave record.

---

## Related

- [Modules/hr_holidays](odoo-18/Modules/hr_holidays.md) — Leave management (approval, refusal, cancellation)
- [Modules/hr_timesheet](odoo-18/Modules/hr_timesheet.md) — Timesheet entry (analytic lines, internal project creation)
- [Modules/project](odoo-18/Modules/project.md) — Project and task models
- [Modules/Account](odoo-18/Modules/account.md) — Analytic account for project accounting
- [Core/Fields](odoo-18/Core/Fields.md) — Many2one, One2many, computed fields
---

## L4: Expanded Security & ORM Override Chain

### Security: `_get_redirect_action()` — User-Friendly Access Denial

**File:** `models/account_analytic.py`, lines 20-26

```python
def _get_redirect_action(self):
    return {
        'type': 'ir.actions.act_window',
        'name': _('Time Off'),
        'res_model': 'hr.leave',
        'view_mode': 'form',
        'res_id': self.holiday_id.id,
    }
```

Returns a `RedirectWarning`-compatible action dict. Used only in `_unlink_except_linked_leave()` when a non-HR-manager non-owner tries to delete an HR leave timesheet. The `RedirectWarning` (raised alongside the `UserError`) redirects the user to the leave form with a message encouraging them to cancel the leave instead.

**Note:** This method exists but is currently only called in the `UserError`/`RedirectWarning` combination in `_unlink_except_linked_leave()`. It could be overridden in custom modules to redirect to a different action (e.g., a custom helpdesk ticket).

---

### Security: `_check_can_write()` — Superuser Lockout

**File:** `models/account_analytic.py`, lines 48-52

```python
def _check_can_write(self, values):
    if not self.env.su and self.holiday_id:
        raise UserError(_('You cannot modify timesheets linked to time off requests.'))
    return super()._check_can_write(values)
```

The `self.env.su` check is the Odoo superuser flag — it is `True` when the code is running as the database superuser (e.g., during module upgrades, migrations, or cron jobs). This means:
- Regular users: always blocked from writing leave-linked timesheets
- Superuser (admin, migration scripts): always allowed

**Key design insight:** The check is on `self.holiday_id` (not `global_leave_id`). Global leave timesheets are protected at the unlink level, not the write level — they are completely immutable at the ORM layer. An administrator could directly SQL-update a global leave timesheet, but attempting it via ORM write() hits this check.

---

### Security: `_unlink_except_linked_leave()` — Double Protection on Global Leaves

```python
def _unlink_except_linked_leave(self):
    if any(line.global_leave_id for line in self):
        raise UserError(...)
    elif any(line.holiday_id for line in self):
        if not is_manager and user != owner:
            raise UserError(...)
        raise RedirectWarning(...)
```

**Interaction with `ondelete='cascade'`:**
The `global_leave_id` field has `ondelete='cascade'` on the field definition. This means: if a `resource.calendar.leaves` record is deleted at the database level, the ORM will automatically delete all `account.analytic.line` records where `global_leave_id = that_record`. This database-level cascade **bypasses** the Python-level `_unlink_except_linked_leave()` check.

In practice this means:
- Direct Python `unlink()` calls: blocked for global leave timesheets
- Database-level cascade from `resource.calendar.leaves` deletion: allowed (cascades silently)

This is a known interaction — the `ondelete='cascade'` on the field takes precedence over the Python-level protection. The protection primarily guards against application-level deletion attempts.

**Interaction with `sudo()` in `action_refuse()`:**
In `hr_leave.action_refuse()`, the code calls `sudo()` before accessing `timesheet_ids` and again before writing/unlinking. This is necessary because:
1. The current user (employee) may not have write access to `account.analytic.line`
2. But the leave's timesheets belong to their own leave record
3. Without `sudo()`, the access check would fail before reaching `_unlink_except_linked_leave`

The `sudo()` bypasses all ACL checks, making the write/unlink always succeed. After `sudo()`, the `holiday_id` is cleared in Python before `unlink()` — this prevents the ORM from hitting the `_unlink_except_linked_leave()` check during the cascade.

---

### Security: `is_timeoff_task` Groups Restriction vs. Logic Enforcement

```python
is_timeoff_task = fields.Boolean(
    compute="_compute_is_timeoff_task",
    search="_search_is_timeoff_task",
    groups="hr_timesheet.group_hr_timesheet_user"
)
```

**Groups-restricted field, non-groups-restricted logic:**
The `groups` attribute means non-timesheet users cannot read or write this field. However, `_check_can_create()` calls `task.is_timeoff_task` directly without a `groups` check:

```python
def _check_can_create(self):
    if not self.env.su and any(task.is_timeoff_task for task in self.task_id):
        raise UserError(...)
```

For a non-timesheet user: `is_timeoff_task` returns `False` (field not accessible, defaults to False). This means `_check_can_create()` would NOT block them — the protection doesn't work for non-timesheet users. However, non-timesheet users typically cannot access the timesheet entry form at all, so this is unlikely to be a real exploit vector.

---

### Security: `_check_can_write()` in Multi-Company Context

The `_check_can_write()` method checks `self.env.su` but does NOT check `company_id` matching. In a multi-company environment:
- A superuser from Company A can write to a leave-linked timesheet belonging to Company B
- This is consistent with Odoo's superuser model (superuser bypasses all company restrictions)

If strict company isolation is required, custom code would need to override `_check_can_write()` to add company matching.

---

## L4: Version Changes — Odoo 18 to 19

The `project_timesheet_holidays` module has minimal Odoo 18 to 19 changes — it is a thin bridge module whose core logic (timesheet generation on leave approval) remained stable across versions.

### Module Auto-Install Behavior

Odoo 19 added improved auto-install resolution for cross-module dependencies. The `project_timesheet_holidays` module depends on both `hr_timesheet` and `hr_holidays`. In Odoo 18, auto-install was resolved at module load time. In Odoo 19, the auto-install system uses a dependency graph that ensures the module is installed automatically when both dependencies are present, even if they are installed in different installation batches.

### `resource.calendar.leaves` — Work Time Computation

No significant changes to the `_work_time_per_day()` logic between Odoo 18 and 19. The method's complexity (handling overlapping global leaves, calendar-specific vs. company-wide leaves) was already well-established in Odoo 18.

### `hr.employee` — Calendar Change Handling

The write-triggered regenerate on calendar change (`write()` → delete future → create future) was present in Odoo 18. No changes in Odoo 19.

### `is_timeoff_task` Compute/Search

The `is_timeoff_task` field with its SQL-based `_search_is_timeoff_task()` was introduced in Odoo 18 or earlier as a way to efficiently identify time-off tasks across large task datasets. No changes in Odoo 19.

### `account.analytic.line` — `holiday_id`/`global_leave_id` Field Addition

These fields were added as part of the initial module design (not a specific version migration). The `index='btree_not_null'` optimization was likely added in a later version — it reduces index size by only indexing non-null entries, which is significant for large timesheet tables where most entries are not leave-linked.

---

## L4: Hooks and Data Flow Summary

### Complete Timesheet Generation Data Flow

```
LEAVE APPROVAL (hr.leave._validate_leave_request)
    └─ _generate_timesheets()
         ├─ Read resource.calendar.leaves grouped by holiday_id
         │   └─ Builds ignored_resource_calendar_leaves for overlap detection
         ├─ Per leave: compute work hours via employee._list_work_time_per_day()
         │   └─ Flexible hours branch: bypasses interval computation
         ├─ Delete old timesheets: sudo().search([('holiday_id', '=', leave.id)])
         └─ Create new timesheets: sudo().create(vals_list)
              └─ vals: name, project_id, task_id, account_id, unit_amount,
                       user_id, date, holiday_id, employee_id, company_id

GLOBAL LEAVE CREATION (resource.calendar.leaves.create)
    └─ _generate_timesheeets() (note: typo in method name)
         ├─ Filter to global leaves only (resource_id = False)
         ├─ Get all relevant calendars via _get_resource_calendars()
         ├─ Compute work hours via _work_time_per_day()
         ├─ Read hr.employee grouped by calendar
         ├─ Read hr.leave for all employees (find overlaps)
         └─ Create per-employee timesheets
              └─ Skip if employee has approved leave covering that day

EMPLOYEE LIFECYCLE (hr.employee.create/write)
    ├─ create(): _create_future_public_holidays_timesheets()
    │   └─ Creates timesheets for company-wide global leaves from today
    └─ write(active=False): _delete_future_public_holidays_timesheets()
         └─ Only future timesheets (date >= today); past preserved

LEAVE REFUSAL (hr.leave.action_refuse)
    ├─ Clear holiday_id on timesheets in Python
    ├─ Unlink timesheets (now unlinkable without hitting protection)
    └─ _check_missing_global_leave_timesheets()
         └─ Fill gaps: any public holiday days missed due to overlap
```

### `sudo()` Usage Map

| Location | Purpose | Risk |
|----------|---------|------|
| `hr_leave._generate_timesheets()` | Create AAL records on behalf of employees | Low — only creates, doesn't expose data |
| `hr_leave.action_refuse()` | Unlink AAL records from refused leaves | Low — only unlinks own leave's timesheets |
| `hr_employee._create_future_public_holidays_timesheets()` | Create AAL for new employees | Low — only creates |
| `hr_employee._delete_future_public_holidays_timesheets()` | Delete old AAL before regenerate | Low — only deletes own company's timesheets |
| `resource_calendar_leaves._timesheet_create_lines()` | Create AAL for all employees on holiday | Low — creates for valid global leaves only |
| `account_analytic._check_can_write()` | Superuser bypass | Required for migrations/cron |

### Key Invariants

1. **Time-off task identity**: A task is `is_timeoff_task=True` if it has ever received a leave-linked timesheet OR it is the company's `leave_timesheet_task_id`. This means the task remains marked as a time-off task even after all leave timesheets are deleted.

2. **No manual timesheet on time-off task**: `_check_can_create()` prevents manual entry. All time-off timesheets must come through `_generate_timesheets()`. This ensures `unit_amount` accurately reflects the employee's work schedule.

3. **Global leave timesheet immutability**: No user (including HR managers) can delete or modify a global leave timesheet at the ORM level. Only the global leave itself can be modified/deleted, which then cascades at the DB level.

4. **Overlap suppression**: When an employee has both a personal leave and a public holiday on the same day, only the personal leave timesheet is generated. The public holiday timesheet is suppressed to avoid double-counting. If the personal leave is later cancelled, `_check_missing_global_leave_timesheets()` fills the gap.

5. **Past timesheets preserved**: Employee calendar changes and global leave date changes only affect future timesheets (date >= today). Historical timesheets are never deleted or regenerated, preserving accurate historical reporting.
