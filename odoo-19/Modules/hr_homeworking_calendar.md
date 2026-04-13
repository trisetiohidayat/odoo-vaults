# Remote Work with Calendar

## Overview
- **Category:** Human Resources/Remote Work
- **Depends:** `hr_homeworking`, `calendar`
- **Version:** 1.0
- **License:** LGPL-3
- **Auto-install:** Yes

## Description
Extends `hr_homeworking` by adding calendar integration. Employees can set their weekly work location directly from the calendar event view, and their location can be displayed in the calendar overlay.

## Key Features
- **Calendar widget on employee location:** A wizard accessible from the calendar allows employees to set their work location for a specific date or update their weekly default.
- **Partner scheduling:** Integrates employee work locations into the `res.partner` calendar availability computation, so meeting organizers can see when attendees are available based on their work schedule.
- **Homework location wizard:** `homework.location.wizard` lets users set location for a specific day (exceptional) or update the weekly default.

## Models

### `hr.employee` (Extended)
Adds `_get_worklocation(start_date, end_date)` method that returns a dict of work locations per employee per day, including exceptions.

```python
def _get_worklocation(self, start_date, end_date):
    # Returns {employee_id: {user_id, employee_id, partner_id,
    #   'monday_location_id': {...}, ...,
    #   'exceptions': {'2026-04-06': {...}}
    # }}
```

### `res.partner` (Extended)
Adds `get_worklocation(start_date, end_date)` method that delegates to the employee's `_get_worklocation`.

### `hr.work.location` (Extended)
Added `_unlink_except_used_by_employee()`: prevents deletion of a work location that is currently assigned to any employee (as a weekly default). Also cascades-deletes any `hr.employee.location` exception records using that location.

## Wizard: `homework.location.wizard`

| Field | Type | Description |
|-------|------|-------------|
| `work_location_id` | Many2one | Target work location (required) |
| `employee_id` | Many2one | Employee (defaults to current user) |
| `weekly` | Boolean | If True, update the weekly default; if False, create an exceptional one-day entry |
| `date` | Date | Date for the exceptional location change |

**`set_employee_location()` logic:**
- If `weekly=True`: deletes any exception for that date, then updates the employee's weekly default location field for that weekday.
- If `weekly=False`: if the selected location matches the weekly default, deletes any exception; if an exception already exists, updates it; otherwise creates a new `hr.employee.location` record.

## Related
- [Modules/hr_homeworking](Modules/hr_homeworking.md) - Core homeworking/work location management
- [Modules/calendar](Modules/calendar.md) - Calendar events and availability
