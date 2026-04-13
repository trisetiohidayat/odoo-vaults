# HR Homeworking

## Overview
- **Name**: Remote Work (`hr_homeworking`)
- **Category**: Human Resources/Remote Work
- **Depends**: `hr`
- **Version**: 2.0
- **License**: LGPL-3
- **Auto-install**: True

Manages employee remote/hybrid work by assigning work locations (Office, Home, Other) to each day of the week, with support for exceptional one-day location changes.

## Models

### `hr.employee` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `monday_location_id` through `sunday_location_id` | Many2one | Default work location per weekday |
| `exceptional_location_id` | Many2one | Non-scheduled location for today (computed) |
| `today_location_name` | Char | Name of current location |
| `hr_icon_display` | Selection | Extended with `presence_home`, `presence_office`, `presence_other` |

- `_get_current_day_location_field`: Returns the location field for today
- `_compute_exceptional_location_id`: Looks up today's `hr.employee.location` exception
- `_compute_presence_icon`: Sets icon based on today's effective location
- `_compute_work_location_name`, `_compute_work_location_type`: Compute from today's location
- `get_views`: Replaces placeholder fields in search/list views with today's field

### `hr.employee.public` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `monday_location_id` through `sunday_location_id` | Many2one | Weekday locations |
| `today_location_name` | Char | Current location |

### `hr.employee.location` (Model)
| Field | Type | Description |
|-------|------|-------------|
| `work_location_id` | Many2one | Work location reference |
| `work_location_name` | Char | Location name (related) |
| `work_location_type` | Selection | Location type (related) |
| `employee_id` | Many2one | Employee |
| `date` | Date | Specific date for this exception |
| `day_week_string` | Char | Formatted day of week |

- Constraint: unique(employee_id, date) -- one default + one exception per day

### `hr.work.location` (extends)
- `_unlink_except_used_by_employee`: Prevents deletion of locations in use; unlinks exceptions using it

### `res.users` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `monday_location_id` through `sunday_location_id` | Many2one | User's work locations (related to employee) |

- `_get_employee_fields_to_sync`: Includes DAY fields in user sync
- `_compute_im_status`: Overrides IM status with location type (`presence_home_online`, etc.)

### `res.partner` (extends)
- `_compute_im_status`: Extends partner IM status with employee's current location type

## Key Features
- Assign default work locations (Office/Home/Other) per weekday per employee
- Exceptional one-day location overrides via `hr.employee.location`
- Presence indicators (icons) on employee kanban reflect current location
- IM status suffixed with location type (e.g., `presence_home_online`)
- Location view hacks to group by today's location field

## Related
- [Modules/HR](odoo-18/Modules/hr.md) - Core HR module
