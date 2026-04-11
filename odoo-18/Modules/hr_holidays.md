# Odoo 18 - hr_holidays Module

## Overview

Time off management module. Handles leave requests, allocations, accrual plans, and validation workflows. Manages the complete lifecycle of employee time off from request through approval.

## Source Path

`~/odoo/odoo18/odoo/addons/hr_holidays/`

## Key Models

### hr.leave (`hr.leave`)

Central time off request model. Inherits `mail.thread.main.attachment` and `mail.activity.mixin`.

**Key Fields:**
- `employee_id` (`hr.employee`): The employee taking leave. Defaults to current user. Domain filters to active employees in allowed companies; non-officers only see themselves or employees they manage.
- `holiday_status_id` (`hr.leave.type`): Leave type. Domain filters by company and requires valid allocation if `requires_allocation == 'yes'`.
- `state`: Selection: `confirm` (To Approve), `refuse` (Refused), `validate1` (Second Approval), `validate` (Approved), `cancel` (Cancelled). Default: `confirm`.
- `date_from` / `date_to`: Computed from `request_date_from/to`, `request_hour_from/to`, `request_unit_half`, `request_unit_hours`, and employee timezone.
- `number_of_days` / `number_of_hours`: Duration computed from resource calendar (work intervals minus public holidays).
- `request_date_from` / `request_date_to`: Interface dates for day-based requests.
- `request_hour_from` / `request_hour_to`: Interface hours for hour-based requests.
- `request_unit_half`: Boolean — half day request.
- `request_unit_hours`: Boolean — custom hours request.
- `resource_calendar_id`: Employee's calendar or company fallback, computed per leave.
- `manager_id`: Computed from `employee_id.parent_id`.
- `first_approver_id`: Set when first validation level completes.
- `second_approver_id`: Set when second validation completes (double validation).
- `private_name`: The actual leave description. Gated by `hr_holidays.group_hr_holidays_user`. Non-officers see `'*****'` in the `name` field.
- `name`: Computed — shows `private_name` to officers/managers, `'*****'` to others.
- `meeting_id`: Linked `calendar.event` created on validation.
- `can_reset` / `can_approve` / `can_cancel`: Computed booleans for UI buttons.
- `has_mandatory_day`: Boolean — leave overlaps a mandatory day.
- `is_hatched` / `is_striked`: UI styling for refused/aborted leaves.
- `leave_type_request_unit`: Related from `holiday_status_id.request_unit`.
- `color`: Related from `holiday_status_id.color`.

**Computed Fields:**
- `_compute_description()`: If officer, manager, or own leave — show `private_name`. Otherwise show `'*****'`.
- `_compute_date_from_to()`: Converts `request_date_from/to` + hours to UTC `Datetime` using employee's timezone.
- `_compute_resource_calendar_id()`: Batch-resolved per employee per date.
- `_compute_request_unit_half/hours()`: Automatically cleared based on leave type request unit.
- `_compute_from_employee_id()`: Syncs `manager_id`, clears `holiday_status_id` if no valid allocation.
- `_compute_department_id()`: From `employee_id.department_id`.
- `_compute_duration()`: Stores `number_of_days` and `number_of_hours` from `_get_durations()`.
- `_compute_duration_display()`: Human-readable duration string.
- `_compute_last_several_days()`: `True` if request spans multiple days.
- `_compute_is_hatched()`: `True` if state is `refuse` or `cancel`.
- `_compute_has_mandatory_day()`: Checks against `hr.employee._get_mandatory_days()`.
- `_compute_tz_mismatch` / `_compute_tz()`: Timezone handling.
- `_compute_can_reset` / `_compute_can_approve` / `_compute_can_cancel()`: Role-based button visibility.

**Key Methods:**
- `_get_durations()`: Core duration calculation — uses `employee._list_work_time_per_day()` and `_get_work_days_data_batch()`. Handles flexible employees (same-day leave = real duration), public holidays, and mandatory days.
- `_get_hour_from_to()`: Determines start/end hours from calendar attendance for a day period (AM/PM/full day).
- `_to_utc()`: Converts local date+time to UTC using employee's timezone.
- `_split_leaves()`: Splits a leave request across public holidays (creates sub-leaves per day).
- `_check_validity()`: Validates no overlap with existing approved leaves and allocation coverage.

**Workflow Actions:**
- `action_approve()`: Routes to `action_validate1` (for `both` validation) or directly calls `action_validate`.
- `action_validate1()`: First-level approval — sets `first_approver_id`, transitions to `validate1` state.
- `action_validate()`: Final approval — sets `second_approver_id`, state → `validate`. Creates `resource.calendar.leaves` and optionally `calendar.event`.
- `action_refuse()`: Refuses leave — state → `refuse`. Unlinks meetings. Notifies manager.
- `action_confirm()`: Resets to `confirm` (employee can re-submit after refuse).
- `action_draft()`: Admin-only reset to draft.

**SQL Constraints:**
- `date_check2`: `date_from <= date_to`
- `date_check3`: `request_date_from <= request_date_to`
- `duration_check`: `number_of_days >= 0`

**Access Control (L3):**
- Officers (`group_hr_holidays_user`): Full read. Can approve HR and manager single-validation leaves from their managed employees.
- Managers: Can approve leaves for their subordinates.
- Employees: Can see own leaves. `name` is hidden for others' leaves.

---

### hr.leave.type (`hr.leave.type`)

Leave type configuration.

**Key Fields:**
- `name`: Type name (translated).
- `leave_validation_type`: `no_validation` / `hr` / `manager` / `both`.
- `requires_allocation`: `yes` (needs allocation) / `no` (unlimited).
- `request_unit`: `day` / `half_day` / `hour`.
- `allocation_validation_type`: For allocation requests.
- `employee_requests`: `yes` / `no` — can employees request allocations?
- `unpaid`: Is leave unpaid.
- `include_public_holidays_in_duration`: Count public holidays in duration.
- `create_calendar_meeting`: Create calendar event on approval.
- `color`, `icon_id`: Display styling.
- `max_leaves` / `leaves_taken` / `virtual_remaining_leaves`: Employee-contextual computed fields (read_group over allocations).
- `has_valid_allocation`: Boolean computed — valid allocation exists for current employee.
- `accruals_ids`: Linked `hr.leave.accrual.plan` records.
- `allows_negative` / `max_allowed_negative`: Negative balance cap.
- `responsible_ids`: M2M to `res.users` for notifications.

**Key Method:**
- `get_allocation_data(employees, target_date)`: Returns complex dict per employee per leave type with remaining_leaves, virtual_remaining_leaves, max_leaves, accrual_bonus, leaves_taken, virtual_leaves_taken, leaves_requested, leaves_approved, closest_allocation_remaining, closest_allocation_expire, holds_changes, etc.
- `_get_closest_expiring_leaves_date_and_count()`: Finds the nearest allocation expiration date and total expiring leaves count.

**SQL Constraint:**
- `check_negative`: Cannot have `max_allowed_negative <= 0` if `allows_negative = True`.

---

### hr.leave.allocation (`hr.leave.allocation`)

Grant of leave days to an employee.

**Key Fields:**
- `employee_id` / `holiday_status_id` / `date_from` / `date_to`: Core fields.
- `number_of_days`: Days granted.
- `allocation_type`: `regular` / `accrual` / `carry_forward` / `lost`.
- `holiday_type`: `employee` / `category` / `department` / `all`.
- `state`: `confirm` → `validate` (or `cancel`).
- `max_leaves`: Total allocation (virtual remaining = max - taken).
- `leaves_taken`: Consumed days.

**Key Constraints:**
- `_check_dates()`: `date_from < date_to`
- `_validate_accrual_levels()`: Accrual plan levels must be valid.

---

### hr.leave.accrual.plan (`hr.leave.accrual.plan`)

Accrual plan configuration.

**Key Fields:**
- `time_off_type_id`: Associated leave type.
- `level_ids`: One2many to `hr.leave.accrual.plan.level`.
- `transition_mode`: `immediately` / `end_of_accrual` — when unused days are applied.
- `carryover_date`: `year_start` / `allocation` / `other` — when carryover resets.
- `carryover_bonus`: Days added from previous year balance.
- `is_based_on_worked_time`: Accrual rate based on work days vs calendar days.
- `max_gained_days`: Maximum days that can be accrued in total.
- `year_start_date`: Custom accrual year start.

---

### hr.leave.accrual.plan.level (`hr.leave.accrual.plan.level`)

Accrual level within a plan.

**Key Fields:**
- `plan_id` / `sequence`
- `start_count` / `start_type`: When accrual starts (e.g., `start_count=1`, `start_type='month'` → starts on month 1).
- `frequency`: `hourly` / `daily` / `weekly` / `bimonthly` / `monthly` / `biyearly` / `yearly`.
- `interval`: Every N frequency periods.
- `accrued_time`: Days/hours gained per period.
- `cap_accrued_time`: Maximum balance from this level.
- `maximum_leave`: Total balance cap.
- `action_with_unused_accruals`: `lost` / `all` / `maximum` — carryover policy.
- `postpone_max_days`: Days kept when carryover expires.
- `is_accrued_when_worked`: Based on worked time rather than calendar time.

**Key Method:**
- `_get_next_date(basis_date, employee_id)`: Computes next accrual date per frequency. Complex date arithmetic for each frequency type.

**SQL Constraints:**
- Monthly with day > 28: Warning only (last day of month).
- Bimonthly: Day must be 1-15.
- Yearly: Day must be 1-31.
- Weekly: Dayofweek 0-6.
- Start count/type validated per frequency.

## Cross-Model Relationships

| Model | Field | Purpose |
|-------|-------|---------|
| `hr.leave` | `employee_id` | Leave requestor |
| `hr.leave` | `holiday_status_id` | Leave type configuration |
| `hr.leave` | `meeting_id` | Calendar event on approval |
| `hr.leave` | `first_approver_id` / `second_approver_id` | Approval chain |
| `hr.leave` | `resource_calendar_id` | Work schedule for duration |
| `hr.leave.allocation` | `holiday_status_id` | Allocation grant |
| `hr.leave.allocation` | `employee_id` / `holiday_type` | Allocation target |
| `hr.leave.accrual.plan` | `time_off_type_id` | Plan linked to type |
| `hr.leave.accrual.plan.level` | `plan_id` | Level within plan |

## Edge Cases & Failure Modes

1. **Double validation**: When `leave_validation_type = 'both'`, `action_approve()` calls `action_validate1()` first, then `action_validate()` completes the second step.
2. **Half day on multi-day leave**: Setting half day on multi-day range auto-corrects `request_date_to = request_date_from`.
3. **Flexible employee duration**: Single-day leave for fully flexible employee uses real intervals (not calendar), ignoring public holidays.
4. **No allocation for limited type**: `holiday_status_id` domain automatically excludes types with no valid allocation when `requires_allocation == 'yes'`.
5. **Negative balance**: If `allows_negative = True`, requests can exceed allocation up to `max_allowed_negative`.
6. **Accrual carryover expiry**: `_get_closest_expiring_leaves_date_and_count()` accounts for both allocation expiry and carryover expiry.
7. **Description hiding**: `private_name` is always stored; `name` is masked to `'*****'` via `_compute_description()` for non-authorized viewers.

## Security Groups

- `hr_holidays.group_hr_holidays_user`: Time off officer — full read, can approve/refuse leaves.
- `hr_holidays.group_hr_holidays_manager`: Department manager — approve own team's leaves.

## Workflow

```
Employee creates leave
        ↓
[confirm] ──→ HR/Officer approves
                     ↓
          (if 'both' validation)
                     ↓
            [validate1] ──→ Second approver
                              ↓
                         [validate]
                              ↓
                    Creates calendar event
                    + resource.calendar.leaves

Any state:
  [refuse] ←─ HR/Officer refuses
  [cancel] ←─ Employee cancels
  [draft]  ←─ Admin resets
```

## Integration Points

- **hr**: Uses `hr.employee`, `hr.department`, `resource.mixin`.
- **resource**: Duration computed via `resource.calendar` work intervals.
- **calendar**: `calendar.event` created on leave approval.
- **mail**: Threading, activity mixins, followers.