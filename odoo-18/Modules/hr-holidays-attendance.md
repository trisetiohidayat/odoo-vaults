---
Module: hr_holidays_attendance
Version: Odoo 18
Type: Integration
Tags: #hr, #attendance, #leaves, #overtime, #integration
---

# hr_holidays_attendance — Leave & Attendance Integration

## Overview

**Module:** `hr_holidays_attendance`
**Category:** Human Resources / Attendance
**Depends:** `hr_attendance`, `hr_holidays`
**Auto-installs:** Yes (`auto_install: True`)
**License:** LGPL-3
**Canonical path:** `~/odoo/odoo18/odoo/addons/hr_holidays_attendance/`

`hr_holidays_attendance` bridges `hr_holidays` and `hr_attendance`, enabling two-way integration:

1. **Attendance ← Leaves:** Approved leaves cause the attendance system's overtime calculations to exclude leave days (employees are not expected to badge in). The `_get_overtime_leave_domain()` is extended to include time-off days as non-working.
2. **Leaves ← Overtime:** Certain leave types can be **deducted from overtime balance** rather than from a traditional allocation. Employees with accumulated extra hours can convert those hours into leave.
3. **Accrual precision:** Hourly accrual plans can optionally source worked hours from actual **attendance records** rather than the calendar schedule, providing more accurate leave accrual for flex-time employees.

---

## Model Map

| Extended Model | File | Key Addition |
|---|---|---|
| `hr.leave` | `hr_leave.py` | `overtime_id`, `employee_overtime`, `overtime_deductible`; overtime deduction on approve/refuse |
| `hr.leave.allocation` | `hr_leave_allocation.py` | `overtime_id`, `overtime_deductible`; overtime deduction on create/write |
| `hr.leave.type` | `hr_leave_type.py` | `overtime_deductible` boolean; display name shows hours available |
| `hr.attendance` | `hr_attendance.py` | `_get_overtime_leave_domain()` override |
| `hr.leave.accrual.level` | `hr_leave_accrual_plan_level.py` | `frequency_hourly_source` (calendar vs. attendance) |
| `res.users` | `res_users.py` | `request_overtime` computed boolean |

---

## `hr.leave.type` — EXTENDED

Inherited from `hr.leave.type`. Controls whether a leave type draws from overtime balance.

### Fields

| Field | Type | Notes |
|---|---|---|
| `overtime_deductible` | `Boolean` | Default `False`. If `True`, leaves of this type deduct from the employee's `hr.attendance.overtime` balance instead of a regular allocation. Only makes sense when `requires_allocation == 'no'`. |

### Display Name Override

When displaying leave types in an employee's portal or time-off request wizard, if the current employee has a positive `total_overtime` balance and the leave type has `overtime_deductible == True` and `requires_allocation == 'no'`, the type's display name is suffixed with the available overtime count:

```
"Unpaid Leave (4.00 hours available)"
```

This is computed in `_compute_display_name()` — an override of the parent method. It requires the `request_type` context to be `'leave'` (not `'allocation'`).

### `get_allocation_data()`

Returns allocation data for all employees. For leave types where `overtime_deductible == True` and `requires_allocation == 'no'`, it **replaces `virtual_remaining_leaves`** with the employee's `total_overtime` balance. This means the overtime pool is shown as the "available balance" for that leave type in the time-off dashboard.

---

## `hr.leave` — EXTENDED

Inherited from `hr.leave`. See also: [Modules/HR Holidays](Modules/HR-Holidays.md).

### Fields

| Field | Type | Notes |
|---|---|---|
| `overtime_id` | `Many2one(hr.attendance.overtime)` | Links this leave to a specific overtime record (created when the leave is created/approved). |
| `employee_overtime` | `Float` (related) | Related to `employee_id.total_overtime`. Readable by `base.group_user`. |
| `overtime_deductible` | `Boolean` (computed) | `holiday_status_id.overtime_deductible` AND `requires_allocation == 'no'`. Controls whether the leave interacts with overtime. |

### Overtime Deduction Lifecycle

#### On create: `_check_overtime_deductible()` (called from `create()`)

```
If overtime_deductible == True AND no overtime_id yet:
  1. Check: number_of_hours <= employee.total_overtime
     → raises ValidationError if insufficient balance
  2. Create hr.attendance.overtime record:
     employee_id: self.employee_id
     date: leave.date_from
     adjustment: True
     duration: -1 * number_of_hours
```

This creates a **negative overtime adjustment** at leave creation time, immediately reducing the available overtime balance.

#### On approve: `action_approve()`

Re-runs `_check_overtime_deductible()` as a guard — ensures the employee still has enough overtime balance when approval happens (balance may have changed since the request was made).

#### On validate ( `_validate_leave_request()`):

Calls `self._update_leaves_overtime()` which notifies `hr.attendance` to recalculate overtime for the leave's date range.

#### On refuse: `action_refuse()`

Unlinks the `overtime_id` record, reversing the balance deduction.

#### On write: Overtime balance guard

```python
def write(self, vals):
    ...
    for leave in self.sudo().filtered('overtime_id'):
        if vals.get('state') == 'refuse':
            continue  # let action_refuse handle it
        employee = leave.employee_id
        duration = leave.number_of_hours
        overtime_duration = leave.overtime_id.sudo().duration
        if overtime_duration != -1 * duration:
            if duration > employee.total_overtime - overtime_duration:
                raise ValidationError(_('Not enough extra hours to extend this leave.'))
            leave.overtime_id.sudo().duration = -1 * duration
```

When a leave with `overtime_id` is extended or shortened, the overtime record's `duration` is updated to match. The guard checks that the new total does not exceed available balance.

#### On unlink: `_force_cancel()`

Unlinks the `overtime_id` before deleting the leave record.

#### On reset to draft: `action_reset_confirm()`

Re-runs `_check_overtime_deductible()` — if overtime balance was consumed elsewhere since approval, this will block the reset.

### `_update_leaves_overtime()`

```python
def _update_leaves_overtime(self):
    employee_dates = defaultdict(set)
    for leave in self:
        if leave.employee_id:
            for d in range((leave.date_to - leave.date_from).days + 1):
                employee_dates[leave.employee_id].add(
                    self.env['hr.attendance']._get_day_start_and_day(
                        leave.employee_id,
                        leave.date_from + timedelta(days=d)
                    )
                )
    if employee_dates:
        self.env['hr.attendance'].sudo()._update_overtime(employee_dates)
```

Collects all `(day_start_utc, local_date)` tuples for every day covered by each leave, grouped by employee, then calls `hr.attendance._update_overtime()` to recompute overtime for those days. This ensures that overtime calculations **exclude leave days** (since approved leave = expected absence).

---

## `hr.leave.allocation` — EXTENDED

Inherited from `hr.leave.allocation`. Supports overtime-deductible allocations (e.g., manager grants extra leave drawn from overtime).

### Fields

| Field | Type | Notes |
|---|---|---|
| `overtime_deductible` | `Boolean` (computed) | Mirrors `holiday_status_id.overtime_deductible`. |
| `overtime_id` | `Many2one(hr.attendance.overtime)` | Created when the allocation is made. Deleted if allocation is refused. Groups: `hr_holidays_user` only. |
| `employee_overtime` | `Float` (related) | Related to `employee_id.total_overtime`. |

### Default_get — `deduct_extra_hours` context

```python
def default_get(self, fields):
    res = super().default_get(fields)
    if 'holiday_status_id' in fields and self.env.context.get('deduct_extra_hours'):
        domain = [('overtime_deductible', '=', True), ('requires_allocation', '=', 'yes')]
        if self.env.context.get('deduct_extra_hours_employee_request', False):
            domain = expression.AND([domain, [('employee_requests', '=', 'yes')]])
        leave_type = self.env['hr.leave.type'].search(domain, limit=1)
        res['holiday_status_id'] = leave_type.id
    return res
```

When created with context `deduct_extra_hours=True`, pre-selects the overtime-deductible leave type (one with `requires_allocation='yes'`). The `deduct_extra_hours_employee_request` context variant further restricts to types where `employee_requests=True`.

### Overtime Deduction on create

```python
def create(self, vals_list):
    res = super().create(vals_list)
    for allocation in res:
        if allocation.overtime_deductible:
            duration = allocation.number_of_hours_display
            if duration > allocation.employee_id.total_overtime:
                raise ValidationError(...)
            if not allocation.overtime_id:
                allocation.sudo().overtime_id = self.env['hr.attendance.overtime'].sudo().create({
                    'employee_id': allocation.employee_id.id,
                    'date': allocation.date_from,
                    'adjustment': True,
                    'duration': -1 * duration,
                })
    return res
```

Unlike `hr.leave` (which deducts on create), the allocation creates an overtime record only if one doesn't already exist. This prevents duplicate deductions if the allocation is modified.

### Overtime Deduction on write

When `number_of_days` changes, the `overtime_id.duration` is updated to match the new duration, with the same balance guard as `hr.leave`.

### `_get_accrual_plan_level_work_entry_prorata()`

Overrides the parent method in `hr.leave.allocation`. Used when computing leave accruals from **attendance-based hourly accrual plans**.

```python
def _get_accrual_plan_level_work_entry_prorata(self, level, start_period, start_date, end_period, end_date):
    if level.frequency != 'hourly' or level.frequency_hourly_source != 'attendance':
        return super()._get_accrual_plan_level_work_entry_prorata(...)
    datetime_min_time = datetime.min.time()
    start_dt = datetime.combine(start_date, datetime_min_time)
    end_dt = datetime.combine(end_date, datetime_min_time)
    attendances = self.env['hr.attendance'].sudo().search([
        ('employee_id', '=', self.employee_id.id),
        ('check_in', '>=', start_dt),
        ('check_out', '<=', end_dt),
    ])
    work_entry_prorata = sum(attendances.mapped('worked_hours'))
    return work_entry_prorata
```

If the accrual level uses `frequency='hourly'` with `frequency_hourly_source='attendance'`, the prorated accrual is computed from actual attendance records within the period (sum of `worked_hours`), rather than from the calendar schedule. This provides **true attendance-based accrual** for flex-time workers.

---

## `hr.attendance` — EXTENDED

Inherited from `hr.attendance`. See also: [Modules/HR Attendance](Modules/HR-Attendance.md).

### Overridden Method: `_get_overtime_leave_domain()`

```python
def _get_overtime_leave_domain(self):
    domain = super()._get_overtime_leave_domain()
    # resource_id = False => Public holidays
    return AND([domain, ['|',
        ('holiday_id.holiday_status_id.time_type', '=', 'leave'),
        ('resource_id', '=', False)
    ]])
```

Base `hr_attendance` returns `[]` (include all resource leaves). This extension ANDs an additional domain that explicitly includes:
- `('holiday_id.holiday_status_id.time_type', '=', 'leave')` — approved leave records with `time_type='leave'`
- `('resource_id', '=', False)` — public holidays (where `resource_id` is False)

This is the mechanism by which **approved time-off days are excluded from overtime calculations** — the overtime computation treats these days as expected non-working time.

---

## `hr.leave.accrual.level` — EXTENDED

Inherited from `hr.leave.accrual.level`. Controls where hourly accrual amounts are sourced from.

### Fields

| Field | Type | Notes |
|---|---|---|
| `frequency_hourly_source` | `Selection([('calendar', 'Calendar'), ('attendance', 'Attendances')])` | Default `'calendar'`. `store=True, compute=True, readonly=False`. |

### Compute: `_compute_frequency_hourly_source()`

```python
@api.depends('accrued_gain_time')
def _compute_frequency_hourly_source(self):
    for level in self:
        if level.accrued_gain_time == 'start':
            level.frequency_hourly_source = 'calendar'
```

When `accrued_gain_time == 'start'`, the source is forced to `'calendar'`. Otherwise, the user can choose between `calendar` and `attendance`. This field controls whether the **hourly accrual amount** is calculated from the employee's working schedule (`calendar`) or from actual badge-in records (`attendance`).

---

## `res.users` — EXTENDED

### Fields

| Field | Type | Notes |
|---|---|---|
| `request_overtime` | `Boolean` (computed) | `True` if the user can request overtime-deductible leave. |

### Compute: `_compute_request_overtime()`

```python
@api.depends_context('uid')
@api.depends('total_overtime')
def _compute_request_overtime(self):
    is_holiday_user = self.env.user.has_group('hr_holidays.group_hr_holidays_user')
    time_off_types = self.env['hr.leave.type'].search_count([
        ('requires_allocation', '=', 'yes'),
        ('employee_requests', '=', 'yes'),
        ('overtime_deductible', '=', True)
    ])
    for user in self:
        if user.total_overtime >= 1:
            if is_holiday_user:
                user.request_overtime = True
            else:
                user.request_overtime = time_off_types
        else:
            user.request_overtime = False
```

Logic:
- If user has `>= 1 hour` of overtime balance AND is a holiday officer → always `True`.
- If user has `>= 1 hour` of overtime balance AND is a regular user → `True` only if at least one overtime-deductible leave type allows employee requests.
- If overtime balance `< 1 hour` → always `False`.

This drives the UI visibility of the "Request time off from extra hours" button in the time-off app.

---

## L4: How Overtime Calculations Work with Leaves

### The Two Integration Paths

#### Path 1: Leave Days Excluded from Overtime (No Allocation Required)

When a leave is approved, `hr.leave._update_leaves_overtime()` fires `hr.attendance._update_overtime()` for every day in the leave range. The attendance system then:

1. Looks up expected work intervals from `resource.calendar` via `_employee_attendance_intervals()`.
2. Compares actual badge-in records against expected intervals.
3. Since the leave day is registered as a resource leave with `time_type='leave'`, the expected work intervals for that day are cleared.
4. Result: No overtime is computed for a day when the employee was on approved leave — they are not expected to badge in.

#### Path 2: Leave Deducted from Overtime Balance (Deductible Leave Types)

When a leave type has `overtime_deductible = True` and `requires_allocation = 'no'`:

1. **Request time:** Employee requests leave. On `create()`, a negative `hr.attendance.overtime` record is atomically created with `adjustment=True`, reducing the employee's `total_overtime` balance immediately.
2. **Approval:** `action_approve()` re-validates the balance is still sufficient.
3. **Refusal:** `action_refuse()` deletes the negative overtime record, restoring the balance.
4. **Extension/Reduction:** `write()` updates the overtime record's `duration` to match the new leave duration.

This allows employees to **"pay" for time off with overtime hours** without needing a formal allocation. Common in knowledge-worker flex policies.

### Accrual Plan Precision: Calendar vs. Attendance Source

For **hourly frequency accrual plans** (`frequency='hourly'`):
- `frequency_hourly_source='calendar'` (default): accrual amount is based on the employee's working schedule from `resource.calendar.attendance`. E.g., 8h/day schedule → 40h/week → prorated hourly accrual.
- `frequency_hourly_source='attendance'`: accrual amount uses actual badge-in records. Only actual worked hours count toward future leave accrual.

The attendance-based source is ideal for truly flexible employees whose hours vary week-to-week.

### Data Flow Diagram

```
Employee requests overtime-deductible leave
    → create() → _check_overtime_deductible()
        → Creates hr.attendance.overtime (adjustment=True, duration=-hours)
            → employee.total_overtime decreases

Leave approved
    → action_approve() → _check_overtime_deductible() [balance recheck]
    → _validate_leave_request() → _update_leaves_overtime()
        → hr.attendance._update_overtime() for each leave day
            → leave days excluded from overtime calculation

Leave refused
    → action_refuse() → overtime_id.unlink()
        → employee.total_overtime restored

Public holiday / Approved leave
    → hr.attendance._get_overtime_leave_domain()
        → includes ('holiday_id.holiday_status_id.time_type', '=', 'leave')
        → excludes these days from overtime computation
```
