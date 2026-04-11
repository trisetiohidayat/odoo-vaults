---
description: Track employee time on tasks — timesheet entries, project hour tracking, UoM encoding, multi-company, portal access, approval workflow, and overtime computation.
tags: [odoo, odoo19, modules, timesheet, hr, project, analytic]
created: 2026-04-06
---

# hr_timesheet (Task Logs)

**Module Key:** `hr_timesheet`
**Category:** Services/Timesheets
**Version:** 1.0
**License:** LGPL-3
**Author:** Odoo S.A.
**Sequence:** 23
**Depends:** `hr`, `hr_hourly_cost`, `analytic`, `project`, `uom`

---

## Overview

Implements a timesheet system where each employee encodes and tracks time spent on projects and tasks. Fully integrated with analytic accounting for cost management and reporting.

## Module Files

| File | Purpose |
|------|---------|
| `models/hr_timesheet.py` | Core: `account.analytic.line` extension, project/task/employee overrides |
| `models/project_project.py` | `project.project` extension — timesheet fields, auto-account creation |
| `models/project_task.py` | `project.task` extension — task effective hours, overtime, progress |
| `models/hr_employee.py` | `hr.employee` extension — `has_timesheet`, delete wizard guard |
| `models/res_company.py` | `res.company` extension — internal project, UoM defaults |
| `models/res_config_settings.py` | Settings view — UoM encoding, reminder toggles |
| `models/ir_http.py` | Session info injection for JS `timesheet_uom` widget |
| `models/ir_ui_menu.py` | Hides "My Timesheets" activity menu from approvers |
| `models/analytic_applicability.py` | Adds `business_domain = 'timesheet'` |
| `models/hr_employee_public.py` | `hr.employee.public` extension |
| `models/project_update.py` | `project.update` extension — timesheet snapshot on status updates |
| `models/project_collaborator.py` | Portal timesheet ACL toggle on project sharing enable |
| `models/uom_uom.py` | `timesheet_widget` field + UoM deletion protection |
| `models/account_analytic_line_calendar_employee.py` | Calendar view employee filter preferences |
| `security/hr_timesheet_security.xml` | Groups, ir.rule domains for timesheet access |
| `security/ir.model.access.csv` | ACL records per group |
| `data/hr_timesheet_data.xml` | UoM widget assignment, export templates, init data |

## Hooks

| Hook | Purpose |
|------|---------|
| `post_init_hook: create_internal_project` | On first install, creates one "Internal" `project.project` per company with "Training" and "Meeting" tasks |
| `uninstall_hook: _uninstall_hook` | Cleans up auto-created analytic accounts and internal projects on uninstall |

---

## `account.analytic.line` — Timesheet Entry

**Inheritance:** Extends `account.analytic.line` from the `analytic` module.
**File:** `models/hr_timesheet.py`

This is the **primary record** of the module — one `account.analytic.line` per timesheet line entry. Lines without a `project_id` are plain analytic entries (e.g., expenses). Lines with `project_id` are timesheet entries.

### Fields

#### Core Identity Fields

**`employee_id`** — `Many2one(hr.employee)`
- Stored, indexed.
- Domain: `company_id in allowed_company_ids`. Non-approvers further restricted to `user_id = current_user.id`.
- **Required for timesheet entries.** Absence of `employee_id` means the line is a non-timesheet analytic entry. Drives costing via `hourly_cost`.
- Set automatically from `user_id` if not explicitly provided (see `create()` flow below).

**`project_id`** — `Many2one(project.project)`
- Stored, indexed.
- Domain via `_domain_project_id()`: `allow_timesheets = True`, `is_template = False`. Non-managers: `privacy_visibility in ['employees', 'portal']` OR user is in `message_partner_ids`.
- Auto-populated from `task_id` if only `task_id` is set.

**`task_id`** — `Many2one(project.task)`
- Stored, indexed (`index='btree_not_null'`).
- Domain: `allow_timesheets = True`, `project_id` matches, `has_template_ancestor = False`.
- `parent_task_id` is a stored **related copy** of `task_id.parent_id` for efficient domain filtering without joining through `task_id`.

**`user_id`** — `Many2one(res.users)`
- Stored.
- Derives from `employee_id.user_id`. Falls back to `self._default_user()` which returns `context.get('user_id', self.env.user.id)`.

#### Cross-Linked Fields

**`department_id`** — `Many2one(hr.department)`
- Stored. Derives from `employee_id.department_id`. `compute_sudo=True`.

**`manager_id`** — `Many2one(hr.employee)`
- Stored related: `employee_id.parent_id`. The employee's direct line manager.

**`partner_id`** — `Many2one(res.partner)`
- Stored. Computed via `_compute_partner_id()`: prefers `task_id.partner_id` over `project_id.partner_id`. Overrides base `analytic` behavior.

**`milestone_id`** — `Many2one(project.milestone)`
- Related to `task_id.milestone_id`. Used for display.

**`message_partner_ids`** — `Many2many(res.partner)`
- Computed: union of `task_id.message_partner_ids` and `project_id.message_partner_ids`.
- `_search_message_partner_ids` resolves followed projects/tasks via `mail.followers` to build a domain — powers portal access.
- Domain: `Domain('project_id', 'in', followed_project_ids) | Domain('task_id', 'in', followed_task_ids)`. Returns `Domain.FALSE` if nothing followed.

**`readonly_timesheet`** — `Boolean`
- Computed, `compute_sudo=True`.
- `True` for any non-internal user (not in `base.group_user`). Can be overridden by `_is_readonly()` in extensions (e.g., `mrp_account` locks validated timesheets on work orders).

#### Encoding/Display Fields

**`encoding_uom_id`** — `Many2one(uom.uom)`
- `company_id.timesheet_encode_uom_id` — the user's preferred encoding unit (hours or days).

**`calendar_display_name`** — `Char`
- Computed: `"ProjectName (XhYm)"` or `"ProjectName (Xd)"` depending on `company.timesheet_encode_uom_id`.
- Used exclusively in calendar view rendering.

**`job_title`** — `Char` (related)
- `employee_id.job_title`. Read-only.

### Methods

#### `create()` — 5-Phase Flow

```
Phase 1: Calendar-view work-schedule guard
  └── If timesheet_calendar context: skip days where employee has no work interval
Phase 2: Company + analytic account propagation
  └── company_id from task → project → vals; call _timesheet_preprocess_get_accounts()
Phase 3: product_uom_id default
  └── Falls back to company.project_time_mode_id
Phase 4: Employee resolution (3 cases)
  └── (A) employee_id provided + active → use it
  └── (B) no employee_id: look up by user_id (one-per-company → use it; multi-company → use current company)
  └── (C) no active employee → ValidationError
Phase 5: super().create() + _timesheet_postprocess per line
  └── Computes amount = -unit_amount × hourly_cost
```

**Calendar batch creation:** When `timesheet_calendar` context is set, the code prefetches all employees via `browse()` before the loop, then calls `resource_id._get_valid_work_intervals()` per entry to skip non-working days. After the batch, sends a bus notification (`simple_notification`) with count of skipped entries.

**Employee resolution edge cases:**
- If a user has employees in multiple companies, and `company_id` is not set in vals: uses the first company in `employee_per_company` if only one, otherwise uses `self.env.company.id`.
- Archived employees: case (A) raises if the provided `employee_id` is not in the search results (archived/not in company).

#### `write()` — Same Guards

- `_check_can_write()`: non-approvers can only write their own lines (`user_id != self.env.user` raises `AccessError`).
- Raises `UserError` if attempting to set an archived employee on existing timesheets.
- Raises `ValidationError` if attempting to create a timesheet on a private task (`task_id` with no `project_id`).
- `_timesheet_postprocess()` called for all lines with `project_id`.

#### `_timesheet_postprocess_values()` — Amount Derivation

```python
cost = timesheet._hourly_cost()          # employee_id.hourly_cost or 0.0
amount = -timesheet.unit_amount * cost   # negative = debit convention
amount_converted = employee.currency_id._convert(
    amount, account.currency_id or currency_id, self.env.company, date)
result[timesheet.id] = {'amount': amount_converted}
```

Requires `hr_hourly_cost` module on `hr.employee` to populate `hourly_cost`. The `amount` field is **always negative** because timesheet cost is recorded as an expense on the analytic account.

**Company一致性:** The method validates that `timesheet.company_id`, `account.company_id`, `task.company_id`, and `project.company_id` all match before computing. Raises `ValidationError` if they diverge across companies.

#### Access Control Methods

```python
def _check_can_write(self, values):
    # Raises AccessError if non-approver tries to write a line owned by another user

def _check_can_create(self):
    # Hook; default is pass. Extensions (e.g., mrp_account) override for extra checks.
```

#### Favorite Project Resolution

```python
@api.model
def _get_favorite_project_id(self, employee_id=False):
    # Returns statistical mode of project_id from last 5 timesheets
    # Falls back to company.internal_project_id (if active, allow_timesheets, readable)
    return mode([t.project_id.id for t in last_timesheets])
```

Used in `default_get()` when `is_timesheet` context is active but no `project_id` is provided. The fallback to `internal_project_id` ensures a valid project is always pre-selected.

#### Domain Helpers

```python
def _domain_project_id(self):
    # Non-manager: privacy in ['employees','portal'] OR user in message_partner_ids
    domain = [('allow_timesheets', '=', True), ('is_template', '=', False)]
    if not manager: domain &= [privacy_or_follower_condition]

def _domain_employee_id(self):
    # Non-approver: user_id must match current user
    domain = [('company_id', 'in', allowed_company_ids)]
    if not approver: domain &= [('user_id', '=', user.id)]
```

#### Portal Domain

```python
def _timesheet_get_portal_domain(self):
    # Internal user with group_hr_timesheet_user → standard ir.rule
    # Otherwise → projects where privacy='invited_users' or 'portal'
    #             AND (message_partner_ids or partner_id includes user's commercial_partner)
```

#### Other Key Methods

```python
def _is_readonly(self):
    # Overridden in mrp_account to return True for timesheets on confirmed MOs

def _split_amount_fname(self):
    # Returns 'unit_amount' when project_id is set (splits qty, not amount)

def _hourly_cost(self):
    return self.employee_id.hourly_cost or 0.0

def _default_user(self):
    return self.env.context.get('user_id', self.env.user.id)

@api.model
def get_unusual_days(self, date_from, date_to=None):
    # Delegates to employee._get_unusual_days() for public holiday highlighting
    return self.env.user.employee_id._get_unusual_days(date_from, date_to)
```

---

## `project.project` — Timesheet-Enabled Project

**Inheritance:** `_inherit = "project.project"`
**File:** `models/project_project.py`

### Fields

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `allow_timesheets` | `Boolean` | `True` | Computed + Stored + readonly=False. Auto-disabled when `account_id` is removed. Setting True without account auto-creates one. |
| `account_id` | `Many2one(account.analytic.account)` | Auto-created | Domain includes partner matching. Auto-created in `create()`/`write()` when `allow_timesheets=True` with no account. |
| `analytic_account_active` | `Boolean` | Related | `account_id.active` |
| `timesheet_ids` | `One2many` | — | All `account.analytic.line` records on this project |
| `timesheet_encode_uom_id` | `Many2one(uom.uom)` | Computed | From `company_id.timesheet_encode_uom_id` |
| `total_timesheet_time` | `Float` | Computed | Multi-UoM aggregation → encode UoM. Group-restricted. |
| `encode_uom_in_days` | `Boolean` | Computed | `timesheet_encode_uom_id == product_uom_day` |
| `is_internal_project` | `Boolean` | Computed | `self == company.internal_project_id`. Multi-company: appends company name to display_name. |
| `allocated_hours` | `Float` | `False` | User-set budget. `tracking=True`. |
| `effective_hours` | `Float` | Computed | `SUM(timesheet_ids.unit_amount)` |
| `remaining_hours` | `Float` | Computed | `allocated_hours - effective_hours`. Can be negative. |
| `is_project_overtime` | `Boolean` | Computed | `remaining_hours < 0` |

### `_compute_remaining_hours()`

Uses `_read_group` on `account.analytic.line` grouped by `project_id`:
```python
timesheets_read_group = self.env['account.analytic.line']._read_group(
    [('project_id', 'in', self.ids)],
    ['project_id'],
    ['unit_amount:sum'],
)
# effective_hours = round(timesheet_time_dict.get(project.id, 0.0), 2)
# remaining_hours = allocated_hours - effective_hours
# is_project_overtime = remaining_hours < 0
```

### `_compute_total_timesheet_time()` — Multi-UoM Aggregation

```python
for product_uom, unit_amount in timesheet_time_dict[project.id]:
    factor = (product_uom or project.timesheet_encode_uom_id).factor
    total_time += unit_amount * (1.0 if project.encode_uom_in_days else factor)
total_time /= project.timesheet_encode_uom_id.factor
project.total_timesheet_time = float_round(total_time, precision_digits=2)
```

When encoding in days, raw `unit_amount` is treated as already being in hours (reference unit) and only the final division by the day-factor is applied. Lines without `product_uom_id` use the project's `timesheet_encode_uom_id` as their UoM for conversion.

### `_search_is_project_overtime` — SQL Search

Only counts **top-level tasks** in **active states** (`01_in_progress`, `02_changes_requested`, `03_approved`, `04_waiting_normal`). This differs from `remaining_hours` which uses timesheet entries directly.

```sql
SELECT Project.id
  FROM project_project AS Project
  JOIN project_task AS Task
    ON Project.id = Task.project_id
 WHERE Project.allocated_hours > 0
   AND Project.allow_timesheets = TRUE
   AND Task.parent_id IS NULL
   AND Task.state IN ('01_in_progress','02_changes_requested','03_approved','04_waiting_normal')
 GROUP BY Project.id
HAVING Project.allocated_hours - SUM(Task.effective_hours) < 0
```

### `_check_allow_timesheet()` Constraint

Raises `ValidationError` if `allow_timesheets=True` with no `account_id` and the project is not a template. Uses `_get_all_plans()` to find the default plan name for the error message.

### Auto-Account Creation

- **`create()`**: Pre-creates `account.analytic.account` for all `allow_timesheets=True` projects in `vals_list` **before** calling `super()`, avoiding the `_check_allow_timesheet` validation error.
- **`write()`**: If `allow_timesheets` is set to `True` and `account_id` is missing, calls `_create_analytic_account()` on the filtered subset.

### Unlink Protection

`_unlink_except_contains_entries` raises `RedirectWarning` redirecting to `timesheet_action_project` with `active_ids` set to projects that have `timesheet_ids`.

### `_get_stat_buttons()`

Injects two buttons into the project smart bar:
1. **"Timesheets"** — shows `effective / allocated (percentage%)` with color coding (green <80%, yellow ≥80%, red >100%).
2. **"Extra Time"** — shown only when `allocated > 0` and `effective > allocated` (overtime), shows `exceeding_hours (+exceeding_rate%)`.

---

## `project.task` — Task Time Tracking

**Inheritance:** `_inherit = "project.task"`
**File:** `models/project_task.py`

### Fields

| Field | Type | Compute/Store | Notes |
|-------|------|---------------|-------|
| `timesheet_ids` | `One2many` | — | Direct timesheet lines on this task |
| `effective_hours` | `Float` | Computed + Stored | `SUM(timesheet_ids.unit_amount)`. `compute_sudo=True` |
| `subtask_effective_hours` | `Float` | Computed + Stored (recursive) | Propagates through all `child_ids` recursively |
| `total_hours_spent` | `Float` | Computed + Stored | `effective_hours + subtask_effective_hours` |
| `remaining_hours` | `Float` | Computed + Stored | `allocated_hours - effective_hours - subtask_effective_hours` |
| `progress` | `Float` | Computed + Stored | `(effective + subtask_effective) / allocated_hours`. `aggregator="avg"` |
| `overtime` | `Float` | Computed + Stored | `max(total_hours - allocated_hours, 0)` |
| `allow_timesheets` | `Boolean` | Computed + Stored | Mirrors `project_id.allow_timesheets`. `compute_sudo=True` |
| `remaining_hours_percentage` | `Float` | Computed + Stored | `remaining_hours / allocated_hours`. Supports SQL search |

### `_compute_subtask_effective_hours()` — Recursive

```python
task.subtask_effective_hours = sum(
    child.effective_hours + child.subtask_effective_hours
    for child_task in task.child_ids
)
```

Uses `with_context(active_test=False)` — archived subtasks still count toward total time. `recursive=True` on the field definition means Odoo manages the dependency chain bottom-up.

### `display_name` Enhancement

When context key `hr_timesheet_display_remaining_hours` is set, appends:
- Days: `"(X days remaining)"`
- Hours: `"(HH:MM remaining)"` with `-` prefix for negative remaining time.

### Title Parsing: Allocated Hours

Tasks created via quick-add with format `"Review PR 5h"` will have `allocated_hours = 5.0`. The regex `\s(\d+(?:\.\d+)?)[hH]` is defined in `_get_group_pattern()`. `_extract_allocated_hours()` strips the matched token from `display_name` after extraction.

### Constraint: Private Task Prohibition

```python
def _check_project_root(self):
    # Raises UserError if any timesheet exists on a task with no project_id
    # Prevents 'private task' timesheet entries
```

### Unlink Protection

`_unlink_except_contains_entries` raises `RedirectWarning` if any task has `timesheet_ids`, redirecting to `timesheet_action_task`. Also checks user access to the timesheet lines first — raises `UserError` if the user cannot access the timesheets.

---

## `hr.employee` — Employee Extension

**Inheritance:** `_inherit = "hr.employee"`
**File:** `models/hr_employee.py`

### Fields

**`has_timesheet`** — `Boolean` (computed)
```python
def _compute_has_timesheet(self):
    result = dict(self.env.execute_query(SQL(
        """ SELECT id, EXISTS(
                    SELECT 1 FROM account_analytic_line
                     WHERE project_id IS NOT NULL AND employee_id = e.id
                     LIMIT 1)
              FROM hr_employee e
             WHERE id in %s """,
        tuple(self.ids),
    )))
    # Returns True for the first timesheet found (LIMIT 1)
```
Uses raw SQL with `EXISTS(...) LIMIT 1` for performance. `execute_query(SQL(...))` is the Odoo 19 safe query API.

### `action_unlink_wizard()`

Raises `UserError` if ALL of: user lacks `group_hr_timesheet_approver`, employee has timesheets (`has_timesheet=True`), and employee has no active employment record. Prevents deletion of employees whose timesheet history must be preserved.

---

## `res.company` — Company Settings

**Inheritance:** `_inherit = "res.company"`
**File:** `models/res_company.py`

### Fields

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `project_time_mode_id` | `Many2one(uom.uom)` | `product_uom_hour` | Used as fallback `product_uom_id` on timesheet creation. Also sets project/task time mode. |
| `timesheet_encode_uom_id` | `Many2one(uom.uom)` | `product_uom_hour` | User's preferred encoding unit in timesheet UI. |
| `internal_project_id` | `Many2one(project.project)` | Auto-created | Default project for timesheet entries not linked to a client project. Created via `_create_internal_project_task()` on company creation. |

### `_create_internal_project_task()`

Called from `create()` via `sudo()` (user may create company without project creation rights). Creates:
- Project: name=`'Internal'`, `allow_timesheets=True`, company-matched
- Two tasks: `'Training'` and `'Meeting'`
- Stage: `hr_timesheet.internal_project_default_stage` (sequence=1, name=`'Internal'`)

Constraint `_check_internal_project_id_company` prevents assigning an internal project from a different company.

---

## `res.config.settings` — Configuration

**Inheritance:** `_inherit = "res.config.settings"`
**File:** `models/res_config_settings.py`

| Field | Type | Notes |
|-------|------|-------|
| `module_project_timesheet_holidays` | `Boolean` | Triggers installation of `project_timesheet_holidays`. Only shown when `module_hr_timesheet` is installed. |
| `reminder_user_allow` | `Boolean` | Employee reminder notifications |
| `reminder_allow` | `Boolean` | Approver reminder notifications |
| `project_time_mode_id` | `Many2one(uom.uom)` | Related to `company_id.project_time_mode_id`, `readonly=False` for write-back |
| `timesheet_encode_method` | `Selection(hours/days)` | Inverse writes to `company_id.timesheet_encode_uom_id` |
| `is_encode_uom_days` | `Boolean` | Computed from `timesheet_encode_method`. Used in view conditions |

---

## Supporting Models

### `ir_http` — Session Info for JS Widget

`session_info()` injects per-company into the web session:
```python
result["user_companies"]["allowed_companies"][company.id] = {
    "timesheet_uom_id": company.timesheet_encode_uom_id.id,
    "timesheet_uom_factor": company.project_time_mode_id._compute_quantity(
        1.0, company.timesheet_encode_uom_id, round=False),
}
result["uom_ids"] = self.get_timesheet_uoms()
```
Enables the `timesheet_uom` JS widget to format values correctly per company in multi-company setups.

### `ir_ui_menu` — Menu Visibility

`_load_menus_blacklist`: Hides `timesheet_menu_activity_user` ("My Timesheets" activity menu) when the user has `group_hr_timesheet_approver`, since approvers see the full "Timesheets" menu instead.

### `uom.uom` — UoM Extension

- `timesheet_widget`: Char field storing the JS widget name. `uom.product_uom_day` → `float_toggle`; `uom.product_uom_hour` → `float_time`.
- `_unprotected_uom_xml_ids()`: Returns only `["product_uom_dozen", "product_uom_pack_6"]` — **hour and day UoM cannot be deleted** while `hr_timesheet` is installed.

### `account.analytic.applicability` — Business Domain

`business_domain` selection adds `'timesheet'`. Enables the applicability system to apply specific analytic plans to timesheet entries (e.g., a dedicated "Timesheet" plan alongside the general project plan).

### `project.update` — Timesheet Snapshot

On `create()`, each update writes timesheet stats to the update record:
- `allocated_time`: `project.allocated_hours × (hour_factor / encode_uom_factor)`, rounded to integer.
- `timesheet_time`: `project.sudo().total_timesheet_time`, rounded to integer.
- `uom_id`: `company.timesheet_encode_uom_id`.
- `timesheet_percentage`: `round(timesheet_time × 100 / allocated_time)`.

### `project.collaborator` — Portal ACL Toggle

When `_toggle_project_sharing_portal_rules(active=True)` is called (project sharing enabled), it also activates:
1. `access_account_analytic_line_portal_user` ACL record (perm_write=True).
2. `timesheet_line_rule_portal_user` ir.rule (portal can read/write/create/unlink timesheets on projects they collaborate on).

### `account.analytic.line.calendar.employee` — Calendar Filter Preferences

`account.analytic.line.calendar.employee` — lightweight model for per-user, per-employee calendar visibility:
- `user_id`: defaults to `self.env.user`.
- `employee_id`: which employee's timesheets to show in calendar.
- `checked`: visibility toggle (default True).
- `active`: soft-delete toggle (default True).

### `hr.employee.public` — Public Employee Extension

- `has_timesheet`: related to `employee_id.has_timesheet`.
- `action_timesheet_from_employee()`: only functional for internal users (`is_user=True`).

---

## Security Model

### Groups Hierarchy

```
base.group_user
  └── group_hr_timesheet_user        # Own timesheets only
        └── group_hr_timesheet_approver  # All timesheets in visible projects
              └── group_timesheet_manager  # Full access (also implies hr.group_hr_user)

res_groups_privilege_timesheets (privilege marker, category: Services/Timesheets)
```

### ir.rule Domains on `account.analytic.line`

| Group | Domain | Effect |
|-------|--------|--------|
| `group_hr_timesheet_user` | `user_id = user.id` AND (visibility check) | Own lines only |
| `group_hr_timesheet_approver` | visibility check | All lines in visible projects |
| `group_timesheet_manager` + `project.group_project_manager` | `[('project_id', '!=', False)]` | All timesheet lines |
| `base.group_portal` (inactive) | Portal collaboration check | Portal collaborator's own lines on shared projects |

### Portal Rule

`timesheet_line_rule_portal_user` is **inactive by default**. Activated when project sharing is enabled (via `project.collaborator._toggle_project_sharing_portal_rules()`). Non-collaborators see no timesheet records.

---

## Performance Notes

| Pattern | Technique | Why |
|---------|-----------|-----|
| `_compute_remaining_hours` | `_read_group` (SQL `GROUP BY`) | Single query for all projects, no N+1 |
| `total_timesheet_time` | `_read_group` + per-line UoM conversion | Scales with project count, not timesheet count |
| `has_timesheet` | `EXISTS(SELECT 1 LIMIT 1)` raw SQL | Stops at first match; bypasses ORM overhead |
| Overtime/remaining % searches | Raw `SQL()` via `_search_*` | Float fields cannot be efficiently searched via ORM |
| `subtask_effective_hours` | `recursive=True` field + `active_test=False` | Odoo manages bottom-up dependency chain |
| Calendar batch create | Prefetch all employees with single `browse()` | Avoids N single-record fetches in loop |

---

## Edge Cases

1. **Mixed UoM on same project**: `total_timesheet_time` converts each line's `product_uom_id` → reference unit → encode UoM. Lines without `product_uom_id` use the project's `timesheet_encode_uom_id` for conversion.

2. **Employee in multiple companies**: Non-approver users see only the employee matching their current company. User-id-based lookup in `create()` picks the current company if exactly one match exists, otherwise uses `self.env.company`.

3. **Archived employee on existing timesheet**: `write()` raises `UserError`. `has_timesheet` computation via raw SQL still finds the record (archived lines remain). Employee deletion is blocked by `action_unlink_wizard()`.

4. **`allow_timesheets` toggle with existing entries**: Users can disable timesheets on projects that have entries. Entries persist but new entries cannot be created. The analytic account is **not** auto-deleted.

5. **Private task timesheet**: Attempting to remove `project_id` from a task with timesheet lines raises `UserError`. Creating a timesheet with a task whose `project_id` is null raises `ValidationError`.

6. **Company mismatch**: `_timesheet_postprocess_values` raises `ValidationError` if `company_id` diverges across timesheet, account, task, and project.

7. **Internal project deleted manually**: `company.internal_project_id` becomes `False`. `_get_favorite_project_id` falls back gracefully by checking `has_access('read')`, `active`, and `allow_timesheets` on the result.

8. **`internal_project_id` cross-company**: A project is `is_internal_project = True` only for its own company. It is never treated as internal for another company, even if both companies can access it.

9. **Uninstall cleanup**: `uninstall_hook` must unlink auto-created `account.analytic.account` records (those created by `_create_analytic_account()` on project creation) and reset `company.internal_project_id`.

10. **WIP report removal**: `get_views()` strips the MRP `wip_report` print button from toolbar when the view arch contains a `timesheet_uom*` widget, preventing irrelevant manufacturing reports from appearing in timesheet views.

---

## Cross-Module Integration Map

```
hr_timesheet
  ├── hr                          # hr.employee, has_timesheet, action_unlink_wizard
  ├── hr_hourly_cost              # employee.hourly_cost → _hourly_cost()
  ├── analytic                    # account.analytic.line (base), _default_user()
  ├── project                     # project.project, project.task, project.update
  ├── uom                         # uom.uom, timesheet_encode_uom_id, timesheet_widget
  │
  ├── project_timesheet_holidays  (optional) — links timesheets to hr.leave
  ├── mrp_account                 (optional) — _is_readonly() locks timesheets on confirmed MOs
  └── sale_timesheet              (optional) — _get_timesheet() includes SO lines on tasks
```

---

## Odoo 18 → 19 Changes

| Area | Change |
|------|--------|
| `account.analytic.line` | `_compute_partner_id` now checks `task_id.partner_id` first, correcting a scenario where the project-level partner was incorrectly used |
| `project.project` | `allow_timesheets` is now **computed+stored** (previously a plain Boolean); auto-disabled when `account_id` is removed |
| `project.project` | `is_internal_project` field added; multi-company display name appends `"- CompanyName"` |
| `project.project` | `_search_is_project_overtime` SQL query restricted to top-level tasks (`parent_id IS NULL`) in active states only |
| `project.project` | `_timesheet_preprocess_get_accounts` now validates **all mandatory plans** from the applicability system, not only the default analytic account |
| `account.analytic.line` | Employee resolution in `create()` uses `execute_query(SQL(...))` (Odoo 19 ORM safe query API) |
| `hr.employee` | Multi-company: display name appends `"- CompanyName"` when employee appears in multiple companies |
| General | `project.group_project_manager` now **implies** `group_hr_timesheet_approver` (via XML assignment in `hr_timesheet_security.xml`) |

---

## Key Computed Field Formulas

| Field | Model | Formula |
|-------|-------|---------|
| `effective_hours` | `project.project` | `SUM(timesheet_ids.unit_amount)` |
| `total_timesheet_time` | `project.project` | Multi-UoM conversion of all `timesheet_ids.unit_amount` → encode UoM |
| `remaining_hours` | `project.project` | `allocated_hours - effective_hours` |
| `is_project_overtime` | `project.project` | `remaining_hours < 0` |
| `effective_hours` | `project.task` | `SUM(timesheet_ids.unit_amount)` |
| `subtask_effective_hours` | `project.task` | `SUM(child.effective_hours + child.subtask_effective_hours)` (recursive) |
| `total_hours_spent` | `project.task` | `effective_hours + subtask_effective_hours` |
| `progress` | `project.task` | `(effective_hours + subtask_effective_hours) / allocated_hours` |
| `overtime` | `project.task` | `max(total_hours_spent - allocated_hours, 0)` |
| `remaining_hours` | `project.task` | `allocated_hours - effective_hours - subtask_effective_hours` |
| `amount` | `account.analytic.line` | `-unit_amount × employee_id.hourly_cost` (currency-converted to account currency) |
| `calendar_display_name` | `account.analytic.line` | `"ProjectName (XhYm)"` or `"ProjectName (Xd)"` |
