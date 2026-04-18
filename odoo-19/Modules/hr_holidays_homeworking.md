---
type: module
module: hr_holidays_homeworking
tags: [odoo, odoo19, hr, holidays, leave, work from home, attendance]
created: 2026-04-06
uuid: a7b8c9d0-1234-5678-9abc-123456789abc
---

# HR Holidays Homeworking

## Overview

| Property | Value |
|----------|-------|
| **Name** | Holidays with Remote Work |
| **Technical** | `hr_holidays_homeworking` |
| **Category** | Human Resources |
| **Depends** | `hr_holidays`, `hr_homeworking` |
| **License** | LGPL-3 |
| **Auto-install** | True |

## What It Does

`hr_holidays_homeworking` is a composite module that integrates two capabilities -- **leave (time-off) management** from `hr_holidays` and **work location / remote work** management from `hr_homeworking` -- into a unified experience. The central feature is a backend Python method on `hr.employee` that overrides the employee presence icon computation to show an airplane icon when an employee is on leave (time off), rather than showing their homeworking location icon. The module also ships a JavaScript Owl component patch that extends the frontend presence status display to render location-specific icons (home, office, other) and color-coded leave badges on the employee kanban and form views.

The module is `auto_install: True`. When a database has both `hr_holidays` and `hr_homeworking` installed but not `hr_holidays_homeworking`, Odoo automatically installs it to bridge the two subsystems.

## Module Structure

```
hr_holidays_homeworking/
├── __init__.py                              # Imports models submodule
├── __manifest__.py                         # Metadata
├── models/
│   ├── __init__.py                         # Imports hr_employee
│   └── hr_employee.py                      # Backend: _compute_presence_icon override
└── static/
    └── src/
        └── components/
            └── hr_presence_status/
                └── hr_presence_status.js   # Frontend: Owl component patches
    └── tests/
        └── hr_presence_status.test.js       # Hoot unit test for the JS patches
```

### `__manifest__.py`

```python
{
    'name': 'Holidays with Remote Work',
    'category': 'Human Resources',
    'summary': 'Manage holidays with remote work',
    'depends': [
        'hr_holidays',     # Leave management: time off, leave types, allocation
        'hr_homeworking',  # Work locations: monday_location_id ... sunday_location_id
    ],
    'assets': {
        # Load the JS patches into the backend web client
        'web.assets_backend': [
            'hr_holidays_homeworking/static/src/**/*',
        ],
        # Load tests into the test runner
        'web.assets_unit_tests': [
            'hr_holidays_homeworking/static/tests/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'auto_install': True,
}
```

## The Two Subsystems Being Bridged

### `hr_holidays` (Leave Management)

`hr_holidays` provides:
- `hr.leave.type` -- Types of leave (Annual Leave, Sick Leave, etc.)
- `hr.leave` -- Individual leave requests (time off bookings)
- `hr.leave.allocation` -- Vacation allocation / accrual
- State machine: `draft` -> `confirm` -> `validate` (approved) / `cancel`
- When a leave is **approved**, the employee's `current_leave_id` and `current_leave_state` fields are updated
- When `current_leave_id` is set, the employee is considered "absent" for attendance purposes

### `hr_homeworking` (Work Locations)

`hr_homeworking` provides:
- Per-weekday work location fields on `hr.employee`:
  - `monday_location_id` through `sunday_location_id` (Many2one to `hr.work.location`)
- An `exceptional_location_id` (Many2one) for ad-hoc location overrides on a given day
- A computed `today_location_id` that returns today's location (considering exceptional overrides)
- A `work_location_name` Char field for display purposes
- `location_type` Char field on `hr.work.location` (values: `home`, `office`, `other`)

### The Conflict `hr_holidays_homeworking` Resolves

Without this module, the presence icon on an employee kanban card would show the **work location** icon (e.g., a home icon for employees working from home) even when the employee has an **approved leave** booked for that day. This is confusing for managers who need to know whether an employee is truly available.

`hr_holidays_homeworking` resolves this by prioritizing the leave state: when an employee has an active approved leave (`current_leave_id` is set), the work location icon is suppressed and replaced by the leave status icon.

## Backend: `hr.employee._compute_presence_icon`

### `models/hr_employee.py`

```python
from odoo import models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _compute_presence_icon(self):
        super()._compute_presence_icon()
        dayfield = self._get_current_day_location_field()
        for employee in self:
            today_employee_location_id = (
                employee.sudo().exceptional_location_id
                or employee[dayfield]
            )
            if employee.is_absent:
                # Employee has an approved leave: show leave icon, not location icon
                employee.hr_icon_display = (
                    f'presence_holiday_{"absent" if employee.hr_presence_state != "present" else "present"}'
                )
                employee.show_hr_icon_display = True
            elif today_employee_location_id:
                # No active leave but has a work location set for today:
                # show the location-type icon (home, office, other)
                employee.hr_icon_display = (
                    f'presence_{today_employee_location_id.location_type}'
                )
                employee.show_hr_icon_display = True
```

**Method analysis:**

1. **`super()._compute_presence_icon()`**: Calls the parent implementation from the `hr` module. The parent sets the default presence icon (green dot for present, red dot for absent) based on the employee's attendance record (`hr.attendance` model).

2. **`self._get_current_day_location_field()`**: A method provided by `hr_homeworking` that returns the Many2one field name corresponding to today's weekday (e.g., `"monday_location_id"` if today is Monday).

3. **`today_employee_location_id` resolution**:
   - If `exceptional_location_id` is set (ad-hoc override for today), use it.
   - Otherwise, fall back to the regular weekday location from the appropriate `*_location_id` field.
   - The `sudo()` call ensures the location field is readable even if the current user lacks full employee record access (the location is a matter of public record for the current day).

4. **`is_absent` check**: The `is_absent` boolean (provided by `hr_holidays` on `hr.employee`) is `True` when the employee has an approved leave covering today. When this is the case, the work location icon is suppressed.

5. **Icon naming convention**:
   - `presence_holiday_present`: Employee is on leave today but their attendance state is "present" (they may have checked in)
   - `presence_holiday_absent`: Employee is on leave and absent
   - `presence_home`: Working from home today (no leave, location type is `home`)
   - `presence_office`: Working from office today
   - `presence_other`: Working from another location today

6. **`show_hr_icon_display = True`**: Forces the icon to be displayed on the kanban card. Without this, the presence icon might be suppressed by other conditions in the parent method.

## Frontend: Owl Component Patches

### `static/src/components/hr_presence_status/hr_presence_status.js`

The module ships JavaScript patches for four Owl components that render the employee presence status on various views:

#### `patchHrPresenceStatus()` -- Color, Icon, and Label patches

Applied to `HrPresenceStatus` and `HrPresenceStatusPrivate` prototypes:

**Color patch:**
```javascript
get color() {
    if (this.value?.includes("holiday")) {
        // Leave states: green if present-on-leave, red if absent
        return `${this.value === "presence_holiday_present" ? "text-success" : "o_icon_employee_absent"}`;
    } else if (this.location) {
        // Work location states: gray by default, green if present, red if absent
        let color = "text-muted";
        if (this.props.record.data.hr_presence_state !== "out_of_working_hour") {
            color = this.props.record.data.hr_presence_state === "present"
                ? "text-success"
                : "o_icon_employee_absent";
        }
        return color;
    }
    return super.color;
}
```

**Icon patch:**
```javascript
get icon() {
    if (this.value?.includes("holiday")) {
        return "fa-plane";  // Airplane icon for leave
    } else if (this.location) {
        switch (this.location) {
            case "home":    return "fa-home";        // Home icon
            case "office":  return "fa-building";    // Building icon
            case "other":   return "fa-map-marker";  // Pin icon
        }
    }
    return super.icon;
}
```

**Label patch (for `HrPresenceStatus`):**
```javascript
get label() {
    if (this.value?.includes("holiday")) {
        // Show: "Annual Leave, back on Jan 6, 2025"
        return _t("%(label)s, back on %(date)s", {
            label: this.options.find(([value, label]) => value === this.value)[1],
            date: this.props.record.data['leave_date_to'].toLocaleString({...})
        });
    } else if (this.location) {
        return this.props.record.data.work_location_name || _t("Unspecified");
    }
    return super.label;
}
```

**Label patch (for `HrPresenceStatusPrivate`):**
```javascript
get label() {
    return this.props.record.data.current_leave_id
        ? _t("%(label)s, back on %(date)s", {
            label: this.props.record.data.current_leave_id.display_name,
            date: this.props.record.data['leave_date_to'].toLocaleString({...})
        })
        : super.label;
}
```

The difference between `HrPresenceStatus` and `HrPresenceStatusPrivate`: the Private version (shown on the employee private details form) displays the current leave's display name (`current_leave_id.display_name`) rather than the translated enum label from the options list.

#### `patchHrPresenceStatusPill()` -- Badge Color patches

Applied to `HrPresenceStatusPill` and `HrPresenceStatusPrivatePill` prototypes (the pill/badge variant of the presence indicator used in list views):

```javascript
get color() {
    if (this.value?.includes("holiday")) {
        return this.value === "presence_holiday_present"
            ? "btn-outline-success"   // Green outline: on leave but present
            : "btn-outline-warning";   // Orange outline: absent on leave
    }
    else if (this.location) {
        let color = "btn-outline-secondary text-muted";  // Gray: default
        if (this.props.record.data.hr_presence_state !== "out_of_working_hour") {
            color = this.props.record.data.hr_presence_state === "present"
                ? "btn-outline-success"   // Green: at work (home or office)
                : "btn-outline-warning";   // Orange: not at work
        }
        return color;
    }
    return super.color;
}
```

## Unit Test

### `static/tests/hr_presence_status.test.js`

```javascript
test("Show Time Off before Work Location", async () => {
    HrEmployee._records = [
        {
            id: 1,
            name: "Employee test",
            work_location_name: "Office 1",
            work_location_type: "office",
            show_hr_icon_display: true,
            hr_icon_display: "presence_holiday_absent",  // On leave
            leave_date_to: "2025-01-06 00:00:00",
        },
    ];
    await mountView({
        resModel: "hr.employee",
        type: "form",
        resId: 1,
        arch: `<form><field name="hr_icon_display" widget="hr_presence_status"/></form>`,
    });

    // Should NOT show the office building icon (holiday takes priority)
    expect("small.fa-building").toHaveCount(0);

    // Should show the airplane icon for leave
    expect("small.fa-plane").toBeVisible();

    // Tooltip should show the return date
    expect("div.o_field_hr_presence_status>div")
        .toHaveAttribute("title", "On leave, back on Jan 6, 2025");

    // Badge should be orange (absent on leave), not green
    expect("div.o_field_hr_presence_status>div").toHaveClass("btn-outline-warning");
});
```

The test validates the key design decision: **leave takes visual priority over work location**. When an employee has `hr_icon_display = "presence_holiday_absent"`, the component renders the airplane icon and orange badge, not the office/home icon.

## Key Business Logic: Leave vs. Work Location Priority

The module implements this decision table for the presence icon:

| Employee State | Icon | Badge Color | Label |
|---------------|------|-------------|-------|
| On approved leave + absent | `fa-plane` | Orange (`btn-outline-warning`) | "Leave Type, back on Date" |
| On approved leave + present | `fa-plane` | Green (`btn-outline-success`) | "Leave Type, back on Date" |
| No leave + work location = home | `fa-home` | Green/Gray | Home address name |
| No leave + work location = office | `fa-building` | Green/Gray | Office name |
| No leave + work location = other | `fa-map-marker` | Green/Gray | Location name |
| No leave + no location set | Default (parent) | Default | Default |

This hierarchy ensures that:
1. **Leave always takes priority** visually -- managers seeing a kanban board of employees can immediately spot who is out.
2. **When not on leave**, the work location icon tells managers where each employee is working today.
3. **The return date** is always shown for employees on leave, helping managers plan coverage.

## Integration with `hr_homeworking` Fields

The `hr_homeworking` module adds these fields to `hr.employee`:

| Field | Type | Description |
|-------|------|-------------|
| `monday_location_id` ... `sunday_location_id` | Many2one (`hr.work.location`) | Scheduled work location per weekday |
| `exceptional_location_id` | Many2one (`hr.work.location`) | Today's override (resets tomorrow) |
| `today_location_id` | Many2one (`hr.work.location`, computed) | Today's effective location |
| `work_location_name` | Char (computed, related) | Display name of today's location |
| `work_location_type` | Char (related) | `home`, `office`, or `other` |

These fields are used by `hr_holidays_homeworking` in the JavaScript patches via `this.location` (which reads `work_location_type` from the record data).

## Related

- [Modules/hr_holidays](hr_holidays.md) -- Leave types, leave requests, allocations, approval workflow
- [Modules/hr_homeworking](hr_homeworking.md) -- Work locations, weekday scheduling, exceptional overrides
- [Modules/HR](HR.md) -- Core `hr.employee` model, `_compute_presence_icon()`, attendance
- [Modules/hr_attendance](hr_attendance.md) -- Attendance check-in/check-out, presence computation
- [Modules/hr_org_chart](hr_org_chart.md) -- Organizational chart showing employee hierarchy
