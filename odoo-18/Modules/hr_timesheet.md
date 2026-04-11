# Odoo 18 - hr_timesheet Module

## Overview

Timesheet entry module. Extends `account.analytic.line` with employee/timesheet context. Provides the core timesheet data model used by project timesheets, sale timesheet billing, and HR cost tracking.

## Source Path

`~/odoo/odoo18/odoo/addons/hr_timesheet/`

## Key Model

### account.analytic.line (extended)

The timesheet entry model. Inherited from `account.analytic.line`; not a standalone model.

**Key Fields (added by hr_timesheet):**
- `employee_id` (`hr.employee`): Required for timesheet cost computation. Domain restricts to user's employee or timesheet approver's employees.
- `user_id`: Computed from `employee_id.user_id`. Defaults to current user.
- `project_id` (`project.project`): Must have `allow_timesheets = True`. Privacy visibility filter applied for non-managers.
- `task_id` (`project.task`): Must have `allow_timesheets = True`. Automatically set from `task_id.project_id`. Onchange resets task when project changes.
- `parent_task_id`: Related to `task_id.parent_id`, stored, indexed.
- `department_id`: Computed from `employee_id.department_id`.
- `manager_id`: Related to `employee_id.parent_id`.
- `encoding_uom_id`: Company timesheet encoding UoM (hours or days).
- `milestone_id`: Related to `task_id.milestone_id`.
- `readonly_timesheet`: Computed boolean. `True` for non-internal users and for timesheets in readonly state.
- `display_name`: Custom display: `"Project - Task"` or just `"Project"`.

**Domain Filters:**
- `_domain_project_id()`: `allow_timesheets = True`. Non-managers also filtered by privacy visibility: exclude `followers`-only projects unless user is a follower.
- `_domain_employee_id()`: Restricts to user's own employee unless user is in `group_hr_timesheet_approver`.

**Computed Fields:**
- `_compute_user_id`: `user_id = employee_id.user_id` or `_default_user()`.
- `_compute_project_id`: Syncs `project_id` from `task_id.project_id` if mismatched.
- `_compute_task_id`: Clears task if no project.
- `_compute_department_id`: From `employee_id.department_id`.
- `_compute_partner_id`: From `task_id.partner_id` or `project_id.partner_id`.
- `_compute_message_partner_ids`: Union of project and task followers.
- `_compute_display_name`: Project-based display name.
- `_compute_readonly_timesheet`: `True` for non-internal users.

## Key Methods

### `create(vals_list)`

Complex employee resolution on create:
1. Collect `user_id` and `employee_id` from all vals.
2. Search active employees by user_ids + employee_ids across allowed companies.
3. For each record: if `employee_id` provided and valid, use it; otherwise resolve from `user_id` (must have exactly one active employee in company or exactly one across all companies).
4. Pre-process accounts via `_timesheet_preprocess_get_accounts()`.
5. Set `product_uom_id` from company `project_time_mode_id`.
6. Auto-set `name = '/'` if empty.
7. Call `_timesheet_postprocess()` per record for amount computation.

**Raises `ValidationError`** if:
- Task is private (`not task.project_id`).
- No active employee found in selected companies.

### `write(values)`

- Access check via `_check_can_write()`: non-approvers cannot write others' timesheets.
- Raises `ValidationError` if writing a private task.
- Pre-processes accounts and runs `_timesheet_postprocess()`.

### `_timesheet_preprocess_get_accounts(vals)`

Validates that mandatory analytic plans are set on the project (excludes `account_id` from the check — that's validated in `_timesheet_postprocess_values`). Raises `ValidationError` if any required plan column is missing.

### `_timesheet_postprocess_values(values)`

Computes `amount = -unit_amount * employee_id.hourly_cost` and converts to the analytic account's currency. Validates active analytic account and company consistency across task/project/accounts.

### `_hourly_cost()`

Returns `employee_id.hourly_cost` or `0.0`.

### `_check_can_write(values)`

Raises `AccessError` if user is not a timesheet approver and tries to write timesheets not belonging to them.

### `_check_can_create()`

Hook method; override in sub-modules to add creation access checks.

## Access Control (L3)

- Basic users: can only write their own timesheets.
- Timesheet approvers: can write any timesheet.
- Non-internal users (portal): `readonly_timesheet = True`.
- `_is_readonly()`: Override point for sub-modules (e.g., `mrp` grants portal write access on production timesheets).

## Edge Cases & Failure Modes

1. **Archived employee on timesheet**: `write()` raises `UserError` if setting `employee_id` to an archived employee.
2. **Task private**: Raises `ValidationError` if `task_id` has no `project_id` (private task).
3. **Project/task company mismatch**: Raises `ValidationError` if project, task, and analytic accounts belong to different companies.
4. **No analytic account active**: Raises `ValidationError` in `_timesheet_postprocess_values` if the account is inactive.
5. **Task-project sync**: `_compute_project_id` auto-corrects if `task_id.project_id != project_id`. The `onchange` resets task when project changes.
6. **Multiple employees per user**: Resolved by company priority — picks the employee matching the timesheet's company, or the only employee if one exists across all allowed companies.

## Cross-Model Relationships

| Model | Field | Purpose |
|-------|-------|---------|
| `account.analytic.line` | `employee_id` | Cost tracking, user resolution |
| `account.analytic.line` | `project_id` | Project timesheet filtering |
| `account.analytic.line` | `task_id` | Task-linked timesheet |
| `hr.employee` | (reverse) | Employee's timesheet entries |
| `project.project` | (via field) | Privacy visibility, allow_timesheets |
| `project.task` | (via field) | Task billing, milestone |

## Integration Points

- **project_timesheet**: The `project` field is provided by this module; `hr_timesheet` extends it.
- **sale_timesheet**: Links `sale_line_id` on timesheet lines for billing. `hr_timesheet` provides the base; `sale_timesheet` adds the billable link.
- **project_account**: Profitability calculation uses timesheet `amount` (negative = cost).

## Security Groups

- `hr_timesheet.group_hr_timesheet_user`: Basic timesheet user (can create/write own timesheets).
- `hr_timesheet.group_hr_timesheet_manager`: Timesheet approver (can write all timesheets).

## Cron Jobs

None directly in `hr_timesheet`. Project-level crons (e.g., recurring task generation) may trigger timesheet creation.