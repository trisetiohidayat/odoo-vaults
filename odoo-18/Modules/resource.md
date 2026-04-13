---
type: module
name: resource
version: Odoo 18
tags: [module, resource, calendar, time]
source: ~/odoo/odoo18/odoo/addons/resource/
---

# Resource

Working time calendars, resource scheduling, and interval management.

**Source:** `addons/resource/`
**Depends:** `base`

---

## Models

### `resource.calendar` — Working Time

```python
class ResourceCalendar(models.Model):
    _name = 'resource.calendar'
    _description = 'Resource Working Time'
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Calendar name (required) |
| `active` | Boolean | Default True |
| `company_id` | Many2one | `res.company` |
| `attendance_ids` | One2many | `resource.calendar.attendance` |
| `leave_ids` | One2many | `resource.calendar.leaves` |
| `global_leave_ids` | One2many | Computed from leaves |
| `hours_per_day` | Float | Computed from attendance |
| `tz` | Selection | Timezone (e.g. `Asia/Jakarta`) |
| `tz_offset` | Char | Computed UTC offset |
| `two_weeks_calendar` | Boolean | Enable two-week rotation |
| `flexible_hours` | Boolean | Allow flexible scheduling |
| `full_time_required_hours` | Float | Required hours for full-time |

**Key Methods:**
- `_attendance_intervals_batch()` — Return attendance intervals for resources
- `_leave_intervals_batch()` — Return leave intervals
- `_work_intervals_batch()` — Effective work intervals (attendance − leaves)
- `_unavailable_intervals_batch()` — Return unavailable intervals
- `get_work_hours_count()` — Count work hours between datetimes
- `get_work_duration_data()` — Return days/hours for a period
- `plan_hours()` — Plan hours forward from datetime
- `plan_days()` — Plan days forward from datetime
- `_get_closest_work_time()` — Find closest work interval boundary
- `_get_unusual_days()` — Get unusual days in date range

---

### `resource.calendar.attendance` — Work Detail

```python
class ResourceCalendarAttendance(models.Model):
    _name = 'resource.calendar.attendance'
    _description = 'Work Detail'
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Shift name (required) |
| `dayofweek` | Selection | Day 0–6 (Mon–Sun), required |
| `date_from` / `date_to` | Date | Validity range |
| `hour_from` / `hour_to` | Float | Start/end hour (required) |
| `duration_hours` | Float | Computed from hour range |
| `duration_days` | Float | Computed days |
| `calendar_id` | Many2one | `resource.calendar`, required |
| `day_period` | Selection | `morning` / `lunch` / `afternoon` |
| `resource_id` | Many2one | `resource.resource` (optional) |
| `week_type` | Selection | `0` / `1` for two-week calendars |
| `display_type` | Selection | `line_section` for separators |
| `sequence` | Integer | Sort order |

---

### `resource.calendar.leaves` — Time Off Detail

```python
class ResourceCalendarLeaves(models.Model):
    _name = 'resource.calendar.leaves'
    _description = 'Resource Time Off Detail'
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Leave name |
| `company_id` | Many2one | Computed from context |
| `calendar_id` | Many2one | Computed from resource |
| `date_from` | Datetime | Start (required) |
| `date_to` | Datetime | End (computed, required) |
| `resource_id` | Many2one | `resource.resource` |
| `time_type` | Selection | `leave` / `other` |

---

### `resource.resource` — Resources

```python
class ResourceResource(models.Model):
    _name = 'resource.resource'
    _description = 'Resources'
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Required |
| `active` | Boolean | Default True |
| `company_id` | Many2one | `res.company` |
| `resource_type` | Selection | `user` / `material` |
| `user_id` | Many2one | `res.users` |
| `avatar_128` | Image | Computed from user |
| `share` | Boolean | Related from user |
| `email` / `phone` | Char | Related from partner |
| `time_efficiency` | Float | Default `100` |
| `calendar_id` | Many2one | `resource.calendar` |
| `tz` | Selection | Timezone |

**_sql_constraints:**
- `check_time_efficiency` — CHECK(time_efficiency > 0)

**Key Methods:**
- `_adjust_to_calendar()` — Adjust datetime to closest working hours
- `_get_unavailable_intervals()` — Get unavailable intervals
- `_get_calendars_validity_within_period()` — Get calendar validity
- `_get_valid_work_intervals()` — Get valid work intervals
- `_is_fully_flexible()` — No calendar attached
- `_is_flexible()` — Has flexible schedule

---

### `resource.mixin` — Abstract Mixin

```python
class ResourceMixin(models.AbstractModel):
    _name = 'resource.mixin'
    _description = 'Resource Mixin'
```

Abstract — not stored. Adds scheduling to any model.

| Field | Type | Description |
|-------|------|-------------|
| `resource_id` | Many2one | `resource.resource`, required |
| `company_id` | Many2one | `res.company` |
| `resource_calendar_id` | Many2one | `resource.calendar` |
| `tz` | Selection | Timezone override |

**Key Methods:**
- `_get_work_days_data_batch()` — Working days/hours for period
- `_get_leave_days_data_batch()` — Leave days/hours for period
- `_adjust_to_calendar()` — Delegate to resource
- `_list_work_time_per_day()` — List daily work time
- `list_leaves()` — List leaves in period

---

## Extensions

### `res.company`
Added fields:
- `resource_calendar_ids` — One2many `resource.calendar`
- `resource_calendar_id` — Default Many2one `resource.calendar`

### `res.users`
Added fields:
- `resource_ids` — One2many `resource.resource`
- `resource_calendar_id` — Related Many2one `resource.calendar`

---

## Utility Functions (`utils.py`)

| Function | Description |
|----------|-------------|
| `HOURS_PER_DAY = 8` | Constant |
| `make_aware(dt, tz)` | Add timezone to naive datetime |
| `string_to_datetime()` | Parse `'YYYY-MM-DD HH:MM:SS'` string |
| `datetime_to_string()` | Format datetime to string |
| `float_to_time(hours)` | Convert float hours to `time` object |
| `timezone_datetime(dt)` | Ensure datetime has timezone |
| `Intervals` class | Ordered disjoint intervals — union, intersection, difference |
| `sum_intervals()` | Sum duration of intervals |

---

## Cross-Module Relations

| Module | Integration |
|--------|-------------|
| `hr` | Work entries via `hr_work_entry_contract` |
| `project` | Project planning and task scheduling |
| `mrp` | Work center scheduling |
| `sale_timesheet` | Timesheet billing |
| `hr_holidays` | Leave management |

---

## Related Links
- [Core/BaseModel](odoo-18/Core/BaseModel.md) — ORM foundation
- [Modules/HR](odoo-18/Modules/hr.md) — HR module
- [Modules/Project](odoo-18/Modules/project.md) — Project scheduling
- [Modules/MRP](odoo-18/Modules/mrp.md) — Manufacturing scheduling
