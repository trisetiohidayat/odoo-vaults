---
title: project_timesheet (hr_timesheet)
created: 2026-04-11
tags: [odoo, odoo19, modules, timesheet, hr, project, analytic]
---

# project_timesheet / hr_timesheet Module

## Module Overview

> **Important**: In Odoo 19, the former `project_timesheet` module was merged into `hr_timesheet`. The `project_timesheet` technical name no longer exists as a standalone module. All timesheet functionality for projects is now part of `hr_timesheet`, which also handles HR-level timesheet features. This document covers the full module at `hr_timesheet`.

**Technical Name**: `hr_timesheet`
**Category**: Services/Timesheets
**Depends**: `hr`, `hr_hourly_cost`, `analytic`, `project`, `uom`
**Author**: Odoo S.A.
**License**: LGPL-3

The `hr_timesheet` module is the core integration layer between the Project Management (`project`) and HR Timesheet (`hr_timesheet`) systems. It enables time tracking on projects and tasks, links timesheet lines (`account.analytic.line`) to project tasks, provides billable/non-billable tracking, and delivers comprehensive reporting on time spent across the organization.

## Architecture: Two-Layer Model

The module operates on two distinct layers:

```
project.project ──One2many──> account.analytic.line (timesheets)
       │
       └── project.task ──One2many──> account.analytic.line (task timesheets)

Each account.analytic.line represents a single timesheet entry (a row of time logged).
```

### Key Design Principles

1. **`account.analytic.line` is the central record**: Every timesheet entry is a line in the analytic accounting system. The `hr_timesheet` module extends this model with project/task references, employee links, and computed costs.
2. **Bidirectional linking**: Timesheets link to both `project_id` (for project-level logs) and `task_id` (for task-level logs). Changing one can cascade to the other.
3. **Company-aware**: All timesheet operations respect multi-company constraints. The company is derived from the employee, project, or task context.
4. **Lazy favorite project**: The default project for a new timesheet is computed as the most-frequently-used project by the current user (mode of last 5 timesheets).

---

## Models Inventory

### 1. `account.analytic.line` — Timesheet Entry (Core Extended Model)

**Inherited from**: `account.analytic.line` (in `analytic` module)
**File**: `hr_timesheet/models/hr_timesheet.py`

This is the central model. Every row in the timesheet grid is an `account.analytic.line` record. The `hr_timesheet` module extends it with project/task/employee relationships, computed costs, and company-aware UoM handling.

#### Fields

| Field | Type | Purpose |
|-------|------|---------|
| `task_id` | Many2one (`project.task`) | Task this line is logged against. Computed from `project_id`/`task_id` relationship. Domain: only tasks with `allow_timesheets=True`. Indexed with `btree_not_null`. |
| `parent_task_id` | Many2one (`project.task`) | Parent of `task_id`. Stored and indexed. Used for hierarchical timesheet rollup. |
| `project_id` | Many2one (`project.project`) | Project this line belongs to. Domain: only projects with `allow_timesheets=True` and `is_template=False`. Non-approvers see only projects where they are a follower or partner, or with `privacy_visibility` in `['employees', 'portal']`. |
| `user_id` | Many2one (`res.users`) | User who owns this timesheet. Computed from `employee_id.user_id`. Writeable to allow reassignment. |
| `employee_id` | Many2one (`hr.employee`) | Employee whose time is being tracked. Domain filters by allowed companies. For non-approvers, restricted to their own employee. This is the anchor for `hourly_cost`. |
| `job_title` | Char (related) | Read-only related field to `employee_id.job_title`. |
| `department_id` | Many2one (`hr.department`) | Employee's department. Computed (`store=True`) from `employee_id.department_id`. Used for department-level reporting. |
| `manager_id` | Many2one (`hr.employee`) | Employee's manager. Related to `employee_id.parent_id`, stored. |
| `encoding_uom_id` | Many2one (`uom.uom`) | Unit of measure for encoding display. Computed from `company_id.timesheet_encode_uom_id`. |
| `partner_id` | Many2one (`res.partner`) | Partner (customer). Computed: `task_id.partner_id` or fallback to `project_id.partner_id`. Stored and writable. |
| `readonly_timesheet` | Boolean | Whether this timesheet line is read-only for the current user. Computed via `_compute_readonly_timesheet()`. Portal users and external users see this as `True`. Internal users depend on `_is_readonly()` override (e.g., MRP module locks timesheets on done manufacturing orders). |
| `milestone_id` | Many2one (`project.milestone`) | Related to `task_id.milestone_id`. Used for milestone-based progress tracking. |
| `message_partner_ids` | Many2many (`res.partner`) | Followers of this timesheet. Computed as union of `task_id` and `project_id` followers. Used for portal access rules. |
| `calendar_display_name` | Char | Computed display name shown in calendar view: `"Project Name (8h30)"` or `"Project Name (2.5d)"` depending on encoding UoM (hours vs days). |

#### Methods

##### `_domain_project_id()`
Returns the domain for the `project_id` selection field.

```python
def _domain_project_id(self):
    domain = Domain([('allow_timesheets', '=', True), ('is_template', '=', False)])
    if not self.env.user.has_group('hr_timesheet.group_timesheet_manager'):
        domain &= Domain('privacy_visibility', 'in', ['employees', 'portal']) | Domain('message_partner_ids', 'in', [self.env.user.partner_id.id])
    return domain
```

- **Non-managers**: Can only select projects with `privacy_visibility` in `employees` or `portal`, OR where they are a follower.
- **Managers**: Can select any active timesheet-enabled project.

##### `_domain_employee_id()`
Returns the domain for `employee_id`.

```python
def _domain_employee_id(self):
    domain = Domain('company_id', 'in', self.env.context.get('allowed_company_ids'))
    if not self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver'):
        domain &= Domain('user_id', '=', self.env.user.id)
    return domain
```

- **Non-approvers**: Can only log time against their own employee.
- **Approvers**: Can log time against any employee in their allowed companies.

##### `_get_favorite_project_id()`
Returns the most frequently used project (mode of last 5 timesheet entries) for the given employee. Falls back to the company's `internal_project_id` if no history exists and the internal project is accessible.

```python
def _get_favorite_project_id(self, employee_id=False):
    last_timesheets = self.search_fetch(
        self._get_favorite_project_id_domain(employee_id), ['project_id'], limit=5
    )
    if not last_timesheets:
        internal_project = self.env.company.internal_project_id
        return internal_project.has_access('read') and internal_project.active and internal_project.allow_timesheets and internal_project.id
    return mode([t.project_id.id for t in last_timesheets])
```

##### `default_get()`
Pre-fills defaults when opening the timesheet view. Sets `employee_id` from `user_id` if not provided, and auto-selects the favorite project when `is_timesheet` context flag is set.

##### `_compute_project_id()`
Auto-syncs `project_id` from `task_id`. If a task is set and its project differs from the current `project_id`, the `project_id` is updated to match.

```python
def _compute_project_id(self):
    for line in self:
        if not line.task_id.project_id or line.project_id == line.task_id.project_id:
            continue
        line.project_id = line.task_id.project_id
```

##### `_onchange_project_id()`
Resets `task_id` when the project changes, preventing mismatched project/task combinations.

##### `_compute_partner_id()`
Sets `partner_id` to the task's partner, falling back to the project's partner. This ensures correct customer billing references on timesheet lines.

##### `_compute_user_id()`
Derives `user_id` from `employee_id.user_id`. If no employee is set, uses `_default_user()` (current user from context).

##### `_compute_department_id()`, `_compute_encoding_uom_id()`, `_compute_message_partner_ids()`
Standard computed fields for department, encoding UoM, and follower tracking.

##### `_compute_display_name()`
Custom display name for timesheet lines with a project:

```python
def _compute_display_name(self):
    analytic_line_with_project = self.filtered('project_id')
    super(AccountAnalyticLine, self - analytic_line_with_project)._compute_display_name()
    for analytic_line in analytic_line_with_project:
        if analytic_line.task_id:
            analytic_line.display_name = f"{analytic_line.project_id.sudo().display_name} - {analytic_line.task_id.sudo().display_name}"
        else:
            analytic_line.display_name = analytic_line.project_id.display_name
```

##### `_compute_calendar_display_name()`
Formats the timesheet for calendar view display. Shows hours (e.g., `8h30`) or days (e.g., `2.5d`) depending on the company's encoding UoM setting.

##### `_is_readonly()`
Hook method, overridable by other modules (e.g., `mrp` locks timesheets on done orders). Returns `False` by default.

```python
def _is_readonly(self):
    self.ensure_one()
    return False
```

##### `_compute_readonly_timesheet()`
Sets `readonly_timesheet = True` for portal/external users. For internal users, delegates to `_is_readonly()` for each line.

##### `create(vals_list)` — **Critical Override**
This is the most complex method in the module. It handles batch creation of timesheet lines with extensive preprocessing:

1. **Collects user_ids and employee_ids** from all vals in the list
2. **Validates work intervals** when creating from calendar view (`timesheet_calendar` context): skips employees not working on the specified date
3. **Resolves company** from task, project, or explicit `company_id` field
4. **Sets analytic accounts** via `_timesheet_preprocess_get_accounts()`: validates mandatory plan columns exist on the project
5. **Sets `product_uom_id`** to company's `project_time_mode_id` if not provided
6. **Normalizes employee assignment** (case B in code comments): if `employee_id` is not provided, looks up the active employee by `user_id` within the target company. Raises `ValidationError` if no valid employee found.
7. **Creates lines** via `super().create()`
8. **Postprocesses** each line via `_timesheet_postprocess()` to compute amounts
9. **Sends notification** in calendar view mode with success/failure message

**Key behavior**: When batch-creating from the timesheet calendar, employees without valid work intervals on the given date are silently skipped. A notification is sent via the bus indicating how many were created vs. skipped.

##### `write(vals)`
Handles timesheet updates with access control and validation:

1. **`_check_can_write()`**: Non-approvers and non-superusers can only modify their own timesheets. Raises `AccessError` otherwise.
2. **Private task check**: Raises `ValidationError` if attempting to set a private task (task without project).
3. **Company auto-set**: Derives company from task or project if not provided.
4. **Archived employee check**: Prevents setting an archived employee on existing timesheets.
5. **Account sync**: Updates analytic accounts via `_timesheet_preprocess_get_accounts()`.
6. **Postprocess**: Recomputes amounts via `_timesheet_postprocess()`.

##### `_check_can_write(values)`
Access control for writes. Raises `AccessError` if a basic user attempts to modify another user's timesheet.

##### `_check_can_create()`
Hook for subclasses (e.g., `sale_timesheet`) to add creation access checks.

##### `_timesheet_preprocess_get_accounts(vals)`
Validates that the project has all mandatory analytic plan columns set. Raises `ValidationError` listing missing plan names. Returns a dict mapping column names to analytic account IDs.

##### `_timesheet_postprocess(values)` / `_timesheet_postprocess_values(values)`
Hook pattern for post-creation/writing processing. Computes and writes the `amount` field based on `unit_amount` and the employee's hourly cost:

```python
cost = timesheet._hourly_cost()          # from employee_id.hourly_cost
amount = -timesheet.unit_amount * cost  # negative because it's a cost
amount_converted = employee_currency._convert(
    amount, account_currency, company, date
)
```

Also validates that the analytic account is active and that all related entities (project, task, analytic accounts) belong to the same company.

##### `_timesheet_get_portal_domain()`
Returns the domain used for portal (external user) access to timesheets:

```python
def _timesheet_get_portal_domain(self):
    if self.env.user.has_group('hr_timesheet.group_hr_timesheet_user'):
        return self.env['ir.rule']._compute_domain(self._name)
    return (
        Domain('message_partner_ids', 'child_of', [...commercial_partner_id])
        | Domain('partner_id', 'child_of', [...commercial_partner_id])
    ) & Domain('project_id.privacy_visibility', 'in', ['invited_users', 'portal'])
```

##### `_split_amount_fname()`
Returns `'unit_amount'` for timesheet lines (splits quantity, not amount, since amount is postprocessed from quantity x cost).

##### `_hourly_cost()`
Returns `employee_id.hourly_cost or 0.0`. The cost comes from the `hr_hourly_cost` module which adds the `hourly_cost` field to `hr.employee`.

##### `_is_timesheet_encode_uom_day()`
Returns `True` if the company's `timesheet_encode_uom_id` is the "Day" UoM. Used throughout the UI to switch between hour-based and day-based display.

##### `get_unusual_days(date_from, date_to=None)`
Returns unusual days (public holidays, company holidays) for the current user's employee. Delegates to `hr.employee._get_unusual_days()`.

##### `get_import_templates()`
Returns an Excel import template path when the context has `is_timesheet=True`, enabling CSV/XLSX import of timesheet data.

##### `get_views(views, options=None)`
Toolbar customization: removes the MRP WIP report print button from timesheet views when the timesheet UoM widget is used.

##### `_get_report_base_filename()`
Returns the report filename: `"Timesheets - {task_name}"` for single-task reports, or `"Timesheets"` for multi-task.

---

### 2. `project.project` — Project Extended (Timesheet Integration)

**Inherited from**: `project.project`
**File**: `hr_timesheet/models/project_project.py`

Adds timesheet configuration, tracking, and auto-analytic-account creation to projects.

#### Fields

| Field | Type | Purpose |
|-------|------|---------|
| `allow_timesheets` | Boolean | Master switch enabling timesheet recording on this project. Default `True`. Compute-when-origin-exists pattern: if a project has no `account_id`, this is set to `False` (projects need an analytic account to track timesheets). Writeable with `readonly=False`. |
| `account_id` | Many2one (`account.analytic.account`) | The analytic account linked to this project. Domain includes company and partner matching. This is the anchor for all timesheet accounting. |
| `analytic_account_active` | Boolean (related) | Convenience field: `account_id.active`. Used in UI to show if the analytic account is archived. |
| `timesheet_ids` | One2many (`account.analytic.line`, `project_id`) | All timesheet lines logged against this project (direct, not through tasks). Used for project-level totals. |
| `timesheet_encode_uom_id` | Many2one (`uom.uom`) | The UoM used for encoding/displaying timesheet hours on this project. Computed from `company_id.timesheet_encode_uom_id`. |
| `total_timesheet_time` | Float | Total time recorded on this project, converted to the encoding UoM. Rounded to 2 decimal places. Group-restricted: only visible to `group_hr_timesheet_user`. |
| `encode_uom_in_days` | Boolean | Convenience flag: `True` if encoding UoM is "Day". |
| `is_internal_project` | Boolean | `True` if this project is the company's `internal_project_id`. Computed and searchable. |
| `remaining_hours` | Float | `allocated_hours - effective_hours`. Positive = under budget, negative = over budget (overtime). Compute-sudo for access control. |
| `is_project_overtime` | Boolean | `True` if `remaining_hours < 0`. Searchable for filtering overtime projects. |
| `allocated_hours` | Float | Total hours allocated/planned for the project. Optional tracking field with `tracking=True`. |
| `effective_hours` | Float | Sum of all timesheet `unit_amount` on this project. Alias for project-level time spent. |

#### Methods

##### `_compute_allow_timesheets()`
When a project has no analytic account (`_origin` exists but `account_id` is falsy), automatically sets `allow_timesheets = False`. This prevents creating timesheets on projects without accounting infrastructure.

##### `_compute_is_internal_project()`
Compares `self == self.company_id.internal_project_id`. Used to identify the special "Internal" project auto-created per company.

##### `_search_is_internal_project(operator, value)`
SQL-based search for internal projects using a subquery against `res.company`:

```python
sql = Company._search(
    [('internal_project_id', '!=', False)],
    active_test=False, bypass_access=True,
).subselect("internal_project_id")
return [('id', operator, sql)]
```

##### `_compute_remaining_hours()`
Aggregates `unit_amount` from all timesheet lines via `_read_group` for efficiency:

```python
timesheets_read_group = self.env['account.analytic.line']._read_group(
    [('project_id', 'in', self.ids)],
    ['project_id'],
    ['unit_amount:sum'],
)
timesheet_time_dict = {project.id: unit_amount_sum for project, unit_amount_sum in timesheets_read_group}
```

Computes `effective_hours`, `remaining_hours`, and `is_project_overtime` in a single pass.

##### `_search_is_project_overtime(operator, value)`
Complex SQL search for projects in overtime. Joins `project_project` with `project_task` (only parent tasks, in active states) and uses a HAVING clause:

```sql
SELECT Project.id FROM project_project AS Project
JOIN project_task AS Task ON Project.id = Task.project_id
WHERE Project.allocated_hours > 0
  AND Project.allow_timesheets = TRUE
  AND Task.parent_id IS NULL
  AND Task.state IN ('01_in_progress', '02_changes_requested', '03_approved', '04_waiting_normal')
GROUP BY Project.id
HAVING Project.allocated_hours - SUM(Task.effective_hours) < 0
```

Note: Uses task `effective_hours` (which sums timesheet lines on the task) rather than project-level timesheet sums, for more accurate overtime detection based on task progress.

##### `_compute_total_timesheet_time()`
The most complex compute method. Converts all timesheet entries to a common reference unit, then to the encoding UoM:

```python
for product_uom, unit_amount in timesheet_time_dict[project.id]:
    factor = (product_uom or project.timesheet_encode_uom_id).factor
    total_time += unit_amount * (1.0 if project.encode_uom_in_days else factor)
total_time /= project.timesheet_encode_uom_id.factor
project.total_timesheet_time = float_round(total_time, precision_digits=2)
```

- If encoding in days, the product UoM factor is ignored (assumed 1.0 = 1 day reference)
- If encoding in hours, product UoM factors are used for conversion (e.g., a line recorded in "half-days" gets converted to hours)

##### `_check_allow_timesheet()`
`@api.constrains` validation: raises `ValidationError` if `allow_timesheets=True` but no `account_id` is set (and project is not a template).

##### `create(vals_list)` — **Override**
Pre-creates analytic accounts for projects that have `allow_timesheets=True` and no `account_id`. Creates accounts via `_get_values_analytic_account_batch()` before calling `super()`, ensuring the account exists before the constraint check runs.

##### `write(vals)` — **Override**
If `allow_timesheets` is set to `True` and no `account_id` exists, auto-creates the analytic account via `_create_analytic_account()`.

##### `_init_data_analytic_account()`
Post-install data migration: finds all projects with `allow_timesheets=True` but no `account_id` and creates accounts for them. Called from `hr_timesheet_data.xml`.

##### `_unlink_except_contains_entries()`
`@ondelete` hook: prevents deleting projects that have timesheet entries. Raises `RedirectWarning` that redirects to the timesheet action with the affected projects pre-selected.

##### `_convert_project_uom_to_timesheet_encode_uom(time)`
Converts time from the project's `company_id.project_time_mode_id` to the encoding UoM. Used for consistent display across different UoM configurations.

##### `action_project_timesheets()`
Opens the timesheet action filtered to this project: `act_hr_timesheet_line_by_project`.

##### `_get_stat_buttons()`
Adds timesheet stat buttons to the project's dashboard (Piggy bank / smart action buttons). Shows:
- `allocated / effective {uom_name}` with color coding:
  - Green: `< 80%`
  - Warning (orange): `>= 80%`
  - Red (danger): `> 100%` (overtime)
- Extra Time button (only when overtime): shows exceeding hours and percentage

##### `action_view_tasks()`
Passes `allow_timesheets` in context to the task view so the task form can conditionally show timesheet fields.

##### `_toggle_template_mode(is_template)`
When converting a template back to a regular project and `allow_timesheets=True` with no `account_id`, creates the analytic account first.

---

### 3. `project.task` — Task Extended (Timesheet on Tasks)

**Inherited from**: `project.task`
**File**: `hr_timesheet/models/project_task.py`

Adds time tracking fields and computed progress to tasks, and parses task names for embedded time allocations.

#### Fields

| Field | Type | Purpose |
|-------|------|---------|
| `allow_timesheets` | Boolean | Inherited from `project_id.allow_timesheets`. Searchable (allows filtering tasks by project timesheet setting). Compute-sudo. |
| `analytic_account_active` | Boolean (related) | Convenience: `project_id.analytic_account_active`. |
| `remaining_hours` | Float | Hours remaining: `allocated_hours - effective_hours - subtask_effective_hours`. Stored. |
| `remaining_hours_percentage` | Float | `remaining_hours / allocated_hours`. Searchable via custom SQL. |
| `effective_hours` | Float | Sum of `timesheet_ids.unit_amount`. Stored, compute-sudo. |
| `total_hours_spent` | Float | `effective_hours + subtask_effective_hours`. Full rollup including sub-tasks. |
| `progress` | Float | Progress percentage: `(effective_hours + subtask_effective_hours) / allocated_hours`. Stored with `aggregator="avg"` for task-stage rollup reporting. |
| `overtime` | Float | `max(0, (effective_hours + subtask_effective_hours) - allocated_hours)`. |
| `subtask_effective_hours` | Float | Recursive sum of effective hours on all sub-tasks (and their sub-tasks). Stored, recursive. |
| `timesheet_ids` | One2many (`account.analytic.line`, `task_id`) | All timesheet lines logged on this task. |
| `encode_uom_in_days` | Boolean | `True` if company encodes timesheets in days. |

#### Methods

##### `_compute_effective_hours()`
Uses `_read_group` for efficiency when tasks have IDs. Falls back to `mapped()` for new records:

```python
if not any(self._ids):
    for task in self:
        task.effective_hours = sum(task.timesheet_ids.mapped('unit_amount'))
    return
timesheet_read_group = self.env['account.analytic.line']._read_group(
    [('task_id', 'in', self.ids)], ['task_id'], ['unit_amount:sum']
)
```

##### `_compute_progress_hours()`
Computes `progress` (0.0 if no allocation) and `overtime` (never negative). Uses both task hours and sub-task hours.

##### `_compute_remaining_hours()`
Subtracts effective hours AND sub-task effective hours from allocation. Stored for searchability.

##### `_compute_subtask_effective_hours()`
Recursive: `sum(child.effective_hours + child.subtask_effective_hours for child in task.child_ids)`. Uses `with_context(active_test=False)` to include archived sub-tasks in the sum.

##### `_compute_total_hours_spent()`
`effective_hours + subtask_effective_hours`. Full time including sub-tasks.

##### `_search_remaining_hours_percentage(operator, value)`
Custom SQL search for remaining hours percentage. Uses `OPERATOR_MAPPING` to support all standard operators:

```sql
SELECT id FROM project_task
WHERE remaining_hours > 0
  AND allocated_hours > 0
  AND remaining_hours / allocated_hours < value
```

##### `_check_project_root()`
`@api.constrains`: raises `UserError` if attempting to make a task private (no `project_id`) when it has timesheet entries. Timesheet-linked tasks cannot be made private.

##### `_uom_in_days()`
Returns `True` if the company's encoding UoM is "Day".

##### `_extract_allocated_hours()`
Parses the task's `display_name` for patterns like `5h` or `10H` using regex, extracts the number, sets `allocated_hours`, and removes the pattern from the display name. Only runs if `allow_timesheets=True`.

```python
allocated_hours_group = r'\s(\d+(?:\.\d+)?)[hH]'
self.allocated_hours = sum(float(num) for num in re.findall(allocated_hours_group, self.display_name))
self.display_name = re.sub(allocated_hours_group, '', self.display_name)
```

##### `_get_group_pattern()`, `_prepare_pattern_groups()`, `_get_cannot_start_with_patterns()`, `_get_groups()`
Pattern-based task creation system. Adds `allocated_hours` pattern to the existing task creation pattern system (tags, assignees, priority). Allows creating tasks with embedded time allocation via title parsing (e.g., `"Fix bug 5h #urgent @john"`).

##### `action_view_subtask_timesheet()`
Opens a timesheet view filtered to all sub-tasks of the current task. Handles portal vs. internal user view switching, selecting appropriate views (portal tree/form/kanban for portal users).

##### `_get_timesheet_report_data()`
Builds a data structure for timesheet reporting on a task and its sub-tasks. Returns:
- `subtask_ids_per_task_id`: mapping of parent ID to list of sub-task IDs
- `timesheets_per_task`: mapping of task ID to the recordset of timesheet lines

##### `_compute_display_name()`
Extends the display name with remaining time when context `hr_timesheet_display_remaining_hours` is set:
- Days: `"(2.5 days remaining)"`
- Hours: `"(03:45 remaining)"` (HH:MM format, handles negative for overtime)

##### `_unlink_except_contains_entries()`
Prevents task deletion if timesheet entries exist. Raises `RedirectWarning` to show the timesheet entries. If some tasks are inaccessible to the current user, raises a descriptive `UserError` directing them to request higher access.

##### `_get_portal_total_hours_dict()`
Returns a dict with `allocated_hours` and `effective_hours` summed across all timesheetable tasks in the recordset. Used in the project sharing portal interface.

---

### 4. `hr.employee` — Employee Extended

**Inherited from**: `hr.employee`
**File**: `hr_timesheet/models/hr_employee.py`

#### Fields

| Field | Type | Purpose |
|-------|------|---------|
| `has_timesheet` | Boolean | `True` if the employee has at least one timesheet entry with a project. Computed via raw SQL for performance on large datasets. |

#### Methods

##### `_compute_has_timesheet()`
Uses raw SQL for efficiency on large employee datasets. Queries `account_analytic_line` for any row with `project_id IS NOT NULL` and matching `employee_id`:

```sql
SELECT id, EXISTS(
    SELECT 1 FROM account_analytic_line
    WHERE project_id IS NOT NULL AND employee_id = e.id
    LIMIT 1)
FROM hr_employee e
WHERE id in %s
```

This is used to prevent deleting employees who have timesheets.

##### `_compute_display_name()`
Extends the standard employee display name to include company name when the user has access to multiple companies and the same user has multiple employee records across companies:

```python
if employees_count_per_user.get(employee.user_id.id, 0) > 1:
    employee.display_name = f'{employee.display_name} - {employee.company_id.name}'
```

##### `action_unlink_wizard()`
Opens the employee deletion wizard. Pre-checks: if the user is not a timesheet approver AND the employee has timesheets AND has no active employee record, raises `UserError` preventing deletion.

##### `action_timesheet_from_employee()`
Opens the timesheet action filtered to this employee. Passes `create=True` only if the employee is active.

---

### 5. `res.company` — Company Extended

**Inherited from**: `res.company`
**File**: `hr_timesheet/models/res_company.py`

#### Fields

| Field | Type | Purpose |
|-------|------|---------|
| `project_time_mode_id` | Many2one (`uom.uom`) | Unit of measure for project time tracking. Default: Hour. Applied to projects and tasks. |
| `timesheet_encode_uom_id` | Many2one (`uom.uom`) | Unit of measure for timesheet encoding/display. Default: Hour. Can be switched to Day for day-based organizations. |
| `internal_project_id` | Many2one (`project.project`) | The "Internal" project auto-created per company. Used for timesheets on internal activities (meetings, training, etc.). Domain: `is_template=False`. |

#### Methods

##### `_check_internal_project_id_company()`
`@api.constrains`: validates that a company's `internal_project_id` belongs to that same company.

##### `create(vals_list)` — **Override**
After creating a company, calls `_create_internal_project_task()` to auto-create the internal project.

##### `_create_internal_project_task()`
Creates an "Internal" project with two default tasks ("Training", "Meeting") for each company:

```python
results += [{
    'name': _('Internal'),
    'allow_timesheets': True,
    'company_id': company.id,
    'type_ids': type_ids,
    'task_ids': [(0, 0, {
        'name': name,
        'company_id': company.id,
    }) for name in [_('Training'), _('Meeting')]]
}]
```

The internal project is set as `company.internal_project_id`. This project is used as the default when no other project is available (e.g., timesheets on time off).

---

### 6. `res.config.settings` — Configuration Extended

**Inherited from**: `res.config.settings`
**File**: `hr_timesheet/models/res_config_settings.py`

#### Fields

| Field | Type | Purpose |
|-------|------|---------|
| `module_project_timesheet_holidays` | Boolean | Toggle for `project_timesheet_holidays` sub-module (time off linked to timesheets). Computed: forced to `False` if `module_hr_timesheet` is not installed. |
| `project_time_mode_id` | Many2one (`uom.uom`) | Related to `company_id.project_time_mode_id`. Sets the time unit for projects. |
| `is_encode_uom_days` | Boolean | Computed: `True` if encoding method is "days". Used in UI for conditional display. |
| `timesheet_encode_method` | Selection (`hours`/`days`) | Encoding display mode. Inverse writes to `company_id.timesheet_encode_uom_id`. |

---

### 7. `project.update` — Project Update Extended

**Inherited from**: `project.update`
**File**: `hr_timesheet/models/project_update.py`

#### Fields

| Field | Type | Purpose |
|-------|------|---------|
| `display_timesheet_stats` | Boolean | `True` if the project has timesheets enabled. Controls visibility of timesheet stats in project status updates. |
| `allocated_time` | Integer | Project's allocated hours at the time of this update. Converted from `project.allocated_hours` using the UoM ratio. |
| `timesheet_time` | Integer | Total timesheet time at the time of this update. Converted to the encoding UoM. |
| `timesheet_percentage` | Integer | `round(timesheet_time * 100 / allocated_time)`. |
| `uom_id` | Many2one (`uom.uom`) | The encoding UoM used for the time values. |

#### Methods

##### `create(vals_list)` — **Override**
On creation, computes and stores the project's timesheet stats at that moment:

```python
ratio = self.env.ref("uom.product_uom_hour").factor / encode_uom.factor
update.write({
    "uom_id": encode_uom,
    "allocated_time": round(project.allocated_hours * ratio),
    "timesheet_time": round(project.sudo().total_timesheet_time),
})
```

Also updates `project.last_update_id` to point to this update (via `sudo()` since the project may have restricted access).

---

### 8. `account.analytic.line.calendar.employee` — Calendar Filter Model

**File**: `hr_timesheet/models/account_analytic_line_calendar_employee.py`

A personal (per-user) filter model for the timesheet calendar view. Stores which employee checkboxes are checked in the calendar view filter bar.

| Field | Type | Purpose |
|-------|------|---------|
| `user_id` | Many2one (`res.users`) | Owner of this filter setting. Required, default to current user. Cascade delete. |
| `employee_id` | Many2one (`hr.employee`) | The employee whose timesheets are shown when this filter is active. |
| `checked` | Boolean | Whether this employee filter is active. Default `True`. |
| `active` | Boolean | Whether this filter record itself is active. Default `True`. |

---

### 9. `account.analytic.applicability` — Analytic Applicability Extended

**Inherited from**: `account.analytic.applicability`
**File**: `hr_timesheet/models/analytic_applicability.py`

Adds `'timesheet'` as a business domain option for analytic applicability rules. Enables configuring which analytic plans/applicabilities apply specifically to timesheet lines.

```python
business_domain = fields.Selection(
    selection_add=[('timesheet', 'Timesheet')],
    ondelete={'timesheet': 'cascade'},
)
```

---

### 10. `uom.uom` — UoM Extended

**Inherited from**: `uom.uom`
**File**: `hr_timesheet/models/uom_uom.py`

#### Fields

| Field | Type | Purpose |
|-------|------|---------|
| `timesheet_widget` | Char | The JavaScript widget used for timesheet encoding when this UoM is active. Set to `"float_time"` for hours and `"float_toggle"` for days in `hr_timesheet_data.xml`. |

#### Methods

##### `_unprotected_uom_xml_ids()`
Overrides to also protect the hour UoM from deletion when the timesheet module is installed:

```python
return [
    "product_uom_dozen",
    "product_uom_pack_6",
]
```

(Note: hour and day UoMs are also implicitly protected via `noupdate=True` in the data file, but this method adds explicit protection.)

---

### 11. `project.collaborator` — Portal Collaborator Extended

**Inherited from**: `project.collaborator`
**File**: `hr_timesheet/models/project_collaborator.py`

#### Methods

##### `_toggle_project_sharing_portal_rules(active)`
When project sharing portal rules are toggled, also activates/deactivates the timesheet portal access control and record rule:

```python
access_timesheet_portal.active = active
timesheet_portal_ir_rule.active = active
```

This ensures that when project sharing is disabled, portal users lose timesheet access on those projects as well.

---

### 12. `hr.employee.public` — Public Employee Extended

**Inherited from**: `hr.employee.public`
**File**: `hr_timesheet/models/hr_employee_public.py`

#### Fields

| Field | Type | Purpose |
|-------|------|---------|
| `has_timesheet` | Boolean (related) | Mirrors `hr.employee.has_timesheet` for public/portal access. |

#### Methods

##### `action_timesheet_from_employee()`
Only executes for internal users (`is_user=True`). Delegates to the actual `hr.employee` record's method.

---

### 13. `ir.http` — Session Info Extended

**Inherited from**: `ir.http`
**File**: `hr_timesheet/models/ir_http.py`

#### Methods

##### `session_info()`
Injects timesheet UoM information into the web client's session info for all internal users. This enables the `timesheet_uom` JavaScript widget to render timesheet values correctly per company:

```python
result["user_companies"]["allowed_companies"][company.id].update({
    "timesheet_uom_id": company.timesheet_encode_uom_id.id,
    "timesheet_uom_factor": company.project_time_mode_id._compute_quantity(
        1.0, company.timesheet_encode_uom_id, round=False
    ),
})
result["uom_ids"] = self.get_timesheet_uoms()
```

##### `get_timesheet_uoms()`
Returns a dict of all UoM IDs and their properties (name, rounding, widget) for both encoding and project time modes across all user companies.

---

### 14. `ir.ui.menu` — Menu Extended

**Inherited from**: `ir.ui.menu`
**File**: `hr_timesheet/models/ir_ui_menu.py`

#### Methods

##### `_load_menus_blacklist()`
Hides the "My Activities" menu item (`timesheet_menu_activity_user`) from timesheet approvers, since they see all activities rather than just their own.

---

### 15. `timesheets.analysis.report` — Reporting Model

**Inherited from**: `hr.manager.department.report` (mixin providing department manager access fields)
**File**: `hr_timesheet/report/timesheets_analysis_report.py`
**Type**: `ir.actions.act_window` / SQL View (`_auto = False`)

A materialized SQL view for timesheet analytics. Joins `account_analytic_line` with employee, project, task, and manager data.

| Field | Type | Purpose |
|-------|------|---------|
| `name` | Char | Timesheet description |
| `user_id` | Many2one | User who logged the time |
| `project_id` | Many2one | Project |
| `task_id` | Many2one | Task |
| `parent_task_id` | Many2one | Parent task (for sub-task rollup) |
| `employee_id` | Many2one | Employee |
| `manager_id` | Many2one | Employee's manager |
| `company_id` | Many2one | Company |
| `department_id` | Many2one | Employee's department |
| `currency_id` | Many2one | Currency for amount |
| `date` | Date | Timesheet date |
| `amount` | Monetary | Cost amount (negative, from employee hourly rate) |
| `unit_amount` | Float | Time spent in encoding UoM |
| `partner_id` | Many2one | Customer partner |
| `milestone_id` | Many2one | Task milestone |
| `message_partner_ids` | Many2many | Followers (computed/searchable) |
| `has_department_manager_access` | Boolean (inherited from mixin) | `True` if current user is a department manager |

The view is initialized via `init()` which drops and recreates the view:

```sql
CREATE or REPLACE VIEW timesheets_analysis_report AS (
    SELECT A.id, A.name, A.user_id, A.project_id, A.task_id, ...
    FROM account_analytic_line A
    WHERE A.project_id IS NOT NULL
)
```

---

### 16. `report.project.task.user` — Task Reporting Extended

**Inherited from**: `report.project.task.user`
**File**: `hr_timesheet/report/project_report.py`

Adds timesheet fields to the Project Task Analysis report.

| Field | Type | Purpose |
|-------|------|---------|
| `allocated_hours` | Float | Planned hours |
| `effective_hours` | Float | Logged hours (NULL if 0) |
| `remaining_hours` | Float | `allocated_hours - effective_hours` (NULL if no allocation) |
| `remaining_hours_percentage` | Float | `remaining_hours / allocated_hours` |
| `progress` | Float | `effective_hours * 100 / allocated_hours` |
| `overtime` | Float | Overtime hours (NULL if 0) |

All fields are group-restricted to `group_hr_timesheet_user`.

---

### 17. `hr.employee.delete.wizard` — Employee Deletion Wizard

**File**: `hr_timesheet/wizard/hr_employee_delete_wizard.py`

A transient wizard for safely deleting employees with timesheet history.

| Field | Type | Purpose |
|-------|------|---------|
| `employee_ids` | Many2many (`hr.employee`) | Employees being considered for deletion |
| `has_active_employee` | Boolean | Whether any of the selected employees are still active |
| `has_timesheet` | Boolean | Whether any selected employee has timesheet entries |

#### Methods

##### `_compute_has_timesheet()`
Uses `_read_group` to efficiently check if any selected employee has timesheet entries.

##### `action_archive()`
Redirects to the standard employee departure wizard (termination flow).

##### `action_confirm_delete()`
Actually deletes the employee records (and cascades to unlink). Used when the user confirms deletion despite timesheet existence.

##### `action_open_timesheets()`
Opens a timesheet list view filtered to the selected employees, allowing review before deletion.

---

## L2: Billable Tracking and Integration Fields

### Timesheet Billable Flow

The billable tracking in `hr_timesheet` operates through the analytic account system:

```
Employee Timesheet Entry
    │
    ├── project_id ──> account.analytic.account
    │                      │
    │                      ├── plan: timesheet (or other business domain)
    │                      │
    │                      └── currency_id ──> amount conversion
    │
    ├── task_id ──> project_id ──> account_id
    │
    └── employee_id ──> hourly_cost
                           │
                           └── unit_amount × hourly_cost = amount (negative cost)
```

### Key Billable Tracking Fields

| Source | Field | Role |
|--------|-------|------|
| `project.project` | `account_id` | Primary analytic account for the project |
| `project.project` | `allow_timesheets` | Master switch for billable tracking |
| `account.analytic.line` | `partner_id` | Customer for invoicing (from task or project) |
| `account.analytic.line` | `amount` | Computed cost (negative) = `unit_amount * employee.hourly_cost` |
| `account.analytic.line` | `unit_amount` | Quantity of time logged |

### Billable vs. Non-Billable Distinction

The base `hr_timesheet` module does **not** distinguish billable from non-billable time directly. This distinction is added by the `sale_timesheet` module (Odoo Enterprise), which:
- Adds `billable_type` field to tasks: `task_rate`, `project_rate`, or `non_billable`
- Adds `pricing_type` to projects
- Creates analytic lines with tags that map to sale order lines
- Generates invoiced amounts from timesheets via `sale.order.line.timesheet_ids`

In the base CE module, all timesheets are cost-tracking entries with no direct billing link.

---

## L3: Cross-Module Integration Patterns

### Timesheet Line Creation from Project/Task

The timesheet line creation follows this cascade:

```
User creates timesheet (UI / API)
    │
    ▼
account.analytic.line.create()
    │
    ├── Validate employee (active, in allowed company)
    │
    ├── Validate project/task relationship
    │     ├── If task provided: project_id = task.project_id
    │     ├── If project provided: task_id = False
    │     └── If neither: skip (not a timesheet)
    │
    ├── Resolve company from task/project/employee
    │
    ├── Set analytic accounts from project
    │     └── _timesheet_preprocess_get_accounts()
    │           └── Validates mandatory plan columns
    │
    ├── Set product_uom_id from company
    │
    ├── Set default name '/' if empty
    │
    ├── Validate work intervals (calendar view only)
    │     └── Skip employees not working on date
    │
    ├── super().create()  ──> DB insert
    │
    └── _timesheet_postprocess()
          └── Compute amount: -unit_amount × hourly_cost
```

### Task Timesheet Linking

The link between `project.task.timesheet_ids` and `account.analytic.line` is bidirectional:

```python
# project_task.py
timesheet_ids = fields.One2many(
    'account.analytic.line', 'task_id', 'Timesheets'
)

# hr_timesheet.py
task_id = fields.Many2one(
    'project.task', 'Task',
    index='btree_not_null',
    compute='_compute_task_id', store=True, readonly=False,
    domain="[('allow_timesheets', '=', True), ('project_id', '=?', project_id), ('has_template_ancestor', '=', False)]"
)
```

Key behaviors:
- `domain` ensures only timesheet-enabled tasks with matching projects are selectable
- `has_template_ancestor = False` prevents logging time on template-derived tasks
- `=?` (conditional equals) operator: project domain only applies if `project_id` is set
- `_onchange_project_id()` resets `task_id` when project changes, preventing mismatched entries

### Timesheet from Time Off (project_timesheet_holidays)

The `project_timesheet_holidays` module (installed alongside `hr_timesheet`) creates timesheet entries automatically when employees take time off:

1. Employee requests time off
2. On time off validation, a timesheet line is created on the company's `internal_project_id`
3. The timesheet has `task_id` pointing to a specific internal task (Training, Meeting, or generic)
4. This ensures internal activities are also tracked in the timesheet system

### Timesheet for Manufacturing (MRP Integration)

The `mrp` module (Manufacturing) extends `hr_timesheet` to:
- Override `_is_readonly()` to lock timesheets on done manufacturing orders
- Link timesheet lines to manufacturing workorders
- Track time per work center operation

---

## L4: Performance, Historical Changes, and Security

### Performance Considerations

#### 1. `has_timesheet` SQL Optimization
The `_compute_has_timesheet()` on `hr.employee` uses raw SQL with a correlated subquery and `LIMIT 1` to avoid N+1 when checking many employees:

```sql
SELECT id, EXISTS(
    SELECT 1 FROM account_analytic_line
    WHERE project_id IS NOT NULL AND employee_id = e.id
    LIMIT 1)
FROM hr_employee e
WHERE id in %s
```

This is the correct pattern for boolean existence checks on large tables.

#### 2. `_read_group` for Aggregation
All time aggregation uses `_read_group` instead of `search() + mapped()`:

```python
# GOOD: Single query with aggregation
timesheets_read_group = self.env['account.analytic.line']._read_group(
    [('project_id', 'in', self.ids)],
    ['project_id'],
    ['unit_amount:sum'],
)

# BAD: N+1 queries
for project in self:
    project.effective_hours = sum(project.timesheet_ids.mapped('unit_amount'))
```

#### 3. `_compute_remaining_hours()` on `project.project`
Uses a single `_read_group` to compute all three fields (`effective_hours`, `remaining_hours`, `is_project_overtime`) in one pass.

#### 4. Pre-init Hook for Large Databases
The `_pre_init_hook` manually adds database columns before the ORM initializes the model, preventing OOM errors on large databases:

```sql
ALTER TABLE account_analytic_line
ADD COLUMN IF NOT EXISTS task_id        INT4,
ADD COLUMN IF NOT EXISTS parent_task_id INT4,
ADD COLUMN IF NOT EXISTS project_id     INT4,
ADD COLUMN IF NOT EXISTS department_id  INT4,
ADD COLUMN IF NOT EXISTS manager_id     INT4
```

Without this, Odoo's ORM would try to compute these stored fields via triggers during installation, which can cause memory exhaustion on tables with millions of rows.

#### 5. `_compute_subtask_effective_hours` with `active_test=False`
Uses `with_context(active_test=False)` to include archived sub-tasks in the sum, avoiding an extra query to fetch archived records.

### Historical Changes: Odoo 18 to 19

#### Module Renaming
In Odoo 18: `project_timesheet` and `hr_timesheet` were separate modules.
In Odoo 19: `project_timesheet` was merged into `hr_timesheet`. All timesheet-project functionality is now in a single module.

#### SQL.execute_query Replace
In Odoo 18: `self._cr.execute()` for raw SQL.
In Odoo 19: `self.env.execute_query(SQL(...))` using the safe `SQL` composition helper.

```python
# Odoo 18
self._cr.execute("""SELECT id, EXISTS(...) FROM hr_employee WHERE id in %s""", (tuple(self.ids),))

# Odoo 19
self.env.execute_query(SQL(
    """ SELECT id, EXISTS(...) FROM hr_employee e WHERE id in %s """,
    tuple(self.ids),
))
```

The `SQL` helper prevents SQL injection by separating the query structure from parameter values.

#### Calendar View Employee Filter
Odoo 18: Employee filter in calendar view used a custom approach.
Odoo 19: Dedicated `account.analytic.line.calendar.employee` model stores per-user, per-employee filter preferences. This allows persisting which employees are checked in the calendar filter bar.

#### `_compute_display_name` on `project.project`
Odoo 18: `display_name` was not extended for multi-company.
Odoo 19: When a user has access to multiple companies and the same user has multiple employees across companies, the employee display name appends the company name (e.g., `"John Smith - Acme Corp"`).

#### Domain Class Usage
Odoo 18: Domain tuples/list literals in code.
Odoo 19: `Domain` class for programmatic domain construction (e.g., `Domain('field', '=', value)`, `Domain.FALSE`, `Domain('field', 'in', [...])`). Provides better composability and IDE support.

#### `analytic_account_active` Field
Odoo 19: New convenience field `project.project.analytic_account_active` that directly mirrors `account_id.active`, avoiding repeated related field access.

### Security: Access Control Layers

The `hr_timesheet` module implements a three-layer security model for timesheet data:

#### Layer 1: ACL (ir.model.access.csv)

| Group | Model | Read | Write | Create | Unlink |
|-------|-------|------|-------|--------|--------|
| `group_hr_timesheet_user` | `account.analytic.line` | Yes | Own only | Yes | Own only |
| `group_hr_timesheet_approver` | `account.analytic.line` | All | All | All | All |
| `group_timesheet_manager` | `account.analytic.line` | All | All | All | All |
| `base.group_portal` | `account.analytic.line` | Filtered | Own only | Yes | Own only |

#### Layer 2: Record Rules (ir.rule)

Four record rules govern data visibility:

1. **`timesheet_line_rule_user`** (`group_hr_timesheet_user`):
   ```python
   domain_force = [
       ('user_id', '=', user.id),           # Own timesheets
       ('project_id', '!=', False),         # Must have project
       '|', '|',
           ('project_id.privacy_visibility', 'in', ['employees', 'portal']),
           ('partner_id', '=', user.partner_id.id),
           ('message_partner_ids', 'in', [user.partner_id.id])
   ]
   ```

2. **`timesheet_line_rule_approver`** (`group_hr_timesheet_approver`):
   Sees all timesheets on projects with `privacy_visibility` in `employees` or `portal`, or where they follow the project/task or are the partner.

3. **`timesheet_line_rule_manager`** (`group_timesheet_manager` + `project.group_project_manager`):
   No domain restriction: sees all timesheets with a project.

4. **`timesheet_line_rule_portal_user`** (`base.group_portal`):
   ```python
   domain_force = [
       ('project_id', '!=', False),
       ('message_partner_ids', 'child_of', [user.partner_id.commercial_partner_id.id]),
       ('project_id.privacy_visibility', 'in', ['invited_users', 'portal']),
       ('project_id.collaborator_ids.partner_id', 'in', [user.partner_id.id]),
   ]
   ```
   Active only when project sharing is enabled.

#### Layer 3: Field-Level Security

All time-tracking fields on `project.task` (effective_hours, remaining_hours, progress, etc.) are restricted to `group_hr_timesheet_user`. Portal users cannot see time tracking data on tasks.

#### Access Control in Code

The `create()` and `write()` methods enforce access programmatically:

```python
def _check_can_write(self, values):
    if (
        not (self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver') or self.env.su)
        and any(analytic_line.user_id != self.env.user for analytic_line in self)
    ):
        raise AccessError(_("You cannot access timesheets that are not yours."))
```

This is an additional check beyond record rules, ensuring that even if a record rule is somehow bypassed, users cannot modify others' timesheets.

### Uninstall Hook

The `_uninstall_hook` in `__init__.py`:
1. Restores action window domains for internal projects to the default (removes `is_internal_project` filter)
2. Archives (not deletes) the internal projects
3. Removes the internal project default stage XML data record

---

## Hooks and Lifecycle

### Pre-init Hook (`_pre_init_hook`)
- Adds database columns directly via `ALTER TABLE` to avoid ORM overhead on large datasets
- Runs before module installation, before any model definition is loaded

### Post-init Hook (`create_internal_project`)
- Called via `post_init_hook` in the manifest
- Writes `allow_timesheets = True` to all existing projects
- Creates the internal project for each company via `_create_internal_project_task()`
- Creates a zero-amount analysis timesheet line for admin on each internal task
- Checks for project sharing collaborators

### Uninstall Hook (`_uninstall_hook`)
- Archives internal projects
- Removes internal project stage XML data
- Restores action window domains

---

## Related Modules

| Module | Relationship |
|--------|-------------|
| `analytic` | Base analytic accounting; `account.analytic.line` lives here |
| `project` | Project and task models; extended by `hr_timesheet` |
| `hr` | Employee model; extended by `hr_timesheet` |
| `hr_hourly_cost` | Adds `hourly_cost` field to `hr.employee`; required dependency |
| `uom` | Unit of measure; required for time encoding |
| `sale_timesheet` | EE only; adds billable tracking to timesheets |
| `project_timesheet_holidays` | Links time off to timesheet entries |
| `mrp` | Manufacturing integration; locks timesheets on done orders |
| `rating` | Used for rating timesheet entries |

---

## Tags

#modules #odoo19 #hr_timesheet #timesheet #project #analytic #time-tracking #employee
