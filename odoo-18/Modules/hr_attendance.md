# Odoo 18 - hr_attendance Module

## Overview

Employee attendance tracking module. Records check-in/check-out timestamps, computes worked hours and overtime, and supports kiosk, systray, and manual entry modes.

## Source Path

`~/odoo/odoo18/odoo/addons/hr_attendance/`

## Key Model

### hr.attendance (`hr.attendance`)

Individual attendance record. Inherits `mail.thread`.

**Key Fields:**
- `employee_id` (`hr.employee`): Required. Defaults to current user. Group-expanded via `_read_group_employee_id()`.
- `check_in`: Datetime, required. Check-in timestamp.
- `check_out`: Datetime (nullable). Check-out timestamp.
- `worked_hours`: Float, computed from `check_in`/`check_out` via `_compute_worked_hours()`. Stored.
- `expected_hours`: Float, computed as `worked_hours - overtime_hours`. Stored.
- `overtime_hours`: Float, computed via `_compute_overtime_hours()`. Stores percentage of worked hours that count as overtime.
- `overtime_status`: Selection: `to_approve` / `approved` / `refused`. Default from company setting.
- `validated_overtime_hours`: Float, copy of `overtime_hours` when status is `to_approve` or `approved`, else 0.
- `no_validated_overtime_hours`: Boolean — `True` if `validated_overtime_hours` is zero.
- `color`: Integer — computed for kanban display (red for abnormal, 0 for normal).
- `department_id` / `manager_id`: Related from `employee_id`.
- `in_latitude` / `in_longitude`: Check-in GPS coordinates.
- `out_latitude` / `out_longitude`: Check-out GPS coordinates.
- `in_country_name` / `out_country_name`: Country derived from IP.
- `in_city` / `out_city`: City derived from IP.
- `in_ip_address` / `out_ip_address`: Device IP address.
- `in_browser` / `out_browser`: Browser info.
- `in_mode`: Check-in mode: `kiosk` / `systray` / `manual` / `technical` / `auto_check_out`.
- `out_mode`: Same as `in_mode` plus `auto_check_out`.

**Computed Fields:**
- `_compute_worked_hours()`: Uses `resource.models.utils.Intervals` — subtracts lunch intervals for non-flexible employees. Converts to timezone of employee calendar.
- `_compute_overtime_hours()`: Complex SQL query joins `hr.attendance` with `hr.attendance.overtime` on the same day. Distributes overtime reservoir across attendances.
- `_compute_validated_overtime_hours()`: If `company.attendance_overtime_validation == 'no_validation'` → equals `overtime_hours`. If `overtime_status == 'to_approve'` → equals `overtime_hours`. If `refused` → 0.
- `_compute_no_validated_overtime_hours()`: `float_compare(validated_overtime_hours, 0.0, precision_digits=5) == 0`.
- `_compute_overtime_status()`: Default `approved` if company setting `by_manager` else `to_approve` (requires manager approval).
- `_compute_color()`: Red (1) if worked_hours > 16 or out_mode == 'technical' or check_in > 1 day ago. Orange (10) if still open and checked in > 1 day ago. White (0) otherwise.
- `_compute_display_name()`: Format: `"From <check_in>"` if no check_out; `"<worked_hours> (<check_in>-<check_out>)"` if checked out.

## Key Methods

### `_check_validity()`

SQL constraint enforcement via `@api.constrains`:
1. `check_out >= check_in` — raises `ValidationError`.
2. No overlapping records for same employee:
   - Latest attendance with `check_in <= self.check_in` must not have `check_out > self.check_in`.
   - No other open attendance (no `check_out`) for same employee.
   - Latest attendance with `check_in < self.check_out` must be the same as the pre-check-in record.

### `_update_overtime(employee_attendance_dates)`

Updates `hr.attendance.overtime` records for affected employees:

1. Groups attendances by employee + local date.
2. For each day, determines:
   - **No working hours in calendar**: All worked hours = overtime.
   - **Has working hours**: `overtime = worked_hours - planned_work_duration`. Pre/post-work overtime counted if > threshold.
3. Creates new `hr.attendance.overtime` records, updates existing, or deletes if zero.
4. Schedules recomputation of `overtime_hours`, `validated_overtime_hours`, `expected_hours`.

**Thresholds:**
- `company_threshold`: Tolerance before overtime starts (from company setting, in minutes).
- `employee_threshold`: Tolerance for early check-in.

**Fully flexible employees:** No overtime computed (`is_fully_flexible` → skip).

**Unfinished shifts:** Overtime not counted if any shift is still open.

### `_get_pre_post_work_time(employee, working_times, attendance_date)`

Computes pre-work, work duration, and post-work time for a specific day:
1. Gets planned start/end from `working_times[attendance_date]`.
2. For each attendance, adjusts check_in/out within threshold to treated as on-time.
3. Pre-work: time before planned start.
4. Work duration: overlap with planned hours, minus lunch (for non-flexible).
5. Post-work: time after planned end.

### `_get_attendances_dates()`

Returns dict `{employee_id: set((day_start_utc, local_date))}`. Used before and after write/unlink to merge date sets for overtime recomputation.

## Key Actions

- `action_in_attendance_maps()`: Opens Google Maps for check-in location.
- `action_out_attendance_maps()`: Opens Google Maps for check-out location.
- `action_approve_overtime()`: Sets `overtime_status = 'approved'`.
- `action_refuse_overtime()`: Sets `overtime_status = 'refused'`.
- `action_try_kiosk()`: Opens kiosk mode (requires `group_hr_attendance_manager`).

## Cron Jobs

### `_cron_auto_check_out()`

Runs daily. Finds open attendances where:
- `check_out = False`
- `employee_id.company_id.auto_check_out = True`
- Employee calendar is NOT flexible (`flexible_hours = False`)

Logic: Uses previous day average worked hours + current check-in time + tolerance vs scheduled work hours for the day. Auto-sets `check_out` and `out_mode = 'auto_check_out'`. Posts a message on the attendance.

### `_cron_absence_detection()`

Runs daily. For companies with `absence_management = True`:
1. Finds employees who have no overtime record (no check-in) for yesterday.
2. Creates `technical` attendance records (1 second apart) for absent employees.
3. Posts notification message on technical attendance.
4. Deletes technical attendances with zero overtime (fully absent with no calendar expectation).

Purpose: Creates negative overtime records for unjustified absences.

## Cross-Model Relationships

| Model | Field | Purpose |
|-------|-------|---------|
| `hr.attendance` | `employee_id` | Attendance owner |
| `hr.attendance.overtime` | `employee_id` / `date` | Daily overtime tracking |
| `hr.employee` | `resource_calendar_id` | Work schedule for expected hours |
| `hr.employee` | `is_fully_flexible` | Skip overtime computation |
| `res.company` | `attendance_overtime_validation` | Overtime auto-approval |
| `res.company` | `overtime_company_threshold` | Pre-work overtime tolerance (minutes) |
| `res.company` | `overtime_employee_threshold` | Late check-in tolerance (minutes) |

## Edge Cases & Failure Modes

1. **Open attendance on create**: `_check_validity()` raises if employee already has an open attendance.
2. **Overlapping attendances**: Raises if new check-in overlaps with previous attendance's check-out window.
3. **Negative overtime**: If overtime reservoir is negative (e.g., overtime threshold exceeded), `overtime_hours` becomes negative. UI shows this as "negative overtime" indicator.
4. **Overtime distribution across sessions**: If employee has multiple check-in/check-out sessions in a day, the overtime duration is distributed proportionally across each session.
5. **Timezone handling**: All dates converted to employee's local timezone via `employee._get_tz()`. `check_in` stored in UTC but computed in local time for display and overtime calculation.
6. **Technical attendance for absence**: Creates very short attendance (1 second apart) to register the absence as negative overtime. Deleted if no actual worked hours were expected.
7. **Auto check-out**: Tolerance is computed as `previously_worked_hours + (current_time - check_in) - max_tolerance < scheduled_hours`. Excess hours are subtracted from check-out time to keep total hours = scheduled + tolerance.
8. **Manual mode override**: If `out_mode == 'technical'`, setting a check_out changes mode to `manual`. Similarly for check_in if `in_mode == 'technical'`.
9. **No payroll in overtime computation**: Only calendar hours used — no wage/rate information. Pure time tracking.

## Security Groups

- `hr_attendance.group_hr_attendance_manager`: Full access. Can approve/refuse overtime, access kiosk mode.
- `hr_attendance.group_hr_attendance_officer`: Can edit others' attendances.
- `hr_attendance.group_attendance`: Basic attendance access.

## Integration Points

- **hr**: Uses `hr.employee`, `hr.department`. Employee's calendar determines expected hours.
- **resource**: `Intervals` utility for worked hours computation. `_employee_attendance_intervals()` for lunch interval detection.
- **hr_contract**: Contract's `resource_calendar_id` may differ from employee's calendar (`calendar_mismatch` field in contract).
- **payroll**: Overtime data used for payroll processing (via `hr.attendance.overtime` model).

## Source Files

- `hr_attendance/models/hr_attendance.py` — Main model.
- `hr_attendance/models/hr_attendance_overtime.py` — Overtime tracking.