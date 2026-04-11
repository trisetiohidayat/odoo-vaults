# HR Holidays Homeworking

## Overview
- **Name**: Holidays with Remote Work (`hr_holidays_homeworking`)
- **Category**: Human Resources
- **Depends**: `hr_holidays`, `hr_homeworking`
- **License**: LGPL-3
- **Auto-install**: True

Extends leave management to distinguish between remote work days and actual time off, allowing employees to switch between office and remote work while on leave.

## Models

### `hr.employee.public` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `monday_location_id` through `sunday_location_id` | Many2one | Work location per weekday (from `hr_homeworking`) |
| `today_location_name` | Char | Current location name |

## Key Features
- Allows employees to book leaves on homeworking days
- Integrates with `hr_homeworking` work location model
- Per-weekday work location fields from `hr_homeworking` are exposed on the public employee model

## Related
- [[Modules/hr_holidays]] - Leave management
- [[Modules/hr_homeworking]] - Work location management
