---
type: module
module: resource
tags: [odoo, odoo19, resource, scheduling, calendar, hr, time-off, timezone]
created: 2026-04-06
updated: 2026-04-11
depth: [L1, L2, L3, L4]
---

# Resource Management (`resource`)

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `resource` |
| **Version** | 1.1 |
| **Category** | Hidden (Core framework module) |
| **Dependencies** | `base`, `web` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Odoo Source** | `~/odoo/odoo19/odoo/addons/resource/` |

## Purpose

The `resource` module is a **core framework module** that manages resource scheduling, working time calendars, and time-off allocations. It provides the foundational time-tracking infrastructure used by `hr`, `project`, `mrp`, and virtually every module that deals with employee schedules or work orders.

**Key responsibilities:**
- Define resources (humans and equipment) with working time calendars
- Calculate working days, hours, and intervals between datetimes
- Handle time-off (leaves) for both individual resources and company-wide
- Support flexible schedules, two-week alternating calendars, and fully-flexible resources
- Multi-timezone-aware datetime computation
- Plan hours/days forward from a starting datetime

**Architecture:** The module is intentionally minimal. It defines the data models and interval-computation logic but leaves UI, approvals, and accrual policies to domain-specific modules (`hr_holidays`, `project`, `mrp`).

---

## Architecture

```
resource.mixin                    (Abstract) -- attaches resource/calendar to any model
       |
       +-- resource.resource      -- the schedulable entity (employee or equipment)
       |        |
       |        +-- calendar_id -----> resource.calendar
       |
resource.calendar                -- working time template
       |
       +-- attendance_ids --------> resource.calendar.attendance  (one2many)
       +-- leave_ids --------------> resource.calendar.leaves       (one2many)

res.company                      (extends) -- adds resource_calendar_id field
res.users                       (extends) -- adds resource_ids / calendar_id
```

### Core Concepts

**Intervals:** All time computations in this module use `(datetime, datetime, meta)` tuples called *intervals*. The third element (`meta`) carries the source record (e.g., a `resource.calendar.attendance` or `resource.calendar.leaves` object). Interval lists support set operations (`&` intersection, `-` difference) via the `odoo.tools.intervals.Intervals` class.

**Working Time vs. Leave Time:** Working intervals are the intersection of *attendance* intervals (scheduled working periods) minus *leave* intervals (time off). Both are computed in batch across multiple resources simultaneously.

**Fully Flexible vs. Flexible vs. Fully Fixed:**
- **Fully Fixed** (`schedule_type='fully_fixed'`): explicit `hour_from`/`hour_to` per weekday, standard attendance lines.
- **Flexible** (`flexible_hours=True`, `schedule_type='flexible'`): no fixed hours, but a weekly hours target (`full_time_required_hours`). Hours are distributed across the week, centered around 12:00.
- **Fully Flexible Resource** (`calendar_id=False` on `resource.resource`): no working schedule at all; the whole period counts as available time.

---

## Models

### 1. `resource.mixin`

**File:** `models/resource_mixin.py`

Abstract model that attaches resource behavior to any record. Used by `hr.employee`, `project.project`, and other resource-aware models. The mixin is the primary integration point: it creates the underlying `resource.resource` record automatically on first creation of any mixin model.

#### L1: Surface

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `resource_id` | Many2one `resource.resource` | auto-created | Core link to the resource |
| `company_id` | Many2one `res.company` | `self.env.company` | Auto-synced from resource |
| `resource_calendar_id` | Many2one `resource.calendar` | company calendar | Synced from resource |
| `tz` | Selection (timezone) | from resource | Per-record timezone override |

#### L2: Context

- `resource_id` has `bypass_search_access=True` — allows searching by resource without explicit ACL on `resource.resource`.
- `company_id` is `related='resource_id.company_id', precompute=True, store=True, readonly=False` — automatically mirrors the resource's company.
- `resource_calendar_id` is `related='resource_id.calendar_id', store=True, readonly=False` — same mirroring pattern.
- `tz` is `related='resource_id.tz', readonly=False` — allows per-record timezone override.

#### L3: Key Methods

**`create(vals_list)`** (override)
- Intercepts create to auto-create a `resource.resource` record if `resource_id` is not provided.
- Extracts `tz` from `vals['tz']` or from `vals['resource_calendar_id']`'s calendar.
- Delegates to `super()` with `check_idempotence=True` context to prevent double-creation.
- **L3 Detail:** Batches resource creation via `api.model_create_multi` — all new resources are created in a single `create()` call, then their IDs are assigned to the correct records in `vals_list`.

**`_prepare_resource_values(vals, tz)`**
- Hook method that builds the resource creation dict. Extracts `name` from `self._rec_name`, copies `tz`, `company_id`, and `calendar_id`.

**`_get_calendars(date_from=None)`** -> dict
- Returns `{resource.id: calendar}` mapping. Default implementation returns the resource's own calendar. Override point for contract-aware calendar changes (e.g., `hr_contract` module overrides this to return calendar-per-contract validity windows).

**`_get_work_days_data_batch(from_datetime, to_datetime, compute_leaves=True, calendar=None, domain=None)`** -> dict
- **L3 Performance:** Batches computation across all records sharing the same calendar to minimize queries. Groups records by calendar first, then calls `_work_intervals_batch` once per distinct calendar.
- Returns `{'days': n, 'hours': h}` for each record.
- When `compute_leaves=True`, calls `calendar._work_intervals_batch()` which subtracts leave intervals.
- When `compute_leaves=False`, uses `_attendance_intervals_batch()` for raw schedule only.
- `domain` parameter filters which leave types are counted (default: `('time_type', '=', 'leave')`).
- Converts naive datetimes to UTC via `localized()`.
- **L4 Edge Case:** Fully flexible resources (no calendar) return `{'days': 0, 'hours': 0}`.

**`_get_leave_days_data_batch(from_datetime, to_datetime, calendar=None, domain=None)`** -> dict
- Returns `{'days': n, 'hours': h}` for leaves only (the inverse of work days).
- Uses `attendances & leaves` intersection to find time-off intervals.
- For fully flexible resources, returns the full span without leave subtraction.

**`_adjust_to_calendar(start, end)`** -> dict
- Delegates to `resource_id._adjust_to_calendar()` and converts dict keys from resources back to mixin records.

**`_list_work_time_per_day(from_datetime, to_datetime, ...)`** -> dict
- Returns `list of (date, hours)` tuples per record. Used for per-day reporting. Groups by calendar first, then iterates per record.

**`list_leaves(from_datetime, to_datetime, ...)`** -> list
- Returns `(date, hours, leave_record)` tuples for each leave in the period, using `leaves & attendances` intersection.

#### L4: `copy_data` Override

- Overrides `copy_data` to duplicate the underlying `resource.resource` record alongside the mixin record.
- Copies `company_id` and `resource_calendar_id` from defaults if provided.
- Assigns the new resource ID to the copied vals dict, ensuring the duplicated mixin record links to the new resource.

---

### 2. `resource.resource`

**File:** `models/resource_resource.py`

The schedulable entity. Can represent a human (employee) or a piece of equipment (work center).

#### L1: Surface

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | required | Resource name |
| `active` | Boolean | `True` | Soft delete |
| `company_id` | Many2one `res.company` | `self.env.company` | |
| `resource_type` | Selection | `'user'` | `'user'` (Human) or `'material'` |
| `user_id` | Many2one `res.users` | — | Links to Odoo user; indexed `btree_not_null` |
| `avatar_128` | Image | computed | From `user_id` |
| `share` | Boolean | related | From `user_id.share` |
| `email` | Char | related | From `user_id.email` |
| `phone` | Char | related | From `user_id.phone` |
| `time_efficiency` | Float | `100` | >0, affects MRP work order duration |
| `calendar_id` | Many2one `resource.calendar` | company calendar | `None` = fully flexible |
| `tz` | Selection | user tz or UTC | |

#### L2: Context

- `resource_type='user'` links the resource to a human; `'material'` links to equipment.
- `time_efficiency` is a multiplier: `100` = 100%, `200` = twice as fast (halves duration). Used by `mrp` for work center efficiency. SQL constraint: `CHECK(time_efficiency > 0)`.
- `calendar_id=False` (no Many2one set) marks a **fully flexible resource** — the entire time period counts as available; no fixed schedule.
- `tz` defaults to context tz → user tz → UTC; this field is **critical** for all interval computations.
- `user_id` has `index='btree_not_null'` — SQL index that is defined only for non-null values, efficient for both NULL and non-NULL lookups.

#### L3: Key Methods

**`create(vals_list)`** (override)
- Auto-sets `calendar_id` from the company's default calendar if `company_id` is set but `calendar_id` is not.
- Auto-retrieves `tz` from the linked `user_id.tz` or the calendar's `tz` if not explicitly provided.
- Calls `super().create()` which triggers ORM precomputation.

**`_adjust_to_calendar(start, end, compute_leaves=True)`** -> dict
- Snaps a datetime range to the nearest working period in the resource's calendar.
- Returns `{resource: (localized_start_datetime, localized_end_datetime)}`.
- Uses `_get_closest_work_time()` to find the earliest attendance start and latest attendance end.
- Falls back to the company calendar if the resource has no calendar.
- `compute_leaves=True` skips periods blocked by leave.

**`_get_unavailable_intervals(start, end)`** -> dict
- Returns periods when the resource is NOT available (complement of work intervals).
- Groups resources by calendar to batch-query `_unavailable_intervals_batch`.
- Returns `{}` for fully flexible resources (no unavailable periods).
- **L3 Edge Case (cross-module):** Used by enterprise forecast/planning features in Odoo Enterprise.

**`_get_calendars_validity_within_period(start, end, default_company=None)`** -> dict
- Returns `{resource_id: {calendar: Intervals}}` — maps each calendar and its validity interval for each resource. Here, validity covers the full period (each calendar is valid for the whole range).
- **Override point:** Extended in `hr_contract` to split validity by contract periods (one calendar per contract).

**`_get_valid_work_intervals(start, end, calendars=None, compute_leaves=True)`** -> tuple
- Combines calendar work intervals with calendar validity intervals.
- Returns `(resource_work_intervals, calendar_work_intervals)`.
- Handles fully flexible resources (no calendar) by returning the full period.
- **L3 Edge Case:** If `calendars` is passed, those calendars' work intervals are also computed (used for comparison/display).

**`_is_fully_flexible()`** -> bool
- Returns `True` if `calendar_id` is not set (False/empty).

**`_is_flexible()`** -> bool
- Returns `True` if `_is_fully_flexible()` OR if `calendar_id.flexible_hours == True`.

**`_get_flexible_resources_default_work_intervals(start, end)`** -> dict
- For fully-flexible resources, creates full-day intervals (00:00–23:59:59) for each day in range, grouped by timezone.

**`_get_flexible_resource_valid_work_intervals(start, end)`** -> tuple
- Computes work intervals for flexible resources, handling per-day and per-week hour caps.
- Subtracts custom time-off intervals from the default full-day availability.
- Returns `(resource_work_intervals, resource_hours_per_day, resource_hours_per_week)`.
- Applies `min(hours, hours_per_day)` and `min(cumulative, full_time_required_hours)` caps per day and per week.

**`_get_flexible_resource_work_hours(intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week, work_hours_per_day=None)`** -> float
- Sums working hours from intervals, respecting daily and weekly hour limits for flexible resources.
- Handles the midnight boundary microsecond loss: when `end.time() == time.max`, adds 1 microsecond before computing duration.
- **L4 Edge Case:** Returns raw interval sum for fully flexible resources (no cap applied).

**`_format_leave(leave, ...)`** (internal)
- Adjusts `resource_hours_per_day` and `resource_hours_per_week` based on leave periods.
- Iterates through each day of leave, subtracting `hours_per_day` from daily and weekly trackers.
- Appends full-day (00:00–23:59:59.999999) intervals to `ranges_to_remove` for each leave day.

#### L4: `write()` Idempotency Guard

```python
def write(self, vals):
    if self.env.context.get('check_idempotence') and len(self) == 1:
        vals = {
            fname: value
            for fname, value in vals.items()
            if self._fields[fname].convert_to_write(self[fname], self) != value
        }
```

The `check_idempotence` context prevents the mixin's `create()` from re-writing identical values when it calls `super().create()`. Only writes fields whose computed-in-db value differs from the incoming value — a performance optimization and a guard against infinite loops in computed-field cycles.

---

### 3. `resource.calendar`

**File:** `models/resource_calendar.py`

The working time template. Contains attendance lines and global leave definitions.

#### L1: Surface

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | required | Calendar name |
| `active` | Boolean | `True` | |
| `attendance_ids` | One2many | from company | Work hours per day/week |
| `attendance_ids_1st_week` | One2many | computed | Filtered for 2-week mode |
| `attendance_ids_2nd_week` | One2many | computed | Filtered for 2-week mode |
| `company_id` | Many2one `res.company` | `self.env.company` | |
| `leave_ids` | One2many | — | Time off (all types) |
| `global_leave_ids` | One2many | from company | Filtered: `resource_id=False` |
| `schedule_type` | Selection | `'fully_fixed'` | `'flexible'` or `'fully_fixed'` |
| `duration_based` | Boolean | `False` | Hours centered around 12:00 |
| `flexible_hours` | Boolean | computed | Mirror of `schedule_type` |
| `full_time_required_hours` | Float | from company | Weekly hours for FTE |
| `hours_per_day` | Float | computed | Average hours/day |
| `hours_per_week` | Float | computed | Total hours/week |
| `is_fulltime` | Boolean | computed | `hours_per_week == full_time_required_hours` |
| `two_weeks_calendar` | Boolean | `False` | Alternating week mode |
| `two_weeks_explanation` | Char | computed | Human-readable week label |
| `tz` | Selection | user/system | Timezone for computations |
| `tz_offset` | Char | computed | UTC offset string |
| `work_resources_count` | Integer | computed | Resources using this calendar |
| `work_time_rate` | Float | computed | `%` of full-time schedule |

#### L2: Context

- `schedule_type` drives the entire computation mode:
  - `'fully_fixed'`: uses `attendance_ids` as-is with explicit `hour_from`/`hour_to`.
  - `'flexible'`: ignores time-of-day; uses `full_time_required_hours` weekly target only, distributed across days.
- `duration_based=True` centers working hours around noon (12:00) rather than using explicit start/end times. Cannot mix with `day_period='lunch'` attendance lines.
- `two_weeks_calendar=True` splits `attendance_ids` into week-type A (odd) and B (even) using the "ordinal week number parity" algorithm — guarantees alternating week types even across year boundaries.
- `full_time_required_hours` defaults to the parent company's `resource_calendar_id.hours_per_week`.
- `hours_per_day` and `hours_per_week` are `store=True` computed fields that avoid recomputation on every access.
- `global_leave_ids` is a filtered view of `leave_ids` where `resource_id=False` (company-wide leave).
- `leave_ids` contains **all** leaves (both global and resource-specific), filtered by domain in the view.
- `work_time_rate = hours_per_week / full_time_required_hours * 100` — enables filtering by schedule intensity (e.g., find all 50% schedules).

#### L3: Interval Computation Methods

These are the **core engine** of the module. All operate on batches of resources.

**`_attendance_intervals_batch(start_dt, end_dt, resources=None, domain=None, tz=None, lunch=False)`** -> dict
- Returns `{resource_id: Intervals}` of scheduled working time.
- For **fully fixed calendars**: uses `rrule(DAILY)` to iterate dates, matches weekday + week_type against `attendance_ids`.
- For **flexible calendars**: generates intervals that fill up to `full_time_required_hours` per week, distributed across days, centered around 12:00.
- For **fully flexible resources** (`calendar_id=False`): returns a single interval from `start_dt` to `end_dt` with a dummy attendance record (hours = total hours in range).
- `lunch=True` returns only `day_period='lunch'` intervals.
- **L4 Performance:** `rrule(DAILY)` generates dates once in UTC, then the result is cloned per timezone — avoids redundant rrule computation across all resources sharing the same calendar.
- The `Domain` object (new in recent Odoo) is used for SQL-efficient filtering of `attendance_ids`.
- `domain` parameter adds extra filter conditions on `resource.calendar.attendance` (e.g., filter by `resource_id` for resource-specific attendances).

**`_leave_intervals_batch(start_dt, end_dt, resources=None, domain=None, tz=None)`** -> dict
- Returns `{resource_id: Intervals}` of leave periods.
- Default `domain=('time_type', '=', 'leave')`. Override with custom domain for training/other time types.
- Handles both global leaves (`resource_id=False`) and resource-specific leaves.
- For fully flexible resources, delegates to `_handle_flexible_leave_interval()` hook.
- **L3 Detail:** All datetime comparisons are done in UTC (both `date_from` and `date_to` are converted to UTC before comparison). The result intervals are expressed in the resource's timezone.

**`_work_intervals_batch(start_dt, end_dt, resources=None, domain=None, tz=None, compute_leaves=True)`** -> dict
- Returns `attendance - leaves` intervals (set difference using `Intervals` class).
- `compute_leaves=True` subtracts leave intervals; `False` returns pure attendance.
- **L3 Note:** The context key `employee_timezone` is read as the `tz` parameter — allows passing timezone through the call chain.

**`_unavailable_intervals_batch(start_dt, end_dt, resources=None, domain=None, tz=None)`** -> dict
- Returns complement intervals: the time NOT covered by work intervals.
- Uses the "flatten-then-pair" algorithm: takes `[start] + flat(work_intervals) + [end]`, pairs them, and those pairs are the unavailable periods.
- Skips fully flexible resources (returns nothing for them).

**`_get_closest_work_time(dt, match_end=False, resource=None, search_range=None, compute_leaves=True)`** -> datetime
- Finds the nearest working interval boundary (start or end) to a given datetime.
- Used by `_adjust_to_calendar()` for snapping. Returns `None` if no work interval exists within the search range.
- Raises `ValueError` if datetimes lack timezone info.

**`_check_overlap(attendance_ids)`**
- Raises `ValidationError` if attendance lines overlap on the same day.
- Uses `Intervals` set logic: adds `0.000001` to each `hour_from` to prevent contiguous intervals from being detected as overlapping (since `Intervals` joins touching intervals).
- Applies separately within each week type for two-week calendars.

**`get_work_hours_count(start_dt, end_dt, compute_leaves=True, domain=None)`** -> float
- Returns total hours as sum of `(stop - start).total_seconds() / 3600`.
- Internal use only; `get_work_duration_data()` is the public API.

**`get_work_duration_data(from_datetime, to_datetime, compute_leaves=True, domain=None)`** -> dict
- Returns `{'days': n, 'hours': h}` using `_get_attendance_intervals_days_data()`.

**`_get_attendance_intervals_days_data(attendance_intervals)`** -> dict
- Converts interval hours to days using duration ratio from attendance metadata.
- Groups hours and days by date, then applies the formula: `duration_days_ratio * (interval_hours / total_attendance_hours)`.
- **L4 Edge Case:** For flexible calendars (`self.flexible_hours`), uses `interval_hours / self.hours_per_day` (not attendance metadata) because no real attendance records exist.
- Rounds days to nearest 0.001 (`precision_rounding=0.001`).

**`plan_hours(hours, day_dt, compute_leaves=False, domain=None, resource=None)`** -> datetime
- Given a starting datetime and a number of hours, finds the datetime that falls `hours` working hours later.
- Iterates in 14-day chunks up to 100 chunks (700 days max). Returns `False` if no result found within that range.
- **L3 Edge Case:** If `hours < 0`, searches backwards.
- **L4 Edge Case:** `hours == 0` returns the start of the first work interval, not `day_dt` itself.

**`plan_days(days, day_dt, compute_leaves=False, domain=None)`** -> datetime
- Same logic as `plan_hours` but counting full working days by unique `start.date()`.
- Returns the `stop` of the interval on the Nth working day.
- Returns `revert(day_dt)` if `days == 0`.

**`_works_on_date(date)`** -> bool
- Returns whether the calendar has working hours on a given date.
- For two-week calendars, uses `get_week_type(date)` to determine week type.

**`_get_hours_for_date(target_date, day_period=None)`** -> tuple
- Returns `(hour_from, hour_to)` floats for a given date.
- For flexible calendars: centers around 12:00, uses `hours_per_day / 2`.
- For fixed calendars: uses `_read_group` to aggregate `hour_from:min` and `hour_to:max` per weekday+weektype.

#### L3: Calendar Configuration Methods

**`_get_default_attendance_ids(company_id=None)`** -> list of Command.create dicts
- Returns the standard 5-day week (Mon–Fri, 8:00–12:00 and 13:00–17:00, with 12:00–13:00 lunch).
- If `company_id` has an existing calendar, copies its attendance lines instead.
- This is the "Standard 40 hours/week" template used for new companies and new calendars.

**`_get_two_weeks_attendance()`** -> list of Command.create dicts
- Converts a normal calendar to 2-week mode by duplicating all attendance lines with `week_type='0'` and `week_type='1'`, with section separators.
- Section headers have `sequence=0` (first week) and `sequence=25` (second week) to ensure they bracket the respective attendance lines.

**`switch_calendar_type()`**
- Toggles `two_weeks_calendar`. If enabling, calls `_get_two_weeks_attendance()`. If disabling, unlinks all attendances and resets to default.
- When disabling, also resets `duration_based=False`.

**`switch_based_on_duration()`**
- Toggles `duration_based`. When enabling, removes lunch periods. When disabling, resets to default (or two-week if applicable).

#### L3: Constraints

**`@api.constrains('attendance_ids')`**
1. In 2-week mode: all attendance lines must be inside week-type sections (first attendance must be a section).
2. Checks for superimposition within each week type using `_check_overlap()`.

#### L4: `DummyAttendance` NamedTuple

Used internally to create virtual attendance records for:
- Fully flexible resources (one record spanning the full requested period)
- Flexible calendars (multiple records per day centered around 12:00)

The `DummyAttendance` has fields: `hour_from`, `hour_to`, `dayofweek`, `day_period`, `week_type`. These are never persisted — they exist only as in-memory objects used to construct intervals.

---

### 4. `resource.calendar.attendance`

**File:** `models/resource_calendar_attendance.py`

Individual working period line on a calendar.

#### L1: Surface

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | required | Label (e.g., "Monday Morning") |
| `dayofweek` | Selection | `'0'` | 0=Monday ... 6=Sunday |
| `hour_from` | Float | `0` | Start hour (e.g., 8.5 = 8:30 AM) |
| `hour_to` | Float | `0` | End hour |
| `duration_hours` | Float | computed | `hour_to - hour_from` (not lunch) |
| `duration_days` | Float | computed | 0 / 0.5 / 1 based on period |
| `calendar_id` | Many2one | required | Parent calendar; `ondelete='cascade'` |
| `duration_based` | Boolean | related | From calendar |
| `day_period` | Selection | `'morning'` | `'morning'/'lunch'/'afternoon'/'full_day'` |
| `week_type` | Selection | `False` | `'0'` (First) / `'1'` (Second) |
| `two_weeks_calendar` | Boolean | related | From calendar |
| `display_type` | Selection | `False` | `'line_section'` for section headers |
| `sequence` | Integer | `10` | Display ordering |

#### L2: Context

- `hour_from` and `hour_to` are floats representing hours with decimal minutes (e.g., `8.5` = 8:30 AM). A value of `24.0` is treated as `23:59:59.999999` via `float_to_time()`.
- `duration_hours` is computed as `hour_to - hour_from` unless `day_period='lunch'` (returns 0).
- `duration_based=True` on the calendar enables centered hours: for `day_period='morning'`, `hour_from = 12 - duration_hours`; for `'afternoon'`, `hour_to = 12 + duration_hours`; for `'full_day'`, hours split evenly around noon.
- `week_type` uses ordinal week parity: `floor((date.toordinal - 1) / 7) % 2`. This means week 1 is always followed by week 2, regardless of ISO week numbers — avoids the "53-week year" problem.
- `display_type='line_section'` creates visual separators in the calendar view; `_is_work_period()` returns `False` for these.

#### L3: Methods

**`_onchange_hours()`**
- Clamps `hour_from` to `[0.0, 23.99]`, `hour_to` to `[0.0, 24.0]`.
- Ensures `hour_to >= hour_from`.

**`_inverse_duration_hours()`**
- When `calendar_id.duration_based=True`, recomputes `hour_from`/`hour_to` from `duration_hours` and `day_period`.
- `full_day`: `hour_to = 12 + duration/2`, `hour_from = 12 - duration/2`
- `morning`: `hour_to = 12`, `hour_from = 12 - duration`
- `afternoon`: `hour_to = 12 + duration`, `hour_from = 12`

**`_compute_duration_days()`**
- `lunch` = 0 days; `full_day` = 1 day; `morning`/`afternoon` = 0.5 if `duration_hours <= hours_per_day * 3/4`, else 1.
- The `3/4` threshold means half-days are recognized only if they occupy 75% or less of a full workday.

**`get_week_type(date)`** -> int
- Static method returning `0` or `1` for any date using ordinal parity: `int(math.floor((date.toordinal() - 1) / 7) % 2)`.
- **L4 Historical Note:** ISO week numbers have years with 53 weeks; ordinal parity avoids this entirely. January 1 and December 31 can be in different week types, which is the intended behavior.

**`_is_work_period()`** -> bool
- Returns `False` for `day_period='lunch'` or `display_type='line_section'`.
- Used to filter out non-working periods from interval computations.

**`_copy_attendance_vals()`** -> dict
- Returns a dict of field values suitable for `Command.create()`, used by calendar duplication and two-week conversion.

**`_compute_display_name()`**
- For section headers (`display_type='line_section'`), sets a dynamic name: "First week (this week)", "Second week (other week)", etc. — based on whether the section's week type matches the current week type.

#### L4: Constraint

**`@api.constrains('day_period')`**
- Raises `UserError` if `day_period='lunch'` on a `duration_based=True` calendar. Breaks and duration-based schedules are mutually exclusive.

---

### 5. `resource.calendar.leave`

**File:** `models/resource_calendar_leaves.py`

Time-off / leave record attached to a calendar.

#### L1: Surface

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | — | Reason / description |
| `company_id` | Many2one `res.company` | computed | From calendar |
| `calendar_id` | Many2one | computed | From resource |
| `date_from` | Datetime | required | Start of leave |
| `date_to` | Datetime | computed | End of leave |
| `resource_id` | Many2one `resource.resource` | — | Specific resource or empty (global) |
| `time_type` | Selection | `'leave'` | `'leave'` or `'other'` |

#### L2: Context

- `resource_id` is optional. If empty (`False`), the leave is **global** (applies to all resources using this calendar). If set, only that specific resource is affected.
- `time_type='leave'` is the default; `time_type='other'` is used for training days, bank holidays counted as work time, etc.
- `calendar_id` is computed from `resource_id.calendar_id` when `resource_id` is set.
- `company_id` is computed from `calendar_id.company_id`.
- `date_to` is auto-computed from `date_from` if not set: `date_from + relativedelta(hour=23, minute=59, second=59)` in the user's timezone. If `date_to` is already set and is greater than `date_from`, the existing value is preserved (no overwrite).
- The `default_get()` method pre-fills `date_from`/`date_to` with the current day using the company's calendar timezone.

#### L3: Constraints

**`@api.constrains('date_from', 'date_to')`**
- Raises `ValidationError` if `date_from > date_to`.

#### L3: `_copy_leave_vals()` -> dict

Returns `{name, date_from, date_to, time_type}` for use in calendar duplication.

---

### 6. `res.company` (Extension)

**File:** `models/res_company.py`

| Field | Type | Description |
|-------|------|-------------|
| `resource_calendar_ids` | One2many | All calendars owned by the company |
| `resource_calendar_id` | Many2one | **Default working hours** for this company |

- When a new company is created without a calendar, `_create_resource_calendar()` is called via the post-init hook `_init_data_resource_calendar`.
- Creates a `'Standard 40 hours/week'` calendar named with the company.
- **L3 Hook Chain:** `create()` calls `_create_resource_calendar()` for companies without one, then fixes `company_id` on the newly created calendar if it wasn't set during creation (handles form-view creation where the company hasn't been saved yet).

---

### 7. `res.users` (Extension)

**File:** `models/res_users.py`

| Field | Type | Description |
|-------|------|-------------|
| `resource_ids` | One2many | All resources linked to this user |
| `resource_calendar_id` | Many2one | Convenience shortcut to `resource_ids.calendar_id` |

- `resource_calendar_id` uses `related='resource_ids.calendar_id', readonly=False` — picks up the calendar of the first resource linked to the user.
- **L3 `write()` Hook:** When admin's `tz` is set on first login (`login_date` is null) and the user being updated is the admin user, the admin's resource calendar timezone is also updated. This ensures the default calendar inherits the server admin's timezone.

---

## Calendar Management

### Two-Week Calendar Mode

When `two_weeks_calendar=True`, the calendar alternates between two sets of attendance lines:

1. All attendance lines must be wrapped in section separators (lines with `display_type='line_section'`). Section headers are `sequence=0` (week 0) and `sequence=25` (week 1), acting as visual and logical brackets.
2. Week type is determined by ordinal parity: `floor((ordinal - 1) / 7) % 2`.
3. `attendance_ids_1st_week` and `attendance_ids_2nd_week` are computed inverses that filter by `week_type`.
4. Switching to 2-week mode via `switch_calendar_type()` duplicates all existing attendance lines with both week types.
5. Switching off resets attendance to the default 5-day schedule (loses existing attendance data).

### Flexible Schedule Mode

When `schedule_type='flexible'`:
- No fixed `hour_from`/`hour_to` on attendance lines (can be left blank).
- `full_time_required_hours` defines the weekly hour target (e.g., 30 hours for part-time).
- `_attendance_intervals_batch()` generates intervals that fill each day/week up to the target.
- Each interval is centered around 12:00, clamped to day boundaries.
- **L4 Edge Case:** If the requested period is shorter than a full week, hours are prorated (partial week handles proportionally).

### Duration-Based Attendance

When `duration_based=True`:
- Working hours are defined by `duration_hours` rather than explicit times.
- `day_period` determines how hours are distributed: morning (ends at 12:00), afternoon (starts at 12:00), full_day (centered).
- Lunch breaks (`day_period='lunch'`) are prohibited in this mode (`@api.constrains` raises `UserError`).
- When enabling, existing lunch periods are silently deleted.
- When disabling, all attendance is reset to the default schedule.

---

## Time Intervals

### Interval Data Structure

All interval-based methods use the `odoo.tools.intervals.Intervals` class. An interval is:

```python
(start: datetime, end: datetime, meta: record)
```

- `start` and `end` are timezone-aware datetimes (UTC internally, localized for output).
- `meta` is the source record (e.g., `resource.calendar.attendance` or `resource.calendar.leave`).
- Intervals support set operations: `+` (union), `-` (difference), `&` (intersection), `|` (union).
- `keep_distinct=True` prevents merging of adjacent intervals (important for per-resource attribution).

### Interval Computation Flow

```
_requested_datetime_range
        |
        v
_get_calendars_validity_within_period()   -- validity windows per resource
        |
        v
_attendance_intervals_batch()             -- scheduled working hours
        |
        v  (if compute_leaves=True)
_leave_intervals_batch()                 -- time-off periods
        |
        v
(attendance - leaves)                     -- effective working time
        |
        v
_get_attendance_intervals_days_data()    -- convert to {days, hours}
```

### Batch Processing

All interval methods use the `_batch` suffix pattern:
- Accept a `resources` recordset (can be empty, meaning "all resources using this calendar").
- Return a `dict` keyed by `resource.id` (with `False` as the key for calendar-level/no-resource results).
- Group resources by timezone to minimize redundant computation.
- `Domain` objects are used for SQL-efficient filtering in `_attendance_intervals_batch`.

---

## Resource Allocation

### Creating Resources with Mixin

When a record using `resource.mixin` is created:

```
1. mixin.create(vals_list) intercepts the create
2. If resource_id not provided in vals:
   a. Extract tz from vals['tz'] or calendar tz
   b. Build resource dict via _prepare_resource_values()
   c. Create all new resources in one batch call
   d. Assign resource IDs back into vals_list
3. super().create() with check_idempotence=True context
   (prevents re-writing identical values on the newly created resource)
4. copy_data override duplicates the resource.resource too
```

### Resource Type: Human vs. Material

- `resource_type='user'`: Links to a `res.users` record. Used for employees.
- `resource_type='material'`: No user link. Used for equipment, meeting rooms, machines.
- `time_efficiency` applies only to `material` resources (MRP work center efficiency).
- `time_efficiency` is a SQL-constrained positive float (error raised if `<= 0`).

### Fully Flexible Resources

A resource with `calendar_id=False`:
- Has no working schedule constraints.
- `_attendance_intervals_batch()` returns the full requested period as a single interval (hours = total hours in range).
- `_leave_intervals_batch()` returns leave intervals (if any).
- `_work_intervals_batch()` returns the full period minus leaves.
- `_get_unavailable_intervals()` returns `{}` (nothing is unavailable).
- Used for contractors, consultants, or equipment with no predefined schedule.

---

## Timezone Handling

### Timezone Resolution Order

1. `resource.resource.tz` field (per-resource override)
2. `resource.calendar.tz` field (calendar default)
3. `res.users.tz` (user's preference)
4. Admin user's tz (for calendar creation defaults)
5. `UTC` (ultimate fallback)

### How Timezones Affect Intervals

1. All interval computations happen in **UTC** internally.
2. Input datetimes are made explicit in UTC via `localized()`.
3. Results are converted back to the resource's timezone for display.
4. `bounds_per_tz` tracks the timezone-specific date boundaries for each group of resources.
5. The outer date bounds across all timezones are used to run `rrule(DAILY)` — this ensures we generate enough dates to cover all timezone offsets.

### Key Timezone Gotchas

- `dateutil.rrule` generates dates in UTC, but calendar hours (e.g., `hour_from=8`) are interpreted in the **calendar's timezone**.
- The interval generation converts each attendance line's hours into UTC datetimes by applying the timezone offset.
- A resource in `America/New_York` with calendar hours 9:00–17:00 means 14:00–22:00 UTC during EST, but 13:00–21:00 during EDT — the same local time corresponds to different UTC times depending on DST.

### Timezone-Aware Default Values

- `resource.calendar.tz` defaults to: context tz → user tz → admin user tz → UTC.
- `resource.resource.tz` defaults to: context tz → user tz → UTC.
- `resource.calendar.leaves` `default_get()` uses the calendar's timezone (not the user's) to initialize `date_from`/`date_to`.

---

## `utils.py` — Domain Filter Utility

**File:** `models/utils.py`

**`HOURS_PER_DAY = 8`** — module-level constant. Used as fallback when no calendar is available (e.g., in `project` before resource is linked).

**`filter_domain_leaf(domain, field_check, field_name_mapping=None)`** -> `Domain`
- Transforms a domain by keeping only leaves where `field_check(field_name)` returns True, and optionally remapping field names via `field_name_mapping`.
- Respects logical operators: `&`, `|`, `!` — undetermined leaves are replaced with `Domain.TRUE` (ignored).
- Used by downstream modules (e.g., `planning`) to adapt leave domains between models.
- Handles `Domain` objects (new ORM API) — not the legacy list-of-tuples format.

---

## Performance Notes

### Batch Methods Reduce N+1

The `_batch` suffix methods (`_attendance_intervals_batch`, `_leave_intervals_batch`, `_work_intervals_batch`) accept a `resources` recordset and group resources by timezone and calendar. This avoids:

- N queries for N resources (would be 1 per resource).
- Redundant rrule date generation (done once per timezone, not per resource).

### Intervals Set Operations

Using `odoo.tools.intervals.Intervals` with set operations (`&`, `-`, `|`) is O(n log n) rather than O(n^2) for naive list operations.

### Fully Flexible Resource Handling

Fully flexible resources (`calendar_id=False`) are detected early and return the full period directly, bypassing expensive attendance search and rrule generation.

### Cache Strategy

- `hours_per_day` and `hours_per_week` are `store=True` computed fields, so they don't need recomputation on every access.
- Calendar attendance search (`_attendance_intervals_batch`) uses `Domain` objects for efficient SQL filtering.
- `_compute_work_resources_count()` uses `_read_group()` (single aggregate query) rather than `search_count()` per calendar.

### Known Performance Concerns

- **`_get_work_days_data_batch` called in a loop**: If called per-record rather than per-batch from a mixin model, the batch optimization is lost. Always call on a recordset, not in a `for` loop.
- **Large leave period queries**: `_leave_intervals_batch` searches all leaves in the date range. For resources with many historical leaves, this can be slow. Consider adding `resource_id` domain filtering.
- **`rrule(DAILY)` over long ranges**: Generating daily dates for a 1-year range creates 365 iterations. This is acceptable for typical use but can add up in batch scheduling scenarios.
- **`plan_hours` and `plan_days` in 100-chunk loops**: These iterate in 14-day chunks up to 100 times (700 days). For large hour counts, this can be slow. Consider caching results for repeated queries.

---

## Dependencies

### Incoming (modules that depend on `resource`)

| Module | What it uses |
|--------|-------------|
| `hr` | `resource.mixin` on `hr.employee`, time tracking |
| `project` | `resource.mixin` on `project.project`, task scheduling |
| `mrp` | `resource.resource.time_efficiency`, work order duration |
| `sale_project` | Gantt scheduling with resource allocation |
| `hr_holidays` | Leaves, calendar-based accruals |
| `planning` | Shift scheduling, resource conflict detection |
| `manufacture` | Work center capacity planning |
| `stock` | Resource capacity in warehouse operations |

### Outgoing (`resource` depends on)

| Module | What it uses |
|--------|-------------|
| `base` | `res.company`, `res.users`, basic models |
| `web` | Assets, JS for calendar UI (static/src) |

---

## Security

### Access Control (`ir.model.access.csv`)

| ACL | Model | Group | R | W | C | D |
|-----|-------|-------|---|---|---|---|
| `access_resource_calendar_user` | `resource.calendar` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_resource_calendar_system` | `resource.calendar` | `base.group_system` | 1 | 1 | 1 | 1 |
| `access_resource_calendar_attendance_user` | `resource.calendar.attendance` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_resource_calendar_attendance_system` | `resource.calendar.attendance` | `base.group_system` | 1 | 1 | 1 | 1 |
| `access_resource_resource` | `resource.resource` | `base.group_system` | 1 | 0 | 0 | 0 |
| `access_resource_resource_all` | `resource.resource` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_resource_calendar_leaves_user` | `resource.calendar.leaves` | `base.group_user` | 1 | 1 | 1 | 1 |
| `access_resource_calendar_leaves` | `resource.calendar.leaves` | `base.group_system` | 1 | 1 | 1 | 1 |

**Key observations:**
- Regular users can **read** calendars and attendance but cannot write them.
- Regular users can **CRUD** leaves (create, write, delete) — this allows employees to request time off directly in the calendar view.
- `resource.resource` write access is `base.group_system` only (only admins can create/modify resources).
- `access_resource_resource_all` gives read-only access to all users — this is what allows `hr` and `project` to link to resources.

### Record Rules (`resource_security.xml`)

| Rule | Model | Scope | Purpose |
|------|-------|-------|---------|
| `resource_calendar_leaves_rule_group_user_create` | `resource.calendar.leaves` | `base.group_user` | Employees can read their own leaves or global leaves |
| `resource_calendar_leaves_rule_group_user_modify` | `resource.calendar.leaves` | `base.group_user` | Employees can modify their own leaves only |
| `resource_calendar_leaves_rule_group_admin_modify` | `resource.calendar.leaves` | `base.group_erp_manager` | Admins can modify global leaves |
| `resource_resource_multi_company` | `resource.resource` | all | Resources belong to their company or have no company |
| `resource_calendar_leaves_rule_multi_company` | `resource.calendar.leaves` | all | Leaves belong to their company or have no company |

**L4 Security Detail:** The `perm_write/perm_create/perm_unlink = False` flags on `resource_calendar_leaves_rule_group_user_create` mean that rule only restricts reads — writes are handled by the next rule (`resource_calendar_leaves_rule_group_user_modify`). Similarly, `perm_read = False` on modify rules means those rules only control writes, not reads.

---

## Odoo 18 → 19 Changes

### New in Odoo 19

1. **`schedule_type` Selection Field** (new): Replaces the old `flexible_hours` boolean with a more expressive selection (`'flexible'` vs `'fully_fixed'`). The boolean field `flexible_hours` is kept as a computed inverse.

2. **`full_time_required_hours`** (new): Explicit FTE weekly hours target. Previously FTE was implied from `hours_per_week`. Now drives the flexible schedule computation explicitly.

3. **Flexible Resources** have enhanced support in interval computation with `_get_flexible_resource_valid_work_intervals()` and `_get_flexible_resource_work_hours()` — supporting per-day and per-week hour caps.

4. **`resource.mixin`** now uses `api.model_create_multi` for batch resource creation with `check_idempotence=True` context.

5. **`resource.calendar`** now has `work_time_rate` and `is_fulltime` computed fields for easier schedule comparison. `work_time_rate` has a custom `_search_work_time_rate()` method enabling filtering in tree views.

6. **`resource.calendar.attendance`** gains `duration_based` support with centered hour computation and `_inverse_duration_hours()`.

7. **`DummyAttendance` NamedTuple** (new): Introduced to represent virtual attendance records for flexible resources and calendars, replacing ad-hoc dicts.

8. **`Domain` object** (new ORM feature) is used in `_attendance_intervals_batch` for SQL-efficient filtering instead of legacy list-of-tuples domains.

9. **`two_weeks_explanation`** (new): Human-readable computed field showing which week type the current week corresponds to.

### Deprecations

- `_get_work_interval()` on `resource.resource` is deprecated; use `_adjust_to_calendar()` instead.

---

## Extension Points

### Override `_get_calendars()` in Mixin Models

For contract-aware calendar changes (different calendars per employment contract period):

```python
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _get_calendars(self, date_from=None):
        # Return {resource.id: calendar} based on contract validity
        # Called by _get_work_days_data_batch
```

### Override `_get_calendars_validity_within_period()` in `resource.resource`

For multi-calendar resources (e.g., an employee who changes contracts):

```python
class HrEmployee(models.Model):
    _inherit = 'resource.resource'

    def _get_calendars_validity_within_period(self, start, end, default_company=None):
        # Return {resource_id: {calendar: Intervals}} per validity window
        # Split by contract dates
```

### Override `_handle_flexible_leave_interval()` in Calendar

For customizing how leave is interpreted for flexible schedules:

```python
class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    def _handle_flexible_leave_interval(self, dt0, dt1, leave):
        # Custom leave handling for flexible resources
        # Default: full day from 00:00 to 23:59:59
```

### Override `_get_calendar_at()` in `resource.resource`

For resource-specific attendance overrides (attendance lines that belong to the resource, not the calendar):

```python
class MrpWorkcenter(models.Model):
    _inherit = 'resource.resource'

    def _get_calendar_at(self, date_target, tz=False):
        # Return {resource: calendar} with resource-specific calendar if needed
```

---

## Related

- [Modules/HR](modules/hr.md) — Uses `resource.mixin` for employee scheduling
- [Modules/Project](modules/project.md) — Task scheduling using resource calendars
- [Modules/MRP](modules/mrp.md) — Work center efficiency from `resource.resource.time_efficiency`
- [Modules/Stock](modules/stock.md) — Warehouse capacity using resource intervals
- [Core/API](core/api.md) — `@api.depends`, `@api.onchange` patterns
- [Core/BaseModel](core/basemodel.md) — ORM foundation
