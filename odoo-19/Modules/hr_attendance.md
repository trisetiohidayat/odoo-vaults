---
type: module
module: hr_attendance
tags: [odoo, odoo19, hr, attendance, time-tracking, overtime, geofencing, biometric]
created: 2026-04-06
updated: 2026-04-11
l4: true
---

# Attendance Tracking (`hr_attendance`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Attendances |
| **Technical** | `hr_attendance` |
| **Category** | Human Resources/Attendances |
| **Version** | 2.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description

Manages employee attendance through check-in/check-out actions. Keeps account of the attendances of the employees on the basis of the actions performed by them. Supports kiosk mode, systray, mobile geofencing, biometric/barcode scanning, and configurable overtime calculation with approval workflows.

## Dependencies

| Module | Reason |
|--------|--------|
| `hr` | Base employee model |
| `barcodes` | Barcode/RFID scanner integration for kiosk |
| `base_geolocalize` | GPS reverse-geocoding for mobile/location tracking |

## Architecture

### Entry Points (4 Modes)

| Mode | Context | Entry Method |
|------|---------|--------------|
| `kiosk` | Physical terminal (badge scanner, manual select) | `/hr_attendance/<token>` — public kiosk URL |
| `systray` | Web client notification area | `HrAttendanceController.systray_attendance()` |
| `manual` | Direct create/write on `hr.attendance` | Standard ORM |
| `technical` | Cron jobs, absence detection, auto-check-out | `_cron_auto_check_out`, `_cron_absence_detection` |

All modes capture device metadata: GPS coordinates, IP address, browser, and a mode label.

---

## Security Groups

| Group | ID | Access Level |
|-------|----|-------------|
| Own Reader | `group_hr_attendance_own_reader` | Read own attendance (implied by `base.group_user`) |
| Officer | `group_hr_attendance_officer` | Read/write attendances for managed employees |
| User | `group_hr_attendance_user` | Full access all employees (implied Officer) |
| Manager | `group_hr_attendance_manager` | Admin — full CRUD on overtime rulesets + attendance |
| Attendances (Privilege) | `res_groups_privilege_attendances` | Attached to User and Manager groups |

### Record Rules (`hr.attendance`)

| Rule | Who | Domain | CRUD |
|------|-----|--------|------|
| Multi-company | `global` | `employee_id.company_id in company_ids` | — |
| Admin | `group_hr_attendance_user` | `(1,=,1)` | CRWUD |
| Officer | `group_hr_attendance_officer` | `employee_id.attendance_manager_id = user.id` OR `employee_id.user_id = user.id` | CRWUD |
| Own reader | `group_hr_attendance_own_reader` | `employee_id.user_id = user.id` | R |

### Record Rules (`hr.attendance.overtime.ruleset`)

| Rule | Who | Domain | CRUD |
|------|-----|--------|------|
| Default | global | `company_id in company_ids or False` | R |
| Manager | `group_hr_attendance_manager` | `company_id in company_ids or False` | CRUD |

---

## Cron Jobs

| Cron | Model | Interval | Purpose |
|------|-------|----------|---------|
| Auto Check-Out | `hr.attendance` | Every 4 hours | Closes open attendance records when employee exceeds scheduled work hours + tolerance |
| Absence Detection | `hr.attendance` | Every 4 hours | Creates 1-second technical attendance records for employees absent from work on working days (triggers negative overtime when `absence_management` is enabled) |

---

## Key Models

| Model | File | Purpose |
|-------|------|---------|
| `hr.attendance` | `models/hr_attendance.py` | Individual check-in/check-out records |
| `hr.attendance.overtime.line` | `models/hr_attendance_overtime.py` | Overtime interval entries linked to attendance |
| `hr.attendance.overtime.rule` | `models/hr_attendance_overtime_rule.py` | Rule defining when/how overtime is calculated |
| `hr.attendance.overtime.ruleset` | `models/hr_attendance_overtime_ruleset.py` | Collection of rules, scoped to company/country |
| `hr.employee` (extended) | `models/hr_employee.py` | Attendance fields, state, computed hours |
| `hr.version` (extended) | `models/hr_version.py` | `ruleset_id` per-employee version tracking |
| `res.company` (extended) | `models/res_company.py` | Attendance configuration |
| `ir.http` (extended) | `models/ir_http.py` | Session info injection for systray |
| `res.users` (extended) | `models/res_users.py` | Officer group cleanup on manager reassignment |
| `hr.employee.public` (extended) | `models/hr_employee_public.py` | Public-facing attendance fields |

---

## `hr.attendance`

**File:** `models/hr_attendance.py`
**Inherits:** `mail.thread` (enables chatter/messaging on attendance records)

### Field Reference

| Field | Type | Default | Store | Notes |
|-------|------|---------|-------|-------|
| `employee_id` | Many2one `hr.employee` | `_default_employee` (current user's employee) | Yes | Required. `group_expand` on `_read_group_employee_id` for gantt/list view filtering |
| `department_id` | Many2one `hr.department` | Related | Yes | Auto-populated from `employee_id.department_id` |
| `manager_id` | Many2one `hr.employee` | Related | Yes | `employee_id.parent_id` |
| `attendance_manager_id` | Many2one `res.users` | Related | Yes | `employee_id.attendance_manager_id` |
| `is_manager` | Boolean | Compute | No | `group_hr_attendance_user` OR (`group_hr_attendance_officer` AND user is this record's attendance_manager) |
| `check_in` | Datetime | `fields.Datetime.now()` | Yes | Required. Indexed. `tracking=True` |
| `check_out` | Datetime | `False` | Yes | `tracking=True` |
| `date` | Date | Compute | Yes | Precomputed. Extracted from `check_in` in employee's timezone. Indexed. This is the authoritative day for overtime grouping |
| `worked_hours` | Float | Compute | Yes | Excludes lunch breaks (via `_get_employee_calendar` + resource intervals). `readonly=True` |
| `color` | Integer | Compute | No | `1` if `worked_hours > 16` or `out_mode == 'technical'`; `10` if open and check_in < yesterday |
| `overtime_hours` | Float | Compute | Yes | Sum of `linked_overtime_ids.mapped('manual_duration')` |
| `overtime_status` | Selection | Compute | Yes | `to_approve` if any OT pending; `approved` if all approved; `refused` if all refused; `False` if no OT lines |
| `validated_overtime_hours` | Float | Compute | Yes | Sum of `linked_overtime_ids` with `status == 'approved'` |
| `expected_hours` | Float | Compute | Yes | `worked_hours - overtime_hours` (regular hours) |
| `in_latitude` | Float `(10,7)` | — | Yes | GPS latitude at check-in. `readonly=True` |
| `in_longitude` | Float `(10,7)` | — | Yes | GPS longitude at check-in |
| `in_location` | Char | — | Yes | Reverse-geocoded location string (from GPS or IP) |
| `in_ip_address` | Char | — | Yes | Source IP of check-in request |
| `in_browser` | Char | — | Yes | `request.httprequest.user_agent.browser` at check-in |
| `in_mode` | Selection | `'manual'` | Yes | `kiosk`, `systray`, `manual`, `technical` |
| `out_latitude` | Float `(10,7)` | — | Yes | GPS latitude at check-out |
| `out_longitude` | Float `(10,7)` | — | Yes | GPS longitude at check-out |
| `out_location` | Char | — | Yes | Reverse-geocoded location string at check-out |
| `out_ip_address` | Char | — | Yes | Source IP of check-out request |
| `out_browser` | Char | — | Yes | Browser at check-out |
| `out_mode` | Selection | `'manual'` | Yes | `kiosk`, `systray`, `manual`, `technical`, `auto_check_out` |
| `device_tracking_enabled` | Boolean | Related | No | `employee_id.company_id.attendance_device_tracking` |
| `linked_overtime_ids` | Many2many | Compute | No | Overtime lines whose `time_start` matches this record's `check_in` |

### Computed Fields — Implementation Notes

#### `_compute_date`
- Converts `check_in` (naive UTC) to employee's timezone via `employee_id._get_tz()`.
- Handles precompute edge cases where `employee_id` is not yet set (returns `datetime.today()`).
- **Why store:** Used as indexed filter for overtime recalculation domain queries.

#### `_compute_worked_hours`
- Uses `_get_worked_hours_in_range(check_in, check_out)` internally.
- For non-flexible employees: subtracts lunch intervals from `resource.calendar`.
- For flexible employees: raw difference between check_in and check_out.
- **Edge case:** If `check_out` is in the future, `worked_hours` recomputes continuously until checkout.

#### `_compute_linked_overtime_ids`
- Overtime lines are matched by `(employee_id, time_start)` tuple — `time_start` equals `check_in`.
- This is the inverse relationship from `hr.attendance.overtime.line._linked_attendances()`.
- **Performance note:** Uses `_linked_overtimes()` which queries `hr.attendance.overtime.line` by `time_start IN check_ins`. If many records are written in batch, the query can be large.

### Key Methods

#### `_attendance_action_change(geo_information=None)` — on `hr.employee`
See `hr.employee` section. Creates or closes `hr.attendance` records.

#### `_get_worked_hours_in_range(start_dt, end_dt)`
- Uses `Intervals` from `odoo.tools.intervals` to compute the intersection of attendance time with the requested range, excluding lunch.
- Lunch exclusion only applies when `resource._is_flexible() == False`.
- Returns `sum_intervals()` of the resulting interval set.
- **Returns** float (hours) or `0.0` if `end_dt < start_dt`.

#### `_update_overtime(attendance_domain=None)`
- **Triggered on:** `create`, `write` (when `check_in/check_out/employee_id` changes), `unlink`.
- **Phase 1:** Delete all `hr.attendance.overtime.line` records matching the domain (covers week before check_in through week after check_out to handle cross-day/cross-week overtime rules).
- **Phase 2:** Search all closed attendances in the domain + current records.
- **Phase 3:** Group by `ruleset_id` (via employee's `hr.version.ruleset_id`).
- **Phase 4:** Call `rule_ids._generate_overtime_vals_v2()` for each ruleset group.
- **Phase 5:** Batch-create new overtime lines.
- **Phase 6:** Trigger recompute of `overtime_hours`, `validated_overtime_hours`, `overtime_status` via `add_to_compute`.
- **Overswrite protection:** Searches for existing open attendance before writing check_out. Raises `UserError` if no open attendance found — prevents orphan check-outs.

#### `_check_validity()` — Constrains
- No overlapping check_in times for the same employee.
- At most one open attendance (no `check_out`) per employee at any time.
- The latest attendance with check_in before our check_out must be the same record (no gaps in attendance chain).
- All checks use `search([...], order='check_in desc', limit=1)` — **O(n) per record** on large datasets.

#### `_cron_auto_check_out()`
- Only processes employees with `resource_calendar_id.flexible_hours = False` and `company.auto_check_out = True`.
- Uses `pytz` to interpret check_in in the employee's timezone.
- Computes `expected_worked_hours` from the calendar's `dayofweek`-based attendance lines (respects two-week calendars via `week_type`).
- Handles multiple sessions per day (morning + afternoon) via `mapped_previous_duration`.
- `out_mode` set to `'auto_check_out'`.
- Tolerance: `company.auto_check_out_tolerance` (default 2 hours).
- Posts a message to the attendance record chatter on auto-checkout.

#### `_cron_absence_detection()`
- Only runs when `absence_management = True` on company.
- Target: employees with a signed contract (`current_version_id.contract_date_start <= yesterday`) who have **no** overtime line for yesterday.
- Creates 1-second `in_mode='technical'` attendance records. These trigger negative overtime under quantity rules (because the attendance is 1 second of work but the employee's expected hours are 7-8 hours, resulting in `worked_hours - expected_hours < -employee_tolerance`).
- Records with zero overtime contribution are silently deleted.
- Posts a chatter message on records that contribute overtime.

#### `_get_overtimes_to_update_domain()`
- Returns a `Domain` covering all employees and their attendances from 1 week before the earliest check_in through 1 week after the latest check_out.
- This over-computes the domain deliberately to capture weekly overtime rule changes when a single day's attendance is modified.
- Returns `Domain.FALSE` if called on an empty recordset.

#### `_read_group_employee_id(resources, domain)`
- Enables group expand in the gantt/list views.
- Restricts visible employees based on: `company_id in allowed_company_ids` AND (user has `group_hr_attendance_user` OR `attendance_manager_id = user.id`).
- For non-manager users doing name searches, intersects user-domain with employee-domain.

#### `_get_attendance_by_periods_by_employee()`
- Returns `{'day': defaultdict, 'week': defaultdict}`.
- `day` key: date of the localized check_in/check_out.
- `week` key: Sunday of the week (ISO week).
- Used by quantity-based overtime rules to bucket attendance intervals by period.
- Handles attendance spans crossing midnight by splitting into per-day intervals.

#### `_get_localized_times()`
- Converts UTC `check_in`/`check_out` to the employee's timezone (from their version's schedule).
- Returns naive datetimes (tzinfo stripped) for interval arithmetic.
- **L4 Note:** Uses `employee_id.sudo()._get_version(self.check_in.date())` — version lookup by date.

---

## `hr.attendance.overtime.line`

**File:** `models/hr_attendance_overtime.py`
**Rec_name:** `employee_id`
**Order:** `time_start asc`

### Field Reference

| Field | Type | Default | Store | Notes |
|-------|------|---------|-------|-------|
| `employee_id` | Many2one `hr.employee` | Required | Yes | `ondelete='cascade'`. Indexed. |
| `company_id` | Many2one | Related | Yes | `employee_id.company_id` |
| `date` | Date | Required | Yes | Day overtime applies. Indexed. Must match attendance's `date` field |
| `status` | Selection | Compute | Yes | Default `approved` if `company.attendance_overtime_validation == 'no_validation'`; else `to_approve` |
| `duration` | Float | `0.0` | Yes | Raw overtime hours from rule computation |
| `manual_duration` | Float | Compute | Yes | Mirror of `duration`. The TODO comment indicates intent to rename to `real_duration` |
| `time_start` | Datetime | — | Yes | Must equal an `hr.attendance.check_in` — this is the link key |
| `time_stop` | Datetime | — | Yes | Must equal an `hr.attendance.check_out` |
| `amount_rate` | Float | `1.0` | Yes | Overtime pay rate (e.g., 1.5 for 150%). Combined from multiple rules via `ruleset.rate_combination_mode` |
| `is_manager` | Boolean | Compute | No | `group_hr_attendance_manager` OR (`group_hr_attendance_officer` AND `employee_id.attendance_manager_id == user`) |
| `rule_ids` | Many2many `hr.attendance.overtime.rule` | — | Yes | Rules that contributed to this overtime line |

### Constraints

```
CHECK(time_stop > time_start)  — "Starting time should be before end time"
```

The commented-out PostgreSQL GIST exclusion constraint for preventing overlapping overtime would use `tsrange(time_start, time_stop, '()')` but was not enabled.

### Key Methods

#### `_compute_status()`
- If `attendance_overtime_validation == 'by_manager'`: defaults to `to_approve`.
- Otherwise: defaults to `approved` immediately (auto-approved).

#### `_compute_is_manager()`
- Checks `group_hr_attendance_manager` first.
- Falls back to `group_hr_attendance_officer` only if the current user is the `attendance_manager_id` of the overtime's employee.
- **Security note:** Officers can only manage overtime for their own assigned employees.

#### `write(vals)`
- If `status` or `manual_duration` is changed, triggers recompute of the linked attendance's `overtime_status` and `validated_overtime_hours`.
- Uses `self.env.add_to_compute()` — lazy recompute, not immediate.

#### `_linked_attendances()`
- Searches for `hr.attendance` records where `check_in IN self.mapped('time_start')` AND `employee_id IN self.employee_id.ids`.
- This is the inverse of `hr.attendance.linked_overtime_ids`.

---

## `hr.attendance.overtime.rule`

**File:** `models/hr_attendance_overtime_rule.py`

### Field Reference

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | Required | Rule display name |
| `description` | Html | — | Rule documentation |
| `base_off` | Selection | Required, `'quantity'` | `quantity` = excess hours threshold; `timing` = specific time windows |
| `timing_type` | Selection | `'work_days'` | Only for `base_off='timing'`: `work_days`, `non_work_days`, `leave`, `schedule` |
| `timing_start` | Float | `0` | Start hour (0-24). Constraint: `0 <= timing_start < 24` |
| `timing_stop` | Float | `24` | End hour (0-24). Constraint: `0 < timing_stop <= 24`. Value `24` is treated as `datetime.max.time()` |
| `expected_hours_from_contract` | Boolean | `True` | When `True`, reads expected hours from employee's `resource.calendar` instead of fixed `expected_hours` |
| `resource_calendar_id` | Many2one `resource.calendar` | — | Domain: `flexible_hours = False`. Required when `timing_type == 'schedule'` |
| `expected_hours` | Float | — | Required when `base_off='quantity'` and `expected_hours_from_contract=False` |
| `quantity_period` | Selection | `'day'` | `day` or `week`. Required when `base_off='quantity'` |
| `sequence` | Integer | `10` | Processing order for rate combination |
| `ruleset_id` | Many2one `hr.attendance.overtime.ruleset` | Required | Index. Parent ruleset |
| `company_id` | Many2one | Related | `ruleset_id.company_id` |
| `paid` | Boolean | — | If `True`, rule contributes to `amount_rate` calculation |
| `amount_rate` | Float | `1.0` | Overtime multiplier (e.g., 1.5 for time-and-a-half) |
| `employee_tolerance` | Float | — | Hours below this undertime are ignored (used in absence management for negative overtime) |
| `employer_tolerance` | Float | — | Hours below this overtime are ignored (minimum OT threshold) |
| `information_display` | Char | Compute | Human-readable summary of the rule |

### Constraints

| Constraint | Description |
|------------|-------------|
| `_timing_start_is_hour` | `0 <= timing_start < 24` |
| `_timing_stop_is_hour` | `0 < timing_stop <= 24` |
| `@api.constrains('base_off', 'expected_hours', 'quantity_period')` | Quantity rules must specify `expected_hours` (or use contract) and `quantity_period` |
| `@api.constrains('base_off', 'timing_type', 'resource_calendar_id')` | Schedule timing rules must specify a resource calendar |

### Key Methods

#### Quantity-Based Overtime (`_get_all_overtime_undertime_intervals_for_quantity_rule`)
- Batches attendances by period (`day` or `week`).
- For each day/period: computes `expected_duration` from contract schedule OR fixed `expected_hours`.
- Computes `overtime_amount = sum_intervals(attendance_intervals) - expected_duration`.
- If `absence_management` enabled and `overtime_amount < -employee_tolerance`: returns negative overtime (undertime) instead of positive.
- Distributes overtime backwards from the last attendance of the period (most recent work absorbs overtime first).
- **Performance:** Attendances sorted by `check_in asc`, intervals processed in order.

#### Timing-Based Overtime (`_get_all_overtime_intervals_for_timing_rule`)
- `work_days`: overtime only on days that are working days per company calendar.
- `non_work_days`: overtime on weekends/holidays.
- `schedule`: overtime for time outside a specific `resource_calendar_id` schedule.
- `leave`: overtime while employee has approved time off (untested per code comment).
- Tolerance filtering: intervals shorter than `employer_tolerance` are dropped.

#### `_get_rules_intervals_by_timing_type(min_check_in, max_check_out, employees, schedules_intervals_by_employee)`
- Pre-computes work-day and non-work-day intervals for all employees over the date range.
- For `schedule` type: queries `resource_calendar_id._attendance_intervals_batch()` with 1-day buffer on each end to avoid timezone shift issues.
- Returns a dict of `timing_type -> intervals_by_employee`.

#### `_generate_overtime_vals_v2(min_check_in, max_check_out, attendances, schedules_intervals_by_employee)`
- Main entry point for overtime line creation.
- Splits overtime by day (using employee timezone to determine date boundaries).
- Aggregates overlapping intervals from multiple rules per day.
- Handles undertime: creates overtime lines with negative `duration` for absence detection.

#### `_extra_overtime_vals()`
- If no rules are `paid`, returns `{'amount_rate': 0.0}` (overtime not payable).
- If `rate_combination_mode == 'max'`: returns the highest `amount_rate` among paid rules.
- If `rate_combination_mode == 'sum'`: sums the *extra* above 100% (e.g., 150% + 120% = 170%).
- Uses `sequence` as a tiebreaker for equal rates.

#### `_compute_information_display()`
- For `quantity` rules: shows `"8h / day"` or `"From Employee"` (contract).
- For `timing` rules: shows timing type or `"Outside Schedule: <calendar_name>"`.

---

## `hr.attendance.overtime.ruleset`

**File:** `models/hr_attendance_overtime_ruleset.py`

### Field Reference

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | Required | |
| `description` | Html | — | |
| `rule_ids` | One2many | — | `hr.attendance.overtime.rule` records in this ruleset |
| `company_id` | Many2one `res.company` | `self.env.company` | |
| `country_id` | Many2one `res.country` | `company.country_id` | |
| `rate_combination_mode` | Selection | `'max'` | `'max'`: highest rate wins. `'sum'`: sum extra above 100% |
| `rules_count` | Integer | Compute | Count of `rule_ids` |
| `active` | Boolean | `True` | |

### Rate Combination Mode — Worked Example

Given rules with `paid=True`:
- Rule A: `amount_rate = 1.5` (weekend 150%)
- Rule B: `amount_rate = 1.2` (evening 120%)

| Mode | Result |
|------|--------|
| `max` | `1.5` (highest wins) |
| `sum` | `1.0 (baseline) + 0.5 + 0.2 = 1.7` (70% extra total) |

### Key Methods

#### `_attendances_to_regenerate_for()`
- Finds all `hr.version` records pointing to this ruleset.
- Returns all attendances for those employees from the earliest version date onwards.
- Used when ruleset rules are modified to recompute all affected overtime.

#### `action_regenerate_overtimes()`
- Button action that calls `_attendances_to_regenerate_for()._update_overtime()`.
- Batch-recomputes overtime for all employees governed by this ruleset.

---

## `hr.employee` (Extended)

**File:** `models/hr_employee.py`
**Inherits:** `hr.employee` (standard employee model)

### Field Reference

| Field | Type | Default | Store | Groups | Notes |
|-------|------|---------|-------|--------|-------|
| `attendance_manager_id` | Many2one `res.users` | — | Yes | `group_hr_attendance_officer` | User who can manage this employee's attendance |
| `attendance_ids` | One2many `hr.attendance` | — | — | `group_hr_attendance_officer` | All attendance records |
| `last_attendance_id` | Many2one `hr.attendance` | Compute | Yes | `group_hr_attendance_officer` | Most recent attendance |
| `last_check_in` | Datetime | Related | Yes | `group_hr_attendance_officer` | `last_attendance_id.check_in` |
| `last_check_out` | Datetime | Related | Yes | `group_hr_attendance_officer` | `last_attendance_id.check_out` |
| `attendance_state` | Selection | Compute | No | `group_hr_attendance_officer` | `'checked_out'` or `'checked_in'` |
| `hours_last_month` | Float | Compute | No | `hr.group_hr_user` | |
| `hours_last_month_overtime` | Float | Compute | No | `hr.group_hr_user` | |
| `hours_today` | Float | Compute | No | `group_hr_attendance_officer` | |
| `hours_previously_today` | Float | Compute | No | `group_hr_attendance_officer` | Hours before the current open attendance |
| `last_attendance_worked_hours` | Float | Compute | No | `group_hr_attendance_officer` | Hours of the most recent (potentially open) attendance |
| `hours_last_month_display` | Char | Compute | No | `hr.group_hr_user` | `"%g"`-formatted string |
| `overtime_ids` | One2many | — | — | `group_hr_attendance_officer` | |
| `total_overtime` | Float | Compute | No | `hr.group_hr_user` | Sum of approved overtime |
| `display_extra_hours` | Boolean | Related | No | — | `company_id.hr_attendance_display_overtime` |
| `ruleset_id` | Many2one | Related | No | `hr.group_hr_manager` | `version_id.ruleset_id` — inherited from version, writable by managers |

### Key Methods

#### `_attendance_action_change(geo_information=None)`
- **Check-in path:** Creates `hr.attendance` with all geo_information fields merged in as `in_*` fields.
- **Check-out path:** Searches for the open attendance `check_out == False` for this employee. Writes `check_out` and all `out_*` geo fields. Raises `UserError` if no open attendance found.
- Returns the `hr.attendance` record (new or modified).
- **L4 Note:** This is the core write path. Geo_information is a dict with keys like `latitude`, `longitude`, `location`, etc. The `in_`/`out_` prefix is applied dynamically.

#### `_compute_hours_today()`
- Queries all attendances where `check_in <= now` AND (`check_out >= day_start` OR `check_out == False`).
- Handles multi-session days by summing `delta` per attendance.
- `hours_previously_today` excludes the current (potentially open) attendance.
- `last_attendance_worked_hours` = hours of the last attendance (whether open or closed).
- **Timezone handling:** `day_start` computed in employee's local timezone (UTC conversion applied).

#### `_compute_hours_last_month()`
- Computes from day 1 of current month to now in employee's timezone.
- Filters: `check_in >= start_naive AND check_out <= end_naive` (only closed attendances).
- **L4 Note:** `hours_last_month_display` uses `"%g"` format (significant figures, not trailing zeros).

#### `_compute_total_overtime()`
- Uses `_read_group` with `groupby=['employee_id']` and `aggregates=['manual_duration:sum']`.
- Filter: `status == 'approved'`.
- Runs with `compute_sudo=True` (bypasses record rules for aggregate computation).
- **Performance:** Single aggregate query for all employees.

#### `_get_schedules_by_employee_by_work_type(start, stop, version_periods_by_employee)`
- Batches employees by `resource_calendar_id`.
- Fetches work attendance intervals, leave intervals, and lunch intervals per calendar.
- Strips timezone info from all intervals for naive UTC arithmetic.
- Returns structured dict with `leave`, `schedule` (work + lunch), and `fully_flexible` keys.
- **Why store `resource.calendar` locally:** Prevents repeated lookups during overtime computation.

#### `action_open_last_month_attendances()`
- Opens a read-only list view filtered to this employee for the current month.
- Sets `display_extra_hours` in context for column visibility.

#### `open_barcode_scanner()`
- Action that triggers `employee_barcode_scanner` client action.
- Loads the barcode scanner component from the `barcodes` module.

#### `_compute_presence_state()`
- Extends the `hr_presence` module's presence computation.
- Priority order: login state > attendance state > schedule-based working hours.
- If employee is checked in: `hr_presence_state = 'present'`.
- If checked out but within scheduled working hours: `hr_presence_state = 'absent'` (calls `_get_employee_working_now()`).
- Otherwise: falls through to schedule-based state.

### `create(vals_list)` / `write(vals)` — Officer Group Management

When `attendance_manager_id` is set/changed:
- **`create`:** Adds the new manager to `group_hr_attendance_officer` group if not already a member.
- **`write`:** Adds new manager to group. Calls `old_officers._clean_attendance_officers()` on removal.
- **`_clean_attendance_officers` (on `res.users`):** Removes users from the officer group if they are no longer anyone's attendance manager. Prevents accumulating group memberships.

---

## `hr.version` (Extended)

**File:** `models/hr_version.py`
**Inherits:** `hr.version` (base version model)

### Added Fields

| Field | Type | Notes |
|-------|------|-------|
| `ruleset_id` | Many2one `hr.attendance.overtime.ruleset` | Domain: current company's countries. Default: `hr_attendance_default_ruleset` (from XML). `tracking=True` |

### `_domain_current_countries()`
- Returns: `['|', ('country_id', '=', False), ('country_id', 'in', self.env.companies.country_id.ids)]`
- Rulesets without a country (`country_id = False`) are available globally as defaults.
- **L4 Note:** This enables per-country overtime rule sets while keeping a universal fallback.

### `_get_versions_by_employee_and_date(employee_dates)`
- Builds a 2-level dict: `employee -> date -> hr.version`.
- Searches `hr.version` records where `date_version <= max(date)` (no upper bound since end date is not stored).
- Uses binary search (`version_index`) to find the applicable version for each date.
- **Performance:** Single search call, then Python-side binary search — avoids N queries per employee.

---

## `res.company` (Extended)

**File:** `models/res_company.py`

### Company-Level Attendance Settings

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `overtime_company_threshold` | Integer | `0` | **Deprecated — TODO: Remove in master** |
| `overtime_employee_threshold` | Integer | `0` | **Deprecated — TODO: Remove in master** |
| `hr_attendance_display_overtime` | Boolean | `False` | Show extra hours in employee form |
| `attendance_kiosk_mode` | Selection | `'barcode_manual'` | `barcode`, `barcode_manual`, `manual` |
| `attendance_barcode_source` | Selection | `'front'` | `scanner`, `front`, `back` (camera) |
| `attendance_kiosk_delay` | Integer | `10` | Seconds before returning to menu after check-in |
| `attendance_kiosk_key` | Char | UUID hex | Access token for kiosk URL. Initialized per-column in `_init_column` |
| `attendance_kiosk_url` | Char | Compute | `/hr_attendance/<kiosk_key>` |
| `attendance_kiosk_use_pin` | Boolean | `False` | Require employee PIN for kiosk check-in |
| `attendance_from_systray` | Boolean | `False` | Enable web client systray check-in |
| `attendance_overtime_validation` | Selection | `'no_validation'` | `'no_validation'` (auto-approve) or `'by_manager'` |
| `auto_check_out` | Boolean | `False` | Auto-close open attendance records |
| `auto_check_out_tolerance` | Float | `2` | Hours of tolerance before auto-checkout |
| `absence_management` | Boolean | `False` | Create technical attendance for absences |
| `attendance_device_tracking` | Boolean | `False` | Collect GPS/IP/browser on check-in/out |

### `_init_column(column_name)`
- Overridden specifically for `attendance_kiosk_key` to generate unique UUIDs per company using `cr.execute_values` (batch SQL UPDATE).
- Without this override, the default `BaseModel._init_column` would assign the same UUID to all companies.

### `write(vals)` — Overtime Recomputation
- When `overtime_company_threshold` or `overtime_employee_threshold` changes, triggers `_update_overtime()` for all affected attendances.
- Uses `Domain` for efficient domain construction.

---

## `ir.http` (Extended)

**File:** `models/ir_http.py`

### `lazy_session_info()`
- Injects `attendance_user_data` into the session info returned to the web client.
- Calls `HrAttendance._get_user_attendance_data(employee)` — static method.
- Only injected if `self.env.user.employee_id` exists.

---

## Model Relationships

```
hr.version
  |-- ruleset_id --> hr.attendance.overtime.ruleset

hr.employee
  |-- version_id --> hr.version
  |-- ruleset_id (via version) --> hr.attendance.overtime.ruleset
  |-- attendance_ids (1->N) --> hr.attendance
  |-- last_attendance_id (N->1) --> hr.attendance
  |-- overtime_ids (1->N) --> hr.attendance.overtime.line
  |-- attendance_manager_id --> res.users

hr.attendance
  |-- employee_id --> hr.employee
  |-- linked_overtime_ids (M2M) --> hr.attendance.overtime.line
  |-- (via overtime lines) --> hr.attendance.overtime.rule

hr.attendance.overtime.ruleset
  |-- rule_ids (1->N) --> hr.attendance.overtime.rule

hr.attendance.overtime.rule
  |-- ruleset_id --> hr.attendance.overtime.ruleset
  |-- linked via M2M --> hr.attendance.overtime.line

hr.attendance.overtime.line
  |-- employee_id --> hr.employee
  |-- time_start = hr.attendance.check_in (link key)
  |-- time_stop = hr.attendance.check_out
```

---

## State Flow

```
Employee opens web client / kiosk:
  --> systray_attendance() or scan_barcode() or manual_selection()
  --> employee._attendance_action_change(geo_information)
  --> hr.attendance created (check_in=now, check_out=False)
  --> employee.attendance_state = 'checked_in'
  --> hr.attendance.overtime_status = False (no OT lines yet)

Employee checks out:
  --> employee._attendance_action_change()
  --> hr.attendance.check_out = now (open attendance found and closed)
  --> hr.attendance.write({'out_mode': ...})
  --> _update_overtime() called
  --> hr.attendance.overtime.line records created
  --> employee.attendance_state = 'checked_out'

Overtime Line created:
  --> status = 'to_approve' (if by_manager validation) OR 'approved'
  --> hr.attendance.overtime_hours computed (sum of linked lines)
  --> hr.attendance.overtime_status computed (approved/refused/to_approve)
  --> hr.attendance.validated_overtime_hours = sum(approved lines)

Manager approves overtime:
  --> hr.attendance.overtime.line.action_approve()
  --> status = 'approved'
  --> hr.attendance.overtime_status recomputed
  --> hr.attendance.validated_overtime_hours recomputed
  --> employee.total_overtime recomputed via _read_group
```

---

## Overtime Calculation Engine

### Ruleset + Rule Hierarchy

A **ruleset** (`hr.attendance.overtime.ruleset`) contains ordered **rules** (`hr.attendance.overtime.rule`). Each rule applies to a period of an employee's attendance based on the rule's type.

### Quantity-Based Rules
1. Group attendances by `day` or `week` (Sunday-to-Saturday week).
2. Compute total worked hours per period.
3. Subtract expected hours (from contract or fixed value).
4. If result > `employer_tolerance`: create overtime for the excess, from the latest attendance backward.
5. If result < `-employee_tolerance` and `absence_management`: create negative overtime (undertime).

### Timing-Based Rules
1. Determine applicable intervals based on `timing_type`:
   - `work_days`: working days per company calendar
   - `non_work_days`: non-working days (weekends + unusual days)
   - `schedule`: outside specific calendar hours
   - `leave`: during approved leave intervals
2. Intersect attendance intervals with timing intervals.
3. Filter by `employer_tolerance`.
4. Create overtime for remaining intervals.

### Default Rules (from XML data)

| Rule | Type | Behavior |
|------|------|----------|
| Employee Schedule Rule | `quantity`, `expected_hours_from_contract=True`, `paid=True` | OT for hours beyond contract schedule |
| Non Working Days Rule | `timing`, `timing_type=non_work_days`, `timing_start=0`, `timing_stop=24`, `paid=True` | All hours on non-working days count as OT |

---

## Biometric / Barcode Device Integration

### Kiosk Mode Flow
1. Public URL: `/hr_attendance/<token>` opens kiosk interface.
2. `barcode_scanner` component listens for barcode/RFID scan events.
3. On scan: `POST /hr_attendance/attendance_barcode_scanned` with `{token, barcode}`.
4. Server: searches `hr.employee` by `barcode`, calls `employee._attendance_action_change()`.
5. Response: employee info, current state, today's hours.

### Manual Selection (No Badge)
- `POST /hr_attendance/get_employees_without_badge` — lists employees without barcodes.
- `POST /hr_attendance/create_employee` — creates employee from kiosk.
- `POST /hr_attendance/manual_selection` — requires PIN if `attendance_kiosk_use_pin=True`.

### PIN Verification
- Stored on `hr.employee.pin` (not in this module, defined in `hr` base).
- Checked at kiosk: `employee.pin == pin_code` (if `attendance_kiosk_use_pin`).

---

## Geofencing (Mobile Attendance)

### Location Capture
- Client calls `systray_attendance(latitude, longitude)` or `manual_selection(latitude, longitude)`.
- `_get_geoip_response()`:
  1. Checks `device_tracking_enabled` — returns only mode if disabled.
  2. Calls `base.geocoder._get_localisation(lat, lon)` for reverse geocoding.
  3. Falls back to `request.geoip` (IP-based location) if GPS unavailable.
  4. Captures `ip_address`, `browser` from `user_agent`.

### Map Display
- `action_in_attendance_maps()` / `action_out_attendance_maps()`: opens Google Maps URL `https://maps.google.com?q=<lat>,<lon>`.

### Geofencing (Future/External)
- The `in_location` / `out_location` fields store the resolved address string.
- Actual geofence boundary enforcement (GPS radius check) is not implemented in Odoo core — it would require a custom module or external device integration.

---

## L4: Performance, Edge Cases, Odoo 18→19 Changes

### Performance Considerations

| Concern | Detail |
|---------|--------|
| `_update_overtime()` batch behavior | Overtime lines are deleted and recreated in full for the affected domain. For large batch edits, this can cause N+1 queries on overtime line creation. Rule: keep the affected date range as narrow as possible. |
| `_check_validity()` search per record | Each `create`/`write` triggers up to 3 `search()` calls ordered by `check_in desc`. With thousands of records per employee, use `LIMIT 1` as the code does, but the underlying index on `check_in` is critical. |
| `total_overtime` via `_read_group` | Uses `_read_group` aggregate — single query for all employees, but may be slow on very large `overtime.line` tables. |
| `_compute_hours_today` per employee | Not batched — loops `for employee in self` with a separate `search()` per employee. On large employee sets, consider calling `_compute_hours_today` in batch via a single `search()` grouped by `employee_id`. |
| Kiosk employee search | `employees_infos` endpoint uses `search_fetch` with `company_id` domain filter — should be indexed. |
| `_get_schedules_by_employee_by_work_type` | Batches by `resource_calendar_id` but performs 3 batch interval queries per calendar. The number of calendars is usually small. |

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| Check-in without check-out | `attendance_state = 'checked_in'`. `_cron_auto_check_out` may close it after scheduled hours. |
| Multiple sessions same day | Each session is a separate `hr.attendance` record. `hours_today` sums all. Overtime computed per-attendance, then aggregated. |
| Attendance crosses midnight | `date` field is computed from `check_in` in employee's timezone — both sessions on same day share the same `date`. `_get_localized_times()` uses employee's version timezone. |
| Employee with no timezone | Falls back to `UTC`. `date` will be UTC midnight, may differ from local expectation. |
| Duplicate badge scan | Same employee searched, `_attendance_action_change()` called again — creates check-out for open attendance, then next scan creates new check-in. |
| Move attendance to different day | On `write({'check_in': new_date})`, `_get_overtimes_to_update_domain()` computes both old and new date ranges. `_update_overtime` is called for merged domain. |
| Unlink attendance | Overtime lines for the domain are deleted, then `write` is called on remaining attendances to recompute. |
| Technical attendance (1-second absence) | Created by `_cron_absence_detection` with `in_mode='technical'`. `color=1` (highlighted) in list view. Silently deleted if no overtime contribution. |
| Overlapping manual edits | `_check_validity` prevents overlapping check-ins for the same employee. Edits that create gaps are also caught. |
| Empty `resource_calendar_id` (fully flexible) | `_get_schedules_by_employee_by_work_type` classifies as `fully_flexible` — no lunch or schedule subtraction. |
| Two-week calendar | `expected_worked_hours` in auto-check-out uses `week_type` from `resource.calendar.attendance` line's `two_weeks_calendar` setting. |

### Odoo 18 → 19 Changes

| Area | Change |
|------|--------|
| Overtime engine | Complete rewrite. Odoo 18 had separate methods `_get_overtime_intervals_by_date`, `_generate_overtime_vals`, `_get_overtime_undertime_intervals_by_employee_by_attendance` (v1). Odoo 19 adds `_generate_overtime_vals_v2` and `_get_overtime_undertime_intervals_for_quantity_rule` as the primary path. v1 methods retained as bridges but marked `# TO REMOVE IN MASTER`. |
| Absence management | New in Odoo 19. `_cron_absence_detection` creates technical attendances that produce negative overtime when `absence_management` is enabled. |
| Auto check-out | New in Odoo 19. `_cron_auto_check_out` closes open records based on calendar schedule. |
| `hr.version` extension | New in Odoo 19. Rulesets assigned per employee version rather than directly on `hr.employee`. |
| Rate combination mode | New in Odoo 19. `hr.attendance.overtime.ruleset.rate_combination_mode` (`max`/`sum`) controls how multiple paid rules combine. |
| Tolerance fields moved | `overtime_company_threshold` and `overtime_employee_threshold` moved from `res.company` to per-rule `employer_tolerance` and `employee_tolerance` fields. Company-level fields marked `# TODO: Remove in master`. |
| `hr.employee` schedule methods | `_get_schedules_by_employee_by_work_type` is new — consolidates calendar interval fetching for batch overtime computation. |
| `HrVersion._get_versions_by_employee_and_date` | New in Odoo 19 — efficient binary-search version lookup per employee per date. |
| Session info injection | `ir_http.lazy_session_info()` extends session with `attendance_user_data` for systray display. |

---

## Post-Init and Uninstall Hooks

- `post_init_hook`: triggered on module installation. Currently unused in code (referenced in manifest but no dedicated hook file — likely reserved for future use).
- `uninstall_hook`: referenced in manifest, no dedicated file.

---

## Related Modules

- [Modules/hr](odoo-18/Modules/hr.md) — Base employee model, barcode field, PIN field
- [Modules/hr_work_entry](odoo-17/Modules/hr_work_entry.md) — Work entries generated from attendances (integration point)
- [Modules/hr_holidays](odoo-18/Modules/hr_holidays.md) — Time off tracking; absence detection creates technical attendances that interact with leave
- [Modules/hr_timesheet](odoo-18/Modules/hr_timesheet.md) — Timesheet entry; attendance data used for approval context
- `resource` — Resource calendar, work hours, leave intervals
- `barcodes` — Barcode scanner component, service
- `base_geolocalize` — GPS geocoding
- `mail` — Chatter on attendance records (via `mail.thread` inheritance)

---

## Key File Paths

```
odoo/addons/hr_attendance/
  __manifest__.py                      — module declaration, assets, hooks
  models/
    __init__.py                        — 12 submodules
    hr_attendance.py                   — core attendance model + CRON
    hr_attendance_overtime.py          — overtime line
    hr_attendance_overtime_rule.py     — overtime rules (quantity + timing)
    hr_attendance_overtime_ruleset.py  — ruleset container
    hr_employee.py                     — employee extension + schedule batching
    hr_version.py                      — ruleset per employee version
    hr_employee_public.py              — public employee extension
    ir_http.py                         — session info injection
    res_company.py                     — company settings
    res_users.py                       — officer group cleanup
    res_config_settings.py             — settings wizard
  controllers/
    main.py                            — kiosk HTTP endpoints, systray, barcode
  security/
    hr_attendance_security.xml         — groups + record rules
    hr_attendance_overtime_ruleset_security.xml — ruleset record rules
    ir.model.access.csv                — per-group CRUD permissions
  data/
    hr_attendance_data.xml             — cron jobs
    hr_attendance_overtime_ruleset_data.xml — default ruleset
    hr_attendance_overtime_rule_data.xml — default rules
    hr_attendance_demo.xml             — demo data
    scenarios/hr_attendance_scenario.xml — demo scenario
  views/
    hr_attendance_view.xml
    hr_employee_view.xml
    hr_attendance_kiosk_templates.xml
    hr_attendance_overtime_rule_views.xml
    res_config_settings_views.xml
```