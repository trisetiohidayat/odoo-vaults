---
Module: hr_calendar
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_calendar
---

## Overview
Display Working Hours in Calendar. This module bridges `hr` and `calendar` to show each employee's working schedule on calendar events, making it easy to see availability conflicts. It is `auto_install=True` (depends on `hr` and `calendar`). No Python models are defined by this module itself — it extends `calendar.event` and `res.partner`.

## Models

### calendar.event (Extension)
Inherits from: `calendar.event`
File: `~/odoo/odoo18/odoo/addons/hr_calendar/models/calendar_event.py`

| Field | Type | Description |
|-------|------|-------------|
| unavailable_partner_ids | Many2many(res.partner) | Compute: partners who are NOT available during the event time, based on their work schedule |

**`unavailable_partner_ids` Compute Logic (`_compute_unavailable_partner_ids`):**
- Filters to events where start/stop are defined and valid
- For allday events: checks if the company calendar is open for all event days
- If company is closed for entire allday event, all partners are unavailable
- Otherwise: calls `partner_ids._get_schedule()` and `_check_employees_availability_for_event()`
- Uses `Intervals` utility from `resource.models.utils` for overlap detection

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| get_unusual_days | self, date_from, date_to | dict | Delegates to `self.env.user.employee_id._get_unusual_days()` |
| _get_events_interval | self | Intervals | Returns work Intervals per event; allday events are clipped to company calendar working hours; empty interval if company closed on all days |
| _check_employees_availability_for_event | self, schedule_by_partner, event_interval | list of partner IDs | Finds partners whose work schedule does NOT fully cover the event interval |

### res.partner (Extension)
Inherits from: `res.partner`
File: `~/odoo/odoo18/odoo/addons/hr_calendar/models/res_partner.py`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_employees_from_attendees | self, everybody=False | dict | Maps partner IDs to `hr.employee` recordset via `work_contact_id`. Filters by current companies and optionally by `self.ids` |
| _get_schedule | self, start_period, stop_period, everybody=False, merge=True | defaultdict | Core scheduling method: retrieves employee calendars for the period, computes work intervals per calendar, then builds per-partner schedule as union of employee schedules. Supports mixed-calendar employees via `_get_calendar_periods` |
| get_working_hours_for_all_attendees | cls/env, attendee_ids, date_from, date_to, everybody=False | list | RPC-entrypoint: converts ISO date strings to UTC, calls `_get_schedule()`, intersects all partner intervals, returns fullcalendar-formatted business hours |
| _interval_to_business_hours | self, working_intervals | list of dict | Converts `Intervals` object to fullcalendar `daysOfWeek/startTime/endTime` format. If empty, returns dummy weekday-7 slot to gray out the calendar |

## Critical Notes
- **No new Python models** — pure extension module; the heavy logic lives in `res.partner._get_schedule()` which is also called by the JS calendar widget
- **JS Side:** The fullcalendar overlay is computed in JS via `get_working_hours_for_all_attendees` RPC call
- **Allday events:** If the company calendar has no working hours on any day of an allday event, the entire event is marked as unavailable
- **Performance:** `_get_schedule` batches employees by calendar via `_work_intervals_batch` for efficiency
- **Version:** No breaking v17→v18 changes identified; same architecture since at least v15
