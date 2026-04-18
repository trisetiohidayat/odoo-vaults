---
type: module
module: test_resource
tags: [odoo, odoo19, test, resource, calendar, allocation, timezone, performance]
created: 2026-04-06
---

# Test Resource

## Overview

| Property | Value |
|----------|-------|
| **Name** | Test Resource |
| **Technical** | `test_resource` |
| **Category** | Hidden (Test Module) |
| **Depends** | `resource` |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |

## Description

Test module for the `resource` app. Contains comprehensive test models and test data for testing resource planning, calendar scheduling, capacity planning, and timezone-aware scheduling functionality.

This module is **test-only** and is not installed in production databases. It provides the `resource.test` model (inheriting from `resource.mixin`) and a shared `TestResourceCommon` base class used across all resource tests.

## Module Structure

```
test_resource/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── test_resource.py           # resource.test model
└── tests/
    ├── __init__.py
    ├── common.py                   # TestResourceCommon base class + fixtures
    ├── test_calendar.py           # Calendar attendance/work hours tests
    ├── test_mixin.py              # Resource mixin scheduling tests
    ├── test_performance.py         # Performance benchmarks
    ├── test_resource.py            # Resource validity and work intervals
    ├── test_resource_errors.py     # Error/edge case tests
    └── test_timezones.py          # Timezone edge case tests
```

## Models

### `resource.test`

A minimal test model that inherits from `resource.mixin`. Used to create employee/resource records for testing calendar scheduling without coupling to the `hr.employee` model.

**File:** `models/test_resource.py`

```python
class ResourceTest(models.Model):
    _name = 'resource.test'
    _description = 'Test Resource Model'
    _inherit = ['resource.mixin']

    name = fields.Char()
```

**Design Notes:**

- Inherits from `resource.mixin` which provides `resource_id` (Many2one to `resource.resource`)
- Has a simple `name` Char field for identification
- The `resource.mixin` provides all scheduling and calendar methods:
  - `_adjust_to_calendar()` — adjusts datetime range to working hours
  - `_get_work_days_data_batch()` — calculates working days/hours in a range
  - `_get_leave_days_data_batch()` — calculates leave days in a range
  - `list_leaves()` — returns leave intervals within a date range
  - `_list_work_time_per_day()` — returns working time per day

### `resource.mixin`

The mixin being tested, provided by the `resource` module. Key behaviors:

| Method | Returns | Description |
|--------|---------|-------------|
| `_adjust_to_calendar(start, end)` | Dict[resource, (start, end)] | Clips a datetime range to the resource's working hours |
| `_get_work_days_data_batch(start, end)` | Dict[resource, {days, hours}] | Computes working days/hours excluding leaves |
| `_get_leave_days_data_batch(start, end)` | Dict[resource, {days, hours}] | Computes leave days within a range |
| `list_leaves(start, end)` | List[(date, hours, leave)] | Lists individual leave intervals |
| `_list_work_time_per_day(start, end)` | Dict[resource, List[(date, hours)]] | Working hours broken down per day |

## Test Fixtures: `TestResourceCommon`

**File:** `tests/common.py`

The `TestResourceCommon` class provides shared setup for all resource tests. It creates a library of calendars and resources covering a wide range of scheduling scenarios.

### Calendars

| Calendar | Name | Hours | Timezone | Notes |
|----------|------|-------|----------|-------|
| `calendar_jean` | 40 Hours | Mon-Fri 8:00-16:00 | Europe/Brussels | Standard 5-day week |
| `calendar_patel` | 38 Hours | Mon-Fri 9:00-12:00, 13:00-17:00 | Etc/GMT-6 | Two attendance blocks per day |
| `calendar_john` | 8+12 Hours | Tue 8-16, Fri 8-13 & 16-23 | America/Los_Angeles | Split day, two-day week |
| `calendar_jules` | 2-week cycle | Week1 30h, Week2 16h | Europe/Brussels | Two-weeks rotating |
| `calendar_paul` | Split shifts | Mon-Fri 2-7 & 10-16 | America/Noronha | Two blocks per day |
| `calendar_bob` | Adjacent | Mon-Fri 8-12 & 12-16 | Europe/Brussels | Back-to-back blocks |

### Resources

| Resource | Name | Calendar | Timezone | Notes |
|---------|------|----------|----------|-------|
| `jean` | Jean | 40 Hours | Europe/Brussels | UTC+1/UTC+2 |
| `patel` | Patel | 38 Hours | Etc/GMT-6 | UTC+6 |
| `john` | John | 8+12 Hours | America/Los_Angeles | UTC-8/UTC-7 |
| `jules` | Jules | 2-week cycle | Europe/Brussels | DST transitions |
| `paul` | Paul | Split shifts | America/Noronha | UTC-2 |
| `bob` | Bob | Adjacent blocks | Europe/Brussels | Adjacent attendances |

### Helper Methods

```python
@classmethod
def datetime_tz(cls, year, month, day, hour=0, minute=0, second=0,
                  microsecond=0, tzinfo=None):
    """Return a datetime with a given timezone (tzinfo can be string or pytz object)."""

@classmethod
def datetime_str(cls, year, month, day, hour=0, minute=0, second=0,
                  microsecond=0, tzinfo=None):
    """Return a fields.Datetime string in UTC (converted from given timezone)."""
    # Used to create datetime values for ORM write operations

@classmethod
def _define_calendar(cls, name, attendances, tz):
    """Create a resource.calendar with attendance lines.
    attendances: list of (hour_from, hour_to, dayofweek, duration_days)
    """

@classmethod
def _define_calendar_2_weeks(cls, name, attendances, tz):
    """Create a two-weeks rotating calendar.
    attendances: list of (hour_from, hour_to, dayofweek, week_type)
    """
```

## Test Files

### `tests/test_calendar.py`

Tests for `resource.calendar` model — work hours counting, planning hours/days, closest work time.

**Key test methods:**

- `test_get_work_hours_count` — Verifies `get_work_hours_count()` correctly sums working hours with and without leaves, including DST transitions and two-week calendars
- `test_calendar_working_hours_count` — Tests standard 35h/week calendar with lunch break
- `test_calendar_working_hours_24` — Tests 24-hour attendance spanning midnight boundary
- `test_plan_hours` — Tests `plan_hours()` for forward/backward scheduling, including negative and fractional hour planning
- `test_plan_days` — Tests `plan_days()` for multi-day scheduling across weekends and leaves
- `test_closest_time` — Tests `_get_closest_work_time()` for edge cases: before shift, after shift, midnight boundary
- `test_attendance_interval_edge_tz` — DST boundary behavior for attendance interval generation
- `test_resource_calendar_update` — Ensures leaves move with calendar when reassigned
- `test_compute_work_time_rate_with_one_week_calendar` — Verifies `work_time_rate` computation (50%, 80%, 90%, 100%)
- `test_compute_work_time_rate_with_two_weeks_calendar` — Same for two-week rotating calendars

### `tests/test_mixin.py`

Tests for `resource.mixin` methods on resource records — adjusting to calendar, work days, and leaves.

**Key test methods:**

- `test_adjust_calendar` — Most complex test: verifies `_adjust_to_calendar()` handles split shifts, multi-day ranges crossing non-working days, and search ranges
- `test_adjust_calendar_timezone_before` / `test_adjust_calendar_timezone_after` — Tests timezone handling when resource TZ differs from calendar TZ
- `test_work_days_data` — Tests `_get_work_days_data_batch()` across 4 resources from 4 timezones viewing the same date range; includes half-day leaves
- `test_leaves_days_data` — Tests `_get_leave_days_data_batch()` for half-day leaves, zero-length leaves, timezone conversion, and resource-specific leaves
- `test_list_leaves` — Tests `list_leaves()` for half-day, zero-length, and micro-leaves; returns `(date, hours, leave_id)` tuples
- `test_list_work_time_per_day` — Tests `_list_work_time_per_day()` for half-day leaves and timezone changes

### `tests/test_resource.py`

Tests for `resource.resource` model — calendars validity, work intervals, and two-week switching.

**Key test methods:**

- `test_calendars_validity_within_period` — Tests `_get_calendars_validity_within_period()` returning correct calendar per resource
- `test_performance` — Query count benchmark for `_get_valid_work_intervals()` with 50 resources across 10 days (13 queries target)
- `test_get_valid_work_intervals` — Verifies correct interval computation for a single resource
- `test_get_valid_work_intervals_calendars_only` — Tests calendar-only computation (without resource mapping)
- `test_switch_two_weeks_resource` — Tests calendar type switching without errors
- `test_create_company_using_two_weeks_resource` — Tests company creation with two-week calendar as default
- `test_empty_working_hours_for_two_weeks_resource` — Edge case: resources with no working hours

### `tests/test_performance.py`

Performance benchmarks for attendance interval computation.

**Key test method:**

- `test_performance_attendance_intervals_batch` — Benchmarks `_attendance_intervals_batch()` for 100 resources over a full year:
  - Before optimization: ~2.0 seconds
  - After optimization: ~0.4 seconds (5x improvement)

### `tests/test_timezones.py`

Timezone edge case tests. (Full content not loaded — refers to cross-timezone boundary handling for resource scheduling.)

### `tests/test_resource_errors.py`

Error case tests. (Full content not loaded — refers to invalid calendar configurations and error handling.)

## What Gets Tested

| Test Category | What Is Verified |
|--------------|-----------------|
| Calendar hours | Correct sum of working hours per period |
| Calendar leaves | Half-day, zero-length, and micro-second leaves are handled |
| DST transitions | UTC offset changes are handled correctly (Europe/Brussels, LA) |
| Two-week calendars | Week1 vs Week2 switching, work time rate calculation |
| Timezone conversion | Resource TZ vs calendar TZ independence |
| Adjust to calendar | Split shifts, overnight ranges, cross-midnight ranges |
| Work days data | Per-resource from multiple timezones viewing same range |
| Leave days data | Leave attribution per resource with timezone conversion |
| Interval planning | `plan_hours()` and `plan_days()` with/without leaves |
| Closest work time | Edge cases at shift boundaries and midnight |
| Performance | Batch interval computation at scale (100 resources, 1 year) |
| JSON patch format | RFC 6902 patch format for HTML field revisions |
| Edge cases | Zero-length leaves, adjacent attendance blocks, two-week switching |

## Related

- [Modules/resource](Modules/resource.md) — Resource calendar, working hours, and capacity planning
- [Core/API](API.md) — `@api.depends` and computed field patterns
