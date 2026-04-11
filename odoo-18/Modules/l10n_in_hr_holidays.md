---
Module: l10n_in_hr_holidays
Version: 18.0
Type: l10n/india
Tags: #odoo18 #l10n #hr #india
---

# l10n_in_hr_holidays — Indian Time Off / Leave Management

## Overview
India-specific extension of the HR Holidays (Time Off) module. Adds **sandwich leave** calculation — a rule where if a leave period covers holidays, those holidays are counted as part of the leave (the leave period is "sandwiched" between working days, hence all intermediate non-working days count as leave). Also adds India-specific leave type configuration.

## Country
India

## Dependencies
- hr_holidays

## Key Models

### `HolidaysType` (`hr.leave.type`) — hr_leave_type.py
- `_inherit = "hr.leave.type"`
- `l10n_in_is_sandwich_leave` — Boolean
  - When enabled: holidays within a leave period are included in the total leave count
  - The extra non-working days (added before/after the leave) receive the same treatment (allocation, pay, reports) as the original request

### `HolidaysRequest` (`hr.leave`) — hr_leave.py
- `_inherit = "hr.leave"`
- `l10n_in_contains_sandwich_leaves` — Boolean (stored), computed field
- `_l10n_in_apply_sandwich_rule(public_holidays, employee_leaves)` — applies sandwich leave logic:
  - Counts non-working days (weekends, public holidays) before and after the leave period
  - Adds those days to total leave count
  - Trims non-working days from start/end of period (so leave only starts/ends on working days)
- `_get_durations(check_leave_type=True, resource_calendar=None)` — EXTENDS hr_holidays:
  - Detects Indian companies (`country_id.code == 'IN'`)
  - For leaves with `l10n_in_is_sandwich_leave = True`: recalculates duration with sandwich rule
  - Sets `l10n_in_contains_sandwich_leaves` flag if duration changed
  - Uses `_read_group` to fetch other approved leaves per employee for sandwich calculation

## Data Files
- `views/hr_leave_views.xml` — Leave request form with Indian-specific fields
- `views/hr_leave_type_views.xml` — Leave type config with sandwich leave checkbox

## Sandwich Leave Logic (Detailed)
The `_l10n_in_apply_sandwich_rule` method:
1. Takes public holidays and other employee leaves as input
2. `count_sandwich_days(calendar, date, direction)` — walks backward/forward from leave dates counting non-working days (weekends or public holidays) until hitting a working day, then stops when another employee leave is encountered
3. `is_non_working_day(calendar, date)` — checks calendar schedule and holiday list
4. After counting sandwich days in both directions, trims leading/trailing non-working days from the period
5. Returns the corrected total leave days including sandwich days

This is distinct from standard Odoo leave computation and requires the resource calendar and public holidays data.

## Installation
Auto-installs with `hr_holidays`. India-specific behavior only activates for companies with country code `IN`.

## Historical Notes
Version 1.0 in Odoo 18. New module in Odoo 18. Sandwich leave is a common Indian HR practice where holidays between two leave segments are counted as leave (e.g., Saturday + Sunday + Monday leave = 5 days total when the weekend is sandwiched).