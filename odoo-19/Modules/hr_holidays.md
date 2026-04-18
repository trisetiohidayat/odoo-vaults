---
type: module
module: hr_holidays
tags: [odoo, odoo19, hr, leave, time-off, absence, accrual, allocation]
created: 2026-04-06
updated: 2026-04-11
DEPTH: L4
---

# Leave Management (`hr_holidays`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Time Off |
| **Technical** | `hr_holidays` |
| **Category** | Human Resources/Time Off |
| **Version** | 1.6 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Odoo Version** | 19 |
| **Model Files** | 19 files under `models/`, 4 wizard files, 1 controller, 4 report files |
| **Main Models** | `hr.leave`, `hr.leave.type`, `hr.leave.allocation`, `hr.leave.accrual.plan`, `hr.leave.accrual.plan.level`, `hr.leave.mandatory.day` |

## Description

Controls the time off schedule of the company. Allows employees to request time off. Managers can review and approve or reject requests. Configure time off types, allocate days, and track leave planning. Includes accrual plans, mandatory days, double validation workflows, and calendar sync.

## Dependencies

- `hr` — Employee records
- `calendar` — Meeting integration
- `resource` — Working time calendars and resource scheduling

## Internal Dependencies

Within the `hr_holidays` module itself, models depend on each other as follows:

```
hr.leave.type  -->  hr.leave.accrual.plan  -->  hr.leave.accrual.plan.level
hr.leave.allocation  -->  hr.leave.accrual.plan
hr.leave      -->  hr.leave.type
hr.leave      -->  hr.leave.allocation
hr.leave.allocation  -->  hr.leave.type
hr.employee   -->  hr.leave (consumed leaves balance)
hr.version    -->  hr.leave (contract schedule change handling)
resource.calendar.leaves  -->  hr.leave (public holiday re-evaluation)
mail.message.subtype  -->  hr.leave / hr.leave.allocation (department-scoped subtypes)
```

---

## Model: `hr.leave`

**File:** `models/hr_leave.py`
**Inherits:** `mail.thread.main.attachment`, `mail.activity.mixin`
**Records:** Time off (leave) requests submitted by employees.

This is the central model of the module. Every leave request is a `hr.leave` record. The model handles the full lifecycle from employee request to final approval/refusal, calendar meeting creation, resource calendar bridge, duration computation, double validation rules, and automatic cancellation when allocations become insufficient.

### Fields

#### Core Identifiers

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Free-text description (computed/inverse — employee-facing; `private_name` shown only to `hr_holidays.group_hr_holidays_responsible`) |
| `private_name` | Char | HR-only description field (gated by group) |
| `state` | Selection | Workflow state: `confirm`, `refuse`, `validate1`, `validate`, `cancel` |
| `active` | Boolean | Allows archiving records |
| `company_id` | Many2one | Company scoping (computed from employee) |
| `tz` | Selection | Employee's timezone (computed from employee or user) |

#### Leave Type and Employee

| Field | Type | Description |
|-------|------|-------------|
| `holiday_status_id` | Many2one | The leave type (e.g. "Paid Time Off", "Sick Leave") — required, tracked |
| `holiday_status_requires_allocation` | Boolean | Related from leave type (`requires_allocation`) |
| `color` | Integer | Related from leave type (Kanban color) |
| `validation_type` | Selection | Related from leave type (`leave_validation_type`) |
| `holiday_type` | Selection | Batch scope: `employee` (single), `department` (all dept employees), `category` (all in category) — stored on the form |
| `employee_id` | Many2one | Target employee — required, indexed |
| `employee_ids` | Many2many | Target employees (used when `holiday_type = department` or `category`) |
| `department_id` | Many2one | Department of the employee at time of request — computed+stored |
| `category_id` | Many2one | Employee category for batch allocation |
| `employee_company_id` | Many2one | Related from `employee_id.company_id` |

#### Date and Time

| Field | Type | Description |
|-------|------|-------------|
| `date_from` | Datetime | UTC-aware start datetime — **computed stored** from `request_date_from` + `request_hour_from` |
| `date_to` | Datetime | UTC-aware end datetime — **computed stored** from `request_date_to` + `request_hour_to` |
| `request_date_from` | Date | Writeable interface for start date |
| `request_date_to` | Date | Writeable interface for end date |
| `request_hour_from` | Float | Start hour (Float, e.g. 9.0 for 9:00 AM) for hour-unit requests |
| `request_hour_to` | Float | End hour for hour-unit requests |
| `request_date_from_period` | Selection | `am` or `pm` — determines half-day period |
| `request_date_to_period` | Selection | `am` or `pm` — for end of multi-day half-day requests |
| `duration_display` | Char | Human-readable duration string (e.g. "2 days") — computed |
| `number_of_days` | Float | Duration in **working days**, stored computed field |
| `number_of_hours` | Float | Duration in hours, stored computed field |
| `last_several_days` | Boolean | True if leave spans multiple calendar days (computed — inverse of "single-day" flag) |
| `tz_mismatch` | Boolean | True if employee's timezone differs from current user's timezone (computed) |

#### Request Unit (How Leave is Requested)

| Field | Type | Description |
|-------|------|-------------|
| `request_unit_half` | Boolean | True when unit is half-day (computed from leave type's `request_unit = 'half_day'`) |
| `request_unit_hours` | Boolean | True when unit is hours (computed from leave type's `request_unit = 'hour'`) |
| `leave_type_request_unit` | Char | Related from leave type |
| `leave_type_support_document` | Boolean | Related from leave type |

#### Resource and Calendar

| Field | Type | Description |
|-------|------|-------------|
| `resource_calendar_id` | Many2one | Employee's working schedule at time of leave — **computed stored** from contracts |
| `meeting_id` | Many2one | Related `calendar.event` — created when leave is validated |
| `tz_mismatch` | Boolean | True if employee's timezone differs from their resource calendar's timezone |

#### Approval and Validation

| Field | Type | Description |
|-------|------|-------------|
| `first_approver_id` | Many2one | Employee who performed first approval |
| `second_approver_id` | Many2one | Employee who performed second approval |
| `can_approve` | Boolean | Computed: current user can approve (first step) |
| `can_validate` | Boolean | Computed: current user can validate (second step) |
| `can_refuse` | Boolean | Computed: current user can refuse |
| `can_cancel` | Boolean | Computed: current user can cancel |
| `can_back_to_approve` | Boolean | Computed: can reset from `validate1` back to `confirm` |
| `is_hatched` | Boolean | True if state is not `validate` or `refuse` (strikethrough display) |
| `is_striked` | Boolean | True if state is `refuse` |

#### Balance and Allocation

| Field | Type | Description |
|-------|------|-------------|
| `max_leaves` | Float | Total allocated days for this type (computed) |
| `virtual_remaining_leaves` | Float | Remaining balance after this leave (for warning display) |

#### Dashboard Warnings

| Field | Type | Description |
|-------|------|-------------|
| `dashboard_warning_message` | Char | Computed warning message for the Leave Dashboard (e.g. "Exceeds available balance by X days") |
| `leave_type_increases_duration` | Char | Warning that leave duration has changed due to public holiday inclusion/exclusion settings |

#### Mandatory Day

| Field | Type | Description |
|-------|------|-------------|
| `has_mandatory_day` | Boolean | Computed: whether any day in leave range is a mandatory day for the employee (non-HR users cannot request leave on mandatory days) |

#### UX Flags

| Field | Type | Description |
|-------|------|-------------|
| `attachment_ids` | One2many | Attachments on the leave request |
| `supported_attachment_ids` | Many2many | Writeable computed field for attachments (respects `support_document` on type) |
| `supported_attachment_ids_count` | Integer | Count of supported attachments |

### State Machine

```
draft ──(submit)──> confirm ──(first approval)──> validate1 ──(second approval)──> validate
  │                    │                              │
  │                    └───────(refuse)───────────────┴──> refuse
  │                    └───────(cancel)──────────────────> cancel
  │
  └───────────────────(reset button)─────────────────────> draft (reset)
```

| State | Meaning | Who Acts |
|-------|---------|----------|
| `confirm` | Submitted for approval | Employee submits |
| `validate1` | First approval done, awaiting second | Manager or HR |
| `validate` | Fully approved — leave is active | System on second approval |
| `refuse` | Denied | Manager or HR |
| `cancel` | Cancelled by employee (before approval) | Employee |

### Key Methods

#### Date/Duration Computation

**`_compute_resource_calendar_id()`**
Returns the employee's working schedule (`resource.calendar`) at the time of the leave. It queries the employee's active `hr.version` contracts (via `contract_id`) that overlap the leave dates and returns the calendar from the contract whose `contract_date_start` is closest to the leave's `request_date_from`. This is the critical bridge between leave requests and the contract system — it determines which calendar's working hours apply to duration computation. If the employee has no contracts, falls back to the company-level resource calendar.

**`_compute_date_from_to()`**
Converts the employee-facing date interface (`request_date_from`, `request_date_to`, `request_hour_from`, `request_hour_to`, `request_date_from_period`) into UTC-aware `Datetime` fields `date_from` and `date_to`. For half-day requests, reads `request_date_from_period` to set `hour_from`/`hour_to` to the correct morning (0–12) or afternoon (12–24) window. For hour-unit requests, reads `request_hour_from` and `request_hour_to` floats directly. This method uses the `tz` field to localize the request dates before converting to UTC.

**`_compute_duration()`**
Computes `number_of_days` and `number_of_hours` from the `date_from`/`date_to` range. Delegates to `_get_durations()`.

**`_get_durations(check_leave_type=True, resource_calendar=None)`** — `@api.model`
Static method. Takes a date range and employee IDs, returns a dict mapping employee ID to `(number_of_days, number_of_hours)`. Uses batched `_work_intervals_batch()` on `resource.resource` to compute working time — only actual working hours within the employee's calendar count. When `check_leave_type=True` (default), excludes public holidays if `include_public_holidays_in_duration = False` on the leave type. The method also reads `include_public_holidays_in_duration` directly from `holiday_status_id` to determine whether to pass `resource.calendar.leaves` as an exclusion argument to `_work_intervals_batch()`.

**`_default_get_request_dates(values)`**
In `default_get()`, converts view-initialized `date_from`/`date_to` values to `request_date_from`/`request_date_to` using the client's timezone (`pytz`). This ensures that when the form loads with default dates from the calendar view, they are correctly localized before being stored as request dates.

**`_compute_last_several_days()`**
Sets `last_several_days = True` if `number_of_days > 1`. This field drives the "all day" toggle display in the form view.

**`_compute_tz_mismatch()`**
Sets `tz_mismatch = True` if the leave's `tz` differs from the current user's `tz`. Used for UI warnings when the employee's timezone does not match the approver's timezone.

**`_compute_leave_type_increases_duration()`**
If `include_public_holidays_in_duration = False` but the leave spans a public holiday (which would increase duration when the flag is True), sets a warning message. This alerts the employee that their working schedule expects them to work on a covered public holiday.

**`_compute_dashboard_warning_message()`**
For leaves in non-terminal states (`confirm`, `validate1`, `validate`), computes a warning if the leave exceeds available allocation balance. The message includes the overdraw amount. Leaves in `cancel` or `refuse` state have no warning. Before writing, `_check_validity()` raises a `ValidationError` with this message if it is set, blocking the operation.

#### Validation

**`_check_validity()`**
Checks whether the employee has sufficient allocation balance for the leave. Called during `_validate_leave_request()` and when allocations change. Raises `ValidationError` if balance is insufficient. Respects `allows_negative` and `max_allowed_negative` on the leave type. Also checks mandatory days: non-HR users cannot have a leave covering a mandatory day.

**`_check_approval_update(state, raise_if_not_possible=True)`**
Determines whether the current user can transition a leave to `state`. Returns `True`/`False` if `raise_if_not_possible=False`, otherwise raises `AccessError`. The check evaluates:
1. Is the user superadmin or a Holiday Manager? → always allowed
2. Is the user a Holiday Officer? → allowed for refusal and cancellation
3. Is the user the employee's leave manager? → allowed for approval steps
4. Is the user the employee's direct manager? → allowed for first approval
5. Special case for `cancel`: the employee themselves can cancel their own leaves in `confirm`/`validate1` state

**`_check_double_validation_rules(employees, state)`**
Determines whether a leave requires a second-level approval. If the user is a Holiday Manager, skip all checks. If `state == 'validate1'` and there are employees whose leave manager is NOT the current user, and the user is not an officer, raise `AccessError`. If `state == 'validate'` and the user is not an officer, raise `AccessError`.

**`_get_overlapping_contracts()`**
Returns the list of `hr.version` (contract) records for this leave's employee that overlap the leave's date range. Used by `hr_version.write()` to detect schedule changes. If all overlapping contracts use the same `resource_calendar_id` as the leave, returns `False` (no action needed).

**`_get_responsible_for_approval()`**
Returns the `res.users` recordset responsible for approving this leave. Checks in order: holiday type's `responsible_ids`, the employee's `leave_manager_id`, the department manager. Used for activity notifications and message posting.

**`_check_contracts()`**
Called in `@api.constrains` on `date_from`/`date_to`. When a leave overlaps a contract version change (different `resource_calendar_id`), calls `hr_version._check_overlapping_contract()` which either updates the leave's calendar or triggers a split/refuse via `_split_leaves()`.

**`_split_leaves(split_date_from, split_date_to=False)`**
Splits a leave that spans a contract schedule change into multiple leaves. If `split_date_to` is not given, the split is `[split_date_from - 1 day]` and the new leave starts at `split_date_from`. Handles multi-day leaves correctly — only creates new leaves for segments with non-zero duration. The original leave is shortened in-place; additional split leaves are created and returned.

#### Workflow Actions

**`action_approve(check_state=True)`**
First-level approval. Transitions `confirm` → `validate1` (if double validation) or `confirm` → `validate` (if single validation). Calls `_action_validate()` which calls `_validate_leave_request()` on transition to `validate`. Reads `can_approve` or falls back to `validation_type` when `check_state=False`.

**`action_validate()`** (internal `_action_validate(check_state=True)`)
Second-level validation. Transitions `validate1` → `validate`. Requires `can_validate` for the current user. Sets `second_approver_id` and calls `_validate_leave_request()`.

**`action_refuse()`**
Sets state to `refuse`. Unlinks linked calendar meetings. Unlinks resource leaves. Posts refusal notification to employee.

**`action_draft()` / `action_send_to_draft()`**
Resets state from `refuse` or `cancel` back to `draft`, allowing re-editing.

**`action_cancel()`**
Opens the `hr.holidays.cancel.leave` wizard. Does not directly cancel — the wizard calls `_action_user_cancel()`.

**`_action_user_cancel(reason=None)`**
Cancels a leave on behalf of the employee. Calls `_force_cancel()`. Only callable if `can_cancel` is True for the current user.

**`_force_cancel(reason, msg_subtype, notify_responsibles=True)`**
Performs the actual cancellation. Posts a message with the cancellation reason. Notifies managers/HR depending on the validation type and current state. Uses `sudo()` internally to bypass access checks when called during module uninstall.

#### Calendar Meeting

**`_validate_leave_request()`**
Called when a leave transitions to `validate`. Creates or updates the linked `resource.calendar.leaves` record (the resource bridge) via `_create_resource_leave()`. Creates a `calendar.event` via `_prepare_holidays_meeting_values()`. Posts an acceptance notification to the employee.

**`_prepare_holidays_meeting_values()`**
Builds the `calendar.event` creation dict. Handles all-day vs. timed events based on `request_unit_hours` and `request_unit_half`. Converts dates to the user's timezone for storage. Sets `allday=True` for day/half-day requests. Sets `res_id` to link back to the leave.

#### Allocation Balance

**`_compute_leaves()`**
Computes `virtual_remaining_leaves` and `max_leaves` for display on the leave form. Internally calls `employee_id._get_consumed_leaves()` and extracts the values for the specific leave's `holiday_status_id`. This is a per-record compute (not a batch method), making it slightly less efficient than `hr.leave.type.get_allocation_data()` but sufficient for single-record views.

**`get_mandatory_day()`**
Checks whether any date in the leave range overlaps a mandatory day record (`hr.leave.mandatory.day`) scoped to the employee's department, job, or global calendar. Used to set `has_mandatory_day` and block non-HR users. The implementation calls `employee_id.sudo()._get_mandatory_days()` and then filters the result against the leave's scope (date range, calendar, department hierarchy).

#### Automatic Cleanup

**`_cancel_invalid_leaves()`** — cron method
Runs daily. Finds all `validate`d leaves that no longer have sufficient allocation balance (due to allocation changes, expiration, or carryover limits). For each:
- Transitions state back to `confirm` (or refuses if past the approval threshold)
- Sends a notification to the employee
- Triggers re-validation to recalculate duration

This is the safety net for the "allocation expired mid-leave" scenario.

### Constraints

| Constraint | Condition | Message |
|-----------|---------|---------|
| `_date_check2` | `date_from <= date_to` | Start must be before end |
| `_date_check3` | `request_date_from <= request_date_to` | Request start must be before request end |

Compound index `('date_to', 'date_from')` on the model for optimized date-range queries and overlap detection.

---

## Model: `hr.leave.type`

**File:** `models/hr_leave_type.py`
**Inherits:** `mail.thread`
**Records:** Time off type definitions (e.g. "Annual Leave", "Sick Leave", "Parental Leave").

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Type name — required, translatable |
| `sequence` | Integer | Sort order in dropdown (default 100). Smallest = default in requests |
| `create_calendar_meeting` | Boolean | Validated leaves of this type create calendar events |
| `color` | Integer | Kanban color index |
| `icon_id` | Many2one | Icon for kanban/card display |
| `active` | Boolean | Deactivate without deleting |
| `hide_on_dashboard` | Boolean | Hidden on dashboard but still selectable |
| `leave_validation_type` | Selection | `no_validation`, `hr`, `manager`, `both` — default `hr` |
| `requires_allocation` | Boolean | Whether employees need an allocation to request this type — required field |
| `employee_requests` | Boolean | Allow employees to self-request allocations of this type |
| `allocation_validation_type` | Selection | Validation for employee allocation requests: `hr`, `manager`, `both`, `no_validation` |
| `time_type` | Selection | `leave` (absence) or `other` (counts as worked time for accruals) — default `leave` |
| `request_unit` | Selection | `day`, `half_day`, `hour` — default `day` |
| `unpaid` | Boolean | Whether the leave is unpaid (affects payroll) |
| `include_public_holidays_in_duration` | Boolean | Count public holidays in leave duration (adds days) — immutable if existing leaves overlap public holidays |
| `leave_notif_subtype_id` | Many2one | Mail notification subtype for leaves |
| `allocation_notif_subtype_id` | Many2one | Mail notification subtype for allocations |
| `support_document` | Boolean | Whether employees can attach documents |
| `allow_request_on_top` | Boolean | Allow requesting days beyond available balance (cannot be used with `time_type = 'leave'`) |
| `has_valid_allocation` | Boolean | Computed+search: whether a valid allocation exists for current employee/context date range |
| `responsible_ids` | Many2many | HR officers notified for this leave type |
| `accruals_ids` | One2many | Accrual plans linked to this leave type |
| `accrual_count` | Integer | Count of linked accrual plans |
| `allows_negative` | Boolean | Allow employees to go negative balance |
| `max_allowed_negative` | Integer | Maximum negative days (requires `allows_negative = True`) |
| `company_id` | Many2one | Company scoping |
| `country_id` | Many2one | Country (computed from company) |
| `max_leaves` | Float | Total allocated days across all allocations (computed per-employee in context) |
| `leaves_taken` | Float | Days consumed in current year |
| `virtual_remaining_leaves` | Float | Current balance: `max_leaves - leaves_taken` |
| `allocation_count` | Integer | Number of allocations of this type |
| `group_days_leave` | Float | Total days for group/company-level leaves |
| `is_used` | Boolean | Whether this type has any active leaves or allocation records |

### Key Methods

**`_search_valid(operator, value)`** — custom search on `has_valid_allocation`
This is the core search method that powers the leave type selector dropdown. It:
1. Reads `default_date_from`/`default_date_to`/`tz` from context to determine the target date range
2. Gets `default_employee_id` from context (or falls back to current user)
3. Searches for approved allocations (`state = 'validate'`) where `date_from <= date_to` for that employee
4. Returns domain `[('id', operator, found_leave_type_ids)]`

This is why the leave type dropdown only shows types with valid allocations for the current employee — the `has_valid_allocation` field uses this search.

**`get_allocation_data(employees, target_date=None)`**
Central data provider for leave balance information. Returns structured data per employee:

```python
{
  employee: [
    (leave_type_name, {
      'remaining_leaves': float,
      'virtual_remaining_leaves': float,
      'max_leaves': float,
      'accrual_bonus': float,        # future accruals from today to target_date
      'leaves_taken': float,         # validated leaves
      'virtual_leaves_taken': float, # validated + confirm/validate1
      'leaves_requested': float,     # virtual_taken - taken
      'leaves_approved': float,       # taken
      'closest_allocation_remaining': float,
      'closest_allocation_expire': str,
      'total_virtual_excess': float,
      'virtual_excess_data': {date_str: {amount, is_virtual}},
      'request_unit': str,
      'icon': str,
      'allows_negative': bool,
      'max_allowed_negative': int,
    }, requires_allocation, leave_type_id)
  ]
}
```

Called by: Leave Dashboard, `hr.employee._get_consumed_leaves()`, and `hr.leave._compute_leaves()`.

**`_get_closest_expiring_leaves_date_and_count(allocations, remaining_leaves, target_date)`**
Returns `(closest_expiration_date, expiring_leaves_count)` for all allocations in scope. Handles three types of expiration:
1. The allocation's own `date_to`
2. The carryover date (when unused days are subject to `postpone_max_days`)
3. The carried-over days expiration date

This drives the "X days will expire on Y" warning on the dashboard.

**`_compute_leaves()`**
Recomputes `max_leaves`, `leaves_taken`, and `virtual_remaining_leaves`. Uses `get_allocation_data()` internally. The `@api.depends_context` includes `employee_id`, `default_employee_id`, `leave_date_from`, `default_date_from` — the compute is context-sensitive.

**`action_see_days_allocated()`** / **`action_see_group_leaves()`** / **`action_see_accrual_plans()`**
Action buttons that open filtered list views for allocations, group leaves, and accrual plans of this type.

**`_compute_display_name()`**
Appends balance info to the leave type name when in an employee context: `"Paid Time Off (12.5 remaining out of 20.0 days)"`.

### Validation Type Matrix

| `leave_validation_type` | First Approval By | Second Approval By |
|------------------------|-------------------|--------------------|
| `no_validation` | — (auto-approved) | — |
| `hr` | HR Officer | — |
| `manager` | Employee's Manager | — |
| `both` | HR Officer OR Manager | The other party |

When `employee_requests = True`, employees can submit allocation requests using `allocation_validation_type` (which may differ from `leave_validation_type`).

### Constraints

| Constraint | Condition | Message |
|-----------|---------|---------|
| `_check_negative` | `NOT allows_negative OR max_allowed_negative > 0` | Max excess must be > 0 if negative allowed |
| `check_allocation_requirement_edit_validity` | Cannot set `requires_allocation = False` if any leaves of that type exist | Create a new type instead |

---

## Model: `hr.leave.allocation`

**File:** `models/hr_leave_allocation.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`
**Records:** Grants of time off days to employees. Can be regular (one-time) or accrual-based (recurring).

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Computed/inverse: "{Leave Type} ({N} day(s))" or hour variant — user-editable |
| `is_name_custom` | Boolean | True if user manually edited the name (prevents auto-update) |
| `name_validity` | Char | Name with validity dates appended: "PTO (from Jan 1 to Dec 31)" |
| `state` | Selection | `confirm`, `refuse`, `validate1`, `validate` |
| `holiday_status_id` | Many2one | Leave type being allocated — computed from accrual plan or default |
| `employee_id` | Many2one | Target employee — required, indexed |
| `department_id` | Many2one | Target department — computed from employee |
| `manager_id` | Many2one | Employee's manager — computed |
| `date_from` | Date | Start date of allocation validity — required, default today |
| `date_to` | Date | End date (optional, for temporary allocations) |
| `number_of_days` | Float | Days granted — stored computed from `number_of_days_display` or hours conversion |
| `number_of_days_display` | Float | Display duration in days — mirrors `number_of_days` for regular allocations |
| `number_of_hours_display` | Float | Duration in hours (for hour-unit types) |
| `duration_display` | Char | Human-readable: "5 days" or "40 hours" |
| `allocation_type` | Selection | `regular` (one-time) or `accrual` (periodic) — default `regular` |
| `accrual_plan_id` | Many2one | Linked accrual plan — inverse sets `allocation_type = 'accrual'` |
| `lastcall` | Date | Date of the last completed accrual run (updated only on accrual dates) |
| `actual_lastcall` | Date | Actual datetime of the last accrual action — includes carryover/level transition dates that don't update `lastcall` |
| `nextcall` | Date | Next scheduled accrual run date |
| `already_accrued` | Boolean | Whether the current period's accrual has been applied (prevents double accrual in `start` gain mode) |
| `last_executed_carryover_date` | Date | Tracks when carryover was last applied — used to distinguish pre- and post-transition accruals in `accrued_gain_time = 'start'` mode |
| `yearly_accrued_amount` | Float | Total days accrued in the current calendar year (for yearly cap checking) |
| `expiring_carryover_days` | Float | Carried-over days that will expire on `carried_over_days_expiration_date` |
| `carried_over_days_expiration_date` | Date | When carried-over days expire |
| `max_leaves` | Float | Total allocated days (from `_get_consumed_leaves()`) |
| `virtual_remaining_leaves` | Float | Remaining balance after consumed leaves |
| `leaves_taken` | Float | Days consumed from this allocation |
| `approver_id` | Many2one | First approver |
| `second_approver_id` | Many2one | Second approver |
| `can_approve` / `can_validate` / `can_refuse` | Boolean | Per-user permission computed fields |
| `type_request_unit` | Selection | `day`, `half_day`, `hour` — computed from accrual plan or leave type |
| `is_officer` | Boolean | True if current user is in `hr_holidays.group_hr_holidays_user` |
| `active_employee` | Boolean | Related from `employee_id.active` |

### Key Methods

#### Workflow State Machine

**`_get_next_states_by_state()`**
Returns a dict of allowed target states for each current state, scoped by user role (officer, time-off manager, or regular user):

```python
state_result = {
    'confirm': {'validate', 'refuse', 'validate1', ...},
    'validate1': {'confirm', 'validate', 'refuse', ...},
    'validate': {'confirm', 'refuse', ...},
    'refuse': {'confirm', ...},
}
```

This is the authoritative matrix for which state transitions are permitted for the current user. Officers can do almost anything. Time-off managers can approve/refuse within their scope. Regular users have very limited transitions.

#### Accrual Processing

**`_process_accrual_plans(date_to=False, force_period=False, log=True)`**
The core accrual engine. Called by `_update_accrual()` cron and directly on allocation approval to catch up missed periods.

**Algorithm (fully detailed):**
```
while allocation.nextcall <= date_to:
    current_level = _get_current_accrual_plan_level_id(allocation.nextcall)
    if not current_level: break

    period_end = normal accrual date for current level
    # Adjust nextcall if level transition, carryover, or expiration is sooner
    if level_transition_date < period_end: nextcall = min(nextcall, level_transition_date)
    if carryover_date < nextcall: nextcall = min(nextcall, carryover_date)
    if expiration_date < nextcall: nextcall = min(nextcall, expiration_date)

    period_start = _get_previous_date(lastcall)    # always returns lastcall except on first call
    period_end   = _get_next_date(lastcall)

    # Skip if already accrued this period (for 'start' gain time)
    is_accrual_date = (nextcall == period_end) or (nextcall == level_transition_date)
    if not allocation.already_accrued and is_accrual_date and accrued_gain_time == 'start':
        allocation._add_days_to_allocation(...)
        allocation.already_accrued = True

    # Carryover: runs at carryover_date
    if nextcall == carryover_date:
        allocation.last_executed_carryover_date = carryover_date
        if action_with_unused_accruals == 'lost':
            allocation.number_of_days = min(number_of_days, postpone_max_days) + leaves_taken
        elif action_with_unused_accruals == 'all' and carryover_options == 'limited':
            allocation.number_of_days = min(postpone_max_days, remaining) + leaves_taken
        allocation.expiring_carryover_days = allocation.number_of_days

    # Carryover expiry: runs when carried-over days expire
    if accrual_validity and nextcall == carried_over_days_expiration_date:
        expiring_days = max(0, expiring_carryover_days - leaves_taken)
        allocation.number_of_days -= expiring_days

    # Normal 'end' gain time accrual
    if not allocation.already_accrued and is_accrual_date and accrued_gain_time == 'end':
        allocation._add_days_to_allocation(...)

    # Handle pre-transition accruals in 'start' mode
    if accrued_gain_time == 'start' and last_executed_carryover_date:
        if last_carryover_date <= nextcall <= carryover_period_end:
            allocation.number_of_days = min(number_of_days, postpone_max_days) + leaves_taken
            allocation.last_executed_carryover_date = carryover_date

    allocation.lastcall = allocation.nextcall
    allocation.actual_lastcall = allocation.nextcall
    allocation.nextcall = nextcall
    allocation.already_accrued = False
    if force_period and allocation.nextcall > date_to:
        allocation.nextcall = date_to

# Post-loop: process one more period if accrued_gain_time == 'start'
if accrued_gain_time == 'start' and not allocation.already_accrued:
    if actual_lastcall is at period_start or date_from:
        allocation._add_days_to_allocation(...)
        allocation.already_accrued = True
```

**`_get_current_accrual_plan_level_id(date, level_ids=False)`**
Returns `(current_level_record, level_index)`. The level is determined by comparing `date` against each level's milestone date (`date_from + start_count * multiplier`). Special handling for `transition_mode = 'immediately'`: the transition occurs on the milestone date even if the current accrual period hasn't ended. For `transition_mode = 'end_of_accrual'`, the transition is deferred until the period end.

**`_process_accrual_plan_level(level, start_period, start_date, end_period, end_date)`**
Computes days to add for one level in one accrual iteration. If `is_based_on_worked_time` or frequency is hourly: calls `_get_accrual_plan_level_work_entry_prorata()`. Otherwise returns `level.added_value` (with period proration if partial period).

**`_get_accrual_plan_level_work_entry_prorata(level, start_period, start_date, end_period, end_date)`**
Computes the proration ratio for worked-time accruals:

```
worked_hours = work_days_data['hours'] + eligible_leave_hours
total_expected = worked_hours + ineligible_leave_hours
work_entry_prorata = worked_hours / total_expected   # capped at 1.0
days_to_add = level.added_value * work_entry_prorata * period_prorata
```

For hourly frequency accruals: `planned_worked = work + eligible_leaves` always (no exclusion).
For non-hourly with `is_based_on_worked_time = True`: uses `planned_worked` not actual `worked` — this ensures employees are not penalized for taking eligible leave mid-period.
For non-hourly without `is_based_on_worked_time = True`: uses all calendar time.

**`_add_days_to_allocation(current_level, current_level_maximum_leave, leaves_taken, period_start, period_end)`**
Adds accrued days to `number_of_days`. Respects:
- `cap_accrued_time_yearly`: limits to `yearly_accrued_amount` remaining in the year
- `cap_accrued_time`: caps total balance at `maximum_leave`

**`_get_carryover_date(date_from)`**
Computes the carryover date:
- `year_start`: January 1 of the year containing `date_from`
- `allocation`: the allocation's own `date_from` month/day
- `other`: `carryover_month`/`carryover_day` of that year

If `date_from > carryover_date`, adds 1 year (carryover happens next year).

**`_get_future_leaves_on(accrual_date)`**
Creates a temporary copy of the allocation via `Model.new(origin=self)` and runs `_process_accrual_plans(accrual_date, log=False)` on it to compute how many more days will accrue by `accrual_date`. Returns the difference from current `number_of_days`. Used by `_get_consumed_leaves()` to show future accruals in balance calculations. The fake copy is discarded — no database write occurs.

**`_add_lastcalls()`** — helper for initialization and state recovery
Ensures `lastcall`, `actual_lastcall`, and `nextcall` are set on an allocation. Used when an allocation is approved and needs to establish its accrual clock. Sets `lastcall` to `max(date_from, today)`, then adjusts `nextcall` to the earliest of: first accrual date, carryover date, level transition date, or expiration date.

**`_reset_accrual()`**
Resets `lastcall = date_from`, `nextcall = False`, `number_of_days = 0`, `already_accrued = False` — used by `_get_future_leaves_on()` to reinitialize the fake copy before each preview run.

#### Cron Jobs

**`_update_accrual()`** — scheduled action
Searches all `accrual` allocations in `validate` state with `nextcall <= today` and calls `_process_accrual_plans()` on them. Runs daily (configured in `data/ir_cron_data.xml`).

### Constraint

| Constraint | Condition | Message |
|-----------|---------|---------|
| `_duration_check` | `number_of_days > 0` for regular allocations | Duration must be > 0 |

---

## Model: `hr.leave.accrual.plan`

**File:** `models/hr_leave_accrual_plan.py`
**Records:** Accrual plan definitions — the ruleset that drives periodic day granting.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Plan name — required |
| `time_off_type_id` | Many2one | Associated leave type — enforces one plan per type |
| `level_ids` | One2many | Accrual levels (sorted by `sequence`) |
| `transition_mode` | Selection | `immediately` (mid-period) or `end_of_accrual` — default `immediately` |
| `accrued_gain_time` | Selection | `start` (beginning of period) or `end` (end of period) — default `end` |
| `can_be_carryover` | Boolean | Whether unused days can be carried over at year end |
| `carryover_date` | Selection | `year_start`, `allocation`, `other` — default `year_start` |
| `carryover_day` | Integer | Day of month for custom carryover |
| `carryover_month` | Selection | Month for custom carryover (default current month) |
| `is_based_on_worked_time` | Boolean | Prorate accrual by actual attendance — auto-false if `accrued_gain_time = 'start'` |
| `added_value_type` | Selection | `day` or `hour` — stored on plan, propagated to first level |
| `employees_count` | Integer | Count of employees with this plan (from allocations) |
| `level_count` | Integer | Count of levels in this plan |

### Transition Modes

| Mode | Behavior |
|------|---------|
| `immediately` | When milestone date is crossed, the new accrual rate applies mid-period |
| `end_of_accrual` | Level transitions only take effect at the next scheduled accrual date after milestone |

### Accrued Gain Time

| Setting | Behavior |
|--------|---------|
| `start` | All days for the period are added on the first day of the period |
| `end` | Days are added on the last day of the period (default) |

When `accrued_gain_time = 'start'`, the system sets `already_accrued = True` after the first accrual to prevent double-accrual in the same period. The post-loop block processes one additional period after the main while-loop exits.

---

## Model: `hr.leave.accrual.plan.level`

**File:** `models/hr_leave_accrual_plan_level.py`
**Records:** Individual accrual levels within a plan.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | Integer | Sort order (auto-computed: `start_count * multiplier`) |
| `accrual_plan_id` | Many2one | Parent accrual plan — cascade delete |
| `start_count` | Integer | Time until milestone (e.g., 12) |
| `start_type` | Selection | Unit: `day`, `month`, `year` — default `day` |
| `milestone_date` | Selection | `creation` or `after` — inverse sets `start_count = 0` if `creation` |
| `added_value` | Float | Days/hours accrued per period (required, must be > 0) |
| `added_value_type` | Selection | `day` or `hour` — computed from leave type or plan |
| `frequency` | Selection | `hourly`, `daily`, `weekly`, `bimonthly`, `monthly`, `biyearly`, `yearly` |
| `week_day` | Selection | Day of week for `weekly` frequency |
| `first_day` / `second_day` | Integer | Day of month for `bimonthly` frequency (first < second required) |
| `first_month` / `second_month` | Selection | Month for `bimonthly`/`biyearly` frequencies |
| `first_month_day` / `second_month_day` | Integer | Day within month for `biyearly` (auto-clamped to month length) |
| `yearly_month` | Selection | Month for `yearly` frequency |
| `yearly_day` | Integer | Day for `yearly` frequency |
| `cap_accrued_time` | Boolean | Cap total balance at `maximum_leave` |
| `maximum_leave` | Float | Cap value for total balance (requires `cap_accrued_time = True`) |
| `cap_accrued_time_yearly` | Boolean | Cap yearly accrual at `maximum_leave_yearly` |
| `maximum_leave_yearly` | Float | Cap value for yearly accrual amount |
| `can_be_carryover` | Boolean | Related from plan (readonly) |
| `action_with_unused_accruals` | Selection | `lost` or `all` — default `lost` if plan has `can_be_carryover = False` |
| `carryover_options` | Selection | `unlimited` or `limited` — default `unlimited`, forced to `unlimited` if `action = lost` |
| `postpone_max_days` | Integer | Max days to carry over (requires `action = all` + `carryover_options = limited`) |
| `accrual_validity` | Boolean | Whether accrued days from this level have an expiry period |
| `accrual_validity_count` | Integer | Number of periods for validity (requires `accrual_validity = True`) |
| `accrual_validity_type` | Selection | Unit for validity period: `day` or `month` |

### Frequency Configuration

| Frequency | Required Fields |
|-----------|----------------|
| `hourly` | None |
| `daily` | None |
| `weekly` | `week_day` |
| `bimonthly` | `first_day`, `second_day`, `first_month`, `second_month` |
| `monthly` | None (defaults to day 1) |
| `biyearly` | `first_month`, `first_month_day`, `second_month`, `second_month_day` |
| `yearly` | `yearly_month`, `yearly_day` |

### Key Methods

**`_get_next_date(from_date)`** and **`_get_previous_date(from_date)`**
These two methods are the clock of the accrual system. `_get_next_date()` returns the next accrual date from a given reference point. `_get_previous_date()` returns the date the previous accrual would have occurred at (used for period boundary computation in proration). Both handle all frequency types correctly, including edge cases like month-end days (clamped via `monthrange`).

**`_get_level_transition_date(allocation_start)`**
Returns `allocation_start + start_count * start_type_multiplier`. Used to determine when a level transition should occur.

**`action_save_new()`**
Opens the accrual level form in dialog mode from the plan's action, returning the result of `accrual_plan_id.action_create_accrual_plan_level()`.

### Constraints

| Constraint | Condition | Message |
|-----------|-----------|---------|
| `_start_count_check` | `(start_count > 0 AND milestone_date = 'after') OR (start_count = 0 AND milestone_date = 'creation')` | You can not start an accrual in the past. |
| `_added_value_greater_than_zero` | `added_value > 0` | You must give a rate greater than 0 in accrual plan levels. |
| `_valid_postpone_max_days_value` | `action_with_unused_accruals != 'all' OR carryover_options != 'limited' OR postpone_max_days > 0` | You cannot have a maximum quantity to carryover set to 0. |
| `_valid_accrual_validity_value` | `NOT accrual_validity OR accrual_validity_count > 0` | You cannot have an accrual validity time set to 0. |
| `_valid_yearly_cap_value` | `NOT cap_accrued_time_yearly OR maximum_leave_yearly > 0` | You cannot have a cap on yearly accrued time without setting a maximum amount. |

---

## Model: `hr.leave.mandatory.day`

**File:** `models/hr_leave_mandatory_day.py`
**Records:** Company-wide blocked days (e.g., public holidays, company shutdown days).

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Name of the mandatory day — required |
| `company_id` | Many2one | Company — required, default current company |
| `start_date` | Date | Start of the blocked period — required |
| `end_date` | Date | End of the blocked period — required |
| `resource_calendar_id` | Many2one | Optional: only applies to employees using this calendar |
| `department_ids` | Many2many | Optional: only applies to employees in these departments |
| `job_ids` | Many2many | Optional: only applies to employees with these job titles |
| `color` | Integer | Kanban color index — random default (1–11) |

### Constraint

`start_date <= end_date`

### Usage in `hr.leave`

`has_mandatory_day` is computed by calling `employee_id._get_mandatory_days(start_date, end_date)`. The employee's method scopes mandatory days by the employee's calendar, department (with `parent_of` domain for hierarchy), and job. Non-HR users are blocked from submitting leaves covering mandatory days via `_check_validity()`.

---

## Model: `hr.employee` (Extension)

**File:** `models/hr_employee.py`
**Inherits:** `hr.employee`

### Added Fields

| Field | Type | Description |
|-------|------|-------------|
| `leave_manager_id` | Many2one | Employee's leave approver — computed from parent, overridable |
| `current_leave_id` | Many2one | Currently active leave (state `validate`) — `sudo()` access |
| `current_leave_state` | Selection | State of current leave |
| `leave_date_from` | Date | Start of current leave — stored for avatar cards |
| `leave_date_to` | Date | End of current leave (next working day after `date_to`) |
| `allocation_count` | Float | Total allocated days (current valid allocations) |
| `allocations_count` | Integer | Number of allocations |
| `show_leaves` | Boolean | Show leave-related fields in views |
| `is_absent` | Boolean | Employee is currently on approved leave |
| `allocation_display` | Char | Formatted allocation count |
| `allocation_remaining_display` | Char | Formatted remaining allocation |
| `hr_icon_display` | Selection | Extended: `presence_holiday_absent`, `presence_holiday_present` |

### Key Methods

**`_get_contextual_employee()`**
Returns the target employee for the current context. Checks in order: `context['employee_id']`, `context['default_employee_id']`, `env.user.employee_id`. This is the canonical way the system maps the current user to their employee record.

**`_get_consumed_leaves(leave_types, target_date=False, ignore_future=False)`**
The central balance engine. Returns a tuple of two dicts:

*Dict 1 — `allocations_leaves_consumed`:*
```python
{
  employee: {
    leave_type: {
      allocation: {
        'max_leaves': float,
        'leaves_taken': float,       # validated only
        'virtual_leaves_taken': float, # validated + confirm/validate1
        'remaining_leaves': float,   # max - taken
        'virtual_remaining_leaves': float,
        'accrual_bonus': float,       # future accrual from today to target_date
      }
    }
  }
}
```

*Dict 2 — `to_recheck_leaves_per_leave_type`:*
```python
{
  employee: {
    leave_type: {
      'excess_days': {date: {amount, is_virtual, leave_id}},
      'exceeding_duration': float,  # negative = over limit
      'to_recheck_leaves': hr.leave recordset,
    }
  }
}
```

The method iterates leaves in `date_from` order, distributing them across allocations. For accrual allocations, future leaves (before `target_date`) are tracked separately and not immediately deducted — they contribute to `exceeding_duration` for balance warnings instead.

**`_get_hours_per_day(date_from)`**
Returns 24 for fully flexible employees (those without a working calendar). Returns `calendar.hours_per_day` otherwise. This ensures that hour-based calculations work correctly even without a defined schedule.

**`get_time_off_dashboard_data(target_date=None)`**
Builds dashboard data: `has_accrual_allocation`, `allocation_data` (from `get_allocation_data_request()`), and `allocation_request_amount` (pending requests count).

**`get_mandatory_days(start_date, end_date)`** / **`_get_mandatory_days(start_date, end_date)`**
Returns a dict `{date_string: color}` for all mandatory days in range. Scoped by calendar, department hierarchy, and job. Used by the calendar view to render mandatory day overlays.

**`get_public_holidays_data(date_start, date_end)`**
Returns public holidays for the employee's calendar in FullCalendar format. Used by the dashboard calendar view.

### Manager Auto-Assignment

On `create()`: if `parent_id` is set, assigns `leave_manager_id` to the manager's user. On `write()`: if `parent_id` changes, propagates to `leave_manager_id`. The manager is also added to `hr_holidays.group_hr_holidays_responsible` via `_clean_leave_responsible_users()`.

### Calendar Update Propagation

When `resource_calendar_id` changes on an employee (outside of `no_leave_resource_calendar_update` context):
1. Future unvalidated leaves (`date_from > now`) have their `resource_calendar_id` updated
2. Their `date_from`/`date_to` are recomputed via `_compute_date_from_to()`
3. If any leave is `validate`d, it is re-validated (resource leave recreated)
4. If recomputation causes a balance shortfall, `ValidationError` is raised

---

## Model: `hr.version` (Extension)

**File:** `models/hr_version.py`
**Inherits:** `hr.version`

### Purpose

When an employee's working schedule changes (via a contract version with a different `resource_calendar_id`), existing leaves that span the change date must be handled. This extension:
- **Splits** leaves that overlap the schedule change into multiple leaves (one per schedule)
- **Refuses** leaves that can no longer be accommodated due to allocation insufficiency
- **Sets to draft** leaves pending approval that need re-evaluation

### Key Methods

**`create(vals_list)`**
On contract creation:
1. Find existing leaves overlapping the new contract's date range that use a different calendar
2. For leaves ending before contract start: refuse them (via `_refuse_leave()`)
3. For leaves spanning contract start: set to draft (via `_set_leave_draft()`) or split
4. Create the contract
5. Create split leaves with `_create_all_new_leave()`

**`write(vals)`**
On contract update (when calendar, dates, or period changes):
1. Find leaves overlapping the change period with a different calendar
2. Write the contract first
3. For each overlapping leave: check for calendar conflicts
4. If overlapping contracts exist: refuse the original, create split leaves
5. If no overlap: update the leave's calendar and recompute duration

**`_get_leaves(extra_domain=None)`**
Searches `hr.leave` records for employees on these contracts overlapping the contract date range. Used to find all affected leaves.

**`_check_overlapping_contract(leave)`**
Returns `False` if all overlapping contracts use the same calendar as the leave (no action needed). Otherwise returns the sorted list of overlapping `hr.version` records for splitting.

**`_populate_all_new_leave_vals_from_split_leave(...)`**
For each segment bounded by contract transitions, copies leave data with adjusted dates. The last segment gets `confirm` state; intermediate segments keep the original state.

---

## Model: `resource.calendar.leaves` (Extension)

**File:** `models/resource.py`
**Inherits:** `resource.calendar.leaves`

### Added Fields

| Field | Type | Description |
|-------|------|-------------|
| `holiday_id` | Many2one | Linked `hr.leave` record |
| `elligible_for_accrual_rate` | Boolean | Whether this leave counts toward accrual proration (default False) |

### Key Methods

**`_reevaluate_leaves(time_domain_dict)`**
Called after any write/create/unlink on global (non-employee) public holidays. Finds all `hr.leave` records overlapping the changed public holiday period and:
1. Re-computes `number_of_days` and `duration_display`
2. Transitions `validate` leaves back to `confirm` (to bypass approval for administrative changes)
3. Re-validates to recreate the resource leave
4. If re-validation fails (balance insufficient): refuses the leave
5. Posts a notification: if duration decreased (public holiday added), grants days back; if duration increased (public holiday removed), deducts from allocation

This is triggered for every global public holiday change — not per-employee calendar leaves.

**`_get_time_domain_dict()`** and **`_get_domain(time_domain_dict)`**
Helper methods that build the domain for finding affected leaves. `_get_time_domain_dict()` returns `[{company_id, date_from, date_to}]` for all global leaves. `_get_domain()` builds the `AND` domain combining all time ranges with `state not in ['refuse', 'cancel']`.

**`_prepare_public_holidays_values(vals_list)`**
In `create()`, converts datetime from user's timezone to the calendar's timezone before storing. Handles the case where a public holiday is created by a user in a different timezone than the calendar's timezone. Uses `pytz` for accurate conversion.

### Constraint

`date_from <= date_to` across all global public holidays for the same company/calendar. Raises `ValidationError` on overlap.

---

## Model: `resource.resource` (Extension)

**File:** `models/resource.py`
**Inherits:** `resource.resource`

### `_format_leave()` Override

Overrides the base method to handle `half_day` and `hour`-unit leaves. For half-day leaves, replaces the entire-day range with the half-day range (`am`: 0–12, `pm`: 12–24). For hour-unit leaves, replaces the range with the precise `request_hour_from`/`request_hour_to` window. Both call through to the parent for full-day leaves.

---

## Model: `resource.calendar` (Extension)

**File:** `models/resource.py`
**Inherits:** `resource.calendar`

| Field | Type | Description |
|-------|------|-------------|
| `associated_leaves_count` | Integer | Count of public holidays (global + calendar-specific) for this calendar |

---

## Model: `calendar.event` (Extension)

**File:** `models/calendar_event.py`
**Inherits:** `calendar.event`

**`_need_video_call()`**
Returns `False` for events linked to `hr.leave` records. This prevents video calls from being automatically created for leave meetings (since leave is an absence, not a meeting).

---

## Model: `hr.department` (Extension)

**File:** `models/hr_department.py`
**Inherits:** `hr.department`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `absence_of_today` | Integer | Employees absent today (state `validate`, today in range) |
| `leave_to_approve_count` | Integer | Pending leaves (`state = confirm`) in this department |
| `allocation_to_approve_count` | Integer | Pending allocations (`state = confirm`) in this department |

---

## Model: `hr.employee.public` (Extension)

**File:** `models/hr_employee_public.py`
**Inherits:** `hr.employee.public`

Mirrors leave-related fields from `hr.employee` using `_compute_from_employee()` pattern. Enables the public employee view to show leave status without exposing full HR data. Includes `leave_manager_id`, `leave_date_to`, `is_absent`, `show_leaves`, `allocation_display`.

---

## Model: `res.partner` (Extension)

**File:** `models/res_partner.py`
**Inherits:** `res.partner`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `leave_date_to` | Date | Computed: earliest return date across all linked users |

### `_compute_im_status()` Override

Extends base presence states with leave-aware variants:
- `online` → `leave_online`
- `away` → `leave_away`
- `busy` → `leave_busy`
- `offline` → `leave_offline`

---

## Model: `res.users` (Extension)

**File:** `models/res_users.py`
**Inherits:** `res.users`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `leave_date_to` | Date | Related from `employee_id.leave_date_to` — included in `SELF_READABLE_FIELDS` |

### Key Methods

**`_get_on_leave_ids(partner=False)`**
Raw SQL query (with `flush_model` before execution) to find all users with a validated leave covering the current moment. Joins `res_users` → `hr_leave` → `hr_leave_type` filtering for `state = 'validate'` and `time_type = 'leave'`. Returns user IDs or partner IDs. The `flush_model` call ensures ORM data is committed to the DB before the raw SQL runs.

**`_compute_display_name()` Override**
When `formatted_display_name` context is active and `leave_date_to` is set, appends "Back on [date]" to the user's display name. Example: `"John Smith ✈ --Back on Jan 15--"`

**`_clean_leave_responsible_users()`**
Compares the current set of leave managers against the `leave_manager_id` fields on all employees. Removes users who are no longer referenced as leave managers from `hr_holidays.group_hr_holidays_responsible`. Called on user creation and when `leave_manager_id` changes.

---

## Model: `mail.activity.type` (Extension)

**File:** `models/mail_activity_type.py`
**Inherits:** `mail.activity.type`

**`_get_model_info_by_xmlid()` Override**
Registers Odoo-internal XML IDs for leave-specific activity types (`hr_holidays.mail_act_leave_approval`, `hr_holidays.mail_act_leave_second_approval`, etc.) so they resolve correctly to `hr.leave` and `hr.leave.allocation` models.

---

## Model: `mail.message.subtype` (Extension)

**File:** `models/mail_message_subtype.py`
**Inherits:** `mail.message.subtype`

**Purpose:** Automatically creates department-scoped message subtypes for leave and allocation message subtypes.

**`_update_department_subtype()`**
For each leave/allocation message subtype, creates a corresponding `hr.department` subtype with `relation_field = 'department_id'`. This enables department-specific leave notifications.

**`create(vals_list)`** / **`write(vals)`**
On subtype create/write for `hr.leave` or `hr.leave.allocation`, automatically creates or updates the department-scoped variant.

---

## Wizard Models

### `hr.holidays.cancel.leave`

**File:** `wizard/hr_holidays_cancel_leave.py`
**Records:** Transient wizard for employee-initiated leave cancellation.

| Field | Type | Description |
|-------|------|-------------|
| `leave_id` | Many2one | The leave being cancelled — required |
| `reason` | Text | Optional cancellation reason |

**`action_cancel_leave()`**
Calls `leave_id._action_user_cancel(reason)` which invokes `_force_cancel()`. Posts the reason in the leave's chatter and notifies managers/HR. Returns a success notification.

### `hr.leave.generate.multi.wizard`

**File:** `wizard/hr_leave_generate_multi_wizard.py`
**Purpose:** Bulk creation of leave requests for multiple employees.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Description for all created leaves |
| `holiday_status_id` | Many2one | Leave type |
| `allocation_mode` | Selection | `employee`, `company`, `department`, `category` |
| `employee_ids` | Many2many | Target employees |
| `company_id` | Many2one | Target company |
| `department_id` | Many2one | Target department |
| `category_id` | Many2one | Target employee tag |
| `date_from` | Date | Start date — required |
| `date_to` | Date | End date — required |

**`action_generate_time_off()`**
1. Resolves target employees from `allocation_mode`
2. Converts dates to UTC using company's calendar timezone
3. Checks for conflicts: hour-unit leaves that overlap are errors; day/half-day leaves are refused or split
4. Creates leaves with `leave_fast_create=True` context (skips followers/activities)
5. Calls `_validate_leave_request()` on all created leaves
6. Returns a tree view of created leaves

### `hr.leave.allocation.generate.multi.wizard`

**File:** `wizard/hr_leave_allocation_generate_multi_wizard.py`
**Purpose:** Bulk creation of allocations for multiple employees.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Description (auto-computed from type + duration) |
| `duration` | Float | Number of days/hours to allocate |
| `holiday_status_id` | Many2one | Leave type |
| `allocation_mode` | Selection | `employee`, `company`, `department`, `category` |
| `employee_ids` | Many2many | Target employees |
| `company_id` | Many2one | Target company |
| `department_id` | Many2one | Target department |
| `category_id` | Many2one | Target employee tag |
| `allocation_type` | Selection | `regular` or `accrual` |
| `accrual_plan_id` | Many2one | Accrual plan (when `allocation_type = accrual`) |
| `date_from` | Date | Start date |
| `date_to` | Date | End date (optional) |
| `notes` | Text | Notes |

**`action_generate_allocations()`**
1. Resolves target employees
2. Converts hours to days if needed using company hours-per-day
3. Creates all allocations in `confirm` state
4. Auto-approves allocations where `validation_type` is `manager` or `both` (calls `action_approve()`)
5. If current user is an officer, also auto-approves `hr` validation types
6. Returns a tree view of created allocations

### `hr.holidays.summary.employee`

**File:** `wizard/hr_holidays_summary_employees.py`
**Purpose:** Print a summary report of employee time off.

| Field | Type | Description |
|-------|------|-------------|
| `date_from` | Date | Report start date — required, default first day of month |
| `emp` | Many2many | Target employees |
| `holiday_type` | Selection | `Approved`, `Confirmed`, `both` |

**`print_report()`**
Reads active IDs from context, resolves employees, and calls `action_report_holidayssummary` report.

### `hr.departure.wizard` (Extension)

**File:** `wizard/hr_departure_wizard.py`
**Inherits:** `hr.departure.wizard`

**`action_register_departure()`**
Extends the base employee departure handler with leave/allocation cleanup:

1. Finds leaves overlapping the departure date
2. For leaves starting before departure: truncates `date_to` to departure date, posts a message
3. For leaves starting on/after departure: cancels if validated/pending, deletes otherwise
4. For allocations: sets `date_to = departure_date` for active ones, deletes future ones

---

## Cron Jobs

| Cron ID | Model | Method | Interval | Purpose |
|---------|-------|--------|----------|---------|
| `hr_leave_allocation_cron_accrual` | `hr.leave.allocation` | `_update_accrual()` | Daily | Process pending accrual allocations |
| `hr_leave_cron_cancel_invalid` | `hr.leave` | `_cancel_invalid_leaves()` | Daily | Cancel/refuse leaves that lost allocation coverage |

---

## Web Controllers

**File:** `controllers/main.py`

Provides public HTTP routes for leave and allocation approval/refusal via email tokens (enables one-click approval from email notifications):

| Route | Purpose |
|------|---------|
| `/leave/approve` | First-level approve (token-authenticated) |
| `/leave/validate` | Second-level validate (token-authenticated) |
| `/leave/refuse` | Refuse leave (token-authenticated) |
| `/allocation/validate` | Approve allocation (token-authenticated) |
| `/allocation/refuse` | Refuse allocation (token-authenticated) |

Uses `MailController._check_token_and_record_or_redirect()` for secure token validation. Falls back to generic error page on failure.

---

## Report Models

### `report.hr_holidays.report_holidayssummary`

**File:** `report/holidays_summary_report.py`
**Purpose:** Printable 60-day leave summary report per employee, showing color-coded day cells.

Key methods:
- `_get_leaves_summary()`: Maps each of 60 days to a color based on leave type color
- `_get_leaves()`: Search for leaves in date range filtered by state (`confirm`/`validate`)
- `_get_holidays_status()`: Lists all leave types appearing in the report

### `hr.leave.report` / `hr.leave.employee.type.report` / `hr.leave.report.calendar`

**Files:** `report/hr_leave_report.py`, `report/hr_leave_employee_type_report.py`, `report/hr_leave_report_calendar.py`
**Purpose:** Standard Odoo reporting views (list, pivot, graph) for leave data.

---

## Security Model

### Groups

| Group | Name | Implies | Privilege |
|-------|------|---------|-----------|
| `base.group_user` | Employee | — | Create own leaves, see own data |
| `group_hr_holidays_responsible` | Time Off Responsible | `base.group_user` | Approve leaves for direct reports |
| `group_hr_holidays_user` | Officer | `group_hr_holidays_responsible` + `hr.group_hr_user` | Approve all leaves, manage types |
| `group_hr_holidays_manager` | Administrator | `group_hr_holidays_user` | Full access, config, unlinking |

### Record Rules (`hr_holidays_security.xml`)

**`hr.leave` rules:**

| Rule | Scope | Operations | Group |
|------|-------|-----------|-------|
| `hr_leave_rule_employee` | Own leaves (`employee_id.user_id = user`) | read | `base.group_user` |
| `hr_leave_rule_employee_update` | Own draft/confirm, or manager's reports with manager/hr validation | write (limited) | `base.group_user` |
| `hr_leave_rule_employee_unlink` | Own confirm/validate1 | unlink | `base.group_user` |
| `hr_leave_rule_responsible_read` | Employees where `leave_manager_id = user` | read | `group_hr_holidays_responsible` |
| `hr_leave_rule_responsible_update` | Own leaves (any state) or manager's leaves | write (limited) | `group_hr_holidays_responsible` |
| `hr_leave_rule_user_read` | All leaves | read | `group_hr_holidays_user` |
| `hr_leave_rule_officer_update` | Non-validated own leaves or others' leaves | write | `group_hr_holidays_user` |
| `hr_leave_rule_manager` | All leaves | all | `group_hr_holidays_manager` |
| `hr_leave_rule_multicompany` | `company_id in company_ids` | all | global |

**`hr.leave.allocation` rules:** Same pattern — employees see/manage own, managers see/manage team's, officers see all, managers see no limits.

### SQL Injection Prevention

`_get_on_leave_ids()` uses raw SQL but with parameterized queries (`%s` with tuple args) and `flush_model()` before execution. No string concatenation with user input.

### Field Group Restrictions

- `private_name`: only visible to `hr_holidays.group_hr_holidays_responsible`
- `can_approve/validate/refuse`: computed per-user from `_check_approval_update()`
- `supported_attachment_ids`: only writeable if `leave_type.support_document = True`
- `leave_date_to` on `res.users`: included in `SELF_READABLE_FIELDS`

---

## Upgrade/Migration

**File:** `upgrades/1.6/pre-migrate.py`

Updates the multi-company domain force for `hr_leave_allocation_rule_multicompany` ir_rule to include `holiday_status_id.company_id` in the domain. This was needed to properly scope allocation visibility by both the employee company and the leave type company.

---

## L4 Deep Dive

### Performance Considerations

#### `_get_durations()` Batch Optimization

`_get_durations()` is a `@api.model` static method designed for batch use. It calls `_work_intervals_batch()` once for all employees and all calendars. However, `_compute_number_of_days()` is called per-record (not batched), which means the batch optimization is only effective when called from `_get_durations()` directly. The per-record `_compute_number_of_days()` re-computes for each leave independently.

#### Accrual Cron Scalability

`_process_accrual_plans()` processes all approved accrual allocations in the while loop. For long-running allocations (years old), `nextcall` is updated in large jumps via `_get_next_date()`, preventing N iterations for each missed period. However, each iteration triggers ORM writes to `number_of_days`, and the `leaves_taken` re-computation is cached in `_get_consumed_leaves()` to avoid repeated queries.

#### `get_allocation_data()` Heavy Queries

This method is called by the Leave Dashboard and can be slow for large organizations because:
1. It searches all allocations and leaves per employee per leave type
2. For each allocation, it calls `_get_future_leaves_on()` which creates a fake allocation copy and runs `_process_accrual_plans()` up to `target_date`
3. `_get_closest_expiring_leaves_date_and_count()` calls `_process_accrual_plans()` on fake allocations for each allocation with remaining days

Mitigation: `target_date` defaults to today, reducing the accrual computation scope.

#### Compound Index for Overlap Detection

The compound index `('date_to', 'date_from')` on `hr.leave` enables index-only scans for range queries:
```sql
WHERE date_from < X AND date_to > Y  -- overlap detection
WHERE date_from <= date AND date_to >= date  -- dashboard "today" filter
WHERE date_from > now  -- future leave queries
```

#### `_get_on_leave_ids()` Raw SQL

This method runs a raw SQL query (with `flush_model` first) because the ORM cannot efficiently express the "leave covering current timestamp" condition across a join. The raw SQL is safe: it uses `%s` parameterization and only accesses known tables.

### Historical Changes: Odoo 18 to Odoo 19

| Feature | Odoo 18 | Odoo 19 |
|---------|---------|---------|
| Negative balance | Informal, no formal cap | Formalized with `allows_negative`, `max_allowed_negative` fields |
| Accrual validity | Indefinite once earned | `accrual_validity` + `accrual_validity_count` + `accrual_validity_type` per level |
| Accrual gain time | End of period only | `accrued_gain_time`: `start` or `end` |
| Yearly accrual cap | Total balance cap only | Both `cap_accrued_time` and `cap_accrued_time_yearly` per level |
| Contract integration | `hr.contract` fields | `hr.version` with proper split/refuse on schedule change |
| Public holiday re-evaluation | Basic duration recalc | Full `_reevaluate_leaves()` with notification, refuse-on-insufficient-balance |
| Carryover expiry | Not tracked | `carried_over_days_expiration_date` + `expiring_carryover_days` |
| Half-day leave | Hour-based morning/afternoon | `request_date_from_period` (`am`/`pm`) with full-day toggle |
| Work-based accrual | Via `hr_attendance` | `is_based_on_worked_time` on plan, direct in `_process_accrual_plan_level()` |
| Leave duration unit | Day only | `request_unit`: `day`, `half_day`, `hour` |
| Private leave name | Hidden field | `private_name` gated by `hr_holidays.group_hr_holidays_responsible` |
| Dual-call accrual tracking | Single `lastcall` | `lastcall` + `actual_lastcall` for precise accrual/carryover date separation |

### Edge Cases and Failure Modes

#### Contract Schedule Change: Split vs. Refuse

When a leave spans a contract schedule change:
1. If the new calendar reduces working days and exceeds available allocation: the leave is refused
2. If the new calendar increases or maintains working days: the leave is split
3. Split leaves: intermediate segments keep their original state; the final segment gets `confirm` (needs re-approval since calendar changed)
4. The check in `_check_overlapping_contract()` sorts contracts by `contract_date_start` and detects if more than one unique calendar is involved

#### Accrual Initialization with Retroactive Approval

When an accrual allocation is approved after its `date_from` has already passed:
- `lastcall` is set to `max(lastcall, first_level_start_date)` — the accrual clock starts from the later of the last call date or the first milestone
- `_process_accrual_plans()` is called immediately and catches up all missed accruals in one pass
- The `already_accrued` flag is set based on whether `number_of_days != 0` and `accrued_gain_time == 'start'`

#### Carryover with Level Transitions and `accrued_gain_time = 'start'`

When a level transition occurs and `accrued_gain_time = 'start'`:
1. The carryover policy for days accrued **before** the transition date is applied at the transition date
2. The carryover policy for days accrued **after** the transition date (but before the next accrual date) is applied at the next accrual date
3. `_get_accrual_plan_level_work_entry_prorata()` uses `planned_worked` (expected hours) rather than `worked` (actual hours) for non-hourly frequency plans with `is_based_on_worked_time = True` — this prevents penalizing employees who took leave mid-period
4. `last_executed_carryover_date` distinguishes pre- and post-transition accrual periods

#### Fully Flexible Employees

Employees without a resource calendar (fully flexible) get `hours_per_day = 24` from `_get_hours_per_day()`. This means:
- `number_of_days` for a 24-hour leave = 1 day
- Duration computations use 24 as the divisor, making any fractional day calculation exact

#### Mandatory Day Blocking

Non-HR users are blocked from creating leaves that overlap mandatory days. However, the check only fires in `_check_validity()` which is called during `write()` and `create()`, not during `action_approve()`. This means a leave can be submitted that covers a mandatory day and then be blocked at the approval stage by an HR user.

#### Hourly Leave Conflict in Batch Generation

`hr.leave.generate.multi.wizard` refuses to create batch leaves if any employee already has an **hourly-unit** leave that overlaps the batch period. This is because hourly leaves cannot be safely auto-adjusted/split. Day-unit conflicts are handled by refusing single-day overlaps and splitting multi-day overlaps.

#### Accrual Cap: Yearly vs. Total

Two independent caps exist:
- `cap_accrued_time` + `maximum_leave`: total balance cannot exceed `maximum_leave`
- `cap_accrued_time_yearly` + `maximum_leave_yearly`: total accrued in the calendar year cannot exceed `maximum_leave_yearly`

`yearly_accrued_amount` is reset to 0 at each carryover date. The yearly cap is checked per-level per-iteration in `_add_days_to_allocation()`.

#### Timezone Mismatch

When the employee's timezone differs from the approver's timezone (`tz_mismatch = True`), date/datetime conversions can cause confusion. The `_compute_tz_mismatch()` field highlights this for the approver.

### Cross-Model Integration Map

```
hr.leave.type
  (validation_type, request_unit, allows_negative, max_allowed_negative)
         │
         ▼
  ┌─────────────────┐         ┌──────────────────────┐
  │    hr.leave     │────────►│ hr.leave.allocation │
  │ (date_from/to,  │  uses   │  (accrual processing│
  │  employee_id,    │ balance │   via _process_    │
  │  number_of_days)  │         │   accrual_plans())  │
  └────────┬────────┘         └──────────┬───────────┘
           │ records leave                     │
           ▼                                  ▼
  ┌─────────────────────┐         ┌──────────────────────┐
  │resource.calendar.    │         │hr.leave.accrual.plan│
  │leaves                │         │hr.leave.accrual.    │
  │(holiday_id bridge)   │         │plan.level           │
  └──────────┬───────────┘         └──────────────────────┘
             │ bridge
             ▼
  ┌─────────────────────┐
  │  resource.resource    │
  │  (_format_leave for   │
  │   half-day/hour)     │
  └──────────────────────┘
             │
             │ overlaps contract change
             ▼
  ┌─────────────────────┐
  │     hr.version       │
  │ (_check_overlapping_  │
  │  contract → split or  │
  │  refuse leaves)       │
  └──────────────────────┘
```

### Overtime and Attendance Integration

Overtime linkage is not native to `hr_holidays`. The related feature is `is_based_on_worked_time` on accrual plans:
- When `True`, the accrual amount is prorated based on actual attendance hours
- `_get_accrual_plan_level_work_entry_prorata()` reads work data via `employee_id._get_work_days_data_batch()` and `employee_id._get_leave_days_data_batch()`
- Leaves of type `time_type = 'leave'` with `elligible_for_accrual_rate = False` are excluded from the worked-time calculation (they don't reduce accruals)
- Leaves of type `time_type = 'other'` with `elligible_for_accrual_rate = True` are added to worked time (they count as attendance)

---

## Quick Reference

### State Transitions

```
hr.leave:     confirm ──(approve)──► validate1 ──(validate)──► validate
                  │                      │
                  └──(refuse/cancel)────┴──► refuse / cancel

hr.leave.allocation:  confirm ──(approve)──► validate
```

### Key Cron Jobs

| Cron | Model | Method | Frequency |
|------|-------|--------|-----------|
| `_update_accrual` | `hr.leave.allocation` | `_process_accrual_plans()` | Daily |
| `_cancel_invalid_leaves` | `hr.leave` | `_cancel_invalid_leaves()` | Daily |

### Core Compute Methods

| Field | Model | Method |
|-------|-------|--------|
| `number_of_days` | `hr.leave` | `_compute_duration()` → `_get_durations()` |
| `resource_calendar_id` | `hr.leave` | `_compute_resource_calendar_id()` |
| `date_from` / `date_to` | `hr.leave` | `_compute_date_from_to()` |
| `virtual_remaining_leaves` | `hr.leave.type` | `_compute_leaves()` → `get_allocation_data()` |
| `is_absent` | `hr.employee` | `_compute_leave_status()` |
| `can_approve/validate/refuse` | `hr.leave` | `_compute_can_approve/validate/refuse()` |

### File Locations

| Purpose | Path |
|---------|------|
| Main leave model | `models/hr_leave.py` |
| Leave type model | `models/hr_leave_type.py` |
| Allocation model | `models/hr_leave_allocation.py` |
| Accrual plan model | `models/hr_leave_accrual_plan.py` |
| Accrual level model | `models/hr_leave_accrual_plan_level.py` |
| Mandatory day model | `models/hr_leave_mandatory_day.py` |
| Employee extension | `models/hr_employee.py` |
| Version (contract change) | `models/hr_version.py` |
| Resource calendar bridge | `models/resource.py` |
| Department extension | `models/hr_department.py` |
| Employee public extension | `models/hr_employee_public.py` |
| Partner extension | `models/res_partner.py` |
| User extension | `models/res_users.py` |
| Mail activity type extension | `models/mail_activity_type.py` |
| Mail message subtype extension | `models/mail_message_subtype.py` |
| Calendar event extension | `models/calendar_event.py` |
| Wizard: cancel leave | `wizard/hr_holidays_cancel_leave.py` |
| Wizard: batch leaves | `wizard/hr_leave_generate_multi_wizard.py` |
| Wizard: batch allocations | `wizard/hr_leave_allocation_generate_multi_wizard.py` |
| Wizard: summary report | `wizard/hr_holidays_summary_employees.py` |
| Wizard: departure | `wizard/hr_departure_wizard.py` |
| Controllers | `controllers/main.py` |
| Report: summary | `report/holidays_summary_report.py` |
| Report: leave | `report/hr_leave_report.py` |
| Report: employee type | `report/hr_leave_employee_type_report.py` |
| Report: calendar | `report/hr_leave_report_calendar.py` |
| Security rules | `security/hr_holidays_security.xml` |
| Cron jobs | `data/ir_cron_data.xml` |
| Upgrade migration | `upgrades/1.6/pre-migrate.py` |
| Views | `views/hr_leave_views.xml`, `views/hr_leave_type_views.xml`, etc. |

---
## Related Modules



- [Modules/hr](Modules/HR.md) — Employee base model, `hr.version`
- [Modules/calendar](Modules/calendar.md) — Meeting integration
- [Modules/resource](Modules/resource.md) — Working time calendars, `resource.calendar.leaves`
- [Modules/hr_attendance](Modules/hr_attendance.md) — Attendance tracking (used by accrual proration)
- [Modules/hr_holidays_attendance](Modules/hr_holidays_attendance.md) — Integrates attendance with leave
- [Modules/hr_work_entry](Modules/hr_work_entry.md) — Work entries (conflicts with leaves)
- [Modules/HR](Modules/HR.md) — Contracts (related to `hr.version`)
