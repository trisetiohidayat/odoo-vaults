---
type: module
module: hr_calendar
tags: [odoo, odoo19, hr, calendar, resource, scheduling, availability]
created: 2026-04-14
uuid: c2d8f1a3-4b5e-6d7a-8f9b-0c1d2e3f4a5b
---

# Display Working Hours in Calendar (`hr_calendar`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Display Working Hours in Calendar |
| **Technical** | `hr_calendar` |
| **Category** | Human Resources / Scheduling |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 19.0 |
| **Depends** | `hr`, `calendar` |
| **Auto-install** | `True` |

The `hr_calendar` module bridges the gap between employee resource scheduling and the calendar event system in Odoo. It integrates each employee's working hours — defined in their HR profile via a resource calendar — into the base calendar module's partner availability mechanism. The result is that when a user creates a calendar event with employee attendees, Odoo automatically marks those employees as unavailable if the event falls outside their working hours, preventing double-booking and scheduling conflicts.

This module operates entirely through ORM-level overrides on the `calendar.event` model. It does not introduce any new database models or menus; instead it extends the behavior of existing calendar events with employee-specific availability computation. The integration is seamless and transparent: once installed, the calendar automatically respects each attendee's work schedule without requiring manual configuration.

## Architecture

### Design Philosophy

The `hr_calendar` module follows a clean extension pattern: it inherits from `calendar.event` and overrides four key methods to inject employee availability logic into the existing calendar framework. The base `calendar` module already has an `unavailable_partner_ids` computed field that tracks which partners cannot attend an event due to schedule conflicts. This module extends that mechanism by adding employee-specific availability checks that compare the event's time window against each employee's resource calendar working hours.

The module uses Odoo's `Intervals` utility class — a powerful abstraction for working with time ranges — to represent both calendar event windows and employee work schedules. This allows set-like operations (intersection, union, difference) to be performed on time intervals, making it straightforward to detect overlaps between events and working hours.

### Dependency Chain

```
hr_calendar
├── calendar          (calendar.event, unavailable_partner_ids, resource.calendar)
├── hr                (hr.employee, resource.mixin)
└── resource          (resource.calendar, _work_intervals_batch)
```

The module depends on `calendar` for the base event model and the `unavailable_partner_ids` mechanism, `hr` for employee data and the `_get_unusual_days` method, and `resource` for the calendar working hours computation. All three are transitive dependencies of `hr`, but the explicit declaration ensures the module cannot be installed without them.

### Time Zone Handling

All time-based operations in this module use UTC (`pytz.UTC`) as the reference timezone. This is critical for correctness when Odoo is deployed in multi-timezone environments. The module converts local datetimes to UTC before performing interval operations and uses Odoo's `localized` utility to handle timezone-aware datetime arithmetic.

## Models

### `calendar.event` (Extended)

The `calendar.event` model is the central entity of the calendar module. It represents a calendar event or meeting, with fields for start/stop times, attendee partners, allday flag, and various metadata. The `hr_calendar` module extends this model by overriding the `unavailable_partner_ids` computed field and adding methods that compute employee-specific availability windows.

The model inherits from `mail.thread` (indirectly via `calendar`) and `mail.activity.mixin`, giving it full messaging and activity tracking capabilities. Events can be linked to many attendees (as `res.partner` records), and each attendee's availability is checked when the event is saved or displayed.

#### Inherited Fields (from `calendar`)

| Field | Type | Description |
|-------|------|-------------|
| `start` | Datetime | Event start datetime (UTC) |
| `stop` | Datetime | Event end datetime (UTC) |
| `allday` | Boolean | True for all-day events |
| `partner_ids` | Many2many | Event attendees (res.partner) |
| `unavailable_partner_ids` | Many2many | Partners unavailable for this event (computed) |
| `res_model` | Char | Related model (for linked events) |
| `res_id` | Integer | ID of linked record |

#### Computed Availability Logic

The availability computation follows a four-step pipeline:

1. **Filter complete events**: The module first filters events that have a valid start/stop time, at least one attendee, and a non-zero duration (or allday status).

2. **Compute event intervals**: For each complete event, `_get_events_interval()` builds an `Intervals` object representing the actual working time covered by the event. For timed events this is simply the event's start and stop. For allday events it is the intersection of the event's full day and the company's working hours.

3. **Fetch employee schedules**: For each attendee in the event, the module calls `res.partner._get_schedule()` to get that attendee's working schedule as an `Intervals` object. This method (from the `resource` module) returns only the working hours from the partner's associated resource calendar.

4. **Compare intervals**: The `_check_employees_availability_for_event()` method compares the event's interval against each attendee's schedule. An attendee is marked unavailable if their schedule does not fully cover the event's duration — i.e., if the intersection of the schedule and event interval is smaller than the event interval.

This design means that an allday event scheduled on a weekend or company holiday will not conflict with employees who are available Monday through Friday, because the company's resource calendar working hours do not include weekends.

## Key Methods

### `_compute_unavailable_partner_ids()`

```python
@api.depends('allday')
def _compute_unavailable_partner_ids(self):
    super()._compute_unavailable_partner_ids()
    complete_events = self.filtered(
        lambda event: event.start and event.stop
            and (event.stop > event.start
                 or (event.stop >= event.start and event.allday))
            and event.partner_ids)
    if not complete_events:
        return
    event_intervals = complete_events._get_events_interval()
    for event, event_interval in event_intervals.items():
        # Event_interval is empty when an allday event
        # contains at least one day where the company is closed
        if not event_interval:
            continue
        start = event_interval._items[0][0]
        stop = event_interval._items[-1][1]
        schedule_by_partner = event.partner_ids._get_schedule(
            start, stop, merge=False)
        event.unavailable_partner_ids |= event._check_employees_availability_for_event(
            schedule_by_partner, event_interval)
```

**Step-by-step breakdown:**

1. **Call parent**: `super()._compute_unavailable_partner_ids()` runs the base calendar's logic first, populating the field with partners who have conflicting events. The `|=` operator later adds to this set.

2. **Filter complete events**: Only events with valid start/stop times, a non-zero duration, and at least one attendee are processed. The duration check has a special case: for allday events, `event.stop >= event.start` is accepted as valid since allday events span midnight boundaries.

3. **Get event intervals**: The `_get_events_interval()` method (see below) returns a dictionary mapping each event to its computed time interval as an `Intervals` object.

4. **Skip empty intervals**: If an allday event falls entirely on a day when the company is closed, its interval will be empty. Skipping such events prevents false "unavailable" flags.

5. **Fetch schedules per partner**: `partner_ids._get_schedule()` (from `res.partner`, which delegates to the associated `resource.mixin`) returns a dictionary mapping each partner to their working schedule for the given time window. The `merge=False` flag returns individual partner schedules rather than a merged result.

6. **Check availability**: For each partner with a schedule, the method computes the intersection between their schedule and the event interval. If the sum of the common interval is less than the sum of the event interval, the partner is not fully available and is added to `unavailable_partner_ids`.

7. **Uses `|=` operator**: This extends the set from the parent call rather than replacing it, preserving the base calendar's existing conflict detection.

### `_get_events_interval()`

```python
def _get_events_interval(self):
    start = min(self.mapped('start')).replace(
        hour=0, minute=0, second=0, tzinfo=UTC)
    stop = max(self.mapped('stop')).replace(
        hour=23, minute=59, second=59, tzinfo=UTC)
    company_calendar = self.env.company.resource_calendar_id
    global_interval = company_calendar._work_intervals_batch(start, stop)[False]
    interval_by_event = {}
    for event in self:
        if event.allday:
            # Build full-day interval for this event
            allday_event_interval = Intervals([(
                event.start.replace(hour=0, minute=0, second=0, tzinfo=UTC),
                event.stop.replace(hour=23, minute=59, second=59, tzinfo=UTC),
                self.env['resource.calendar']
            )])
            # Check each day of the event against company work schedule
            if any(not (Intervals([(
                event.start.replace(hour=0, minute=0, second=0, tzinfo=UTC)
                    + relativedelta(days=i),
                event.start.replace(hour=23, minute=59, second=59, tzinfo=UTC)
                    + relativedelta(days=i),
                self.env['resource.calendar']
            )]) & global_interval)
                for i in range(0, (event.stop_date - event.start_date).days + 1)):
                interval_by_event[event] = Intervals([])
            else:
                interval_by_event[event] = allday_event_interval & global_interval
        else:
            interval_by_event[event] = Intervals([(
                localized(event.start),
                localized(event.stop),
                self.env['resource.calendar']
            )])
    return interval_by_event
```

**Key design decisions:**

1. **Global interval as fallback**: The method first computes the company's global work schedule across the entire date range covered by all events being processed. This is done via `_work_intervals_batch()`, which returns work intervals per resource (with `False` meaning "global calendar").

2. **Allday events**: For allday events, the full calendar day (00:00:00 to 23:59:59) is intersected with the company's work hours. This means an allday event on a Saturday will have an empty interval if the company works Monday–Friday.

3. **Day-by-day validation**: For allday events spanning multiple days, each individual day is checked against the company calendar. If any single day falls outside working hours, the entire event's interval is set to empty. This prevents false conflicts from spanning events that include non-working days.

4. **Timed events**: For non-allday events, the actual start and stop times are used directly, wrapped in an `Intervals` object using `localized()` to handle timezone conversion.

5. **Timezone handling**: All datetimes are normalized to UTC using `pytz.UTC`, ensuring consistent comparison across events and schedules.

### `_check_employees_availability_for_event()`

```python
def _check_employees_availability_for_event(self, schedule_by_partner, event_interval):
    unavailable_partners = self.env["res.partner"]
    for partner, schedule in schedule_by_partner.items():
        common_interval = schedule & event_interval
        if sum_intervals(common_interval) != sum_intervals(event_interval):
            unavailable_partners |= partner
    return unavailable_partners
```

**Logic:** This method iterates over each attendee's schedule and computes the intersection with the event interval. If the total working time in the intersection does not equal the total event duration, the partner is unavailable. For example, if an event runs 8:00–18:00 but a partner only works 8:00–13:00, the partner is unavailable for the afternoon portion.

The `sum_intervals()` function (from `odoo.tools.date_utils`) returns the total duration in hours of an `Intervals` object, enabling a straightforward numeric comparison.

### `get_unusual_days()`

```python
@api.model
def get_unusual_days(self, date_from, date_to=None):
    return self.env.user.employee_id._get_unusual_days(date_from, date_to)
```

This method delegates to the current user's associated employee record. The `_get_unusual_days()` method (from `hr` / `resource`) returns non-working days within the specified date range. The calendar module uses this to display public holidays and company closures as "unusual days" on the calendar view.

## Allday Event Behavior

The handling of allday events reveals the module's most nuanced design. Consider an allday event scheduled Monday through Wednesday:

1. The event's raw interval covers all three days from 00:00 to 23:59:59.
2. This raw interval is intersected with the company calendar's work hours (e.g., Monday–Friday 08:00–18:00).
3. For the Monday and Tuesday portions, the intersection yields the full 08:00–18:00 window.
4. For the Wednesday portion, if Wednesday is a public holiday, the intersection is empty.
5. The module checks each individual day. Since Wednesday has no working hours, the entire event's interval is set to empty.
6. With an empty interval, no employees are marked unavailable for this event — even though they could work Monday and Tuesday.

This conservative approach avoids incorrectly flagging employees as unavailable for allday events that include non-working days. The practical implication is that allday events spanning holidays require explicit time boundaries (i.e., should be created as timed events) to enforce working-hours compliance for all portions.

## Integration with `resource.calendar`

The module relies on the `resource.calendar` model from the `resource` module to compute working hours. Key concepts:

- **Resource calendar**: Each company has a default `resource_calendar_id` that defines working days and hours. Employees can have individual calendars that override the company default.
- **Work intervals**: `_work_intervals_batch()` returns the working time windows from a calendar for a given date range, accounting for public holidays, weekends, and working hour exceptions.
- **Partner schedule**: `res.partner._get_schedule()` delegates to the partner's resource (via `resource.mixin`), returning the actual working hours for that partner.

## Business Impact

### Double-Booking Prevention

The primary business benefit is preventing managers and assistants from scheduling meetings during times when key employees are unavailable. In organizations with field service staff, sales teams, or service technicians whose schedules are managed through Odoo, this automatic check eliminates the need for manual schedule verification.

### HR-Calendar Synchronization

The module creates a direct link between HR data (employee working hours) and the calendar application. Any change to an employee's working schedule — such as adjusting their resource calendar for a new contract or adding a public holiday — is automatically reflected in their calendar availability without any additional configuration.

### Meeting Room Booking

In conjunction with the `calendar` module's existing room booking features, `hr_calendar` ensures that when a room and employees are added as attendees to a meeting, the system checks both the room's availability and each employee's schedule simultaneously. This is particularly valuable for organizations with limited meeting space or remote workers with varied schedules.

## Extension Points

### Custom Availability Rules

Developers can extend `_check_employees_availability_for_event()` to implement custom availability logic. For example, a module could:

```python
class CalendarEventHrExtended(models.Model):
    _inherit = 'calendar.event'

    def _check_employees_availability_for_event(
            self, schedule_by_partner, event_interval):
        unavailable = super()._check_employees_availability_for_event(
            schedule_by_partner, event_interval)
        # Add custom logic: e.g., block certain employees on project deadlines
        return unavailable | self._get_project_deadline_blockers()
```

### Integration with `hr_homeworking`

The [Modules/hr_homeworking](hr_homeworking.md) module extends this module to handle remote work days and alternate work locations. When both modules are installed, the availability check considers not only working hours but also the employee's designated work location for each day, enabling accurate scheduling for hybrid workers.

## Configuration

### Setting Up Employee Working Hours

1. Navigate to **Employees > Employees** and open an employee record.
2. In the **HR Settings** tab, assign a **Working Schedule** (Resource Calendar). If not set, the company's default calendar is used.
3. The calendar can be configured with specific working hours per day, exceptions for public holidays, and alternate schedules for part-time employees.

### Company Default Calendar

1. Navigate to **Settings > Companies > Companies**.
2. Open the company record and set the **Working Hours** field to the appropriate resource calendar.
3. This calendar is used for allday event availability checks and as the default for employees without individual calendars.

## Related

- [Modules/HR](HR.md) — HR base module, employee management, resource calendars
- [Modules/calendar](calendar.md) — Calendar event system, partner availability
- [Modules/hr_homeworking](hr_homeworking.md) — Remote work scheduling with location awareness
- [Modules/resource](resource.md) — Resource calendar, working hours management
- [Modules/resource_calendar](resource_calendar.md) — Advanced calendar features

## Real-World Scenarios

### Scenario 1: Service Technician Scheduling

An HVAC company has three field technicians with different working schedules:
- **Technician A**: Monday–Friday, 8:00–17:00 (standard)
- **Technician B**: Tuesday–Saturday, 9:00–18:00 (shift worker)
- **Technician C**: Monday–Friday, 6:00–14:00 (early shift)

A service manager creates a calendar event for Monday 7:00–15:00 to cover an early morning emergency call. With `hr_calendar` installed:

1. Technician A (starts 8:00) is marked **unavailable** for the 7:00–8:00 portion.
2. Technician B (works Tuesday–Saturday) is marked **fully unavailable** for Monday.
3. Technician C (starts 6:00) is marked **fully available** — no conflict.

Without this module, the manager would have no automated way to know these scheduling conflicts exist.

### Scenario 2: Multi-Day Allday Event with Holiday

A company schedules an allday team-building event for Monday through Wednesday. Wednesday is a public holiday. With `hr_calendar`:

1. The module detects that Wednesday is a non-working day from the company's resource calendar.
2. Because the allday event includes Wednesday (a non-working day), the event's interval is set to **empty**.
3. No employees are marked unavailable for this event.
4. The conservative behavior prevents false "unavailable" flags for events that span non-working days.

The practical implication: if the event is truly important for all attendees, it should be scheduled as a timed event (9:00–17:00) on the working days, rather than as an allday spanning event.

### Scenario 3: Part-Time Employee

A part-time employee works only Monday and Wednesday mornings (8:00–12:00). Their individual resource calendar reflects this schedule. When a 4-hour meeting is scheduled for Wednesday 9:00–13:00:

1. The event interval is 9:00–13:00.
2. The employee's schedule for that window is 8:00–12:00.
3. The intersection is 9:00–12:00 (3 hours).
4. The event is 4 hours; the employee is only available for 3.
5. Result: the employee is marked **unavailable**.

This accurate conflict detection prevents overbooking part-time staff who genuinely have limited availability.

## Key Differences from Base Calendar Availability

The base `calendar` module checks for **event conflicts** — it prevents double-booking when a partner already has a calendar event during the proposed time. The `hr_calendar` module adds a complementary check for **working hours conflicts** — it prevents scheduling when an employee is not supposed to be working.

Both checks run simultaneously when `unavailable_partner_ids` is computed:
1. Base calendar: marks partners unavailable if they have **other events** at the same time.
2. `hr_calendar`: marks partners unavailable if their **working hours** don't cover the event.

A partner can be unavailable for both reasons simultaneously.

## Troubleshooting

### Issue: Employees Not Showing as Unavailable

**Symptoms**: An employee with a non-standard schedule is not marked unavailable even when an event falls outside their working hours.

**Possible causes**:
1. The employee does not have an individual resource calendar assigned — the system falls back to the company's default calendar. Check **Employees > Employee > HR Settings > Working Schedule**.
2. The event is an allday event that includes a non-working day — the module conservatively sets the interval to empty in this case.
3. The employee is not linked to the partner record. The `partner_ids` in the calendar event are `res.partner` records; the availability check uses `partner._get_schedule()` which delegates to the partner's `resource_id` (from HR). Ensure the employee has a linked resource.

### Issue: Wrong Timezone Display

**Symptoms**: Available times appear offset by hours in the calendar view.

**Cause**: The module works internally in UTC but Odoo's calendar view may display in the user's timezone. This is a display issue in the calendar view, not in the availability computation. The computation itself uses UTC throughout.

### Issue: Allday Event Marking Everyone Available

**Symptoms**: Allday events that should conflict with non-working days are not marking anyone unavailable.

**Cause**: This is by design. An allday event spanning a holiday results in an empty interval, which means no one is marked unavailable. To enforce working-hour compliance for multi-day events, create them as timed events with explicit start and stop times.

## Extension Ideas

### Custom Availability Exceptions

A custom module could extend `_check_employees_availability_for_event()` to add project-based or role-based availability:

```python
def _check_employees_availability_for_event(
        self, schedule_by_partner, event_interval):
    unavailable = super()._check_employees_for_event(
        schedule_by_partner, event_interval)

    # Block employees on project deadline days
    deadline_blockers = self._get_project_deadline_blockers()
    return unavailable | deadline_blockers

def _get_project_deadline_blockers(self):
    """Return partners who have project deadlines during this event."""
    event_start = event_interval._items[0][0]
    event_stop = event_interval._items[-1][1]
    # Search for project tasks due during the event window
    # Mark those employees as unavailable
```

### Integration with Planning (Shift Scheduling)

When the `hr_presence` or `planning` modules are installed, the availability check could be extended to also consider:
- Employee check-in/check-out status (presence)
- Planned shifts (planning module)

This would create a more dynamic availability view that reflects real-time employee availability rather than just scheduled working hours.
