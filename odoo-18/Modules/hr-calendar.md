---
Module: hr_calendar
Version: Odoo 18
Type: Integration
Tags: #hr #calendar #integration #resource
Related Modules: hr, calendar, resource
---

# hr_calendar — Calendar in HR

**Addon Key:** `hr_calendar`
**Depends:** `hr`, `calendar`
**Auto-install:** `True`
**Category:** Human Resources/Employees
**License:** LGPL-3

## Purpose

`hr_calendar` bridges the **HR** and **Calendar** modules. It surfaces employee working schedules in the calendar UI by:

1. Marking **unusual days** (company holidays, employee leaves) as gray overlay in the calendar view
2. Computing and displaying **unavailable partners** on calendar events (attendees who are not working during the event window)
3. Adding a **"My Team"** filter to the partner search, scoped to the current user's department
4. Serving the **working hours overlay** (weekly schedule blocks per attendee) via RPC on the Calendar app frontend

Unlike modules that extend `hr.employee` with calendar fields, this module works primarily through **`calendar.event`** and **`res.partner`** extensions.

---

## Models Extended

### `calendar.event` — Calendar Event

**Inherited from:** `calendar.event` (base)
**File:** `models/calendar_event.py`

#### Fields Added

| Field | Type | Compute | Description |
|-------|------|----------|-------------|
| `unavailable_partner_ids` | `Many2many(res.partner)` | Yes — `_compute_unavailable_partner_ids` | Partners (attendees) who are **not available** during the event window. Computed per-event by intersecting the event's time interval against each attendee's working schedule. |

#### Methods

**`_compute_unavailable_partner_ids()`**
```
@api.depends('partner_ids', 'start', 'stop', 'allday')
def _compute_unavailable_partner_ids(self)
```
Filters events that have valid time windows and attendee partners. For complete events, calls `_get_events_interval()` to build the event's active interval (excluding company closed days for allday events), then calls `_check_employees_availability_for_event()` to find unavailable attendees.

**`_get_events_interval()`**
```
def _get_events_interval(self) -> Dict[calendar.event, Intervals]
```
Returns a dict mapping each event to an `Intervals` object representing its active time range:

- **Timed events**: interval is `start` to `stop` directly, in UTC
- **Allday events**: interval is the full day (00:00–23:59 UTC) intersected with the **company's resource calendar** (`company.resource_calendar_id`). If the company is closed for any day in the range, the event's interval is empty → all attendees are marked unavailable
- **No allday**: intervals are merged with global calendar work intervals

**`_check_employees_availability_for_event(schedule_by_partner, event_interval)`**
```
def _check_employees_availability_for_event(self, schedule_by_partner, event_interval) -> List[int]
```
For each partner/attendee, computes the intersection of their personal schedule with the event interval. If the common interval duration does not equal the event interval duration, the partner is unavailable. Returns partner IDs.

**`get_unusual_days(date_from, date_to=None)`**
```
@api.model
def get_unusual_days(date_from, date_to=None)
```
Delegates to `self.env.user.employee_id._get_unusual_days()` — calls the resource calendar's `_get_unusual_days()` on the user's employee record. This is what the calendar view's `show_unusual_days=True` attribute calls.

#### View Extensions

- `calendar.view_calendar_event_calendar` → adds `show_unusual_days="True"` attribute
- `calendar.view_calendar_event_form_quick_create` and `calendar.view_calendar_event_form` → add invisible `unavailable_partner_ids` field (used by the `many2many_attendees` widget to show unavailable attendee graying)

---

### `res.partner` — Contact

**Inherited from:** `res.partner` (base)
**File:** `models/res_partner.py`

#### Methods Added

**`_get_employees_from_attendees(everybody=False)`**
```
def _get_employees_from_attendees(self, everybody=False) -> Dict[res.partner, hr.employee]
```
Builds a mapping of partner → set of employees linked to that partner via `work_contact_id`. Scoped to current companies.

- `everybody=False` (default): returns only partners in `self`
- `everybody=True`: returns all employees in those companies regardless of partner

Uses `_read_group` with `work_contact_id` as the groupby field.

**`_get_schedule(start_period, stop_period, everybody=False, merge=True)`**
```
def _get_schedule(self, start_period, stop_period, everybody=False, merge=True) -> defaultdict
```
Main method. Returns a `defaultdict(list)` mapping each partner to their `Intervals` of working time during `start_period` to `stop_period`.

Algorithm:
1. Get employees linked to attendees via `_get_employees_from_attendees()`
2. Group employees by their resource calendars (with periods, since other modules like `planning` can override `_get_calendar_periods`)
3. Call `calendar._work_intervals_batch()` once per distinct calendar
4. Map intervals back to individual employees, then union to partner level
5. If `merge=False`: return per-resource interval dicts (used by the availability widget)

**`get_working_hours_for_all_attendees(attendee_ids, date_from, date_to, everybody=False)`**
```
@api.model
def get_working_hours_for_all_attendees(attendee_ids, date_from, date_to, everybody=False)
```
RPC method called by the Calendar App frontend. Converts the intersection of all attendees' working schedules into a list of **RFC 5545 day/time objects** (e.g., `{"daysOfWeek": [1], "startTime": "08:00", "endTime": "18:00"}`). If all attendees are unavailable, returns `{"daysOfWeek": [7], ...}` (a dummy value that greys out the entire week).

**`_interval_to_business_hours(working_intervals)`**
```
def _interval_to_business_hours(self, working_intervals) -> List[dict]
```
Converts raw `Intervals` tuples into the FullCalendar overlay format. Each interval becomes a dict with:
- `daysOfWeek`: integer 0–6 (ISO), converted from Python weekday
- `startTime` / `endTime`: in the current user's timezone

#### View Extensions

- `base.view_res_partner_filter` → added `filter` named `"type_team"` with domain:
  ```
  [('employee_ids.department_id.manager_id.user_id', '=', uid)]
  ```
  Shows only contacts whose employees belong to a department managed by the current user.

---

## L4 — How Calendar + HR Leaves Work Together

### The Unusual Days Flow

```
calendar.event (calendar view, show_unusual_days=True)
    → get_unusual_days() [model method]
        → self.env.user.employee_id._get_unusual_days()
            → resource.calendar._get_unusual_days()
                → filters resource.calendar.leaves where:
                    - leave type is a company leave (not employee-specific)
                    - date range overlaps
```

The unusual days are rendered as gray blocks in the calendar grid, covering the company-level closed days. Employee-specific leaves do not appear here — they are visible inside the employee leave management views.

### The Unavailable Attendees Flow

```
calendar.event form (attendees selected)
    → _compute_unavailable_partner_ids()
        → _get_events_interval() → event_interval
        → res.partner._get_schedule(start, stop) → per-partner schedules
        → _check_employees_availability_for_event(schedules, event_interval)
            → if sum(common) != sum(event_interval): attendee unavailable
```

The result is stored in `unavailable_partner_ids`. The `many2many_attendees` widget uses this to gray out unavailable attendees visually.

### The Working Hours Overlay Flow

```
Calendar App frontend (JS)
    → get_working_hours_for_all_attendees(attendee_ids, date_from, date_to)
        → res.partner._get_schedule() (merged=False for individual schedules)
        → reduce(Intervals.__and__, schedule_by_partner.values())
            → returns intersection of ALL attendees' working hours
        → _interval_to_business_hours() → FullCalendar format
```

The result is fed into FullCalendar's `businessHours` to render a shaded overlay on the calendar, showing the shared working window of all attendees.

### Key Design Notes

- **`hr.employee.base._get_calendar_periods()`** is the hook point. `hr_calendar` does not override it, but `res.partner._get_schedule()` calls it via `employee._get_calendar_periods()`. Other modules (e.g., `planning`) can override this to assign employees different calendars over time periods.
- The `unavailable_partner_ids` field is **invisible in the UI** but is used by the `many2many_attendees` widget's JS logic to set CSS classes on attendee avatars.
- `get_working_hours_for_all_attendees` is an `@api.model` method designed to be called as JSON-RPC from the calendar frontend — it does not depend on the current record's state.

---

## Asset / Frontend

- **JS/CSS:** None. This module has no Python controllers, no static JS — it purely extends Python models and XML views. The calendar app JS in the `calendar` module calls the Python RPC methods directly.

## Security

- No new security rules. Fields added to `calendar.event` and `res.partner` are either computed or filtered through existing access rights. The `unavailable_partner_ids` is not visible in any view directly.

## File Reference

| File | Purpose |
|------|---------|
| `__manifest__.py` | Module declaration, depends on `hr` + `calendar`, auto_install |
| `models/__init__.py` | Imports `calendar_event`, `res_partner` |
| `models/calendar_event.py` | `calendar.event` extensions |
| `models/res_partner.py` | `res.partner` extensions |
| `views/calendar_views_calendarApp.xml` | Add `show_unusual_days`, invisible `unavailable_partner_ids` |
| `views/res_partner_views.xml` | Add "My Team" filter to partner search |