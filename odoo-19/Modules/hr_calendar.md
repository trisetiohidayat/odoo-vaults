# Display Working Hours in Calendar (hr_calendar)

## Overview
- **Category:** Human Resources/Employees
- **Depends:** `hr`, `calendar`
- **Auto-install:** True
- **License:** LGPL-3

Shows employees' working hours in the calendar view. Integrates employee schedules into the calendar's partner availability system, preventing scheduling meetings outside working hours.

## Models

### `calendar.event` (inherited)
Extends calendar events with employee availability checking.

## Key Methods

### `_compute_unavailable_partner_ids()`
Extends the base calendar's unavailable partner computation:
- For each event with attendees, computes the event's time interval (using `_get_events_interval()`)
- Gets each attendee's schedule for that interval via `res.partner._get_schedule()`
- Marks partners as unavailable if they have conflicting events during the calendar event time
- Uses `_check_employees_availability_for_event()` to compare event interval against each partner's schedule

### `_get_events_interval()`
Builds an `Intervals` object for each event:
- For timed events: uses actual `start`/`stop` datetimes
- For allday events: uses the company's work calendar to determine actual working hours
- If an allday event falls on a day when the company is closed, the interval is empty (no conflict)

### `_check_employees_availability_for_event()`
Compares the event interval against each partner's schedule. Returns partners whose schedule does not fully cover the event duration.

### `get_unusual_days()`
Returns non-working days for the current user's employee (used by calendar's holiday display).

## Key Features
- Prevents double-booking employees outside their working hours
- Uses company resource calendar for allday event availability
- Integrates with `calendar` module's existing unavailable partner mechanism

## Related
- [Modules/HR](Modules/hr.md) — HR base
- [Modules/calendar](Modules/calendar.md) — Calendar module
- [Modules/hr_homeworking](Modules/hr_homeworking.md) — Remote work scheduling
